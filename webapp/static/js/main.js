/*
 * JavaScript principale - Gestione interfaccia e sezioni
 * Replica comportamenti dell'app desktop
 * 
 * VERSIONE: 2.1 - 2025-12-20 - Tabella Unificata con auto-espansione
 * ULTIMO AGGIORNAMENTO: Corretto openUnifiedAnalysisSection con log dettagliati
 */

// main.js v6.18

// ============================================================
// COSTANTI DI RISOLUZIONE — usate su tutti i tre flussi
// (webcam, video, immagine statica) per garantire che
// dlib / MediaPipe / white-dots ricevano SEMPRE la stessa
// scala e qualità JPEG, rendendo i rilevamenti coerenti.
// ============================================================
// Risoluzione massima per ANALISI (puntini, landmarks, ecc.)
// Deve coincidere con la risoluzione max del flusso più frequente (webcam desktop).
const ANALYSIS_MAX_PX = 1280;
// Risoluzione max per l'analisi WHITE DOTS (Trova Differenze).
// null = nessun resize: i dot bianchi sono piccoli (5-400px²), ridimensionare
// l'immagine cambia il blob-size e sposta le coordinate rispetto al canvas display.
const WHITE_DOTS_MAX_PX = null;
// Qualità JPEG per le immagini di analisi (uguale a webcam desktop).
const ANALYSIS_JPEG_QUALITY = 0.88;
// Risoluzione max per i frame LIVE in streaming (WebSocket).
// Mobile usa metà per ridurre latenza.
const STREAM_MAX_PX_DESKTOP = 1280;
const STREAM_MAX_PX_MOBILE = 640;

// Variabili globali (controllo per evitare ridichiarazioni)
if (typeof currentTool === 'undefined') var currentTool = 'selection';
if (typeof isWebcamActive === 'undefined') var isWebcamActive = false;
if (typeof currentImage === 'undefined') var currentImage = null;
if (typeof currentImageElement === 'undefined') var currentImageElement = null;
if (typeof currentLandmarks === 'undefined') var currentLandmarks = [];

// Array per memorizzare le linee perpendicolari all'asse (posizioni normalizzate 0-1)
if (typeof perpendicularLines === 'undefined') var perpendicularLines = [];

// Esponi currentLandmarks globalmente
window.currentLandmarks = currentLandmarks;
window.currentImage = currentImage;
window.perpendicularLines = perpendicularLines;

// ===================================
// HELPER - Interruzione sintesi vocale
// ===================================

function stopVoiceAssistant() {
  if (typeof voiceAssistant !== 'undefined' && voiceAssistant.audioPlayer) {
    console.log('🔇 Interruzione sintesi vocale...');
    voiceAssistant.audioPlayer.pause();
    voiceAssistant.audioPlayer.currentTime = 0;
    voiceAssistant.audioPlayer.src = '';
    voiceAssistant.audioPlayer.onended = null;

    // Svuota anche la coda delle frasi
    if (voiceAssistant.queue) {
      voiceAssistant.queue = [];
    }
    if (voiceAssistant.isPlaying !== undefined) {
      voiceAssistant.isPlaying = false;
    }
  }
}

// ===================================
// SISTEMA DI AUTENTICAZIONE
// ===================================

// Usa percorso relativo per funzionare tramite nginx proxy
const AUTH_SERVER_URL = window.location.origin;

/**
 * Verifica autenticazione all'avvio della pagina
 */
async function checkAuthentication() {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');

  if (!token) {
    window.location.href = '/landing.html';
    return false;
  }

  try {
    const response = await fetch(`${AUTH_SERVER_URL}/api/auth/verify`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    const data = await response.json();

    if (data.success && data.user) {
      updateUserUI(data.user);
      // Track login activity
      trackActivity('login');
      return true;
    } else {
      localStorage.removeItem('auth_token');
      sessionStorage.removeItem('auth_token');
      window.location.href = '/landing.html';
      return false;
    }
  } catch (error) {
    window.location.href = '/landing.html';
    return false;
  }
}

/**
 * Traccia attività utente
 */
async function trackActivity(actionType, details = {}) {
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (!token) return;

  try {
    await fetch(`${AUTH_SERVER_URL}/api/user/track-activity`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        action_type: actionType,
        details: details
      })
    });
  } catch (error) {
    // Silently fail - non bloccare l'app se il tracking fallisce
    console.debug('Activity tracking failed:', error);
  }
}

// Esponi trackActivity globalmente
window.trackActivity = trackActivity;

// Variabile globale per memorizzare il nome utente
window.currentUserName = '';

/**
 * Aggiorna UI con dati utente
 */
function updateUserUI(user) {
  const userNameElement = document.getElementById('user-name');
  const roleBadgeElement = document.getElementById('role-badge');
  const avatarElement = document.getElementById('user-avatar-img');

  // Salva il nome utente globalmente per l'assistente vocale
  window.currentUserName = user.firstname || '';

  // Persisti il nome per il benvenuto speculativo alla prossima visita.
  if (window.currentUserName) {
    localStorage.setItem('_kimerika_welcome_name', window.currentUserName);
  }

  // Avvia speakWelcome se non già partito in anticipo (speculativo pre-await).
  // _welcomeStarted evita doppia chiamata se updateUserUI viene invocata di nuovo.
  // _hasPendingAction: non salutare sui reload da "Avvia Webcam" / "Carica Video".
  if (window.currentUserName && typeof voiceAssistant !== 'undefined'
    && !window._welcomeStarted && !window._hasPendingAction) {
    window._welcomeStarted = true;
    voiceAssistant.speakWelcome(window.currentUserName);
  }

  if (userNameElement) {
    userNameElement.textContent = `${user.firstname} ${user.lastname}`;
  }

  if (roleBadgeElement) {
    const roleText = user.role === 'admin' ? 'Amministratore' : 'Operatore';
    roleBadgeElement.textContent = roleText;

    // Rimuovi tutte le classi role esistenti
    roleBadgeElement.classList.remove('admin', 'operator');

    // Aggiungi la classe corretta
    roleBadgeElement.classList.add(user.role);
  }

  // Aggiorna avatar se presente
  if (avatarElement && user.profile_image) {
    avatarElement.src = user.profile_image + '?t=' + Date.now();
  }

  // Mostra pulsante admin se utente e' admin
  const adminBtn = document.getElementById('admin-btn');
  if (adminBtn) {
    adminBtn.style.display = user.role === 'admin' ? 'block' : 'none';
  }

}

/**
 * Logout utente
 */
function logout() {
  localStorage.removeItem('auth_token');
  sessionStorage.removeItem('auth_token');
  window.location.href = '/landing.html';
}

// Esponi funzione logout globalmente per onclick
window.logout = logout;

// === SISTEMA SEMPLIFICATO - LANDMARKS SEMPRE DISPONIBILI ===
let landmarksAutoDetected = false;
let isDetectingLandmarks = false;
let lastImageProcessed = null;

let scoringWeights = {
  nose: 0.30,
  mouth: 0.25,
  symmetry: 0.25,
  eye: 0.20
};

// Funzione globale per gestione sezioni
window.toggleSection = function (headerElement) {
  const section = headerElement.parentElement;
  const content = section.querySelector('.section-content');
  const icon = headerElement.querySelector('.icon');

  if (!content) return;

  const isExpanded = section.dataset.expanded === 'true';

  if (isExpanded) {
    content.style.setProperty('display', 'none', 'important');
    section.dataset.expanded = 'false';
    if (icon) icon.textContent = '►';
  } else {
    content.style.setProperty('display', 'block', 'important');
    section.dataset.expanded = 'true';
    if (icon) icon.textContent = '▼';
  }

  setTimeout(() => {
    if (typeof resizeCanvas === 'function') resizeCanvas();
  }, 300);
};

// === SISTEMA SEMPLIFICATO - AUTO-RILEVAMENTO LANDMARKS ===

async function autoDetectLandmarksOnImageChange() {
  /**
   * FUNZIONE CHIAVE: Rileva automaticamente i landmarks ogni volta che cambia l'immagine
   * Chiamata da: loadImage, captureFromWebcam, updateCanvasWithBestFrame, etc.
   */
  if (!currentImage || isDetectingLandmarks) {
    return false;
  }

  // Evita rilevamento multiplo sulla stessa immagine
  const currentImageSignature = getImageSignature(currentImage);
  if (currentImageSignature === lastImageProcessed) {
    return true;
  }

  isDetectingLandmarks = true;

  try {
    const success = await detectLandmarksSilent();
    if (success) {
      landmarksAutoDetected = true;
      lastImageProcessed = currentImageSignature;
    }
    return success;
  } catch (error) {
    return false;
  } finally {
    isDetectingLandmarks = false;
  }
}

function getImageSignature(image) {
  /**
   * Crea una "firma" dell'immagine per evitare riprocessamento
   */
  if (!image) return null;

  if (image.getElement) {
    // Fabric.js image
    const element = image.getElement();
    return `fabric_${element.width}x${element.height}_${Date.now()}`;
  } else {
    // HTML image element
    return `html_${image.width}x${image.height}_${image.src?.slice(-20) || Date.now()}`;
  }
}

async function detectLandmarksSilent() {
  /**
   * Versione silenziosa di detectLandmarks() - senza toast/status
   */
  if (!currentImage) return false;

  try {
    let base64Image;

    // Acquisisce SEMPRE l'immagine originale via getElement() a piena risoluzione.
    // Non si usa mai il canvas renderizzato: i landmark restituiti sarebbero in
    // coordinate canvas (già ruotate/scalate) e corromperebbero il sistema di
    // coordinate usato da transformLandmarkCoordinate() e drawSymmetryAxis().
    if (currentImage && typeof currentImage.getElement === 'function') {
      const fabricElement = currentImage.getElement();
      // Valida che sia un tipo effettivamente disegnabile su canvas.
      // Fabric.js imposta _element in modo asincrono: nei primi ms l'oggetto
      // esiste ma non è ancora un HTMLImageElement/HTMLCanvasElement valido.
      const _DRAWABLE = [HTMLImageElement, HTMLCanvasElement, HTMLVideoElement,
        ...(typeof ImageBitmap !== 'undefined' ? [ImageBitmap] : []),
        ...(typeof OffscreenCanvas !== 'undefined' ? [OffscreenCanvas] : [])];
      const _isDrawable = fabricElement != null && _DRAWABLE.some(T => fabricElement instanceof T);
      // Per HTMLImageElement attendere il caricamento completo
      const _imgReady = !(fabricElement instanceof HTMLImageElement)
        || (fabricElement.complete && fabricElement.naturalWidth > 0);
      if (_isDrawable && _imgReady) {
        try {
          const w = fabricElement.naturalWidth || fabricElement.videoWidth || fabricElement.width;
          const h = fabricElement.naturalHeight || fabricElement.videoHeight || fabricElement.height;
          if (w > 0 && h > 0) {
            // ⚠️ LANDMARK DETECTION: NON ridimensionare qui.
            // Le coordinate restituite dal backend (normalizzate 0-1 o assolute in pixel)
            // vengono mappate tramite transformLandmarkCoordinate() che usa
            // el.naturalWidth/naturalHeight come base. Se si invia un'immagine ridotta
            // e il backend restituisce coordinate assolute, queste sarebbero nel sistema
            // dell'immagine ridotta e non in quello originale → misallineamento overlay.
            // Per la sola rilevazione landmark si usa sempre la piena risoluzione.
            const snapEl = document.createElement('canvas');
            snapEl.width = w;
            snapEl.height = h;
            snapEl.getContext('2d').drawImage(fabricElement, 0, 0, w, h);
            base64Image = snapEl.toDataURL('image/jpeg', 0.92);
          }
        } catch (elErr) {
          console.warn('🔍 detectLandmarksSilent: drawImage fallito:', elErr.message);
        }
      }
    }

    if (!base64Image) {
      return false; // Elemento non ancora pronto: verrà ritentato alla prossima chiamata
    }

    // Chiama API tramite percorso relativo (nginx proxy)
    const response = await fetch(`${window.location.origin}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: base64Image })
    });

    if (!response.ok) return false;

    const result = await response.json();

    if (result.landmarks && result.landmarks.length > 0) {
      // Coordinate restituite dal backend in pixel immagine originale.
      // refW/refH corrispondono alle dimensioni della sorgente inviata all'API.
      const el = currentImage.getElement();
      const refW = el.naturalWidth || el.videoWidth || el.width || fabricCanvas.getWidth();
      const refH = el.naturalHeight || el.videoHeight || el.height || fabricCanvas.getHeight();

      const firstLandmark = result.landmarks[0];
      const isNormalized = firstLandmark.x <= 1.0 && firstLandmark.y <= 1.0;

      currentLandmarks = result.landmarks.map(lm => ({
        x: isNormalized ? lm.x * refW : lm.x,
        y: isNormalized ? lm.y * refH : lm.y,
        z: lm.z || 0,
        visibility: lm.visibility || 1.0
      }));

      window.currentLandmarks = currentLandmarks;
      console.log(`✅ detectLandmarksSilent: ${currentLandmarks.length} landmarks rilevati`);
      return true;
    }
    console.warn('⚠️ detectLandmarksSilent: Nessun landmark nella risposta API');
    return false;
  } catch (error) {
    console.error('❌ detectLandmarksSilent: Errore:', error);
    return false;
  }
}

// ============================================================================
// HARD REFRESH PER NUOVA SESSIONE
// ============================================================================
/**
 * Esegue un hard refresh completo della pagina prima di iniziare una nuova sessione.
 * Chiamato dai pulsanti AVVIA WEBCAM, CARICA VIDEO, CARICA IMMAGINE.
 * Pulisce cache, stato e ricarica la pagina per garantire uno stato pulito.
 */
function hardRefreshForNewSession(actionType) {
  // Salva il tipo di azione da eseguire dopo il refresh
  sessionStorage.setItem('pendingAction', actionType);
  sessionStorage.setItem('pendingActionTime', Date.now().toString());

  // Esegui hard refresh (ignora cache)
  window.location.reload(true);
}

/**
 * Controlla se c'è un'azione pendente dopo un hard refresh
 * Chiamato all'avvio dell'app
 */
function checkPendingAction() {
  const pendingAction = sessionStorage.getItem('pendingAction');
  const pendingTime = sessionStorage.getItem('pendingActionTime');

  if (!pendingAction || !pendingTime) return;

  // Verifica che l'azione sia recente (max 5 secondi)
  const elapsed = Date.now() - parseInt(pendingTime);
  if (elapsed > 5000) {
    sessionStorage.removeItem('pendingAction');
    sessionStorage.removeItem('pendingActionTime');
    return;
  }

  // Pulisci sessionStorage
  sessionStorage.removeItem('pendingAction');
  sessionStorage.removeItem('pendingActionTime');

  // Esegui l'azione dopo un breve delay per permettere inizializzazione
  setTimeout(() => {
    switch (pendingAction) {
      case 'webcam':
        if (typeof startWebcamDirect === 'function') startWebcamDirect();
        break;
      case 'video':
        if (typeof loadVideoDirect === 'function') loadVideoDirect();
        break;
      case 'image':
        if (typeof loadImageDirect === 'function') loadImageDirect();
        break;
    }
  }, 500);
}

// ============================================================================
// RESET GLOBALE PER NUOVA ANALISI
// ============================================================================
function resetForNewAnalysis() {
  // Reset score globale
  if (typeof currentBestScore !== 'undefined') {
    currentBestScore = 0;
  }

  // Chiudi WebSocket precedente
  if (typeof webcamWebSocket !== 'undefined' && webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
    webcamWebSocket.close();
  }

  // Ferma webcam se attiva
  if (typeof isWebcamActive !== 'undefined' && isWebcamActive) {
    stopWebcam();
  }

  // Ferma anteprima video se attiva
  if (typeof stopLivePreview === 'function') {
    stopLivePreview();
  }

  // Pulisci tabella debug
  const debugTableBody = document.getElementById('debug-data');
  if (debugTableBody) {
    debugTableBody.innerHTML = '';
  }

  // Pulisci tabella unificata
  const unifiedTableBody = document.getElementById('unified-table-body');
  if (unifiedTableBody) {
    unifiedTableBody.innerHTML = '';
  }

  // Reset flag per forzare apertura tab debug al prossimo caricamento
  window._shouldOpenDebugTab = true;

  // Reset frame buffer globale
  if (typeof currentBestFrames !== 'undefined') {
    currentBestFrames = [];
  }
  if (window.currentBestFrames) {
    window.currentBestFrames = [];
  }

  // ✅ RESET COMPLETO CANVAS E LANDMARKS
  if (typeof fabricCanvas !== 'undefined' && fabricCanvas) {
    fabricCanvas.clear();
    fabricCanvas.backgroundColor = '#f0f0f0';

    // Reset zoom e viewportTransform
    fabricCanvas.setZoom(1);
    fabricCanvas.viewportTransform = [1, 0, 0, 1, 0, 0];

    fabricCanvas.renderAll();
  }

  // ✅ PULISCI ASSE DI SIMMETRIA ESPLICITAMENTE
  if (typeof clearSymmetryAxis === 'function') {
    clearSymmetryAxis();
  }

  // Pulisci landmarks globali
  if (typeof currentLandmarks !== 'undefined') {
    currentLandmarks = [];
  }
  if (window.currentLandmarks) {
    window.currentLandmarks = [];
  }
  if (window.originalLandmarks) {
    window.originalLandmarks = [];
  }
  if (window.currentLandmarkObjects) {
    window.currentLandmarkObjects = [];
  }

  // Pulisci landmarks dal canvas (se la funzione esiste)
  if (typeof clearLandmarks === 'function') {
    clearLandmarks();
  }

  // Pulisci tabella landmarks
  const landmarksTableBody = document.getElementById('landmarks-table-body');
  if (landmarksTableBody) {
    landmarksTableBody.innerHTML = '';
  }

  // Pulisci anche landmarks-data (tabella alternativa)
  const landmarksData = document.getElementById('landmarks-data');
  if (landmarksData) {
    landmarksData.innerHTML = '';
  }

  // Reset immagine corrente
  if (typeof currentImage !== 'undefined') {
    currentImage = null;
  }
  if (window.currentImage) {
    window.currentImage = null;
  }
  currentImageElement = null;

  // ✅ RESET CANVAS MODES (pulsanti toolbar)
  if (typeof setCanvasMode === 'function') {
    setCanvasMode(null);
  }
  if (typeof currentCanvasMode !== 'undefined') {
    currentCanvasMode = null;
  }
  if (window.currentCanvasMode !== undefined) {
    window.currentCanvasMode = null;
  }

  // ✅ RESET TUTTI I PULSANTI ATTIVI (rimuovi classe 'active' e 'btn-active')
  document.querySelectorAll('.btn.active, .toggle-btn.active, button.active, .btn-analysis.btn-active, .btn-tool-strip.btn-active').forEach(btn => {
    btn.classList.remove('active', 'btn-active');
  });

  // ✅ RESET OVERLAY MISURAZIONI (mappa, cache sopracciglia, pulsanti rimasti)
  if (typeof clearAllMeasurementOverlays === 'function') {
    clearAllMeasurementOverlays();
  }

  // ✅ RESET POINT-PAIR HIGHLIGHT (overlay da click su righe tabella)
  if (typeof clearPointPairHighlight === 'function') {
    clearPointPairHighlight();
  }
  window.highlightedPair = null;
  window.highlightOverlayObjects = [];

  // ✅ RESET GREEN DOTS / WHITE DOTS STATE
  window.greenDotsData = null;
  window.greenDotsDetected = false;
  document.getElementById('green-dots-btn')?.classList.remove('active');
  window.currentGreenDotsOverlay = null;
  window.currentGreenDotsOverlayNaturalW = null;
  window.currentGreenDotsOverlayNaturalH = null;
  window.greenDotsDetectionAngle = null;
  window.greenDotsOverlayScaleXAtDetection = null;
  window.greenDotsOverlayScaleYAtDetection = null;
  window.greenDotsDetectionCenterX = null;
  window.greenDotsDetectionCenterY = null;
  window.highResCanvasForAnalysis = null;
  window.lastImageResizeScale = 1.0;
  window.eyebrowSymmetryCache = null;
  window._eyebrowSymmetryCache = null;

  // ✅ RESET CURSORE CANVAS
  if (fabricCanvas) {
    fabricCanvas.defaultCursor = 'default';
    fabricCanvas.hoverCursor = 'move';
  }

  // ✅ RESET VIDEO PLAYER
  const videoPlayer = document.getElementById('video-player');
  const videoSource = document.getElementById('video-source');
  if (videoPlayer) {
    videoPlayer.pause();
    videoPlayer.currentTime = 0;
    if (videoSource) {
      videoSource.src = '';
    }
    videoPlayer.load();
    videoPlayer.style.display = 'none';
  }

  // ✅ RESET WEBCAM
  const webcamVideo = document.getElementById('webcam-video');
  if (webcamVideo && webcamVideo.srcObject) {
    const stream = webcamVideo.srcObject;
    stream.getTracks().forEach(track => track.stop());
    webcamVideo.srcObject = null;
    webcamVideo.style.display = 'none';
  }

  // Reset flag webcam
  if (typeof isWebcamActive !== 'undefined') {
    isWebcamActive = false;
  }
  if (window.isWebcamActive !== undefined) {
    window.isWebcamActive = false;
  }

  // ✅ RESET ANALISI VISAGISTICA (chiudi modal e pulisci dati)
  const analysisModal = document.getElementById('analysis-modal');
  if (analysisModal) {
    analysisModal.style.display = 'none';
  }

  // Pulisci contenuto analisi
  const analysisContent = document.getElementById('analysis-content');
  if (analysisContent) {
    analysisContent.innerHTML = '';
  }

  // ✅ RESET MODALI CORREZIONE SOPRACCIGLIA (rimuovi tutti i modal generati dinamicamente)
  stopVoiceAssistant();
  document.querySelectorAll('body > div[style*="position: fixed"][style*="z-index: 10000"]').forEach(modal => {
    modal.remove();
  });

  // ✅ RESET STILI DINAMICI (animazioni generate da eyebrow-correction)
  document.querySelectorAll('head > style').forEach(style => {
    if (style.textContent.includes('blink-arrow') || style.textContent.includes('pulse-glow')) {
      style.remove();
    }
  });

  // ✅ RESET SVG OVERLAYS (frecce, poligoni, ecc. generati da eyebrow-correction)
  document.querySelectorAll('svg[style*="position: absolute"][style*="pointer-events: none"]').forEach(svg => {
    svg.remove();
  });

  // ✅ RESET SVG nel canvas-wrapper
  const canvasWrapper = document.querySelector('.canvas-wrapper');
  if (canvasWrapper) {
    canvasWrapper.querySelectorAll('svg').forEach(svg => {
      svg.remove();
    });
  }

  // ✅ RESET OGGETTI FABRIC.JS CON TAG SPECIFICI (overlays, frecce, asse simmetria, etc)
  if (typeof fabricCanvas !== 'undefined' && fabricCanvas) {
    const objectsToRemove = fabricCanvas.getObjects().filter(obj => {
      return obj.isPerpendicularLine || obj.isEyebrowOverlay || obj.customType ||
        obj.isSymmetryAxis || obj.isDebugPoint || obj.isLandmark ||
        obj.isGreenDot || obj.isGreenDotsOverlay || obj.isGreenDotsGroup;
    });
    objectsToRemove.forEach(obj => {
      fabricCanvas.remove(obj);
    });
  }

  // ✅ RESET FLAG ASSE DI SIMMETRIA
  if (window.symmetryAxisVisible !== undefined) {
    window.symmetryAxisVisible = false;
  }

  // ✅ RESET FLAG E MODALITÀ LANDMARKS
  if (window.landmarksVisible !== undefined) {
    window.landmarksVisible = false;
  }
  if (typeof landmarksVisible !== 'undefined') {
    landmarksVisible = false;
  }
  if (window.landmarkSelectionMode !== undefined) {
    window.landmarkSelectionMode = false;
  }
  if (typeof landmarksAutoDetected !== 'undefined') {
    landmarksAutoDetected = false;
  }

  // ✅ PULISCI LANDMARKS ESPLICITAMENTE
  if (typeof clearLandmarks === 'function') {
    clearLandmarks();
  }

  // ✅ RESET VARIABILI GLOBALI MISURAZIONI
  if (window.measurementLines) {
    window.measurementLines = [];
  }
  if (window.allMeasurements) {
    window.allMeasurements = {};
  }

  // ✅ RESET VARIABILI GLOBALI EYEBROW CORRECTION
  if (window.greenDotsDetected !== undefined) {
    window.greenDotsDetected = false;
  }
  if (window.greenDotsData) {
    window.greenDotsData = null;
  }
  window.isDetectingGreenDots = false;
  document.getElementById('green-dots-btn')?.classList.remove('active');
  // NON resettare imageOffset e imageScale - mantieni valori esistenti o default
  // Verranno sovrascritti quando la nuova immagine viene caricata
  if (!window.imageOffset) {
    window.imageOffset = { x: 0, y: 0 };
  }
  if (window.imageScale === undefined) {
    window.imageScale = 1;
  }

  // ✅ RESET SEZIONI SIDEBAR (chiudi tutte tranne quelle base)
  const sections = document.querySelectorAll('.left-sidebar .section');
  sections.forEach(section => {
    const btnText = section.querySelector('.toggle-btn')?.textContent || '';
    const content = section.querySelector('.section-content');
    const icon = section.querySelector('.icon');

    // Chiudi tutte le sezioni tranne SORGENTE
    if (!btnText.includes('SORGENTE') && content && icon) {
      content.style.display = 'none';
      icon.textContent = '▶';
      section.setAttribute('data-expanded', 'false');
    }
  });

  // Reset status
  updateStatus('Pronto per nuova analisi');

  // Log compatto per debug (dettagli solo se necessario)
  if (window.DEBUG_MODE) {
    console.log('🔄 Reset completo eseguito');
    console.log('   ✓ Canvas pulito e zoom resettato');
    console.log('   ✓ Landmarks e misurazioni pulite');
    console.log('   ✓ Video/Webcam fermate');
    console.log('   ✓ Pulsanti attivi resettati');
    console.log('   ✓ Sezioni sidebar chiuse');
    console.log('   ✓ Tabelle pulite');
  } else {
    console.log('✅ Reset stato completato');
  }
}

// Inizializzazione al caricamento pagina
document.addEventListener('DOMContentLoaded', function () {
  // Verifica che Fabric.js sia caricato
  if (typeof fabric === 'undefined') {
    console.error('Fabric.js non caricato');
    return;
  }

  // Inizializza componenti
  initializeSections();

  // Ritardo per assicurarsi che tutto sia caricato
  setTimeout(() => {
    initializeFabricCanvas();
    initializeFileHandlers();
    initializeKeyboardShortcuts();

    // Ridimensionamento aggiuntivo dopo l'inizializzazione completa
    setTimeout(() => {
      if (typeof resizeCanvas === 'function') {
        resizeCanvas();
      }
    }, 300);
  }, 100);

  // Aggiorna status iniziale
  updateStatus('Pronto - Interfaccia web caricata');
  updateBadges();
});

// === GESTIONE SEZIONI COLLASSABILI ===

function initializeSections() {
  // Le sezioni sono già configurate nel HTML con onclick
}

// Funzione toggleSection ora è definita globalmente sopra

// === GESTIONE FILE ===

function initializeFileHandlers() {
  // Drag & Drop per il canvas
  const canvas = document.getElementById('main-canvas');

  canvas.addEventListener('dragover', function (e) {
    e.preventDefault();
    e.stopPropagation();
    canvas.style.border = '3px dashed #007bff';
  });

  canvas.addEventListener('dragleave', function (e) {
    e.preventDefault();
    e.stopPropagation();
    canvas.style.border = 'none';
  });

  canvas.addEventListener('drop', function (e) {
    e.preventDefault();
    e.stopPropagation();
    canvas.style.border = 'none';

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleUnifiedFileLoad(files[0]);
    }
  });
}

function loadImage() {
  // Reset inline: non si può usare hardRefreshForNewSession perché i browser
  // bloccano input[type=file].click() se non è direttamente nel gestore utente.
  resetForNewAnalysis();
  loadImageDirect();
}

function loadImageDirect() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = function (e) {
    const file = e.target.files[0];
    if (file) {
      trackActivity('image_upload', { fileSize: file.size, fileType: file.type });
      handleUnifiedFileLoad(file, 'image');
    }
  };
  input.click();
}

function collapseDetectionSections() {
  // Trova e ESPANDI (apri) le sezioni "RILEVAMENTI" e "MISURAZIONI PREDEFINITE"
  const sections = document.querySelectorAll('.left-sidebar .section');
  sections.forEach(section => {
    const btnText = section.querySelector('.toggle-btn')?.textContent || '';
    if (btnText.includes('RILEVAMENTI') || btnText.includes('MISURAZIONI PREDEFINITE')) {
      const content = section.querySelector('.section-content');
      const icon = section.querySelector('.icon');
      if (content && content.style.display === 'none') {
        content.style.display = 'block';
        if (icon) icon.textContent = '▼';
        section.setAttribute('data-expanded', 'true');
        console.log(`📂 Sezione "${btnText.trim()}" aperta`);
      }
    }
  });
}

function loadVideo() {
  // Reset inline: stesso motivo di loadImage (file picker bloccato dopo reload).
  resetForNewAnalysis();
  loadVideoDirect();
}

function loadVideoDirect() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'video/*';
  input.onchange = function (e) {
    const file = e.target.files[0];
    if (file) {
      trackActivity('video_upload', { fileSize: file.size, fileType: file.type });
      handleUnifiedFileLoad(file, 'video');
    }
  };
  input.click();
}

// ============================================================================
// ============================================================================
// FUNZIONI DEPRECATE - MANTENUTE SOLO PER COMPATIBILITÀ
// ⚠️ NON USARE: La compressione deve avvenire A MONTE, non frame-per-frame
// ============================================================================
function compressImage(sourceCanvas, maxWidth = 1280, quality = 0.7) {
  /**
   * ⚠️ DEPRECATED: Usato solo per codice legacy che non è stato ancora refactorizzato
   * La compressione dovrebbe avvenire A MONTE (video preprocessing, riduzione stream webcam, riduzione immagini all'upload)
   */
  // NOTA: Funzione deprecata - warning rimosso per evitare spam console

  const originalWidth = sourceCanvas.width;
  const originalHeight = sourceCanvas.height;

  // Calcola nuove dimensioni mantenendo proporzioni
  let newWidth = originalWidth;
  let newHeight = originalHeight;

  if (originalWidth > maxWidth) {
    const ratio = maxWidth / originalWidth;
    newWidth = maxWidth;
    newHeight = Math.round(originalHeight * ratio);
  }

  // Crea canvas compresso
  const compressedCanvas = document.createElement('canvas');
  compressedCanvas.width = newWidth;
  compressedCanvas.height = newHeight;

  const ctx = compressedCanvas.getContext('2d');
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(sourceCanvas, 0, 0, newWidth, newHeight);

  return compressedCanvas;
}

// ============================================================================
// PREPROCESSING VIDEO LATO CLIENT - Riduce PRIMA dell'upload
// ============================================================================
async function preprocessVideoClientSide(file, maxWidth = 1920, progressCallback = null) {
  /**
   * Preprocessa video lato client riducendo a 1920px (lato maggiore).
   * Garantisce almeno 1080px sul lato corto anche per video landscape,
   * preservando il dettaglio necessario per rilevare i puntini LB/RB.
   *
   * @param {File} file - File video originale
   * @param {number} maxWidth - Lato maggiore massimo (default 1920px)
   * @param {function} progressCallback - Callback per progress (0-100)
   * @returns {Promise<Blob>} - Video come Blob
   */
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;

    const url = URL.createObjectURL(file);
    video.src = url;

    video.onloadedmetadata = async () => {
      try {
        // Mantieni risoluzione nativa, cap a 3024px (qualità successo.jpg)
        let targetWidth = video.videoWidth;
        let targetHeight = video.videoHeight;

        const maxDim = Math.max(targetWidth, targetHeight);
        if (maxDim > maxWidth) {
          const ratio = maxWidth / maxDim;
          targetWidth = Math.round(targetWidth * ratio);
          targetHeight = Math.round(targetHeight * ratio);
          // Forza dimensioni pari per encoder
          if (targetWidth % 2 !== 0) targetWidth++;
          if (targetHeight % 2 !== 0) targetHeight++;
        }

        console.log(`🎬 Preprocessing video lato client: ${video.videoWidth}x${video.videoHeight} → ${targetWidth}x${targetHeight}`);

        // Canvas per cattura frame con alta qualità
        const canvas = document.createElement('canvas');
        canvas.width = targetWidth;
        canvas.height = targetHeight;
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';

        // MediaRecorder per ricreare video ad alta qualità
        const stream = canvas.captureStream(30); // 30 FPS
        const options = {
          mimeType: 'video/webm;codecs=vp9',
          videoBitsPerSecond: 8000000 // 8 Mbps per alta qualità
        };
        // Fallback a vp8 se vp9 non supportato
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          options.mimeType = 'video/webm;codecs=vp8';
          options.videoBitsPerSecond = 5000000; // 5 Mbps
        }

        const mediaRecorder = new MediaRecorder(stream, options);
        const chunks = [];

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
          const blob = new Blob(chunks, { type: 'video/webm' });
          URL.revokeObjectURL(url);
          console.log(`✅ Video preprocessato: ${(file.size / 1024 / 1024).toFixed(2)}MB → ${(blob.size / 1024 / 1024).toFixed(2)}MB`);
          resolve(blob);
        };

        mediaRecorder.start();
        video.play();

        // Cattura frame durante riproduzione
        const fps = 30;
        const interval = 1000 / fps;
        let lastTime = 0;

        const captureFrame = () => {
          if (video.ended || video.paused) {
            mediaRecorder.stop();
            return;
          }

          const currentTime = video.currentTime;
          if (currentTime - lastTime >= interval / 1000) {
            ctx.drawImage(video, 0, 0, targetWidth, targetHeight);
            lastTime = currentTime;

            // Progress callback
            if (progressCallback) {
              const progress = (currentTime / video.duration) * 100;
              progressCallback(Math.round(progress));
            }
          }

          requestAnimationFrame(captureFrame);
        };

        video.onplay = () => captureFrame();

      } catch (error) {
        URL.revokeObjectURL(url);
        reject(error);
      }
    };

    video.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Errore caricamento video'));
    };
  });
}

function normalizeTo72DPI(sourceCanvas) {
  /**
   * ⚠️ DEPRECATED: La normalizzazione DPI non è necessaria - i canvas non hanno DPI
   * Questa funzione ora fa solo una copia del canvas
   */
  // NOTA: Funzione deprecata - warning rimosso per evitare spam console

  const normalizedCanvas = document.createElement('canvas');
  normalizedCanvas.width = sourceCanvas.width;
  normalizedCanvas.height = sourceCanvas.height;

  const ctx = normalizedCanvas.getContext('2d');
  ctx.drawImage(sourceCanvas, 0, 0);

  return normalizedCanvas;
}

// ============================================================================
// HANDLER UNIFICATO PER IMMAGINI E VIDEO
// ============================================================================
async function handleUnifiedFileLoad(file, type) {
  // Reset completo stato per nuova analisi
  resetForNewAnalysis(`Caricamento nuovo ${type === 'image' ? 'immagine' : 'video'}`);

  // Cache bust per forzare refresh
  const cacheBust = Date.now();

  updateStatus(`Caricamento ${type === 'image' ? 'immagine' : 'video'}...`);

  if (type === 'image') {
    const reader = new FileReader();
    reader.onload = async function (e) {
      const img = new Image();
      img.onload = async function () {
        // Salva il tipo MIME originale per preservare il formato (JPG/PNG)
        img._originalMimeType = file.type || 'image/jpeg';
        collapseDetectionSections();

        // ✅ COMPRESSIONE A MONTE: Riduci immagine a larghezza 464px (altezza proporzionale)
        const rawCanvas = document.createElement('canvas');
        rawCanvas.width = img.naturalWidth || img.width;
        rawCanvas.height = img.naturalHeight || img.height;
        const rawCtx = rawCanvas.getContext('2d');
        rawCtx.drawImage(img, 0, 0);

        // Target: larghezza fissa 1800px, altezza proporzionale per mantenere aspect ratio
        // ✅ OTTIMIZZATO: 1800px per bilanciare qualità e performance nel rilevamento punti bianchi
        // ⬆️ AUMENTATO da 1200px a 1800px: risoluzione più alta = rilevamento puntini più affidabile
        const targetWidth = 1800;
        let finalWidth = rawCanvas.width;
        let finalHeight = rawCanvas.height;

        if (finalWidth > targetWidth) {
          const ratio = targetWidth / finalWidth;
          finalWidth = targetWidth;
          finalHeight = Math.round(finalHeight * ratio);
          if (window.DEBUG_MODE) {
            console.log(`📐 Riduzione immagine a ${finalWidth}x${finalHeight} (larghezza fissa: ${targetWidth}px, aspect ratio preservato)`);
          }
        } else if (window.DEBUG_MODE) {
          console.log(`✅ Immagine già ottima: ${finalWidth}x${finalHeight}px (no riduzione)`);
        }

        // Crea canvas finale con dimensioni target (solo ridimensionamento, nessuna altra elaborazione)
        const finalCanvas = document.createElement('canvas');
        finalCanvas.width = finalWidth;
        finalCanvas.height = finalHeight;
        const finalCtx = finalCanvas.getContext('2d');
        finalCtx.drawImage(rawCanvas, 0, 0, finalWidth, finalHeight);

        // Converti in base64 dal canvas ridimensionato (quality 0.98 per massima qualità)
        const base64Image = finalCanvas.toDataURL('image/jpeg', 0.98);
        const base64Data = base64Image.split(',')[1];

        // Carica immagine sul canvas (versione ridotta per display performance)
        updateCanvasWithBestFrame(base64Data, img._originalMimeType);

        // ⚠️ IMPORTANTE: assegna DOPO updateCanvasWithBestFrame (che è sincrono nel setup).
        // Conserva il rawCanvas full-res come sorgente per l'analisi (es. trova differenze).
        // getCanvasImageAsBase64 userà questo invece dell'elemento ridimensionato in Fabric.js,
        // garantendo la stessa qualità del flusso video.
        window.highResCanvasForAnalysis = rawCanvas;
        console.log(`💾 Canvas full-res pronto per analisi: ${rawCanvas.width}x${rawCanvas.height}`);

        updateStatus(`Immagine caricata: ${file.name}`);
        showToast('Immagine caricata con successo', 'success');
        setAnalysisSourceCanvas('image');

        // Su mobile: porta il canvas in primo piano dopo il caricamento
        if (window.innerWidth <= 768 && typeof window.focusCanvas === 'function') {
          setTimeout(() => window.focusCanvas(), 300);
        }

        if (window.DEBUG_MODE) {
          console.log(`✅ Immagine caricata - ${finalWidth}x${finalHeight}px`);
        }

        // Force repaint canvas
        if (window.canvas && window.canvas.renderAll) {
          window.canvas.renderAll();
        }

        // AUTO-RILEVAMENTO LANDMARKS silenzioso
        const landmarksDetected = await autoDetectLandmarksOnImageChange();
        if (landmarksDetected) {
          updateStatus(`✅ Landmarks rilevati automaticamente (${currentLandmarks.length})`);
          if (window.DEBUG_MODE) {
            console.log('✅ Auto-rilevamento landmarks completato');
          }
        }
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);

  } else if (type === 'video') {
    // Nasconde la guida viso sul canvas: non serve durante l'analisi di un video
    window.faceGuideHidden = true;
    // RIPRISTINO SISTEMA ORIGINALE: Analisi automatica via WebSocket
    try {
      collapseDetectionSections();
      setAnalysisSourceCanvas('video');

      // ========================================================================
      // PREPROCESSING VIDEO LATO CLIENT: Riduce dimensioni PRIMA dell'upload
      // ⚡ VELOCE: No upload file originale, no FFmpeg server, solo client-side
      // ========================================================================
      const fileSizeMB = file.size / (1024 * 1024);
      if (fileSizeMB > 5) {  // Solo per video >5MB (soglia aumentata)
        updateStatus('🔧 Preprocessing video lato client...');
        showToast('Compressione video in corso...', 'info');

        try {
          // Progress callback per feedback utente
          let lastProgress = 0;
          const progressCallback = (progress) => {
            if (progress - lastProgress >= 10) {  // Aggiorna ogni 10%
              updateStatus(`🔧 Preprocessing: ${progress}% completato`);
              lastProgress = progress;
            }
          };

          // Preprocessing lato client con MediaRecorder (max 1920px per preservare dettaglio LB/RB)
          const processedBlob = await preprocessVideoClientSide(file, 1920, progressCallback);

          // Sostituisci file originale
          file = new File([processedBlob], file.name.replace(/\.[^.]+$/, '.webm'), { type: 'video/webm' });

          const compressionRatio = ((1 - processedBlob.size / (fileSizeMB * 1024 * 1024)) * 100).toFixed(1);
          console.log(`✅ Video compresso lato client: ${fileSizeMB.toFixed(2)}MB → ${(processedBlob.size / 1024 / 1024).toFixed(2)}MB (-${compressionRatio}%)`);
          showToast(`Video compresso: ${fileSizeMB.toFixed(1)}MB → ${(processedBlob.size / 1024 / 1024).toFixed(1)}MB`, 'success');

        } catch (preprocessError) {
          console.warn('⚠️ Preprocessing fallito, uso video originale:', preprocessError);
          showToast('Preprocessing fallito, uso video originale', 'warning');
        }
      }
      // ========================================================================

      updateStatus('Avvio analisi video...');

      // Crea elemento video nascosto per elaborazione
      const video = document.createElement('video');
      video.muted = true;
      video.style.position = 'absolute';
      video.style.left = '-9999px';
      video.style.top = '-9999px';
      document.body.appendChild(video);

      // Carica file video (PREPROCESSATO se era >5MB)
      const url = URL.createObjectURL(file);
      video.src = url;

      // Aspetta caricamento video
      await new Promise(resolve => {
        video.onloadedmetadata = resolve;
      });

      await new Promise(resolve => setTimeout(resolve, 100));

      // Imposta video per riproduzione singola (NO LOOP)
      video.loop = false;

      // Handler per fermare quando finisce
      video.addEventListener('ended', () => {
        stopLivePreview();

        // Attendi 2 secondi prima di chiudere il WebSocket
        // per permettere al backend di processare gli ultimi frame
        setTimeout(() => {
          // ✅ FIX: usa disconnectWebcamWebSocket() che invia get_results con final:true
          // così handleResultsReady riceve is_final=true e aggiorna canvas+tabella
          disconnectWebcamWebSocket();
          currentBestScore = 0;
        }, 2000);
      });

      // PROCESSO ORIGINALE: Setup anteprima + elaborazione WebSocket
      openWebcamSection();
      showWebcamPreview(video);

      // Aspetta WebSocket PRIMA di avviare il video
      await connectWebcamWebSocket();

      // Ora avvia il video e l'anteprima
      video.play().then(() => {
        startLivePreview(video); // Anteprima continua
        startVideoFrameProcessing(video, file.name); // Elaborazione frame
      }).catch(e => console.error('Errore play video:', e));

      showToast('Video in elaborazione - sistema WebSocket automatico', 'success');

    } catch (error) {
      console.error('Errore analisi video:', error);
      updateStatus('Errore: Impossibile analizzare il video');
      showToast('Errore analisi video', 'error');
    }
  }
}

// ⚠️ FUNZIONE LEGACY RIMOSSA: handleFileLoad
// Sostituita da handleUnifiedFileLoad() in frame-processor.js
// Rimossa durante l'unificazione del 2024-01-12

// ⚠️ FUNZIONE LEGACY RIMOSSA: handleVideoLoad
// Codice consolidato in handleUnifiedFileLoad() - branch 'video'
// Eliminata duplicazione del 2024-01-16

function startVideoFrameProcessing(video, fileName) {
  updateStatus(`Elaborazione video: ${fileName}`);

  let lastCaptureTimestamp = 0;
  let lastCaptureVideoTime = -1;   // traccia currentTime usato per l'ultimo invio
  let framesCapturati = 0;
  const FRAME_INTERVAL_MS = 500; // 2 FPS per il server

  console.log(`🎬 captureLoop avviato: duration=${video.duration?.toFixed(1)}s paused=${video.paused} ended=${video.ended}`);

  function captureLoop(timestamp) {
    // Fermati se il video è finito o in pausa dopo l'inizio
    if (video.ended) {
      console.log(`🎬 captureLoop terminato: ${framesCapturati} frame inviati`);
      return;
    }
    if (video.paused && video.currentTime > 0) {
      console.log(`🎬 captureLoop: video in pausa a ${video.currentTime.toFixed(2)}s`);
      return;
    }

    if (!webcamWebSocket || webcamWebSocket.readyState !== WebSocket.OPEN) {
      // WS non ancora pronto — riprova al prossimo frame
      requestAnimationFrame(captureLoop);
      return;
    }

    if (timestamp - lastCaptureTimestamp >= FRAME_INTERVAL_MS) {
      // ANTI-DUPLICATO: invia solo se il video ha avanzato di almeno 200ms
      if (video.currentTime - lastCaptureVideoTime >= 0.2) {
        captureFrameFromVideoElement(video);
        lastCaptureVideoTime = video.currentTime;
        framesCapturati++;
        console.log(`🎬 Frame #${framesCapturati} inviato @ ${video.currentTime.toFixed(2)}s ws=${webcamWebSocket.readyState}`);
      }
      lastCaptureTimestamp = timestamp;
    }

    requestAnimationFrame(captureLoop);
  }

  requestAnimationFrame(captureLoop);
}

function captureFrameFromVideoElement(video) {
  try {
    // Cap a 2048px (lato lungo): alta qualità per il best frame.
    // Il server riduce a 640px per MediaPipe (veloce), ma conserva l'originale.
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');

    let w = video.videoWidth || 1080;
    let h = video.videoHeight || 1920;
    // Usa STREAM_MAX_PX_DESKTOP: stesso cap del flusso webcam desktop
    // → i frame video e webcam vanno sullo stesso canale WebSocket,
    //   devono avere scala e qualità identiche.
    const maxDim = Math.max(w, h);
    if (maxDim > STREAM_MAX_PX_DESKTOP) {
      const scale = STREAM_MAX_PX_DESKTOP / maxDim;
      w = Math.round(w * scale);
      h = Math.round(h * scale);
    }
    canvas.width = w;
    canvas.height = h;

    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = 'high';
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const frameBase64 = canvas.toDataURL('image/jpeg', ANALYSIS_JPEG_QUALITY).split(',')[1];

    // Riusa il protocollo WebSocket della webcam
    const frameMessage = {
      action: 'process_frame',
      frame_data: frameBase64
    };

    webcamWebSocket.send(JSON.stringify(frameMessage));

  } catch (error) {
    console.error('Errore cattura frame video:', error);
  }
}

function showVideoModeChoice(fileName) {
  return new Promise((resolve) => {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
      <div class="modal-content">
        <div class="modal-header">
          <h3>🎥 Modalità Video: ${fileName}</h3>
        </div>
        <div class="modal-body">
          <p>Come vuoi analizzare questo video?</p>
          <div class="choice-buttons">
            <button class="btn btn-primary" onclick="selectMode('preview')">
              📹 Anteprima Interattiva<br>
              <small>Guarda il video e scegli i frame da analizzare</small>
            </button>
            <button class="btn btn-success" onclick="selectMode('auto')">
              🤖 Analisi Automatica<br>
              <small>Trova automaticamente il miglior frame frontale</small>
            </button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    window.selectMode = function (mode) {
      stopVoiceAssistant();
      document.body.removeChild(modal);
      delete window.selectMode;
      resolve(mode);
    };
  });
}

async function showVideoPreview(file) {
  console.log('📹 Modalità anteprima video');

  // Mostra modal di anteprima
  const modal = document.getElementById('preview-modal');
  const videoContainer = document.getElementById('video-player-container');
  const video = document.getElementById('preview-video');
  const modalTitle = document.getElementById('modal-title');
  const previewInfo = document.getElementById('preview-info');

  if (!modal || !video) {
    showToast('Errore: elementi video non trovati', 'error');
    return;
  }

  // Configura modal
  modalTitle.textContent = `📹 Anteprima: ${file.name}`;
  previewInfo.innerHTML = `
    <p><strong>File:</strong> ${file.name}</p>
    <p><strong>Dimensione:</strong> ${(file.size / 1024 / 1024).toFixed(2)} MB</p>
    <p>Usa i controlli del video per navigare e scegliere i frame da analizzare.</p>
  `;

  // Carica video
  const videoURL = URL.createObjectURL(file);
  video.src = videoURL;

  // Mostra elementi
  videoContainer.style.display = 'block';
  modal.style.display = 'block';

  // Setup controlli
  setupVideoControls(video, file);

  updateStatus(`📹 Anteprima video: ${file.name}`);
  showToast('Video caricato in anteprima', 'success');
}

async function showVideoInMainCanvas(file) {
  console.log('🎥 Caricamento video nel canvas centrale');

  try {
    // Crea elemento video nascosto per processare il video
    const video = document.createElement('video');
    video.muted = true;
    video.loop = false;
    video.style.display = 'none';
    document.body.appendChild(video);

    // Carica il file video
    const videoURL = URL.createObjectURL(file);
    video.src = videoURL;

    // Aspetta che il video sia caricato
    await new Promise((resolve, reject) => {
      video.addEventListener('loadedmetadata', resolve);
      video.addEventListener('error', reject);
    });

    console.log(`📹 Video caricato: ${video.videoWidth}x${video.videoHeight}, durata: ${video.duration.toFixed(1)}s`);

    // Crea interfaccia video nel canvas
    createVideoInterface(video, file);

    updateStatus(`📹 Video caricato: ${file.name} (${video.duration.toFixed(1)}s)`);
    showToast('Video caricato nel canvas', 'success');

  } catch (error) {
    console.error('❌ Errore caricamento video:', error);
    updateStatus(`Errore caricamento video: ${error.message}`);
    showToast(`Errore: ${error.message}`, 'error');
  }
}

// ⚠️ FUNZIONE createVideoInterface RIMOSSA
// Il sistema ora usa automaticamente WebSocket per l'analisi video
// Nessuna interfaccia manuale con pulsanti necessaria
// Rimosso durante ripristino comportamento originale 2024-01-12

function drawVideoFrame(video, currentTime) {
  if (!fabricCanvas || !video) return;

  // Imposta tempo video
  video.currentTime = currentTime;

  video.addEventListener('seeked', function onSeeked() {
    video.removeEventListener('seeked', onSeeked);

    // Cattura frame corrente a ANALYSIS_MAX_PX
    const _dvw = video.videoWidth || 1280;
    const _dvh = video.videoHeight || 720;
    const _dvs = Math.min(1.0, ANALYSIS_MAX_PX / Math.max(_dvw, _dvh));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(_dvw * _dvs);
    canvas.height = Math.round(_dvh * _dvs);
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Converti in immagine
    canvas.toBlob(blob => {
      const img = new Image();
      img.onload = function () {
        displayImageOnCanvas(img);

        // L'immagine viene salvata da displayImageOnCanvas()

        // Aggiorna interfaccia
        updateVideoTimeDisplay(currentTime, video.duration);
      };
      img.src = URL.createObjectURL(blob);
    }, 'image/jpeg', ANALYSIS_JPEG_QUALITY);
  });
}

// ⚠️ FUNZIONE OBSOLETA RIMOSSA: createVideoControls
// Sistema automatico WebSocket non richiede controlli manuali
// Rimossa durante ripristino sistema originale 2024-01-12

// ⚠️ FUNZIONE OBSOLETA RIMOSSA: setupVideoEventListeners
// Sistema automatico WebSocket non richiede event listeners manuali
// Rimossa durante ripristino sistema originale 2024-01-12

async function analyzeCurrentVideoFrame() {
  if (!currentImage) {
    showToast('Nessun frame da analizzare', 'warning');
    return;
  }

  try {
    updateStatus('🔍 Analisi frontalità frame corrente tramite API...');

    // Usa UnifiedFrameProcessor per catturare e analizzare frame corrente
    const processor = new UnifiedFrameProcessor();
    const imageElement = canvas.fabric.getObjects().find(obj => obj.type === 'image');
    if (!imageElement || !imageElement._element) {
      throw new Error('Nessuna immagine caricata sul canvas');
    }
    const frameSource = new FrameSource(imageElement._element, 'image');
    const result = await processor.processFrame(frameSource);
    const analysisResult = result ? result.analysis : null;

    if (analysisResult) {
      const frontalityScore = analysisResult.frontality_score;
      const poseAngles = analysisResult.pose_angles;

      // Aggiorna display score
      const scoreDisplay = document.getElementById('current-score');
      if (scoreDisplay) {
        scoreDisplay.textContent = frontalityScore.toFixed(3);
        scoreDisplay.style.color = getFrontalityColor(frontalityScore);
      }

      // Aggiungi alla tabella debug se abbiamo un video caricato
      if (window.currentVideo) {
        const timeline = document.getElementById('video-timeline');
        const currentTime = timeline ? parseFloat(timeline.value) : 0;

        const frameData = {
          frameIndex: Math.floor(currentTime / 0.5),
          time: currentTime,
          score: frontalityScore,
          pose: poseAngles,
          landmarks: analysisResult.landmarks,
          status: getFrontalityStatus(frontalityScore)
        };

        addDebugAnalysisRow(frameData);

        // Evidenzia questa riga come frame corrente
        highlightCurrentFrameInTable(currentTime);
      }

      // Attiva landmarks se non già attivi
      const landmarksBtn = document.getElementById('landmarks-btn');
      if (landmarksBtn && !landmarksBtn.classList.contains('active')) {
        landmarksBtn.classList.add('active');
        updateCanvasDisplay();
      }

      updateStatus(`Frame analizzato - Score: ${frontalityScore.toFixed(3)} | Pitch: ${poseAngles.pitch.toFixed(1)}° Yaw: ${poseAngles.yaw.toFixed(1)}° Roll: ${poseAngles.roll.toFixed(1)}°`);
      showToast(`Score: ${frontalityScore.toFixed(3)} | P:${poseAngles.pitch.toFixed(1)}° Y:${poseAngles.yaw.toFixed(1)}°`, 'success');

      // ✅ AGGIORNA IL CANVAS DOPO L'ANALISI
      updateCanvasDisplay();
    } else {
      updateStatus('Errore nell\'analisi del frame');
      showToast('Errore durante l\'analisi', 'error');
    }
  } catch (error) {
    console.error('❌ Errore analisi frame:', error);
    updateStatus('Errore analisi frame');
    showToast('Errore durante l\'analisi', 'error');
  }
}

function highlightCurrentFrameInTable(currentTime) {
  const tbody = document.getElementById('debug-data');
  if (!tbody) return;

  // Rimuovi highlight corrente esistenti
  Array.from(tbody.children).forEach(row => {
    row.classList.remove('current-frame-highlight');
  });

  // Trova e evidenzia il frame corrente (con tolleranza di 0.1s)
  Array.from(tbody.children).forEach(row => {
    const frameTime = parseFloat(row.getAttribute('data-frame-time'));
    if (Math.abs(frameTime - currentTime) < 0.1) {
      row.classList.add('current-frame-highlight');
    }
  });
}

async function runAutomaticVideoAnalysis(file) {
  console.log('🤖 Modalità analisi automatica');

  updateStatus(`🔄 Analisi automatica video: ${file.name}`);
  showToast('Analisi automatica in corso...', 'info');

  // Mostra modal di analisi
  const modal = document.getElementById('video-analysis-modal');
  const statusDiv = document.getElementById('video-analysis-status');

  if (modal && statusDiv) {
    statusDiv.innerHTML = `
      <div class="analysis-progress">
        <div class="spinner"></div>
        <p>Analizzando ${file.name}...</p>
        <p>Ricerca del miglior frame frontale...</p>
      </div>
    `;
    modal.style.display = 'block';
  }

  // Continua con l'analisi automatica esistente (tutto il codice che c'era prima)
  try {
    // ✅ PREPROCESSING LATO CLIENT: Comprimi video PRIMA dell'upload per video >5MB
    const fileSizeMB = file.size / (1024 * 1024);
    let fileToUpload = file;

    if (fileSizeMB > 5) {
      console.log(`🔧 Preprocessing video lato client (${fileSizeMB.toFixed(2)}MB)...`);

      if (statusDiv) {
        statusDiv.innerHTML = `
          <div class="analysis-progress">
            <div class="spinner"></div>
            <p>Compressione video...</p>
            <p id="preprocess-progress">0% completato</p>
          </div>
        `;
      }

      try {
        // Progress callback
        const progressCallback = (progress) => {
          const progressEl = document.getElementById('preprocess-progress');
          if (progressEl) {
            progressEl.textContent = `${progress}% completato`;
          }
        };

        const processedBlob = await preprocessVideoClientSide(file, 1920, progressCallback);
        fileToUpload = new File([processedBlob], file.name.replace(/\.[^.]+$/, '.webm'), { type: 'video/webm' });

        console.log(`✅ Video compresso: ${fileSizeMB.toFixed(2)}MB → ${(fileToUpload.size / 1024 / 1024).toFixed(2)}MB`);

      } catch (preprocessError) {
        console.warn('⚠️ Preprocessing fallito, uso video originale:', preprocessError);
      }

      // Aggiorna status per mostrare che il preprocessing è completato
      if (statusDiv) {
        statusDiv.innerHTML = `
          <div class="analysis-progress">
            <div class="spinner"></div>
            <p>Analizzando ${file.name}...</p>
            <p>Ricerca del miglior frame frontale...</p>
          </div>
        `;
      }
    }

    // Prepara FormData per upload
    const formData = new FormData();
    formData.append('file', fileToUpload);

    console.log('📤 Invio video al backend...');

    // Chiama API backend per analisi video
    const response = await fetch(`${API_CONFIG.baseURL}/api/analyze-video`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Errore sconosciuto' }));
      throw new Error(`Errore API: ${errorData.detail || response.statusText}`);
    }

    const result = await response.json();
    console.log('✅ Analisi video completata:', {
      success: result.success,
      score: result.score,
      totalFrames: result.total_frames,
      analyzedFrames: result.analyzed_frames
    });

    if (result.success && result.best_frame) {
      // Continua con la logica esistente per caricare il frame...
      const img = new Image();
      img.onload = async function () {
        // Chiudi modal di analisi
        if (modal) {
          modal.style.display = 'none';
        }

        // Carica il miglior frame sul canvas principale
        displayImageOnCanvas(img);

        // 🔧 ASSICURA che le sezioni sidebar rimangano visibili
        ensureSidebarSectionsVisible();

        if (result.landmarks && result.landmarks.length > 0) {
          currentLandmarks = result.landmarks;
          window.currentLandmarks = currentLandmarks;
          console.log('💾 Salvati', result.landmarks.length, 'landmarks pre-analizzati dal video');
        } else {
          console.log('🔍 Rilevamento landmarks dal frame del video...');
          updateStatus(`🔍 Rilevamento landmarks dal frame video...`);

          try {
            await detectLandmarks();
            console.log('✅ Landmarks rilevati dal frame video');
          } catch (error) {
            console.error('❌ Errore rilevamento landmarks:', error);
            showToast('Errore rilevamento landmarks dal frame', 'warning');
          }
        }

        // Attiva automaticamente i landmarks se disponibili
        if (currentLandmarks && currentLandmarks.length > 0) {
          const landmarksBtn = document.getElementById('landmarks-btn');
          if (landmarksBtn && !landmarksBtn.classList.contains('active')) {
            landmarksBtn.classList.add('active');
            landmarksVisible = true;
            console.log('🎯 Landmarks attivati automaticamente dopo caricamento video');
          }
        }

        updateCanvasDisplay();
        updateStatus(`Video analizzato: ${file.name} - Miglior frame (Score: ${result.score.toFixed(3)})`);
        showToast(`Video analizzato! Trovato miglior frame con score ${result.score.toFixed(3)}`, 'success');
      };

      img.src = `data:image/jpeg;base64,${result.best_frame}`;
    }

  } catch (error) {
    console.error('❌ Errore analisi video:', error);
    updateStatus(`Errore analisi video: ${error.message}`);
    showToast(`Errore: ${error.message}`, 'error');

    if (statusDiv) {
      statusDiv.innerHTML = `
        <div class="analysis-error">
          <h4>❌ Errore Analisi</h4>
          <p>${error.message}</p>
          <button onclick="closeVideoAnalysis()" class="btn btn-secondary">Chiudi</button>
        </div>
      `;
    }
  }
}

async function runAutomaticVideoAnalysisActual(file) {
  try {
    // Prepara FormData per upload
    const formData = new FormData();
    formData.append('file', file);

    console.log('📤 Invio video al backend...');

    // Chiama API backend per analisi video
    const response = await fetch(`${API_CONFIG.baseURL}/api/analyze-video`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Errore sconosciuto' }));
      throw new Error(`Errore API: ${errorData.detail || response.statusText}`);
    }

    const result = await response.json();
    console.log('✅ Analisi video completata:', {
      success: result.success,
      score: result.score,
      totalFrames: result.total_frames,
      analyzedFrames: result.analyzed_frames
    });

    if (result.success && result.best_frame) {
      // Converti base64 in immagine
      const img = new Image();
      img.onload = async function () {
        // Carica il miglior frame sul canvas
        displayImageOnCanvas(img);

        // Se il video aveva landmarks preanalizzati, usali
        if (result.landmarks && result.landmarks.length > 0) {
          currentLandmarks = result.landmarks;
          window.currentLandmarks = currentLandmarks;
          console.log('💾 Salvati', result.landmarks.length, 'landmarks pre-analizzati dal video');
        } else {
          // Altrimenti rileva landmarks dal frame risultante
          console.log('🔍 Rilevamento landmarks dal frame del video...');
          updateStatus(`🔍 Rilevamento landmarks dal frame video...`);

          try {
            await detectLandmarks();
            console.log('✅ Landmarks rilevati dal frame video');
          } catch (error) {
            console.error('❌ Errore rilevamento landmarks:', error);
            showToast('Errore rilevamento landmarks dal frame', 'warning');
          }
        }

        // Attiva automaticamente i landmarks se disponibili
        if (currentLandmarks && currentLandmarks.length > 0) {
          // Attiva il pulsante landmarks
          const landmarksBtn = document.getElementById('landmarks-btn');
          if (landmarksBtn && !landmarksBtn.classList.contains('active')) {
            landmarksBtn.classList.add('active');
            landmarksVisible = true;
            console.log('🎯 Landmarks attivati automaticamente dopo caricamento video');
          }
        }

        // Aggiorna interfaccia
        updateCanvasDisplay();
        updateStatus(`Video analizzato: ${file.name} - Miglior frame (Score: ${result.score.toFixed(3)})`);
        showToast(`Video analizzato! Trovato miglior frame con score ${result.score.toFixed(3)}`, 'success');

        // Chiudi modal
        if (modal) {
          modal.style.display = 'none';
        }

        // Mostra statistiche
        if (statusDiv) {
          statusDiv.innerHTML = `
            <div class="analysis-complete">
              <h4>✅ Analisi Completata</h4>
              <p><strong>Frame totali:</strong> ${result.total_frames}</p>
              <p><strong>Frame analizzati:</strong> ${result.analyzed_frames}</p>
              <p><strong>Miglior score:</strong> ${result.score.toFixed(3)}</p>
              <p><strong>Landmarks rilevati:</strong> ${result.landmarks.length}</p>
            </div>
          `;

          // Chiudi automaticamente dopo 3 secondi
          setTimeout(() => {
            if (modal) modal.style.display = 'none';
          }, 3000);
        }
      };

      img.onerror = function () {
        throw new Error('Errore caricamento frame risultante');
      };

      img.src = `data:image/jpeg;base64,${result.best_frame}`;

    } else {
      throw new Error(result.message || 'Nessun frame valido trovato nel video');
    }

  } catch (error) {
    console.error('❌ Errore analisi video:', error);
    updateStatus(`Errore analisi video: ${error.message}`);
    showToast(`Errore: ${error.message}`, 'error');

    // Aggiorna modal con errore
    if (statusDiv) {
      statusDiv.innerHTML = `
        <div class="analysis-error">
          <h4>❌ Errore Analisi</h4>
          <p>${error.message}</p>
          <button onclick="document.getElementById('video-preview-modal').style.display='none'" class="btn btn-secondary">Chiudi</button>
        </div>
      `;
    }
  }
}

function setupVideoControls(video, file) {
  const analyzeCurrentBtn = document.getElementById('analyze-current-frame');
  const autoAnalyzeBtn = document.getElementById('auto-analyze');
  const stopBtn = document.getElementById('stop-analysis');

  // Analizza frame corrente
  if (analyzeCurrentBtn) {
    analyzeCurrentBtn.onclick = async function () {
      const currentTime = video.currentTime;
      console.log(`🎯 Analisi frame al tempo: ${currentTime}s`);

      try {
        // Cattura il frame corrente a ANALYSIS_MAX_PX per uniformare la scala
        // con il flusso webcam (stessa risoluzione per dlib/MediaPipe).
        const _vw = video.videoWidth || 1280;
        const _vh = video.videoHeight || 720;
        const _vs = Math.min(1.0, ANALYSIS_MAX_PX / Math.max(_vw, _vh));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(_vw * _vs);
        canvas.height = Math.round(_vh * _vs);
        const ctx = canvas.getContext('2d');
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Converti in blob
        canvas.toBlob(async (blob) => {
          const img = new Image();
          img.onload = function () {
            // Chiudi modal di anteprima
            closeVideoPreview();

            // Carica sul canvas principale
            displayImageOnCanvas(img);

            // 🔧 ASSICURA che le sezioni sidebar rimangano visibili
            ensureSidebarSectionsVisible();

            // Rileva landmarks
            detectLandmarks().then(() => {
              updateCanvasDisplay();
              showToast(`Frame analizzato (${currentTime.toFixed(1)}s)`, 'success');
            });
          };

          img.src = URL.createObjectURL(blob);
        }, 'image/jpeg', ANALYSIS_JPEG_QUALITY);

      } catch (error) {
        console.error('❌ Errore cattura frame:', error);
        showToast('Errore cattura frame corrente', 'error');
      }
    };
  }

  // Analisi automatica
  if (autoAnalyzeBtn) {
    autoAnalyzeBtn.onclick = function () {
      closeVideoPreview();
      runAutomaticVideoAnalysis(file);
    };
  }
}

function closeVideoPreview() {
  const modal = document.getElementById('preview-modal');
  const video = document.getElementById('preview-video');

  stopVoiceAssistant();

  if (video && video.src) {
    URL.revokeObjectURL(video.src);
    video.src = '';
  }

  if (modal) {
    modal.style.display = 'none';
  }
}

function closeVideoAnalysis() {
  stopVoiceAssistant();
  const modal = document.getElementById('video-analysis-modal');
  if (modal) {
    modal.style.display = 'none';
  }
}

// === GESTIONE CANVAS ===

function initializeCanvas() {
  const canvas = document.getElementById('main-canvas');
  const ctx = canvas.getContext('2d');

  // Ridimensiona canvas al container
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  // Event listeners per interazioni desktop
  canvas.addEventListener('mousedown', onCanvasMouseDown);
  canvas.addEventListener('mousemove', onCanvasMouseMove);
  canvas.addEventListener('mouseup', onCanvasMouseUp);
  canvas.addEventListener('wheel', onCanvasWheel);
  canvas.addEventListener('contextmenu', onCanvasRightClick);

  // Event listeners per touch mobile
  canvas.addEventListener('touchstart', onCanvasTouchStart, { passive: false });
  canvas.addEventListener('touchmove', onCanvasTouchMove, { passive: false });
  canvas.addEventListener('touchend', onCanvasTouchEnd, { passive: false });

  console.log('🎨 Canvas inizializzato (desktop + mobile)');
}

function resizeCanvas() {
  const canvas = document.getElementById('main-canvas');
  const wrapper = canvas.parentElement;

  // Salva le dimensioni correnti per evitare ridisegni inutili
  const newWidth = wrapper.clientWidth;
  const newHeight = wrapper.clientHeight;

  // Verifica che le dimensioni siano ragionevoli (max 2000px)
  if (newWidth > 2000 || newHeight > 2000 || newWidth < 10 || newHeight < 10) {
    console.warn(`⚠️ Dimensioni canvas anomale: ${newWidth}x${newHeight}, ignorata`);
    return;
  }

  if (canvas.width !== newWidth || canvas.height !== newHeight) {
    console.log(`📐 Ridimensionamento canvas: ${newWidth}x${newHeight}`);

    // Imposta dimensioni interne del canvas
    canvas.width = newWidth;
    canvas.height = newHeight;

    // Ridisegna solo se non siamo già in un processo di disegno
    if (currentImageElement && !window.isDrawing) {
      window.isDrawing = true;
      displayImageOnCanvas(currentImageElement);
      window.isDrawing = false;
    }
  }
}

function displayImageOnCanvas(image) {
  // Usa Fabric.js invece del context 2D per evitare conflitti
  if (!fabricCanvas) {
    console.warn('⚠️ Fabric canvas non inizializzato');
    return;
  }

  // Rimuovi immagine precedente
  const existingImage = fabricCanvas.getObjects().find(obj => obj.isBackgroundImage);
  if (existingImage) {
    fabricCanvas.remove(existingImage);
  }

  // Calcola dimensioni mantenendo aspect ratio
  const canvasWidth = fabricCanvas.width;
  const canvasHeight = fabricCanvas.height;
  const scale = Math.min(canvasWidth / image.width, canvasHeight / image.height);
  const scaledWidth = image.width * scale;
  const scaledHeight = image.height * scale;
  const x = (canvasWidth - scaledWidth) / 2;
  const y = (canvasHeight - scaledHeight) / 2;


  // Salva riferimento all'elemento HTML sorgente per i ridimensionamenti futuri
  currentImageElement = image;

  // Crea oggetto immagine Fabric.js
  const fabricImage = new fabric.Image(image, {
    left: x,
    top: y,
    scaleX: scale,
    scaleY: scale,
    selectable: false,
    evented: false,
    isBackgroundImage: true
  });

  // Aggiungi al canvas e porta in background
  fabricCanvas.add(fabricImage);
  fabricCanvas.sendToBack(fabricImage);
  fabricCanvas.renderAll();

  // Salva riferimento all'oggetto fabric (non all'elemento HTML)
  currentImage = fabricImage;

  // Salva le informazioni di scala per i landmarks
  window.imageScale = scale;
  window.imageOffset = { x: x, y: y };

  // Auto-rilevamento landmarks con delay: attende che Fabric.js completi l'init interno
  setTimeout(() => autoDetectLandmarksOnImageChange(), 300);
}

// === GESTIONE WEBCAM ===

// Variabili globali per WebSocket
let webcamWebSocket = null;
let webcamStream = null;
let frameCounter = 0;
let captureInterval = null;

// Compatibility shim: legacy callers may call startRealTimeFaceDetection(video)
// Provide a thin wrapper that simply starts our frame capture loop.
function startRealTimeFaceDetection(video) {
  // If webcam already started via startWebcam(), startFrameCapture will be invoked
  // Otherwise start capturing frames directly (useful for legacy code paths)
  try {
    if (!isWebcamActive) {
      // Bind a temporary stream if video has srcObject
      if (video && video.srcObject) {
        webcamStream = video.srcObject;
        isWebcamActive = true;
        updateWebcamBadge(true);
      }
    }

    // Ensure websocket is connected
    if (!webcamWebSocket || webcamWebSocket.readyState !== WebSocket.OPEN) {
      connectWebcamWebSocket().catch(err => console.warn('Impossibile connettere WebSocket:', err));
    }

    startFrameCapture(video);
  } catch (e) {
    console.warn('startRealTimeFaceDetection shim error:', e);
  }
}

async function startWebcam() {
  const _onMobile = window.innerWidth <= 768;

  // Hard refresh solo su DESKTOP per garantire stato pulito.
  // Su mobile il reload rompe il contesto del gesto utente: iOS Safari richiede
  // che getUserMedia() sia chiamata nella stessa call-stack del tap dell'utente.
  // Su mobile eseguiamo un reset inline e procediamo direttamente.
  if (!_onMobile && !window.isIPhoneStreamActive && !sessionStorage.getItem('webcamRefreshDone')) {
    sessionStorage.setItem('webcamRefreshDone', 'true');
    hardRefreshForNewSession('webcam');
    return;
  }
  sessionStorage.removeItem('webcamRefreshDone');

  if (window.isIPhoneStreamActive) {
    // ⚠️ iPhone: NON chiamare resetForNewAnalysis() perché chiuderebbe il WebSocket
    // già connesso per le notifiche iPhone e chiamerebbe stopWebcam() se isWebcamActive=true.
    // Reset leggero: solo score e frame buffer, senza toccare WebSocket né stopWebcam.
    currentBestScore = 0;
    window.lastFramesHash = null;
    window.bestIPhoneScore = 0;
    window._populateTableCalled = false;  // reset throttle analisi tabella
    if (typeof currentBestFrames !== 'undefined') currentBestFrames = [];
    if (window.currentBestFrames) window.currentBestFrames = [];
  } else {
    // Desktop (post-refresh) + Mobile: reset completo inline
    resetForNewAnalysis();
  }

  // Procedi con startWebcamDirect
  await startWebcamDirect();
}

async function startWebcamDirect() {
  try {
    // Track webcam start
    trackActivity('webcam_start');

    if (window.isIPhoneStreamActive) {
      updateStatus('📱 iPhone Camera attiva - Anteprima in corso...');
      showToast('iPhone Camera avviata - Anteprima in corso', 'success');

      // Invia start_session + start_webcam al server — uguale al flusso webcam PC
      if (webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
        // Reinizializza il buffer frame_scorer sul server
        webcamWebSocket.send(JSON.stringify({
          action: 'start_session',
          session_id: `iphone_session_${new Date().toISOString().replace(/[:.]/g, '_')}`,
          session_token: window._iphoneSessionToken || ''
        }));
        webcamWebSocket.send(JSON.stringify({
          action: 'start_webcam',
          session_token: window._iphoneSessionToken || ''
        }));
      }

      // Apri sezione ANTEPRIMA per mostrare frame iPhone
      if (typeof openWebcamSection === 'function') {
        openWebcamSection();
      }

      // Mostra canvas preview per iPhone
      const previewCanvas = document.getElementById('webcam-preview-canvas');
      const previewInfo = document.getElementById('webcam-preview-info');
      if (previewCanvas) {
        previewCanvas.classList.add('active');
        previewCanvas.style.display = 'block';
      }

      // Aggiorna info preview
      if (previewInfo) {
        previewInfo.innerHTML = '📱 iPhone Camera attiva - Anteprima in tempo reale';
      }

      // Marca webcam come attiva per permettere rendering frame
      window.faceGuideHidden = false;
      isWebcamActive = true;
      updateWebcamBadge(true);

      // Apri fullscreen anche per stream iPhone (senza video element locale,
      // verrà renderizzato dal canvas preview esistente)
      openWebcamFullscreen(null);

      // Pre-carica frasi di guida posa e avvia guida vocale
      if (typeof voiceAssistant !== 'undefined' && voiceAssistant.prefetchAudio) {
        voiceAssistant.prefetchAudio([
          'Avvicìnati alla camera', 'Allontànati dalla camera',
          'Avvicìnati un po\'',
          'Gira il viso verso sinistra', 'Gira il viso verso destra',
          'Abbassa leggermente il mento', 'Alza leggermente il mento',
          'Inclina la testa verso sinistra', 'Inclina la testa verso destra',
          'Ottima posa!'
        ]);
      }
      startPoseVoiceGuidance();

      return;
    }

    // Reset completo prima di avviare webcam
    resetForNewAnalysis('Avvio nuova sessione webcam');
    setAnalysisSourceCanvas('webcam');

    // Riconnetti WebSocket DOPO il reset
    await connectWebcamWebSocket();

    // Constraints video adattivi per dispositivo:
    // - Mobile: no min (evita OverconstrainedError su camera portrait iOS/Android)
    // - Desktop: massima risoluzione disponibile
    const _isMobileDevice = window.innerWidth <= 768;
    let videoConstraints;
    if (_isMobileDevice) {
      videoConstraints = {
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        facingMode: 'user',  // fotocamera frontale per analisi facciale
      };
    } else {
      videoConstraints = {
        width: { ideal: 3024, min: 640 },
        height: { ideal: 4032, min: 480 },
        facingMode: 'user',
        aspectRatio: { ideal: 0.75 }  // portrait 3:4 come successo.jpg
      };
    }

    updateStatus('Avvio webcam...');

    // Avvia stream webcam
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: videoConstraints
    });

    const video = document.getElementById('webcam-video');
    video.srcObject = webcamStream;
    video.style.display = 'none';

    // Aspetta che il video sia pronto
    await new Promise(resolve => {
      video.onloadedmetadata = resolve;
    });

    // IMPORTANTE: Avvia la riproduzione del video prima di disegnarlo sul canvas
    await video.play();

    // Mantieni canvas centrale visibile per mostrare i migliori frame
    const canvas = document.getElementById('main-canvas');
    canvas.style.display = 'block';

    // Su mobile: chiudi tutti i pannelli e porta al canvas prima di aprire fullscreen
    if (window.innerWidth <= 768 && typeof closeAllMobilePanels === 'function') {
      closeAllMobilePanels();
    }

    // Apri sezione anteprima webcam (solo desktop: su mobile è nella sidebar nascosta)
    if (window.innerWidth > 768) {
      openWebcamSection();
      showWebcamPreview(video);
      startLivePreview(video); // Solo desktop: su mobile la sidebar è nascosta,
      // il rendering viene fatto dal loop fullscreen.
    }

    // Pre-carica in cache le frasi di guida posa per latenza zero su mobile
    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.prefetchAudio) {
      voiceAssistant.prefetchAudio([
        'Avvicìnati alla camera',
        'Allontànati dalla camera',
        'Avvicìnati un po\'',
        'Gira il viso verso sinistra',
        'Gira il viso verso destra',
        'Abbassa leggermente il mento',
        'Alza leggermente il mento',
        'Inclina la testa verso sinistra',
        'Inclina la testa verso destra',
        'Ottima posa!'
      ]);
    }

    // Apri anteprima a tutto schermo durante l'acquisizione
    openWebcamFullscreen(video);

    // Avvia guida vocale posa (frasi già pre-fetchate sopra → latenza zero)
    startPoseVoiceGuidance();

    // ✅ WEBCAM: usa WebSocket per buffer circolare lato server
    // Invia frame a 2 FPS → server analizza e mantiene buffer migliori 40 frame
    startFrameCapture(video);

    window.faceGuideHidden = false;
    isWebcamActive = true;

    // Mostra stato webcam
    updateStatus('Webcam attiva - WebSocket streaming');
    updateWebcamBadge(true);

    showToast('Webcam avviata', 'success');

  } catch (error) {
    console.error('Errore avvio webcam:', error);
    updateStatus('Errore: Impossibile accedere alla webcam');
    showToast('Errore accesso webcam: ' + error.message, 'error');
  }
}

function stopWebcam() {
  try {
    // Ferma processing impostando flag a false
    isWebcamActive = false;
    updateWebcamBadge(false);

    // Chiudi overlay fullscreen
    closeWebcamFullscreen();

    // Ferma guida vocale posa
    stopPoseVoiceGuidance();

    // Invia stop_webcam al server per smettere di ricevere frames
    if (window.isIPhoneStreamActive && webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
      webcamWebSocket.send(JSON.stringify({
        action: 'stop_webcam',
        session_token: window._iphoneSessionToken || ''
      }));
    }

    // Ferma cattura frame webcam
    if (captureInterval) {
      cancelAnimationFrame(captureInterval);
      captureInterval = null;
    }

    if (webcamStream) {
      const tracks = webcamStream.getTracks();
      tracks.forEach(track => track.stop());
      webcamStream = null;
    }

    const video = document.getElementById('webcam-video');
    video.srcObject = null;
    video.style.display = 'none';

    hideWebcamPreview();
    document.getElementById('main-canvas').style.display = 'block';

    // Gestisci WebSocket in base a fonte (iPhone vs Webcam PC)
    if (!window.isIPhoneStreamActive) {
      // Webcam PC - chiudi WebSocket
      if (webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
        setTimeout(() => {
          if (webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
            webcamWebSocket.close();
          }
          disconnectWebcamWebSocket();
          currentBestScore = 0;
        }, 100);
      } else {
        disconnectWebcamWebSocket();
        currentBestScore = 0;
      }
    } else {
      // iPhone - mantieni WebSocket aperto per ricevere best frames
      currentBestScore = 0;
    }

    updateStatus('Webcam fermata');
    showToast('Webcam fermata', 'info');

  } catch (error) {
    console.error('Errore stop webcam:', error);
    showToast('Errore stop webcam', 'error');
  }
}

async function connectWebcamWebSocket() {
  return new Promise((resolve, reject) => {
    try {
      // Chiudi WebSocket esistente prima di crearne uno nuovo
      if (webcamWebSocket) {
        try {
          webcamWebSocket.onclose = null;
          webcamWebSocket.onerror = null;
          webcamWebSocket.onmessage = null;

          if (webcamWebSocket.readyState === WebSocket.OPEN ||
            webcamWebSocket.readyState === WebSocket.CONNECTING) {
            webcamWebSocket.close();
          }
        } catch (e) {
          // Ignora errori chiusura
        }
        webcamWebSocket = null;
      }

      // Connessione al server WebSocket tramite Nginx proxy
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const hostname = window.location.hostname;
      const wsUrl = `${protocol}//${hostname}/ws`;

      const newWebSocket = new WebSocket(wsUrl);

      newWebSocket.onopen = function () {
        // ✅ FIX: Assegna solo dopo che è connesso
        webcamWebSocket = newWebSocket;
        updateStatus('WebSocket connesso - Avvio sessione...');

        // Registra desktop per ricevere notifiche iPhone (con session_token per isolamento utente)
        webcamWebSocket.send(JSON.stringify({
          action: 'register_desktop',
          session_token: window._iphoneSessionToken || ''
        }));

        // Avvia sessione
        const startMessage = {
          action: 'start_session',
          session_id: `webapp_session_${new Date().toISOString().replace(/[:.]/g, '_')}`,
          session_token: window._iphoneSessionToken || ''
        };
        webcamWebSocket.send(JSON.stringify(startMessage));

        resolve();
      };

      newWebSocket.onmessage = function (event) {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (error) {
          console.error('Errore parsing messaggio WebSocket:', error);
        }
      };

      newWebSocket.onclose = function () {
        // Imposta null solo se è ancora questo WebSocket
        if (webcamWebSocket === newWebSocket) {
          webcamWebSocket = null;
        }
      };

      newWebSocket.onerror = function (error) {
        console.error('Errore WebSocket:', error);
        reject(error);
      };

    } catch (error) {
      console.error('Errore connessione WebSocket:', error);
      reject(error);
    }
  });
}

function disconnectWebcamWebSocket() {
  if (webcamWebSocket) {
    if (webcamWebSocket.readyState === WebSocket.OPEN) {
      // Richiedi risultati finali con request_id per correlazione
      const requestId = ++getResultsRequestId;
      const stopMessage = {
        action: 'get_results',
        request_id: requestId,
        session_token: window._iphoneSessionToken || '',
        final: true
      };

      try {
        webcamWebSocket.send(JSON.stringify(stopMessage));
      } catch (error) {
        // Ignora errori invio
      }

      // Chiudi connessione dopo breve delay per ricevere risultati
      const wsToClose = webcamWebSocket;
      setTimeout(() => {
        try {
          if (wsToClose && wsToClose.readyState === WebSocket.OPEN) {
            wsToClose.close();
          }
        } catch (e) {
          // Ignora errori chiusura
        }
        pendingGetResultsRequests.clear();
      }, 1000);
    } else {
      pendingGetResultsRequests.clear();
    }
  }
}

function startFrameCapture(video) {
  // Previeni loop duplicati
  if (captureInterval) {
    cancelAnimationFrame(captureInterval);
    captureInterval = null;
  }

  frameCounter = 0;
  let lastCaptureTimestamp = 0;

  const _captureMobile = window.innerWidth <= 768;
  // 8 FPS sia mobile che desktop: frame più piccoli → round-trip più rapido → feedback posa fluido
  const FRAME_INTERVAL_MS = 125; // 8 FPS

  // Pre-allocazione canvas fuori dal loop: evita migliaia di allocazioni GC nell'RAF
  const rawCanvas = document.createElement('canvas');
  const rawCtx = rawCanvas.getContext('2d');
  const resizedCanvas = document.createElement('canvas');
  const resizedCtx = resizedCanvas.getContext('2d');

  // Dimensioni e qualità:
  //   Mobile  → max  640px, quality 0.72 (payload ≈20-40KB, bassa latenza)
  //   Desktop → max 1280px, quality 0.88 (payload ≈80-180KB, ottima qualità)
  //   (era 2048px q=0.95 → ≈600KB-1.5MB → encoding lento, server lento)
  const maxAllowed = _captureMobile ? STREAM_MAX_PX_MOBILE : STREAM_MAX_PX_DESKTOP;
  const jpegQuality = _captureMobile ? 0.72 : ANALYSIS_JPEG_QUALITY;
  const smoothingQuality = _captureMobile ? 'medium' : 'high';

  // ✅ requestAnimationFrame: scheduling più preciso, non blocca il thread principale
  function captureLoop(timestamp) {
    if (!isWebcamActive) return; // Ferma il loop se webcam disattivata

    if (timestamp - lastCaptureTimestamp >= FRAME_INTERVAL_MS) {
      if (webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
        try {
          const vw = video.videoWidth || 640;
          const vh = video.videoHeight || 480;

          // 1. Disegna sul rawCanvas (riuso: aggiorna width/height solo se cambiano)
          if (rawCanvas.width !== vw || rawCanvas.height !== vh) {
            rawCanvas.width = vw;
            rawCanvas.height = vh;
          }
          rawCtx.drawImage(video, 0, 0, vw, vh);

          // 2. Scala se necessario (riuso resizedCanvas)
          let finalCanvas = rawCanvas;
          const maxDim = Math.max(vw, vh);
          if (maxDim > maxAllowed) {
            const scale = maxAllowed / maxDim;
            const rw = Math.round(vw * scale);
            const rh = Math.round(vh * scale);
            if (resizedCanvas.width !== rw || resizedCanvas.height !== rh) {
              resizedCanvas.width = rw;
              resizedCanvas.height = rh;
              resizedCtx.imageSmoothingEnabled = true;
              resizedCtx.imageSmoothingQuality = smoothingQuality;
            }
            resizedCtx.drawImage(rawCanvas, 0, 0, rw, rh);
            finalCanvas = resizedCanvas;
          }

          const frameBase64 = finalCanvas.toDataURL('image/jpeg', jpegQuality).split(',')[1];

          const frameMessage = {
            action: 'process_frame',
            frame_data: frameBase64
          };
          webcamWebSocket.send(JSON.stringify(frameMessage));
          frameCounter++;
        } catch (err) {
          console.error('❌ Errore cattura/invio frame webcam:', err);
        }
      }
      lastCaptureTimestamp = timestamp;
    }

    captureInterval = requestAnimationFrame(captureLoop);
  }

  captureInterval = requestAnimationFrame(captureLoop);
}

function openWebcamSection() {
  // Trova e apri la sezione anteprima webcam
  const webcamSections = document.querySelectorAll('.section');
  webcamSections.forEach(section => {
    const btn = section.querySelector('.toggle-btn');
    if (btn && btn.textContent.includes('ANTEPRIMA')) {
      const content = section.querySelector('.section-content');
      const icon = section.querySelector('.icon');

      section.dataset.expanded = 'true';
      content.style.display = 'block';
      icon.textContent = '▼';
    }
  });
}

function showWebcamPreview(video) {
  const previewCanvas = document.getElementById('webcam-preview-canvas');
  const previewInfo = document.getElementById('webcam-preview-info');

  if (previewCanvas && video) {
    // Mostra il canvas
    previewCanvas.classList.add('active');
    previewCanvas.style.display = 'block';

    // Forza anche il contenitore parent
    const container = previewCanvas.parentElement;
    if (container) {
      container.style.display = 'block';
      container.style.visibility = 'visible';
    }

    // Distingui tra webcam e video file
    if (video.src && video.src.startsWith('blob:')) {
      previewInfo.innerHTML = 'Video in elaborazione - Anteprima frame';
    } else {
      previewInfo.innerHTML = 'Webcam attiva - Anteprima in tempo reale';
    }

    // Setup iniziale
    updateWebcamPreview(video);
  }
}

function hideWebcamPreview() {
  const previewCanvas = document.getElementById('webcam-preview-canvas');
  const previewInfo = document.getElementById('webcam-preview-info');

  if (previewCanvas) {
    previewCanvas.style.display = 'none';
    previewCanvas.classList.remove('active');
    if (previewInfo) {
      previewInfo.innerHTML = 'Anteprima webcam non attiva';
    }
  }

  // Ferma anteprima live
  stopLivePreview();

  // Reset cache canvas iPhone (forza re-inizializzazione dimensioni alla prossima sessione)
  if (typeof window.resetPreviewCache === 'function') {
    window.resetPreviewCache();
  }
}

function startLivePreview(video) {
  // Ferma loop precedente se esiste
  window.livePreviewActive = false;
  if (window.livePreviewId) {
    cancelAnimationFrame(window.livePreviewId);
    window.livePreviewId = null;
  }

  let lastRenderTimestamp = 0;
  const RENDER_INTERVAL_MS = 33; // ~30 FPS

  // ✅ requestAnimationFrame: sincronizzato con il refresh del browser, nessun jank
  function renderLoop(timestamp) {
    if (!window.livePreviewActive) return;

    if (timestamp - lastRenderTimestamp >= RENDER_INTERVAL_MS) {
      if (video && video.videoWidth > 0) {
        renderLivePreview(video);
      }
      lastRenderTimestamp = timestamp;
    }

    window.livePreviewId = requestAnimationFrame(renderLoop);
  }

  window.livePreviewActive = true;
  window.livePreviewId = requestAnimationFrame(renderLoop);
}

function renderLivePreview(video) {
  const previewCanvas = document.getElementById('webcam-preview-canvas');

  if (!previewCanvas || !video) {
    return;
  }

  // Throttling gestito da requestAnimationFrame (startLivePreview)
  try {
    const ctx = previewCanvas.getContext('2d');

    // Calcola dimensioni dinamiche basate sul container e aspect ratio del video
    const containerWidth = previewCanvas.parentElement.offsetWidth - 16;
    const aspectRatio = video.videoWidth / video.videoHeight;
    const canvasWidth = containerWidth;
    const canvasHeight = canvasWidth / aspectRatio;

    // Imposta dimensioni canvas
    previewCanvas.width = video.videoWidth;
    previewCanvas.height = video.videoHeight;
    previewCanvas.style.width = canvasWidth + 'px';
    previewCanvas.style.height = canvasHeight + 'px';

    // ✅ NO COMPRESSIONE - stream webcam già ridotto a monte (464x832)
    try {
      // Disegna a specchio (flip orizzontale) — solo visivo, il frame inviato al server NON è specchiato
      const W = previewCanvas.width, H = previewCanvas.height;
      ctx.save();
      ctx.translate(W, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(video, 0, 0, W, H);
      ctx.restore();

    } catch (drawError) {
      console.error('❌ Errore drawImage:', drawError);

      // Canvas di fallback
      ctx.fillStyle = 'blue';
      ctx.fillRect(0, 0, video.videoWidth, video.videoHeight);
      ctx.fillStyle = 'white';
      ctx.font = '16px Arial';
      ctx.fillText('ERRORE VIDEO', 50, 120);
      ctx.fillText('CANVAS FUNZIONA', 50, 150);
    }

    // Disegna overlay guida viso e HUD pose angles
    drawFaceGuideOverlay(ctx, previewCanvas.width, previewCanvas.height);

  } catch (error) {
    console.error('❌ Errore renderLivePreview:', error);
  }
}

/**
 * Overlay principale durante l'anteprima webcam.
 *
 * SEMANTICA ANGOLI (da calculate_head_pose_from_mediapipe):
 *   pitch > 0  → testa ALZATA (mento su)   → correzione: "Abbassa il mento"
 *   pitch < 0  → testa ABBASSATA (mento giù) → correzione: "Alza il mento"
 *   yaw   > 0  → viso girato a DESTRA       → correzione: "Gira a sinistra"
 *   yaw   < 0  → viso girato a SINISTRA     → correzione: "Gira a destra"
 *   roll  > 0  → testa inclinata a DESTRA   → correzione: "Raddrizza a sinistra"
 *   roll  < 0  → testa inclinata a SINISTRA → correzione: "Raddrizza a destra"
 *
 * Score breakdown (dal server):
 *   poseScore     (60%) → frontalità Yaw/Pitch/Roll
 *   sizeScore     (30%) → dimensione viso nel frame (30-45% = ottimo)
 *   positionScore (10%) → centramento nel frame
 */
function drawFaceGuideOverlay(ctx, W, H) {
  // Overlay nascosto quando è stato caricato un video (non è una sessione webcam)
  if (window.faceGuideHidden) return;

  const pose = window.livePoseAngles || {
    yaw: 0, pitch: 0, roll: 0, score: 0,
    poseScore: 0, sizeScore: 0, positionScore: 0
  };
  const { yaw, pitch, roll, score, poseScore, sizeScore, positionScore } = pose;

  // 1. Silhouette FISSA della posa ideale (non si muove mai)
  drawIdealFaceSilhouette(ctx, W, H, score);

  // 2. HUD angoli (angolo alto-sinistra)
  drawAngleHUD(ctx, W, H, yaw, pitch, roll, score);

  // 3. Barre score breakdown (angolo alto-destra)
  drawScoreBreakdown(ctx, W, H, poseScore, sizeScore, positionScore, score);

  // 4. Messaggio di guida semplificato (centro-basso)
  drawGuidanceText(ctx, W, H, yaw, pitch, roll, score);
}

/* ─── Cache immagine guida viso ─────────────────────────────────────────── */
let _faceGuideImg = null;
(function _initFaceGuideImg() {
  const img = new Image();
  img.src = '/static/face_guide.png';
  img.onload = () => { _faceGuideImg = img; };
}());

/* ─── Guida viso basata su immagine IMG_8112 ─────────────────────────────── */
/*
 * Disegna IMG_8112.PNG come guida fissa per il posizionamento ottimale del
 * viso. L'immagine (640×640, aspect ratio 1:1) viene scalata proporzionalmente
 * e centrata nella stessa area geometrica dell'ovale precedente, garantendo
 * la corretta area di inquadratura per massimizzare lo score di rilevamento.
 * I corner brackets AR indicano lo stato dello score con colori rosso/giallo/verde.
 */
function drawIdealFaceSilhouette(ctx, W, H, score) {
  // ── Geometria base ────────────────────────────────────────────────────────
  const cx = W * 0.50;
  const cy = H * 0.42;
  const rx = W * 0.30;   // aumentato da 0.26 → overlay più grande per score migliore
  const ry = rx * 1.38;
  const lw = Math.max(1.5, W * 0.003);

  // ── Palette colore score-driven ───────────────────────────────────────────
  const isGood = score >= 85;
  const isMid = score >= 55;
  const colR = isGood ? 0 : isMid ? 255 : 220;
  const colG = isGood ? 210 : isMid ? 185 : 50;
  const colB = isGood ? 90 : isMid ? 0 : 50;
  const colStr = `rgba(${colR},${colG},${colB},`;

  ctx.save();
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  // ── Immagine guida viso (pngwing.com.png, 1158×2188) ────────────────────────
  // Contiene viso frontale (top ~70%) + collo (bottom ~30%).
  // Si scala per LARGHEZZA (imgW = rx*2): il viso copre l'area orizzontale
  // dell'ovale di rilevamento. drawY allineato al TOP dell'ovale (cy - ry):
  // viso coincide con la zona di detection, il collo si estende sotto.
  const imgW = rx * 2;                   // larghezza = diametro ovale
  const imgH = imgW * (2188 / 1158);    // ≈ imgW × 1.889 (aspect originale)
  const drawX = cx - rx;                // allineato a sinistra dell'ovale
  const drawY = cy - ry;               // top immagine = top ovale

  if (_faceGuideImg) {
    ctx.globalAlpha = 0.85;
    ctx.drawImage(_faceGuideImg, drawX, drawY, imgW, imgH);
    ctx.globalAlpha = 1;
  } else {
    // Fallback ellisse mentre l'immagine si carica
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.strokeStyle = colStr + '0.80)';
    ctx.lineWidth = lw * 1.3;
    ctx.stroke();
  }

  // ── Corner brackets AR (indicatore score) ─────────────────────────────────
  const bLen = rx * 0.18;
  ctx.strokeStyle = colStr + '0.90)';
  ctx.lineWidth = lw * 2.2;
  [
    [cx - rx * 0.74, cy - ry * 0.68, [bLen, 0], [0, bLen]],
    [cx + rx * 0.74, cy - ry * 0.68, [-bLen, 0], [0, bLen]],
    [cx - rx * 0.74, cy + ry * 0.68, [bLen, 0], [0, -bLen]],
    [cx + rx * 0.74, cy + ry * 0.68, [-bLen, 0], [0, -bLen]],
  ].forEach(([x, y, [dx1, dy1], [dx2, dy2]]) => {
    ctx.beginPath();
    ctx.moveTo(x + dx1, y + dy1);
    ctx.lineTo(x, y);
    ctx.lineTo(x + dx2, y + dy2);
    ctx.stroke();
  });

  ctx.restore();
}

/* ─── helper: rettangolo con angoli arrotondati ─────────────────────────── */
function _rrect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

/* ─── HUD angoli (alto-sinistra) ────────────────────────────────────────── */
function drawAngleHUD(ctx, W, H, yaw, pitch, roll, score) {
  const pad = W * 0.022;
  const fs = Math.max(11, Math.min(16, W * 0.028));
  const lh = fs * 1.65;

  ctx.save();
  ctx.globalAlpha = 0.88;

  const boxW = W * 0.36;
  const boxH = lh * 4 + pad;
  ctx.fillStyle = 'rgba(0,0,0,0.58)';
  _rrect(ctx, pad, pad, boxW, boxH, 6);
  ctx.fill();

  ctx.font = `bold ${fs}px monospace`;
  ctx.textBaseline = 'middle';

  const scoreColor = score >= 80 ? '#00e676' : score >= 50 ? '#ffd740' : '#ff5252';

  const rows = [
    { label: 'SCORE', val: score.toFixed(1), col: scoreColor },
    // yaw > 0 = destra → mostra '+' per destra, '-' per sinistra
    {
      label: 'YAW  ', val: `${yaw >= 0 ? '+' : ''}${yaw.toFixed(1)}°`,
      col: Math.abs(yaw) < 5 ? '#00e676' : Math.abs(yaw) < 12 ? '#ffd740' : '#ff5252'
    },
    // pitch > 0 = testa alzata
    {
      label: 'PITCH', val: `${pitch >= 0 ? '+' : ''}${pitch.toFixed(1)}°`,
      col: Math.abs(pitch) < 5 ? '#00e676' : Math.abs(pitch) < 12 ? '#ffd740' : '#ff5252'
    },
    {
      label: 'ROLL ', val: `${roll >= 0 ? '+' : ''}${roll.toFixed(1)}°`,
      col: Math.abs(roll) < 5 ? '#00e676' : Math.abs(roll) < 12 ? '#ffd740' : '#ff5252'
    },
  ];

  rows.forEach((r, i) => {
    const cy = pad + lh * (i + 0.5) + lh * 0.1;
    ctx.fillStyle = 'rgba(200,200,200,0.85)';
    ctx.textAlign = 'left';
    ctx.fillText(r.label + ':', pad + W * 0.012, cy + lh * 0.5);
    ctx.fillStyle = r.col;
    ctx.textAlign = 'right';
    ctx.fillText(r.val, pad + boxW - W * 0.012, cy + lh * 0.5);
  });

  ctx.restore();
}

/* ─── Barre breakdown score (alto-destra) ───────────────────────────────── */
function drawScoreBreakdown(ctx, W, H, poseScore, sizeScore, positionScore, totalScore) {
  const pad = W * 0.022;
  const fs = Math.max(10, Math.min(14, W * 0.024));
  const lh = fs * 1.8;
  const barW = W * 0.18;
  const boxW = W * 0.33;
  const boxH = lh * 3 + pad * 1.8;
  const x0 = W - pad - boxW;

  ctx.save();
  ctx.globalAlpha = 0.88;
  ctx.fillStyle = 'rgba(0,0,0,0.58)';
  _rrect(ctx, x0, pad, boxW, boxH, 6);
  ctx.fill();

  const rows = [
    { label: 'Posa', val: Number(poseScore) || 0, weight: '60%' },
    { label: 'Dim.', val: Number(sizeScore) || 0, weight: '30%' },
    { label: 'Centro', val: Number(positionScore) || 0, weight: '10%' },
  ];

  rows.forEach((r, i) => {
    const cy = pad + lh * i + lh * 0.5 + pad * 0.4;
    const barX = x0 + W * 0.015;
    const barY = cy + fs * 0.2;
    const barH = fs * 0.75;
    const filled = Math.max(0, Math.min(1, r.val / 100));
    const col = filled >= 0.8 ? '#00e676' : filled >= 0.5 ? '#ffd740' : '#ff5252';

    // Etichetta
    ctx.font = `bold ${fs}px sans-serif`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(200,200,200,0.85)';
    ctx.fillText(`${r.label} (${r.weight})`, barX, cy);

    // Barra sfondo
    ctx.fillStyle = 'rgba(255,255,255,0.15)';
    _rrect(ctx, barX, barY + fs, barW, barH, 2);
    ctx.fill();

    // Barra riempimento
    ctx.fillStyle = col;
    if (filled > 0) {
      _rrect(ctx, barX, barY + fs, barW * filled, barH, 2);
      ctx.fill();
    }

    // Valore numerico
    ctx.font = `bold ${fs}px monospace`;
    ctx.textAlign = 'right';
    ctx.fillStyle = col;
    ctx.fillText(r.val.toFixed(0), x0 + boxW - W * 0.012, cy);
  });

  ctx.restore();
}

/* ─── Frecce direzionali sui bordi ─────────────────────────────────────── */
/*
 * LOGICA CORRETTA (verificata contro calculate_head_pose_from_mediapipe):
 *
 *   YAW   > 0 → viso gira DESTRA → freccia a sinistra  (← sul bordo sinistro)
 *   YAW   < 0 → viso gira SINISTRA → freccia a destra  (→ sul bordo destro)
 *   PITCH > 0 → testa ALZATA → freccia in basso         (↓ sul bordo basso)
 *   PITCH < 0 → testa ABBASSATA → freccia in alto       (↑ sul bordo alto)
 *   ROLL  > 0 → inclinata DESTRA → arco sinistra
 *   ROLL  < 0 → inclinata SINISTRA → arco destra
 *
 *   size_score < 50 e face_ratio < 0.20  → avvicinati  (↕ centro)
 *   size_score < 50 e face_ratio > 0.55  → allontanati (↕ centro, diverso colore)
 *
 *   Soglie: frecce compaiono solo oltre ±8° per yaw/pitch, ±6° per roll.
 */
/* ─── Overlay landmark live ──────────────────────────────────────────────── */
/*
 * Disegna i punti landmark MediaPipe ricevuti dal server sul canvas.
 * I landmark sono normalizzati [0,1] e vengono scalati alle dimensioni del canvas.
 * Gruppi: oval (contorno viso), occhi, naso, sopracciglia, bocca.
 */
function drawLandmarkOverlay(ctx, W, H) {
  const pose = window.livePoseAngles || {};
  const lm = pose.landmarks;
  if (!lm) return;

  // Converti lista flat [x0,y0,x1,y1,...] in array di punti {x,y} scalati
  function toPoints(flatArr) {
    const pts = [];
    for (let i = 0; i + 1 < flatArr.length; i += 2) {
      pts.push({ x: flatArr[i] * W, y: flatArr[i + 1] * H });
    }
    return pts;
  }

  ctx.save();
  ctx.globalAlpha = 0.65;
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';

  function polyline(pts, close) {
    if (pts.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
    if (close) ctx.closePath();
    ctx.stroke();
  }

  const lw = Math.max(1, W * 0.0025);

  // Contorno viso — bianco molto sottile
  if (lm.oval) {
    ctx.strokeStyle = 'rgba(255,255,255,0.40)';
    ctx.lineWidth = lw;
    polyline(toPoints(lm.oval), true);
  }

  // Sopracciglia — ciano
  ctx.strokeStyle = 'rgba(0,210,210,0.70)';
  ctx.lineWidth = lw * 1.3;
  if (lm.l_brow) polyline(toPoints(lm.l_brow), false);
  if (lm.r_brow) polyline(toPoints(lm.r_brow), false);

  // Occhi — verde
  ctx.strokeStyle = 'rgba(0,210,100,0.75)';
  ctx.lineWidth = lw * 1.3;
  if (lm.l_eye) polyline(toPoints(lm.l_eye), true);
  if (lm.r_eye) polyline(toPoints(lm.r_eye), true);

  // Naso — arancione
  ctx.strokeStyle = 'rgba(255,150,40,0.65)';
  ctx.lineWidth = lw;
  if (lm.nose) polyline(toPoints(lm.nose), false);

  // Bocca — rosa
  ctx.strokeStyle = 'rgba(255,70,110,0.70)';
  ctx.lineWidth = lw * 1.3;
  if (lm.mouth) polyline(toPoints(lm.mouth), true);

  ctx.restore();
}

/* ─── Indicatori di guida semplificati ──────────────────────────────────── */
/*
 * Mostra UN messaggio testuale chiaro al centro-basso del frame.
 * Priorità: distanza > yaw > pitch > roll > ok.
 */
function drawGuidanceText(ctx, W, H, yaw, pitch, roll, score) {
  const pose = window.livePoseAngles || {};
  const sz = pose.sizeScore || 0;
  const ratio = pose.faceRatio || 0;

  // Determina il messaggio di guida (solo il problema principale)
  let msg = null;
  let col = '#ffd740';

  if (score >= 92) {
    msg = '✓ Ottima posa!';
    col = '#00e676';
  } else if (ratio < 0.18) {
    msg = '→ Avvicìnati alla camera';
    col = '#ff8c00';
  } else if (ratio > 0.58) {
    msg = '← Allontànati dalla camera';
    col = '#ff8c00';
  } else if (Math.abs(yaw) > 6) {
    msg = yaw > 0 ? '← Gira il viso verso sinistra' : '→ Gira il viso verso destra';
  } else if (Math.abs(pitch) > 6) {
    msg = pitch > 0 ? '↓ Abbassa leggermente il mento' : '↑ Alza leggermente il mento';
  } else if (Math.abs(roll) > 5) {
    msg = roll > 0 ? '↺ Inclina la testa verso sinistra' : '↻ Inclina la testa verso destra';
  } else if (sz < 40) {
    msg = '→ Avvicìnati un po\'';
    col = '#ff8c00';
  }

  if (!msg) {
    // Nessuna guida necessaria in questo frame: resetta per evitare stale messages
    window.lastGuidanceMsg = null;
    const _domG = document.getElementById('wfs-guidance-text');
    if (_domG) _domG.style.display = 'none';
    return;
  }

  // Esponi il messaggio corrente per il sistema di guida vocale
  window.lastGuidanceMsg = msg;
  window.lastGuidanceMsgTime = Date.now();

  // Su mobile: aggiorna solo il DOM element (posizionato in CSS); no canvas.
  // Su desktop: nascondi DOM e disegna solo sul canvas (evita il duplicato sotto al canvas).
  const _domGuidance = document.getElementById('wfs-guidance-text');
  if (window.innerWidth <= 768) {
    if (_domGuidance) {
      _domGuidance.textContent = msg;
      _domGuidance.style.color = col;
      _domGuidance.style.display = 'block';
    }
    return; // mobile: testo mostrato dal DOM, nessun ridisegno canvas
  }
  // Desktop: nascondi DOM, usa solo il canvas
  if (_domGuidance) _domGuidance.style.display = 'none';

  const _mobileFs = W <= 480;
  const fs = _mobileFs ? Math.max(18, Math.min(26, W * 0.055)) : Math.max(13, Math.min(18, W * 0.030));
  const pad = W * 0.025;

  ctx.save();
  ctx.font = `bold ${fs}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const tw = ctx.measureText(msg).width;
  const bw = tw + pad * 2.5;
  const bh = fs * 1.8;
  const bx = (W - bw) / 2;
  const by = H - bh - H * 0.04;

  // Sfondo etichetta
  ctx.globalAlpha = 0.82;
  ctx.fillStyle = 'rgba(0,0,0,0.65)';
  _rrect(ctx, bx, by, bw, bh, 6);
  ctx.fill();

  // Testo
  ctx.globalAlpha = 1.0;
  ctx.fillStyle = col;
  ctx.shadowColor = 'rgba(0,0,0,0.9)';
  ctx.shadowBlur = 6;
  ctx.fillText(msg, W / 2, by + bh / 2);

  ctx.restore();
}

function stopLivePreview() {
  window.livePreviewActive = false;
  if (window.livePreviewId) {
    cancelAnimationFrame(window.livePreviewId);
    window.livePreviewId = null;
  }
}

/**
 * Apre l'overlay webcam a tutto schermo.
 * Crea un div fisso che copre tutto lo schermo e vi sposta il canvas di anteprima.
 */
function openWebcamFullscreen(video) {
  if (document.getElementById('webcam-fullscreen-overlay')) return; // già aperto

  const overlay = document.createElement('div');
  overlay.id = 'webcam-fullscreen-overlay';

  const stopBtn = document.createElement('button');
  stopBtn.id = 'wfs-stop-btn';
  stopBtn.innerHTML = '⏹ Stop Webcam';
  stopBtn.onclick = () => stopWebcam();

  const guidanceText = document.createElement('div');
  guidanceText.id = 'wfs-guidance-text';

  // Crea un canvas dedicato per il fullscreen (il canvas originale rimane nella sidebar)
  const fsCanvas = document.createElement('canvas');
  fsCanvas.id = 'webcam-fullscreen-canvas';
  // Le dimensioni (width/height) vengono impostate dinamicamente dal loop di rendering
  // in base all'aspect ratio del video — NON usare object-fit che non funziona su <canvas>.
  fsCanvas.style.cssText = 'display:block;';

  overlay.appendChild(fsCanvas);
  overlay.appendChild(guidanceText);
  overlay.appendChild(stopBtn);
  document.body.appendChild(overlay);

  // Avvia il rendering sul canvas fullscreen
  startFullscreenPreviewLoop(video, fsCanvas);
}

/**
 * Chiude l'overlay fullscreen e ferma il rendering dedicato.
 */
function closeWebcamFullscreen() {
  window.fsPreviewActive = false;
  if (window.fsPreviewId) {
    cancelAnimationFrame(window.fsPreviewId);
    window.fsPreviewId = null;
  }
  const overlay = document.getElementById('webcam-fullscreen-overlay');
  if (overlay) overlay.remove();
}

/**
 * Pronuncia una frase di guida posa con strategia a doppio livello:
 *
 *   1. Audio TTS server (voce Isabella) se già in cache → zero latenza
 *   2. Cache miss → voiceAssistant.speakCoach() → TTS server (voce Isabella)
 *      NOTA: Rimosso il fallback window.speechSynthesis che usava la voce
 *      di default del browser (spesso maschile), incoerente con Isabella.
 *
 * ANTI-ACCODAMENTO: la funzione verifica prima se il voiceAssistant
 * ha già elementi in coda o se la sintesi nativa è in corso.
 * In tal caso NON aggiunge nulla → l'utente sente UNA frase alla volta.
 */
function speakPoseInstant(text) {
  if (!text) return;

  // ── Controllo audio TTS server in coda ───────────────────────────────────
  // Se il voiceAssistant ha già elementi pendenti (da guida posa o altro),
  // non accodiamo: aspettiamo che finisca prima di parlare di nuovo.
  if (typeof voiceAssistant !== 'undefined') {
    if (voiceAssistant.pendingQueue && voiceAssistant.pendingQueue.length > 0) return;
    if (voiceAssistant._flushRunning) return;
  }

  // ── Controllo Web Speech API in corso ────────────────────────────────────
  // (mantenuto per sicurezza nel caso altri moduli la usino ancora)
  try {
    if (window.speechSynthesis && window.speechSynthesis.speaking) return;
  } catch (_) { }

  // 1. Cache hit: riproduce audio TTS server (voce Isabella, già scaricata)
  if (typeof voiceAssistant !== 'undefined' && voiceAssistant._audioCache &&
    voiceAssistant._audioCache.has(text)) {
    voiceAssistant.speak(text).catch(() => { });
    return;
  }

  // 2. Cache miss: usa voiceAssistant.speakCoach() → voce Isabella (TTS server).
  // NON usare window.speechSynthesis perché usa la voce di default del browser
  // (spesso maschile) creando incongruenza con la voce Isabella.
  if (typeof voiceAssistant !== 'undefined') {
    voiceAssistant.speakCoach(text).catch(() => { });
  }
}

/**
 * Avvia il sistema di guida vocale durante la webcam.
 *
 * REGOLE DI MODERAZIONE:
 *   • Stessa frase → non viene ripetuta prima di SAME_MSG_COOLDOWN_MS (12s).
 *     Questo evita il loop "Abbassa il mento… Abbassa il mento… Abbassa il mento".
 *   • Frase diversa → può essere pronunciata subito, ma non prima di
 *     MIN_BETWEEN_SPEAKS_MS (3s) dall'ultima pronuncia (evita raffiche).
 *   • Anti-accodamento: speakPoseInstant() non aggiunge se c'è già qualcosa
 *     in coda/in riproduzione, quindi al massimo 1 frase per volta.
 *   • Poll ogni 250ms → reazione visivamente "istantanea" al cambio di posa.
 */
function startPoseVoiceGuidance() {
  stopPoseVoiceGuidance(); // Ferma e pulisce ogni stato precedente

  const SAME_MSG_COOLDOWN_MS = 12000; // Stessa frase: non ripetere prima di 12s
  const MIN_BETWEEN_SPEAKS_MS = 3000; // Tra frasi diverse: almeno 3s

  // Variabili locali — la chiusura le mantiene vive per tutta la sessione
  let lastSpokenMsg = null;
  let lastSpokenTime = 0;

  window._poseVoiceTimer = setInterval(() => {
    if (!isWebcamActive) { stopPoseVoiceGuidance(); return; }

    const msg = window.lastGuidanceMsg;
    if (!msg) return;

    // Rimuovi frecce/emoji, mantieni solo il testo leggibile
    const voiceText = msg.replace(/^[↑↓←→↺↻✓]\s*/, '').trim();
    if (!voiceText) return;

    const now = Date.now();
    const isSameMsg = (voiceText === lastSpokenMsg);
    const elapsed = now - lastSpokenTime;

    // Salta se:
    //   • stessa frase E non sono passati 12s  (anti-ripetizione)
    //   • frase diversa ma non sono passati 3s  (anti-raffica)
    if (isSameMsg && elapsed < SAME_MSG_COOLDOWN_MS) return;
    if (!isSameMsg && elapsed < MIN_BETWEEN_SPEAKS_MS) return;

    lastSpokenMsg = voiceText;
    lastSpokenTime = now;
    speakPoseInstant(voiceText);
  }, 250);
}

/**
 * Ferma la guida vocale e interrompe IMMEDIATAMENTE qualsiasi audio in corso.
 *
 * Oltre a fermare il timer, svuota anche la pendingQueue del voiceAssistant
 * e ferma l'audioPlayer → nessuna frase residua viene pronunciata dopo Stop.
 */
function stopPoseVoiceGuidance() {
  if (window._poseVoiceTimer) {
    clearInterval(window._poseVoiceTimer);
    window._poseVoiceTimer = null;
  }
  window.lastGuidanceMsg = null;
  const _domG = document.getElementById('wfs-guidance-text');
  if (_domG) _domG.style.display = 'none';

  // 1. Nessuna sintesi nativa da fermare (rimossa per evitare voce maschile del browser)

  // 2. Svuota coda + ferma audioPlayer del voiceAssistant (evita la "coda lunga")
  if (typeof voiceAssistant !== 'undefined') {
    try {
      voiceAssistant.pendingQueue = [];   // svuota la coda
      voiceAssistant._flushRunning = false; // sblocca il mutex
      if (voiceAssistant.audioPlayer) {
        voiceAssistant.audioPlayer.pause();
        voiceAssistant.audioPlayer.onended = null;
        voiceAssistant.audioPlayer.src = '';
      }
    } catch (_) { }
  }
}

/**
 * Loop di rendering per il canvas fullscreen.
 * Se video è disponibile (webcam PC), disegna direttamente dal video.
 * Se video è null (iPhone), copia dal canvas di anteprima sidebar.
 */
function startFullscreenPreviewLoop(video, fsCanvas) {
  window.fsPreviewActive = false;
  if (window.fsPreviewId) {
    cancelAnimationFrame(window.fsPreviewId);
    window.fsPreviewId = null;
  }

  let lastTs = 0;
  const INTERVAL = 33; // ~30 FPS

  // Timestamp ultima stima posa locale (throttle 10fps)
  let _localPoseTs = 0;

  function loop(ts) {
    if (!window.fsPreviewActive) return;

    if (ts - lastTs >= INTERVAL) {
      // Sorgente: video element (webcam PC) oppure canvas fullres iPhone (fallback: canvas sidebar)
      const source = (video && video.videoWidth > 0)
        ? video
        : (document.getElementById('iphone-fullres-canvas') || document.getElementById('webcam-preview-canvas'));

      if (source) {
        const srcW = source.videoWidth || source.width;
        const srcH = source.videoHeight || source.height;

        if (srcW > 0 && srcH > 0) {
          const ctx = fsCanvas.getContext('2d');

          const _fsIsMobile = window.innerWidth <= 768;
          const vw = window.innerWidth;
          const vh = _fsIsMobile ? window.innerHeight : (window.innerHeight - 70);

          let cw, ch;
          let drawX = 0, drawY = 0, drawW, drawH;

          if (_fsIsMobile) {
            // Mobile — modalità COVER: il canvas occupa TUTTO lo schermo, i margini
            // del video vengono tagliati ma il centro (dove si trova il viso) rimane
            // visibile. Questo elimina le barre nere sopra/sotto ("doppio fondo").
            cw = vw;
            ch = vh;
            const srcAr = srcW / srcH;
            const canvasAr = cw / ch;
            if (canvasAr > srcAr) {
              // Canvas più largo del video → riempie larghezza, ritaglia altezza
              drawW = cw;
              drawH = Math.round(cw / srcAr);
              drawX = 0;
              drawY = Math.round((ch - drawH) / 2); // centro verticale
            } else {
              // Canvas più alto del video → riempie altezza, ritaglia larghezza
              drawH = ch;
              drawW = Math.round(ch * srcAr);
              drawX = Math.round((cw - drawW) / 2); // centro orizzontale
              drawY = 0;
            }
          } else {
            // Desktop — modalità CONTAIN: rispetta l'aspect ratio del video,
            // eventuale sfondo nero intorno al canvas.
            const ar = srcW / srcH;
            if (vw / vh > ar) {
              ch = vh; cw = Math.round(ch * ar);
            } else {
              cw = vw; ch = Math.round(cw / ar);
            }
            drawW = cw;
            drawH = ch;
          }

          if (fsCanvas.width !== cw || fsCanvas.height !== ch) {
            fsCanvas.width = cw;
            fsCanvas.height = ch;
            fsCanvas.style.width = cw + 'px';
            fsCanvas.style.height = ch + 'px';
          }

          // Disegna a specchio (flip orizzontale) — solo visivo.
          // Con il flip + la centratura simmetrica di drawX/drawY, il ritaglio
          // cover rimane centrato anche dopo il ribaltamento.
          ctx.save();
          ctx.translate(cw, 0);
          ctx.scale(-1, 1);
          ctx.drawImage(source, drawX, drawY, drawW, drawH);
          ctx.restore();

          // ─── Stima posa locale (MediaPipe browser, ~10fps) ───────────────────────
          // Aggiorna livePoseAngles nel browser, senza attendere il server.
          // Elimina 200-400ms di latenza round-trip per overlay e guida vocale.
          if (video && video.videoWidth > 0
            && typeof faceLandmarker !== 'undefined' && faceLandmarker
            && typeof isMediaPipeLoaded !== 'undefined' && isMediaPipeLoaded
            && ts - _localPoseTs >= 100) {
            _localPoseTs = ts;
            try {
              const _r = faceLandmarker.detect(video);
              if (_r.faceLandmarks && _r.faceLandmarks.length > 0) {
                const _lm = _r.faceLandmarks[0];
                // faceRatio: altezza faccia normalizzata (range 0–1)
                let _minY = 1, _maxY = 0;
                for (const _p of _lm) {
                  if (_p.y < _minY) _minY = _p.y;
                  if (_p.y > _maxY) _maxY = _p.y;
                }
                // Yaw/pitch/roll dalla matrice di trasformazione 3D MediaPipe
                let _yaw = 0, _pitch = 0, _roll = 0;
                if (_r.facialTransformationMatrixes && _r.facialTransformationMatrixes.length > 0) {
                  const _m = _r.facialTransformationMatrixes[0].data;
                  // Column-major 4×4: estrazione angoli di Eulero (ZYX)
                  const _cy = Math.sqrt(_m[0] * _m[0] + _m[1] * _m[1]);
                  if (_cy > 1e-6) {
                    _yaw = Math.atan2(-_m[2], _cy) * 180 / Math.PI;
                    _pitch = Math.atan2(_m[6], _m[10]) * 180 / Math.PI;
                    _roll = Math.atan2(_m[1], _m[0]) * 180 / Math.PI;
                  }
                }
                // Preserva score e landmark dal server; aggiorna solo la posa locale
                window.livePoseAngles = {
                  yaw: _yaw, pitch: _pitch, roll: _roll,
                  faceRatio: _maxY - _minY,
                  score: window.livePoseAngles.score || 0,
                  sizeScore: window.livePoseAngles.sizeScore || 0,
                  poseScore: window.livePoseAngles.poseScore || 0,
                  positionScore: window.livePoseAngles.positionScore || 0,
                  landmarks: window.livePoseAngles.landmarks || null,
                };
              } else {
                // Viso non rilevato → faceRatio=0 → guida "Posizionati davanti"
                if (window.livePoseAngles) window.livePoseAngles.faceRatio = 0;
              }
            } catch (_) { /* MediaPipe occupato o frame non pronto: riprova al prossimo tick */ }
          }
          // ───────────────────────────────────────────────────────────────────
          drawFaceGuideOverlay(ctx, cw, ch);
        }
      }

      lastTs = ts;
    }
    window.fsPreviewId = requestAnimationFrame(loop);
  }

  window.fsPreviewActive = true;
  window.fsPreviewId = requestAnimationFrame(loop);
}

function updateWebcamPreview(video) {
  // Questa funzione ora serve solo per il setup iniziale
}

// Variabile globale per tracciare miglior score finora
let currentBestScore = 0;
let getResultsRequestId = 0; // Contatore richieste
let pendingGetResultsRequests = new Set(); // Track richieste in corso

// Pose angles live (aggiornati da ogni frame_processed del server)
window.livePoseAngles = { yaw: 0, pitch: 0, roll: 0, score: 0 };

function handleWebSocketMessage(data) {
  try {
    // ✅ DELEGA messaggi iPhone all'handler in index.html
    if (data.action && (data.action.startsWith('iphone_') || data.action === 'desktop_registered')) {
      // Chiama handler iPhone se disponibile
      if (typeof handleIPhoneWebSocketMessage === 'function') {
        handleIPhoneWebSocketMessage(data);
      }
      return; // Non processare oltre in main.js
    }

    switch (data.action) {
      case 'session_started':
        updateStatus('Sessione avviata - Analisi in corso...');
        // Reset stato per nuova sessione
        currentBestScore = 0;
        pendingGetResultsRequests.clear();
        lastGetResultsTime = 0;
        window.lastFramesHash = null;
        break;

      case 'frame_processed':
        // Frame elaborato dal server
        updateFrameProcessingStats(data);

        // Richiedi get_results se ci sono frame validi
        const hasFrames = (data.total_frames_collected && data.total_frames_collected > 0) ||
          (data.faces_detected && data.faces_detected > 0);

        if (hasFrames) {
          const frameCount = data.total_frames_collected || 1;
          const shouldRequest = currentBestScore === 0 ||
            (data.current_score && data.current_score > currentBestScore + 0.5) ||
            (frameCount % 5 === 0);

          if (shouldRequest) {
            requestBestFramesUpdate();
          }
        }
        break;

      case 'results_ready':
        // Risultati finali dal server
        handleResultsReady(data);

        // ✅ APRI automaticamente sezione DATI ANALISI per mostrare tabella debug
        // (sia durante streaming webcam che al termine)
        openUnifiedAnalysisSection();
        switchUnifiedTab('debug');
        break;

      case 'pong':
        // Risposta al ping - ignora
        break;

      default:
        if (data.error) {
          console.error('Errore dal server:', data.error);
          showToast(data.error, 'error');
        }
    }
  } catch (error) {
    console.error('Errore gestione messaggio WebSocket:', error);
  }
}

// ✅ THROTTLING: Limita richieste get_results
const MAX_PENDING_REQUESTS = 3; // ✅ FIX: Aumentato da 2 a 3
let lastGetResultsTime = 0;
const MIN_REQUEST_INTERVAL = 300; // ✅ FIX: Ridotto da 500ms a 300ms per aggiornamenti più frequenti

function requestBestFramesUpdate(force = false) {
  if (!webcamWebSocket || webcamWebSocket.readyState !== WebSocket.OPEN) {
    return;
  }

  const now = Date.now();

  // Throttle: non inviare se troppe richieste pending o troppo recente
  if (!force && pendingGetResultsRequests.size >= MAX_PENDING_REQUESTS) {
    return;
  }

  if (!force && now - lastGetResultsTime < MIN_REQUEST_INTERVAL) {
    return;
  }

  lastGetResultsTime = now;

  // Incrementa contatore e traccia richiesta
  const requestId = ++getResultsRequestId;
  pendingGetResultsRequests.add(requestId);

  const requestMessage = {
    action: 'get_results',
    request_id: requestId,
    session_token: window._iphoneSessionToken || '',
    timestamp: now
  };

  webcamWebSocket.send(JSON.stringify(requestMessage));
}

function updateFrameProcessingStats(data) {
  // Aggiorna statistiche di elaborazione live in un box SEPARATO
  // così non sovrascrive il box del frame selezionato
  const liveStats = document.getElementById('live-processing-stats');
  if (liveStats) {
    liveStats.innerHTML = `
      ⏳ Frame elaborati: ${data.total_frames_collected || 0} ―
      Ultimo: ${(data.current_score || data.score || 0).toFixed(1)} ―
      Volti: ${data.faces_detected || 0}
    `;
  }

  // Salva pose angles live per il rendering dell'overlay nell'anteprima
  // Il server invia 'pose' (non 'pose_angles') nel messaggio frame_processed,
  // più 'score_breakdown' con i dettagli delle tre componenti.
  const poseData = data.pose || data.pose_angles;
  if (poseData) {
    const sb = data.score_breakdown || {};
    window.livePoseAngles = {
      yaw: poseData.yaw || 0,
      pitch: poseData.pitch || 0,
      roll: poseData.roll || 0,
      score: data.current_score || data.score || 0,  // iPhone usa 'score', webcam usa 'current_score'
      poseScore: sb.pose_score || 0,
      sizeScore: sb.size_score || 0,
      positionScore: sb.position_score || 0,
      faceRatio: sb.face_ratio || 0,
      landmarks: data.landmarks || null,
    };
  } else if (data.current_score !== undefined || data.score !== undefined) {
    window.livePoseAngles.score = data.current_score || data.score || 0;
  }

  // Notifica audio per frame con score ≥ 92 (solo webcam PC - iPhone usa playBeep in index.html)
  // Non suonare se è un frame iPhone (evita doppio beep)
  const _statsScore = data.current_score || data.score || 0;
  const _isIPhoneFrame = data.action === 'iphone_frame_processed';
  if (!_isIPhoneFrame && _statsScore >= 92 && _statsScore > currentBestScore) {
    playHighScoreSound(_statsScore);
  }
}

// Variabile per throttling suono
let lastSoundTime = 0;

function playHighScoreSound(score) {
  // Throttle: max 1 suono ogni 800ms
  const now = Date.now();
  if (now - lastSoundTime < 800) return;
  lastSoundTime = now;

  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    // 1000 Hz se score ≥ 97, altrimenti 800 Hz
    oscillator.frequency.value = (score >= 97) ? 1000 : 800;
    oscillator.type = 'sine';

    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

    // Resume necessario su Chrome dopo policy autoplay
    audioContext.resume().then(() => {
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.2);
    });
  } catch (e) {
    console.error('Errore riproduzione suono:', e);
  }
}

function updateBestFramesDisplay(data) {
  try {
    if (data.best_frames && data.best_frames.length > 0) {
      const bestFrame = data.best_frames[0]; // Prendi il miglior frame

      if (bestFrame.image_data) {
        // Aggiorna canvas con il miglior frame
        updateCanvasWithBestFrame(bestFrame.image_data);
      }
    }
  } catch (error) {
    console.error('Errore aggiornamento display frame:', error);
  }
}

function updateCanvasWithBestFrame(imageData, mimeType = 'image/jpeg') {
  try {
    if (!fabricCanvas) return;

    // Mostra canvas se nascosto
    const canvasElement = document.getElementById('main-canvas');
    if (canvasElement) {
      canvasElement.style.display = 'block';
    }

    // Crea immagine da base64 usando Fabric.js (preserva formato originale)
    const imageUrl = `data:${mimeType};base64,${imageData}`;

    fabric.Image.fromURL(imageUrl, function (img) {
      // Propaga il tipo MIME originale
      if (img && img.getElement) {
        img.getElement()._originalMimeType = mimeType;
      }
      try {
        // Rimuovi immagine precedente se presente
        if (currentImage) {
          fabricCanvas.remove(currentImage);
        }

        // Utilizza tutto lo spazio disponibile per i frame video/webcam
        const sizing = calculateOptimalImageSize(
          img.width,
          img.height,
          fabricCanvas.width,
          fabricCanvas.height,
          5  // padding ancora più ridotto per video/webcam
        );


        // Applica il ridimensionamento
        img.scale(sizing.scale);

        // Posiziona l'immagine utilizzando tutto lo spazio disponibile
        // IMMAGINE COMPLETAMENTE NON INTERATTIVA
        img.set({
          left: sizing.left,
          top: sizing.top,
          selectable: false,      // DISABILITA selezione
          evented: false,         // DISABILITA eventi
          lockMovementX: true,
          lockMovementY: true,
          lockScalingX: true,
          lockScalingY: true,
          lockRotation: true,
          hasControls: false,     // Nessun controllo
          hasBorders: false,      // Nessun bordo
          hoverCursor: 'default'  // Cursore normale
        });

        // Aggiungi al canvas e metti in background
        fabricCanvas.add(img);
        fabricCanvas.sendToBack(img);

        // FORZA il blocco dell'immagine dopo l'aggiunta al canvas
        img.selectable = false;
        img.evented = false;
        img.lockMovementX = true;
        img.lockMovementY = true;
        img.lockScalingX = true;
        img.lockScalingY = true;
        img.lockRotation = true;
        img.hasControls = false;
        img.hasBorders = false;

        // Configura sincronizzazione overlay (anche se immagine bloccata)
        if (typeof setupImageTransformSync === 'function') {
          setupImageTransformSync(img);
        }

        // IMPORTANTE: Assegna currentImage per le funzioni che ne hanno bisogno
        currentImage = img;
        currentImage.isBackgroundImage = true;
        currentImageElement = img.getElement ? img.getElement() : null;

        // Aggiorna le variabili globali di trasformazione
        window.imageScale = sizing.scale;
        window.imageOffset = { x: sizing.left, y: sizing.top };

        console.log('✅ imageScale e imageOffset impostati:', {
          scale: sizing.scale,
          offset: { x: sizing.left, y: sizing.top }
        });

        fabricCanvas.renderAll();


        // Aggiorna info immagine se disponibile
        if (typeof updateImageInfo === 'function') {
          updateImageInfo(img);
        }

        // NON chiamare auto-rilevamento landmarks per frame video/webcam
        // L'analisi avviene tramite WebSocket, non HTTP API
        // Solo per immagini statiche caricate dall'utente

      } catch (fabricError) {
        console.error('❌ Errore Fabric.js:', fabricError);
      }
    }, {
      // Opzioni per il caricamento dell'immagine
      crossOrigin: 'anonymous'
    });

  } catch (error) {
    console.error('❌ Errore aggiornamento canvas:', error);
  }
}

// Variabile globale per conservare i frame (esposta su window)
window.currentBestFrames = [];
let currentBestFrames = window.currentBestFrames; // Alias per retrocompatibilità

/**
 * PUNTO UNICO di sincronizzazione canvas ↔ info-box.
 * Aggiorna il canvas con l'immagine del frame E il box info con i metadati corretti.
 * @param {Object} frame  - Oggetto frame con image_data, score, rank, yaw, pitch, roll
 * @param {number} index  - Indice nella lista (0 = miglior frame)
 * @param {boolean} silent - Se true non mostra toast
 */
function _syncCanvasFrame(frame, index, silent = false) {
  if (!frame || !frame.image_data) return;
  const frameNumber = frame.rank || (index + 1);

  updateCanvasWithBestFrame(frame.image_data);

  // Aggiorna sempre il box info con i dati reali del frame visualizzato
  const frameInfo = document.getElementById('best-frame-info');
  if (frameInfo) {
    frameInfo.innerHTML = `
      Frame selezionato: #${frameNumber}<br>
      Score: ${(frame.score || 0).toFixed(3)}<br>
      Pose: Y=${(frame.yaw || 0).toFixed(1)}° P=${(frame.pitch || 0).toFixed(1)}° R=${(frame.roll || 0).toFixed(1)}°
    `;
  }

  if (!silent) {
    showToast(`Frame ${frameNumber} visualizzato nel canvas`, 'info');
  }
}

/**
 * Ri-aggancia gli event listener alle righe della tabella debug unificata
 * @param {HTMLElement} unifiedTableBody - La tabella unificata
 * @param {HTMLElement} originalTableBody - La tabella originale debug
 * @param {number} startIndex - Indice da cui iniziare (opzionale, default 0)
 */
function reattachDebugTableListeners(unifiedTableBody, originalTableBody, startIndex = 0) {
  if (!unifiedTableBody || !originalTableBody) return;

  const unifiedRows = Array.from(unifiedTableBody.querySelectorAll('tr'));

  // Processa SOLO le righe a partire da startIndex
  for (let index = startIndex; index < unifiedRows.length; index++) {
    const unifiedRow = unifiedRows[index];

    // Aggiungi il listener SOLO se non esiste già (controlla se ha già il dataset)
    if (!unifiedRow.dataset.listenerAttached && window.currentBestFrames && window.currentBestFrames[index]) {
      unifiedRow.style.cursor = 'pointer';
      unifiedRow.dataset.listenerAttached = 'true'; // Marca come processato

      unifiedRow.addEventListener('click', function () {
        const frame = window.currentBestFrames[index];
        if (typeof showFrameInMainCanvas === 'function') {
          showFrameInMainCanvas(frame, index);

          // Rimuovi highlight precedente
          unifiedTableBody.querySelectorAll('tr').forEach(r => r.classList.remove('selected-frame'));
          if (originalTableBody) {
            originalTableBody.querySelectorAll('tr').forEach(r => r.classList.remove('selected-frame'));
          }

          // Aggiungi highlight
          unifiedRow.classList.add('selected-frame');
        }
      });
    }
  }

  const processedCount = unifiedRows.length - startIndex;
  if (processedCount > 0) {
    console.log(`🔗 Event listener aggiunti a ${processedCount} righe (da ${startIndex} a ${unifiedRows.length - 1})`);
  }
}

function updateDebugTable(bestFrames) {
  try {
    const debugTableBody = document.getElementById('debug-data');
    if (!debugTableBody) return;

    // Salva i frame globalmente per il click handler
    currentBestFrames = bestFrames;
    window.currentBestFrames = bestFrames; // Esponi anche su window

    // Pulisci tabella esistente
    debugTableBody.innerHTML = '';

    // Aggiungi righe per ogni frame
    bestFrames.forEach((frame, index) => {
      const row = document.createElement('tr');

      // Applica classe per evidenziare il miglior frame
      if (index === 0) {
        row.classList.add('best-frame-row');
      }

      // Aggiunge cursor pointer e click handler
      row.style.cursor = 'pointer';
      row.title = 'Clicca per visualizzare questo frame nel canvas principale';

      // Calcola il timestamp - usa quello del frame o l'attuale
      const frameTime = frame.timestamp ? new Date(frame.timestamp * 1000) : new Date();

      row.innerHTML = `
        <td>${String(frame.rank || index + 1).padStart(2, '0')}</td>
        <td>${frameTime.toLocaleTimeString()}</td>
        <td class="score-cell ${getScoreClass(frame.score)}">${(frame.score || 0).toFixed(3)}</td>
        <td>${(frame.yaw || 0).toFixed(2)}°</td>
        <td>${(frame.pitch || 0).toFixed(2)}°</td>
        <td>${(frame.roll || 0).toFixed(2)}°</td>
        <td><span class="status-badge status-success">Salvato</span></td>
      `;

      // Aggiungi click handler per visualizzare il frame nel canvas
      row.addEventListener('click', function () {
        showFrameInMainCanvas(frame, index);

        // Rimuovi highlight precedente
        debugTableBody.querySelectorAll('tr').forEach(r => r.classList.remove('selected-frame'));
        // Aggiungi highlight alla riga selezionata
        row.classList.add('selected-frame');
      });

      debugTableBody.appendChild(row);
    });

    // Apri la sezione DATI ANALISI unificata e switcha al tab DEBUG
    // SEMPRE quando riceviamo i primi frame di un nuovo video (forza apertura)
    const currentTab = window.unifiedTableCurrentTab;
    const unifiedTableBody = document.getElementById('unified-table-body');
    const shouldForceOpen = window._shouldOpenDebugTab === true;

    if (!currentTab || currentTab !== 'debug' || !unifiedTableBody || unifiedTableBody.children.length === 0 || shouldForceOpen) {
      console.log('🔄 [UNIFIED] Apertura forzata tab DEBUG - nuovo video caricato');
      openUnifiedAnalysisSection();
      switchUnifiedTab('debug', null, true); // ✅ Forza aggiornamento con terzo parametro
      window._shouldOpenDebugTab = false; // Reset flag dopo apertura
    } else {
      // La tabella è già sul tab debug - aggiornamento INCREMENTALE per evitare flickering
      const tableBody = document.getElementById('unified-table-body');
      if (tableBody && debugTableBody) {
        const currentRowCount = tableBody.children.length;
        const newRowCount = debugTableBody.children.length;

        if (currentRowCount < newRowCount) {

          // Aggiungi solo le righe dalla posizione currentRowCount in poi
          const newRows = Array.from(debugTableBody.children).slice(currentRowCount);
          newRows.forEach(row => {
            const clonedRow = row.cloneNode(true);
            tableBody.appendChild(clonedRow);
          });

          // Ri-aggiungi event listener SOLO alle nuove righe appena aggiunte
          reattachDebugTableListeners(tableBody, debugTableBody, currentRowCount);
        } else if (currentRowCount > newRowCount) {

          while (tableBody.children.length > newRowCount) {
            tableBody.removeChild(tableBody.lastChild);
          }
        } else {
          // ✅ FIX: Stesso numero di righe MA dati potrebbero essere cambiati
          // Aggiorna il contenuto delle celle esistenti
          const sourceRows = Array.from(debugTableBody.children);
          const targetRows = Array.from(tableBody.children);

          sourceRows.forEach((sourceRow, i) => {
            if (targetRows[i]) {
              // Copia innerHTML aggiornato dalla source
              const sourceCells = sourceRow.querySelectorAll('td');
              const targetCells = targetRows[i].querySelectorAll('td');

              sourceCells.forEach((cell, j) => {
                if (targetCells[j] && targetCells[j].innerHTML !== cell.innerHTML) {
                  targetCells[j].innerHTML = cell.innerHTML;
                  targetCells[j].className = cell.className;
                }
              });
            }
          });

        }
      }
    }

    // Mostra automaticamente il miglior frame (primo della lista) nel canvas centrale
    // e aggiorna il box info in modo coerente (silent: no toast durante aggiornamenti periodici)
    if (bestFrames.length > 0 && bestFrames[0].image_data) {
      _syncCanvasFrame(bestFrames[0], 0, true);
    }

    // Scroll automatico DISABILITATO - la colonna rimane in alto
    // const autoScroll = document.getElementById('auto-scroll');
    // if (autoScroll && autoScroll.checked) {
    //   debugTableBody.scrollIntoView({ behavior: 'smooth', block: 'end' });
    // }

  } catch (error) {
    console.error('Errore aggiornamento tabella debug:', error);
  }
}

// ✅ NUOVA FUNZIONE: Aggiorna solo tabella senza toccare canvas
function getScoreClass(score) {
  if (score >= 0.9) return 'excellent';
  if (score >= 0.8) return 'very-good';
  if (score >= 0.7) return 'good';
  return 'poor';
}

/**
 * ✅ FONTE UNICA DI VERITÀ: Trasforma i dati WebSocket in formato bestFrames
 * Usa json_data come fonte primaria per score, pose e timestamp
 * data.frames fornisce solo le immagini base64
 */
function transformWebSocketFrames(data) {
  if (!data.frames || data.frames.length === 0) {
    return [];
  }

  if (data.json_data && data.json_data.frames && data.json_data.frames.length > 0) {
    // ✅ CASO PRINCIPALE: Costruisci da json_data
    return data.json_data.frames.map((jsonFrame, index) => ({
      rank: index + 1,
      original_frame: jsonFrame.rank,
      score: jsonFrame.total_score || 0,
      image_data: data.frames[index]?.data || null,
      timestamp: jsonFrame.timestamp || Date.now() / 1000,
      yaw: jsonFrame.pose?.yaw || 0,
      pitch: jsonFrame.pose?.pitch || 0,
      roll: jsonFrame.pose?.roll || 0
    }));
  } else {
    // ⚠️ FALLBACK: Se json_data non disponibile
    return data.frames.map((frame, index) => ({
      rank: index + 1,
      original_frame: frame.rank,
      score: frame.score || 0,
      image_data: frame.data,
      timestamp: Date.now() / 1000,
      yaw: 0,
      pitch: 0,
      roll: 0
    }));
  }
}

function showFrameInMainCanvas(frame, index) {
  try {
    const frameNumber = frame.rank || (index + 1);
    console.log(`🖼️ Mostrando frame ${frameNumber} nel canvas principale`);

    if (frame.image_data) {
      // Usa il punto unico di sync canvas + info box (con toast)
      _syncCanvasFrame(frame, index, false);
    } else {
      showToast('Dati immagine non disponibili per questo frame', 'warning');
    }

  } catch (error) {
    console.error('Errore visualizzazione frame:', error);
    showToast('Errore visualizzazione frame', 'error');
  }
}

function handleResultsReady(data) {
  try {
    const responseId = data.request_id || 'unknown';

    // Rimuovi dalla lista pending se presente
    if (typeof responseId === 'number') {
      pendingGetResultsRequests.delete(responseId);
    }

    // 🔍 DIAGNOSTICA: log sempre visibile indipendentemente da success
    console.log(`🔍 results_ready: success=${data.success} frames=${data.frames?.length ?? 'N/A'} error=${data.error ?? 'none'} is_final=${data.is_final ?? false}`);

    if (data.success && data.frames && data.frames.length > 0) {
      const newBestScore = data.best_score || 0;
      const scoreDiff = newBestScore - currentBestScore;

      // Hash affidabile: usa SCORES + RANKS di tutti i frame (non solo count+bestscore)
      const newHash = data.frames.map(f => `${f.rank || 0}:${(f.score || 0).toFixed(2)}`).join('|');

      // Aggiorna solo se cambia: primo frame, score migliora, contenuto frame diverso,
      // oppure se è il risultato finale (fine sessione)
      const isFirstFrame = currentBestScore === 0;
      const hasImproved = scoreDiff > 0.05;
      const framesChanged = !window.lastFramesHash || window.lastFramesHash !== newHash;
      const isFinalResult = !!data.is_final;
      console.log(`📊 handleResultsReady: frames=${data.frames?.length || 0} bestScore=${newBestScore.toFixed(2)} isFinal=${isFinalResult} first=${isFirstFrame} improved=${hasImproved} changed=${framesChanged}`);

      if (!isFirstFrame && !hasImproved && !framesChanged && !isFinalResult) {
        return;
      }

      // Aggiorna score e hash (hash dettagliato)
      currentBestScore = newBestScore;
      window.lastFramesHash = newHash;

      // Usa funzione centralizzata per trasformare i dati
      const bestFrames = transformWebSocketFrames(data);

      // Aggiorna quando i dati cambiano effettivamente
      updateDebugTable(bestFrames);

      updateStatus(`Ricevuti ${bestFrames.length} migliori frame dal server`);

      // Al termine dell'analisi, forza sync canvas + info box con il vero miglior frame
      if (isFinalResult && bestFrames.length > 0 && bestFrames[0].image_data) {
        _syncCanvasFrame(bestFrames[0], 0, true);
        showToast(`✅ Analisi completata − Score migliore: ${newBestScore.toFixed(1)}`, 'success');
      }
    }

  } catch (error) {
    console.error('Errore gestione results_ready:', error);
  }
}

function handleFinalResults(data) {
  try {
    updateStatus('Analisi completata - Risultati finali disponibili');
    showToast(`Analisi completata: ${data.frames_count || 0} frame elaborati`, 'success');

    // Processa i risultati finali dal server 8765
    if (data.success && data.frames && data.frames.length > 0) {
      // ✅ Usa funzione centralizzata per trasformare i dati
      const debugFrames = transformWebSocketFrames(data);

      // Aggiorna tabella debug
      updateDebugTable(debugFrames);

      // Mostra il miglior frame nel canvas con info box aggiornato
      if (debugFrames.length > 0 && debugFrames[0].image_data) {
        _syncCanvasFrame(debugFrames[0], 0, true);
      }

      // Salva i frame localmente nella cartella best_frontal_frames
      saveBestFramesLocally(debugFrames);
    }

  } catch (error) {
    console.error('Errore gestione risultati finali:', error);
  }
}

async function saveBestFramesLocally(frames) {
  try {
    // Nota: il salvataggio locale avviene automaticamente nel server WebSocket 8765
    // Qui possiamo fare una richiesta per verificare che i file siano stati salvati
    console.log(`📁 ${frames.length} frame dovrebbero essere salvati in best_frontal_frames/`);
  } catch (error) {
    console.error('Errore salvataggio frame:', error);
  }
}

// === GESTIONE STRUMENTI CANVAS ===

function setTool(tool) {
  console.log('🔧 setTool chiamato:', tool);

  // Gestione speciale per modalità MISURA
  if (tool === 'measure') {
    if (typeof window.toggleMeasureMode === 'function') {
      window.toggleMeasureMode();
    } else {
      console.warn('⚠️ toggleMeasureMode non disponibile');
    }
    return;
  }

  // Per tutti gli altri tool, usa il nuovo sistema modalità
  if (typeof window.setCanvasMode === 'function') {
    window.setCanvasMode(tool);
  } else {
    // Fallback per compatibilità
    currentTool = tool;

    // Aggiorna pulsanti toolbar
    document.querySelectorAll('.tool-btn').forEach(btn => {
      btn.classList.remove('active');
    });

    const activeBtn = document.querySelector(`[data-tool="${tool}"]`);
    if (activeBtn) {
      activeBtn.classList.add('active');
    }

    // Aggiorna cursore
    updateCanvasCursor(tool);
    updateModeBadge(tool);
  }

  console.log('✅ Strumento selezionato:', tool);
}

// === ROTAZIONE IMMAGINE ===

function rotateImageClockwise() {
  /**
   * Ruota l'immagine di 1 grado in senso orario
   */
  if (!currentImage) {
    console.warn('⚠️ Nessuna immagine da ruotare');
    return;
  }

  const currentAngle = currentImage.angle || 0;
  const newAngle = currentAngle + 1;

  currentImage.rotate(newAngle);
  fabricCanvas.renderAll();

  // Sincronizza TUTTI gli overlay
  setTimeout(() => {
    // Ridisegna landmarks se visibili
    if (window.originalLandmarks && window.originalLandmarks.length > 0 && typeof window.redrawLandmarks === 'function') {
      window.redrawLandmarks();
    }

    // Sincronizza green dots overlay
    if (window.currentGreenDotsOverlay && typeof syncGreenDotsOverlayWithViewport === 'function') {
      syncGreenDotsOverlayWithViewport();
    }

    // Ridisegna misurazioni
    if (typeof redrawAllMeasurementOverlays === 'function') {
      redrawAllMeasurementOverlays();
    }

    // Ridisegna asse di simmetria se presente
    if (window.symmetryAxisVisible && typeof drawSymmetryAxis === 'function') {
      drawSymmetryAxis();
    }

    // Ridisegna overlay rotazione occhi se presente
    if (window.eyeRotationOverlayActive && typeof window.redrawEyeRotationOverlay === 'function') {
      window.redrawEyeRotationOverlay();
    }

    // Ridisegna overlay aree sopracciglia se presente
    if (typeof window.redrawEyebrowAreasOverlay === 'function') {
      window.redrawEyebrowAreasOverlay();
    }

    // Ridisegna overlay setto nasale se presente
    if (window.nosalWingOverlayActive && typeof window.redrawNosalWingOverlay === 'function') {
      window.redrawNosalWingOverlay();
    }

    // Ridisegna linee perpendicolari
    if (typeof redrawPerpendicularLines === 'function') {
      redrawPerpendicularLines();
    }

    // Ridisegna coppie di linee verticali
    if (typeof redrawCoupleLines === 'function') {
      redrawCoupleLines();
    }

    // Ridisegna highlight coppia punti se attivo
    if (window.highlightedPair && typeof clearPointPairHighlight === 'function' && typeof drawPointPairHighlight === 'function') {
      clearPointPairHighlight();
      drawPointPairHighlight(window.highlightedPair);
    }
  }, 50);

  console.log(`↻ Immagine ruotata: ${currentAngle}° → ${newAngle}°`);
}

function rotateImageCounterClockwise() {
  /**
   * Ruota l'immagine di 1 grado in senso antiorario
   */
  if (!currentImage) {
    console.warn('⚠️ Nessuna immagine da ruotare');
    return;
  }

  const currentAngle = currentImage.angle || 0;
  const newAngle = currentAngle - 1;

  currentImage.rotate(newAngle);
  fabricCanvas.renderAll();

  // Sincronizza TUTTI gli overlay
  setTimeout(() => {
    // Ridisegna landmarks se visibili
    if (window.originalLandmarks && window.originalLandmarks.length > 0 && typeof window.redrawLandmarks === 'function') {
      window.redrawLandmarks();
    }

    // Sincronizza green dots overlay
    if (window.currentGreenDotsOverlay && typeof syncGreenDotsOverlayWithViewport === 'function') {
      syncGreenDotsOverlayWithViewport();
    }

    // Ridisegna misurazioni
    if (typeof redrawAllMeasurementOverlays === 'function') {
      redrawAllMeasurementOverlays();
    }

    // Ridisegna asse di simmetria se presente
    if (window.symmetryAxisVisible && typeof drawSymmetryAxis === 'function') {
      drawSymmetryAxis();
    }

    // Ridisegna overlay rotazione occhi se presente
    if (window.eyeRotationOverlayActive && typeof window.redrawEyeRotationOverlay === 'function') {
      window.redrawEyeRotationOverlay();
    }

    // Ridisegna overlay aree sopracciglia se presente
    if (typeof window.redrawEyebrowAreasOverlay === 'function') {
      window.redrawEyebrowAreasOverlay();
    }

    // Ridisegna overlay setto nasale se presente
    if (window.nosalWingOverlayActive && typeof window.redrawNosalWingOverlay === 'function') {
      window.redrawNosalWingOverlay();
    }

    // Ridisegna linee perpendicolari
    if (typeof redrawPerpendicularLines === 'function') {
      redrawPerpendicularLines();
    }

    // Ridisegna coppie di linee verticali
    if (typeof redrawCoupleLines === 'function') {
      redrawCoupleLines();
    }

    // Ridisegna highlight coppia punti se attivo
    if (window.highlightedPair && typeof clearPointPairHighlight === 'function' && typeof drawPointPairHighlight === 'function') {
      clearPointPairHighlight();
      drawPointPairHighlight(window.highlightedPair);
    }
  }, 50);

  console.log(`↺ Immagine ruotata: ${currentAngle}° → ${newAngle}°`);
}

function rotateImage90Clockwise() {
  /**
   * Ruota l'immagine di 90 gradi in senso orario
   */
  if (!currentImage) {
    console.warn('⚠️ Nessuna immagine da ruotare');
    return;
  }

  const currentAngle = currentImage.angle || 0;
  const newAngle = currentAngle + 90;

  currentImage.rotate(newAngle);
  fabricCanvas.renderAll();

  // Sincronizza TUTTI gli overlay
  setTimeout(() => {
    if (window.originalLandmarks && window.originalLandmarks.length > 0 && typeof window.redrawLandmarks === 'function') {
      window.redrawLandmarks();
    }
    if (window.currentGreenDotsOverlay && typeof syncGreenDotsOverlayWithViewport === 'function') {
      syncGreenDotsOverlayWithViewport();
    }
    if (typeof redrawAllMeasurementOverlays === 'function') {
      redrawAllMeasurementOverlays();
    }
    if (window.symmetryAxisVisible && typeof drawSymmetryAxis === 'function') {
      drawSymmetryAxis();
    }
    if (window.eyeRotationOverlayActive && typeof window.redrawEyeRotationOverlay === 'function') {
      window.redrawEyeRotationOverlay();
    }
    if (typeof window.redrawEyebrowAreasOverlay === 'function') {
      window.redrawEyebrowAreasOverlay();
    }
    if (window.nosalWingOverlayActive && typeof window.redrawNosalWingOverlay === 'function') {
      window.redrawNosalWingOverlay();
    }
    if (typeof redrawPerpendicularLines === 'function') {
      redrawPerpendicularLines();
    }
    if (typeof redrawCoupleLines === 'function') {
      redrawCoupleLines();
    }

    // Ridisegna highlight coppia punti se attivo
    if (window.highlightedPair && typeof clearPointPairHighlight === 'function' && typeof drawPointPairHighlight === 'function') {
      clearPointPairHighlight();
      drawPointPairHighlight(window.highlightedPair);
    }
  }, 50);

  console.log(`↻ Immagine ruotata 90°: ${currentAngle}° → ${newAngle}°`);
}

function rotateImage90CounterClockwise() {
  /**
   * Ruota l'immagine di 90 gradi in senso antiorario
   */
  if (!currentImage) {
    console.warn('⚠️ Nessuna immagine da ruotare');
    return;
  }

  const currentAngle = currentImage.angle || 0;
  const newAngle = currentAngle - 90;

  currentImage.rotate(newAngle);
  fabricCanvas.renderAll();

  // Sincronizza TUTTI gli overlay
  setTimeout(() => {
    if (window.originalLandmarks && window.originalLandmarks.length > 0 && typeof window.redrawLandmarks === 'function') {
      window.redrawLandmarks();
    }
    if (window.currentGreenDotsOverlay && typeof syncGreenDotsOverlayWithViewport === 'function') {
      syncGreenDotsOverlayWithViewport();
    }
    if (typeof redrawAllMeasurementOverlays === 'function') {
      redrawAllMeasurementOverlays();
    }
    if (window.symmetryAxisVisible && typeof drawSymmetryAxis === 'function') {
      drawSymmetryAxis();
    }
    if (window.eyeRotationOverlayActive && typeof window.redrawEyeRotationOverlay === 'function') {
      window.redrawEyeRotationOverlay();
    }
    if (typeof window.redrawEyebrowAreasOverlay === 'function') {
      window.redrawEyebrowAreasOverlay();
    }
    if (window.nosalWingOverlayActive && typeof window.redrawNosalWingOverlay === 'function') {
      window.redrawNosalWingOverlay();
    }
    if (typeof redrawPerpendicularLines === 'function') {
      redrawPerpendicularLines();
    }
    if (typeof redrawCoupleLines === 'function') {
      redrawCoupleLines();
    }

    // Ridisegna highlight coppia punti se attivo
    if (window.highlightedPair && typeof clearPointPairHighlight === 'function' && typeof drawPointPairHighlight === 'function') {
      clearPointPairHighlight();
      drawPointPairHighlight(window.highlightedPair);
    }
  }, 50);

  console.log(`↺ Immagine ruotata -90°: ${currentAngle}° → ${newAngle}°`);
}

// Rendi le funzioni globali
window.rotateImageClockwise = rotateImageClockwise;
window.rotateImageCounterClockwise = rotateImageCounterClockwise;
window.rotateImage90Clockwise = rotateImage90Clockwise;
window.rotateImage90CounterClockwise = rotateImage90CounterClockwise;

// === ROTAZIONE AUTOMATICA ASSE VERTICALE ===

async function autoRotateToVerticalAxis() {
  /**
   * Ruota automaticamente l'immagine in modo che l'asse di simmetria
   * risulti verticale (perpendicolare allo schermo).
   *
   * Strategia:
   *  1. Usa currentLandmarks (in coordinate pixel immagine originale).
   *     Se mancano, chiama autoDetectLandmarksOnImageChange() una sola volta.
   *  2. Calcola axisAngleInImage = atan2(dx, dy) fra i landmark 9 (glabella) e
   *     164 (philtrum) nello spazio immagine originale — NON trasformati.
   *     Viso dritto → dx≈0, dy>0 → 0°. Viso inclinato CW di α° → +α°.
   *  3. Applica newAngle = -axisAngleInImage (valore ASSOLUTO, indipendente
   *     dall'angolo corrente → idempotente: premere più volte = stesso risultato).
   *  Nessuna chiamata API aggiuntiva se i landmark sono già stati rilevati.
   */
  if (!currentImage || !fabricCanvas) {
    showToast('Nessuna immagine caricata', 'warning');
    return;
  }

  // ── Passo 1: ottieni landmark (solo se mancano) ───────────────────────────
  if (!currentLandmarks || currentLandmarks.length === 0) {
    showToast('Rilevamento landmarks in corso...', 'info');
    const ok = await autoDetectLandmarksOnImageChange();
    if (!ok || !currentLandmarks || currentLandmarks.length === 0) {
      showToast('Impossibile rilevare il viso nell\'immagine', 'error');
      return;
    }
  }

  if (!currentLandmarks[9] || !currentLandmarks[164]) {
    showToast('Landmark mediofacciali non trovati (punti 9 e 164)', 'warning');
    return;
  }

  // ── Passo 2: calcola l'angolo dell'asse nello spazio IMMAGINE ORIGINALE ────
  // currentLandmarks sono SEMPRE in coordinate pixel dell'immagine originale
  // (non del canvas). Usiamo questi coord diretti, senza transformLandmarkCoordinate,
  // per evitare doppia applicazione della rotazione canvas.
  //
  // atan2(dx, dy): angolo rispetto alla verticale verso il basso (+Y immagine).
  // Per un viso dritto: philtrum(164) è sotto la glabella(9) → dx≈0, dy>0 → 0°.
  // Se il viso è inclinato CW di α gradi: axisAngleInImage = +α.
  // Nota sulla convenzione di segno in questo sistema:
  // Con Fabric.js in coordinate schermo (Y verso il basso) la relazione empirica
  // fra l'angolo del canvas (fabricAngle) e la direzione visiva dell'asse è:
  //   screen_axis_angle = axisAngleInImage - fabricAngle
  // Per ottenere screen_axis_angle = 0 (verticale): fabricAngle = axisAngleInImage.
  // Formula ASSOLUTA e IDEMPOTENTE: indipendente da prevAngle.
  const dx = currentLandmarks[164].x - currentLandmarks[9].x;
  const dy = currentLandmarks[164].y - currentLandmarks[9].y;
  const axisAngleInImage = Math.atan2(dx, dy) * (180 / Math.PI);

  // ── Passo 3: applica correzione angolare (formula assoluta) ──────────────
  const imgRef = currentImage;
  const prevAngle = imgRef.angle || 0;
  const newAngle = axisAngleInImage; // NON negato: vedi nota convenzione segno sopra

  console.log(`🎯 autoRotateToVerticalAxis: axisAngleInImage=${axisAngleInImage.toFixed(2)}° prevAngle=${prevAngle.toFixed(2)}° → newAngle=${newAngle.toFixed(2)}°`);

  if (!fabricCanvas.getObjects().includes(imgRef)) {
    showToast('Immagine non più disponibile nel canvas', 'warning');
    return;
  }

  try {
    imgRef.rotate(newAngle);
    fabricCanvas.renderAll();
  } catch (e) {
    console.warn('⚠️ autoRotateToVerticalAxis: renderAll exceptioned', e.message);
    requestAnimationFrame(() => {
      try { fabricCanvas.renderAll(); } catch (_) { /* patch fabric in canvas.js */ }
    });
  }

  // ── Passo 4: attiva pulsante asse + ridisegna overlay ─────────────────────
  const axisBtn = document.getElementById('axis-btn');
  if (axisBtn && !axisBtn.classList.contains('active')) {
    axisBtn.classList.add('active');
    window.symmetryAxisVisible = true;
  }

  setTimeout(() => {
    if (window.symmetryAxisVisible && typeof drawSymmetryAxis === 'function') {
      drawSymmetryAxis({ autoDetect: false });
    }
    if (window.eyeRotationOverlayActive && typeof window.redrawEyeRotationOverlay === 'function') {
      window.redrawEyeRotationOverlay();
    }
    if (typeof window.redrawEyebrowAreasOverlay === 'function') {
      window.redrawEyebrowAreasOverlay();
    }
    if (window.originalLandmarks && window.originalLandmarks.length > 0 && typeof window.redrawLandmarks === 'function') {
      window.redrawLandmarks();
    }
    if (window.currentGreenDotsOverlay && typeof syncGreenDotsOverlayWithViewport === 'function') {
      syncGreenDotsOverlayWithViewport();
    }
    if (typeof redrawAllMeasurementOverlays === 'function') {
      redrawAllMeasurementOverlays();
    }
    if (typeof redrawPerpendicularLines === 'function') {
      redrawPerpendicularLines();
    }
    if (typeof redrawCoupleLines === 'function') {
      redrawCoupleLines();
    }
  }, 80);

  showToast(`Asse allineato (${newAngle.toFixed(1)}°)`, 'success');
  console.log(`🎯 Auto-rotazione asse verticale: ${prevAngle.toFixed(1)}° → ${newAngle.toFixed(1)}° (axisAngleInImage: ${axisAngleInImage.toFixed(2)}°)`);
}

window.autoRotateToVerticalAxis = autoRotateToVerticalAxis;

function updateCanvasCursor(tool) {
  const canvas = document.getElementById('main-canvas');

  const cursors = {
    'selection': 'default',
    'zoom-in': 'zoom-in',
    'zoom-out': 'zoom-out',
    'pan': 'move',
    'line': 'crosshair',
    'rectangle': 'crosshair',
    'circle': 'crosshair',
    'measure': 'crosshair'
  };

  canvas.style.cursor = cursors[tool] || 'default';
}

function clearCanvas() {
  const canvas = document.getElementById('main-canvas');
  const ctx = canvas.getContext('2d');

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (currentImage) {
    displayImageOnCanvas(currentImage);
  }

  updateStatus('Canvas pulito');
}

function fitToWindow() {
  if (!fabricCanvas) {
    updateStatus('Canvas non inizializzato');
    return;
  }

  // Prima ridimensiona il canvas per utilizzare tutto lo spazio
  forceCanvasResize();

  // Poi ottimizza l'immagine se presente
  if (currentImage && typeof optimizeCurrentImageDisplay === 'function') {
    setTimeout(() => {
      optimizeCurrentImageDisplay();
      updateStatus('Immagine adattata per utilizzare tutto lo spazio disponibile');
    }, 100);
  } else {
    updateStatus('Canvas ridimensionato per utilizzo ottimale dello spazio');
  }
}

// === EVENT HANDLERS CANVAS ===

let isDrawing = false;
let startX = 0;
let startY = 0;

function onCanvasMouseDown(e) {
  // Non attivare il disegno se siamo in modalità misurazione o selezione landmarks
  if (window.measurementMode || window.landmarkSelectionMode) {
    return;
  }

  isDrawing = true;
  const rect = e.target.getBoundingClientRect();
  startX = e.clientX - rect.left;
  startY = e.clientY - rect.top;

  console.log(`Mouse down: (${startX}, ${startY}) - Tool: ${currentTool}`);
}

function onCanvasMouseMove(e) {
  const rect = e.target.getBoundingClientRect();
  const x = Math.round(e.clientX - rect.left);
  const y = Math.round(e.clientY - rect.top);

  // Aggiorna info cursore
  updateCursorInfo(x, y);

  // Non disegnare se siamo in modalità misurazione o selezione landmarks
  if (isDrawing && !window.measurementMode && !window.landmarkSelectionMode) {
    // Disegna in base allo strumento selezionato
    drawWithCurrentTool(startX, startY, x, y);
  }
}

function onCanvasMouseUp(e) {
  // Non finalizzare il disegno se siamo in modalità misurazione o selezione landmarks
  if (window.measurementMode || window.landmarkSelectionMode) {
    isDrawing = false;
    return;
  }

  isDrawing = false;
  const rect = e.target.getBoundingClientRect();
  const endX = e.clientX - rect.left;
  const endY = e.clientY - rect.top;

  console.log(`Mouse up: (${endX}, ${endY})`);

  // Finalizza disegno
  finalizeDrawing(startX, startY, endX, endY);
}

function onCanvasWheel(e) {
  e.preventDefault();

  if (currentTool === 'zoom-in' || currentTool === 'zoom-out') {
    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
    zoomCanvas(zoomFactor, e.offsetX, e.offsetY);
  }
}

function onCanvasRightClick(e) {
  e.preventDefault();
  showContextMenu(e.clientX, e.clientY);
}

function drawWithCurrentTool(startX, startY, endX, endY) {
  const canvas = document.getElementById('main-canvas');
  const ctx = canvas.getContext('2d');

  // Ripristina immagine base
  if (currentImage) {
    displayImageOnCanvas(currentImage);
  }

  // Disegna overlay temporaneo
  ctx.save();
  ctx.strokeStyle = '#007bff';
  ctx.lineWidth = 2;

  switch (currentTool) {
    case 'line':
      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.lineTo(endX, endY);
      ctx.stroke();
      break;

    case 'rectangle':
      const width = endX - startX;
      const height = endY - startY;
      ctx.strokeRect(startX, startY, width, height);
      break;

    case 'circle':
      const radius = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
      ctx.beginPath();
      ctx.arc(startX, startY, radius, 0, 2 * Math.PI);
      ctx.stroke();
      break;
  }

  ctx.restore();
}

function finalizeDrawing(startX, startY, endX, endY) {
  // Salva il disegno permanentemente
  console.log(`Disegno finalizzato: ${currentTool} da (${startX},${startY}) a (${endX},${endY})`);

  // TODO: Salvare in una lista di elementi disegnati
}

function zoomCanvas(factor, centerX, centerY) {
  // TODO: Implementare zoom
  console.log(`Zoom: ${factor} al punto (${centerX}, ${centerY})`);
}

// === GESTIONE EVENTI TOUCH PER MOBILE ===
let lastTouchDistance = 0;
let touchStartTime = 0;

function onCanvasTouchStart(e) {
  e.preventDefault();

  // Non attivare il disegno se siamo in modalità misurazione o selezione landmarks
  if (window.measurementMode || window.landmarkSelectionMode) {
    return;
  }

  touchStartTime = Date.now();

  // Pinch to zoom con 2 dita
  if (e.touches.length === 2) {
    const touch1 = e.touches[0];
    const touch2 = e.touches[1];
    lastTouchDistance = Math.hypot(
      touch2.clientX - touch1.clientX,
      touch2.clientY - touch1.clientY
    );
    return;
  }

  // Pan/draw con 1 dito
  if (e.touches.length === 1) {
    isDrawing = true;
    const touch = e.touches[0];
    const rect = e.target.getBoundingClientRect();
    startX = touch.clientX - rect.left;
    startY = touch.clientY - rect.top;
    console.log(`Touch start: (${startX}, ${startY})`);
  }
}

function onCanvasTouchMove(e) {
  e.preventDefault();

  // Pinch to zoom con 2 dita
  if (e.touches.length === 2) {
    const touch1 = e.touches[0];
    const touch2 = e.touches[1];
    const currentDistance = Math.hypot(
      touch2.clientX - touch1.clientX,
      touch2.clientY - touch1.clientY
    );

    if (lastTouchDistance > 0) {
      const zoomFactor = currentDistance / lastTouchDistance;
      const centerX = (touch1.clientX + touch2.clientX) / 2;
      const centerY = (touch1.clientY + touch2.clientY) / 2;
      const rect = e.target.getBoundingClientRect();
      zoomCanvas(zoomFactor, centerX - rect.left, centerY - rect.top);
    }

    lastTouchDistance = currentDistance;
    return;
  }

  // Pan/draw con 1 dito
  if (e.touches.length === 1 && isDrawing) {
    const touch = e.touches[0];
    const rect = e.target.getBoundingClientRect();
    const x = Math.round(touch.clientX - rect.left);
    const y = Math.round(touch.clientY - rect.top);

    updateCursorInfo(x, y);

    if (!window.measurementMode && !window.landmarkSelectionMode) {
      drawWithCurrentTool(startX, startY, x, y);
    }
  }
}

function onCanvasTouchEnd(e) {
  e.preventDefault();

  // Reset pinch zoom
  if (e.touches.length < 2) {
    lastTouchDistance = 0;
  }

  // Non finalizzare se siamo in modalità misurazione
  if (window.measurementMode || window.landmarkSelectionMode) {
    isDrawing = false;
    return;
  }

  // Finalizza disegno con 1 dito
  if (e.changedTouches.length === 1 && isDrawing) {
    const touch = e.changedTouches[0];
    const rect = e.target.getBoundingClientRect();
    const endX = touch.clientX - rect.left;
    const endY = touch.clientY - rect.top;

    // Tap rapido = click
    const touchDuration = Date.now() - touchStartTime;
    if (touchDuration < 200 && Math.abs(endX - startX) < 10 && Math.abs(endY - startY) < 10) {
      console.log(`Touch tap: (${endX}, ${endY})`);
    } else {
      console.log(`Touch end: (${endX}, ${endY})`);
      finalizeDrawing(startX, startY, endX, endY);
    }
  }

  isDrawing = false;
}

// === GESTIONE RILEVAMENTI ===

async function detectLandmarks() {
  /**
   * === SISTEMA SEMPLIFICATO ===
   * I landmarks sono già rilevati automaticamente.
   * Questo pulsante serve solo per mostrarli/nasconderli.
   */
  if (!currentImage) {
    showToast('Carica prima un\'immagine', 'warning');
    return;
  }

  // Se non ci sono landmarks, prova a rilevare
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark disponibile - Tentativo rilevamento...');
    const success = await autoDetectLandmarksOnImageChange();
    if (!success) {
      showToast('Errore nel rilevamento landmarks', 'error');
      return;
    }
  }

  // Mostra/nascondi landmarks già disponibili
  try {
    const landmarkObjects = fabricCanvas.getObjects().filter(obj =>
      obj.isLandmark || (obj.fill && obj.fill === 'red' && obj.radius === 2)
    );

    if (landmarkObjects.length > 0) {
      // Nascondi landmarks
      landmarkObjects.forEach(obj => fabricCanvas.remove(obj));
      fabricCanvas.renderAll();
      updateStatus(`👁️ Landmarks nascosti (${currentLandmarks.length} disponibili)`);
      showToast('Landmarks nascosti', 'info');
    } else {
      // Mostra landmarks
      displayLandmarksOnCanvas();
      updateStatus(`✅ Landmarks visualizzati: ${currentLandmarks.length}`);
      showToast(`${currentLandmarks.length} landmarks visualizzati`, 'success');
    }

  } catch (error) {
    console.error('Errore gestione landmarks:', error);
    showToast('Errore nella gestione landmarks', 'error');
  }
}

function displayLandmarksOnCanvas() {
  /**
   * Mostra i landmarks già rilevati sul canvas
   * DELEGA a canvas.js per la trasformazione corretta
   */
  if (!currentLandmarks || currentLandmarks.length === 0 || !fabricCanvas) {
    console.warn('⚠️ Nessun landmark da visualizzare');
    return;
  }

  console.log(`🎯 Visualizzazione ${currentLandmarks.length} landmarks sul canvas - DELEGA a canvas.js`);

  // USA la funzione da canvas.js che applica correttamente imageOffset e imageScale
  if (typeof window.drawMediaPipeLandmarks === 'function') {
    window.drawMediaPipeLandmarks(currentLandmarks);
  } else {
    console.error('❌ drawMediaPipeLandmarks non disponibile da canvas.js');
  }
}

function updateCanvasDisplay() {
  /**
   * Aggiorna la visualizzazione del canvas con overlay condizionali.
   * Replica il comportamento di canvas_app.py:update_canvas_display()
   */
  console.log('🔄 updateCanvasDisplay chiamata');
  console.log('📊 Stato:', {
    hasCanvas: !!fabricCanvas,
    hasLandmarks: !!currentLandmarks,
    landmarksCount: currentLandmarks?.length || 0
  });

  if (!fabricCanvas) {
    console.error('❌ fabricCanvas non disponibile');
    return;
  }

  // PRIMA pulisci tutti gli overlay esistenti
  clearAllOverlays();

  // POI ridisegna SOLO gli overlay abilitati nell'interfaccia

  // Disegna landmarks SOLO se abilitati nell'interfaccia
  const landmarksBtn = document.getElementById('landmarks-btn');
  const landmarksActive = landmarksBtn && landmarksBtn.classList.contains('active');
  console.log('🎯 Landmarks:', {
    button: !!landmarksBtn,
    active: landmarksActive,
    hasData: !!currentLandmarks,
    landmarksLength: currentLandmarks?.length || 0
  });

  if (landmarksActive && currentLandmarks && currentLandmarks.length > 0) {
    console.log('🎯 Disegno landmarks MediaPipe - abilitati nell\'interfaccia');
    if (typeof window.drawMediaPipeLandmarks === 'function') {
      window.drawMediaPipeLandmarks(currentLandmarks);
    } else {
      console.error('❌ Funzione drawMediaPipeLandmarks non disponibile');
    }
  }

  // Disegna asse di simmetria SOLO se abilitato nell'interfaccia
  const axisBtn = document.getElementById('axis-btn');
  const axisActive = axisBtn && axisBtn.classList.contains('active');
  console.log('📏 Asse:', { button: !!axisBtn, active: axisActive, hasLandmarks: !!currentLandmarks });

  if (axisActive && currentLandmarks) {
    console.log('🎯 Disegno asse di simmetria - abilitato nell\'interfaccia');
    drawSymmetryAxis();
  }

  // Disegna green dots SOLO se abilitati nell'interfaccia
  const greenDotsBtn = document.getElementById('green-dots-btn');
  const greenDotsActive = greenDotsBtn && greenDotsBtn.classList.contains('active');
  console.log('🟢 Green dots:', { button: !!greenDotsBtn, active: greenDotsActive, detected: !!window.greenDotsDetected });

  if (greenDotsActive && window.greenDotsDetected) {
    console.log('🎯 Disegno green dots - abilitati nell\'interfaccia');
    drawGreenDots();
  }

  // 🔧 ASSICURA che le sezioni sidebar rimangano sempre visibili
  ensureSidebarSectionsVisible();
}

function transformLandmarkCoordinate(landmark) {
  /**
   * Trasforma coordinate landmark usando il centro CORRETTO dell'immagine di Fabric.js
   */
  if (!currentImage || !fabricCanvas) {
    return landmark;
  }

  // Dimensioni originali
  const element = currentImage.getElement();
  const originalWidth = element.naturalWidth || element.width;
  const originalHeight = element.naturalHeight || element.height;

  // Normalizza in 0-1
  const normX = landmark.x / originalWidth;
  const normY = landmark.y / originalHeight;

  // Dimensioni scalate
  const scaledW = currentImage.width * currentImage.scaleX;
  const scaledH = currentImage.height * currentImage.scaleY;

  // Coordinate relative al centro (prima di ruotare)
  let relX = (normX - 0.5) * scaledW;
  let relY = (normY - 0.5) * scaledH;

  // Applica rotazione
  const angleRad = (currentImage.angle || 0) * Math.PI / 180;
  if (angleRad !== 0) {
    const cos = Math.cos(angleRad);
    const sin = Math.sin(angleRad);
    const rotX = relX * cos - relY * sin;
    const rotY = relX * sin + relY * cos;
    relX = rotX;
    relY = rotY;
  }

  // Ottieni il centro EFFETTIVO dell'immagine (gestisce originX/originY)
  const center = currentImage.getCenterPoint();

  return {
    x: center.x + relX,
    y: center.y + relY,
    z: landmark.z || 0,
    visibility: landmark.visibility || 1.0
  };
}

function recalculateImageTransformation() {
  /**
   * Ricalcola le informazioni di trasformazione immagine quando necessario
   */
  if (!currentImage || !fabricCanvas) {
    console.error('❌ Impossibile ricalcolare: immagine o canvas mancanti');
    return;
  }

  // Trova l'oggetto immagine nel canvas
  const fabricImages = fabricCanvas.getObjects().filter(obj => obj.type === 'image');
  if (fabricImages.length === 0) {
    console.error('❌ Nessuna immagine trovata nel canvas');
    return;
  }

  const fabricImage = fabricImages[0]; // Prendi la prima immagine

  // Calcola scala e offset dalla fabric image
  const scaleX = fabricImage.scaleX || 1;
  const scaleY = fabricImage.scaleY || 1;
  const scale = Math.min(scaleX, scaleY); // Usa la scala minore per uniformità

  const x = fabricImage.left || 0;
  const y = fabricImage.top || 0;

  window.imageScale = scale;
  window.imageOffset = { x, y };

  console.log('🔄 Trasformazione ricalcolata:', {
    scale: scale.toFixed(3),
    offset: `(${x.toFixed(1)}, ${y.toFixed(1)})`,
    fabricImage: {
      scaleX: scaleX.toFixed(3),
      scaleY: scaleY.toFixed(3),
      left: fabricImage.left,
      top: fabricImage.top,
      width: fabricImage.width,
      height: fabricImage.height
    },
    scaleDifference: {
      scaleXvsCalculated: (scaleX - scale).toFixed(4),
      scaleYvsCalculated: (scaleY - scale).toFixed(4)
    }
  });
}

// Rendi la funzione globalmente accessibile
window.transformLandmarkCoordinate = transformLandmarkCoordinate;

/**
 * Trasforma coordinate restituite dall'API green-dots in coordinate canvas.
 * A differenza di transformLandmarkCoordinate, gestisce correttamente il caso
 * in cui il rilevamento sia stato eseguito su un'immagine già ruotata:
 * le coordinate API sono nello spazio dell'immagine ruotata-al-detection-angle,
 * non nello spazio dell'immagine originale.
 *
 * @param {number} apiX  - Coordinata X nell'immagine inviata all'API (ruotata+resized)
 * @param {number} apiY  - Coordinata Y nell'immagine inviata all'API (ruotata+resized)
 * @returns {{x, y}}     - Coordinate nel canvas Fabric.js
 */
function transformGreenDotCoordinate(apiX, apiY) {
  if (!currentImage || !fabricCanvas) return { x: apiX, y: apiY };

  const natW = window.currentGreenDotsOverlayNaturalW;
  const natH = window.currentGreenDotsOverlayNaturalH;
  const scaleX = window.greenDotsOverlayScaleXAtDetection;
  const scaleY = window.greenDotsOverlayScaleYAtDetection;

  if (!natW || !natH || !scaleX || !scaleY) {
    // Fallback: usa trasformazione standard (valida solo se detection a angolo=0)
    return transformLandmarkCoordinate({ x: apiX, y: apiY });
  }

  // Converti da spazio API (0..natW × 0..natH) a spazio centrato sull'overlay
  const cx = apiX - natW / 2;
  const cy = apiY - natH / 2;

  // Applica la scala dell'overlay
  let relX = cx * scaleX;
  let relY = cy * scaleY;

  // Applica la rotazione aggiuntiva avvenuta DOPO il detection
  const detectionAngle = window.greenDotsDetectionAngle || 0;
  const additionalAngle = (currentImage.angle || 0) - detectionAngle;
  if (additionalAngle !== 0) {
    const rad = additionalAngle * Math.PI / 180;
    const cos = Math.cos(rad);
    const sin = Math.sin(rad);
    const rx = relX * cos - relY * sin;
    const ry = relX * sin + relY * cos;
    relX = rx;
    relY = ry;
  }

  const center = currentImage.getCenterPoint();
  return {
    x: center.x + relX,
    y: center.y + relY
  };
}
window.transformGreenDotCoordinate = transformGreenDotCoordinate;

function clearAllOverlays() {
  /**
   * Pulisce tutti gli overlay dal canvas (landmarks, assi, green dots).
   * Equivale alla pulizia che fa canvas_app.py prima di ridisegnare.
   */
  if (!fabricCanvas) return;

  const overlays = fabricCanvas.getObjects().filter(obj =>
    obj.isLandmark || obj.isSymmetryAxis || obj.isGreenDot || obj.isGreenDotsOverlay || obj.isGreenDotsGroup || obj.isDebugPoint
  );
  overlays.forEach(overlay => fabricCanvas.remove(overlay));
  fabricCanvas.renderAll();
}

function clearLandmarks() {
  /**
   * Pulisce SOLO i landmarks dal canvas, senza toccare asse o green dots
   */
  if (fabricCanvas) {
    // Rimuovi SOLO gli oggetti landmark dal canvas
    const landmarks = fabricCanvas.getObjects().filter(obj => obj.isLandmark);
    landmarks.forEach(landmark => fabricCanvas.remove(landmark));
    fabricCanvas.renderAll();
  }
}

function drawSymmetryAxis({ autoDetect = true } = {}) {
  /**
   * === SISTEMA SEMPLIFICATO ===
   * Disegna l'asse di simmetria usando landmarks già disponibili
   * Landmarks MediaPipe: Glabella (9) e Philtrum (164)
   * @param {boolean} autoDetect - Se true, tenta auto-rilevamento landmarks se mancano.
   *   Passare false per evitare ricorsione quando chiamata da callback di auto-rilevamento.
   */
  console.log('📏 drawSymmetryAxis - Sistema Semplificato');

  // PRIMA rimuovi l'asse precedente (se esiste)
  clearSymmetryAxis();

  // Se non ci sono landmarks, prova auto-rilevamento (una sola volta)
  if (!currentLandmarks || currentLandmarks.length === 0) {
    if (autoDetect) {
      console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
      showToast('Rilevamento landmarks in corso...', 'info');
      autoDetectLandmarksOnImageChange().then(success => {
        if (success) {
          drawSymmetryAxis({ autoDetect: false }); // Evita ricorsione infinita
        } else {
          showToast('Impossibile rilevare landmarks per l\'asse', 'error');
        }
      });
    } else {
      console.warn('⚠️ drawSymmetryAxis: landmarks non disponibili dopo auto-rilevamento');
      showToast('Impossibile rilevare landmarks per l\'asse', 'error');
    }
    return;
  }

  // Verifica landmarks necessari
  if (currentLandmarks.length <= 164 || !currentLandmarks[9] || !currentLandmarks[164]) {
    showToast('Landmarks insufficienti per l\'asse di simmetria', 'warning');
    console.error('❌ Landmarks mancanti:', {
      total: currentLandmarks.length,
      landmark9: !!currentLandmarks[9],
      landmark164: !!currentLandmarks[164]
    });
    return;
  }

  console.log('🎯 Disegno asse con landmarks disponibili: 9 e 164');

  // Landmark MediaPipe esatti come nel face_detector.py
  const glabella = currentLandmarks[9];   // Punto superiore: glabella (tra le sopracciglia)
  const philtrum = currentLandmarks[164]; // Punto inferiore: philtrum (area naso-labbro)

  // Trasforma le coordinate per la scala e posizione dell'immagine
  const transformedGlabella = transformLandmarkCoordinate(glabella);
  const transformedPhiltrum = transformLandmarkCoordinate(philtrum);

  console.log('📍 Landmarks originali:', {
    glabella: { x: glabella.x.toFixed(1), y: glabella.y.toFixed(1) },
    philtrum: { x: philtrum.x.toFixed(1), y: philtrum.y.toFixed(1) }
  });

  console.log('📍 Landmarks trasformati:', {
    glabella: { x: transformedGlabella.x.toFixed(1), y: transformedGlabella.y.toFixed(1) },
    philtrum: { x: transformedPhiltrum.x.toFixed(1), y: transformedPhiltrum.y.toFixed(1) }
  });

  // DEBUG: Cerchi di debug rimossi per evitare grafiche indesiderate
  // const debugGlabella = new fabric.Circle({
  //   left: transformedGlabella.x - 3,
  //   top: transformedGlabella.y - 3,
  //   radius: 3,
  //   fill: '#00FF00',
  //   stroke: '#000000',
  //   strokeWidth: 1,
  //   selectable: false,
  //   evented: false,
  //   isDebugPoint: true
  // });

  // const debugPhiltrum = new fabric.Circle({
  //   left: transformedPhiltrum.x - 3,
  //   top: transformedPhiltrum.y - 3,
  //   radius: 3,
  //   fill: '#FFFF00',
  //   stroke: '#000000',
  //   strokeWidth: 1,
  //   selectable: false,
  //   evented: false,
  //   isDebugPoint: true
  // });

  // fabricCanvas.add(debugGlabella);
  // fabricCanvas.add(debugPhiltrum);

  if (!glabella || !philtrum) {
    console.warn('⚠️ Landmarks 9 o 164 non disponibili per l\'asse');
    return;
  }

  // Calcola la direzione della linea usando le coordinate trasformate (già ruotate)
  const dx = transformedPhiltrum.x - transformedGlabella.x;
  const dy = transformedPhiltrum.y - transformedGlabella.y;
  const length = Math.sqrt(dx * dx + dy * dy);

  // Normalizza la direzione
  const dirX = dx / length;
  const dirY = dy / length;

  // Estendi la linea in entrambe le direzioni per coprire tutto il canvas
  // Usa una lunghezza grande abbastanza da coprire qualsiasi rotazione
  const canvasWidth = fabricCanvas.getWidth();
  const canvasHeight = fabricCanvas.getHeight();
  const maxExtension = Math.sqrt(canvasWidth * canvasWidth + canvasHeight * canvasHeight);

  // Punto superiore: estendi dalla glabella nella direzione opposta
  const topX = transformedGlabella.x - dirX * maxExtension;
  const topY = transformedGlabella.y - dirY * maxExtension;

  // Punto inferiore: estendi dal philtrum nella direzione principale
  const bottomX = transformedPhiltrum.x + dirX * maxExtension;
  const bottomY = transformedPhiltrum.y + dirY * maxExtension;

  // Crea linea asse con stile dell'app desktop
  const axisLine = new fabric.Line([topX, topY, bottomX, bottomY], {
    stroke: '#FF0000',      // Rosso come nell'app desktop
    strokeWidth: 2,
    strokeDashArray: [10, 5], // Linea tratteggiata
    selectable: false,
    evented: false,
    isSymmetryAxis: true
  });

  fabricCanvas.add(axisLine);
  fabricCanvas.renderAll();

  console.log(`📏 Asse di simmetria disegnato da (${topX.toFixed(1)}, ${topY}) a (${bottomX.toFixed(1)}, ${bottomY})`);
}

function clearSymmetryAxis() {
  if (fabricCanvas) {
    const axes = fabricCanvas.getObjects().filter(obj => obj.isSymmetryAxis || obj.isDebugPoint);
    axes.forEach(axis => fabricCanvas.remove(axis));
    fabricCanvas.renderAll();
    if (window.DEBUG_MODE) {
      console.log('🧹 Asse di simmetria rimosso');
    }
  }
}

// Esponi funzioni asse di simmetria globalmente
window.drawSymmetryAxis = drawSymmetryAxis;
window.clearSymmetryAxis = clearSymmetryAxis;

// === GESTIONE LINEE PERPENDICOLARI ALL'ASSE ===

let isRedrawingLines = false; // Flag per evitare loop infiniti

function addPerpendicularLine(normalizedPosition) {
  /**
   * Aggiunge una linea perpendicolare all'asse di simmetria
   * normalizedPosition: posizione lungo l'asse (0=glabella, 1=philtrum, può essere <0 o >1)
   */
  perpendicularLines.push(normalizedPosition);
  window.perpendicularLines = perpendicularLines;

  // Crea SOLO la nuova linea, senza ridisegnare tutte le altre
  createSinglePerpendicularLine(normalizedPosition);

  console.log(`➕ Linea perpendicolare aggiunta: ${normalizedPosition.toFixed(3)}`);
}

function createSinglePerpendicularLine(normalizedPos) {
  /**
   * Crea una singola linea perpendicolare senza toccare le altre
   */
  if (!currentLandmarks || currentLandmarks.length === 0) return;
  if (!currentLandmarks[9] || !currentLandmarks[164]) return;

  const glabella = currentLandmarks[9];
  const philtrum = currentLandmarks[164];

  const transformedGlabella = transformLandmarkCoordinate(glabella);
  const transformedPhiltrum = transformLandmarkCoordinate(philtrum);

  // Direzione dell'asse
  const dx = transformedPhiltrum.x - transformedGlabella.x;
  const dy = transformedPhiltrum.y - transformedGlabella.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  const axisX = dx / length;
  const axisY = dy / length;

  // Direzione perpendicolare (ruotata di 90°)
  const perpX = -axisY;
  const perpY = axisX;

  // Lunghezza della linea perpendicolare (copre tutto il canvas)
  const canvasWidth = fabricCanvas.getWidth();
  const canvasHeight = fabricCanvas.getHeight();
  const lineLength = Math.sqrt(canvasWidth * canvasWidth + canvasHeight * canvasHeight) * 2;

  // Punto sull'asse
  const pointX = transformedGlabella.x + axisX * normalizedPos * length;
  const pointY = transformedGlabella.y + axisY * normalizedPos * length;

  // Punti della linea perpendicolare
  const x1 = pointX - perpX * lineLength / 2;
  const y1 = pointY - perpY * lineLength / 2;
  const x2 = pointX + perpX * lineLength / 2;
  const y2 = pointY + perpY * lineLength / 2;

  console.log(`📏 Creazione linea: normalizedPos=${normalizedPos.toFixed(3)}, center=(${pointX.toFixed(1)}, ${pointY.toFixed(1)})`);

  const line = new fabric.Line([x1, y1, x2, y2], {
    stroke: '#00FFFF',
    strokeWidth: 2,
    selectable: true,
    evented: true,
    lockRotation: true,
    lockScalingX: true,
    lockScalingY: true,
    hasControls: false,
    hasBorders: false,
    isPerpendicularLine: true,
    normalizedPosition: normalizedPos,
    hoverCursor: 'move',
    moveCursor: 'move',
    padding: 20  // Area touch generosa per selezione da mobile
  });

  fabricCanvas.add(line);
  console.log(`✅ Linea aggiunta al canvas - selectable: ${line.selectable}, evented: ${line.evented}`);

  // Assicurati che l'handler sia attivo
  setupPerpendicularLineHandlers();

  fabricCanvas.renderAll();
}

function clearPerpendicularLines() {
  /**
   * Rimuove tutte le linee perpendicolari dal canvas
   */
  if (fabricCanvas) {
    const lines = fabricCanvas.getObjects().filter(obj => obj.isPerpendicularLine);
    lines.forEach(line => fabricCanvas.remove(line));
    fabricCanvas.renderAll();
  }
}

function redrawPerpendicularLines() {
  /**
   * Ridisegna tutte le linee perpendicolari seguendo l'asse di simmetria
   */
  if (!currentLandmarks || currentLandmarks.length === 0) return;
  if (!currentLandmarks[9] || !currentLandmarks[164]) return;

  isRedrawingLines = true; // Blocca l'event handler durante il ridisegno

  // Disabilita TUTTI gli eventi di Fabric.js temporaneamente
  fabricCanvas.off('object:moving');

  clearPerpendicularLines();

  const glabella = currentLandmarks[9];
  const philtrum = currentLandmarks[164];

  const transformedGlabella = transformLandmarkCoordinate(glabella);
  const transformedPhiltrum = transformLandmarkCoordinate(philtrum);

  // Direzione dell'asse
  const dx = transformedPhiltrum.x - transformedGlabella.x;
  const dy = transformedPhiltrum.y - transformedGlabella.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  const axisX = dx / length;
  const axisY = dy / length;

  // Direzione perpendicolare (ruotata di 90°)
  const perpX = -axisY;
  const perpY = axisX;

  // Lunghezza della linea perpendicolare (copre tutto il canvas)
  const canvasWidth = fabricCanvas.getWidth();
  const canvasHeight = fabricCanvas.getHeight();
  const lineLength = Math.sqrt(canvasWidth * canvasWidth + canvasHeight * canvasHeight) * 2;

  perpendicularLines.forEach((normalizedPos, index) => {
    // Punto sull'asse
    const pointX = transformedGlabella.x + axisX * normalizedPos * length;
    const pointY = transformedGlabella.y + axisY * normalizedPos * length;

    // Punti della linea perpendicolare
    const x1 = pointX - perpX * lineLength / 2;
    const y1 = pointY - perpY * lineLength / 2;
    const x2 = pointX + perpX * lineLength / 2;
    const y2 = pointY + perpY * lineLength / 2;

    console.log(`📏 Creazione linea ${index}: normalizedPos=${normalizedPos.toFixed(3)}, center=(${pointX.toFixed(1)}, ${pointY.toFixed(1)})`);

    const line = new fabric.Line([x1, y1, x2, y2], {
      stroke: '#00FFFF',
      strokeWidth: 2,
      selectable: true,
      evented: true,
      lockRotation: true,
      lockScalingX: true,
      lockScalingY: true,
      hasControls: false,
      hasBorders: false, // Nessun bordo di selezione
      isPerpendicularLine: true,
      normalizedPosition: normalizedPos,
      hoverCursor: 'move',
      moveCursor: 'move',
      padding: 20  // Area touch generosa per selezione da mobile
    });

    fabricCanvas.add(line);
    console.log(`✅ Linea ${index} aggiunta al canvas - selectable: ${line.selectable}, evented: ${line.evented}`);
  });

  fabricCanvas.renderAll();

  // Riabilita l'event handler
  setupPerpendicularLineHandlers();
  isRedrawingLines = false;
}

window.addPerpendicularLine = addPerpendicularLine;
window.clearPerpendicularLines = clearPerpendicularLines;
window.redrawPerpendicularLines = redrawPerpendicularLines;

// Event handler per movimento linee perpendicolari
let perpendicularLineHandler = null;

function setupPerpendicularLineHandlers() {
  if (!fabricCanvas) return;

  // Rimuovi handler precedente se esiste
  if (perpendicularLineHandler) {
    fabricCanvas.off('object:moving', perpendicularLineHandler);
  }

  // Crea nuovo handler
  perpendicularLineHandler = function (e) {
    const obj = e.target;

    console.log('🔄 object:moving event triggered', obj ? obj.type : 'no object', obj ? obj.isPerpendicularLine : false);

    if (!obj || !obj.isPerpendicularLine) return;

    // IGNORA se stiamo ridisegnando (evita loop infiniti)
    if (isRedrawingLines) {
      console.log('⏸️ Ignoring move - redrawing in progress');
      return;
    }

    console.log('✅ Processing perpendicular line movement');

    // Vincola il movimento solo lungo l'asse di simmetria
    if (!currentLandmarks || !currentLandmarks[9] || !currentLandmarks[164]) return;

    const glabella = currentLandmarks[9];
    const philtrum = currentLandmarks[164];
    const transGlab = transformLandmarkCoordinate(glabella);
    const transPhil = transformLandmarkCoordinate(philtrum);

    // Vettore dell'asse
    const axisVecX = transPhil.x - transGlab.x;
    const axisVecY = transPhil.y - transGlab.y;
    const axisLength = Math.sqrt(axisVecX * axisVecX + axisVecY * axisVecY);
    const axisNormX = axisVecX / axisLength;
    const axisNormY = axisVecY / axisLength;

    // Centro attuale della linea dopo il trascinamento - usa getCenterPoint per Fabric.js
    const lineCenter = obj.getCenterPoint();
    const lineCenterX = lineCenter.x;
    const lineCenterY = lineCenter.y;

    console.log(`📍 Linea trascinata a: (${lineCenterX.toFixed(1)}, ${lineCenterY.toFixed(1)})`);

    // Proietta il centro della linea sull'asse
    const clickVecX = lineCenterX - transGlab.x;
    const clickVecY = lineCenterY - transGlab.y;
    const projection = (clickVecX * axisVecX + clickVecY * axisVecY) / (axisLength * axisLength);
    // NON clampare - permetti linee oltre i landmark
    const newNormalizedPos = projection;

    console.log(`📊 Proiezione: ${projection.toFixed(3)} (NON clampata)`);

    // Calcola il punto esatto sull'asse
    const pointOnAxisX = transGlab.x + axisNormX * newNormalizedPos * axisLength;
    const pointOnAxisY = transGlab.y + axisNormY * newNormalizedPos * axisLength;

    console.log(`📍 Punto sull'asse: (${pointOnAxisX.toFixed(1)}, ${pointOnAxisY.toFixed(1)})`);

    // Direzione perpendicolare
    const perpX = -axisNormY;
    const perpY = axisNormX;

    // Lunghezza della linea
    const canvasWidth = fabricCanvas.getWidth();
    const canvasHeight = fabricCanvas.getHeight();
    const lineLength = Math.sqrt(canvasWidth * canvasWidth + canvasHeight * canvasHeight) * 2;

    // Aggiorna direttamente le coordinate della linea
    obj.set({
      x1: pointOnAxisX - perpX * lineLength / 2,
      y1: pointOnAxisY - perpY * lineLength / 2,
      x2: pointOnAxisX + perpX * lineLength / 2,
      y2: pointOnAxisY + perpY * lineLength / 2
    });
    obj.setCoords();

    // Aggiorna la posizione normalizzata nell'array
    const oldIndex = perpendicularLines.indexOf(obj.normalizedPosition);
    if (oldIndex !== -1) {
      perpendicularLines[oldIndex] = newNormalizedPos;
      obj.normalizedPosition = newNormalizedPos;
      window.perpendicularLines = perpendicularLines;
    }

    fabricCanvas.renderAll();
  };

  // Aggiungi l'handler al canvas
  fabricCanvas.on('object:moving', perpendicularLineHandler);
}

// Chiama setup quando il canvas è pronto
if (typeof fabricCanvas !== 'undefined' && fabricCanvas) {
  setupPerpendicularLineHandlers();
}

// === GESTIONE COPPIE DI LINEE VERTICALI SPECULARI (COUPLE) ===

var coupleLines = []; // Array di coppie: [{id, normalizedAxisPos, distanceFromAxis}]
let coupleLineCounter = 0; // Contatore per ID univoci
let isRedrawingCoupleLines = false; // Flag per evitare loop infiniti

function addCoupleVerticalLines(normalizedAxisPos, distanceFromAxis) {
  /**
   * Aggiunge una coppia di linee verticali speculari rispetto all'asse di simmetria
   * normalizedAxisPos: posizione lungo l'asse (0=glabella, 1=philtrum)
   * distanceFromAxis: distanza orizzontale dall'asse (valore assoluto)
   */
  const coupleId = ++coupleLineCounter;

  coupleLines.push({
    id: coupleId,
    normalizedAxisPos: normalizedAxisPos,
    distanceFromAxis: distanceFromAxis
  });
  window.coupleLines = coupleLines;

  // Crea le due linee speculari
  createCoupleLines(coupleId, normalizedAxisPos, distanceFromAxis);

  console.log(`⚖️ Coppia linee verticali aggiunta: id=${coupleId}, axisPos=${normalizedAxisPos.toFixed(3)}, distance=${distanceFromAxis.toFixed(1)}`);
}

function createCoupleLines(coupleId, normalizedAxisPos, distanceFromAxis) {
  /**
   * Crea le due linee verticali speculari sul canvas
   */
  if (!currentLandmarks || currentLandmarks.length === 0) return;
  if (!currentLandmarks[9] || !currentLandmarks[164]) return;

  const glabella = currentLandmarks[9];
  const philtrum = currentLandmarks[164];

  const transformedGlabella = transformLandmarkCoordinate(glabella);
  const transformedPhiltrum = transformLandmarkCoordinate(philtrum);

  // Direzione dell'asse
  const dx = transformedPhiltrum.x - transformedGlabella.x;
  const dy = transformedPhiltrum.y - transformedGlabella.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  const axisX = dx / length;
  const axisY = dy / length;

  // Direzione perpendicolare (sinistra-destra)
  const perpX = -axisY;
  const perpY = axisX;

  // Punto centrale sull'asse
  const centerX = transformedGlabella.x + axisX * normalizedAxisPos * length;
  const centerY = transformedGlabella.y + axisY * normalizedAxisPos * length;

  // Lunghezza delle linee verticali (parallele all'asse)
  const canvasWidth = fabricCanvas.getWidth();
  const canvasHeight = fabricCanvas.getHeight();
  const lineLength = Math.sqrt(canvasWidth * canvasWidth + canvasHeight * canvasHeight) * 2;

  // Punti per linea sinistra (distanza negativa dall'asse)
  const leftCenterX = centerX - perpX * distanceFromAxis;
  const leftCenterY = centerY - perpY * distanceFromAxis;
  const leftX1 = leftCenterX - axisX * lineLength / 2;
  const leftY1 = leftCenterY - axisY * lineLength / 2;
  const leftX2 = leftCenterX + axisX * lineLength / 2;
  const leftY2 = leftCenterY + axisY * lineLength / 2;

  // Punti per linea destra (distanza positiva dall'asse)
  const rightCenterX = centerX + perpX * distanceFromAxis;
  const rightCenterY = centerY + perpY * distanceFromAxis;
  const rightX1 = rightCenterX - axisX * lineLength / 2;
  const rightY1 = rightCenterY - axisY * lineLength / 2;
  const rightX2 = rightCenterX + axisX * lineLength / 2;
  const rightY2 = rightCenterY + axisY * lineLength / 2;

  console.log(`📏 Creazione coppia linee: id=${coupleId}, center=(${centerX.toFixed(1)}, ${centerY.toFixed(1)}), distance=${distanceFromAxis.toFixed(1)}`);

  // Crea linea sinistra
  const leftLine = new fabric.Line([leftX1, leftY1, leftX2, leftY2], {
    stroke: '#FF00FF', // Magenta
    strokeWidth: 2,
    selectable: true,
    evented: true,
    lockRotation: true,
    lockScalingX: true,
    lockScalingY: true,
    hasControls: false,
    hasBorders: false,
    isCoupleVerticalLine: true,
    coupleId: coupleId,
    coupleSide: 'left',
    normalizedAxisPos: normalizedAxisPos,
    distanceFromAxis: distanceFromAxis,
    hoverCursor: 'move',
    moveCursor: 'move',
    padding: 20  // Area touch generosa per selezione da mobile
  });

  // Crea linea destra
  const rightLine = new fabric.Line([rightX1, rightY1, rightX2, rightY2], {
    stroke: '#FF00FF', // Magenta
    strokeWidth: 2,
    selectable: true,
    evented: true,
    lockRotation: true,
    lockScalingX: true,
    lockScalingY: true,
    hasControls: false,
    hasBorders: false,
    isCoupleVerticalLine: true,
    coupleId: coupleId,
    coupleSide: 'right',
    normalizedAxisPos: normalizedAxisPos,
    distanceFromAxis: distanceFromAxis,
    hoverCursor: 'move',
    moveCursor: 'move',
    padding: 20  // Area touch generosa per selezione da mobile
  });

  fabricCanvas.add(leftLine);
  fabricCanvas.add(rightLine);
  console.log(`✅ Coppia linee aggiunte al canvas - id=${coupleId}`);

  // Assicurati che l'handler sia attivo
  setupCoupleLineHandlers();

  fabricCanvas.renderAll();
}

function clearCoupleLines() {
  /**
   * Rimuove tutte le coppie di linee verticali dal canvas
   */
  if (fabricCanvas) {
    const lines = fabricCanvas.getObjects().filter(obj => obj.isCoupleVerticalLine);
    lines.forEach(line => fabricCanvas.remove(line));
    fabricCanvas.renderAll();
  }
}

function redrawCoupleLines() {
  /**
   * Ridisegna tutte le coppie di linee verticali
   */
  if (!currentLandmarks || currentLandmarks.length === 0) return;
  if (!currentLandmarks[9] || !currentLandmarks[164]) return;

  isRedrawingCoupleLines = true;

  // Disabilita temporaneamente l'handler
  fabricCanvas.off('object:moving');

  clearCoupleLines();

  coupleLines.forEach(couple => {
    createCoupleLines(couple.id, couple.normalizedAxisPos, couple.distanceFromAxis);
  });

  fabricCanvas.renderAll();

  // Riabilita handler
  setupPerpendicularLineHandlers();
  setupCoupleLineHandlers();
  isRedrawingCoupleLines = false;
}

// Event handler per movimento coppie di linee
let coupleLineHandler = null;

function setupCoupleLineHandlers() {
  if (!fabricCanvas) return;

  // Rimuovi handler precedente se esiste
  if (coupleLineHandler) {
    fabricCanvas.off('object:moving', coupleLineHandler);
  }

  // Crea nuovo handler
  coupleLineHandler = function (e) {
    const obj = e.target;

    if (!obj || !obj.isCoupleVerticalLine) return;

    // IGNORA se stiamo ridisegnando
    if (isRedrawingCoupleLines) {
      console.log('⏸️ Ignoring couple move - redrawing in progress');
      return;
    }

    console.log(`⚖️ Moving couple line: id=${obj.coupleId}, side=${obj.coupleSide}`);

    // Trova il dato della coppia nell'array
    const coupleData = coupleLines.find(c => c.id === obj.coupleId);
    if (!coupleData) return;

    // Calcola nuova posizione
    if (!currentLandmarks || !currentLandmarks[9] || !currentLandmarks[164]) return;

    const glabella = currentLandmarks[9];
    const philtrum = currentLandmarks[164];
    const transGlab = transformLandmarkCoordinate(glabella);
    const transPhil = transformLandmarkCoordinate(philtrum);

    // Vettore dell'asse
    const axisVecX = transPhil.x - transGlab.x;
    const axisVecY = transPhil.y - transGlab.y;
    const axisLength = Math.sqrt(axisVecX * axisVecX + axisVecY * axisVecY);
    const axisNormX = axisVecX / axisLength;
    const axisNormY = axisVecY / axisLength;

    // Direzione perpendicolare
    const perpX = -axisNormY;
    const perpY = axisNormX;

    // Centro attuale della linea trascinata
    const lineCenter = obj.getCenterPoint();

    // Calcola la nuova distanza dall'asse (componente perpendicolare)
    const vecFromGlabX = lineCenter.x - transGlab.x;
    const vecFromGlabY = lineCenter.y - transGlab.y;
    const newDistanceFromAxis = Math.abs(vecFromGlabX * perpX + vecFromGlabY * perpY);

    // Aggiorna la distanza nella coppia
    coupleData.distanceFromAxis = newDistanceFromAxis;
    obj.distanceFromAxis = newDistanceFromAxis;

    console.log(`📊 Nuova distanza dall'asse: ${newDistanceFromAxis.toFixed(1)}`);

    // Punto centrale sull'asse per questa posizione
    const centerX = transGlab.x + axisNormX * coupleData.normalizedAxisPos * axisLength;
    const centerY = transGlab.y + axisNormY * coupleData.normalizedAxisPos * axisLength;

    // Lunghezza delle linee
    const canvasWidth = fabricCanvas.getWidth();
    const canvasHeight = fabricCanvas.getHeight();
    const lineLength = Math.sqrt(canvasWidth * canvasWidth + canvasHeight * canvasHeight) * 2;

    // Aggiorna la linea trascinata
    const sign = (obj.coupleSide === 'left') ? -1 : 1;
    const lineCenterX = centerX + sign * perpX * newDistanceFromAxis;
    const lineCenterY = centerY + sign * perpY * newDistanceFromAxis;

    obj.set({
      x1: lineCenterX - axisNormX * lineLength / 2,
      y1: lineCenterY - axisNormY * lineLength / 2,
      x2: lineCenterX + axisNormX * lineLength / 2,
      y2: lineCenterY + axisNormY * lineLength / 2
    });
    obj.setCoords();

    // Trova e aggiorna la linea gemella (speculare)
    const allCoupleLines = fabricCanvas.getObjects().filter(
      o => o.isCoupleVerticalLine && o.coupleId === obj.coupleId && o !== obj
    );

    allCoupleLines.forEach(twinLine => {
      const twinSign = (twinLine.coupleSide === 'left') ? -1 : 1;
      const twinCenterX = centerX + twinSign * perpX * newDistanceFromAxis;
      const twinCenterY = centerY + twinSign * perpY * newDistanceFromAxis;

      twinLine.set({
        x1: twinCenterX - axisNormX * lineLength / 2,
        y1: twinCenterY - axisNormY * lineLength / 2,
        x2: twinCenterX + axisNormX * lineLength / 2,
        y2: twinCenterY + axisNormY * lineLength / 2
      });
      twinLine.distanceFromAxis = newDistanceFromAxis;
      twinLine.setCoords();

      console.log(`⚖️ Linea gemella (${twinLine.coupleSide}) aggiornata specularmente`);
    });

    fabricCanvas.renderAll();
  };

  // Aggiungi l'handler al canvas
  fabricCanvas.on('object:moving', coupleLineHandler);
}

window.addCoupleVerticalLines = addCoupleVerticalLines;
window.clearCoupleLines = clearCoupleLines;
window.redrawCoupleLines = redrawCoupleLines;
window.coupleLines = coupleLines;

// Chiama setup quando il canvas è pronto
if (typeof fabricCanvas !== 'undefined' && fabricCanvas) {
  setupCoupleLineHandlers();
}

function drawGreenDots() {
  /**
   * Disegna i green dots rilevati dall'API o fallback sui punti chiave landmarks.
   * Integra i risultati del modulo src/green_dots_processor.py.
   */
  if (!fabricCanvas) return;

  console.log('🟢 Disegno green dots');

  // Se abbiamo dati dall'API green dots, disegna quelli
  if (window.greenDotsData && window.greenDotsData.success) {
    drawGreenDotsFromAPI();
  } else if (currentLandmarks && currentLandmarks.length > 0) {
    // Fallback: disegna sui punti chiave landmarks
    drawGreenDotsLandmarksFallback();
  }
}

function drawGreenDotsFromAPI() {
  /**
   * Disegna l'overlay dei green dots rilevati dall'API green-dots-processor.
   * NON disegna i singoli punti per evitare duplicazioni.
   */
  const data = window.greenDotsData;
  console.log('🎯 Disegno overlay green dots dall\'API - Dati:', data);

  // Rimuovi solo gli overlay green dots esistenti (non disabilitare movimento)
  if (fabricCanvas) {
    const elementsToRemove = fabricCanvas.getObjects().filter(obj =>
      obj.isGreenDot || obj.isGreenDotsOverlay || obj.isGreenDotsGroup
    );
    elementsToRemove.forEach(element => fabricCanvas.remove(element));
    console.log(`🧹 Rimossi ${elementsToRemove.length} elementi green dots dal canvas`);
  }

  // Disegna solo l'overlay se disponibile, altrimenti disegna i gruppi manualmente
  if (data.overlay_base64) {
    console.log('🎨 Uso overlay generato dal processore');
    drawGreenDotsOverlay(data.overlay_base64);
  } else if (data.groups) {
    console.log('🔶 Disegno gruppi manualmente (nessun overlay disponibile)');
    drawGreenDotsGroups(data.groups);
  } else {
    console.log('⚠️ Nessun overlay o gruppi disponibili, uso fallback landmarks');
    drawGreenDotsLandmarksFallback();
  }

  // Assicura che il movimento dell'immagine sia abilitato dopo il ridisegno
  if (window.currentGreenDotsOverlay || data.overlay_base64) {
    enableImageMovement();
  }

  fabricCanvas.renderAll();
  console.log('🎨 Overlay green dots disegnato dall\'API con movimento abilitato');
}

function drawGreenDotsLandmarksFallback() {
  /**
   * Fallback: disegna green dots sui landmarks chiave quando l'API non è disponibile.
   */
  console.log('🟡 Fallback: disegno green dots sui landmarks chiave');

  const keyPoints = [
    10, 151, 9, 8, 168, 6, 148, 152,
    33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246,
    362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382,
    1, 2, 5, 4, 6, 19, 20, 94, 125, 141, 235, 236, 237, 238, 239, 240, 241, 242,
    61, 84, 17, 314, 405, 320, 307, 375, 321, 308, 324, 318,
    78, 81, 13, 82, 312, 15, 16, 85, 179, 86, 316, 317, 18,
    46, 53, 52, 51, 48, 115, 131, 134, 102, 49, 220, 305,
    276, 283, 282, 295, 285, 336, 296, 334, 293, 300, 276, 283
  ];

  let dotsDrawn = 0;
  keyPoints.forEach(pointIndex => {
    if (currentLandmarks[pointIndex]) {
      const point = currentLandmarks[pointIndex];
      const transformedPoint = transformLandmarkCoordinate(point);

      const dot = new fabric.Circle({
        left: transformedPoint.x - 2,
        top: transformedPoint.y - 2,
        radius: 2,
        fill: '#00FF00',
        stroke: '#008000',
        strokeWidth: 0.5,
        selectable: false,
        evented: false,
        isGreenDot: true,
        isFallbackDot: true,
        landmarkIndex: pointIndex
      });

      fabricCanvas.add(dot);
      dotsDrawn++;
    }
  });

  fabricCanvas.renderAll();
  console.log(`� ${dotsDrawn} green dots fallback disegnati sui landmarks`);
}

function drawGreenDotsOverlay(overlayBase64) {
  /**
   * Disegna l'overlay trasparente generato dal processore green dots.
   *
   * POSIZIONAMENTO ROBUSTO: usa currentImage.getBoundingRect(true) per ricavare
   * il rettangolo visivo reale dell'immagine sul canvas indipendentemente dall'angolo
   * di rotazione Fabric.js.
   * L'overlay ha i pixel già nella corretta orientazione (inviati ruotati all'API)
   * quindi viene posizionato con angle=0 e stretchato sul bounding rect.
   * Questo funziona correttamente per 0°, 90°, 180°, 270° e qualsiasi altro angolo.
   */
  try {
    fabric.Image.fromURL(overlayBase64, function (overlayImg) {
      if (!currentImage) {
        console.warn('⚠️ Nessuna immagine corrente disponibile per overlay');
        return;
      }

      // Rimuovi overlay precedente se esiste
      const existingOverlay = fabricCanvas.getObjects().find(obj => obj.isGreenDotsOverlay);
      if (existingOverlay) {
        fabricCanvas.remove(existingOverlay);
      }

      // Bounding rect assoluto dell'immagine nel canvas (asse-allineato, comprende rotazione)
      const bbox = currentImage.getBoundingRect(true);
      const normalizedAngle = ((currentImage.angle || 0) % 360 + 360) % 360;

      console.log(`🎨 Overlay: ${overlayImg.width}x${overlayImg.height} → bbox ${bbox.width.toFixed(0)}x${bbox.height.toFixed(0)} @ (${bbox.left.toFixed(1)}, ${bbox.top.toFixed(1)}) angle=${normalizedAngle}°`);

      overlayImg.set({
        left: bbox.left,
        top: bbox.top,
        // Stretch dell'overlay sull'intero bounding rect visivo dell'immagine
        scaleX: bbox.width / overlayImg.width,
        scaleY: bbox.height / overlayImg.height,
        angle: 0,        // pixel già nella corretta orientazione finale (ruotati da getCanvasImageAsBase64)
        originX: 'left',
        originY: 'top',
        selectable: false,
        evented: false,
        isGreenDotsOverlay: true,
        opacity: 0.8
      });

      // Salva riferimento all'overlay e i metadati di detection per sync futura
      window.currentGreenDotsOverlay = overlayImg;
      window.currentGreenDotsOverlayNaturalW = overlayImg.width;
      window.currentGreenDotsOverlayNaturalH = overlayImg.height;
      // Metadati detection: angolo immagine e scala al momento del rilevamento
      window.greenDotsDetectionAngle = currentImage.angle || 0;
      window.greenDotsOverlayScaleXAtDetection = (bbox.width / overlayImg.width);
      window.greenDotsOverlayScaleYAtDetection = (bbox.height / overlayImg.height);
      const _ctr = currentImage.getCenterPoint();
      window.greenDotsDetectionCenterX = _ctr.x;
      window.greenDotsDetectionCenterY = _ctr.y;

      fabricCanvas.add(overlayImg);

      // Posiziona l'overlay sopra l'immagine di sfondo ma sotto altri elementi
      const backgroundImage = fabricCanvas.getObjects().find(obj => obj.isBackgroundImage);
      if (backgroundImage) {
        fabricCanvas.sendToBack(backgroundImage);
        const allObjects = fabricCanvas.getObjects();
        const backgroundIndex = allObjects.indexOf(backgroundImage);
        fabricCanvas.moveTo(overlayImg, backgroundIndex + 1);
      } else {
        console.log('🎨 Nessuna immagine di sfondo trovata');
      }

      fabricCanvas.renderAll();
      console.log('🎨 Overlay green dots aggiunto con bounding-rect positioning');

      // Abilita l'immagine per essere spostata e configura sincronizzazione
      enableImageMovement();
    });
  } catch (error) {
    console.error('❌ Errore aggiunta overlay green dots:', error);
  }
}

function _setupOverlaySync() {
  // Registra event listeners per sincronizzare l'overlay green dots
  // con l'immagine durante pan/zoom/rotazione (gestiti da canvas-modes.js).
  if (!currentImage || !currentImage.isBackgroundImage) return;

  fabricCanvas.off('object:moving');
  fabricCanvas.off('object:scaling');
  fabricCanvas.off('object:modified');
  fabricCanvas.off('object:moved');
  fabricCanvas.off('object:scaled');
  fabricCanvas.off('object:rotated');

  fabricCanvas.on('object:moving', function (e) {
    if (e.target === currentImage && window.currentGreenDotsOverlay) {
      window.currentGreenDotsOverlay.set({ left: currentImage.left, top: currentImage.top });
      fabricCanvas.requestRenderAll();
    }
  });

  fabricCanvas.on('object:scaling', function (e) {
    if (e.target === currentImage && window.currentGreenDotsOverlay) {
      window.currentGreenDotsOverlay.set({
        left: currentImage.left, top: currentImage.top,
        scaleX: currentImage.scaleX, scaleY: currentImage.scaleY
      });
      fabricCanvas.requestRenderAll();
    }
  });

  fabricCanvas.on('object:modified', function (e) {
    if (e.target === currentImage && window.currentGreenDotsOverlay) {
      syncGreenDotsOverlayWithImage();
    }
  });
}
// Alias retrocompatibile (chiamata da drawGreenDotsFromAPI e drawGreenDotsOverlay)
const enableImageMovement = _setupOverlaySync;

function disableImageMovement() {
  /**
   * Disabilita il movimento dell'immagine e rimuove event listeners
   */
  if (currentImage && currentImage.isBackgroundImage) {
    currentImage.set({
      selectable: false,
      evented: false
    });

    // Rimuovi event listeners per object events (NON mouse events - rimangono globali)
    fabricCanvas.off('object:moving');
    fabricCanvas.off('object:scaling');
    fabricCanvas.off('object:modified');
    fabricCanvas.off('object:moved');
    fabricCanvas.off('object:scaled');
    fabricCanvas.off('object:rotated');

    // Pulisci timeout pan se esiste
    if (window.panSyncTimeout) {
      clearTimeout(window.panSyncTimeout);
      window.panSyncTimeout = null;
    }

    fabricCanvas.renderAll();
    console.log('🔒 Movimento immagine e pan canvas disabilitati');
  }
}

function drawGreenDotsGroups(groups) {
  /**
   * Disegna le forme dei gruppi sinistro/destro dei green dots.
   */
  const colors = {
    'Sx': { fill: 'rgba(0, 255, 0, 0.2)', stroke: 'rgba(0, 255, 0, 0.8)' },
    'Dx': { fill: 'rgba(0, 0, 255, 0.2)', stroke: 'rgba(0, 0, 255, 0.8)' }
  };

  Object.keys(groups).forEach(groupName => {
    const groupPoints = groups[groupName];
    if (groupPoints && groupPoints.length >= 3) {

      // Converte i punti in coordinate canvas
      const canvasPoints = groupPoints.map(point => {
        const scaled = scaleImageCoordinates(point.x, point.y);
        return { x: scaled.x, y: scaled.y };
      });

      // Crea un poligono per il gruppo
      const polygon = new fabric.Polygon(canvasPoints, {
        fill: colors[groupName]?.fill || 'rgba(128, 128, 128, 0.2)',
        stroke: colors[groupName]?.stroke || 'rgba(128, 128, 128, 0.8)',
        strokeWidth: 2,
        selectable: false,
        evented: false,
        isGreenDotsGroup: true,
        groupName: groupName
      });

      fabricCanvas.add(polygon);
      console.log(`🔶 Gruppo ${groupName} disegnato con ${groupPoints.length} punti`);
    }
  });
}

function scaleImageCoordinates(x, y) {
  /**
   * Converte coordinate dell'immagine INVIATA ALL'API in coordinate del canvas scalato.
   *
   * L'API restituisce x/y nel sistema di pixel dell'immagine inviata (ANALYSIS_MAX_PX),
   * che può essere ridotta rispetto all'originale. window.greenDotsImageScale contiene
   * il fattore di riduzione (sent_px / original_px). Per ottenere le coordinate
   * nel sistema dell'immagine originale (usato da window.imageScale / imageOffset)
   * dividiamo prima per greenDotsImageScale.
   *
   * Formula:
   *   x_canvas = (x_sent / greenDotsImageScale) * imageScale + imageOffset.x
   */
  if (!window.imageScale || !window.imageOffset) {
    console.warn('⚠️ Informazioni scala green dots non disponibili, ricalcolo...');

    if (currentImage && fabricCanvas) {
      recalculateImageTransformation();
    }

    if (!window.imageScale || !window.imageOffset) {
      console.warn('❌ Impossibile scalare coordinate green dots, usando originali');
      return { x, y };
    }
  }

  // Converti da spazio immagine inviata a spazio immagine originale
  const sentToOrigScale = window.greenDotsImageScale || 1.0;
  const xOrig = x / sentToOrigScale;
  const yOrig = y / sentToOrigScale;

  const scaled = {
    x: xOrig * window.imageScale + window.imageOffset.x,
    y: yOrig * window.imageScale + window.imageOffset.y
  };

  console.log(`🟢 Scala green dots: sent(${x}, ${y}) → orig(${xOrig.toFixed(0)}, ${yOrig.toFixed(0)}) → canvas(${scaled.x.toFixed(1)}, ${scaled.y.toFixed(1)}) | sentScale:${sentToOrigScale.toFixed(3)} imgScale:${window.imageScale?.toFixed(4)}`);

  return scaled;
}

function updateMeasurementsFromGreenDots(greenDotsResult) {
  /**
   * Aggiorna la sezione misurazioni con i risultati dell'analisi green dots.
   */
  console.log('📏 Aggiornamento misurazioni green dots:', greenDotsResult);

  if (!greenDotsResult.success) {
    console.warn('⚠️ Risultati green dots non validi per le misurazioni');
    return;
  }

  try {
    // Trova la sezione misurazioni (corretta struttura HTML)
    const measurementsSection = document.querySelector('#measurements-data');
    if (!measurementsSection) {
      console.warn('⚠️ Sezione misurazioni non trovata - cercando #measurements-data');
      console.log('🔍 Elementi disponibili:', document.querySelectorAll('[id*="measurement"], [class*="measurement"]'));
      return;
    }

    // Rimuovi solo le righe green dots esistenti per evitare duplicati
    const existingGreenDotsRows = measurementsSection.querySelectorAll('tr[data-type="green-dots"]');
    existingGreenDotsRows.forEach(row => row.remove());

    // Genera e aggiungi le nuove righe dei green dots
    const tableRows = generateGreenDotsTableRows(greenDotsResult);
    measurementsSection.insertAdjacentHTML('afterbegin', tableRows);

    // Assicurati che la sezione misurazioni sia visibile ed espansa
    const measurementsSections = document.querySelectorAll('.right-sidebar .section');
    measurementsSections.forEach(section => {
      const toggleBtn = section.querySelector('.toggle-btn');
      if (toggleBtn && toggleBtn.textContent.includes('📏 MISURAZIONI')) {
        const sectionContent = section.querySelector('.section-content');
        if (sectionContent) {
          sectionContent.style.display = 'block';
          section.setAttribute('data-expanded', 'true');
          const icon = section.querySelector('.icon');
          if (icon) icon.textContent = '▼';
          console.log('👁️ Sezione misurazioni resa visibile ed espansa');
        }
      }
    });

    console.log('✅ Misurazioni green dots aggiornate e mostrate');

    // Apri la sezione DATI ANALISI unificata e switcha al tab MISURAZIONI
    openUnifiedAnalysisSection();
    switchUnifiedTab('measurements', null, true); // FORCE UPDATE per aggiornare anche se già attivo

    console.log('🔄 [UNIFIED] Tab MISURAZIONI attivato/aggiornato automaticamente per green dots');

  } catch (error) {
    console.error('❌ Errore aggiornamento misurazioni green dots:', error);
  }
}

function generateGreenDotsTableRows(result) {
  /**
   * Genera le righe della tabella delle misurazioni per i green dots.
   */
  let rows = '';

  if (!result.success || !result.statistics) {
    rows += `<tr data-type="green-dots">
      <td>⚠️ Green Dots</td>
      <td>Nessun dato</td>
      <td>-</td>
      <td>❌ Errore</td>
    </tr>`;
    return rows;
  }

  // === DETTAGLI PUNTINI BIANCHI === (header in cima, sempre visibile)
  rows += `<tr data-type="green-dots" style="background:#2a4a5e; color:#fff; font-weight:bold; cursor:default;">
    <td colspan="4" style="text-align:left; padding:6px 10px;">⚪ DETTAGLI PUNTINI BIANCHI</td>
  </tr>`;

  // === SOPRACCIGLIO SINISTRO (collassabile, chiuso) ===
  const leftDots2 = result.groups?.Sx || [];
  if (leftDots2.length > 0) {
    const gidL = 'gd-collapse-left-' + Date.now();
    rows += `<tr data-type="green-dots" style="background:#1a5276; color:#fff; font-weight:bold; cursor:pointer;"
      onclick="document.querySelectorAll('[data-collapse=\\'${gidL}\\']').forEach(r=>{r.style.display=r.style.display==='none'?'':'none';})">
      <td colspan="4" style="text-align:left; padding:6px 10px;">◀️ SOPRACCIGLIO SINISTRO (${leftDots2.length} puntini) ▾</td>
    </tr>`;
    leftDots2.forEach((dot, idx) => {
      const colorClass = dot.size > 35 ? 'color:#f44336' : dot.size > 25 ? 'color:#ff9800' : dot.size > 15 ? 'color:#ffc107' : 'color:#4caf50';
      const compactStr = dot.compactness ? dot.compactness.toFixed(2) : null;
      const scoreStr = dot.score ? dot.score.toFixed(1) : (dot.size * 1.5).toFixed(1);
      const hsvStr = (dot.h !== undefined && dot.s !== undefined && dot.v !== undefined) ? `H:${dot.h}° S:${dot.s}% V:${dot.v}%` : 'N/A';
      const label = dot.anatomical_name || `L${idx + 1}`;
      rows += `<tr data-type="green-dots" data-collapse="${gidL}" style="font-size:0.9em; display:none;">
        <td style="padding-left:20px;"><strong>⚪ ${label}</strong> (${dot.x}, ${dot.y})</td>
        <td style="${colorClass}">Size:${dot.size}px${compactStr ? ` | C:${compactStr}` : ''} | Score:${scoreStr}</td>
        <td>${hsvStr}</td><td>✅</td>
      </tr>`;
    });
  }

  // === SOPRACCIGLIO DESTRO (collassabile, chiuso) ===
  const rightDots2 = result.groups?.Dx || [];
  if (rightDots2.length > 0) {
    const gidR = 'gd-collapse-right-' + (Date.now() + 1);
    rows += `<tr data-type="green-dots" style="background:#1a5276; color:#fff; font-weight:bold; cursor:pointer;"
      onclick="document.querySelectorAll('[data-collapse=\\'${gidR}\\']').forEach(r=>{r.style.display=r.style.display==='none'?'':'none';})">
      <td colspan="4" style="text-align:left; padding:6px 10px;">▶️ SOPRACCIGLIO DESTRO (${rightDots2.length} puntini) ▾</td>
    </tr>`;
    rightDots2.forEach((dot, idx) => {
      const colorClass = dot.size > 35 ? 'color:#f44336' : dot.size > 25 ? 'color:#ff9800' : dot.size > 15 ? 'color:#ffc107' : 'color:#4caf50';
      const compactStr = dot.compactness ? dot.compactness.toFixed(2) : null;
      const scoreStr = dot.score ? dot.score.toFixed(1) : (dot.size * 1.5).toFixed(1);
      const hsvStr = (dot.h !== undefined && dot.s !== undefined && dot.v !== undefined) ? `H:${dot.h}° S:${dot.s}% V:${dot.v}%` : 'N/A';
      const label = dot.anatomical_name || `R${idx + 1}`;
      rows += `<tr data-type="green-dots" data-collapse="${gidR}" style="font-size:0.9em; display:none;">
        <td style="padding-left:20px;"><strong>⚪ ${label}</strong> (${dot.x}, ${dot.y})</td>
        <td style="${colorClass}">Size:${dot.size}px${compactStr ? ` | C:${compactStr}` : ''} | Score:${scoreStr}</td>
        <td>${hsvStr}</td><td>✅</td>
      </tr>`;
    });
  }

  const stats = result.statistics;

  // Calcola quale poligono è maggiore
  let leftArea = stats.left ? stats.left.area : 0;
  let rightArea = stats.right ? stats.right.area : 0;
  let largerSide = leftArea > rightArea ? 'left' : rightArea > leftArea ? 'right' : 'equal';

  // Area lato sinistro con evidenziazione se maggiore
  if (stats.left) {
    const isLarger = largerSide === 'left';
    rows += `<tr data-type="green-dots">
      <td>🟢 Poligono Sinistro</td>
      <td>${stats.left.area.toFixed(1)} ${isLarger ? '🔴 MAGGIORE' : ''}</td>
      <td>px²</td>
      <td>✅ OK</td>
    </tr>`;
  }

  // Area lato destro con evidenziazione se maggiore
  if (stats.right) {
    const isLarger = largerSide === 'right';
    rows += `<tr data-type="green-dots">
      <td>🟢 Poligono Destro</td>
      <td>${stats.right.area.toFixed(1)} ${isLarger ? '🔴 MAGGIORE' : ''}</td>
      <td>px²</td>
      <td>✅ OK</td>
    </tr>`;
  }

  // Area totale
  if (stats.combined) {
    rows += `<tr data-type="green-dots">
      <td>🟢 Area Totale</td>
      <td>${stats.combined.total_area.toFixed(1)}</td>
      <td>px²</td>
      <td>✅ OK</td>
    </tr>`;
  }

  // === ANALISI SIMMETRIA ===
  const symmetryRows = generateSymmetryAnalysisRows(result);
  rows += symmetryRows;

  // Punti totali rilevati
  if (result.detection_results) {
    rows += `<tr data-type="green-dots">
      <td>🟢 Punti Rilevati</td>
      <td>${result.detection_results.total_dots}</td>
      <td>pz</td>
      <td>✅ OK</td>
    </tr>`;
  }

  return rows;
}

function analyzeEyebrowDesignFromGreenDotsTable() {
  /**
   * Analizza i dati green dots dalla tabella misurazioni e genera un feedback vocale
   * descrivendo le differenze tra i due sopraccigli.
   */
  console.log('📊 [FEEDBACK VOCALE] Analisi dati tabella green dots');

  const measurementsTable = document.getElementById('measurements-data');
  if (!measurementsTable) {
    console.error('❌ [FEEDBACK VOCALE] Tabella misurazioni non trovata');
    return null;
  }

  const rows = measurementsTable.querySelectorAll('tr[data-type="green-dots"]');
  if (rows.length === 0) {
    console.error('❌ [FEEDBACK VOCALE] Nessun dato green dots trovato');
    return null;
  }

  console.log(`📋 [FEEDBACK VOCALE] Trovate ${rows.length} righe di dati green dots`);

  // Estrai i dati rilevanti
  let externalEyebrow = null; // Quale sopracciglio inizia più esternamente (punto A più lontano dall'asse)
  let higherEyebrow = null; // Quale sopracciglio è più alto (punto C1)
  let longerTail = null; // Quale ha la coda più lunga (punto B)
  let thickerEyebrow = null; // Quale è più spesso (area)

  rows.forEach(row => {
    const cells = row.querySelectorAll('td');
    if (cells.length < 2) return;

    const label = cells[0].textContent.trim();
    const value = cells[1].textContent.trim();

    console.log(`   📝 [FEEDBACK VOCALE] ${label}: ${value}`);

    // Analisi punto A (distanza dall'asse) - Il punto PIÙ LONTANO inizia più esternamente
    if (label.includes('LA vs RA') && label.includes('Distanza Asse')) {
      if (value.includes('LA più esterno')) {
        externalEyebrow = 'sinistro';
      } else if (value.includes('RA più esterno')) {
        externalEyebrow = 'destro';
      }
    }

    // Analisi punto C1 (altezza)
    if (label.includes('LC1 vs RC1') && label.includes('Altezza')) {
      if (value.includes('LC1')) {
        higherEyebrow = 'sinistro';
      } else if (value.includes('RC1')) {
        higherEyebrow = 'destro';
      }
    }

    // Analisi punto B (coda più lunga) - Il punto PIÙ LONTANO dall'asse ha la coda più lunga
    if (label.includes('LB vs RB') && label.includes('Distanza Asse')) {
      if (value.includes('LB più esterno')) {
        longerTail = 'sinistro';
      } else if (value.includes('RB più esterno')) {
        longerTail = 'destro';
      }
    }

    // Analisi area (spessore)
    if ((label.includes('Poligono Sinistro') || label.includes('Poligono Destro')) && value.includes('MAGGIORE')) {
      if (label.includes('Sinistro')) {
        thickerEyebrow = 'sinistro';
      } else if (label.includes('Destro')) {
        thickerEyebrow = 'destro';
      }
    }
  });

  console.log('🔍 [FEEDBACK VOCALE] Risultati analisi:', {
    externalEyebrow,
    higherEyebrow,
    longerTail,
    thickerEyebrow
  });

  // Genera il feedback testuale
  if (!externalEyebrow && !higherEyebrow && !longerTail && !thickerEyebrow) {
    console.warn('⚠️ [FEEDBACK VOCALE] Nessun dato disponibile per generare feedback');
    return null;
  }

  // Costruisci la frase seguendo esattamente il formato richiesto
  let feedback = '';

  // 1. Quale sopracciglio inizia più esternamente (punto A più lontano dall'asse)
  if (externalEyebrow === 'destro') {
    feedback += 'Il sopracciglio alla tua destra inizia più esternamente. ';
  } else if (externalEyebrow === 'sinistro') {
    feedback += 'Il sopracciglio alla tua sinistra inizia più esternamente. ';
  }

  // 2. Quale sopracciglio è più alto (C1)
  if (higherEyebrow === 'sinistro') {
    feedback += 'Il sopracciglio alla tua sinistra è più alto rispetto all\'altro. ';
  } else if (higherEyebrow === 'destro') {
    feedback += 'Il sopracciglio alla tua destra è più alto rispetto all\'altro. ';
  }

  // 3. Quale ha la coda più lunga (B)
  if (longerTail === 'sinistro') {
    feedback += 'La coda del sopracciglio alla tua sinistra è più lunga. ';
  } else if (longerTail === 'destro') {
    feedback += 'La coda del sopracciglio alla tua destra è più lunga. ';
  }

  // 4. Quale è più spesso (area)
  if (thickerEyebrow === 'sinistro') {
    feedback += 'Ed infine il sopracciglio sinistro è più spesso.';
  } else if (thickerEyebrow === 'destro') {
    feedback += 'Ed infine il sopracciglio destro è più spesso.';
  }

  console.log('✅ [FEEDBACK VOCALE] Feedback generato:', feedback);
  return feedback || null;
}

function analyzeEyebrowDesignFromData(greenDotsData) {
  /**
   * Genera il feedback vocale leggendo direttamente dalla struttura dati JSON,
   * senza fare parsing del DOM. Sostituisce analyzeEyebrowDesignFromGreenDotsTable().
   *
   * Struttura attesa in greenDotsData:
   *   statistics.left.area, statistics.right.area
   *   coordinates.Sx[idx], coordinates.Dx[idx]  — in coordinate immagine originale
   *   Indici: 0=C1, 1=A0, 2=A, 3=C, 4=B  (Sx) / 0=RC1, 1=RB, 2=RC, 3=RA, 4=RA0  (Dx)
   */
  console.log('📊 [FEEDBACK VOCALE] Analisi da dati JSON green dots');

  if (!greenDotsData || !greenDotsData.success) {
    console.warn('⚠️ [FEEDBACK VOCALE] Dati non validi o assenti');
    return null;
  }

  let externalEyebrow = null; // quale sopracciglio inizia più esternamente (punto A)
  let higherEyebrow = null;   // quale sopracciglio è più alto (punto C1)
  let longerTail = null;      // quale ha la coda più lunga (punto B)
  let thickerEyebrow = null;  // quale è più spesso (area)

  // === Analisi area (spessore) ===
  const stats = greenDotsData.statistics;
  if (stats && stats.left && stats.right) {
    const leftArea = stats.left.area || 0;
    const rightArea = stats.right.area || 0;
    if (leftArea !== rightArea) {
      thickerEyebrow = leftArea > rightArea ? 'sinistro' : 'destro';
    }
  }

  // === Analisi coordinate (punto A, B, C1) ===
  const coords = greenDotsData.coordinates;
  if (coords && coords.Sx && coords.Dx) {
    const sx = coords.Sx; // [LC1, LA0, LA, LC, LB]
    const dx = coords.Dx; // [RC1, RB, RC, RA, RA0]

    // Asse di simmetria: necessario per calcolare distanze
    const axisData = getSymmetryAxisPosition();
    if (axisData && axisData.lineOriginal) {
      const axis = axisData.lineOriginal;

      // Punto A (indice 2 in Sx = LA, indice 3 in Dx = RA) — più lontano = più esterno
      if (sx[2] && dx[3]) {
        const distLA = typeof getPerpendicularDistanceFromLine === 'function'
          ? getPerpendicularDistanceFromLine(sx[2][0], sx[2][1], axis)
          : Math.abs(sx[2][0] - axisData.x);
        const distRA = typeof getPerpendicularDistanceFromLine === 'function'
          ? getPerpendicularDistanceFromLine(dx[3][0], dx[3][1], axis)
          : Math.abs(dx[3][0] - axisData.x);
        if (Math.abs(distLA - distRA) > 1) {
          externalEyebrow = distLA > distRA ? 'sinistro' : 'destro';
        }
      }

      // Punto C1 (indice 0 in Sx = LC1, indice 0 in Dx = RC1) — y più bassa = più in alto
      if (sx[0] && dx[0]) {
        const heightLA = typeof getProjectionAlongLine === 'function'
          ? getProjectionAlongLine(sx[0][0], sx[0][1], axis)
          : sx[0][1];
        const heightRA = typeof getProjectionAlongLine === 'function'
          ? getProjectionAlongLine(dx[0][0], dx[0][1], axis)
          : dx[0][1];
        if (Math.abs(heightLA - heightRA) > 1) {
          higherEyebrow = heightLA < heightRA ? 'sinistro' : 'destro';
        }
      }

      // Punto B (indice 4 in Sx = LB, indice 1 in Dx = RB) — più lontano = coda più lunga
      if (sx[4] && dx[1]) {
        const distLB = typeof getPerpendicularDistanceFromLine === 'function'
          ? getPerpendicularDistanceFromLine(sx[4][0], sx[4][1], axis)
          : Math.abs(sx[4][0] - axisData.x);
        const distRB = typeof getPerpendicularDistanceFromLine === 'function'
          ? getPerpendicularDistanceFromLine(dx[1][0], dx[1][1], axis)
          : Math.abs(dx[1][0] - axisData.x);
        if (Math.abs(distLB - distRB) > 1) {
          longerTail = distLB > distRB ? 'sinistro' : 'destro';
        }
      }
    } else {
      console.warn('⚠️ [FEEDBACK VOCALE] Asse non disponibile, skip analisi coordinate');
    }
  }

  console.log('🔍 [FEEDBACK VOCALE] Risultati da dati JSON:', {
    externalEyebrow, higherEyebrow, longerTail, thickerEyebrow
  });

  if (!externalEyebrow && !higherEyebrow && !longerTail && !thickerEyebrow) {
    console.warn('⚠️ [FEEDBACK VOCALE] Nessun dato sufficiente per generare feedback');
    return null;
  }

  let feedback = '';

  if (externalEyebrow === 'destro') {
    feedback += 'Il sopracciglio alla tua destra inizia più esternamente. ';
  } else if (externalEyebrow === 'sinistro') {
    feedback += 'Il sopracciglio alla tua sinistra inizia più esternamente. ';
  }

  if (higherEyebrow === 'sinistro') {
    feedback += 'Il sopracciglio alla tua sinistra è più alto rispetto all\'altro. ';
  } else if (higherEyebrow === 'destro') {
    feedback += 'Il sopracciglio alla tua destra è più alto rispetto all\'altro. ';
  }

  if (longerTail === 'sinistro') {
    feedback += 'La coda del sopracciglio alla tua sinistra è più lunga. ';
  } else if (longerTail === 'destro') {
    feedback += 'La coda del sopracciglio alla tua destra è più lunga. ';
  }

  if (thickerEyebrow === 'sinistro') {
    feedback += 'Ed infine il sopracciglio sinistro è più spesso.';
  } else if (thickerEyebrow === 'destro') {
    feedback += 'Ed infine il sopracciglio destro è più spesso.';
  }

  console.log('✅ [FEEDBACK VOCALE] Feedback generato da dati JSON:', feedback);
  return feedback || null;
}

function generateSymmetryAnalysisRows(result) {
  /**
   * Genera le righe della tabella per l'analisi di simmetria dei punti green dots.
   */
  let rows = '';

  // Verifica che ci siano i dati necessari
  if (!result.coordinates || !result.coordinates.Sx || !result.coordinates.Dx) {
    console.warn('⚠️ Coordinate non disponibili per analisi simmetria');
    return '';
  }

  // Ottieni l'asse di simmetria (dovrebbe essere già stato attivato all'inizio di detectGreenDots)
  const symmetryAxisData = getSymmetryAxisPosition();

  // DEBUG: Verifica stato landmarks
  if (window.DEBUG_MODE) {
    console.log('🔍 [SIMMETRIA DEBUG] Stato currentLandmarks:', {
      exists: !!currentLandmarks,
      length: currentLandmarks ? currentLandmarks.length : 0,
      hasLandmark9: currentLandmarks && currentLandmarks[9] ? 'SI' : 'NO',
      hasLandmark164: currentLandmarks && currentLandmarks[164] ? 'SI' : 'NO'
    });
  }

  // Se l'asse non è disponibile, significa che non è stato possibile generarlo
  if (!symmetryAxisData) {
    // Verifica se l'asse è attivo visivamente ma i landmarks non sono disponibili
    const axisBtn = document.getElementById('axis-btn');
    const isAxisActive = axisBtn && axisBtn.classList.contains('active');

    console.warn('⚠️ [SIMMETRIA] Asse non disponibile - impossibile calcolare distanze');
    console.warn(`   Asse BTN attivo: ${isAxisActive}, Landmarks disponibili: ${currentLandmarks && currentLandmarks.length > 0}`);

    // Messaggio più chiaro basato sullo stato
    const message = isAxisActive
      ? 'Asse simmetria attivo ma landmarks non disponibili (prova a riattivare l\'asse)'
      : 'Asse simmetria non rilevato (richiede volto frontale)';

    rows += `<tr data-type="green-dots" style="background: #fff3cd;">
      <td>⚖️ Simmetria</td>
      <td>${message}</td>
      <td>-</td>
      <td>ℹ️ Info</td>
    </tr>`;
    return rows;
  }

  console.log(`⚖️ generateSymmetryAnalysisRows: Asse X = ${symmetryAxisData.x.toFixed(1)}, Linea: (${symmetryAxisData.line.x1.toFixed(1)},${symmetryAxisData.line.y1}) → (${symmetryAxisData.line.x2.toFixed(1)},${symmetryAxisData.line.y2})`);
  console.log(`   Linea in coordinate IMMAGINE ORIGINALE: (${symmetryAxisData.lineOriginal.x1.toFixed(1)},${symmetryAxisData.lineOriginal.y1}) → (${symmetryAxisData.lineOriginal.x2.toFixed(1)},${symmetryAxisData.lineOriginal.y2})`);

  const leftPoints = result.coordinates.Sx; // Coordinate [(x,y), ...] in coordinate IMMAGINE ORIGINALE
  const rightPoints = result.coordinates.Dx;

  console.log('📍 COORDINATE GREEN DOTS (immagine originale):');
  console.log('   Sx (sinistro):', leftPoints);
  console.log('   Dx (destro):', rightPoints);

  // Mapping degli indici ai nomi delle etichette
  const leftLabels = ["LC1", "LA0", "LA", "LC", "LB"];
  const rightLabels = ["RC1", "RB", "RC", "RA", "RA0"];

  // Coppie da confrontare (indice sinistro, indice destro, nome confronto)
  const comparisons = [
    [1, 4, "LA0 vs RA0"], // LA0 (indice 1) vs RA0 (indice 4)  
    [2, 3, "LA vs RA"],   // LA (indice 2) vs RA (indice 3)
    [0, 0, "LC1 vs RC1"], // LC1 (indice 0) vs RC1 (indice 0)
    [4, 1, "LB vs RB"],   // LB (indice 4) vs RB (indice 1)
    [3, 2, "LC vs RC"]    // LC (indice 3) vs RC (indice 2)
  ];

  comparisons.forEach(([leftIdx, rightIdx, comparisonName]) => {
    if (leftIdx < leftPoints.length && rightIdx < rightPoints.length) {
      const leftPoint = leftPoints[leftIdx];
      const rightPoint = rightPoints[rightIdx];

      // Calcola distanze PERPENDICOLARI dall'asse usando coordinate immagine originale
      const leftDistance = getPerpendicularDistanceFromLine(leftPoint[0], leftPoint[1], symmetryAxisData.lineOriginal);
      const rightDistance = getPerpendicularDistanceFromLine(rightPoint[0], rightPoint[1], symmetryAxisData.lineOriginal);

      const fartherPoint = leftDistance > rightDistance ? leftLabels[leftIdx] : rightLabels[rightIdx];
      const closerPoint = leftDistance > rightDistance ? rightLabels[rightIdx] : leftLabels[leftIdx];
      const maxDistance = Math.max(leftDistance, rightDistance);
      const minDistance = Math.min(leftDistance, rightDistance);
      const distanceDifference = Math.abs(leftDistance - rightDistance);

      // Calcola altezze (proiezione lungo l'asse) - valori Y più BASSI = più in alto
      const leftHeight = getProjectionAlongLine(leftPoint[0], leftPoint[1], symmetryAxisData.lineOriginal);
      const rightHeight = getProjectionAlongLine(rightPoint[0], rightPoint[1], symmetryAxisData.lineOriginal);

      const higherPoint = leftHeight < rightHeight ? leftLabels[leftIdx] : rightLabels[rightIdx];
      const lowerPoint = leftHeight < rightHeight ? rightLabels[rightIdx] : leftLabels[leftIdx];
      const heightDifference = Math.abs(leftHeight - rightHeight);

      // Determina direzione frecce: ↔ per distanza orizzontale, ↕ per altezza
      const horizontalArrow = leftDistance > rightDistance ? '←' : '→'; // Freccia verso il più esterno
      const verticalArrow = leftHeight < rightHeight ? '↑' : '↓'; // Freccia verso il più alto

      console.log(`  📊 ${comparisonName}: L=${leftLabels[leftIdx]}(${leftPoint[0].toFixed(1)},${leftPoint[1].toFixed(1)}, dist⊥=${leftDistance.toFixed(1)}, h=${leftHeight.toFixed(1)}) vs R=${rightLabels[rightIdx]}(${rightPoint[0].toFixed(1)},${rightPoint[1].toFixed(1)}, dist⊥=${rightDistance.toFixed(1)}, h=${rightHeight.toFixed(1)}) → 🔴 ${fartherPoint} più lontano, ⬆️ ${higherPoint} più alto (diff=${heightDifference.toFixed(1)}px)`);

      // Prepara dati per highlight interattivo
      const pairData = JSON.stringify({
        leftLabel: leftLabels[leftIdx],
        rightLabel: rightLabels[rightIdx],
        leftPoint: leftPoint,
        rightPoint: rightPoint,
        leftIdx: leftIdx,
        rightIdx: rightIdx,
        fartherPoint: fartherPoint,
        closerPoint: closerPoint,
        higherPoint: higherPoint,
        lowerPoint: lowerPoint,
        distanceDiff: distanceDifference,
        heightDiff: heightDifference
      }).replace(/"/g, '&quot;');

      // Riga distanza dall'asse - CLICCABILE per evidenziare la coppia
      rows += `<tr data-type="green-dots" class="point-pair-row" data-pair='${pairData}'
               onclick="highlightPointPair(this)" style="cursor: pointer;">
        <td>⚖️ ${comparisonName}</td>
        <td>
          <span style="color: #00bcd4;">${leftLabels[leftIdx]}</span>: ${leftDistance.toFixed(1)}px ${horizontalArrow}
          <span style="color: #ff9800;">${rightLabels[rightIdx]}</span>: ${rightDistance.toFixed(1)}px<br/>
          <small><strong>🔴 ${fartherPoint}</strong> più esterno (+${distanceDifference.toFixed(1)}px) |
          <strong>⬆️ ${higherPoint}</strong> più alto (+${heightDifference.toFixed(1)}px)</small>
        </td>
        <td>px</td>
        <td><span class="highlight-indicator">👆</span></td>
      </tr>`;
    } else {
      rows += `<tr data-type="green-dots">
        <td>⚖️ ${comparisonName}</td>
        <td>Punti mancanti</td>
        <td>-</td>
        <td>❌ Errore</td>
      </tr>`;
    }
  });

  return rows;
}

function generateGreenDotsMeasurementsHTML(result) {
  /**
   * Genera l'HTML per visualizzare le misurazioni dei green dots con aree e confronti.
   */
  let html = '<h4>🟢 Analisi Green Dots</h4>';

  // Aree poligoni con evidenziazione del maggiore
  if (result.statistics && result.statistics.left && result.statistics.right) {
    const leftArea = result.statistics.left.area;
    const rightArea = result.statistics.right.area;
    const largerArea = leftArea > rightArea ? 'left' : 'right';

    html += '<div class="measurement-group">';
    html += '<h5>� Aree Poligoni</h5>';

    html += `<div class="measurement-item ${largerArea === 'left' ? 'highlighted' : ''}">
      <span class="measurement-label">Area Sinistra:</span>
      <span class="measurement-value">${leftArea.toFixed(1)} px²</span>
      ${largerArea === 'left' ? '<span class="highlight-badge">MAGGIORE</span>' : ''}
    </div>`;

    html += `<div class="measurement-item ${largerArea === 'right' ? 'highlighted' : ''}">
      <span class="measurement-label">Area Destra:</span>
      <span class="measurement-value">${rightArea.toFixed(1)} px²</span>
      ${largerArea === 'right' ? '<span class="highlight-badge">MAGGIORE</span>' : ''}
    </div>`;

    html += `<div class="measurement-item">
      <span class="measurement-label">Differenza:</span>
      <span class="measurement-value">${Math.abs(leftArea - rightArea).toFixed(1)} px²</span>
    </div>`;

    html += '</div>';
  }

  // Debug dei dati ricevuti
  console.log('🔍 DEBUG generateGreenDotsMeasurementsHTML - dati completi:', result);
  console.log('🔍 DEBUG coordinates object:', result.coordinates);
  console.log('🔍 DEBUG Sx coordinates:', result.coordinates?.Sx);
  console.log('🔍 DEBUG Dx coordinates:', result.coordinates?.Dx);

  // Confronti distanze dall'asse di simmetria
  html += generateSymmetryAnalysis(result);

  // Statistiche generali
  html += '<div class="measurement-group">';
  html += '<h5>� Statistiche Generali</h5>';
  html += `<div class="measurement-item">
    <span class="measurement-label">Puntini Totali:</span>
    <span class="measurement-value">${result.detection_results.total_dots}</span>
  </div>`;
  html += `<div class="measurement-item">
    <span class="measurement-label">Pixel Verdi:</span>
    <span class="measurement-value">${result.detection_results.total_green_pixels}</span>
  </div>`;
  html += '</div>';

  return html;
}

function generateSymmetryAnalysis(result) {
  /**
   * Genera l'analisi delle distanze dall'asse di simmetria per coppie di punti.
   */
  let html = '<div class="measurement-group">';
  html += '<h5>⚖️ Analisi Simmetria</h5>';

  console.log('🔍 DEBUG generateSymmetryAnalysis:', {
    result: result,
    coordinates: result?.coordinates,
    Sx: result?.coordinates?.Sx,
    Dx: result?.coordinates?.Dx
  });

  // Ottieni l'asse di simmetria se disponibile
  const symmetryAxisData = getSymmetryAxisPosition();

  console.log('🔍 DEBUG symmetryAxis:', symmetryAxisData);
  console.log('🔍 DEBUG currentLandmarks:', currentLandmarks);
  console.log('🔍 DEBUG currentImage:', currentImage);
  console.log('🔍 DEBUG window.imageScale:', window.imageScale);
  console.log('🔍 DEBUG window.imageOffset:', window.imageOffset);

  if (!symmetryAxisData || !result.coordinates || !result.coordinates.Sx || !result.coordinates.Dx) {
    html += '<div class="measurement-item">';
    html += '<span class="measurement-label">⚠️ Dati insufficienti per analisi simmetria</span>';
    html += '<span class="measurement-value">Asse: ' + (symmetryAxisData ? symmetryAxisData.x : 'N/A') + ', Coords: ' + (result.coordinates ? 'SI' : 'NO') + '</span>';
    html += '</div>';
    html += '</div>';
    return html;
  }

  const leftPoints = result.coordinates.Sx; // Coordinate [(x,y), ...]
  const rightPoints = result.coordinates.Dx;

  // Mapping degli indici ai nomi delle etichette
  const leftLabels = ["LC1", "LA0", "LA", "LC", "LB"];
  const rightLabels = ["RC1", "RB", "RC", "RA", "RA0"];

  // Coppie da confrontare (indice sinistro, indice destro, nome confronto)
  const comparisons = [
    [1, 4, "LA0 vs RA0"], // LA0 (indice 1) vs RA0 (indice 4)  
    [2, 3, "LA vs RA"],   // LA (indice 2) vs RA (indice 3)
    [0, 0, "LC1 vs RC1"], // LC1 (indice 0) vs RC1 (indice 0)
    [4, 1, "LB vs RB"],   // LB (indice 4) vs RB (indice 1)
    [3, 2, "LC vs RC"]    // LC (indice 3) vs RC (indice 2)
  ];

  comparisons.forEach(([leftIdx, rightIdx, comparisonName]) => {
    if (leftIdx < leftPoints.length && rightIdx < rightPoints.length) {
      const leftPoint = leftPoints[leftIdx];
      const rightPoint = rightPoints[rightIdx];

      // Calcola distanze PERPENDICOLARI dall'asse usando coordinate immagine originale
      const leftDistance = getPerpendicularDistanceFromLine(leftPoint[0], leftPoint[1], symmetryAxisData.lineOriginal);
      const rightDistance = getPerpendicularDistanceFromLine(rightPoint[0], rightPoint[1], symmetryAxisData.lineOriginal);

      const fartherPoint = leftDistance > rightDistance ? leftLabels[leftIdx] : rightLabels[rightIdx];
      const maxDistance = Math.max(leftDistance, rightDistance);

      // Calcola altezze
      const leftHeight = getProjectionAlongLine(leftPoint[0], leftPoint[1], symmetryAxisData.lineOriginal);
      const rightHeight = getProjectionAlongLine(rightPoint[0], rightPoint[1], symmetryAxisData.lineOriginal);

      const higherPoint = leftHeight < rightHeight ? leftLabels[leftIdx] : rightLabels[rightIdx];
      const heightDifference = Math.abs(leftHeight - rightHeight);

      html += `<div class="measurement-item">
        <span class="measurement-label">${comparisonName} Distanza:</span>
        <span class="measurement-value">
          <strong class="farther-point">${fartherPoint}</strong> 
          (${maxDistance.toFixed(1)} px)
        </span>
      </div>`;

      html += `<div class="measurement-item">
        <span class="measurement-label">${comparisonName} Altezza:</span>
        <span class="measurement-value">
          <strong class="higher-point">⬆️ ${higherPoint}</strong> 
          (${heightDifference.toFixed(1)} px)
        </span>
      </div>`;
    }
  });

  html += '</div>';
  return html;
}

function getSymmetryAxisPosition() {
  /**
   * Ottiene la posizione X dell'asse di simmetria calcolato con landmarks 9 e 164.
   * Questa è la STESSA logica usata in drawSymmetryAxis().
   */
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.warn('⚠️ getSymmetryAxisPosition: Nessun landmark disponibile');
    return null;
  }

  // Verifica landmarks necessari (STESSI usati per disegnare l'asse)
  if (currentLandmarks.length <= 164 || !currentLandmarks[9] || !currentLandmarks[164]) {
    console.warn('⚠️ getSymmetryAxisPosition: Landmarks 9 o 164 non disponibili');
    return null;
  }

  // Landmark MediaPipe: Glabella (9) e Philtrum (164)
  const glabella = currentLandmarks[9];
  const philtrum = currentLandmarks[164];

  // Trasforma le coordinate usando la stessa logica del disegno
  const transformedGlabella = transformLandmarkCoordinate(glabella);
  const transformedPhiltrum = transformLandmarkCoordinate(philtrum);

  console.log(`🔬 DETTAGLI CALCOLO ASSE:`);
  console.log(`   Glabella (9) normalizzato: x=${glabella.x.toFixed(3)}, y=${glabella.y.toFixed(3)}`);
  console.log(`   Philtrum (164) normalizzato: x=${philtrum.x.toFixed(3)}, y=${philtrum.y.toFixed(3)}`);
  console.log(`   Glabella trasformato: x=${transformedGlabella.x.toFixed(1)}, y=${transformedGlabella.y.toFixed(1)}`);
  console.log(`   Philtrum trasformato: x=${transformedPhiltrum.x.toFixed(1)}, y=${transformedPhiltrum.y.toFixed(1)}`);

  // Calcola la direzione della linea (stessa logica di drawSymmetryAxis)
  const dx = transformedPhiltrum.x - transformedGlabella.x;
  const dy = transformedPhiltrum.y - transformedGlabella.y;

  // Estendi la linea per tutta l'altezza del canvas
  const canvasHeight = fabricCanvas ? fabricCanvas.getHeight() : 1000;

  let topX, topY, bottomX, bottomY;

  if (Math.abs(dy) > 0.1) {
    // Punto in alto (y=0)
    topX = transformedGlabella.x - (transformedGlabella.y * dx / dy);
    topY = 0;
    // Punto in basso (y=canvasHeight)
    bottomX = transformedGlabella.x + ((canvasHeight - transformedGlabella.y) * dx / dy);
    bottomY = canvasHeight;
  } else {
    // Linea verticale
    topX = bottomX = transformedGlabella.x;
    topY = 0;
    bottomY = canvasHeight;
  }

  const axisX = (transformedGlabella.x + transformedPhiltrum.x) / 2;

  console.log(`📏 getSymmetryAxisPosition: X = ${axisX.toFixed(1)} (media di ${transformedGlabella.x.toFixed(1)} e ${transformedPhiltrum.x.toFixed(1)})`);
  console.log(`   Linea estesa CANVAS: da (${topX.toFixed(1)}, ${topY}) a (${bottomX.toFixed(1)}, ${bottomY})`);

  // CONVERSIONE INVERSA: Converti l'asse dalle coordinate canvas alle coordinate immagine originale
  // Formula inversa: originalX = (canvasX - offsetX) / scale
  const scale = window.imageScale || 1;
  const offsetX = window.imageOffset ? window.imageOffset.x : 0;
  const offsetY = window.imageOffset ? window.imageOffset.y : 0;

  // Altezza immagine originale (stimata dai green dots che sono ~400px max)
  const originalImageHeight = currentImage ? currentImage.height : 832;

  // Converti i punti della linea in coordinate immagine originale
  const topX_orig = (topX - offsetX) / scale;
  const topY_orig = 0; // Top dell'immagine
  const bottomX_orig = (bottomX - offsetX) / scale;
  const bottomY_orig = originalImageHeight;

  console.log(`   Linea estesa IMMAGINE ORIGINALE: da (${topX_orig.toFixed(1)}, ${topY_orig}) a (${bottomX_orig.toFixed(1)}, ${bottomY_orig})`);
  console.log(`   Scale: ${scale.toFixed(3)}, Offset: (${offsetX.toFixed(1)}, ${offsetY.toFixed(1)})`);
  console.log(`✅ ASSE CALCOLATO CON LANDMARKS 9 (glabella) & 164 (philtrum) - NON landmark 1 (naso)!`);

  // Restituisce sia coordinate canvas che coordinate immagine originale
  return {
    x: axisX,
    line: { x1: topX, y1: topY, x2: bottomX, y2: bottomY },
    lineOriginal: { x1: topX_orig, y1: topY_orig, x2: bottomX_orig, y2: bottomY_orig }
  };
}

function getPerpendicularDistanceFromLine(pointX, pointY, line) {
  /**
   * Calcola la distanza perpendicolare di un punto da una linea.
   * Formula: |((x2-x1)(y1-y0) - (x1-x0)(y2-y1))| / sqrt((x2-x1)^2 + (y2-y1)^2)
   * Dove (x0,y0) è il punto e la linea va da (x1,y1) a (x2,y2)
   */
  const { x1, y1, x2, y2 } = line;

  const numerator = Math.abs((x2 - x1) * (y1 - pointY) - (x1 - pointX) * (y2 - y1));
  const denominator = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));

  const distance = numerator / denominator;

  console.log(`    🔍 Distanza⊥ punto (${pointX.toFixed(1)},${pointY.toFixed(1)}) da linea [(${x1.toFixed(1)},${y1})→(${x2.toFixed(1)},${y2})]: ${distance.toFixed(2)}px`);

  return distance;
}

function getProjectionAlongLine(pointX, pointY, line) {
  /**
   * Calcola la proiezione di un punto lungo la linea (coordinate parametrica t).
   * Questo determina la "posizione verticale" del punto lungo l'asse di simmetria.
   * Valori più BASSI = più in alto (verso y1), valori più ALTI = più in basso (verso y2)
   * 
   * Formula: t = ((P-A)·(B-A)) / |B-A|²
   * dove A=(x1,y1), B=(x2,y2), P=(pointX,pointY)
   */
  const { x1, y1, x2, y2 } = line;

  // Vettore dalla linea al punto
  const dx = x2 - x1;
  const dy = y2 - y1;

  // Proiezione scalare
  const dotProduct = (pointX - x1) * dx + (pointY - y1) * dy;
  const lineLengthSquared = dx * dx + dy * dy;

  const t = dotProduct / lineLengthSquared;

  // Calcola la coordinata Y proiettata per il log
  const projectedY = y1 + t * dy;

  console.log(`    📐 Proiezione punto (${pointX.toFixed(1)},${pointY.toFixed(1)}) su linea: t=${t.toFixed(3)} → Y_proj=${projectedY.toFixed(1)} (più alto = Y minore)`);

  return projectedY; // Restituisce la Y proiettata (più basso = più in basso nell'immagine)
}

function clearGreenDots(preserveMovement = false) {
  /**
   * Rimuove tutti gli elementi relativi ai green dots dal canvas.
   * @param {boolean} preserveMovement - Se true, non disabilita il movimento dell'immagine
   */
  if (fabricCanvas) {
    const elementsToRemove = fabricCanvas.getObjects().filter(obj =>
      obj.isGreenDot || obj.isGreenDotsOverlay || obj.isGreenDotsGroup
    );
    elementsToRemove.forEach(element => fabricCanvas.remove(element));

    // Pulisci riferimenti globali
    window.currentGreenDotsOverlay = null;

    // Disabilita il movimento dell'immagine solo se richiesto esplicitamente
    if (!preserveMovement) {
      disableImageMovement();
    }

    fabricCanvas.renderAll();
    console.log(`🧹 Rimossi ${elementsToRemove.length} elementi green dots dal canvas`);
  }
}

function toggleAxis() {
  /**
   * Gestisce il toggle del pulsante ASSE nella sezione RILEVAMENTI.
   * Replica esattamente canvas_app.py:toggle_asse_section()
   */
  const btn = document.getElementById('axis-btn');
  btn.classList.toggle('active');

  const isActive = btn.classList.contains('active');

  // IMPORTANTE: Imposta la variabile globale per la rotazione
  window.symmetryAxisVisible = isActive;

  if (isActive) {
    if (!currentLandmarks) {
      // Se non ci sono landmarks, calcola l'asse automaticamente
      calculateAxis();
    } else {
      // Disegna l'asse di simmetria
      drawSymmetryAxis();
    }
  } else {
    // Rimuovi l'asse di simmetria
    clearSymmetryAxis();
  }

  updateStatus(isActive ? 'Asse di simmetria attivo' : 'Asse di simmetria disattivo');
}

function calculateAxis() {
  /**
   * Calcola e mostra l'asse di simmetria facciale.
   * Replica esattamente canvas_app.py:calculate_axis()
   */
  if (!currentImage) {
    showToast('Nessuna immagine caricata', 'warning');
    return;
  }

  // Prima rileva i landmarks se non esistono
  if (!currentLandmarks) {
    detectLandmarks().then(() => {
      if (currentLandmarks) {
        // Attiva la visualizzazione dell'asse
        document.getElementById('axis-btn').classList.add('active');
        updateCanvasDisplay();
        updateStatus('Asse di simmetria calcolato');
      } else {
        showToast('Impossibile rilevare landmarks per calcolare l\'asse', 'warning');
      }
    });
  } else {
    // Attiva la visualizzazione dell'asse
    document.getElementById('axis-btn').classList.add('active');
    updateCanvasDisplay();
    updateStatus('Asse di simmetria calcolato');
  }
}

// Variabile globale per modalità selezione landmarks
window.landmarkSelectionMode = false;
window.selectedLandmarksForTable = [];

// Variabili globali per il sistema di misurazione
window.measurementMode = false;
window.selectedLandmarksForMeasurement = []; // Array di {id, x, y, name}
window.measurementResults = []; // Array di risultati di misurazione

function toggleLandmarks() {
  /**
   * Gestisce il toggle del pulsante LANDMARKS nella sezione RILEVAMENTI.
   * Replica esattamente canvas_app.py:toggle_landmarks_section()
   */
  console.log('🔥 TOGGLE LANDMARKS CHIAMATA! 🔥');

  const btn = document.getElementById('landmarks-btn');
  if (!btn) {
    console.error('❌ Pulsante landmarks-btn non trovato!');
    return;
  }

  btn.classList.toggle('active');
  const isActive = btn.classList.contains('active');

  // Aggiorna variabile globale - FORZA il valore
  window.landmarksVisible = isActive;
  if (typeof landmarksVisible !== 'undefined') {
    landmarksVisible = isActive;
  }

  console.log('🎯 Toggle Landmarks:', {
    active: isActive,
    visible: window.landmarksVisible,
    hasCurrentLandmarks: !!currentLandmarks,
    landmarksCount: currentLandmarks?.length || 0
  });

  if (isActive) {
    // Attiva modalità selezione landmarks
    window.landmarkSelectionMode = true;
    console.log('🖱️ Modalità selezione landmarks ATTIVA - clicca sui landmarks per aggiungerli alla tabella');

    // NON impostare cursore globale - i landmarks gestiranno il proprio hover
    // Il cursore diventerà "pointer" solo quando si passa sopra un landmark
    if (fabricCanvas) {
      fabricCanvas.defaultCursor = 'default'; // Cursore normale
      fabricCanvas.renderAll();
      console.log('👆 Cursore base impostato a DEFAULT - diventerà POINTER solo sopra i landmarks');
    }

    if (!currentLandmarks || currentLandmarks.length === 0) {
      // Se non ci sono landmarks, rilevali automaticamente
      console.log('🔍 Rilevamento landmarks necessario');
      detectLandmarks();
    } else {
      // IMPORTANTE: Ridisegna i landmarks per renderli cliccabili
      console.log('✅ Landmarks disponibili, ridisegno per renderli cliccabili');
      if (typeof window.drawMediaPipeLandmarks === 'function') {
        window.drawMediaPipeLandmarks(currentLandmarks);
      } else {
        console.warn('⚠️ drawMediaPipeLandmarks non disponibile');
      }
    }
  } else {
    // Disattiva modalità selezione landmarks
    window.landmarkSelectionMode = false;
    console.log('🖱️ Modalità selezione landmarks DISATTIVATA');

    // Ripristina cursore default
    if (fabricCanvas && !window.measurementMode) {
      fabricCanvas.defaultCursor = 'default';
      fabricCanvas.hoverCursor = 'move';
      fabricCanvas.renderAll();
      console.log('👆 Cursore ripristinato a DEFAULT');
    }

    // Nascondi landmarks
    console.log('❌ Nascondo landmarks');
    if (typeof window.clearLandmarks === 'function') {
      window.clearLandmarks();
    } else {
      // Fallback: rimuovi tutti i landmark objects
      if (fabricCanvas) {
        const landmarkObjects = fabricCanvas.getObjects().filter(obj => obj.isLandmark);
        landmarkObjects.forEach(obj => fabricCanvas.remove(obj));
        fabricCanvas.renderAll();
      }
    }
  }

  updateStatus(isActive ? 'Landmarks attivi - Clicca per selezionarli' : 'Landmarks disattivi');
}

// ============================================================================
// FUNZIONI PER SELEZIONE INTERATTIVA LANDMARKS
// ============================================================================

function handleLandmarkSelection(canvasX, canvasY) {
  /**
   * Gestisce il click sul canvas per selezionare un landmark
   * Trova il landmark più vicino e lo aggiunge alla tabella
   * IMPORTANTE: NO overlay grafici in questa modalità - solo tabella
   */
  if (!fabricCanvas) {
    console.warn('⚠️ fabricCanvas non disponibile');
    return;
  }

  // Trova il landmark più vicino usando gli oggetti già disegnati sul canvas
  const nearestLandmark = findNearestLandmarkOnCanvas(canvasX, canvasY);

  if (nearestLandmark && nearestLandmark.distance < 20) {  // Tolleranza 20px
    const landmarkId = nearestLandmark.landmarkIndex;
    const landmark = window.currentLandmarks[landmarkId];

    // Verifica se già selezionato
    if (window.selectedLandmarksForTable.includes(landmarkId)) {
      console.log(`⚠️ Landmark ${landmarkId} già nella tabella`);
      return;
    }

    addLandmarkToTable(landmarkId, landmark, false); // false = NO highlight grafico
    console.log(`✅ Landmark ${landmarkId} selezionato e aggiunto alla tabella`);
  } else {
    console.log('❌ Nessun landmark abbastanza vicino al click');
  }
}

function findNearestLandmarkOnCanvas(canvasX, canvasY) {
  /**
   * Trova il landmark più vicino alle coordinate canvas usando gli oggetti già disegnati
   * Ritorna: { landmarkIndex, distance, circle }
   */
  if (!fabricCanvas) return null;

  // Ottieni tutti gli oggetti landmark dal canvas
  const landmarkObjects = fabricCanvas.getObjects().filter(obj => obj.isLandmark && obj.landmarkType === 'mediapipe');

  if (landmarkObjects.length === 0) {
    console.warn('⚠️ Nessun landmark disegnato sul canvas');
    return null;
  }

  let nearestLandmark = null;
  let minDistance = Infinity;

  landmarkObjects.forEach((circle) => {
    // Il centro del cerchio è left + radius, top + radius
    const centerX = circle.left + circle.radius;
    const centerY = circle.top + circle.radius;

    // Calcola distanza euclidea dal click al centro del cerchio
    const dx = centerX - canvasX;
    const dy = centerY - canvasY;
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance < minDistance) {
      minDistance = distance;
      nearestLandmark = {
        landmarkIndex: circle.landmarkIndex,
        distance: distance,
        circle: circle,
        centerX: centerX,
        centerY: centerY
      };
    }
  });

  return nearestLandmark;
}

// Esponi la funzione globalmente per canvas-modes.js
window.handleLandmarkSelection = handleLandmarkSelection;

function addLandmarkToTable(landmarkId, landmark, showHighlight = false) {
  /**
   * Aggiunge un landmark alla tabella nella colonna destra
   * @param {number} landmarkId - ID del landmark
   * @param {object} landmark - Dati del landmark
   * @param {boolean} showHighlight - Se true, mostra cerchio colorato sul canvas (default: false)
   */
  // Verifica se già selezionato
  if (window.selectedLandmarksForTable.includes(landmarkId)) {
    console.log(`ℹ️ Landmark ${landmarkId} già nella tabella`);
    return;
  }

  window.selectedLandmarksForTable.push(landmarkId);

  const tbody = document.getElementById('landmarks-data');
  if (!tbody) {
    console.error('❌ Tabella landmarks-data non trovata');
    return;
  }

  // Nome del landmark (usa mapping se disponibile)
  const landmarkName = getLandmarkName(landmarkId);

  // Coordinate in pixel
  const imageWidth = window.currentImage?.width || 1;
  const imageHeight = window.currentImage?.height || 1;
  const pixelX = (landmark.x * imageWidth).toFixed(1);
  const pixelY = (landmark.y * imageHeight).toFixed(1);

  // Colore distintivo
  const hue = (landmarkId * 137) % 360;  // Golden angle per distribuzione uniforme
  const color = `hsl(${hue}, 70%, 50%)`;

  // Crea riga
  const row = document.createElement('tr');
  row.innerHTML = `
    <td><div style="width:12px;height:12px;background:${color};border-radius:50%;margin:auto;"></div></td>
    <td>${landmarkId}</td>
    <td>${landmarkName}</td>
    <td>${pixelX}</td>
    <td>${pixelY}</td>
  `;

  tbody.appendChild(row); // Aggiungi in fondo - poi verrà invertito da updateUnifiedTableForLandmarks

  // SOLO se richiesto esplicitamente, evidenzia il landmark sul canvas
  if (showHighlight) {
    highlightSelectedLandmark(landmarkId, color);
  }

  // Apri automaticamente la sezione LANDMARKS se era chiusa (vecchia - ora nascosta)
  openLandmarksSection();

  // Apri la sezione DATI ANALISI unificata e switcha al tab LANDMARKS
  openUnifiedAnalysisSection();
  switchUnifiedTab('landmarks', null, true); // Forza il passaggio e l'aggiornamento del tab landmarks

  console.log('🔄 [UNIFIED] Tab LANDMARKS attivato/aggiornato automaticamente');

  console.log(`📍 Landmark ${landmarkId} (${landmarkName}) aggiunto alla tabella${showHighlight ? ' con highlight' : ''}: (${pixelX}, ${pixelY})`);
}

function getLandmarkName(landmarkId) {
  /**
   * Ritorna il nome descrittivo del landmark MediaPipe Face Mesh (478 punti)
   * Basato sulla documentazione ufficiale: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
   */
  const landmarkNames = {
    // SILHOUETTE (Contorno viso)
    10: 'Face Top', 152: 'Chin Center', 234: 'Left Cheek', 454: 'Right Cheek',

    // LABBRA (Lips)
    0: 'Lip Top Center', 17: 'Lip Bottom Center',
    61: 'Lip Upper Left Outer', 291: 'Lip Upper Right Outer',
    39: 'Lip Upper Left Inner', 269: 'Lip Upper Right Inner',
    84: 'Lip Lower Left Outer', 314: 'Lip Lower Right Outer',
    78: 'Lip Lower Left Inner', 308: 'Lip Lower Right Inner',
    13: 'Lip Bottom Left', 14: 'Lip Bottom Right',
    37: 'Lip Top Left', 267: 'Lip Top Right',

    // OCCHIO SINISTRO (Left Eye)
    33: 'Left Eye Outer Corner', 133: 'Left Eye Inner Corner',
    160: 'Left Eye Top', 144: 'Left Eye Bottom',
    159: 'Left Eye Top Left', 145: 'Left Eye Bottom Left',
    158: 'Left Eye Top Right', 153: 'Left Eye Bottom Right',

    // OCCHIO DESTRO (Right Eye)
    362: 'Right Eye Outer Corner', 263: 'Right Eye Inner Corner',
    387: 'Right Eye Top', 373: 'Right Eye Bottom',
    386: 'Right Eye Top Left', 374: 'Right Eye Bottom Left',
    385: 'Right Eye Top Right', 380: 'Right Eye Bottom Right',

    // IRIS SINISTRO (Left Iris)
    468: 'Left Iris Center', 469: 'Left Iris Right',
    470: 'Left Iris Top', 471: 'Left Iris Left', 472: 'Left Iris Bottom',

    // IRIS DESTRO (Right Iris)
    473: 'Right Iris Center', 474: 'Right Iris Right',
    475: 'Right Iris Top', 476: 'Right Iris Left', 477: 'Right Iris Bottom',

    // SOPRACCIGLIO SINISTRO (Left Eyebrow)
    46: 'Left Eyebrow Inner', 53: 'Left Eyebrow Top Inner',
    52: 'Left Eyebrow Top Center', 65: 'Left Eyebrow Top Outer',
    55: 'Left Eyebrow Outer', 70: 'Left Eyebrow Bottom Inner',
    63: 'Left Eyebrow Bottom Center', 105: 'Left Eyebrow Bottom Outer',

    // SOPRACCIGLIO DESTRO (Right Eyebrow)
    276: 'Right Eyebrow Inner', 283: 'Right Eyebrow Top Inner',
    282: 'Right Eyebrow Top Center', 295: 'Right Eyebrow Top Outer',
    285: 'Right Eyebrow Outer', 300: 'Right Eyebrow Bottom Inner',
    293: 'Right Eyebrow Bottom Center', 334: 'Right Eyebrow Bottom Outer',

    // NASO (Nose)
    1: 'Nose Bridge Top', 4: 'Nose Bridge Center',
    5: 'Nose Left Side', 6: 'Nose Right Side',
    8: 'Nose Bottom Center', 19: 'Nose Bottom Left', 94: 'Nose Bottom Right',
    168: 'Nose Center', 195: 'Nose Tip Left', 197: 'Nose Tip Right',

    // GUANCE (Cheeks)
    117: 'Left Cheek Upper', 118: 'Left Cheek Center', 119: 'Left Cheek Lower',
    101: 'Left Cheek Inner Upper', 36: 'Left Cheek Inner Center',
    346: 'Right Cheek Upper', 347: 'Right Cheek Center', 348: 'Right Cheek Lower',
    330: 'Right Cheek Inner Upper', 266: 'Right Cheek Inner Center',

    // FRONTE (Forehead)
    9: 'Forehead Center (Glabella)', 108: 'Forehead Left', 337: 'Forehead Right',
    151: 'Chin Bottom',

    // MASCELLA (Jaw)
    58: 'Jaw Left Upper', 172: 'Jaw Left Center', 136: 'Jaw Left Lower',
    132: 'Jaw Left Bottom', 150: 'Jaw Bottom Left',
    288: 'Jaw Right Upper', 397: 'Jaw Right Center', 365: 'Jaw Right Lower',
    361: 'Jaw Right Bottom', 379: 'Jaw Bottom Right',

    // ZONE TEMPIE (Temples)
    127: 'Left Temple', 356: 'Right Temple',

    // Altri landmark rilevanti per anatomia facciale
    2: 'Bridge Nose Left', 98: 'Bridge Nose Right',
    200: 'Left Nostril Outer', 429: 'Right Nostril Outer',
    49: 'Left Nose Wing', 279: 'Right Nose Wing',

    // LABBRA SUPERIORE dettaglio
    40: 'Upper Lip Left Peak', 270: 'Upper Lip Right Peak',
    185: 'Upper Lip Left Curve', 409: 'Upper Lip Right Curve',

    // LABBRA INFERIORE dettaglio  
    91: 'Lower Lip Left Peak', 321: 'Lower Lip Right Peak',
    146: 'Lower Lip Left Curve', 375: 'Lower Lip Right Curve',

    // MENTO (Chin)
    149: 'Chin Left Side', 378: 'Chin Right Side',
    176: 'Chin Left Lower', 400: 'Chin Right Lower',
    199: 'Chin Bottom Left Corner', 428: 'Chin Bottom Right Corner',

    // CONTORNO OCCHI dettaglio aggiuntivo
    246: 'Left Eye Upper Lid Center', 161: 'Left Eye Upper Lid Left',
    7: 'Left Eye Upper Lid Right', 163: 'Left Eye Lower Lid Left',
    466: 'Right Eye Upper Lid Center', 388: 'Right Eye Upper Lid Left',
    255: 'Right Eye Upper Lid Right', 390: 'Right Eye Lower Lid Left'
  };

  return landmarkNames[landmarkId] || `Face Mesh Point ${landmarkId}`;
}

function openLandmarksSection() {
  /**
   * Apre la sezione LANDMARKS nella sidebar destra se è chiusa
   */
  const landmarksSection = document.querySelector('.section:has(#landmarks-table)');
  if (!landmarksSection) {
    console.warn('⚠️ Sezione LANDMARKS non trovata');
    return;
  }

  const content = landmarksSection.querySelector('.section-content');
  const icon = landmarksSection.querySelector('.icon');

  // Se la sezione è chiusa (display: none), aprila
  if (content && content.style.display === 'none') {
    content.style.display = 'block';
    landmarksSection.dataset.expanded = 'true';
    if (icon) icon.textContent = '▼';
    console.log('✅ Sezione LANDMARKS aperta automaticamente');
  }
}

function highlightNearestLandmarkOnHover(canvasX, canvasY) {
  /**
   * Evidenzia temporaneamente il landmark più vicino durante l'hover
   */
  if (!fabricCanvas) {
    console.warn('⚠️ fabricCanvas non disponibile per hover');
    return;
  }

  if (!window.currentLandmarks || window.currentLandmarks.length === 0) {
    console.warn('⚠️ currentLandmarks non disponibili per hover');
    return;
  }

  // Rimuovi precedente evidenziazione hover
  const existingHover = fabricCanvas.getObjects().filter(obj => obj.isHoverHighlight);
  existingHover.forEach(obj => fabricCanvas.remove(obj));

  // Trova il landmark più vicino usando gli oggetti canvas
  const nearestLandmark = findNearestLandmarkOnCanvas(canvasX, canvasY);

  if (nearestLandmark && nearestLandmark.distance < 20) {  // Tolleranza 20px
    const landmarkId = nearestLandmark.landmarkIndex;
    const centerX = nearestLandmark.centerX;
    const centerY = nearestLandmark.centerY;

    // Crea cerchio hover con effetto pulsante
    const hoverCircle = new fabric.Circle({
      left: centerX,
      top: centerY,
      radius: 10,
      fill: 'rgba(255, 255, 0, 0.3)',
      stroke: '#FFD700',
      strokeWidth: 2,
      originX: 'center',
      originY: 'center',
      selectable: false,
      evented: false,
      isHoverHighlight: true,
      landmarkId: landmarkId
    });

    fabricCanvas.add(hoverCircle);

    // Tooltip con ID e nome landmark
    const landmarkName = getLandmarkName(landmarkId);
    const tooltip = new fabric.Text(`${landmarkId}: ${landmarkName}`, {
      left: centerX + 15,
      top: centerY - 10,
      fontSize: 12,
      fill: '#FFD700',
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      padding: 4,
      selectable: false,
      evented: false,
      isHoverHighlight: true
    });

    fabricCanvas.add(tooltip);
    fabricCanvas.renderAll();
  }
}

function highlightSelectedLandmark(landmarkId, color) {
  /**
   * Evidenzia un landmark selezionato con un cerchio colorato
   */
  if (!window.currentLandmarks || !window.currentImage || !fabricCanvas) return;

  const landmark = window.currentLandmarks[landmarkId];
  if (!landmark) return;

  const imageWidth = window.currentImage.width || 1;
  const imageHeight = window.currentImage.height || 1;
  const scale = window.imageScale || 1;
  const offset = window.imageOffset || { x: 0, y: 0 };

  // Converti a coordinate canvas
  const canvasX = landmark.x * imageWidth * scale + offset.x;
  const canvasY = landmark.y * imageHeight * scale + offset.y;

  // Crea cerchio evidenziato
  const circle = new fabric.Circle({
    left: canvasX,
    top: canvasY,
    radius: 8,
    fill: 'transparent',
    stroke: color,
    strokeWidth: 3,
    originX: 'center',
    originY: 'center',
    selectable: false,
    evented: false,
    isLandmarkHighlight: true,
    landmarkId: landmarkId
  });

  fabricCanvas.add(circle);
  fabricCanvas.renderAll();
}

async function toggleGreenDots() {
  if (window.isDetectingGreenDots) {
    showToast('⏳ Elaborazione già in corso, attendere...', 'info');
    return;
  }

  const btn = document.getElementById('green-dots-btn');
  btn.classList.toggle('active');
  const isActive = btn.classList.contains('active');

  if (isActive) {
    if (!window.greenDotsDetected) {
      await detectGreenDots();
    } else {
      updateCanvasDisplay();
      if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak && window.greenDotsData) {
        const feedback = analyzeEyebrowDesignFromData(window.greenDotsData);
        if (feedback) voiceAssistant.speak(feedback);
      }
    }
  } else {
    updateCanvasDisplay();
  }

  updateStatus(isActive ? 'Trova differenze attivo' : 'Trova differenze disattivo');
}

async function detectGreenDots() {
  if (!currentImage) {
    showToast('Nessuna immagine caricata', 'warning');
    return;
  }

  if (window.isDetectingGreenDots) return;
  window.isDetectingGreenDots = true;

  const btn = document.getElementById('green-dots-btn');
  if (btn) btn.disabled = true;

  try {
    // Assicura landmarks disponibili (necessari per asse di simmetria)
    if (!getSymmetryAxisPosition()) {
      await autoDetectLandmarksOnImageChange();
    }

    updateStatus('Rilevamento in corso...');
    showToast('⏳ Elaborazione in corso... Può richiedere 10-60 secondi', 'info');

    // Invia immagine full-res (WHITE_DOTS_MAX_PX = null): i dot bianchi sono piccoli
    // (5-400px²) e ridimensionare sposta coordinate e altera i blob.
    const canvasImageData = getCanvasImageAsBase64(WHITE_DOTS_MAX_PX);
    if (!canvasImageData) throw new Error('Impossibile ottenere dati immagine dal canvas');

    window.greenDotsImageScale = window.lastImageResizeScale || 1.0;

    // Adatta parametri se il viso è piccolo nell'immagine (sopracciglio < 1/5 larghezza immagine)
    const extraParams = _getGreenDotsParamsForFaceSize();

    const result = await analyzeGreenDotsViaAPI(canvasImageData, extraParams);

    if (!result.success) throw new Error(result.error || 'Errore sconosciuto');

    window.greenDotsData = result;
    window.greenDotsDetected = true;

    updateMeasurementsFromGreenDots(result);

    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
      const feedback = analyzeEyebrowDesignFromData(result);
      if (feedback) voiceAssistant.speak(feedback);
    }

    // Espandi sezione CORREZIONE SOPRACCIGLIA se chiusa
    document.querySelectorAll('.left-sidebar .section').forEach(section => {
      const toggleBtn = section.querySelector('.toggle-btn');
      if (toggleBtn?.textContent.includes('✂️ CORREZIONE SOPRACCIGLIA') &&
        section.dataset.expanded !== 'true') {
        section.querySelector('.section-header')?.click();
      }
    });

    updateCanvasDisplay();
    updateStatus(`Rilevati ${result.detection_results.total_dots} punti`);
    showToast(`Rilevamento completato: ${result.detection_results.total_dots} punti`, 'success');

  } catch (error) {
    console.error('Errore rilevamento trova differenze:', error);
    updateStatus('Errore rilevamento');
    showToast(`Errore: ${error.message}`, 'error');
    const errBtn = document.getElementById('green-dots-btn');
    if (errBtn?.classList.contains('active')) errBtn.classList.remove('active');
  } finally {
    window.isDetectingGreenDots = false;
    const finalBtn = document.getElementById('green-dots-btn');
    if (finalBtn) finalBtn.disabled = false;
  }
}

/**
 * Misura la larghezza del sopracciglio sinistro dai landmark MediaPipe già disponibili
 * e la confronta con la larghezza dell'immagine. Se il sopracciglio è < 1/5 dell'immagine
 * restituisce parametri ridotti per il rilevamento su visi piccoli.
 */
function _getGreenDotsParamsForFaceSize() {
  const lms = window.currentLandmarks;
  if (!lms || lms.length < 468) return {};

  // Landmark sopracciglio sinistro MediaPipe: estremo esterno=46, estremo interno=107
  const lbIdxs = [46, 53, 52, 65, 55, 107, 66, 105, 63, 70];
  const xs = lbIdxs.map(i => lms[i] && lms[i].x).filter(x => x != null);
  if (xs.length < 2) return {};

  const eyebrowWidth = Math.max(...xs) - Math.min(...xs);

  // I landmark sono in pixel riferiti a el.naturalWidth (dimensioni Fabric display).
  // Usiamo la stessa sorgente per imgWidth, così il ratio è coerente.
  let imgWidth = 0;
  if (currentImage) {
    const el = currentImage.getElement ? currentImage.getElement() : currentImage;
    imgWidth = el.naturalWidth || el.width || 0;
  }

  if (imgWidth <= 0) return {};

  const ratio = eyebrowWidth / imgWidth;
  console.log(`📐 Sopracciglio/immagine ratio: ${(ratio * 100).toFixed(1)}% (${Math.round(eyebrowWidth)}px / ${imgWidth}px)`);

  if (ratio < 0.2) {
    console.log('🔎 Viso piccolo rilevato — parametri ridotti: min_distance=30, outer_px=25');
    return { min_distance: 30, outer_px: 25 };
  }
  return {};
}

// ── Swatch luminanza: mostra quadratino grigio corrispondente al valore (0-255) ──
function pdUpdateLumaSwatch(swatchId, luma) {
  const el = document.getElementById(swatchId);
  if (!el) return;
  const v = Math.max(0, Math.min(255, luma));
  el.style.background = `rgb(${v},${v},${v})`;
}
window.pdUpdateLumaSwatch = pdUpdateLumaSwatch;

/**
 * Disegna la curva di trasferimento highlight boost su un canvas.
 * Asse X = grigio input (0-255), Asse Y = grigio output.
 * La zona boosted è evidenziata in arancione trasparente.
 */
function pdUpdateHighlightPreview(canvasId, threshInputId, strengthInputId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const thresh = parseFloat(document.getElementById(threshInputId)?.value ?? 160);
  const strength = parseFloat(document.getElementById(strengthInputId)?.value ?? 0.8);
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const PAD = 6;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#111118';
  ctx.fillRect(0, 0, W, H);

  // Helper: input gray → output gray
  const boost = x => x < thresh ? x : Math.min(255, x + strength * (255 - x));
  // Map gray 0-255 → canvas coords
  const gx = g => PAD + (g / 255) * (W - PAD * 2);
  const gy = g => H - PAD - (g / 255) * (H - PAD * 2);

  // Zona boosted: da thresh a 255, riempita arancione semitrasparente
  ctx.fillStyle = 'rgba(255,140,0,0.13)';
  ctx.fillRect(gx(thresh), PAD, gx(255) - gx(thresh), H - PAD * 2);

  // Linea diagonale identità (grigio)
  ctx.strokeStyle = '#333';
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(gx(0), gy(0));
  ctx.lineTo(gx(255), gy(255));
  ctx.stroke();
  ctx.setLineDash([]);

  // Curva effettiva
  ctx.strokeStyle = '#ffe066';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let g = 0; g <= 255; g++) {
    const out = boost(g);
    const px = gx(g), py = gy(out);
    if (g === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.stroke();

  // Linea verticale soglia
  ctx.strokeStyle = 'rgba(255,140,0,0.7)';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 2]);
  ctx.beginPath();
  ctx.moveTo(gx(thresh), PAD);
  ctx.lineTo(gx(thresh), H - PAD);
  ctx.stroke();
  ctx.setLineDash([]);

  // Etichetta soglia
  ctx.fillStyle = 'rgba(255,140,0,0.9)';
  ctx.font = '9px monospace';
  ctx.fillText(`thr=${thresh}`, gx(thresh) + 2, PAD + 10);
  ctx.fillStyle = 'rgba(255,220,80,0.7)';
  ctx.fillText(`str=${strength.toFixed(2)}`, W - 52, H - PAD - 2);
}
window.pdUpdateHighlightPreview = pdUpdateHighlightPreview;

/**
 * Disegna anteprime delle forme accettabili in base a circolarità e perimetro.
 * Mostra una griglia di blob sintetici: asse X = circolarità (min→max),
 * asse Y = dimensione (perimetro min→max). 1.0=cerchio, valori bassi=forme allungate.
 */
function pdUpdateShapePreview(canvasId, minCircId, maxCircId, minPeriId, maxPeriId, accentColor) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const minC = parseFloat(document.getElementById(minCircId)?.value ?? 0.5);
  const maxC = parseFloat(document.getElementById(maxCircId)?.value ?? 1.0);
  const minP = parseFloat(document.getElementById(minPeriId)?.value ?? 3);
  const maxP = parseFloat(document.getElementById(maxPeriId)?.value ?? 60);
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#111118';
  ctx.fillRect(0, 0, W, H);

  // Parse accent color to rgb
  const tmp = document.createElement('canvas');
  const tc = tmp.getContext('2d');
  tc.fillStyle = accentColor;
  tc.fillRect(0, 0, 1, 1);
  const [ar, ag, ab] = tc.getImageData(0, 0, 1, 1).data;

  const COLS = 5, ROWS = 2;
  const cellW = W / COLS, cellH = H / ROWS;
  // col = circolarità steps da minC a maxC
  // row = perimetro: row 0 = minP, row 1 = maxP
  const circSteps = COLS <= 1 ? [minC] : Array.from({ length: COLS }, (_, i) => minC + (maxC - minC) * i / (COLS - 1));
  const periSteps = ROWS <= 1 ? [minP] : [minP, maxP];

  for (let row = 0; row < ROWS; row++) {
    for (let col = 0; col < COLS; col++) {
      const circ = circSteps[col];
      const peri = periSteps[row];
      // Raggio base dal perimetro: peri = 2*pi*r → r = peri/(2*pi)
      // Scala per stare nel cell
      const rBase = Math.max(1.5, peri / (2 * Math.PI));
      const maxR = Math.min(cellW, cellH) * 0.38;
      const rDisp = Math.min(rBase * 1.4, maxR);
      const cx = cellW * (col + 0.5);
      const cy = cellH * (row + 0.5);

      // Deformazione da circolarità: circ=1→cerchio, circ→0→ellisse schiacciata
      // circ = 4π*area/peri² → per ellisse a=(r), b=r*k: area=π*a*b=π*r²*k, peri≈2π*r*sqrt((1+k²)/2)
      // Approssimazione visiva: aspect ratio dal valore di circolarità
      const aspectApprox = Math.max(0.2, Math.min(1, circ));
      const rx = rDisp;
      const ry = rDisp * aspectApprox;

      const alpha = circ >= minC && circ <= maxC ? 1.0 : 0.2;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = accentColor;
      ctx.fillStyle = `rgba(${ar},${ag},${ab},0.22)`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      // Label in basso
      ctx.fillStyle = 'rgba(200,200,200,0.6)';
      ctx.font = '8px monospace';
      const lblC = circ.toFixed(1);
      const lblP = `${Math.round(peri)}p`;
      ctx.fillText(lblC, cx - 8, cy + ry + 10);
      if (col === 0) ctx.fillText(lblP, 2, cy + 4);
    }
  }
  // Bordo campo accettato (arancione/blu leggero)
  ctx.strokeStyle = `rgba(${ar},${ag},${ab},0.3)`;
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 3]);
  ctx.strokeRect(1, 1, W - 2, H - 2);
  ctx.setLineDash([]);
}
window.pdUpdateShapePreview = pdUpdateShapePreview;

// Inizializza le anteprime canvas con i valori di default quando il DOM è pronto
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    pdUpdateHighlightPreview('pd-highlight-preview-inner', 'pd-highlight-thresh-inner', 'pd-highlight-strength-inner');
    pdUpdateHighlightPreview('pd-highlight-preview-outer', 'pd-highlight-thresh-outer', 'pd-highlight-strength-outer');
    pdUpdateShapePreview('pd-shape-preview-inner', 'pd-min-circ-inner', 'pd-max-circ-inner', 'pd-min-peri-inner', 'pd-max-peri-inner', '#7d9fff');
    pdUpdateShapePreview('pd-shape-preview-outer', 'pd-min-circ-outer', 'pd-max-circ-outer', 'pd-min-peri-outer', 'pd-max-peri-outer', '#ff9966');
  }, 300);
});

/**
 * Vista rapida: chiama /api/debug/trova-differenze e mostra Step1+Step2+Step3
 * nelle 3 card esistenti (zone, detect, masked).
 */
async function showWhiteDotsDebugImages() {
  const modal = document.getElementById('wdots-debug-modal');
  const status = document.getElementById('wdots-debug-status');
  const imgZ = document.getElementById('wdots-debug-zone');
  const imgD = document.getElementById('wdots-debug-detect');
  const imgM = document.getElementById('wdots-debug-masked');
  const paramsEl = document.getElementById('wdots-debug-params');
  const paramsTxt = document.getElementById('wdots-params-text');

  if (!modal) return;
  modal.style.display = 'block';

  await loadCurrentParams();

  status.textContent = '⏳ Ricalcolo...';
  [imgZ, imgD, imgM].forEach(el => el && (el.style.display = 'none'));
  if (paramsEl) paramsEl.style.display = 'none';

  if (!currentImage) {
    status.textContent = '⚠️ Nessuna immagine caricata sul canvas.';
    return;
  }

  try {
    const canvasImageData = getCanvasImageAsBase64(WHITE_DOTS_MAX_PX);
    if (!canvasImageData) throw new Error('Impossibile ottenere dati immagine dal canvas');

    const baseUrl = (typeof API_CONFIG !== 'undefined' && API_CONFIG?.baseURL)
      ? API_CONFIG.baseURL
      : window.location.origin;

    // Vista rapida: usa i suoi slider per luma_min e luma_max
    const params = readPipelineParams();
    const lumaSlider = document.getElementById('wdots-luma');
    const lumaMaxSlider = document.getElementById('wdots-luma-max');
    if (lumaSlider) params.luma_min = parseInt(lumaSlider.value);
    if (lumaMaxSlider) params.luma_max = parseInt(lumaMaxSlider.value);

    const resp = await fetch(`${baseUrl}/api/debug/trova-differenze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: canvasImageData, ...params }),
      signal: AbortSignal.timeout(120000),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    const data = await resp.json();
    if (!data.success || !Array.isArray(data.steps)) throw new Error('Risposta non valida dal server');

    // Step 1 → zona, Step 2 → detect, Step 3 → ordine anatomico
    const b64 = (n) => {
      const s = data.steps.find(s => s.step === n);
      return s ? `data:image/jpeg;base64,${s.image_b64}` : null;
    };
    if (imgZ && b64(1)) { imgZ.src = b64(1); imgZ.style.display = 'block'; }
    if (imgD && b64(2)) { imgD.src = b64(2); imgD.style.display = 'block'; }
    if (imgM && b64(3)) { imgM.src = b64(3); imgM.style.display = 'block'; }

    if (paramsEl && paramsTxt) {
      paramsTxt.textContent =
        `zona ${params.outer_px}px  |  ` +
        `luma [${params.luma_min}–${params.luma_max}]  |  ` +
        `LB/RB luma [${params.luma_lb}–${params.luma_max_lb}]  |  ` +
        `boost inner thr=${params.highlight_thresh_inner} str=${params.highlight_strength_inner}  |  ` +
        `boost outer thr=${params.highlight_thresh_outer} str=${params.highlight_strength_outer}  |  ` +
        `circ inner [${params.min_circularity_inner}–${params.max_circularity_inner}] peri [${params.min_perimeter_inner}–${params.max_perimeter_inner}]  |  ` +
        `circ outer [${params.min_circularity_outer}–${params.max_circularity_outer}] peri [${params.min_perimeter_outer}–${params.max_perimeter_outer}]`;
      paramsEl.style.display = 'block';
    }

    const n = data.steps.length;
    status.textContent = `✅ ${n} step completati`;

  } catch (err) {
    console.error('❌ Errore debug immagini:', err);
    status.textContent = `❌ Errore: ${err.message}`;
  }
}

// Debounce per il ricalcolo automatico al cambio slider (400ms)
let _wdotsRecalcTimer = null;
function wdotsScheduleRecalc() {
  clearTimeout(_wdotsRecalcTimer);
  const pipelineVisible = document.getElementById('wdots-panel-pipeline')?.style.display !== 'none';
  _wdotsRecalcTimer = setTimeout(() => pipelineVisible ? showDebugPipeline() : showWhiteDotsDebugImages(), 400);
}
window.wdotsScheduleRecalc = wdotsScheduleRecalc;

window.showWhiteDotsDebugImages = showWhiteDotsDebugImages;

// Tab switcher per il modal debug
function wdotsSetTab(tab) {
  const quickPanel = document.getElementById('wdots-panel-quick');
  const pipelinePanel = document.getElementById('wdots-panel-pipeline');
  const quickBtn = document.getElementById('wdots-tab-quick');
  const pipelineBtn = document.getElementById('wdots-tab-pipeline');
  if (!quickPanel || !pipelinePanel) return;

  const isQuick = tab === 'quick';
  quickPanel.style.display = isQuick ? '' : 'none';
  pipelinePanel.style.display = isQuick ? 'none' : '';

  if (quickBtn) {
    quickBtn.style.background = isQuick ? '#1a4a2a' : '#111';
    quickBtn.style.fontWeight = isQuick ? 'bold' : 'normal';
  }
  if (pipelineBtn) {
    pipelineBtn.style.background = isQuick ? '#111' : '#1a1a3a';
    pipelineBtn.style.fontWeight = isQuick ? 'normal' : 'bold';
  }

  // Alla prima apertura del tab pipeline: carica parametri e aggiorna preview
  if (!isQuick) {
    loadCurrentParams();
    const grid = document.getElementById('wdots-pipeline-grid');
    if (grid && grid.children.length === 0) showDebugPipeline();
  }
}
window.wdotsSetTab = wdotsSetTab;

// Legge i valori degli slider parametri pipeline
function readPipelineParams() {
  return {
    target_width: parseInt(document.getElementById('pd-target-width')?.value ?? 1200),
    outer_px: parseInt(document.getElementById('pd-outer-px')?.value ?? 35),
    luma_min: parseInt(document.getElementById('pd-luma-min')?.value ?? 200),
    luma_max: parseInt(document.getElementById('pd-luma-max')?.value ?? 255),
    luma_lb: parseInt(document.getElementById('pd-luma-lb')?.value ?? 120),
    luma_max_lb: parseInt(document.getElementById('pd-luma-max-lb')?.value ?? 255),
    highlight_thresh_inner: parseInt(document.getElementById('pd-highlight-thresh-inner')?.value ?? 160),
    highlight_strength_inner: parseFloat(document.getElementById('pd-highlight-strength-inner')?.value ?? 0.8),
    highlight_thresh_outer: parseInt(document.getElementById('pd-highlight-thresh-outer')?.value ?? 140),
    highlight_strength_outer: parseFloat(document.getElementById('pd-highlight-strength-outer')?.value ?? 0.6),
    min_circularity_inner: parseFloat(document.getElementById('pd-min-circ-inner')?.value ?? 0.5),
    max_circularity_inner: parseFloat(document.getElementById('pd-max-circ-inner')?.value ?? 1.0),
    min_perimeter_inner: parseInt(document.getElementById('pd-min-peri-inner')?.value ?? 3),
    max_perimeter_inner: parseInt(document.getElementById('pd-max-peri-inner')?.value ?? 60),
    min_circularity_outer: parseFloat(document.getElementById('pd-min-circ-outer')?.value ?? 0.3),
    max_circularity_outer: parseFloat(document.getElementById('pd-max-circ-outer')?.value ?? 1.0),
    min_perimeter_outer: parseInt(document.getElementById('pd-min-peri-outer')?.value ?? 2),
    max_perimeter_outer: parseInt(document.getElementById('pd-max-peri-outer')?.value ?? 40),
    min_distance: parseInt(document.getElementById('pd-min-distance')?.value ?? 12),
  };
}

// Popola gli slider dagli oggetto params (sia pipeline che vista rapida)
function populatePipelineSliders(params) {
  const set = (id, valId, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
    const lbl = document.getElementById(valId);
    if (lbl) lbl.textContent = val;
  };
  set('pd-target-width', 'pd-target-width-val', params.target_width ?? 1200);
  set('pd-outer-px', 'pd-outer-px-val', params.outer_px ?? 35);
  set('pd-luma-min', 'pd-luma-min-val', params.luma_min ?? 200);
  set('pd-luma-max', 'pd-luma-max-val', params.luma_max ?? 255);
  set('pd-luma-lb', 'pd-luma-lb-val', params.luma_lb ?? 120);
  set('pd-luma-max-lb', 'pd-luma-max-lb-val', params.luma_max_lb ?? 255);
  set('pd-highlight-thresh-inner', 'pd-highlight-thresh-inner-val', params.highlight_thresh_inner ?? 160);
  set('pd-highlight-strength-inner', 'pd-highlight-strength-inner-val', parseFloat(params.highlight_strength_inner ?? 0.8).toFixed(2));
  set('pd-highlight-thresh-outer', 'pd-highlight-thresh-outer-val', params.highlight_thresh_outer ?? 140);
  set('pd-highlight-strength-outer', 'pd-highlight-strength-outer-val', parseFloat(params.highlight_strength_outer ?? 0.6).toFixed(2));
  set('pd-min-circ-inner', 'pd-min-circ-inner-val', parseFloat(params.min_circularity_inner ?? 0.5).toFixed(2));
  set('pd-max-circ-inner', 'pd-max-circ-inner-val', parseFloat(params.max_circularity_inner ?? 1.0).toFixed(2));
  set('pd-min-peri-inner', 'pd-min-peri-inner-val', params.min_perimeter_inner ?? 3);
  set('pd-max-peri-inner', 'pd-max-peri-inner-val', params.max_perimeter_inner ?? 60);
  set('pd-min-circ-outer', 'pd-min-circ-outer-val', parseFloat(params.min_circularity_outer ?? 0.3).toFixed(2));
  set('pd-max-circ-outer', 'pd-max-circ-outer-val', parseFloat(params.max_circularity_outer ?? 1.0).toFixed(2));
  set('pd-min-peri-outer', 'pd-min-peri-outer-val', params.min_perimeter_outer ?? 2);
  set('pd-max-peri-outer', 'pd-max-peri-outer-val', params.max_perimeter_outer ?? 40);
  set('pd-min-distance', 'pd-min-distance-val', params.min_distance ?? 12);
  // sincronizza anche gli slider della vista rapida
  set('wdots-luma', 'wdots-luma-val', params.luma_min ?? 200);
  set('wdots-luma-max', 'wdots-luma-max-val', params.luma_max ?? 255);
  // aggiorna swatches luminanza dopo popolamento
  pdUpdateLumaSwatch('pd-luma-min-swatch', params.luma_min ?? 200);
  pdUpdateLumaSwatch('pd-luma-max-swatch', params.luma_max ?? 255);
  pdUpdateLumaSwatch('pd-luma-lb-swatch', params.luma_lb ?? 120);
  pdUpdateLumaSwatch('pd-luma-max-lb-swatch', params.luma_max_lb ?? 255);
  pdUpdateLumaSwatch('pd-highlight-thresh-inner-swatch', params.highlight_thresh_inner ?? 160);
  pdUpdateLumaSwatch('pd-highlight-thresh-outer-swatch', params.highlight_thresh_outer ?? 140);
  pdUpdateLumaSwatch('wdots-luma-swatch', params.luma_min ?? 200);
  // aggiorna anteprime canvas
  pdUpdateHighlightPreview('pd-highlight-preview-inner', 'pd-highlight-thresh-inner', 'pd-highlight-strength-inner');
  pdUpdateHighlightPreview('pd-highlight-preview-outer', 'pd-highlight-thresh-outer', 'pd-highlight-strength-outer');
  pdUpdateShapePreview('pd-shape-preview-inner', 'pd-min-circ-inner', 'pd-max-circ-inner', 'pd-min-peri-inner', 'pd-max-peri-inner', '#7d9fff');
  pdUpdateShapePreview('pd-shape-preview-outer', 'pd-min-circ-outer', 'pd-max-circ-outer', 'pd-min-peri-outer', 'pd-max-peri-outer', '#ff9966');
}

// Carica i parametri attuali dal server e popola gli slider
async function loadCurrentParams() {
  try {
    const baseUrl = (typeof API_CONFIG !== 'undefined' && API_CONFIG?.baseURL)
      ? API_CONFIG.baseURL : window.location.origin;
    const resp = await fetch(`${baseUrl}/api/debug/params`);
    const data = await resp.json();
    if (data.success && data.params) populatePipelineSliders(data.params);
  } catch (err) {
    console.warn('loadCurrentParams error:', err);
  }
}
window.loadCurrentParams = loadCurrentParams;


// Approva i parametri attuali degli slider come nuovi default
async function approveDebugParams() {
  if (!currentImage) {
    alert('⚠️ Nessuna immagine caricata — impossibile determinare il contesto.');
    return;
  }
  const params = readPipelineParams();
  const baseUrl = (typeof API_CONFIG !== 'undefined' && API_CONFIG?.baseURL)
    ? API_CONFIG.baseURL : window.location.origin;
  try {
    const canvasImageData = getCanvasImageAsBase64(WHITE_DOTS_MAX_PX);
    const resp = await fetch(`${baseUrl}/api/debug/params/approve`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: canvasImageData || '', ...params }),
    });
    const data = await resp.json();
    if (data.success) {
      const st = document.getElementById('wdots-pipeline-status');
      if (st) { st.textContent = `✅ ${data.message}`; st.style.display = ''; }
    }
  } catch (err) {
    console.error('approveDebugParams error:', err);
  }
}
window.approveDebugParams = approveDebugParams;

// Pipeline step-by-step debug
async function showDebugPipeline() {
  const grid = document.getElementById('wdots-pipeline-grid');
  const pipeSt = document.getElementById('wdots-pipeline-status');
  if (!grid) return;

  if (!currentImage) {
    if (pipeSt) { pipeSt.textContent = '⚠️ Nessuna immagine caricata.'; pipeSt.style.display = ''; }
    return;
  }

  grid.innerHTML = '<div style="color:#888; font-size:12px; padding:16px;">⏳ Elaborazione pipeline... (10-60s)</div>';
  if (pipeSt) { pipeSt.textContent = '⏳ Richiesta in corso...'; pipeSt.style.display = ''; }

  try {
    const canvasImageData = getCanvasImageAsBase64(WHITE_DOTS_MAX_PX);
    if (!canvasImageData) throw new Error('Impossibile ottenere dati immagine dal canvas');

    const baseUrl = (typeof API_CONFIG !== 'undefined' && API_CONFIG?.baseURL)
      ? API_CONFIG.baseURL : window.location.origin;

    const params = readPipelineParams();
    const resp = await fetch(`${baseUrl}/api/debug/trova-differenze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: canvasImageData, ...params }),
      signal: AbortSignal.timeout(120000)
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    const data = await resp.json();
    if (!data.success || !Array.isArray(data.steps)) throw new Error('Risposta non valida');

    const stepColors = ['#aaa', '#00d4ff', '#4dff91', '#ffd700', '#ff9900', '#ff66cc', '#ff4444', '#7dff7d', '#ffaa44', '#a0c4ff', '#7dff7d'];

    grid.innerHTML = '';
    // popup blob condiviso — riusa se già presente
    let blobPopup = document.getElementById('blob-popup');
    if (!blobPopup) {
      blobPopup = document.createElement('div');
      blobPopup.id = 'blob-popup';
      blobPopup.style.cssText = 'display:none;position:fixed;z-index:20000;background:#111;border:1px solid #444;border-radius:8px;padding:12px 16px;min-width:200px;max-width:280px;box-shadow:0 4px 24px rgba(0,0,0,0.7);pointer-events:none;font-size:13px;line-height:1.6;';
      document.body.appendChild(blobPopup);
      document.addEventListener('click', () => { blobPopup.style.display = 'none'; });
    }

    data.steps.forEach(step => {
      if (!step.image_b64) return;
      const card = document.createElement('div');
      card.style.cssText = 'background:#1a1a1a; border:1px solid #2a2a2a; border-radius:8px; overflow:hidden;';
      const col = stepColors[step.step] || '#aaa';

      // header
      const header = document.createElement('div');
      header.style.cssText = 'padding:8px 10px; border-bottom:1px solid #2a2a2a; display:flex; align-items:baseline; gap:8px;';
      header.innerHTML = `<span style="color:${col};font-size:13px;font-weight:bold;">Step ${step.step}</span>
        <span style="color:#eee;font-size:12px;font-weight:bold;">${step.name}</span>`;
      card.appendChild(header);

      if (step.step === 2 && Array.isArray(step.blobs)) {
        // ── Step 2: immagine + canvas overlay interattivo ──────────────────
        const hint = document.createElement('div');
        hint.style.cssText = 'padding:4px 10px;background:#161a10;color:#8bc;font-size:11px;';
        hint.textContent = '● Ciano/Verde = accettato inner  ● Blu = accettato outer  ● Rosso = scartato  ● Grigio = rumore  — click su un punto per i dettagli';
        card.appendChild(hint);

        const wrap = document.createElement('div');
        wrap.style.cssText = 'position:relative;display:block;line-height:0;';

        const img = document.createElement('img');
        img.src = step.image_b64;
        img.style.cssText = 'width:100%;display:block;';
        wrap.appendChild(img);

        const cvs = document.createElement('canvas');
        cvs.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;cursor:crosshair;';
        wrap.appendChild(cvs);
        card.appendChild(wrap);

        const blobs = step.blobs;
        const imgW = step.img_w, imgH = step.img_h;

        function renderBlobOverlay() {
          const dpr = window.devicePixelRatio || 1;
          const rw = wrap.offsetWidth, rh = wrap.offsetHeight || (rw * imgH / imgW);
          cvs.width = rw * dpr;
          cvs.height = rh * dpr;
          const ctx = cvs.getContext('2d');
          ctx.scale(dpr, dpr);
          ctx.clearRect(0, 0, rw, rh);
          blobs.forEach(b => {
            const px = b.x * rw, py = b.y * rh;
            const r = b.type === 'noise' ? 3 : b.type === 'accepted' ? 7 : 5;
            ctx.beginPath();
            ctx.arc(px, py, r, 0, Math.PI * 2);
            ctx.fillStyle = b.hex;
            ctx.fill();
            if (b.type === 'accepted') {
              ctx.strokeStyle = '#fff';
              ctx.lineWidth = 1.5;
              ctx.stroke();
            }
          });
        }

        img.onload = renderBlobOverlay;
        if (img.complete) renderBlobOverlay();
        new ResizeObserver(renderBlobOverlay).observe(wrap);

        // click su canvas → trova blob più vicino e mostra popup
        cvs.addEventListener('click', e => {
          e.stopPropagation();
          const rect = cvs.getBoundingClientRect();
          const mx = (e.clientX - rect.left) / rect.width;
          const my = (e.clientY - rect.top) / rect.height;
          // trova blob più vicino in coordinate normalizzate
          let best = null, bestD = Infinity;
          blobs.forEach(b => {
            const dx = b.x - mx, dy = b.y - my;
            // raggio click in spazio normalizzato (hitbox ~12px)
            const hitR = 14 / rect.width;
            const d = Math.sqrt(dx * dx + dy * dy);
            if (d < hitR && d < bestD) { best = b; bestD = d; }
          });
          if (!best) { blobPopup.style.display = 'none'; return; }

          const typeLabel = best.type === 'accepted' ? '✅ ACCETTATO' : best.type === 'noise' ? '⚪ RUMORE (sub-px)' : best.type === 'rejected_nms' ? '⚡ ELIMINATO NMS' : '❌ SCARTATO';
          const typeColor = best.type === 'accepted' ? '#4dff91' : best.type === 'noise' ? '#888' : best.type === 'rejected_nms' ? '#ff6644' : '#ff7070';
          blobPopup.innerHTML = `
            <div style="font-weight:bold;color:${typeColor};margin-bottom:6px;">${typeLabel}</div>
            <div style="color:#aaa;font-size:11px;margin-bottom:8px;">zona: <b style="color:#eee">${best.zone}</b> &nbsp; lato: <b style="color:#eee">${best.side}</b></div>
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
              <tr><td style="color:#888;padding:2px 6px 2px 0">area</td><td style="color:#eee;font-weight:bold">${best.area} px</td></tr>
              <tr><td style="color:#888;padding:2px 6px 2px 0">perimetro</td><td style="color:#eee;font-weight:bold">${best.perim} px</td></tr>
              <tr><td style="color:#888;padding:2px 6px 2px 0">circolarità</td><td style="color:#eee;font-weight:bold">${best.circ.toFixed(3)}<span style="color:#666;font-size:10px"> (1=cerchio)</span></td></tr>
              ${best.luma !== null ? `<tr><td style="color:#888;padding:2px 6px 2px 0">score luma</td><td style="color:#eee;font-weight:bold">${best.luma}%</td></tr>` : ''}
            </table>
            ${best.type !== 'accepted' ? `<div style="margin-top:8px;padding:6px 8px;background:#1a1010;border-radius:4px;color:#ff9999;font-size:11px;">${best.verdict}</div>` : `<div style="margin-top:8px;padding:6px 8px;background:#0a1a0a;border-radius:4px;color:#4dff91;font-size:11px;">${best.verdict}</div>`}
          `;
          blobPopup.style.display = 'block';
          // posiziona popup vicino al click ma dentro viewport
          const pw = 280, ph = 220;
          let px = e.clientX + 14, py = e.clientY - ph / 2;
          if (px + pw > window.innerWidth - 8) px = e.clientX - pw - 14;
          if (py < 8) py = 8;
          if (py + ph > window.innerHeight - 8) py = window.innerHeight - ph - 8;
          blobPopup.style.left = px + 'px';
          blobPopup.style.top = py + 'px';
        });

      } else {
        // ── altri step: immagine semplice ──────────────────────────────────
        const img = document.createElement('img');
        img.src = step.image_b64;
        img.alt = `step${step.step}`;
        img.style.cssText = 'width:100%;display:block;cursor:zoom-in;';
        img.addEventListener('click', () => {
          if (img.dataset.zoomed === '1') {
            img.dataset.zoomed = '';
            img.style.cssText = 'width:100%;display:block;cursor:zoom-in;';
            document.body.style.overflow = '';
          } else {
            img.dataset.zoomed = '1';
            img.style.cssText = 'position:fixed;inset:0;z-index:10000;width:auto;height:100vh;max-width:100vw;object-fit:contain;background:rgba(0,0,0,0.93);margin:auto;cursor:zoom-out;display:block;';
            document.body.style.overflow = 'hidden';
          }
        });
        card.appendChild(img);
      }

      const desc = document.createElement('div');
      desc.style.cssText = 'padding:6px 10px; color:#888; font-size:11px;';
      desc.textContent = step.description;
      card.appendChild(desc);

      grid.appendChild(card);
    });

    if (pipeSt) { pipeSt.textContent = `✅ ${data.total} step caricati`; }

  } catch (err) {
    console.error('❌ Errore debug pipeline:', err);
    grid.innerHTML = `<div style="color:#ff4444; font-size:12px; padding:16px;">❌ Errore: ${err.message}</div>`;
    if (pipeSt) { pipeSt.textContent = `❌ ${err.message}`; }
  }
}
window.showDebugPipeline = showDebugPipeline;

// Resetta highResCanvasForAnalysis per sorgenti non-immagine (video/webcam)
function setAnalysisSourceCanvas(sourceType) {
  if (sourceType !== 'image') {
    window.highResCanvasForAnalysis = null;
  }
}

// ==================== POINT PAIR HIGHLIGHT TOOL ====================

/**
 * Stato corrente dell'evidenziazione coppia punti
 */
window.highlightedPair = null;
window.highlightOverlayObjects = [];

/**
 * Evidenzia una coppia di punti corrispondenti sul canvas
 * Mostra frecce che indicano quale punto è più alto/basso e più interno/esterno
 */
function highlightPointPair(rowElement) {
  // Rimuovi evidenziazione precedente
  clearPointPairHighlight();

  // Ottieni i dati della coppia dalla riga
  const pairDataStr = rowElement.getAttribute('data-pair');
  if (!pairDataStr) {
    console.error('❌ Nessun dato coppia trovato');
    return;
  }

  const pairData = JSON.parse(pairDataStr.replace(/&quot;/g, '"'));
  console.log('🎯 Evidenziazione coppia:', pairData);

  // Toggle: se clicco sulla stessa riga, rimuovi evidenziazione
  if (window.highlightedPair &&
    window.highlightedPair.leftLabel === pairData.leftLabel &&
    window.highlightedPair.rightLabel === pairData.rightLabel) {
    window.highlightedPair = null;
    // Rimuovi classe active da tutte le righe
    document.querySelectorAll('.point-pair-row').forEach(r => r.classList.remove('active'));
    updateCanvasDisplay();
    return;
  }

  window.highlightedPair = pairData;

  // Evidenzia la riga nella tabella
  document.querySelectorAll('.point-pair-row').forEach(r => r.classList.remove('active'));
  rowElement.classList.add('active');

  // Disegna l'evidenziazione sul canvas
  drawPointPairHighlight(pairData);

  // Mostra toast informativo
  showToast(`📍 ${pairData.leftLabel} ↔ ${pairData.rightLabel}: ${pairData.fartherPoint} più esterno, ${pairData.higherPoint} più alto`, 'info');
}

/**
 * Rimuove l'evidenziazione della coppia punti dal canvas
 */
function clearPointPairHighlight() {
  if (!fabricCanvas) return;

  // Rimuovi oggetti overlay precedenti
  window.highlightOverlayObjects.forEach(obj => {
    fabricCanvas.remove(obj);
  });
  window.highlightOverlayObjects = [];
}

/**
 * Disegna l'evidenziazione visiva di una coppia di punti (click su riga tabella).
 *
 * Layout:
 *   • Cerchio ciano (sinistro) e arancione (destro), etichetta nome al centro.
 *   • Linea tratteggiata di connessione.
 *   • Frecce ORIZZONTALI: entrambe puntano nella direzione del punto più esterno
 *     (frecce convergenti verso il lato dominante), NON frecce speculari.
 *     Il punto esterno ha la freccia sul suo lato esterno, il punto interno
 *     ha la freccia sullo stesso lato (verso il dominante).
 *   • Frecce VERTICALI: ↑ sopra il cerchio più alto, ↓ sotto quello più basso.
 *   • Badge info centrato che mostra ↔ Δpx laterale e ↕ Δpx altezza.
 *
 * Tutte le frecce: stessa opacità e stesso peso → no disparità visiva.
 * Frecce attaccate alla circonferenza (gap 0px).
 */
function drawPointPairHighlight(pairData) {
  if (!fabricCanvas || !currentImage) return;

  const lt = transformGreenDotCoordinate(pairData.leftPoint[0], pairData.leftPoint[1]);
  const rt = transformGreenDotCoordinate(pairData.rightPoint[0], pairData.rightPoint[1]);
  const lx = lt.x, ly = lt.y;
  const rx = rt.x, ry = rt.y;

  console.log(`🎯 Highlight: L(${lx.toFixed(0)},${ly.toFixed(0)}) R(${rx.toFixed(0)},${ry.toFixed(0)})`);

  // ── Costanti ─────────────────────────────────────────────────────────
  const R = 22;          // raggio cerchi
  const AW = 26;          // lunghezza freccia (dal bordo del cerchio)
  const AHW = 9;           // larghezza testa freccia
  const AHH = 12;          // altezza testa freccia
  const SW_CIRC = 2.8;         // border cerchio
  const SW_ARR = 2.2;         // stroke freccia

  const C_LEFT = '#00c8e0';   // ciano
  const C_RIGHT = '#ffa020';   // arancio
  const C_HORIZ = '#ff3355';   // rosso-coral per differenza laterale
  const C_VERT = '#44ee88';   // verde per differenza verticale
  const C_LINE = 'rgba(255,255,255,0.45)';

  const leftIsOuter = pairData.fartherPoint === pairData.leftLabel;
  const leftIsHigher = ly < ry;

  const objs = [];

  // ── helper ── disegna freccia (linea + triangolo) senza fabric.Group
  function arrow(x1, y1, x2, y2, color) {
    const ang = Math.atan2(y2 - y1, x2 - x1);
    objs.push(new fabric.Line([x1, y1, x2, y2], {
      stroke: color, strokeWidth: SW_ARR,
      strokeLineCap: 'round',
      selectable: false, evented: false
    }));
    objs.push(new fabric.Triangle({
      left: x2, top: y2,
      width: AHW, height: AHH,
      fill: color,
      angle: ang * 180 / Math.PI + 90,
      originX: 'center', originY: 'center',
      selectable: false, evented: false
    }));
  }

  // ── Linea di connessione ────────────────────────────────────────────
  objs.push(new fabric.Line([lx, ly, rx, ry], {
    stroke: C_LINE, strokeWidth: 1.5,
    strokeDashArray: [7, 5], selectable: false, evented: false
  }));

  // ── Cerchi con fill semi-trasparente ────────────────────────────────
  objs.push(new fabric.Circle({
    left: lx, top: ly, radius: R,
    fill: 'rgba(0,200,224,0.12)', stroke: C_LEFT, strokeWidth: SW_CIRC,
    originX: 'center', originY: 'center', selectable: false, evented: false
  }));
  objs.push(new fabric.Circle({
    left: rx, top: ry, radius: R,
    fill: 'rgba(255,160,32,0.12)', stroke: C_RIGHT, strokeWidth: SW_CIRC,
    originX: 'center', originY: 'center', selectable: false, evented: false
  }));

  // ── Etichette dentro i cerchi ───────────────────────────────────────
  objs.push(new fabric.Text(pairData.leftLabel, {
    left: lx, top: ly, fontSize: 10,
    fill: C_LEFT, fontWeight: 'bold', fontFamily: 'monospace',
    originX: 'center', originY: 'center', selectable: false, evented: false
  }));
  objs.push(new fabric.Text(pairData.rightLabel, {
    left: rx, top: ry, fontSize: 10,
    fill: C_RIGHT, fontWeight: 'bold', fontFamily: 'monospace',
    originX: 'center', originY: 'center', selectable: false, evented: false
  }));

  // ── Frecce ORIZZONTALI ─────────────────────────────────────────────
  // Entrambe puntano vers il lato del punto più ESTERNO (frecce convergenti).
  // Il punto esterno riceve la freccia sul proprio lato esterno (outward).
  // Il punto interno riceve la freccia sul lato opposto (verso il dominante).
  if (leftIsOuter) {
    // Punto sinistro più esterno → entrambe verso sinistra (←)
    arrow(lx - R, ly, lx - R - AW, ly, C_HORIZ); // LC: outward ←
    arrow(rx - R, ry, rx - R - AW, ry, C_HORIZ); // RC: anche ← (verso il lato dominante sinistro)
  } else {
    // Punto destro più esterno → entrambe verso destra (→)
    arrow(lx + R, ly, lx + R + AW, ly, C_HORIZ); // LC: → verso il lato dominante destro
    arrow(rx + R, ry, rx + R + AW, ry, C_HORIZ); // RC: outward →
  }

  // ── Frecce VERTICALI ──────────────────────────────────────────────
  // Punto più alto: ↑ sopra il cerchio | Punto più basso: ↓ sotto
  const hx = leftIsHigher ? lx : rx, hy = leftIsHigher ? ly : ry;
  const ox = leftIsHigher ? rx : lx, oy = leftIsHigher ? ry : ly;
  arrow(hx, hy - R, hx, hy - R - AW, C_VERT); // ↑ più alto
  arrow(ox, oy + R, ox, oy + R + AW, C_VERT); // ↓ più basso

  // ── Badge info centrale ────────────────────────────────────────────
  // Rettangolo arrotondato + testo con entrambi i delta
  const midX = (lx + rx) / 2;
  const topY = Math.min(ly - R, ry - R) - 38;
  const dH = pairData.heightDiff.toFixed(0);
  const dD = pairData.distanceDiff.toFixed(0);
  const badge = `↔ ${dD}px    ↕ ${dH}px`;
  const bW = badge.length * 7 + 22;
  const bH = 24;

  objs.push(new fabric.Rect({
    left: midX, top: topY, width: bW, height: bH, rx: 7, ry: 7,
    fill: 'rgba(8,8,18,0.86)',
    stroke: 'rgba(255,255,255,0.20)', strokeWidth: 1,
    originX: 'center', originY: 'center',
    selectable: false, evented: false
  }));
  objs.push(new fabric.Text(badge, {
    left: midX, top: topY, fontSize: 11.5,
    fill: '#f0f0f0', fontWeight: 'bold', fontFamily: 'monospace',
    originX: 'center', originY: 'center',
    selectable: false, evented: false
  }));

  // ── Aggiunge al canvas ─────────────────────────────────────────────
  objs.forEach(o => { fabricCanvas.add(o); window.highlightOverlayObjects.push(o); });
  fabricCanvas.renderAll();
}

/**
 * Crea una freccia come gruppo di oggetti Fabric.js
 */
function createArrow(x1, y1, x2, y2, color, strokeWidth) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const headLength = 12;

  // Linea principale
  const line = new fabric.Line([x1, y1, x2, y2], {
    stroke: color,
    strokeWidth: strokeWidth,
    selectable: false,
    evented: false
  });

  // Punta della freccia (triangolo)
  const headX1 = x2 - headLength * Math.cos(angle - Math.PI / 6);
  const headY1 = y2 - headLength * Math.sin(angle - Math.PI / 6);
  const headX2 = x2 - headLength * Math.cos(angle + Math.PI / 6);
  const headY2 = y2 - headLength * Math.sin(angle + Math.PI / 6);

  const arrowHead = new fabric.Triangle({
    left: x2,
    top: y2,
    width: 10,
    height: 15,
    fill: color,
    angle: (angle * 180 / Math.PI) + 90,
    originX: 'center',
    originY: 'center',
    selectable: false,
    evented: false
  });

  // Raggruppa linea e punta
  const group = new fabric.Group([line, arrowHead], {
    selectable: false,
    evented: false
  });

  return group;
}

/**
 * Resetta l'evidenziazione quando si aggiorna il canvas
 */
function resetPointPairHighlightOnUpdate() {
  // Mantieni l'evidenziazione se presente
  if (window.highlightedPair) {
    // Ridisegna dopo un breve delay per permettere all'overlay base di essere disegnato
    setTimeout(() => {
      drawPointPairHighlight(window.highlightedPair);
    }, 100);
  }
}

// ==================== END POINT PAIR HIGHLIGHT TOOL ====================

// Esponi le funzioni globalmente
window.setAnalysisSourceCanvas = setAnalysisSourceCanvas;
window.highlightPointPair = highlightPointPair;
window.clearPointPairHighlight = clearPointPairHighlight;

function getCanvasImageAsBase64(maxDimension = null) {
  /**
   * Ottiene l'immagine corrente dal canvas come stringa base64.
   * Prende solo l'immagine di base senza overlay.
   * PRESERVA IL FORMATO ORIGINALE (JPG→JPG, PNG→PNG) per evitare conversioni che degradano la qualità.
   * 
   * @param {number|null} maxDimension - Dimensione massima (larghezza o altezza). Se null, usa dimensioni originali.
   * @returns {string|null} - Immagine in formato base64
   */
  try {
    if (!currentImage) {
      console.warn('⚠️ Nessuna immagine corrente disponibile');
      return null;
    }

    // Crea un canvas temporaneo con solo l'immagine base
    const tempCanvas = document.createElement('canvas');
    const tempCtx = tempCanvas.getContext('2d');

    // Ottiene l'elemento HTML dall'oggetto Fabric.js
    let imageElement;
    if (currentImage.getElement) {
      imageElement = currentImage.getElement();
    } else if (currentImage.src) {
      // Se currentImage è già un elemento HTML
      imageElement = currentImage;
    } else {
      console.error('❌ currentImage non è un oggetto valido');
      return null;
    }

    // Recupera il tipo MIME originale (preserva JPG/PNG)
    const originalMimeType = imageElement._originalMimeType || 'image/jpeg';
    const isPNG = originalMimeType.includes('png');
    const outputFormat = isPNG ? 'image/png' : 'image/jpeg';
    const quality = isPNG ? undefined : 0.95; // Quality solo per JPEG

    // Se disponibile, usa il canvas full-res salvato al caricamento dell'immagine statica.
    // Questo evita che l'analisi lavori sulla versione ridimensionata (1800px) caricata
    // in Fabric.js per performance, invece della risoluzione originale del file.
    // Per i frame video questo valore è null, quindi si usa imageElement come sempre.
    const sourceElement = window.highResCanvasForAnalysis || imageElement;

    // Ottiene dimensioni originali dalla sorgente (full-res se disponibile)
    const origWidth = sourceElement.naturalWidth || sourceElement.width || 800;
    const origHeight = sourceElement.naturalHeight || sourceElement.height || 600;
    if (window.highResCanvasForAnalysis) {
      console.log(`🔬 Analisi su canvas full-res: ${origWidth}x${origHeight} (display Fabric.js: ${imageElement.naturalWidth || imageElement.width}x${imageElement.naturalHeight || imageElement.height})`);
    }

    // Calcola dimensioni finali con resize se necessario
    let finalWidth = origWidth;
    let finalHeight = origHeight;
    let needsResize = false;
    let resizeScale = 1.0;

    // Applica resize SOLO se l'immagine supera maxDimension
    if (maxDimension) {
      const maxOriginal = Math.max(origWidth, origHeight);
      if (maxOriginal > maxDimension) {
        needsResize = true;
        resizeScale = maxDimension / maxOriginal;
        finalWidth = Math.round(origWidth * resizeScale);
        finalHeight = Math.round(origHeight * resizeScale);
        console.log(`📐 Resize applicato: ${origWidth}x${origHeight} → ${finalWidth}x${finalHeight} (scala: ${resizeScale.toFixed(2)})`);
      } else {
        console.log(`✅ Immagine già ottimale: ${origWidth}x${origHeight} (max consentito: ${maxDimension}px) - Nessun resize`);
      }
    }

    // Salva la scala applicata per uso esterno (es. eyebrow processor)
    window.lastImageResizeScale = resizeScale;

    // === GESTIONE ROTAZIONE FABRIC.JS ===
    // currentImage.angle contiene la rotazione applicata dall'utente (es. "ruota 90°")
    // L'imageElement grezzo NON ha questa rotazione: dobbiamo applicarla noi.
    const fabricAngle = (currentImage.angle || 0);
    const normalizedAngle = ((fabricAngle % 360) + 360) % 360;
    const angleRad = normalizedAngle * Math.PI / 180;
    const flipX = currentImage.flipX || false;
    const flipY = currentImage.flipY || false;
    const hasTransform = (normalizedAngle !== 0 || flipX || flipY);

    // Calcola le dimensioni del canvas di output DOPO la rotazione.
    // Per 90°/270° le dimensioni si invertono; per 0°/180° rimangono uguali.
    const cosA = Math.abs(Math.cos(angleRad));
    const sinA = Math.abs(Math.sin(angleRad));
    const rotatedCanvasW = Math.round(finalWidth * cosA + finalHeight * sinA);
    const rotatedCanvasH = Math.round(finalWidth * sinA + finalHeight * cosA);

    // Imposta le dimensioni del canvas temporaneo (ruotato)
    tempCanvas.width = rotatedCanvasW;
    tempCanvas.height = rotatedCanvasH;

    // Disegna l'immagine applicando rotazione e flip se necessario
    // Usa sourceElement (full-res per immagini statiche, element Fabric.js per video)
    if (hasTransform) {
      tempCtx.save();
      tempCtx.translate(rotatedCanvasW / 2, rotatedCanvasH / 2);
      tempCtx.rotate(angleRad);
      if (flipX) tempCtx.scale(-1, 1);
      if (flipY) tempCtx.scale(1, -1);
      tempCtx.drawImage(sourceElement, -finalWidth / 2, -finalHeight / 2, finalWidth, finalHeight);
      tempCtx.restore();
      console.log(`🔄 Rotazione applicata: ${normalizedAngle}°, flipX=${flipX}, flipY=${flipY} → canvas: ${rotatedCanvasW}x${rotatedCanvasH}`);
    } else {
      // Nessuna trasformazione: disegno diretto
      tempCtx.drawImage(sourceElement, 0, 0, finalWidth, finalHeight);
    }

    // Converti direttamente in base64 senza ulteriori elaborazioni
    // Quality massima (0.98) per preservare tutti i dettagli
    const base64Data = tempCanvas.toDataURL('image/jpeg', 0.98);
    console.log('✅ Immagine convertita in base64:', {
      source: window.highResCanvasForAnalysis ? 'full-res canvas' : 'fabric element',
      original: `${origWidth}x${origHeight}`,
      final: `${rotatedCanvasW}x${rotatedCanvasH}`,
      drawSize: `${finalWidth}x${finalHeight}`,
      resized: needsResize,
      angle: `${normalizedAngle}°`,
      flipX, flipY,
      format: `${outputFormat.toUpperCase()} ${isPNG ? '(lossless)' : '(quality 95)'}`,
      originalMimeType: originalMimeType,
    });

    return base64Data;

  } catch (error) {
    console.error('❌ Errore conversione canvas a base64:', error);
    return null;
  }
}

// toggleMeasureMode() rimosso - usa la versione in canvas-modes.js

// === GESTIONE SHORTCUTS ===

function initializeKeyboardShortcuts() {
  document.addEventListener('keydown', function (e) {
    // Ctrl+C - Copia
    if (e.ctrlKey && e.key === 'c') {
      e.preventDefault();
      console.log('Copia (Ctrl+C)');
    }

    // Ctrl+V - Incolla
    if (e.ctrlKey && e.key === 'v') {
      e.preventDefault();
      console.log('Incolla (Ctrl+V)');
    }

    // ESC - Annulla operazione
    if (e.key === 'Escape') {
      setTool('selection');
      updateStatus('Operazione annullata');
    }

    // Spazio - Pan temporaneo
    if (e.key === ' ' && !e.repeat) {
      e.preventDefault();
      // TODO: Attivare pan temporaneo
    }
  });
}

// === SISTEMA MISURAZIONE ===

function handleMeasurementLandmarkSelection(canvasX, canvasY) {
  /**
   * Gestisce la selezione di un landmark per la misurazione.
   * Calcola distanza (2 punti) o area poligono (3+ punti).
   */
  if (!fabricCanvas || !window.measurementMode) return;

  const nearestLandmark = findNearestLandmarkOnCanvas(canvasX, canvasY);

  if (nearestLandmark && nearestLandmark.distance < 20) {
    const landmarkId = nearestLandmark.landmarkIndex;
    const landmark = window.currentLandmarks[landmarkId];

    // Verifica se già selezionato
    const alreadySelected = window.selectedLandmarksForMeasurement.find(l => l.id === landmarkId);
    if (alreadySelected) {
      console.log(`⚠️ Landmark ${landmarkId} già selezionato per misurazione`);
      return;
    }

    // Usa le coordinate del canvas (già trasformate) dal landmark trovato
    const canvasCoords = {
      x: nearestLandmark.centerX,
      y: nearestLandmark.centerY
    };

    // Aggiungi alla lista di misurazione con coordinate canvas
    const landmarkData = {
      id: landmarkId,
      x: canvasCoords.x,
      y: canvasCoords.y,
      name: getLandmarkName(landmarkId)
    };
    window.selectedLandmarksForMeasurement.push(landmarkData);

    // Evidenzia il landmark
    const hue = (landmarkId * 137) % 360;
    const color = `hsl(${hue}, 90%, 50%)`;
    highlightMeasurementLandmark(landmarkId, color);

    console.log(`✅ Landmark ${landmarkId} aggiunto per misurazione (${window.selectedLandmarksForMeasurement.length} punti) - Canvas coords: (${canvasCoords.x.toFixed(1)}, ${canvasCoords.y.toFixed(1)})`);

    // Calcola misurazione in base al numero di punti
    const numPoints = window.selectedLandmarksForMeasurement.length;
    if (numPoints === 2) {
      calculateDistance();
    } else if (numPoints >= 3) {
      calculatePolygonAreaFromSelection();
    }

    // Mostra il pulsante "NUOVA MISURAZIONE" quando c'è almeno una misurazione valida (2+ punti)
    if (numPoints >= 2) {
      const completeBtn = document.getElementById('complete-measure-btn');
      if (completeBtn) {
        completeBtn.style.display = 'block';
      }
    }

    updateStatus(`📐 ${numPoints} punto/i selezionato/i per misurazione`);
  }
}

// Esponi la funzione a window
window.handleMeasurementLandmarkSelection = handleMeasurementLandmarkSelection;

function calculateDistance() {
  /**
   * Calcola la distanza euclidea tra i primi 2 punti selezionati.
   */
  if (window.selectedLandmarksForMeasurement.length < 2) return;

  const p1 = window.selectedLandmarksForMeasurement[0];
  const p2 = window.selectedLandmarksForMeasurement[1];

  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const distance = Math.sqrt(dx * dx + dy * dy);

  const result = {
    type: 'distance',
    label: `Distanza ${p1.name} → ${p2.name}`,
    value: distance.toFixed(2),
    unit: 'px',
    landmarks: [p1.id, p2.id]
  };

  // Inizializza array se non esiste
  if (!window.measurementResults) {
    window.measurementResults = [];
  }

  // Rimuovi la misurazione temporanea corrente se esiste (l'ultima aggiunta)
  // Questo permette di aggiornare la misurazione in corso mentre si aggiungono punti
  const lastResult = window.measurementResults[window.measurementResults.length - 1];
  if (lastResult && !lastResult.completed) {
    window.measurementResults.pop();
    // Rimuovi overlay precedenti della misurazione temporanea
    removeMeasurementOverlaysExceptHighlights();
  }

  // Aggiungi la nuova distanza come misurazione temporanea (non completata)
  result.completed = false;
  window.measurementResults.push(result);

  updateMeasurementsTable();
  drawMeasurementLine(p1, p2, distance);

  console.log(`📏 Distanza calcolata: ${distance.toFixed(2)} px`);
}

function calculatePolygonAreaFromSelection() {
  /**
   * Calcola l'area del poligono formato dai punti selezionati usando la formula Shoelace.
   */
  if (window.selectedLandmarksForMeasurement.length < 3) return;

  const points = window.selectedLandmarksForMeasurement;
  let area = 0;

  // Formula Shoelace (Gauss)
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length;
    area += points[i].x * points[j].y;
    area -= points[j].x * points[i].y;
  }
  area = Math.abs(area) / 2;

  const landmarkIds = points.map(p => p.id);
  const result = {
    type: 'area',
    label: `Area Poligono (${points.length} punti)`,
    value: area.toFixed(2),
    unit: 'px²',
    landmarks: landmarkIds
  };

  // Inizializza array se non esiste
  if (!window.measurementResults) {
    window.measurementResults = [];
  }

  // Rimuovi la misurazione temporanea corrente se esiste (l'ultima aggiunta)
  // Questo permette di aggiornare la misurazione in corso mentre si aggiungono punti
  const lastResult = window.measurementResults[window.measurementResults.length - 1];
  if (lastResult && !lastResult.completed) {
    window.measurementResults.pop();
    // Rimuovi overlay precedenti della misurazione temporanea
    removeMeasurementOverlaysExceptHighlights();
  }

  // Aggiungi la nuova area come misurazione temporanea (non completata)
  result.completed = false;
  window.measurementResults.push(result);

  updateMeasurementsTable();
  drawMeasurementPolygon(points, area);

  console.log(`📐 Area poligono calcolata: ${area.toFixed(2)} px²`);
}

function updateMeasurementsTable() {
  /**
   * Aggiorna la tabella misurazioni con i risultati.
   */
  const tbody = document.getElementById('measurements-data');
  if (!tbody) {
    console.error('❌ Tabella measurements-data non trovata');
    return;
  }

  // Pulisci tabella esistente
  tbody.innerHTML = '';

  // Aggiungi righe per ogni risultato
  window.measurementResults.forEach((result) => {
    const row = document.createElement('tr');
    const statusText = result.completed ? '✅ Completata' : '🔄 In corso...';
    const statusClass = result.completed ? 'status-ok' : 'status-pending';

    row.innerHTML = `
      <td>${result.label}</td>
      <td><strong>${result.value}</strong></td>
      <td>${result.unit}</td>
      <td><span class="${statusClass}">${statusText}</span></td>
    `;

    // Evidenzia la riga in corso con sfondo scuro e testo chiaro
    if (!result.completed) {
      row.style.backgroundColor = '#856404';
      row.style.color = '#fff';
    }

    tbody.appendChild(row);
  });

  // Apri automaticamente la sezione MISURAZIONI (vecchia - ora nascosta)
  openMeasurementsSection();

  // Apri la sezione DATI ANALISI unificata e sincronizza
  openUnifiedAnalysisSection();

  // Se il tab corrente è measurements, aggiorna subito la tabella unificata
  if (window.unifiedTableCurrentTab === 'measurements') {
    syncUnifiedTableWithOriginal();
  }

  console.log(`📊 Tabella misurazioni aggiornata: ${window.measurementResults.length} risultati`);
}

function openMeasurementsSection() {
  /**
   * Apre automaticamente la sezione MISURAZIONI nella sidebar destra.
   */
  const sections = document.querySelectorAll('.right-sidebar .section');
  sections.forEach(section => {
    const toggleBtn = section.querySelector('.toggle-btn');
    if (toggleBtn && toggleBtn.textContent.includes('📏 MISURAZIONI')) {
      const content = section.querySelector('.section-content');
      const icon = section.querySelector('.icon');
      if (content && content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '▼';
        section.setAttribute('data-expanded', 'true');
        console.log('📏 Sezione MISURAZIONI aperta automaticamente');
      }
    }
  });
}

function removeMeasurementOverlaysExceptHighlights() {
  /**
   * Rimuove linee e poligoni di misurazione dal canvas, ma mantiene gli highlights dei landmark.
   */
  if (!fabricCanvas) return;

  const overlaysToRemove = fabricCanvas.getObjects().filter(obj =>
    obj.isMeasurement && obj.measurementType !== 'highlight'
  );
  overlaysToRemove.forEach(obj => fabricCanvas.remove(obj));
  fabricCanvas.renderAll();
}

function clearAllMeasurementOverlays() {
  /**
   * Pulisce tutte le misurazioni: resetta contatore punti, rimuove overlay dal canvas,
   * svuota tabella misurazioni e landmarks, riporta i pulsanti verdi ad arancioni,
   * e disattiva tutti gli overlay associati ai pulsanti attivi.
   */
  console.log('🧹 Pulizia misurazioni e reset pulsanti attivi...');

  // === DISATTIVA PULSANTI TOGGLE E LORO OVERLAY ===

  // 1. Disattiva asse di simmetria
  const axisBtn = document.getElementById('axis-btn');
  if (axisBtn && axisBtn.classList.contains('active')) {
    axisBtn.classList.remove('active');
    window.symmetryAxisVisible = false;
    if (typeof clearSymmetryAxis === 'function') {
      clearSymmetryAxis();
    }
    console.log('✅ Asse di simmetria disattivato');
  }

  // 2. Disattiva landmarks
  const landmarksBtn = document.getElementById('landmarks-btn');
  if (landmarksBtn && landmarksBtn.classList.contains('active')) {
    landmarksBtn.classList.remove('active');
    window.landmarkSelectionMode = false;
    window.landmarksVisible = false;
    if (typeof window.clearLandmarks === 'function') {
      window.clearLandmarks();
    }
    console.log('✅ Landmarks disattivati');
  }

  // 3. Disattiva modalità misura
  const measureBtn = document.getElementById('measure-btn');
  if (measureBtn && measureBtn.classList.contains('active')) {
    measureBtn.classList.remove('active');
    window.measurementMode = false;
    if (typeof window.measureModeActive !== 'undefined') {
      window.measureModeActive = false;
    }
    console.log('✅ Modalità misura disattivata');
  }

  // 4. Disattiva green dots
  const greenDotsBtn = document.getElementById('green-dots-btn');
  if (greenDotsBtn && greenDotsBtn.classList.contains('active')) {
    greenDotsBtn.classList.remove('active');
    // Rimuovi green dots dal canvas
    if (fabricCanvas) {
      const greenDots = fabricCanvas.getObjects().filter(obj => obj.isGreenDot || obj.isGreenDotsOverlay);
      greenDots.forEach(obj => fabricCanvas.remove(obj));
    }
    console.log('✅ Green dots disattivati');
  }

  // === DISATTIVA TUTTI I PULSANTI DI MISURAZIONE CON OVERLAY ===

  // Trova tutti i pulsanti con classe btn-active (pulsanti di misurazione attivi)
  document.querySelectorAll('.btn-analysis.btn-active').forEach(btn => {
    btn.classList.remove('btn-active');
    console.log('🔄 Disattivato pulsante misurazione:', btn.textContent.trim());
  });

  // Pulisci tutti gli overlay di misurazione usando la mappa globale
  if (typeof window.measurementOverlays !== 'undefined' && window.measurementOverlays) {
    window.measurementOverlays.forEach((overlayObjects, measurementType) => {
      overlayObjects.forEach(obj => {
        if (fabricCanvas) {
          fabricCanvas.remove(obj);
        }
      });
      console.log(`🧹 Rimosso overlay: ${measurementType}`);
    });
    window.measurementOverlays.clear();
  }

  // Pulisci anche activeMeasurements
  if (typeof window.activeMeasurements !== 'undefined' && window.activeMeasurements) {
    window.activeMeasurements.clear();
  }

  // Invalida cache overlay sopracciglia (immagine cambiata → vecchio PNG non più valido)
  window._eyebrowSymmetryCache = null;

  // Rimuovi la classe 'active' da tutti gli altri pulsanti .btn-analysis rimasti
  document.querySelectorAll('.btn-analysis.active').forEach(btn => {
    btn.classList.remove('active');
    console.log('🔄 Rimossa classe active da:', btn.textContent.trim());
  });

  // === PULISCI TABELLE ===

  // Reset variabili
  window.selectedLandmarksForMeasurement = [];
  window.measurementResults = [];

  // Pulisci tabella misurazioni
  const tbody = document.getElementById('measurements-data');
  if (tbody) {
    tbody.innerHTML = '';
  }

  // Pulisci tabella landmarks
  const landmarksTbody = document.getElementById('landmarks-data');
  if (landmarksTbody) {
    landmarksTbody.innerHTML = '';
  }

  // Pulisci la tabella unificata se sta mostrando misurazioni o landmarks (ma non debug)
  const unifiedTableBody = document.getElementById('unified-table-body');
  const currentTab = window.unifiedTableCurrentTab;
  if (unifiedTableBody && (currentTab === 'measurements' || currentTab === 'landmarks')) {
    unifiedTableBody.innerHTML = '';
  }

  // === PULISCI OVERLAY DAL CANVAS ===

  // Rimuovi tutti gli overlay di misurazione generici dal canvas
  if (fabricCanvas) {
    const measurementObjects = fabricCanvas.getObjects().filter(obj =>
      obj.isMeasurement || obj.isMeasurementOverlay || obj.isMeasurementLine || obj.isMeasurementLabel
    );
    measurementObjects.forEach(obj => fabricCanvas.remove(obj));
    fabricCanvas.renderAll();
  }

  // === PULISCI LINEE PERPENDICOLARI E COPPIE ===

  // Pulisci linee perpendicolari
  if (typeof clearPerpendicularLines === 'function') {
    clearPerpendicularLines();
    perpendicularLines = [];
    window.perpendicularLines = perpendicularLines;
    console.log('✅ Linee perpendicolari rimosse');
  }

  // Pulisci coppie di linee verticali speculari
  if (typeof clearCoupleLines === 'function') {
    clearCoupleLines();
    coupleLines = [];
    coupleLineCounter = 0;
    window.coupleLines = coupleLines;
    console.log('✅ Coppie linee verticali rimosse');
  }

  // Nascondi il pulsante "NUOVA MISURAZIONE"
  const completeBtn = document.getElementById('complete-measure-btn');
  if (completeBtn) {
    completeBtn.style.display = 'none';
  }

  updateStatus('🧹 Tutti i pulsanti e overlay puliti - Riparti da zero');
  console.log('✅ Pulizia completa: pulsanti, overlay, tabelle misurazioni e landmarks');
}

function completeMeasurement() {
  /**
   * Completa la misurazione corrente e prepara il sistema per una nuova misurazione.
   * - Marca la misurazione corrente come completata
   * - Reset dei punti selezionati per iniziare una nuova misurazione
   * - Rimuove gli highlights temporanei
   * - Mantiene tutte le misurazioni precedenti visibili nella tabella
   */
  console.log('✅ Completamento misurazione corrente...');

  // Verifica se c'è una misurazione in corso
  if (!window.measurementResults || window.measurementResults.length === 0) {
    console.warn('⚠️ Nessuna misurazione da completare');
    updateStatus('⚠️ Nessuna misurazione in corso');
    return;
  }

  // Verifica se ci sono punti selezionati
  if (!window.selectedLandmarksForMeasurement || window.selectedLandmarksForMeasurement.length === 0) {
    console.warn('⚠️ Nessun punto selezionato per la misurazione');
    updateStatus('⚠️ Seleziona almeno 2 punti per una misurazione');
    return;
  }

  // Marca l'ultima misurazione come completata
  const lastMeasurement = window.measurementResults[window.measurementResults.length - 1];
  if (lastMeasurement && !lastMeasurement.completed) {
    lastMeasurement.completed = true;
    console.log(`✅ Misurazione completata: ${lastMeasurement.label} = ${lastMeasurement.value} ${lastMeasurement.unit}`);
  }

  // Reset punti selezionati per nuova misurazione
  window.selectedLandmarksForMeasurement = [];

  // Rimuovi solo gli highlights (cerchi colorati) ma mantieni linee/poligoni completati
  if (fabricCanvas) {
    const highlights = fabricCanvas.getObjects().filter(obj =>
      obj.isMeasurement && obj.measurementType === 'highlight'
    );
    highlights.forEach(obj => fabricCanvas.remove(obj));
    fabricCanvas.renderAll();
  }

  // Aggiorna tabella per mostrare lo stato "Completata"
  updateMeasurementsTable();

  // Nascondi il pulsante "NUOVA MISURAZIONE" fino al prossimo punto
  const completeBtn = document.getElementById('complete-measure-btn');
  if (completeBtn) {
    completeBtn.style.display = 'none';
  }

  updateStatus('✅ Misurazione completata! Inizia una nuova misurazione selezionando i punti');
  console.log('🔄 Pronto per nuova misurazione');
}

// Esponi le funzioni a window
window.clearAllMeasurementOverlays = clearAllMeasurementOverlays;
window.completeMeasurement = completeMeasurement;

function highlightMeasurementLandmark(landmarkId, color) {
  /**
   * Evidenzia un landmark selezionato per misurazione con un cerchio colorato.
   */
  if (!fabricCanvas) return;

  // Trova il landmark sul canvas
  const landmarkObjects = fabricCanvas.getObjects().filter(obj =>
    obj.isLandmark && obj.landmarkType === 'mediapipe' && obj.landmarkIndex === landmarkId
  );

  if (landmarkObjects.length > 0) {
    const landmark = landmarkObjects[0];

    // Crea un cerchio di evidenziazione più grande
    const highlightCircle = new fabric.Circle({
      left: landmark.left - 3,
      top: landmark.top - 3,
      radius: landmark.radius + 3,
      fill: 'transparent',
      stroke: color,
      strokeWidth: 3,
      selectable: false,
      evented: false,
      isMeasurement: true,
      measurementType: 'highlight'
    });

    fabricCanvas.add(highlightCircle);
    fabricCanvas.renderAll();
  }
}

function drawMeasurementLine(p1, p2, distance) {
  /**
   * Disegna una linea tra 2 punti con l'etichetta della distanza.
   */
  if (!fabricCanvas) return;

  // Linea
  const line = new fabric.Line([p1.x, p1.y, p2.x, p2.y], {
    stroke: '#FF6B6B',
    strokeWidth: 2,
    selectable: false,
    evented: false,
    isMeasurement: true,
    measurementType: 'line'
  });

  // Etichetta con distanza
  const midX = (p1.x + p2.x) / 2;
  const midY = (p1.y + p2.y) / 2;
  const label = new fabric.Text(`${distance.toFixed(1)} px`, {
    left: midX,
    top: midY - 15,
    fontSize: 14,
    fill: '#FF6B6B',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    padding: 3,
    selectable: false,
    evented: false,
    isMeasurement: true,
    measurementType: 'label'
  });

  fabricCanvas.add(line, label);

  // Porta in primo piano per renderli visibili sopra l'immagine
  line.bringToFront();
  label.bringToFront();

  fabricCanvas.renderAll();
  console.log('✅ Linea di misurazione disegnata e portata in primo piano');
}

function drawMeasurementPolygon(points, area) {
  /**
   * Disegna un poligono con i punti selezionati e mostra l'area.
   */
  if (!fabricCanvas) return;

  // Crea array di punti per Fabric.js
  const fabricPoints = points.map(p => ({ x: p.x, y: p.y }));

  // Poligono
  const polygon = new fabric.Polygon(fabricPoints, {
    fill: 'rgba(76, 175, 80, 0.2)',
    stroke: '#4CAF50',
    strokeWidth: 2,
    selectable: false,
    evented: false,
    isMeasurement: true,
    measurementType: 'polygon'
  });

  // Calcola centro del poligono per posizionare l'etichetta
  const centerX = points.reduce((sum, p) => sum + p.x, 0) / points.length;
  const centerY = points.reduce((sum, p) => sum + p.y, 0) / points.length;

  // Etichetta con area
  const label = new fabric.Text(`${area.toFixed(1)} px²`, {
    left: centerX - 30,
    top: centerY - 10,
    fontSize: 14,
    fill: '#4CAF50',
    backgroundColor: 'rgba(255, 255, 255, 0.9)',
    padding: 5,
    selectable: false,
    evented: false,
    isMeasurement: true,
    measurementType: 'label'
  });

  fabricCanvas.add(polygon, label);

  // Porta in primo piano per renderli visibili sopra l'immagine
  polygon.bringToFront();
  label.bringToFront();

  fabricCanvas.renderAll();
  console.log('✅ Poligono di misurazione disegnato e portato in primo piano');
}

// === UTILITIES ===

function updateCursorInfo(x, y) {
  const info = document.getElementById('cursor-info');
  if (info) {
    info.textContent = `Mouse: (${x}, ${y}) | Zoom: 100%`;
  }
}

function updateStatus(message) {
  const statusText = document.getElementById('status-text');
  if (statusText) {
    statusText.textContent = message;
  }
  console.log('📊 Status:', message);
}

function showProgress(message, percentage = 0) {
  const container = document.getElementById('progress-container');
  const bar = document.getElementById('progress-bar');
  const text = document.getElementById('progress-text');

  container.style.display = 'flex';
  bar.style.setProperty('--progress', `${percentage}%`);
  text.textContent = `${percentage}%`;

  updateStatus(message);
}

function hideProgress() {
  const container = document.getElementById('progress-container');
  container.style.display = 'none';
}

function updateBadges() {
  updateWebcamBadge(isWebcamActive);
  updateLandmarksBadge(currentLandmarks.length);
  updateQualityBadge(null);
  updateModeBadge(currentTool);
}

function updateWebcamBadge(connected) {
  const badge = document.getElementById('webcam-badge');
  if (badge) {
    badge.textContent = connected ? '📹 Webcam: Connessa' : '📹 Webcam: Disconnessa';
    badge.className = connected ? 'badge connected' : 'badge disconnected';
  }
}

function updateLandmarksBadge(count) {
  const badge = document.getElementById('landmarks-badge');
  if (badge) {
    badge.textContent = `🎯 Landmarks: ${count}`;
    badge.className = count > 0 ? 'badge connected' : 'badge disconnected';
  }
}

function updateQualityBadge(score) {
  const badge = document.getElementById('quality-badge');
  if (badge) {
    if (score === null) {
      badge.textContent = '⭐ Qualità: N/A';
      badge.className = 'badge disconnected';
    } else if (score >= 0.8) {
      badge.textContent = `⭐ Qualità: Eccellente (${score.toFixed(3)})`;
      badge.className = 'badge quality-excellent';
    } else if (score >= 0.6) {
      badge.textContent = `⭐ Qualità: Buona (${score.toFixed(3)})`;
      badge.className = 'badge quality-good';
    } else {
      badge.textContent = `⭐ Qualità: Scarsa (${score.toFixed(3)})`;
      badge.className = 'badge quality-poor';
    }
  }
}

function updateModeBadge(mode) {
  const badge = document.getElementById('mode-badge');
  if (badge) {
    const modes = {
      'selection': '🔧 Modalità: Selezione',
      'zoom-in': '🔧 Modalità: Zoom In',
      'zoom-out': '🔧 Modalità: Zoom Out',
      'pan': '🔧 Modalità: Pan',
      'line': '🔧 Modalità: Linea',
      'rectangle': '🔧 Modalità: Rettangolo',
      'circle': '🔧 Modalità: Cerchio',
      'measure': '🔧 Modalità: Misura'
    };

    badge.textContent = modes[mode] || '🔧 Modalità: Sconosciuta';
    badge.className = 'badge info';
  }
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;

  document.body.appendChild(toast);

  // Rimuovi dopo 3 secondi
  setTimeout(() => {
    if (toast.parentNode) {
      toast.parentNode.removeChild(toast);
    }
  }, 3000);
}

function showContextMenu(x, y) {
  // TODO: Implementare menu contestuale
  console.log(`Menu contestuale richiesto a (${x}, ${y})`);
}

// === GESTIONE TABELLE DATI ===

function updateLandmarksTable(landmarks) {
  const tbody = document.getElementById('landmarks-data');
  if (!tbody) {
    console.warn('⚠️ Tabella landmarks non trovata');
    return;
  }

  // Pulisci tabella esistente
  tbody.innerHTML = '';

  if (!landmarks || landmarks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5">Nessun landmark rilevato</td></tr>';
    updateLandmarksBadge(0);
    // Reset variabili paginazione
    allCurrentLandmarks = [];
    currentLandmarksPage = 0;
    updateLandmarksPagination(0, 0, 10);
    return;
  }

  // 💾 Salva landmarks globalmente per paginazione
  allCurrentLandmarks = landmarks;
  currentLandmarksPage = 0;

  // 📏 LIMITAZIONE: Mostra solo i primi 10 landmarks principali
  const maxLandmarksToShow = 10;
  const landmarksToShow = landmarks.slice(0, maxLandmarksToShow);
  const totalLandmarks = landmarks.length;

  // Aggiungi landmarks alla tabella (solo i primi 10)
  landmarksToShow.forEach((landmark, index) => {
    const row = tbody.insertRow();

    // Colore in base al tipo di landmark
    const color = getLandmarkColor(index);

    row.innerHTML = `
      <td><div class="color-indicator" style="background-color: ${color};"></div></td>
      <td>${index}</td>
      <td>${getLandmarkName(index)}</td>
      <td>${landmark.x ? landmark.x.toFixed(1) : 'N/A'}</td>
      <td>${landmark.y ? landmark.y.toFixed(1) : 'N/A'}</td>
    `;
  });

  // 📊 Aggiungi riga informativa se ci sono più di 10 landmarks
  if (totalLandmarks > maxLandmarksToShow) {
    const infoRow = tbody.insertRow();
    infoRow.className = 'landmarks-info-row';
    infoRow.innerHTML = `
      <td colspan="5" style="text-align: center; font-style: italic; color: #888; padding: 8px;">
        📋 Mostrando ${maxLandmarksToShow} di ${totalLandmarks} landmarks totali
        <br><span style="font-size: 9px;">Tutti i landmarks sono visibili sul canvas</span>
      </td>
    `;
  }

  // Aggiorna badge con il numero totale
  updateLandmarksBadge(totalLandmarks);

  console.log(`📊 Tabella landmarks aggiornata: mostrati ${landmarksToShow.length}/${totalLandmarks} punti`);

  // 📄 Gestisci controlli paginazione
  updateLandmarksPagination(totalLandmarks, 0, maxLandmarksToShow);
}

function getLandmarkColor(index) {
  // Colori per diversi tipi di landmarks
  const colors = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
    '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
  ];

  return colors[index % colors.length];
}

function clearLandmarksTable() {
  const tbody = document.getElementById('landmarks-data');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="5">Nessun landmark rilevato</td></tr>';
  }
  updateLandmarksBadge(0);
}

// === DEBUG ANALYSIS TABLE FUNCTIONS ===
function clearDebugAnalysisTable() {
  const tbody = document.getElementById('debug-data');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="7">Nessun dato di analisi</td></tr>';
  }
}

function addDebugAnalysisRow(frameData) {
  const tbody = document.getElementById('debug-data');
  if (!tbody) return;

  // FILTRO: Ignora frame con score troppo basso (< 0.5)
  if (frameData.score < 0.5) {
    console.log(`⏭️ Frame ignorato (score troppo basso): ${frameData.score.toFixed(3)}`);
    return;
  }

  // Rimuovi placeholder se presente
  if (tbody.children.length === 1 && tbody.children[0].textContent.includes('Nessun dato')) {
    tbody.innerHTML = '';
  }

  const row = document.createElement('tr');
  row.setAttribute('data-frame-time', frameData.time);
  row.className = getRowClassByScore(frameData.score);

  // Rendi la riga cliccabile per saltare al frame
  row.style.cursor = 'pointer';
  row.onclick = () => jumpToVideoFrame(frameData.time);

  row.innerHTML = `
    <td>${frameData.frameIndex}</td>
    <td>${formatTime(frameData.time)}</td>
    <td class="score-cell" style="color: ${getFrontalityColor(frameData.score)}">${frameData.score.toFixed(3)}</td>
    <td>${frameData.pose.yaw.toFixed(1)}°</td>
    <td>${frameData.pose.pitch.toFixed(1)}°</td>
    <td>${frameData.pose.roll.toFixed(1)}°</td>
    <td class="status-cell">${frameData.status}</td>
  `;

  tbody.appendChild(row);

  // Apri la sezione DATI ANALISI unificata e switcha al tab DEBUG
  openUnifiedAnalysisSection();
  switchUnifiedTab('debug'); // Forza il passaggio al tab debug

  console.log('🔄 [UNIFIED] Tab DEBUG attivato automaticamente (addRow)');

  // Mantieni solo gli ultimi 50 risultati per performance
  while (tbody.children.length > 50) {
    tbody.removeChild(tbody.firstChild);
  }
}

function highlightBestFramesInTable(topResults) {
  // Rimuovi highlight esistenti
  const tbody = document.getElementById('debug-data');
  if (!tbody) return;

  Array.from(tbody.children).forEach(row => {
    row.classList.remove('best-frame-highlight', 'very-frontal-frame', 'top-frame');
  });

  // 🏆 Aggiungi highlight categorizzato per i frame migliori
  topResults.forEach((result, index) => {
    const row = tbody.querySelector(`[data-frame-time="${result.time}"]`);
    if (row) {
      // Classificazione per ranking
      if (index === 0) {
        row.classList.add('top-frame'); // Primo classificato
        row.title = `🥇 MIGLIOR FRAME - Score: ${result.score.toFixed(3)} | Pitch: ${result.pose.pitch.toFixed(1)}° Yaw: ${result.pose.yaw.toFixed(1)}°`;
      } else if (index < 3) {
        row.classList.add('best-frame-highlight'); // Top 3
        row.title = `🥈 #${index + 1} Frame Frontale - Score: ${result.score.toFixed(3)} | Pitch: ${result.pose.pitch.toFixed(1)}° Yaw: ${result.pose.yaw.toFixed(1)}°`;
      } else if (result.score > 0.7) {
        row.classList.add('very-frontal-frame'); // Molto frontali
        row.title = `⭐ #${index + 1} Frame Molto Frontale - Score: ${result.score.toFixed(3)} | Pitch: ${result.pose.pitch.toFixed(1)}° Yaw: ${result.pose.yaw.toFixed(1)}°`;
      }

      // 📊 Aggiungi badge ranking nella prima colonna
      const firstCell = row.querySelector('td:first-child');
      if (firstCell && index < 5) {
        const badge = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`;
        firstCell.innerHTML = `${badge} ${firstCell.textContent}`;
      }
    }
  });

  // 📈 Mostra riassunto nella console
  console.log(`🏆 TOP ${Math.min(topResults.length, 10)} FRAME FRONTALI EVIDENZIATI NELLA TABELLA:`);
  topResults.slice(0, 10).forEach((result, index) => {
    const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`;
    console.log(`${medal} t=${result.time.toFixed(1)}s - Score: ${result.score.toFixed(3)} | P:${result.pose.pitch.toFixed(1)}° Y:${result.pose.yaw.toFixed(1)}° R:${result.pose.roll.toFixed(1)}°`);
  });
}

// 🎯 Filtri per la tabella dei frame frontali
function filterFramesByFrontality(filterType) {
  const tbody = document.getElementById('debug-data');
  if (!tbody) return;

  const rows = Array.from(tbody.children);
  let visibleCount = 0;

  rows.forEach(row => {
    if (row.textContent.includes('Nessun dato')) {
      return; // Skip placeholder row
    }

    const scoreCell = row.querySelector('.score-cell');
    if (!scoreCell) return;

    const score = parseFloat(scoreCell.textContent);
    let shouldShow = false;

    switch (filterType) {
      case 'all':
        shouldShow = true;
        break;
      case 'frontal':
        shouldShow = score > 0.7;
        break;
      case 'very-frontal':
        shouldShow = score > 0.8;
        break;
      case 'excellent':
        shouldShow = score > 0.9;
        break;
      case 'top':
        shouldShow = row.classList.contains('top-frame') ||
          row.classList.contains('best-frame-highlight') ||
          row.classList.contains('very-frontal-frame');
        break;
    }

    if (shouldShow) {
      row.style.display = '';
      visibleCount++;
    } else {
      row.style.display = 'none';
    }
  });

  // Aggiorna i pulsanti di filtro per mostrare quale è attivo
  document.querySelectorAll('.frontal-filters .btn-mini').forEach(btn => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');

  // Mostra statistiche del filtro
  const filterNames = {
    'all': 'Tutti i frame',
    'frontal': 'Frame frontali (>0.7)',
    'very-frontal': 'Frame molto frontali (>0.8)',
    'excellent': 'Frame eccellenti (>0.9)',
    'top': 'Frame migliori evidenziati'
  };

  showToast(`📊 Filtro: ${filterNames[filterType]} - ${visibleCount} frame visibili`, 'info');
}

// 🔍 Funzione per assicurare che le sezioni della sidebar rimangano visibili
function ensureSidebarSectionsVisible() {
  // ℹ️ Le vecchie sezioni Misurazioni, Landmarks e Debug sono ora unificate in DATI ANALISI
  // Non serve più controllare le singole sezioni perché sono nascoste per compatibilità

  console.log('🔍 Verifica visibilità sezioni sidebar...');

  // Verifica solo che la sidebar principale sia visibile
  const rightSidebar = document.querySelector('.right-sidebar');
  if (rightSidebar) {
    rightSidebar.style.display = 'block';
    console.log('✅ Right sidebar confermata visibile');
  }

  // Verifica che la sezione unificata DATI ANALISI sia presente
  const unifiedSection = document.querySelector('.section .section-header .toggle-btn');
  if (unifiedSection && unifiedSection.textContent.includes('📊 DATI ANALISI')) {
    console.log('✅ Sezione unificata DATI ANALISI trovata e pronta');
  }
}

// 📄 Variabili globali per paginazione landmarks
let currentLandmarksPage = 0;
const landmarksPerPage = 10;
let allCurrentLandmarks = [];

// 📄 Funzioni per gestire la paginazione dei landmarks
function updateLandmarksPagination(totalLandmarks, currentPage, itemsPerPage) {
  const paginationDiv = document.getElementById('landmarks-pagination');
  const pageInfo = document.getElementById('landmarks-page-info');
  const prevBtn = document.getElementById('landmarks-prev');
  const nextBtn = document.getElementById('landmarks-next');

  if (totalLandmarks <= itemsPerPage) {
    // Nascondi controlli se non servono
    paginationDiv.style.display = 'none';
    return;
  }

  // Mostra controlli
  paginationDiv.style.display = 'flex';

  const totalPages = Math.ceil(totalLandmarks / itemsPerPage);
  pageInfo.textContent = `Pagina ${currentPage + 1}/${totalPages} (${totalLandmarks} landmarks)`;

  // Abilita/disabilita pulsanti
  prevBtn.disabled = currentPage === 0;
  nextBtn.disabled = currentPage >= totalPages - 1;

  prevBtn.style.opacity = prevBtn.disabled ? '0.5' : '1';
  nextBtn.style.opacity = nextBtn.disabled ? '0.5' : '1';
}

function showLandmarksPage(direction) {
  if (!allCurrentLandmarks || allCurrentLandmarks.length === 0) {
    showToast('Nessun landmark disponibile', 'warning');
    return;
  }

  const totalPages = Math.ceil(allCurrentLandmarks.length / landmarksPerPage);

  if (direction === 'next' && currentLandmarksPage < totalPages - 1) {
    currentLandmarksPage++;
  } else if (direction === 'prev' && currentLandmarksPage > 0) {
    currentLandmarksPage--;
  }

  // Aggiorna visualizzazione
  updateLandmarksTablePage(allCurrentLandmarks, currentLandmarksPage);
}

function updateLandmarksTablePage(landmarks, page) {
  const tbody = document.getElementById('landmarks-data');
  if (!tbody) return;

  // Calcola indici per la pagina corrente
  const startIndex = page * landmarksPerPage;
  const endIndex = Math.min(startIndex + landmarksPerPage, landmarks.length);
  const pageData = landmarks.slice(startIndex, endIndex);

  // Pulisci e riempi tabella
  tbody.innerHTML = '';

  pageData.forEach((landmark, relativeIndex) => {
    const absoluteIndex = startIndex + relativeIndex;
    const row = tbody.insertRow();
    const color = getLandmarkColor(absoluteIndex);

    row.innerHTML = `
      <td><div class="color-indicator" style="background-color: ${color};"></div></td>
      <td>${absoluteIndex}</td>
      <td>${getLandmarkName(absoluteIndex)}</td>
      <td>${landmark.x ? landmark.x.toFixed(1) : 'N/A'}</td>
      <td>${landmark.y ? landmark.y.toFixed(1) : 'N/A'}</td>
    `;
  });

  // Aggiorna controlli paginazione
  updateLandmarksPagination(landmarks.length, page, landmarksPerPage);

  console.log(`📄 Pagina landmarks ${page + 1}: mostrati ${pageData.length} di ${landmarks.length} totali`);
}

function showAllLandmarks() {
  if (!allCurrentLandmarks || allCurrentLandmarks.length === 0) {
    showToast('Nessun landmark disponibile', 'warning');
    return;
  }

  // Crea una finestra popup con tutti i landmarks
  const popup = window.open('', 'AllLandmarks', 'width=600,height=400,scrollbars=yes');

  let html = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Tutti i Landmarks (${allCurrentLandmarks.length})</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #2a2a2a; color: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #555; }
        th { background: #404040; }
        tr:nth-child(even) { background: #333; }
        .color-indicator { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 5px; }
      </style>
    </head>
    <body>
      <h2>🎯 Tutti i Landmarks (${allCurrentLandmarks.length} punti)</h2>
      <table>
        <thead>
          <tr><th>🎨</th><th>ID</th><th>Nome</th><th>X</th><th>Y</th></tr>
        </thead>
        <tbody>
  `;

  allCurrentLandmarks.forEach((landmark, index) => {
    const color = getLandmarkColor(index);
    html += `
      <tr>
        <td><div class="color-indicator" style="background-color: ${color};"></div></td>
        <td>${index}</td>
        <td>${getLandmarkName(index)}</td>
        <td>${landmark.x ? landmark.x.toFixed(1) : 'N/A'}</td>
        <td>${landmark.y ? landmark.y.toFixed(1) : 'N/A'}</td>
      </tr>
    `;
  });

  html += `
        </tbody>
      </table>
    </body>
    </html>
  `;

  popup.document.write(html);
  popup.document.close();

  showToast(`📋 Finestra con tutti i ${allCurrentLandmarks.length} landmarks aperta`, 'info');
}

function jumpToVideoFrame(time) {
  if (!window.currentVideo) {
    showToast('Nessun video caricato', 'warning');
    return;
  }

  // Aggiorna timeline e salta al frame
  const timeline = document.getElementById('video-timeline');
  if (timeline) {
    timeline.value = time;
  }

  drawVideoFrame(window.currentVideo, time);
  showToast(`Saltato al frame: ${formatTime(time)}`, 'info');
}

// FUNZIONE OBSOLETA - Ora usa l'API backend con logica landmarkPredict_webcam.py
/*
async function calculateDetailedPoseAngles(landmarks) {
  // DEPRECATA: Sostituita dall'API backend che usa la logica migliorata
  // di landmarkPredict_webcam.py con calcoli PnP più precisi.
  // Tutte le chiamate a questa funzione sono state sostituite con analyzeImageViaAPI()
  
  console.warn('⚠️ FUNZIONE OBSOLETA: calculateDetailedPoseAngles() - Usa analyzeImageViaAPI()');
  return { pitch: 0, yaw: 0, roll: 0 };
}
*/

function getFrontalityStatus(score) {
  if (score >= 0.8) return '🟢 OTTIMA';
  if (score >= 0.6) return '🟡 BUONA';
  if (score >= 0.4) return '🟠 MEDIA';
  return '🔴 SCARSA';
}

function getRowClassByScore(score) {
  if (score >= 0.8) return 'excellent-frame';
  if (score >= 0.6) return 'good-frame';
  if (score >= 0.4) return 'medium-frame';
  return 'poor-frame';
}

// === DEBUG LANDMARKS FUNCTION ===
function forceShowLandmarks() {
  console.log('🔥 FORZANDO VISUALIZZAZIONE LANDMARKS 🔥');

  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.error('❌ Nessun landmark disponibile');
    return;
  }

  // Forza l'attivazione del pulsante
  const btn = document.getElementById('landmarks-btn');
  if (btn) {
    btn.classList.add('active');
    console.log('✅ Pulsante landmarks attivato forzatamente');
  }

  // Forza variabili globali
  window.landmarksVisible = true;
  if (typeof landmarksVisible !== 'undefined') {
    landmarksVisible = true;
  }

  // Landmarks drawing functionality removed

  // Verifica risultato
  const landmarkObjects = fabricCanvas.getObjects().filter(obj => obj.isLandmark);
  console.log('📊 Risultato debug:', {
    totalCanvasObjects: fabricCanvas.getObjects().length,
    landmarkObjects: landmarkObjects.length,
    landmarks: landmarkObjects.slice(0, 3)
  });
}

// Funzione diagnostica completa
function diagnoseLandmarksIssue() {
  console.log('🔍 === DIAGNOSI LANDMARKS === 🔍');

  // Verifica DOM
  const btn = document.getElementById('landmarks-btn');
  console.log('🎛️ Pulsante landmarks:', {
    exists: !!btn,
    classes: btn?.className,
    isActive: btn?.classList.contains('active')
  });

  // Verifica variabili globali
  console.log('📊 Variabili stato:', {
    'window.landmarksVisible': window.landmarksVisible,
    'landmarksVisible': typeof landmarksVisible !== 'undefined' ? landmarksVisible : 'undefined',
    'currentLandmarks': !!currentLandmarks,
    'landmarksCount': currentLandmarks?.length || 0
  });

  // Verifica canvas
  console.log('🎨 Canvas state:', {
    fabricCanvas: !!fabricCanvas,
    totalObjects: fabricCanvas?.getObjects()?.length || 0,
    landmarkObjects: fabricCanvas?.getObjects()?.filter(obj => obj.isLandmark)?.length || 0
  });

  // Landmarks functions removed

  // Test campione landmarks se disponibili
  if (currentLandmarks && currentLandmarks.length > 0) {
    console.log('📍 Sample landmarks:', currentLandmarks.slice(0, 3));
  }

  return {
    buttonActive: btn?.classList.contains('active'),
    hasLandmarks: !!currentLandmarks && currentLandmarks.length > 0,
    functionsAvailable: false, // drawLandmarksMain function removed
    canvasReady: !!fabricCanvas
  };
}

// Funzione test per landmarks con punti fissi
function testLandmarksWithFixedPoints() {
  if (!fabricCanvas) {
    console.error('❌ Canvas non disponibile');
    return;
  }

  // Crea landmarks di test in posizioni note
  const testLandmarks = [
    { x: 100, y: 100, z: 0, visibility: 1.0 }, // Top-left area
    { x: 200, y: 150, z: 0, visibility: 1.0 }, // Center-left  
    { x: 300, y: 200, z: 0, visibility: 1.0 }, // Center
    { x: 400, y: 150, z: 0, visibility: 1.0 }, // Center-right
    { x: 500, y: 100, z: 0, visibility: 1.0 }  // Top-right area
  ];

  console.log('🧪 TEST LANDMARKS CON PUNTI FISSI:', testLandmarks);

  // Imposta landmarks di test
  currentLandmarks = testLandmarks;
  window.currentLandmarks = currentLandmarks;

  // Forza visualizzazione
  const btn = document.getElementById('landmarks-btn');
  if (btn) btn.classList.add('active');
  window.landmarksVisible = true;

  // Landmarks drawing functionality removed

  console.log('🎯 Test landmarks completato');
}

// Funzione debug avanzata per landmarks
function debugLandmarksDetailed() {
  console.log('🔍 === DEBUG LANDMARKS DETTAGLIATO ===');

  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('❌ Nessun landmark disponibile');
    return;
  }

  console.log(`📊 STATISTICHE LANDMARKS:
    - Totale: ${currentLandmarks.length}
    - Formato: ${currentLandmarks[0].x > 1 ? 'Pixel' : 'Normalizzato'}
    - Range X: ${Math.min(...currentLandmarks.map(lm => lm.x)).toFixed(1)} - ${Math.max(...currentLandmarks.map(lm => lm.x)).toFixed(1)}
    - Range Y: ${Math.min(...currentLandmarks.map(lm => lm.y)).toFixed(1)} - ${Math.max(...currentLandmarks.map(lm => lm.y)).toFixed(1)}
  `);

  // Landmarks chiave MediaPipe (equivalenti ai 68 dlib)
  const keyLandmarks = [
    { index: 10, name: 'Fronte centro' },
    { index: 151, name: 'Mento' },
    { index: 33, name: 'Naso punta' },
    { index: 362, name: 'Occhio sinistro centro' },
    { index: 133, name: 'Occhio destro centro' },
    { index: 61, name: 'Labbro superiore' },
    { index: 17, name: 'Labbro inferiore' }
  ];

  console.log('🎯 LANDMARKS CHIAVE:');
  keyLandmarks.forEach(({ index, name }) => {
    if (currentLandmarks[index]) {
      const lm = currentLandmarks[index];
      console.log(`  ${name} (${index}): (${lm.x.toFixed(1)}, ${lm.y.toFixed(1)})`);
    }
  });

  // Informazioni trasformazione
  console.log(`🔄 TRASFORMAZIONE:
    - imageScale: ${window.imageScale?.toFixed(3)}
    - imageOffset: (${window.imageOffset?.x?.toFixed(1)}, ${window.imageOffset?.y?.toFixed(1)})
    - Canvas: ${fabricCanvas?.width}x${fabricCanvas?.height}
    - Immagine: ${currentImage?.width}x${currentImage?.height}
  `);

  // Canvas objects
  const landmarkObjects = fabricCanvas?.getObjects().filter(obj => obj.isLandmark) || [];
  console.log(`🎨 CANVAS: ${landmarkObjects.length} cerchi landmark disegnati`);
}

// Rendi globalmente accessibile per debug
window.forceShowLandmarks = forceShowLandmarks;
window.diagnoseLandmarksIssue = diagnoseLandmarksIssue;
window.testLandmarksWithFixedPoints = testLandmarksWithFixedPoints;
window.recalculateImageTransformation = recalculateImageTransformation;
window.debugLandmarksDetailed = debugLandmarksDetailed;

// === FACE-LANDMARK-LOCALIZATION INTEGRATION INFO ===
function showFaceLandmarkLocalizationInfo() {
  console.log(`
🧠 === FACE-LANDMARK-LOCALIZATION INTEGRATION REPORT ===

📋 FUNZIONI UTILIZZATE DAL PROGETTO ORIGINALE:
  ✅ calculatePoseAngles() - Adattata da landmarkPredict.py
  ✅ pose_name array ['Pitch', 'Yaw', 'Roll'] - Implementato
  ✅ Punti chiave 68-landmarks - Compatibile
  ✅ Sistema scoring frontalità - Implementato

🎯 LOGICA DI CALCOLO POSE (da face-landmark-localization):
  • Tip of nose (landmark 33) - ✅ Utilizzato
  • Chin (landmark 8) - ✅ Utilizzato  
  • Left eye corner (landmark 36) - ✅ Utilizzato
  • Right eye corner (landmark 45) - ✅ Utilizzato
  • Mouth corners (landmarks 48, 54) - ✅ Utilizzato

📐 CALCOLI IMPLEMENTATI:
  • YAW: Simmetria occhi + bocca rispetto centro immagine
  • PITCH: Rapporto naso-mento + posizione verticale occhi  
  • ROLL: Inclinazione linea degli occhi
  • FRONTALITY SCORE: 1.0 - ((|pitch|/90 + |yaw|/90) / 2)

🚀 MIGLIORAMENTI WEBAPP RISPETTO ALL'ORIGINALE:
  ✅ Real-time video analysis con timeline
  ✅ Tabella debug con tutti i frame analizzati
  ✅ Color coding per qualità frontalità
  ✅ Click-to-jump nella tabella debug
  ✅ Scansione automatica completa video
  ✅ Sistema di ranking frame migliori

⚠️  DIFFERENZE DALL'ORIGINALE:
  • Non usa Caffe/dlib (sostituiti con MediaPipe via API)
  • Non carica modelli .caffemodel (usa rilevamento web-based)  
  • Calcoli pose approssimativi (no PnP solver completo)
  • Range angoli limitati: Pitch/Yaw ±45°, Roll ±30°

📊 STATO ATTUALE:
  • Sistema completamente integrato e funzionante ✅
  • Compatibilità logica face-landmark-localization ✅
  • Interfaccia user-friendly per analisi video ✅
  `);

  return {
    functionsUsed: [
      'calculatePoseAngles()',
      'pose_name array',
      '68-landmarks system',
      'frontality scoring logic'
    ],
    improvements: [
      'Real-time video timeline',
      'Debug analysis table',
      'Automatic best frame detection',
      'Interactive frame jumping',
      'Color-coded quality indicators'
    ],
    differences: [
      'MediaPipe instead of Caffe/dlib',
      'Web-based instead of desktop Python',
      'Approximated pose calculations',
      'Limited angle ranges for stability'
    ]
  };
}

// Nuove funzioni per video nel canvas centrale
function updateVideoTimeDisplay(currentTime, duration) {
  const timeDisplay = document.getElementById('time-display');
  if (timeDisplay) {
    timeDisplay.textContent = `${formatTime(currentTime)} / ${formatTime(duration)}`;
  }
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Converte currentImage in base64 per l'invio all'API
 */
// ⚠️ FUNZIONE LEGACY RIMOSSA: convertCurrentImageToBase64
// Sostituita da FrameSource.captureFrame() in frame-processor.js
// Rimossa durante l'unificazione del 2024-01-12

// FUNZIONE OBSOLETA - Ora usa l'API backend con logica landmarkPredict_webcam.py
/*
async function calculateFrontalityScore(landmarks) {
  // DEPRECATA: Sostituita dall'API backend che implementa la logica migliorata
  // di landmarkPredict_webcam.py con calcoli PnP per la posa della testa.
  // Tutte le chiamate a questa funzione sono state sostituite con analyzeImageViaAPI()
  
  console.warn('⚠️ FUNZIONE OBSOLETA: calculateFrontalityScore() - Usa analyzeImageViaAPI()');
  return 0.0;
}
*/

// Funzione calculatePoseAngles rimossa - ora usa l'API backend con logica landmarkPredict_webcam.py

function getFrontalityColor(score) {
  if (score >= 0.8) return '#00ff00'; // Verde - ottima frontalità
  if (score >= 0.6) return '#ffff00'; // Giallo - buona frontalità
  if (score >= 0.4) return '#ff8800'; // Arancione - media frontalità
  return '#ff0000'; // Rosso - scarsa frontalità
}

// ⚠️ FUNZIONE OBSOLETA RIMOSSA: findBestFrontalFrame
// Sistema WebSocket automatico trova il miglior frame senza intervento manuale
// Rimossa durante ripristino sistema originale 2024-01-12

// ⚠️ FUNZIONE OBSOLETA RIMOSSA: startAutomaticVideoScanning
// Sistema WebSocket automatico scansiona il video senza intervento manuale
// Rimossa durante ripristino sistema originale 2024-01-12

// === FUNZIONI SINCRONIZZAZIONE OVERLAY GREEN DOTS ===

function syncGreenDotsOverlayWithImage() {
  /**
   * Sincronizza la posizione e scala dell'overlay green dots con l'immagine principale
   * Usa le stesse coordinate dinamiche dei landmarks per consistenza
   */
  if (!window.currentGreenDotsOverlay) {
    console.log('⚠️ Nessun overlay green dots da sincronizzare');
    return;
  }

  if (!currentImage || !currentImage.isBackgroundImage) {
    console.log('⚠️ Nessuna immagine di sfondo da sincronizzare');
    return;
  }

  // Salva posizioni precedenti per debug
  const oldOverlayPos = {
    left: window.currentGreenDotsOverlay.left,
    top: window.currentGreenDotsOverlay.top
  };

  // Aggiorna le variabili globali di trasformazione
  window.imageScale = currentImage.scaleX;
  window.imageOffset = {
    x: currentImage.left,
    y: currentImage.top
  };

  // Aggiorna l'overlay con le coordinate ESATTE dell'immagine
  window.currentGreenDotsOverlay.set({
    left: currentImage.left,
    top: currentImage.top,
    scaleX: currentImage.scaleX,
    scaleY: currentImage.scaleY
  });

  fabricCanvas.renderAll();

  console.log('🔄 SINCRONIZZAZIONE OVERLAY GREEN DOTS:', {
    immagine: {
      pos: `(${currentImage.left.toFixed(1)}, ${currentImage.top.toFixed(1)})`,
      scale: currentImage.scaleX.toFixed(3)
    },
    overlay: {
      oldPos: `(${oldOverlayPos.left.toFixed(1)}, ${oldOverlayPos.top.toFixed(1)})`,
      newPos: `(${window.currentGreenDotsOverlay.left.toFixed(1)}, ${window.currentGreenDotsOverlay.top.toFixed(1)})`,
      scale: window.currentGreenDotsOverlay.scaleX.toFixed(3)
    },
    variabiliGlobali: {
      imageScale: window.imageScale?.toFixed(3),
      imageOffset: `(${window.imageOffset?.x?.toFixed(1)}, ${window.imageOffset?.y?.toFixed(1)})`
    }
  });
}

function syncGreenDotsOverlayWithViewport() {
  /**
   * Sincronizza l'overlay green dots quando l'immagine viene ruotata/spostata.
   * Usa il centro dell'immagine + rotazione delta rispetto all'angolo di detection
   * per mantenere l'overlay allineato anche dopo ulteriori rotazioni.
   */
  if (!window.currentGreenDotsOverlay) {
    console.log('⚠️ Nessun overlay green dots da sincronizzare con viewport');
    return;
  }

  if (!currentImage) {
    console.log('⚠️ Nessuna immagine per sincronizzazione viewport');
    return;
  }

  const detectionAngle = window.greenDotsDetectionAngle || 0;
  const currentAngle = currentImage.angle || 0;
  // Rotazione aggiuntiva rispetto al momento del rilevamento
  const additionalAngle = currentAngle - detectionAngle;

  const center = currentImage.getCenterPoint();

  // Usa le scale salvate al momento della detection (basate sul bbox di allora)
  const scaleX = window.greenDotsOverlayScaleXAtDetection;
  const scaleY = window.greenDotsOverlayScaleYAtDetection;

  if (!scaleX || !scaleY) {
    // Fallback: vecchio metodo con bbox
    const bbox = currentImage.getBoundingRect(true);
    const natW = window.currentGreenDotsOverlayNaturalW || window.currentGreenDotsOverlay.width;
    const natH = window.currentGreenDotsOverlayNaturalH || window.currentGreenDotsOverlay.height;
    window.currentGreenDotsOverlay.set({
      left: bbox.left,
      top: bbox.top,
      scaleX: bbox.width / natW,
      scaleY: bbox.height / natH,
      angle: 0
    });
  } else {
    window.currentGreenDotsOverlay.set({
      left: center.x,
      top: center.y,
      originX: 'center',
      originY: 'center',
      scaleX: scaleX,
      scaleY: scaleY,
      angle: additionalAngle
    });
  }

  console.log('🔄 SINCRONIZZAZIONE VIEWPORT:', {
    currentAngle,
    detectionAngle,
    additionalAngle,
    center: `(${center.x.toFixed(1)}, ${center.y.toFixed(1)})`
  });

  fabricCanvas.renderAll();
}

// ===================================
// INIZIALIZZAZIONE APP CON AUTH CHECK
// ===================================

window.addEventListener('DOMContentLoaded', async () => {
  // STEP 0: Controlla se c'è un'azione pendente da hard refresh.
  // Leggi il flag PRIMA di checkPendingAction (che lo cancella).
  const _hasPendingAction = !!sessionStorage.getItem('pendingAction');
  window._hasPendingAction = _hasPendingAction; // esposto per updateUserUI
  checkPendingAction();

  // STEP 0.5: Benvenuto speculativo — PRIMA di qualsiasi await.
  // Usa il nome cachato dall'ultima sessione autenticata (localStorage).
  // Se il token non c'è o l'auth fallisce verrà eseguita la redirect;
  // se l'auth ha successo, _welcomeStarted evita la doppia chiamata in updateUserUI.
  const _cachedWelcomeName = localStorage.getItem('_kimerika_welcome_name');
  const _hasToken = !!(localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token'));
  if (_hasToken && _cachedWelcomeName && !_hasPendingAction && typeof voiceAssistant !== 'undefined') {
    window.currentUserName = _cachedWelcomeName;
    window._welcomeStarted = true;
    voiceAssistant.speakWelcome(_cachedWelcomeName);
  }

  // STEP 1: Verifica autenticazione (in parallelo con il download TTS benvenuto)
  const isAuthenticated = await checkAuthentication();

  if (!isAuthenticated) {
    return;
  }

  // STEP 2: speakWelcome è già partito (speculativo o da updateUserUI).
  // Nessun prefetch aggiuntivo qui: le frasi di coaching vengono pre-caricate
  // da startWebcamDirect() appena prima di avviarsi, con i testi corretti.
  // (Prefetch anticipato a DOMContentLoaded causa fetch concorrenti con il benvenuto.)
});

// ===================================
// GESTIONE TABELLA UNIFICATA
// ===================================

/**
 * Variabile globale per tracciare il tab corrente della tabella unificata
 */
window.unifiedTableCurrentTab = 'measurements';

/**
 * Cambia il tab attivo nella tabella unificata
 * @param {string} tabName - Nome del tab ('measurements', 'landmarks', 'debug')
 */
// Cache per evitare switch ripetuti
let _lastUnifiedTab = null;

function switchUnifiedTab(tabName, event = null, forceUpdate = false) {
  // Evita switch se già sul tab corretto (a meno che non sia forzato)
  if (_lastUnifiedTab === tabName && !event && !forceUpdate) {
    console.log('🔄 [UNIFIED] Tab già attivo, skip (usa forceUpdate per aggiornare)');
    return;
  }
  _lastUnifiedTab = tabName;

  // Aggiorna variabile globale
  window.unifiedTableCurrentTab = tabName;

  // Aggiorna stato visivo dei tabs
  document.querySelectorAll('.unified-tab').forEach(tab => {
    tab.classList.remove('active');
    // Se la chiamata è programmatica (senza event), trova il tab corrispondente
    if (!event && tab.dataset.tab === tabName) {
      tab.classList.add('active');
    }
  });

  // Se c'è un evento, usa event.target
  if (event && event.target) {
    event.target.classList.add('active');
  }

  // Aggiorna header e contenuto della tabella in base al tab
  const tableHead = document.getElementById('unified-table-head');
  const tableBody = document.getElementById('unified-table-body');

  // Animazione di cambio
  const table = document.getElementById('unified-table');
  table.classList.add('switching');

  setTimeout(() => {
    switch (tabName) {
      case 'measurements':
        updateUnifiedTableForMeasurements(tableHead, tableBody);
        break;
      case 'landmarks':
        updateUnifiedTableForLandmarks(tableHead, tableBody);
        break;
      case 'debug':
        updateUnifiedTableForDebug(tableHead, tableBody);
        // Nessun controllo per debug
        break;
    }

    table.classList.remove('switching');
  }, 200);
}

/**
 * Aggiorna la tabella unificata per mostrare le misurazioni
 */
function updateUnifiedTableForMeasurements(tableHead, tableBody) {
  console.log('🔄 updateUnifiedTableForMeasurements chiamata');

  // Header per misurazioni
  tableHead.innerHTML = `
    <tr>
      <th>📏 Tipo Misurazione</th>
      <th>📊 Valore</th>
      <th>📐 Unità</th>
      <th>✅ Stato</th>
    </tr>
  `;

  // SALVA le righe di misurazione esistenti prima di pulire
  const measurementRows = [];
  if (tableBody.children.length > 0) {
    // Filtra solo le righe che sono misurazioni (non debug frame)
    Array.from(tableBody.children).forEach(row => {
      // Le righe di misurazione hanno 4 colonne e NON hanno attributi data-frame-time
      if (row.children.length === 4 && !row.hasAttribute('data-frame-time')) {
        measurementRows.push(row.cloneNode(true));
      }
    });
  }

  console.log('📊 Righe misurazione trovate:', measurementRows.length);

  // Pulisci SEMPRE la tabella quando switchi a measurements
  tableBody.innerHTML = '';

  // Ripristina le righe di misurazione dalla tabella unificata (se ci sono già)
  // MA escludi righe green-dots che verranno ricaricate dalla tabella originale
  if (measurementRows.length > 0) {
    measurementRows.forEach(row => {
      // Non ripristinare righe green-dots vecchie - verranno ricaricate
      if (!row.hasAttribute('data-type') || row.getAttribute('data-type') !== 'green-dots') {
        tableBody.appendChild(row);
      }
    });
    console.log('✅ Ripristinate', tableBody.children.length, 'righe di misurazione (esclusi green-dots)');
  }

  // SEMPRE copia TUTTE le righe dalla tabella originale (in ordine inverso)
  const originalTableBody = document.getElementById('measurements-data');
  if (originalTableBody && originalTableBody.children.length > 0) {
    console.log('📊 Copiando', originalTableBody.children.length, 'righe da measurements-data...');

    // Copia TUTTE le righe dalla tabella originale IN ORDINE INVERSO (ultima per prima)
    Array.from(originalTableBody.children).reverse().forEach((row, index) => {
      tableBody.appendChild(row.cloneNode(true));
      console.log(`  ✓ Riga ${index + 1}:`, row.querySelector('td')?.textContent?.substring(0, 50) || 'N/A');
    });

    console.log('📋 Totale righe nella tabella unificata:', tableBody.children.length);
  } else {
    console.warn('⚠️ Tabella measurements-data vuota o non trovata');
  }

  // Se ancora vuota, mostra messaggio
  if (tableBody.children.length === 0) {
    tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Nessuna misurazione disponibile</td></tr>';
  }
}

/**
 * Aggiorna la tabella unificata per mostrare i landmarks
 */
function updateUnifiedTableForLandmarks(tableHead, tableBody) {
  // Header per landmarks
  tableHead.innerHTML = `
    <tr>
      <th>🎨</th>
      <th>ID</th>
      <th>Nome</th>
      <th>X</th>
      <th>Y</th>
    </tr>
  `;

  // Copia i dati dalla tabella originale IN ORDINE INVERSO
  const originalTableBody = document.getElementById('landmarks-data');
  if (originalTableBody && originalTableBody.children.length > 0) {
    tableBody.innerHTML = '';
    // Inverti l'ordine: ultima riga per prima
    Array.from(originalTableBody.children).reverse().forEach(row => {
      tableBody.appendChild(row.cloneNode(true));
    });
  } else {
    tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Nessun landmark disponibile</td></tr>';
  }
}

/**
 * Aggiorna la tabella unificata per mostrare i dati di debug
 */
function updateUnifiedTableForDebug(tableHead, tableBody) {
  // Header per debug
  tableHead.innerHTML = `
    <tr>
      <th>Frame</th>
      <th>Tempo</th>
      <th>Score</th>
      <th>Yaw</th>
      <th>Pitch</th>
      <th>Roll</th>
      <th>Stato</th>
    </tr>
  `;

  // Copia i dati dalla tabella originale
  const originalTableBody = document.getElementById('debug-data');
  if (originalTableBody && originalTableBody.children.length > 0) {
    // Copia l'HTML
    tableBody.innerHTML = originalTableBody.innerHTML;

    // Ri-aggiungi gli event listener per il click sulle righe
    // Trova le righe originali e quelle unificate e sincronizza i listener
    const originalRows = originalTableBody.querySelectorAll('tr');
    const unifiedRows = tableBody.querySelectorAll('tr');

    originalRows.forEach((originalRow, index) => {
      const unifiedRow = unifiedRows[index];
      if (unifiedRow && originalRow.onclick) {
        // Copia l'onclick se esiste
        unifiedRow.onclick = originalRow.onclick;
        unifiedRow.style.cursor = 'pointer';
      } else if (unifiedRow) {
        // Se la riga originale ha event listener tramite addEventListener,
        // dobbiamo aggiungerlo anche alla riga unificata
        // Verifichiamo se la riga è cliccabile dal cursor
        if (originalRow.style.cursor === 'pointer') {
          unifiedRow.style.cursor = 'pointer';

          // Aggiungi un listener generico che chiama la stessa funzione
          // Usa i dati salvati globalmente in currentBestFrames
          if (window.currentBestFrames && window.currentBestFrames[index]) {
            unifiedRow.addEventListener('click', function () {
              const frame = window.currentBestFrames[index];
              if (typeof showFrameInMainCanvas === 'function') {
                showFrameInMainCanvas(frame, index);

                // Rimuovi highlight precedente sia dalla tabella originale che unificata
                originalTableBody.querySelectorAll('tr').forEach(r => r.classList.remove('selected-frame'));
                tableBody.querySelectorAll('tr').forEach(r => r.classList.remove('selected-frame'));

                // Aggiungi highlight
                originalRow.classList.add('selected-frame');
                unifiedRow.classList.add('selected-frame');
              }
            });
          }
        }
      }
    });
  } else {
    tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Nessun dato di debug disponibile</td></tr>';
  }
}

/**
 * Apre automaticamente la sezione DATI ANALISI quando arrivano nuovi dati
 * Versione 2.0 - Semplificata e robusta
 */
// Cache per evitare ricerche ripetute
let _unifiedSectionCache = null;

function openUnifiedAnalysisSection() {
  try {
    // Usa cache se disponibile
    if (!_unifiedSectionCache) {
      const allSections = document.querySelectorAll('.section');
      for (const section of allSections) {
        const btn = section.querySelector('.toggle-btn');
        if (btn && (btn.textContent.includes('DATI ANALISI') || btn.textContent.includes('📊'))) {
          _unifiedSectionCache = {
            section: section,
            content: section.querySelector('.section-content'),
            icon: section.querySelector('.icon')
          };
          break;
        }
      }
    }

    if (!_unifiedSectionCache || !_unifiedSectionCache.content) return;

    // Apri solo se non già aperta
    if (_unifiedSectionCache.content.style.display !== 'block') {
      _unifiedSectionCache.content.style.display = 'block';
      if (_unifiedSectionCache.icon) _unifiedSectionCache.icon.textContent = '▼';
      _unifiedSectionCache.section.setAttribute('data-expanded', 'true');
    }
  } catch (error) {
    // Ignora errori silenziosi
  }
}

/**
 * Mantiene sincronizzata la tabella unificata quando viene aggiornata una delle tabelle originali
 */
function syncUnifiedTableWithOriginal() {
  if (!window.unifiedTableCurrentTab) return;

  const tableHead = document.getElementById('unified-table-head');
  const tableBody = document.getElementById('unified-table-body');

  if (!tableHead || !tableBody) return;

  // Aggiorna solo se la sezione unificata è visibile
  const unifiedSection = document.querySelector('.section[data-expanded="true"] .toggle-btn');
  if (!unifiedSection || !unifiedSection.textContent.includes('📊 DATI ANALISI')) return;

  switch (window.unifiedTableCurrentTab) {
    case 'measurements':
      updateUnifiedTableForMeasurements(tableHead, tableBody);
      break;
    case 'landmarks':
      updateUnifiedTableForLandmarks(tableHead, tableBody);
      break;
    case 'debug':
      updateUnifiedTableForDebug(tableHead, tableBody);
      break;
  }
}

// Aggiungi observers per sincronizzare automaticamente quando le tabelle originali cambiano
if (typeof MutationObserver !== 'undefined') {
  // Observer per la tabella misurazioni
  const measurementsObserver = new MutationObserver(() => {
    if (window.unifiedTableCurrentTab === 'measurements') {
      syncUnifiedTableWithOriginal();
    }
  });

  // Observer per la tabella landmarks
  const landmarksObserver = new MutationObserver(() => {
    if (window.unifiedTableCurrentTab === 'landmarks') {
      syncUnifiedTableWithOriginal();
    }
  });

  // Observer per la tabella debug
  const debugObserver = new MutationObserver(() => {
    if (window.unifiedTableCurrentTab === 'debug') {
      syncUnifiedTableWithOriginal();
    }
  });

  // Attiva gli observers quando il DOM è pronto
  window.addEventListener('DOMContentLoaded', () => {
    const measurementsTable = document.getElementById('measurements-data');
    const landmarksTable = document.getElementById('landmarks-data');
    const debugTable = document.getElementById('debug-data');

    if (measurementsTable) {
      measurementsObserver.observe(measurementsTable, { childList: true, subtree: true });
    }
    if (landmarksTable) {
      landmarksObserver.observe(landmarksTable, { childList: true, subtree: true });
    }
    if (debugTable) {
      debugObserver.observe(debugTable, { childList: true, subtree: true });
    }

    console.log('👀 Observers per sincronizzazione tabella unificata attivati');
  });
}
