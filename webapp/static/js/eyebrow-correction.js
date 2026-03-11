/**
 * ============================================================================
 * EYEBROW CORRECTION - REPLICA ESATTA DESKTOP FLOW
 * ============================================================================
 * Data: 2025-11-16
 * Autore: Sistema WebApp
 * 
 * FLUSSO DESKTOP (da canvas_app.py):
 * 1. Verifica prerequisiti (green dots + landmarks)
 * 2. Calcola asse simmetria (landmark 9 → 151)
 * 3. Crea overlay COMPLETO su tutta l'immagine:
 *    - Disegna punti VERDI del lato selezionato
 *    - Riflette e disegna punti ROSSI del lato opposto
 * 4. Calcola bbox che include tutti i punti (verdi + rossi)
 * 5. Ritaglia l'immagine CON overlay al bbox
 * 6. Mostra finestra popup con immagine ritagliata
 */

console.log('🔄 Eyebrow Correction Module LOADED v1.0');

// ============================================================================
// HELPER FUNCTION - Interrompe sintesi vocale
// ============================================================================

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

// ============================================================================
// ENTRY POINTS - Chiamati dai pulsanti HTML
// ============================================================================

function showLeftEyebrow() {
  console.log('🟢 === CORREZIONE SOPRACCIGLIO SINISTRO ===');
  showEyebrowCorrectionWindow('left');
}

function showRightEyebrow() {
  console.log('🔵 === CORREZIONE SOPRACCIGLIO DESTRO ===');
  showEyebrowCorrectionWindow('right');
}

// ============================================================================
// MAIN FUNCTION
// ============================================================================

