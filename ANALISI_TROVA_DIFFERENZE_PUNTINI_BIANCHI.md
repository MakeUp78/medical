# ANALISI COMPLETA: Flusso "Trova Differenze" - Rilevamento Puntini Bianchi

## Data Analisi
**29 Gennaio 2026**

---

## 📋 EXECUTIVE SUMMARY

### Problema Riscontrato
Caricando due immagini con dimensioni e risoluzioni simili che ritraggono due soggetti con 10 puntini bianchi posizionati sui contorni delle sopracciglia:
- ✅ **successo.jpg**: Rileva **9 puntini** (quasi funzionante)
- ❌ **fallisce.JPG**: Rileva **9 puntini** (quasi funzionante)

**Entrambe NON raggiungono i 10 puntini necessari**, ma il sistema attualmente usa parametri ottimizzati per **puntini VERDI** invece che per **puntini BIANCHI**.

### Causa Principale Identificata
**MISMATCH TRA PARAMETRI HSV E COLORE REALE DEI PUNTINI**

I puntini nelle immagini sono **BIANCHI/BIANCASTRI** ma:
1. I parametri di default del `GreenDotsProcessor` sono ottimizzati per **puntini VERDI**
2. Il frontend passa parametri con `hue_range: [60, 150]` che esclude i puntini bianchi (Hue 15-31°)
3. Il check per puntini bianchi in `is_green_pixel()` esiste ma è **bypassato** dai filtri HSV del costruttore

---

## 🔄 SCHEMA COMPLETO DEL FLUSSO

