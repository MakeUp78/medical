/*
 * Sistema Canvas - Gestione canvas con Fabric.js per replica dell'interfaccia desktop
 */

// === VARIABILI GLOBALI CANVAS ===

// fabricCanvas viene dichiarata globalmente per essere accessibile da tutti i moduli
if (typeof fabricCanvas === 'undefined') var fabricCanvas = null;
// currentImage e currentLandmarks sono dichiarate in main.js
let canvasScale = 1.0;
let canvasOffset = { x: 0, y: 0 };

// Salvataggio landmark originali per trasformazioni
let originalLandmarks = []; // Landmark in coordinate normalizzate (0-1)
let currentLandmarkObjects = []; // Oggetti Fabric.js dei landmark correnti

// Modalità canvas
let drawingMode = false;
let landmarksVisible = true;
let gridVisible = false; // Griglia opzionale
let measurementMode = false; // Modalità misurazione

// === INIZIALIZZAZIONE CANVAS ===

function initializeFabricCanvas() {
  const canvasElement = document.getElementById('main-canvas');
  if (!canvasElement) {
    console.error('Canvas element not found');
    return;
  }

  console.log('🎨 Inizializzazione Fabric.js canvas...');

  // Inizializza Fabric.js canvas con dimensioni dinamiche
  const container = document.querySelector('.canvas-wrapper');
  const containerRect = container.getBoundingClientRect();
  const initialWidth = Math.max(400, containerRect.width - 10);
  const initialHeight = Math.max(300, containerRect.height - 10);

  fabricCanvas = new fabric.Canvas('main-canvas', {
    width: initialWidth,
    height: initialHeight,
    backgroundColor: '#f0f0f0',
    selection: true,
    preserveObjectStacking: true
  });

  console.log('✅ Fabric canvas creato:', fabricCanvas);

  // Correzione più robusta: intercetta errori della console
  window.addEventListener('error', function (e) {
    if (e.message && e.message.includes('alphabetical') && e.message.includes('CanvasTextBaseline')) {
      e.preventDefault();
      console.warn('🔧 Errore textBaseline intercettato e ignorato');
      return false;
    }
  });

  // Event listeners per interazioni canvas
  setupCanvasEventListeners();

  // Aggiorna dimensioni responsive
  // Aspetta che il DOM sia completamente renderizzato
  setTimeout(() => {
    resizeCanvas();
    console.log('🎨 Canvas dimensioni aggiornate');
  }, 100);

  // Aggiungi griglia di default
  drawGrid();

  console.log('🎨 Canvas inizializzato correttamente');
}

