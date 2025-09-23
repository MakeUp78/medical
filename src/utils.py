"""
Utility functions for facial analysis application.
"""

import cv2
import numpy as np
import math
from typing import List, Tuple, Optional


def calculate_distance(
    point1: Tuple[float, float], point2: Tuple[float, float]
) -> float:
    """Calcola la distanza euclidea tra due punti."""
    return math.sqrt((point1[0] - point2[0]) ** 2 + (point1[1] - point2[1]) ** 2)


def calculate_angle(
    point1: Tuple[float, float],
    vertex: Tuple[float, float],
    point2: Tuple[float, float],
) -> float:
    """Calcola l'angolo formato da tre punti."""
    vector1 = (point1[0] - vertex[0], point1[1] - vertex[1])
    vector2 = (point2[0] - vertex[0], point2[1] - vertex[1])

    dot_product = vector1[0] * vector2[0] + vector1[1] * vector2[1]
    magnitude1 = math.sqrt(vector1[0] ** 2 + vector1[1] ** 2)
    magnitude2 = math.sqrt(vector2[0] ** 2 + vector2[1] ** 2)

    if magnitude1 == 0 or magnitude2 == 0:
        return 0

    cos_angle = dot_product / (magnitude1 * magnitude2)
    cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]

    return math.degrees(math.acos(cos_angle))


def get_face_orientation_score(landmarks: List[Tuple[float, float]]) -> float:
    """
    Calcola un punteggio di frontalità del volto basato sui landmark.
    Returns: valore tra 0 e 1, dove 1 indica massima frontalità.
    """
    if len(landmarks) < 468:
        return 0.0

    # Indici dei landmark chiave per valutare la frontalità
    nose_tip = landmarks[1]  # Punta del naso
    left_eye_outer = landmarks[33]  # Angolo esterno occhio sinistro
    right_eye_outer = landmarks[362]  # Angolo esterno occhio destro
    left_mouth = landmarks[61]  # Angolo sinistro bocca
    right_mouth = landmarks[291]  # Angolo destro bocca

    # Calcola simmetria orizzontale
    eye_symmetry = abs(
        (nose_tip[0] - left_eye_outer[0]) - (right_eye_outer[0] - nose_tip[0])
    )
    mouth_symmetry = abs((nose_tip[0] - left_mouth[0]) - (right_mouth[0] - nose_tip[0]))

    # Normalizza i valori di simmetria
    face_width = calculate_distance(left_eye_outer, right_eye_outer)
    if face_width == 0:
        return 0.0

    eye_symmetry_normalized = eye_symmetry / face_width
    mouth_symmetry_normalized = mouth_symmetry / face_width

    # Calcola punteggio finale (più basso è meglio per la simmetria)
    symmetry_score = 1.0 - min(
        1.0, (eye_symmetry_normalized + mouth_symmetry_normalized) / 2
    )

    return symmetry_score


def resize_image_keep_aspect(
    image: np.ndarray, max_width: int, max_height: int
) -> np.ndarray:
    """Ridimensiona un'immagine mantenendo le proporzioni."""
    height, width = image.shape[:2]

    # Calcola il fattore di scala
    scale_w = max_width / width
    scale_h = max_height / height
    scale = min(scale_w, scale_h)

    # Calcola le nuove dimensioni
    new_width = int(width * scale)
    new_height = int(height * scale)

    return cv2.resize(image, (new_width, new_height))


def draw_landmark(
    image: np.ndarray,
    point: Tuple[float, float],
    color: Tuple[int, int, int] = (0, 255, 0),
    radius: int = 2,
) -> None:
    """Disegna un landmark sull'immagine."""
    cv2.circle(image, (int(point[0]), int(point[1])), radius, color, -1)


def draw_line(
    image: np.ndarray,
    point1: Tuple[float, float],
    point2: Tuple[float, float],
    color: Tuple[int, int, int] = (255, 0, 0),
    thickness: int = 2,
) -> None:
    """Disegna una linea tra due punti sull'immagine."""
    cv2.line(
        image,
        (int(point1[0]), int(point1[1])),
        (int(point2[0]), int(point2[1])),
        color,
        thickness,
    )


def add_text_with_background(
    image: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: float = 0.6,
    color: Tuple[int, int, int] = (255, 255, 255),
    bg_color: Tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Aggiunge testo con sfondo all'immagine."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 1

    # Calcola dimensioni del testo
    (text_width, text_height), baseline = cv2.getTextSize(
        text, font, font_scale, thickness
    )

    # Disegna rettangolo di sfondo
    cv2.rectangle(
        image,
        (position[0] - 2, position[1] - text_height - 2),
        (position[0] + text_width + 2, position[1] + baseline + 2),
        bg_color,
        -1,
    )

    # Disegna il testo
    cv2.putText(image, text, position, font, font_scale, color, thickness)
