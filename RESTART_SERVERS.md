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

```bash
systemctl restart kimerika-api.service kimerika-websocket.service && echo "✅ Server riavviati!"
```

> ⚠️ **NON usare uvicorn manualmente** — crea un processo zombie che occupa la porta 8001
> impedendo al service systemd di avviarsi (il vecchio codice rimane in esecuzione).

---

## 📝 PROCEDURA PASSO-PASSO

### 1️⃣ Riavvia API Server (porta 8001)

```bash
systemctl restart kimerika-api.service
systemctl status kimerika-api.service
```

### 2️⃣ Riavvia WebSocket Server (porta 8765)

```bash
systemctl restart kimerika-websocket.service
systemctl status kimerika-websocket.service
```

### 3️⃣ Verifica che tutto sia attivo

```bash
# Verifica servizi
systemctl status kimerika-api.service kimerika-websocket.service kimerika-auth.service

# Verifica porte
ss -tlnp | grep -E ":8001|:8765"

# Test API Health
curl -s http://localhost:8001/health
```

---

## 🛠️ COMANDI UTILI

### Riavvia solo un server specifico

```bash
# Solo API (FastAPI/main.py — porta 8001)
systemctl restart kimerika-api.service

# Solo WebSocket (porta 8765)
systemctl restart kimerika-websocket.service

# Solo Auth (porta auth)
systemctl restart kimerika-auth.service
```

### Visualizza log in real-time

```bash
# API log
journalctl -u kimerika-api.service -f

# WebSocket log
journalctl -u kimerika-websocket.service -f

# Auth log
journalctl -u kimerika-auth.service -f
```

### Se la porta 8001 risulta occupata dopo un crash

```bash
# Trova e uccidi il processo zombie
fuser -k 8001/tcp
systemctl start kimerika-api.service
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
