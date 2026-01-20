#!/usr/bin/env python3
"""
Verifica se i landmark sono invertiti o se c'è un problema nella convenzione assi
VERSIONE CON TEST INVERSIONE YAW
"""

import json
import cv2
import mediapipe as mp
import numpy as np
import os

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def calculate_yaw_with_variations(image_path):
    """Calcola Yaw con diverse variazioni per testare quale è corretta"""
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
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            landmarks = face_landmarks.landmark
            
            # Converti landmarks in array
            num_landmarks = len(landmarks)
            all_landmarks = np.zeros((num_landmarks, 2))
            
            for i in range(num_landmarks):
                landmark = landmarks[i]
                x = landmark.x * w
                y = landmark.y * h
                x = max(1, min(w-1, x))
                y = max(1, min(h-1, y))
                all_landmarks[i, 0] = x
                all_landmarks[i, 1] = y
            
            # Indici chiave
            NOSE_TIP = 4
            CHIN = 152
            LEFT_EYE_CORNER = 33
            RIGHT_EYE_CORNER = 263
            LEFT_MOUTH_CORNER = 78
            RIGHT_MOUTH_CORNER = 308
            
            nose_tip = all_landmarks[NOSE_TIP]
            chin = all_landmarks[CHIN]
            left_eye = all_landmarks[LEFT_EYE_CORNER]
            right_eye = all_landmarks[RIGHT_EYE_CORNER]
            left_mouth = all_landmarks[LEFT_MOUTH_CORNER]
            right_mouth = all_landmarks[RIGHT_MOUTH_CORNER]
            
            # Modello 3D originale
            model_points = np.array([
                (0.0, 0.0, 0.0),
                (0.0, -330.0, -65.0),
                (-225.0, 170.0, -135.0),
                (225.0, 170.0, -135.0),
                (-150.0, -150.0, -125.0),
                (150.0, -150.0, -125.0)
            ], dtype=np.float32)
            
            image_points = np.array([
                nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
            ], dtype=np.float32)
            
            focal_length = w
            center = (w/2, h/2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float32)
            
            dist_coeffs = np.zeros((4,1))
            
            success, rotation_vector, translation_vector = cv2.solvePnP(
                model_points, image_points, camera_matrix, dist_coeffs)
            
            if success:
                rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
                
                # CALCOLO ORIGINALE
                yaw_original = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi
                
                # TEST 1: Inverti segno
                yaw_inverted_sign = -yaw_original
                
                # TEST 2: Inverti indici matrice
                yaw_inverted_indices = np.arctan2(rotation_matrix[0,0], rotation_matrix[1,0]) * 180.0 / np.pi
                
                # TEST 3: Inverti segno con indici invertiti
                yaw_both_inverted = -yaw_inverted_indices
                
                return {
                    'yaw_original': yaw_original,
                    'yaw_inverted_sign': yaw_inverted_sign,
                    'yaw_inverted_indices': yaw_inverted_indices,
                    'yaw_both_inverted': yaw_both_inverted,
                    'nose_x': nose_tip[0],
                    'left_eye_x': left_eye[0],
                    'right_eye_x': right_eye[0],
                    'center_x': w / 2
                }
    
    return None

def analyze_landmarks(image_path):
    """Analizza i landmark e verifica la geometria"""
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
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            landmarks = face_landmarks.landmark
            
            # Indici chiave
            NOSE_TIP = 4
            LEFT_EYE_CORNER = 33  # Questo è l'occhio SINISTRO della persona
            RIGHT_EYE_CORNER = 263  # Questo è l'occhio DESTRO della persona
            
            nose = landmarks[NOSE_TIP]
            left_eye = landmarks[LEFT_EYE_CORNER]
            right_eye = landmarks[RIGHT_EYE_CORNER]
            
            # Converti in pixel
            nose_x = nose.x * w
            left_eye_x = left_eye.x * w
            right_eye_x = right_eye.x * w
            
            return {
                'nose_x': nose_x,
                'left_eye_x': left_eye_x,
                'right_eye_x': right_eye_x,
                'width': w,
                'center_x': w / 2
            }
    
    return None

