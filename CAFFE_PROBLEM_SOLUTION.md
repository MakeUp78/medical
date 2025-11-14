# Risoluzione Problema Caffe - Face Landmark Detection

## Problema Identificato
Il file `landmarkPredict_webcam.py` utilizzava la libreria **Caffe** che non è più facilmente disponibile tramite pip, specialmente su Windows. Questo causava errori di installazione:

```
ERROR: Could not find a version that satisfies the requirement caffe-gpu
ERROR: Could not find a version that satisfies the requirement pycaffe
```

## Soluzioni Implementate

### 1. Modifica del File Originale
- **File**: `landmarkPredict_webcam.py`
- **Cambiamento**: Sostituito `import caffe` con `import mediapipe as mp`
- **Risultato**: Il codice ora usa MediaPipe per il rilevamento dei landmark facciali

### 2. Versione Migliorata
- **File**: `landmarkPredict_webcam_fixed.py`
- **Caratteristiche**:
  - Interfaccia utente migliorata
  - Gestione errori robusta
  - Controlli da tastiera (q=quit, s=save, r=reset)
  - Contatore FPS in tempo reale
  - Supporto per più volti simultanei
  - Effetto specchio per webcam

### 3. Versione con OpenCV DNN
- **File**: `landmarkPredict_webcam_opencv.py` (creato precedentemente)
- **Caratteristiche**: Alternativa che usa solo OpenCV e dlib

## Dipendenze Aggiornate

### Rimosse
- ❌ `caffe` (non disponibile)
- ❌ `caffe-gpu` (non disponibile)
- ❌ `pycaffe` (non disponibile)

### Aggiunte/Mantenute
- ✅ `mediapipe>=0.10.0` (già presente)
- ✅ `opencv-python>=4.8.0` (già presente)
- ✅ `dlib>=19.20.0` (aggiunto al requirements.txt)

## Funzionalità Mantenute

1. **Rilevamento Volti**: Funziona con MediaPipe Face Mesh
2. **Landmark Detection**: Estrae landmark facciali in tempo reale
3. **Bounding Box**: Calcola automaticamente i box intorno ai volti
4. **Visualizzazione**: Mostra landmark e box sulla webcam
5. **Performance**: Mantiene prestazioni elevate

## Come Usare

### Versione Base (Modificata)
```bash
python landmarkPredict_webcam.py
```

### Versione Migliorata (Consigliata)
```bash
python landmarkPredict_webcam_fixed.py
```

### Controlli
- **Q**: Esci dal programma
- **S**: Salva il frame corrente
- **R**: Reset del sistema di rilevamento

## Vantaggi della Soluzione

1. **Compatibilità**: Funziona su Windows senza problemi
2. **Prestazioni**: MediaPipe è ottimizzato per il tempo reale
3. **Facilità**: Non richiede installazioni complesse
4. **Aggiornamenti**: MediaPipe è attivamente mantenuto da Google
5. **Precisione**: MediaPipe fornisce rilevamento accurato

## Note Tecniche

- MediaPipe usa TensorFlow Lite internamente
- I messaggi TensorFlow all'avvio sono normali
- La webcam deve essere disponibile e accessibile
- Richiede permessi per l'accesso alla camera

## Troubleshooting

### Webcam non funziona
1. Verifica che nessun'altra app usi la webcam
2. Controlla i permessi della camera
3. Prova a cambiare l'indice della camera (0, 1, 2...)

### Performance lente
1. Riduci il numero di volti da rilevare
2. Abbassa la risoluzione della webcam
3. Usa `static_image_mode=True` per immagini singole

### Errori di import
1. Assicurati che MediaPipe sia installato: `pip install mediapipe`
2. Verifica la versione Python (>=3.7 richiesta)
3. Aggiorna pip: `python -m pip install --upgrade pip`