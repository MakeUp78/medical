"""
Face detection and landmark extraction using MediaPipe.
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import List, Tuple, Optional
from src.utils import get_face_orientation_score


class FaceDetector:
    def __init__(self):
        """Inizializza il detector di volti MediaPipe."""
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Configura MediaPipe Face Mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def detect_face_landmarks(
        self, image: np.ndarray
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Rileva i landmark facciali in un'immagine.
        Returns: Lista di coordinate (x, y) dei landmark o None se nessun volto rilevato.
        """
        # Converte BGR in RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Processo di rilevamento
        results = self.face_mesh.process(rgb_image)

        if not results.multi_face_landmarks:
            return None

        # Estrae i landmark del primo volto rilevato
        face_landmarks = results.multi_face_landmarks[0]
        height, width = image.shape[:2]

        landmarks = []
        for landmark in face_landmarks.landmark:
            x = int(landmark.x * width)
            y = int(landmark.y * height)
            landmarks.append((x, y))

        return landmarks

    def calculate_frontal_score(self, landmarks: List[Tuple[float, float]]) -> float:
        """Calcola il punteggio di frontalità del volto."""
        return get_face_orientation_score(landmarks)

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
