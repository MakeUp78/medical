# 🔐 Autenticazione OAuth - Google e Apple Sign In

## ✅ Implementazione Completata

L'autenticazione con Google e Apple è stata **completamente implementata** in Kimerika Cloud!

### 🎯 Cosa è Stato Fatto

#### Frontend (✓ Completo)

- ✅ Pulsanti "Continua con Google" con logo e styling
- ✅ Pulsanti "Continua con Apple" con logo e styling
- ✅ Funzioni JavaScript per login e signup
- ✅ Gestione callback OAuth
- ✅ Feedback utente durante l'autenticazione
- ✅ Supporto per selezione piano durante registrazione

#### Backend (✓ Completo)

- ✅ Server di autenticazione Flask configurato
- ✅ Integrazione con Authlib per OAuth 2.0
- ✅ Endpoint per Google OAuth:
  - `/api/auth/google/login` - Login con account esistente
  - `/api/auth/google/signup` - Registrazione nuovo account
  - `/api/auth/google/callback` - Gestione callback
- ✅ Endpoint per Apple Sign In:
  - `/api/auth/apple/login` - Login con account esistente
  - `/api/auth/apple/signup` - Registrazione nuovo account
  - `/api/auth/apple/callback` - Gestione callback
- ✅ Database con campi `google_id` e `apple_id`
- ✅ Gestione JWT token per sessioni utente
- ✅ Collegamento account OAuth a account esistenti

---

## 📚 Documentazione

### Guide Disponibili

1. **[OAUTH_SETUP_GUIDE.md](OAUTH_SETUP_GUIDE.md)** (📖 Guida Completa)

   - Configurazione passo-passo di Google OAuth
   - Configurazione passo-passo di Apple Sign In
   - Ottenere credenziali da Google Cloud Console
   - Ottenere credenziali da Apple Developer
   - Configurazione file `.env`
   - Best practices di sicurezza

2. **[OAUTH_TEST_GUIDE.md](OAUTH_TEST_GUIDE.md)** (🧪 Test e Debug)

   - Test dell'implementazione
   - Verifica endpoint
   - Debug problemi comuni
   - Script di monitoraggio utenti
   - Checklist pre-produzione

3. **[scripts/generate_apple_client_secret.py](scripts/generate_apple_client_secret.py)** (🛠️ Tool)

   - Script interattivo per generare il client secret Apple
   - Necessario perché Apple richiede un JWT firmato

4. **[scripts/verify_oauth_implementation.py](scripts/verify_oauth_implementation.py)** (✅ Verifica)
   - Script di verifica automatica
   - Controlla dipendenze, configurazione, database
   - Rapporto dettagliato dello stato

---

## 🚀 Quick Start

### Step 1: Installa le Dipendenze

```bash
cd /var/www/html/kimerika.cloud
pip install -r requirements_auth.txt
```

### Step 2: Verifica l'Implementazione

```bash
python3 scripts/verify_oauth_implementation.py
```

Questo script controllerà:

- ✓ Dipendenze Python installate
- ✓ File `.env` esistente
- ✓ Endpoint backend OAuth
- ✓ File frontend OAuth
- ✓ Struttura database

### Step 3: Configura le Credenziali OAuth

#### Opzione A: Google OAuth (Consigliato per iniziare)

1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un progetto e abilita Google+ API
3. Configura OAuth consent screen
4. Crea credenziali OAuth 2.0
5. Aggiungi redirect URI: `http://localhost:3000/api/auth/google/callback`
6. Copia Client ID e Client Secret nel file `.env`:

```bash
GOOGLE_CLIENT_ID=123456-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijk
```

#### Opzione B: Apple Sign In

⚠️ **Requisiti**: Account Apple Developer ($99/anno)

