# Implementazione Camera iPhone via Browser per Analisi Simmetrie Facciali

## Obiettivo
Sostituire IRIUN con una soluzione browser-based che permetta di usare la camera dell'iPhone per analisi di simmetrie facciali tramite WebSocket, con configurazione persistente e accesso rapido.

---

## Requisiti Tecnici

### Lato Server (Python/Flask)
- Flask con SocketIO per WebSocket
- Libreria `qrcode[pil]` per generazione QR code
- Server accessibile in rete locale

### Lato Client (iPhone)
- Browser Safari o Chrome
- Connessione WiFi alla stessa rete del server
- iOS 11+ (supporto getUserMedia API)

### Protocolli
- **Locale**: HTTP + WS (WebSocket non sicuro)
- **Online**: HTTPS + WSS (WebSocket sicuro) - obbligatorio per getUserMedia

---

## Architettura della Soluzione

### Flusso Prima Connessione
1. Webapp desktop mostra QR code con URL camera
2. Utente scansiona QR con iPhone
3. Si apre pagina camera nel browser
4. Richiesta permesso accesso camera iOS
5. Generazione device ID univoco salvato in localStorage
6. Connessione WebSocket con device ID
7. Stream frame camera → Server
8. Prompt "Aggiungi a Home" per accesso rapido

### Flusso Connessioni Successive
1. Tap icona dalla home iPhone
2. Apertura webapp in modalità standalone
3. Lettura configurazione da localStorage
4. Connessione automatica WebSocket
5. Stream attivo in ~1 secondo

---

## Implementazione Backend

### 1. Installazione dipendenze

```bash
pip install qrcode[pil] flask-socketio
```

### 2. Generazione QR Code

```python
import qrcode
import socket
import io
from flask import Flask, render_template, send_file, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Ottieni IP locale del server
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

# Route per QR code dinamico
@app.route('/qrcode.png')
def generate_qr():
    port = request.host.split(':')[1] if ':' in request.host else '5000'
    camera_url = f"http://{get_local_ip()}:{port}/camera"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(camera_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png')

# Pagina desktop con QR code
@app.route('/')
def index():
    port = request.host.split(':')[1] if ':' in request.host else '5000'
    camera_url = f"http://{get_local_ip()}:{port}/camera"
    return render_template('index.html', camera_url=camera_url)

# Pagina camera per iPhone
@app.route('/camera')
def camera():
    return render_template('camera.html')
```

### 3. Gestione WebSocket e Device

