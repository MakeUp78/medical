# ANALISI COMPLETA CALCOLO YAW - TUTTE LE FUNZIONI COLLEGATE

## PANORAMICA DEL FLUSSO

```
Frame video → process_frame() → calculate_head_pose_from_mediapipe() → solvePnP → Yaw
                                                                           ↓
                                    calculate_face_score() ← Yaw value
                                                ↓
                                          Total Score
                                                ↓
                                    Best Frames Buffer (top 10)
```

---

## 1. FUNZIONE PRINCIPALE: `calculate_head_pose_from_mediapipe()`

**Posizione**: `websocket_frame_api.py:81-155`

**Scopo**: Calcola gli angoli di rotazione della testa (pitch, yaw, roll) dai landmark MediaPipe

### INPUT:
- `landmarks_array`: Array numpy (468, 2) con coordinate (x, y) di tutti i landmark MediaPipe
- `img_width`: Larghezza immagine in pixel
- `img_height`: Altezza immagine in pixel

### OUTPUT:
- Array numpy [pitch, yaw, roll] in gradi

### STEP BY STEP:

#### STEP 1: Selezione landmark chiave (righe 85-92)
```python
NOSE_TIP = 4          # Punta del naso
CHIN = 152            # Mento
LEFT_EYE_CORNER = 33  # Angolo interno occhio sinistro
RIGHT_EYE_CORNER = 263 # Angolo interno occhio destro
LEFT_MOUTH_CORNER = 78 # Angolo sinistro bocca
RIGHT_MOUTH_CORNER = 308 # Angolo destro bocca
```
**Perché questi punti?**
- Sono i landmark più stabili e meno affetti da espressioni facciali
- Definiscono la struttura principale del viso (profilo + simmetria)
- Sono gli stessi punti usati nel modello 3D standard

#### STEP 2: Estrazione coordinate 2D (righe 94-100)
```python
nose_tip = landmarks_array[NOSE_TIP]       # Es: [246.6, 538.0]
chin = landmarks_array[CHIN]               # Es: [255.3, 687.1]
left_eye = landmarks_array[LEFT_EYE_CORNER]  # Es: [139.8, 437.9]
right_eye = landmarks_array[RIGHT_EYE_CORNER] # Es: [352.4, 432.5]
left_mouth = landmarks_array[LEFT_MOUTH_CORNER] # Es: [195.8, 601.2]
right_mouth = landmarks_array[RIGHT_MOUTH_CORNER] # Es: [307.5, 597.1]
```
**Sistema di coordinate 2D:**
- Origine: Top-left dell'immagine
- X: positivo verso DESTRA
- Y: positivo verso BASSO

#### STEP 3: Modello 3D del viso (righe 108-116)
```python
model_points = np.array([
    (0.0, 0.0, 0.0),             # Naso (ORIGINE del modello)
    (0.0, -330.0, -65.0),        # Mento (sotto e dietro)
    (-225.0, 170.0, -135.0),     # Occhio SX (sinistra, sopra, dietro)
    (225.0, 170.0, -135.0),      # Occhio DX (destra, sopra, dietro)
    (-150.0, -150.0, -125.0),    # Bocca SX (sinistra, sotto, dietro)
    (150.0, -150.0, -125.0)      # Bocca DX (destra, sotto, dietro)
], dtype=np.float32)
```
**Sistema di coordinate 3D del MODELLO:**
- Origine: Punta del naso
- X: positivo = DESTRA del viso (dal punto di vista del viso stesso)
- Y: positivo = SU (verso la fronte)
- Z: positivo = FUORI (verso la camera)

**⚠️ CRITICO:** Questo è un modello "medio" generico:
- Le coordinate sono in unità arbitrarie (non millimetri reali)
- Rappresenta un viso "standard" che NON corrisponde al viso specifico analizzato
- È la principale fonte di imprecisione in solvePnP!

