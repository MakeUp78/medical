# Guida all'Assistente Vocale Symmetra

## Panoramica
L'assistente vocale Symmetra è ora completamente integrato nella tua applicazione di analisi facciale Kimerika 2.0. Ti permette di controllare l'app usando comandi vocali naturali in italiano.

## Configurazione

### Dipendenze Installate
✅ edge-tts - Sintesi vocale con voce Isabella italiana
✅ pygame - Riproduzione audio
✅ SpeechRecognition - Riconoscimento vocale
✅ pyaudio - Gestione microfono

### Messaggio di Benvenuto
All'avvio dell'applicazione, Symmetra si presenta automaticamente con il messaggio personalizzato per l'app medica.

## Controlli Interfaccia

### Pannello di Controllo
Nel pannello sinistro trovi la sezione "ASSISTENTE VOCALE SYMMETRA" con:
- **Indicatore di stato**: Mostra se l'assistente è attivo/disattivo
- **Pulsante Attiva/Disattiva**: Accende o spegne l'assistente vocale
- **Test Audio**: Verifica che l'audio funzioni correttamente
- **Comandi**: Mostra la lista completa dei comandi disponibili
- **Comandi Rapidi**: Mini-guida sempre visibile

## Comandi Vocali Disponibili

### Attivazione
- **"Hey Symmetra"** - Attiva l'assistente per il prossimo comando

### Analisi Facciale
- "Analizza volto" / "Avvia analisi" / "Inizia analisi"
- "Ferma analisi" / "Interrompi"

### Gestione File
- "Carica immagine" / "Apri immagine" / "Carica foto"
- "Avvia webcam" / "Avvia camera" / "Attiva webcam"
- "Carica video" / "Apri video"

### Misurazione
- "Calcola misura" / "Misura distanza" / "Calcola"
- "Cancella selezioni" / "Pulisci"

### Salvataggio
- "Salva risultati" / "Salva immagine" / "Esporta"

### Controlli
- "Aiuto" - Mostra lista comandi
- "Status" - Stato del sistema
- "Goodbye" / "Arrivederci" - Disattiva assistente

## Messaggi Vocali Personalizzati

L'assistente fornisce feedback vocale specifico per l'analisi facciale:
- Conferma delle operazioni completate
- Avvisi quando non ci sono immagini caricate
- Risultati delle analisi e misurazioni
- Indicazioni per migliorare la qualità delle immagini

## Configurazione Avanzata

### File di Configurazione
Il file `voice/isabella_voice_config.json` contiene:
- **Messaggi personalizzati** per ogni situazione dell'app
- **Comandi vocali** configurabili
- **Impostazioni audio** (velocità, volume, qualità)
- **Parametri di riconoscimento** vocale

### Personalizzazione Messaggi
Puoi modificare i messaggi in `custom_messages` per:
- Cambiare il tono (professionale/amichevole)
- Aggiungere informazioni specifiche
- Adattare il linguaggio alle tue preferenze

### Aggiungere Nuovi Comandi
Per aggiungere comandi vocali personalizzati, modifica il metodo `setup_voice_commands()` in `src/canvas_app.py`.

## Risoluzione Problemi

### Assistente Non Disponibile
Se vedi "Non disponibile":
1. Verifica che tutte le dipendenze siano installate: `pip install -r requirements.txt`
2. Controlla che il microfono sia connesso e funzionante
3. Verifica i permessi audio del sistema

### Audio Non Funziona
1. Usa il pulsante "Test Audio" per verificare l'output
2. Controlla il volume del sistema
3. Verifica che non ci siano altri programmi che usano l'audio

### Riconoscimento Vocale Problematico
1. Parla chiaramente e non troppo velocemente
2. Riduci il rumore di fondo
3. Assicurati che il microfono sia vicino
4. Attendi il segnale di conferma prima di parlare

## Utilizzo Ottimale

### Workflow Consigliato
1. **Avvia l'app** - Symmetra ti darà il benvenuto
2. **Attiva l'assistente** - Clicca "Attiva Assistente"
3. **Carica un'immagine** - Di' "Hey Symmetra, carica immagine"
4. **Analizza** - Di' "Hey Symmetra, analizza volto"
5. **Misura** - Seleziona punti e di' "calcola misura"
6. **Salva** - Di' "salva risultati" quando hai finito

### Suggerimenti
- Usa frasi naturali, non solo le parole chiave esatte
- L'assistente è più preciso in ambienti silenziosi
- Attendi sempre la conferma vocale prima del comando successivo
- Puoi sempre usare i controlli manuali insieme ai comandi vocali

## Sicurezza e Privacy

- **Nessun dato inviato online**: Tutto il riconoscimento vocale avviene localmente
- **Nessuna registrazione permanente**: I comandi non vengono salvati
- **Audio temporaneo**: I file audio vengono eliminati dopo l'uso

---

*Per supporto tecnico o personalizzazioni avanzate, consulta la documentazione completa nell'assistente vocale.*