```
┌─────────────────────────────────────────────────────────────────┐
│                          UTENTE                                  │
│              Clicca "🔍 Trova Differenze"                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND - index.html                          │
│              Button ID: green-dots-btn                           │
│              onclick="toggleGreenDots()"                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│            FRONTEND - webapp/static/js/main.js                   │
│                  function toggleGreenDots()                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Toggle classe 'active' sul pulsante                   │   │
│  │ 2. Se attivo e non ci sono greenDotsDetected:            │   │
│  │    → Chiama detectGreenDots()                            │   │
│  │ 3. Se attivo e già rilevati:                             │   │
│  │    → Aggiorna display e pronuncia feedback vocale        │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│            FRONTEND - webapp/static/js/main.js                   │
│               async function detectGreenDots()                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Attiva automaticamente asse simmetria (se disattivo)  │   │
│  │ 2. Ottiene immagine canvas come base64                   │   │
│  │    → Resize max 2400px (per preservare dettagli)         │   │
│  │ 3. Prepara parametri HSV:                                │   │
│  │    ⚠️ hue_range: [60, 150]        ← VERDE               │   │
│  │    ⚠️ saturation_min: 15                                 │   │
│  │    ⚠️ value_range: [15, 95]                              │   │
│  │       cluster_size_range: [2, 150]                       │   │
│  │       clustering_radius: 2                               │   │
│  │ 4. Chiama API POST /api/green-dots/analyze               │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP POST
                             │ Content-Type: application/json
                             │ Body: {image: base64, hue_range, ...}
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              BACKEND API - webapp/api/main.py                    │
│        @app.post("/api/green-dots/analyze")                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Genera session_id UUID                                │   │
│  │ 2. Verifica disponibilità GREEN_DOTS_AVAILABLE           │   │
│  │ 3. Chiama process_green_dots_analysis()                  │   │
│  │ 4. Converte risultati in Pydantic models                 │   │
│  │ 5. Restituisce GreenDotsAnalysisResult JSON              │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              BACKEND - webapp/api/main.py                        │
│          def process_green_dots_analysis()                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Decodifica immagine base64 → PIL Image                │   │
│  │ 2. Inizializza GreenDotsProcessor con parametri ricevuti │   │
│  │ 3. Chiama processor.process_pil_image()                  │   │
│  │    ✅ use_preprocessing=True                             │   │
│  │    (attiva preprocessing MediaPipe maschere sopracciglia)│   │
│  │ 4. Converte overlay PIL → base64                         │   │
│  │ 5. Restituisce Dict con risultati                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│          CORE - src/green_dots_processor.py                      │
│         class GreenDotsProcessor                                 │
│         def process_pil_image()                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Se use_preprocessing=True:                            │   │
│  │    → Chiama preprocess_for_detection()                   │   │
│  │    → Scala immagine a target_width=1400px                │   │
│  │    → Rileva maschere sopracciglia con MediaPipe          │   │
│  │    → Estrae ROI sopracciglia su sfondo bianco            │   │
│  │ 2. Chiama detect_green_dots(image)                       │   │
│  │ 3. Verifica: total_dots == 10?                           │   │
│  │    NO → Genera overlay_dots_only + warning               │   │
│  │    SÌ → Divide in gruppi Sx/Dx                           │   │
│  │       → Ordina punti anatomicamente                      │   │
│  │       → Calcola statistiche forme                        │   │
│  │       → Genera overlay con poligoni                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│          CORE - src/green_dots_processor.py                      │
│              def detect_green_dots()                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 🔴 CORE ALGORITHM - Qui avviene il rilevamento           │   │
│  │                                                           │   │
│  │ 1. Converte PIL Image → numpy array                      │   │
│  │ 2. FOR ogni pixel (y, x) in immagine:                    │   │
│  │    a. Legge RGB (r, g, b)                                │   │
│  │    b. Chiama is_green_pixel(r, g, b)                     │   │
│  │    c. Se True → Aggiungi a green_pixels[]                │   │
│  │ 3. Raggruppa pixel in cluster (BFS):                     │   │
│  │    → cluster_pixels() con clustering_radius              │   │
│  │ 4. Per ogni cluster:                                     │   │
│  │    → Calcola centroide (avg_x, avg_y)                    │   │
│  │    → Calcola avg_saturation, score                       │   │
│  │    → FILTRA pixel dispersi (compactness check)           │   │
│  │      ⚠️ Puntini BIANCHI: compactness < 1.0 (stringente) │   │
│  │    → Se passa filtri: aggiungi a dots[]                  │   │
│  │ 5. Restituisce Dict con dots, total_dots, statistiche    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│          CORE - src/green_dots_processor.py                      │
│           def is_green_pixel(r, g, b) → bool                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 🚨 PUNTO CRITICO - Qui avviene il filtering HSV          │   │
│  │                                                           │   │
│  │ 1. Converte RGB → HSV usando rgb_to_hsv()                │   │
│  │ 2. Check puntini VERDI:                                  │   │
│  │    is_green = (                                           │   │
│  │        self.hue_min <= h <= self.hue_max      ← 60-150°  │   │
│  │        AND s >= self.saturation_min           ← ≥15%     │   │
│  │        AND self.value_min <= v <= self.value_max ← 15-95%│   │
│  │    )                                                      │   │
│  │ 3. Check puntini BIANCHI (hardcoded):                    │   │
│  │    is_white = (s <= 20 AND 78 <= v <= 95)                │   │
│  │ 4. return is_green OR is_white                           │   │
│  │                                                           │   │
│  │ ⚠️ PROBLEMA: Se Hue non è in [60-150], il pixel viene    │   │
│  │    scartato anche se soddisfa is_white perché la logica  │   │
│  │    valuta prima is_green con AND dei 3 parametri.        │   │
│  │    I puntini bianchi hanno Hue=15-31° → ESCLUSI!         │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              RISULTATI ritornano all'API                         │
│         (percorso inverso attraverso lo stack)                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ - total_dots: 9 (invece di 10 desiderati)                │   │
│  │ - warning: "Rilevati 9 punti invece di 10"               │   │
│  │ - overlay: immagine con solo i 9 punti rilevati          │   │
│  │ - groups: None (serve esattamente 10 per dividere)       │   │
│  │ - coordinates: None                                      │   │
│  │ - statistics: None                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 FRONTEND - Gestione Risposta                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Salva window.greenDotsData = result                   │   │
│  │ 2. Chiama updateMeasurementsFromGreenDots(result)        │   │
│  │ 3. Feedback vocale con analisi differenze                │   │
│  │ 4. Attiva asse simmetria (se non attivo)                 │   │
│  │ 5. Espande sezione CORREZIONE SOPRACCIGLIA               │   │
│  │ 6. Ridisegna canvas con overlay                          │   │
│  │ 7. Toast: "Rilevamento completato: 9 punti verdi"        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 ANALISI DETTAGLIATA DELLE IMMAGINI TEST

### Immagine: successo.jpg
```
📐 DIMENSIONI: 3024 x 4032 pixels
📄 FORMATO: JPEG
📸 EXIF Orientation: None
🎨 Media RGB: [169.3, 157.4, 153.0]

