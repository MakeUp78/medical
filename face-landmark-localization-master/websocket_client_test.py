#!/usr/bin/env python3
"""
Client di esempio per testare l'API WebSocket
Simula l'invio di frame dalla webcam
"""

import asyncio
import websockets
import json
import base64
import cv2
import numpy as np
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_webcam_client():
    """Client di test che usa la webcam per inviare frame"""
    
    # Connetti al server WebSocket
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("Connesso al server WebSocket")
            
            # 1. Avvia una nuova sessione
            start_message = {
                "action": "start_session",
                "session_id": f"test_session_{int(time.time())}"
            }
            await websocket.send(json.dumps(start_message))
            response = await websocket.recv()
            session_info = json.loads(response)
            logger.info(f"Sessione avviata: {session_info}")
            
            # 2. Inizializza webcam
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logger.error("Impossibile aprire la webcam")
                return
            
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            frame_count = 0
            max_frames = 50  # Invia solo 50 frame per test
            
            logger.info(f"Inizio invio frame (max {max_frames})...")
            logger.info("Premi 'q' nella finestra video per terminare")
            
            try:
                while frame_count < max_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    frame_count += 1
                    
                    # Converti frame in base64
                    _, buffer = cv2.imencode('.jpg', frame)
                    frame_b64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # Invia frame al server
                    frame_message = {
                        "action": "process_frame",
                        "frame_data": frame_b64
                    }
                    
                    await websocket.send(json.dumps(frame_message))
                    
                    # Ricevi risposta
                    response = await websocket.recv()
                    result = json.loads(response)
                    
                    if result.get('faces_detected', 0) > 0:
                        score = result.get('current_score', 0)
                        pose = result.get('pose', {})
                        logger.info(f"Frame {frame_count}: Score={score:.1f}, Pitch={pose.get('pitch', 0):.1f}°, Yaw={pose.get('yaw', 0):.1f}°")
                        
                        # Aggiungi info sul frame
                        cv2.putText(frame, f"Frame: {frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                        cv2.putText(frame, f"Score: {score:.1f}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        cv2.putText(frame, f"Total: {result.get('total_frames_collected', 0)}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    else:
                        cv2.putText(frame, f"Frame: {frame_count} (No Face)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                    # Mostra frame
                    cv2.imshow('WebSocket Client - Sending Frames', frame)
                    
                    # Controlla se premuto 'q'
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                    
                    # Pausa per non sovraccaricare il server
                    await asyncio.sleep(0.1)
                
            finally:
                cap.release()
                cv2.destroyAllWindows()
            
            # 3. Richiedi i risultati finali
            logger.info("Richiesta risultati finali...")
            results_message = {"action": "get_results"}
            await websocket.send(json.dumps(results_message))
            
            response = await websocket.recv()
            results = json.loads(response)
            
            if results.get('success'):
                logger.info(f"✅ Risultati ricevuti:")
                logger.info(f"   - Frame processati: {results['json_data']['metadata']['total_frames_processed']}")
                logger.info(f"   - Migliori frame: {results['frames_count']}")
                logger.info(f"   - Miglior punteggio: {results['best_score']:.2f}")
                logger.info(f"   - File salvati in: {results['files_saved_to']}")
                
                # Salva anche i risultati localmente per il client
                with open(f"client_results_{session_info['session_id']}.json", 'w') as f:
                    json.dump(results['json_data'], f, indent=2, ensure_ascii=False)
                
                logger.info(f"   - JSON salvato localmente: client_results_{session_info['session_id']}.json")
            else:
                logger.error(f"❌ Errore nei risultati: {results.get('error', 'Sconosciuto')}")
    
    except websockets.exceptions.ConnectionRefused:
        logger.error("❌ Impossibile connettersi al server. Assicurati che sia in esecuzione su ws://localhost:8765")
    except Exception as e:
        logger.error(f"❌ Errore client: {e}")

async def test_static_images_client():
    """Client di test che invia immagini statiche"""
    
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("Connesso al server WebSocket (test immagini statiche)")
            
            # Avvia sessione
            start_message = {
                "action": "start_session", 
                "session_id": "static_test_session"
            }
            await websocket.send(json.dumps(start_message))
            response = await websocket.recv()
            logger.info(f"Sessione avviata: {json.loads(response)}")
            
            # Crea alcune immagini di test (simulano frame diversi)
            test_images = []
            for i in range(10):
                # Crea immagine di test
                img = cv2.imread("test_image.jpg")  # Sostituisci con un'immagine reale
                if img is None:
                    # Crea immagine vuota se non trova file
                    img = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(img, f"Test Frame {i+1}", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                _, buffer = cv2.imencode('.jpg', img)
                frame_b64 = base64.b64encode(buffer).decode('utf-8')
                test_images.append(frame_b64)
            
            # Invia immagini
            for i, frame_b64 in enumerate(test_images):
                message = {
                    "action": "process_frame",
                    "frame_data": frame_b64
                }
                await websocket.send(json.dumps(message))
                
                response = await websocket.recv()
                result = json.loads(response)
                logger.info(f"Immagine {i+1}: {result}")
                
                await asyncio.sleep(0.5)
            
            # Ottieni risultati
            await websocket.send(json.dumps({"action": "get_results"}))
            response = await websocket.recv()
            results = json.loads(response)
            logger.info(f"Risultati finali: {results}")
            
    except Exception as e:
        logger.error(f"Errore test statico: {e}")

if __name__ == "__main__":
    import sys
    
    print("🎯 Client di test per WebSocket Frame API")
    print("1. Test con webcam (default)")
    print("2. Test con immagini statiche")
    
    choice = input("Scegli test (1/2): ").strip()
    
    if choice == "2":
        logger.info("Avvio test con immagini statiche...")
        asyncio.run(test_static_images_client())
    else:
        logger.info("Avvio test con webcam...")
        asyncio.run(test_webcam_client())