function setupCanvasEventListeners() {
  if (!fabricCanvas) return;

  // Mouse events per misurazioni
  fabricCanvas.on('mouse:down', function (e) {
    if (measurementMode && e.e) {
      const pointer = fabricCanvas.getPointer(e.e);
      handleMeasurementClick(pointer.x, pointer.y);
    }
  });

  // Zoom con rotella mouse
  fabricCanvas.on('mouse:wheel', function (opt) {
    const delta = opt.e.deltaY;
    let zoom = fabricCanvas.getZoom();
    zoom *= 0.999 ** delta;

    if (zoom > 20) zoom = 20;
    if (zoom < 0.01) zoom = 0.01;

    fabricCanvas.setZoom(zoom);
    canvasScale = zoom;
    opt.e.preventDefault();
    opt.e.stopPropagation();

    updateZoomDisplay(zoom);
  });

  // Event listener per trasformazioni dell'immagine
  fabricCanvas.on('object:modified', function (e) {
    if (e.target === currentImage) {
      console.log('🔄 Immagine trasformata - ridisegno landmark');
      setTimeout(() => redrawLandmarks(), 50);
    }
  });

  fabricCanvas.on('object:moved', function (e) {
    if (e.target === currentImage) {
      console.log('📍 Immagine spostata - aggiorno landmark');
      setTimeout(() => redrawLandmarks(), 10);
    }
  });

  fabricCanvas.on('object:scaled', function (e) {
    if (e.target === currentImage) {
      console.log('📏 Immagine ridimensionata - aggiorno landmark');
      setTimeout(() => redrawLandmarks(), 10);
    }
  });

  fabricCanvas.on('object:rotated', function (e) {
    if (e.target === currentImage) {
      console.log('🔄 Immagine ruotata - aggiorno landmark');
      setTimeout(() => redrawLandmarks(), 10);
    }
  });

  // Event listener per zoom canvas
  fabricCanvas.on('after:render', function () {
    // Ridisegna solo se il zoom è cambiato significativamente
    const currentZoom = fabricCanvas.getZoom();
    if (Math.abs(currentZoom - canvasScale) > 0.05) {
      canvasScale = currentZoom;
      if (originalLandmarks.length > 0) {
        setTimeout(() => redrawLandmarks(), 20);
      }
    }
  });

  // Pan con trascinamento
  let isPanning = false;
  fabricCanvas.on('mouse:down', function (opt) {
    const evt = opt.e;
    if (evt.ctrlKey === true) {
      isPanning = true;
      fabricCanvas.selection = false;
      fabricCanvas.defaultCursor = 'move';
    }
  });

  fabricCanvas.on('mouse:move', function (opt) {
    if (isPanning === true) {
      const evt = opt.e;
      const vpt = fabricCanvas.viewportTransform;
      vpt[4] += evt.clientX - (this.lastPosX || evt.clientX);
      vpt[5] += evt.clientY - (this.lastPosY || evt.clientY);

      fabricCanvas.requestRenderAll();
      this.lastPosX = evt.clientX;
      this.lastPosY = evt.clientY;
    }
  });

  fabricCanvas.on('mouse:up', function (opt) {
    fabricCanvas.setViewportTransform(fabricCanvas.viewportTransform);
    isPanning = false;
    fabricCanvas.selection = true;
    fabricCanvas.defaultCursor = 'default';
  });

  // Ridimensionamento finestra
  window.addEventListener('resize', resizeCanvas);
}

function updateCanvasEventListeners() {
  if (!fabricCanvas) return;

  // Aggiorna cursore basato sulla modalità corrente
  if (measurementMode) {
    fabricCanvas.defaultCursor = 'crosshair';
    fabricCanvas.hoverCursor = 'crosshair';
  } else if (drawingMode) {
    fabricCanvas.defaultCursor = 'crosshair';
    fabricCanvas.hoverCursor = 'crosshair';
  } else {
    fabricCanvas.defaultCursor = 'default';
    fabricCanvas.hoverCursor = 'move';
  }
}

// === GESTIONE IMMAGINI ===

function loadImageToCanvas(imageFile) {
  if (!fabricCanvas || !imageFile) return;

  const reader = new FileReader();

  reader.onload = function (e) {
    fabric.Image.fromURL(e.target.result, function (img) {
      // Rimuovi immagine precedente se presente
      if (currentImage) {
        fabricCanvas.remove(currentImage);
      }

      // Utilizza tutto lo spazio disponibile con padding minimo
      const sizing = calculateOptimalImageSize(
        img.width,
        img.height,
        fabricCanvas.width,
        fabricCanvas.height,
        10  // padding ridotto
      );

      console.log('📐 Dimensioni immagine ottimizzate:', sizing);

      img.scale(sizing.scale);

      // Posiziona immagine utilizzando tutto lo spazio disponibile
      img.set({
        left: sizing.left,
        top: sizing.top,
        selectable: true,   // Abilita selezione per trasformazioni
        evented: true,      // Abilita eventi per trasformazioni
        lockUniScaling: true, // Mantieni proporzioni durante resize
        cornerStyle: 'circle',
        cornerSize: 10,
        transparentCorners: false,
        cornerColor: '#007bff'
      });

      currentImage = img;
      fabricCanvas.add(img);
      fabricCanvas.sendToBack(img); // Immagine sempre dietro
      fabricCanvas.renderAll();

      console.log('📷 Immagine caricata nel canvas con dimensioni ottimali');

      // Forza un ulteriore ridimensionamento per assicurarsi che tutto sia ottimizzato
      setTimeout(() => {
        forceCanvasResize();
      }, 100);

      // Aggiorna info immagine
      updateImageInfo(img);

      // Auto-rileva landmarks se possibile
      if (typeof detectFaceLandmarks === 'function') {
        detectFaceLandmarks(e.target.result);
      }
    });
  };

  reader.readAsDataURL(imageFile);
}