🎯 RILEVAMENTO (con preprocessing MediaPipe):
   - Puntini rilevati: 9 / 10 richiesti
   - Pixel totali: 114
   - Immagine processata: 1400 x 1866

📍 CARATTERISTICHE PUNTINI RILEVATI:
   Puntino 1: Hue=31.4°, Sat=9.9%,  Val=88.3%, Size=25px
   Puntino 2: Hue=20.4°, Sat=7.7%,  Val=88.1%, Size=16px
   Puntino 3: Hue=19.3°, Sat=15.2%, Val=88.7%, Size=13px
   Puntino 4: Hue=21.8°, Sat=11.6%, Val=92.8%, Size=13px
   Puntino 5: Hue=15.7°, Sat=11.9%, Val=89.8%, Size=10px
   Puntino 6: Hue=26.3°, Sat=14.8%, Val=89.7%, Size=9px
   Puntino 7: Hue=24.9°, Sat=8.6%,  Val=87.6%, Size=8px
   Puntino 8: Hue=20.9°, Sat=16.7%, Val=85.0%, Size=7px
   Puntino 9: Hue=28.2°, Sat=8.8%,  Val=87.0%, Size=4px

🔬 ANALISI HSV:
   - Hue medio: 15-31° (Rosso/Arancione chiaro, NON verde!)
   - Saturazione: 7-17% (MOLTO BASSA, colori desaturati/bianchi)
   - Value: 85-93% (ALTA luminosità, tipico del bianco)
```

### Immagine: fallisce.JPG
```
📐 DIMENSIONI: 4032 x 3024 pixels (landscape)
📄 FORMATO: MPO (Multi Picture Object - formato iPhone stereo)
📸 EXIF Orientation: 8 (Rotazione 90° CCW)
🎨 Media RGB: [166.7, 142.2, 131.7]

🎯 RILEVAMENTO (con preprocessing MediaPipe):
   - Puntini rilevati: 9 / 10 richiesti
   - Pixel totali: 307
   - Immagine processata: 1400 x 1866

📍 CARATTERISTICHE PUNTINI RILEVATI:
   Puntino 1: Hue=21.4°, Sat=18.5%, Val=87.3%, Size=51px
   Puntino 2: Hue=16.0°, Sat=19.7%, Val=90.7%, Size=41px
   Puntino 3: Hue=25.9°, Sat=13.8%, Val=88.3%, Size=39px
   Puntino 4: Hue=31.1°, Sat=16.1%, Val=90.3%, Size=26px
   Puntino 5: Hue=26.7°, Sat=16.5%, Val=86.5%, Size=22px
   Puntino 6: Hue=22.0°, Sat=19.3%, Val=80.9%, Size=21px
   Puntino 7: Hue=27.1°, Sat=15.0%, Val=91.5%, Size=21px
   Puntino 8: Hue=20.7°, Sat=19.7%, Val=79.3%, Size=11px
   Puntino 9: Hue=20.2°, Sat=20.0%, Val=79.7%, Size=6px

🔬 ANALISI HSV:
   - Hue medio: 16-31° (Rosso/Arancione chiaro, NON verde!)
   - Saturazione: 13-20% (BASSA, colori desaturati/bianchi)
   - Value: 79-91% (ALTA luminosità, tipico del bianco)
