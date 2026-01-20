#!/usr/bin/env python3
"""
Test diverse configurazioni model_points per trovare quella che produce Yaw semanticamente corretto
"""

import cv2
import mediapipe as mp
import numpy as np
import os

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def calculate_yaw_with_different_models(image_path):
    """Testa diverse configurazioni di model_points"""
    mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    )
    
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    h, w = img.shape[:2]
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mp_face_mesh.process(rgb_img)
    
    if not results.multi_face_landmarks:
        return None
    
    landmarks = results.multi_face_landmarks[0].landmark
    
    # Converti landmarks in array
    all_landmarks = np.zeros((len(landmarks), 2))
    for i in range(len(landmarks)):
        all_landmarks[i, 0] = landmarks[i].x * w
        all_landmarks[i, 1] = landmarks[i].y * h
    
    # Indici chiave
    NOSE_TIP = 4
    CHIN = 152
    LEFT_EYE = 33
    RIGHT_EYE = 263
    LEFT_MOUTH = 78
    RIGHT_MOUTH = 308
    
    nose_tip = all_landmarks[NOSE_TIP]
    chin = all_landmarks[CHIN]
    left_eye = all_landmarks[LEFT_EYE]
    right_eye = all_landmarks[RIGHT_EYE]
    left_mouth = all_landmarks[LEFT_MOUTH]
    right_mouth = all_landmarks[RIGHT_MOUTH]
    
    image_points = np.array([
        nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
    ], dtype=np.float32)
    
    # TEST 1: Configurazione ORIGINALE (quella attuale nel codice)
    model_original = np.array([
        (0.0, 0.0, 0.0),
        (0.0, -330.0, -65.0),
        (-225.0, 170.0, -135.0),
        (225.0, 170.0, -135.0),
        (-150.0, -150.0, -125.0),
        (150.0, -150.0, -125.0)
    ], dtype=np.float32)
    
    # TEST 2: INVERTI SEGNO X (left/right scambiati)
    model_inverted_x = np.array([
        (0.0, 0.0, 0.0),
        (0.0, -330.0, -65.0),
        (225.0, 170.0, -135.0),   # ← X invertito
        (-225.0, 170.0, -135.0),  # ← X invertito
        (150.0, -150.0, -125.0),  # ← X invertito
        (-150.0, -150.0, -125.0)  # ← X invertito
    ], dtype=np.float32)
    
    # TEST 3: SCAMBIA ordine left/right negli image_points
    image_points_swapped = np.array([
        nose_tip, chin, right_eye, left_eye, right_mouth, left_mouth  # ← Scambiati
    ], dtype=np.float32)
    
    # Camera matrix
    focal_length = w
    center = (w/2, h/2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float32)
    dist_coeffs = np.zeros((4,1))
    
    results_dict = {}
    
    # Calcola Yaw con configurazione ORIGINALE
    success, rvec, tvec = cv2.solvePnP(model_original, image_points, camera_matrix, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        results_dict['original'] = yaw
    
    # Calcola Yaw con X INVERTITO
    success, rvec, tvec = cv2.solvePnP(model_inverted_x, image_points, camera_matrix, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        results_dict['inverted_x'] = yaw
    
    # Calcola Yaw con IMAGE POINTS SCAMBIATI
    success, rvec, tvec = cv2.solvePnP(model_original, image_points_swapped, camera_matrix, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        results_dict['swapped_landmarks'] = yaw
    
    # Calcola Yaw con YAW INVERTITO (segno opposto)
    success, rvec, tvec = cv2.solvePnP(model_original, image_points, camera_matrix, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        results_dict['negated_yaw'] = -yaw
    
    # Geometria reale
    nose_offset = nose_tip[0] - (w/2)
    results_dict['nose_offset'] = nose_offset
    
    return results_dict

def main():
    print("=" * 130)
    print(" TROVA IL BUG YAW - TEST CONFIGURAZIONI DIVERSE")
    print("=" * 130)
    print()
    
    print("🎯 OBIETTIVO:")
    print("   Trovare quale configurazione produce Yaw semanticamente CORRETTO:")
    print("   • Viso FRONTALE (naso centrato) → Yaw ~0°")
    print("   • Viso GIRATO A DESTRA (naso offset positivo) → Yaw POSITIVO e lontano da 0")
    print("   • Viso GIRATO A SINISTRA (naso offset negativo) → Yaw NEGATIVO e lontano da 0")
    print()
    print("-" * 130)
    print()
    
    frame_01_path = os.path.join(SESSION_DIR, "frame_01.jpg")
    frame_07_path = os.path.join(SESSION_DIR, "frame_07.jpg")
    
    print("📊 TEST FRAME 01 (FRONTALE):")
    results_01 = calculate_yaw_with_different_models(frame_01_path)
    if results_01:
        print(f"   Geometria: Naso offset = {results_01['nose_offset']:+.1f}px → {'FRONTALE' if abs(results_01['nose_offset']) < 30 else 'GIRATO'}")
        print()
        print(f"   Configurazione ORIGINALE (attuale):      Yaw = {results_01['original']:+7.2f}°")
        print(f"   Con MODEL X INVERTITO:                   Yaw = {results_01['inverted_x']:+7.2f}°")
        print(f"   Con LANDMARK SCAMBIATI:                  Yaw = {results_01['swapped_landmarks']:+7.2f}°")
        print(f"   Con YAW NEGATO (segno opposto):          Yaw = {results_01['negated_yaw']:+7.2f}°")
    
    print()
    print("-" * 130)
    print()
    
    print("📊 TEST FRAME 07 (GIRATO A DESTRA):")
    results_07 = calculate_yaw_with_different_models(frame_07_path)
    if results_07:
        print(f"   Geometria: Naso offset = {results_07['nose_offset']:+.1f}px → {'FRONTALE' if abs(results_07['nose_offset']) < 30 else 'GIRATO A DESTRA'}")
        print()
        print(f"   Configurazione ORIGINALE (attuale):      Yaw = {results_07['original']:+7.2f}°")
        print(f"   Con MODEL X INVERTITO:                   Yaw = {results_07['inverted_x']:+7.2f}°")
        print(f"   Con LANDMARK SCAMBIATI:                  Yaw = {results_07['swapped_landmarks']:+7.2f}°")
        print(f"   Con YAW NEGATO (segno opposto):          Yaw = {results_07['negated_yaw']:+7.2f}°")
    
    print()
    print("=" * 130)
    print()
    print("🔍 ANALISI QUALE CONFIGURAZIONE È CORRETTA:")
    print()
    
    if results_01 and results_07:
        print("REGOLA: Frame 07 ha naso più a DESTRA di Frame 01")
        print(f"        Differenza offset: {results_07['nose_offset'] - results_01['nose_offset']:+.1f}px")
        print(f"        → Yaw dovrebbe AUMENTARE (diventare più positivo) da Frame 01 a Frame 07")
        print()
        
        configs = ['original', 'inverted_x', 'swapped_landmarks', 'negated_yaw']
        names = ['ORIGINALE (attuale)', 'MODEL X INVERTITO', 'LANDMARK SCAMBIATI', 'YAW NEGATO']
        
        for config, name in zip(configs, names):
            yaw_01 = results_01[config]
            yaw_07 = results_07[config]
            diff = yaw_07 - yaw_01
            
            # Verifica logica
            is_correct = diff > 0  # Yaw deve aumentare
            
            # Verifica che frame frontale abbia Yaw vicino a 0
            frame01_near_zero = abs(yaw_01) < abs(yaw_07)
            
            marker = "✅" if (is_correct and frame01_near_zero) else "❌"
            
            print(f"{marker} {name:30}")
            print(f"   Frame 01: {yaw_01:+7.2f}°  |  Frame 07: {yaw_07:+7.2f}°  |  Diff: {diff:+7.2f}°")
            
            if is_correct and frame01_near_zero:
                print(f"   → LOGICA CORRETTA: Yaw aumenta quando naso va a destra E frame frontale ha Yaw più basso")
            elif is_correct:
                print(f"   → Yaw aumenta correttamente, ma frame frontale non ha Yaw più basso")
            else:
                print(f"   → SBAGLIATO: Yaw diminuisce invece di aumentare")
            print()
        
        print("-" * 130)
        print()
        print("💡 SOLUZIONE IDENTIFICATA:")
        print()
        
        # Trova la configurazione corretta
        best_config = None
        for config, name in zip(configs, names):
            yaw_01 = results_01[config]
            yaw_07 = results_07[config]
            diff = yaw_07 - yaw_01
            if diff > 0 and abs(yaw_01) < abs(yaw_07):
                best_config = (config, name)
                break
        
        if best_config:
            config, name = best_config
            print(f"✅ La configurazione CORRETTA è: {name}")
            print()
            if config == 'original':
                print("   Il codice è già corretto! Non serve modificare nulla.")
            elif config == 'inverted_x':
                print("   SOLUZIONE: Invertire il segno della coordinata X nei model_points")
                print("   Cambiare:")
                print("   (-225.0, 170.0, -135.0) → (225.0, 170.0, -135.0)")
                print("   (225.0, 170.0, -135.0)  → (-225.0, 170.0, -135.0)")
            elif config == 'swapped_landmarks':
                print("   SOLUZIONE: Scambiare left_eye con right_eye negli image_points")
                print("   Oppure invertire gli indici MEDIAPIPE:")
                print("   LEFT_EYE_CORNER = 263")
                print("   RIGHT_EYE_CORNER = 33")
            elif config == 'negated_yaw':
                print("   SOLUZIONE: Negare il segno dello Yaw dopo il calcolo")
                print("   yaw = -np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi")
        else:
            print("❌ Nessuna configurazione testata produce valori corretti!")
            print("   Il problema potrebbe essere più complesso.")

if __name__ == "__main__":
    main()
