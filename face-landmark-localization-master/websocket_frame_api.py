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
import sys

# Configurazione logging: usa stdout (già unbuffered con python3 -u)
# così i log vengono scritti immediatamente senza buffering su stderr
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
    force=True
)
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
        # static_image_mode=True: tratta ogni frame come immagine indipendente
        # (non come video-stream). Essenziale perché riceve JPEG indipendenti via WebSocket.
        # Con False, se il 1° frame non rileva il volto, il tracking fallisce su tutti.
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
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
        """Calcola pitch/yaw/roll direttamente dalla geometria 2D dei landmark.

        Approccio landmark-geometrico puro, senza solvePnP né modelli 3D.
        Produce valori ≈ 0° per un viso frontale per costruzione geometrica.

        Convenzione angoli output (tutti in gradi):
          yaw   > 0  → viso gira a destra (camera)  → utente deve girare a SINISTRA
          yaw   < 0  → viso gira a sinistra          → utente deve girare a DESTRA
          pitch > 0  → testa alzata (mento su)       → utente deve ABBASSARE il mento
          pitch < 0  → testa abbassata               → utente deve ALZARE il mento
          roll  > 0  → testa inclinata a destra      → raddrizzare a sinistra
          roll  < 0  → testa inclinata a sinistra    → raddrizzare a destra
        """
        try:
            if len(landmarks_array) < 468:
                return np.array([0.0, 0.0, 0.0])

            # ── Indici MediaPipe Face Mesh ─────────────────────────────────────
            # Occhi: centri approssimati come media degli angoli interni+esterni
            L_EYE_OUTER  = 33;   L_EYE_INNER  = 133
            R_EYE_OUTER  = 263;  R_EYE_INNER  = 362
            NOSE_TIP     = 4
            # Punto nasion (radice del naso tra gli occhi, stabile per pitch/yaw)
            NOSE_BRIDGE  = 6
            CHIN         = 152
            L_CHEEK      = 234   # punto laterale guancia sinistra (dal punto di vista camera)
            R_CHEEK      = 454   # punto laterale guancia destra

            lm = landmarks_array

            # Centri occhi
            l_eye = (lm[L_EYE_OUTER] + lm[L_EYE_INNER]) * 0.5
            r_eye = (lm[R_EYE_OUTER] + lm[R_EYE_INNER]) * 0.5
            eye_mid = (l_eye + r_eye) * 0.5          # punto medio tra gli occhi

            nose  = lm[NOSE_TIP]
            bridge= lm[NOSE_BRIDGE]
            chin  = lm[CHIN]
            l_cheek = lm[L_CHEEK]
            r_cheek = lm[R_CHEEK]

            # ── ROLL: angolo della linea degli occhi rispetto all'orizzontale ──
            # roll > 0: occhio sinistro (sx camera) più in alto → testa inclinata a destra
            dx = r_eye[0] - l_eye[0]
            dy = r_eye[1] - l_eye[1]
            roll_deg = np.degrees(np.arctan2(dy, dx))
            # roll_deg ≈ 0° per occhi orizzontali; piccole deviazioni → piccoli angoli

            # ── YAW: asimmetria orizzontale del viso ─────────────────────────
            # Distanza naso dagli angoli laterali delle guance.
            # Per viso frontale: dist_left ≈ dist_right.
            # Per viso girato a destra (camera): l_cheek più vicino al naso.
            dist_left  = nose[0] - l_cheek[0]   # positivo se naso è a destra della guancia sx
            dist_right = r_cheek[0] - nose[0]   # positivo se guancia dx è a destra del naso
            total_width = dist_left + dist_right

            if total_width > 1e-3:
                # asimmetria normalizzata in [-1, +1]: 0 = frontale
                # se dist_right < dist_left → viso girato a sinistra → yaw < 0
                asym = (dist_right - dist_left) / total_width
                # scala a gradi: asym=1 → ~45°, usiamo arcsin per rispettare la geometria
                yaw_deg = float(np.degrees(np.arcsin(np.clip(asym * 0.95, -0.95, 0.95))))
            else:
                yaw_deg = 0.0

            # ── PITCH: posizione verticale del naso rispetto alla linea occhi-mento ─
            # Per viso frontale: il naso è a metà tra occhi e mento.
            # pitch > 0 (testa alzata): il naso si avvicina agli occhi (chin va su in immagine Y-down)
            eye_y  = eye_mid[1]
            chin_y = chin[1]
            nose_y = nose[1]
            face_height = chin_y - eye_y

            if face_height > 1e-3:
                # rapporto dove si trova il naso [0=occhi, 1=mento].
                # 0.46: posa calibrata con mento leggermente alzato rispetto alla verticale
                # (valore abbassato da 0.55 → meno penalità per postura naturale della testa)
                FRONTAL_NOSE_RATIO = 0.46
                nose_ratio = (nose_y - eye_y) / face_height
                deviation = (nose_ratio - FRONTAL_NOSE_RATIO) / FRONTAL_NOSE_RATIO
                pitch_deg = float(np.degrees(np.arcsin(np.clip(-deviation * 0.85, -0.85, 0.85))))
            else:
                pitch_deg = 0.0

            logger.debug(f"Pose geo: P={pitch_deg:.1f}° Y={yaw_deg:.1f}° R={roll_deg:.1f}°")
            return np.array([pitch_deg, yaw_deg, roll_deg])

        except Exception as e:
            logger.error(f"Errore nel calcolo pose: {e}")
            return np.array([0.0, 0.0, 0.0])
    
    def calculate_face_score(self, pitch, yaw, roll, face_bbox, frame_width, frame_height):
        """Sistema di scoring a 3 parametri ottimizzato"""
        
        # 1. POSE SCORE (0-100) - 60% del punteggio
        # YAW e PITCH hanno peso UGUALE per bilanciare frontalità verticale/orizzontale
        
        # Normalizza Roll a range [-90, 90] (wrap semplice, niente inversione ±180°)
        normalized_roll = roll % 360
        if normalized_roll > 180:
            normalized_roll -= 360
        if normalized_roll > 90:
            normalized_roll = 180 - normalized_roll
        elif normalized_roll < -90:
            normalized_roll = -180 - normalized_roll
        
        roll_weighted = abs(normalized_roll) * 0.3

        # Pesi PRIORITÀ YAW: Yaw ha peso maggiore per privilegiare frontalità orizzontale
        yaw_weighted = abs(yaw) * 2.5
        pitch_weighted = abs(pitch) * 1.0

        # BIAS: Penalità extra per Yaw fuori dalla soglia ottimale [-3, +3]
        yaw_penalty = 0
        if abs(yaw) > 3:
            # Penalità progressiva: ogni grado oltre ±3 costa 5 punti
            yaw_penalty = (abs(yaw) - 3) * 5

        pose_deviation = yaw_weighted + pitch_weighted + roll_weighted
        pose_score = max(0, 100 - pose_deviation * 0.8 - yaw_penalty)
        
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

            # ── RESIZE PER MEDIAPIPE ──────────────────────────────────────────
            # MediaPipe è ottimizzato per immagini ~640px: su frame ad alta
            # risoluzione (>1280px) il calcolo diventa molto lento senza
            # alcun guadagno di accuratezza. Facciamo il resize SOLO per
            # il rilevamento; conserviamo il frame originale per la restituzione.
            MEDIAPIPE_MAX_DIM = 640
            if max(h, w) > MEDIAPIPE_MAX_DIM:
                scale = MEDIAPIPE_MAX_DIM / max(h, w)
                mp_w = int(w * scale)
                mp_h = int(h * scale)
                mp_frame = cv2.resize(frame, (mp_w, mp_h), interpolation=cv2.INTER_AREA)
            else:
                mp_frame = frame
                mp_w, mp_h = w, h
            # ─────────────────────────────────────────────────────────────────

            # Processa con MediaPipe sul frame ridotto
            rgb_frame = cv2.cvtColor(mp_frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)

            faces_found = len(results.multi_face_landmarks) if results.multi_face_landmarks else 0
            logger.info(f"[FRAME #{current_frame_number:04d}] orig={w}x{h} mp={mp_w}x{mp_h} volti={faces_found}")
            
            response = {
                "frame_processed": True,
                "faces_detected": 0,
                "current_score": 0.0,
                "total_frames_collected": len(self.best_frames)
            }
            
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    # Estrai landmark usando le dimensioni del frame ridotto (per MediaPipe)
                    all_landmarks = self.get_all_mediapipe_landmarks(face_landmarks, mp_w, mp_h)

                    if len(all_landmarks) >= 6:
                        # Calcola bounding box nel frame ridotto
                        valid_x = [x for x in all_landmarks[:, 0] if x > 0]
                        valid_y = [y for y in all_landmarks[:, 1] if y > 0]

                        if valid_x and valid_y:
                            x_min, x_max = min(valid_x), max(valid_x)
                            y_min, y_max = min(valid_y), max(valid_y)

                            margin = 30
                            bbox = [
                                max(0, x_min-margin), min(mp_w, x_max+margin),
                                max(0, y_min-margin), min(mp_h, y_max+margin)
                            ]

                            # Calcola pose usando il frame ridotto
                            head_pose = self.calculate_head_pose_from_mediapipe(all_landmarks, mp_w, mp_h)

                            # Score calcolato rispetto al frame ridotto (le proporzioni sono identiche)
                            score, score_details = self.calculate_face_score(
                                head_pose[0], head_pose[1], head_pose[2], bbox, mp_w, mp_h
                            )
                            
                            # ✅ FILTRO: Scarta solo Yaw/Pitch invalidi (>170°)
                            # Roll>170° è gestito con normalizzazione (inversione asse)
                            is_invalid = (abs(head_pose[0]) > 170 or  # Pitch invalido
                                         abs(head_pose[1]) > 170)      # Yaw invalido
                            
                            if is_invalid:
                                logger.info(
                                    f"[FRAME #{current_frame_number:04d}] INVALIDO "
                                    f"P={head_pose[0]:.1f}° Y={head_pose[1]:.1f}° R={head_pose[2]:.1f}°"
                                )
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
                            # Frame con |yaw|<8° E |pitch|<8° bypassano la soglia (frontalità prioritaria)
                            is_excellent = score >= 95
                            is_frontal_pose = (abs(head_pose[1]) < 8 and abs(head_pose[0]) < 8)
                            
                            reason = "" 
                            if is_excellent:       reason = "EXCELLENT(>=95)"
                            elif is_frontal_pose:  reason = "FRONTAL(|yaw|<8,|pitch|<8)"
                            elif score >= self.min_score_threshold: reason = "SCORE_OK"

                            if len(self.best_frames) < self.buffer_size:
                                # Buffer non pieno - aggiungi se supera soglia minima
                                if reason:
                                    self.best_frames.append(frame_data)
                                    self.frames_added += 1
                                    logger.info(
                                        f"[FRAME #{current_frame_number:04d}] ACCETTATO({reason}) "
                                        f"score={score:.1f} pose_s={score_details['pose_score']:.1f} "
                                        f"size_s={score_details['size_score']:.1f} "
                                        f"P={head_pose[0]:.1f}° Y={head_pose[1]:.1f}° R={head_pose[2]:.1f}° "
                                        f"buf={len(self.best_frames)}/{self.buffer_size} thr={self.min_score_threshold:.1f}"
                                    )
                                    # Riordina e aggiorna soglia quando raggiungi buffer_size
                                    if len(self.best_frames) == self.buffer_size:
                                        self.best_frames.sort(key=lambda x: x['score'], reverse=True)
                                        self.min_score_threshold = max(50, self.best_frames[-1]['score'])
                                        logger.info(f"[BUFFER PIENO] soglia aggiornata → {self.min_score_threshold:.1f}")
                                else:
                                    logger.info(
                                        f"[FRAME #{current_frame_number:04d}] SCARTATO "
                                        f"score={score:.1f} < thr={self.min_score_threshold:.1f} "
                                        f"P={head_pose[0]:.1f}° Y={head_pose[1]:.1f}° R={head_pose[2]:.1f}°"
                                    )
                            elif reason:
                                # Buffer pieno - sostituisci il peggiore se questo è migliore O se è eccellente/frontale
                                logger.info(
                                    f"[FRAME #{current_frame_number:04d}] SOSTITUZIONE({reason}) "
                                    f"score={score:.1f} pose_s={score_details['pose_score']:.1f} "
                                    f"size_s={score_details['size_score']:.1f} "
                                    f"P={head_pose[0]:.1f}° Y={head_pose[1]:.1f}° R={head_pose[2]:.1f}°"
                                )
                                self.best_frames[-1] = frame_data
                                self.frames_added += 1
                                
                                # Riordina e aggiorna soglia
                                self.best_frames.sort(key=lambda x: x['score'], reverse=True)
                                self.min_score_threshold = max(50, self.best_frames[-1]['score'])
                            else:
                                logger.info(
                                    f"[FRAME #{current_frame_number:04d}] SCARTATO "
                                    f"score={score:.1f} < thr={self.min_score_threshold:.1f} "
                                    f"P={head_pose[0]:.1f}° Y={head_pose[1]:.1f}° R={head_pose[2]:.1f}°"
                                )
                            
                            # Roll già in range naturale dall'approccio geometrico
                            normalized_roll_display = head_pose[2]

                            # ── LANDMARK COMPATTI PER OVERLAY LIVE ───────────────────────
                            # Inviamo i landmark normalizzati [0,1] come lista flat [x0,y0,x1,y1,...]
                            # Solo i punti necessari al rendering: contorno viso, occhi, naso, bocca.
                            # Gruppi: OVAL(36), L_EYE(16), R_EYE(16), NOSE(9), L_BROW(10), R_BROW(10)
                            LM_GROUPS = {
                                # Oval: contorno viso sinistro→alto→destro→basso
                                'oval': [10,338,297,332,284,251,389,356,454,323,361,288,
                                         397,365,379,378,400,377,152,148,176,149,150,136,
                                         172,58,132,93,234,127,162,21,54,103,67,109],
                                # Occhio sinistro (esterno → interno)
                                'l_eye': [33,7,163,144,145,153,154,155,133,173,157,158,159,160,161,246],
                                # Occhio destro
                                'r_eye': [362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398],
                                # Naso (ponte + punta + narici)
                                'nose': [168,6,197,195,5,4,45,220,115,48],
                                # Sopracciglio sinistro
                                'l_brow': [276,283,282,295,285,300,293,334,296,336],
                                # Sopracciglio destro
                                'r_brow': [46,53,52,65,55,70,63,105,66,107],
                                # Bocca (labbro esterno)
                                'mouth': [61,146,91,181,84,17,314,405,321,375,291,
                                          308,324,318,402,317,14,87,178,88,95],
                            }
                            lm_out = {}
                            for group, indices in LM_GROUPS.items():
                                coords = []
                                for idx in indices:
                                    if idx < len(face_landmarks.landmark):
                                        lm = face_landmarks.landmark[idx]
                                        coords.append(round(lm.x, 4))
                                        coords.append(round(lm.y, 4))
                                lm_out[group] = coords
                            # ─────────────────────────────────────────────────────────────

                            response.update({
                                "faces_detected": 1,
                                "current_score": round(score, 2),
                                "pose": {
                                    "pitch": round(head_pose[0], 2),
                                    "yaw": round(head_pose[1], 2),
                                    "roll": round(normalized_roll_display, 2)
                                },
                                "score_breakdown": {
                                    "pose_score": round(score_details['pose_score'], 2),
                                    "size_score": round(score_details['size_score'], 2),
                                    "position_score": round(score_details['position_score'], 2),
                                    "face_ratio": round(score_details['face_ratio'], 4)
                                },
                                "landmarks": lm_out
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
            # Salva frame come immagine (qualità 97 per massima fedeltà - vicino a successo.jpg)
            filename = f"frame_{i+1:02d}.jpg"
            filepath = os.path.join(self.session_dir, filename)
            cv2.imwrite(filepath, frame_data['frame'], [cv2.IMWRITE_JPEG_QUALITY, 97])
            
            # Converti frame in base64 per la risposta (qualità 97 per preservare dettagli LB/RB)
            _, buffer = cv2.imencode('.jpg', frame_data['frame'], [cv2.IMWRITE_JPEG_QUALITY, 97])
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            frames_base64.append({
                'filename': filename,
                'data': frame_b64,
                'rank': frame_data.get('frame_number', i + 1),  # Usa frame_number originale
                'score': round(frame_data['score'], 2)
            })
            
            # Prepara dati JSON
            json_data = {
                'filename': filename,
                'rank': frame_data.get('frame_number', i + 1),
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
            frames_data.append(json_data)
        
        # ── RIEPILGO TOP-10 SU LOG ──────────────────────────────────────────────
        logger.info("=" * 72)
        logger.info(f"TOP-{len(best_frames)} FRAMES SELEZIONATI (sessione {self.session_id})")
        logger.info(f"{'Rank':>4}  {'Frame':>6}  {'Score':>6}  {'Pose':>5}  {'Size':>5}  {'Pos':>5}  {'Pitch':>7}  {'Yaw':>7}  {'Roll':>7}")
        logger.info("-" * 72)
        for i, fd in enumerate(best_frames):
            sd = fd['score_details']
            logger.info(
                f"{i+1:>4}  #{fd.get('frame_number',i+1):>5}  "
                f"{fd['score']:>6.2f}  {sd['pose_score']:>5.1f}  "
                f"{sd['size_score']:>5.1f}  {sd['position_score']:>5.1f}  "
                f"{fd['pitch']:>+7.2f}°  {fd['yaw']:>+7.2f}°  {fd['roll']:>+7.2f}°"
            )
        logger.info("=" * 72)
        # ────────────────────────────────────────────────────────────────────────

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
                    # Propaga il flag final per consentire al client di forzare l'aggiornamento canvas
                    if data.get('final'):
                        result['is_final'] = True
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
                        "current_score": result.get('current_score', 0),  # alias per compatibilità con updateFrameProcessingStats
                        "faces_detected": result.get('faces_detected', 0),
                        "total_frames_collected": result.get('total_frames_collected', 0),
                        "landmarks": result.get('landmarks'),
                        "pose": result.get('pose'),               # ✅ Overlay inclinazione testa nel fullscreen
                        "score_breakdown": result.get('score_breakdown'),  # ✅ Dettagli punteggio live
                        "timestamp": time.time(),
                        "frame_data": frame_data
                    }
                    
                    await broadcast_to_active_desktops(desktop_message)

                elif action == 'iphone_disconnect':
                    # iPhone si disconnette esplicitamente
                    device_id = data.get('deviceId')
                    if device_id and device_id in connected_iphone_devices:
                        del connected_iphone_devices[device_id]
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
                    is_desktop_client = True
                    desktop_websockets.add(websocket)
                    active_desktop_webcams.add(websocket)
                    await websocket.send(json.dumps({
                        "action": "webcam_started",
                        "message": "Desktop pronto a ricevere frames iPhone"
                    }))

                elif action == 'stop_webcam':
                    active_desktop_webcams.discard(websocket)
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
            except websockets.exceptions.ConnectionClosed:
                # Client ha chiuso la connessione durante il processing — normale fine sessione
                break
            except Exception as e:
                logger.error(f"Errore handling message: {e}")
                try:
                    await websocket.send(json.dumps({"error": f"Errore server: {str(e)}"}))
                except websockets.exceptions.ConnectionClosed:
                    break

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        logger.error(f"Errore WebSocket: {e}")
    finally:
        if is_desktop_client:
            desktop_websockets.discard(websocket)
            active_desktop_webcams.discard(websocket)

        if iphone_device_id and iphone_device_id in connected_iphone_devices:
            del connected_iphone_devices[iphone_device_id]
            await broadcast_to_desktop({
                "action": "iphone_disconnected",
                "deviceId": iphone_device_id,
                "timestamp": time.time()
            })

async def main():
    """Avvia il server WebSocket"""
    host = "0.0.0.0"
    port = 8765
    logger.info(f"WebSocket server avviato su {host}:{port}")
    async with websockets.serve(handle_websocket, host, port):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass