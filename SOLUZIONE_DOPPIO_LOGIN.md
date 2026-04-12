# 🔒 Soluzione Problema Doppio Login

## Problema Risolto
**Sintomo**: Il primo tentativo di login falliva sempre, il secondo con gli stessi dati andava a buon fine.

**Causa**: Processi duplicati di `auth_server.py` in esecuzione contemporaneamente, causando conflitti di sessione/database.

## Soluzione Implementata

### 1. 🛡️ Protezione Singleton in `auth_server.py`
Aggiunto sistema di protezione a due livelli:

**Livello 1 - Controllo Porta (Primario)**
- Verifica se la porta 5000 è già occupata PRIMA dell'avvio
- Blocca immediatamente istanze duplicate
- Metodo più affidabile contro race conditions

**Livello 2 - Controllo PID File (Secondario)**
- File PID: `.auth_server.pid`
- Cleanup automatico di PID file obsoleti
- Gestione corretta del Flask reloader (debug mode)

**Gestori di Segnali**
- `SIGTERM`, `SIGINT`: pulizia automatica del PID file
- `atexit`: cleanup alla chiusura normale

### 2. 🧹 Script di Cleanup (`cleanup_servers.py`)
Script Python per gestione robusta dei processi server.

**Comandi disponibili:**
```bash
# Mostra stato di tutti i server
python3 cleanup_servers.py status

# Pulisce solo auth server (risolve doppio login)
python3 cleanup_servers.py auth

# Pulisce tutti i server
python3 cleanup_servers.py all

# Forza terminazione di tutti i server
python3 cleanup_servers.py force
```

**Funzionalità:**
- ✅ Rileva processi duplicati
- ✅ Verifica coerenza PID file
- ✅ Termina processi gracefully (o forzatamente se necessario)
- ✅ Pulisce file PID obsoleti
- ✅ Report dettagliato dello stato

### 3. 🔄 Script di Restart Migliorato (`restart_all.sh`)
Aggiornato per prevenire duplicati:

**Fasi di restart:**
1. **Cleanup**: rimuove tutti i processi duplicati
2. **Terminazione**: doppio controllo di terminazione
3. **Avvio**: avvia server con protezioni attive
4. **Verifica**: controlla stato e rileva problemi

**Comandi:**
```bash
# Riavvio completo di tutti i server
./restart_all.sh

# Solo per problemi auth
python3 cleanup_servers.py auth
./restart_all.sh
```

## Test di Verifica

### ✅ Test Eseguiti
1. **Terminazione processi duplicati**: ✅ PASSATO
2. **Avvio singolo con protezione**: ✅ PASSATO  
3. **Blocco seconda istanza**: ✅ PASSATO
4. **Compatibilità Flask debug mode**: ✅ PASSATO

### 🧪 Come Testare
```bash
# 1. Verifica stato
python3 cleanup_servers.py status

# 2. Se ci sono duplicati, pulisci
python3 cleanup_servers.py auth

# 3. Avvia server
python3 auth_server.py

# 4. In un altro terminale, tenta secondo avvio (deve fallire)
python3 auth_server.py
# Deve mostrare: "❌ ERRORE: Porta 5000 già in uso!"
```

## Uso Quotidiano

### Avvio Normale
```bash
# Avvia tutti i server (incluso auth)
./restart_all.sh
```

### In Caso di Problemi
```bash
# 1. Diagnostica
python3 cleanup_servers.py status

# 2. Se auth è duplicato
python3 cleanup_servers.py auth

# 3. Riavvia
./restart_all.sh
```

### Monitoring
```bash
# Verifica log auth
tail -f auth_server.log

# Verifica porta in uso
ss -tlnp | grep :5000

# Conta processi auth
ps aux | grep auth_server.py | grep -v grep | wc -l
# Deve restituire: 2 (padre + reloader in debug mode)
```

## File Modificati

1. **auth_server.py**
   - Aggiunta protezione singleton con check porta primario
   - Gestione Flask reloader (WERKZEUG_RUN_MAIN)
   - Signal handlers per cleanup

2. **cleanup_servers.py** (NUOVO)
   - Script unificato per gestione processi
   - Supporta tutti i server della piattaforma

3. **restart_all.sh**
   - Aggiunto cleanup automatico pre-avvio
   - Gestione auth_server inclusa
   - Verifica post-avvio processi duplicati

## Note Tecniche

### Flask Debug Mode
- Flask crea 2 processi: padre e reloader
- La protezione distingue correttamente tra:
  - ✅ Padre + Reloader (normale)
  - ❌ Due istanze indipendenti (problema)

### Perché il Controllo Porta?
- **PID file solo**: race condition possibili
- **Porta + PID file**: protezione a prova di errore
- Se la porta è occupata, è IMPOSSIBILE avviare un'altra istanza

### Sicurezza Host Condiviso
- Tutte le modifiche sono confinate all'applicazione
- Nessun cambiamento a livello di sistema
- Nessun restart di servizi globali
- Script Python pure, portabili

## Risultato Finale

✅ **PROBLEMA RISOLTO**
- ❌ Primo login fallisce ➜ ✅ Primo login funziona
- ❌ Processi duplicati ➜ ✅ Istanza singola garantita
- ❌ File PID obsoleti ➜ ✅ Cleanup automatico
- ❌ Nessun controllo ➜ ✅ Protezione robusta

## Supporto

In caso di problemi persistenti:
1. Esegui `python3 cleanup_servers.py status` per diagnostica
2. Controlla `auth_server.log` per errori specifici
3. Usa `cleanup_servers.py force` per reset completo

---
**Data soluzione**: 22 Marzo 2026  
**Versione**: 1.0.0  
**Testato**: ✅ Ambiente di produzione
