# 🏥 FacialMed Pro - Landing Page & Sistema di Autenticazione

Landing page professionale di vendita con sistema completo di autenticazione per la webapp di analisi facciale medicale.

## ✨ Caratteristiche

### Landing Page
- 🎨 Design moderno e professionale
- 📱 Completamente responsive
- ⚡ Animazioni fluide e accattivanti
- 🎯 Sezioni ottimizzate per la conversione:
  - Hero section con statistiche
  - Funzionalità principali
  - Come funziona (3 step)
  - Piani tariffari (Starter, Professional, Enterprise)
  - Testimonianze
  - Call-to-Action finale

### Sistema di Autenticazione
- ✅ Registrazione utenti con validazione
- ✅ Login con email e password
- ✅ Recupero password via email
- ✅ Login con Google OAuth 2.0
- ✅ Login con Apple Sign In
- 🔒 JWT token-based authentication
- 💾 Database SQLite (facile upgrade a PostgreSQL)
- 🔐 Password hashing con Werkzeug
- 📊 Gestione piani e limiti utilizzo
- ⏰ Trial period di 14 giorni

## 📁 Struttura File

```
medical/
├── webapp/
│   ├── landing.html              # Landing page principale
│   └── static/
│       ├── css/
│       │   └── landing.css       # Stili landing page
│       └── js/
│           └── landing.js        # JavaScript landing page
├── auth_server.py                # Backend Flask autenticazione
├── requirements_auth.txt         # Dipendenze Python backend
├── start_auth_server.bat         # Script avvio server auth
├── .env.example                  # Template variabili ambiente
└── LANDING_README.md             # Questa documentazione
```

## 🚀 Installazione e Avvio

### 1. Installa le Dipendenze

```bash
# Attiva virtual environment (se non già attivo)
.\venv\Scripts\activate

# Installa dipendenze backend
pip install -r requirements_auth.txt
```

### 2. Configura le Variabili d'Ambiente

Copia `.env.example` in `.env` e configura le tue credenziali:

```bash
cp .env.example .env
```

Modifica `.env` con i tuoi valori:

```env
# Secret keys (genera nuove chiavi per produzione!)
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Google OAuth (opzionale)
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx

# Apple Sign In (opzionale)
APPLE_CLIENT_ID=xxx
APPLE_CLIENT_SECRET=xxx

# Email per recupero password (opzionale)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. Avvia i Server

**Opzione A: Usando gli script batch (Windows)**

```bash
# Terminal 1: Avvia il server di autenticazione
.\start_auth_server.bat

# Terminal 2: Avvia il server webapp
.\start_webapp.bat
```

**Opzione B: Manualmente**

```bash
# Terminal 1: Server autenticazione (porta 5000)
python auth_server.py

# Terminal 2: Server webapp (porta 3000)
python start_webapp.py
```

### 4. Accedi alla Landing Page

Apri il browser e vai su:
- **Landing Page**: http://localhost:3000/landing.html
- **Webapp**: http://localhost:3000/index.html
- **API Auth**: http://localhost:5000/api

## 🔧 Configurazione OAuth

### Google OAuth

1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuovo progetto o seleziona uno esistente
3. Abilita "Google+ API"
4. Vai su "Credenziali" → "Crea credenziali" → "ID client OAuth 2.0"
5. Configura schermata consenso OAuth
6. Aggiungi URI di reindirizzamento autorizzati:
   - `http://localhost:5000/api/auth/google/callback`
   - `https://tuodominio.com/api/auth/google/callback` (produzione)
7. Copia Client ID e Client Secret nel file `.env`

### Apple Sign In

