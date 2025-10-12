# 🔧 ADMIN VOICE CONFIGURATOR - GUIDA AMMINISTRATORE

## 📋 Panoramica

L'**Admin Voice Configurator** è uno strumento avanzato per amministratori che permette di configurare e mappare tutti i comandi vocali del sistema Symmetra senza modificare manualmente il codice.

## 🔐 Accesso e Sicurezza

### Credenziali di Default
- **Username:** `admin`
- **Password:** `password`

> ⚠️ **IMPORTANTE:** Cambiare le credenziali predefinite dopo il primo accesso!

### Modifica Password
Per cambiare la password, modifica il file `admin_config.json`:
```bash
# Genera nuovo hash della password
python -c "import hashlib; print(hashlib.sha256('nuova_password'.encode()).hexdigest())"
```

## 🚀 Avvio Rapido

### Windows
```bash
# Doppio click su:
start_admin_configurator.bat
```

### Manuale
```bash
python admin_voice_configurator.py
```

## 📖 Funzionalità Principali

### 1. 🔍 Scanner Interfaccia
- **Scansiona automaticamente** tutti i pulsanti e metodi dell'applicazione
- **Rileva candidati** per comandi vocali
- **Mostra dettagli** tecnici di ogni elemento

**Come usare:**
1. Click su "🔍 Scansiona" nella toolbar
2. Naviga tra i tab "Metodi Disponibili" e "Pulsanti Rilevati"
3. Seleziona elementi per vedere i dettagli

### 2. 🗺️ Mapper Comandi
- **Crea mappature** tra comandi vocali e pulsanti
- **Configura keywords** per ogni comando
- **Gestisce handler** delle funzioni

**Workflow:**
1. Click "➕ Nuovo" per creare mappatura
2. Compila:
   - **Azione:** Nome identificativo (es. "face_analysis")
   - **Handler:** Metodo da chiamare (es. "detect_landmarks")
   - **Keywords:** Una per riga (es. "analizza volto", "avvia analisi")
3. Click "💾 Salva"

### 3. 🧪 Tester
- **Testa comandi** senza attivare l'assistente vocale
- **Simula riconoscimento** vocale
- **Verifica mappature** configurate

**Come testare:**
1. Inserisci un comando nel campo di test
2. Click "🧪 Testa Comando"
3. Verifica il risultato nell'output

### 4. ⚙️ Configurazione
- **Editor JSON** per configurazioni avanzate
- **Backup automatico** delle configurazioni
- **Validazione** prima del salvataggio

## 📁 Struttura File

```
medical/
├── admin_voice_configurator.py     # Tool principale
├── admin_config.json               # Configurazione admin
├── start_admin_configurator.bat    # Script avvio Windows
├── voice_mapping_generator.py      # Generatore codice
└── voice/
    ├── isabella_voice_assistant.py
    ├── voice_gui_integration.py
    └── isabella_voice_config.json
```

## 🔧 Configurazione Mappature

### Esempio di Mappatura Completa
```json
{
  "face_analysis": {
    "action": "face_analysis",
    "handler": "detect_landmarks", 
    "keywords": [
      "analizza volto",
      "avvia analisi",
      "inizia analisi",
      "rileva landmark"
    ],
    "confirmation": "Avvio analisi facciale"
  }
}
```

### Handler Disponibili (Scansionati Automaticamente)
- `detect_landmarks` - Rilevamento landmark facciali
- `load_image` - Caricamento immagine
- `start_webcam` - Avvio webcam
- `load_video` - Caricamento video
- `calculate_measurement` - Calcolo misurazioni
- `clear_selections` - Pulizia selezioni
- `save_image` - Salvataggio risultati

## 📋 Workflow Consigliato

### Setup Iniziale
1. **Avvia** il configuratore
2. **Scansiona** l'interfaccia
3. **Verifica** pulsanti e metodi rilevati

### Creazione Mappature
1. **Identifica** il pulsante da mappare
2. **Trova** il metodo handler corrispondente
3. **Crea** la mappatura nel Mapper
4. **Testa** il comando nel Tester

