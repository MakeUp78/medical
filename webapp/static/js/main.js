/*
 * JavaScript principale - Gestione interfaccia e sezioni
 * Replica comportamenti dell'app desktop
 * 
 * VERSIONE: 2.1 - 2025-12-20 - Tabella Unificata con auto-espansione
 * ULTIMO AGGIORNAMENTO: Corretto openUnifiedAnalysisSection con log dettagliati
 */

// 🚀 VERSION CHECK - main.js v6.17 - AUTH SYSTEM + LEFT SIDEBAR FIX + CANVAS MODES
console.log('🚀🚀🚀 main.js v6.17 - AUTH SYSTEM + LEFT SIDEBAR FIX + CANVAS MODES! 🚀🚀🚀');
console.log('   ✅ Cerca CORREZIONE SOPRACCIGLIA nella LEFT sidebar (non right!)');
console.log('   ✅ Debug dettagliato per trovare la sezione');
console.log('   ✅ Ora il calcolo usa la distanza perpendicolare dalla linea di simmetria');
console.log('   ✅ Non più solo distanza orizzontale (X)!');
console.log('   ✅ Canvas modes system - immagine bloccata di default');
console.log('   ℹ️ Se vedi ancora calcoli errati:');
console.log('   1️⃣ Premi Ctrl+F5 per forzare reload');
console.log('   2️⃣ Ripremi il pulsante GREEN DOTS per rigenerare la tabella');
console.log('   ✅ window.toggleSection definita:', typeof window.toggleSection === 'function');

// Variabili globali (controllo per evitare ridichiarazioni)
if (typeof currentTool === 'undefined') var currentTool = 'selection';
if (typeof isWebcamActive === 'undefined') var isWebcamActive = false;
if (typeof currentImage === 'undefined') var currentImage = null;
if (typeof currentLandmarks === 'undefined') var currentLandmarks = [];

// Array per memorizzare le linee perpendicolari all'asse (posizioni normalizzate 0-1)
if (typeof perpendicularLines === 'undefined') var perpendicularLines = [];

// Esponi currentLandmarks globalmente
window.currentLandmarks = currentLandmarks;
window.currentImage = currentImage;
window.perpendicularLines = perpendicularLines;

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
    console.log('🔒 Nessun token trovato, redirect a landing.html');
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
      console.log('✅ Utente autenticato:', data.user.email);
      updateUserUI(data.user);
      return true;
    } else {
      console.log('❌ Token invalido, redirect a landing.html');
      localStorage.removeItem('auth_token');
      sessionStorage.removeItem('auth_token');
      window.location.href = '/landing.html';
      return false;
    }
  } catch (error) {
    console.error('❌ Errore verifica autenticazione:', error);
    window.location.href = '/landing.html';
    return false;
  }
}

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

  console.log('👤 UI utente aggiornata:', {
    name: `${user.firstname} ${user.lastname}`,
    role: user.role,
    plan: user.plan,
    has_avatar: !!user.profile_image
  });
}

/**
 * Logout utente
 */
function logout() {
  console.log('👋 Logout utente');
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

// Funzione globale per gestione sezioni (deve essere disponibile immediatamente)
window.toggleSection = function (headerElement) {
  console.log('🔧 toggleSection chiamata', headerElement);

  const section = headerElement.parentElement;
  console.log('📦 Section element:', section);

  const content = section.querySelector('.section-content');
  console.log('📄 Content element:', content);

  const icon = headerElement.querySelector('.icon');
  console.log('🔽 Icon element:', icon);

  if (!content) {
    console.error('❌ Impossibile trovare .section-content');
    return;
  }

  const isExpanded = section.dataset.expanded === 'true';
  console.log('📊 isExpanded:', isExpanded);

  if (isExpanded) {
    // Chiudi sezione
    content.style.setProperty('display', 'none', 'important');
    section.dataset.expanded = 'false';
    if (icon) icon.textContent = '►';
    console.log('📁 Sezione chiusa:', headerElement.querySelector('.toggle-btn')?.textContent);
  } else {
    // Apri sezione
    content.style.setProperty('display', 'block', 'important');
    section.dataset.expanded = 'true';
    if (icon) icon.textContent = '▼';
    console.log('📂 Sezione aperta:', headerElement.querySelector('.toggle-btn')?.textContent);
  }

  // Forza ridimensionamento canvas dopo cambi nel layout
  setTimeout(() => {
    if (typeof resizeCanvas === 'function') {
      resizeCanvas();
    }
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
    console.log('🔄 Immagine già processata, landmarks disponibili');
    return true;
  }

  console.log('🚀 AUTO-RILEVAMENTO LANDMARKS per nuova immagine');
  isDetectingLandmarks = true;

  try {
    const success = await detectLandmarksSilent();
    if (success) {
      landmarksAutoDetected = true;
      lastImageProcessed = currentImageSignature;
      console.log('✅ Landmarks auto-rilevati:', currentLandmarks.length);
    }
    return success;
  } catch (error) {
    console.error('❌ Errore auto-rilevamento landmarks:', error);
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
    // Converti immagine in base64 (stessa logica di detectLandmarks)
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    let base64Image;

    if (currentImage.getElement) {
      const fabricElement = currentImage.getElement();
      canvas.width = fabricElement.width || fabricElement.naturalWidth;
      canvas.height = fabricElement.height || fabricElement.naturalHeight;
      ctx.drawImage(fabricElement, 0, 0);
      base64Image = canvas.toDataURL('image/jpeg', 0.9);
    } else if (currentImage.width && currentImage.height) {
      canvas.width = currentImage.width;
      canvas.height = currentImage.height;
      ctx.drawImage(currentImage, 0, 0);
      base64Image = canvas.toDataURL('image/jpeg', 0.9);
    } else {
      base64Image = fabricCanvas.toDataURL('image/jpeg', 0.9);
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
      // Trasforma landmarks (stessa logica)
      const firstLandmark = result.landmarks[0];
      const isNormalized = firstLandmark.x <= 1.0 && firstLandmark.y <= 1.0;

      currentLandmarks = result.landmarks.map(lm => {
        let x = lm.x;
        let y = lm.y;

        if (isNormalized && currentImage) {
          if (currentImage.getElement) {
            const element = currentImage.getElement();
            x = lm.x * (element.width || element.naturalWidth);
            y = lm.y * (element.height || element.naturalHeight);
          } else {
            x = lm.x * currentImage.width;
            y = lm.y * currentImage.height;
          }
        }

        return { x, y, z: lm.z || 0, visibility: lm.visibility || 1.0 };
      });

      // Sincronizza con window.currentLandmarks
      window.currentLandmarks = currentLandmarks;

      console.log(`🎯 Landmarks auto-rilevati: ${currentLandmarks.length}`);
      return true;
    }

    return false;
  } catch (error) {
    console.error('Errore detectLandmarksSilent:', error);
    return false;
  }
}

// Inizializzazione al caricamento pagina
document.addEventListener('DOMContentLoaded', function () {
  console.log('🏥 Facial Analysis Web App - Inizializzazione...');

  // Verifica che Fabric.js sia caricato
  if (typeof fabric === 'undefined') {
    console.error('❌ Fabric.js non è caricato!');
    return;
  }

  console.log('✅ Fabric.js disponibile');

  // Inizializza componenti
  initializeSections();

  // Ritardo per assicurarsi che tutto sia caricato
  setTimeout(() => {
    initializeFabricCanvas();  // Usa Fabric.js canvas invece del canvas HTML5
    initializeFileHandlers();
    initializeKeyboardShortcuts();

    // Ridimensionamento aggiuntivo dopo l'inizializzazione completa
    setTimeout(() => {
      if (typeof resizeCanvas === 'function') {
        resizeCanvas();
        console.log('🔧 Ridimensionamento canvas post-inizializzazione');
      }
    }, 300);
  }, 100);

  // Aggiorna status iniziale
  updateStatus('Pronto - Interfaccia web caricata');
  updateBadges();

  console.log('✅ Inizializzazione completata');
});

// === GESTIONE SEZIONI COLLASSABILI ===

function initializeSections() {
  // Le sezioni sono già configurate nel HTML con onclick
  console.log('📂 Sezioni collassabili inizializzate');
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
      handleFileLoad(files[0]);
    }
  });
}

