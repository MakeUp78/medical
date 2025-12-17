/*
 * Sistema di Face Detection - Integrazione MediaPipe per rilevamento landmarks facciali
 */

// === VARIABILI GLOBALI FACE DETECTION ===

let faceLandmarker = null;
let isMediaPipeLoaded = false;
let detectionRunning = false;

// Configurazione MediaPipe
const MEDIAPIPE_CONFIG = {
  baseOptions: {
    modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
    delegate: "GPU"
  },
  outputFaceBlendshapes: true,
  outputFacialTransformationMatrixes: true,
  runningMode: "IMAGE",
  numFaces: 1
};

// === INIZIALIZZAZIONE MEDIAPIPE ===

async function initializeMediaPipe() {
  if (isMediaPipeLoaded) return true;

  try {
    // Carica MediaPipe Tasks Vision
    console.log('🔄 Caricamento MediaPipe...');

    // Importa la libreria MediaPipe
    const { FaceLandmarker, FilesetResolver } = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/vision_bundle.js');

    // Crea il resolver per i file del modello
    const vision = await FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm'
    );

    // Inizializza il face landmarker
    faceLandmarker = await FaceLandmarker.createFromOptions(vision, MEDIAPIPE_CONFIG);

    isMediaPipeLoaded = true;
    console.log('✅ MediaPipe inizializzato con successo');

    // Aggiorna UI
    updateDetectionStatus('ready');

    return true;

  } catch (error) {
    console.error('❌ Errore inizializzazione MediaPipe:', error);
    showToast('Errore caricamento sistema di rilevamento', 'error');
    updateDetectionStatus('error');
    return false;
  }
}

function updateDetectionStatus(status) {
  const statusElement = document.getElementById('detection-status');
  const detectButton = document.getElementById('detect-landmarks-btn');

  if (!statusElement || !detectButton) return;

  switch (status) {
    case 'loading':
      statusElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Caricamento...';
      statusElement.className = 'detection-status loading';
      detectButton.disabled = true;
      break;

    case 'ready':
      statusElement.innerHTML = '<i class="fas fa-check-circle"></i> Pronto';
      statusElement.className = 'detection-status ready';
      detectButton.disabled = false;
      break;

    case 'detecting':
      statusElement.innerHTML = '<i class="fas fa-eye"></i> Rilevamento...';
      statusElement.className = 'detection-status detecting';
      detectButton.disabled = true;
      break;

    case 'error':
      statusElement.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Errore';
      statusElement.className = 'detection-status error';
      detectButton.disabled = true;
      break;
  }
}

// === RILEVAMENTO LANDMARKS ===

/**
 * Prova il rilevamento tramite API backend
 */
async function tryAPIDetection(imageSource) {
  try {
    // Converti immagine in base64
    const base64Image = await imageToBase64(imageSource);
    if (!base64Image) return null;

    // Chiamata API per analisi
    const result = await analyzeImageViaAPI(base64Image);
    if (result && result.landmarks) {
      console.log('✅ Landmarks rilevati tramite API backend');
      return {
        landmarks: result.landmarks,
        score: result.score,
        components: result.score_components
      };
    }
  } catch (error) {
    console.log('💡 API non disponibile, uso MediaPipe locale:', error.message);
  }
  return null;
}

/**
 * Converte un'immagine in base64
 */
async function imageToBase64(imageSource) {
  try {
    let canvas = document.createElement('canvas');
    let ctx = canvas.getContext('2d');
    let img;

    // Gestisci diversi tipi di input
    if (typeof imageSource === 'string') {
      img = await loadImageFromURL(imageSource);
    } else if (imageSource instanceof File) {
      img = await loadImageFromFile(imageSource);
    } else if (imageSource instanceof HTMLImageElement) {
      img = imageSource;
    } else {
      return null;
    }

    canvas.width = img.width;
    canvas.height = img.height;
    ctx.drawImage(img, 0, 0);

    return canvas.toDataURL('image/jpeg', 0.8).split(',')[1]; // Rimuovi prefisso data:image
  } catch (error) {
    console.error('Errore conversione base64:', error);
    return null;
  }
}

