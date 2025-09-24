"""
Utility functions for facial analysis application.
"""

import cv2
import numpy as np
import math
from typing import List, Tuple, Optional, Dict


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
    Sistema semplice ma affidabile basato su simmetria facciale.
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


def calculate_improved_frontal_score(landmarks: List[Tuple[float, float]]) -> float:
    """
    Algoritmo migliorato per calcolo frontalità basato su geometria facciale.
    Più accurato e affidabile del sistema 3D che aveva problemi.
    """
    if len(landmarks) < 468:
        return 0.0

    try:
        # Landmark chiave per valutazione frontalità
        nose_tip = landmarks[1]  # Punta naso
        left_eye_outer = landmarks[33]  # Occhio sx esterno
        right_eye_outer = landmarks[362]  # Occhio dx esterno
        left_mouth = landmarks[61]  # Bocca sx
        right_mouth = landmarks[291]  # Bocca dx
        chin = landmarks[152]  # Mento

        # 1. SIMMETRIA ORIZZONTALE MIGLIORATA (peso: 55%)
        # Centro facciale basato su occhi
        face_center_x = (left_eye_outer[0] + right_eye_outer[0]) / 2

        # Distanza naso dal centro (dovrebbe essere ~0 per frontalità)
        nose_deviation = abs(nose_tip[0] - face_center_x)

        # Asimmetria occhi-naso (distanze dovrebbero essere uguali)
        left_eye_nose_dist = abs(nose_tip[0] - left_eye_outer[0])
        right_eye_nose_dist = abs(right_eye_outer[0] - nose_tip[0])
        eye_asymmetry = abs(left_eye_nose_dist - right_eye_nose_dist)

        # Asimmetria bocca-naso
        left_mouth_nose_dist = abs(nose_tip[0] - left_mouth[0])
        right_mouth_nose_dist = abs(right_mouth[0] - nose_tip[0])
        mouth_asymmetry = abs(left_mouth_nose_dist - right_mouth_nose_dist)

        # Larghezza facciale per normalizzazione
        face_width = abs(left_eye_outer[0] - right_eye_outer[0])
        if face_width == 0:
            return 0.0

        # Score simmetria normalizzato (1 = perfetto, 0 = pessimo)
        total_asymmetry = (
            nose_deviation + eye_asymmetry + mouth_asymmetry
        ) / face_width
        # RIDUCENDO la penalizzazione per avere score più alti
        symmetry_score = max(
            0.0, 1.0 - total_asymmetry * 1.2
        )  # Era *2.0, ora *1.2 per essere meno severi

        # 2. ALLINEAMENTO VERTICALE (peso: 30%)
        # Naso, centro bocca e mento dovrebbero essere allineati
        mouth_center_x = (left_mouth[0] + right_mouth[0]) / 2

        nose_mouth_alignment = abs(nose_tip[0] - mouth_center_x)
        nose_chin_alignment = abs(nose_tip[0] - chin[0])

        vertical_deviation = (nose_mouth_alignment + nose_chin_alignment) / face_width
        # RIDUCENDO anche qui la severità
        vertical_score = max(
            0.0, 1.0 - vertical_deviation * 2.0
        )  # Era *3.0, ora *2.0 per essere meno severi

        # 3. STABILITÀ ANGOLARE OCCHI (peso: 15%)
        # Gli occhi dovrebbero essere orizzontali per frontalità
        eye_angle = abs(
            math.atan2(
                right_eye_outer[1] - left_eye_outer[1],
                right_eye_outer[0] - left_eye_outer[0],
            )
        )

        # Converti in score (angolo piccolo = score alto) - MENO SEVERO
        eye_angle_score = max(
            0.0, 1.0 - (eye_angle / 0.35)
        )  # Era 0.2, ora 0.35 (~20°) per tolleranza maggiore

        # SCORE FINALE PESATO (3 componenti principali)
        final_score = (
            symmetry_score * 0.55  # Simmetria aumentata (era 0.45)
            + vertical_score * 0.30  # Allineamento verticale aumentato (era 0.25)
            + eye_angle_score * 0.15  # Stabilità angolare occhi invariata
        )

        # DEBUG: Salva sempre i dettagli per debug
        calculate_improved_frontal_score._debug_info = {
            "symmetry_score": symmetry_score,
            "vertical_score": vertical_score,
            "eye_angle_score": eye_angle_score,
            "final_score": final_score,
            "nose_deviation": nose_deviation,
            "eye_asymmetry": eye_asymmetry,
            "mouth_asymmetry": mouth_asymmetry,
            "eye_angle_deg": math.degrees(eye_angle),
        }

        return max(0.0, min(1.0, final_score))

    except Exception:
        # Fallback al sistema originale in caso di errore
        return get_face_orientation_score(landmarks)


