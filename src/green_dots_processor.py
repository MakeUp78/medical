#!/usr/bin/env python3
"""
Modulo per il rilevamento di puntini verdi e generazione di overlay trasparenti.
Questo modulo può essere importato in altri script per elaborare immagini senza interfaccia grafica.

Funzionalità principali:
- Rilevamento puntini verdi usando analisi HSV
- Divisione dei puntini in gruppi sinistro (Sx) e destro (Dx)
- Generazione di overlay trasparenti con i perimetri
- Calcolo delle coordinate e statistiche delle forme

Dipendenze: opencv-python, numpy, pillow

Esempio d'uso:
    from src.green_dots_processor import GreenDotsProcessor

    processor = GreenDotsProcessor()
    results = processor.process_image("path/to/image.jpg")
    overlay = processor.generate_overlay(results['image_size'])
"""

import cv2
import numpy as np
from PIL import Image, ImageDraw, ExifTags
import math
from typing import Dict, List, Tuple, Optional

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False


class GreenDotsProcessor:
    """
    Processore per il rilevamento di puntini verdi e generazione di forme geometriche.
    """

    def __init__(
        self,
        hue_range: Tuple[int, int] = (125, 185),
        saturation_min: int = 50,
        value_range: Tuple[int, int] = (15, 55),
        cluster_size_range: Tuple[int, int] = (4, 170),
        clustering_radius: int = 3,
    ):
        """
        Inizializza il processore con parametri configurabili.

        Args:
            hue_range: Range di tonalità HSV per il verde (min, max)
            saturation_min: Saturazione minima per considerare un pixel verde
            value_range: Range di luminosità HSV (min, max)
            cluster_size_range: Range dimensioni cluster validi (min, max pixel)
            clustering_radius: Raggio per il clustering dei pixel adiacenti
        """
        self.hue_min, self.hue_max = hue_range
        self.saturation_min = saturation_min
        self.value_min, self.value_max = value_range
        self.cluster_min, self.cluster_max = cluster_size_range
        self.clustering_radius = clustering_radius

        # Risultati dell'ultimo processing
        self.last_results = None
        self.left_dots = []
        self.right_dots = []

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

    def is_green_pixel(self, r: int, g: int, b: int) -> bool:
        """
        Determina se un pixel è verde o bianco secondo i parametri configurati.

        Args:
            r, g, b: Valori RGB del pixel

        Returns:
            bool: True se il pixel è considerato verde o bianco
        """
        h, s, v = self.rgb_to_hsv(r, g, b)
        
        # Check per puntini verdi (originale)
        is_green = (
            self.hue_min <= h <= self.hue_max
            and s >= self.saturation_min
            and self.value_min <= v <= self.value_max
        )
        
        # Check per puntini bianchi (luminosità minima 78)
        is_white = (s <= 20 and 78 <= v <= 95)
        
        return is_green or is_white

    def cluster_pixels(self, pixels: List[Dict]) -> List[List[Dict]]:
        """
        Raggruppa i pixel verdi in cluster usando algoritmo BFS.

        Args:
            pixels: Lista di pixel verdi con coordinate e informazioni colore

        Returns:
            List[List[Dict]]: Lista di cluster, ogni cluster è una lista di pixel
        """
        visited = set()
        clusters = []

        for pixel in pixels:
            key = f"{pixel['x']},{pixel['y']}"
            if key in visited:
                continue

            # Trova tutti i pixel connessi (BFS)
            cluster = []
            queue = [pixel]

            while queue:
                current = queue.pop(0)
                current_key = f"{current['x']},{current['y']}"

                if current_key in visited:
                    continue

                visited.add(current_key)
                cluster.append(current)

                # Cerca pixel adiacenti
                for neighbor in pixels:
                    neighbor_key = f"{neighbor['x']},{neighbor['y']}"
                    if neighbor_key not in visited:
                        dx = abs(current["x"] - neighbor["x"])
                        dy = abs(current["y"] - neighbor["y"])
                        if (
                            dx <= self.clustering_radius
                            and dy <= self.clustering_radius
                        ):
                            queue.append(neighbor)

            if self.cluster_min <= len(cluster) <= self.cluster_max:
                clusters.append(cluster)

        return clusters

    def detect_green_dots(self, image: Image.Image) -> Dict:
        """
        Rileva i puntini verdi in un'immagine.

        Args:
            image: Immagine PIL da analizzare

        Returns:
            Dict: Risultati del rilevamento con puntini, statistiche e metadati
        """
        # Converti l'immagine PIL in numpy array
        img_array = np.array(image)
        height, width = img_array.shape[:2]

        green_pixels = []

        # Scansiona tutti i pixel
        for y in range(height):
            for x in range(width):
                r, g, b = img_array[y, x][:3]

                if self.is_green_pixel(r, g, b):
                    h, s, v = self.rgb_to_hsv(r, g, b)
                    green_pixels.append(
                        {"x": x, "y": y, "r": r, "g": g, "b": b, "h": h, "s": s, "v": v}
                    )

        # Raggruppa i pixel verdi in cluster
        clusters = self.cluster_pixels(green_pixels)

        # Calcola centroidi per ogni cluster
        dots = []
        for cluster in clusters:
            avg_x = sum(p["x"] for p in cluster) / len(cluster)
            avg_y = sum(p["y"] for p in cluster) / len(cluster)
            
            # Calcola score del cluster (basato su dimensione e saturazione media)
            avg_saturation = sum(p["s"] for p in cluster) / len(cluster)
            score = len(cluster) * (1 + avg_saturation / 100)
            
            # FILTRA: puntini bianchi (bassa saturazione) devono avere almeno 3 pixel
            if avg_saturation <= 20 and len(cluster) < 3:
                continue  # Scarta puntino bianco troppo piccolo
            
            # FILTRA: esclude puntini con bordi non definiti (pixel dispersi)
            # Calcola deviazione standard dalla posizione del centroide
            variance_x = sum((p["x"] - avg_x)**2 for p in cluster) / len(cluster)
            variance_y = sum((p["y"] - avg_y)**2 for p in cluster) / len(cluster)
            std_dev = math.sqrt(variance_x + variance_y)
            
            # Se deviazione standard troppo alta rispetto alla dimensione, bordi non definiti
            compactness = std_dev / math.sqrt(len(cluster))
            
            # Soglia più stringente per puntini BIANCHI (devono essere più compatti)
            if avg_saturation <= 20:
                if compactness >= 1.0:  # Puntini bianchi devono essere estremamente compatti (< 1.0)
                    continue
            else:
                if compactness > 2.5:  # Puntini verdi possono essere meno compatti
                    continue

            dots.append(
                {
                    "x": round(avg_x),
                    "y": round(avg_y),
                    "size": len(cluster),
                    "score": score,
                    "pixels": cluster,
                }
            )

        # Filtra puntini troppo vicini, mantieni solo quello con score più alto
        # Distanza ridotta a 10px per permettere punti più vicini
        dots = self.filter_close_dots(dots, min_distance=10)

        results = {
            "dots": dots,
            "total_dots": len(dots),
            "total_green_pixels": len(green_pixels),
            "image_size": (width, height),
            "parameters": {
                "hue_range": (self.hue_min, self.hue_max),
                "saturation_min": self.saturation_min,
                "value_range": (self.value_min, self.value_max),
            },
        }

        self.last_results = results
        return results

    def filter_close_dots(self, dots: List[Dict], min_distance: int = 15) -> List[Dict]:
        """
        Filtra puntini troppo vicini, mantiene solo quello con score più alto.
        
        Args:
            dots: Lista di puntini con coordinate e score
            min_distance: Distanza minima in pixel tra puntini
            
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
                distance = math.sqrt((dot['x'] - accepted['x'])**2 + (dot['y'] - accepted['y'])**2)
                if distance < min_distance:
                    too_close = True
                    break
            
            if not too_close:
                filtered.append(dot)
        
        return filtered

    def divide_dots_by_vertical_center(
        self, dots: List[Dict], image_width: int
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Divide i puntini in due gruppi basati sulla divisione verticale centrale.

        Args:
            dots: Lista dei puntini rilevati
            image_width: Larghezza dell'immagine in pixel

        Returns:
            Tuple[List[Dict], List[Dict]]: (puntini_sinistra, puntini_destra)
        """
        middle_x = image_width // 2

        left_dots = [dot for dot in dots if dot["x"] < middle_x]
        right_dots = [dot for dot in dots if dot["x"] >= middle_x]

        self.left_dots = left_dots
        self.right_dots = right_dots

        return left_dots, right_dots

    # ========== FUNZIONI DI PREPROCESSING ==========
    
    def _expand_polygon_with_offset(self, points, offset_pixels, image_shape):
        """Espande un poligono applicando un offset verso l'esterno."""
        points = np.array(points, dtype=np.int32)
        mask = np.zeros(image_shape, dtype=np.uint8)
        cv2.fillPoly(mask, [points], 255)
        kernel = np.ones((int(offset_pixels * 2) + 1, int(offset_pixels * 2) + 1), np.uint8)
        dilated_mask = cv2.dilate(mask, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            expanded_contour = max(contours, key=cv2.contourArea)
            return expanded_contour.squeeze()
        else:
            return points

    def _get_eyebrow_masks(self, image_np):
        """Rileva sopracciglia usando MediaPipe Face Mesh e genera maschere poligonali."""
        if not MEDIAPIPE_AVAILABLE:
            return None, None, None, None
            
        h, w = image_np.shape[:2]
        mp_face_mesh = mp.solutions.face_mesh

        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        ) as face_mesh:
            rgb_image = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_image)

            if not results.multi_face_landmarks:
                y_start = int(h * 0.10)
                y_end = int(h * 0.35)
                left_bbox = (int(w * 0.10), y_start, int(w * 0.48), y_end)
                right_bbox = (int(w * 0.52), y_start, int(w * 0.90), y_end)
                return None, None, left_bbox, right_bbox

            landmarks = results.multi_face_landmarks[0]
            left_eyebrow = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
            right_eyebrow = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]

            left_points = [(int(landmarks.landmark[i].x * w), int(landmarks.landmark[i].y * h))
                           for i in left_eyebrow]
            right_points = [(int(landmarks.landmark[i].x * w), int(landmarks.landmark[i].y * h))
                            for i in right_eyebrow]

            left_bbox_temp = cv2.boundingRect(np.array(left_points, dtype=np.int32))
            characteristic_size = max(left_bbox_temp[2], left_bbox_temp[3])
            offset_pixels = characteristic_size * 0.15

            left_polygon = self._expand_polygon_with_offset(left_points, offset_pixels, (h, w))
            right_polygon = self._expand_polygon_with_offset(right_points, offset_pixels, (h, w))

            left_bbox = cv2.boundingRect(left_polygon)
            right_bbox = cv2.boundingRect(right_polygon)

            left_bbox = (left_bbox[0], left_bbox[1], left_bbox[0] + left_bbox[2], left_bbox[1] + left_bbox[3])
            right_bbox = (right_bbox[0], right_bbox[1], right_bbox[0] + right_bbox[2], right_bbox[1] + right_bbox[3])

            return left_polygon, right_polygon, left_bbox, right_bbox

    def _fix_image_orientation(self, pil_image):
        """Corregge orientamento immagine usando dati EXIF."""
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break

            exif = pil_image._getexif()
            if exif is not None:
                orientation_value = exif.get(orientation)

                if orientation_value == 3:
                    pil_image = pil_image.rotate(180, expand=True)
                elif orientation_value == 6:
                    pil_image = pil_image.rotate(270, expand=True)
                elif orientation_value == 8:
                    pil_image = pil_image.rotate(90, expand=True)
        except:
            pass

        return pil_image

    def preprocess_for_detection(self, pil_image, target_width=1400):
        """
        Preprocessa immagine per migliorare rilevamento green dots:
        scala, rileva maschere sopracciglia, crea output con ritagli su bianco.

        Args:
            pil_image: Immagine PIL da preprocessare
            target_width: Larghezza target per scaling

        Returns:
            Tuple: (immagine_preprocessata, immagine_originale, fattore_scala)
        """
        if not MEDIAPIPE_AVAILABLE:
            return pil_image, pil_image, 1.0
            
        pil_image_original = self._fix_image_orientation(pil_image)
        
        scale_factor = target_width / pil_image_original.width if pil_image_original.width > target_width else 1.0
        
        if scale_factor < 1.0:
            new_width = int(pil_image_original.width * scale_factor)
            new_height = int(pil_image_original.height * scale_factor)
            pil_image_scaled = pil_image_original.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            pil_image_scaled = pil_image_original.copy()

        image_np = cv2.cvtColor(np.array(pil_image_scaled), cv2.COLOR_RGB2BGR)

        left_polygon, right_polygon, left_bbox, right_bbox = self._get_eyebrow_masks(image_np)

        if left_bbox is None:
            return pil_image_scaled, pil_image_original, scale_factor

        result = np.ones_like(image_np) * 255
        
        if left_polygon is not None:
            x_min, y_min, x_max, y_max = left_bbox
            left_region = image_np[y_min:y_max, x_min:x_max].copy()
            
            left_mask = np.zeros(image_np.shape[:2], dtype=np.uint8)
            cv2.fillPoly(left_mask, [left_polygon], 255)
            left_mask_region = left_mask[y_min:y_max, x_min:x_max]
            
            result[y_min:y_max, x_min:x_max][left_mask_region == 255] = left_region[left_mask_region == 255]
            
            x_min, y_min, x_max, y_max = right_bbox
            right_region = image_np[y_min:y_max, x_min:x_max].copy()
            
            right_mask = np.zeros(image_np.shape[:2], dtype=np.uint8)
            cv2.fillPoly(right_mask, [right_polygon], 255)
            right_mask_region = right_mask[y_min:y_max, x_min:x_max]
            
            result[y_min:y_max, x_min:x_max][right_mask_region == 255] = right_region[right_mask_region == 255]
        else:
            x_min, y_min, x_max, y_max = left_bbox
            left_region = image_np[y_min:y_max, x_min:x_max].copy()
            result[y_min:y_max, x_min:x_max] = left_region
            
            x_min, y_min, x_max, y_max = right_bbox
            right_region = image_np[y_min:y_max, x_min:x_max].copy()
            result[y_min:y_max, x_min:x_max] = right_region
        
        result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        result_pil = Image.fromarray(result_rgb)
        
        return result_pil, pil_image_original, scale_factor

    # ========== FINE FUNZIONI DI PREPROCESSING ==========

    def sort_points_by_proximity(self, points: List[Dict]) -> List[Dict]:
        """
        Ordina i punti per prossimità usando algoritmo Nearest Neighbor.

        Args:
            points: Lista di punti da ordinare

        Returns:
            List[Dict]: Punti ordinati per formare un percorso ottimale
        """
        if len(points) < 3:
            return points

        sorted_points = [points[0]]
        remaining = points[1:]

        while remaining:
            current = sorted_points[-1]

            # Trova il punto più vicino
            min_distance = float("inf")
            nearest_index = 0

            for i, point in enumerate(remaining):
                dx = point["x"] - current["x"]
                dy = point["y"] - current["y"]
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < min_distance:
                    min_distance = distance
                    nearest_index = i

            sorted_points.append(remaining.pop(nearest_index))

        return sorted_points

    def calculate_eyebrow_bounding_box(self, dots: List[Dict], expand_factor: float = 0.5) -> Tuple[int, int, int, int]:
        """
        Calcola il bounding box dei punti del sopracciglio e lo allarga del fattore specificato.
        
        Args:
            dots: Lista dei punti verdi del sopracciglio
            expand_factor: Fattore di allargamento del bounding box (0.5 = 50%)
            
        Returns:
            Tuple[int, int, int, int]: (x_min, y_min, x_max, y_max) del bounding box allargato
        """
        if not dots:
            return (0, 0, 0, 0)
            
        # Trova coordinate minime e massime
        x_coords = [dot["x"] for dot in dots]
        y_coords = [dot["y"] for dot in dots]
        
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        # Calcola dimensioni originali
        width = x_max - x_min
        height = y_max - y_min
        
        # Calcola l'espansione
        expand_width = int(width * expand_factor / 2)
        expand_height = int(height * expand_factor / 2)
        
        # Applica l'espansione
        x_min_expanded = max(0, x_min - expand_width)
        y_min_expanded = max(0, y_min - expand_height)
        x_max_expanded = x_max + expand_width
        y_max_expanded = y_max + expand_height
        
        return (x_min_expanded, y_min_expanded, x_max_expanded, y_max_expanded)

    def get_left_eyebrow_bbox(self, expand_factor: float = 0.5) -> Tuple[int, int, int, int]:
        """
        Restituisce il bounding box del sopracciglio sinistro.
        
        Args:
            expand_factor: Fattore di allargamento del bounding box
            
        Returns:
            Tuple[int, int, int, int]: Bounding box del sopracciglio sinistro
        """
        return self.calculate_eyebrow_bounding_box(self.left_dots, expand_factor)
        
    def get_right_eyebrow_bbox(self, expand_factor: float = 0.5) -> Tuple[int, int, int, int]:
        """
        Restituisce il bounding box del sopracciglio destro.
        
        Args:
            expand_factor: Fattore di allargamento del bounding box
            
        Returns:
            Tuple[int, int, int, int]: Bounding box del sopracciglio destro
        """
        return self.calculate_eyebrow_bounding_box(self.right_dots, expand_factor)

    def sort_points_convex_hull(self, points: List[Dict]) -> List[Dict]:
        """
        Ordina i punti usando algoritmo Convex Hull (Graham Scan).

        Args:
            points: Lista di punti da ordinare

        Returns:
            List[Dict]: Punti ordinati secondo l'ordine del convex hull
        """
        if len(points) < 3:
            return points

        # Trova il punto più in basso
        bottom_point = min(points, key=lambda p: (p["y"], p["x"]))

        def angle_distance(p):
            dx = p["x"] - bottom_point["x"]
            dy = p["y"] - bottom_point["y"]
            angle = math.atan2(dy, dx)
            distance = math.sqrt(dx * dx + dy * dy)
            return angle, distance

        other_points = [p for p in points if p != bottom_point]
        other_points.sort(key=angle_distance)

        return [bottom_point] + other_points

    def calculate_polygon_area(self, points: List[Dict]) -> float:
        """
        Calcola l'area di un poligono usando la formula Shoelace.

        Args:
            points: Lista di punti del poligono

        Returns:
            float: Area del poligono in pixel quadrati
        """
        if len(points) < 3:
            return 0

        area = 0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            area += points[i]["x"] * points[j]["y"]
            area -= points[j]["x"] * points[i]["y"]

        return abs(area) / 2

    def calculate_perimeter(self, points: List[Dict]) -> float:
        """
        Calcola il perimetro di un poligono.

        Args:
            points: Lista di punti del poligono

        Returns:
            float: Perimetro del poligono in pixel
        """
        if len(points) < 2:
            return 0

        perimeter = 0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            dx = points[j]["x"] - points[i]["x"]
            dy = points[j]["y"] - points[i]["y"]
            perimeter += math.sqrt(dx * dx + dy * dy)

        return perimeter

    def sort_points_anatomical(self, points: List[Dict], is_left: bool) -> List[Dict]:
        """
        Ordina i punti in base a criteri anatomici fissi per garantire mappatura consistente.
        
        Criteri di identificazione:
        1. Coppia B (LB/RB): Punti più esterni
           - LB: x minima (più a sinistra)
           - RB: x massima (più a destra)
        
        2. Coppia C1 (LC1/RC1): Punto più alto E tra i 3 più esterni
           - y minima (più in alto)
           - Deve essere tra i 3 punti con x più estrema
        
        3. Coppia A/A0: Dai 2 punti più interni, quello più basso è A, quello più alto è A0
           - Trovare i 2 punti più interni (verso il centro)
           - Il più basso (y massima) è A
           - Il più alto (y minima) è A0
        
        4. Coppia C (LC/RC): Per esclusione
        
        Ordine finale:
        - Sinistro: [LA, LC, LB, LC1, LA0]  # Perimetro: esterno basso → centro → esterno basso → interno alto → interno alto
        - Destro: [RA, RC, RB, RC1, RA0]  # Perimetro: esterno basso → centro → esterno basso → interno alto → interno alto

        Args:
            points: Lista di punti da ordinare
            is_left: True per sopracciglio sinistro, False per destro

        Returns:
            List[Dict]: Punti ordinati secondo criteri anatomici
        """
        if len(points) < 5:
            return points
        
        if is_left:
            # Sopracciglio sinistro
            # 1. B: punto più esterno (x minima)
            b_point = min(points, key=lambda p: p["x"])
            
            # 2. C1: tra i 3 punti più esterni, quello più alto
            sorted_by_x = sorted(points, key=lambda p: p["x"])
            three_most_external = sorted_by_x[:3]
            c1_point = min(three_most_external, key=lambda p: p["y"])
            
            # 3. A e A0: dai 2 punti più interni, quello più basso è A, più alto è A0
            sorted_by_x_desc = sorted(points, key=lambda p: p["x"], reverse=True)
            two_most_internal = sorted_by_x_desc[:2]
            a_point = max(two_most_internal, key=lambda p: p["y"])  # più basso
            a0_point = min(two_most_internal, key=lambda p: p["y"])  # più alto
            
            # 4. C: per esclusione
            identified = [b_point, c1_point, a_point, a0_point]
            c_point = [p for p in points if p not in identified][0]
            
            # Ordine finale per perimetro: [LA, LC, LB, LC1, LA0]
            return [a_point, c_point, b_point, c1_point, a0_point]
            
        else:
            # Sopracciglio destro
            # 1. B: punto più esterno (x massima)
            b_point = max(points, key=lambda p: p["x"])
            
            # 2. C1: tra i 3 punti più esterni, quello più alto
            sorted_by_x = sorted(points, key=lambda p: p["x"], reverse=True)
            three_most_external = sorted_by_x[:3]
            c1_point = min(three_most_external, key=lambda p: p["y"])
            
            # 3. A e A0: dai 2 punti più interni, quello più basso è A, più alto è A0
            sorted_by_x_asc = sorted(points, key=lambda p: p["x"])
            two_most_internal = sorted_by_x_asc[:2]
            a_point = max(two_most_internal, key=lambda p: p["y"])  # più basso
            a0_point = min(two_most_internal, key=lambda p: p["y"])  # più alto
            
            # 4. C: per esclusione
            identified = [b_point, c1_point, a_point, a0_point]
            c_point = [p for p in points if p not in identified][0]
            
            # Ordine finale per perimetro: [RA, RC, RB, RC1, RA0]
            return [a_point, c_point, b_point, c1_point, a0_point]

    def sort_points_optimal(self, points: List[Dict]) -> List[Dict]:
        """
        Ordina i punti in modo ottimale scegliendo l'algoritmo che produce il perimetro minimo.

        Args:
            points: Lista di punti da ordinare

        Returns:
            List[Dict]: Punti ordinati in modo ottimale
        """
        if len(points) < 3:
            return points

        methods = [
            self.sort_points_by_proximity(points.copy()),
            self.sort_points_convex_hull(points.copy()),
        ]

        # Scegli il metodo con perimetro minimo
        best_method = min(methods, key=self.calculate_perimeter)
        return best_method

    def calculate_shape_statistics(self, points: List[Dict], label: str = "") -> Dict:
        """
        Calcola le statistiche complete di una forma.

        Args:
            points: Lista di punti della forma
            label: Etichetta per identificare la forma

        Returns:
            Dict: Statistiche della forma (area, perimetro, centro, etc.)
        """
        if not points:
            return {}

        area = self.calculate_polygon_area(points)
        perimeter = self.calculate_perimeter(points)
        center_x = sum(p["x"] for p in points) / len(points)
        center_y = sum(p["y"] for p in points) / len(points)

        return {
            "label": label,
            "vertices": len(points),
            "area": round(area, 2),
            "perimeter": round(perimeter, 2),
            "center": {"x": round(center_x, 1), "y": round(center_y, 1)},
            "points": points,
        }

    def _create_curved_polygon(
        self,
        points: List[Tuple[float, float]],
        is_left: bool,
        arc_segments: int = 20,
        curvature: float = None
    ) -> List[Tuple[float, float]]:
        """
        Crea un poligono con arco curvato convesso verso l'esterno tra LB-LC1 (sinistro) o RB-RC1 (destro).
        
        Ordine punti aggiornato:
        - Sinistro: [LA, LC, LB, LC1, LA0] → arco tra LB (idx 2) e LC1 (idx 3)
        - Destro: [RA, RC, RB, RC1, RA0] → arco tra RB (idx 2) e RC1 (idx 3)
        
        Args:
            points: Lista di punti (x, y) del poligono nell'ordine corretto
            is_left: True per sopracciglio sinistro, False per destro
            arc_segments: Numero di segmenti per approssimare l'arco
            curvature: Raggio di curvatura. Se None, usa la distanza tra i punti da collegare
        
        Returns:
            Lista di punti con l'arco inserito
        """
        if len(points) < 5:
            return points
        
        # Nuovo ordine: LA, LC, LB, LC1, LA0 (sinistro) o RA, RC, RB, RC1, RA0 (destro)
        # L'arco è sempre tra l'indice 2 (LB/RB) e l'indice 3 (LC1/RC1)
        start_point = points[2]  # LB o RB
        end_point = points[3]    # LC1 o RC1
        
        # Altri punti del poligono (esclusi quelli dell'arco)
        other_points = [points[0], points[1], points[4]]  # LA, LC, LA0 (o RA, RC, RA0)
        
        # Calcola distanza tra i punti da collegare
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        distance = (dx**2 + dy**2)**0.5
        
        if distance == 0:
            return points
        
        # Se curvatura non specificata, usa la distanza tra i punti come raggio
        if curvature is None:
            curvature = 1.0  # Raggio = distanza tra i punti
        
        # Calcola punto medio
        mid_x = (start_point[0] + end_point[0]) / 2
        mid_y = (start_point[1] + end_point[1]) / 2
        
        # Calcola vettore perpendicolare per spostare il punto di controllo verso l'esterno
        perp_x = -dy / distance
        perp_y = dx / distance
        
        # CORREZIONE: Per curvatura convessa verso l'esterno del poligono
        # Sinistro (LB→LC1): curva verso sinistra (-), Destro (RB→RC1): curva verso destra (+)
        direction = -1 if is_left else 1
        
        # Sposta il punto medio lungo il vettore perpendicolare
        # Raggio di curvatura ridotto al 60% della distanza tra i punti
        offset_distance = distance * curvature * 0.6
        control_x = mid_x + direction * perp_x * offset_distance
        control_y = mid_y + direction * perp_y * offset_distance
        
        # Genera punti lungo la curva di Bezier quadratica
        arc_points = []
        for i in range(arc_segments + 1):
            t = i / arc_segments
            # Formula della curva di Bezier quadratica: B(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂
            one_minus_t = 1 - t
            x = (one_minus_t**2 * start_point[0] + 
                 2 * one_minus_t * t * control_x + 
                 t**2 * end_point[0])
            y = (one_minus_t**2 * start_point[1] + 
                 2 * one_minus_t * t * control_y + 
                 t**2 * end_point[1])
            arc_points.append((x, y))
        
        # Costruisci il poligono finale con l'arco tra LB-LC1 (o RB-RC1)
        # Ordine: LA, LC, [arco da LB a LC1], LA0
        # Gli arc_points vanno da start_point (LB/RB) a end_point (LC1/RC1)
        result = [other_points[0], other_points[1]] + arc_points + [other_points[2]]
        
        return result

    def generate_overlay_dots_only(
        self,
        image_size: Tuple[int, int],
        all_dots: List[Dict],
    ) -> Image.Image:
        """
        Genera un overlay trasparente con solo i punti rilevati (senza poligoni).
        Usato quando il numero di punti non è quello atteso.

        Args:
            image_size: Dimensioni dell'immagine (width, height)
            all_dots: Lista di tutti i punti rilevati

        Returns:
            Image.Image: Overlay trasparente PNG con solo i punti gialli
        """
        width, height = image_size

        # Crea immagine trasparente
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Disegna solo i punti gialli
        for i, dot in enumerate(all_dots):
            x, y = dot["x"], dot["y"]
            draw.ellipse(
                [x - 4, y - 4, x + 4, y + 4],
                fill=(255, 255, 0, 255),
                outline=(0, 0, 0, 255),
                width=1,
            )
            # Etichetta numerica semplice (sopra il punto, leggermente più lontana)
            draw.text((x + 10, y - 14), str(i + 1), fill=(0, 0, 0, 255))

        return overlay

    def generate_overlay(
        self,
        image_size: Tuple[int, int],
        left_points: Optional[List[Dict]] = None,
        right_points: Optional[List[Dict]] = None,
        left_color: Tuple[int, int, int, int] = (0, 255, 0, 128),
        right_color: Tuple[int, int, int, int] = (0, 0, 255, 128),
        border_width: int = 3,
    ) -> Image.Image:
        """
        Genera un overlay trasparente con i perimetri delle forme.

        Args:
            image_size: Dimensioni dell'immagine (width, height)
            left_points: Punti della forma sinistra (opzionale)
            right_points: Punti della forma destra (opzionale)
            left_color: Colore RGBA per la forma sinistra
            right_color: Colore RGBA per la forma destra
            border_width: Spessore del bordo in pixel

        Returns:
            Image.Image: Overlay trasparente PNG con le forme
        """
        width, height = image_size

        # Crea immagine trasparente
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Linea di divisione centrale rimossa per richiesta utente

        # Usa i punti forniti o quelli dell'ultimo processing
        if left_points is None:
            left_points = self.left_dots
        if right_points is None:
            right_points = self.right_dots

        # Disegna forma sinistra SOLO se ci sono esattamente 5 punti
        if left_points and len(left_points) == 5:
            sorted_left = self.sort_points_anatomical(left_points, is_left=True)
            polygon_points = [(p["x"], p["y"]) for p in sorted_left]

            # Crea poligono con arco tra i punti nell'ordine corretto
            curved_points = self._create_curved_polygon(polygon_points, is_left=True)

            # Riempimento semi-trasparente
            draw.polygon(curved_points, fill=left_color)

            # Bordo
            border_color = left_color[:3] + (255,)  # Bordo opaco
            draw.polygon(curved_points, outline=border_color, width=border_width)

            # Vertici
            # Etichette nell'ordine corretto: LA, LC, LB, LC1, LA0
            left_labels = ["LA", "LC", "LB", "LC1", "LA0"]
            for i, point in enumerate(sorted_left):
                x, y = point["x"], point["y"]
                draw.ellipse(
                    [x - 4, y - 4, x + 4, y + 4],
                    fill=(255, 255, 0, 255),
                    outline=(0, 0, 0, 255),
                    width=1,
                )
                # Usa etichette personalizzate o fallback se ci sono più punti
                label = left_labels[i] if i < len(left_labels) else f"L{i+1}"
                # LA, LC, LB → sotto il punto; LC1, LA0 → sopra
                below_labels = {"LA", "LC", "LB"}
                text_y = y + 12 if label in below_labels else y - 14
                draw.text((x + 10, text_y), label, fill=(0, 0, 0, 255))

        # Disegna forma destra SOLO se ci sono esattamente 5 punti
        if right_points and len(right_points) == 5:
            sorted_right = self.sort_points_anatomical(right_points, is_left=False)
            polygon_points = [(p["x"], p["y"]) for p in sorted_right]

            # Crea poligono con arco tra i punti nell'ordine corretto
            curved_points = self._create_curved_polygon(polygon_points, is_left=False)

            # Riempimento semi-trasparente
            draw.polygon(curved_points, fill=right_color)

            # Bordo
            border_color = right_color[:3] + (255,)  # Bordo opaco
            draw.polygon(curved_points, outline=border_color, width=border_width)

            # Vertici
            # Etichette nell'ordine corretto: RA, RC, RB, RC1, RA0
            right_labels = ["RA", "RC", "RB", "RC1", "RA0"]
            for i, point in enumerate(sorted_right):
                x, y = point["x"], point["y"]
                draw.ellipse(
                    [x - 4, y - 4, x + 4, y + 4],
                    fill=(255, 255, 0, 255),
                    outline=(0, 0, 0, 255),
                    width=1,
                )
                # Usa etichette personalizzate o fallback se ci sono più punti
                label = right_labels[i] if i < len(right_labels) else f"R{i+1}"
                # RA, RC, RB → sotto il punto; RC1, RA0 → sopra
                below_labels = {"RA", "RC", "RB"}
                text_y = y + 12 if label in below_labels else y - 14
                draw.text((x + 10, text_y), label, fill=(0, 0, 0, 255))

        return overlay

    def process_image(self, image_path: str, use_preprocessing: bool = False, return_scale_info: bool = False) -> Dict:
        """
        Processa completamente un'immagine: rileva puntini, li divide e calcola statistiche.

        Args:
            image_path: Percorso dell'immagine da processare
            use_preprocessing: Se True, applica preprocessing eyebrow (default: False per retrocompatibilità)
            return_scale_info: Se True, include info su scala e immagine originale nel risultato

        Returns:
            Dict: Risultati completi del processing
        """
        # Carica immagine
        image = Image.open(image_path)
        
        # Applica preprocessing se richiesto
        if use_preprocessing:
            preprocessed_image, original_image, scale_factor = self.preprocess_for_detection(image)
            detection_image = preprocessed_image
        else:
            detection_image = image
            original_image = image
            scale_factor = 1.0

        # Rileva puntini verdi
        detection_results = self.detect_green_dots(detection_image)

        # Se non ci sono abbastanza punti o ce ne sono troppi, genera overlay solo con punti
        if detection_results["total_dots"] != 10:
            overlay = self.generate_overlay_dots_only(
                detection_results["image_size"],
                detection_results["dots"]
            )
            return {
                "success": True,
                "warning": f"Rilevati {detection_results['total_dots']} punti invece di 10. Overlay generato solo con punti.",
                "detection_results": detection_results,
                "overlay": overlay,
                "image_size": detection_results["image_size"],
                "groups": None,
                "coordinates": None,
                "statistics": None,
            }

        # Dividi in gruppi
        left_dots, right_dots = self.divide_dots_by_vertical_center(
            detection_results["dots"], detection_results["image_size"][0]
        )

        if len(left_dots) < 3 or len(right_dots) < 3:
            return {
                "success": False,
                "error": f"Gruppi insufficienti: Sx={len(left_dots)}, Dx={len(right_dots)}. Servono almeno 3 per lato.",
                "detection_results": detection_results,
                "left_dots": left_dots,
                "right_dots": right_dots,
            }

        # Ordina punti e calcola statistiche
        sorted_left = self.sort_points_anatomical(left_dots, is_left=True)
        sorted_right = self.sort_points_anatomical(right_dots, is_left=False)

        left_stats = self.calculate_shape_statistics(sorted_left, "Sinistra")
        right_stats = self.calculate_shape_statistics(sorted_right, "Destra")

        # Genera overlay
        overlay = self.generate_overlay(
            detection_results["image_size"], sorted_left, sorted_right
        )

        result = {
            "success": True,
            "detection_results": detection_results,
            "groups": {
                "Sx": sorted_left,  # Gruppo sinistro
                "Dx": sorted_right,  # Gruppo destro
            },
            "coordinates": {
                "Sx": [(p["x"], p["y"]) for p in sorted_left],
                "Dx": [(p["x"], p["y"]) for p in sorted_right],
            },
            "statistics": {
                "left": left_stats,
                "right": right_stats,
                "combined": {
                    "total_vertices": len(sorted_left) + len(sorted_right),
                    "total_area": left_stats["area"] + right_stats["area"],
                    "total_perimeter": left_stats["perimeter"]
                    + right_stats["perimeter"],
                },
            },
            "overlay": overlay,
            "image_size": detection_results["image_size"],
        }
        
        # Aggiungi info preprocessing se richiesto
        if return_scale_info and use_preprocessing:
            result["scale_factor"] = scale_factor
            result["original_image"] = original_image
            result["preprocessed_image"] = detection_image
        
        return result

    def process_pil_image(self, pil_image: Image.Image, use_preprocessing: bool = False, return_scale_info: bool = False) -> Dict:
        """
        Processa direttamente un'immagine PIL senza salvare su file.

        Args:
            pil_image: Immagine PIL da processare
            use_preprocessing: Se True, applica preprocessing eyebrow (default: False per retrocompatibilità)
            return_scale_info: Se True, include info su scala e immagine originale nel risultato

        Returns:
            Dict: Risultati completi del processing
        """
        # Applica preprocessing se richiesto
        if use_preprocessing:
            preprocessed_image, original_image, scale_factor = self.preprocess_for_detection(pil_image)
            detection_image = preprocessed_image
        else:
            detection_image = pil_image
            original_image = pil_image
            scale_factor = 1.0
            
        # Rileva puntini verdi
        detection_results = self.detect_green_dots(detection_image)

        # DEVE trovare esattamente 10 punti per output completo, ma mostra sempre overlay
        if detection_results["total_dots"] != 10:
            overlay = self.generate_overlay_dots_only(
                detection_results["image_size"],
                detection_results["dots"]
            )
            return {
                "success": True,  # SUCCESS per mostrare overlay
                "warning": f"⚠️ Rilevati {detection_results['total_dots']} punti invece di 10. Overlay con punti rilevati.",
                "detection_results": detection_results,
                "overlay": overlay,
                "image_size": detection_results["image_size"],
                "groups": None,
                "coordinates": None,
                "statistics": None,
            }

        # Dividi in gruppi
        left_dots, right_dots = self.divide_dots_by_vertical_center(
            detection_results["dots"], detection_results["image_size"][0]
        )

        # DEVE essere esattamente 5+5 per poligoni, ma mostra sempre overlay
        if len(left_dots) != 5 or len(right_dots) != 5:
            overlay = self.generate_overlay_dots_only(
                detection_results["image_size"],
                detection_results["dots"]
            )
            return {
                "success": True,  # SUCCESS per mostrare overlay
                "warning": f"⚠️ Gruppi non bilanciati: Sx={len(left_dots)}, Dx={len(right_dots)}. Overlay con punti rilevati.",
                "detection_results": detection_results,
                "overlay": overlay,
                "image_size": detection_results["image_size"],
                "groups": None,
                "coordinates": None,
                "statistics": None,
            }

        # Ordina punti e calcola statistiche
        sorted_left = self.sort_points_anatomical(left_dots, is_left=True)
        sorted_right = self.sort_points_anatomical(right_dots, is_left=False)

        left_stats = self.calculate_shape_statistics(sorted_left, "Sinistra")
        right_stats = self.calculate_shape_statistics(sorted_right, "Destra")

        # Genera overlay con poligoni perimetrali
        overlay = self.generate_overlay(
            detection_results["image_size"], sorted_left, sorted_right
        )

        result = {
            "success": True,
            "detection_results": detection_results,
            "groups": {
                "Sx": sorted_left,
                "Dx": sorted_right,
            },
            "coordinates": {
                "Sx": [(p["x"], p["y"]) for p in sorted_left],
                "Dx": [(p["x"], p["y"]) for p in sorted_right],
            },
            "statistics": {
                "left": left_stats,
                "right": right_stats,
                "combined": {
                    "total_vertices": len(sorted_left) + len(sorted_right),
                    "total_area": left_stats["area"] + right_stats["area"],
                    "total_perimeter": left_stats["perimeter"] + right_stats["perimeter"],
                },
            },
            "overlay": overlay,
            "image_size": detection_results["image_size"],
        }
        
        # Aggiungi info preprocessing se richiesto
        if return_scale_info and use_preprocessing:
            result["scale_factor"] = scale_factor
            result["original_image"] = original_image
            result["preprocessed_image"] = detection_image
        
        return result