#### STEP 4: Camera Matrix (righe 118-128)
```python
focal_length = img_width  # Esempio: 464 px
center = (img_width/2, img_height/2)  # Es: (232, 416)

camera_matrix = np.array([
    [focal_length, 0, center[0]],  # [464, 0, 232]
    [0, focal_length, center[1]],  # [0, 464, 416]
    [0, 0, 1]                       # [0, 0, 1]
], dtype=np.float32)
```
**Spiegazione Camera Matrix:**
```
[fx  0  cx]
[0  fy  cy]
[0   0   1]
```
- `fx, fy`: Focal length in pixel (assume FOV specifica della camera)
- `cx, cy`: Principal point (centro ottico, assume centro immagine)

**⚠️ ASSUNZIONE CRITICA:** `focal_length = img_width`
- Questo assume un campo visivo (FOV) di circa 53° orizzontale
- Se la camera reale ha FOV diverso, gli angoli saranno SBAGLIATI!
- Esempio: iPhone camera ha FOV ~60-70° → focal dovrebbe essere ~0.7x width
- Webcam ha FOV ~70-80° → focal dovrebbe essere ~0.6x width

#### STEP 5: solvePnP (righe 130-133)
```python
success, rotation_vector, translation_vector = cv2.solvePnP(
    model_points,    # Punti 3D del modello
    image_points,    # Punti 2D osservati nell'immagine
    camera_matrix,   # Parametri intrinseci camera
    dist_coeffs      # Distorsioni (zero per semplicità)
)
```
**Cosa fa solvePnP?**
1. Prende i 6 punti 3D del modello
2. Prende i 6 punti 2D corrispondenti nell'immagine
3. Trova la rotazione + traslazione che "proietta" il modello 3D sull'immagine
4. Restituisce:
   - `rotation_vector`: Vettore di rotazione (rappresentazione axis-angle)
   - `translation_vector`: Posizione 3D del viso rispetto alla camera

**Output esempio:**
```
rotation_vector = [-3.1068, +0.0640, +0.0816]
translation_vector = [+28.15, +229.42, +866.75]
```

#### STEP 6: Conversione Rodrigues (riga 136)
```python
rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
```
**Da rotation_vector a rotation_matrix 3x3:**

Input (axis-angle): `[-3.1068, +0.0640, +0.0816]`

Output (matrice 3x3):
```
[+0.9978  -0.0420  -0.0518]
[-0.0403  -0.9986  +0.0341]
[-0.0531  -0.0320  -0.9981]
```

**Interpretazione della rotation matrix:**
- Ogni colonna rappresenta un asse del sistema di coordinate del viso
- Le righe rappresentano come questi assi sono orientati rispetto alla camera
- `R[i,j]` = componente del j-esimo asse del viso lungo l'i-esimo asse della camera

#### STEP 7: Estrazione angoli di Eulero (righe 137-149)

**Formula Yaw (rotazione orizzontale):**
```python
yaw = -np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi
```

**Spiegazione matematica:**
```
R[1,0] = sin(yaw)    # Componente Y dell'asse X del viso
R[0,0] = cos(yaw)    # Componente X dell'asse X del viso

yaw = arctan2(sin(yaw), cos(yaw))
    = arctan2(R[1,0], R[0,0])
```

**⚠️ IL SEGNO NEGATIVO (`-`):**
- È la correzione del PRIMO BIAS che abbiamo trovato!
- Senza `-`, yaw positivo significherebbe "girato a sinistra"
- Con `-`, yaw positivo significa correttamente "girato a destra"
- Questo perché il sistema di coordinate di OpenCV ha Y verso il basso

