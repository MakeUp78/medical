#!/usr/bin/env python3
"""
Confronto OUTPUT ATTUALE vs OUTPUT CON DIVERSE CORREZIONI
Per trovare quale correzione produce Yaw semanticamente corretto
"""

import cv2
import mediapipe as mp
import numpy as np
import os
import json

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def calculate_yaw_all_methods(image_path):
    """Calcola Yaw con tutti i metodi possibili"""
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
    
    image_points = np.array([
        nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
    ], dtype=np.float32)
    
    # Model 3D standard
    model_points = np.array([
        (0.0, 0.0, 0.0),
        (0.0, -330.0, -65.0),
        (-225.0, 170.0, -135.0),
        (225.0, 170.0, -135.0),
        (-150.0, -150.0, -125.0),
        (150.0, -150.0, -125.0)
    ], dtype=np.float32)
    
    dist_coeffs = np.zeros((4,1))
    
    results_dict = {
        'nose_offset': nose_tip[0] - (w/2),
        'width': w
    }
    
    # METODO 1: ATTUALE (come nel codice)
    focal_length = w
    camera_matrix = np.array([
        [focal_length, 0, w/2],
        [0, focal_length, h/2],
        [0, 0, 1]
    ], dtype=np.float32)
    
    success, rvec, tvec = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        pitch = np.arctan2(-rmat[2,0], np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)) * 180.0 / np.pi
        results_dict['current'] = {'yaw': yaw, 'pitch': pitch}
    
    # METODO 2: YAW INVERTITO (segno opposto)
    if success:
        results_dict['inverted_sign'] = {'yaw': -yaw, 'pitch': pitch}
    
    # METODO 3: Focal length CORRETTA (più realistica per webcam)
    focal_length_corrected = w * 1.2  # Focal length tipica per webcam
    camera_matrix_corrected = np.array([
        [focal_length_corrected, 0, w/2],
        [0, focal_length_corrected, h/2],
        [0, 0, 1]
    ], dtype=np.float32)
    
    success, rvec, tvec = cv2.solvePnP(model_points, image_points, camera_matrix_corrected, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        pitch = np.arctan2(-rmat[2,0], np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)) * 180.0 / np.pi
        results_dict['focal_corrected'] = {'yaw': yaw, 'pitch': pitch}
    
    # METODO 4: Model points con scala diversa
    model_scaled = model_points * 1.5
    success, rvec, tvec = cv2.solvePnP(model_scaled, image_points, camera_matrix, dist_coeffs)
    if success:
        rmat, _ = cv2.Rodrigues(rvec)
        yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
        pitch = np.arctan2(-rmat[2,0], np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)) * 180.0 / np.pi
        results_dict['model_scaled'] = {'yaw': yaw, 'pitch': pitch}
    
    # METODO 5: Calcolo semplificato basato su geometria diretta
    # Usa la posizione relativa del naso rispetto agli occhi
    eye_center_x = (left_eye[0] + right_eye[0]) / 2
    eye_distance = abs(right_eye[0] - left_eye[0])
    
    if eye_distance > 0:
        # Normalizza la posizione del naso rispetto agli occhi
        # -1 = naso molto a sinistra, 0 = centrato, +1 = molto a destra
        nose_relative = (nose_tip[0] - eye_center_x) / (eye_distance / 2)
        # Converti in angolo (approssimazione: ±30° massimo)
        yaw_geometric = nose_relative * 30
        results_dict['geometric'] = {'yaw': yaw_geometric, 'pitch': 0}
    
    return results_dict

