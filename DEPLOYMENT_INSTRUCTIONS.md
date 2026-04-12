# 🚀 ISTRUZIONI DI DEPLOYMENT - Soluzione Doppio Login v2.0

## TL;DR (Fast Start)

```bash
cd /var/www/html/kimerika.cloud

# Cleanup completo
python3 cleanup_servers.py force

# Avvio
./restart_all.sh

# Verifica
python3 cleanup_servers.py status
```

Se tutto è verde (✅), il sito è pronto.

---

## 📋 COSA È STATO RISOLTO

### Prima (Problema Doppio Login)
```
❌ Primo login fallisce sempre
❌ Secondo login funziona
❌ Processi duplicati auth_server
❌ Sessioni pendenti
❌ Race condition database
```

### Dopo (Soluzione v2.0)
```
✅ Primo login funziona
✅ Secondo login funziona
✅ Zero processi duplicati
✅ Zero sessioni pendenti
✅ Zero race condition
```

---

## 🎯 STEP-BY-STEP DEPLOYMENT

### Step 1: Cleanup Totale
```bash
cd /var/www/html/kimerika.cloud

# Forza terminazione tutti i processi vecchi
python3 cleanup_servers.py force

# Attendi conferma
# Output: ✅ Cleanup completato!
```

### Step 2: Verifica Porte Liberate
```bash
# Controlla che NESSUNA porta sia occupata
python3 cleanup_servers.py status

# Dovresti vedere:
# 📊 Auth Server - ⚪ FERMO
# 📊 API Server - ⚪ FERMO
# 📊 WebApp Server - ⚪ FERMO
# 📊 WebSocket Server - ⚪ FERMO
```

Se hai ancora processi, esegui:
```bash
# Termina processi ostinati
pkill -9 python3
sleep 2
python3 cleanup_servers.py status
```

### Step 3: Avvio Servers
```bash
# Questo avvia i server in ordine critico:
# 1. Auth Server (porta 5000) - PRIMO
# 2. WebApp Server (porta 3000)
# 3. API Server (porta 8001)
# 4. WebSocket Server (porta 8765)
./restart_all.sh
```

Output atteso:
```
✅ Restart completato! Tutti i server sono operativi.

🌍 Accedi all'applicazione:
   http://localhost:3000/landing.html
```

### Step 4: Verifica Stato
```bash
python3 cleanup_servers.py status

# Output atteso:
# 📊 Auth Server - 🟢 ATTIVO (PID: xxxxx)
# 📊 API Server - 🟢 ATTIVO (PID: xxxxx)
# 📊 WebApp Server - 🟢 ATTIVO (PID: xxxxx)
# 📊 WebSocket Server - 🟢 ATTIVO (PID: xxxxx)
```

### Step 5: Test Login
```bash
# Apri browser e accedi a:
http://localhost:3000/landing.html

# Clicca "Accedi"
# Inserisci credenziali valide
# Clicca "Accedi"

# ✅ DEVE FUNZIONARE AL PRIMO TENTATIVO
```

---

## 🔍 TROUBLESHOOTING

### Problema: Restart ancora fallisce

**Soluzione:**
```bash
# 1. Doppio cleanup
python3 cleanup_servers.py force
sleep 2
python3 cleanup_servers.py force

# 2. Verifica porte con fuser
sudo fuser 3000/tcp 5000/tcp 8001/tcp 8765/tcp -k

# 3. Riavvia
./restart_all.sh
```

### Problema: Auth Server non parte

**Debug:**
```bash
# Leggi il log
tail -50 auth_server.log

# Possibili cause:
# - DATABASE_URL non configurata (se usi PostgreSQL)
# - Porta 5000 occupata da altro processo
# - Credenziali database sbagliate
```

**Fix:**
```bash
# Se porta occupata
sudo lsof -i :5000
# Nota il PID
kill -9 <PID>

# Se database down
# - Verifica DATABASE_URL in .env
# - Verifica che database sia online
# - Se usi SQLite, verifica permessi file

./restart_all.sh
```

### Problema: Login ancora fallisce al primo tentativo

**Questo non dovrebbe succedere!** Se accade:

```bash
# 1. Verifica log login
tail -100 auth_server.log | grep "🔐"

# 2. Cerca "PROBLEMA DATABASE"
# Se lo vedi, il database ha problemi di connessione

# 3. Verifica stato:
python3 cleanup_servers.py status

# 4. Se Auth Server non è attivo:
ps aux | grep auth_server
# Dovrebbe mostrare SOLO 1 processo (o 2 con reloader)

# 5. Se ce ne sono multipli:
python3 cleanup_servers.py auth
sleep 2
./restart_all.sh
```

---

## 📊 VERIFICA DEL DEPLOYMENT

### Checklist Post-Deployment

- [ ] `python3 cleanup_servers.py status` mostra ✅ tutti i server ATTIVI
- [ ] Porta 5000 ha Auth Server (controllare con `ss -tlnp | grep 5000`)
- [ ] Login tramite UI funziona al PRIMO tentativo
- [ ] Non ci sono processi python duplicati (`ps aux | grep python | wc -l` < 10)
- [ ] File log sono presenti:
  ```bash
  ls -lh *.log
  # auth_server.log
  # api_server.log
  # webapp_server.log
  # websocket_server.log
  ```

---

## 📖 FILE IMPORTANTI

### File Modificati
- **start_webapp.py** - Porta hardcoded 3000 (non ricerca dinamica)
- **auth_server.py** - DB lock, retry logic, logging dettagliato
- **cleanup_servers.py** - Pulizia più aggressiva
- **restart_all.sh** - Ordine di avvio critico

### File di Riferimento
- **DOPPIO_LOGIN_SOLUZIONE_v2.md** - Documentazione completa
- **SOLUZIONE_DOPPIO_LOGIN.md** - Soluzione precedente (v1.0)

---

## 🔄 RIAVVIO PERIODICO

Configurare riavvio giornaliero (cron):

```bash
# Apri crontab
crontab -e

# Aggiungi (riavvio ogni giorno alle 2:00 AM):
0 2 * * * cd /var/www/html/kimerika.cloud && python3 cleanup_servers.py force && ./restart_all.sh > /tmp/kimerika-restart.log 2>&1

# Oppure (ogni giorno alle 3:00 AM):
0 3 * * * cd /var/www/html/kimerika.cloud && ./restart_all.sh > /tmp/kimerika-restart.log 2>&1
```

---

## 📞 SUPPORT CHECKLIST

Se continua il problema, fornire:

1. **Output status:**
   ```bash
   python3 cleanup_servers.py status
   ```

2. **Log auth:**
   ```bash
   tail -50 auth_server.log
   ```

3. **Processi attivi:**
   ```bash
   ps aux | grep python
   ```

4. **Porte:**
   ```bash
   ss -tlnp
   ```

5. **Database check:**
   ```bash
   # Se usi PostgreSQL:
   psql -U postgres -d kimerika_db -c "SELECT 1;"
   
   # Se usi SQLite:
   sqlite3 kimerika.db "SELECT 1;"
   ```

---

## ✅ NEXT STEPS

1. Eseguire Step 1-5 di sopra
2. Attendere conferma che tutto è ✅
3. Aprire browser e testare login
4. Se tutto OK → Deployment completo!
5. Se problemi → Eseguire Troubleshooting

---

**VERSIONE:** 2.0  
**DATA:** 12 Aprile 2026  
**STATUS:** ✅ Production Ready
