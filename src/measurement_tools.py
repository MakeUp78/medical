"""
Measurement tools for facial analysis - distances, angles, areas and facial proportions.
"""

import math
import numpy as np
from typing import List, Tuple, Optional, Dict
from src.utils import calculate_distance, calculate_angle


class MeasurementTools:
    def __init__(self):
        """Inizializza gli strumenti di misurazione."""
        # Proporzioni facciali standard (ratio aurei)
        self.golden_ratios = {
            "face_width_to_height": 1.618,
            "eye_width_to_height": 3.0,
            "nose_width_to_height": 1.0,
            "mouth_width_to_nose_width": 1.5,
            "eye_separation_to_eye_width": 1.0,
        }

        # Landmark indici per misurazioni standard
        self.measurement_landmarks = {
            "face_width": {"left": 234, "right": 454},
            "face_height": {"top": 10, "bottom": 175},
            "eye_left": {"inner": 133, "outer": 33, "top": 159, "bottom": 145},
            "eye_right": {"inner": 362, "outer": 263, "top": 386, "bottom": 374},
            "nose": {"tip": 1, "bridge": 9, "left": 131, "right": 360},
            "mouth": {"left": 61, "right": 291, "top": 13, "bottom": 14},
            "eyebrow_left": {"inner": 70, "outer": 107},
            "eyebrow_right": {"inner": 296, "outer": 336},
        }

    def calculate_distance(
        self, point1: Tuple[float, float], point2: Tuple[float, float]
    ) -> float:
        """Calcola la distanza euclidea tra due punti."""
        return calculate_distance(point1, point2)

    def calculate_angle(
        self,
        point1: Tuple[float, float],
        vertex: Tuple[float, float],
        point2: Tuple[float, float],
    ) -> float:
        """Calcola l'angolo formato da tre punti."""
        return calculate_angle(point1, vertex, point2)

    def calculate_polygon_area(self, points: List[Tuple[float, float]]) -> float:
        """Calcola l'area di un poligono usando la formula shoelace."""
        if len(points) < 3:
            return 0.0

        area = 0.0
        n = len(points)

        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]

        return abs(area) / 2.0

    def calculate_facial_measurements(
        self, landmarks: List[Tuple[float, float]]
    ) -> Dict[str, float]:
        """
        Calcola le misurazioni facciali standard.

        Args:
            landmarks: Lista completa dei landmark facciali (478 punti)

        Returns:
            Dizionario con le misurazioni calcolate
        """
        measurements = {}

        if len(landmarks) < 478:
            return measurements

        try:
            # Larghezza e altezza del volto
            face_left = landmarks[self.measurement_landmarks["face_width"]["left"]]
            face_right = landmarks[self.measurement_landmarks["face_width"]["right"]]
            face_top = landmarks[self.measurement_landmarks["face_height"]["top"]]
            face_bottom = landmarks[self.measurement_landmarks["face_height"]["bottom"]]

            face_width = self.calculate_distance(face_left, face_right)
            face_height = self.calculate_distance(face_top, face_bottom)

            measurements["face_width"] = face_width
            measurements["face_height"] = face_height
            measurements["face_ratio"] = (
                face_width / face_height if face_height > 0 else 0
            )

            # Misurazioni occhi
            left_eye = self.measurement_landmarks["eye_left"]
            right_eye = self.measurement_landmarks["eye_right"]

            # Occhio sinistro
            left_eye_width = self.calculate_distance(
                landmarks[left_eye["inner"]], landmarks[left_eye["outer"]]
            )
            left_eye_height = self.calculate_distance(
                landmarks[left_eye["top"]], landmarks[left_eye["bottom"]]
            )

            # Occhio destro
            right_eye_width = self.calculate_distance(
                landmarks[right_eye["inner"]], landmarks[right_eye["outer"]]
            )
            right_eye_height = self.calculate_distance(
                landmarks[right_eye["top"]], landmarks[right_eye["bottom"]]
            )

            measurements["left_eye_width"] = left_eye_width
            measurements["left_eye_height"] = left_eye_height
            measurements["right_eye_width"] = right_eye_width
            measurements["right_eye_height"] = right_eye_height

            # Distanza tra gli occhi
            eye_distance = self.calculate_distance(
                landmarks[left_eye["outer"]], landmarks[right_eye["outer"]]
            )
            measurements["eye_distance"] = eye_distance

            # Misurazioni naso
            nose = self.measurement_landmarks["nose"]
            nose_width = self.calculate_distance(
                landmarks[nose["left"]], landmarks[nose["right"]]
            )
            nose_height = self.calculate_distance(
                landmarks[nose["bridge"]], landmarks[nose["tip"]]
            )

            measurements["nose_width"] = nose_width
            measurements["nose_height"] = nose_height

            # Misurazioni bocca
            mouth = self.measurement_landmarks["mouth"]
            mouth_width = self.calculate_distance(
                landmarks[mouth["left"]], landmarks[mouth["right"]]
            )
            mouth_height = self.calculate_distance(
                landmarks[mouth["top"]], landmarks[mouth["bottom"]]
            )

            measurements["mouth_width"] = mouth_width
            measurements["mouth_height"] = mouth_height

            # Simmetria facciale
            measurements["facial_symmetry"] = self.calculate_facial_symmetry(landmarks)

        except (IndexError, KeyError) as e:
            print(f"Errore nel calcolo delle misurazioni: {e}")

        return measurements

    def calculate_facial_symmetry(self, landmarks: List[Tuple[float, float]]) -> float:
        """
        Calcola un indice di simmetria facciale.

        Returns:
            Valore tra 0 e 1, dove 1 indica perfetta simmetria
        """
        if len(landmarks) < 478:
            return 0.0

        try:
            # Punti di riferimento per la simmetria
            nose_tip = landmarks[1]

            # Coppie di punti simmetrici
            symmetric_pairs = [
                (landmarks[33], landmarks[362]),  # Angoli esterni occhi
                (landmarks[133], landmarks[362]),  # Angoli interni occhi
                (landmarks[61], landmarks[291]),  # Angoli bocca
                (landmarks[116], landmarks[345]),  # Guance
                (landmarks[70], landmarks[300]),  # Sopracciglia esterne
            ]

            symmetry_scores = []

            for left_point, right_point in symmetric_pairs:
                # Calcola la distanza dal centro (naso)
                left_distance = abs(left_point[0] - nose_tip[0])
                right_distance = abs(right_point[0] - nose_tip[0])

                # Calcola il punteggio di simmetria per questa coppia
                if left_distance + right_distance > 0:
                    symmetry = 1.0 - abs(left_distance - right_distance) / (
                        left_distance + right_distance
                    )
                    symmetry_scores.append(max(0, symmetry))

            # Media dei punteggi di simmetria
            return (
                sum(symmetry_scores) / len(symmetry_scores) if symmetry_scores else 0.0
            )

        except (IndexError, KeyError):
            return 0.0

    def create_symmetry_overlay(self, landmarks: List[Tuple[float, float]]) -> Optional[Dict]:
        """
        Crea un overlay per visualizzare l'analisi di simmetria facciale.
        
        Args:
            landmarks: Lista dei landmark facciali
            
        Returns:
            Dizionario con le informazioni dell'overlay
        """
        if len(landmarks) < 478:
            return None
            
        try:
            # Punti di riferimento
            nose_tip = landmarks[1]
            
            # Linea di simmetria centrale (verticale dal naso)
            face_top = landmarks[10]
            face_bottom = landmarks[152]
            
            # Coppie di punti simmetrici per le linee di confronto
            symmetric_pairs = [
                (landmarks[33], landmarks[362]),    # Angoli esterni occhi
                (landmarks[133], landmarks[362]),   # Angoli interni occhi  
                (landmarks[61], landmarks[291]),    # Angoli bocca
                (landmarks[116], landmarks[345]),   # Guanche
                (landmarks[70], landmarks[300]),    # Sopracciglia esterne
            ]
            
            # Crea le linee per l'overlay
            lines = []
            
            # Linea centrale di simmetria
            lines.append([nose_tip, face_top])
            lines.append([nose_tip, face_bottom])
            
            # Linee orizzontali per ogni coppia simmetrica
            for left_point, right_point in symmetric_pairs:
                # Linea orizzontale che collega i punti simmetrici
                lines.append([left_point, right_point])
                
                # Linee verticali dal centro verso i punti (per mostrare le distanze)
                center_y = (left_point[1] + right_point[1]) / 2
                center_point = (nose_tip[0], center_y)
                lines.append([center_point, left_point])
                lines.append([center_point, right_point])
            
            return {
                'points': lines,
                'type': 'multiple_lines',
                'color': 'purple',
                'description': 'Analisi simmetria facciale'
            }
            
        except (IndexError, KeyError):
            return None

    def calculate_golden_ratio_scores(
        self, measurements: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calcola quanto le misurazioni si avvicinano alle proporzioni auree.

        Args:
            measurements: Dizionario delle misurazioni facciali

        Returns:
            Dizionario con i punteggi di aderenza alle proporzioni auree (0-1)
        """
        scores = {}

        try:
            # Rapporto larghezza/altezza del volto
            if "face_width" in measurements and "face_height" in measurements:
                actual_ratio = measurements["face_width"] / measurements["face_height"]
                ideal_ratio = self.golden_ratios["face_width_to_height"]
                scores["face_ratio_score"] = self._calculate_ratio_score(
                    actual_ratio, ideal_ratio
                )

            # Rapporto larghezza/altezza occhi
            if "left_eye_width" in measurements and "left_eye_height" in measurements:
                actual_ratio = (
                    measurements["left_eye_width"] / measurements["left_eye_height"]
                )
                ideal_ratio = self.golden_ratios["eye_width_to_height"]
                scores["eye_ratio_score"] = self._calculate_ratio_score(
                    actual_ratio, ideal_ratio
                )

            # Rapporto larghezza bocca / larghezza naso
            if "mouth_width" in measurements and "nose_width" in measurements:
                actual_ratio = measurements["mouth_width"] / measurements["nose_width"]
                ideal_ratio = self.golden_ratios["mouth_width_to_nose_width"]
                scores["mouth_nose_ratio_score"] = self._calculate_ratio_score(
                    actual_ratio, ideal_ratio
                )

            # Rapporto distanza occhi / larghezza occhio
            if "eye_distance" in measurements and "left_eye_width" in measurements:
                actual_ratio = (
                    measurements["eye_distance"] / measurements["left_eye_width"]
                )
                ideal_ratio = self.golden_ratios["eye_separation_to_eye_width"]
                scores["eye_separation_score"] = self._calculate_ratio_score(
                    actual_ratio, ideal_ratio
                )

        except (KeyError, ZeroDivisionError):
            pass

        return scores

    def _calculate_ratio_score(
        self, actual: float, ideal: float, tolerance: float = 0.2
    ) -> float:
        """
        Calcola un punteggio di aderenza a un rapporto ideale.

        Args:
            actual: Rapporto attuale
            ideal: Rapporto ideale
            tolerance: Tolleranza per il punteggio massimo

        Returns:
            Punteggio tra 0 e 1
        """
        if ideal == 0:
            return 0.0

        difference = abs(actual - ideal) / ideal

        if difference <= tolerance:
            return (
                1.0 - (difference / tolerance) * 0.2
            )  # Perdita massima del 20% nella tolleranza
        else:
            return max(
                0.0, 0.8 - difference
            )  # Decadimento graduale oltre la tolleranza

    def get_measurement_description(self, measurement_name: str) -> str:
        """Restituisce una descrizione leggibile della misurazione."""
        descriptions = {
            "face_width": "Larghezza del volto",
            "face_height": "Altezza del volto",
            "face_ratio": "Rapporto larghezza/altezza volto",
            "left_eye_width": "Larghezza occhio sinistro",
            "left_eye_height": "Altezza occhio sinistro",
            "right_eye_width": "Larghezza occhio destro",
            "right_eye_height": "Altezza occhio destro",
            "eye_distance": "Distanza tra gli occhi",
            "nose_width": "Larghezza del naso",
            "nose_height": "Altezza del naso",
            "mouth_width": "Larghezza della bocca",
            "mouth_height": "Altezza della bocca",
            "facial_symmetry": "Indice di simmetria facciale",
            "face_ratio_score": "Aderenza proporzioni auree (volto)",
            "eye_ratio_score": "Aderenza proporzioni auree (occhi)",
            "mouth_nose_ratio_score": "Aderenza proporzioni auree (bocca/naso)",
            "eye_separation_score": "Aderenza proporzioni auree (distanza occhi)",
            "left_eyebrow_area": "Area sopracciglio sinistro",
            "right_eyebrow_area": "Area sopracciglio destro",
            "eyebrow_area_difference": "Differenza aree sopraccigli",
            "larger_eyebrow": "Sopracciglio più grande",
            "left_eye_area": "Area occhio sinistro",
            "right_eye_area": "Area occhio destro",
            "eye_area_difference": "Differenza aree occhi",
            "larger_eye": "Occhio più grande",
        }

        return descriptions.get(measurement_name, measurement_name)

    def format_measurement_value(self, value: float, measurement_type: str) -> str:
        """Formatta il valore di una misurazione per la visualizzazione."""
        if (
            "ratio" in measurement_type
            or "score" in measurement_type
            or "symmetry" in measurement_type
        ):
            return f"{value:.3f}"
        elif "area" in measurement_type:
            return f"{value:.1f} px²"
        elif "difference" in measurement_type:
            return f"{value:.1f} px²"
        elif "larger" in measurement_type:
            return str(value)
        else:
            return f"{value:.1f} px"

    def calculate_eyebrow_areas(
        self, landmarks: List[Tuple[float, float]]
    ) -> Dict[str, float]:
        """
        Calcola le aree dei sopraccigli sinistro e destro utilizzando
        i landmarks MediaPipe UFFICIALI estratti da FACEMESH_LEFT_EYEBROW e FACEMESH_RIGHT_EYEBROW.

        Returns:
            Dict con aree individuali, differenza e quale è più grande
        """
        if len(landmarks) < 478:
            return {}

        # Landmarks per sopracciglio SINISTRO
        # Ordinati secondo NUOVA SEQUENZA PERIMETRALE PERSONALIZZATA
        # RIMOSSO landmark 276 e DUPLICATO 285
        left_eyebrow_points = [
            landmarks[334],
            landmarks[296],
            landmarks[336],
            landmarks[285],
            landmarks[295],
            landmarks[282],
            landmarks[283],
            landmarks[300],
            landmarks[293],
            landmarks[334],  # Chiude il perimetro
        ]

        # Landmarks per sopracciglio DESTRO
        # Ordinati secondo NUOVA SEQUENZA PERIMETRALE PERSONALIZZATA
        # RIMOSSO landmark 46
        right_eyebrow_points = [
            landmarks[53],
            landmarks[52],
            landmarks[65],
            landmarks[55],
            landmarks[107],
            landmarks[66],
            landmarks[105],
            landmarks[63],
            landmarks[70],
            landmarks[53],  # Chiude il perimetro
        ]
        # NON serve più order_polygon_points - già ordinati correttamente secondo le connessioni

        left_area = self.calculate_polygon_area(left_eyebrow_points)
        right_area = self.calculate_polygon_area(right_eyebrow_points)

        area_difference = abs(left_area - right_area)
        larger_eyebrow = "Sinistro" if left_area > right_area else "Destro"

        return {
            "left_eyebrow_area": left_area,
            "right_eyebrow_area": right_area,
            "eyebrow_area_difference": area_difference,
            "larger_eyebrow": larger_eyebrow,
        }

    def calculate_eye_areas(
        self, landmarks: List[Tuple[float, float]]
    ) -> Dict[str, float]:
        """
        Calcola le aree degli occhi sinistro e destro utilizzando
        tutti i landmarks MediaPipe disponibili per il contorno degli occhi.

        Returns:
            Dict con aree individuali, differenza e quale è più grande
        """
        if len(landmarks) < 478:
            return {}

        # Landmark per occhio sinistro (contorno completo con più punti)
        # Sequenza ordinata seguendo il contorno dell'occhio
        left_eye_points = [
            landmarks[33],  # angolo esterno
            landmarks[7],  # superiore esterno
            landmarks[163],  # superiore esterno-centro
            landmarks[144],  # superiore centro
            landmarks[145],  # superiore centro-interno
            landmarks[153],  # superiore interno
            landmarks[154],  # angolo interno superiore
            landmarks[155],  # angolo interno
            landmarks[133],  # angolo interno inferiore
            landmarks[173],  # inferiore interno
            landmarks[157],  # inferiore interno-centro
            landmarks[158],  # inferiore centro
            landmarks[159],  # inferiore centro-esterno
            landmarks[160],  # inferiore esterno-centro
            landmarks[161],  # inferiore esterno
            landmarks[246],  # connessione inferiore
        ]

        # Landmark per occhio destro (contorno completo con più punti)
        # Sequenza ordinata seguendo il contorno dell'occhio
        right_eye_points = [
            landmarks[362],  # angolo interno
            landmarks[398],  # angolo interno superiore
            landmarks[384],  # superiore interno
            landmarks[385],  # superiore interno-centro
            landmarks[386],  # superiore centro
            landmarks[387],  # superiore centro-esterno
            landmarks[388],  # superiore esterno
            landmarks[466],  # superiore esterno-angolo
            landmarks[263],  # angolo esterno
            landmarks[249],  # inferiore esterno
            landmarks[390],  # inferiore esterno-centro
            landmarks[373],  # inferiore centro
            landmarks[374],  # inferiore centro-interno
            landmarks[380],  # inferiore interno-centro
            landmarks[381],  # inferiore interno
            landmarks[382],  # connessione inferiore
        ]

        left_area = self.calculate_polygon_area(left_eye_points)
        right_area = self.calculate_polygon_area(right_eye_points)

        area_difference = abs(left_area - right_area)
        larger_eye = "Sinistro" if left_area > right_area else "Destro"

        return {
            "left_eye_area": left_area,
            "right_eye_area": right_area,
            "eye_area_difference": area_difference,
            "larger_eye": larger_eye,
        }