def main():
    print("=" * 120)
    print(" TEST INVERSIONE YAW - QUALE FORMULA È CORRETTA?")
    print("=" * 120)
    print()
    
    # Carica JSON
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    print("🧪 TEST: Confronto 4 varianti di calcolo Yaw con geometria reale")
    print()
    print("LEGENDA GEOMETRICA:")
    print("  • Naso CENTRATO (offset ~0px) = Viso FRONTALE → Yaw dovrebbe essere ~0°")
    print("  • Naso a SINISTRA (offset negativo) = Viso girato a SINISTRA → Yaw dovrebbe essere NEGATIVO")
    print("  • Naso a DESTRA (offset positivo) = Viso girato a DESTRA → Yaw dovrebbe essere POSITIVO")
    print()
    print("-" * 120)
    print()
    
    print(f"{'Frame':12} | {'JSON':8} | {'Original':9} | {'Invertito':10} | {'Indici Inv':11} | {'Entrambi':9} | {'Offset Naso':12} | Geometria Reale")
    print("-" * 120)
    
    results_data = []
    
    for frame_data in json_data['frames']:
        filename = frame_data['filename']
        yaw_json = frame_data['pose']['yaw']
        image_path = os.path.join(SESSION_DIR, filename)
        
        yaw_data = calculate_yaw_with_variations(image_path)
        
        if yaw_data:
            nose_offset = yaw_data['nose_x'] - yaw_data['center_x']
            
            # Interpretazione geometrica
            if abs(nose_offset) < 30:
                geom = "💚 FRONTALE"
            elif nose_offset < -30:
                geom = "🔵 SINISTRA"
            else:
                geom = "🔴 DESTRA"
            
            print(f"{filename:12} | {yaw_json:7.2f}° | {yaw_data['yaw_original']:8.2f}° | {yaw_data['yaw_inverted_sign']:9.2f}° | {yaw_data['yaw_inverted_indices']:10.2f}° | {yaw_data['yaw_both_inverted']:8.2f}° | {nose_offset:+10.1f}px | {geom}")
            
            results_data.append({
                'filename': filename,
                'yaw_json': yaw_json,
                'yaw_original': yaw_data['yaw_original'],
                'yaw_inverted_sign': yaw_data['yaw_inverted_sign'],
                'nose_offset': nose_offset,
                'geometry': 'FRONT' if abs(nose_offset) < 30 else ('LEFT' if nose_offset < 0 else 'RIGHT')
            })
    
    print()
    print("=" * 120)
    print()
    print("📊 ANALISI CORRELAZIONE: Quale formula Yaw corrisponde alla geometria reale?")
    print()
    print("-" * 120)
    
    # Analizza correlazione tra offset naso e diverse formule Yaw
    print()
    print("🔍 CORRELAZIONE ATTESA:")
    print("   Se la formula è CORRETTA:")
    print("   • Offset naso NEGATIVO (viso a sinistra) → Yaw NEGATIVO")
    print("   • Offset naso POSITIVO (viso a destra) → Yaw POSITIVO")
    print("   • Offset naso ZERO (frontale) → Yaw ZERO")
    print()
    print("-" * 120)
    print()
    
    # Test frame_01 (frontale) vs frame_07 (girato)
    frame_01_data = results_data[0]  # frame_01
    frame_07_data = results_data[6]  # frame_07
    
    print("📐 CASO TEST: Frame 01 (frontale) vs Frame 07 (girato a destra)")
    print()
    print(f"Frame 01:")
    print(f"  Offset naso: {frame_01_data['nose_offset']:+.1f}px (frontale)")
    print(f"  Yaw ORIGINAL:  {frame_01_data['yaw_original']:+7.2f}°")
    print(f"  Yaw INVERTITO: {frame_01_data['yaw_inverted_sign']:+7.2f}°")
    print(f"  Yaw JSON:      {frame_01_data['yaw_json']:+7.2f}°")
    print()
    print(f"Frame 07:")
    print(f"  Offset naso: {frame_07_data['nose_offset']:+.1f}px (girato a DESTRA)")
    print(f"  Yaw ORIGINAL:  {frame_07_data['yaw_original']:+7.2f}°")
    print(f"  Yaw INVERTITO: {frame_07_data['yaw_inverted_sign']:+7.2f}°")
    print(f"  Yaw JSON:      {frame_07_data['yaw_json']:+7.2f}°")
    print()
    print("-" * 120)
    print()
    
    # Verifica logica
    offset_diff = frame_07_data['nose_offset'] - frame_01_data['nose_offset']
    yaw_orig_diff = frame_07_data['yaw_original'] - frame_01_data['yaw_original']
    yaw_inv_diff = frame_07_data['yaw_inverted_sign'] - frame_01_data['yaw_inverted_sign']
    
    print("🧮 VERIFICA LOGICA:")
    print()
    print(f"Frame 07 ha naso {offset_diff:+.1f}px più a DESTRA di Frame 01")
    print(f"  → Yaw dovrebbe AUMENTARE (diventare più positivo)")
    print()
    print(f"Con formula ORIGINALE:")
    print(f"  Yaw aumenta di: {yaw_orig_diff:+.2f}° {'✅ CORRETTO' if yaw_orig_diff > 0 else '❌ SBAGLIATO'}")
    print()
    print(f"Con formula INVERTITA (segno opposto):")
    print(f"  Yaw aumenta di: {yaw_inv_diff:+.2f}° {'✅ CORRETTO' if yaw_inv_diff > 0 else '❌ SBAGLIATO'}")
    print()
    print("-" * 120)
    print()
    
    # Conclusione
    if yaw_orig_diff > 0 and offset_diff > 0:
        print("✅ RISULTATO: La formula ORIGINALE è CORRETTA")
        print("   Il Yaw nel codice è calcolato correttamente.")
        print()
        print("⚠️  MA: Il JSON mostra valori diversi!")
        print(f"   Frame 01 JSON: {frame_01_data['yaw_json']:.2f}° vs Calcolato: {frame_01_data['yaw_original']:.2f}°")
        print(f"   Frame 07 JSON: {frame_07_data['yaw_json']:.2f}° vs Calcolato: {frame_07_data['yaw_original']:.2f}°")
        print()
        print("💡 CONCLUSIONE:")
        print("   Il problema NON è nel calcolo solvePnP, ma nel dato SALVATO nel JSON.")
        print("   Possibili cause:")
        print("   1. Il JSON salva un valore DIVERSO da quello calcolato")
        print("   2. Esiste una trasformazione/normalizzazione che modifica il Yaw prima del salvataggio")
        print("   3. Race condition: il Yaw salvato appartiene a un frame diverso dall'immagine")
    elif yaw_inv_diff > 0 and offset_diff > 0:
        print("❌ RISULTATO: La formula ORIGINALE è SBAGLIATA, serve INVERSIONE SEGNO")
        print("   Il Yaw dovrebbe essere calcolato con segno opposto:")
        print("   yaw = -np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi")
    else:
        print("⚠️  RISULTATO AMBIGUO: Necessaria analisi più approfondita")
    print()
    print("=" * 120)

if __name__ == "__main__":
    main()
