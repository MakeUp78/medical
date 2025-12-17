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

    // Salva bbox e arrowPairs nel canvas per usarli nel popup
    croppedCanvas.bbox = bbox;
    croppedCanvas.arrowPairs = fullImageWithOverlay.arrowPairs;

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
  // MediaPipe landmarks: 9 = glabella (centro fronte), 151 = chin (mento)
  const glabella = window.currentLandmarks[9];
  const chin = window.currentLandmarks[151];

  if (!glabella || !chin) {
    console.error('❌ Landmarks 9 o 151 non disponibili');
    return null;
  }

  // Trasforma coordinate landmark → canvas (passa l'intero oggetto!)
  const p1 = window.transformLandmarkCoordinate(glabella);
  const p2 = window.transformLandmarkCoordinate(chin);

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

  // I punti green dots dall'API sono già in coordinate IMMAGINE ORIGINALE
  // NON servono conversioni!
  const greenDots = side === 'left'
    ? window.greenDotsData.groups.Sx.slice(0, 5)
    : window.greenDotsData.groups.Dx.slice(0, 5);

  const dotsToReflect = side === 'left'
    ? window.greenDotsData.groups.Dx.slice(0, 5)
    : window.greenDotsData.groups.Sx.slice(0, 5);

  console.log(`  📍 Punti verdi: ${greenDots.length}, Punti da riflettere: ${dotsToReflect.length}`);

  // L'asse è in coordinate canvas, dobbiamo convertirlo a coordinate immagine
  const scale = window.imageScale || 1;
  const offset = window.imageOffset || { x: 0, y: 0 };

  const canvasToImage = (canvasPoint) => ({
    x: (canvasPoint.x - offset.x) / scale,
    y: (canvasPoint.y - offset.y) / scale
  });

  const axisImage = {
    p1: canvasToImage(axis.p1),
    p2: canvasToImage(axis.p2)
  };

  console.log(`  📏 Asse convertito a coordinate immagine`);

  // Array per salvare coppie di punti per le frecce
  const arrowPairs = [];

  // Disegna punti VERDI (originali del lato selezionato)
  ctx.fillStyle = 'rgb(0, 255, 0)';
  greenDots.forEach((dot, i) => {
    ctx.beginPath();
    ctx.arc(dot.x, dot.y, 1, 0, 2 * Math.PI);
    ctx.fill();
    console.log(`    🟢 Punto verde ${i + 1}: (${dot.x.toFixed(1)}, ${dot.y.toFixed(1)})`);
  });

  // Array per salvare i punti rossi riflessi
  const reflectedRedDots = [];

  // Rifletti e disegna punti ROSSI (dal lato opposto)
  ctx.fillStyle = 'rgb(255, 0, 0)';
  dotsToReflect.forEach((dot, i) => {
    const reflected = reflectPointAcrossAxis({ x: dot.x, y: dot.y }, axisImage);
    ctx.beginPath();
    ctx.arc(reflected.x, reflected.y, 1, 0, 2 * Math.PI);
    ctx.fill();

    reflectedRedDots.push(reflected);

    console.log(`    🔴 Punto rosso ${i + 1}: (${dot.x.toFixed(1)}, ${dot.y.toFixed(1)}) → (${reflected.x.toFixed(1)}, ${reflected.y.toFixed(1)})`);
  });

  // CORREZIONE: Accoppia ogni punto verde con il punto rosso PIÙ VICINO
  // Questo garantisce che le frecce puntino sempre al centro del punto corrispondente
  console.log(`  🔗 Accoppiamento punti verde-rosso per distanza minima:`);
  greenDots.forEach((greenDot, greenIdx) => {
    // Trova il punto rosso più vicino a questo punto verde
    let minDistance = Infinity;
    let closestRedDot = null;
    let closestRedIdx = -1;

    reflectedRedDots.forEach((redDot, redIdx) => {
      const dx = redDot.x - greenDot.x;
      const dy = redDot.y - greenDot.y;
      const distance = Math.sqrt(dx * dx + dy * dy);

      if (distance < minDistance) {
        minDistance = distance;
        closestRedDot = redDot;
        closestRedIdx = redIdx;
      }
    });

    if (closestRedDot) {
      arrowPairs.push({
        from: greenDot,
        to: closestRedDot
      });
      console.log(`    🔗 Verde ${greenIdx} → Rosso ${closestRedIdx} (distanza: ${minDistance.toFixed(1)}px)`);
    }
  });

  // Restituisce il canvas E i dati delle frecce per disegnarle in SVG
  overlayCanvas.arrowPairs = arrowPairs;

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
  const axisNorm = {
    x: axisVector.x / axisLength,
    y: axisVector.y / axisLength
  };

  // Normale perpendicolare all'asse
  const normal = { x: -axisNorm.y, y: axisNorm.x };

  // Vettore dal punto dell'asse al punto da riflettere
  const toPoint = {
    x: point.x - axis.p1.x,
    y: point.y - axis.p1.y
  };

  // Prodotto scalare: distanza dal punto all'asse
  const distance = toPoint.x * normal.x + toPoint.y * normal.y;

  // Rifletti: punto - 2 * distanza * normale
  return {
    x: point.x - 2 * distance * normal.x,
    y: point.y - 2 * distance * normal.y
  };
}

