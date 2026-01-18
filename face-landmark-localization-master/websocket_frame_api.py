#!/usr/bin/env python3
"""
WebSocket API per l'analisi dei frame in tempo reale
Riceve frame dal client via WebSocket e restituisce i migliori 10 frame con JSON
Basato su landmarkPredict_webcam_enhanced.py
"""

import asyncio
import websockets
import json
import base64
import cv2
import numpy as np
import mediapipe as mp
import time
import os
import io
from collections import deque
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketFrameScorer:
    """Versione WebSocket del FrameScorer"""
    
    def __init__(self, max_frames=10):
        self.max_frames = max_frames
        self.best_frames = []  # Buffer circolare - mantiene solo i migliori
        self.buffer_size = max_frames * 4  # Buffer 4x per catturare più variazioni (40 frame)
        self.output_dir = "websocket_best_frames"
        self.frames_added = 0
        self.frames_processed = 0  # Contatore frame totali processati
        self.session_id = None
        self.min_score_threshold = 70  # Soglia minima: scarta solo frame molto scarsi
        
        # MediaPipe setup
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,  # Abbassato da 0.7 per catturare più pose frontali
            min_tracking_confidence=0.5
        )
        
        # Crea directory di output se non esiste
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def start_session(self, session_id):
        """Inizia una nuova sessione"""
        self.session_id = session_id
        self.best_frames = []
        self.frames_added = 0
        self.frames_processed = 0  # Reset contatore frame
        self.min_score_threshold = 0  # Reset soglia
        
        # Crea sottocartella per la sessione
        self.session_dir = os.path.join(self.output_dir, f"session_{session_id}")
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)
        
        logger.info(f"Nuova sessione iniziata: {session_id}")
    
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
                return np.array([0.0, 0.0, 0.0])
            
            # Punti chiave
            nose_tip = landmarks_array[NOSE_TIP]
            chin = landmarks_array[CHIN] 
            left_eye = landmarks_array[LEFT_EYE_CORNER]
            right_eye = landmarks_array[RIGHT_EYE_CORNER]
            left_mouth = landmarks_array[LEFT_MOUTH_CORNER]
            right_mouth = landmarks_array[RIGHT_MOUTH_CORNER]
            
            points_2d = np.array([nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth])
            if np.any(np.isnan(points_2d)):
                return np.array([0.0, 0.0, 0.0])
            
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
                
                return np.array([pitch, yaw, roll])
                
        except Exception as e:
            logger.error(f"Errore nel calcolo pose: {e}")
            return np.array([0.0, 0.0, 0.0])
        
        return np.array([0.0, 0.0, 0.0])
    
    def calculate_face_score(self, pitch, yaw, roll, face_bbox, frame_width, frame_height):
        """Sistema di scoring a 3 parametri ottimizzato"""
        
        # 1. POSE SCORE (0-100) - 60% del punteggio
        # YAW e PITCH hanno peso UGUALE per bilanciare frontalità verticale/orizzontale
        
        # ✅ Normalizza Roll a range [-180, 180] → [-90, 90]
        # MediaPipe a volte inverte di 180° l'asse Roll per orientamento video
        normalized_roll = roll
        while normalized_roll > 180:
            normalized_roll -= 360
        while normalized_roll < -180:
            normalized_roll += 360
            
        # Se Roll è vicino a ±180°, è equivalente a 0° (inversione asse)
        if abs(normalized_roll) > 150:
            # Esempio: Roll=-177° → equivalente a +3° (180-177=3)
            normalized_roll = 180 - abs(normalized_roll)
            if roll < 0:
                normalized_roll = -normalized_roll
        
        # Ora normalizza a [-90, 90]
        while normalized_roll > 90:
            normalized_roll -= 180
        while normalized_roll < -90:
            normalized_roll += 180
        
        roll_weighted = abs(normalized_roll) * 0.3

        # Pesi PRIORITÀ YAW: Yaw ha peso maggiore per privilegiare frontalità orizzontale
        yaw_weighted = abs(yaw) * 2.5
        pitch_weighted = abs(pitch) * 1.0

        pose_deviation = yaw_weighted + pitch_weighted + roll_weighted
        pose_score = max(0, 100 - pose_deviation * 0.8)
        
        # 2. SIZE SCORE (0-100) - 30% del punteggio - Premia volti PIÙ GRANDI
        face_width = face_bbox[1] - face_bbox[0]
        face_height = face_bbox[3] - face_bbox[2]
        face_area = face_width * face_height
        frame_area = frame_width * frame_height
        face_ratio = face_area / frame_area
        
        # Range ottimale 30-45% del frame per volti più grandi
        if face_ratio >= 0.30:
            if face_ratio <= 0.45:
                size_score = 100
            elif face_ratio <= 0.55:
                size_score = max(75, 100 - (face_ratio - 0.45) * 250)
            else:
                size_score = max(40, 75 - (face_ratio - 0.55) * 300)
        else:
            if face_ratio >= 0.20:
                size_score = max(40, (face_ratio - 0.20) * 600)
            else:
                size_score = max(0, face_ratio * 200)
        
        # 3. POSITION SCORE (0-100) - 10% del punteggio - Centramento completo
        face_center_x = (face_bbox[0] + face_bbox[1]) / 2
        face_center_y = (face_bbox[2] + face_bbox[3]) / 2
        
        frame_center_x = frame_width / 2
        frame_center_y = frame_height / 2
        
        distance_x = abs(face_center_x - frame_center_x) / (frame_width / 2)
        distance_y = abs(face_center_y - frame_center_y) / (frame_height / 2)
        
        total_distance = (distance_x + distance_y) / 2
        position_score = max(0, 100 - total_distance * 100)
        
        # Combinazione finale con pesi ottimizzati
        total_score = (pose_score * 0.6 + size_score * 0.3 + position_score * 0.1)
        
        return total_score, {
            'pose_score': pose_score,
            'size_score': size_score,
            'position_score': position_score,
            'face_ratio': face_ratio,
            'center_distance_x': distance_x,
            'center_distance_y': distance_y,
            'total_center_distance': total_distance
        }
    
    async def process_frame(self, frame_data):
        """Processa un singolo frame ricevuto dal client"""
        try:
            # Incrementa contatore frame processati
            self.frames_processed += 1
            current_frame_number = self.frames_processed
            
            # Decodifica il frame da base64
            frame_bytes = base64.b64decode(frame_data)
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return {"error": "Impossibile decodificare il frame"}
            
            h, w = frame.shape[:2]
            
            # Processa con MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)
            
            response = {
                "frame_processed": True,
                "faces_detected": 0,
                "current_score": 0.0,
                "total_frames_collected": len(self.best_frames)
            }
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Estrai landmark
                    all_landmarks = self.get_all_mediapipe_landmarks(face_landmarks, w, h)
                    
                    if len(all_landmarks) >= 6:
                        # Calcola bounding box
                        valid_x = [x for x in all_landmarks[:, 0] if x > 0]
                        valid_y = [y for y in all_landmarks[:, 1] if y > 0]
                        
                        if valid_x and valid_y:
                            x_min, x_max = min(valid_x), max(valid_x)
                            y_min, y_max = min(valid_y), max(valid_y)
                            
                            margin = 30
                            bbox = [
                                max(0, x_min-margin), min(w, x_max+margin),
                                max(0, y_min-margin), min(h, y_max+margin)
                            ]
                            
                            # Calcola pose
                            head_pose = self.calculate_head_pose_from_mediapipe(all_landmarks, w, h)
                            
                            # Calcola score
                            score, score_details = self.calculate_face_score(
                                head_pose[0], head_pose[1], head_pose[2], bbox, w, h
                            )
                            
                            # ✅ FILTRO: Scarta solo Yaw/Pitch invalidi (>170°)
                            # Roll>170° è gestito con normalizzazione (inversione asse)
                            is_invalid = (abs(head_pose[0]) > 170 or  # Pitch invalido
                                         abs(head_pose[1]) > 170)      # Yaw invalido
                            
                            if is_invalid:
                                # ⚠️ LOG RIDOTTO: Non stampare ogni frame scartato
                                response.update({
                                    "faces_detected": 1,
                                    "current_score": 0,
                                    "warning": "Frame scartato - pose invalida"
                                })
                                return response
                            
                            # Aggiungi frame al sistema di scoring
                            frame_data = {
                                'frame': frame.copy(),
                                'frame_number': current_frame_number,  # Numero frame originale
                                'score': score,
                                'timestamp': time.time(),
                                'pitch': head_pose[0],
                                'yaw': head_pose[1],
                                'roll': head_pose[2],
                                'bbox': bbox,
                                'score_details': score_details
                            }
                            
                            # ✅ BUFFER CIRCOLARE INTELLIGENTE CON PRIORITÀ PER FRAME ECCELLENTI
                            # Frame con score >95 hanno SEMPRE priorità (pose quasi perfette)
                            is_excellent = score >= 95
                            
                            if len(self.best_frames) < self.buffer_size:
                                # Buffer non pieno - aggiungi se supera soglia minima
                                if score >= self.min_score_threshold or is_excellent:
                                    self.best_frames.append(frame_data)
                                    self.frames_added += 1
                                    
                                    # Riordina e aggiorna soglia quando raggiungi buffer_size
                                    if len(self.best_frames) == self.buffer_size:
                                        self.best_frames.sort(key=lambda x: x['score'], reverse=True)
                                        self.min_score_threshold = max(70, self.best_frames[-1]['score'])  # Min 70
                                        logger.info(f"✅ Buffer pieno ({self.buffer_size}), soglia aggiornata: {self.min_score_threshold:.2f}")
                            elif score > self.min_score_threshold or is_excellent:
                                # Buffer pieno - sostituisci il peggiore se questo è migliore O se è eccellente
                                self.best_frames[-1] = frame_data
                                self.frames_added += 1
                                
                                # Riordina e aggiorna soglia
                                self.best_frames.sort(key=lambda x: x['score'], reverse=True)
                                old_threshold = self.min_score_threshold
                                self.min_score_threshold = max(70, self.best_frames[-1]['score'])
                                
                                if is_excellent:
                                    logger.info(f"🌟 Frame ECCELLENTE #{current_frame_number} score={score:.2f}")
                                # ⚠️ LOG RIDOTTO: Non stampare ogni sostituzione
                            else:
                                # ⚠️ LOG RIDOTTO: Non stampare ogni frame scartato
                                pass
                            
                            # Calcola Roll normalizzato per la UI
                            normalized_roll_display = head_pose[2]
                            while normalized_roll_display > 180:
                                normalized_roll_display -= 360
                            while normalized_roll_display < -180:
                                normalized_roll_display += 360
                            if abs(normalized_roll_display) > 150:
                                # Inversione asse: 173° → 7°, -177° → -3°
                                normalized_roll_display = 180 - abs(normalized_roll_display)
                                if head_pose[2] < 0:
                                    normalized_roll_display = -normalized_roll_display
                            
                            response.update({
                                "faces_detected": 1,
                                "current_score": round(score, 2),
                                "pose": {
                                    "pitch": round(head_pose[0], 2),
                                    "yaw": round(head_pose[1], 2),
                                    "roll": round(normalized_roll_display, 2)  # Roll normalizzato
                                },
                                "score_breakdown": {
                                    "pose_score": round(score_details['pose_score'], 2),
                                    "size_score": round(score_details['size_score'], 2),
                                    "position_score": round(score_details['position_score'], 2)
                                }
                            })
            
            return response
            
        except Exception as e:
            logger.error(f"Errore processing frame: {e}")
            return {"error": f"Errore nel processing: {str(e)}"}
    
    def get_best_frames_result(self):
        """Restituisce i migliori 10 frame e il JSON"""
        if len(self.best_frames) == 0:
            return {"error": "Nessun frame processato"}

        # ✅ COPIA ATOMICA: Ordina e copia il buffer per evitare race condition
        # Durante la preparazione della risposta, process_frame() potrebbe modificare il buffer
        # Creando una copia snapshot garantiamo che frames_base64 e frames_data siano coerenti
        self.best_frames.sort(key=lambda x: x['score'], reverse=True)
        best_frames_snapshot = [frame.copy() for frame in self.best_frames[:self.max_frames]]

        # Usa lo snapshot invece del buffer originale
        best_frames = best_frames_snapshot
        
        # Salva i frame e prepara i dati
        frames_base64 = []
        frames_data = []
        
        for i, frame_data in enumerate(best_frames):
            # Salva frame come immagine
            filename = f"frame_{i+1:02d}.jpg"
            filepath = os.path.join(self.session_dir, filename)
            cv2.imwrite(filepath, frame_data['frame'])
            
            # Converti frame in base64 per la risposta
            _, buffer = cv2.imencode('.jpg', frame_data['frame'])
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            frames_base64.append({
                'filename': filename,
                'data': frame_b64,
                'rank': frame_data.get('frame_number', i + 1),  # Usa frame_number originale
                'score': round(frame_data['score'], 2)
            })
            
            # Normalizza Roll per la UI
            roll_raw = frame_data['roll']
            normalized_roll_display = roll_raw
            while normalized_roll_display > 180:
                normalized_roll_display -= 360
            while normalized_roll_display < -180:
                normalized_roll_display += 360
            if abs(normalized_roll_display) > 150:
                normalized_roll_display = 180 - abs(normalized_roll_display)
                if roll_raw < 0:
                    normalized_roll_display = -normalized_roll_display
            
            # Prepara dati JSON
            json_data = {
                'filename': filename,
                'rank': frame_data.get('frame_number', i + 1),  # Usa frame_number originale
                'total_score': round(frame_data['score'], 2),
                'timestamp': frame_data['timestamp'],
                'pose': {
                    'pitch': round(frame_data['pitch'], 2),
                    'yaw': round(frame_data['yaw'], 2),
                    'roll': round(normalized_roll_display, 2)  # Roll normalizzato
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
            frames_data.append(json_data)
        
        # Crea JSON finale
        json_result = {
            'metadata': {
                'session_id': self.session_id,
                'total_frames_processed': len(self.best_frames),
                'best_frames_saved': len(best_frames),
                'session_completed': time.strftime("%Y-%m-%d %H:%M:%S"),
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
            'frames': frames_data
        }
        
        # Salva JSON su file
        json_filepath = os.path.join(self.session_dir, "best_frames_data.json")
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_result, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "session_id": self.session_id,
            "frames_count": len(best_frames),
            "best_score": best_frames[0]['score'] if best_frames else 0,
            "frames": frames_base64,
            "json_data": json_result,
            "files_saved_to": self.session_dir
        }

# Istanza globale del scorer
frame_scorer = WebSocketFrameScorer()

# === GESTIONE DEVICE IPHONE ===
# Dizionario per tracciare device iPhone connessi
connected_iphone_devices = {}

# Callback per notificare desktop di nuove connessioni iPhone
desktop_websockets = set()

# ✅ NUOVO: Set desktop che hanno premuto "Avvia Webcam" e vogliono ricevere frames
active_desktop_webcams = set()

async def broadcast_to_desktop(message):
    """Invia messaggio a tutti i client desktop connessi"""
    if desktop_websockets:
        disconnected = set()
        for ws in desktop_websockets:
            try:
                await ws.send(json.dumps(message))
            except Exception:
                disconnected.add(ws)
        desktop_websockets.difference_update(disconnected)

async def broadcast_to_active_desktops(message):
    """Invia messaggio SOLO ai desktop che hanno avviato la webcam"""
    if active_desktop_webcams:
        disconnected = set()
        for ws in active_desktop_webcams:
            try:
                await ws.send(json.dumps(message))
            except Exception:
                disconnected.add(ws)
        active_desktop_webcams.difference_update(disconnected)

async def handle_websocket(websocket):
    """Handler principale WebSocket"""
    logger.info(f"Nuova connessione WebSocket da {websocket.remote_address}")

    # Flag per tracciare se questo e' un client desktop
    is_desktop_client = False
    iphone_device_id = None

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get('action')

                # === AZIONI STANDARD (WEBCAM DESKTOP) ===
                if action == 'start_session':
                    session_id = data.get('session_id', f"session_{int(time.time())}")
                    frame_scorer.start_session(session_id)

                    # Registra come client desktop
                    is_desktop_client = True
                    desktop_websockets.add(websocket)

                    response = {
                        "action": "session_started",
                        "session_id": session_id,
                        "message": "Sessione iniziata. Invia frame con action='process_frame'"
                    }
                    await websocket.send(json.dumps(response))

                elif action == 'process_frame':
                    frame_data = data.get('frame_data')
                    if not frame_data:
                        await websocket.send(json.dumps({"error": "frame_data mancante"}))
                        continue

                    result = await frame_scorer.process_frame(frame_data)
                    result['action'] = 'frame_processed'
                    await websocket.send(json.dumps(result))

                elif action == 'get_results':
                    result = frame_scorer.get_best_frames_result()
                    result['action'] = 'results_ready'
                    # Include request_id per correlazione richiesta/risposta
                    if 'request_id' in data:
                        result['request_id'] = data['request_id']
                    await websocket.send(json.dumps(result))

                elif action == 'ping':
                    await websocket.send(json.dumps({"action": "pong", "timestamp": time.time()}))

                # === AZIONI IPHONE CAMERA ===
                elif action == 'iphone_connect':
                    # iPhone si connette per la prima volta
                    device_id = data.get('deviceId')
                    if device_id:
                        iphone_device_id = device_id
                        connected_iphone_devices[device_id] = {
                            'websocket': websocket,
                            'connected_at': time.time(),
                            'user_agent': data.get('userAgent', 'Unknown'),
                            'last_frame': None
                        }
                        logger.info(f"iPhone connesso: {device_id[:8]}...")

                        # Avvia sessione automaticamente per iPhone
                        session_id = f"iphone_{device_id[:8]}_{int(time.time())}"
                        frame_scorer.start_session(session_id)

                        # Conferma connessione all'iPhone
                        await websocket.send(json.dumps({
                            "action": "connected",
                            "deviceId": device_id,
                            "session_id": session_id,
                            "message": "Connesso al server Kimerika"
                        }))

                        # Notifica i client desktop
                        await broadcast_to_desktop({
                            "action": "iphone_connected",
                            "deviceId": device_id,
                            "deviceIdShort": device_id[:8] + "...",
                            "timestamp": time.time()
                        })

                elif action == 'iphone_frame':
                    # iPhone invia un frame
                    device_id = data.get('deviceId')
                    frame_data = data.get('frame')

                    if not frame_data:
                        await websocket.send(json.dumps({"error": "frame mancante"}))
                        continue

                    # Aggiorna timestamp ultimo frame
                    if device_id and device_id in connected_iphone_devices:
                        connected_iphone_devices[device_id]['last_frame'] = time.time()

                    # Processa il frame con lo stesso sistema usato per webcam
                    result = await frame_scorer.process_frame(frame_data)
                    result['action'] = 'frame_processed'
                    result['source'] = 'iphone'
                    result['deviceId'] = device_id

                    # Rispondi all'iPhone
                    await websocket.send(json.dumps(result))

                    # ✅ Invia frame processato SOLO ai desktop che hanno avviato webcam
                    desktop_message = {
                        "action": "iphone_frame_processed",
                        "deviceId": device_id,
                        "score": result.get('current_score', 0),
                        "faces_detected": result.get('faces_detected', 0),
                        "total_frames_collected": result.get('total_frames_collected', 0),  # ✅ Per requestBestFramesUpdate
                        "landmarks": result.get('landmarks'),  # ✅ Includi landmarks per canvas
                        "timestamp": time.time(),
                        "frame_data": frame_data  # Invia frame corrente
                    }
                    
                    await broadcast_to_active_desktops(desktop_message)

                elif action == 'iphone_disconnect':
                    # iPhone si disconnette esplicitamente
                    device_id = data.get('deviceId')
                    if device_id and device_id in connected_iphone_devices:
                        del connected_iphone_devices[device_id]
                        logger.info(f"iPhone disconnesso: {device_id[:8]}...")

                        await broadcast_to_desktop({
                            "action": "iphone_disconnected",
                            "deviceId": device_id,
                            "timestamp": time.time()
                        })

                elif action == 'register_desktop':
                    # Client desktop si registra per ricevere notifiche iPhone
                    is_desktop_client = True
                    desktop_websockets.add(websocket)

                    # Invia lista device attualmente connessi
                    connected_list = [
                        {
                            "deviceId": did,
                            "deviceIdShort": did[:8] + "...",
                            "connected_at": info['connected_at']
                        }
                        for did, info in connected_iphone_devices.items()
                    ]

                    await websocket.send(json.dumps({
                        "action": "desktop_registered",
                        "connected_iphones": connected_list
                    }))

                elif action == 'start_webcam':
                    # ✅ Desktop ha premuto "Avvia Webcam" - inizia a ricevere frames iPhone
                    is_desktop_client = True
                    desktop_websockets.add(websocket)
                    active_desktop_webcams.add(websocket)
                    logger.info(f"🎥 Desktop avviato - ora riceve frames iPhone")
                    
                    await websocket.send(json.dumps({
                        "action": "webcam_started",
                        "message": "Desktop pronto a ricevere frames iPhone"
                    }))

                elif action == 'stop_webcam':
                    # ✅ Desktop ha premuto "Ferma Webcam" - smetti di inviare frames
                    active_desktop_webcams.discard(websocket)
                    logger.info(f"⏸️ Desktop fermato - non riceve più frames iPhone")
                    
                    await websocket.send(json.dumps({
                        "action": "webcam_stopped",
                        "message": "Desktop fermato"
                    }))

                elif action == 'get_iphone_status':
                    # Desktop richiede stato iPhone
                    connected_list = [
                        {
                            "deviceId": did,
                            "deviceIdShort": did[:8] + "...",
                            "connected_at": info['connected_at'],
                            "last_frame": info.get('last_frame')
                        }
                        for did, info in connected_iphone_devices.items()
                    ]

                    await websocket.send(json.dumps({
                        "action": "iphone_status",
                        "connected_count": len(connected_iphone_devices),
                        "devices": connected_list
                    }))

                else:
                    await websocket.send(json.dumps({"error": f"Azione sconosciuta: {action}"}))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Messaggio JSON non valido"}))
            except Exception as e:
                logger.error(f"Errore handling message: {e}")
                await websocket.send(json.dumps({"error": f"Errore server: {str(e)}"}))

    except websockets.exceptions.ConnectionClosed:
        logger.info("Connessione WebSocket chiusa")
    except Exception as e:
        logger.error(f"Errore WebSocket: {e}")
    finally:
        # Cleanup alla disconnessione
        if is_desktop_client:
            desktop_websockets.discard(websocket)
            active_desktop_webcams.discard(websocket)  # ✅ Rimuovi anche da active

        if iphone_device_id and iphone_device_id in connected_iphone_devices:
            del connected_iphone_devices[iphone_device_id]
            logger.info(f"iPhone rimosso (disconnessione): {iphone_device_id[:8]}...")
            await broadcast_to_desktop({
                "action": "iphone_disconnected",
                "deviceId": iphone_device_id,
                "timestamp": time.time()
            })

async def main():
    """Avvia il server WebSocket"""
    host = "0.0.0.0"  # Ascolta su tutte le interfacce di rete
    port = 8765
    
    logger.info(f"Avvio server WebSocket su {host}:{port}")
    logger.info("Protocollo supportato:")
    logger.info("1. Invia: {'action': 'start_session', 'session_id': 'optional_id'}")
    logger.info("2. Invia frame: {'action': 'process_frame', 'frame_data': 'base64_encoded_image'}")
    logger.info("3. Ottieni risultati: {'action': 'get_results'}")
    
    async with websockets.serve(handle_websocket, host, port):
        await asyncio.Future()  # Mantiene il server in esecuzione

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server fermato dall'utente")