# Feature Spec: Social Dominance Geometry

## Obiettivo

Implementare una funzione che calcoli e visualizzi il **"Dominance Score"** di un viso, basato su parametri geometrici scientificamente documentati. Il risultato indica dove si colloca il viso del cliente su uno spettro tra **"percepito come empatico/affidabile"** e **"percepito come dominante/autorevole"**, con indicazioni su come la dermopigmentazione può modulare questa percezione.

---

## Contesto tecnico

- La webapp usa già **MediaPipe FaceMesh** con landmark attivi
- Esiste già un sistema di rilevamento e misurazione di elementi del viso tramite pulsanti
- La funzione si aggiunge come nuova voce a quel sistema esistente
- L'immagine del viso deve essere frontale per risultati affidabili

---

## Parametri da calcolare

### 1. fWHR — Facial Width-to-Height Ratio (parametro principale)

```
fWHR = larghezza_bizigomatica / altezza_viso_superiore
```

**Landmark MediaPipe da usare:**

| Misura | Landmark sinistro | Landmark destro |
|---|---|---|
| Larghezza bizigomatica | 234 | 454 |
| Labbro superiore (base altezza) | 0 | — |
| Sopracciglio (tetto altezza) | 105 | 334 |

L'altezza è la media tra i due sopracciglia:
```
altezza = y(labbro_superiore) - media(y(sopracciglio_sx), y(sopracciglio_dx))
larghezza = distanza_euclidea(punto_234, punto_454)
fWHR = larghezza / altezza
```

**Scala interpretativa:**

| fWHR | Percezione |
|---|---|
| < 1.7 | Empatico, affidabile, avvicinabile |
| 1.7 — 2.0 | Neutro / bilanciato |
| > 2.0 | Dominante, autorevole, competitivo |

---

### 2. Angolo Mandibolare — contributo secondario

Misura la prominenza del mento rispetto alla larghezza della mandibola.

```
angolo_mandibolare = altezza_mento / larghezza_mandibola
```

**Landmark MediaPipe:**

| Misura | Landmark |
|---|---|
| Punta del mento | 152 |
| Angolo mandibola sinistra | 172 |
| Angolo mandibola destra | 397 |
| Larghezza mandibola | distanza(172, 397) |
| Altezza mento | distanza verticale tra 152 e midpoint(172,397) |

Mento prominente → aumenta percezione di dominanza.

---

### 3. Posizione Sopracciglio — contributo secondario

Misura quanto il sopracciglio è basso rispetto all'occhio.

```
eyebrow_ratio = distanza(sopracciglio, occhio) / altezza_occhio
```

**Landmark MediaPipe:**

| Misura | Landmark |
|---|---|
| Sopracciglio sx (punto centrale) | 105 |
| Occhio sx (punto superiore) | 159 |
| Occhio sx (punto inferiore) | 145 |

Sopracciglio basso e orizzontale → aumenta percezione di autorità.

---

## Dominance Score composito

Combinare i tre parametri in un unico score normalizzato 0–100:

```javascript
function calcDominanceScore(fWHR, jawAngle, browRatio) {

  // Normalizzazione fWHR: range reale ~1.4–2.4, mappa su 0–100
  const fwhrScore = ((fWHR - 1.4) / (2.4 - 1.4)) * 100;

  // Normalizzazione angolo mandibolare: range ~0.2–0.6
  const jawScore = ((jawAngle - 0.2) / (0.6 - 0.2)) * 100;

  // Normalizzazione sopracciglio: ratio basso = più dominante
  // range ~0.2–0.8, invertito (basso = alto score)
  const browScore = 100 - ((browRatio - 0.2) / (0.8 - 0.2)) * 100;

  // Pesi: fWHR è il parametro principale
  const score = (fwhrScore * 0.6) + (jawScore * 0.2) + (browScore * 0.2);

  return Math.max(0, Math.min(100, score));
}
```

---

## Output UI

### Spettro orizzontale

Visualizzare uno slider non interattivo con il punteggio posizionato:

```
Empatico ◄────────────●────────────► Dominante
         0           50            100
```

Con etichette descrittive sul valore:
- 0–30 → "Percepito come molto empatico e affidabile"
- 31–50 → "Bilanciato, tende all'accessibilità"
- 51–70 → "Bilanciato, tende all'autorevolezza"
- 71–100 → "Percepito come molto dominante e autorevole"

---

### Dettaglio parametri

Mostrare sotto lo spettro i 3 parametri singoli con il loro contributo:

```
fWHR:               1.85  ████████░░  (principale)
Angolo mandibola:   0.41  ██████░░░░
Posizione sopracciglio: 0.35  ███░░░░░░░
```

---

### Sezione "Come modulare"

Testo dinamico generato in base al punteggio che suggerisce interventi di dermopigmentazione:

| Score | Suggerimento |
|---|---|
| Score basso (< 40) | "Sopracciglio più orizzontale e leggermente abbassato può aumentare la percezione di autorevolezza" |
| Score alto (> 70) | "Sopracciglio più arcuato e sollevato può bilanciare la dominanza visiva verso maggiore accessibilità" |
| Score neutro | "Il viso è già bilanciato tra autorevolezza e accessibilità" |

---

## Note implementative

- Calcolare solo se il viso è sufficientemente frontale (verificare con angolo yaw dei landmark MediaPipe, accettare solo ±15°)
- Tutti i calcoli usano **distanze normalizzate** rispetto all'altezza totale del viso per essere indipendenti dalla dimensione dell'immagine
- Il risultato va mostrato solo come **indicatore percettivo**, non come giudizio estetico assoluto
- Aggiungere tooltip che cita la fonte scientifica: *Facial Width-to-Height Ratio (Weston et al., 2007 / Carré & McCormick, 2008)*

---

## Riferimenti scientifici

- Weston, E.M. et al. (2007). *Biometric evidence that sexual selection has shaped the hominin face.* PLOS ONE.
- Carré, J.M. & McCormick, C.M. (2008). *In your face: facial metrics predict aggressive behaviour.* Proceedings of the Royal Society B.
- Todorov, A. et al. (2008). *Understanding evaluation of faces on social dimensions.* Trends in Cognitive Sciences.
