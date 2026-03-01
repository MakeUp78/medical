"""
Processore ottimizzato per rilevamento SOLO puntini bianchi.
Usa MASCHERE ESPANSE delle sopracciglia (non ROI rettangolare).

Versione 2: Ricerca limitata ai pixel dentro le maschere.
"""

import numpy as np
from PIL import Image, ImageDraw
from typing import Dict, List, Tuple, Optional
from collections import deque
import math
import cv2

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False


# ── Costanti formula di scoring calibrata da dot_selector ─────────────────
_MULTI_CONFIGS = [
    {"brightness_percentile": 41, "sat_cap": 37},  # Config A – permissiva
    {"brightness_percentile": 73, "sat_cap": 25},  # Config B – restrittiva
]
_SCORE_NORM_RAW    = 120.1  # media score dei punti corretti
_SCORE_NORM_SIZE   = 138.6  # media size  dei punti corretti
_SCORE_NORM_SOURCE =   2.1  # media source_count dei punti corretti
_MERGE_RADIUS_PX   =  12    # px: raggio entro cui due dot sono lo stesso


class WhiteDotsProcessorV2:
    """
    Processore ottimizzato per il rilevamento di puntini bianchi nelle sopracciglia.
    Usa maschere MediaPipe espanse per limitare la ricerca.
    """

    def __init__(
        self,
        saturation_max: int = 20,
        saturation_min: int = 0,
        value_min: int = 70,
        value_max: int = 95,
        cluster_size_range: Tuple[int, int] = (9, 40),
        clustering_radius: int = 2,
        min_distance: int = 10,
        large_cluster_threshold: int = 35,
        # ── Parametri modalità ADATTIVA ──────────────────────────────────────
        adaptive: bool = True,
        brightness_percentile: int = 75,  # top (100-X)% pixel luminosi = candidati
        sat_cap: int = 45,                # saturazione max assoluta (0-100) per escludere skin
    ):
        """
        Inizializza il processore.

        Modalità ADATTIVA (default, consigliata):
            brightness_percentile: soglia auto-calibrata = percentile X della luminosità
                                   dentro la maschera sopracciglio (75 → top 25% più luminosi).
                                   Invariante all'illuminazione globale.
            sat_cap: cap di saturazione (0-100): esclude skin highlights colorati tenendo
                     i punti bianchi reali (tipicamente S<25%). Default conservativo=45.
            cluster_size_range / min_distance: invariati.

        Modalità LEGACY (adaptive=False):
            saturation_max, saturation_min, value_min, value_max: soglie assolute HSV.
        """
        self.saturation_max = saturation_max
        self.saturation_min = saturation_min
        self.value_min = value_min
        self.value_max = value_max
        self.cluster_min, self.cluster_max = cluster_size_range
        self.clustering_radius = clustering_radius
        self.min_distance = min_distance
        self.large_cluster_threshold = large_cluster_threshold
        self.adaptive = adaptive
        self.brightness_percentile = max(1, min(99, brightness_percentile))
        self.sat_cap = sat_cap

        # MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh if MEDIAPIPE_AVAILABLE else None

    def rgb_to_hsv(self, r: int, g: int, b: int) -> Tuple[int, int, int]:
        """
        Converte valori RGB in HSV.

        Args:
            r, g, b: Valori RGB (0-255)

        Returns:
            Tuple[int, int, int]: Valori HSV (H: 0-360, S: 0-100, V: 0-100)
        """
        r, g, b = r / 255.0, g / 255.0, b / 255.0

        max_val = max(r, g, b)
        min_val = min(r, g, b)
        diff = max_val - min_val

        # Hue
        if diff == 0:
            h = 0
        elif max_val == r:
            h = ((g - b) / diff) % 6
        elif max_val == g:
            h = (b - r) / diff + 2
        else:
            h = (r - g) / diff + 4

        h = round(h * 60)
        if h < 0:
            h += 360

        # Saturation
        s = 0 if max_val == 0 else round((diff / max_val) * 100)

        # Value
        v = round(max_val * 100)

        return h, s, v

    def is_white_pixel(self, r: int, g: int, b: int) -> bool:
        """
        Determina se un pixel è bianco secondo i parametri configurati.

        Args:
            r, g, b: Valori RGB del pixel

        Returns:
            bool: True se il pixel è considerato bianco
        """
        h, s, v = self.rgb_to_hsv(r, g, b)

        # Pixel bianco: saturazione nel range [min, max], luminosità nel range [min, max]
        return (self.saturation_min <= s <= self.saturation_max and
                self.value_min <= v <= self.value_max)

    def get_face_landmarks(self, image_np: np.ndarray) -> Optional[object]:
        """
        Rileva i landmark facciali usando MediaPipe.

        Args:
            image_np: Immagine numpy in formato BGR

        Returns:
            Landmarks facciali o None se non rilevati
        """
        if not MEDIAPIPE_AVAILABLE or self.mp_face_mesh is None:
            return None

        with self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        ) as face_mesh:
            rgb_image = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_image)

            if results.multi_face_landmarks:
                return results.multi_face_landmarks[0]

        return None

    def generate_left_eyebrow_mask(
        self,
        landmarks,
        image_shape: Tuple[int, int],
        expand_factor: float = 0.15
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Genera maschera per sopracciglio sinistro con espansione.

        Args:
            landmarks: Landmarks MediaPipe
            image_shape: (height, width) dell'immagine
            expand_factor: Fattore di espansione della maschera

        Returns:
            Tuple[np.ndarray, np.ndarray]: (maschera binaria, poligono punti)
        """
        h, w = image_shape

        # Indici landmarks sopracciglio sinistro
        left_eyebrow_indices = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]

        points = np.array([
            (int(landmarks.landmark[i].x * w), int(landmarks.landmark[i].y * h))
            for i in left_eyebrow_indices
        ], dtype=np.int32)

        # Calcola bounding box per determinare l'espansione
        bbox = cv2.boundingRect(points)
        characteristic_size = max(bbox[2], bbox[3])
        offset_pixels = int(characteristic_size * expand_factor)

        # Crea maschera base e espandila
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [points], 255)

        kernel = np.ones((offset_pixels * 2 + 1, offset_pixels * 2 + 1), np.uint8)
        expanded_mask = cv2.dilate(mask, kernel, iterations=1)

        # Estrai contorno espanso
        contours, _ = cv2.findContours(expanded_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            expanded_polygon = max(contours, key=cv2.contourArea).squeeze()
        else:
            expanded_polygon = points

        return expanded_mask, expanded_polygon

    def generate_right_eyebrow_mask(
        self,
        landmarks,
        image_shape: Tuple[int, int],
        expand_factor: float = 0.15
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Genera maschera per sopracciglio destro con espansione.

        Args:
            landmarks: Landmarks MediaPipe
            image_shape: (height, width) dell'immagine
            expand_factor: Fattore di espansione della maschera

        Returns:
            Tuple[np.ndarray, np.ndarray]: (maschera binaria, poligono punti)
        """
        h, w = image_shape

        # Indici landmarks sopracciglio destro
        right_eyebrow_indices = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]

        points = np.array([
            (int(landmarks.landmark[i].x * w), int(landmarks.landmark[i].y * h))
            for i in right_eyebrow_indices
        ], dtype=np.int32)

        # Calcola bounding box per determinare l'espansione
        bbox = cv2.boundingRect(points)
        characteristic_size = max(bbox[2], bbox[3])
        offset_pixels = int(characteristic_size * expand_factor)

        # Crea maschera base e espandila
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [points], 255)

        kernel = np.ones((offset_pixels * 2 + 1, offset_pixels * 2 + 1), np.uint8)
        expanded_mask = cv2.dilate(mask, kernel, iterations=1)

        # Estrai contorno espanso
        contours, _ = cv2.findContours(expanded_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            expanded_polygon = max(contours, key=cv2.contourArea).squeeze()
        else:
            expanded_polygon = points

        return expanded_mask, expanded_polygon

    def cluster_pixels(self, pixels: List[Dict]) -> List[List[Dict]]:
        """
        Raggruppa i pixel bianchi in cluster usando algoritmo BFS.

        Args:
            pixels: Lista di pixel bianchi con coordinate e informazioni colore

        Returns:
            List[List[Dict]]: Lista di cluster, ogni cluster è una lista di pixel
        """
        if not pixels:
            return []

        # Crea dizionario per lookup veloce
        pixel_dict = {}
        for p in pixels:
            key = (p['x'], p['y'])
            pixel_dict[key] = p

        visited = set()
        clusters = []

        for pixel in pixels:
            key = (pixel['x'], pixel['y'])
            if key in visited:
                continue

            # BFS per trovare tutti i pixel connessi
            cluster = []
            queue = deque([pixel])

            while queue:
                current = queue.popleft()
                current_key = (current['x'], current['y'])

                if current_key in visited:
                    continue

                visited.add(current_key)
                cluster.append(current)

                # Cerca pixel adiacenti nel raggio configurato
                for dx in range(-self.clustering_radius, self.clustering_radius + 1):
                    for dy in range(-self.clustering_radius, self.clustering_radius + 1):
                        if dx == 0 and dy == 0:
                            continue
                        neighbor_key = (current['x'] + dx, current['y'] + dy)
                        if neighbor_key in pixel_dict and neighbor_key not in visited:
                            queue.append(pixel_dict[neighbor_key])

            # Filtra per dimensione cluster
            if self.cluster_min <= len(cluster) <= self.cluster_max:
                clusters.append(cluster)

        return clusters

    def calculate_compactness(self, cluster: List[Dict]) -> float:
        """
        Calcola la compattezza di un cluster (quanto è circolare vs disperso).

        Args:
            cluster: Lista di pixel del cluster

        Returns:
            float: Valore di compattezza (più basso = più compatto)
        """
        if len(cluster) < 2:
            return 0.0

        # Calcola centroide
        avg_x = sum(p['x'] for p in cluster) / len(cluster)
        avg_y = sum(p['y'] for p in cluster) / len(cluster)

        # Calcola deviazione standard dalla posizione del centroide
        variance_x = sum((p['x'] - avg_x) ** 2 for p in cluster) / len(cluster)
        variance_y = sum((p['y'] - avg_y) ** 2 for p in cluster) / len(cluster)
        std_dev = math.sqrt(variance_x + variance_y)

        # Compattezza normalizzata per dimensione
        compactness = std_dev / math.sqrt(len(cluster))

        return compactness

    def split_large_cluster(self, cluster: List[Dict]) -> List[Dict]:
        """
        Per cluster grandi, usa il centroide invece di tutti i pixel.

        Args:
            cluster: Lista di pixel del cluster

        Returns:
            List[Dict]: Lista con un singolo punto (centroide) per cluster grandi
        """
        if len(cluster) <= self.large_cluster_threshold:
            return cluster

        # Calcola centroide
        avg_x = sum(p['x'] for p in cluster) / len(cluster)
        avg_y = sum(p['y'] for p in cluster) / len(cluster)

        # Media dei valori HSV
        avg_h = sum(p.get('h', 0) for p in cluster) / len(cluster)
        avg_s = sum(p.get('s', 0) for p in cluster) / len(cluster)
        avg_v = sum(p.get('v', 0) for p in cluster) / len(cluster)

        return [{
            'x': int(avg_x),
            'y': int(avg_y),
            'h': int(avg_h),
            's': int(avg_s),
            'v': int(avg_v),
            'is_centroid': True
        }]

    def filter_close_dots(self, dots: List[Dict]) -> List[Dict]:
        """
        Filtra puntini troppo vicini, mantiene solo quello con score più alto.

        Args:
            dots: Lista di puntini con coordinate e score

        Returns:
            Lista filtrata di puntini
        """
        if len(dots) <= 1:
            return dots

        # Ordina per score decrescente
        sorted_dots = sorted(dots, key=lambda d: d.get('score', d['size']), reverse=True)

        filtered = []
        for dot in sorted_dots:
            # Controlla se è troppo vicino a puntini già accettati
            too_close = False
            for accepted in filtered:
                distance = math.sqrt(
                    (dot['x'] - accepted['x']) ** 2 +
                    (dot['y'] - accepted['y']) ** 2
                )
                if distance < self.min_distance:
                    too_close = True
                    break

            if not too_close:
                filtered.append(dot)

        return filtered

    # ─────────────────────────────────────────────────────────────────────────
    # MODALITÀ ADATTIVA (default)
    # ─────────────────────────────────────────────────────────────────────────
    def _single_pass_raw(
        self,
        v_ch: np.ndarray,
        s_ch: np.ndarray,
        combined_mask: np.ndarray,
        brightness_percentile: int,
        sat_cap: float,
    ) -> Tuple[List[Dict], int]:
        """
        Singolo pass di detection con parametri espliciti.
        Ritorna lista dot grezzi (score = area × mean_v/255) e totale pixel luminosi.
        """
        ys, xs = np.where(combined_mask > 0)
        if len(ys) < 10:
            return [], 0

        v_in_mask = v_ch[ys, xs]
        thresh_v = float(np.percentile(v_in_mask, brightness_percentile))
        thresh_s = sat_cap / 100.0 * 255.0

        bright = np.zeros(v_ch.shape, dtype=np.uint8)
        bright[(v_ch > thresh_v) & (s_ch <= thresh_s) & (combined_mask > 0)] = 255

        n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            bright, connectivity=8
        )
        total_bright = int(np.sum(bright > 0))

        dots = []
        for lbl in range(1, n_labels):
            area = int(stats[lbl, cv2.CC_STAT_AREA])
            if area < self.cluster_min or area > self.cluster_max:
                continue
            cx = float(centroids[lbl, 0])
            cy = float(centroids[lbl, 1])
            clust_mask = (labels == lbl)
            mean_v = float(np.mean(v_ch[clust_mask]))
            mean_s = float(np.mean(s_ch[clust_mask]))
            score = area * (mean_v / 255.0)
            dots.append({
                'x': int(round(cx)),
                'y': int(round(cy)),
                'size': area,
                'score': round(score, 2),
                'compactness': 0.0,
                'v': int(round(mean_v / 255.0 * 100)),
                's': int(round(mean_s / 255.0 * 100)),
                'h': 0,
            })

        return dots, total_bright

    def _detect_adaptive(
        self,
        img_array: np.ndarray,
        combined_mask: np.ndarray,
    ) -> Tuple[List[Dict], int]:
        """
        Rilevamento adattivo multi-config con scoring calibrato.

        Esegue la detection con i parametri utente + 2 config aggiuntive per
        calcolare il source_count (quante config rilevano lo stesso punto).
        Formula finale: (raw_score/NORM_RAW) × (size/NORM_SIZE) × (source_count/NORM_SOURCE)

        Returns:
            (dots_list, total_bright_pixels)
        """
        # Canale V e S in HSV (calcolati una volta sola per tutti i pass)
        hsv  = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
        v_ch = hsv[:, :, 2].astype(np.float32)  # 0-255
        s_ch = hsv[:, :, 1].astype(np.float32)  # 0-255

        # ── Pass primario con parametri utente ────────────────────────────
        primary_dots, total_bright = self._single_pass_raw(
            v_ch, s_ch, combined_mask,
            self.brightness_percentile, self.sat_cap
        )

        # ── Pass aggiuntivi per calcolare source_count ────────────────────
        extra_runs: List[List[Dict]] = []
        for cfg in _MULTI_CONFIGS:
            extra, _ = self._single_pass_raw(
                v_ch, s_ch, combined_mask,
                cfg["brightness_percentile"], cfg["sat_cap"]
            )
            extra_runs.append(extra)

        # ── Calcola source_count e applica nuova formula ──────────────────
        for dot in primary_dots:
            sc = 1  # trovato almeno nel pass primario
            for run in extra_runs:
                for od in run:
                    dx = dot['x'] - od['x']
                    dy = dot['y'] - od['y']
                    if math.sqrt(dx * dx + dy * dy) < _MERGE_RADIUS_PX:
                        sc += 1
                        break

            raw_score = dot['score']   # area × mean_v/255
            sz        = dot['size']    # area
            # Formula calibrata da dot_selector
            dot['score'] = round(
                (raw_score / _SCORE_NORM_RAW)
                * (sz       / _SCORE_NORM_SIZE)
                * (sc       / _SCORE_NORM_SOURCE),
                4
            )
            dot['source_count'] = sc

        return primary_dots, total_bright

    # ─────────────────────────────────────────────────────────────────────────

    def detect_white_dots(self, pil_image: Image.Image) -> Dict:
        """
        Rileva i puntini bianchi nelle sopracciglia usando maschere MediaPipe.

        Args:
            pil_image: Immagine PIL da analizzare

        Returns:
            Dict: Risultati del rilevamento con puntini, statistiche e metadati
        """
        # Converti in numpy BGR per MediaPipe
        img_array = np.array(pil_image)
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        elif img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        elif img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        height, width = img_array.shape[:2]

        # Rileva landmarks facciali
        landmarks = self.get_face_landmarks(img_array)

        if landmarks is None:
            return {
                'error': 'Volto non rilevato. Impossibile generare maschere sopracciglia.',
                'dots': [],
                'total_white_pixels': 0
            }

        # Genera maschere sopracciglia espanse
        left_mask, left_polygon = self.generate_left_eyebrow_mask(
            landmarks, (height, width)
        )
        right_mask, right_polygon = self.generate_right_eyebrow_mask(
            landmarks, (height, width)
        )

        # Combina maschere
        combined_mask = cv2.bitwise_or(left_mask, right_mask)

        # ── Scelta strategia di rilevamento ───────────────────────────────
        if self.adaptive:
            # ── MODALITÀ ADATTIVA: percentile luminosità, nessun tuning HSV ─
            dots, total_white_pixels = self._detect_adaptive(img_array, combined_mask)
        else:
            # ── MODALITÀ LEGACY: soglie HSV assolute ─────────────────────
            rgb_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
            white_pixels = []
            mask_coords = np.where(combined_mask > 0)

            for y, x in zip(mask_coords[0], mask_coords[1]):
                r, g, b = rgb_array[y, x]
                if self.is_white_pixel(r, g, b):
                    h, s, v = self.rgb_to_hsv(r, g, b)
                    white_pixels.append({'x': int(x), 'y': int(y), 'r': int(r),
                                         'g': int(g), 'b': int(b), 'h': h, 's': s, 'v': v})

            clusters = self.cluster_pixels(white_pixels)
            total_white_pixels = len(white_pixels)
            dots = []
            for cluster in clusters:
                if len(cluster) > self.large_cluster_threshold:
                    cluster = self.split_large_cluster(cluster)
                avg_x = sum(p['x'] for p in cluster) / len(cluster)
                avg_y = sum(p['y'] for p in cluster) / len(cluster)
                avg_s = sum(p.get('s', 0) for p in cluster) / len(cluster)
                avg_v = sum(p.get('v', 0) for p in cluster) / len(cluster)
                avg_h = sum(p.get('h', 0) for p in cluster) / len(cluster)
                compactness = self.calculate_compactness(cluster)
                size = len(cluster)
                score = size * (1.0 / (compactness + 0.1)) * (avg_v / 100)
                if compactness >= 1.0:
                    continue
                dots.append({'x': int(round(avg_x)), 'y': int(round(avg_y)),
                             'size': size, 'score': score,
                             'compactness': round(compactness, 3),
                             'h': int(round(avg_h)), 's': int(round(avg_s)),
                             'v': int(round(avg_v))})

        # Filtra puntini troppo vicini e ordina per score
        dots = self.filter_close_dots(dots)
        dots = sorted(dots, key=lambda d: d['score'], reverse=True)

        return {
            'dots': dots,
            'total_white_pixels': total_white_pixels,
            'total_clusters': len(dots),
            'image_size': (width, height),
            'parameters': {
                'adaptive': self.adaptive,
                'brightness_percentile': self.brightness_percentile,
                'sat_cap': self.sat_cap,
                'saturation_max': self.saturation_max,
                'saturation_min': self.saturation_min,
                'value_min': self.value_min,
                'value_max': self.value_max,
                'cluster_size_range': (self.cluster_min, self.cluster_max),
                'clustering_radius': self.clustering_radius,
                'min_distance': self.min_distance
            },
            'left_polygon': left_polygon,
            'right_polygon': right_polygon
        }


# Funzione di test del modulo
if __name__ == "__main__":
    print("Test del modulo WhiteDotsProcessorV2")
    print("=" * 50)
    print("Esempio d'uso:")
    print("""
    from white_dots_processor_v2 import WhiteDotsProcessorV2
    from PIL import Image

    # Carica immagine
    image = Image.open("path/to/image.jpg")

    # Inizializza processore
    processor = WhiteDotsProcessorV2(
        saturation_max=30,
        value_min=70,
        value_max=95,
        cluster_size_range=(9, 40),
        clustering_radius=2,
        min_distance=10
    )

    # Rileva puntini bianchi
    results = processor.detect_white_dots(image)

    if 'error' not in results:
        print(f"Puntini rilevati: {len(results['dots'])}")
        for dot in results['dots']:
            print(f"  - ({dot['x']}, {dot['y']}) size={dot['size']} score={dot['score']:.2f}")
    """)
