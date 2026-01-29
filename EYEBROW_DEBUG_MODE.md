# 🐛 Debug Mode - Visualizzazione Elaborazione Sopracciglia

## 📅 Data Implementazione
**28 Gennaio 2026 - Ore 09:30**

## 🎯 Obiettivo
Fornire visualizzazioni grafiche degli step intermedi dell'elaborazione avanzata delle aree sopraccigliari per debugging e verifica del processo di binarizzazione.

---

## 🎨 Visualizzazioni Debug Disponibili

### 1. **🟢 Maschera Scalata +10% (Verde/Ciano)**
Mostra il poligono originale dei landmarks scalato del 10% attorno al centroide.

- **Colore Sopracciglio Sinistro:** 🟢 Verde (#00FF00)
- **Colore Sopracciglio Destro:** 🔵 Ciano (#00FFFF)
- **Stile:** Linea tratteggiata (dash pattern 10,5)
- **Trasparenza:** 12% fill

**Cosa mostra:**
- L'area che verrà utilizzata per estrarre i pixel dall'immagine
- La maschera è più grande dei landmarks originali per garantire inclusione completa

### 2. **🟣🟡 Bounding Box (Magenta/Giallo)**
Mostra il rettangolo che delimita la regione estratta dall'immagine.

- **Colore BBox Sinistro:** 🟣 Magenta (#FF00FF)
- **Colore BBox Destro:** 🟡 Giallo (#FFFF00)
- **Stile:** Linea tratteggiata (dash pattern 5,5)
- **Etichetta:** Dimensioni in pixel (es. "BBox: 120×80px")

**Cosa mostra:**
- Il rettangolo minimo che contiene la maschera scalata
- Le dimensioni della regione che verrà processata

### 3. **🔴 Maschera Binaria (Rosso)**
Visualizza i pixel identificati come "sopracciglia" dopo la binarizzazione.

- **Colore:** 🔴 Rosso (#FF0000)
- **Opacità:** 70%
- **Etichetta:** Statistiche pixel (es. "Pixels: 1189/3200 (37.2%)")

**Cosa mostra:**
- Pixel scuri (luminanza < 128) → visualizzati in rosso
- Pixel chiari (luminanza ≥ 128) → trasparenti
- Percentuale dell'area classificata come sopracciglio

---

## 🎮 Pannello di Controllo Debug

### Posizione
**Bottom-Right** della finestra (fixed position)

### Funzionalità

#### Toggle Debug Mode
```javascript
// Da console browser
window.toggleEyebrowDebug()  // Attiva/Disattiva debug mode
```

#### Pulisci Oggetti Debug
- Click su **"🧹 Pulisci Debug"** nel pannello
- Rimuove tutti gli overlay di debug dal canvas
- Mantiene gli overlay finali delle aree sopraccigliari

#### Chiudi Pannello
- Click sulla **✕** in alto a destra
- Il pannello può essere ricreato alla prossima analisi

---

## 📊 Interpretazione Visualizzazioni

### Scenario Ideale ✅

```
🟢 Maschera Verde         → Copre completamente il sopracciglio
🟣 BBox Magenta          → Dimensioni ragionevoli (80-150px lato)
🔴 Pixel Rossi           → Concentrati al centro, forma del sopracciglio chiara
📊 Statistiche           → 30-50% dell'area = sopracciglio
```

### Problemi Comuni ⚠️

#### Problema 1: Maschera Troppo Piccola
```
🟢 Maschera             → Non copre completamente il sopracciglio
🔴 Pixel Rossi          → Sopracciglio tagliato ai bordi
```
**Soluzione:** Aumenta scale factor da 1.10 a 1.15

#### Problema 2: Troppo Pochi Pixel Rossi
```
📊 Statistiche          → < 20% dell'area
🔴 Pixel Rossi          → Sparsi, non continui
```
**Soluzione:** Riduci threshold da 128 a 100-110

#### Problema 3: Troppi Pixel Rossi
```
📊 Statistiche          → > 60% dell'area
🔴 Pixel Rossi          → Includono pelle circostante
```
**Soluzione:** Aumenta threshold da 128 a 140-150

#### Problema 4: BBox Fuori dall'Immagine
```
🟡 BBox Giallo          → Esce dai bordi dell'immagine
```
**Soluzione:** Landmarks non accurati, riposiziona o usa immagine frontale

---

## 🔧 Utilizzo Pratico

### Step 1: Attivazione
1. Carica un'immagine nell'applicazione
2. Click su **"✂️ Aree Sopracciglia"**
3. Il pannello debug appare automaticamente in basso a destra

### Step 2: Analisi Visiva
```
Osserva la sequenza degli overlay:
1. 🟢🔵 Maschere scalate (tratteggiato)
2. 🟣🟡 Bounding boxes (rettangoli)
3. 🔴   Pixel binari (rosso sopra l'immagine)
4. 🟠🔵 Overlay finali (aree sopraccigliari)
```

### Step 3: Verifica Console
Apri Console Browser (F12) e verifica i log:
```
🐛 DEBUG: Maschera scalata left visualizzata
🐛 DEBUG: BBox left visualizzato: {minX, minY, width, height}
🐛 DEBUG: Maschera binaria left visualizzata
📊 Aree reali calcolate: {leftReal: 1189, rightReal: 1245}
```

### Step 4: Regolazioni
Se necessario, modifica i parametri nel codice:

#### Aumenta Area Maschera
```javascript
// measurements.js riga ~1790
const scaledLeftBrow = scalePolygonAroundCentroid(transformedLeftBrow, 1.15); // da 1.10 a 1.15
```

#### Regola Threshold Binarizzazione
```javascript
// measurements.js riga ~2218
const threshold = 110; // da 128 a 110 (più pixel scuri = sopracciglio)
```

### Step 5: Test Iterativo
1. Modifica parametro
2. Ricarica pagina (CTRL+F5)
3. Click su "Aree Sopracciglia"
4. Osserva differenze negli overlay rossi
5. Ripeti fino a risultato ottimale

---

## 🎓 Guida Visiva Colori

### Legenda Completa
```
🟢 Verde tratteggiato    = Maschera Sopracciglio Sinistro +10%
🔵 Ciano tratteggiato    = Maschera Sopracciglio Destro +10%
🟣 Magenta tratteggiato  = Bounding Box Sinistro
🟡 Giallo tratteggiato   = Bounding Box Destro
🔴 Rosso semi-opaco      = Pixel classificati come sopracciglio
🟠 Arancione solido      = Overlay finale Sopracciglio Sinistro
🔵 Blu solido            = Overlay finale Sopracciglio Destro
```

---

## 💻 API Debug

### Variabili Globali
```javascript
window.eyebrowDebugMode        // boolean: stato debug mode
window.toggleEyebrowDebug()    // function: toggle debug on/off
window.eyebrowDebugObjects     // array: oggetti debug sul canvas
```

### Funzioni Debug
```javascript
clearEyebrowDebugObjects()                    // Pulisce overlay debug
drawScaledMaskDebug(polygon, 'left'|'right') // Disegna maschera scalata
drawBoundingBoxDebug(bbox, 'left'|'right')   // Disegna bbox
drawBinaryMaskDebug(regionData, 'left'|'right') // Disegna maschera binaria
createDebugControlPanel()                     // Crea pannello controllo
```

### Esempio Uso da Console
```javascript
// Attiva debug mode
window.toggleEyebrowDebug()

// Pulisci tutti gli overlay debug
clearEyebrowDebugObjects()

// Verifica stato
console.log('Debug mode:', window.eyebrowDebugMode)
console.log('Debug objects:', window.eyebrowDebugObjects.length)
```

---

## 📸 Screenshot Interpretazione

### Esempio Output Visivo

```
┌─────────────────────────────────────┐
│  🖼️ Immagine Viso                   │
│                                     │
│    🟢┄┄┄┄┄┐         ┌┄┄┄┄┄🔵       │
│    ┆🟣───┐┆         ┆┌───🟡┆       │
│    ┆│🔴🔴││         ││🔴🔴│┆       │
│    ┆│🔴🔴││         ││🔴🔴│┆       │
│    ┆└───┘┆         ┆└───┘┆       │
│    └┄┄┄┄┄┘         └┄┄┄┄┄┘       │
│                                     │
│  🟠 Overlay    🔵 Overlay           │
│   Sinistro       Destro             │
└─────────────────────────────────────┘

Legenda:
🟢🔵 = Maschere scalate +10% (tratteggiato)
🟣🟡 = Bounding boxes (rettangoli)
🔴   = Pixel binari sopracciglia (rosso)
🟠🔵 = Overlay finali (aree reali)
```

---

## 🧪 Test di Verifica

### Test 1: Sopracciglia Spesse
- **Atteso:** 40-60% dell'area in rosso
- **Maschera:** Verde/Ciano copre completamente
- **BBox:** Proporzionato al sopracciglio

### Test 2: Sopracciglia Sottili
- **Atteso:** 25-40% dell'area in rosso
- **Maschera:** Verde/Ciano leggermente più grande
- **BBox:** Rettangolo allungato

### Test 3: Sopracciglia Chiare
- **Problema:** < 20% area in rosso
- **Soluzione:** Riduci threshold a 110-115

### Test 4: Illuminazione Alta
- **Problema:** Pixel rossi dispersi
- **Soluzione:** Aumenta threshold a 140-150

---

## 🔍 Troubleshooting Debug

### Pannello Debug Non Appare
**Causa:** Errore JavaScript  
**Soluzione:** Controlla console per errori

### Overlay Debug Sovrapposti
**Causa:** Click multipli su "Aree Sopracciglia"  
**Soluzione:** Click su "🧹 Pulisci Debug" prima di rieseguire

### Pixel Rossi Non Visibili
**Causa:** Threshold troppo alto per l'immagine  
**Soluzione:** Riduci threshold gradualmente

### Maschera Verde Copre Tutto
**Causa:** Scale factor troppo alto  
**Soluzione:** Riduci da 1.10 a 1.08

---

## 📚 Riferimenti

- **File Modificato:** `webapp/static/js/measurements.js`
- **Righe Debug Mode:** 30-45 (variabili globali)
- **Righe Funzioni Debug:** 2470-2750
- **Righe Integrazione:** 1790-1870

---

## ✅ Checklist Debug

Prima di confermare che l'elaborazione funziona correttamente:

- [ ] Maschera verde/ciano copre completamente il sopracciglio
- [ ] BBox ha dimensioni ragionevoli (non troppo grande/piccolo)
- [ ] Pixel rossi formano la shape del sopracciglio
- [ ] Statistiche mostrano 30-50% dell'area classificata
- [ ] Overlay finale segue i pixel rossi
- [ ] Nessun errore in console

---

**Debug Mode Attivo di Default!** 🎉  
Per disattivare: `window.toggleEyebrowDebug()` o deseleziona checkbox nel pannello.

---

*Implementato da: GitHub Copilot (Claude Sonnet 4.5)*  
*Data: 28 Gennaio 2026*