function updateImageInfo(img) {
  const info = document.getElementById('image-info');
  if (info && img) {
    const width = Math.round(img.width);
    const height = Math.round(img.height);
    const scale = Math.round(img.scaleX * 100);

    info.innerHTML = `
            <i class="fas fa-info-circle"></i>
            ${width}×${height}px (${scale}%)
        `;
  }
}

// === LANDMARKS ===

function saveLandmarksAsNormalized(landmarks, imageWidth, imageHeight) {
  /**
   * Salva i landmark in coordinate normalizzate (0-1) relative all'immagine originale
   */

  // Se l'immagine ha dimensioni originali disponibili, usa quelle
  let normalizeWidth = imageWidth;
  let normalizeHeight = imageHeight;

  console.log(`🔍 DEBUG saveLandmarksAsNormalized - Input: ${imageWidth}x${imageHeight}`);
  console.log(`🔍 currentImage type:`, currentImage ? currentImage.type : 'null');
  console.log(`🔍 currentImage.getElement available:`, currentImage && typeof currentImage.getElement === 'function');

  if (currentImage) {
    // Prova diversi modi per ottenere le dimensioni originali
    if (typeof currentImage.getElement === 'function') {
      const element = currentImage.getElement();
      if (element) {
        const originalWidth = element.naturalWidth || element.width;
        const originalHeight = element.naturalHeight || element.height;

        if (originalWidth && originalHeight) {
          console.log(`📏 Dimensioni per normalizzazione - Canvas: ${imageWidth}x${imageHeight}, Originali: ${originalWidth}x${originalHeight}`);
          normalizeWidth = originalWidth;
          normalizeHeight = originalHeight;
        }
      }
    } else if (currentImage._element) {
      // Fallback per immagini statiche
      const element = currentImage._element;
      const originalWidth = element.naturalWidth || element.width;
      const originalHeight = element.naturalHeight || element.height;

      if (originalWidth && originalHeight) {
        console.log(`📏 Dimensioni per normalizzazione (fallback) - Canvas: ${imageWidth}x${imageHeight}, Originali: ${originalWidth}x${originalHeight}`);
        normalizeWidth = originalWidth;
        normalizeHeight = originalHeight;
      }
    }
  }

  originalLandmarks = landmarks.map(landmark => {
    // Se i landmark sono già normalizzati, lasciali così
    if (landmark.x <= 1.0 && landmark.y <= 1.0) {
      console.log(`✅ Landmark già normalizzato: (${landmark.x}, ${landmark.y})`);
      return { ...landmark };
    }
    // Altrimenti normalizzali usando le dimensioni originali
    const normalized = {
      x: landmark.x / normalizeWidth,
      y: landmark.y / normalizeHeight,
      z: landmark.z || 0,
      visibility: landmark.visibility || 1.0
    };
    console.log(`🔄 Landmark normalizzato: (${landmark.x}, ${landmark.y}) → (${normalized.x}, ${normalized.y})`);
    return normalized;
  });

  console.log(`💾 Salvati ${originalLandmarks.length} landmark normalizzati (${normalizeWidth}x${normalizeHeight})`);
}

function transformLandmarksToCanvasCoords() {
  /**
   * Trasforma i landmark normalizzati nelle coordinate attuali del canvas
   * basandosi sulla posizione e scala correnti dell'immagine
   */
  if (!currentImage || !fabricCanvas || originalLandmarks.length === 0) {
    return [];
  }

  // Usa le proprietà dirette dell'immagine per ottenere coordinate precise
  const imageLeft = currentImage.left;
  const imageTop = currentImage.top;

  // Ora tutto passa attraverso il flusso video uniforme
  const imageWidth = currentImage.getScaledWidth();
  const imageHeight = currentImage.getScaledHeight();

  console.log(`🔧 Transform landmarks - Image pos: (${imageLeft}, ${imageTop}), size: ${imageWidth}x${imageHeight}`);
  console.log(`🔧 currentImage properties:`, {
    width: currentImage.width,
    height: currentImage.height,
    scaleX: currentImage.scaleX,
    scaleY: currentImage.scaleY,
    left: currentImage.left,
    top: currentImage.top
  });

  const transformedLandmarks = originalLandmarks.map((landmark, index) => {
    const transformed = {
      x: imageLeft + (landmark.x * imageWidth),
      y: imageTop + (landmark.y * imageHeight),
      z: landmark.z,
      visibility: landmark.visibility,
      index: index
    };

    // Log solo i primi 3 landmark per non intasare la console
    if (index < 3) {
      console.log(`🔄 Landmark ${index}: (${landmark.x}, ${landmark.y}) → (${transformed.x}, ${transformed.y})`);
    }

    return transformed;
  });

  console.log(`✅ Trasformati ${transformedLandmarks.length} landmarks`);
  return transformedLandmarks;
}