```python
# Dizionario device connessi
connected_devices = {}

@socketio.on('connect')
def handle_connect():
    device_id = request.args.get('device')
    if device_id:
        connected_devices[device_id] = request.sid
        print(f"Device {device_id} connesso - SID: {request.sid}")
        emit('connected', {'deviceId': device_id})

@socketio.on('disconnect')
def handle_disconnect():
    # Rimuovi device disconnesso
    for device_id, sid in list(connected_devices.items()):
        if sid == request.sid:
            del connected_devices[device_id]
            print(f"Device {device_id} disconnesso")
            break

@socketio.on('video_frame')
def handle_video_frame(data):
    """Riceve frame video da iPhone"""
    device_id = data.get('deviceId')
    frame_data = data.get('frame')  # Base64 encoded image
    
    # TODO: Processa frame con MediaPipe/OpenCV per analisi simmetrie
    # frame_bytes = base64.b64decode(frame_data)
    # analizza_simmetrie(frame_bytes)
    
    # Rimanda risultati al device o alla dashboard
    emit('analysis_result', {'landmarks': [], 'symmetry_score': 0.95})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

---

## Implementazione Frontend

### 1. Template Desktop (templates/index.html)

```html
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dermamente - Analisi Simmetrie Facciali</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 800px;
            margin: 50px auto;
            text-align: center;
            padding: 20px;
        }
        .qr-container {
            background: #f5f5f5;
            padding: 30px;
            border-radius: 12px;
            margin: 30px 0;
        }
        .qr-container img {
            max-width: 300px;
            margin: 20px 0;
        }
        .url-display {
            background: white;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
            margin-top: 20px;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <h1>🎯 Analisi Simmetrie Facciali</h1>
    
    <div class="qr-container">
        <h2>Connetti iPhone</h2>
        <p>Scansiona il QR code con la fotocamera del tuo iPhone:</p>
        <img src="/qrcode.png" alt="QR Code per connessione camera">
        <div class="url-display">{{ camera_url }}</div>
        <p style="color: #666; font-size: 14px; margin-top: 20px;">
            ℹ️ Assicurati che iPhone e PC siano sulla stessa rete WiFi
        </p>
    </div>
    
    <div id="status">
        <p>In attesa di connessione...</p>
    </div>
    
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const socket = io();
        
        socket.on('connected', (data) => {
            document.getElementById('status').innerHTML = 
                `<p style="color: green;">✅ Device ${data.deviceId.substring(0, 8)}... connesso</p>`;
        });
        
        socket.on('analysis_result', (data) => {
            console.log('Risultati analisi:', data);
            // TODO: Mostra risultati analisi simmetrie
        });
    </script>
</body>
</html>
```

### 2. Template Camera iPhone (templates/camera.html)

```html
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Dermamente">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Dermamente Camera</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #000;
            color: white;
            overflow: hidden;
        }
        #video-container {
            position: relative;
            width: 100vw;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        video {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        #controls {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 15px;
            z-index: 100;
        }
        button {
            background: rgba(255,255,255,0.2);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 12px 24px;
            border-radius: 20px;
            font-size: 14px;
            cursor: pointer;
        }
        button:active {
            background: rgba(255,255,255,0.3);
        }
        #status {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7);
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 12px;
            z-index: 100;
        }
        #install-banner {
            position: fixed;
            bottom: 80px;
            left: 20px;
            right: 20px;
            background: rgba(255,255,255,0.95);
            color: #000;
            padding: 20px;
            border-radius: 12px;
            z-index: 200;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        #install-banner h3 {
            margin-bottom: 10px;
        }
        #install-banner ol {
            margin: 10px 0;
            padding-left: 20px;
        }
        #install-banner button {
            background: #007AFF;
            width: 100%;
            margin-top: 15px;
        }
        .status-connected { color: #00ff00; }
        .status-disconnected { color: #ff3b30; }
        .status-streaming { color: #ffcc00; }
    </style>
</head>
<body>
    <div id="status">Inizializzazione...</div>
    
    <div id="install-banner" style="display:none;">
        <h3>📱 Accesso Rapido</h3>
        <p>Per usare questa camera senza scansionare il QR ogni volta:</p>
        <ol>
            <li>Tap icona <strong>Condividi</strong> ⬆️ (in basso)</li>
            <li>Scorri e tap <strong>"Aggiungi a Home"</strong></li>
            <li>Conferma</li>
        </ol>
        <p style="margin-top: 10px;">✅ Prossime volte: apri l'icona dalla home screen</p>
        <button onclick="dismissInstallBanner()">Ho capito</button>
    </div>
    
    <div id="video-container">
        <video id="video" autoplay playsinline></video>
    </div>
    
    <div id="controls">
        <button id="toggle-camera">Cambia Camera</button>
        <button id="toggle-stream">Ferma Stream</button>
    </div>
    
    <canvas id="canvas" style="display:none;"></canvas>
    
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const CONFIG_KEY = 'dermamente_camera_config';
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const statusEl = document.getElementById('status');
        
        let config = {};
        let socket = null;
        let stream = null;
        let streamingInterval = null;
        let currentFacingMode = 'user'; // 'user' o 'environment'
        let isStreaming = false;
        
        // Carica o crea configurazione
        function loadConfig() {
            const saved = localStorage.getItem(CONFIG_KEY);
            if (saved) {
                config = JSON.parse(saved);
                console.log('Configurazione esistente caricata');
            } else {
                config = {
                    deviceId: crypto.randomUUID(),
                    serverUrl: window.location.origin,
                    savedAt: new Date().toISOString(),
                    cameraPreference: 'user',
                    quality: 0.8,
                    fps: 15
                };
                localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
                console.log('Nuova configurazione creata');
                
                // Mostra banner installazione solo prima volta
                setTimeout(() => {
                    document.getElementById('install-banner').style.display = 'block';
                }, 2000);
            }
            return config;
        }
        
        function dismissInstallBanner() {
            document.getElementById('install-banner').style.display = 'none';
            config.installPromptShown = true;
            localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
        }
        
        // Connessione WebSocket
        function connectWebSocket() {
            const wsUrl = config.serverUrl.replace('http://', 'ws://').replace('https://', 'wss://');
            socket = io(wsUrl, {
                query: { device: config.deviceId }
            });
            
            socket.on('connect', () => {
                updateStatus('Connesso', 'connected');
                console.log('WebSocket connesso');
            });
            
            socket.on('disconnect', () => {
                updateStatus('Disconnesso', 'disconnected');
                console.log('WebSocket disconnesso');
            });
            
            socket.on('connected', (data) => {
                console.log('Device registrato:', data.deviceId);
            });
            
            socket.on('analysis_result', (data) => {
                console.log('Risultati analisi:', data);
            });
        }
        
        // Avvia camera
        async function startCamera(facingMode = 'user') {
            try {
                // Ferma stream precedente se esiste
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                }
                
                const constraints = {
                    video: {
                        facingMode: facingMode,
                        width: { ideal: 1920 },
                        height: { ideal: 1080 },
                        frameRate: { ideal: 30 }
                    },
                    audio: false
                };
                
                stream = await navigator.mediaDevices.getUserMedia(constraints);
                video.srcObject = stream;
                
                updateStatus('Camera attiva', 'streaming');
                currentFacingMode = facingMode;
                
                // Salva preferenza camera
                config.cameraPreference = facingMode;
                localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
                
                // Avvia streaming
                startStreaming();
                
            } catch (error) {
                console.error('Errore accesso camera:', error);
                updateStatus('Errore camera: ' + error.message, 'disconnected');
                alert('Impossibile accedere alla fotocamera. Verifica i permessi.');
            }
        }
        
        // Stream frame via WebSocket
        function startStreaming() {
            if (streamingInterval) {
                clearInterval(streamingInterval);
            }
            
            isStreaming = true;
            const fps = config.fps || 15;
            const quality = config.quality || 0.8;
            
            streamingInterval = setInterval(() => {
                if (!socket || !socket.connected || !isStreaming) return;
                
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0);
                
                canvas.toBlob((blob) => {
                    if (!blob) return;
                    
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64data = reader.result.split(',')[1];
                        socket.emit('video_frame', {
                            deviceId: config.deviceId,
                            frame: base64data,
                            timestamp: Date.now()
                        });
                    };
                    reader.readAsDataURL(blob);
                }, 'image/jpeg', quality);
                
            }, 1000 / fps);
        }
        
        function stopStreaming() {
            isStreaming = false;
            if (streamingInterval) {
                clearInterval(streamingInterval);
                streamingInterval = null;
            }
        }
        
        function updateStatus(text, type) {
            statusEl.textContent = text;
            statusEl.className = 'status-' + type;
        }
        
        // Toggle camera
        document.getElementById('toggle-camera').addEventListener('click', () => {
            const newMode = currentFacingMode === 'user' ? 'environment' : 'user';
            startCamera(newMode);
        });
        
        // Toggle streaming
        document.getElementById('toggle-stream').addEventListener('click', function() {
            if (isStreaming) {
                stopStreaming();
                this.textContent = 'Avvia Stream';
                updateStatus('Stream in pausa', 'disconnected');
            } else {
                startStreaming();
                this.textContent = 'Ferma Stream';
                updateStatus('Streaming attivo', 'streaming');
            }
        });
        
        // Inizializzazione
        window.onload = async function() {
            loadConfig();
            connectWebSocket();
            await startCamera(config.cameraPreference || 'user');
        };
        
        // Cleanup alla chiusura
        window.onbeforeunload = function() {
            stopStreaming();
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
            if (socket) {
                socket.disconnect();
            }
        };
    </script>
