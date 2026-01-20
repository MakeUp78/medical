# 🛡️ Sistema Admin Dashboard - Kimerika Evolution

## 📋 Panoramica

Sistema completo di amministrazione con dashboard integrata nel profilo utente e pannello admin dedicato per la gestione degli utenti e monitoraggio dell'utilizzo della web app.

## ✨ Funzionalità Implementate

### 1. Dashboard Admin nel Profilo Utente

**Posizione:** `profile.html` → Sezione "Admin Dashboard"

**Visibilità:** Solo per utenti con `role = 'admin'`

**Caratteristiche:**
- ✅ Statistiche in tempo reale
  - Utenti totali, attivi, nuovi (30gg)
  - Analisi totali effettuate
  - Analisi oggi e questa settimana
  - Utenti attivi nelle ultime 24h
  - Trial attivi

- ✅ Attività recenti
  - Ultimi 5 utenti registrati
  - Nome, email, piano, data registrazione, stato

- ✅ Azioni rapide
  - Link a gestione utenti
  - Link ad analytics avanzate
  - Link a log audit

### 2. Dashboard Admin Completa

**Posizione:** `admin.html`

**Sezioni:**

#### 📊 Panoramica (Overview)
- Statistiche principali
- Grafici registrazioni ultimi 30 giorni
- Distribuzione piani (Starter/Professional/Enterprise)
- Quick stats (oggi, settimana, 24h, trial)
- Tabella ultimi utenti registrati

#### 👥 Gestione Utenti
- Lista completa utenti con filtri:
  - Ricerca per nome/email
  - Filtro per piano
  - Filtro per stato (attivo/inattivo)
- Azioni per utente:
  - Visualizza dettagli completi
  - Attiva/Disattiva account
  - Cambia piano
  - Reset password
  - Elimina utente
- Paginazione risultati
- Dettagli utente in modal

#### 📈 Analytics Avanzate
- **Periodo selezionabile:** Settimana / Mese / Anno
- **Grafici:**
  - Attività per tipo (Doughnut chart)
    - Login
    - Upload immagini
    - Upload video
    - Avvio webcam
    - Analisi completate
  - Utilizzo per ora del giorno (Bar chart)
  - Trend attività giornaliera (Line chart)
- **Tabella utenti più attivi**
  - Nome, email, conteggio attività

#### 📝 Log Audit
- Tracciamento azioni admin:
  - Utente attivato/disattivato
  - Piano modificato
  - Password reimpostata
  - Utente eliminato
- Informazioni per log entry:
  - Data/ora
  - Admin che ha eseguito l'azione
  - Tipo azione
  - Utente target
  - IP address
  - Dettagli aggiuntivi
- Paginazione

### 3. Tracciamento Attività Utenti

**Tabella Database:** `user_activity`

**Campi:**
```sql
id              INTEGER PRIMARY KEY
user_id         INTEGER FOREIGN KEY → user.id
action_type     VARCHAR(50)         -- 'login', 'image_upload', 'video_upload', 'webcam_start', 'analysis'
action_details  JSON                -- Dettagli aggiuntivi (es. fileSize, fileType)
ip_address      VARCHAR(45)
user_agent      VARCHAR(255)
created_at      DATETIME (indexed)
```

**Attività Tracciate:**
- ✅ Login utente
- ✅ Upload immagine (con size e type)
- ✅ Upload video (con size e type)
- ✅ Avvio webcam
- ✅ Analisi completata (pronto per implementazione)

## 🎨 UI/UX