# Funzioni di convenienza per uso diretto del modulo
def process_image_file(image_path: str, **kwargs) -> Dict:
    """
    Funzione di convenienza per processare un'immagine con parametri di default.

    Args:
        image_path: Percorso dell'immagine
        **kwargs: Parametri opzionali per GreenDotsProcessor

    Returns:
        Dict: Risultati del processing
    """
    processor = GreenDotsProcessor(**kwargs)
    return processor.process_image(image_path)


def create_overlay_from_coordinates(
    image_size: Tuple[int, int],
    left_coords: List[Tuple[int, int]],
    right_coords: List[Tuple[int, int]],
) -> Image.Image:
    """
    Crea un overlay dalle coordinate fornite.

    Args:
        image_size: Dimensioni dell'immagine (width, height)
        left_coords: Lista di coordinate (x, y) per il lato sinistro
        right_coords: Lista di coordinate (x, y) per il lato destro

    Returns:
        Image.Image: Overlay trasparente
    """
    # Converte coordinate in formato dizionario
    left_points = [{"x": x, "y": y} for x, y in left_coords]
    right_points = [{"x": x, "y": y} for x, y in right_coords]

    processor = GreenDotsProcessor()
    return processor.generate_overlay(image_size, left_points, right_points)


if __name__ == "__main__":
    # Test del modulo
    print("Test del modulo GreenDotsProcessor")
    print("Esempio d'uso:")
    print(
        """
    from src.green_dots_processor import GreenDotsProcessor
    
    # Processa un'immagine
    processor = GreenDotsProcessor()
    results = processor.process_image("path/to/image.jpg")
    
    if results['success']:
        print(f"Puntini Sx: {len(results['groups']['Sx'])}")
        print(f"Puntini Dx: {len(results['groups']['Dx'])}")
        
        # Salva overlay
        results['overlay'].save("overlay.png")
        
        # Coordinate dei puntini
        sx_coords = results['coordinates']['Sx']
        dx_coords = results['coordinates']['Dx']
    """
    )
