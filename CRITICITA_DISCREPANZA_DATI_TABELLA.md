# 🔴 CRITICITÀ: Discrepanza Dati tra Tabella e Sezione Anteprima

**Data rilevamento:** 12 Gennaio 2026  
**Gravità:** ALTA  
**Impatto:** Dati incoerenti mostrati all'utente

---

## 📋 Descrizione Problema

Quando l'utente clicca su una riga nella tabella DEBUG, i dati mostrati nella **sezione sotto l'anteprima** sono **diversi** dai dati nella **riga della tabella**.

### Esempio rilevato:

**Tabella (riga #1):**
```
01  09:45:23  85.190  -3.09°  14.45°  1.68°  Salvato
```

**Sezione anteprima (dopo click):**
```
Frame selezionato: #1
Score: 96.770
Pose: Y=0.7° P=0.3° R=6.2°
```

### ⚠️ Problema:
- Score diverso: **85.190** vs **96.770**
- Pose completamente diverse:
  - Yaw: **14.45°** vs **0.7°**
  - Pitch: **-3.09°** vs **0.3°**
  - Roll: **1.68°** vs **6.2°**

---

## 🔍 Root Cause Analysis

### 1️⃣ **Due fonti di dati NON sincronizzate**

Il frontend riceve dal backend WebSocket due array:
1. `data.frames` - Array con score e immagini base64
2. `data.json_data.frames` - Array con score, pose e dettagli completi

### 2️⃣ **Codice problematico nel frontend**

**File:** `webapp/static/js/main.js`

#### ❌ Punto critico 1: Creazione bestFrames (righe 2703-2710)
```javascript
const bestFrames = data.frames.map((frame, index) => ({
  rank: index + 1,
  original_frame: frame.rank,
  score: frame.score || 0,           // ← Score da data.frames
  image_data: frame.data,
  timestamp: Date.now() / 1000,
  yaw: 0,    // ← HARDCODED
  pitch: 0,  // ← HARDCODED
  roll: 0    // ← HARDCODED
}));
```

**Problema:** Usa `data.frames[index].score` per lo score.

#### ❌ Punto critico 2: Aggiornamento pose (righe 2712-2722)
```javascript
if (data.json_data && data.json_data.frames) {
  data.json_data.frames.forEach((jsonFrame, index) => {
    if (index < bestFrames.length && jsonFrame.pose) {
      bestFrames[index].yaw = jsonFrame.pose.yaw || 0;
      bestFrames[index].pitch = jsonFrame.pose.pitch || 0;
      bestFrames[index].roll = jsonFrame.pose.roll || 0;
      bestFrames[index].timestamp = jsonFrame.timestamp || bestFrames[index].timestamp;
      // ⚠️ NON AGGIORNA SCORE!
    }
  });
}
```

**Problema:** Aggiorna solo `yaw`, `pitch`, `roll` e `timestamp`, MA NON aggiorna `score` da `json_data`.

#### ❌ Punto critico 3: Tabella HTML (righe 2448-2452)
```javascript
row.innerHTML = `
  <td>${(frame.score || 0).toFixed(3)}</td>
  <td>${(frame.yaw || 0).toFixed(2)}°</td>
  <td>${(frame.pitch || 0).toFixed(2)}°</td>
  <td>${(frame.roll || 0).toFixed(2)}°</td>
`;
```

**Problema:** Mostra:
- `frame.score` da `data.frames`
- `frame.yaw/pitch/roll` da `data.json_data`

Questi dati appartengono a **frame diversi**!

---

## 🎯 Perché i dati sono diversi?

### Backend: Race Condition nel sorting

**File:** `face-landmark-localization-master/websocket_frame_api.py`

#### Step 1: Sort del buffer (riga 400)
```python
def get_best_frames_result(self):
    self.best_frames.sort(key=lambda x: x['score'], reverse=True)
    best_frames = self.best_frames[:self.max_frames]
```

#### Step 2: Creazione frames_base64 (righe 409-422)
```python
for i, frame_data in enumerate(best_frames):
    frames_base64.append({
        'filename': filename,
        'data': frame_b64,
        'rank': frame_data.get('frame_number', i + 1),
        'score': round(frame_data['score'], 2)  # ← Score frame A
    })
```

#### Step 3: Creazione frames_data (righe 438-464)
```python
for i, frame_data in enumerate(best_frames):
    json_data = {
        'rank': frame_data.get('frame_number', i + 1),
        'total_score': round(frame_data['score'], 2),  # ← Score frame A
        'pose': {
            'pitch': round(frame_data['pitch'], 2),
            'yaw': round(frame_data['yaw'], 2),
            'roll': round(normalized_roll_display, 2)
        }
    }
    frames_data.append(json_data)
```

### ⚠️ Problema:
Se arriva un **nuovo frame con score migliore** MENTRE viene preparata la risposta:
1. `frames_base64` viene popolato con frame A (score 85.190)
2. Il buffer `self.best_frames` viene modificato da `process_frame()` in parallelo
3. `frames_data` viene popolato con frame B (score 96.770)

**Risultato:** 
- `data.frames[0]` ha i dati del frame A
- `data.json_data.frames[0]` ha i dati del frame B

---

## 💡 Soluzioni Proposte

### ✅ Soluzione 1: Usare SOLO json_data (CONSIGLIATA)

Modificare `handleResultsReady()` per costruire `bestFrames` SOLO da `json_data`:

```javascript
// Usa json_data come fonte unica di verità
if (data.json_data && data.json_data.frames) {
  const bestFrames = data.json_data.frames.map((jsonFrame, index) => ({
    rank: index + 1,
    original_frame: jsonFrame.rank,
    score: jsonFrame.total_score || 0,  // ← Score da json_data
    image_data: data.frames[index]?.data || null,  // Immagine da data.frames
    timestamp: jsonFrame.timestamp || Date.now() / 1000,
    yaw: jsonFrame.pose?.yaw || 0,
    pitch: jsonFrame.pose?.pitch || 0,
    roll: jsonFrame.pose?.roll || 0
  }));
} else {
  // Fallback se json_data non disponibile
  const bestFrames = data.frames.map((frame, index) => ({
    rank: index + 1,
    score: frame.score || 0,
    image_data: frame.data,
    timestamp: Date.now() / 1000,
    yaw: 0,
    pitch: 0,
    roll: 0
  }));
}
```

**Vantaggi:**
- ✅ Fonte unica di verità
- ✅ Elimina discrepanze tra tabella e anteprima
- ✅ Usa dati più completi e accurati

**Svantaggi:**
- ⚠️ Se `json_data` non arriva, nessun dato disponibile (mitigato con fallback)

---

### ✅ Soluzione 2: Lock nel backend durante preparazione risposta

Modificare `get_best_frames_result()` per fare una **copia atomica** del buffer:

```python
def get_best_frames_result(self):
    # ✅ COPIA ATOMICA del buffer per evitare race condition
    with threading.Lock():
        self.best_frames.sort(key=lambda x: x['score'], reverse=True)
        best_frames_snapshot = [frame.copy() for frame in self.best_frames[:self.max_frames]]
    
    # Usa best_frames_snapshot invece di self.best_frames
    frames_base64 = []
    frames_data = []
    
    for i, frame_data in enumerate(best_frames_snapshot):
        # ... resto del codice invariato
```

**Vantaggi:**
- ✅ Garantisce coerenza tra `frames_base64` e `frames_data`
- ✅ Nessun cambio logica frontend
- ✅ Thread-safe

**Svantaggi:**
- ⚠️ Richiede import threading
- ⚠️ Possibile overhead prestazionale (minimo)

---

### ✅ Soluzione 3: Verificare correlazione per index

Aggiungere nel frontend un controllo che verifica la coerenza:

```javascript
// Dopo la creazione di bestFrames
if (data.json_data && data.json_data.frames) {
  data.json_data.frames.forEach((jsonFrame, index) => {
    if (index < bestFrames.length && jsonFrame.pose) {
      // ⚠️ VERIFICA: score deve corrispondere
      if (Math.abs(bestFrames[index].score - jsonFrame.total_score) > 0.1) {
        console.warn(`⚠️ Discrepanza score frame ${index}: ${bestFrames[index].score} vs ${jsonFrame.total_score}`);
        // AGGIORNA TUTTO da json_data
        bestFrames[index].score = jsonFrame.total_score;
      }
      
      bestFrames[index].yaw = jsonFrame.pose.yaw || 0;
      bestFrames[index].pitch = jsonFrame.pose.pitch || 0;
      bestFrames[index].roll = jsonFrame.pose.roll || 0;
      bestFrames[index].timestamp = jsonFrame.timestamp || bestFrames[index].timestamp;
    }
  });
}
```

**Vantaggi:**
- ✅ Rileva e corregge discrepanze
- ✅ Log di warning per debug
- ✅ Backward compatible

**Svantaggi:**
- ⚠️ Non risolve la root cause
- ⚠️ Potrebbe mostrare warning frequenti

---

## 📊 File da Modificare

### 🔧 Soluzione 1 (CONSIGLIATA):
- **File:** `webapp/static/js/main.js`
- **Funzione:** `handleResultsReady()` (circa righe 2650-2730)
- **Modifiche:** Righe 2703-2722

### 🔧 Soluzione 2 (BACKEND):
- **File:** `face-landmark-localization-master/websocket_frame_api.py`
- **Funzione:** `get_best_frames_result()` (righe 392-500)
- **Modifiche:** Righe 394-403 (sorting e copia buffer)

### 🔧 Soluzione 3 (IBRIDA):
- **File:** `webapp/static/js/main.js`
- **Funzione:** `handleResultsReady()` (circa righe 2650-2730)
- **Modifiche:** Righe 2712-2722 (aggiungere verifica)

---

## 🎯 Raccomandazioni

### 🥇 Priorità 1: Implementare Soluzione 1
Usare `json_data` come fonte unica è l'approccio più pulito e risolve definitivamente il problema.

### 🥈 Priorità 2: Implementare Soluzione 2 (se Soluzione 1 non basta)
Se ci sono altri casi di race condition, il lock nel backend garantisce coerenza assoluta.

### 🥉 Priorità 3: Aggiungere logging
Aggiungere log temporanei per verificare quando si verifica la discrepanza:

```javascript
console.log('🔍 data.frames scores:', data.frames.map(f => f.score));
console.log('🔍 json_data scores:', data.json_data?.frames?.map(f => f.total_score));
```

---

## 🧪 Test da Effettuare

### Test 1: Video processing
1. Caricare un video di 10 secondi
2. Attendere completamento analisi
3. Cliccare su ogni riga della tabella
4. Verificare che score e pose corrispondano

### Test 2: Webcam stream
1. Avviare stream webcam
2. Muovere la testa in varie pose
3. Cliccare sulle righe della tabella mentre stream è attivo
4. Verificare coerenza dati

### Test 3: Race condition simulata
1. Caricare video molto lungo (>30 secondi)
2. Chiamare `get_results` mentre frame vengono ancora processati
3. Verificare se si verificano discrepanze

---

## 📝 Note Aggiuntive

### Evidenze dai log utente:
```
Tabella:    01  09:45:23  85.190  -3.09°  14.45°  1.68°
Anteprima:  Frame #1 - Score: 96.770 - Y=0.7° P=0.3° R=6.2°
```

**Differenza score:** 96.770 - 85.190 = **11.58 punti**

Questa è una differenza **enorme** che suggerisce si tratti di **frame completamente diversi**, non di un semplice errore di arrotondamento.

### Possibile scenario:
1. Frame A (score 85.190) era il migliore al momento della chiamata `get_results`
2. Durante la preparazione della risposta arriva Frame B (score 96.770)
3. Il buffer viene riordinato e Frame B diventa #1
4. `data.frames` contiene Frame A, `data.json_data.frames` contiene Frame B

---

## ✅ Checklist Implementazione

- [ ] Decidere quale soluzione implementare
- [ ] Fare backup di `main.js` prima delle modifiche
- [ ] Implementare modifiche nel frontend O backend
- [ ] Aggiungere log temporanei per verifica
- [ ] Test con video
- [ ] Test con webcam
- [ ] Test con race condition simulata
- [ ] Rimuovere log temporanei
- [ ] Verificare nessun regression
- [ ] Documentare cambio in changelog

---

**FINE DOCUMENTO**
