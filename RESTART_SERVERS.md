# Come Riavviare i Server Kimerika.cloud

## 1. FERMARE I SERVER
```bash
pkill -f "uvicorn.*main:app" || true
pkill -f "start_webapp.py" || true
pkill -f "websocket_frame_api.py" || true
```

## 2. AVVIARE I SERVER (nell'ordine corretto)

### API Server (porta 8001)
```bash
cd /var/www/html/kimerika.cloud
nohup python3 -m uvicorn webapp.api.main:app --host 0.0.0.0 --port 8001 --reload > api_server.log 2>&1 &
```

### WebApp Frontend (porta 5000)
```bash
cd /var/www/html/kimerika.cloud
nohup python3 start_webapp.py > webapp_server.log 2>&1 &
```

### WebSocket Server (porta 8765)
```bash
cd /var/www/html/kimerika.cloud/face-landmark-localization-master
nohup python3 websocket_frame_api.py > ../websocket_server.log 2>&1 &
```

## 3. VERIFICARE CHE TUTTO SIA ATTIVO
```bash
ps aux | grep -E "uvicorn|start_webapp|websocket_frame" | grep -v grep
netstat -tuln | grep -E ":8001|:5000|:8765"
```

## 4. SE NGINX NON RISPONDE
```bash
systemctl restart nginx
```

## NOTE IMPORTANTI
- **API Server DEVE essere sulla porta 8001** (non 8000!)
- Nginx fa da reverse proxy e punta alla porta 8001
- Se il sito non risponde, verificare prima i processi, poi nginx