</body>
</html>
```

---

## Configurazioni Opzionali

### 1. Icona per "Aggiungi a Home"

Crea file `static/icon-192.png` (192x192px) con logo Dermamente.

### 2. Configurazione HTTPS per Deploy Online

Se vuoi usarlo da remoto (non solo rete locale), serve HTTPS:

```python
# Con certificato SSL
if __name__ == '__main__':
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=443,
        ssl_context=('cert.pem', 'key.pem'),
        debug=False
    )
```

### 3. Impostazioni Qualità/FPS Personalizzabili

Aggiungi controlli nella pagina camera per modificare:
- Risoluzione: 720p, 1080p, 4K
- FPS: 10, 15, 30
- Qualità JPEG: 0.6, 0.8, 0.95

---

## Integrazione con Analisi Simmetrie

### Esempio processamento frame lato server

```python
import base64
import cv2
import numpy as np
import mediapipe as mp

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

@socketio.on('video_frame')
def handle_video_frame(data):
    device_id = data.get('deviceId')
    frame_b64 = data.get('frame')
    
    # Decodifica frame
    frame_bytes = base64.b64decode(frame_b64)
    nparr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Converti BGR -> RGB per MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Analisi facial landmarks
    results = face_mesh.process(rgb_frame)
    
    if results.multi_face_landmarks:
        landmarks = results.multi_face_landmarks[0]
        
        # TODO: Calcola simmetrie, distanze, angoli
        # symmetry_data = calcola_simmetrie(landmarks)
        
        emit('analysis_result', {
            'landmarks': [[lm.x, lm.y, lm.z] for lm in landmarks.landmark],
            'symmetry_score': 0.95,
            'timestamp': data.get('timestamp')
        })
