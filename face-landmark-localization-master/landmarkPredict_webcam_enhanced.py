# Versione migliorata con controlli avanzati e tutti i landmark
# usage: python landmarkPredict_webcam_enhanced.py

import os
import sys
import numpy as np
import cv2
import mediapipe as mp
import time
import json
from collections import deque

system_height = 650
system_width = 1280
# pointNum rimosso - ora è dinamico in base ai landmark MediaPipe trovati!
pose_name = ['Pitch', 'Yaw', 'Roll']

# Sistema di scoring per i migliori frame
class FrameScorer:
    def __init__(self, max_frames=10):
        self.max_frames = max_frames
        self.best_frames = []  # Lista senza limite - mantiene TUTTI i frame della sessione
        self.frame_data = []
        self.output_dir = "best_frontal_frames"
        self.frames_added = 0
        self.last_update_count = 0
        
        # Crea directory di output se non esiste
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Pulisce eventuali vecchi file con formato obsoleto
        self._clean_obsolete_files()
    
    def calculate_face_score(self, pitch, yaw, roll, face_bbox, frame_width, frame_height):
        """
        Calcola il punteggio di un frame con 3 parametri:
        1. Qualità pose (yaw, pitch, roll) - PRIORITÀ MASSIMA
        2. Dimensione del volto - premia volti più grandi
        3. Posizione centrata - premia volti al centro del frame
        """
        
        # 1. POSE SCORE (0-100) - Più importante
        # Normalizza roll nel range corretto
        normalized_roll = roll
        while normalized_roll > 90:
            normalized_roll -= 180
        while normalized_roll < -90:
            normalized_roll += 180
            
        # Punteggio pose: penalizza deviazioni da pose frontale perfetta
        pose_deviation = abs(pitch) + abs(yaw) + abs(normalized_roll)
        pose_score = max(0, 100 - pose_deviation * 1.2)  # Moltiplicatore per sensibilità
        
        # 2. SIZE SCORE (0-100) - Premia volti PIÙ GRANDI
        face_width = face_bbox[1] - face_bbox[0]  # x_max - x_min
        face_height = face_bbox[3] - face_bbox[2]  # y_max - y_min
        face_area = face_width * face_height
        frame_area = frame_width * frame_height
        face_ratio = face_area / frame_area
        
        # AGGIORNATO: Premia volti ancora più grandi - range ottimale 30-45% del frame
        if face_ratio >= 0.30:  # Volti grandi: punteggio alto
            if face_ratio <= 0.45:  # Range ottimale espanso per volti più grandi
                size_score = 100  # Punteggio massimo
            elif face_ratio <= 0.55:  # Ancora buono ma inizia a penalizzare
                size_score = max(75, 100 - (face_ratio - 0.45) * 250)
            else:  # Troppo grande
                size_score = max(40, 75 - (face_ratio - 0.55) * 300)
        else:  # Volti piccoli: penalizza più severamente
            if face_ratio >= 0.20:  # Volti medi: punteggio ridotto
                size_score = max(40, (face_ratio - 0.20) * 600)  # Da 20% a 30% = da 40 a 100 punti
            else:  # Volti molto piccoli: penalizza fortemente
                size_score = max(0, face_ratio * 200)  # 0.20 = 40 punti, 0 = 0 punti
        
        # 3. POSITION SCORE (0-100) - Premia centralità COMPLETA
        face_center_x = (face_bbox[0] + face_bbox[1]) / 2
        face_center_y = (face_bbox[2] + face_bbox[3]) / 2
        
        frame_center_x = frame_width / 2
        frame_center_y = frame_height / 2
        
        # Distanza dal centro perfetto del frame
        distance_x = abs(face_center_x - frame_center_x) / (frame_width / 2)
        distance_y = abs(face_center_y - frame_center_y) / (frame_height / 2)
        
        # Combinazione delle distanze - più è centrato, più alto il punteggio
        total_distance = (distance_x + distance_y) / 2  # Media delle distanze
        position_score = max(0, 100 - total_distance * 100)
        
        # COMBINAZIONE FINALE CON NUOVI PESI
        total_score = (pose_score * 0.6 +      # 60% - PRIORITÀ MASSIMA per pose frontale
                      size_score * 0.3 +       # 30% - Importanza media per dimensione
                      position_score * 0.1)    # 10% - Minor importanza per posizione
        
        return total_score, {
            'pose_score': pose_score,
            'size_score': size_score,
            'position_score': position_score,
            'face_ratio': face_ratio,
            'center_distance_x': distance_x,
            'center_distance_y': distance_y,
            'total_center_distance': total_distance
        }
    
    def add_frame(self, clean_frame, pitch, yaw, roll, face_bbox, timestamp):
        """Aggiunge un frame al sistema di scoring e aggiorna i file continuamente"""
        frame_height, frame_width = clean_frame.shape[:2]
        
        score, score_details = self.calculate_face_score(
            pitch, yaw, roll, face_bbox, frame_width, frame_height
        )
        
        frame_data = {
            'frame': clean_frame.copy(),
            'score': score,
            'timestamp': timestamp,
            'pitch': pitch,
            'yaw': yaw,
            'roll': roll,
            'bbox': face_bbox,
            'score_details': score_details
        }
        
        self.best_frames.append(frame_data)
        self.frames_added += 1
        
        # Aggiorna i file periodicamente per evitare troppi I/O
        # Frequenza adattiva: più frame ci sono, meno spesso aggiorna
        update_frequency = max(30, min(100, len(self.best_frames) // 10))
        if self.frames_added - self.last_update_count >= update_frequency:
            self.update_best_frames_continuously()
            self.last_update_count = self.frames_added
    
    def update_best_frames_continuously(self):
        """Aggiorna continuamente i file dei migliori frame durante l'esecuzione"""
        if len(self.best_frames) == 0:
            return
        
        # Ordina per punteggio decrescente
        sorted_frames = sorted(self.best_frames, key=lambda x: x['score'], reverse=True)
        
        # Prendi i migliori frame (max_frames)
        best_frames = sorted_frames[:self.max_frames]
        
        # Rimuovi i vecchi file prima di salvare i nuovi
        self._clean_old_files()
        
        saved_frames = []
        
        for i, frame_data in enumerate(best_frames):
            # Nome file progressivo da 01 a 10 (01 = miglior punteggio)
            filename = f"frame_{i+1:02d}.jpg"
            filepath = os.path.join(self.output_dir, filename)
            cv2.imwrite(filepath, frame_data['frame'])
            
            # Prepara dati per JSON con nuovo sistema di scoring
            json_data = {
                'filename': filename,
                'rank': i + 1,
                'total_score': round(frame_data['score'], 2),
                'timestamp': frame_data['timestamp'],
                'pose': {
                    'pitch': round(frame_data['pitch'], 2),
                    'yaw': round(frame_data['yaw'], 2),
                    'roll': round(frame_data['roll'], 2)
                },
                'face_bbox': {
                    'x_min': int(frame_data['bbox'][0]),
                    'x_max': int(frame_data['bbox'][1]),
                    'y_min': int(frame_data['bbox'][2]),
                    'y_max': int(frame_data['bbox'][3])
                },
                'score_breakdown': {
                    'pose_score': round(frame_data['score_details']['pose_score'], 2),
                    'size_score': round(frame_data['score_details']['size_score'], 2),
                    'position_score': round(frame_data['score_details']['position_score'], 2),
                    'face_ratio': round(frame_data['score_details']['face_ratio'], 4),
                    'center_distance_x': round(frame_data['score_details']['center_distance_x'], 4),
                    'center_distance_y': round(frame_data['score_details']['center_distance_y'], 4),
                    'total_center_distance': round(frame_data['score_details']['total_center_distance'], 4)
                }
            }
            saved_frames.append(json_data)
        
        # Aggiorna JSON con i dati attuali
        json_filepath = os.path.join(self.output_dir, "best_frames_data.json")
        json_output = {
            'metadata': {
                'total_frames_processed': len(self.best_frames),
                'best_frames_saved': len(best_frames),
                'last_update': time.strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'updating_continuously',
                'scoring_criteria': {
                    'pose_weight': 0.6,
                    'size_weight': 0.3,
                    'position_weight': 0.1
                },
                'scoring_description': {
                    'pose': 'Frontality quality (pitch, yaw, roll) - TOP PRIORITY',
                    'size': 'Face size (prefers LARGER faces 30-45% of frame)',
                    'position': 'Face centering (both horizontal and vertical)'
                }
            },
            'frames': saved_frames
        }
        
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
    
    def _clean_old_files(self):
        """Rimuove i vecchi file frame prima di salvare i nuovi"""
        for i in range(1, self.max_frames + 1):
            old_filepath = os.path.join(self.output_dir, f"frame_{i:02d}.jpg")
            if os.path.exists(old_filepath):
                os.remove(old_filepath)
    
    def _clean_obsolete_files(self):
        """Rimuove vecchi file con formato obsoleto (con punteggio nel nome)"""
        import glob
        obsolete_pattern = os.path.join(self.output_dir, "best_frame_*.jpg")
        obsolete_files = glob.glob(obsolete_pattern)
        for file_path in obsolete_files:
            try:
                os.remove(file_path)
            except OSError:
                pass  # Ignora errori se il file è già stato rimosso
    
    def save_final_best_frames(self):
        """Salvataggio finale dei migliori frame alla chiusura dell'app"""
        if len(self.best_frames) == 0:
            print("Nessun frame da salvare")
            return 0
        
        # Ordina per punteggio decrescente
        sorted_frames = sorted(self.best_frames, key=lambda x: x['score'], reverse=True)
        
        # Prendi i migliori frame (max_frames)
        best_frames = sorted_frames[:self.max_frames]
        
        # Rimuovi i vecchi file prima di salvare i nuovi
        self._clean_old_files()
        
        saved_frames = []
        
        for i, frame_data in enumerate(best_frames):
            # Nome file definitivo progressivo da 01 a 10
            filename = f"frame_{i+1:02d}.jpg"
            filepath = os.path.join(self.output_dir, filename)
            cv2.imwrite(filepath, frame_data['frame'])
            
            # Prepara dati per JSON finale con nuovo sistema
            json_data = {
                'filename': filename,
                'rank': i + 1,
                'total_score': round(frame_data['score'], 2),
                'timestamp': frame_data['timestamp'],
                'pose': {
                    'pitch': round(frame_data['pitch'], 2),
                    'yaw': round(frame_data['yaw'], 2),
                    'roll': round(frame_data['roll'], 2)
                },
                'face_bbox': {
                    'x_min': int(frame_data['bbox'][0]),
                    'x_max': int(frame_data['bbox'][1]),
                    'y_min': int(frame_data['bbox'][2]),
                    'y_max': int(frame_data['bbox'][3])
                },
                'score_breakdown': {
                    'pose_score': round(frame_data['score_details']['pose_score'], 2),
                    'size_score': round(frame_data['score_details']['size_score'], 2),
                    'position_score': round(frame_data['score_details']['position_score'], 2),
                    'face_ratio': round(frame_data['score_details']['face_ratio'], 4),
                    'center_distance_x': round(frame_data['score_details']['center_distance_x'], 4),
                    'center_distance_y': round(frame_data['score_details']['center_distance_y'], 4),
                    'total_center_distance': round(frame_data['score_details']['total_center_distance'], 4)
                }
            }
            saved_frames.append(json_data)
        
        # Salva JSON finale
        json_filepath = os.path.join(self.output_dir, "best_frames_data.json")
        json_output = {
            'metadata': {
                'total_frames_processed': len(self.best_frames),
                'best_frames_saved': len(best_frames),
                'session_completed': time.strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'final_save_completed',
                'scoring_criteria': {
                    'pose_weight': 0.6,
                    'size_weight': 0.3,
                    'position_weight': 0.1
                },
                'scoring_description': {
                    'pose': 'Frontality quality (pitch, yaw, roll) - TOP PRIORITY',
                    'size': 'Face size (prefers LARGER faces 30-45% of frame)',
                    'position': 'Face centering (both horizontal and vertical)'
                }
            },
            'frames': saved_frames
        }
        
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ SALVATAGGIO FINALE: {len(best_frames)} migliori frame salvati in: {self.output_dir}")
        print(f"📄 Dati finali JSON salvati in: {json_filepath}")
        print(f"🏆 Miglior punteggio finale: {best_frames[0]['score']:.1f}")
        print(f"📊 Frame totali processati durante la sessione: {len(self.best_frames)}")
        
        return len(best_frames)

def get_all_mediapipe_landmarks(mediapipe_landmarks, img_width, img_height):
    """Estrae TUTTI i landmark MediaPipe (468 punti) senza limitazioni dlib"""
    
    # MediaPipe Face Mesh ha 468 landmark - li prendiamo TUTTI!
    num_landmarks = len(mediapipe_landmarks.landmark)
    
    # Array dinamico per tutti i punti trovati
    all_landmarks = np.zeros((num_landmarks, 2))
    
    # Estrai OGNI singolo landmark senza limitazioni
    for i in range(num_landmarks):
        landmark = mediapipe_landmarks.landmark[i]
        
        # Coordinate normalizzate da MediaPipe (0.0-1.0)
        x = landmark.x * img_width
        y = landmark.y * img_height
        
        # Validazione coordinate (mantieni dentro l'immagine)
        x = max(1, min(img_width-1, x))
        y = max(1, min(img_height-1, y))
        
        all_landmarks[i, 0] = x
        all_landmarks[i, 1] = y
    
    return all_landmarks

def calculate_head_pose_from_mediapipe(landmarks_array, img_width, img_height):
    """Calcola la pose della testa usando DIRETTAMENTE i landmark MediaPipe (468 punti)"""
    
    try:
        # Indici MediaPipe Face Mesh corretti (basati sulla documentazione ufficiale)
        NOSE_TIP = 4        # Punta del naso (tip of nose)
        CHIN = 152          # Mento (chin)
        LEFT_EYE_CORNER = 33   # Angolo interno occhio sinistro  
        RIGHT_EYE_CORNER = 263 # Angolo interno occhio destro
        LEFT_MOUTH_CORNER = 78  # Angolo sinistro bocca
        RIGHT_MOUTH_CORNER = 308 # Angolo destro bocca
        
        # landmarks_array è già un array NumPy con coordinate [x, y]
        # Verifica che abbiamo abbastanza landmark
        if len(landmarks_array) < 468:
            return np.array([0.0, 0.0, 0.0])
        
        # Punti chiave con indici MediaPipe corretti
        nose_tip = landmarks_array[NOSE_TIP]
        chin = landmarks_array[CHIN] 
        left_eye = landmarks_array[LEFT_EYE_CORNER]
        right_eye = landmarks_array[RIGHT_EYE_CORNER]
        left_mouth = landmarks_array[LEFT_MOUTH_CORNER]
        right_mouth = landmarks_array[RIGHT_MOUTH_CORNER]
        
        # Verifica validità punti
        points_2d = np.array([nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth])
        if np.any(np.isnan(points_2d)):
            return np.array([0.0, 0.0, 0.0])
        
        # Modello 3D del volto - proporzioni anatomiche realistiche
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Punta del naso (origine)
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
            # Converti il vettore di rotazione in matrice di rotazione
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            
            # Estrai gli angoli di Eulero (pitch, yaw, roll)
            # Conversione da matrice di rotazione ad angoli di Eulero
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
            
            return np.array([pitch, yaw, roll])
            
    except Exception as e:
        return np.array([0.0, 0.0, 0.0])
    
    return np.array([0.0, 0.0, 0.0])

def is_frontal_pose(pitch, yaw, roll, strict=False):
    """Determina se la pose è frontale con soglie normalizzate"""
    # Normalizza il Roll per la valutazione
    normalized_roll = roll
    while normalized_roll > 90:
        normalized_roll -= 180
    while normalized_roll < -90:
        normalized_roll += 180
    
    if strict:
        # Soglie rigide per pose perfettamente frontale
        return abs(pitch) <= 8 and abs(yaw) <= 8 and abs(normalized_roll) <= 5
    else:
        # Soglie permissive per pose accettabilmente frontale  
        return abs(pitch) <= 25 and abs(yaw) <= 25 and abs(normalized_roll) <= 15

def get_pose_status_and_color(pitch, yaw, roll):
    """Restituisce stato della pose e colore con valori normalizzati"""
    # Normalizza il Roll
    normalized_roll = roll
    while normalized_roll > 90:
        normalized_roll -= 180
    while normalized_roll < -90:
        normalized_roll += 180
    
    # Usa il Roll normalizzato per il calcolo
    max_angle = max(abs(pitch), abs(yaw), abs(normalized_roll))
    
    if max_angle <= 8:
        return "🎯 PERFETTO FRONTALE", (0, 255, 0), 4  # Verde brillante
    elif max_angle <= 15:
        return "✅ Ottimo frontale", (0, 200, 0), 3     # Verde medio
    elif max_angle <= 25:
        return "👍 Buono frontale", (0, 255, 255), 2   # Giallo
    elif max_angle <= 40:
        return "⚠️ Accettabile", (0, 165, 255), 2      # Arancione
    else:
        return "❌ Non frontale", (0, 0, 255), 2       # Rosso

def show_enhanced_image_with_score(img, facepoint, bboxs, headpose=None, show_landmarks=True, show_numbers=False, current_score=0.0, frames_collected=0):
    """Versione con sistema di scoring integrato"""
    show_enhanced_image(img, facepoint, bboxs, headpose, show_landmarks, show_numbers)
    
    # Aggiungi informazioni di scoring nella parte superiore destra
    score_color = (0, 255, 0) if current_score > 70 else (0, 255, 255) if current_score > 50 else (0, 165, 255) if current_score > 30 else (0, 0, 255)
    
    cv2.putText(img, f"Current: {current_score:.1f}", (img.shape[1] - 200, 25), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, score_color, 2)
    cv2.putText(img, f"Total: {frames_collected}", (img.shape[1] - 200, 50), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(img, f"Analyzing...", (img.shape[1] - 200, 75), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    # Barra di progresso per il punteggio corrente
    bar_width = 150
    bar_height = 8
    bar_x = img.shape[1] - 200
    bar_y = 85
    
    # Sfondo della barra
    cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (40, 40, 40), -1)
    
    # Riempimento della barra basato sul punteggio corrente
    fill_width = int((current_score / 100.0) * bar_width)
    if fill_width > 0:
        cv2.rectangle(img, (bar_x, bar_y), (bar_x + fill_width, bar_y + bar_height), score_color, -1)
    
    # Indicatore di attività (puntino che si muove per mostrare processing continuo)
    import time
    pulse = int((time.time() * 3) % bar_width)
    cv2.circle(img, (bar_x + pulse, bar_y + bar_height + 8), 2, (0, 255, 255), -1)

def show_enhanced_image(img, facepoint, bboxs, headpose=None, show_landmarks=True, show_numbers=False):
    """Versione migliorata per mostrare TUTTI i landmark MediaPipe con rilevamento frontale avanzato"""
    
    for faceNum in range(facepoint.shape[0]):
        # Determina colore e status basato sulla pose
        bbox_color = (128, 128, 128)  # Grigio default
        pose_status = "No Face"
        thickness = 2
        pitch = yaw = roll = 0.0
        
        if headpose is not None and faceNum < headpose.shape[0]:
            pitch, yaw, roll = headpose[faceNum, 0], headpose[faceNum, 1], headpose[faceNum, 2]
            
            # Usa la nuova funzione avanzata per determinare status e colore
            pose_status, bbox_color, thickness = get_pose_status_and_color(pitch, yaw, roll)
        cv2.rectangle(img, (int(bboxs[faceNum,0]), int(bboxs[faceNum,2])), 
                     (int(bboxs[faceNum,1]), int(bboxs[faceNum,3])), bbox_color, thickness)
        
        # Mostra valori pose con aggiornamento in tempo reale
        if headpose is not None and faceNum < headpose.shape[0]:
            # Posizione per i valori della pose
            pose_x = int(bboxs[faceNum,0])
            pose_y = int(bboxs[faceNum,2])
            
            for p in range(3):
                raw_angle = headpose[faceNum,p]
                
                # Normalizzazione dei valori per range realistici
                if p == 2:  # Roll - normalizza nel range ±90°
                    # Assicura che il Roll sia nel range -90° a +90°
                    angle_value = raw_angle
                    while angle_value > 90:
                        angle_value -= 180
                    while angle_value < -90:
                        angle_value += 180
                else:  # Pitch e Yaw - mantieni nel range ±180° ma limita display a ±90°
                    angle_value = max(-90, min(90, raw_angle))
                
                # Soglie aggiornate per range realistici
                if p == 2:  # Roll - soglie specifiche per inclinazione laterale
                    if abs(angle_value) <= 5:
                        text_color = (0, 255, 0)    # Verde - perfetto
                    elif abs(angle_value) <= 15:
                        text_color = (50, 255, 50)  # Verde chiaro - molto buono  
                    elif abs(angle_value) <= 30:
                        text_color = (0, 255, 255)  # Giallo - buono
                    elif abs(angle_value) <= 45:
                        text_color = (0, 165, 255)  # Arancione - accettabile
                    else:
                        text_color = (0, 0, 255)    # Rosso - troppo inclinato
                else:  # Pitch e Yaw - soglie standard
                    if abs(angle_value) <= 8:
                        text_color = (0, 255, 0)    # Verde - perfetto
                    elif abs(angle_value) <= 15:
                        text_color = (50, 255, 50)  # Verde chiaro - ottimo
                    elif abs(angle_value) <= 25:
                        text_color = (0, 255, 255)  # Giallo - buono
                    elif abs(angle_value) <= 40:
                        text_color = (0, 165, 255)  # Arancione - accettabile
                    else:
                        text_color = (0, 0, 255)    # Rosso - problematico
                
                # Testo più grande e chiaro con formattazione migliorata
                # Formato: nome: +/-XX.X° (sempre con segno e larghezza fissa)
                sign = '+' if angle_value >= 0 else '-'
                abs_value = abs(angle_value)
                value_text = f'{pose_name[p]}: {sign}{abs_value:4.1f}°'
                cv2.putText(img, value_text,
                           (pose_x, pose_y - (p+1)*30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
                
                # Piccolo punto verde per indicare aggiornamento in tempo reale
                cv2.circle(img, (pose_x - 10, pose_y - (p+1)*30 - 5), 3, (0, 255, 0), -1)
        
        # Disegna TUTTI i landmark MediaPipe se abilitato
        if show_landmarks:
            # Calcola numero totale di landmark disponibili
            total_landmarks = facepoint.shape[1] // 2
            
            # Definisce gruppi di colori per diversi range di landmark
            landmark_groups = [
                (range(0, 17), (255, 0, 0), "Contorno", 2),        # Rosso per contorno viso
                (range(17, 27), (0, 255, 255), "Sopracciglia", 2), # Giallo per sopracciglia  
                (range(27, 36), (255, 255, 0), "Naso", 2),         # Ciano per naso
                (range(36, 48), (255, 0, 255), "Occhi", 3),        # Magenta per occhi
                (range(48, 68), (0, 255, 0), "Bocca", 2),          # Verde per bocca
                # NUOVI GRUPPI per landmark MediaPipe aggiuntivi (68+)
                (range(68, min(150, total_landmarks)), (100, 149, 237), "Face Mesh 1", 1),  # Cornflower blue
                (range(150, min(300, total_landmarks)), (147, 20, 255), "Face Mesh 2", 1),  # Deep pink
                (range(300, total_landmarks), (0, 191, 255), "Face Mesh 3", 1),             # Deep sky blue
            ]
            
            landmarks_drawn = 0
            for point_range, color, name, radius in landmark_groups:
                for i in point_range:
                    if i < total_landmarks:
                        x = int(round(facepoint[faceNum, i*2]))
                        y = int(round(facepoint[faceNum, i*2+1]))
                        
                        # Disegna solo punti validi
                        if x > 1 and y > 1:
                            landmarks_drawn += 1
                            cv2.circle(img, (x, y), radius, color, -1)
                            
                            # Mostra numeri se richiesto (solo ogni 10° punto per chiarezza)
                            if show_numbers and i % 10 == 0:
                                cv2.putText(img, str(i), (x+3, y-3),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
            
            # Mostra conteggio landmark reali disegnati
            cv2.putText(img, f'Landmarks: {landmarks_drawn}/{total_landmarks}', (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    # Informazioni nella parte superiore con status frontale
    info_y = 25
    cv2.putText(img, f"Status: {pose_status}", (10, info_y), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, bbox_color, 2)
    
    # Legenda controlli aggiornata
    controls = [
        "Q=Quit+Save | L=Landmarks | N=Numbers | S=Save Current | B=Update Now | T=Toggle Scoring",
        "CONTINUOUS ANALYSIS: Processing ALL session frames - No time/frame limits"
    ]
    
    for i, text in enumerate(controls):
        cv2.putText(img, text, (10, img.shape[0] - 40 + i*20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Ridimensiona se necessario
    height, width = img.shape[:2]
    if height > system_height or width > system_width:
        height_radius = system_height / height
        width_radius = system_width / width
        radius = min(height_radius, width_radius)
        img = cv2.resize(img, (0, 0), fx=radius, fy=radius)
    
    cv2.imshow('Enhanced Face Landmark Detection', img)

def predict_image_webcam():
    """Funzione principale migliorata con sistema di scoring"""
    
    print("=== Enhanced Face Landmark Detection con Sistema di Scoring ===")
    print("🎯 Sistema di raccolta continua dei migliori frame frontali")
    print("📊 NUOVO SISTEMA: 3 criteri ottimizzati")
    print("🎯 1) POSE (60%) - Qualità frontale massima priorità")  
    print("📏 2) SIZE (30%) - Premia volti PIÙ GRANDI (30-45% del frame)")
    print("� 3) POSITION (10%) - Centramento completo nel frame")
    print("� Analisi continua per tutta la sessione - sempre i migliori!")
    print("⌨️  Controlli: Q=Esci+Salva | B=Aggiorna ora | T=Toggle scoring")
    print("Inizializzazione...")
    
    # Inizializza sistema di scoring
    frame_scorer = FrameScorer(max_frames=10)
    
    # MediaPipe setup
    mp_face_mesh = mp.solutions.face_mesh
    
    face_mesh = mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("ERRORE: Impossibile aprire la webcam")
        return
    
    # Impostazioni webcam
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # Webcam attiva - tutti i controlli e informazioni mostrati nel video
    
    # Stato dell'applicazione
    show_landmarks = True
    show_numbers = False
    frame_count = 0
    scoring_enabled = True  # Sistema di scoring attivo
    fps_start_time = time.time()
    last_pose_values = None  # Per verificare l'aggiornamento dei valori
    current_score = 0.0  # Punteggio del frame corrente

    try:
        while True:
            ret, colorImage = cap.read()
            if not ret:
                break
                
            frame_count += 1
            
            # Flip per effetto specchio
            colorImage = cv2.flip(colorImage, 1)
            
            # Processa con MediaPipe
            rgb_frame = cv2.cvtColor(colorImage, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    h, w = colorImage.shape[:2]
                    
                    # Converti landmarks - TUTTI i MediaPipe (NON limitati a 68!)
                    all_landmarks = get_all_mediapipe_landmarks(face_landmarks, w, h)
                    
                    # Aggiorna numero di punti per riflettere i landmark reali
                    actual_pointNum = len(all_landmarks)
                    # Nessun debug nel terminale
                    
                    # Prepara per visualizzazione - TUTTI i landmark trovati
                    predictpoints = np.zeros((1, actual_pointNum*2))
                    for i in range(actual_pointNum):  # TUTTI i punti MediaPipe
                        predictpoints[0, i*2] = all_landmarks[i, 0]
                        predictpoints[0, i*2+1] = all_landmarks[i, 1]
                    
                    # Calcola bounding box
                    valid_x = [x for x in predictpoints[0, 0::2] if x > 0]
                    valid_y = [y for y in predictpoints[0, 1::2] if y > 0]
                    
                    if valid_x and valid_y:
                        x_min, x_max = min(valid_x), max(valid_x)
                        y_min, y_max = min(valid_y), max(valid_y)
                        
                        margin = 30
                        bboxs = np.array([[
                            max(0, x_min-margin), min(w, x_max+margin),
                            max(0, y_min-margin), min(h, y_max+margin)
                        ]])
                        
                        # Calcola pose usando tutti i landmark MediaPipe
                        if actual_pointNum >= 6:  # Verifica che ci siano abbastanza landmark
                            head_pose = calculate_head_pose_from_mediapipe(all_landmarks, w, h)
                            predictpose = np.array([head_pose])
                            
                            # Sistema di scoring - aggiungi frame se il scoring è abilitato
                            if scoring_enabled:
                                # Salva il frame pulito (senza overlay) per il sistema di scoring
                                clean_frame = colorImage.copy()
                                timestamp = time.time()
                                
                                # Calcola il punteggio e aggiungi al sistema
                                score, _ = frame_scorer.calculate_face_score(
                                    head_pose[0], head_pose[1], head_pose[2], 
                                    bboxs[0], w, h
                                )
                                current_score = score
                                
                                # Aggiungi OGNI frame con volto rilevato al sistema di scoring
                                # Rimussa soglia minima - analizza tutti i frame per trovare i migliori
                                frame_scorer.add_frame(
                                    clean_frame, head_pose[0], head_pose[1], head_pose[2],
                                    bboxs[0], timestamp
                                )
                            
                            # Verifica che i valori si aggiornino (solo se cambiano significativamente)
                            if last_pose_values is None or \
                               abs(head_pose[0] - last_pose_values[0]) > 2 or \
                               abs(head_pose[1] - last_pose_values[1]) > 2 or \
                               abs(head_pose[2] - last_pose_values[2]) > 2:
                                last_pose_values = head_pose.copy()
                        else:
                            # Fallback: pose neutrale
                            head_pose = [0.0, 0.0, 0.0]  # pitch, yaw, roll = 0
                            predictpose = np.array([head_pose])
                            current_score = 0.0
                        
                        # Mostra l'immagine con overlay di debug
                        show_enhanced_image_with_score(colorImage, predictpoints, bboxs, predictpose, 
                                          show_landmarks, show_numbers, current_score, len(frame_scorer.best_frames))
                    else:
                        cv2.imshow('Enhanced Face Landmark Detection', colorImage)
            else:
                cv2.imshow('Enhanced Face Landmark Detection', colorImage)
            
            # Gestione input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                # Salvataggio finale prima di uscire
                if len(frame_scorer.best_frames) > 0:
                    print("\n💾 Eseguendo salvataggio finale...")
                    frame_scorer.save_final_best_frames()
                break
            elif key == ord('l'):
                show_landmarks = not show_landmarks
                print(f"Landmarks: {'ON' if show_landmarks else 'OFF'}")
            elif key == ord('n'):
                show_numbers = not show_numbers
                print(f"Numbers: {'ON' if show_numbers else 'OFF'}")
            elif key == ord('s'):
                filename = f"face_detection_{int(time.time())}.jpg"
                cv2.imwrite(filename, colorImage)
                print(f"Frame corrente salvato: {filename}")
            elif key == ord('b'):
                # Forza aggiornamento immediato dei migliori frame
                if len(frame_scorer.best_frames) > 0:
                    frame_scorer.update_best_frames_continuously()
                    print(f"💾 Aggiornamento manuale completato - {len(frame_scorer.best_frames)} frame processati!")
                else:
                    print("⚠️  Nessun frame da aggiornare ancora")
            elif key == ord('t'):
                scoring_enabled = not scoring_enabled
                print(f"Sistema di scoring: {'ATTIVO' if scoring_enabled else 'DISATTIVATO'}")
            elif key == ord('r'):
                print("Reset rilevamento...")
                face_mesh.close()
                face_mesh = mp_face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.7,
                    min_tracking_confidence=0.5
                )
    
    except KeyboardInterrupt:
        print("\nInterruzione utente")
    finally:
        # Calcola FPS media
        total_time = time.time() - fps_start_time
        avg_fps = frame_count / total_time if total_time > 0 else 0
        
        print(f"\n📊 Statistiche sessione:")
        print(f"- Frame processati: {frame_count}")
        print(f"- FPS medio: {avg_fps:.1f}")
        print(f"- Durata: {total_time:.1f} secondi")
        print(f"- Frame raccolti per scoring: {len(frame_scorer.best_frames)}")
        
        # Salvataggio finale se non è già stato fatto
        if len(frame_scorer.best_frames) > 0:
            print("\n💾 Salvataggio finale dei migliori frame...")
            frame_scorer.save_final_best_frames()
        
        cap.release()
        cv2.destroyAllWindows()
        face_mesh.close()
        print("✅ Programma terminato - controlla la cartella 'best_frontal_frames' per i risultati!")

if __name__ == '__main__':
    predict_image_webcam()