function clearLandmarks() {
  /**
   * Rimuove tutti i landmark dal canvas
   */
  if (!fabricCanvas) return;

  const landmarkObjects = fabricCanvas.getObjects().filter(obj => obj.isLandmark);
  landmarkObjects.forEach(obj => fabricCanvas.remove(obj));
  currentLandmarkObjects = [];
}

function redrawLandmarks() {
  /**
   * Ridisegna i landmark usando le coordinate trasformate attuali
   */
  if (!fabricCanvas || originalLandmarks.length === 0) return;

  // Verifica se i landmarks devono essere visibili
  const landmarksBtn = document.getElementById('landmarks-btn');
  const shouldShowLandmarks = landmarksBtn && landmarksBtn.classList.contains('active');

  if (!shouldShowLandmarks) return;

  // Cancella landmark esistenti
  clearLandmarks();

  // Calcola nuove coordinate
  const transformedLandmarks = transformLandmarksToCanvasCoords();

  // Ridisegna con le nuove coordinate
  drawLandmarkPoints(transformedLandmarks);
}

function drawMediaPipeLandmarks(landmarks) {
  /**
   * Disegna i landmarks MediaPipe sul canvas con i colori appropriati per ogni regione del viso
   * Supporta tutti i 478 landmarks MediaPipe Face Mesh
   * Args:
   *   landmarks: Array di oggetti {x, y, z?, visibility?}
   */
  console.log('🔥 DISEGNO MEDIAPIPE LANDMARKS 🔥');

  if (!fabricCanvas) {
    console.error('❌ fabricCanvas non disponibile');
    return;
  }

  if (!landmarks || landmarks.length === 0) {
    console.error('❌ Nessun landmark fornito');
    return;
  }

  // Verifica se i landmarks devono essere visibili
  const landmarksBtn = document.getElementById('landmarks-btn');
  const shouldShowLandmarks = landmarksBtn && landmarksBtn.classList.contains('active');

  if (!shouldShowLandmarks) {
    console.log('❌ Landmarks non abilitati - USCITA');
    return;
  }

  console.log(`🎯 Disegno ${landmarks.length} landmarks MediaPipe`);

  // Salva i landmark originali per future trasformazioni
  if (currentImage) {
    // Ora tutto passa attraverso il flusso video uniforme, quindi usa sempre getScaledWidth
    const currentWidth = currentImage.getScaledWidth();
    const currentHeight = currentImage.getScaledHeight();

    console.log(`💾 Normalizzazione landmarks con dimensioni correnti: ${currentWidth}x${currentHeight}`);
    saveLandmarksAsNormalized(landmarks, currentWidth, currentHeight);
  }

  // Rimuovi landmarks precedenti
  clearLandmarks();

  // Calcola dimensione cerchio in base al zoom del canvas
  const zoomFactor = fabricCanvas.getZoom() || 1.0;
  let circleRadius, strokeWidth;

  if (zoomFactor < 0.5) {
    circleRadius = 2; // Punti piccoli per immagini ridotte
    strokeWidth = 1;
  } else if (zoomFactor < 1.0) {
    circleRadius = 3; // Punti medi per zoom normale
    strokeWidth = 1;
  } else if (zoomFactor > 2.0) {
    circleRadius = 1.5; // Punti molto piccoli per ingrandimenti
    strokeWidth = 0.5;
  } else {
    circleRadius = 2.5; // Dimensione default
    strokeWidth = 1;
  }

  console.log(`🔴 DIMENSIONI CERCHI: raggio=${circleRadius}px, stroke=${strokeWidth}px, zoom=${zoomFactor.toFixed(2)}`);

  let visibleCount = 0;
  let invisibleCount = 0;

  // Usa le coordinate trasformate per il disegno
  const transformedLandmarks = transformLandmarksToCanvasCoords();
  drawLandmarkPoints(transformedLandmarks);

  console.log(`✅ ${landmarks.length} landmarks processati e salvati per trasformazioni automatiche`);
}

