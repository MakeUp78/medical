#!/usr/bin/env python3
"""
Crea immagini annotate con Yaw CORRETTO (metodo geometrico)
per confronto visivo con i valori attuali
"""

import cv2
import mediapipe as mp
import numpy as np
import os
import json

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"
OUTPUT_DIR = os.path.join(SESSION_DIR, "debug_annotated_correct")

def calculate_all_angles(image_path):
    """Calcola tutti gli angoli: solvePnP (attuale) e geometrico (corretto)"""
    mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    )
    
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    
    h, w = img.shape[:2]
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mp_face_mesh.process(rgb_img)
    
    if not results.multi_face_landmarks:
        return None, None
    
    landmarks = results.multi_face_landmarks[0].landmark
    all_landmarks = np.zeros((len(landmarks), 2))
    for i in range(len(landmarks)):
        all_landmarks[i, 0] = landmarks[i].x * w
        all_landmarks[i, 1] = landmarks[i].y * h
    
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
    
    # Calcolo solvePnP (ATTUALE)
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
    camera_matrix = np.array([
        [focal_length, 0, w/2],
        [0, focal_length, h/2],
        [0, 0, 1]
    ], dtype=np.float32)
    dist_coeffs = np.zeros((4,1))
    
    yaw_solvepnp = 0
    pitch_solvepnp = 0
    
    success, rvec, tvec = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw_solvepnp = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        pitch_solvepnp = np.arctan2(-rmat[2,0], np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)) * 180.0 / np.pi
    
    # Calcolo GEOMETRICO (CORRETTO)
    eye_center_x = (left_eye[0] + right_eye[0]) / 2
    eye_distance = abs(right_eye[0] - left_eye[0])
    
    yaw_geometric = 0
    if eye_distance > 0:
        nose_relative = (nose_tip[0] - eye_center_x) / (eye_distance / 2)
        yaw_geometric = nose_relative * 30
    
    # Calcolo Pitch geometrico (basato su posizione verticale naso)
    eye_center_y = (left_eye[1] + right_eye[1]) / 2
    nose_chin_distance = abs(chin[1] - nose_tip[1])
    
    pitch_geometric = 0
    if nose_chin_distance > 0:
        nose_vertical_pos = (nose_tip[1] - eye_center_y) / nose_chin_distance
        pitch_geometric = nose_vertical_pos * 40  # Approssimazione
    
    landmarks_dict = {
        'nose_tip': nose_tip,
        'chin': chin,
        'left_eye': left_eye,
        'right_eye': right_eye,
        'left_mouth': left_mouth,
        'right_mouth': right_mouth,
        'eye_center_x': eye_center_x,
        'nose_offset': nose_tip[0] - (w/2)
    }
    
    angles = {
        'solvepnp': {'yaw': yaw_solvepnp, 'pitch': pitch_solvepnp},
        'geometric': {'yaw': yaw_geometric, 'pitch': pitch_geometric}
    }
    
    return img, {'landmarks': landmarks_dict, 'angles': angles, 'width': w, 'height': h}

