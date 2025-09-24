"""
Face detection and landmark extraction using MediaPipe.
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import List, Tuple, Optional
from src.utils import calculate_pure_frontal_score


class FaceDetector:
    def __init__(self):
        """Inizializza il detector di volti MediaPipe."""
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Configura MediaPipe Face Mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,  # FIX BUG: True per disabilitare tracking tra frame
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def detect_face_landmarks(
        self, image: np.ndarray
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Rileva i landmark facciali in un'immagine con logging per debug.
        Returns: Lista di coordinate (x, y) dei landmark o None se nessun volto rilevato.
        """
        try:
            # Converte BGR in RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Processo di rilevamento
            results = self.face_mesh.process(rgb_image)

            if not results.multi_face_landmarks:
                # Log solo occasionalmente per evitare spam
                if hasattr(self, "_no_face_count"):
                    self._no_face_count += 1
                else:
                    self._no_face_count = 1

                if self._no_face_count % 100 == 1:  # Log ogni 100 frame senza volto
                    print(
                        f"👤 FACE_DETECTOR: Nessun volto rilevato (totale: {self._no_face_count})"
                    )
                return None

            # Reset contatore se troviamo un volto
            if hasattr(self, "_no_face_count"):
                if self._no_face_count > 0:
                    print(
                        f"✅ FACE_DETECTOR: Volto rilevato dopo {self._no_face_count} frame vuoti"
                    )
                self._no_face_count = 0

            # Estrae i landmark del primo volto rilevato
            face_landmarks = results.multi_face_landmarks[0]
            height, width = image.shape[:2]

            landmarks = []
            for landmark in face_landmarks.landmark:
                x = int(landmark.x * width)
                y = int(landmark.y * height)
                landmarks.append((x, y))

            print(f"FACE_DETECTOR: {len(landmarks)} landmark rilevati")
            return landmarks

        except Exception as e:
            print(f"FACE_DETECTOR: Errore nel rilevamento: {e}")
            return None

    def calculate_frontal_score(
        self, landmarks: List[Tuple[float, float]], config=None
    ) -> float:
        """
        Calcola il punteggio di frontalità del volto.
        SEMPLIFICATO: Usa SOLO l'algoritmo puro di frontalità, più affidabile.
        """
        try:
            return calculate_pure_frontal_score(landmarks, config=config)
        except Exception as e:
            print(f"Errore nel calcolo frontalità: {e}")
            return 0.0

    def draw_landmarks(
        self,
        image: np.ndarray,
        landmarks: List[Tuple[float, float]],
        draw_all: bool = False,
        key_only: bool = True,
    ) -> np.ndarray:
        """
        Disegna i landmark sull'immagine.

        Args:
            image: Immagine su cui disegnare
            landmarks: Lista dei landmark
            draw_all: Se True, disegna tutti i 468 landmark
            key_only: Parametro mantenuto per compatibilità (non utilizzato)
        """
        result_image = image.copy()

        if draw_all:
            # Disegna tutti i landmark
            for point in landmarks:
                cv2.circle(
                    result_image, (int(point[0]), int(point[1])), 1, (0, 255, 0), -1
                )

        return result_image

    def draw_face_mesh(
        self, image: np.ndarray, landmarks: List[Tuple[float, float]]
    ) -> np.ndarray:
        """Disegna la mesh completa del volto."""
        result_image = image.copy()

        # Converte i landmark nel formato MediaPipe
        height, width = image.shape[:2]

        # Crea un oggetto NormalizedLandmarkList per MediaPipe
        face_landmarks = self.mp_face_mesh.FaceMesh().process(
            cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        )

        if face_landmarks.multi_face_landmarks:
            for face_landmark in face_landmarks.multi_face_landmarks:
                self.mp_drawing.draw_landmarks(
                    result_image,
                    face_landmark,
                    self.mp_face_mesh.FACEMESH_CONTOURS,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style(),
                )

        return result_image

    def draw_symmetry_axis(
        self, image: np.ndarray, landmarks: List[Tuple[float, float]]
    ) -> np.ndarray:
        """
        Disegna l'asse di simmetria dal glabella al philtrum.

        Landmark MediaPipe:
        - Glabella (area tra le sopracciglia): landmark 9
        - Philtrum (area naso-labbro): landmark 164
        """
        result_image = image.copy()

        if len(landmarks) > 164:  # Assicurati che abbiamo abbastanza landmark
            # Punto superiore: glabella (tra le sopracciglia)
            glabella = landmarks[9]
            # Punto inferiore: philtrum (area naso-labbro)
            philtrum = landmarks[164]

            # Estendi la linea per tutta l'altezza dell'immagine
            height, width = image.shape[:2]

            # Calcola la direzione della linea
            dx = philtrum[0] - glabella[0]
            dy = philtrum[1] - glabella[1]

            # Evita divisione per zero
            if abs(dy) > 0.1:
                # Calcola i punti di estensione
                # Punto in alto (y=0)
                top_x = glabella[0] - (glabella[1] * dx / dy)
                top_point = (int(top_x), 0)

                # Punto in basso (y=height)
                bottom_x = glabella[0] + ((height - glabella[1]) * dx / dy)
                bottom_point = (int(bottom_x), height)

                # Disegna la linea dell'asse
                cv2.line(result_image, top_point, bottom_point, (255, 0, 0), 2)

                # Disegna i punti di riferimento
                cv2.circle(
                    result_image,
                    (int(glabella[0]), int(glabella[1])),
                    3,
                    (255, 0, 0),
                    -1,
                )
                cv2.circle(
                    result_image,
                    (int(philtrum[0]), int(philtrum[1])),
                    3,
                    (255, 0, 0),
                    -1,
                )

        return result_image
