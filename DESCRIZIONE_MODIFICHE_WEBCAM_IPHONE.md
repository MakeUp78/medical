# DESCRIZIONE MODIFICHE WEBCAM IPHONE

## 1. Riduzione della qualità dei frame per migliorare il flusso
- **Azione:** Integra una configurazione lato client per ridurre la risoluzione e applicare compressione sui frame inviati dall’iPhone.
- **File da modificare:**
  - `webapp/static/js/main.js`
    - Aggiungi logica per ridurre la qualità dei frame usando `canvas.toDataURL('image/jpeg', qualità)` prima della trasmissione.
    - Adatta la funzione `startStreaming` per processare i frame in modo più leggero.
  - `face-landmark-localization-master/websocket_frame_api.py`
    - Verifica che il backend supporti correttamente la decodifica dei frame compressi.
    - Aggiungi log per il monitoraggio della qualità dei frame ricevuti e per scartare quelli non validi.
- **Impatto atteso:** Riduzione della latenza e miglioramento dell’elaborazione.

## 2. Ottimizzazione della gestione asincrona dei WebSocket
- **Azione:** Sposta il calcolo dei punteggi dei frame (MediaPipe) su thread separati per non bloccare il ciclo principale del WebSocket.
- **File da modificare:**
  - `face-landmark-localization-master/websocket_frame_api.py`
    - Introduci un sistema di coda per i frame che assegna il lavoro a thread secondari.
    - Usa librerie come `concurrent.futures` o `asyncio.Queue`.
- **Impatto atteso:** Più frame processati in meno tempo e miglioramento della reattività.

## 3. Throttle e limitazione delle richieste simultanee
- **Azione:** Applica un meccanismo di throttle a livello di WebSocket per limitare la quantità di frame inviati al server in un dato intervallo di tempo.
- **File da modificare:**
  - `webapp/static/js/main.js`
    - Aggiorna la funzione `startStreaming` per inviare i frame a cadenza ridotta, es. ogni 200ms o secondo una configurazione dinamica ricevuta dal backend.
  - `face-landmark-localization-master/websocket_frame_api.py`
    - Configura un limite massimo di frame per secondo che possono essere processati per client.
- **Impatto atteso:** Stabilità migliorata e riduzione del carico.

## 4. Miglioramento del recupero in caso di disconnessione
- **Azione:** Implementa riconnessione automatica con ritardi esponenziali (exponential backoff) per ripristinare i WebSocket.
- **File da modificare:**
  - `webapp/static/js/main.js`
    - Aggiungi una logica di fallback nel metodo `connectWebcamWebSocket` che gestisca le riconnessioni progressivamente.
- **Impatto atteso:** Minori interruzioni nell’utilizzo della webcam.

## 5. Gestione delle notifiche di stato
- **Azione:** Riduci la ridondanza delle notifiche (es. toast, debug log) e fornisci messaggi chiari sulla qualità dei frame o sullo stato della connessione.
- **File da modificare:**
  - `webapp/static/js/main.js`
    - Unifica i messaggi di stato (connessione/disconnessione, qualità frame) in una sezione `status`.
- **Impatto atteso:** Miglior esperienza utente e debugging più semplice.

## 6. Standardizzazione delle risoluzioni supportate
- **Azione:** Forza una risoluzione standard a livello di iPhone per evitare frame di dimensioni inconsistenti.
- **File da modificare:**
  - `webapp/static/js/main.js`
    - Fissa una risoluzione target (es. 640x480 o 1280x720) nella funzione `startStreaming` con il metodo `canvas.width/height`.