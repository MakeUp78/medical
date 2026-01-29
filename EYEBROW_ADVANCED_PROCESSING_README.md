# 🔬 Elaborazione Avanzata Aree Sopracciglia con Maschere e Binarizzazione

## 📅 Data Implementazione
**28 Gennaio 2026**

## 🎯 Obiettivo
Migliorare la precisione del rilevamento delle aree sopraccigliari passando da un overlay basato esclusivamente sui landmarks MediaPipe a un overlay basato sui **pixel reali** delle sopracciglia tramite:
1. Maschere scalate del +10%
2. Estrazione delle regioni dall'immagine originale
3. Binarizzazione dei pixel (scuri → nero, chiari → bianco)
4. Generazione overlay dai pixel reali delle sopracciglia

---

## 📁 File Modificati e Backup

### Backup Creati
```bash
webapp/static/js/measurements.js.backup_20260128_091846
webapp/api/main.py.backup_20260128_091846  
src/measurement_tools.py.backup_20260128_091846
```

### File Modificati
- ✅ **webapp/static/js/measurements.js** (implementazione principale)

---

## 🔄 Flusso Implementato

### **1. Calcolo Poligoni Base** (invariato)
```javascript
// Landmarks sopracciglio sinistro
const leftBrowLandmarks = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46];

// Landmarks sopracciglio destro
const rightBrowLandmarks = [296, 334, 293, 300, 276, 283, 282, 295, 285, 336];

// Calcola aree base
const leftBrowArea = calculatePolygonArea(leftBrowPoints);
const rightBrowArea = calculatePolygonArea(rightBrowPoints);
```

---

### **2. Scala Poligoni +10%** (NUOVO)
```javascript
// Trasforma coordinate landmark → canvas
const transformedLeftBrow = leftBrowPoints.map(p => 
  window.transformLandmarkCoordinate(p)
);
const transformedRightBrow = rightBrowPoints.map(p => 
  window.transformLandmarkCoordinate(p)
);

// Scala del +10% attorno ai centroidi
const scaledLeftBrow = scalePolygonAroundCentroid(transformedLeftBrow, 1.10);
const scaledRightBrow = scalePolygonAroundCentroid(transformedRightBrow, 1.10);
```

**Funzione:** `scalePolygonAroundCentroid(points, scaleFactor)`
- Calcola il centroide del poligono
- Per ogni punto: `nuovo_punto = centroide + (punto - centroide) × scaleFactor`
- Risultato: poligono scalato del 10% che include più area attorno al sopracciglio

---

### **3. Estrazione Regione Immagine** (NUOVO)
```javascript
const canvasImage = fabricCanvas.backgroundImage || 
  fabricCanvas.getObjects().find(obj => obj.type === 'image');

const leftRegionData = extractAndBinarizeImageRegion(scaledLeftBrow, canvasImage);
const rightRegionData = extractAndBinarizeImageRegion(scaledRightBrow, canvasImage);
```

**Funzione:** `extractAndBinarizeImageRegion(maskPolygon, canvasImage)`

**Step:**
1. Calcola il bounding box del poligono scalato
2. Crea un canvas temporaneo per il ritaglio
3. Estrae i pixel dall'immagine originale dentro il bbox
4. Per ogni pixel dentro il poligono:
   - Calcola luminosità: `L = 0.299×R + 0.587×G + 0.114×B`
   - Se `L < 128` (threshold) → pixel scuro → **1** (sopracciglio)
   - Se `L ≥ 128` → pixel chiaro → **0** (pelle/sfondo)

**Ritorna:**
```javascript
{
  bbox: {minX, minY, maxX, maxY, width, height},
  binaryMask: Array2D[height][width], // 0 o 1
  imageData: ImageData
}
```

---

### **4. Generazione Overlay da Pixel Reali** (NUOVO)
```javascript
const leftBrowPolygon = createPolygonFromBinaryMask(
  leftRegionData, 
  'Area Sopracciglio Sinistro (Reale)', 
  '#FF6B35'
);
const rightBrowPolygon = createPolygonFromBinaryMask(
  rightRegionData, 
  'Area Sopracciglio Destro (Reale)', 
  '#6B73FF'
);
```