def annotate_image(img, data):
    """Annota l'immagine con landmark e valori corretti"""
    annotated = img.copy()
    
    landmarks = data['landmarks']
    angles = data['angles']
    w = data['width']
    
    # Disegna landmark chiave
    for name, point in landmarks.items():
        if name in ['eye_center_x', 'nose_offset']:
            continue
        x, y = int(point[0]), int(point[1])
        cv2.circle(annotated, (x, y), 4, (0, 255, 0), -1)
    
    # Disegna linea centro VISO (non immagine!)
    eye_center_x_int = int(landmarks['eye_center_x'])
    cv2.line(annotated, (eye_center_x_int, 0), (eye_center_x_int, data['height']), (255, 255, 0), 1)
    
    # Disegna offset naso dal centro del VISO
    nose_x = int(landmarks['nose_tip'][0])
    nose_y = int(landmarks['nose_tip'][1])
    cv2.line(annotated, (eye_center_x_int, nose_y), (nose_x, nose_y), (255, 0, 255), 2)
    
    # Testo con confronto OLD vs NEW
    y_pos = 30
    
    # Intestazione
    cv2.putText(annotated, "CONFRONTO: OLD (solvePnP) vs NEW (Geometrico)", 
                (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    y_pos += 30
    
    # Linea separatore
    cv2.line(annotated, (10, y_pos-5), (w-10, y_pos-5), (100, 100, 100), 1)
    
    # Valori OLD
    yaw_old = angles['solvepnp']['yaw']
    pitch_old = angles['solvepnp']['pitch']
    cv2.putText(annotated, f"OLD - Yaw: {yaw_old:+.2f}  Pitch: {pitch_old:+.2f}", 
                (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    y_pos += 35
    
    # Valori NEW
    yaw_new = angles['geometric']['yaw']
    pitch_new = angles['geometric']['pitch']
    cv2.putText(annotated, f"NEW - Yaw: {yaw_new:+.2f}  Pitch: {pitch_new:+.2f}", 
                (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    y_pos += 35
    
    # Differenza
    diff_yaw = yaw_new - yaw_old
    nose_offset_from_face_center = landmarks['nose_tip'][0] - landmarks['eye_center_x']
    cv2.putText(annotated, f"Delta Yaw: {diff_yaw:+.2f}  (Offset da centro viso: {nose_offset_from_face_center:+.1f}px)", 
                (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    y_pos += 35
    
    # Interpretazione
    if abs(yaw_new) < 5:
        interpretation = "FRONTALE"
        color = (0, 255, 0)
    elif yaw_new > 5:
        interpretation = "GIRATO A DESTRA"
        color = (0, 165, 255)
    else:
        interpretation = "GIRATO A SINISTRA"
        color = (255, 0, 255)
    
    cv2.putText(annotated, f"Posa: {interpretation}", 
                (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    return annotated

def main():
    print("=" * 100)
    print(" CREAZIONE IMMAGINI ANNOTATE CON YAW CORRETTO")
    print("=" * 100)
    print()
    
    # Crea directory output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Carica JSON per sapere quali frame processare
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    print(f"📁 Directory output: {OUTPUT_DIR}/")
    print()
    print("🔄 Processamento frame...")
    print()
    
    results_comparison = []
    
    for frame_data in json_data['frames']:
        filename = frame_data['filename']
        image_path = os.path.join(SESSION_DIR, filename)
        
        print(f"   • {filename}...", end=" ")
        
        img, data = calculate_all_angles(image_path)
        
        if img is not None and data is not None:
            annotated = annotate_image(img, data)
            
            output_path = os.path.join(OUTPUT_DIR, f"corrected_{filename}")
            cv2.imwrite(output_path, annotated)
            
            yaw_old = data['angles']['solvepnp']['yaw']
            yaw_new = data['angles']['geometric']['yaw']
            diff = yaw_new - yaw_old
            
            print(f"✅ (Yaw: {yaw_old:+.2f}° → {yaw_new:+.2f}°, Δ{diff:+.2f}°)")
            
            results_comparison.append({
                'filename': filename,
                'rank': frame_data['rank'],
                'yaw_old': yaw_old,
                'yaw_new': yaw_new,
                'diff': diff,
                'nose_offset': data['landmarks']['nose_offset']
            })
        else:
            print("❌ Errore")
    
    print()
    print("=" * 100)
    print()
    print("📊 RIEPILOGO CONFRONTO:")
    print()
    print(f"{'Frame':12} | {'Rank':4} | {'Yaw OLD':9} | {'Yaw NEW':9} | {'Δ':8} | {'Offset':10} | Interpretazione")
    print("-" * 100)
    
    for res in results_comparison:
        interpretation = ""
        if abs(res['nose_offset']) < 30:
            interpretation = "FRONTALE"
        elif res['nose_offset'] > 50:
            interpretation = "GIRATO A DX"
        else:
            interpretation = "INTERMEDIO"
        
        print(f"{res['filename']:12} | {res['rank']:4} | {res['yaw_old']:8.2f}° | {res['yaw_new']:8.2f}° | {res['diff']:+7.2f}° | {res['nose_offset']:+9.1f}px | {interpretation}")
    
    print()
    print("=" * 100)
    print()
    print(f"✅ Completato! {len(results_comparison)} immagini annotate create in:")
    print(f"   {OUTPUT_DIR}/")
    print()
    print("🔍 CONFRONTO VISIVO:")
    print(f"   • Vecchie annotazioni: {SESSION_DIR}/debug_annotated/")
    print(f"   • Nuove annotazioni:   {OUTPUT_DIR}/")
    print()
    print("💡 Puoi confrontare le immagini per vedere la differenza tra:")
    print("   • Yaw OLD (solvePnP): valori controintuitivi")
    print("   • Yaw NEW (geometrico): valori semanticamente corretti")
    print()

if __name__ == "__main__":
    main()