function drawLandmarkPoints(transformedLandmarks) {
  /**
   * Disegna effettivamente i punti landmark sul canvas
   */
  if (!fabricCanvas || !transformedLandmarks) return;

  // Calcola dimensione cerchio in base al zoom del canvas
  const zoomFactor = fabricCanvas.getZoom() || 1.0;
  let circleRadius, strokeWidth;

  if (zoomFactor < 0.5) {
    circleRadius = 2;
    strokeWidth = 1;
  } else if (zoomFactor < 1.0) {
    circleRadius = 3;
    strokeWidth = 1;
  } else if (zoomFactor > 2.0) {
    circleRadius = 1.5;
    strokeWidth = 0.5;
  } else {
    circleRadius = 2.5;
    strokeWidth = 1;
  }

  console.log(`🔴 DIMENSIONI CERCHI: raggio=${circleRadius}px, stroke=${strokeWidth}px, zoom=${zoomFactor.toFixed(2)}`);

  let visibleCount = 0;
  let invisibleCount = 0;

  transformedLandmarks.forEach((landmark, index) => {
    // Verifica se il landmark è nel canvas
    const isVisible = (
      landmark.x >= 0 &&
      landmark.x <= fabricCanvas.width &&
      landmark.y >= 0 &&
      landmark.y <= fabricCanvas.height
    );

    if (isVisible) {
      visibleCount++;
    } else {
      invisibleCount++;
    }

    // Ottieni colore appropriato per regione MediaPipe
    const fillColor = getMediaPipeLandmarkColor(index);
    const strokeColor = '#FFFFFF';

    // Crea il cerchio per il landmark
    const circle = new fabric.Circle({
      left: landmark.x - circleRadius,
      top: landmark.y - circleRadius,
      radius: circleRadius,
      fill: fillColor,
      stroke: strokeColor,
      strokeWidth: strokeWidth,
      selectable: false,
      evented: false,
      isLandmark: true,
      landmarkIndex: index,
      landmarkType: 'mediapipe'
    });

    fabricCanvas.add(circle);
    currentLandmarkObjects.push(circle);
  });

  // Porta tutti i landmarks in primo piano
  const landmarkObjects = fabricCanvas.getObjects().filter(obj => obj.isLandmark);
  landmarkObjects.forEach(landmark => fabricCanvas.bringToFront(landmark));

  fabricCanvas.renderAll();

  console.log(`✅ ${transformedLandmarks.length} landmarks processati - Visibili: ${visibleCount}, Fuori canvas: ${invisibleCount}`);
  console.log(`🔴 Cerchi landmark creati: ${landmarkObjects.length}`);
}

function getMediaPipeLandmarkColor(index) {
  /**
   * Colori per diverse regioni del viso MediaPipe Face Mesh (478 landmarks)
   */
  // Contorno viso (0-16)
  if (index <= 16) return '#FF6B6B';

  // Sopracciglio destro (17-21)
  if (index >= 17 && index <= 21) return '#4ECDC4';

  // Sopracciglio sinistro (22-26) 
  if (index >= 22 && index <= 26) return '#4ECDC4';

  // Naso (27-35)
  if (index >= 27 && index <= 35) return '#45B7D1';

  // Occhio destro (36-41)
  if (index >= 36 && index <= 41) return '#F9CA24';

  // Occhio sinistro (42-47)
  if (index >= 42 && index <= 47) return '#F9CA24';

  // Bocca esterno (48-59)
  if (index >= 48 && index <= 59) return '#6C5CE7';

  // Bocca interno (60-67)
  if (index >= 60 && index <= 67) return '#A29BFE';

  // Regioni MediaPipe specifiche
  // Naso completo (includendo narici)
  if ((index >= 1 && index <= 9) || (index >= 168 && index <= 175)) return '#00CEC9';

  // Occhi completi (includendo palpebre)
  if ((index >= 33 && index <= 35) || (index >= 133 && index <= 145) ||
    (index >= 362 && index <= 384) || (index >= 385 && index <= 398)) return '#FDCB6E';

  // Labbra complete
  if ((index >= 61 && index <= 96) || (index >= 269 && index <= 306) ||
    (index >= 375 && index <= 402)) return '#E17055';

  // Guance
  if ((index >= 116 && index <= 117) || (index >= 213 && index <= 192) ||
    (index >= 234 && index <= 227) || (index >= 435 && index <= 410)) return '#74B9FF';

  // Fronte
  if ((index >= 10 && index <= 151) || (index >= 9 && index <= 10) ||
    (index >= 151 && index <= 162)) return '#00B894';

  // Default per altri punti MediaPipe
  return '#DDA0DD'; // Orchid per punti generici
}