```

---

## 🚨 PROBLEMI IDENTIFICATI

### 1. **MISMATCH PARAMETRI HSV**

**Parametri passati dal frontend (main.js linea 6138-6143):**
```javascript
hue_range: [60, 150],      // Range per VERDE
saturation_min: 15,         // OK per bianchi
value_range: [15, 95],      // Troppo ampio
```

**Valori HSV reali dei puntini bianchi nelle immagini:**
```
Hue:        15-31°    ← FUORI dal range [60-150]!
Saturation: 7-20%     ← OK, sotto 20%
Value:      79-93%    ← OK, ma range [15-95] troppo ampio
```

**CONCLUSIONE**: I puntini hanno Hue di 15-31° (arancione/rosso chiaro) che è **ESCLUSO** dal range 60-150° (verde/giallo-verde).

### 2. **LOGICA is_green_pixel() INEFFICIENTE**

Il metodo `is_green_pixel()` in [src/green_dots_processor.py](src/green_dots_processor.py#L106-L128) ha questa logica:

```python
def is_green_pixel(self, r: int, g: int, b: int) -> bool:
    h, s, v = self.rgb_to_hsv(r, g, b)
    
    # Check per puntini verdi (originale)
    is_green = (
        self.hue_min <= h <= self.hue_max           # 60 <= h <= 150
        and s >= self.saturation_min                # s >= 15
        and self.value_min <= v <= self.value_max   # 15 <= v <= 95
    )
    
    # Check per puntini bianchi (luminosità minima 78)
    is_white = (s <= 20 and 78 <= v <= 95)
    
    return is_green or is_white
```

**PROBLEMA**: Il check `is_green` usa **AND** di tre condizioni. Se il pixel ha:
- Hue = 20° (fuori range 60-150) → `is_green = False`
- Anche se `is_white = True`, la logica OR li salva

**MA**: Il vero problema è nei **parametri di costruzione** del `GreenDotsProcessor`:

```python
# Backend: webapp/api/main.py linea 891-896
processor = GreenDotsProcessor(
    hue_range=(60, 150),      # ← ESCLUDE Hue 15-31°
    saturation_min=15,
    value_range=(15, 95),
    cluster_size_range=(2, 150),
    clustering_radius=2
)
```

Questi parametri vengono salvati come `self.hue_min, self.hue_max` che vengono usati nel check `is_green`. 

**Tuttavia**, guardando meglio il codice, vedo che `is_white` è **hardcoded** e non dipende dai parametri del costruttore! Quindi il pixel con Hue=20° dovrebbe passare tramite `is_white`.

### 3. **POSSIBILE FILTRO SUCCESSIVO**

Il problema potrebbe essere nei **filtri post-clustering** in [detect_green_dots()](src/green_dots_processor.py#L210-L250):

```python
# FILTRA: puntini bianchi (bassa saturazione) devono avere almeno 3 pixel
if avg_saturation <= 20 and len(cluster) < 3:
    continue  # Scarta puntino bianco troppo piccolo

# FILTRA: esclude puntini con bordi non definiti (pixel dispersi)
compactness = std_dev / math.sqrt(len(cluster))

# Soglia più stringente per puntini BIANCHI
if avg_saturation <= 20:
    if compactness >= 1.0:  # ← MOLTO STRINGENTE
        continue
