# 🔐 Guida Completa all'Integrazione OAuth

## Google Sign-In e Apple Sign-In per Kimerika Cloud

---

## 📋 Indice

1. [Panoramica](#panoramica)
2. [Configurazione Google OAuth](#configurazione-google-oauth)
3. [Configurazione Apple Sign In](#configurazione-apple-sign-in)
4. [Configurazione Backend](#configurazione-backend)
5. [Test e Verifica](#test-e-verifica)
6. [Troubleshooting](#troubleshooting)

---

## 📖 Panoramica

L'autenticazione OAuth è già implementata nel codice di Kimerika Cloud. Questa guida ti aiuterà a configurare le credenziali necessarie per Google e Apple.

### ✅ Cosa è già implementato:

- ✓ Frontend con pulsanti Google e Apple
- ✓ Backend con endpoints OAuth completi
- ✓ Gestione utenti con OAuth ID
- ✓ Redirect e callback handlers

### 🔧 Cosa devi configurare:

- ⚙️ Credenziali Google OAuth
- ⚙️ Credenziali Apple Sign In
- ⚙️ Variabili d'ambiente

---

## 🔵 Configurazione Google OAuth

### Passo 1: Crea un Progetto Google Cloud

1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Clicca su "Seleziona un progetto" > "Nuovo progetto"
3. Nome progetto: `Kimerika Cloud Auth`
4. Clicca "Crea"

### Passo 2: Abilita Google+ API

1. Nel menu laterale, vai su "API e servizi" > "Libreria"
2. Cerca "Google+ API"
3. Clicca "Abilita"

### Passo 3: Configura la Schermata di Consenso OAuth

1. Vai su "API e servizi" > "Schermata consenso OAuth"
2. Seleziona "Esterno" (o "Interno" se hai Google Workspace)
3. Clicca "Crea"
4. Compila il modulo:
   - **Nome applicazione**: Kimerika Cloud
   - **Email assistenza utente**: tua-email@gmail.com
   - **Logo applicazione**: (opzionale)
   - **Domini autorizzati**:
     - `kimerika.cloud`
     - `localhost` (per test)
   - **Email contatto sviluppatore**: tua-email@gmail.com
5. Clicca "Salva e continua"
6. **Ambiti**: Aggiungi questi ambiti:
   - `openid`
   - `email`
   - `profile`
7. Clicca "Salva e continua"
8. **Utenti test**: Aggiungi email per test (solo in modalità sviluppo)
9. Clicca "Salva e continua"

### Passo 4: Crea Credenziali OAuth 2.0

1. Vai su "API e servizi" > "Credenziali"
2. Clicca "+ CREA CREDENZIALI" > "ID client OAuth 2.0"
3. Tipo di applicazione: **Applicazione web**
4. Nome: `Kimerika Web Client`
5. **URI di reindirizzamento autorizzati**:
   ```
   http://localhost:3000/api/auth/google/callback
   http://localhost:5000/api/auth/google/callback
   https://kimerika.cloud/api/auth/google/callback
   ```
6. Clicca "Crea"
7. **IMPORTANTE**: Copia il **Client ID** e il **Client secret**

### Passo 5: Aggiorna il file .env

Apri `/var/www/html/kimerika.cloud/.env` e aggiorna:

```bash
GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuvwxyz
```

---

## 🍎 Configurazione Apple Sign In

### Passo 1: Iscrizione Apple Developer Program

> ⚠️ **Nota**: Apple Sign In richiede un account Apple Developer ($99/anno)

1. Vai su [Apple Developer](https://developer.apple.com/programs/)
2. Iscriviti al programma se non sei già iscritto

### Passo 2: Crea un App ID

1. Vai su [Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/)
2. Clicca "Identifiers" > "+"
3. Seleziona "App IDs" > "Continue"
4. Tipo: "App"
5. Compila:
   - **Description**: Kimerika Cloud
   - **Bundle ID**: `com.kimerika.cloud`
6. **Capabilities**: Abilita "Sign in with Apple"
7. Clicca "Continue" > "Register"

### Passo 3: Crea un Service ID

1. Vai su "Identifiers" > "+"
2. Seleziona "Services IDs" > "Continue"
3. Compila:
   - **Description**: Kimerika Cloud Web Auth
   - **Identifier**: `com.kimerika.cloud.signin`
4. Abilita "Sign in with Apple"
5. Clicca "Configure"
6. Seleziona il Primary App ID creato sopra
7. **Domains and Subdomains**:
   ```
   kimerika.cloud
   localhost
   ```
8. **Return URLs**:
   ```
   http://localhost:3000/api/auth/apple/callback
   http://localhost:5000/api/auth/apple/callback
   https://kimerika.cloud/api/auth/apple/callback
   ```
9. Clicca "Save" > "Continue" > "Register"

### Passo 4: Crea una Key per Sign in with Apple

1. Vai su "Keys" > "+"
2. **Key Name**: Kimerika Apple Sign In Key
3. Abilita "Sign in with Apple"
4. Clicca "Configure" e seleziona il Primary App ID
5. Clicca "Save" > "Continue" > "Register"
6. **IMPORTANTE**: Scarica la chiave (file .p8)
   - ⚠️ Puoi scaricarla **solo una volta**!
   - Salva il file come `AuthKey_ABCDEFGHIJ.p8`
   - Annota il **Key ID** (es: ABCDEFGHIJ)
7. Trova il tuo **Team ID**:
   - Vai su "Membership" nel menu laterale
   - Copia il **Team ID** (10 caratteri alfanumerici)

### Passo 5: Genera il Client Secret

Apple richiede un JWT come client secret. Usa lo script Python:

```bash
cd /var/www/html/kimerika.cloud
python3 scripts/generate_apple_client_secret.py
```

Oppure manualmente con questo codice:

```python
import jwt
import time

# Configurazione
TEAM_ID = "ABC123XYZ"  # Il tuo Team ID
CLIENT_ID = "com.kimerika.cloud.signin"  # Il tuo Service ID
KEY_ID = "ABCDEFGHIJ"  # Il tuo Key ID
PRIVATE_KEY_FILE = "AuthKey_ABCDEFGHIJ.p8"  # Path alla chiave

# Leggi la chiave privata
with open(PRIVATE_KEY_FILE, 'r') as f:
    private_key = f.read()

# Genera JWT
headers = {
    'kid': KEY_ID,
    'alg': 'ES256'
}

payload = {
    'iss': TEAM_ID,
    'iat': int(time.time()),
    'exp': int(time.time()) + 15777000,  # 6 mesi
    'aud': 'https://appleid.apple.com',
    'sub': CLIENT_ID
}

client_secret = jwt.encode(payload, private_key, algorithm='ES256', headers=headers)
print(f"\nAPPLE_CLIENT_SECRET={client_secret}\n")
```

### Passo 6: Aggiorna il file .env

```bash
APPLE_CLIENT_ID=com.kimerika.cloud.signin
APPLE_CLIENT_SECRET=eyJhbGciOiJFUzI1NiIsImtpZCI6IkFCQ0RFRkdISUoifQ...
APPLE_TEAM_ID=ABC123XYZ
APPLE_KEY_ID=ABCDEFGHIJ
```

---

## 🔧 Configurazione Backend

### Verifica Dipendenze

Assicurati che tutte le dipendenze siano installate:

```bash
cd /var/www/html/kimerika.cloud
pip install -r requirements_auth.txt
```

Il file `requirements_auth.txt` dovrebbe contenere:

```txt
Flask==2.3.3
Flask-CORS==4.0.0
Flask-SQLAlchemy==3.0.5
Authlib==1.2.1
python-dotenv==1.0.0
PyJWT==2.8.0
cryptography==41.0.4
requests==2.31.0
```

### Verifica Configurazione Database

Il database deve avere i campi OAuth:

```bash
# Entra nella shell Python
python3

# Esegui i comandi:
from auth_server import app, db
with app.app_context():
    db.create_all()
    print("✓ Database aggiornato con campi OAuth")
```

### Riavvia il Server di Autenticazione

```bash
# Termina il processo esistente
pkill -f auth_server.py

# Avvia il nuovo server
cd /var/www/html/kimerika.cloud
python3 auth_server.py
```

Il server dovrebbe avviarsi su `http://localhost:5000`

---

## ✅ Test e Verifica

### Test 1: Verifica Endpoint

```bash
# Verifica che il server risponda
curl http://localhost:5000/api/health

# Dovrebbe restituire: {"status": "ok"}
```

### Test 2: Test Google OAuth (Browser)

1. Apri [http://localhost:3000](http://localhost:3000)
2. Clicca "Accedi"
3. Clicca "Continua con Google"
4. Dovresti essere reindirizzato a Google
5. Seleziona il tuo account
6. Accetta i permessi
7. Dovresti essere reindirizzato alla dashboard

### Test 3: Test Apple Sign In (Browser)

1. Apri [http://localhost:3000](http://localhost:3000)
2. Clicca "Registrati"
3. Clicca "Registrati con Apple"
4. Dovresti essere reindirizzato alla pagina Apple
5. Inserisci Apple ID e password
6. Accetta i permessi
7. Dovresti essere reindirizzato alla dashboard

### Test 4: Verifica Database

```bash
python3
```

```python
from auth_server import app, db, User
with app.app_context():
    # Controlla utenti OAuth
    google_users = User.query.filter(User.google_id != None).all()
    apple_users = User.query.filter(User.apple_id != None).all()

    print(f"Utenti Google: {len(google_users)}")
    print(f"Utenti Apple: {len(apple_users)}")

    # Mostra dettagli
    for user in google_users:
        print(f"  - {user.email} (Google ID: {user.google_id})")

    for user in apple_users:
        print(f"  - {user.email} (Apple ID: {user.apple_id})")
```

---

## 🐛 Troubleshooting

### Problema: "Redirect URI mismatch" (Google)

**Soluzione**:

1. Verifica che l'URI in `.env` corrisponda esattamente a quello configurato in Google Cloud Console
2. Assicurati di includere:
   - `http://` o `https://`
   - Porta (se non standard)
   - Path completo: `/api/auth/google/callback`

### Problema: "Invalid client" (Google)

**Soluzione**:

1. Verifica che `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` siano corretti
2. Riavvia il server dopo aver modificato `.env`
3. Controlla che il progetto Google Cloud sia attivo

### Problema: "Invalid client_secret" (Apple)

**Soluzione**:

1. Il client secret Apple scade dopo 6 mesi, rigeneralo
2. Verifica che il JWT sia generato correttamente
3. Controlla che Team ID, Key ID e Client ID siano corretti
4. Assicurati che la chiave privata (.p8) sia quella corretta

### Problema: "User info not found"

**Soluzione**:

1. Verifica che gli scope includano `email` e `profile`
2. Controlla i log del server per errori dettagliati
3. Assicurati che l'utente abbia accettato i permessi

### Problema: "CORS error"

**Soluzione**:

```python
# In auth_server.py, verifica CORS:
from flask_cors import CORS
CORS(app, origins=['http://localhost:3000', 'https://kimerika.cloud'])
```

### Problema: "Database not found"

**Soluzione**:

```bash
cd /var/www/html/kimerika.cloud
python3 -c "from auth_server import app, db; app.app_context().push(); db.create_all(); print('✓ Database creato')"
```

---

## 📝 Note di Sicurezza

### ✅ Best Practices

1. **Mai committare credenziali**: `.env` deve essere in `.gitignore`
2. **Usa HTTPS in produzione**: OAuth richiede connessioni sicure
3. **Rigenera secret periodicamente**: Cambia i secret ogni 6 mesi
4. **Limita scope OAuth**: Richiedi solo i permessi necessari
5. **Valida sempre i token**: Non fidarti mai dei dati non verificati
6. **Logging**: Monitora tentativi di accesso sospetti

### 🔒 Per la Produzione

Prima di andare in produzione:

1. Cambia `FLASK_ENV=production` in `.env`
2. Imposta `FLASK_DEBUG=0`
3. Genera nuove chiavi segrete:
   ```bash
   openssl rand -hex 32
   ```
4. Configura un reverse proxy (nginx/Apache)
5. Usa un database PostgreSQL/MySQL
6. Abilita rate limiting
7. Implementa 2FA per account amministratori

---

## 📚 Risorse Utili

- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Apple Sign In Documentation](https://developer.apple.com/sign-in-with-apple/)
- [Authlib Documentation](https://docs.authlib.org/)
- [Flask-SQLAlchemy Documentation](https://flask-sqlalchemy.palletsprojects.com/)

---

## 🎉 Conclusione

L'integrazione OAuth è completa! Gli utenti possono ora:

- ✓ Accedere con il loro account Google
- ✓ Accedere con il loro account Apple
- ✓ Registrarsi rapidamente senza password
- ✓ Avere un'esperienza di login sicura e veloce

Per supporto: support@kimerika.cloud