1. Vai su [Apple Developer](https://developer.apple.com/)
2. Registra un nuovo App ID
3. Abilita "Sign in with Apple"
4. Crea un Service ID
5. Configura domini e URL di ritorno:
   - `http://localhost:5000/api/auth/apple/callback`
   - `https://tuodominio.com/api/auth/apple/callback` (produzione)
6. Genera una chiave privata (.p8)
7. Configura Client ID e Secret nel file `.env`

### Email SMTP (Gmail)

1. Vai nelle impostazioni del tuo account Google
2. Abilita autenticazione a due fattori
3. Genera una "Password per le app"
4. Usa quella password nel campo `SMTP_PASSWORD` del file `.env`

## 📡 API Endpoints

### Autenticazione

```http
POST /api/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "firstname": "Mario",
  "lastname": "Rossi",
  "plan": "starter"  // opzionale: starter, professional, enterprise
}
```

```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "remember": true  // opzionale
}
```

```http
POST /api/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

```http
GET /api/auth/verify
Authorization: Bearer <token>
```

### OAuth

```http
GET /api/auth/google/login
# Reindirizza a Google OAuth
```

```http
GET /api/auth/apple/login
# Reindirizza a Apple Sign In
```

### Profilo Utente

```http
GET /api/user/profile
Authorization: Bearer <token>
```

```http
PUT /api/user/profile
Authorization: Bearer <token>
Content-Type: application/json

{
  "firstname": "Mario",
  "lastname": "Rossi"
}
```

```http
GET /api/user/usage
Authorization: Bearer <token>
```

## 🎨 Personalizzazione

### Colori e Branding

Modifica le variabili CSS in [webapp/static/css/landing.css](webapp/static/css/landing.css):

```css
:root {
    --primary: #6366f1;        /* Colore primario */
    --primary-dark: #4f46e5;   /* Colore primario scuro */
    --secondary: #10b981;       /* Colore secondario */
    /* ... */
}
```

### Contenuti

Modifica i testi direttamente in [webapp/landing.html](webapp/landing.html):
- Hero title e description
- Funzionalità
- Prezzi dei piani
- Testimonianze
- Footer

### Logo

Sostituisci l'emoji 🏥 con il tuo logo:

```html
<!-- In landing.html -->
<div class="logo">
    <img src="static/img/logo.png" alt="Logo" class="logo-icon">
    <span class="logo-text">FacialMed<span class="pro">Pro</span></span>
</div>
```

## 💾 Database

Il sistema usa SQLite di default (`facialmed.db`). Per passare a PostgreSQL:

1. Installa psycopg2:
   ```bash
   pip install psycopg2-binary
   ```

2. Modifica la connessione in `auth_server.py`:
   ```python
   app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/facialmed'
   ```

3. O usa variabile d'ambiente:
   ```env
   DATABASE_URL=postgresql://user:password@localhost/facialmed
   ```

### Schema Database

**Tabella `user`:**
- `id` - Primary key
- `email` - Email univoca
- `password_hash` - Password hashata
- `firstname` - Nome
- `lastname` - Cognome
- `plan` - Piano sottoscritto (starter/professional/enterprise)
- `google_id` - ID Google (OAuth)
- `apple_id` - ID Apple (OAuth)
- `is_active` - Account attivo
- `created_at` - Data creazione
- `last_login` - Ultimo accesso
- `trial_ends_at` - Fine trial
- `analyses_count` - Numero analisi effettuate
- `analyses_limit` - Limite analisi per piano

**Tabella `password_reset_token`:**
- `id` - Primary key
- `user_id` - Foreign key a user
- `token` - Token univoco
- `created_at` - Data creazione
- `expires_at` - Data scadenza
- `used` - Token utilizzato

## 🔒 Sicurezza

### Produzione

Prima di andare in produzione:

1. **Cambia le secret key**:
   ```python
   import secrets
   print(secrets.token_hex(32))  # Genera nuova chiave
   ```

2. **Usa HTTPS**: Configura certificato SSL

3. **Configura CORS** appropriatamente in `auth_server.py`

4. **Usa database PostgreSQL** invece di SQLite

5. **Abilita rate limiting**:
   ```bash
   pip install Flask-Limiter
   ```

6. **Configura logging** e monitoraggio errori

7. **Backup regolari** del database

## 📊 Piani Tariffari

| Piano | Analisi/mese | Prezzo | Limiti |
|-------|--------------|--------|--------|
| **Starter** | 50 | €29/mese | Report base, supporto email |
| **Professional** | 200 | €79/mese | Report avanzati, API limitato, supporto prioritario |
| **Enterprise** | Illimitate | €199/mese | White-label, API completo, supporto 24/7 |

Tutti i piani includono 14 giorni di trial gratuito.

## 🐛 Troubleshooting

### Il server auth non si avvia

Verifica che:
- Le dipendenze siano installate: `pip install -r requirements_auth.txt`
- La porta 5000 sia libera
- Il virtual environment sia attivato

### OAuth non funziona

Verifica:
- Le credenziali OAuth siano corrette nel file `.env`
- Gli URI di callback siano configurati correttamente nelle console OAuth
- Il server sia raggiungibile dall'URL configurato

### Email non viene inviata

Verifica:
- Le credenziali SMTP nel file `.env`
- Se usi Gmail, che la password sia una "Password per le app"
- Che il firewall non blocchi la porta SMTP

## 📈 Prossimi Passi

1. **Integra con la webapp esistente**: Proteggi gli endpoint della webapp con JWT
2. **Aggiungi pagamento**: Integra Stripe o PayPal per i piani a pagamento
3. **Dashboard utente**: Crea pagina profilo con statistiche
4. **Admin panel**: Interfaccia per gestire utenti e piani
5. **Analytics**: Integra Google Analytics o Plausible
6. **Email marketing**: Integra Mailchimp o SendGrid
7. **Chat support**: Aggiungi widget di supporto (Intercom, Crisp)

## 📝 Licenza

Questo progetto è parte dell'applicazione FacialMed Pro.

## 🆘 Supporto

Per problemi o domande, apri un issue o contatta il team di sviluppo.

---

**Creato con ❤️ per FacialMed Pro**