```

**PROBLEMA IDENTIFICATO**: Il filtro di **compactness per puntini bianchi è troppo stringente** (`< 1.0`). Questo potrebbe escludere puntini validi che sono leggermente meno compatti.

### 4. **PREPROCESSING MEDIAPIPE**

Il preprocessing con MediaPipe:
1. Scala l'immagine a 1400px di larghezza
2. Rileva le sopracciglia con Face Mesh
3. Estrae ROI delle sopracciglia su sfondo bianco

**POSSIBILI PROBLEMI**:
- Se MediaPipe non rileva correttamente il volto → usa fallback con bounding box fissi
- Lo scaling potrebbe degradare i puntini più piccoli
- Il ritaglio potrebbe escludere puntini al bordo

### 5. **FORMATO IMMAGINE DIVERSO**

- **successo.jpg**: JPEG standard, nessuna rotazione EXIF
- **fallisce.JPG**: **MPO** (Multi Picture Object), Orientation=8 (rotazione 90°)

Il formato MPO è usato da iPhone per foto stereo/3D. Il preprocessing dovrebbe gestire la rotazione EXIF, ma potrebbe esserci qualche problema nella conversione.

---

## 📊 RISULTATI COMPARATI

| Caratteristica           | successo.jpg | fallisce.JPG | Note |
|-------------------------|--------------|--------------|------|
| **Dimensioni originali** | 3024×4032    | 4032×3024    | Entrambe ~12MP |
| **Formato**              | JPEG         | MPO          | MPO = iPhone stereo |
| **Orientation EXIF**     | None         | 8 (90° CCW)  | Richiede rotazione |
| **Puntini rilevati**     | **9**        | **9**        | Serve 10 |
| **Pixel rilevati**       | 114          | 307          | fallisce ha più pixel |
| **Hue medio puntini**    | 15-31°       | 16-31°       | Entrambi FUORI range 60-150° |
| **Sat media puntini**    | 7-17%        | 13-20%       | Entrambi OK per bianchi |
| **Val media puntini**    | 85-93%       | 79-91%       | Entrambi alta luminosità |
| **Dimensione cluster**   | 4-25px       | 6-51px       | fallisce ha cluster più grandi |

---

## 💡 CAUSE PRINCIPALI DEL FALLIMENTO

### 🔴 CAUSA PRIMARIA: Range Hue Errato

I puntini sono **BIANCHI/BIANCASTRI** con tonalità nel rosso-arancione chiaro (Hue 15-31°), ma il sistema cerca puntini con Hue nel **verde-giallo** (60-150°).

**Impatto**: I pixel vengono comunque rilevati grazie al check `is_white` hardcoded, quindi questo NON è il problema principale.

### 🔴 CAUSA SECONDARIA: Filtro Compactness Troppo Stringente

Il filtro di compattezza per puntini bianchi richiede `compactness < 1.0`, che è **MOLTO stringente**. Questo potrebbe escludere il 10° puntino che è leggermente più disperso.

### 🟡 CAUSA TERZIARIA: Preprocessing MediaPipe

Se MediaPipe non rileva correttamente le sopracciglia (es. angolazione viso, illuminazione), la ROI estratta potrebbe:
- Escludere un puntino posizionato al bordo
- Includere troppo rumore che viene confuso con puntini

### 🟡 CAUSA MINORE: Formato MPO

Il formato MPO di iPhone richiede gestione EXIF Orientation. Anche se il codice ha `_fix_image_orientation()`, potrebbero esserci edge case non gestiti.

---

## 🔧 RACCOMANDAZIONI PER MIGLIORARE IL SISTEMA

### 1. **OTTIMIZZARE PARAMETRI HSV PER PUNTINI BIANCHI**

**Modifica frontend**: [webapp/static/js/main.js](webapp/static/js/main.js#L6138-6143)

```javascript
// PRIMA (ottimizzato per verdi):
result = await analyzeGreenDotsViaAPI(canvasImageData, {
  hue_range: [60, 150],      // ❌ Esclude bianchi (15-31°)
  saturation_min: 15,
  value_range: [15, 95],
  cluster_size_range: [2, 150],
  clustering_radius: 2
});

// DOPO (ottimizzato per bianchi):
result = await analyzeGreenDotsViaAPI(canvasImageData, {
  hue_range: [0, 360],       // ✅ Qualsiasi tonalità (per bianchi)
  saturation_min: 0,         // ✅ Nessun minimo (bianchi hanno sat bassa)
  value_range: [70, 100],    // ✅ Solo alta luminosità
  cluster_size_range: [3, 150],  // ✅ Min 3 pixel (più robusto)
  clustering_radius: 3       // ✅ Radius più ampio
});
```

### 2. **RILASSARE FILTRO COMPACTNESS**

**Modifica backend**: [src/green_dots_processor.py](src/green_dots_processor.py#L233-236)

```python
# PRIMA:
if avg_saturation <= 20:
    if compactness >= 1.0:  # ❌ Troppo stringente
        continue