function calculateInclusiveBbox(side, axis) {
  // I green dots dall'API sono GIÀ in coordinate immagine originale
  const greenDots = side === 'left'
    ? window.greenDotsData.groups.Sx.slice(0, 5)
    : window.greenDotsData.groups.Dx.slice(0, 5);

  console.log(`  📏 Bbox basato su ${greenDots.length} punti verdi (già in coordinate immagine)`);

  // Trova min/max
  let minX = Infinity, minY = Infinity;
  let maxX = -Infinity, maxY = -Infinity;

  greenDots.forEach(dot => {
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
  const sideName = side === 'left' ? 'Sinistro' : 'Destro';

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
  title.textContent = `🔍 Correzione Sopracciglio ${sideName}`;
  title.style.cssText = 'margin: 0; color: #333; font-size: 20px;';

  // Legenda
  const legend = document.createElement('div');
  legend.style.cssText = 'display: flex; gap: 20px; font-size: 14px;';
  legend.innerHTML = `
        <span style="color: green;">🟢 Verde: Punti originali del lato selezionato</span>
        <span style="color: red;">🔴 Rosso: Punti riflessi dal lato opposto</span>
        <span style="color: black;">➡️ Frecce: Direzione verso punto riflesso</span>
    `;

  // Container per immagine + frecce animate
  const imageContainer = document.createElement('div');
  imageContainer.style.cssText = 'position: relative; display: inline-block;';

  // Immagine (ingrandita 8x per maggiore visibilità)
  const img = document.createElement('img');
  img.src = croppedCanvas.toDataURL('image/png');
  const scale = 8;
  img.style.cssText = `
        width: ${croppedCanvas.width * scale}px;
        height: ${croppedCanvas.height * scale}px;
        image-rendering: pixelated;
        border: 2px solid #ccc;
        max-width: 95vw;
        max-height: 85vh;
        object-fit: contain;
        display: block;
    `;

  imageContainer.appendChild(img);

  // Aggiungi SVG overlay con frecce animate se ci sono dati
  if (croppedCanvas.arrowPairs && croppedCanvas.arrowPairs.length > 0 && croppedCanvas.bbox) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.style.cssText = `
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 1000;
    `;
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

      // Freccia MOLTO PICCOLA: max 8px o 25% della distanza
      const arrowLength = Math.min(8, distance * 0.25);

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
      line.setAttribute('stroke-width', '0.8');
      line.setAttribute('stroke-linecap', 'round');
      g.appendChild(line);

      // FRECCIA DIREZIONALE MIGLIORATA: triangolo isoscele con punta pronunciata
      const headLength = 3.5;  // Lunghezza dalla punta alla base
      const headWidth = 1.2;   // Larghezza base ridotta per triangolo isoscele stretto
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
      polygon.setAttribute('stroke-width', '0.3');

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
  closeBtn.onclick = () => modal.remove();

  // Assembla tutto
  buttons.appendChild(saveBtn);
  buttons.appendChild(closeBtn);

  content.appendChild(title);
  content.appendChild(legend);
  content.appendChild(imageContainer);
  content.appendChild(buttons);

  modal.appendChild(content);
  document.body.appendChild(modal);

  console.log('✅ Finestra modale aperta');
}

// Export funzioni globali
window.showLeftEyebrow = showLeftEyebrow;
window.showRightEyebrow = showRightEyebrow;

console.log('✅ Eyebrow Correction Module READY');
