# 🔄 Guida Rapida Riavvio Server Kimerika.cloud

Procedura per riavviare i 3 server necessari per la webapp kimerika.cloud.

## 🎯 OTTIMIZZAZIONI APPLICATE

### ✅ Normalizzazione 72 DPI
- Tutti i contenuti (immagini, video, webcam) vengono normalizzati a 72 pixel/pollice
- Standard web per consistenza tra sorgenti diverse

### ✅ Compressione Bilanciata
- **Immagini caricate**: max 1920px, quality JPEG 0.85 (~150-200KB/immagine, qualità alta)
- **Video frames elaborazione**: max 1280px, quality JPEG 0.6 (~50KB/frame per analisi)
- **Video anteprima**: max 1280px, quality JPEG 0.75 (~70KB/frame per display)
- **Webcam frames**: max 1280px, quality JPEG 0.6 (~50KB/frame)
- Proporzioni originali mantenute, NO ritagli

### ✅ Reset Completo Interfaccia
- Canvas completamente pulito quando si carica nuovo contenuto
- Landmarks azzerati (currentLandmarks = [])
- Tabelle svuotate (debug + unificata)
- WebSocket precedente chiuso
- Score reset a 0
- Cache-busting con timestamp

### ✅ Anteprima Video Ottimizzata
- Frame anteprima compressi PRIMA di essere mostrati
- Riduzione consumo memoria e CPU
- Qualità visiva preservata (0.75)

---

## ⚡ RIAVVIO RAPIDO (One-Liner)

Copia e incolla questo comando per riavviare tutto in un colpo:

```bash
pkill -f "uvicorn.*main:app"; pkill -f "start_webapp.py"; pkill -f "websocket_frame_api.py"; sleep 2 && cd /var/www/html/kimerika.cloud && nohup python3 -m uvicorn webapp.api.main:app --host 0.0.0.0 --port 8001 --reload > api_server.log 2>&1 & nohup python3 start_webapp.py > webapp_server.log 2>&1 & cd face-landmark-localization-master && nohup python3 websocket_frame_api.py > ../websocket_server.log 2>&1 & sleep 2 && echo "✅ Server riavviati!" && ps aux | grep -E "uvicorn|start_webapp|websocket_frame" | grep -v grep
```

---

## 📝 PROCEDURA PASSO-PASSO

### 1️⃣ Ferma tutti i server

```bash
pkill -f "uvicorn.*main:app"
pkill -f "start_webapp.py"
pkill -f "websocket_frame_api.py"
sleep 2
```

### 2️⃣ Avvia API Server (porta 8001)

```bash
cd /var/www/html/kimerika.cloud
nohup python3 -m uvicorn webapp.api.main:app --host 0.0.0.0 --port 8001 --reload > api_server.log 2>&1 &
```

### 3️⃣ Avvia WebApp Frontend (porta 5000)

```bash
cd /var/www/html/kimerika.cloud
nohup python3 start_webapp.py > webapp_server.log 2>&1 &
```

### 4️⃣ Avvia WebSocket Server (porta 8765)

```bash
cd /var/www/html/kimerika.cloud/face-landmark-localization-master
nohup python3 websocket_frame_api.py > ../websocket_server.log 2>&1 &
```

### 5️⃣ Verifica che tutto sia attivo

```bash
# Verifica processi
ps aux | grep -E "uvicorn|start_webapp|websocket_frame" | grep -v grep

# Verifica porte
netstat -tuln | grep -E ":8001|:5000|:8765"

# Test API Health
curl -s https://kimerika.cloud/api/health | jq
```

---

## 🛠️ COMANDI UTILI

### Riavvia solo un server specifico

```bash
# Solo API
pkill -f "uvicorn.*main:app" && cd /var/www/html/kimerika.cloud && nohup python3 -m uvicorn webapp.api.main:app --host 0.0.0.0 --port 8001 --reload > api_server.log 2>&1 &

# Solo WebApp
pkill -f "start_webapp.py" && cd /var/www/html/kimerika.cloud && nohup python3 start_webapp.py > webapp_server.log 2>&1 &

# Solo WebSocket
pkill -f "websocket_frame_api.py" && cd /var/www/html/kimerika.cloud/face-landmark-localization-master && nohup python3 websocket_frame_api.py > ../websocket_server.log 2>&1 &
```

### Visualizza log in real-time

```bash
# API log
tail -f /var/www/html/kimerika.cloud/api_server.log

# WebApp log
tail -f /var/www/html/kimerika.cloud/webapp_server.log

# WebSocket log
tail -f /var/www/html/kimerika.cloud/websocket_server.log
```

### Riavvia solo JavaScript frontend

```bash
# NON serve riavviare server - NGINX serve direttamente da /var/www/html/kimerika.cloud/webapp/static/js/
# Basta ricaricare NGINX per pulire cache
sudo nginx -t && sudo systemctl reload nginx
```

### Riavvia NGINX (se il sito non risponde)

```bash
sudo systemctl restart nginx
```

---

## ⚠️ NOTE IMPORTANTI

- **NON si apre automaticamente il browser** (nohup lo previene)
- **API Server DEVE essere sulla porta 8001** (NGINX punta a 8001)
- **NGINX** serve i file statici da `/var/www/html/kimerika.cloud/webapp/`
- I server girano in background con `nohup`
- I log sono salvati nella directory principale
- L'app è accessibile su: **https://kimerika.cloud**
- Per modifiche JavaScript NON serve riavviare, basta reload NGINX

---

## 🎯 ARCHITETTURA

```
Cliente → NGINX (443) → {
  /api/*       → FastAPI (8001)
  /ws          → WebSocket (8765)
  /static/*    → File System
  /            → Flask WebApp (5000)
}
```
