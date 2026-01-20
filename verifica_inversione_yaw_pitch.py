#!/usr/bin/env python3
"""
VERIFICA INVERSIONE YAW/PITCH

Testa se c'è confusione tra yaw e pitch:
1. Analizza frame con movimento ORIZZONTALE (yaw)
2. Analizza frame con movimento VERTICALE (pitch)
3. Verifica quale valore cambia per quale movimento
"""

import cv2
import mediapipe as mp
import numpy as np

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def analyze_frame_detailed(image_path, description):
    """Analizza frame e verifica yaw vs pitch"""
    
    mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    )
    
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mp_face_mesh.process(rgb_img)
    
    if not results.multi_face_landmarks:
        return None
    
    landmarks = results.multi_face_landmarks[0].landmark
    landmarks_array = np.zeros((len(landmarks), 2))
    for i in range(len(landmarks)):
        landmarks_array[i, 0] = landmarks[i].x * w
        landmarks_array[i, 1] = landmarks[i].y * h
    
    # Landmark chiave
    NOSE_TIP = 4
    CHIN = 152
    LEFT_EYE = 33
    RIGHT_EYE = 263
    LEFT_MOUTH = 78
    RIGHT_MOUTH = 308
    FOREHEAD = 10  # Punto alto fronte
    
    nose_tip = landmarks_array[NOSE_TIP]
    chin = landmarks_array[CHIN]
    left_eye = landmarks_array[LEFT_EYE]
    right_eye = landmarks_array[RIGHT_EYE]
    left_mouth = landmarks_array[LEFT_MOUTH]
    right_mouth = landmarks_array[RIGHT_MOUTH]
    forehead = landmarks_array[FOREHEAD]
    
    # ANALISI GEOMETRICA
    eye_center_x = (left_eye[0] + right_eye[0]) / 2
    eye_center_y = (left_eye[1] + right_eye[1]) / 2
    eye_distance = abs(right_eye[0] - left_eye[0])
    
    # YAW GEOMETRICO (movimento ORIZZONTALE)
    nose_offset_horizontal = nose_tip[0] - eye_center_x
    yaw_geometric = (nose_offset_horizontal / (eye_distance / 2)) * 30
    
    # PITCH GEOMETRICO (movimento VERTICALE)
    # Posizione verticale del naso rispetto al centro degli occhi
    nose_offset_vertical = nose_tip[1] - eye_center_y
    nose_chin_distance = abs(chin[1] - nose_tip[1])
    pitch_geometric = (nose_offset_vertical / nose_chin_distance) * 40 if nose_chin_distance > 0 else 0
    
    # Angolo testa (su/giù) - alternativo
    face_vertical_line = chin[1] - forehead[1]  # Lunghezza verticale viso
    nose_position_ratio = (nose_tip[1] - forehead[1]) / face_vertical_line if face_vertical_line > 0 else 0.5
    # Se nose_position_ratio > 0.5 → testa giù, < 0.5 → testa su
    
    print(f"{'='*80}")
    print(f"FRAME: {description}")
    print(f"{'='*80}")
    print()
    
    print("📐 GEOMETRIA LANDMARK:")
    print(f"   Naso:        ({nose_tip[0]:.1f}, {nose_tip[1]:.1f})")
    print(f"   Centro occhi: ({eye_center_x:.1f}, {eye_center_y:.1f})")
    print(f"   Mento:       ({chin[0]:.1f}, {chin[1]:.1f})")
    print(f"   Fronte:      ({forehead[0]:.1f}, {forehead[1]:.1f})")
    print()
    
    print("🔍 OFFSET GEOMETRICI:")
    print(f"   Offset naso ORIZZONTALE: {nose_offset_horizontal:+.1f} px")
    print(f"      (positivo = naso a DESTRA, negativo = naso a SINISTRA)")
    print(f"   Offset naso VERTICALE:   {nose_offset_vertical:+.1f} px")
    print(f"      (positivo = naso SOTTO gli occhi, negativo = naso SOPRA gli occhi)")
    print(f"   Posizione verticale naso: {nose_position_ratio:.2f}")
    print(f"      (>0.5 = testa GIÙ, <0.5 = testa SU)")
    print()
    
    print("🎯 ANGOLI GEOMETRICI:")
    print(f"   Yaw geometrico:   {yaw_geometric:+.2f}° (rotazione ORIZZONTALE)")
    print(f"   Pitch geometrico: {pitch_geometric:+.2f}° (rotazione VERTICALE)")
    print()
    
    # CALCOLO solvePnP
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
    
    success, rvec, tvec = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs)
    
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)
        
        # Formula ATTUALE
        pitch_solvepnp = np.arctan2(-rmat[2,0], sy) * 180.0 / np.pi
        yaw_solvepnp = -np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        roll_solvepnp = np.arctan2(rmat[2,1], rmat[2,2]) * 180.0 / np.pi
        
        # Formula INVERTITA (per test)
        pitch_inverted = -np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        yaw_inverted = np.arctan2(-rmat[2,0], sy) * 180.0 / np.pi
        
        print("🔧 ANGOLI solvePnP (FORMULA ATTUALE):")
        print(f"   Pitch: {pitch_solvepnp:+.2f}°")
        print(f"   Yaw:   {yaw_solvepnp:+.2f}°")
        print(f"   Roll:  {roll_solvepnp:+.2f}°")
        print()
        
        print("🔄 ANGOLI solvePnP (SE INVERTITI):")
        print(f"   Pitch: {pitch_inverted:+.2f}° (se fosse yaw)")
        print(f"   Yaw:   {yaw_inverted:+.2f}° (se fosse pitch)")
        print()
        
        # VERIFICA COERENZA
        print("✅ VERIFICA COERENZA:")
        print()
        
        # Yaw test
        if abs(nose_offset_horizontal) > 20:  # Movimento orizzontale significativo
            if abs(nose_offset_horizontal) > 0:
                expected_sign_yaw = "positivo" if nose_offset_horizontal > 0 else "negativo"
                actual_sign_yaw = "positivo" if yaw_solvepnp > 0 else "negativo"
                yaw_match = (nose_offset_horizontal > 0 and yaw_solvepnp > 0) or \
                           (nose_offset_horizontal < 0 and yaw_solvepnp < 0)
                
                # Test con yaw invertito
                actual_sign_inverted = "positivo" if yaw_inverted > 0 else "negativo"
                yaw_inverted_match = (nose_offset_horizontal > 0 and yaw_inverted > 0) or \
                                    (nose_offset_horizontal < 0 and yaw_inverted < 0)
                
                print(f"   MOVIMENTO ORIZZONTALE:")
                print(f"      Naso offset: {nose_offset_horizontal:+.1f}px → dovrebbe essere Yaw {expected_sign_yaw}")
                print(f"      Yaw attuale:  {yaw_solvepnp:+.2f}° ({actual_sign_yaw}) {'✅' if yaw_match else '❌ INVERTITO!'}")
                print(f"      Yaw invertito: {yaw_inverted:+.2f}° ({actual_sign_inverted}) {'✅ SE FOSSE QUESTO!' if yaw_inverted_match else ''}")
                print()
        
        # Pitch test
        if abs(nose_offset_vertical) > 20:  # Movimento verticale significativo
            # Pitch positivo = testa su (naso si abbassa relativamente agli occhi)
            # Pitch negativo = testa giù (naso si alza relativamente agli occhi)
            expected_sign_pitch = "positivo" if nose_offset_vertical > 0 else "negativo"
            actual_sign_pitch = "positivo" if pitch_solvepnp > 0 else "negativo"
            pitch_match = (nose_offset_vertical > 0 and pitch_solvepnp > 0) or \
                         (nose_offset_vertical < 0 and pitch_solvepnp < 0)
            
            # Test con pitch invertito
            actual_sign_inverted_p = "positivo" if pitch_inverted > 0 else "negativo"
            pitch_inverted_match = (nose_offset_vertical > 0 and pitch_inverted > 0) or \
                                  (nose_offset_vertical < 0 and pitch_inverted < 0)
            
            print(f"   MOVIMENTO VERTICALE:")
            print(f"      Naso offset: {nose_offset_vertical:+.1f}px → dovrebbe essere Pitch {expected_sign_pitch}")
            print(f"      Pitch attuale:  {pitch_solvepnp:+.2f}° ({actual_sign_pitch}) {'✅' if pitch_match else '❌ INVERTITO!'}")
            print(f"      Pitch invertito: {pitch_inverted:+.2f}° ({actual_sign_inverted_p}) {'✅ SE FOSSE QUESTO!' if pitch_inverted_match else ''}")
        
        print()
        
        return {
            'geometric': {'yaw': yaw_geometric, 'pitch': pitch_geometric},
            'solvepnp_current': {'pitch': pitch_solvepnp, 'yaw': yaw_solvepnp, 'roll': roll_solvepnp},
            'solvepnp_inverted': {'pitch': pitch_inverted, 'yaw': yaw_inverted},
            'offsets': {'horizontal': nose_offset_horizontal, 'vertical': nose_offset_vertical}
        }