**Funzione:** `createPolygonFromBinaryMask(regionData, label, color)`

**Step:**
1. Trova i pixel di bordo della maschera binaria:
   - Pixel = 1 (nero) E ha almeno un vicino = 0 (bianco)
2. Crea array di punti contorno
3. Semplifica il contorno (prende 1 punto ogni N per ridurre complessità)
4. Crea `fabric.Polygon` con i punti semplificati
5. Applica colore con trasparenza 25%

**Risultato:** Overlay che segue i pixel reali delle sopracciglia invece dei landmarks

---

### **5. Calcolo Aree Reali** (NUOVO)
```javascript
// Conta i pixel neri (valore = 1) nella maschera binaria
const leftRealArea = leftRegionData.binaryMask.flat().filter(p => p === 1).length;
const rightRealArea = rightRegionData.binaryMask.flat().filter(p => p === 1).length;
```

**Nota:** Le aree sono ora in pixel reali dell'immagine, non più aree geometriche dei poligoni landmark.

---

### **6. Etichette e Tabella** (invariato dal punto 5 in poi)
Il resto del flusso rimane identico:
- Creazione etichette con valori px²
- Aggiunta alla tabella misurazioni
- Calcolo percentuale differenza
- Feedback vocale

---

## 🆕 Nuove Funzioni Aggiunte

### `scalePolygonAroundCentroid(points, scaleFactor)`
Scala un poligono attorno al suo centroide.

**Parametri:**
- `points`: Array di punti `{x, y}`
- `scaleFactor`: Fattore di scala (1.1 = +10%)

**Ritorna:** Array di punti scalati

---

### `getPolygonBoundingBox(points)`
Calcola il bounding box di un poligono.

**Ritorna:**
```javascript
{
  minX, minY, maxX, maxY,
  width, height
}
```

---

### `isPointInPolygon(point, polygon)`
Verifica se un punto è dentro un poligono (Ray Casting Algorithm).

**Parametri:**
- `point`: `{x, y}`
- `polygon`: Array di punti

**Ritorna:** `boolean`

---

### `extractAndBinarizeImageRegion(maskPolygon, canvasImage)`
Estrae una regione dall'immagine e la binarizza.

**Ritorna:**
```javascript
{
  bbox: Object,
  binaryMask: Array2D,
  imageData: ImageData
}
```

---

### `createPolygonFromBinaryMask(regionData, label, color)`
Crea un poligono overlay dai pixel della maschera binaria.

**Ritorna:** `fabric.Polygon`

---

## ⚙️ Parametri Configurabili

### Fattore di Scala Maschera
```javascript
// In performEyebrowAreasMeasurement() - righe ~1790
const scaledLeftBrow = scalePolygonAroundCentroid(transformedLeftBrow, 1.10); // +10%
const scaledRightBrow = scalePolygonAroundCentroid(transformedRightBrow, 1.10); // +10%
```

**Valori possibili:**
- `1.05` = +5% (maschera più piccola, più precisa)
- `1.10` = +10% (valore di default)
- `1.15` = +15% (maschera più grande, include più contesto)

---

### Threshold Binarizzazione
```javascript
// In extractAndBinarizeImageRegion() - riga ~2218
const threshold = 128; // Threshold per binarizzazione (regolabile)
```

**Valori possibili:**
- `100` = soglia più bassa (più pixel considerati "scuri"/sopracciglia)
- `128` = valore di default (mediana 0-255)
- `150` = soglia più alta (solo pixel molto scuri = sopracciglia)

---

### Semplificazione Contorno
```javascript
// In createPolygonFromBinaryMask() - riga ~2271
const simplificationFactor = Math.max(1, Math.floor(contourPoints.length / 20));
```

**Valori possibili:**
- `/ 10` = contorno più dettagliato (più punti)
- `/ 20` = valore di default (buon compromesso)
- `/ 30` = contorno semplificato (meno punti, più performance)