function showEyebrowCorrectionWindow(side) {
  try {
    const sideName = side === 'left' ? 'Sinistro' : 'Destro';
    console.log(`\n🚀 AVVIO CORREZIONE SOPRACCIGLIO ${sideName.toUpperCase()}`);

    // STEP 1: Verifica prerequisiti
    if (!window.greenDotsDetected || !window.greenDotsData?.success) {
      alert('Prerequisiti mancanti!\n\nÈ necessario:\n1. Rilevare i punti verdi (GREEN DOTS)\n2. Avere almeno una misurazione nella tabella');
      return;
    }

    if (!window.currentLandmarks || window.currentLandmarks.length < 152) {
      alert('Landmarks non disponibili!\n\nCalcola prima l\'asse di simmetria (pulsante ASSE)');
      return;
    }

    console.log('✅ Prerequisiti OK');

    // STEP 2: Ottieni immagine ORIGINALE (quella che vede l'utente!)
    if (!window.currentImage) {
      alert('Immagine non disponibile!\n\nCarica prima un\'immagine.');
      return;
    }

    // currentImage è un oggetto fabric.Image, l'elemento HTML è in _element
    const imageElement = window.currentImage._element || window.currentImage.getElement();
    if (!imageElement) {
      alert('Elemento immagine non accessibile!');
      return;
    }

    // Crea canvas temporaneo con l'immagine ORIGINALE
    const sourceCanvas = document.createElement('canvas');
    sourceCanvas.width = imageElement.width;
    sourceCanvas.height = imageElement.height;
    const sourceCtx = sourceCanvas.getContext('2d');
    sourceCtx.drawImage(imageElement, 0, 0);

    console.log(`📐 Source canvas (immagine originale): ${sourceCanvas.width}x${sourceCanvas.height}`);

    // STEP 3: Calcola asse simmetria (landmark 9 = glabella, 151 = chin)
    const axis = calculateSymmetryAxis();
    if (!axis) {
      alert('Impossibile calcolare asse di simmetria!');
      return;
    }
    console.log(`✅ Asse simmetria: (${axis.p1.x},${axis.p1.y}) → (${axis.p2.x},${axis.p2.y})`);

    // STEP 4: Crea overlay COMPLETO su tutta l'immagine
    const fullImageWithOverlay = createFullImageOverlay(sourceCanvas, side, axis);
    console.log(`✅ Overlay completo creato: ${fullImageWithOverlay.width}x${fullImageWithOverlay.height}`);

    // STEP 5: Calcola bounding box inclusivo (tutti i punti)
    const bbox = calculateInclusiveBbox(side, axis);
    console.log(`✅ Bbox calcolato:`, bbox);

    // STEP 6: Ritaglia immagine con overlay
    const croppedCanvas = cropImageToBbox(fullImageWithOverlay, bbox);
    console.log(`✅ Ritaglio completato: ${croppedCanvas.width}x${croppedCanvas.height}`);

    // Salva bbox, arrowPairs e scale backend→originale nel canvas per usarli nel popup
    croppedCanvas.bbox = bbox;
    croppedCanvas.arrowPairs = fullImageWithOverlay.arrowPairs;
    croppedCanvas.backendToOriginalX = fullImageWithOverlay.backendToOriginalX;
    croppedCanvas.backendToOriginalY = fullImageWithOverlay.backendToOriginalY;

    // STEP 7: Mostra finestra popup
    displayCorrectionWindow(croppedCanvas, side);
    console.log(`✅ === CORREZIONE ${sideName.toUpperCase()} COMPLETATA ===\n`);

  } catch (error) {
    console.error('❌ ERRORE:', error);
    alert(`Errore nella correzione:\n${error.message}`);
  }
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function calculateSymmetryAxis() {
  // Usa getSymmetryAxisPosition() (main.js) come fonte autorevole — garantisce coerenza con l'asse visivo
  if (typeof window.getSymmetryAxisPosition === 'function') {
    const axisPos = window.getSymmetryAxisPosition();
    if (axisPos && axisPos.line) {
      const p1 = { x: axisPos.line.x1, y: axisPos.line.y1 };
      const p2 = { x: axisPos.line.x2, y: axisPos.line.y2 };
      console.log(`✅ Asse simmetria da getSymmetryAxisPosition()`);
      console.log(`   📍 p1: (${p1.x.toFixed(1)}, ${p1.y.toFixed(1)})`);
      console.log(`   📍 p2: (${p2.x.toFixed(1)}, ${p2.y.toFixed(1)})`);
      return { p1, p2 };
    }
  }

  // Fallback: trasforma coordinate raw → canvas
  const glabella = window.currentLandmarks?.[9];
  const philtrum = window.currentLandmarks?.[164];

  if (!glabella || !philtrum) {
    console.error('❌ Landmarks 9 o 164 non disponibili');
    return null;
  }

  const p1 = window.transformLandmarkCoordinate(glabella);
  const p2 = window.transformLandmarkCoordinate(philtrum);

  console.log(`✅ Asse simmetria via transformLandmarkCoordinate (fallback)`);
  return { p1, p2 };
}

function createFullImageOverlay(sourceCanvas, side, axis) {
  // Crea canvas delle stesse dimensioni dell'immagine originale
  const overlayCanvas = document.createElement('canvas');
  overlayCanvas.width = sourceCanvas.width;
  overlayCanvas.height = sourceCanvas.height;
  const ctx = overlayCanvas.getContext('2d');

  // FONDAMENTALE: Copia PRIMA l'immagine originale come sfondo
  ctx.drawImage(sourceCanvas, 0, 0);
  console.log(`  📋 Immagine base copiata: ${overlayCanvas.width}x${overlayCanvas.height}`);

  // I punti green dots dall'API sono in coordinate BACKEND (ridimensionate max 1600px)
  // NON sono in coordinate immagine originale!
  const greenDots = side === 'left'
    ? window.greenDotsData.groups.Sx.slice(0, 5)
    : window.greenDotsData.groups.Dx.slice(0, 5);

  const dotsToReflect = side === 'left'
    ? window.greenDotsData.groups.Dx.slice(0, 5)
    : window.greenDotsData.groups.Sx.slice(0, 5);

  console.log(`  📍 Punti verdi (coordinate backend): ${greenDots.length}, Punti da riflettere: ${dotsToReflect.length}`);

  // CRITICO: Calcola le scale corrette
  // 1. greenDotsData.image_size = dimensioni immagine processata dal backend
  // 2. sourceCanvas = dimensioni immagine originale
  // 3. axis = coordinate canvas display (da landmarks) CON OFFSET!

  const backendWidth = window.greenDotsData.image_size[0];
  const backendHeight = window.greenDotsData.image_size[1];
  const originalWidth = sourceCanvas.width;
  const originalHeight = sourceCanvas.height;

  // Rileva se c'è stato ridimensionamento nel frontend
  const wasResized = (backendWidth !== originalWidth) || (backendHeight !== originalHeight);
  const resizeRatio = wasResized ? (originalWidth / backendWidth) : 1.0;

  console.log(`  📐 Backend: ${backendWidth}x${backendHeight}, Original: ${originalWidth}x${originalHeight}`);
  console.log(`  📐 Ridimensionamento: ${wasResized ? 'SI' : 'NO'}, Ratio: ${resizeRatio.toFixed(3)}`);

  // Scala da backend a originale
  const backendToOriginalX = originalWidth / backendWidth;
  const backendToOriginalY = originalHeight / backendHeight;

  // IMPORTANTE: L'asse ha un offset (left/top dell'immagine nel canvas Fabric.js)
  const imageOffset = window.imageOffset || { x: 0, y: 0 };
  const imageScale = window.imageScale || 1;

  // Scala da display a backend (con rimozione offset!)
  const fabricScaleX = window.currentImage.scaleX || 1;
  const fabricScaleY = window.currentImage.scaleY || 1;

  console.log(`  📐 ImageScale: ${imageScale.toFixed(3)}, Offset: (${imageOffset.x.toFixed(1)}, ${imageOffset.y.toFixed(1)})`);
  console.log(`  📐 FabricScale: (${fabricScaleX.toFixed(3)}, ${fabricScaleY.toFixed(3)})`);
  console.log(`  📐 Scale backend→original: X=${backendToOriginalX.toFixed(3)}, Y=${backendToOriginalY.toFixed(3)}`);

  // FLUSSO DIVERSO per immagini piccole (no resize) vs grandi (con resize)
  let axisBackend;

  if (!wasResized) {
    // IMMAGINI PICCOLE: coordinate già corrette, conversione semplice
    console.log(`  ✅ Immagine NON ridimensionata - Flusso semplice`);
    axisBackend = {
      p1: {
        x: (axis.p1.x - imageOffset.x) / imageScale,
        y: (axis.p1.y - imageOffset.y) / imageScale
      },
      p2: {
        x: (axis.p2.x - imageOffset.x) / imageScale,
        y: (axis.p2.y - imageOffset.y) / imageScale
      }
    };
  } else {
    // IMMAGINI GRANDI: rimuovi offset + scala display→original→backend
    console.log(`  ⚠️ Immagine ridimensionata - Flusso con scale`);
    axisBackend = {
      p1: {
        x: ((axis.p1.x - imageOffset.x) / imageScale) / backendToOriginalX,
        y: ((axis.p1.y - imageOffset.y) / imageScale) / backendToOriginalY
      },
      p2: {
        x: ((axis.p2.x - imageOffset.x) / imageScale) / backendToOriginalX,
        y: ((axis.p2.y - imageOffset.y) / imageScale) / backendToOriginalY
      }
    };
  }

  console.log(`  📏 Asse display (con offset):`, axis);
  console.log(`  📏 Asse backend:`, axisBackend);

  // Array per salvare coppie di punti per le frecce
  const arrowPairs = [];

  // Dimensione punti fissa a schermo: calcola la stessa scale usata dal popup
  // così i cerchi appaiono sempre uguali indipendentemente dalla risoluzione dell'immagine
  const _maxDisplayW = window.innerWidth * 0.9;
  const _maxDisplayH = window.innerHeight * 0.75;
  const _bbox = calculateInclusiveBbox(side, axis);  // stima bbox per la scala
  const _cropW = _bbox ? _bbox.width : originalWidth;
  const _cropH = _bbox ? _bbox.height : originalHeight;
  const _scaleX = _maxDisplayW / _cropW;
  const _scaleY = _maxDisplayH / _cropH;
  const _displayScale = Math.min(_scaleX, _scaleY, 8);
  // 18px fissi a schermo → raggio in pixel canvas originale
  const FIXED_SCREEN_RADIUS = 18;
  const pointRadius = Math.max(2, Math.round(FIXED_SCREEN_RADIUS / _displayScale));
  console.log(`  🎨 Dimensione punti: ${pointRadius.toFixed(1)}px (wasResized: ${wasResized}, ratio: ${resizeRatio.toFixed(2)})`);

  // Disegna punti VERDI (backend → originale per disegno)
  ctx.fillStyle = 'rgb(0, 255, 0)';
  greenDots.forEach((dot, i) => {
    const originalX = wasResized ? (dot.x * backendToOriginalX) : dot.x;
    const originalY = wasResized ? (dot.y * backendToOriginalY) : dot.y;
    ctx.beginPath();
    ctx.arc(originalX, originalY, pointRadius, 0, 2 * Math.PI);
    ctx.fill();
    console.log(`    🟢 Punto verde ${i + 1}: backend(${dot.x.toFixed(1)},${dot.y.toFixed(1)}) → original(${originalX.toFixed(1)},${originalY.toFixed(1)})`);
  });

  // Array per salvare i punti rossi riflessi
  const reflectedRedDots = [];

  // Rifletti punti ROSSI (in coordinate backend, poi scala a originale per disegno)
  ctx.fillStyle = 'rgb(255, 0, 0)';
  dotsToReflect.forEach((dot, i) => {
    // Rifletti in coordinate backend
    const reflected = reflectPointAcrossAxis({ x: dot.x, y: dot.y }, axisBackend);

    // Scala a originale per disegno
    const originalX = wasResized ? (reflected.x * backendToOriginalX) : reflected.x;
    const originalY = wasResized ? (reflected.y * backendToOriginalY) : reflected.y;

    ctx.beginPath();
    ctx.arc(originalX, originalY, pointRadius, 0, 2 * Math.PI);
    ctx.fill();

    reflectedRedDots.push(reflected);

    console.log(`    🔴 Punto rosso ${i + 1}: backend(${dot.x.toFixed(1)},${dot.y.toFixed(1)}) → riflesso_backend(${reflected.x.toFixed(1)},${reflected.y.toFixed(1)}) → original(${originalX.toFixed(1)},${originalY.toFixed(1)})`);
  });

  // Accoppia ogni punto verde con il punto rosso tramite nome anatomico corrispondente.
  // Gli ordini nei due array differiscono: Sx=[LC1,LA0,LA,LC,LB], Dx=[RC1,RB,RC,RA,RA0]
  // quindi né l'indice né la distanza minima garantiscono l'accoppiamento corretto.
  // La mappa L↔R è: LA↔RA, LA0↔RA0, LC1↔RC1, LC↔RC, LB↔RB
  const anatomicalPairMap = { 'LA':'RA','LA0':'RA0','LC1':'RC1','LC':'RC','LB':'RB',
                               'RA':'LA','RA0':'LA0','RC1':'LC1','RC':'LC','RB':'LB' };
  // Costruisce una mappa nome→{point, reflectedPoint} per dotsToReflect
  const redDotByName = {};
  dotsToReflect.forEach((dot, i) => {
    const name = dot.anatomical_name;
    if (name) redDotByName[name] = reflectedRedDots[i];
  });

  console.log(`  🔗 Accoppiamento punti verde-rosso per nome anatomico:`);
  greenDots.forEach((greenDot, greenIdx) => {
    const greenName = greenDot.anatomical_name;
    const partnerName = anatomicalPairMap[greenName];
    const matchedRedDot = partnerName ? redDotByName[partnerName] : null;

    if (!matchedRedDot) {
      console.warn(`    ⚠️ Verde ${greenIdx} (${greenName}): nessun punto rosso corrispondente per "${partnerName}"`);
      return;
    }

    const dx = matchedRedDot.x - greenDot.x;
    const dy = matchedRedDot.y - greenDot.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    // Scala entrambi i punti a originale per il disegno
    arrowPairs.push({
      from: {
        x: wasResized ? (greenDot.x * backendToOriginalX) : greenDot.x,
        y: wasResized ? (greenDot.y * backendToOriginalY) : greenDot.y
      },
      to: {
        x: wasResized ? (matchedRedDot.x * backendToOriginalX) : matchedRedDot.x,
        y: wasResized ? (matchedRedDot.y * backendToOriginalY) : matchedRedDot.y
      }
    });
    console.log(`    🔗 Verde[${greenIdx}] ${greenName} → Rosso ${partnerName} (distanza backend: ${distance.toFixed(1)}px)`);
  });

  // Restituisce il canvas E i dati delle frecce per disegnarle in SVG
  overlayCanvas.arrowPairs = arrowPairs;
  // Salva le scale per conversione backend→originale (usata da applyPopupGreyingByPoints)
  overlayCanvas.backendToOriginalX = backendToOriginalX;
  overlayCanvas.backendToOriginalY = backendToOriginalY;

  return overlayCanvas;
}

function reflectPointAcrossAxis(point, axis) {
  // Vettore dell'asse
  const axisVector = {
    x: axis.p2.x - axis.p1.x,
    y: axis.p2.y - axis.p1.y
  };

  // Normalizza l'asse
  const axisLength = Math.sqrt(axisVector.x ** 2 + axisVector.y ** 2);

  if (axisLength === 0) {
    console.error('❌ reflectPointAcrossAxis: Asse con lunghezza zero!', axis);
    return point;
  }

  const axisNorm = {
    x: axisVector.x / axisLength,
    y: axisVector.y / axisLength
  };

  // Normale perpendicolare all'asse (rotazione di 90° in senso orario)
  const normal = { x: -axisNorm.y, y: axisNorm.x };

  // Vettore dal punto dell'asse al punto da riflettere
  const toPoint = {
    x: point.x - axis.p1.x,
    y: point.y - axis.p1.y
  };

  // Prodotto scalare: distanza con segno dal punto all'asse lungo la normale
  const distance = toPoint.x * normal.x + toPoint.y * normal.y;

  // Rifletti: punto - 2 * distanza * normale
  const reflected = {
    x: point.x - 2 * distance * normal.x,
    y: point.y - 2 * distance * normal.y
  };

  // Log solo per il primo punto (evita spam)
  if (point.x < 100 || Math.random() < 0.2) {
    console.log(`  🔄 Riflessione: (${point.x.toFixed(1)},${point.y.toFixed(1)}) → (${reflected.x.toFixed(1)},${reflected.y.toFixed(1)}) | dist=${distance.toFixed(1)}px`);
  }

  return reflected;
}

function calculateInclusiveBbox(side, axis) {
  // I green dots dall'API sono in coordinate BACKEND (ridimensionate)
  const greenDots = side === 'left'
    ? window.greenDotsData.groups.Sx.slice(0, 5)
    : window.greenDotsData.groups.Dx.slice(0, 5);

  const dotsToReflect = side === 'left'
    ? window.greenDotsData.groups.Dx.slice(0, 5)
    : window.greenDotsData.groups.Sx.slice(0, 5);

  console.log(`  📏 Bbox basato su ${greenDots.length} punti verdi + ${dotsToReflect.length} punti rossi riflessi`);

  // Calcola le scale
  const backendWidth = window.greenDotsData.image_size[0];
  const backendHeight = window.greenDotsData.image_size[1];
  const imageElement = window.currentImage._element || window.currentImage.getElement();
  const originalWidth = imageElement.width;
  const originalHeight = imageElement.height;

  const backendToOriginalX = originalWidth / backendWidth;
  const backendToOriginalY = originalHeight / backendHeight;

  // Rileva se c'è stato ridimensionamento
  const wasResized = (backendWidth !== originalWidth) || (backendHeight !== originalHeight);

  // IMPORTANTE: L'asse ha un offset (left/top dell'immagine nel canvas Fabric.js)
  const imageOffset = window.imageOffset || { x: 0, y: 0 };
  const imageScale = window.imageScale || 1;

  const fabricScaleX = window.currentImage.scaleX || 1;
  const fabricScaleY = window.currentImage.scaleY || 1;

  // Converti asse a backend con flusso appropriato
  let axisBackend;
  if (!wasResized) {
    // IMMAGINI PICCOLE: conversione semplice
    axisBackend = {
      p1: {
        x: (axis.p1.x - imageOffset.x) / imageScale,
        y: (axis.p1.y - imageOffset.y) / imageScale
      },
      p2: {
        x: (axis.p2.x - imageOffset.x) / imageScale,
        y: (axis.p2.y - imageOffset.y) / imageScale
      }
    };
  } else {
    // IMMAGINI GRANDI: rimuovi offset + scala
    axisBackend = {
      p1: {
        x: ((axis.p1.x - imageOffset.x) / imageScale) / backendToOriginalX,
        y: ((axis.p1.y - imageOffset.y) / imageScale) / backendToOriginalY
      },
      p2: {
        x: ((axis.p2.x - imageOffset.x) / imageScale) / backendToOriginalX,
        y: ((axis.p2.y - imageOffset.y) / imageScale) / backendToOriginalY
      }
    };
  }

  // Calcola punti rossi riflessi in coordinate backend
  const reflectedRedDots = dotsToReflect.map(dot =>
    reflectPointAcrossAxis({ x: dot.x, y: dot.y }, axisBackend)
  );

  // Combina TUTTI i punti (verdi + rossi) e scala a originale
  const allPointsOriginal = [
    ...greenDots.map(d => ({
      x: wasResized ? (d.x * backendToOriginalX) : d.x,
      y: wasResized ? (d.y * backendToOriginalY) : d.y
    })),
    ...reflectedRedDots.map(d => ({
      x: wasResized ? (d.x * backendToOriginalX) : d.x,
      y: wasResized ? (d.y * backendToOriginalY) : d.y
    }))
  ];

  // Trova min/max
  let minX = Infinity, minY = Infinity;
  let maxX = -Infinity, maxY = -Infinity;

  allPointsOriginal.forEach(dot => {
    minX = Math.min(minX, dot.x);
    minY = Math.min(minY, dot.y);
    maxX = Math.max(maxX, dot.x);
    maxY = Math.max(maxY, dot.y);
  });

  // Espandi bbox del 50% (come in desktop)
  const width = maxX - minX;
  const height = maxY - minY;
  const expandX = width * 0.5 / 2;
  const expandY = height * 0.5 / 2;

  const bbox = {
    x: Math.floor(minX - expandX),
    y: Math.floor(minY - expandY),
    width: Math.ceil(width + width * 0.5),
    height: Math.ceil(height + height * 0.5)
  };

  console.log(`  📦 Bbox: x=${bbox.x}, y=${bbox.y}, w=${bbox.width}, h=${bbox.height}`);

  return bbox;
}

function cropImageToBbox(sourceCanvas, bbox) {
  const croppedCanvas = document.createElement('canvas');
  croppedCanvas.width = bbox.width;
  croppedCanvas.height = bbox.height;
  const ctx = croppedCanvas.getContext('2d');

  // Copia la porzione dell'immagine
  ctx.drawImage(
    sourceCanvas,
    bbox.x, bbox.y, bbox.width, bbox.height,  // sorgente
    0, 0, bbox.width, bbox.height             // destinazione
  );

  return croppedCanvas;
}

function displayCorrectionWindow(croppedCanvas, side) {
  // Titoli aggiornati: riferimento all'immagine (opposto al cliente)
  const sideName = side === 'left'
    ? 'Sopracciglio a sinistra dell\'immagine (DESTRO DEL CLIENTE)'
    : 'Sopracciglio a destra dell\'immagine (SINISTRO DEL CLIENTE)';

  // Crea modale
  const modal = document.createElement('div');
  modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;

  // Container contenuto
  const content = document.createElement('div');
  content.style.cssText = `
        background: white;
        padding: 20px;
        border-radius: 12px;
        max-width: 95vw;
        max-height: 95vh;
        display: flex;
        flex-direction: column;
        gap: 15px;
    `;

  // Titolo
  const title = document.createElement('h2');
  title.textContent = `🔍 Correzione del ${sideName}`;
  title.style.cssText = 'margin: 0; color: #333; font-size: 20px;';

  // Legenda
  const legend = document.createElement('div');
  legend.style.cssText = 'display: flex; gap: 20px; font-size: 14px; flex-wrap: wrap;';
  legend.innerHTML = `
        <span style="color: green;">🟢 Verde: Punti da spostare del sopracciglio da modificare</span>
        <span style="color: red;">🔴 Rosso: POSIZIONE DEI NUOVI PUNTI DA DISEGNARE (vicino quelli esistenti)</span>
        <span style="color: black;">➡️ Frecce: Direzione verso la quale deve essere spostato il punto originale</span>
    `;

  // Container per immagine + frecce animate
  const imageContainer = document.createElement('div');
  imageContainer.style.cssText = 'position: relative; display: inline-block; max-width: 95vw; max-height: 80vh; overflow: auto;';

  // Calcola scala dinamica per immagini grandi
  // Immagini piccole (< 300px): scala 8x
  // Immagini grandi (> 300px): scala per adattarsi allo schermo
  const maxDisplayWidth = window.innerWidth * 0.9;
  const maxDisplayHeight = window.innerHeight * 0.75;

  let scale;
  if (croppedCanvas.width < 300 && croppedCanvas.height < 300) {
    // Immagine piccola: ingrandisci molto
    scale = 8;
  } else {
    // Immagine grande: scala per adattarsi
    const scaleX = maxDisplayWidth / croppedCanvas.width;
    const scaleY = maxDisplayHeight / croppedCanvas.height;
    scale = Math.min(scaleX, scaleY, 4); // Max 4x per immagini grandi
  }

  console.log(`  🖼️ Crop: ${croppedCanvas.width}x${croppedCanvas.height}, Display scale: ${scale.toFixed(2)}x`);

  // Immagine scalata
  const img = document.createElement('img');
  img.src = croppedCanvas.toDataURL('image/png');
  img.style.cssText = `
        width: ${croppedCanvas.width * scale}px;
        height: ${croppedCanvas.height * scale}px;
        image-rendering: ${scale >= 4 ? 'pixelated' : 'auto'};
        border: 2px solid #ccc;
        display: block;
    `;

  imageContainer.appendChild(img);

  // Aggiungi SVG overlay con frecce animate se ci sono dati
  if (croppedCanvas.arrowPairs && croppedCanvas.arrowPairs.length > 0 && croppedCanvas.bbox) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    // CORREZIONE: SVG deve avere le stesse dimensioni scalate dell'immagine
    const svgWidth = croppedCanvas.width * scale;
    const svgHeight = croppedCanvas.height * scale;
    svg.style.cssText = `
      position: absolute;
      top: 0;
      left: 0;
      width: ${svgWidth}px;
      height: ${svgHeight}px;
      pointer-events: none;
      z-index: 1000;
    `;
    // ViewBox mantiene le coordinate originali del canvas, ma SVG è scalato
    svg.setAttribute('viewBox', `0 0 ${croppedCanvas.width} ${croppedCanvas.height}`);
    svg.setAttribute('preserveAspectRatio', 'none');

    // Aggiungi animazione CSS lampeggiante
    const style = document.createElement('style');
    style.textContent = `
      @keyframes blink-arrow {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.2; }
      }
      @keyframes pulse-glow {
        0%, 100% { 
          filter: drop-shadow(0 0 1px rgba(0,0,0,0.8));
        }
        50% { 
          filter: drop-shadow(0 0 2px rgba(255,255,0,0.9)) drop-shadow(0 0 3px rgba(255,255,0,0.6));
        }
      }
      .arrow-animated {
        animation: blink-arrow 1s ease-in-out infinite, pulse-glow 1s ease-in-out infinite;
      }
    `;
    document.head.appendChild(style);

    const bbox = croppedCanvas.bbox;

    croppedCanvas.arrowPairs.forEach((pair, i) => {
      // Coordinate relative al crop (sottrai offset del bbox)
      const fromX = pair.from.x - bbox.x;
      const fromY = pair.from.y - bbox.y;
      const toX = pair.to.x - bbox.x;
      const toY = pair.to.y - bbox.y;

      const dx = toX - fromX;
      const dy = toY - fromY;
      const distance = Math.sqrt(dx * dx + dy * dy);

      // Normalizza direzione
      const dirX = dx / distance;
      const dirY = dy / distance;

      // Freccia più visibile per immagini grandi: max 14px o 30% della distanza
      const arrowLength = Math.min(14, distance * 0.30);

      // Punto finale freccia
      const endX = fromX + dirX * arrowLength;
      const endY = fromY + dirY * arrowLength;

      // Crea gruppo per la freccia
      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('class', 'arrow-animated');

      // Linea freccia con gradiente di spessore (più sottile all'inizio, più spessa alla fine)
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', fromX);
      line.setAttribute('y1', fromY);
      line.setAttribute('x2', endX);
      line.setAttribute('y2', endY);
      line.setAttribute('stroke', '#000000');
      line.setAttribute('stroke-width', '1.5');
      line.setAttribute('stroke-linecap', 'round');
      g.appendChild(line);

      // FRECCIA DIREZIONALE MIGLIORATA: triangolo isoscele con punta pronunciata
      const headLength = 5.5;  // Lunghezza dalla punta alla base (più grande per immagini grandi)
      const headWidth = 2.0;   // Larghezza base per maggiore visibilità
      const angle = Math.atan2(dy, dx);

      // Crea triangolo isoscele che punta nella direzione
      const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');

      // Punta del triangolo (alla fine della linea)
      const tipX = endX;
      const tipY = endY;

      // Base del triangolo più corta (perpendicolare alla direzione)
      const baseLeftX = endX - headLength * Math.cos(angle) - headWidth * Math.sin(angle);
      const baseLeftY = endY - headLength * Math.sin(angle) + headWidth * Math.cos(angle);
      const baseRightX = endX - headLength * Math.cos(angle) + headWidth * Math.sin(angle);
      const baseRightY = endY - headLength * Math.sin(angle) - headWidth * Math.cos(angle);

      polygon.setAttribute('points', `${tipX},${tipY} ${baseLeftX},${baseLeftY} ${baseRightX},${baseRightY}`);
      polygon.setAttribute('fill', '#000000');
      polygon.setAttribute('stroke', '#FFD700');  // Bordo giallo per maggiore visibilità
      polygon.setAttribute('stroke-width', '0.5');

      g.appendChild(polygon);

      svg.appendChild(g);

      console.log(`    ➡️ Freccia SVG ${i + 1}: da verde(${fromX.toFixed(1)},${fromY.toFixed(1)}) verso rosso(${toX.toFixed(1)},${toY.toFixed(1)}), distanza totale=${distance.toFixed(1)}px, lunghezza freccia=${arrowLength.toFixed(1)}px`);
    });

    imageContainer.appendChild(svg);
  }

  // Container bottoni
  const buttons = document.createElement('div');
  buttons.style.cssText = 'display: flex; gap: 10px; justify-content: center;';

  // Bottone salva
  const saveBtn = document.createElement('button');
  saveBtn.textContent = '💾 Salva Immagine';
  saveBtn.className = 'btn btn-primary';
  saveBtn.onclick = () => {
    const link = document.createElement('a');
    link.download = `sopracciglio_${side}_${Date.now()}.png`;
    link.href = croppedCanvas.toDataURL('image/png');
    link.click();
  };

  // Bottone chiudi
  const closeBtn = document.createElement('button');
  closeBtn.textContent = '❌ Chiudi';
  closeBtn.className = 'btn btn-secondary';
  closeBtn.onclick = () => {
    window._speakPairsActive = false;
    stopVoiceAssistant();
    modal.remove();
  };

  // Chiudi modal cliccando sul background scuro
  modal.onclick = (e) => {
    if (e.target === modal) {
      window._speakPairsActive = false;
      stopVoiceAssistant();
      modal.remove();
    }
  };

  // Assembla tutto
  buttons.appendChild(saveBtn);
  buttons.appendChild(closeBtn);

  content.appendChild(title);
  content.appendChild(legend);
  content.appendChild(imageContainer);
  content.appendChild(buttons);

  modal.appendChild(content);
  document.body.appendChild(modal);

  // Esponi dati popup globalmente per sincronizzazione TTS
  window._eyebrowCorrectionPopup = {
    modal,
    imageContainer,
    img,
    croppedCanvas,
    scale,
    side
  };

  console.log('✅ Finestra modale aperta');
}

// Export funzioni globali
window.showLeftEyebrow = showLeftEyebrow;
window.showRightEyebrow = showRightEyebrow;

console.log('✅ Eyebrow Correction Module READY');