def get_advanced_orientation_score(
    landmarks: List[Tuple[float, float]], image_size: Tuple[int, int]
) -> Tuple[float, Dict]:
    """
    Calcola punteggio di orientamento usando algoritmo geometrico MIGLIORATO.
    SOSTITUISCE il sistema 3D complesso che aveva problemi con solvePnP.

    Args:
        landmarks: Lista dei landmark facciali
        image_size: Dimensioni immagine (width, height)

    Returns:
        Tuple (orientation_score, head_pose_data)
    """
    try:
        # Usa algoritmo geometrico semplice ma molto più accurato
        score = calculate_improved_frontal_score(landmarks)

        # Estrai i dati di debug se disponibili
        debug_info = getattr(calculate_improved_frontal_score, "_debug_info", {})

        # Calcola approssimazioni di orientamento per compatibilità UI
        if len(landmarks) >= 468:
            nose_tip = landmarks[1]
            left_eye = landmarks[33]
            right_eye = landmarks[362]
            left_mouth = landmarks[61]
            right_mouth = landmarks[291]

            # YAW (rotazione sinistra/destra) da asimmetria naso
            face_center_x = (left_eye[0] + right_eye[0]) / 2
            face_width = abs(right_eye[0] - left_eye[0])
            yaw_deviation = (nose_tip[0] - face_center_x) / face_width
            yaw_approx = yaw_deviation * 45  # Scala approssimativa in gradi

            # PITCH (su/giù) da posizione verticale naso rispetto a occhi/bocca
            eye_level = (left_eye[1] + right_eye[1]) / 2
            mouth_level = (left_mouth[1] + right_mouth[1]) / 2
            expected_nose_y = (eye_level + mouth_level) / 2
            face_height = abs(mouth_level - eye_level)
            if face_height > 0:
                pitch_deviation = (nose_tip[1] - expected_nose_y) / face_height
                pitch_approx = pitch_deviation * 30  # Scala in gradi
            else:
                pitch_approx = 0

            # ROLL (inclinazione) da angolo occhi
            eye_angle = math.atan2(
                right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]
            )
            roll_approx = math.degrees(eye_angle)

            # Descrizione intelligibile
            desc_parts = []
            if abs(yaw_approx) > 8:
                direction = "sinistra" if yaw_approx > 0 else "destra"
                desc_parts.append(f"ruotato {direction} ({abs(yaw_approx):.0f}°)")
            else:
                desc_parts.append("frontale")

            if abs(pitch_approx) > 6:
                direction = "basso" if pitch_approx > 0 else "alto"
                desc_parts.append(f"guardando {direction}")

            if abs(roll_approx) > 5:
                direction = "sinistra" if roll_approx > 0 else "destra"
                desc_parts.append(f"inclinato {direction}")

            description = " | ".join(desc_parts) if desc_parts else "ben posizionato"

            return score, {
                "method": "geometric_improved",
                "pitch": pitch_approx,
                "yaw": yaw_approx,
                "roll": roll_approx,
                "tilt": roll_approx,
                "description": description,
                "suitable_for_measurement": score > 0.5,
                # DATI DI DEBUG DETTAGLIATI
                "debug": {
                    "symmetry_score": debug_info.get("symmetry_score", 0),
                    "vertical_score": debug_info.get("vertical_score", 0),
                    "angle_score": debug_info.get("angle_score", 0),
                    "nose_deviation": debug_info.get("nose_deviation", 0),
                    "eye_asymmetry": debug_info.get("eye_asymmetry", 0),
                    "mouth_asymmetry": debug_info.get("mouth_asymmetry", 0),
                    "eye_angle_deg": debug_info.get("eye_angle_deg", 0),
                },
            }

    except Exception as e:
        print(f"Errore scoring avanzato: {e}")

    # Fallback finale
    symmetry_score = get_face_orientation_score(landmarks)
    return symmetry_score, {"method": "symmetry_fallback"}


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