def main():
    print("=" * 140)
    print(" CONFRONTO OUTPUT ATTUALE vs CORREZIONI PROPOSTE")
    print("=" * 140)
    print()
    
    # Carica JSON per avere i dati attuali
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    frames_to_test = [
        ('frame_01.jpg', 'FRONTALE (naso centrato)'),
        ('frame_04.jpg', 'FRONTALE (naso leggermente sinistra)'),
        ('frame_07.jpg', 'GIRATO A DESTRA (naso +104px)'),
        ('frame_09.jpg', 'MOLTO GIRATO A DESTRA (naso +156px)')
    ]
    
    print("📊 LEGENDA:")
    print("   • Viso FRONTALE → Yaw dovrebbe essere vicino a 0° (es. -3° a +3°)")
    print("   • Viso GIRATO A DESTRA → Yaw dovrebbe essere POSITIVO e lontano da 0 (es. +10° a +30°)")
    print("   • Viso GIRATO A SINISTRA → Yaw dovrebbe essere NEGATIVO e lontano da 0 (es. -10° a -30°)")
    print()
    print("-" * 140)
    print()
    
    all_results = []
    
    for filename, description in frames_to_test:
        image_path = os.path.join(SESSION_DIR, filename)
        
        # Trova dati nel JSON
        frame_json = next((f for f in json_data['frames'] if f['filename'] == filename), None)
        
        print(f"🔍 {filename} - {description}")
        print()
        
        results = calculate_yaw_all_methods(image_path)
        
        if results:
            print(f"   Geometria: Naso offset = {results['nose_offset']:+7.1f}px da centro ({results['width']//2}px)")
            print()
            
            if frame_json:
                print(f"   {'METODO':30} | {'Yaw':8} | {'Pitch':8} | Interpretazione")
                print(f"   {'-'*30}-|----------|----------|{'-'*50}")
                
                # JSON attuale
                yaw_json = frame_json['pose']['yaw']
                pitch_json = frame_json['pose']['pitch']
                print(f"   {'JSON/Tabella (ATTUALE)':30} | {yaw_json:+7.2f}° | {pitch_json:+7.2f}° | {interpret_yaw(yaw_json, results['nose_offset'])}")
                
                # Metodo current (ricalcolato, dovrebbe match JSON)
                if 'current' in results:
                    yaw = results['current']['yaw']
                    pitch = results['current']['pitch']
                    print(f"   {'Ricalcolato (stesso metodo)':30} | {yaw:+7.2f}° | {pitch:+7.2f}° | {interpret_yaw(yaw, results['nose_offset'])}")
                
                # Yaw invertito
                if 'inverted_sign' in results:
                    yaw = results['inverted_sign']['yaw']
                    pitch = results['inverted_sign']['pitch']
                    marker = "✅" if is_correct(yaw, results['nose_offset']) else "❌"
                    print(f"   {marker} {'CORREZIONE: Segno invertito':28} | {yaw:+7.2f}° | {pitch:+7.2f}° | {interpret_yaw(yaw, results['nose_offset'])}")
                
                # Focal corrected
                if 'focal_corrected' in results:
                    yaw = results['focal_corrected']['yaw']
                    pitch = results['focal_corrected']['pitch']
                    marker = "✅" if is_correct(yaw, results['nose_offset']) else "❌"
                    print(f"   {marker} {'CORREZIONE: Focal length 1.2x':28} | {yaw:+7.2f}° | {pitch:+7.2f}° | {interpret_yaw(yaw, results['nose_offset'])}")
                
                # Model scaled
                if 'model_scaled' in results:
                    yaw = results['model_scaled']['yaw']
                    pitch = results['model_scaled']['pitch']
                    marker = "✅" if is_correct(yaw, results['nose_offset']) else "❌"
                    print(f"   {marker} {'CORREZIONE: Model scala 1.5x':28} | {yaw:+7.2f}° | {pitch:+7.2f}° | {interpret_yaw(yaw, results['nose_offset'])}")
                
                # Geometric
                if 'geometric' in results:
                    yaw = results['geometric']['yaw']
                    marker = "✅" if is_correct(yaw, results['nose_offset']) else "❌"
                    print(f"   {marker} {'ALTERNATIVA: Calcolo geometrico':28} | {yaw:+7.2f}° | {'N/A':>7}  | {interpret_yaw(yaw, results['nose_offset'])}")
            
            all_results.append({
                'filename': filename,
                'description': description,
                'nose_offset': results['nose_offset'],
                'results': results
            })
        
        print()
        print("-" * 140)
        print()
    
    # Analisi finale
    print()
    print("=" * 140)
    print(" 📊 ANALISI COMPARATIVA: Quale metodo produce valori SEMANTICAMENTE CORRETTI?")
    print("=" * 140)
    print()
    
    methods = ['current', 'inverted_sign', 'focal_corrected', 'model_scaled', 'geometric']
    method_names = ['ATTUALE', 'SEGNO INVERTITO', 'FOCAL 1.2x', 'MODEL 1.5x', 'GEOMETRICO']
    
    for method, name in zip(methods, method_names):
        print(f"🔬 METODO: {name}")
        print()
        
        correct_count = 0
        total_count = 0
        
        for res in all_results:
            if method in res['results']:
                yaw = res['results'][method]['yaw']
                nose_offset = res['nose_offset']
                is_ok = is_correct(yaw, nose_offset)
                
                marker = "✅" if is_ok else "❌"
                print(f"   {marker} {res['filename']:12} (offset {nose_offset:+7.1f}px): Yaw = {yaw:+7.2f}° {interpret_yaw(yaw, nose_offset)}")
                
                if is_ok:
                    correct_count += 1
                total_count += 1
        
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        print()
        print(f"   Accuratezza semantica: {correct_count}/{total_count} ({accuracy:.0f}%)")
        print()
        print("-" * 140)
        print()
    
    print("💡 RACCOMANDAZIONE:")
    print()
    
    # Trova il metodo migliore
    best_method = None
    best_accuracy = 0
    
    for method, name in zip(methods, method_names):
        correct = sum(1 for res in all_results if method in res['results'] and is_correct(res['results'][method]['yaw'], res['nose_offset']))
        total = sum(1 for res in all_results if method in res['results'])
        accuracy = (correct / total * 100) if total > 0 else 0
        
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_method = name
    
    if best_accuracy >= 75:
        print(f"✅ Il metodo '{best_method}' produce valori semanticamente corretti ({best_accuracy:.0f}% accuratezza)")
        print(f"   Questo è il metodo che dovrebbe essere implementato nel codice.")
    else:
        print(f"⚠️  Nessun metodo testato raggiunge un'accuratezza sufficiente.")
        print(f"   Il problema potrebbe richiedere un approccio completamente diverso.")

