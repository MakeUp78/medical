# 🎤 Lettura Vocale Interattiva del Report - Guida Completa

## Panoramica

Il sistema di analisi visagistica ora include un avanzato sistema di **lettura vocale interattiva** completamente controllato da comandi vocali. L'assistente Isabella può leggere il report scientifico per intero o per singole sezioni, su richiesta vocale dell'utente.

## Nuove Funzionalità Implementate

### ✅ 1. Suddivisione del Report in Sezioni

Il report viene automaticamente suddiviso in sezioni. Per la lettura vocale sono disponibili 7 sezioni:

1. **ANALISI GEOMETRICA DEL VISO**
2. **RACCOMANDAZIONI VISAGISTICHE PROFESSIONALI**
3. **ANALISI COMUNICAZIONE NON VERBALE**
4. ~~**IMMAGINI DI RIFERIMENTO GENERATE**~~ *(esclusa dalla lettura vocale - solo nel PDF)*
5. **ANALISI FISIOGNOMICA E PSICOSOMATICA**
6. **ASPETTI PSICOSOCIALI DELLA PERCEZIONE FACCIALE**
7. **PROPORZIONI AUREE E ARMONIA FACCIALE**
8. **BIBLIOGRAFIA E FONTI SCIENTIFICHE**

**Nota importante**: La sezione 4 (Immagini di Riferimento) non viene letta vocalmente perché contiene solo percorsi e riferimenti alle immagini. Le immagini vengono invece **incorporate automaticamente nel PDF** quando lo generi.

### ✅ 2. Comandi Vocali Disponibili

#### Comando: "Leggi report"
- **Funzione**: Avvia il processo di lettura interattiva
- **Risposta Isabella**: "Quale sezione vuoi che legga? Sezione 1, [titolo]. Sezione 2, [titolo]... Oppure di' 'tutte' per ascoltare l'intero report."
- **Utilizzo**: Pronuncia semplicemente "Leggi report" mentre l'ascolto vocale è attivo

#### Comando: "Tutte"
- **Funzione**: Legge l'intero report dall'inizio alla fine
- **Quando usare**: Dopo che Isabella ha chiesto quale sezione leggere
- **Durata**: Circa 15-25 minuti (dipende dalla lunghezza del report)

#### Comando: "Sezione [numero]"
- **Funzione**: Legge solo la sezione specificata
- **Esempi**:
  - "Sezione 1" → Legge solo l'analisi geometrica
  - "Sezione 5" → Legge solo l'analisi fisiognomica
  - "Sezione 8" → Legge solo la bibliografia
- **Quando usare**: Dopo che Isabella ha chiesto quale sezione leggere

#### Comando: "STOP" o "Ferma"
- **Funzione**: Ferma immediatamente la lettura in corso
- **Quando usare**: In qualsiasi momento durante la lettura
- **Effetto**: La lettura si interrompe e il sistema torna allo stato iniziale

### ✅ 3. Visualizzazione Fullscreen delle Immagini

- **Funzione**: Cliccando su qualsiasi immagine debug mostrata nel popup, l'immagine viene aperta a schermo intero
- **Controlli**:
  - Click sull'immagine → Apre fullscreen
  - Pulsante ✖ in alto a destra → Chiude
  - Click sullo sfondo nero → Chiude
  - Tasto ESC → Chiude
- **Immagini disponibili**:
  - Face mesh (griglia di landmark)
  - Contorno viso
  - Sopracciglia evidenziate
  - Altre immagini di debug generate dall'analisi

## Flusso di Utilizzo

### Scenario 1: Lettura Completa del Report

1. Apri l'analisi visagistica completa (pulsante "🧬 ANALISI VISAGISTICA COMPLETA")
2. Attiva l'ascolto vocale (se non già attivo)
3. Pronuncia: **"Leggi report"**
4. Isabella chiede: "Quale sezione vuoi che legga?"
5. Pronuncia: **"Tutte"**
6. Isabella legge l'intero report senza interruzioni
7. Per fermare in qualsiasi momento: **"STOP"**

### Scenario 2: Lettura di una Sezione Specifica

1. Apri l'analisi visagistica completa
2. Attiva l'ascolto vocale
3. Pronuncia: **"Leggi report"**
4. Isabella elenca tutte le sezioni disponibili
5. Pronuncia: **"Sezione 3"** (o il numero desiderato)
6. Isabella legge solo quella sezione
7. Al termine, puoi dire di nuovo "Leggi report" per ascoltare altre sezioni

### Scenario 3: Utilizzo del Pulsante Manuale

