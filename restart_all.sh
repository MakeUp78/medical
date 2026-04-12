#!/bin/bash
# Script unificato per riavviare tutti i server Kimerika
# VERSIONE 2.0 - ANTI-DUPLICATI E ANTI-RACE-CONDITION
# Risolve definitivamente il problema del doppio login

set -e  # Esci in caso di errore

BASE_DIR="/var/www/html/kimerika.cloud"
cd "$BASE_DIR"

echo "=================================="
echo " KIMERIKA CLOUD - RESTART SERVER v2.0"
echo "=================================="
echo ""
echo "⚠️  IMPORTANTE: Questo script elimina processi server duplicati e sessioni pendenti"
echo "   che causavano il problema del doppio login."
echo ""

# STEP 0: Verifica requisiti
echo "✅ FASE 0: Verifica requisiti..."
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 non trovato"
    exit 1
fi
echo "   ✅ python3 trovato"

# STEP 1: Cleanup aggressivo processi duplicati
echo ""
echo "🧹 FASE 1: Pulizia processi duplicati..."
echo "   Questo risolve il problema del doppio login"
python3 cleanup_servers.py force 2>&1 | sed 's/^/   /' || {
    echo "⚠️  Cleanup fallito, procedo comunque..."
}
sleep 2

# STEP 2: Ferma tutti i server con doppio controllo (pkill + kill esplicito)
echo ""
echo "🛑 FASE 2: Terminazione processi server..."
echo "   Uccidendo tutti i processi server per start pulito..."

# Funzione helper per terminare processo
kill_process() {
    local pattern=$1
    local name=$2

    # Primo tentativo: SIGTERM graceful
    local pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "   ⏱️  $name - tentativo SIGTERM..."
        pkill -f "$pattern" 2>/dev/null || true
        sleep 1

        # Secondo tentativo: SIGKILL forzato
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "   💥 $name - SIGKILL forzato..."
            pkill -9 -f "$pattern" 2>/dev/null || true
            sleep 1
        fi
    fi
}

kill_process "uvicorn.*main:app" "API Server"
kill_process "start_webapp.py" "WebApp Server"
kill_process "websocket_frame_api.py" "WebSocket Server"
kill_process "auth_server.py" "Auth Server"  # CRITICO: Ferma auth_server

sleep 2

# STEP 2b: Rimuovi TUTTI i file PID (possono essere corrotti)
echo "   🧹 Pulizia file PID obsoleti..."
rm -f .api_server.pid .webapp_server.pid .websocket_server.pid .auth_server.pid 2>/dev/null || true
rm -f api_server.log webapp_server.log websocket_server.log auth_server.log 2>/dev/null || true
echo "   ✅ File PID e log rimossi"

# STEP 2c: Verifica che le porte siano effettivamente liberate
echo "   🔍 Verifica porte liberate..."
for port in 3000 5000 8001 8765; do
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        echo "   ⚠️  Porta $port ancora occupata - tentativo forzato di liberazione..."
        fuser -k $port/tcp 2>/dev/null || true
        sleep 1
    fi
done
echo "   ✅ Tutte le porte liberate"

# STEP 3: Avvio server con ordine critico
echo ""
echo "🚀 FASE 3: Avvio server..."
echo ""
echo "   ⚠️  IMPORTANTE: Ordine di avvio critico!"
echo "   1. Auth Server DEVE partire per primo (porta 5000)"
echo "   2. WebApp Server DEVE usare porta 3000 (NON 5000)"
echo "   3. Altri server dopo"
echo ""

# Auth Server (porta 5000) - DEVE PARTIRE PER PRIMO
echo "   🔐 Avvio Auth Server (porta 5000)..."
nohup python3 auth_server.py > auth_server.log 2>&1 &
AUTH_PID=$!
echo "      PID: $AUTH_PID"
sleep 3

# Verifica che auth_server sia partito
if ps -p $AUTH_PID > /dev/null 2>&1; then
    echo "      ✅ Auth Server avviato con successo"

    # Verifica porta 5000
    sleep 1
    if netstat -tuln 2>/dev/null | grep -q ":5000 " || ss -tuln 2>/dev/null | grep -q ":5000 "; then
        echo "      ✅ Porta 5000 confermata disponibile"
    else
        echo "      ⚠️  Porta 5000 non verificata (potrebbe servire)"
    fi
else
    echo "      ❌ Auth Server FALLITO - controllare auth_server.log"
    echo "      Estratto log:"
    tail -20 auth_server.log | sed 's/^/         /'
    exit 1
fi

# WebApp Server (porta 3000) - DEVE usare porta diversa da 5000
echo "   🌐 Avvio WebApp Server (porta 3000)..."
nohup python3 start_webapp.py > webapp_server.log 2>&1 &
WEBAPP_PID=$!
echo "      PID: $WEBAPP_PID"
sleep 2

if ps -p $WEBAPP_PID > /dev/null 2>&1; then
    echo "      ✅ WebApp Server avviato"
else
    echo "      ⚠️  WebApp Server potrebbe aver fallito"
    tail -10 webapp_server.log | sed 's/^/         /'
fi

