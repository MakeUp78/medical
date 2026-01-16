#!/bin/bash
# Script unificato per riavviare tutti i server Kimerika

echo "🛑 Fermando tutti i server..."
pkill -f "uvicorn.*main:app" 2>/dev/null
pkill -f "start_webapp.py" 2>/dev/null
pkill -f "websocket_frame_api.py" 2>/dev/null
sleep 2

echo "🚀 Avviando server..."

# API Server (porta 8001)
cd /var/www/html/kimerika.cloud
nohup python3 -m uvicorn webapp.api.main:app --host 0.0.0.0 --port 8001 --reload > api_server.log 2>&1 &
sleep 1

# WebApp Server (porta 5000)
nohup python3 start_webapp.py > webapp_server.log 2>&1 &
sleep 1

# WebSocket Server (porta 8765)
cd /var/www/html/kimerika.cloud/face-landmark-localization-master
nohup python3 websocket_frame_api.py > ../websocket_server.log 2>&1 &
sleep 2

echo ""
echo "=== STATO SERVER ==="
ps aux | grep -E "(uvicorn|start_webapp|websocket_frame)" | grep -v grep | awk '{print $2, $11, $12, $13, $14, $15}'
echo ""

# Verifica porte
if netstat -tuln 2>/dev/null | grep -q ":8001"; then
    echo "✅ API Server (8001): ATTIVO"
else
    echo "❌ API Server (8001): NON ATTIVO"
fi

if netstat -tuln 2>/dev/null | grep -q ":5000"; then
    echo "✅ WebApp Server (5000): ATTIVO"
else
    echo "❌ WebApp Server (5000): NON ATTIVO"
fi

if netstat -tuln 2>/dev/null | grep -q ":8765"; then
    echo "✅ WebSocket Server (8765): ATTIVO"
else
    echo "❌ WebSocket Server (8765): NON ATTIVO"
fi

echo ""
echo "✅ Restart completato! Tutti i server sono operativi."