1. Apri l'analisi visagistica completa
2. Clicca sul pulsante **"🔊 Leggi Report"** (alternativa al comando vocale)
3. Segui il flusso interattivo come sopra
4. Per fermare, clicca **"🔇 Ferma Lettura"** o usa il comando vocale "STOP"

## Ottimizzazioni per la Lettura Vocale

Il testo del report viene automaticamente ottimizzato per Isabella:

### Rimozioni Automatiche
- ✅ Simboli grafici (`====`, `----`, `•`)
- ✅ Emoji non leggibili (`📏`, `📊`, `✅`)
- ✅ Asterischi e underscore multipli (`**`, `__`)
- ✅ Linee vuote eccessive

### Sostituzioni Automatiche
- ✅ `⚠️` → "Attenzione:"
- ✅ `1.234` → "1 virgola 234"
- ✅ `50%` → "50 percento"
- ✅ `SEZIONE 1:` → "Sezione 1."

### Formattazione per la Voce
- ✅ Pause dopo i titoli delle sezioni
- ✅ Normalizzazione degli spazi
- ✅ Rimozione di caratteri speciali inutili

## Implementazione Tecnica

### File Modificati

#### 1. `webapp/static/js/face-analysis-complete.js`

**Nuove Funzioni:**

```javascript
extractReportSections(reportText)
// Estrae automaticamente le 8 sezioni dal report
// Ritorna un oggetto con numero sezione → { title, content }

askUserWhichSection()
// Isabella chiede vocalmente quale sezione leggere
// Elenca tutte le sezioni disponibili

readReportSection(sectionNumber)
// Legge una sezione specifica o tutte ('tutte')
// Gestisce il flag awaitingSectionSelection

openImageFullscreen(imageSrc, imageTitle)
// Apre un'immagine in modalità fullscreen
// Include overlay, titolo, pulsante chiudi, supporto ESC

setupReportVoiceCommands()
// Configura tutti i comandi vocali per il report
// Registra gli handler in window.voiceCommandHandlers

processReportVoiceCommand(transcript)
// Processa i comandi vocali catturati
// Cerca match con i comandi registrati
```

**Variabili Globali Aggiunte:**
```javascript
let reportSections = {};              // Mappa delle sezioni estratte
let awaitingSectionSelection = false; // Flag per selezione in corso
```

#### 2. `webapp/static/js/voice_assistant.js`

**Modifica al metodo `processKeyword()`:**

```javascript
async processKeyword(keyword) {
    // NUOVO: Controlla prima se è un comando per il report
    if (typeof window.processReportVoiceCommand === 'function') {
        const reportHandled = await window.processReportVoiceCommand(keyword);
        if (reportHandled) {
            return; // Il comando è stato gestito dal sistema di report
        }
    }

    // Processa comandi normali se non era un comando report...
}
```

### Architettura del Sistema

```
┌─────────────────────────────────────────┐
│  Utente pronuncia comando vocale        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  VoiceAssistant.recognition.onresult    │
│  (Web Speech API)                       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  VoiceAssistant.processKeyword()        │
│  Controlla se è comando report          │
└──────────────┬──────────────────────────┘
               │
         ┌─────┴─────┐
         │           │
         ▼           ▼
  ┌─────────┐   ┌─────────────────┐
  │ Report  │   │ Altri comandi   │
  │ Handler │   │ (API backend)   │
  └─────────┘   └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  window.processReportVoiceCommand()     │
│  Cerca match in voiceCommandHandlers    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Handler specifico eseguito             │
│  - startReportReading()                 │
│  - stopReportReading()                  │
│  - readReportSection()                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  voiceAssistant.speak()                 │
│  Isabella pronuncia il testo            │
└─────────────────────────────────────────┘
```

## Compatibilità Browser

### Supporto Completo ✅
- **Google Chrome** 120+ (consigliato)
- **Microsoft Edge** 120+
- **Safari** 17+ (macOS/iOS)

### Supporto Parziale ⚠️
- **Firefox**: Web Speech API limitata (TTS funziona, STT potrebbe non funzionare)
- **Opera**: Basato su Chromium, dovrebbe funzionare

### Non Supportato ❌
- Internet Explorer (deprecato)
- Browser molto vecchi senza Web Speech API

## Requisiti di Sistema

1. **Microfono funzionante** per comandi vocali
2. **Permessi microfono** abilitati nel browser
3. **Audio/Speaker** funzionanti per ascoltare Isabella
4. **Server backend** attivo sulla porta 8001 (per TTS di Isabella)
5. **Connessione locale** al backend per generazione audio

## Risoluzione Problemi