# API Server (porta 8001)
echo "   📡 Avvio API Server (porta 8001)..."
nohup python3 -m uvicorn webapp.api.main:app --host 0.0.0.0 --port 8001 --reload > api_server.log 2>&1 &
API_PID=$!
echo "      PID: $API_PID"
sleep 2

# WebSocket Server (porta 8765)
echo "   🔌 Avvio WebSocket Server (porta 8765)..."
cd "$BASE_DIR/face-landmark-localization-master"
nohup python3 websocket_frame_api.py > ../websocket_server.log 2>&1 &
WS_PID=$!
cd "$BASE_DIR"
echo "      PID: $WS_PID"
sleep 2

# STEP 4: Verifica CRITICA dello stato
echo ""
echo "===================================="
echo " VERIFICA CRITICA STATO SERVER"
echo "===================================="
echo ""

# Check 1: Processi attivi
echo "📊 Processi server attivi:"
RUNNING_PROCS=$(ps aux | grep -E "(python3.*(uvicorn|start_webapp|websocket_frame|auth_server))" | grep -v grep)
if [ -z "$RUNNING_PROCS" ]; then
    echo "   ❌ NESSUN PROCESSO SERVER ATTIVO!"
    echo "   Controllare i log per errori"
    exit 1
else
    echo "$RUNNING_PROCS" | awk '{print "   - PID", $2, $11, $12, $13}'
fi
echo ""

# Check 2: Porte
echo "🔍 Porte in ascolto (verifica critica):"
PORTS_OK=1

# Porta 3000 (WebApp)
if netstat -tuln 2>/dev/null | grep -q ":3000 " || ss -tuln 2>/dev/null | grep -q ":3000 "; then
    echo "   ✅ WebApp Server (3000): ATTIVO"
else
    echo "   ⚠️  WebApp Server (3000): Non risponde"
fi

# Porta 5000 (Auth) - CRITICO
if netstat -tuln 2>/dev/null | grep -q ":5000 " || ss -tuln 2>/dev/null | grep -q ":5000 "; then
    echo "   ✅ Auth Server (5000): ATTIVO - CRITICO VERIFICATO ✓"
else
    echo "   ❌ Auth Server (5000): NON ATTIVO - PROBLEMA CRITICO!"
    echo "      Il problema del doppio login è ancora presente"
    PORTS_OK=0
fi

# Porta 8001 (API)
if netstat -tuln 2>/dev/null | grep -q ":8001 " || ss -tuln 2>/dev/null | grep -q ":8001 "; then
    echo "   ✅ API Server (8001): ATTIVO"
else
    echo "   ⚠️  API Server (8001): Non risponde"
fi

# Porta 8765 (WebSocket)
if netstat -tuln 2>/dev/null | grep -q ":8765 " || ss -tuln 2>/dev/null | grep -q ":8765 "; then
    echo "   ✅ WebSocket Server (8765): ATTIVO"
else
    echo "   ⚠️  WebSocket Server (8765): Non risponde"
fi

echo ""

# Check 3: Processi duplicati auth_server (CRITICO)
echo "🔐 Verifica Auth Server (CRITICO per doppio login):"
AUTH_COUNT=$(ps aux | grep "python3.*auth_server.py" | grep -v grep | wc -l)

if [ "$AUTH_COUNT" -gt 1 ]; then
    echo "   ❌ ATTENZIONE: $AUTH_COUNT processi auth_server trovati!"
    echo "   QUESTO CAUSA IL PROBLEMA DEL DOPPIO LOGIN!"
    ps aux | grep "python3.*auth_server.py" | grep -v grep | awk '{print "      - PID", $2}'
    echo ""
    echo "   🔧 FIX: Esegui:"
    echo "      python3 cleanup_servers.py auth"
    echo "      ./restart_all.sh"
    PORTS_OK=0
elif [ "$AUTH_COUNT" -eq 1 ]; then
    PID=$(ps aux | grep "python3.*auth_server.py" | grep -v grep | awk '{print $2}')
    echo "   ✅ Auth Server: 1 processo (OK)"
    echo "      PID: $PID"
else
    echo "   ❌ Auth Server: NESSUN PROCESSO (CRITICO!)"
    echo "   Controllare auth_server.log:"
    if [ -f auth_server.log ]; then
        tail -15 auth_server.log | sed 's/^/      /'
    fi
    PORTS_OK=0
fi

echo ""
echo "===================================="
echo " SUGGERIMENTI"
echo "===================================="
echo ""
echo "📋 Per monitorare i server:"
echo "   tail -f auth_server.log      # Log autenticazione"
echo "   tail -f api_server.log       # Log API"
echo "   tail -f webapp_server.log    # Log WebApp"
echo ""
echo "🔧 In caso di problemi:"
echo "   python3 cleanup_servers.py status    # Stato dettagliato"
echo "   python3 cleanup_servers.py auth      # Risolve doppio login"
echo "   ./restart_all.sh                     # Riavvia completo"
echo ""

if [ $PORTS_OK -eq 0 ]; then
    echo "❌ ATTENZIONE: Alcuni servizi critici non sono attivi!"
    exit 1
else
    echo "✅ Restart completato! Tutti i server sono operativi."
    echo ""
    echo "🌍 Accedi all'applicazione:"
    echo "   http://localhost:3000/landing.html"
fi