**Convenzione finale:**
- `yaw > 0` → viso girato verso la SUA DESTRA (naso verso destra dell'immagine)
- `yaw < 0` → viso girato verso la SUA SINISTRA (naso verso sinistra dell'immagine)
- `yaw ≈ 0` → viso FRONTALE

**Formula Pitch (rotazione verticale):**
```python
sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
```
- `pitch > 0` → testa inclinata SU (guarda verso l'alto)
- `pitch < 0` → testa inclinata GIÙ (guarda verso il basso)

**Formula Roll (rotazione laterale):**
```python
roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2]) * 180.0 / np.pi
```
- `roll > 0` → testa inclinata verso DESTRA (orecchio destro verso spalla)
- `roll < 0` → testa inclinata verso SINISTRA (orecchio sinistro verso spalla)

---

## 2. FUNZIONE SCORING: `calculate_face_score()`

**Posizione**: `websocket_frame_api.py:159-238`

**Scopo**: Calcola uno score 0-100 basato su pose, dimensione e posizione del viso

### INPUT:
- `pitch, yaw, roll`: Angoli in gradi da calculate_head_pose_from_mediapipe()
- `face_bbox`: [x_min, x_max, y_min, y_max] bounding box del viso
- `frame_width, frame_height`: Dimensioni del frame

### OUTPUT:
- `total_score`: Punteggio 0-100
- `score_details`: Dizionario con breakdown dettagliato

### COME USA LO YAW:

#### 1. Peso Yaw (riga 189):
```python
yaw_weighted = abs(yaw) * 2.5
```
**Spiegazione:**
- Prende il valore ASSOLUTO (non interessa se girato a dx o sx)
- Moltiplica per 2.5 (peso MASSIMO tra tutti gli angoli)
- Yaw ha priorità assoluta per frontality detection!

**Esempi:**
```
yaw = 0°   → yaw_weighted = 0.0   (perfetto!)
yaw = 2°   → yaw_weighted = 5.0
yaw = 5°   → yaw_weighted = 12.5
yaw = 10°  → yaw_weighted = 25.0  (già penalizzato molto)
```

#### 2. Combinazione con altri angoli (righe 190-192):
```python
pitch_weighted = abs(pitch) * 1.0
roll_weighted = abs(normalized_roll) * 0.3

pose_deviation = yaw_weighted + pitch_weighted + roll_weighted
```

**Confronto pesi:**
- Yaw: **2.5x** (massima priorità)
- Pitch: **1.0x** (media priorità)
- Roll: **0.3x** (bassa priorità - tollerato)

**Rationale:**
- Yaw è il più importante per frontalità (viso girato lateralmente = inutilizzabile)
- Pitch è moderato (piccola inclinazione su/giù è accettabile)
- Roll è poco importante (testa leggermente inclinata non compromette analisi)

#### 3. Conversione in score (riga 193):
```python
pose_score = max(0, 100 - pose_deviation * 0.8)
```

**Formula:**
```
pose_score = 100 - (|yaw|×2.5 + |pitch|×1.0 + |roll|×0.3) × 0.8
```

**Esempi pratici:**
```
Frame FRONTALE:
yaw=0°, pitch=0°, roll=0°
→ pose_deviation = 0
→ pose_score = 100 ✅

Frame LEGGERMENTE GIRATO:
yaw=5°, pitch=2°, roll=3°
→ pose_deviation = 5×2.5 + 2×1.0 + 3×0.3 = 14.4
→ pose_score = 100 - 14.4×0.8 = 88.5 ✅

Frame MOLTO GIRATO:
yaw=15°, pitch=5°, roll=5°
→ pose_deviation = 15×2.5 + 5×1.0 + 5×0.3 = 44.0
→ pose_score = 100 - 44.0×0.8 = 64.8 ❌ (scartato)
```

#### 4. Score finale (riga 233):
```python
total_score = (pose_score * 0.6 + size_score * 0.3 + position_score * 0.1)
```

**Distribuzione pesi:**
- Pose (yaw/pitch/roll): **60%** del punteggio finale
- Size (grandezza viso): **30%**
- Position (centramento): **10%**

**Conclusione:** Lo Yaw ha un impatto ENORME sul punteggio finale:
```
yaw contribuisce per: 2.5 × 0.8 × 0.6 = 1.2 punti persi per ogni grado
```

---

## 3. FUNZIONE PROCESSING: `process_frame()`

**Posizione**: `websocket_frame_api.py:240-380`

**Scopo**: Processa ogni frame video ricevuto via WebSocket

### UTILIZZO YAW:

#### 1. Chiamata calculate_head_pose (riga 292):
```python
head_pose = self.calculate_head_pose_from_mediapipe(all_landmarks, w, h)
# head_pose = [pitch, yaw, roll]
```

#### 2. Chiamata calculate_face_score (righe 294-296):
```python
score, score_details = self.calculate_face_score(
    head_pose[0],  # pitch
    head_pose[1],  # yaw ← USATO QUI
    head_pose[2],  # roll
    bbox, w, h
)
```

#### 3. Filtro validità (righe 298-301):
```python
is_invalid = (abs(head_pose[0]) > 170 or  # Pitch invalido
              abs(head_pose[1]) > 170)     # Yaw invalido
```
**Scarta frame con yaw > 170° (completamente di profilo o valori impossibili)**

#### 4. Storage nel buffer (riga 319):
```python
frame_data = {
    'frame': frame.copy(),
    'frame_number': current_frame_number,
    'score': score,
    'timestamp': time.time(),
    'pitch': head_pose[0],
    'yaw': head_pose[1],    # ← SALVATO QUI
    'roll': head_pose[2],
    'bbox': bbox,
    'score_details': score_details
}
```

#### 5. Invio al client (righe 369-372):
```python
response.update({
    "faces_detected": 1,
    "current_score": round(score, 2),
    "pose": {
        "pitch": round(head_pose[0], 2),
        "yaw": round(head_pose[1], 2),  # ← INVIATO AL CLIENT
        "roll": round(normalized_roll_display, 2)
    }
})
```

---

## 4. PROBLEMI IDENTIFICATI CON SOLVEPNP YAW

### BIAS #1: Segno invertito (RISOLTO)
**Problema:** Formula originale produceva yaw con semantica invertita
**Causa:** Convenzione coordinate OpenCV (Y verso basso)
**Fix:** Negare il risultato: `yaw = -arctan2(R[1,0], R[0,0])`

### BIAS #2: Errore non lineare (NON RISOLTO)
**Problema:** 
- Frame frontale (yaw reale ~0°): solvePnP calcola yaw ~+2.3° (sovrastima)
- Frame girato (yaw reale ~7°): solvePnP calcola yaw ~+0.7° (sottostima)

**Cause:**
1. `focal_length = img_width` assume FOV errata
2. Modello 3D generico non rappresenta proporzioni reali del viso
3. solvePnP è sensibile a piccoli errori nei landmark (1-2px)
4. Proiezione 3D→2D introduce ambiguità geometriche

**Errore:** Non lineare, cresce con l'angolo reale:
```
yaw_reale = 0° → errore = +2.16°
yaw_reale = 7° → errore = -6.62°
```

### BIAS #3: Dipendenza dal FOV della camera
**Problema:** Cambiando `focal_length`, cambiano gli angoli calcolati
**Test:**
```
focal = 0.5 × width → yaw = +1.57° (err 5.77°) per frame girato
focal = 1.0 × width → yaw = +0.71° (err 6.62°) per frame girato
focal = 1.5 × width → yaw = +0.88° (err 6.46°) per frame girato
focal = 2.0 × width → yaw = +1.18° (err 6.15°) per frame girato
```
**Nessuna focal length elimina completamente l'errore!**

---

## 5. ALTERNATIVA: METODO GEOMETRICO

**Vantaggi:**
- Calcolo diretto senza proiezioni 3D
- Usa riferimento interno al viso (centro occhi), non dipende da posizione nell'immagine
- Normalizzato su distanza tra occhi (scala automaticamente)
- Errore ~0.5° invece di ~6°

**Formula:**
```python
eye_center_x = (left_eye[0] + right_eye[0]) / 2
eye_distance = abs(right_eye[0] - left_eye[0])
nose_offset = nose_tip[0] - eye_center_x
yaw_geometric = (nose_offset / (eye_distance/2)) * 30
```

**Risultati:**
```
Frame frontale: yaw_geometric = +0.15° vs solvePnP = +2.31°
Frame girato:   yaw_geometric = +7.33° vs solvePnP = +0.71°
```

---

## CONCLUSIONI

**solvePnP per Yaw:**
- ✅ Funziona per rilevamento grossolano (frontale vs non frontale)
- ✅ Dopo correzione segno, semantica corretta
- ❌ Errore 2-7° non eliminabile con semplici correzioni
- ❌ Dipende da assunzioni (focal length, modello 3D) che non corrispondono alla realtà

**Metodo geometrico:**
- ✅ Errore <1° 
- ✅ Robusto e indipendente da camera
- ✅ Più semplice e veloce
- ❌ Non fornisce pitch/roll (ma solvePnP può essere usato solo per roll)

**Raccomandazione:** 
Per **rilevamento frontalità** (non ricostruzione 3D completa), 
il metodo geometrico è superiore.