function getLandmarkColor(index) {
  // Colori diversi per diverse parti del viso
  if (index >= 0 && index <= 16) return '#ff6b6b';      // Contorno viso
  if (index >= 17 && index <= 21) return '#4ecdc4';     // Sopracciglio destro
  if (index >= 22 && index <= 26) return '#4ecdc4';     // Sopracciglio sinistro
  if (index >= 27 && index <= 35) return '#45b7d1';     // Naso
  if (index >= 36 && index <= 47) return '#f9ca24';     // Occhi
  if (index >= 48 && index <= 67) return '#6c5ce7';     // Bocca
  return '#95a5a6'; // Punti generici
}

function clearLandmarks() {
  if (!fabricCanvas) return;

  const landmarks = fabricCanvas.getObjects().filter(obj => obj.isLandmark);
  landmarks.forEach(landmark => fabricCanvas.remove(landmark));
}

// Rendi la funzione globalmente accessibile
window.drawMediaPipeLandmarks = drawMediaPipeLandmarks;

// Alias per compatibilità con api-client.js
function drawLandmarksOnCanvas(landmarks) {
  console.log('🔄 drawLandmarksOnCanvas chiamata - redirigo a drawMediaPipeLandmarks');
  drawMediaPipeLandmarks(landmarks);
}

// Rendi anche l'alias globalmente accessibile
window.drawLandmarksOnCanvas = drawLandmarksOnCanvas;

// Funzione toggleLandmarks rimossa - ora gestita da main.js per evitare conflitti

function updateLandmarksCount(count) {
  // Aggiorna il badge landmarks nell'interfaccia
  if (typeof updateLandmarksBadge === 'function') {
    updateLandmarksBadge(count);
  }

  // Fallback per elemento diretto se esiste
  const counter = document.getElementById('landmarks-count');
  if (counter) {
    counter.textContent = count;
  }
}

// === GRIGLIA ===

function drawGrid() {
  if (!fabricCanvas) return;

  clearGrid();

  if (!gridVisible) return;

  const gridSize = 20;
  const width = fabricCanvas.width;
  const height = fabricCanvas.height;

  // Linee verticali
  for (let i = 0; i <= width; i += gridSize) {
    const line = new fabric.Line([i, 0, i, height], {
      stroke: '#e9ecef',
      strokeWidth: 0.5,
      selectable: false,
      evented: false,
      isGrid: true
    });
    fabricCanvas.add(line);
  }

  // Linee orizzontali
  for (let i = 0; i <= height; i += gridSize) {
    const line = new fabric.Line([0, i, width, i], {
      stroke: '#e9ecef',
      strokeWidth: 0.5,
      selectable: false,
      evented: false,
      isGrid: true
    });
    fabricCanvas.add(line);
  }

  // Invia griglia dietro tutto
  const gridLines = fabricCanvas.getObjects().filter(obj => obj.isGrid);
  gridLines.forEach(line => fabricCanvas.sendToBack(line));

  fabricCanvas.renderAll();
}

function clearGrid() {
  if (!fabricCanvas) return;

  const gridLines = fabricCanvas.getObjects().filter(obj => obj.isGrid);
  gridLines.forEach(line => fabricCanvas.remove(line));
}

function toggleGrid() {
  gridVisible = !gridVisible;

  const btn = document.getElementById('grid-btn');
  if (btn) {
    if (gridVisible) {
      btn.classList.add('active');
      btn.innerHTML = '<i class="fas fa-th"></i> Griglia ON';
    } else {
      btn.classList.remove('active');
      btn.innerHTML = '<i class="fas fa-th"></i> Griglia OFF';
    }
  }

  drawGrid();
}

// === ZOOM E PAN ===

