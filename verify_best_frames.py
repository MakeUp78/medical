#!/usr/bin/env python3
"""
Script di verifica coerenza tra JSON e immagini salvate
Analizza le pose effettive nelle immagini e confronta con i dati del JSON
"""

import json
import cv2
import mediapipe as mp
import numpy as np
import os
from datetime import datetime

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

class FrameVerifier:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
    
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
        """Calcola la pose della testa usando landmark MediaPipe"""
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
            
            # Modello 3D del volto
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
                
                return {'pitch': pitch, 'yaw': yaw, 'roll': roll}
                
        except Exception as e:
            print(f"Errore nel calcolo pose: {e}")
            return None
        
        return None
    
    def analyze_image(self, image_path):
        """Analizza un'immagine e calcola la pose effettiva"""
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

def verify_frames():
    """Verifica principale"""
    print("=" * 80)
    print("VERIFICA COERENZA FRAME - ANALISI APPROFONDITA")
    print("=" * 80)
    print()
    
    # Carica JSON
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    print(f"📊 Metadata Sessione:")
    print(f"   Session ID: {data['metadata']['session_id']}")
    print(f"   Frame Processati: {data['metadata']['total_frames_processed']}")
    print(f"   Frame Salvati: {data['metadata']['best_frames_saved']}")
    print(f"   Completato: {data['metadata']['session_completed']}")
    print()
    
    # Analizza timestamp
    print("🕐 ANALISI TIMESTAMP:")
    print("-" * 80)
    timestamps = []
    for frame in data['frames']:
        timestamps.append({
            'filename': frame['filename'],
            'rank': frame['rank'],
            'timestamp': frame['timestamp'],
            'datetime': datetime.fromtimestamp(frame['timestamp']).strftime('%Y-%m-%d %H:%M:%S.%f')
        })
    
    # Ordina per timestamp
    timestamps_sorted = sorted(timestamps, key=lambda x: x['timestamp'])
    
    print("Ordine CRONOLOGICO (per timestamp):")
    for i, ts in enumerate(timestamps_sorted, 1):
        print(f"   {i:2d}. {ts['filename']} - Rank:{ts['rank']:2d} - {ts['datetime']}")
    
    print()
    print("Ordine ATTUALE (come appaiono in tabella):")
    for i, ts in enumerate(timestamps, 1):
        print(f"   {i:2d}. {ts['filename']} - Rank:{ts['rank']:2d} - {ts['datetime']}")
    
    # Verifica ordine rank
    print()
    print("📋 ANALISI RANK:")
    print("-" * 80)
    ranks = [frame['rank'] for frame in data['frames']]
    print(f"Rank mostrati in tabella: {ranks}")
    ranks_sorted = sorted(ranks)
    print(f"Rank ordinati numericamente: {ranks_sorted}")
    
    if ranks != ranks_sorted and ranks != list(range(1, len(ranks)+1)):
        print("⚠️  WARNING: I rank NON sono in ordine sequenziale 1-10!")
        print("   Questo indica che i frame mostrati NON sono stati selezionati")
        print("   in ordine cronologico, ma per SCORE.")
    
    # Verifica pose nelle immagini
    print()
    print("🔍 VERIFICA POSE NELLE IMMAGINI REALI:")
    print("-" * 80)
    
    verifier = FrameVerifier()
    discrepancies = []
    
    for frame_data in data['frames']:
        filename = frame_data['filename']
        image_path = os.path.join(SESSION_DIR, filename)
        
        json_pose = frame_data['pose']
        actual_pose = verifier.analyze_image(image_path)
        
        print(f"\n{filename} (Rank {frame_data['rank']}, Score {frame_data['total_score']}):")
        print(f"   JSON:  Yaw={json_pose['yaw']:6.2f}°  Pitch={json_pose['pitch']:6.2f}°  Roll={json_pose['roll']:6.2f}°")
        
        if actual_pose:
            print(f"   IMAGE: Yaw={actual_pose['yaw']:6.2f}°  Pitch={actual_pose['pitch']:6.2f}°  Roll={actual_pose['roll']:6.2f}°")
            
            # Calcola differenze
            diff_yaw = abs(actual_pose['yaw'] - json_pose['yaw'])
            diff_pitch = abs(actual_pose['pitch'] - json_pose['pitch'])
            diff_roll = abs(actual_pose['roll'] - json_pose['roll'])
            
            # Tolleranza: 2° per piccole variazioni di calcolo
            tolerance = 2.0
            
            if diff_yaw > tolerance or diff_pitch > tolerance or diff_roll > tolerance:
                print(f"   ⚠️  DISCREPANZA: Yaw Δ{diff_yaw:.2f}°  Pitch Δ{diff_pitch:.2f}°  Roll Δ{diff_roll:.2f}°")
                discrepancies.append({
                    'filename': filename,
                    'rank': frame_data['rank'],
                    'diff_yaw': diff_yaw,
                    'diff_pitch': diff_pitch,
                    'diff_roll': diff_roll
                })
            else:
                print(f"   ✓ COERENTE")
        else:
            print(f"   ❌ ERRORE: Impossibile rilevare volto nell'immagine!")
            discrepancies.append({
                'filename': filename,
                'rank': frame_data['rank'],
                'error': 'Face not detected'
            })
    
    # Report finale
    print()
    print("=" * 80)
    print("📊 REPORT FINALE:")
    print("=" * 80)
    
    if discrepancies:
        print(f"⚠️  TROVATE {len(discrepancies)} DISCREPANZE:")
        for d in discrepancies:
            if 'error' in d:
                print(f"   - {d['filename']} (Rank {d['rank']}): {d['error']}")
            else:
                print(f"   - {d['filename']} (Rank {d['rank']}): Δ Yaw={d['diff_yaw']:.2f}° Pitch={d['diff_pitch']:.2f}° Roll={d['diff_roll']:.2f}°")
    else:
        print("✅ NESSUNA DISCREPANZA: I dati JSON corrispondono alle immagini salvate")
    
    # Analisi ordine
    print()
    if ranks != list(range(1, len(ranks)+1)):
        print("🔍 OSSERVAZIONE CRITICA:")
        print("   I 'rank' indicano il NUMERO DEL FRAME ORIGINALE nella sequenza video,")
        print("   NON la posizione 1-10 nella classifica dei migliori.")
        print()
        print("   Esempio:")
        print("   - Frame 01 (rank 14) = era il 14° frame analizzato nel video")
        print("   - Frame 04 (rank 13) = era il 13° frame analizzato nel video")
        print("   - Frame 08 (rank 12) = era il 12° frame analizzato nel video")
        print()
        print("   Questo significa che i frame NON sono ordinati cronologicamente")
        print("   ma per SCORE (dal migliore al peggiore).")
        print()
        print("   Se l'utente vede 'Frame 01, 02, 03...' in tabella potrebbe pensare")
        print("   che siano i primi 10 frame in ordine temporale, ma NON è così!")

if __name__ == "__main__":
    verify_frames()
