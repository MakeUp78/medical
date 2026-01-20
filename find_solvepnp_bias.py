#!/usr/bin/env python3
"""
RICERCA BIAS solvePnP: Trova la correzione esatta per Yaw/Pitch/Roll

Testa diverse ipotesi:
1. Inversione di segno (-yaw)
2. Inversione coordinate modello 3D (X invertito)
3. Diverso ordine angoli di Eulero
4. Diversa formula estrazione angoli
5. Offset costante
"""

import cv2
import mediapipe as mp
import numpy as np
import json

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def get_landmarks(image_path):
    """Estrae landmark MediaPipe da immagine"""
    mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    )
    
    img = cv2.imread(image_path)
    if img is None:
        return None, None, None
    
    h, w = img.shape[:2]
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mp_face_mesh.process(rgb_img)
    
    if not results.multi_face_landmarks:
        return None, None, None
    
    landmarks = results.multi_face_landmarks[0].landmark
    landmarks_array = np.zeros((len(landmarks), 2))
    for i in range(len(landmarks)):
        landmarks_array[i, 0] = landmarks[i].x * w
        landmarks_array[i, 1] = landmarks[i].y * h
    
    return landmarks_array, w, h

def calculate_geometric_reference(landmarks_array):
    """Calcolo geometrico di riferimento (ground truth)"""
    NOSE_TIP = 4
    LEFT_EYE = 33
    RIGHT_EYE = 263
    
    nose_tip = landmarks_array[NOSE_TIP]
    left_eye = landmarks_array[LEFT_EYE]
    right_eye = landmarks_array[RIGHT_EYE]
    
    eye_center_x = (left_eye[0] + right_eye[0]) / 2.0
    eye_distance = abs(right_eye[0] - left_eye[0])
    
    yaw = 0.0
    if eye_distance > 0:
        nose_offset = nose_tip[0] - eye_center_x
        nose_relative = nose_offset / (eye_distance / 2.0)
        yaw = nose_relative * 30.0
    
    return {'yaw': yaw, 'nose_offset': nose_offset}

def test_variant(variant_name, landmarks_array, w, h):
    """Testa una variante di solvePnP"""
    NOSE_TIP = 4
    CHIN = 152
    LEFT_EYE = 33
    RIGHT_EYE = 263
    LEFT_MOUTH = 78
    RIGHT_MOUTH = 308
    
    nose_tip = landmarks_array[NOSE_TIP]
    chin = landmarks_array[CHIN]
    left_eye = landmarks_array[LEFT_EYE]
    right_eye = landmarks_array[RIGHT_EYE]
    left_mouth = landmarks_array[LEFT_MOUTH]
    right_mouth = landmarks_array[RIGHT_MOUTH]
    
    # VARIANTI MODELLO 3D
    if variant_name == "ORIGINALE":
        model_points = np.array([
            (0.0, 0.0, 0.0),
            (0.0, -330.0, -65.0),
            (-225.0, 170.0, -135.0),
            (225.0, 170.0, -135.0),
            (-150.0, -150.0, -125.0),
            (150.0, -150.0, -125.0)
        ], dtype=np.float32)
    
    elif variant_name == "X_INVERTITO":
        # Inverti coordinate X del modello
        model_points = np.array([
            (0.0, 0.0, 0.0),
            (0.0, -330.0, -65.0),
            (225.0, 170.0, -135.0),    # Scambiato
            (-225.0, 170.0, -135.0),   # Scambiato
            (150.0, -150.0, -125.0),   # Scambiato
            (-150.0, -150.0, -125.0)   # Scambiato
        ], dtype=np.float32)
    
    elif variant_name == "SCALA_RIDOTTA":
        # Scala ridotta del modello (più piccolo)
        scale = 0.5
        model_points = np.array([
            (0.0, 0.0, 0.0),
            (0.0, -330.0*scale, -65.0*scale),
            (-225.0*scale, 170.0*scale, -135.0*scale),
            (225.0*scale, 170.0*scale, -135.0*scale),
            (-150.0*scale, -150.0*scale, -125.0*scale),
            (150.0*scale, -150.0*scale, -125.0*scale)
        ], dtype=np.float32)
    
    else:
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
    
    # VARIANTI FOCAL LENGTH
    if "FOCAL_2X" in variant_name:
        focal_length = w * 2
    elif "FOCAL_HALF" in variant_name:
        focal_length = w * 0.5
    elif "FOCAL_1.5X" in variant_name:
        focal_length = w * 1.5
    else:
        focal_length = w
    
    center = (w/2, h/2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float32)
    
    dist_coeffs = np.zeros((4,1))
    
    success, rvec, tvec = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs)
    
    if not success:
        return None
    
    rmat, _ = cv2.Rodrigues(rvec)
    
    # VARIANTI ESTRAZIONE ANGOLI
    if "YAW_NEGATO" in variant_name:
        yaw = -np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
    elif "YAW_ALT1" in variant_name:
        yaw = np.arctan2(-rmat[1,0], rmat[0,0]) * 180.0 / np.pi
    elif "YAW_ALT2" in variant_name:
        yaw = np.arctan2(rmat[0,1], rmat[0,0]) * 180.0 / np.pi
    else:
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
    
    sy = np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)
    pitch = np.arctan2(-rmat[2,0], sy) * 180.0 / np.pi
    roll = np.arctan2(rmat[2,1], rmat[2,2]) * 180.0 / np.pi
    
    return {'yaw': yaw, 'pitch': pitch, 'roll': roll}

