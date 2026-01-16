# 📹 Analisi Invio Frame Video via WebSocket

## ✅ CONFERMA: Video Compresso e Ridotto

Il video caricato dall'utente viene **SEMPRE compresso e ridotto** prima dell'invio via WebSocket.

---

## 🔄 Pipeline Elaborazione Frame Video

### 1️⃣ Cattura Frame Raw
```javascript
const rawCanvas = document.createElement('canvas');
rawCanvas.width = video.videoWidth;  // Dimensioni originali
rawCanvas.height = video.videoHeight;
context.drawImage(video, 0, 0, rawCanvas.width, rawCanvas.height);
```

### 2️⃣ Normalizzazione 72 DPI
```javascript
const normalizedCanvas = normalizeTo72DPI(rawCanvas);
```
- Mantiene dimensioni pixel, normalizza solo metadati DPI

### 3️⃣ Compressione Aggressiva
```javascript
const compressedCanvas = compressImage(normalizedCanvas, 1280, 0.6);
```
- **Max Width**: 1280px (ridimensionamento proporzionale se > 1280px)
- **Quality**: 0.6 (60% - compressione aggressiva)
- **Mantiene proporzioni**: NO ritagli, NO distorsioni

### 4️⃣ Conversione e Invio
```javascript
const frameBase64 = compressedCanvas.toDataURL('image/jpeg', 0.6).split(',')[1];
webcamWebSocket.send(JSON.stringify({
  action: 'process_frame',
  frame_data: frameBase64
}));
```
- Formato: JPEG base64
- Quality: 0.6 (60%)
- Dimensione stimata: **~50KB per frame**

---

## ⏱️ Frame Rate Invio

### Video Caricati
**Location**: `startVideoFrameProcessing()` - [main.js:837-862](webapp/static/js/main.js#L837-L862)

```javascript
const processInterval = setInterval(() => {
  video.currentTime = frameCount / 5;
  captureFrameFromVideoElement(video);
  frameCount++;
}, 200); // 5 FPS
```

- **Frame Rate**: **5 FPS** (5 frame al secondo)
- **Intervallo**: 200ms tra frame
- **Totale Frame**: `Math.floor(video.duration * 5)`
- **Esempio**: Video 10 secondi = 50 frame totali inviati

### Webcam Stream
**Location**: `startFrameCapture()` - [main.js:1860-1902](webapp/static/js/main.js#L1860-L1902)

```javascript
captureInterval = setInterval(() => {
  // cattura e comprimi frame
  webcamWebSocket.send(JSON.stringify(frameMessage));
}, 500); // 2 FPS
```

- **Frame Rate**: **2 FPS** (2 frame al secondo)
- **Intervallo**: 500ms tra frame
- **Streaming continuo** fino a stop webcam

---

## 📊 Confronto Dimensioni

| Tipo | Dimensioni Originali | Dimensioni Inviate | Compressione | Dimensione File |
|------|---------------------|-------------------|--------------|-----------------|
| **Video 4K** | 3840x2160px | 1280x720px | ~12x riduzione pixel | ~50KB/frame |
| **Video 1080p** | 1920x1080px | 1280x720px | ~3x riduzione pixel | ~50KB/frame |
| **Video 720p** | 1280x720px | 1280x720px | Nessun resize | ~50KB/frame |
| **Video 480p** | 854x480px | 854x480px | Nessun resize | ~30KB/frame |

### Esempio Calcolo Banda
**Video 1080p, durata 30 secondi**:
- Frame totali: 30s × 5 FPS = **150 frame**
- Dimensione per frame: ~50KB
- **Totale dati inviati**: 150 × 50KB = **7.5 MB**
- Originale (no compressione): 30s × 30 FPS × ~500KB = **450 MB**
- **Risparmio banda**: ~98.3%

---

## 🎯 Riepilogo Tecnico

### ✅ Cosa Viene Compresso
1. **Dimensioni**: Max 1280px larghezza
2. **Formato**: Conversione a JPEG (anche se originale è .mov, .mp4, ecc.)
3. **Quality**: 0.6 (60%)
4. **DPI**: Normalizzato a 72 pixel/pollice

### ✅ Cosa NON Viene Toccato
1. **Proporzioni**: Aspect ratio originale mantenuto
2. **Frame Order**: Ordine frame preservato
3. **Durata**: Tutta la durata del video elaborata (5 FPS)

### ⚡ Prestazioni
- **Anteprima utente**: 30 FPS (rendering locale, compressione 0.75)
- **Elaborazione server**: 5 FPS (invio WebSocket, compressione 0.6)
- **Webcam live**: 2 FPS (invio WebSocket, compressione 0.6)

---

## 🔍 Verifica Funzioni

### captureFrameFromVideoElement()
**File**: [main.js:866-894](webapp/static/js/main.js#L866-L894)
- ✅ Normalizzazione 72 DPI attiva
- ✅ Compressione 1280px, quality 0.6 attiva
- ✅ Invio via WebSocket

### startVideoFrameProcessing()
**File**: [main.js:837-862](webapp/static/js/main.js#L837-L862)
- ✅ Frame rate: 5 FPS (200ms interval)
- ✅ Durata completa video elaborata
- ✅ WebSocket check attivo

### startFrameCapture() - Webcam
**File**: [main.js:1860-1902](webapp/static/js/main.js#L1860-L1902)
- ✅ Frame rate: 2 FPS (500ms interval)
- ✅ Normalizzazione e compressione attive
- ✅ Streaming continuo

---

## 📝 Conclusioni

**Il sistema è OTTIMIZZATO:**
- ✅ Video compressi PRIMA dell'invio (no dimensioni originali)
- ✅ Frame rate controllato: 5 FPS per video, 2 FPS per webcam
- ✅ Dimensioni ridotte: max 1280px, quality 0.6
- ✅ Risparmio banda: ~98% vs video originale non compresso
- ✅ Proporzioni mantenute: NO distorsioni o ritagli
