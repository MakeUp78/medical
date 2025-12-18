# 👤 Sistema Gestione Profilo Utente - Kimerika Evolution

## 📋 Panoramica

Sistema completo per la gestione del profilo utente con funzionalità avanzate di personalizzazione, sicurezza e gestione abbonamenti.

## ✨ Funzionalità Implementate

### 1. **Panoramica Account**

- ✅ Visualizzazione completa informazioni utente
- ✅ Avatar personalizzabile con upload immagine
- ✅ Badge piano abbonamento
- ✅ Badge account OAuth collegati (Google/Apple)
- ✅ Statistiche utilizzo analisi
- ✅ Barra progresso utilizzo
- ✅ Informazioni trial attivo
- ✅ Data iscrizione e ultimo accesso

### 2. **Dati Personali**

- ✅ Modifica nome e cognome
- ✅ Email (visualizzazione, non modificabile)
- ✅ Telefono (opzionale)
- ✅ Bio personale (opzionale)
- ✅ Validazione input in tempo reale

### 3. **Sicurezza**

- ✅ Cambio password con validazione
- ✅ Indicatore forza password
- ✅ Toggle mostra/nascondi password
- ✅ Supporto cambio password per utenti OAuth
- ✅ Visualizzazione account collegati (Google/Apple)
- ✅ Verifica password corrente

### 4. **Avatar/Immagine Profilo**

- ✅ Upload immagine profilo
- ✅ Formati supportati: PNG, JPG, JPEG, GIF, WEBP
- ✅ Limite dimensione: 5MB
- ✅ Preview in tempo reale
- ✅ Eliminazione avatar
- ✅ Sincronizzazione con app principale

### 5. **Gestione Abbonamento**

- ✅ Visualizzazione piano corrente
- ✅ Dettagli scadenza abbonamento
- ✅ Giorni rimanenti trial
- ✅ Statistiche analisi disponibili
- ✅ Confronto piani disponibili
- ✅ Pulsanti upgrade piano
- ✅ Badge "Più Popolare" per piano consigliato

### 6. **Impostazioni**

- ✅ Selezione lingua (IT, EN, ES, FR, DE)
- ✅ Toggle notifiche email
- ✅ Preferenze salvate nel database

### 7. **Eliminazione Account**

- ✅ Zona pericolosa separata
- ✅ Conferma con password
- ✅ Modal di conferma multipla
- ✅ Eliminazione completa dati
- ✅ Rimozione automatica avatar

## 🗄️ Database

### Nuove Colonne Tabella `user`:

```sql
profile_image VARCHAR(255)          -- Path immagine profilo
phone VARCHAR(20)                   -- Numero telefono
bio TEXT                            -- Bio utente
language VARCHAR(5) DEFAULT 'it'    -- Lingua preferita
notifications_enabled BOOLEAN       -- Notifiche attivate
```

### Colonne Esistenti Utilizzate:

```sql
id, email, password_hash
firstname, lastname
plan (starter/professional/enterprise)
google_id, apple_id
is_active, created_at, last_login
trial_ends_at, subscription_ends_at
analyses_count, analyses_limit
```

## 🔌 API Endpoints

### Profilo Utente

#### GET `/api/user/profile`

Ottiene dati profilo utente corrente.

**Headers:**

```
Authorization: Bearer {token}
```

**Response:**

```json
{
  "success": true,
  "user": {
    "id": 1,
    "email": "user@example.com",
    "firstname": "Mario",
    "lastname": "Rossi",
    "plan": "professional",
    "profile_image": "/static/avatars/user_1_abc123.jpg",
    "phone": "+39 123 456 7890",
    "bio": "Professionista del settore",
    "language": "it",
    "notifications_enabled": true,
    "has_google": true,
    "has_apple": false,
    "has_password": true,
    "created_at": "2025-01-15T10:30:00",
    "last_login": "2025-12-18T14:20:00",
    "trial_ends_at": null,
    "subscription_ends_at": "2026-01-15T10:30:00",
    "analyses_count": 45,
    "analyses_limit": 500
  }
}
```

#### PUT `/api/user/profile`

Aggiorna dati profilo utente.

**Headers:**

```
Authorization: Bearer {token}
Content-Type: application/json
```

**Body:**

```json
{
  "firstname": "Mario",
  "lastname": "Rossi",
  "phone": "+39 123 456 7890",
  "bio": "Aggiornato",
  "language": "en",
  "notifications_enabled": false
}
```

### Sicurezza

#### POST `/api/user/change-password`

Cambia password utente.

**Headers:**

```
Authorization: Bearer {token}
Content-Type: application/json
```

**Body:**

```json
{
  "current_password": "vecchia_password",
  "new_password": "nuova_password_sicura"
}
```

**Note:**

- `current_password` opzionale per utenti solo OAuth
- `new_password` minimo 8 caratteri

### Avatar

#### POST `/api/user/upload-avatar`

Upload immagine profilo.

**Headers:**

```
Authorization: Bearer {token}
Content-Type: multipart/form-data
```

**Body (FormData):**

```
avatar: [File]
```

**Response:**

```json
{
  "success": true,
  "message": "Avatar caricato con successo",
  "profile_image": "/static/avatars/user_1_xyz789.jpg"
}
```

**Limiti:**

- Formati: png, jpg, jpeg, gif, webp
- Dimensione max: 5MB
- File salvati in: `webapp/static/avatars/`

#### DELETE `/api/user/delete-avatar`

Elimina immagine profilo.

**Headers:**

```
Authorization: Bearer {token}
```

### Abbonamento

#### GET `/api/user/subscription`

Ottiene dettagli abbonamento.

**Headers:**

```
Authorization: Bearer {token}
```

**Response:**