### Validazione e Deploy
1. **Valida** la configurazione (Menu > Strumenti > Valida)
2. **Genera** il codice (Menu > Strumenti > Genera Codice)
3. **Salva** la configurazione
4. **Riavvia** l'applicazione principale

## 🎯 Comandi Vocali Attuali

| Comando | Keywords | Handler | Status |
|---------|----------|---------|--------|
| **Analisi Facciale** | "analizza volto", "avvia analisi" | `detect_landmarks` | ✅ Attivo |
| **Carica Immagine** | "carica immagine", "apri immagine" | `load_image` | ✅ Attivo |
| **Avvia Webcam** | "avvia webcam", "attiva camera" | `start_webcam` | ✅ Attivo |
| **Carica Video** | "carica video", "apri video" | `load_video` | ✅ Attivo |
| **Calcola Misura** | "calcola misura", "misura distanza" | `calculate_measurement` | ✅ Attivo |
| **Pulisci** | "cancella selezioni", "pulisci" | `clear_selections` | ✅ Attivo |
| **Salva** | "salva risultati", "salva immagine" | `save_image` | ✅ Attivo |

## 🔄 Generazione Codice Automatica

Il tool può generare automaticamente:

### 1. Codice Integrazione
File: `voice/voice_gui_integration_generated.py`
- Codice Python aggiornato con tutte le mappature
- Gestione errori avanzata
- Logging completo

### 2. Configurazione JSON
File: `voice/isabella_voice_config_generated.json`
- Configurazione Isabella aggiornata
- Messaggi personalizzati
- Impostazioni vocali

### 3. Documentazione
File: `VOICE_COMMANDS_DOCUMENTATION.md`
- Tabella completa comandi
- Statistiche configurazione
- Guide per utenti

## 🛠️ Troubleshooting

### Errori Comuni

#### "Handler non trovato"
**Causa:** Il metodo specificato non esiste nella scansione  
**Soluzione:** Riesegui la scansione o verifica il nome del metodo

#### "Nessuna keyword definita"
**Causa:** Mappatura senza keywords  
**Soluzione:** Aggiungi almeno una keyword per ogni mappatura

#### "Accesso negato"
**Causa:** Credenziali sbagliate  
**Soluzione:** Verifica username/password in `admin_config.json`

### Log e Debug
- **Log file:** Creato automaticamente nella directory principale
- **Livello log:** Configurabile in `admin_config.json`
- **Debug mode:** Attivabile per informazioni dettagliate

## 🔒 Sicurezza e Best Practice

### Sicurezza
- ✅ **Password protetto** con hash SHA-256
- ✅ **Limite tentativi** di login
- ✅ **Timeout sessione** automatico
- ✅ **Backup automatico** configurazioni

### Best Practice
- 🔄 **Backup regolari** delle configurazioni
- 🧪 **Test completi** prima del deploy
- 📝 **Documentazione** delle modifiche
- 🔍 **Validazione** configurazioni

## 📞 Supporto

### Documenti di Riferimento
- `isabella_voice_assistant.py` - Codice assistente vocale
- `voice_gui_integration.py` - Integrazione GUI esistente
- `canvas_app.py` - Applicazione principale

### Contatti Tecnici
- **Sviluppo:** Team AI Assistant
- **Configurazione:** Amministratori di sistema
- **Bug Report:** Repository GitHub

---

## 🚀 Quick Start per Amministratori

```bash
# 1. Avvia configuratore
start_admin_configurator.bat

# 2. Login (credenziali default)
Username: admin
Password: password

# 3. Scansiona interfaccia
Click "🔍 Scansiona"

# 4. Crea mappatura esempio
Tab "Mapper Comandi" > "➕ Nuovo"
Azione: test_command
Handler: detect_landmarks  
Keywords: "test comando"

# 5. Testa comando
Tab "Tester" > Inserisci "test comando" > "🧪 Testa"

# 6. Salva configurazione
Menu "File" > "Salva Configurazione"
```

**Il tuo sistema Symmetra è ora configurato con comandi vocali personalizzati! 🎉**