async function detectFaceLandmarks(imageSource) {
  if (detectionRunning) {
    console.log('⚠️ Rilevamento già in corso');
    return;
  }

  // Prova prima con l'API backend se disponibile
  const apiResult = await tryAPIDetection(imageSource);
  if (apiResult) {
    return apiResult;
  }

  // Fallback a MediaPipe locale se API non disponibile
  if (!isMediaPipeLoaded) {
    showToast('Sistema di rilevamento non ancora caricato', 'warning');
    await initializeMediaPipe();
    if (!isMediaPipeLoaded) return;
  }

  try {
    detectionRunning = true;
    updateDetectionStatus('detecting');

    let imageElement;

    // Gestisci diversi tipi di input
    if (typeof imageSource === 'string') {
      // URL o data URL
      imageElement = await loadImageFromURL(imageSource);
    } else if (imageSource instanceof File) {
      // File immagine
      imageElement = await loadImageFromFile(imageSource);
    } else if (imageSource instanceof HTMLImageElement) {
      // Elemento img già esistente
      imageElement = imageSource;
    } else {
      throw new Error('Tipo di immagine non supportato');
    }

    // Esegui rilevamento
    const results = faceLandmarker.detect(imageElement);

    if (results.faceLandmarks && results.faceLandmarks.length > 0) {
      // Converti landmarks in coordinate canvas
      const landmarks = convertLandmarksToCanvas(results.faceLandmarks[0], imageElement);

      // Disegna landmarks sul canvas
      drawLandmarks(landmarks);

      // Calcola e mostra score se disponibile
      if (typeof calculateFacialScore === 'function') {
        const score = calculateFacialScore(landmarks, imageElement);
        updateScoringInfo(score);
        updateQualityBadge(score);
      }

      // Aggiorna statistiche
      updateLandmarkStatistics(landmarks);

      console.log(`✅ Rilevati ${landmarks.length} landmarks`);
      showToast(`${landmarks.length} punti facciali rilevati`, 'success');

    } else {
      console.log('⚠️ Nessun volto rilevato nell\'immagine');
      showToast('Nessun volto rilevato nell\'immagine', 'warning');
      clearLandmarks();
    }

  } catch (error) {
    console.error('❌ Errore durante il rilevamento:', error);
    showToast('Errore durante il rilevamento dei landmarks', 'error');

  } finally {
    detectionRunning = false;
    updateDetectionStatus('ready');
  }
}

// === CONVERSIONE COORDINATE ===

function convertLandmarksToCanvas(landmarks, imageElement) {
  if (!currentImage || !fabricCanvas) return [];

  const canvasLandmarks = [];

  // Ottieni dimensioni e posizione dell'immagine nel canvas
  const imgBounds = currentImage.getBoundingRect();
  const imgScaleX = imgBounds.width / imageElement.naturalWidth;
  const imgScaleY = imgBounds.height / imageElement.naturalHeight;

  landmarks.forEach(landmark => {
    // Converti da coordinate normalizzate (0-1) a coordinate canvas
    const canvasX = imgBounds.left + (landmark.x * imgBounds.width);
    const canvasY = imgBounds.top + (landmark.y * imgBounds.height);

    canvasLandmarks.push({
      x: canvasX,
      y: canvasY,
      z: landmark.z || 0,
      visibility: landmark.visibility || 1.0
    });
  });

  return canvasLandmarks;
}

// === CARICAMENTO IMMAGINI ===

function loadImageFromURL(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';

    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Errore caricamento immagine da URL'));

    img.src = url;
  });
}

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      const img = new Image();

      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('Errore caricamento immagine da file'));

      img.src = e.target.result;
    };

    reader.onerror = () => reject(new Error('Errore lettura file'));
    reader.readAsDataURL(file);
  });
}

// === STATISTICHE E ANALISI ===