function loadImage() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = function (e) {
    const file = e.target.files[0];
    if (file) {
      handleFileLoad(file);
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
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'video/*';
  input.onchange = function (e) {
    const file = e.target.files[0];
    if (file) {
      handleVideoLoad(file);
    }
  };
  input.click();
}

function handleFileLoad(file) {
  const reader = new FileReader();

  reader.onload = function (e) {
    const img = new Image();
    img.onload = async function () {
      // Espandi sezioni dopo upload immagine
      collapseDetectionSections();

      // 🔄 NUOVO FLUSSO: Converti immagine in base64 e usa il flusso video
      console.log('🖼️ Conversione immagine statica in flusso video-like...');

      // Crea canvas temporaneo per convertire immagine in base64
      const tempCanvas = document.createElement('canvas');
      const tempCtx = tempCanvas.getContext('2d');
      tempCanvas.width = img.width;
      tempCanvas.height = img.height;

      // Disegna immagine sul canvas temporaneo
      tempCtx.drawImage(img, 0, 0);

      // Ottieni base64 (rimuovi prefisso "data:image/png;base64,")
      const base64Data = tempCanvas.toDataURL('image/jpeg', 0.9).split(',')[1];

      // Usa il flusso video standard
      updateCanvasWithBestFrame(base64Data);

      updateStatus(`Immagine caricata: ${file.name}`);
      showToast('Immagine caricata con successo', 'success');

      // === AUTO-RILEVAMENTO LANDMARKS ===
      console.log('📸 Nuova immagine caricata - Avvio auto-rilevamento landmarks');
      const landmarksDetected = await autoDetectLandmarksOnImageChange();
      if (landmarksDetected) {
        updateStatus(`✅ Landmarks rilevati automaticamente (${currentLandmarks.length})`);
      } else {
        console.warn('⚠️ Auto-rilevamento landmarks fallito');
      }
    };
    img.src = e.target.result;
  };

  reader.readAsDataURL(file);
}

async function handleVideoLoad(file) {
  console.log('🎥 handleVideoLoad iniziato:', {
    fileName: file.name,
    fileSize: file.size,
    fileType: file.type
  });

  try {
    // Espandi sezioni dopo upload video
    collapseDetectionSections();

    updateStatus('Avvio analisi video...');

    // Crea elemento video nascosto per elaborazione
    const video = document.createElement('video');
    video.muted = true;
    video.style.position = 'absolute';
    video.style.left = '-9999px';
    video.style.top = '-9999px';
    document.body.appendChild(video);

    // Carica file video
    const url = URL.createObjectURL(file);
    video.src = url;

    // Aspetta caricamento video
    await new Promise(resolve => {
      video.onloadedmetadata = resolve;
    });

    // Aspetta un po' per assicurarsi che il video sia completamente caricato
    await new Promise(resolve => setTimeout(resolve, 100));

    console.log('Video caricato:', {
      width: video.videoWidth,
      height: video.videoHeight,
      duration: video.duration
    });

    // Imposta video per riproduzione singola (NO LOOP)
    video.loop = false;

    // Handler per fermare quando finisce
    video.addEventListener('ended', () => {
      console.log('🎬 Video terminato - fermo anteprima');
      stopLivePreview();
    });

    // PROCESSO UNICO: Setup anteprima + elaborazione
    openWebcamSection();
    showWebcamPreview(video);

    // Aspetta WebSocket PRIMA di avviare il video
    await connectWebcamWebSocket();

    // Ora avvia il video e l'anteprima
    video.play().then(() => {
      console.log('▶️ Video avviato - play singolo');
      startLivePreview(video); // Anteprima continua
      startVideoFrameProcessing(video, file.name); // Elaborazione frame
    }).catch(e => console.error('Errore play video:', e));

    showToast('Video in elaborazione - stesso sistema della webcam', 'success');

  } catch (error) {
    console.error('Errore analisi video:', error);
    updateStatus('Errore: Impossibile analizzare il video');
    showToast('Errore analisi video', 'error');
  }
}

function startVideoFrameProcessing(video, fileName) {
  let frameCount = 0;
  const totalFrames = Math.floor(video.duration * 5); // 5 FPS per non sovraccaricare

  updateStatus(`Elaborazione video: ${fileName}`);

  const processInterval = setInterval(() => {
    if (frameCount >= totalFrames || !webcamWebSocket || webcamWebSocket.readyState !== WebSocket.OPEN) {
      clearInterval(processInterval);
      if (webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
        requestBestFramesUpdate();
      }
      return;
    }

    // Aggiorna posizione video
    video.currentTime = frameCount / 5;

    // Cattura frame e invia tramite WebSocket
    captureFrameFromVideoElement(video);

    frameCount++;
  }, 200); // 5 FPS
}

function captureFrameFromVideoElement(video) {
  try {
    const tempCanvas = document.createElement('canvas');
    const context = tempCanvas.getContext('2d');

    tempCanvas.width = video.videoWidth || 640;
    tempCanvas.height = video.videoHeight || 480;

    context.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

    const frameBase64 = tempCanvas.toDataURL('image/jpeg', 0.8).split(',')[1];

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

function createVideoInterface(video, file) {
  // Pulisci canvas
  if (fabricCanvas) {
    fabricCanvas.clear();
  }

  // Disegna primo frame
  drawVideoFrame(video, 0);

  // Crea controlli video nella sidebar destra
  createVideoControls(video, file);

  // Salva riferimento globale
  window.currentVideo = video;
  window.currentVideoFile = file;
}

function drawVideoFrame(video, currentTime) {
  if (!fabricCanvas || !video) return;

  // Imposta tempo video
  video.currentTime = currentTime;

  video.addEventListener('seeked', function onSeeked() {
    video.removeEventListener('seeked', onSeeked);

    // Cattura frame corrente
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

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
    }, 'image/jpeg', 0.9);
  });
}

function createVideoControls(video, file) {
  // Trova o crea container controlli nella sidebar destra
  let controlsContainer = document.getElementById('video-controls-container');

  if (!controlsContainer) {
    controlsContainer = document.createElement('div');
    controlsContainer.id = 'video-controls-container';
    controlsContainer.className = 'video-controls-panel';

    // 🔧 INSERISCI PRIMA delle sezioni esistenti per non coprirle
    const rightSidebar = document.querySelector('.right-sidebar');
    const measurementsSection = document.querySelector('.measurements-section');

    if (rightSidebar && measurementsSection) {
      // Inserisci prima della sezione misurazioni
      rightSidebar.insertBefore(controlsContainer, measurementsSection);
      console.log('✅ Controlli video inseriti prima delle sezioni esistenti');
    } else if (rightSidebar) {
      // Fallback: append alla fine se non trova le sezioni
      rightSidebar.appendChild(controlsContainer);
      console.log('⚠️ Controlli video inseriti alla fine della sidebar');
    }

    // 🔍 VERIFICA che le sezioni esistenti siano ancora visibili
    ensureSidebarSectionsVisible();
  }

  controlsContainer.innerHTML = `
    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="icon">▼</span>
        <span class="toggle-btn">🎬 CONTROLLI VIDEO</span>
      </div>
      <div class="section-content" style="display: block;">
        <div class="video-info">
          <p><strong>File:</strong> ${file.name}</p>
          <p><strong>Durata:</strong> ${video.duration.toFixed(1)}s</p>
          <p><strong>Risoluzione:</strong> ${video.videoWidth}x${video.videoHeight}</p>
        </div>
        
        <div class="video-timeline">
          <input type="range" id="video-timeline" min="0" max="${video.duration}" value="0" step="0.1" class="timeline-slider">
          <div id="time-display">00:00 / ${formatTime(video.duration)}</div>
        </div>
        
        <div class="video-buttons">
          <button id="play-pause-btn" class="btn btn-primary">▶️ Play</button>
          <button id="prev-frame-btn" class="btn btn-secondary">⏮️ -1s</button>
          <button id="next-frame-btn" class="btn btn-secondary">⏭️ +1s</button>
        </div>
        
        <div class="analysis-buttons">
          <button id="analyze-current-btn" class="btn btn-success">🎯 Analizza Frame</button>
          <button id="find-best-frame-btn" class="btn btn-info">🤖 Trova Miglior Frame</button>
          <button id="auto-scan-btn" class="btn btn-warning">🔍 Scansione Automatica</button>
        </div>
        
        <div id="frontality-score" class="frontality-display">
          <strong>Score Frontalità:</strong> <span id="current-score">N/A</span>
        </div>
      </div>
    </div>
  `;

  // Setup event listeners
  setupVideoEventListeners(video);

  // ✨ AUTOMATIZZA: Avvia immediatamente la ricerca del miglior frame frontale
  setTimeout(() => {
    console.log('🚀 Avvio automatico ricerca miglior frame frontale...');
    updateStatus('🤖 Ricerca automatica del frame più frontale in corso...');
    showToast('🎯 Analisi automatica avviata', 'info');
    findBestFrontalFrame();
  }, 1000); // Attesa di 1 secondo per permettere il setup completo
}

function setupVideoEventListeners(video) {
  const timeline = document.getElementById('video-timeline');
  const playPauseBtn = document.getElementById('play-pause-btn');
  const prevFrameBtn = document.getElementById('prev-frame-btn');
  const nextFrameBtn = document.getElementById('next-frame-btn');
  const analyzeBtn = document.getElementById('analyze-current-btn');
  const findBestBtn = document.getElementById('find-best-frame-btn');
  const autoScanBtn = document.getElementById('auto-scan-btn');

  let isPlaying = false;
  let playInterval = null;

  // Timeline scrubbing
  if (timeline) {
    timeline.addEventListener('input', function () {
      const time = parseFloat(this.value);
      drawVideoFrame(video, time);
    });
  }

  // Play/Pause
  if (playPauseBtn) {
    playPauseBtn.addEventListener('click', function () {
      if (isPlaying) {
        clearInterval(playInterval);
        playInterval = null;
        isPlaying = false;
        this.innerHTML = '▶️ Play';
      } else {
        playInterval = setInterval(() => {
          let currentTime = parseFloat(timeline.value) + 0.1;
          if (currentTime >= video.duration) {
            currentTime = video.duration;
            clearInterval(playInterval);
            playInterval = null;
            isPlaying = false;
            playPauseBtn.innerHTML = '▶️ Play';
          }
          timeline.value = currentTime;
          drawVideoFrame(video, currentTime);
        }, 100);
        isPlaying = true;
        this.innerHTML = '⏸️ Pause';
      }
    });
  }

  // Frame navigation
  if (prevFrameBtn) {
    prevFrameBtn.addEventListener('click', function () {
      const currentTime = Math.max(0, parseFloat(timeline.value) - 1);
      timeline.value = currentTime;
      drawVideoFrame(video, currentTime);
    });
  }

  if (nextFrameBtn) {
    nextFrameBtn.addEventListener('click', function () {
      const currentTime = Math.min(video.duration, parseFloat(timeline.value) + 1);
      timeline.value = currentTime;
      drawVideoFrame(video, currentTime);
    });
  }

  // Analisi frame corrente
  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', function () {
      analyzeCurrentVideoFrame();
    });
  }

  // Trova miglior frame
  if (findBestBtn) {
    findBestBtn.addEventListener('click', function () {
      findBestFrontalFrame();
    });
  }

  // Scansione automatica
  if (autoScanBtn) {
    autoScanBtn.addEventListener('click', function () {
      startAutomaticVideoScanning();
    });
  }
}

async function analyzeCurrentVideoFrame() {
  if (!currentImage) {
    showToast('Nessun frame da analizzare', 'warning');
    return;
  }

  try {
    updateStatus('🔍 Analisi frontalità frame corrente tramite API...');

    // Converti currentImage in base64 e usa l'API
    const imageBase64 = convertCurrentImageToBase64();
    const analysisResult = await analyzeImageViaAPI(imageBase64);

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
        // Cattura il frame corrente
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);

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
        }, 'image/jpeg', 0.9);

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

  if (video && video.src) {
    URL.revokeObjectURL(video.src);
    video.src = '';
  }

  if (modal) {
    modal.style.display = 'none';
  }
}