function zoomIn() {
  if (!fabricCanvas) return;

  const zoom = fabricCanvas.getZoom();
  const newZoom = Math.min(zoom * 1.2, 20);
  fabricCanvas.setZoom(newZoom);
  canvasScale = newZoom;

  updateZoomDisplay(newZoom);
}

function zoomOut() {
  if (!fabricCanvas) return;

  const zoom = fabricCanvas.getZoom();
  const newZoom = Math.max(zoom * 0.8, 0.1);
  fabricCanvas.setZoom(newZoom);
  canvasScale = newZoom;

  updateZoomDisplay(newZoom);
}

function zoomFit() {
  if (!fabricCanvas || !currentImage) return;

  const imgBounds = currentImage.getBoundingRect();
  const canvasWidth = fabricCanvas.width;
  const canvasHeight = fabricCanvas.height;

  const scaleX = canvasWidth / imgBounds.width;
  const scaleY = canvasHeight / imgBounds.height;
  const scale = Math.min(scaleX, scaleY) * 0.9;

  fabricCanvas.setZoom(scale);
  canvasScale = scale;

  // Centra immagine
  fabricCanvas.absolutePan(new fabric.Point(
    (canvasWidth - imgBounds.width * scale) / 2,
    (canvasHeight - imgBounds.height * scale) / 2
  ));

  updateZoomDisplay(scale);
}

function zoomReset() {
  if (!fabricCanvas) return;

  fabricCanvas.setZoom(1);
  fabricCanvas.absolutePan(new fabric.Point(0, 0));
  canvasScale = 1;

  updateZoomDisplay(1);
}

function updateZoomDisplay(zoom) {
  const display = document.getElementById('zoom-level');
  if (display) {
    display.textContent = `${Math.round(zoom * 100)}%`;
  }
}

// === DIMENSIONAMENTO ===

function resizeCanvas() {
  if (!fabricCanvas) return;

  const container = document.querySelector('.canvas-wrapper');
  if (!container) return;

  const containerRect = container.getBoundingClientRect();
  // Riduci il padding a 10px per utilizzare più spazio
  const newWidth = Math.max(400, containerRect.width - 10);
  const newHeight = Math.max(300, containerRect.height - 10);

  console.log('🔧 Ridimensionamento canvas:', {
    containerWidth: containerRect.width,
    containerHeight: containerRect.height,
    newWidth,
    newHeight
  });

  fabricCanvas.setDimensions({
    width: newWidth,
    height: newHeight
  });

  // Ridimensiona l'immagine corrente se presente
  if (currentImage && typeof calculateOptimalImageSize === 'function') {
    const sizing = calculateOptimalImageSize(
      currentImage.width / currentImage.scaleX, // dimensioni originali
      currentImage.height / currentImage.scaleY,
      newWidth,
      newHeight,
      10
    );

    currentImage.set({
      scaleX: sizing.scale,
      scaleY: sizing.scale,
      left: sizing.left,
      top: sizing.top
    });

    console.log('🔄 Immagine ridimensionata per nuovo canvas');
  }

  // Ridisegna griglia se attiva
  if (gridVisible) {
    drawGrid();
  }

  // Ridisegna landmark se presenti
  if (originalLandmarks.length > 0) {
    setTimeout(() => redrawLandmarks(), 100);
  }

  fabricCanvas.renderAll();
}

// === GESTIONE MISURAZIONI ===

function handleMeasurementClick(x, y) {
  /**
   * Gestisce i click quando è attiva la modalità misurazione
   */
  console.log('📐 Click misurazione:', { x, y, measurementMode });

  // Per ora è solo un placeholder - il nuovo sistema usa i toggle dei pulsanti
  // Questo può essere esteso in futuro per misurazioni manuali
}

// === UTILITÀ RIDIMENSIONAMENTO ===

// Funzione di utilità per forzare il ridimensionamento
function forceCanvasResize() {
  if (typeof resizeCanvas === 'function') {
    setTimeout(() => {
      resizeCanvas();
      console.log('🔄 Forzato ridimensionamento canvas');
    }, 50);
  }
}

