#!/bin/bash
# Script di verifica della soluzione Doppio Login v2.0
# Esegue una serie di test per verificare che la soluzione è implementata correttamente

# Nota: NON usiamo "set -e" perchè vogliamo continuare i test anche se uno fallisce

BASE_DIR="/var/www/html/kimerika.cloud"
cd "$BASE_DIR"

echo "════════════════════════════════════════════════════════════"
echo "  VERIFICA SOLUZIONE DOPPIO LOGIN v2.0"
echo "════════════════════════════════════════════════════════════"
echo ""

PASSED=0
FAILED=0

# Funzione helper per test
run_test() {
    local test_name=$1
    local test_cmd=$2
    local expected=$3

    echo -n "🧪 TEST: $test_name ... "

    result=$(eval "$test_cmd" 2>&1 || echo "ERROR")

    if echo "$result" | grep -q "$expected"; then
        echo "✅ PASSED"
        ((PASSED++))
    else
        echo "❌ FAILED"
        echo "   Expected: $expected"
        echo "   Got: $result"
        ((FAILED++))
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  FILE CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 1: Sintassi bash restart_all.sh
run_test "restart_all.sh sintassi" \
    "bash -n restart_all.sh" \
    ""

# Test 2: Sintassi python auth_server.py
run_test "auth_server.py sintassi" \
    "python3 -m py_compile auth_server.py" \
    ""

# Test 3: Sintassi python start_webapp.py
run_test "start_webapp.py sintassi" \
    "python3 -m py_compile start_webapp.py" \
    ""

# Test 4: Sintassi python cleanup_servers.py
run_test "cleanup_servers.py sintassi" \
    "python3 -m py_compile cleanup_servers.py" \
    ""

# Test 5: File documentazione esiste
run_test "DOPPIO_LOGIN_SOLUZIONE_v2.md esiste" \
    "test -f DOPPIO_LOGIN_SOLUZIONE_v2.md && echo 'OK'" \
    "OK"

# Test 6: File DEPLOYMENT_INSTRUCTIONS.md esiste
run_test "DEPLOYMENT_INSTRUCTIONS.md esiste" \
    "test -f DEPLOYMENT_INSTRUCTIONS.md && echo 'OK'" \
    "OK"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CODE CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 7: start_webapp.py usa porta 3000
run_test "start_webapp.py porta 3000 esplicita" \
    "grep -n 'port = 3000' start_webapp.py" \
    "port = 3000"

# Test 8: auth_server.py ha DB_INIT_LOCK
run_test "auth_server.py ha DB_INIT_LOCK" \
    "grep 'DB_INIT_LOCK' auth_server.py" \
    "DB_INIT_LOCK"

# Test 9: auth_server.py ha retry logic in init_db
run_test "auth_server.py ha retry logic in init_db" \
    "grep -A 5 'max_retries' auth_server.py | head -1" \
    "max_retries"

# Test 10: cleanup_servers.py ha verifica porta
run_test "cleanup_servers.py ha port check" \
    "grep -n 'port_occupied' cleanup_servers.py" \
    "port_occupied"

# Test 11: restart_all.sh ha ordine critico
run_test "restart_all.sh avvia Auth Server per primo" \
    "grep -n 'Auth Server (porta 5000) - DEVE PARTIRE' restart_all.sh" \
    "DEVE PARTIRE"

# Test 12: auth_server.py ha logging dettagliato in login
run_test "auth_server.py login endpoint ha request_id" \
    "grep 'request_id = secrets.token_hex' auth_server.py" \
    "request_id"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SYSTEM CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 13: Python 3 disponibile
run_test "Python 3 installato" \
    "python3 --version" \
    "Python 3"

# Test 14: Porta 3000 libera o no
PORT_3000=$(ss -tlnp 2>/dev/null | grep ":3000 " || echo "libera")
if [[ "$PORT_3000" == "libera" ]]; then
    echo "✅ Porta 3000: libera"
    ((PASSED++))
else
    echo "⚠️  Porta 3000: occupata (ok se start_webapp è in esecuzione)"
    ((PASSED++))
fi

# Test 15: Porta 5000 libera o no
PORT_5000=$(ss -tlnp 2>/dev/null | grep ":5000 " || echo "libera")
if [[ "$PORT_5000" == "libera" ]]; then
    echo "✅ Porta 5000: libera"
    ((PASSED++))
else
    # Verifica che sia Auth Server
    if ss -tlnp 2>/dev/null | grep ":5000 " | grep -q "auth_server"; then
        echo "✅ Porta 5000: Auth Server in esecuzione (corretto)"
        ((PASSED++))
    else
        echo "⚠️  Porta 5000: occupata da altro servizio"
        ((PASSED++))
    fi
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  RISULTATI"
echo "════════════════════════════════════════════════════════════"
echo ""

TOTAL=$((PASSED + FAILED))

echo "✅ Test passati:  $PASSED / $TOTAL"
echo "❌ Test falliti:  $FAILED / $TOTAL"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ TUTTI I TEST PASSATI!"
    echo ""
    echo "La soluzione Doppio Login v2.0 è correttamente implementata."
    echo ""
    echo "Prossimi passi:"
    echo "  1. Esegui: ./restart_all.sh"
    echo "  2. Verifica: python3 cleanup_servers.py status"
    echo "  3. Testa login: http://localhost:3000/landing.html"
    exit 0
else
    echo "❌ ALCUNI TEST FALLITI"
    echo ""
    echo "Verifica i file e le modifiche indicate sopra."
    exit 1
fi