```json
{
  "success": true,
  "subscription": {
    "plan": "professional",
    "plan_name": "Professional",
    "plan_price": 29,
    "trial_active": false,
    "trial_ends_at": null,
    "trial_days_left": 0,
    "subscription_active": true,
    "subscription_ends_at": "2026-01-15T10:30:00",
    "subscription_days_left": 28,
    "analyses_count": 45,
    "analyses_limit": 500,
    "analyses_remaining": 455,
    "can_analyze": true
  }
}
```

### Eliminazione Account

#### DELETE `/api/user/delete-account`

Elimina account utente permanentemente.

**Headers:**

```
Authorization: Bearer {token}
Content-Type: application/json
```

**Body:**

```json
{
  "password": "password_conferma"
}
```

**Note:**

- Password opzionale per utenti solo OAuth
- Elimina tutti i dati utente
- Rimuove avatar se presente
- **Azione irreversibile**

## 📁 Struttura File

```
webapp/
├── profile.html                    # Pagina profilo
├── static/
│   ├── css/
│   │   └── profile.css            # Stili profilo
│   ├── js/
│   │   └── profile.js             # Logica profilo
│   └── avatars/                   # Directory avatar utenti
│       └── user_X_hash.jpg
├── index.html                      # Link a profilo aggiunto
└── static/js/main.js              # Aggiornato con avatar

auth_server.py                      # API backend aggiornate
```

## 🎨 Design

### Palette Colori:

- **Primary**: #2196F3 (Blu)
- **Secondary**: #4CAF50 (Verde)
- **Danger**: #f44336 (Rosso)
- **Warning**: #ff9800 (Arancione)
- **Dark Background**: #1a1a1a - #2d2d2d
- **Card Background**: #2a2a2a

### Responsive Design:

- ✅ Desktop (> 992px): Sidebar + Content
- ✅ Tablet (768px - 992px): Stack verticale
- ✅ Mobile (< 768px): Navigazione orizzontale

## 🚀 Accesso

### Dall'App Principale:

1. Login utente
2. Click su pulsante "👤 Profilo" nella sidebar sinistra
3. Reindirizzamento a `profile.html`

### Diretta:

```
http://localhost:8000/profile.html
```

**Nota**: Richiede autenticazione. Redirect automatico a login se non autenticato.

## 🔐 Sicurezza

### Autenticazione:

- JWT Token richiesto per tutti gli endpoint
- Token salvato in `localStorage`
- Verifica automatica all'apertura pagina
- Redirect a login se non valido

### Password:

- Hash con Werkzeug
- Validazione forza password
- Minimo 8 caratteri
- Indicatore visivo forza

### Upload File:

- Validazione estensioni
- Limite dimensione (5MB)
- Nomi file univoci con hash
- Sanitizzazione path

## 📊 Piani Abbonamento

### Starter (Gratuito):

- 50 analisi al mese
- Funzionalità base
- Supporto email
- Trial 14 giorni

### Professional (€29/mese):

- 500 analisi al mese
- Tutte le funzionalità
- Supporto prioritario
- Report avanzati

### Enterprise (€99/mese):

- Analisi illimitate
- Tutte le funzionalità
- Supporto 24/7
- API dedicata
- Manager dedicato

## 🧪 Test

### Test Manuali:

1. **Profilo Base:**

```bash
# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"password123"}'

# Ottieni profilo
curl http://localhost:5000/api/user/profile \
  -H "Authorization: Bearer {TOKEN}"
```

2. **Upload Avatar:**

```bash
curl -X POST http://localhost:5000/api/user/upload-avatar \
  -H "Authorization: Bearer {TOKEN}" \
  -F "avatar=@/path/to/image.jpg"
```

3. **Cambio Password:**

```bash
curl -X POST http://localhost:5000/api/user/change-password \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"old","new_password":"newpass123"}'
```

### Test UI:

1. ✅ Aprire `profile.html`
2. ✅ Verificare caricamento dati
3. ✅ Testare ogni sezione
4. ✅ Provare upload avatar
5. ✅ Testare cambio password
6. ✅ Verificare responsive
7. ✅ Testare eliminazione account

## 🐛 Troubleshooting

### Avatar non carica:

- Verificare permessi directory `webapp/static/avatars/`
- Check path nel database
- Verificare dimensione file < 5MB

### Password non cambia:

- Verificare password corrente
- Check lunghezza minima (8 caratteri)
- Verificare campo `has_password` per utenti OAuth

### Database non aggiornato:

```bash
cd /var/www/html/kimerika.cloud
python3 -c "from auth_server import app, db; app.app_context().push(); db.create_all()"
```

## 🔄 Aggiornamenti Futuri

### In Programma:

- [ ] Integrazione pagamento (Stripe/PayPal)
- [ ] Upgrade piano automatico
- [ ] Storico transazioni
- [ ] Esportazione dati personali (GDPR)
- [ ] Autenticazione a due fattori (2FA)
- [ ] Gestione sessioni attive
- [ ] Crop e resize avatar lato client
- [ ] Temi personalizzati
- [ ] Notifiche push

### Suggerimenti:

- Statistiche dettagliate utilizzo
- Grafici trend analisi
- Badge achievements
- Referral program
- Collegamento social media

## 📚 Riferimenti

- **Backend**: [auth_server.py](auth_server.py)
- **Frontend**: [profile.html](webapp/profile.html)
- **Stili**: [profile.css](webapp/static/css/profile.css)
- **JavaScript**: [profile.js](webapp/static/js/profile.js)

## 📞 Supporto

Per problemi o domande:

- Email: support@kimerika.com
- Documentazione: [docs.kimerika.com](https://docs.kimerika.com)

---

**Versione**: 1.0  
**Data**: 18 Dicembre 2025  
**Autore**: Kimerika Evolution Team