// Calcola le dimensioni ottimali per l'immagine utilizzando tutto lo spazio disponibile
function calculateOptimalImageSize(imgWidth, imgHeight, canvasWidth, canvasHeight, padding = 10) {
  // Spazio utile (sottraendo padding)
  const availableWidth = canvasWidth - (padding * 2);
  const availableHeight = canvasHeight - (padding * 2);

  // Calcola il ratio di scala per mantenere le proporzioni
  const scaleX = availableWidth / imgWidth;
  const scaleY = availableHeight / imgHeight;
  const scale = Math.min(scaleX, scaleY);

  // Calcola dimensioni finali
  const finalWidth = imgWidth * scale;
  const finalHeight = imgHeight * scale;

  // Calcola posizione per centrare l'immagine
  const left = (canvasWidth - finalWidth) / 2;
  const top = (canvasHeight - finalHeight) / 2;

  return {
    scale: scale,
    width: finalWidth,
    height: finalHeight,
    left: left,
    top: top
  };
}

// Aggiungi evento per ridimensionamento quando cambia l'orientamento
window.addEventListener('orientationchange', () => {
  setTimeout(forceCanvasResize, 200);
});

// Funzione per ottimizzare la visualizzazione dell'immagine corrente
function optimizeCurrentImageDisplay() {
  if (!currentImage || !fabricCanvas) return;

  const sizing = calculateOptimalImageSize(
    currentImage.width / currentImage.scaleX, // dimensioni originali
    currentImage.height / currentImage.scaleY,
    fabricCanvas.width,
    fabricCanvas.height,
    10
  );

  currentImage.set({
    scaleX: sizing.scale,
    scaleY: sizing.scale,
    left: sizing.left,
    top: sizing.top
  });

  fabricCanvas.renderAll();

  // Ridisegna landmark se presenti
  if (originalLandmarks.length > 0) {
    setTimeout(() => redrawLandmarks(), 100);
  }

  console.log('✨ Ottimizzata visualizzazione immagine corrente');
}

// Funzione per abilitare/disabilitare trasformazioni immagine
function toggleImageTransform() {
  if (!currentImage) return;

  const isSelectable = currentImage.selectable;

  currentImage.set({
    selectable: !isSelectable,
    evented: !isSelectable
  });

  fabricCanvas.renderAll();

  if (isSelectable) {
    console.log('🔒 Trasformazioni immagine disabilitate');
    updateStatus('Immagine bloccata - trasformazioni disabilitate');
  } else {
    console.log('🔓 Trasformazioni immagine abilitate');
    updateStatus('Immagine sbloccata - trasformazioni abilitate (trascina, zoom, ruota)');
  }
}

// === ESPORTAZIONE ===

function exportCanvasImage() {
  if (!fabricCanvas) return;

  // Crea immagine dal canvas
  const dataURL = fabricCanvas.toDataURL({
    format: 'png',
    quality: 1.0,
    multiplier: 1
  });

  // Download automatico
  const a = document.createElement('a');
  a.href = dataURL;
  a.download = `canvas_export_${new Date().getTime()}.png`;
  a.click();

  showToast('Canvas esportato come immagine', 'success');
}

function exportCanvasJSON() {
  if (!fabricCanvas) return;

  const json = JSON.stringify(fabricCanvas.toJSON(), null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `canvas_data_${new Date().getTime()}.json`;
  a.click();

  URL.revokeObjectURL(url);
  showToast('Dati canvas esportati', 'success');
}

// === UTILITÀ ===

function clearCanvas() {
  if (!fabricCanvas) return;

  // Rimuovi tutto tranne l'immagine di sfondo
  const objects = fabricCanvas.getObjects();
  objects.forEach(obj => {
    if (obj !== currentImage) {
      fabricCanvas.remove(obj);
    }
  });

  // Reset variabili
  currentLandmarks = [];
  measurementLines = [];
  measurementHistory = [];

  fabricCanvas.renderAll();

  // Aggiorna UI
  updateLandmarksCount(0);
  updateMeasurementTable();

  showToast('Canvas pulito', 'info');
}

function redrawCanvas() {
  if (!fabricCanvas) return;

  fabricCanvas.renderAll();

  // Ridisegna elementi se necessario
  if (gridVisible) {
    drawGrid();
  }

  if (landmarksVisible && currentLandmarks.length > 0) {
    // I landmarks sono già oggetti nel canvas, non serve ridisegnarli
  }

  if (measurementLines.length > 0) {
    redrawAllMeasurements();
  }
}