def main():
    print("=" * 100)
    print("RICERCA BIAS solvePnP")
    print("=" * 100)
    print()
    
    # Carica JSON
    json_path = f"{SESSION_DIR}/best_frames_data.json"
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    # Test su frame frontale e girato
    test_frames = [
        ('frame_01.jpg', 'FRONTALE'),
        ('frame_07.jpg', 'GIRATO DESTRA')
    ]
    
    # Varianti da testare
    variants = [
        "ORIGINALE",
        "X_INVERTITO",
        "SCALA_RIDOTTA",
        "ORIGINALE_YAW_NEGATO",
        "ORIGINALE_YAW_ALT1",
        "ORIGINALE_YAW_ALT2",
        "ORIGINALE_FOCAL_2X",
        "ORIGINALE_FOCAL_HALF",
        "ORIGINALE_FOCAL_1.5X"
    ]
    
    results = {}
    
    for filename, description in test_frames:
        image_path = f"{SESSION_DIR}/{filename}"
        landmarks, w, h = get_landmarks(image_path)
        
        if landmarks is None:
            continue
        
        # Ground truth geometrico
        geometric = calculate_geometric_reference(landmarks)
        
        print(f"{'='*100}")
        print(f"FRAME: {filename} ({description})")
        print(f"{'='*100}")
        print()
        print(f"🎯 GROUND TRUTH (geometrico):")
        print(f"   Yaw: {geometric['yaw']:+.2f}°  (nose offset: {geometric['nose_offset']:+.1f}px)")
        print()
        print(f"🔬 TEST VARIANTI solvePnP:")
        print()
        
        frame_results = []
        
        for variant in variants:
            result = test_variant(variant, landmarks, w, h)
            if result:
                yaw = result['yaw']
                
                # Calcola errore rispetto a ground truth
                error = abs(yaw - geometric['yaw'])
                
                # Verifica coerenza semantica
                semantic_ok = (geometric['nose_offset'] > 10 and yaw > 0) or \
                              (geometric['nose_offset'] < -10 and yaw < 0) or \
                              (abs(geometric['nose_offset']) < 10 and abs(yaw) < 5)
                
                marker = "✅" if semantic_ok and error < 5 else ("⚠️" if semantic_ok else "❌")
                
                print(f"   {marker} {variant:25s} → Yaw: {yaw:+7.2f}° (err: {error:5.2f}°)")
                
                frame_results.append({
                    'variant': variant,
                    'yaw': yaw,
                    'error': error,
                    'semantic_ok': semantic_ok
                })
        
        results[filename] = {
            'geometric': geometric,
            'variants': frame_results
        }
        
        print()
    
    # ANALISI FINALE
    print("=" * 100)
    print("ANALISI FINALE - MIGLIORE VARIANTE")
    print("=" * 100)
    print()
    
    # Trova variante con errore minimo medio
    variant_scores = {}
    for variant in variants:
        total_error = 0
        count = 0
        all_semantic_ok = True
        
        for filename in results:
            for v_result in results[filename]['variants']:
                if v_result['variant'] == variant:
                    total_error += v_result['error']
                    count += 1
                    if not v_result['semantic_ok']:
                        all_semantic_ok = False
        
        if count > 0:
            avg_error = total_error / count
            variant_scores[variant] = {
                'avg_error': avg_error,
                'semantic_ok': all_semantic_ok
            }
    
    # Ordina per errore medio
    sorted_variants = sorted(variant_scores.items(), key=lambda x: x[1]['avg_error'])
    
    print("📊 CLASSIFICA (ordinate per errore medio):")
    print()
    for i, (variant, scores) in enumerate(sorted_variants[:5]):
        semantic = "✅ Semantica OK" if scores['semantic_ok'] else "❌ Semantica ERRATA"
        print(f"   {i+1}. {variant:25s} → Errore medio: {scores['avg_error']:.2f}° | {semantic}")
    
    print()
    print("=" * 100)
    print()
    
    best_variant = sorted_variants[0][0]
    print(f"💡 MIGLIOR VARIANTE: {best_variant}")
    print()
    
    if "YAW_NEGATO" in best_variant:
        print("🔧 CORREZIONE DA APPLICARE:")
        print("   yaw = -np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi")
    elif "X_INVERTITO" in best_variant:
        print("🔧 CORREZIONE DA APPLICARE:")
        print("   Invertire coordinate X nel modello 3D (scambiare left/right)")
    elif "FOCAL" in best_variant:
        focal_mult = best_variant.split("_")[-1]
        print(f"🔧 CORREZIONE DA APPLICARE:")
        print(f"   focal_length = img_width * {focal_mult}")
    else:
        print("⚠️ Nessuna correzione semplice trovata - considera metodo geometrico")
    
    print()

if __name__ == "__main__":
    main()
