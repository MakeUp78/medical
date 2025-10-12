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
from PIL import Image, ImageDraw
import math
from typing import Dict, List, Tuple, Optional


class GreenDotsProcessor:
    """
    Processore per il rilevamento di puntini verdi e generazione di forme geometriche.
    """

    def __init__(
        self,
        hue_range: Tuple[int, int] = (60, 150),
        saturation_min: int = 15,
        value_range: Tuple[int, int] = (15, 95),
        cluster_size_range: Tuple[int, int] = (2, 150),
        clustering_radius: int = 2,
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
        Determina se un pixel è verde secondo i parametri configurati.

        Args:
            r, g, b: Valori RGB del pixel

        Returns:
            bool: True se il pixel è considerato verde
        """
        h, s, v = self.rgb_to_hsv(r, g, b)
        return (
            self.hue_min <= h <= self.hue_max
            and s >= self.saturation_min
            and self.value_min <= v <= self.value_max
        )

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

            dots.append(
                {
                    "x": round(avg_x),
                    "y": round(avg_y),
                    "size": len(cluster),
                    "pixels": cluster,
                }
            )

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

        # Disegna linea di divisione centrale
        middle_x = width // 2
        draw.line(
            [(middle_x, 0), (middle_x, height)], fill=(128, 128, 128, 100), width=1
        )

        # Usa i punti forniti o quelli dell'ultimo processing
        if left_points is None:
            left_points = self.left_dots
        if right_points is None:
            right_points = self.right_dots

        # Disegna forma sinistra
        if left_points and len(left_points) >= 3:
            sorted_left = self.sort_points_optimal(left_points)
            polygon_points = [(p["x"], p["y"]) for p in sorted_left]

            # Riempimento semi-trasparente
            draw.polygon(polygon_points, fill=left_color)

            # Bordo
            border_color = left_color[:3] + (255,)  # Bordo opaco
            draw.polygon(polygon_points, outline=border_color, width=border_width)

            # Vertici
            for i, point in enumerate(sorted_left):
                x, y = point["x"], point["y"]
                draw.ellipse(
                    [x - 4, y - 4, x + 4, y + 4],
                    fill=(255, 255, 0, 255),
                    outline=(0, 0, 0, 255),
                    width=1,
                )
                draw.text((x + 6, y - 6), f"L{i+1}", fill=(0, 0, 0, 255))

        # Disegna forma destra
        if right_points and len(right_points) >= 3:
            sorted_right = self.sort_points_optimal(right_points)
            polygon_points = [(p["x"], p["y"]) for p in sorted_right]

            # Riempimento semi-trasparente
            draw.polygon(polygon_points, fill=right_color)

            # Bordo
            border_color = right_color[:3] + (255,)  # Bordo opaco
            draw.polygon(polygon_points, outline=border_color, width=border_width)

            # Vertici
            for i, point in enumerate(sorted_right):
                x, y = point["x"], point["y"]
                draw.ellipse(
                    [x - 4, y - 4, x + 4, y + 4],
                    fill=(255, 255, 0, 255),
                    outline=(0, 0, 0, 255),
                    width=1,
                )
                draw.text((x + 6, y - 6), f"R{i+1}", fill=(0, 0, 0, 255))

        return overlay

    def process_image(self, image_path: str) -> Dict:
        """
        Processa completamente un'immagine: rileva puntini, li divide e calcola statistiche.

        Args:
            image_path: Percorso dell'immagine da processare

        Returns:
            Dict: Risultati completi del processing
        """
        # Carica immagine
        image = Image.open(image_path)

        # Rileva puntini verdi
        detection_results = self.detect_green_dots(image)

        if detection_results["total_dots"] < 6:
            return {
                "success": False,
                "error": f"Trovati solo {detection_results['total_dots']} puntini. Servono almeno 6 (3 per lato).",
                "detection_results": detection_results,
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
        sorted_left = self.sort_points_optimal(left_dots)
        sorted_right = self.sort_points_optimal(right_dots)

        left_stats = self.calculate_shape_statistics(sorted_left, "Sinistra")
        right_stats = self.calculate_shape_statistics(sorted_right, "Destra")

        # Genera overlay
        overlay = self.generate_overlay(
            detection_results["image_size"], sorted_left, sorted_right
        )

        return {
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

    def process_pil_image(self, pil_image: Image.Image) -> Dict:
        """
        Processa direttamente un'immagine PIL senza salvare su file.

        Args:
            pil_image: Immagine PIL da processare

        Returns:
            Dict: Risultati completi del processing
        """
        # Rileva puntini verdi
        detection_results = self.detect_green_dots(pil_image)

        if detection_results["total_dots"] < 6:
            return {
                "success": False,
                "error": f"Trovati solo {detection_results['total_dots']} puntini. Servono almeno 6 (3 per lato).",
                "detection_results": detection_results,
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
        sorted_left = self.sort_points_optimal(left_dots)
        sorted_right = self.sort_points_optimal(right_dots)

        left_stats = self.calculate_shape_statistics(sorted_left, "Sinistra")
        right_stats = self.calculate_shape_statistics(sorted_right, "Destra")

        # Genera overlay
        overlay = self.generate_overlay(
            detection_results["image_size"], sorted_left, sorted_right
        )

        return {
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