# DOPO:
if avg_saturation <= 20:
    if compactness >= 1.5:  # ✅ Più permissivo per bianchi
        continue
    # Inoltre, verifica che il cluster abbia almeno 3 pixel
    if len(cluster) < 3:
        continue
```

### 3. **AGGIUNGERE PARAMETRO MODALITÀ**

Modificare il costruttore per supportare due modalità:

```python
class GreenDotsProcessor:
    def __init__(
        self,
        mode: str = "green",  # "green" o "white"
        hue_range: Tuple[int, int] = None,
        saturation_min: int = None,
        value_range: Tuple[int, int] = None,
        cluster_size_range: Tuple[int, int] = (4, 170),
        clustering_radius: int = 3,
    ):
        # Preset per modalità
        if mode == "white":
            self.hue_min, self.hue_max = (0, 360) if hue_range is None else hue_range
            self.saturation_min = 0 if saturation_min is None else saturation_min
            self.value_min, self.value_max = (70, 100) if value_range is None else value_range
            self.compactness_threshold = 1.5  # Più permissivo
        else:  # green
            self.hue_min, self.hue_max = (125, 185) if hue_range is None else hue_range
            self.saturation_min = 50 if saturation_min is None else saturation_min
            self.value_min, self.value_max = (15, 55) if value_range is None else value_range
            self.compactness_threshold = 2.5
```

### 4. **MIGLIORARE GESTIONE PREPROCESSING**

- Verificare che MediaPipe rilevi correttamente entrambi i sopracciglia
- Se fallisce, usare bounding box più ampi come fallback
- Salvare immagine di debug con maschere MediaPipe per analisi

### 5. **AGGIUNGERE LOGGING DETTAGLIATO**

Aggiungere log per capire dove vengono persi i puntini:

```python
def detect_green_dots(self, image: Image.Image) -> Dict:
    # ...
    print(f"🔍 Pixel candidati (pre-clustering): {len(green_pixels)}")
    clusters = self.cluster_pixels(green_pixels)
    print(f"🔍 Cluster trovati (post-clustering): {len(clusters)}")
    
    filtered_count = 0
    for cluster in clusters:
        # ... calcoli ...
        
        # Log filtri
        if avg_saturation <= 20 and len(cluster) < 3:
            filtered_count += 1
            print(f"   ❌ Cluster filtrato: size={len(cluster)} < 3 (bianco troppo piccolo)")
            continue
        
        if compactness >= threshold:
            filtered_count += 1
            print(f"   ❌ Cluster filtrato: compactness={compactness:.2f} >= {threshold} (bordi non definiti)")
            continue
        
        # ... aggiungi a dots ...
    
    print(f"🔍 Cluster filtrati: {filtered_count}")
    print(f"✅ Puntini finali: {len(dots)}")
```

### 6. **SUPPORTARE MODALITÀ IBRIDA**

Modificare `is_green_pixel()` per essere più intelligente:

```python
def is_green_pixel(self, r: int, g: int, b: int) -> bool:
    h, s, v = self.rgb_to_hsv(r, g, b)
    
    # PRIORITÀ 1: Check per bianchi (più specifico)
    is_white = (s <= 20 and 78 <= v <= 95)
    if is_white:
        return True
    
    # PRIORITÀ 2: Check per verdi (originale)
    is_green = (
        self.hue_min <= h <= self.hue_max
        and s >= self.saturation_min
        and self.value_min <= v <= self.value_max
    )
    
    return is_green