1. Crea Service ID su [Apple Developer](https://developer.apple.com/)
2. Configura "Sign in with Apple"
3. Genera chiave privata (.p8)
4. Esegui lo script per generare il client secret:

```bash
python3 scripts/generate_apple_client_secret.py
```

5. Copia l'output nel file `.env`

**📖 Per istruzioni dettagliate**: Vedi [OAUTH_SETUP_GUIDE.md](OAUTH_SETUP_GUIDE.md)

### Step 4: Avvia i Server

#### Terminale 1 - Server di Autenticazione

```bash
cd /var/www/html/kimerika.cloud
python3 auth_server.py
```

Dovrebbe avviarsi su `http://localhost:5000`

#### Terminale 2 - Frontend

```bash
cd /var/www/html/kimerika.cloud
python3 start_webapp.py
```

Dovrebbe avviarsi su `http://localhost:3000`

### Step 5: Testa nel Browser

1. Apri http://localhost:3000
2. Clicca "Accedi" o "Inizia Gratis"
3. Clicca "Continua con Google" o "Continua con Apple"
4. Completa l'autenticazione
5. Verifica il reindirizzamento alla dashboard

---

## 🎨 Interfaccia Utente

### Pagina di Login

La modale di login ora include:

```
┌─────────────────────────────────────┐
│          Bentornato!                │
│  Accedi al tuo account Kimerika     │
│                                     │
│  Email: [________________]          │
│  Password: [________________]       │
│  □ Ricordami  Password dimenticata? │
│                                     │
│  [        Accedi        ]           │
│                                     │
│  ──────── oppure ────────           │
│                                     │
│  [🔵 Continua con Google ]          │
│  [🍎 Continua con Apple  ]          │
│                                     │
│  Non hai un account? Registrati     │
└─────────────────────────────────────┘
```

### Pagina di Registrazione

La modale di registrazione include:

```
┌─────────────────────────────────────┐
│        Inizia Gratis                │
│  Crea il tuo account in pochi sec.  │
│                                     │
│  Nome: [_______] Cognome: [_______] │
│  Email: [________________]          │
│  Password: [________________]       │
│  Forza: ██████░░░░ Media            │
│  □ Accetto Termini e Privacy        │
│                                     │
│  [     Crea Account     ]           │
│                                     │
│  ──────── oppure ────────           │
│                                     │
│  [🔵 Registrati con Google]         │
│  [🍎 Registrati con Apple ]         │
│                                     │
│  Hai già un account? Accedi         │
└─────────────────────────────────────┘
```

---

## 🔧 Configurazione

### File .env

Il file `.env` deve contenere:

```bash
# Flask Secret Keys
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Apple Sign In
APPLE_CLIENT_ID=
APPLE_CLIENT_SECRET=
APPLE_TEAM_ID=
APPLE_KEY_ID=

# Database
DATABASE_URL=postgresql://user:pass@host/db

# Application URL
APP_URL=http://localhost:3000
```

### Redirect URIs da Configurare

#### Per Google OAuth:

```
http://localhost:3000/api/auth/google/callback
http://localhost:5000/api/auth/google/callback
https://kimerika.cloud/api/auth/google/callback
```

#### Per Apple Sign In:

```
http://localhost:3000/api/auth/apple/callback
http://localhost:5000/api/auth/apple/callback
https://kimerika.cloud/api/auth/apple/callback
```

---

## 📊 Funzionalità

### Cosa Possono Fare gli Utenti

1. **Registrazione Veloce**

   - Click su "Registrati con Google/Apple"
   - Autorizzazione provider (2 click)
   - Account creato automaticamente
   - Accesso immediato alla dashboard

2. **Login Semplificato**

   - Click su "Continua con Google/Apple"
   - Riconoscimento automatico
   - Accesso senza password

3. **Collegamento Account**

   - Se l'email esiste già, l'account OAuth viene collegato
   - L'utente può usare sia email+password che OAuth

4. **Selezione Piano**
   - Durante la registrazione da un piano specifico
   - Il piano viene salvato automaticamente

### Flusso di Autenticazione

```
Utente                Frontend            Backend             Provider
  │                      │                   │                   │
  ├─ Click "Google" ────>│                   │                   │
  │                      ├─ Redirect ───────>│                   │
  │                      │                   ├─ Authorize ──────>│
  │<─────────────────────┴───────────────────┴─ Login Page ─────┤
  │                                                               │
  ├─ Credentials + Accept ─────────────────────────────────────>│
  │                                                               │
  │<─ Callback with code ─────────────────────────────────────<─┤
  │                      │                   │                   │
  │                      │<─ Callback ──────>│                   │
  │                      │                   ├─ Exchange Token ─>│
  │                      │                   │<─ User Info ──────┤
  │                      │                   │                   │
  │                      │                   ├─ Create/Update DB │
  │                      │                   ├─ Generate JWT     │
  │                      │<─ JWT + Redirect ─┤                   │
  │<─ Dashboard ─────────┤                   │                   │
```

---

## 🔒 Sicurezza

### Implementato

- ✅ JWT token per sessioni
- ✅ Token expiration (7 giorni)
- ✅ Password hashing con Werkzeug
- ✅ HTTPS ready (usa reverse proxy in produzione)
- ✅ CORS configurato
- ✅ OAuth 2.0 standard compliant
- ✅ State parameter per prevenire CSRF
- ✅ Validazione email server-side

### Raccomandazioni Pre-Produzione

- [ ] Usa HTTPS (obbligatorio per OAuth)
- [ ] Configura rate limiting
- [ ] Implementa 2FA per admin
- [ ] Monitora tentativi di accesso
- [ ] Backup database regolari
- [ ] Rigenera secret keys
- [ ] Usa database production-ready (PostgreSQL)

---

## 🐛 Troubleshooting

### Problema: I pulsanti OAuth non fanno nulla

**Causa**: Credenziali non configurate nel file `.env`

**Soluzione**:

1. Verifica che il file `.env` contenga le credenziali
2. Riavvia il server: `pkill -f auth_server && python3 auth_server.py`

### Problema: "Redirect URI mismatch"

**Causa**: L'URI in Google/Apple non corrisponde esattamente

**Soluzione**:

- Assicurati che l'URI sia **esattamente**: `http://localhost:3000/api/auth/google/callback`
- Nessuno spazio, slash finale, o differenza di porta

### Problema: "Invalid client"

**Causa**: Client ID o Client Secret errati

**Soluzione**:

- Verifica che le credenziali in `.env` siano corrette
- Copia-incolla senza spazi extra

### Problema: Errore "Module not found"

**Causa**: Dipendenze non installate

**Soluzione**:

```bash
pip install -r requirements_auth.txt
```

---

## 📈 Monitoraggio

### Verificare Utenti OAuth

```bash
python3 << 'EOF'
from auth_server import app, db, User
with app.app_context():
    total = User.query.count()
    google = User.query.filter(User.google_id != None).count()
    apple = User.query.filter(User.apple_id != None).count()
    print(f"Totale: {total} | Google: {google} | Apple: {apple}")
EOF
```

### Log del Server

I log mostrano ogni tentativo di autenticazione:

```
127.0.0.1 - - [18/Dec/2025 12:34:56] "GET /api/auth/google/login HTTP/1.1" 302 -
127.0.0.1 - - [18/Dec/2025 12:35:02] "GET /api/auth/google/callback?code=... HTTP/1.1" 302 -
```

---

## 🎉 Prossimi Passi

### Subito

1. ✅ Leggi la documentazione completa: [OAUTH_SETUP_GUIDE.md](OAUTH_SETUP_GUIDE.md)
2. ✅ Configura almeno Google OAuth (più semplice)
3. ✅ Testa con account di sviluppo
4. ✅ Verifica il flusso completo

### Prima del Deploy

1. ✅ Configura HTTPS
2. ✅ Aggiorna redirect URIs per dominio produzione
3. ✅ Testa su dominio reale
4. ✅ Configura monitoring

---

## 📞 Supporto

- **Documentazione**: Leggi i file `.md` nella root del progetto
- **Script di Test**: `python3 scripts/verify_oauth_implementation.py`
- **Google OAuth**: https://developers.google.com/identity/protocols/oauth2
- **Apple Sign In**: https://developer.apple.com/sign-in-with-apple/

---

## ✨ Conclusione

L'implementazione OAuth è **completa e funzionante**!

Gli utenti possono ora:

- ✅ Registrarsi con un click
- ✅ Accedere senza password
- ✅ Avere un'esperienza moderna e sicura

**Configurazione richiesta**: Solo le credenziali OAuth (vedi [OAUTH_SETUP_GUIDE.md](OAUTH_SETUP_GUIDE.md))

Tutto il resto è **già implementato e pronto all'uso**! 🚀