function closeVideoAnalysis() {
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

  // Event listeners per interazioni
  canvas.addEventListener('mousedown', onCanvasMouseDown);
  canvas.addEventListener('mousemove', onCanvasMouseMove);
  canvas.addEventListener('mouseup', onCanvasMouseUp);
  canvas.addEventListener('wheel', onCanvasWheel);
  canvas.addEventListener('contextmenu', onCanvasRightClick);

  console.log('🎨 Canvas inizializzato');
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
    if (currentImage && !window.isDrawing) {
      window.isDrawing = true;
      displayImageOnCanvas(currentImage);
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

  console.log(`🖼️ Immagine: ${image.width}x${image.height}, Canvas: ${canvasWidth}x${canvasHeight}, Scale: ${scale.toFixed(3)}`);
  console.log(`📍 Posizione: (${x.toFixed(1)}, ${y.toFixed(1)}), Dimensioni: ${scaledWidth.toFixed(1)}x${scaledHeight.toFixed(1)}`);

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

  console.log('📐 IMPOSTAZIONI SCALA IMMAGINE:', {
    originalSize: `${image.width}x${image.height}`,
    canvasSize: `${fabricCanvas.width}x${fabricCanvas.height}`,
    scale: scale.toFixed(3),
    offset: `(${x.toFixed(1)}, ${y.toFixed(1)})`,
    fabricPosition: `left=${fabricImage.left}, top=${fabricImage.top}`,
    fabricScale: `scaleX=${fabricImage.scaleX?.toFixed(3)}, scaleY=${fabricImage.scaleY?.toFixed(3)}`
  });

  // === AUTO-RILEVAMENTO LANDMARKS ===
  // Rileva SEMPRE i landmarks quando cambia l'immagine (come nell'app desktop)
  setTimeout(async () => {
    console.log('📸 displayImageOnCanvas: Avvio auto-rilevamento landmarks');
    const landmarksDetected = await autoDetectLandmarksOnImageChange();
    if (landmarksDetected) {
      console.log(`✅ Landmarks disponibili globalmente: ${currentLandmarks.length}`);
    } else {
      console.warn('⚠️ Auto-rilevamento landmarks fallito in displayImageOnCanvas');
    }
  }, 100);
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
  try {
    updateStatus('Avvio webcam...');

    // Avvia stream webcam
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: 640,
        height: 480,
        facingMode: 'user'
      }
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
    console.log('▶️ Webcam video play avviato');

    // Mantieni canvas centrale visibile per mostrare i migliori frame
    const canvas = document.getElementById('main-canvas');
    canvas.style.display = 'block';

    // Apri automaticamente la sezione anteprima webcam
    openWebcamSection();

    // PROCESSO 1: Anteprima live (indipendente)
    showWebcamPreview(video);
    startLivePreview(video); // Rendering continuo dell'anteprima

    // PROCESSO 2: Elaborazione server (separato)
    await connectWebcamWebSocket();
    startFrameCapture(video); // Invio frame al server

    isWebcamActive = true;
    updateStatus('Webcam attiva - Anteprima live + Elaborazione server');
    updateWebcamBadge(true);

    showToast('Webcam avviata con successo', 'success');

  } catch (error) {
    console.error('Errore avvio webcam:', error);
    updateStatus('Errore: Impossibile accedere alla webcam');
    showToast('Errore accesso webcam', 'error');
  }
}

function stopWebcam() {
  try {
    // Ferma cattura frame
    if (captureInterval) {
      clearInterval(captureInterval);
      captureInterval = null;
    }

    // Ferma stream webcam
    if (webcamStream) {
      const tracks = webcamStream.getTracks();
      tracks.forEach(track => track.stop());
      webcamStream = null;
    }

    // Nascondi video e anteprima webcam
    const video = document.getElementById('webcam-video');
    video.srcObject = null;
    video.style.display = 'none';

    // Nascondi anteprima webcam nella colonna destra
    hideWebcamPreview();

    document.getElementById('main-canvas').style.display = 'block';

    // Chiudi WebSocket
    disconnectWebcamWebSocket();

    isWebcamActive = false;
    updateStatus('Webcam fermata');
    updateWebcamBadge(false);

    showToast('Webcam fermata', 'info');

  } catch (error) {
    console.error('Errore stop webcam:', error);
    showToast('Errore stop webcam', 'error');
  }
}

