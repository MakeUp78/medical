# Miglioramenti Anteprima Webcam

## Nuove Funzionalità Implementate

### 🎮 Controlli Webcam
- **▶️ Avvia**: Inizia l'acquisizione dalla webcam
- **⏸️ Pausa**: Mette in pausa il flusso video (senza spegnere la webcam)
- **⏹️ Stop**: Ferma completamente la webcam
- **🔄 Restart**: Riavvia la webcam da zero

### 🎨 Overlay in Tempo Reale
Nel pannello di anteprima sono disponibili 3 checkbox indipendenti per visualizzare:

1. **Landmarks**: Mostra i 478 punti del volto rilevati da MediaPipe *(✅ Attivo di default)*
2. **Simmetria**: Visualizza l'asse di simmetria facciale *(✅ Attivo di default)*
3. **Poligono**: Mostra i poligoni generati dai punti verdi rilevati *(Disattivo di default)*

**Impostazioni Default**: All'avvio dell'anteprima video, landmarks e asse di simmetria sono già attivati per una visualizzazione immediata dei rilevamenti facciali.

**Importante**: Gli overlay sono puramente estetici e non influenzano:
- I calcoli di scoring
- La selezione del frame più frontale
- I dati inviati al canvas centrale

### 🗗 Finestra Separata
- **Pulsante 🗗**: Scorpora l'anteprima in una finestra separata
- **Auto-rilevamento**: Se disponibile un secondo monitor, la finestra si apre a schermo intero
- **Pulsante Rincorpora**: Riporta l'anteprima nell'interfaccia principale

## Implementazione Tecnica

### Struttura del Codice
- `VideoAnalyzer.apply_preview_overlays()`: Applica gli overlay estetici
- `VideoAnalyzer.set_overlay_options()`: Configura quali overlay mostrare
- `CanvasApp.detach_preview_window()`: Gestisce la finestra separata
- `CanvasApp.update_overlay_settings()`: Sincronizza le impostazioni overlay

### Architettura
- Gli overlay sono applicati solo ai frame di anteprima
- Il flusso di analisi principale rimane inalterato
- Separazione netta tra visualizzazione e calcoli

## Utilizzo

1. **Avvio Webcam**: Clicca ▶️ per iniziare
2. **Configurazione Overlay**: Seleziona i checkbox desiderati
3. **Controllo Flusso**: Usa ⏸️ per pausa, ⏹️ per stop
4. **Finestra Separata**: Clicca 🗗 per scollegare l'anteprima

## Performance

- Frame rate mantenuto a ~10 FPS per l'anteprima
- Analisi ogni 50ms per efficienza
- Overlay renderizzati senza impatto sui calcoli principali
- Gestione memoria ottimizzata per lunghe sessioni