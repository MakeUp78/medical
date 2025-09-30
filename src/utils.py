"""
Utility functions for facial analysis application.
"""

import cv2
import numpy as np
import math
from typing import List, Tuple, Optional, Dict
from src.scoring_config import scoring_config


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


def calculate_pure_frontal_score(
    landmarks: List[Tuple[float, float]], image_shape=None, config=None
) -> float:
    """
    ALGORITMO COMPLETAMENTE NUOVO - CREATO DA ZERO per l'immagine fornita.

    OBIETTIVO: Score ALTO (0.8-1.0) per pose frontali PERFETTE come nell'esempio.
    CARATTERISTICHE della posa frontale ideale:
    - Viso completamente rivolto verso la camera
    - Simmetria perfetta sinistra-destra
    - Naso centrato tra gli occhi
    - Bocca centrata
    - Occhi allineati orizzontalmente

    Args:
        landmarks: Lista di coordinate (x, y) dei landmark MediaPipe

    Returns:
        float: Score frontalità (0-1, dove 1 = perfettamente frontale come l'esempio)
    """
    if not landmarks or len(landmarks) < 478:
        return 0.0

    try:
        # LANDMARK CHIAVE per analisi frontale
        nose_tip = landmarks[1]  # Punta naso
        left_eye_inner = landmarks[133]  # Angolo interno occhio sinistro
        right_eye_inner = landmarks[362]  # Angolo interno occhio destro
        nose_left = landmarks[131]  # Lato sinistro del naso
        nose_right = landmarks[360]  # Lato destro del naso
        mouth_left = landmarks[61]  # Angolo sinistro bocca
        mouth_right = landmarks[291]  # Angolo destro bocca

        # CALCOLO ASSE CENTRALE DEL VISO
        # In una foto frontale perfetta, tutto è simmetrico rispetto a questo asse
        eyes_center_x = (left_eye_inner[0] + right_eye_inner[0]) / 2.0
        eye_distance = abs(right_eye_inner[0] - left_eye_inner[0])

        # Protezione per visi troppo piccoli o mal rilevati
        if eye_distance < 20:
            return 0.0

        # === CRITERIO 1: OCCHI ALLINEATI (ROLL) ===
        # Occhi orizzontali indicano testa diritta
        eye_height_diff = abs(left_eye_inner[1] - right_eye_inner[1])
        eye_alignment = 1.0 - (eye_height_diff / eye_distance)
        eye_score = max(0.0, min(1.0, eye_alignment))

        # === CRITERIO 2: NASO CENTRATO ===
        # Il naso centrato rispetto agli occhi indica frontalità
        nose_center_x = (nose_left[0] + nose_right[0]) / 2.0
        face_center_x = eyes_center_x  # Centro ideale del viso
        nose_deviation = abs(nose_center_x - face_center_x)
        nose_alignment = 1.0 - (nose_deviation / (eye_distance * 0.3))
        nose_score = max(0.0, min(1.0, nose_alignment))

        # === CRITERIO 3: BOCCA CENTRATA ===
        # La bocca centrata indica frontalità
        mouth_center_x = (mouth_left[0] + mouth_right[0]) / 2.0
        mouth_deviation = abs(mouth_center_x - eyes_center_x)
        mouth_alignment = 1.0 - (mouth_deviation / (eye_distance * 0.4))
        mouth_score = max(0.0, min(1.0, mouth_alignment))

        # === CRITERIO 4: SIMMETRIA GENERALE (CORREZIONE BUG - PIÙ PERMISSIVA) ===
        # PROBLEMA: L'algoritmo precedente era troppo rigoroso per pose frontali
        # SOLUZIONE: Algoritmo più permissivo che tollera micro-variazioni

        # Calcola simmetrie multiple con tolleranza migliorata
        left_eye_nose_dist = abs(left_eye_inner[0] - nose_left[0])
        right_eye_nose_dist = abs(right_eye_inner[0] - nose_right[0])

        # NUOVO: Tolleranza per micro-variazioni (differenze <5px sono considerate simmetriche)
        nose_diff = abs(left_eye_nose_dist - right_eye_nose_dist)
        tolerance_px = 5.0  # Tolleranza in pixel

        if nose_diff <= tolerance_px:
            # Se la differenza è piccolissima, considera altamente simmetrico
            nose_eye_symmetry = 0.95 + (tolerance_px - nose_diff) / tolerance_px * 0.05
        else:
            # Usa calcolo tradizionale solo per differenze significative
            if max(left_eye_nose_dist, right_eye_nose_dist) > 0:
                nose_eye_symmetry = min(left_eye_nose_dist, right_eye_nose_dist) / max(
                    left_eye_nose_dist, right_eye_nose_dist
                )
            else:
                nose_eye_symmetry = 1.0

        # Simmetria occhi-bocca con stessa tolleranza
        left_eye_mouth_dist = abs(left_eye_inner[0] - mouth_left[0])
        right_eye_mouth_dist = abs(right_eye_inner[0] - mouth_right[0])

        mouth_diff = abs(left_eye_mouth_dist - right_eye_mouth_dist)

        if mouth_diff <= tolerance_px:
            eye_mouth_symmetry = (
                0.95 + (tolerance_px - mouth_diff) / tolerance_px * 0.05
            )
        else:
            if max(left_eye_mouth_dist, right_eye_mouth_dist) > 0:
                eye_mouth_symmetry = min(
                    left_eye_mouth_dist, right_eye_mouth_dist
                ) / max(left_eye_mouth_dist, right_eye_mouth_dist)
            else:
                eye_mouth_symmetry = 1.0

        # Simmetria narici con tolleranza
        face_center_x = eyes_center_x  # Centro ideale del viso
        left_nostril_dist = abs(face_center_x - nose_left[0])
        right_nostril_dist = abs(face_center_x - nose_right[0])

        nostril_diff = abs(left_nostril_dist - right_nostril_dist)

        if nostril_diff <= tolerance_px:
            nostril_symmetry = (
                0.95 + (tolerance_px - nostril_diff) / tolerance_px * 0.05
            )
        else:
            if max(left_nostril_dist, right_nostril_dist) > 0:
                nostril_symmetry = min(left_nostril_dist, right_nostril_dist) / max(
                    left_nostril_dist, right_nostril_dist
                )
            else:
                nostril_symmetry = 1.0

        # Combina le tre misure con pesi ottimizzati
        face_symmetry = (
            nose_eye_symmetry * 0.50  # Peso maggiore - più affidabile
            + eye_mouth_symmetry * 0.30  # Importante per rotazioni
            + nostril_symmetry * 0.20  # Meno peso - più sensibile a noise
        )

        # Penalità aggiuntiva se una delle simmetrie è molto bassa (indica rotazione forte)
        min_symmetry = min(nose_eye_symmetry, eye_mouth_symmetry, nostril_symmetry)
        # Penalità aggiuntiva più permissiva per essere meno rigida sulle pose frontali
        if min_symmetry < 0.5:  # CAMBIATO: da 0.7 a 0.5 per essere meno rigorosi
            face_symmetry *= 0.9  # CAMBIATO: da 0.8 a 0.9 per penalità più leggera

        symmetry_score = max(0.0, min(1.0, face_symmetry))

        # === CALCOLI SEPARATI PER YAW E ROLL ===
        # YAW puro: deviazione orizzontale del naso dalla linea centrale
        yaw_score = max(0.0, min(1.0, nose_alignment))  # Usa nose_alignment per YAW

        # ROLL puro: inclinazione della testa basata su disallineamento occhi
        roll_score = max(0.0, min(1.0, eye_alignment))  # Usa eye_alignment per ROLL

        # === SCORE FINALE CON PESI CONFIGURABILI ===
        # Usa i pesi dalla configurazione passata o quella di default
        if config is None:
            config = scoring_config

        base_score = (
            nose_score * config.nose_weight  # Naso centrato (configurabile)
            + mouth_score * config.mouth_weight  # Bocca centrata (configurabile)
            + symmetry_score
            * config.symmetry_weight  # Simmetria generale (configurabile)
            + eye_score * config.eye_weight  # Occhi allineati base (configurabile)
        )

        # PICCOLO BONUS per roll ottimo (occhi perfettamente allineati) - CONFIGURABILE
        # Per privilegiare frame con meno inclinazione
        if eye_score > 0.95:  # Roll quasi perfetto
            roll_bonus = config.roll_bonus_high  # Bonus configurabile
        elif eye_score > 0.90:  # Roll molto buono
            roll_bonus = config.roll_bonus_med  # Bonus configurabile
        else:
            roll_bonus = 1.0  # Nessun bonus

        base_score *= roll_bonus

        # PENALITÀ CONFIGURABILE per pose chiaramente non frontali
        if (
            nose_score < config.penalty_threshold_nose
            or mouth_score < config.penalty_threshold_mouth
            or symmetry_score < config.penalty_threshold_symmetry
        ):
            base_score *= config.penalty_factor  # Penalizza visi decentrati o laterali

        final_score = max(0.0, min(1.0, base_score))

        # === DEBUG INFO per GUI (con pesi configurabili) ===
        calculate_pure_frontal_score._debug_info = {
            "yaw_score": yaw_score,  # YAW puro (rotazione orizzontale)
            "roll_score": roll_score,  # ROLL puro (inclinazione testa)
            "symmetry_score": symmetry_score,  # Simmetria generale
            "nose_score": nose_score,  # Naso centrato (prioritario)
            "mouth_score": mouth_score,  # Bocca centrata
            "eye_score": eye_score,  # Occhi allineati base
            # COMPATIBILITÀ CON TABELLA GUI (vecchi nomi)
            "pitch_score": roll_score,  # PITCH = ROLL per compatibilità
            "simmetria_score": symmetry_score,  # Simmetria per compatibilità
            "dimensione_score": mouth_score,  # Bocca per compatibilità
            "final_score": final_score,
            "eye_distance": eye_distance,
            "nose_deviation": nose_deviation,
            "mouth_center_x": mouth_center_x,
            "face_center_x": face_center_x,
            "roll_bonus": roll_bonus,  # Bonus per roll ottimo
            # Aggiungi pesi attuali per debug
            "weights": config.get_weights_dict(),
            "nose_weight": config.nose_weight,
            "mouth_weight": config.mouth_weight,
            "symmetry_weight": config.symmetry_weight,
            "eye_weight": config.eye_weight,
        }

        return final_score

    except Exception as e:
        print(f"Errore nuovo algoritmo frontale: {e}")
        return 0.0


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
        # Usa algoritmo geometrico puro di frontalità
        score = calculate_pure_frontal_score(landmarks)

        # Estrai i dati di debug se disponibili
        debug_info = getattr(calculate_pure_frontal_score, "_debug_info", {})

        # Calcola approssimazioni di orientamento per compatibilità UI
        if len(landmarks) >= 478:
            nose_tip = landmarks[1]
            left_eye = landmarks[33]
            right_eye = landmarks[362]
            left_mouth = landmarks[61]
            right_mouth = landmarks[291]

            # YAW (rotazione sinistra/destra) dalla posizione del naso
            face_center_x = (left_eye[0] + right_eye[0]) / 2
            face_width = abs(right_eye[0] - left_eye[0])
            if face_width > 0:
                yaw_deviation = (nose_tip[0] - face_center_x) / face_width
                yaw_approx = yaw_deviation * 30  # Scala approssimativa in gradi
            else:
                yaw_approx = 0

            # PITCH (su/giù) dalla posizione verticale del naso
            eye_level = (left_eye[1] + right_eye[1]) / 2
            mouth_level = (left_mouth[1] + right_mouth[1]) / 2
            expected_nose_y = (eye_level + mouth_level) / 2
            face_height = abs(mouth_level - eye_level)
            if face_height > 0:
                pitch_deviation = (nose_tip[1] - expected_nose_y) / face_height
                pitch_approx = pitch_deviation * 20
            else:
                pitch_approx = 0

            # ROLL (inclinazione) dall'angolo degli occhi
            eye_angle = math.atan2(
                right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]
            )
            roll_approx = math.degrees(eye_angle)

            # Descrizione intelligibile basata su frontalità pura
            desc_parts = []
            if score > 0.8:
                desc_parts.append("PERFETTAMENTE FRONTALE")
            elif score > 0.6:
                desc_parts.append("molto frontale")
            elif score > 0.4:
                desc_parts.append("abbastanza frontale")
            else:
                desc_parts.append("non frontale")

            # Aggiungi dettagli se non perfetto
            if abs(yaw_approx) > 5:
                direction = "sinistra" if yaw_approx > 0 else "destra"
                desc_parts.append(f"ruotato {direction}")
            if abs(roll_approx) > 3:
                direction = "sinistra" if roll_approx > 0 else "destra"
                desc_parts.append(f"inclinato {direction}")

            description = " | ".join(desc_parts)

            return score, {
                "method": "pure_frontal",
                "pitch": pitch_approx,
                "yaw": yaw_approx,
                "roll": roll_approx,
                "tilt": roll_approx,
                "description": description,
                "suitable_for_measurement": score > 0.5,
                # DATI DI DEBUG DEL NUOVO ALGORITMO
                "debug": {
                    "nose_score": debug_info.get("nose_score", 0),
                    "eye_level_score": debug_info.get("eye_level_score", 0),
                    "mouth_score": debug_info.get("mouth_score", 0),
                    "eyebrow_score": debug_info.get("eyebrow_score", 0),
                    "nose_offset": debug_info.get("nose_offset", 0),
                    "eye_height_diff": debug_info.get("eye_height_diff", 0),
                    "mouth_offset": debug_info.get("mouth_offset", 0),
                    "nose_symmetry_ratio": debug_info.get("nose_symmetry_ratio", 0),
                    "eye_level_ratio": debug_info.get("eye_level_ratio", 0),
                },
            }

    except Exception as e:
        print(f"Errore scoring avanzato: {e}")

    # Fallback finale - USA NUOVO ALGORITMO
    symmetry_score = calculate_pure_frontal_score(landmarks)
    return symmetry_score, {"method": "pure_frontal_fallback"}


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
