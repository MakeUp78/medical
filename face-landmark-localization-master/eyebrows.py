"""
eyebrows.py — estrae i pixel sopraccigliari da una foto con un volto.

Uso base (file):
    from eyebrows import extract_eyebrows
    pixels_img, overlay_img = extract_eyebrows("foto.jpg")

Uso da array numpy (API/backend):
    from eyebrows import extract_eyebrows_from_array
    res = extract_eyebrows_from_array(image_bgr, predictor_path="/path/to/shape_predictor_68_face_landmarks.dat")
    # res["face_detected"], res["left_mask"], res["right_mask"],
    # res["left_area"], res["right_area"], res["pixels_img"], res["overlay_img"]
"""

import cv2
import dlib
import numpy as np
import os

_predictor_cache = {}   # key = percorso assoluto, value = dlib predictor

def _get_predictor(path: str = "shape_predictor_68_face_landmarks.dat"):
    """Carica (e mette in cache) il predictor dlib per il percorso dato."""
    abs_path = os.path.abspath(path)
    if abs_path not in _predictor_cache:
        _predictor_cache[abs_path] = dlib.shape_predictor(abs_path)
    return _predictor_cache[abs_path]

# alias backward-compat (usato da _get_predictor() chiamate vecchie)
_predictor = None


def _segment_one(gray, image, pts, face_h):
    xs, ys = pts[:, 0], pts[:, 1]
    pad_x    = face_h // 12
    pad_up   = face_h // 10
    pad_down = face_h // 18   # ridotto rispetto a sopra → meno pelle in ombra sotto l'arcata
    h, w  = gray.shape
    x1 = max(0, xs.min() - pad_x)
    y1 = max(0, ys.min() - pad_up)
    x2 = min(w, xs.max() + pad_x)
    y2 = min(h, ys.max() + pad_down)

    roi       = gray[y1:y2, x1:x2]
    skin_tone = int(np.percentile(roi, 80))
    thresh    = int(np.clip(skin_tone - skin_tone // 4 - 10, 35, 150))
    _, dark   = cv2.threshold(roi, thresh, 255, cv2.THRESH_BINARY_INV)

    # striscia poligonale attorno alla polilinea dei landmark
    loc      = pts - np.array([x1, y1])
    half     = face_h // 14
    poly     = np.vstack([loc - [0, half], (loc + [0, half])[::-1]]).astype(np.int32)
    poly[:, 0] = np.clip(poly[:, 0], 0, x2 - x1 - 1)
    poly[:, 1] = np.clip(poly[:, 1], 0, y2 - y1 - 1)
    stripe   = np.zeros_like(roi)
    cv2.fillPoly(stripe, [poly], 255)

    final = cv2.bitwise_and(dark, stripe)
    final = cv2.morphologyEx(final, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

    # tieni solo il blob più grande → elimina frammenti di pelle staccati
    n, labels, stats, _ = cv2.connectedComponentsWithStats(final, connectivity=8)
    if n > 1:
        biggest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        final   = np.where(labels == biggest, 255, 0).astype(np.uint8)

    final = cv2.morphologyEx(final, cv2.MORPH_CLOSE,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    return final, (x1, y1, x2, y2)


def extract_eyebrows(image_path: str, predictor_path: str = "shape_predictor_68_face_landmarks.dat"):
    """
    Parametri
    ---------
    image_path     : percorso dell'immagine (deve contenere esattamente un volto)
    predictor_path : percorso al file .dat dlib

    Ritorna
    -------
    pixels_img : immagine BGR con solo i pixel sopraccigliari su sfondo nero
    overlay_img: immagine BGR originale con sopracciglia evidenziate in verde

    Solleva ValueError se non viene rilevato nessun volto.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Impossibile leggere: {image_path}")
    res = extract_eyebrows_from_array(image, predictor_path=predictor_path)
    if not res["face_detected"]:
        raise ValueError("Nessun volto rilevato nell'immagine.")
    return res["pixels_img"], res["overlay_img"]


def extract_eyebrows_from_array(
    image_bgr: np.ndarray,
    predictor_path: str = "shape_predictor_68_face_landmarks.dat",
) -> dict:
    """
    Versione array: accetta numpy BGR direttamente (es. decodificato da base64).

    Ritorna dict con:
      face_detected : bool
      left_mask     : numpy uint8 maschera binaria sopracciglio sinistro
      right_mask    : numpy uint8 maschera binaria sopracciglio destro
      left_area     : int pixel sopracciglio sinistro
      right_area    : int pixel sopracciglio destro
      pixels_img    : numpy BGR solo pixel sopraccigliari su sfondo nero
      overlay_img   : numpy BGR originale con sopracciglia evidenziate
    """
    h, w = image_bgr.shape[:2]
    result = dict(
        face_detected=False,
        left_mask=np.zeros((h, w), dtype=np.uint8),
        right_mask=np.zeros((h, w), dtype=np.uint8),
        left_area=0, right_area=0,
        pixels_img=np.zeros_like(image_bgr),
        overlay_img=image_bgr.copy(),
    )

    predictor = _get_predictor(predictor_path)
    gray      = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    detector  = dlib.get_frontal_face_detector()
    faces     = detector(gray, 1)
    if not faces:
        return result

    result["face_detected"] = True
    face   = max(faces, key=lambda r: r.width() * r.height())
    lm     = predictor(gray, face)
    lpts   = np.array([(lm.part(i).x, lm.part(i).y) for i in range(17, 22)])
    rpts   = np.array([(lm.part(i).x, lm.part(i).y) for i in range(22, 27)])
    face_h = face.height()

    left_blob,  bl = _segment_one(gray, image_bgr, lpts, face_h)
    right_blob, br = _segment_one(gray, image_bgr, rpts, face_h)

    lx1, ly1, lx2, ly2 = bl
    rx1, ry1, rx2, ry2 = br

    result["left_mask"][ly1:ly2, lx1:lx2]  = cv2.bitwise_or(
        result["left_mask"][ly1:ly2, lx1:lx2], left_blob)
    result["right_mask"][ry1:ry2, rx1:rx2] = cv2.bitwise_or(
        result["right_mask"][ry1:ry2, rx1:rx2], right_blob)

    result["left_area"]  = int(np.count_nonzero(result["left_mask"]))
    result["right_area"] = int(np.count_nonzero(result["right_mask"]))

    full_mask = cv2.bitwise_or(result["left_mask"], result["right_mask"])
    result["pixels_img"] = cv2.bitwise_and(image_bgr, image_bgr, mask=full_mask)

    overlay = image_bgr.copy()
    tint    = np.zeros_like(image_bgr)
    tint[full_mask > 0] = (0, 200, 80)
    overlay = cv2.addWeighted(overlay, 1.0, tint, 0.45, 0)
    dilated = cv2.dilate(full_mask, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
    for cnt in contours:
        cv2.drawContours(overlay, [cv2.approxPolyDP(cnt, 2.5, True)], -1, (0, 255, 60), 2)
    result["overlay_img"] = overlay
    return result
