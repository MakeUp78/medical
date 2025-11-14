# 🎯 WebSocket Frame Analysis API

API WebSocket per l'analisi in tempo reale di frame ricevuti dal client. Basata su `landmarkPredict_webcam_enhanced.py` con sistema di scoring ottimizzato.

## 🚀 Caratteristiche

- **WebSocket Real-time**: Riceve frame dal client via WebSocket
- **Sistema di Scoring a 3 parametri**:
  - 🎯 **POSE (60%)**: Qualità frontale (pitch, yaw, roll)
  - 📏 **SIZE (30%)**: Premia volti più grandi (30-45% del frame)
  - 📍 **POSITION (10%)**: Centramento completo nel frame
- **Ritorna i migliori 10 frame** con punteggi e JSON dettagliato
- **Salvataggio automatico** di frame e dati

## 📁 File Inclusi

```
face-landmark-localization-master/
├── websocket_frame_api.py          # Server WebSocket API principale
├── websocket_client_test.py        # Client di test Python (webcam)
├── websocket_client.html           # Client web browser
├── websocket_requirements.txt      # Dipendenze aggiuntive
└── README_WEBSOCKET_API.md         # Questa documentazione
```

## 🛠️ Installazione

1. **Installa dipendenze**:
```bash
pip install websockets opencv-python mediapipe numpy
```

2. **Avvia il server**:
```bash
python face-landmark-localization-master/websocket_frame_api.py
```

Il server si avvierà su `ws://localhost:8765`

## 📡 Protocollo WebSocket

### 1. Avvia Sessione
```json
{
    "action": "start_session",
    "session_id": "optional_custom_id"
}
```

**Risposta**:
```json
{
    "action": "session_started",
    "session_id": "session_12345",
    "message": "Sessione iniziata..."
}
```

### 2. Invia Frame
```json
{
    "action": "process_frame",
    "frame_data": "base64_encoded_jpeg_image"
}
```

**Risposta**:
```json
{
    "action": "frame_processed",
    "frame_processed": true,
    "faces_detected": 1,
    "current_score": 87.5,
    "total_frames_collected": 25,
    "pose": {
        "pitch": -2.1,
        "yaw": 1.5,
        "roll": 178.2
    },
    "score_breakdown": {
        "pose_score": 94.2,
        "size_score": 85.3,
        "position_score": 92.1
    }
}
```

### 3. Ottieni Risultati
```json
{
    "action": "get_results"
}
```

**Risposta**:
```json
{
    "action": "results_ready",
    "success": true,
    "session_id": "session_12345",
    "frames_count": 10,
    "best_score": 96.8,
    "frames": [
        {
            "filename": "frame_01.jpg",
            "data": "base64_encoded_image",
            "rank": 1,
            "score": 96.8
        }
        // ... altri 9 frame
    ],
    "json_data": {
        "metadata": {
            "session_id": "session_12345",
            "total_frames_processed": 150,
            "best_frames_saved": 10,
            "scoring_criteria": {
                "pose_weight": 0.6,
                "size_weight": 0.3,
                "position_weight": 0.1
            }
        },
        "frames": [
            // Dettagli completi di ogni frame...
        ]
    },
    "files_saved_to": "websocket_best_frames/session_12345"
}
```

## 🧪 Test dell'API

### Opzione 1: Client Python con Webcam
```bash
python face-landmark-localization-master/websocket_client_test.py
```

### Opzione 2: Client Web Browser
1. Apri `websocket_client.html` nel browser
2. Clicca "Avvia Sessione"
3. Permetti l'accesso alla webcam
4. Osserva il processing in real-time
5. Clicca "Ottieni Risultati" per vedere i migliori frame

### Opzione 3: Client Personalizzato

```python
import asyncio
import websockets
import json
import base64
import cv2

async def custom_client():
    uri = "ws://localhost:8765"
    
    async with websockets.connect(uri) as websocket:
        # 1. Avvia sessione
        await websocket.send(json.dumps({
            "action": "start_session",
            "session_id": "my_session"
        }))
        
        # 2. Invia frame
        # ... (converti immagine in base64)
        await websocket.send(json.dumps({
            "action": "process_frame", 
            "frame_data": frame_base64
        }))
        
        # 3. Ricevi risultati
        response = await websocket.recv()
        data = json.loads(response)
        
        # 4. Ottieni frame finali
        await websocket.send(json.dumps({"action": "get_results"}))

asyncio.run(custom_client())
```

## 📊 Sistema di Scoring

### Criteri di Valutazione:

1. **POSE (60% del punteggio)**:
   - Valuta pitch, yaw, roll
   - Range ottimale: tutti vicini a 0°
   - Penalizza pose non frontali

2. **SIZE (30% del punteggio)**:
   - Range ottimale: 30-45% del frame
   - Premia volti più grandi
   - Penalizza volti troppo piccoli

3. **POSITION (10% del punteggio)**:
   - Valuta distanza dal centro del frame
   - Considera sia X che Y
   - Premia centramento perfetto

### Punteggi:
- **90-100**: 🌟 Eccellente
- **80-90**: ✅ Ottimo
- **70-80**: 👍 Buono
- **60-70**: ⚠️ Discreto
- **<60**: ❌ Scadente

## 📂 Output

Per ogni sessione viene creata una cartella:
```
websocket_best_frames/
└── session_12345/
    ├── frame_01.jpg          # Miglior frame
    ├── frame_02.jpg          # Secondo migliore
    ├── ...
    ├── frame_10.jpg          # Decimo migliore
    └── best_frames_data.json # Dati completi
```

## 🔧 Personalizzazioni

### Modifica Criteri di Scoring
Modifica i pesi in `websocket_frame_api.py`:
```python
total_score = (pose_score * 0.6 +    # Cambia questi valori
              size_score * 0.3 + 
              position_score * 0.1)
```

### Modifica Range Dimensioni Volti
Modifica in `calculate_face_score()`:
```python
if face_ratio >= 0.30:  # Cambia soglie
    if face_ratio <= 0.45:  # Range ottimale
```

### Cambia Numero Frame Salvati
```python
frame_scorer = WebSocketFrameScorer(max_frames=15)  # Invece di 10
```

## 🐛 Troubleshooting

### Server non si avvia
- Verifica che la porta 8765 sia libera
- Controlla dipendenze installate

### Client non si connette
- Assicurati che il server sia in esecuzione
- Verifica URL: `ws://localhost:8765`

### Webcam non funziona nel browser
- Usa HTTPS o localhost
- Permetti accesso webcam

### Frame non processati
- Verifica formato base64 corretto
- Controlla che l'immagine sia JPG valida

## 📈 Performance

- **Throughput**: ~5-10 FPS con elaborazione completa
- **Latenza**: <100ms per frame processing
- **Memoria**: ~50MB per sessione tipica
- **CPU**: Dipende da MediaPipe (raccomandato: 4+ core)

## 🎯 Vantaggi vs Versione Webcam

✅ **Flessibilità**: Ricevi frame da qualsiasi sorgente  
✅ **Scalabilità**: Multipli client simultanei  
✅ **Integrazione**: Facile integrazione web/mobile  
✅ **Controllo**: Controllo completo su quando/cosa inviare  
✅ **Distribuzione**: Client e server separati  

---

**Creato da**: Sistema di analisi frame basato su MediaPipe  
**Versione**: 1.0 - Novembre 2025