```

---

## Testing e Troubleshooting

### Test connessione locale
1. Avvia server: `python app.py`
2. Desktop: apri `http://localhost:5000`
3. Verifica QR code visualizzato
4. iPhone: scansiona QR con fotocamera nativa
5. Safari si apre automaticamente
6. Accetta permessi camera
7. Verifica stream attivo

### Problemi comuni

**iPhone non accede alla camera:**
- Verifica permessi Safari in Impostazioni > Safari > Camera
- Controlla che URL sia HTTP (locale) o HTTPS (online)
- getUserMedia funziona SOLO con HTTPS o localhost

**WebSocket non connette:**
- Verifica firewall su porta 5000
- Controlla che iPhone e PC siano stessa rete WiFi
- Prova a disabilitare temporaneamente firewall

**Stream lagga o si blocca:**
- Riduci FPS a 10-12
- Riduci qualità JPEG a 0.6-0.7
- Riduci risoluzione a 1280x720

**QR code non si genera:**
- Verifica installazione: `pip install qrcode[pil]`
- Controlla che `get_local_ip()` ritorni IP valido

---

## Vantaggi vs IRIUN

✅ **Nessuna app da installare** - tutto via browser  
✅ **Cross-platform** - funziona su iPhone, Android, tablet  
✅ **Auto-configurazione** - QR code + localStorage  
✅ **Accesso rapido** - icona home screen dopo prima volta  
✅ **Controllo totale** - risoluzione, FPS, qualità personalizzabili  
✅ **Integrazione diretta** - WebSocket nativo nel tuo stack  
✅ **Zero costi** - nessuna licenza o abbonamento  

---

## Prossimi Step

1. **Implementa backend** - Flask + SocketIO + QR generation
2. **Crea templates HTML** - index.html e camera.html
3. **Testa in locale** - verifica connessione e stream
4. **Integra MediaPipe** - analisi simmetrie facciali real-time
5. **Ottimizza performance** - FPS, qualità, latenza
6. **Deploy HTTPS** - se serve accesso remoto

---

## Note Finali

Questa soluzione sostituisce completamente IRIUN con un sistema nativo integrato nella tua webapp. L'utente non deve installare nulla, la configurazione si salva automaticamente, e l'accesso diventa istantaneo dopo la prima connessione.

Il localStorage persiste anche se l'utente chiude Safari, garantendo che la configurazione rimanga salvata finché non cancella i dati del browser.

Per produzione, considera l'aggiunta di:
- Autenticazione device (token JWT)
- Crittografia stream (HTTPS/WSS)
- Compressione frame avanzata (WebP)
- Fallback connessione (retry automatico)
- Dashboard monitoring device connessi