### Colori e Stili
- **Admin badge:** Gradiente viola/blu (#667eea → #764ba2)
- **Stat cards:** Hover effect con elevazione
- **Charts:** Chart.js con temi scuri
- **Tables:** Responsive con sorting e paginazione
- **Modals:** Design pulito con conferme

### Responsive Design
- Desktop: 4 colonne per statistiche
- Tablet: 2 colonne
- Mobile: 1 colonna
- Sidebar collassabile
- Tabelle con scroll orizzontale

## 🔒 Sicurezza

### Autenticazione
- Decorator `@admin_required` per tutti gli endpoint admin
- Verifica JWT token
- Controllo `user.role === 'admin'`
- Blocco accesso a non-admin con redirect

### Autorizzazioni
- Admin non può:
  - Disattivare se stesso
  - Eliminare altri admin
  - Eliminare se stesso
- Tutte le azioni tracciate in `admin_audit_log`

### Privacy
- IP address tracciato
- User agent registrato
- Password mai in chiaro
- Dettagli sensibili oscurati nei log

## 🚀 API Endpoints

### Statistiche Dashboard
```
GET /api/admin/dashboard/stats
Authorization: Bearer <admin_token>

Response:
{
  "success": true,
  "stats": {
    "users": {
      "total": 150,
      "active": 142,
      "inactive": 8,
      "new_today": 5,
      "new_week": 23,
      "new_month": 67,
      "recent_active_24h": 89
    },
    "subscriptions": {
      "starter": 100,
      "professional": 40,
      "enterprise": 10
    },
    "usage": {
      "total_analyses": 1542,
      "analyses_today": 45,
      "analyses_week": 234,
      "active_trials": 12
    }
  }
}
```

### Grafici Registrazioni
```
GET /api/admin/dashboard/registrations?period=month
Authorization: Bearer <admin_token>

Response:
{
  "success": true,
  "data": [
    {"date": "2026-01-01", "count": 5},
    {"date": "2026-01-02", "count": 8},
    ...
  ]
}
```

### Analytics Utilizzo
```
GET /api/admin/analytics/usage?period=week
Authorization: Bearer <admin_token>

Response:
{
  "success": true,
  "analytics": {
    "activity_breakdown": {
      "login": 456,
      "image_upload": 234,
      "video_upload": 123,
      "webcam_start": 89,
      "analysis": 345
    },
    "daily_trend": [...],
    "most_active_users": [...],
    "hourly_usage": [...]
  }
}
```

### Tracciamento Attività
```
POST /api/user/track-activity
Authorization: Bearer <user_token>
Content-Type: application/json

Body:
{
  "action_type": "image_upload",
  "details": {
    "fileSize": 2456789,
    "fileType": "image/jpeg"
  }
}

Response:
{
  "success": true,
  "message": "Attività tracciata"
}
```

### Lista Utenti
```
GET /api/admin/users?page=1&per_page=20&search=&plan=&status=&sort=created_at&order=desc
Authorization: Bearer <admin_token>

Response:
{
  "success": true,
  "users": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

### Azioni Utente
```
POST /api/admin/users/<id>/toggle-status
POST /api/admin/users/<id>/change-plan
POST /api/admin/users/<id>/reset-password
DELETE /api/admin/users/<id>
GET /api/admin/audit-log?page=1&per_page=50
```

## 📦 Installazione

### 1. Inizializza Database

```bash
cd /var/www/html/kimerika.cloud
python3 init_activity_tracking.py
```

Questo script creerà la tabella `user_activity` nel database.

### 2. Riavvia Server

```bash
# Se usi systemd
sudo systemctl restart kimerika-auth

# Oppure manualmente
pkill -f auth_server.py
python3 auth_server.py
```

### 3. Verifica Funzionamento

1. Accedi come admin
2. Vai su profilo → Sezione "Admin Dashboard" (dovrebbe essere visibile)
3. Verifica statistiche
4. Apri `admin.html` per dashboard completa
5. Testa analytics e log audit

### 4. Crea Primo Admin (se necessario)

```python
from auth_server import app, db, User
with app.app_context():
    # Trova utente da promuovere
    user = User.query.filter_by(email='tua@email.com').first()
    if user:
        user.role = 'admin'
        db.session.commit()
        print(f"✅ {user.email} è ora admin!")
```

## 🧪 Test

### Test Tracciamento Attività

```javascript
// In console browser (dopo login)
await trackActivity('test_action', { test: true });
// Dovrebbe ritornare {success: true}
```

### Test Dashboard Stats

```bash
# Con token admin
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  http://localhost:5000/api/admin/dashboard/stats
```

### Test Analytics

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  http://localhost:5000/api/admin/analytics/usage?period=week
```

## 📊 Metriche Disponibili

### Dashboard Principale
- Utenti totali/attivi/inattivi
- Nuovi utenti (oggi/settimana/mese)
- Analisi totali/oggi/settimana
- Utenti attivi 24h
- Trial attivi
- Distribuzione piani

### Analytics Avanzate
- Breakdown attività per tipo
- Trend giornaliero attività
- Pattern orari di utilizzo
- Top 10 utenti più attivi
- Registrazioni nel tempo

## 🎯 Best Practices

### Performance
- Analytics calcolate on-demand (no cache necessaria inizialmente)
- Indici su `created_at` in `user_activity`
- Paginazione su tutte le liste
- Lazy loading dei grafici

### Manutenzione
- Log audit mantengono cronologia completa
- UserActivity può crescere velocemente
  - Considera pulizia periodica vecchi dati (>1 anno)
  - O archiviazione su storage separato

### Monitoring
- Monitora dimensione tabella `user_activity`
- Alert su anomalie (es. 1000+ login/minuto)
- Backup regolari del database

## 🔄 Aggiornamenti Futuri

### Possibili Miglioramenti
- [ ] Export CSV/Excel delle statistiche
- [ ] Report automatici via email
- [ ] Notifiche real-time (WebSocket)
- [ ] Grafici comparativi periodo precedente
- [ ] Retention analysis
- [ ] Funnel conversione (trial → paid)
- [ ] Heatmap attività settimanale
- [ ] Segmentazione utenti avanzata
- [ ] A/B testing framework

## 📝 Note Tecniche

### Stack
- **Backend:** Flask + SQLAlchemy
- **Frontend:** Vanilla JS + Chart.js
- **Database:** SQLite (compatibile con PostgreSQL)
- **Auth:** JWT tokens
- **Charts:** Chart.js 4.x

### File Modificati
```
auth_server.py              # Nuovi modelli e endpoint
webapp/profile.html         # Sezione admin aggiunta
webapp/static/js/profile.js # Caricamento stats admin
webapp/static/css/profile.css # Stili sezione admin
webapp/admin.html           # Sezione analytics migliorata
webapp/static/js/admin.js   # Grafici analytics
webapp/static/css/admin.css # Stili analytics
webapp/static/js/main.js    # Tracciamento attività
init_activity_tracking.py   # Script inizializzazione
```

## 🆘 Troubleshooting

### Stats non si caricano
- Verifica token JWT valido
- Controlla ruolo utente (`role = 'admin'`)
- Ispeziona console browser per errori
- Verifica connessione al backend

### Grafici non appaiono
- Assicurati che Chart.js sia caricato
- Controlla dati API (potrebbero essere vuoti)
- Verifica canvas ID corretti

### Tracciamento non funziona
- Verifica tabella `user_activity` esista
- Controlla permessi database
- Testa endpoint direttamente con curl

### Analytics vuote
- Potrebbero non esserci ancora dati
- Usa app per generare attività
- Controlla filtro periodo

## 📞 Supporto

Per problemi o domande:
1. Controlla i log: `tail -f /var/log/kimerika/auth.log`
2. Verifica database: `sqlite3 kimerika.db ".tables"`
3. Test endpoint API con curl
4. Revisiona console browser

---

**Versione:** 1.0.0  
**Data:** 20 Gennaio 2026  
**Autore:** Kimerika Evolution Team
