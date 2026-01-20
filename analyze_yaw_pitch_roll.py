#!/usr/bin/env python3
"""
Script per analizzare Yaw, Pitch, Roll delle immagini salvate
e confrontarli con i valori del JSON
"""

import json
import cv2
import mediapipe as mp
import numpy as np
import os

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

class PoseAnalyzer:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
    
    def get_all_mediapipe_landmarks(self, mediapipe_landmarks, img_width, img_height):
        """Estrae TUTTI i landmark MediaPipe (468 punti)"""
        num_landmarks = len(mediapipe_landmarks.landmark)
        all_landmarks = np.zeros((num_landmarks, 2))
        
        for i in range(num_landmarks):
            landmark = mediapipe_landmarks.landmark[i]
            x = landmark.x * img_width
            y = landmark.y * img_height
            x = max(1, min(img_width-1, x))
            y = max(1, min(img_height-1, y))
            all_landmarks[i, 0] = x
            all_landmarks[i, 1] = y
        
        return all_landmarks
    
    def calculate_head_pose_from_mediapipe(self, landmarks_array, img_width, img_height):
        """Calcola la pose della testa usando landmark MediaPipe - IDENTICO al codice originale"""
        try:
            # Indici MediaPipe Face Mesh corretti
            NOSE_TIP = 4
            CHIN = 152
            LEFT_EYE_CORNER = 33
            RIGHT_EYE_CORNER = 263
            LEFT_MOUTH_CORNER = 78
            RIGHT_MOUTH_CORNER = 308
            
            if len(landmarks_array) < 468:
                return None
            
            # Punti chiave
            nose_tip = landmarks_array[NOSE_TIP]
            chin = landmarks_array[CHIN] 
            left_eye = landmarks_array[LEFT_EYE_CORNER]
            right_eye = landmarks_array[RIGHT_EYE_CORNER]
            left_mouth = landmarks_array[LEFT_MOUTH_CORNER]
            right_mouth = landmarks_array[RIGHT_MOUTH_CORNER]
            
            points_2d = np.array([nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth])
            if np.any(np.isnan(points_2d)):
                return None
            
            # Modello 3D del volto - IDENTICO
            model_points = np.array([
                (0.0, 0.0, 0.0),             # Punta del naso
                (0.0, -330.0, -65.0),        # Mento 
                (-225.0, 170.0, -135.0),     # Angolo interno occhio sinistro
                (225.0, 170.0, -135.0),      # Angolo interno occhio destro  
                (-150.0, -150.0, -125.0),    # Angolo sinistro bocca
                (150.0, -150.0, -125.0)      # Angolo destro bocca
            ], dtype=np.float32)
            
            image_points = np.array([
                nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
            ], dtype=np.float32)
            
            # Parametri camera
            focal_length = img_width
            center = (img_width/2, img_height/2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float32)
            
            dist_coeffs = np.zeros((4,1))
            
            # Risolvi PnP
            success, rotation_vector, translation_vector = cv2.solvePnP(
                model_points, image_points, camera_matrix, dist_coeffs)
            
            if success:
                rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
                sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
                
                singular = sy < 1e-6
                
                if not singular:
                    pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                    yaw = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi
                    roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2]) * 180.0 / np.pi
                else:
                    pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                    yaw = 0
                    roll = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1]) * 180.0 / np.pi
                
                return {
                    'pitch': pitch, 
                    'yaw': yaw, 
                    'roll': roll,
                    'landmarks': {
                        'nose_tip': nose_tip.tolist(),
                        'chin': chin.tolist(),
                        'left_eye': left_eye.tolist(),
                        'right_eye': right_eye.tolist(),
                        'left_mouth': left_mouth.tolist(),
                        'right_mouth': right_mouth.tolist()
                    }
                }
                
        except Exception as e:
            print(f"Errore nel calcolo pose: {e}")
            return None
        
        return None
    
    def analyze_image(self, image_path):
        """Analizza un'immagine e calcola la pose"""
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        h, w = img.shape[:2]
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_img)
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                landmarks = self.get_all_mediapipe_landmarks(face_landmarks, w, h)
                pose = self.calculate_head_pose_from_mediapipe(landmarks, w, h)
                if pose:
                    return pose
        
        return None
    
    def draw_landmarks_on_image(self, image_path, output_path, pose_data):
        """Disegna i landmark chiave sull'immagine per verifica visiva"""
        img = cv2.imread(image_path)
        if img is None:
            return
        
        landmarks = pose_data['landmarks']
        
        # Disegna i punti chiave
        for name, point in landmarks.items():
            x, y = int(point[0]), int(point[1])
            cv2.circle(img, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(img, name.replace('_', ' '), (x+10, y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Aggiungi testo con pose
        text = f"Yaw: {pose_data['yaw']:.2f}  Pitch: {pose_data['pitch']:.2f}  Roll: {pose_data['roll']:.2f}"
        cv2.putText(img, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imwrite(output_path, img)

def main():
    print("=" * 100)
    print(" ANALISI YAW, PITCH, ROLL - CONFRONTO JSON vs IMMAGINI REALI")
    print("=" * 100)
    print()
    
    # Carica JSON
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    analyzer = PoseAnalyzer()
    
    print("📐 CONFRONTO DETTAGLIATO:")
    print("-" * 100)
    print()
    
    # Crea directory per immagini annotate
    debug_dir = os.path.join(SESSION_DIR, "debug_annotated")
    os.makedirs(debug_dir, exist_ok=True)
    
    all_results = []
    
    for frame_json in json_data['frames']:
        filename = frame_json['filename']
        image_path = os.path.join(SESSION_DIR, filename)
        
        print(f"🔍 {filename}")
        print(f"   {'':30} |  Yaw     | Pitch    | Roll")
        print(f"   {'-'*30}-|----------|----------|----------")
        
        # Valori dal JSON
        json_yaw = frame_json['pose']['yaw']
        json_pitch = frame_json['pose']['pitch']
        json_roll = frame_json['pose']['roll']
        
        print(f"   {'JSON (Tabella/Frontend)':30} | {json_yaw:7.2f}° | {json_pitch:7.2f}° | {json_roll:7.2f}°")
        
        # Ricalcola dalla immagine
        calculated_pose = analyzer.analyze_image(image_path)
        
        if calculated_pose:
            calc_yaw = calculated_pose['yaw']
            calc_pitch = calculated_pose['pitch']
            calc_roll = calculated_pose['roll']
            
            print(f"   {'RICALCOLATO (Immagine reale)':30} | {calc_yaw:7.2f}° | {calc_pitch:7.2f}° | {calc_roll:7.2f}°")
            
            # Calcola differenze
            diff_yaw = calc_yaw - json_yaw
            diff_pitch = calc_pitch - json_pitch
            diff_roll = calc_roll - json_roll
            
            print(f"   {'DIFFERENZA':30} | {diff_yaw:7.2f}° | {diff_pitch:7.2f}° | {diff_roll:7.2f}°")
            
            # Interpretazione YAW
            print()
            if abs(calc_yaw) < 5:
                print(f"   💚 Yaw {calc_yaw:.2f}° → Viso FRONTALE (quasi dritto)")
            elif calc_yaw < -5:
                print(f"   🔵 Yaw {calc_yaw:.2f}° → Viso girato verso SINISTRA (della persona)")
            else:
                print(f"   🔴 Yaw {calc_yaw:.2f}° → Viso girato verso DESTRA (della persona)")
            
            # Salva immagine annotata
            annotated_path = os.path.join(debug_dir, f"annotated_{filename}")
            analyzer.draw_landmarks_on_image(image_path, annotated_path, calculated_pose)
            
            all_results.append({
                'filename': filename,
                'rank': frame_json['rank'],
                'score': frame_json['total_score'],
                'json_yaw': json_yaw,
                'json_pitch': json_pitch,
                'json_roll': json_roll,
                'calc_yaw': calc_yaw,
                'calc_pitch': calc_pitch,
                'calc_roll': calc_roll,
                'diff_yaw': diff_yaw,
                'diff_pitch': diff_pitch,
                'diff_roll': diff_roll
            })
        else:
            print(f"   ❌ ERRORE: Impossibile calcolare pose dall'immagine")
        
        print()
        print("-" * 100)
        print()
    
    # Riepilogo finale
    print()
    print("=" * 100)
    print(" 📊 RIEPILOGO CONFRONTO")
    print("=" * 100)
    print()
    
    print(f"{'File':12} | {'Rank':4} | {'Score':6} | {'Yaw JSON':9} | {'Yaw REALE':10} | {'Δ Yaw':7} | Interpretazione")
    print("-" * 100)
    
    for result in all_results:
        interpretation = ""
        if abs(result['diff_yaw']) < 2:
            interpretation = "✅ Coerente"
        elif abs(result['diff_yaw']) < 5:
            interpretation = "⚠️  Piccola diff"
        else:
            interpretation = "❌ INCOERENZA!"
        
        print(f"{result['filename']:12} | {result['rank']:4} | {result['score']:6.2f} | {result['json_yaw']:8.2f}° | {result['calc_yaw']:9.2f}° | {result['diff_yaw']:6.2f}° | {interpretation}")
    
    print()
    print("=" * 100)
    print()
    print(f"✅ Immagini annotate salvate in: {debug_dir}/")
    print("   Puoi aprire le immagini per vedere i landmark e i valori calcolati")
    print()
    
    # Analisi pattern
    avg_diff_yaw = sum(r['diff_yaw'] for r in all_results) / len(all_results)
    avg_diff_pitch = sum(r['diff_pitch'] for r in all_results) / len(all_results)
    avg_diff_roll = sum(r['diff_roll'] for r in all_results) / len(all_results)
    
    print("📈 PATTERN RILEVATI:")
    print(f"   Differenza media Yaw:   {avg_diff_yaw:7.2f}°")
    print(f"   Differenza media Pitch: {avg_diff_pitch:7.2f}°")
    print(f"   Differenza media Roll:  {avg_diff_roll:7.2f}°")
    print()
    
    if abs(avg_diff_yaw) > 20:
        print("   🔴 PROBLEMA CRITICO YAW: Differenza sistematica > 20°")
        print("      Possibile inversione di segno o problema nel calcolo")
    elif abs(avg_diff_yaw) > 5:
        print("   ⚠️  ATTENZIONE YAW: Differenza sistematica > 5°")
        print("      Possibile bias nel calcolo o convenzione assi diversa")
    else:
        print("   ✅ Yaw coerente tra JSON e immagini reali")
    
    if abs(avg_diff_roll) > 100:
        print("   🔴 PROBLEMA CRITICO ROLL: Differenza enorme (~180°)")
        print("      Questo è il bug della normalizzazione Roll già identificato")

if __name__ == "__main__":
    main()
