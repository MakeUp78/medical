# Aggiornamento Selezione Webcam

## Data: 6 Gennaio 2026

## Problema Risolto
Il sistema dava priorità automatica a IRIUN Webcam quando disponibile, causando conflitti con la webcam di sistema. Gli utenti non potevano scegliere quale webcam utilizzare.

## Modifiche Implementate

### 1. **Webcam di Sistema come Default**
- La webcam integrata del computer è ora la scelta predefinita
- IRIUN viene utilizzata **SOLO** se esplicitamente abilitata dall'utente
- Non ci sono più conflitti automatici tra le due webcam

### 2. **Nuova Sezione nelle Impostazioni**
Aggiunta interfaccia utente in **⚙️ IMPOSTAZIONI → 📷 Selezione Webcam**:

- **💻 Webcam di Sistema (Consigliata)** - DEFAULT
  - Usa la webcam integrata del computer
  - Sempre disponibile
  - Nessuna configurazione richiesta

- **📱 IRIUN Webcam (Smartphone)** - OPZIONALE
  - Usa lo smartphone come webcam professionale
  - Richiede configurazione IRIUN
  - Deve essere abilitata manualmente dall'utente

### 3. **Persistenza della Scelta**
- La preferenza viene salvata in `localStorage`
- Chiave: `useIriun` (default: `false`)
- La scelta rimane attiva tra una sessione e l'altra

### 4. **Feedback Utente**
- Indicatore visivo della webcam attualmente selezionata
- Toast notification quando si cambia preferenza
- Feedback vocale tramite voice assistant
- Console log per debugging

## File Modificati

### `/webapp/static/js/main.js`
- Funzione `startWebcam()` modificata:
  ```javascript
  // Verifica preferenza utente per IRIUN (default: disabilitato)
  const useIriunPreference = localStorage.getItem('useIriun') === 'true';
  
  // Usa IRIUN SOLO se l'utente ha abilitato l'opzione E IRIUN è disponibile
  if (useIriunPreference && iriunDevice) {
      // Usa IRIUN
  } else {
      // DEFAULT: Usa sempre la webcam di sistema
  }
  ```

### `/webapp/index.html`
- Aggiunta sezione "📷 Selezione Webcam" in IMPOSTAZIONI
- Due radio button per scegliere la webcam
- Indicatore stato attuale
- Funzioni JavaScript:
  - `loadWebcamPreference()` - Carica preferenza all'avvio
  - `setWebcamPreference(type)` - Salva nuova preferenza

## Come Usare

### Per Utenti Standard (Webcam PC)
1. Non serve fare nulla - la webcam di sistema è già attiva di default
2. Cliccare "📹 Avvia Webcam" usa automaticamente la webcam del PC

### Per Utenti IRIUN (Smartphone)
1. Aprire **⚙️ IMPOSTAZIONI**
2. Nella sezione "📷 Selezione Webcam"
3. Selezionare "📱 IRIUN Webcam (Smartphone)"
4. Configurare IRIUN con la procedura guidata se necessario
5. Cliccare "📹 Avvia Webcam" per usare lo smartphone

### Per Cambiare Webcam
- Basta selezionare l'altra opzione in IMPOSTAZIONI
- La nuova scelta si applica al prossimo avvio webcam
- Se la webcam è già attiva, fermarla e riavviarla

## Comportamento Tecnico

### Priorità di Selezione
1. **Preferenza Utente** (localStorage `useIriun`)
2. **Disponibilità Dispositivo** (IRIUN deve essere connessa)
3. **Fallback Automatico** (se IRIUN selezionata ma non disponibile, usa sistema)

### Log Console
```
💻 Uso webcam di sistema (default)
ℹ️ IRIUN trovata ma non selezionata - usando webcam di sistema
✅ Preferenza webcam salvata: system
```

## Test Eseguiti
- ✅ Default: Webcam di sistema si avvia correttamente
- ✅ Selezione IRIUN: Preferenza salvata e applicata
- ✅ Selezione Sistema: Ritorno al default funzionante
- ✅ Persistenza: Preferenza mantenutatraccia riavvio pagina
- ✅ Feedback: Toast, voice assistant, console log funzionano
- ✅ Nessun errore JavaScript

## Benefici
✅ **Esperienza Utente Migliorata**: Controllo completo sulla webcam
✅ **Nessun Conflitto**: IRIUN non interferisce più con webcam di sistema
✅ **Scelta Chiara**: Interfaccia intuitiva con opzioni ben definite
✅ **Flessibilità**: Facile switching tra le due webcam
✅ **Retrocompatibilità**: Funziona con tutti i browser supportati

## Note Tecniche
- La selezione non richiede riavvio dell'applicazione
- Compatible con tutti i browser moderni (Chrome, Firefox, Edge, Safari)
- Non influenza altre funzionalità dell'applicazione
- localStorage pulisce automaticamente se l'utente cancella i dati del browser