async function connectWebcamWebSocket() {
  return new Promise((resolve, reject) => {
    try {
      // Connessione al server WebSocket tramite Nginx proxy
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const hostname = window.location.hostname;
      const wsUrl = `${protocol}//${hostname}/ws`;

      console.log(`🔗 Connessione WebSocket a: ${wsUrl}`);
      webcamWebSocket = new WebSocket(wsUrl);

      webcamWebSocket.onopen = function () {
        console.log('🔌 WebSocket connesso alla porta 8765');
        updateStatus('WebSocket connesso - Avvio sessione...');

        // Avvia sessione
        const startMessage = {
          action: 'start_session',
          session_id: `webapp_session_${new Date().toISOString().replace(/[:.]/g, '_')}`
        };
        webcamWebSocket.send(JSON.stringify(startMessage));

        console.log('✅ WebSocket pronto per l\'invio dei frame');
        resolve(); // Risolvi promise quando connesso
      };

      webcamWebSocket.onmessage = function (event) {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (error) {
          console.error('Errore parsing messaggio WebSocket:', error);
        }
      };

      webcamWebSocket.onclose = function () {
        console.log('🔌 WebSocket disconnesso');
        webcamWebSocket = null;
      };

      webcamWebSocket.onerror = function (error) {
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
    // Invia messaggio di stop con protocollo corretto
    const stopMessage = {
      action: 'get_results'
    };

    try {
      webcamWebSocket.send(JSON.stringify(stopMessage));
    } catch (error) {
      console.error('Errore invio messaggio stop:', error);
    }

    // Chiudi connessione dopo breve delay per ricevere risultati
    setTimeout(() => {
      if (webcamWebSocket) {
        webcamWebSocket.close();
        webcamWebSocket = null;
      }
    }, 1000);
  }
}

function startFrameCapture(video) {
  frameCounter = 0;

  console.log('📡 Avvio cattura frame per server (10 FPS)');

  // Cattura frame ogni 500ms (2 FPS per server - più lento)
  captureInterval = setInterval(() => {
    if (isWebcamActive && webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
      captureAndSendFrame(video);

      // Log occasionale per verificare invio
      if (frameCounter % 10 === 0) {
        console.log(`📡 Frame #${frameCounter} inviato al server`);
      }
      frameCounter++;
    }
  }, 500); // 2 FPS per il server (più efficiente)
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

  console.log('📺 showWebcamPreview chiamata:', {
    canvas: !!previewCanvas,
    previewInfo: !!previewInfo,
    video: !!video,
    videoSrc: video?.src,
    videoType: video?.constructor?.name
  });

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

    console.log('🎨 Canvas pronto per anteprima:', {
      display: previewCanvas.style.display,
      visibility: previewCanvas.style.visibility,
      classList: previewCanvas.classList.toString()
    });

    // Distingui tra webcam e video file
    if (video.src && video.src.startsWith('blob:')) {
      previewInfo.innerHTML = 'Video in elaborazione - Anteprima frame';
      console.log('🎬 Tipo rilevato: Video file');
    } else {
      previewInfo.innerHTML = 'Webcam attiva - Anteprima in tempo reale';
      console.log('📹 Tipo rilevato: Webcam stream');
    }

    // Setup iniziale
    updateWebcamPreview(video);
  } else {
    console.error('❌ Elementi mancanti per anteprima:', {
      previewCanvas: !!previewCanvas,
      video: !!video
    });
  }
}

function hideWebcamPreview() {
  const previewCanvas = document.getElementById('webcam-preview-canvas');
  const previewInfo = document.getElementById('webcam-preview-info');

  if (previewCanvas) {
    previewCanvas.style.display = 'none';
    previewCanvas.classList.remove('active');
    previewInfo.innerHTML = 'Anteprima webcam non attiva';
  }

  // Ferma anteprima live
  stopLivePreview();
}

function startLivePreview(video) {
  // Ferma loop precedente se esiste
  if (window.livePreviewId) {
    clearInterval(window.livePreviewId);
  }

  console.log('🎥 Avvio anteprima LIVE:', {
    video: !!video,
    videoWidth: video?.videoWidth,
    videoHeight: video?.videoHeight,
    readyState: video?.readyState,
    srcObject: !!video?.srcObject
  });

  // Loop per anteprima live continua (30 FPS) - NO render immediato per evitare scatto
  window.livePreviewId = setInterval(() => {
    if (video && video.videoWidth > 0) {
      renderLivePreview(video);
    } else {
      console.warn('⚠️ Video non pronto per rendering:', {
        video: !!video,
        videoWidth: video?.videoWidth,
        readyState: video?.readyState
      });
    }
  }, 33); // 30 FPS
}

function renderLivePreview(video) {
  const previewCanvas = document.getElementById('webcam-preview-canvas');

  if (!previewCanvas) {
    console.error('❌ Canvas webcam-preview-canvas NON TROVATO!');
    return;
  }

  if (!video) {
    console.error('❌ Video element NON FORNITO!');
    return;
  }

  try {
    const ctx = previewCanvas.getContext('2d');

    // Debug completo stato canvas e video
    const debugInfo = {
      canvasVisible: previewCanvas.style.display !== 'none',
      canvasSize: `${previewCanvas.offsetWidth}x${previewCanvas.offsetHeight}`,
      videoReady: video.readyState,
      videoSize: `${video.videoWidth}x${video.videoHeight}`,
      videoPaused: video.paused,
      videoEnded: video.ended,
      videoCurrentTime: video.currentTime,
      videoSrcObject: !!video.srcObject,
      containerWidth: previewCanvas.parentElement?.offsetWidth
    };

    // Log debug ogni 100 frame (circa ogni 1.6 secondi a 60fps)
    if (!window.debugFrameCount) window.debugFrameCount = 0;
    window.debugFrameCount++;

    if (window.debugFrameCount % 100 === 0) {
      console.log('🎥 RENDER DEBUG:', debugInfo);
    }

    // Calcola dimensioni dinamiche basate sul container e aspect ratio del video
    const containerWidth = previewCanvas.parentElement.offsetWidth - 16;
    const aspectRatio = video.videoWidth / video.videoHeight;
    const canvasWidth = containerWidth; // Usa tutta la larghezza disponibile
    const canvasHeight = canvasWidth / aspectRatio;

    // Imposta dimensioni canvas
    previewCanvas.width = video.videoWidth;
    previewCanvas.height = video.videoHeight;
    previewCanvas.style.width = canvasWidth + 'px';
    previewCanvas.style.height = canvasHeight + 'px';

    // DISEGNA il frame corrente del video (senza forzare play ogni volta!)
    try {
      ctx.drawImage(video, 0, 0, video.videoWidth, video.videoHeight);

      // Test: colora un pixel per vedere se il disegno funziona
      ctx.fillStyle = 'lime';
      ctx.fillRect(0, 0, 10, 10);

      // Test: disegna testo per confermare che il canvas funziona
      ctx.fillStyle = 'white';
      ctx.font = '12px Arial';
      ctx.fillText(`${Date.now()}`, 20, 20);

    } catch (drawError) {
      console.error('❌ Errore drawImage:', drawError);

      // Canvas di fallback - dovrebbe essere sempre visibile
      ctx.fillStyle = 'blue';
      ctx.fillRect(0, 0, video.videoWidth, video.videoHeight);
      ctx.fillStyle = 'white';
      ctx.font = '16px Arial';
      ctx.fillText('ERRORE VIDEO', 50, 120);
      ctx.fillText('CANVAS FUNZIONA', 50, 150);
    }

  } catch (error) {
    console.error('❌ Errore renderLivePreview:', error);
  }
}

function stopLivePreview() {
  if (window.livePreviewId) {
    clearInterval(window.livePreviewId);
    window.livePreviewId = null;
    console.log('🛑 Anteprima live fermata');
  }
}

function updateWebcamPreview(video) {
  // Questa funzione ora serve solo per il setup iniziale
  console.log('🎥 Setup iniziale anteprima per:', video?.constructor?.name);
}

function captureAndSendFrame(video) {
  try {
    // Crea canvas temporaneo per catturare frame
    const tempCanvas = document.createElement('canvas');
    const context = tempCanvas.getContext('2d');

    tempCanvas.width = video.videoWidth || 640;
    tempCanvas.height = video.videoHeight || 480;

    // Disegna frame video su canvas
    context.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

    // Converti in base64
    const frameBase64 = tempCanvas.toDataURL('image/jpeg', 0.8).split(',')[1];

    // Invia frame con protocollo corretto del server 8765
    const frameMessage = {
      action: 'process_frame',
      frame_data: frameBase64
    };

    webcamWebSocket.send(JSON.stringify(frameMessage));

  } catch (error) {
    console.error('Errore cattura frame:', error);
  }
}

function handleWebSocketMessage(data) {
  try {
    switch (data.action) {
      case 'session_started':
        updateStatus('Sessione avviata - Analisi in corso...');
        console.log('✅ Sessione WebSocket avviata:', data);
        break;

      case 'frame_processed':
        // Frame elaborato dal server
        console.log('📸 Frame elaborato:', data);
        updateFrameProcessingStats(data);

        // Richiedi migliori frame ogni 3 frame elaborati per popolare la tabella più velocemente
        if (data.total_frames_collected && data.total_frames_collected % 3 === 0 && data.total_frames_collected > 0) {
          requestBestFramesUpdate();
        }
        break;

      case 'results_ready':
        // Risultati finali dal server
        console.log('📊 Risultati finali ricevuti:', data);
        handleResultsReady(data);
        break;

      case 'pong':
        // Risposta al ping - ignora
        break;

      default:
        if (data.error) {
          console.error('❌ Errore dal server:', data.error);
          showToast(data.error, 'error');
        } else {
          console.log('📨 Messaggio WebSocket:', data);
        }
    }
  } catch (error) {
    console.error('Errore gestione messaggio WebSocket:', error);
  }
}

function requestBestFramesUpdate() {
  if (webcamWebSocket && webcamWebSocket.readyState === WebSocket.OPEN) {
    const requestMessage = {
      action: 'get_results'
    };
    webcamWebSocket.send(JSON.stringify(requestMessage));
  }
}

function updateFrameProcessingStats(data) {
  // Aggiorna statistiche elaborazione frame
  const frameInfo = document.getElementById('best-frame-info');
  if (frameInfo) {
    frameInfo.innerHTML = `
      Frame elaborati: ${data.total_frames_collected || 0}<br>
      Ultimo score: ${(data.current_score || 0).toFixed(3)}<br>
      Volti rilevati: ${data.faces_detected || 0}
    `;
  }

  // Notifica audio per frame con score > 95
  if (data.current_score && data.current_score > 95) {
    playHighScoreSound();
    console.log(`🔔 Frame con score ${data.current_score.toFixed(2)} - suono riprodotto`);
  }
}

// Variabile per throttling suono
let lastSoundTime = 0;

function playHighScoreSound() {
  // Throttle: max 1 suono ogni 500ms
  const now = Date.now();
  if (now - lastSoundTime < 500) return;
  lastSoundTime = now;

  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.frequency.value = 800; // Frequenza acuta
    oscillator.type = 'sine';

    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.2);

    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.2);
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

function updateCanvasWithBestFrame(imageData) {
  try {
    console.log('🖼️ Aggiornamento canvas con frame video...');

    // Verifica che Fabric.js sia inizializzato
    if (!fabricCanvas) {
      console.error('Fabric canvas non inizializzato');
      return;
    }

    // Mostra canvas se nascosto
    const canvasElement = document.getElementById('main-canvas');
    if (canvasElement) {
      canvasElement.style.display = 'block';
    }

    // Crea immagine da base64 usando Fabric.js
    const imageUrl = 'data:image/jpeg;base64,' + imageData;

    fabric.Image.fromURL(imageUrl, function (img) {
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

        console.log('📐 Frame video - dimensioni ottimizzate:', sizing);

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

        // Aggiorna le variabili globali di trasformazione
        window.imageScale = sizing.scale;
        window.imageOffset = { x: sizing.left, y: sizing.top };

        fabricCanvas.renderAll();

        console.log('✅ Canvas aggiornato con miglior frame - Dimensioni originali:', img.width, 'x', img.height, 'Scale:', sizing.scale);

        // Aggiorna info immagine se disponibile
        if (typeof updateImageInfo === 'function') {
          updateImageInfo(img);
        }

        // === AUTO-RILEVAMENTO LANDMARKS PER FRAME WEBCAM ===
        setTimeout(async () => {
          console.log('📸 updateCanvasWithBestFrame: Avvio auto-rilevamento landmarks');
          const landmarksDetected = await autoDetectLandmarksOnImageChange();
          if (landmarksDetected) {
            console.log(`✅ Landmarks webcam rilevati: ${currentLandmarks.length}`);
          } else {
            console.warn('⚠️ Auto-rilevamento landmarks fallito per frame webcam');
          }
        }, 200);

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
    // SOLO se la tabella unificata è vuota o se il tab corrente non è già debug
    const currentTab = window.unifiedTableCurrentTab;
    const unifiedTableBody = document.getElementById('unified-table-body');

    if (!currentTab || currentTab !== 'debug' || !unifiedTableBody || unifiedTableBody.children.length === 0) {
      console.log('🔄 [UNIFIED] Prima apertura tab DEBUG - switch necessario');
      openUnifiedAnalysisSection();
      switchUnifiedTab('debug');
    } else {
      // La tabella è già sul tab debug - aggiornamento INCREMENTALE per evitare flickering
      const tableBody = document.getElementById('unified-table-body');
      if (tableBody && debugTableBody) {
        const currentRowCount = tableBody.children.length;
        const newRowCount = debugTableBody.children.length;

        if (currentRowCount < newRowCount) {
          // CI SONO NUOVE RIGHE - Aggiungi SOLO le righe mancanti (evita re-render completo)
          console.log(`➕ [UNIFIED] Nuove righe rilevate (${currentRowCount} → ${newRowCount}) - aggiunta incrementale`);

          // Aggiungi solo le righe dalla posizione currentRowCount in poi
          const newRows = Array.from(debugTableBody.children).slice(currentRowCount);
          newRows.forEach(row => {
            const clonedRow = row.cloneNode(true);
            tableBody.appendChild(clonedRow);
          });

          // Ri-aggiungi event listener SOLO alle nuove righe appena aggiunte
          reattachDebugTableListeners(tableBody, debugTableBody, currentRowCount);
        } else if (currentRowCount > newRowCount) {
          // CI SONO MENO RIGHE - Rimuovi le righe in eccesso
          console.log(`➖ [UNIFIED] Righe rimosse (${currentRowCount} → ${newRowCount}) - rimozione`);

          while (tableBody.children.length > newRowCount) {
            tableBody.removeChild(tableBody.lastChild);
          }

          // Non serve ri-aggiungere listener, le righe rimanenti hanno già i loro listener
        } else {
          // Stesso numero di righe - NESSUN aggiornamento necessario (i listener esistono già)
          console.log('✅ [UNIFIED] Numero righe invariato - nessuna azione necessaria');
        }
      }
    }

    console.log('🔄 [UNIFIED] Aggiornamento tab DEBUG completato');

    // Mostra automaticamente il miglior frame (primo della lista) nel canvas centrale
    if (bestFrames.length > 0 && bestFrames[0].image_data) {
      updateCanvasWithBestFrame(bestFrames[0].image_data);
    }

    console.log(`📊 Tabella debug aggiornata con ${bestFrames.length} frame`);

    // Scroll automatico DISABILITATO - la colonna rimane in alto
    // const autoScroll = document.getElementById('auto-scroll');
    // if (autoScroll && autoScroll.checked) {
    //   debugTableBody.scrollIntoView({ behavior: 'smooth', block: 'end' });
    // }

  } catch (error) {
    console.error('Errore aggiornamento tabella debug:', error);
  }
}

function getScoreClass(score) {
  if (score >= 0.9) return 'excellent';
  if (score >= 0.8) return 'very-good';
  if (score >= 0.7) return 'good';
  return 'poor';
}

function showFrameInMainCanvas(frame, index) {
  try {
    console.log(`🖼️ Mostrando frame ${index + 1} nel canvas principale`);

    if (frame.image_data) {
      updateCanvasWithBestFrame(frame.image_data);

      // Aggiorna info frame corrente
      const frameInfo = document.getElementById('best-frame-info');
      if (frameInfo) {
        frameInfo.innerHTML = `
          Frame selezionato: #${index + 1}<br>
          Score: ${(frame.score || 0).toFixed(3)}<br>
          Pose: Y=${(frame.yaw || 0).toFixed(1)}° P=${(frame.pitch || 0).toFixed(1)}° R=${(frame.roll || 0).toFixed(1)}°
        `;
      }

      showToast(`Frame ${index + 1} visualizzato nel canvas`, 'info');
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
    console.log('📊 Elaborando risultati dal server:', data);

    if (data.success && data.frames && data.frames.length > 0) {
      // Trasforma i dati dei frame nel formato atteso
      const bestFrames = data.frames.map((frame, index) => ({
        rank: frame.rank || index + 1,
        score: frame.score || 0,
        image_data: frame.data, // Base64 dell'immagine
        timestamp: Date.now() / 1000,
        yaw: 0,
        pitch: 0,
        roll: 0
      }));

      // Se sono disponibili i dati JSON dettagliati, usa quelli per pose
      if (data.json_data && data.json_data.frames) {
        data.json_data.frames.forEach((jsonFrame, index) => {
          if (index < bestFrames.length && jsonFrame.pose) {
            bestFrames[index].yaw = jsonFrame.pose.yaw || 0;
            bestFrames[index].pitch = jsonFrame.pose.pitch || 0;
            bestFrames[index].roll = jsonFrame.pose.roll || 0;
            bestFrames[index].timestamp = jsonFrame.timestamp || bestFrames[index].timestamp;
          }
        });
      }

      // Aggiorna tabella con i nuovi frame
      updateDebugTable(bestFrames);

      updateStatus(`Ricevuti ${bestFrames.length} migliori frame dal server`);

    } else {
      console.warn('Nessun frame valido nei risultati:', data);
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
      // Converti i frame nel formato della tabella debug
      const debugFrames = [];

      for (const frameInfo of data.frames) {
        const frameEntry = {
          image_data: frameInfo.data,
          score: frameInfo.score || 0,
          rank: frameInfo.rank || 0,
          timestamp: Date.now()
        };

        // Aggiungi dati pose dal JSON se disponibili
        if (data.json_data && data.json_data.frames && frameInfo.rank) {
          const jsonFrame = data.json_data.frames[frameInfo.rank - 1];
          if (jsonFrame && jsonFrame.pose) {
            frameEntry.yaw = jsonFrame.pose.yaw || 0;
            frameEntry.pitch = jsonFrame.pose.pitch || 0;
            frameEntry.roll = jsonFrame.pose.roll || 0;
          }
        }

        debugFrames.push(frameEntry);
      }

      // Aggiorna tabella debug
      updateDebugTable(debugFrames);

      // Mostra il miglior frame nel canvas
      if (debugFrames.length > 0 && debugFrames[0].image_data) {
        updateCanvasWithBestFrame(debugFrames[0].image_data);
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

    // Ridisegna linee perpendicolari
    if (typeof redrawPerpendicularLines === 'function') {
      redrawPerpendicularLines();
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

    // Ridisegna linee perpendicolari
    if (typeof redrawPerpendicularLines === 'function') {
      redrawPerpendicularLines();
    }
  }, 50);

  console.log(`↺ Immagine ruotata: ${currentAngle}° → ${newAngle}°`);
}

// Rendi le funzioni globali
window.rotateImageClockwise = rotateImageClockwise;
window.rotateImageCounterClockwise = rotateImageCounterClockwise;

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
   */
  if (!currentLandmarks || currentLandmarks.length === 0 || !fabricCanvas) {
    console.warn('⚠️ Nessun landmark da visualizzare');
    return;
  }

  console.log(`🎯 Visualizzazione ${currentLandmarks.length} landmarks sul canvas`);

  currentLandmarks.forEach((landmark, index) => {
    if (landmark.visibility > 0.5) {
      const circle = new fabric.Circle({
        left: landmark.x - 1,
        top: landmark.y - 1,
        radius: 2,
        fill: 'red',
        selectable: false,
        evented: false,
        isLandmark: true,
        landmarkIndex: index
      });
      fabricCanvas.add(circle);
    }
  });

  fabricCanvas.renderAll();
  console.log(`✅ ${currentLandmarks.length} landmarks visualizzati`);
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

function drawSymmetryAxis() {
  /**
   * === SISTEMA SEMPLIFICATO ===
   * Disegna l'asse di simmetria usando landmarks già disponibili
   * Landmarks MediaPipe: Glabella (9) e Philtrum (164)
   */
  console.log('📏 drawSymmetryAxis - Sistema Semplificato');

  // PRIMA rimuovi l'asse precedente (se esiste)
  clearSymmetryAxis();

  // Se non ci sono landmarks, prova auto-rilevamento
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks in corso...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        drawSymmetryAxis(); // Richiama se stesso dopo il rilevamento
      } else {
        showToast('Impossibile rilevare landmarks per l\'asse', 'error');
      }
    });
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
    console.log('🧹 Asse di simmetria rimosso');
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
    perPixelTargetFind: true,
    targetFindTolerance: 3 // Solo 3px di tolleranza
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
      perPixelTargetFind: true,
      targetFindTolerance: 3 // Solo 3px di tolleranza
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
   * Usa la stessa logica di trasformazione dinamica dei landmarks.
   */
  try {
    fabric.Image.fromURL(overlayBase64, function (overlayImg) {
      if (!currentImage) {
        console.warn('⚠️ Nessuna immagine corrente disponibile per overlay');
        return;
      }

      // Ricalcola le informazioni di trasformazione se necessario
      if (!window.imageScale || !window.imageOffset) {
        console.warn('⚠️ Informazioni trasformazione non disponibili, ricalcolo...');
        recalculateImageTransformation();

        if (!window.imageScale || !window.imageOffset) {
          console.error('❌ Impossibile calcolare trasformazione per overlay');
          return;
        }
      }

      // L'overlay è delle dimensioni dell'immagine originale
      const originalWidth = overlayImg.width;
      const originalHeight = overlayImg.height;

      console.log(`🎨 Overlay originale: ${originalWidth}x${originalHeight}`);
      console.log(`🎨 Scala canvas: ${window.imageScale}, Offset: (${window.imageOffset.x}, ${window.imageOffset.y})`);

      // Rimuovi overlay precedente se esiste
      const existingOverlay = fabricCanvas.getObjects().find(obj => obj.isGreenDotsOverlay);
      if (existingOverlay) {
        fabricCanvas.remove(existingOverlay);
      }

      overlayImg.set({
        // USA ESATTAMENTE LE STESSE COORDINATE DELL'IMMAGINE PRINCIPALE
        left: currentImage.left,
        top: currentImage.top,
        scaleX: currentImage.scaleX,
        scaleY: currentImage.scaleY,
        selectable: false,
        evented: false,
        isGreenDotsOverlay: true,
        opacity: 0.8,
        originX: 'left',
        originY: 'top'
      });

      // Salva riferimento all'overlay per poterlo aggiornare
      window.currentGreenDotsOverlay = overlayImg;

      fabricCanvas.add(overlayImg);

      // Posiziona l'overlay sopra l'immagine di sfondo ma sotto altri elementi
      const backgroundImage = fabricCanvas.getObjects().find(obj => obj.isBackgroundImage);
      if (backgroundImage) {
        // Prima manda l'immagine di sfondo in fondo
        fabricCanvas.sendToBack(backgroundImage);
        // Poi porta l'overlay sopra l'immagine ma non al top (per lasciare spazio ai punti)
        const allObjects = fabricCanvas.getObjects();
        const backgroundIndex = allObjects.indexOf(backgroundImage);
        fabricCanvas.moveTo(overlayImg, backgroundIndex + 1);
      } else {
        // Se non c'è immagine di sfondo, l'overlay rimane dove è
        console.log('🎨 Nessuna immagine di sfondo trovata');
      }

      fabricCanvas.renderAll();
      console.log('🎨 Overlay green dots aggiunto e posizionato correttamente con coordinate dinamiche');

      // Abilita l'immagine per essere spostata e configura sincronizzazione
      enableImageMovement();
    });
  } catch (error) {
    console.error('❌ Errore aggiunta overlay green dots:', error);
  }
}

function enableImageMovement() {
  /**
   * DEPRECATA - Il movimento dell'immagine è ora gestito da canvas-modes.js
   * Questa funzione è mantenuta per compatibilità ma NON riabilita più la selezione
   */
  if (!currentImage || !currentImage.isBackgroundImage) {
    console.warn('⚠️ Immagine non disponibile per abilitare movimento');
    return;
  }

  // NON abilitare più la selezione - gestita da canvas-modes.js
  // L'immagine deve rimanere SEMPRE bloccata a meno che non sia attivo il tool PAN
  console.log('ℹ️ enableImageMovement chiamata - movimento gestito da canvas-modes.js');

  // Rimuovi event listeners precedenti per object events (NON mouse events - gestiti globalmente in canvas.js)
  fabricCanvas.off('object:moving');
  fabricCanvas.off('object:scaling');
  fabricCanvas.off('object:modified');
  fabricCanvas.off('object:moved');
  fabricCanvas.off('object:scaled');
  fabricCanvas.off('object:rotated');

  // Configura nuovi event listeners specifici per l'immagine
  fabricCanvas.on('object:moving', function (e) {
    console.log('🔄 Event object:moving triggerato, target:', e.target, 'currentImage:', currentImage);
    if (e.target === currentImage && window.currentGreenDotsOverlay) {
      console.log('🔄 Immagine in movimento, sincronizzando overlay...');
      // Sincronizza immediatamente durante il trascinamento
      window.currentGreenDotsOverlay.set({
        left: currentImage.left,
        top: currentImage.top
      });
      fabricCanvas.requestRenderAll();
    }
  });

  fabricCanvas.on('object:scaling', function (e) {
    console.log('🔄 Event object:scaling triggerato, target:', e.target, 'currentImage:', currentImage);
    if (e.target === currentImage && window.currentGreenDotsOverlay) {
      console.log('🔄 Immagine ridimensionata, sincronizzando overlay...');
      // Sincronizza posizione E scala durante il ridimensionamento
      window.currentGreenDotsOverlay.set({
        left: currentImage.left,
        top: currentImage.top,
        scaleX: currentImage.scaleX,
        scaleY: currentImage.scaleY
      });
      fabricCanvas.requestRenderAll();
    }
  });

  fabricCanvas.on('object:modified', function (e) {
    console.log('🔄 Event object:modified triggerato, target:', e.target, 'currentImage:', currentImage);
    if (e.target === currentImage && window.currentGreenDotsOverlay) {
      console.log('🔄 Immagine modificata, sincronizzando overlay...');
      // Sincronizza completamente dopo le modifiche
      syncGreenDotsOverlayWithImage();
    }
  });

  fabricCanvas.renderAll();
  console.log('🎯 Movimento immagine abilitato, sincronizzazione configurata');
}

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
   * Converte coordinate dell'immagine originale in coordinate del canvas scalato.
   * Usa la stessa logica di transformLandmarkCoordinate per coerenza.
   */
  if (!window.imageScale || !window.imageOffset) {
    console.warn('⚠️ Informazioni scala green dots non disponibili, ricalcolo...');

    // Prova a ricalcolare come per i landmarks
    if (currentImage && fabricCanvas) {
      recalculateImageTransformation();
    }

    if (!window.imageScale || !window.imageOffset) {
      console.warn('❌ Impossibile scalare coordinate green dots, usando originali');
      return { x, y };
    }
  }

  const scaled = {
    x: x * window.imageScale + window.imageOffset.x,
    y: y * window.imageScale + window.imageOffset.y
  };

  console.log(`🟢 Scala green dots: (${x}, ${y}) → (${scaled.x.toFixed(1)}, ${scaled.y.toFixed(1)}) | Scala: ${window.imageScale?.toFixed(4)} Offset: (${window.imageOffset?.x?.toFixed(1)}, ${window.imageOffset?.y?.toFixed(1)})`);

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
    measurementsSection.insertAdjacentHTML('beforeend', tableRows);

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
    switchUnifiedTab('measurements'); // Forza il passaggio al tab measurements

    console.log('🔄 [UNIFIED] Tab MISURAZIONI attivato automaticamente per green dots');

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
  // Aggiungi analisi delle distanze dall'asse di simmetria
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

    rows += `<tr data-type="green-dots">
      <td>🟢 Pixel Verdi</td>
      <td>${result.detection_results.total_green_pixels}</td>
      <td>px</td>
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

  // Ottieni l'asse di simmetria
  const symmetryAxisData = getSymmetryAxisPosition();
  if (!symmetryAxisData) {
    console.warn('⚠️ Asse di simmetria non disponibile');
    rows += `<tr data-type="green-dots">
      <td>⚖️ Simmetria</td>
      <td>Asse non disponibile</td>
      <td>-</td>
      <td>❌ Errore</td>
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
      const heightDifference = Math.abs(leftHeight - rightHeight);

      console.log(`  📊 ${comparisonName}: L=${leftLabels[leftIdx]}(${leftPoint[0].toFixed(1)},${leftPoint[1].toFixed(1)}, dist⊥=${leftDistance.toFixed(1)}, h=${leftHeight.toFixed(1)}) vs R=${rightLabels[rightIdx]}(${rightPoint[0].toFixed(1)},${rightPoint[1].toFixed(1)}, dist⊥=${rightDistance.toFixed(1)}, h=${rightHeight.toFixed(1)}) → 🔴 ${fartherPoint} più lontano, ⬆️ ${higherPoint} più alto (diff=${heightDifference.toFixed(1)}px)`);

      // Riga distanza dall'asse - formato più chiaro con entrambe le distanze
      rows += `<tr data-type="green-dots">
        <td>⚖️ ${comparisonName} Distanza Asse</td>
        <td>${leftLabels[leftIdx]}: ${leftDistance.toFixed(1)}px | ${rightLabels[rightIdx]}: ${rightDistance.toFixed(1)}px<br/>
            <strong>🔴 ${fartherPoint} più esterno</strong> (+${distanceDifference.toFixed(1)}px)</td>
        <td>px</td>
        <td>✅ OK</td>
      </tr>`;

      rows += `<tr data-type="green-dots">
        <td>⬆️ ${comparisonName} Altezza</td>
        <td>⬆️ ${higherPoint} più alto (${heightDifference.toFixed(1)}px)</td>
        <td>px</td>
        <td>✅ OK</td>
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

  tbody.appendChild(row);

  // SOLO se richiesto esplicitamente, evidenzia il landmark sul canvas
  if (showHighlight) {
    highlightSelectedLandmark(landmarkId, color);
  }

  // Apri automaticamente la sezione LANDMARKS se era chiusa (vecchia - ora nascosta)
  openLandmarksSection();

  // Apri la sezione DATI ANALISI unificata e switcha al tab LANDMARKS
  openUnifiedAnalysisSection();
  switchUnifiedTab('landmarks'); // Forza il passaggio al tab landmarks

  console.log('🔄 [UNIFIED] Tab LANDMARKS attivato automaticamente');

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

function toggleGreenDots() {
  /**
   * Gestisce il toggle del pulsante GREEN DOTS nella sezione RILEVAMENTI.
   * Replica esattamente canvas_app.py:toggle_green_dots_section()
   */
  const btn = document.getElementById('green-dots-btn');
  btn.classList.toggle('active');

  const isActive = btn.classList.contains('active');

  if (isActive) {
    // Se non ci sono green dots rilevati, rilevali automaticamente
    if (!window.greenDotsDetected) {
      detectGreenDots();
    } else {
      updateCanvasDisplay();
      // Se i dati esistono già, pronuncia comunque il feedback se non soppresso
      if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak && !window.suppressVoiceFeedback) {
        const feedback = analyzeEyebrowDesignFromGreenDotsTable();
        if (feedback) {
          voiceAssistant.speak(feedback);
        }
      }
    }
  } else {
    updateCanvasDisplay();
  }

  updateStatus(isActive ? 'Green dots attivi' : 'Green dots disattivi');
}

async function detectGreenDots() {
  /**
   * Rileva i puntini verdi REALI nell'immagine usando l'API green dots.
   * Integra le funzionalità di src/green_dots_processor.py tramite API.
   */
  console.log('🟢 DEBUG: Funzioni disponibili:', {
    analyzeGreenDotsViaAPI: typeof analyzeGreenDotsViaAPI,
    API_CONFIG: typeof API_CONFIG,
    currentImage: !!currentImage
  });

  if (!currentImage) {
    showToast('Nessuna immagine caricata', 'warning');
    return;
  }

  try {
    updateStatus('🔄 Rilevamento green dots in corso...');

    // Ottieni l'immagine del canvas come base64
    const canvasImageData = getCanvasImageAsBase64();
    if (!canvasImageData) {
      throw new Error('Impossibile ottenere dati immagine dal canvas');
    }

    console.log('🟢 Invio richiesta API green dots...');

    // Chiamata all'API - usa funzione centralizzata se disponibile, altrimenti fallback
    let result;
    if (typeof analyzeGreenDotsViaAPI === 'function') {
      console.log('✅ Usando funzione API centralizzata');
      result = await analyzeGreenDotsViaAPI(canvasImageData, {
        hue_range: [60, 150],
        saturation_min: 15,
        value_range: [15, 95],
        cluster_size_range: [2, 150],
        clustering_radius: 2
      });
    } else {
      console.log('⚠️ Fallback: chiamata API diretta');
      // Fallback: chiamata diretta all'API tramite percorso relativo
      const baseUrl = (typeof API_CONFIG !== 'undefined' && API_CONFIG?.baseURL)
        ? API_CONFIG.baseURL
        : window.location.origin;
      const apiUrl = `${baseUrl}/api/green-dots/analyze`;
      console.log('🌍 URL API Green Dots (fallback):', apiUrl);
      console.log('🔧 API_CONFIG disponibile:', typeof API_CONFIG !== 'undefined');

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          image: canvasImageData,
          hue_range: [60, 150],
          saturation_min: 15,
          value_range: [15, 95],
          cluster_size_range: [2, 150],
          clustering_radius: 2
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      result = await response.json();
    }
    console.log('🟢 Risposta API green dots:', result);

    if (result.success) {
      // Salva i risultati globalmente
      window.greenDotsData = result;
      window.greenDotsDetected = true;

      // Aggiorna le misurazioni con i risultati
      console.log('📊 Chiamando updateMeasurementsFromGreenDots con:', result);
      updateMeasurementsFromGreenDots(result);

      // AUTOMAZIONE: Feedback vocale con analisi delle differenze
      // Aspetta un attimo che i dati siano nella tabella, poi pronuncia l'analisi
      setTimeout(() => {
        if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak && !window.suppressVoiceFeedback) {
          const feedback = analyzeEyebrowDesignFromGreenDotsTable();
          if (feedback) {
            console.log('🔊 [GREEN DOTS] Feedback vocale generato:', feedback);
            voiceAssistant.speak(feedback);
          }
        }
      }, 500);

      // AUTOMAZIONE: Attiva automaticamente l'asse di simmetria se non è già attivo
      const axisBtn = document.getElementById('axis-btn');
      if (axisBtn && !axisBtn.classList.contains('active')) {
        console.log('🔄 Attivazione automatica asse di simmetria...');
        // Sopprimi feedback vocale per questa attivazione automatica
        window.suppressVoiceFeedback = true;
        axisBtn.click(); // Simula click per attivare l'asse
        // Ripristina feedback vocale dopo un breve delay
        setTimeout(() => { window.suppressVoiceFeedback = false; }, 100);
      }

      // AUTOMAZIONE: Espandi la sezione correzione sopracciglia se è chiusa (nella LEFT sidebar!)
      console.log('🔍 Cercando sezione CORREZIONE SOPRACCIGLIA nella left sidebar...');
      const allSections = document.querySelectorAll('.left-sidebar .section');
      console.log(`🔍 Trovate ${allSections.length} sezioni nella left sidebar`);

      let found = false;
      allSections.forEach(section => {
        const toggleBtn = section.querySelector('.toggle-btn');
        if (toggleBtn) {
          console.log(`   - Sezione trovata: "${toggleBtn.textContent.substring(0, 40)}..."`);
          if (toggleBtn.textContent.includes('✂️ CORREZIONE SOPRACCIGLIA')) {
            found = true;
            const isExpanded = section.dataset.expanded === 'true';
            console.log(`   ✅ CORREZIONE SOPRACCIGLIA trovata! Expanded: ${isExpanded}`);
            if (!isExpanded) {
              console.log('📂 Apertura automatica sezione CORREZIONE SOPRACCIGLIA...');
              const sectionHeader = section.querySelector('.section-header');
              if (sectionHeader) {
                sectionHeader.click(); // Espandi la sezione
              } else {
                console.warn('⚠️ section-header non trovato!');
              }
            } else {
              console.log('   ℹ️ Sezione già aperta, nessuna azione necessaria');
            }
          }
        }
      });

      if (!found) {
        console.warn('⚠️ Sezione CORREZIONE SOPRACCIGLIA non trovata nella left sidebar!');
      }

      // Ridisegna il canvas con l'overlay
      updateCanvasDisplay();

      updateStatus(`✅ Rilevati ${result.detection_results.total_dots} green dots`);
      showToast(`Rilevamento completato: ${result.detection_results.total_dots} punti verdi`, 'success');

    } else {
      throw new Error(result.error || 'Errore sconosciuto durante l\'analisi');
    }

  } catch (error) {
    console.error('❌ Errore rilevamento green dots:', error);
    updateStatus('❌ Errore rilevamento green dots');
    showToast(`Errore: ${error.message}`, 'error');

    // Disattiva il pulsante green dots in caso di errore
    const btn = document.getElementById('green-dots-btn');
    if (btn && btn.classList.contains('active')) {
      btn.classList.remove('active');
    }
  }
}

function getCanvasImageAsBase64() {
  /**
   * Ottiene l'immagine corrente dal canvas come stringa base64.
   * Prende solo l'immagine di base senza overlay.
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

    // Imposta le dimensioni del canvas temporaneo
    tempCanvas.width = imageElement.naturalWidth || imageElement.width || 800;
    tempCanvas.height = imageElement.naturalHeight || imageElement.height || 600;

    // Disegna solo l'immagine corrente
    tempCtx.drawImage(imageElement, 0, 0, tempCanvas.width, tempCanvas.height);

    // Converte in base64
    const base64Data = tempCanvas.toDataURL('image/png');
    console.log('✅ Immagine convertita in base64 per analisi green dots:', {
      width: tempCanvas.width,
      height: tempCanvas.height,
      imageType: imageElement.constructor.name
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
   * svuota tabella misurazioni.
   */
  console.log('🧹 Pulizia misurazioni...');

  // Reset variabili
  window.selectedLandmarksForMeasurement = [];
  window.measurementResults = [];

  // Pulisci tabella
  const tbody = document.getElementById('measurements-data');
  if (tbody) {
    tbody.innerHTML = '';
  }

  // Rimuovi overlay dal canvas
  if (fabricCanvas) {
    const measurementObjects = fabricCanvas.getObjects().filter(obj => obj.isMeasurement);
    measurementObjects.forEach(obj => fabricCanvas.remove(obj));
    fabricCanvas.renderAll();
  }

  // Ridisegna landmarks se necessario
  if (window.measurementMode && currentLandmarks && currentLandmarks.length > 0) {
    if (typeof drawMediaPipeLandmarks === 'function') {
      drawMediaPipeLandmarks(currentLandmarks);
    }
  }

  // Nascondi il pulsante "NUOVA MISURAZIONE"
  const completeBtn = document.getElementById('complete-measure-btn');
  if (completeBtn) {
    completeBtn.style.display = 'none';
  }

  updateStatus('🧹 Misurazioni pulite - Riparti da zero');
  console.log('✅ Misurazioni pulite completamente');
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
function convertCurrentImageToBase64() {
  if (!currentImage) {
    throw new Error('currentImage non disponibile');
  }

  // Ottiene l'elemento HTML dall'oggetto Fabric.js
  let imageElement;
  if (currentImage.getElement) {
    imageElement = currentImage.getElement();
  } else if (currentImage.src) {
    imageElement = currentImage;
  } else {
    throw new Error('currentImage non è un oggetto valido');
  }

  const canvas = document.createElement('canvas');
  canvas.width = imageElement.naturalWidth || imageElement.width || currentImage.width;
  canvas.height = imageElement.naturalHeight || imageElement.height || currentImage.height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(imageElement, 0, 0);
  return canvas.toDataURL('image/jpeg', 0.8);
}

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

async function findBestFrontalFrame() {
  if (!window.currentVideo) {
    showToast('Nessun video caricato', 'warning');
    return;
  }

  const video = window.currentVideo;
  const duration = video.duration;
  const stepSize = 1.0; // Analizza ogni secondo
  let bestScore = 0;
  let bestTime = 0;
  const allResults = []; // 📊 Raccoglie tutti i risultati per la tabella

  updateStatus('🔍 Ricerca del miglior frame frontale...');

  try {
    // 📋 Pulisci tabella prima della nuova scansione
    clearDebugAnalysisTable();

    for (let time = 0; time < duration; time += stepSize) {
      // Aggiorna progress
      const progress = (time / duration) * 100;
      updateStatus(`🔍 Scansione: ${progress.toFixed(1)}% (${time.toFixed(1)}s/${duration.toFixed(1)}s)`);

      // Salta al frame
      drawVideoFrame(video, time);
      await new Promise(resolve => setTimeout(resolve, 500)); // Pausa per rendering

      // Converti currentImage in base64 per l'API
      if (!currentImage) {
        console.warn('⚠️ currentImage non disponibile, salto frame');
        continue;
      }

      try {
        const imageBase64 = convertCurrentImageToBase64();
        const analysisResult = await analyzeImageViaAPI(imageBase64);

        if (analysisResult && analysisResult.frontality_score) {
          const score = analysisResult.frontality_score;
          const poseAngles = analysisResult.pose_angles;

          // 📊 Aggiungi tutti i risultati alla tabella
          const frameData = {
            frameIndex: Math.floor(time / stepSize),
            time: time,
            score: score,
            pose: poseAngles,
            landmarks: analysisResult.landmarks,
            status: getFrontalityStatus(score)
          };

          allResults.push(frameData);
          addDebugAnalysisRow(frameData);

          if (score > bestScore) {
            bestScore = score;
            bestTime = time;
            console.log(`📈 Nuovo miglior frame: t=${time.toFixed(1)}s, score=${score.toFixed(3)}`);
          }
        }
      } catch (error) {
        console.warn(`⚠️ Errore analisi frame a ${time.toFixed(1)}s:`, error);
      }
    }

    // 🎯 Ordina e evidenzia i migliori frame nella tabella
    allResults.sort((a, b) => b.score - a.score);
    const topFrames = allResults.slice(0, 10); // Top 10 frame frontali
    highlightBestFramesInTable(topFrames);

    // 📈 Mostra statistiche dei frame frontali
    const frontalFrames = allResults.filter(f => f.score > 0.7); // Score > 0.7 considerato frontale
    console.log(`📊 STATISTICHE FRONTALITÀ:`);
    console.log(`- Frame totali analizzati: ${allResults.length}`);
    console.log(`- Frame molto frontali (>0.7): ${frontalFrames.length}`);
    console.log(`- Migliori 5 frame:`, topFrames.slice(0, 5).map(f => `t=${f.time.toFixed(1)}s (${f.score.toFixed(3)})`));

    // Vai al miglior frame trovato
    const timeline = document.getElementById('video-timeline');
    if (timeline) {
      timeline.value = bestTime;
    }
    drawVideoFrame(video, bestTime);

    // Analizza il miglior frame
    await analyzeCurrentVideoFrame();

    // ✅ AGGIORNA IL CANVAS ALLA FINE DELL'ANALISI
    updateCanvasDisplay();

    // 🔧 ASSICURA che le sezioni sidebar rimangano visibili dopo l'analisi
    ensureSidebarSectionsVisible();

    updateStatus(`✅ AUTOMATICO: Miglior frame selezionato a ${bestTime.toFixed(1)}s (Score: ${bestScore.toFixed(3)}) - ${frontalFrames.length}/${allResults.length} frame frontali trovati`);
    showToast(`🎯 Frame frontale trovato: ${bestTime.toFixed(1)}s (Score: ${bestScore.toFixed(3)}) - ${frontalFrames.length} frame molto frontali`, 'success');

  } catch (error) {
    console.error('❌ Errore ricerca miglior frame:', error);
    updateStatus('Errore durante la ricerca');
    showToast('Errore nella ricerca automatica', 'error');
  }
}

async function startAutomaticVideoScanning() {
  if (!window.currentVideo) {
    showToast('Nessun video caricato', 'warning');
    return;
  }

  const video = window.currentVideo;
  const duration = video.duration;
  const stepSize = 0.5; // Scansione più fine ogni 0.5s
  const results = [];

  updateStatus('🤖 Scansione automatica completa in corso...');

  try {
    // Pulisci tabella debug prima della nuova scansione
    clearDebugAnalysisTable();

    for (let time = 0; time < duration; time += stepSize) {
      const progress = (time / duration) * 100;
      updateStatus(`🤖 Analisi automatica: ${progress.toFixed(1)}%`);

      drawVideoFrame(video, time);
      await new Promise(resolve => setTimeout(resolve, 300));

      // Converti currentImage in base64 per l'API
      if (!currentImage) {
        console.warn('⚠️ currentImage non disponibile, salto frame');
        continue;
      }

      try {
        const imageBase64 = convertCurrentImageToBase64();
        const analysisResult = await analyzeImageViaAPI(imageBase64);

        if (analysisResult) {
          const score = analysisResult.frontality_score;
          const poseAngles = analysisResult.pose_angles;

          const frameData = {
            frameIndex: Math.floor(time / stepSize),
            time: time,
            score: score,
            pose: poseAngles,
            landmarks: analysisResult.landmarks,
            status: getFrontalityStatus(score)
          };

          results.push(frameData);

          // Aggiorna tabella debug in tempo reale
          addDebugAnalysisRow(frameData);
        }
      } catch (error) {
        console.warn(`⚠️ Errore analisi frame a ${time.toFixed(1)}s:`, error);
      }
    }

    // Ordina risultati per score
    results.sort((a, b) => b.score - a.score);

    // Salva risultati globalmente per riferimenti futuri
    window.videoAnalysisResults = results;

    // 🎯 Evidenzia i migliori frame nella tabella (Top 10 invece di 5)
    const topResults = results.slice(0, 10);
    highlightBestFramesInTable(topResults);

    // 📊 Statistiche dettagliate dei frame frontali
    const frontalFrames = results.filter(f => f.score > 0.7); // Score > 0.7 considerato frontale
    const veryFrontalFrames = results.filter(f => f.score > 0.8); // Score > 0.8 molto frontale
    const excellentFrames = results.filter(f => f.score > 0.9); // Score > 0.9 eccellente

    console.log('📊 STATISTICHE COMPLETE ANALISI VIDEO:');
    console.log(`- Frame totali analizzati: ${results.length}`);
    console.log(`- Frame frontali (>0.7): ${frontalFrames.length} (${((frontalFrames.length / results.length) * 100).toFixed(1)}%)`);
    console.log(`- Frame molto frontali (>0.8): ${veryFrontalFrames.length} (${((veryFrontalFrames.length / results.length) * 100).toFixed(1)}%)`);
    console.log(`- Frame eccellenti (>0.9): ${excellentFrames.length} (${((excellentFrames.length / results.length) * 100).toFixed(1)}%)`);

    // Mostra top 10 risultati
    console.log('🏆 TOP 10 FRAME PIÙ FRONTALI:');
    topResults.forEach((result, index) => {
      const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `#${index + 1}`;
      console.log(`${medal} t=${result.time.toFixed(1)}s - Score: ${result.score.toFixed(3)} - P:${result.pose.pitch.toFixed(1)}° Y:${result.pose.yaw.toFixed(1)}° R:${result.pose.roll.toFixed(1)}°`);
    });

    // Vai al miglior frame
    if (topResults.length > 0) {
      const bestResult = topResults[0];
      const timeline = document.getElementById('video-timeline');
      if (timeline) {
        timeline.value = bestResult.time;
      }
      drawVideoFrame(video, bestResult.time);
      await analyzeCurrentVideoFrame();

      // ✅ AGGIORNA IL CANVAS ALLA FINE DELLA SCANSIONE COMPLETA
      updateCanvasDisplay();

      // 🔧 ASSICURA che le sezioni sidebar rimangano visibili dopo l'analisi completa
      ensureSidebarSectionsVisible();

      updateStatus(`✅ Scansione completa - Miglior frame: ${bestResult.time.toFixed(1)}s (Score: ${bestResult.score.toFixed(3)}) - ${frontalFrames.length}/${results.length} frame frontali (${veryFrontalFrames.length} molto frontali)`);
      showToast(`📊 Analisi completata! ${results.length} frame analizzati - ${frontalFrames.length} frontali (${veryFrontalFrames.length} molto frontali, ${excellentFrames.length} eccellenti)`, 'success');
    } else {
      updateStatus('❌ Nessun volto rilevato nel video');
      showToast('Nessun volto rilevato', 'warning');
    }

  } catch (error) {
    console.error('❌ Errore scansione automatica:', error);
    updateStatus('Errore durante la scansione automatica');
    showToast('Errore nella scansione', 'error');
  }
}

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
   * Sincronizza l'overlay green dots quando il viewport del canvas cambia (pan)
   * Durante il pan, entrambi immagine e overlay si spostano, ma potrebbero desincronizzarsi
   */
  if (!window.currentGreenDotsOverlay) {
    console.log('⚠️ Nessun overlay green dots da sincronizzare con viewport');
    return;
  }

  if (!currentImage || !currentImage.isBackgroundImage) {
    console.log('⚠️ Nessuna immagine di sfondo per sincronizzazione viewport');
    return;
  }

  // Forza l'overlay ad avere esattamente le stesse coordinate dell'immagine
  window.currentGreenDotsOverlay.set({
    left: currentImage.left,
    top: currentImage.top,
    scaleX: currentImage.scaleX,
    scaleY: currentImage.scaleY
  });

  console.log('🔄 SINCRONIZZAZIONE VIEWPORT PAN:', {
    viewportTransform: fabricCanvas.viewportTransform,
    immagine: {
      pos: `(${currentImage.left.toFixed(1)}, ${currentImage.top.toFixed(1)})`,
      scale: currentImage.scaleX.toFixed(3)
    },
    overlay: {
      pos: `(${window.currentGreenDotsOverlay.left.toFixed(1)}, ${window.currentGreenDotsOverlay.top.toFixed(1)})`,
      scale: window.currentGreenDotsOverlay.scaleX.toFixed(3)
    }
  });

  // Forza il re-rendering per assicurarsi che tutto sia sincronizzato
  fabricCanvas.renderAll();
}