function updateLandmarkStatistics(landmarks) {
  if (!landmarks || landmarks.length === 0) return;

  // Calcola statistiche di base
  const stats = {
    total: landmarks.length,
    visible: landmarks.filter(l => l.visibility > 0.5).length,
    avgConfidence: landmarks.reduce((sum, l) => sum + (l.visibility || 1), 0) / landmarks.length
  };

  // Aggiorna display statistiche
  const statsElement = document.getElementById('landmarks-stats');
  if (statsElement) {
    statsElement.innerHTML = `
            <div class="stat-item">
                <span class="stat-label">Punti totali:</span>
                <span class="stat-value">${stats.total}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Visibili:</span>
                <span class="stat-value">${stats.visible}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Confidenza media:</span>
                <span class="stat-value">${(stats.avgConfidence * 100).toFixed(1)}%</span>
            </div>
        `;
  }

  console.log('📊 Statistiche landmarks:', stats);
}

function updateQualityBadge(score) {
  const badge = document.getElementById('quality-badge');
  if (!badge) return;

  let quality, className;

  if (score >= 0.85) {
    quality = 'ECCELLENTE';
    className = 'excellent';
  } else if (score >= 0.7) {
    quality = 'BUONO';
    className = 'good';
  } else if (score >= 0.5) {
    quality = 'DISCRETO';
    className = 'fair';
  } else {
    quality = 'SCARSO';
    className = 'poor';
  }

  badge.textContent = quality;
  badge.className = `quality-badge ${className}`;

  // Aggiungi animazione
  badge.style.animation = 'none';
  setTimeout(() => {
    badge.style.animation = 'pulse 0.5s ease-in-out';
  }, 10);
}

// === GESTIONE ERRORI E FALLBACK ===

function handleDetectionError(error) {
  console.error('Errore rilevamento:', error);

  const errorMessages = {
    'Model not loaded': 'Modello di rilevamento non caricato',
    'No faces detected': 'Nessun volto rilevato nell\'immagine',
    'Invalid image': 'Immagine non valida o corrotta',
    'GPU not available': 'GPU non disponibile, usando CPU'
  };

  const message = errorMessages[error.message] || 'Errore sconosciuto durante il rilevamento';
  showToast(message, 'error');

  updateDetectionStatus('error');
}

// === RILEVAMENTO BATCH ===

async function detectLandmarksFromFiles(files) {
  if (!files || files.length === 0) return;

  const results = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];

    try {
      showToast(`Elaborando immagine ${i + 1} di ${files.length}...`, 'info');

      const imageElement = await loadImageFromFile(file);
      const landmarks = await detectFaceLandmarksFromImage(imageElement);

      results.push({
        fileName: file.name,
        landmarks: landmarks,
        success: true
      });

    } catch (error) {
      console.error(`Errore elaborazione ${file.name}:`, error);
      results.push({
        fileName: file.name,
        error: error.message,
        success: false
      });
    }
  }

  showBatchResults(results);
  return results;
}

function showBatchResults(results) {
  const successful = results.filter(r => r.success).length;
  const total = results.length;

  if (successful === total) {
    showToast(`Tutte le ${total} immagini elaborate con successo`, 'success');
  } else {
    showToast(`${successful}/${total} immagini elaborate con successo`, 'warning');
  }

  // Mostra dettagli se richiesto
  console.log('📊 Risultati batch:', results);
}

async function detectLandmarksFromImage(imageElement) {
  if (!faceLandmarker) throw new Error('Face landmarker not initialized');

  const results = faceLandmarker.detect(imageElement);

  if (!results.faceLandmarks || results.faceLandmarks.length === 0) {
    throw new Error('No faces detected');
  }

  return convertLandmarksToCanvas(results.faceLandmarks[0], imageElement);
}

// === INIZIALIZZAZIONE AUTOMATICA ===

// Inizializza MediaPipe quando il documento è pronto
document.addEventListener('DOMContentLoaded', function () {
  // Inizializza MediaPipe in background
  setTimeout(() => {
    updateDetectionStatus('loading');
    initializeMediaPipe().then(success => {
      if (success) {
        console.log('🎯 Sistema di rilevamento pronto');
      }
    });
  }, 1000);
});

// === EXPORT FUNZIONI GLOBALI ===

// Rende le funzioni principali disponibili globalmente
window.detectFaceLandmarks = detectFaceLandmarks;
window.initializeMediaPipe = initializeMediaPipe;