def main():
    print("=" * 100)
    print("VERIFICA INVERSIONE YAW/PITCH")
    print("=" * 100)
    print()
    
    # Analizza frame di test
    frames = [
        ('frame_01.jpg', 'FRONTALE (baseline)'),
        ('frame_07.jpg', 'GIRATO A DESTRA (movimento orizzontale)')
    ]
    
    results = {}
    for filename, description in frames:
        result = analyze_frame_detailed(f"{SESSION_DIR}/{filename}", description)
        if result:
            results[filename] = result
        print()
    
    print("=" * 100)
    print("CONCLUSIONE")
    print("=" * 100)
    print()
    
    # Confronta risultati
    if 'frame_01.jpg' in results and 'frame_07.jpg' in results:
        r1 = results['frame_01.jpg']
        r7 = results['frame_07.jpg']
        
        delta_yaw_current = r7['solvepnp_current']['yaw'] - r1['solvepnp_current']['yaw']
        delta_pitch_current = r7['solvepnp_current']['pitch'] - r1['solvepnp_current']['pitch']
        
        delta_yaw_inverted = r7['solvepnp_inverted']['yaw'] - r1['solvepnp_inverted']['yaw']
        delta_pitch_inverted = r7['solvepnp_inverted']['pitch'] - r1['solvepnp_inverted']['pitch']
        
        delta_horizontal = r7['offsets']['horizontal'] - r1['offsets']['horizontal']
        
        print(f"📊 VARIAZIONE TRA FRAME FRONTALE E GIRATO:")
        print()
        print(f"   Variazione GEOMETRICA orizzontale: {delta_horizontal:+.1f}px")
        print(f"      → Dovrebbe cambiare principalmente lo YAW")
        print()
        print(f"   FORMULA ATTUALE:")
        print(f"      Δ Yaw:   {delta_yaw_current:+.2f}° {'✅' if abs(delta_yaw_current) > abs(delta_pitch_current) else '❌'}")
        print(f"      Δ Pitch: {delta_pitch_current:+.2f}°")
        print()
        print(f"   FORMULA INVERTITA:")
        print(f"      Δ Yaw:   {delta_yaw_inverted:+.2f}° {'✅ MEGLIO!' if abs(delta_yaw_inverted) > abs(delta_yaw_current) else ''}")
        print(f"      Δ Pitch: {delta_pitch_inverted:+.2f}°")
        print()
        
        if abs(delta_yaw_current) < 2 and abs(delta_pitch_current) > 10:
            print("🚨 PROBLEMA RILEVATO: Yaw cambia POCO ma Pitch cambia MOLTO per movimento ORIZZONTALE!")
            print("   → Possibile inversione Yaw/Pitch!")
        elif abs(delta_yaw_current) > abs(delta_pitch_current):
            print("✅ Formule CORRETTE: Yaw cambia più di Pitch per movimento orizzontale")
        

if __name__ == "__main__":
    main()