// ===================================
// INIZIALIZZAZIONE APP CON AUTH CHECK
// ===================================

window.addEventListener('DOMContentLoaded', async () => {
  console.log('🚀 Inizializzazione applicazione Medical Face Analysis');

  // STEP 1: Verifica autenticazione
  const isAuthenticated = await checkAuthentication();

  if (!isAuthenticated) {
    console.log('❌ Autenticazione fallita, app non inizializzata');
    return;
  }

  console.log('✅ Autenticazione completata, inizializzazione app...');

  // STEP 2: Messaggio di benvenuto personalizzato
  if (window.currentUserName && typeof voiceAssistant !== 'undefined') {
    // Aspetta un piccolo ritardo per dare tempo all'interfaccia di caricarsi
    setTimeout(() => {
      voiceAssistant.speakWelcome(window.currentUserName);
      console.log(`👋 Messaggio di benvenuto per ${window.currentUserName}`);
    }, 1000);
  }

  // STEP 3: Inizializza il resto dell'applicazione
  // (il resto del codice di inizializzazione esistente continua qui)
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
function switchUnifiedTab(tabName, event = null) {
  console.log(`🔄 Cambio tab unificato: ${tabName}`);

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

  // Ripristina le righe di misurazione
  if (measurementRows.length > 0) {
    measurementRows.forEach(row => tableBody.appendChild(row));
    console.log('✅ Ripristinate', measurementRows.length, 'righe di misurazione');
  } else {
    // Se non ci sono misurazioni, copia dalla tabella originale per retrocompatibilità
    const originalTableBody = document.getElementById('measurements-data');
    if (originalTableBody && originalTableBody.children.length > 0) {
      tableBody.innerHTML = originalTableBody.innerHTML;
      console.log('📋 Copiate misurazioni da tabella originale');
    } else {
      tableBody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Nessuna misurazione disponibile</td></tr>';
      console.log('ℹ️ Nessuna misurazione disponibile');
    }
  }

  console.log('✅ Tabella unificata aggiornata: Misurazioni');
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

  // Copia i dati dalla tabella originale
  const originalTableBody = document.getElementById('landmarks-data');
  if (originalTableBody) {
    tableBody.innerHTML = originalTableBody.innerHTML;
  } else {
    tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Nessun landmark disponibile</td></tr>';
  }

  console.log('✅ Tabella unificata aggiornata: Landmarks');
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

  console.log('✅ Tabella unificata aggiornata: Debug con ' + (originalTableBody ? originalTableBody.children.length : 0) + ' righe');
}

/**
 * Apre automaticamente la sezione DATI ANALISI quando arrivano nuovi dati
 * Versione 2.0 - Semplificata e robusta
 */
function openUnifiedAnalysisSection() {
  // LOG IMMEDIATO - per verificare se la funzione viene chiamata
  console.log('%c🔴 [UNIFIED v2.0] FUNZIONE CHIAMATA!', 'color: red; font-weight: bold; font-size: 14px');

  try {
    // Cerca tutte le sezioni
    const allSections = document.querySelectorAll('.section');
    console.log(`🔍 [UNIFIED] Trovate ${allSections.length} sezioni totali`);

    // Trova la sezione DATI ANALISI
    let targetSection = null;
    let targetContent = null;
    let targetIcon = null;

    allSections.forEach((section, index) => {
      const btn = section.querySelector('.toggle-btn');
      if (btn) {
        const text = btn.textContent || btn.innerText || '';
        console.log(`   [${index}] Pulsante: "${text.trim()}"`);

        if (text.includes('DATI ANALISI') || text.includes('📊')) {
          targetSection = section;
          targetContent = section.querySelector('.section-content');
          targetIcon = section.querySelector('.icon');
          console.log(`🎯 [UNIFIED] TROVATA sezione target all'indice ${index}!`);
        }
      }
    });

    if (!targetSection) {
      console.error('%c❌ [UNIFIED] SEZIONE NON TROVATA!', 'color: red; font-weight: bold');
      return;
    }

    // Apri la sezione
    if (targetContent) {
      const wasHidden = targetContent.style.display === 'none';
      targetContent.style.display = 'block';
      if (targetIcon) targetIcon.textContent = '▼';
      targetSection.setAttribute('data-expanded', 'true');

      console.log('%c✅ [UNIFIED] Sezione APERTA! (era nascosta: ' + wasHidden + ')', 'color: green; font-weight: bold');
    } else {
      console.error('❌ [UNIFIED] section-content non trovato');
    }

  } catch (error) {
    console.error('❌ [UNIFIED] ERRORE:', error);
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
