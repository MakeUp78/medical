# 🚀 Test Rapido OAuth - Kimerika Cloud

## ✅ Checklist Implementazione

### Frontend

- ✓ Pulsanti "Continua con Google" presenti
- ✓ Pulsanti "Continua con Apple" presenti
- ✓ Handler JavaScript configurati
- ✓ Gestione callback OAuth

### Backend

- ✓ Endpoints `/api/auth/google/login` e `/api/auth/google/signup`
- ✓ Endpoints `/api/auth/apple/login` e `/api/auth/apple/signup`
- ✓ Gestione callback con parametro `plan`
- ✓ Database con campi `google_id` e `apple_id`
- ✓ Integrazione Authlib per OAuth

---

## 🧪 Test Senza Configurazione OAuth

Puoi testare il frontend anche senza configurare le credenziali OAuth:

```bash
# 1. Avvia il server di autenticazione
cd /var/www/html/kimerika.cloud
python3 auth_server.py

# 2. In un altro terminale, avvia il frontend
python3 start_webapp.py

# 3. Apri il browser
# http://localhost:3000
```

**Cosa vedrai:**

- ✓ I pulsanti OAuth sono visibili e stilizzati
- ✓ Cliccando, vedrai un errore (normale, credenziali non configurate)
- ✓ Questo conferma che il frontend è integrato correttamente

---

## 🔧 Test Con Configurazione OAuth

### Prerequisiti

1. **Installa le dipendenze**:

   ```bash
   pip install -r requirements_auth.txt
   ```

2. **Verifica dipendenze chiave**:
   ```bash
   python3 -c "import authlib; print('✓ Authlib:', authlib.__version__)"
   python3 -c "import jwt; print('✓ PyJWT:', jwt.__version__)"
   python3 -c "from flask_sqlalchemy import SQLAlchemy; print('✓ Flask-SQLAlchemy')"
   ```

### Test Google OAuth

1. **Configura le credenziali** (vedi `OAUTH_SETUP_GUIDE.md`)
2. **Aggiorna `.env`**:

   ```bash
   GOOGLE_CLIENT_ID=tuo-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=tuo-client-secret
   ```

3. **Riavvia il server**:

   ```bash
   pkill -f auth_server
   python3 auth_server.py
   ```

4. **Test nel browser**:
   - Vai su http://localhost:3000
   - Clicca "Accedi" > "Continua con Google"
   - Dovresti essere reindirizzato a Google
   - Dopo l'autenticazione, torni alla dashboard

### Test Apple Sign In

1. **Configura le credenziali** (vedi `OAUTH_SETUP_GUIDE.md`)
2. **Genera il client secret**:

   ```bash
   python3 scripts/generate_apple_client_secret.py
   ```

3. **Aggiorna `.env`** con l'output dello script

4. **Riavvia il server e testa come sopra**

---

## 🐛 Debug

### Verifica che il server di autenticazione sia attivo

```bash
# Controlla che sia in esecuzione
ps aux | grep auth_server.py

# Testa l'endpoint di health
curl http://localhost:5000/api/health
```

### Verifica database

```bash
python3 << 'EOF'
from auth_server import app, db, User
with app.app_context():
    users = User.query.all()
    print(f"Utenti totali: {len(users)}")
    for user in users:
        oauth_methods = []
        if user.google_id:
            oauth_methods.append("Google")
        if user.apple_id:
            oauth_methods.append("Apple")
        oauth_str = f" ({', '.join(oauth_methods)})" if oauth_methods else ""
        print(f"  - {user.email}{oauth_str}")
EOF
```

### Controlla i log del server

```bash
# Se il server è in esecuzione, i log appariranno nel terminale
# Cerca errori come:
# - "Invalid client"
# - "Redirect URI mismatch"
# - "Token validation failed"
```

### Test degli endpoint direttamente

```bash
# Verifica che gli endpoint rispondano
curl http://localhost:5000/api/auth/google/login
# Dovrebbe reindirizzare a Google (302)

curl http://localhost:5000/api/auth/apple/login
# Dovrebbe reindirizzare a Apple (302)
```

---

## 📊 Monitoraggio Utenti OAuth

Script per vedere gli utenti che hanno usato OAuth:

```python
from auth_server import app, db, User
from datetime import datetime

with app.app_context():
    print("\n" + "="*60)
    print("  📊 STATISTICHE UTENTI OAUTH")
    print("="*60 + "\n")

    total = User.query.count()
    google_users = User.query.filter(User.google_id != None).count()
    apple_users = User.query.filter(User.apple_id != None).count()
    standard_users = total - google_users - apple_users

    print(f"Utenti totali:     {total}")
    print(f"  - Standard:      {standard_users}")
    print(f"  - Google OAuth:  {google_users}")
    print(f"  - Apple OAuth:   {apple_users}")
    print()

    # Ultimi 5 accessi OAuth
    print("Ultimi 5 accessi OAuth:")
    oauth_users = User.query.filter(
        (User.google_id != None) | (User.apple_id != None)
    ).order_by(User.last_login.desc()).limit(5).all()

    for user in oauth_users:
        provider = "Google" if user.google_id else "Apple"
        last_login = user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Mai"
        print(f"  [{provider}] {user.email} - {last_login}")
    print()
```

Salva come `check_oauth_users.py` ed esegui:

```bash
python3 check_oauth_users.py
```

---

## ✅ Cosa Verificare

### Nel Browser (Console JavaScript)

1. Apri DevTools (F12)
2. Vai sulla tab "Console"
3. Clicca su un pulsante OAuth
4. Dovresti vedere: `Reindirizzamento a Google...` o `Reindirizzamento a Apple...`

### Nel Server (Logs)

Quando avvii `auth_server.py`, dovresti vedere:

```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

Quando un utente usa OAuth, vedrai:

```
127.0.0.1 - - [18/Dec/2025 12:34:56] "GET /api/auth/google/login HTTP/1.1" 302 -
127.0.0.1 - - [18/Dec/2025 12:35:02] "GET /api/auth/google/callback?code=... HTTP/1.1" 302 -
```

### Nel Database

```bash
sqlite3 kimerika.db "SELECT email, google_id, apple_id FROM user WHERE google_id IS NOT NULL OR apple_id IS NOT NULL;"
```

---

## 🎯 Test Completo End-to-End

### Scenario 1: Registrazione con Google

1. Vai su landing page
2. Clicca "Inizia Gratis"
3. Clicca "Registrati con Google"
4. Seleziona account Google
5. Accetta permessi
6. Verifica reindirizzamento a dashboard
7. Controlla che l'utente sia nel database con `google_id`

### Scenario 2: Login con Account Esistente

1. Crea un account standard (email + password)
2. Logout
3. Clicca "Accedi" > "Continua con Google"
4. Usa la **stessa email** dell'account standard
5. Verifica che l'account venga collegato (campo `google_id` popolato)

### Scenario 3: Selezione Piano durante Registrazione

1. Nella landing page, clicca "Inizia Gratis" su un piano specifico (es. Professional)
2. Clicca "Registrati con Google"
3. Completa autenticazione
4. Verifica nel database che `plan='professional'`

---

## 🚨 Problemi Comuni

### Errore: "Module 'authlib' not found"

```bash
pip install Authlib
```

### Errore: "Client not registered"

```bash
# Verifica che le credenziali siano nel file .env
cat .env | grep GOOGLE_CLIENT_ID
cat .env | grep APPLE_CLIENT_ID
```

### Errore: "Redirect URI mismatch"

- Verifica che l'URI in Google Cloud Console sia **esattamente**:
  `http://localhost:3000/api/auth/google/callback`
- Nota: Nessuno spazio, slash finale, o porta diversa

### OAuth non funziona su localhost

- Alcuni provider OAuth richiedono HTTPS anche in sviluppo
- Usa ngrok per testare:
  ```bash
  ngrok http 3000
  # Aggiorna gli URI di redirect con l'URL ngrok
  ```

---

## 📝 Checklist Finale

Prima di andare in produzione:

- [ ] Credenziali OAuth configurate e testate
- [ ] File `.env` non committato (in `.gitignore`)
- [ ] URI di redirect aggiornati per dominio produzione
- [ ] Database configurato (PostgreSQL/MySQL, non SQLite)
- [ ] HTTPS abilitato
- [ ] Rate limiting configurato
- [ ] Monitoring e logging attivi
- [ ] Backup database configurato

---

## 🎉 Conclusione

L'implementazione OAuth è completa! Gli utenti possono ora:

- ✅ Registrarsi con Google in 2 click
- ✅ Registrarsi con Apple in 2 click
- ✅ Collegare account OAuth a account esistenti
- ✅ Esperienza di login veloce e sicura

Per configurazione dettagliata, vedi: **`OAUTH_SETUP_GUIDE.md`**
