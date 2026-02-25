# Gestione Server Kimerika Cloud

Sistema unificato per la gestione di tutti i server dell'applicazione, completamente indipendente da configurazioni esterne.

## 🚀 Server Gestiti

Il sistema gestisce automaticamente i seguenti server:

1. **API Server (FastAPI)** - Porta 8001
   - Backend API REST principale
   - Gestisce analisi facciali, green dots, etc.

2. **WebApp Server** - Porta 3000
   - Server frontend per file statici
   - Serve HTML/CSS/JS della webapp

3. **WebSocket Server** - Porta 8765
   - Server per streaming real-time frames
   - Comunicazione bidirezionale camera-browser

4. **Auth Server** (opzionale) - Porta 5000
   - Gestione autenticazione e utenti
   - OAuth Google/Apple, JWT tokens

## 📋 Comandi Disponibili

### Avvio Server
```bash
python server_manager.py start
```
Avvia tutti i server richiesti. Il sistema:
- Verifica che le porte siano libere
- Controlla dipendenze e file necessari
- Avvia i processi in background
- Salva PID per gestione successiva
- Genera log separati per ogni server

### Arresto Server
```bash
python server_manager.py stop
```
Ferma tutti i server in modo pulito:
- Termina i processi tramite PID salvati
- Chiude connessioni aperte
- Libera le porte
- Rimuove file PID

### Riavvio Server
```bash
python server_manager.py restart
```
Riavvia tutti i server:
- Esegue stop completo
- Attende 3 secondi
- Riavvia tutti i server

### Stato Server
```bash
python server_manager.py status
```
Mostra stato dettagliato di ogni server:
- ● Verde: server attivo e operativo
- ◐ Giallo: porta occupata da altro processo
- ○ Rosso: server non attivo

Include informazioni su:
- PID del processo
- Utilizzo CPU e memoria
- Stato porta (in uso/libera)

### Pulizia File PID
```bash
python server_manager.py cleanup
```
Rimuove file PID obsoleti (processi non più esistenti).

## 🔧 Configurazione

La configurazione dei server è contenuta nel file `server_manager.py` nella sezione `SERVER_CONFIG`:

```python
SERVER_CONFIG = {
    "api_server": {
        "name": "API Server (FastAPI)",
        "port": 8001,
        "command": [...],
        "required": True  # Server obbligatorio
    },
    # ... altri server
}
```

Ogni server ha:
- **name**: nome descrittivo
- **port**: porta di ascolto
- **command**: comando per avvio
- **cwd**: directory di lavoro
- **log_file**: file di log
- **pid_file**: file PID per tracking
- **required**: se obbligatorio (True) o opzionale (False)
- **startup_delay**: secondi di attesa dopo l'avvio

## 📁 File Generati

Il sistema crea automaticamente:

### File PID (Process ID)
- `.api_server.pid`
- `.webapp_server.pid`
- `.websocket_server.pid`
- `.auth_server.pid`

Contengono il PID del processo per gestione e terminazione.

### File Log
- `api_server.log`
- `webapp_server.log`
- `websocket_server.log`
- `auth_server.log`

Contengono output stdout/stderr di ogni server.

## 🛠️ Troubleshooting

### Porta già in uso
Se un server non si avvia perché la porta è occupata:

```bash
# Verifica quale processo usa la porta
sudo lsof -i :8001

# Oppure usa il manager per vedere lo stato
python server_manager.py status
```

Per liberare la porta:
```bash
# Ferma tutti i server Kimerika
python server_manager.py stop

# Oppure termina il processo specifico
kill <PID>
```

### Server non si avvia
1. Controlla il file di log del server:
   ```bash
   tail -f api_server.log
   ```

2. Verifica dipendenze Python:
   ```bash
   pip install -r requirements.txt
   ```

3. Controlla che i file necessari esistano:
   ```bash
   ls -la webapp/api/main.py
   ls -la start_webapp.py
   ```

### File PID obsoleti
Se i server risultano "running" ma non rispondono:
```bash
python server_manager.py cleanup
python server_manager.py restart
```

### Processi zombie
Se dopo lo stop i processi rimangono attivi:
```bash
# Forza terminazione di tutti i processi Python
pkill -9 -f "uvicorn"
pkill -9 -f "start_webapp"
pkill -9 -f "websocket_frame_api"

# Poi pulisci e riavvia
python server_manager.py cleanup
python server_manager.py start
```

## 🔐 Permessi

Su Linux/Mac, potrebbe essere necessario rendere eseguibile lo script:
```bash
chmod +x server_manager.py
```

Per accedere alle porte < 1024 (es. 80, 443) serve privilegio root:
```bash
sudo python server_manager.py start
```

## 🌐 Accesso Remoto

I server sono configurati per ascoltare su `0.0.0.0` (tutte le interfacce), permettendo accesso:
- Locale: `http://localhost:8001`
- LAN: `http://192.168.x.x:8001`
- Pubblico: configurare port forwarding su router

### Firewall
Assicurati che il firewall permetta traffico sulle porte:
```bash
# Ubuntu/Debian
sudo ufw allow 8001/tcp
sudo ufw allow 3000/tcp
sudo ufw allow 8765/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=8001/tcp --permanent
sudo firewall-cmd --reload
```

## 📊 Monitoraggio

### Utilizzo Risorse
```bash
# Mostra risorse in tempo reale
python server_manager.py status

# Oppure usa htop/top
htop -p $(cat .api_server.pid),$(cat .webapp_server.pid),$(cat .websocket_server.pid)
```

### Log in Tempo Reale
```bash
# Segui tutti i log contemporaneamente
tail -f api_server.log webapp_server.log websocket_server.log
```

## 🔄 Integrazione con Systemd (Linux)

Per avvio automatico al boot, crea un servizio systemd:

```bash
sudo nano /etc/systemd/system/kimerika.service
```

Contenuto:
```ini
[Unit]
Description=Kimerika Cloud Server Manager
After=network.target

[Service]
Type=forking
User=www-data
WorkingDirectory=/var/www/html/kimerika.cloud
ExecStart=/usr/bin/python3 server_manager.py start
ExecStop=/usr/bin/python3 server_manager.py stop
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Poi:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kimerika
sudo systemctl start kimerika
```

## 📝 Note Importanti

1. **Indipendenza**: Il sistema è completamente autocontenuto in questo workspace
2. **Isolamento**: Ogni server ha il proprio processo, log e PID
3. **Graceful Shutdown**: I server vengono terminati in modo pulito con timeout
4. **Auto-recovery**: In caso di crash, basta riavviare con `restart`
5. **Zero Dependencies External**: Non dipende da configurazioni nginx, apache, etc.

## 🆘 Supporto

In caso di problemi:
1. Controlla i log: `tail -f *.log`
2. Verifica lo stato: `python server_manager.py status`
3. Pulisci e riavvia: `python server_manager.py cleanup && python server_manager.py restart`
4. Controlla porte: `sudo netstat -tulpn | grep -E '8001|3000|8765|5000'`

---

**Versione**: 1.0.0  
**Ultima modifica**: 2026-02-04  
**Autore**: Kimerika Cloud Team
