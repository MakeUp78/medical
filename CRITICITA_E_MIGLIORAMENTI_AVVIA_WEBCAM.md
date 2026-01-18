# 🛠️ Criticità e Miglioramenti per la Funzione "Avvia Webcam" con iPhone

Questo documento esplora criticità, suggerimenti di miglioramento e l'impatto dei cambiamenti sulla funzione **"Avvia Webcam"** when utilizzata in combinazione con un iPhone tramite WebSocket.

---

## 🔴 Criticità Identificate

### 1. Connessione iPhone iniziale
**Problema:** Il desktop riceve notifiche ma non è sempre chiaro se l’iPhone è pronto per inviare frame.
**Cause Possibili:** Dati parziali di handshake sul WebSocket.

### 2. Precisione della selezione dei frame
**Problema:** Frame scartati nonostante fossero quasi frontali, probabilmente a causa di soglie pose_score troppo restrittive.

### 3. Ritardo nella trasmissione dei frame
- Latenza osservata sopra i 50ms per frame iPhone.
- Inefficienza nei WebSocket persistenti dovuta alla gestione asincrona del buffer centrale best_frames_buffer.

### 4. Buffer Overflow**Discrepanza reportata nei test:**

- Test di esamini migliori frame confermano crash su troppe "non-synced requests".
---rest di ******* Scalera dal.