def interpret_yaw(yaw, nose_offset):
    """Interpreta il valore Yaw"""
    # Determina orientamento reale dalla geometria
    if abs(nose_offset) < 30:
        expected = "FRONTALE"
    elif nose_offset > 0:
        expected = "GIRATO A DESTRA"
    else:
        expected = "GIRATO A SINISTRA"
    
    # Determina cosa dice lo Yaw
    if abs(yaw) < 5:
        yaw_says = "Yaw dice: FRONTALE"
    elif yaw > 5:
        yaw_says = "Yaw dice: GIRATO A DESTRA"
    else:
        yaw_says = "Yaw dice: GIRATO A SINISTRA"
    
    return f"{yaw_says} (geometria: {expected})"

def is_correct(yaw, nose_offset):
    """Verifica se lo Yaw è semanticamente corretto rispetto alla geometria"""
    # Frontale: offset < 30px, yaw dovrebbe essere < 5°
    if abs(nose_offset) < 30:
        return abs(yaw) < 5
    
    # Girato a destra: offset > 50px, yaw dovrebbe essere > 5° E positivo
    if nose_offset > 50:
        return yaw > 5
    
    # Girato a sinistra: offset < -50px, yaw dovrebbe essere < -5° E negativo
    if nose_offset < -50:
        return yaw < -5
    
    return True  # Casi intermedi

if __name__ == "__main__":
    main()