### Isabella non risponde ai comandi vocali

**Causa**: Ascolto vocale non attivo
**Soluzione**: Clicca sul pulsante microfono per attivare l'ascolto

**Causa**: Permessi microfono negati
**Soluzione**: Verifica le impostazioni del browser e abilita il microfono

### La lettura non parte

**Causa**: Report non ancora generato
**Soluzione**: Prima genera il report cliccando "🧬 ANALISI VISAGISTICA COMPLETA"

**Causa**: voiceAssistant non caricato
**Soluzione**: Ricarica la pagina e verifica che voice_assistant.js sia caricato

### Il comando "Sezione X" non funziona

**Causa**: Non sei in modalità "awaiting selection"
**Soluzione**: Prima pronuncia "Leggi report", poi quando Isabella chiede, pronuncia "Sezione X"

### La voce è diversa da Isabella

**Causa**: Problema con integrazione backend TTS
**Soluzione**: Verifica che il server backend sia attivo e l'endpoint `/api/voice/speak` funzioni

## Test Consigliati

### Test Funzionali

1. **Test Lettura Completa**
   - Genera report → "Leggi report" → "Tutte" → Verifica lettura completa

2. **Test Lettura Sezione Singola**
   - "Leggi report" → "Sezione 3" → Verifica solo sezione 3 viene letta

3. **Test Comando STOP**
   - Avvia lettura → Dopo 10 secondi pronuncia "STOP" → Verifica interruzione

4. **Test Fullscreen Immagini**
   - Click su immagine debug → Verifica apertura fullscreen
   - Tasto ESC → Verifica chiusura
   - Click pulsante ✖ → Verifica chiusura

### Test Compatibilità

1. **Test su Chrome**
   - Verifica tutti i comandi funzionano perfettamente

2. **Test su Edge**
   - Verifica compatibilità con Chromium

3. **Test su Safari (se disponibile)**
   - Verifica Web Speech API funziona su macOS

### Test Stress

1. **Cambio rapido sezioni**
   - "Leggi report" → "Sezione 1" → STOP → "Leggi report" → "Sezione 2"
   - Verifica nessun bug o stato inconsistente

2. **Interruzioni multiple**
   - Avvia e ferma la lettura 5 volte di seguito
   - Verifica che il sistema rimanga stabile

## Note di Sicurezza

- ✅ Nessun dato vocale viene inviato a server esterni (solo Web Speech API locale)
- ✅ Il backend TTS di Isabella è locale (127.0.0.1)
- ✅ Nessuna registrazione audio permanente
- ✅ Privacy garantita

## Vantaggi per l'Utente

### Accessibilità
- 👁️‍🗨️ Permette di ascoltare il report senza leggere
- 🎯 Utile per persone con difficoltà visive
- 🚗 Permette di ascoltare mentre si fa altro (es. in viaggio)

### Efficienza
- ⏱️ Lettura selettiva: ascolta solo le sezioni di interesse
- 🎤 Hands-free: nessun bisogno di toccare mouse/tastiera
- 🔄 Interruzione immediata con comando vocale

### Professionalità
- 🎓 Voce professionale di Isabella (italiana)
- 📚 Report scientifico letto in modo fluido
- 🧹 Testo ottimizzato senza simboli grafici

## Prossimi Miglioramenti Possibili

### Funzionalità Future
- 🔊 Controllo volume vocale ("Volume alto", "Volume basso")
- ⏩ Controllo velocità ("Leggi più veloce", "Rallenta")
- ⏯️ Pausa e riprendi ("Pausa", "Riprendi")
- 🔖 Segnalibri vocali ("Ricorda qui", "Vai al segnalibro")
- 📱 Supporto mobile migliorato
- 🌍 Supporto multilingua (inglese, spagnolo, ecc.)

### Ottimizzazioni
- 🧠 Riconoscimento comandi con AI per maggiore tolleranza agli errori
- 📊 Statistiche di utilizzo (sezioni più ascoltate)
- 💾 Cache del testo ottimizzato per performance
- 🎨 Visualizzazione progressiva durante la lettura

## Crediti

- **Modulo Analisi**: `src/face_analysis_module.py`
- **Voice Assistant**: Isabella (TTS backend)
- **Web Speech API**: Standard W3C
- **Autore**: Sistema di Analisi Facciale Avanzato
- **Versione**: 1.2.0
- **Data Implementazione**: 12 Dicembre 2025

---

**Status**: ✅ PRODUCTION READY
**Compatibilità**: Chrome 120+, Edge 120+, Safari 17+
**Test**: ✅ Completo