---

## 🔧 Fallback System

Il sistema implementa un **fallback automatico** al metodo classico se:
1. L'immagine del canvas non è disponibile
2. Si verificano errori nell'estrazione/binarizzazione

```javascript
if (!canvasImage) {
  console.warn('⚠️ Immagine non trovata, uso overlay classico');
  // Usa createAreaPolygon() classico basato su landmarks
}
```

---

## 📊 Log di Debug

Il sistema produce log dettagliati in console:

```
🔬 Inizio elaborazione avanzata sopracciglia con maschere +10%
✅ Poligoni scalati del +10%: {leftOriginal: 10, leftScaled: 10, ...}
🖼️ Immagine trovata, procedo con estrazione e binarizzazione
✅ Regioni estratte e binarizzate: {leftBbox: {...}, rightBbox: {...}}
✅ Overlay sinistro creato da pixel reali
✅ Overlay destro creato da pixel reali
📊 Aree reali calcolate: {leftLandmarks: "1245.5", leftReal: 1189, ...}
🎯 Elaborazione maschere sopracciglia completata
```

---

## 🚀 Vantaggi della Nuova Implementazione

### ✅ **Precisione Migliorata**
- Overlay basato sui pixel reali delle sopracciglia
- Non più limitato alla geometria dei 10 landmarks

### ✅ **Robustezza**
- Maschera scalata del +10% garantisce inclusione completa del sopracciglio
- Binarizzazione automatica isola i pixel scuri (sopracciglia)

### ✅ **Flessibilità**
- Parametri configurabili (scala, threshold, semplificazione)
- Fallback automatico in caso di errori

### ✅ **Compatibilità**
- Mantiene interfaccia invariata (pulsante, tabella, etichette)
- Cambiamenti trasparenti per l'utente

---

## 🔮 Possibili Miglioramenti Futuri

### 1. **Threshold Adattivo**
Calcolare threshold dinamicamente basato su istogramma regione:
```javascript
const threshold = calculateAdaptiveThreshold(imageData);
```

### 2. **Morfologia Binaria**
Applicare operazioni di erosione/dilatazione per pulire la maschera:
```javascript
const cleanedMask = applyMorphology(binaryMask, 'close');
```

### 3. **Contour Tracing Avanzato**
Usare algoritmo Moore Neighbor per contorni più precisi:
```javascript
const contour = mooreBoundaryTracing(binaryMask);
```

### 4. **Cache Risultati**
Salvare maschere binarizzate per evitare ricalcoli:
```javascript
const cachedMasks = new Map();
```

---

## 📝 Testing

### Test Consigliati

1. **Immagini con Diverse Illuminazioni**
   - Verifica threshold adeguato per illuminazione alta/bassa

2. **Sopracciglia Diverse**
   - Spesse vs sottili
   - Scure vs chiare

3. **Performance**
   - Tempo di elaborazione con immagini ad alta risoluzione

4. **Edge Cases**
   - Immagine non caricata (verifica fallback)
   - Landmarks mancanti/incompleti
   - Sopracciglia molto vicine ai bordi immagine

---

## 🐛 Troubleshooting

### Problema: Overlay non appare
**Causa:** Immagine non trovata sul canvas  
**Soluzione:** Verifica che `fabricCanvas.backgroundImage` esista

### Problema: Area calcolata troppo piccola
**Causa:** Threshold troppo alto  
**Soluzione:** Riduci threshold da 128 a 100-110

### Problema: Area calcolata troppo grande
**Causa:** Threshold troppo basso  
**Soluzione:** Aumenta threshold da 128 a 140-150

### Problema: Overlay troppo irregolare
**Causa:** Semplificazione insufficiente  
**Soluzione:** Aumenta `simplificationFactor` da `/20` a `/30`

---

## 📞 Contatti e Supporto

Per domande o problemi relativi a questa implementazione, contattare il team di sviluppo.

---

**Fine Documentazione** ✅