```

Questo garantisce che i pixel bianchi vengano rilevati indipendentemente dai parametri HSV del costruttore.

---

## 📈 STIMA IMPATTO MODIFICHE

| Modifica | Complessità | Impatto | Priorità |
|----------|------------|---------|----------|
| **1. Ottimizzare parametri HSV frontend** | 🟢 Bassa | 🔴 Alto | ⭐⭐⭐⭐⭐ |
| **2. Rilassare filtro compactness** | 🟢 Bassa | 🟡 Medio | ⭐⭐⭐⭐ |
| **3. Aggiungere modalità white/green** | 🟡 Media | 🔴 Alto | ⭐⭐⭐⭐ |
| **4. Migliorare preprocessing MediaPipe** | 🔴 Alta | 🟡 Medio | ⭐⭐⭐ |
| **5. Aggiungere logging dettagliato** | 🟢 Bassa | 🟡 Medio | ⭐⭐⭐ |
| **6. Supportare modalità ibrida** | 🟢 Bassa | 🟢 Basso | ⭐⭐ |

---

## 🧪 TEST CONSIGLIATI POST-MODIFICA

1. **Test Parametri**:
   - Testare con parametri ottimizzati su entrambe le immagini
   - Verificare che rilevi 10 puntini

2. **Test Robustezza**:
   - Testare con immagini a diverse risoluzioni
   - Testare con diversi formati (JPEG, PNG, MPO)
   - Testare con diverse illuminazioni

3. **Test Regressione**:
   - Verificare che i puntini VERDI continuino a funzionare
   - Testare modalità ibrida (verdi + bianchi nella stessa immagine)

4. **Test Edge Cases**:
   - Immagini con orientamento EXIF diverso
   - Immagini con MediaPipe che fallisce rilevamento
   - Immagini con puntini parzialmente visibili

---

## 📁 FILE COINVOLTI NEL PROCESSO

### Frontend
1. **[webapp/index.html](webapp/index.html#L203-204)** - Pulsante "Trova Differenze"
2. **[webapp/static/js/main.js](webapp/static/js/main.js#L6062-6250)** - Logica frontend
   - `toggleGreenDots()` - Gestisce click pulsante
   - `detectGreenDots()` - Prepara e chiama API
   - `getCanvasImageAsBase64()` - Estrae immagine canvas

### Backend API
3. **[webapp/api/main.py](webapp/api/main.py#L1586-1680)** - Endpoint API
   - `POST /api/green-dots/analyze` - Endpoint principale
   - `process_green_dots_analysis()` - Processing logica

### Core Processing
4. **[src/green_dots_processor.py](src/green_dots_processor.py)** - Algoritmo rilevamento
   - Classe `GreenDotsProcessor` (linea 34)
   - `process_pil_image()` (linea 1106) - Entry point
   - `preprocess_for_detection()` (linea 416) - Preprocessing MediaPipe
   - `detect_green_dots()` (linea 176) - Core algorithm
   - `is_green_pixel()` (linea 106) - Filtro HSV
   - `cluster_pixels()` (linea 130) - Clustering BFS

### Configurazione
5. **Parametri di default**:
   - Frontend: [main.js](webapp/static/js/main.js#L6138-6143)
   - Backend: [green_dots_processor.py](src/green_dots_processor.py#L41-47)

---

## 🎯 CONCLUSIONI FINALI

### Problema Principale
Il sistema è configurato per rilevare **puntini VERDI** ma le immagini contengono **puntini BIANCHI** con caratteristiche HSV completamente diverse.

### Perché rileva 9 invece di 0?
Il check `is_white` hardcoded permette di rilevare pixel bianchi indipendentemente dai parametri HSV, ma il 10° puntino viene probabilmente scartato dal **filtro di compactness troppo stringente**.

### Perché entrambe le immagini hanno lo stesso problema?
Entrambe hanno puntini bianchi con caratteristiche HSV simili (Hue 15-31°, Sat 7-20%, Val 79-93%). Il problema non è legato al formato o all'orientamento, ma ai **parametri di rilevamento inadeguati**.

### Soluzione Immediata (Quick Fix)
Modificare i parametri in [webapp/static/js/main.js](webapp/static/js/main.js#L6138) come indicato nella raccomandazione 1.

### Soluzione Definitiva (Architetturale)
Implementare modalità selezionabile "green" vs "white" con preset ottimizzati per ciascun tipo di puntino.

---

**Fine Analisi - 29 Gennaio 2026**
