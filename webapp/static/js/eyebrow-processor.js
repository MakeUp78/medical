/**
 * ============================================================================
 * EYEBROW CORRECTION PROCESSOR - WEBAPP VERSION v4.4
 * ============================================================================
 * Ultima modifica: 2025-11-16 23:13:00
 * - Rimossa funzione createFullImageWithOverlay() (codice residuo)
 * - Nuovo flusso: crop PRIMA, poi disegna punti
 * - Diagnostica pre-crop aggiunta
 * 
 * Replica ESATTA del flusso desktop da src/canvas_app.py
 * 
 * FLUSSO COMPLETO:
 * 1. Verifica prerequisiti (green dots + landmarks + measurements)
 * 2. Calcola asse simmetria facciale (glabella→chin)
 * 3. Calcola bounding box che include TUTTI i punti (verdi + rossi riflessi)
 * 4. Ritaglia PRIMA l'immagine originale al bounding box
 * 5. Disegna DOPO i punti sul ritaglio (coordinate relative)
 * 6. Mostra finestra grande con immagine ritagliata + punti
 */

console.log('🔄 EYEBROW PROCESSOR v4.4 CARICATO - 2025-11-16 23:13:00');

// ==================== ENTRY POINTS ====================

/**
 * Gestori pulsanti sopracciglia (chiamati da index.html)
 */
async function showLeftEyebrow() {
  console.log('🔵 === AVVIO CORREZIONE SOPRACCIGLIO SINISTRO ===');
  return await processEyebrowCorrection('left');
}

async function showRightEyebrow() {
  console.log('🔵 === AVVIO CORREZIONE SOPRACCIGLIO DESTRO ===');
  return await processEyebrowCorrection('right');
}

// ==================== MAIN FLOW ====================

/**
 * Flusso principale di correzione sopracciglio
 */
async function processEyebrowCorrection(side) {
  try {
    // STEP 1: Verifica prerequisiti
    if (!checkPrerequisites()) {
      alert(
        "Prerequisiti mancanti!\n\n" +
        "Per usare la correzione sopracciglio è necessario:\n" +
        "1. Rilevare i punti verdi (GREEN DOTS)\n" +
        "2. Avere almeno una misurazione nella tabella\n" +
        "3. Calcolare l'asse di simmetria (pulsante ASSE)"
      );
      return;
    }

    const sideName = side === 'left' ? 'Sinistro' : 'Destro';
    console.log(`\n🚀 STEP 1: Prerequisiti OK per sopracciglio ${sideName}`);

    // STEP 2: Calcola asse di simmetria
    const axis = calculateSymmetryAxis();
    if (!axis) {
      alert("Impossibile calcolare asse di simmetria");
      return;
    }
    console.log(`✅ STEP 2: Asse simmetria calcolato`, axis);

    // STEP 3: Ottieni immagine originale e calcola scala
    console.log(`\n📸 STEP 3: Ottenimento immagine originale...`);

    // Ottieni l'immagine originale dalle dimensioni reali (non ridimensionata dal canvas)
    const imageElement = currentImage.getElement ? currentImage.getElement() : currentImage;
    const originalWidth = imageElement.naturalWidth || imageElement.width;
    const originalHeight = imageElement.naturalHeight || imageElement.height;

    // Crea un canvas con le dimensioni ORIGINALI dell'immagine
    const fullSizeCanvas = document.createElement('canvas');
    fullSizeCanvas.width = originalWidth;
    fullSizeCanvas.height = originalHeight;
    const fullSizeCtx = fullSizeCanvas.getContext('2d');
    fullSizeCtx.drawImage(imageElement, 0, 0, originalWidth, originalHeight);

    // IMPORTANTE: Calcola fattore di scala usando le dimensioni EFFETTIVE dell'immagine processata dal backend
    // greenDotsData.image_size contiene [width, height] dell'immagine che il backend ha ricevuto
    // Questo gestisce automaticamente qualsiasi ridimensionamento applicato dal frontend

    const fabricScaleX = currentImage.scaleX || 1;
    const fabricScaleY = currentImage.scaleY || 1;

    // Dimensioni dell'immagine che il backend ha processato (dalla risposta API)
    const backendImageWidth = greenDotsData.image_size[0];
    const backendImageHeight = greenDotsData.image_size[1];

    // Le coordinate green dots sono relative a backendImageWidth x backendImageHeight
    // Dobbiamo scalare DALLE coordinate backend ALLE dimensioni originali dell'immagine
    const scaleX = originalWidth / backendImageWidth;
    const scaleY = originalHeight / backendImageHeight;

    console.log(`📐 Dimensioni immagine originale: ${originalWidth}x${originalHeight}`);
    console.log(`📐 Dimensioni immagine processata dal backend: ${backendImageWidth}x${backendImageHeight}`);
    console.log(`📐 Scala Fabric.js applicata: scaleX=${fabricScaleX.toFixed(3)}, scaleY=${fabricScaleY.toFixed(3)}`);
    console.log(`📐 Fattore scala (backend→original): X=${scaleX.toFixed(3)}, Y=${scaleY.toFixed(3)}`);

    const sourceCanvas = fullSizeCanvas;

    const greenDotsData = window.greenDotsData;
    if (!greenDotsData || !greenDotsData.success) {
      alert("Dati green dots non disponibili");
      return;
    }

    console.log('📍 Green dots data completo:', greenDotsData);
    console.log('📍 Image size dal backend:', greenDotsData.image_size);
    console.log('📍 Green dots groups:', greenDotsData.groups);
    console.log('📍 window.greenDotsImageScale:', window.greenDotsImageScale);
    console.log('📍 window.lastImageResizeScale:', window.lastImageResizeScale);

    // STEP 4: Calcola bounding box che include TUTTI i punti (verdi + rossi)
    console.log(`\n📐 STEP 4: Calcolo bounding box inclusivo...`);
    const bbox = calculateInclusiveBoundingBox(greenDotsData, axis, side, scaleX, scaleY, fabricScaleX, fabricScaleY);
    if (!bbox || bbox.width === 0 || bbox.height === 0) {
      alert(`Bounding box non valido per sopracciglio ${sideName}`);
      console.error('❌ Bbox invalido:', bbox);
      return;
    }
    console.log(`✅ Bounding box calcolato:`, bbox);

    // DIAGNOSTICA: Verifica sourceCanvas PRIMA del crop
    console.log(`\n🔍 DIAGNOSTICA PRE-CROP:`);
    console.log(`  Source canvas: ${sourceCanvas.width}x${sourceCanvas.height}`);

    // Test pixel al centro del bbox per vedere cosa c'è
    const testCtx = sourceCanvas.getContext('2d');
    const testX = Math.floor(bbox.x + bbox.width / 2);
    const testY = Math.floor(bbox.y + bbox.height / 2);
    const testPixel = testCtx.getImageData(testX, testY, 1, 1);
    console.log(`  Pixel al centro bbox (${testX},${testY}): R=${testPixel.data[0]} G=${testPixel.data[1]} B=${testPixel.data[2]} A=${testPixel.data[3]}`);

    // Test pixel agli angoli del bbox
    const topLeftPixel = testCtx.getImageData(bbox.x, bbox.y, 1, 1);
    console.log(`  Pixel top-left bbox (${bbox.x},${bbox.y}): R=${topLeftPixel.data[0]} G=${topLeftPixel.data[1]} B=${topLeftPixel.data[2]} A=${topLeftPixel.data[3]}`);

    // STEP 5: Ritaglia l'immagine ORIGINALE (sourceCanvas) al bounding box
    console.log(`\n✂️ STEP 5: Ritaglio immagine ORIGINALE al bounding box...`);
    const croppedImage = cropCanvasToBbox(sourceCanvas, bbox);
    console.log(`✅ Ritaglio base completato: ${croppedImage.width}x${croppedImage.height}`);

    // STEP 6: Disegna i punti verdi e rossi SUL ritaglio
    console.log(`\n🎨 STEP 6: Disegno punti sul ritaglio...`);
    const croppedWithPoints = drawPointsOnCroppedImage(croppedImage, greenDotsData, axis, side, bbox, scaleX, scaleY, fabricScaleX, fabricScaleY);
    console.log(`✅ Punti disegnati sul ritaglio`);

    // STEP 7: Mostra finestra con risultato
    console.log(`\n🖼️ STEP 7: Apertura finestra risultato...`);
    showEyebrowCorrectionWindow(croppedWithPoints, side);
    console.log(`✅ === CORREZIONE COMPLETATA ===\n`);

  } catch (error) {
    console.error('❌ ERRORE nel processo di correzione:', error);
    alert(`Errore nella correzione sopracciglio:\n${error.message}`);
  }
}

// ==================== STEP 1: PREREQUISITI ====================

/**
 * Verifica che tutti i prerequisiti siano soddisfatti
 */
function checkPrerequisites() {
  // Verifica green dots
  const hasGreenDots = (
    window.greenDotsDetected &&
    window.greenDotsData &&
    window.greenDotsData.success &&
    (window.greenDotsData.groups.Sx.length > 0 || window.greenDotsData.groups.Dx.length > 0)
  );

  // Verifica measurements
  const measurementsTable = document.getElementById('measurements-table');
  const hasMeasurements = measurementsTable && measurementsTable.rows.length > 1;

  // Verifica landmarks (necessari per asse simmetria)
  const hasLandmarks = window.currentLandmarks && window.currentLandmarks.length > 0;

  console.log('📋 Verifica prerequisiti:', {
    hasGreenDots,
    hasMeasurements,
    hasLandmarks
  });

  return hasGreenDots && hasMeasurements && hasLandmarks;
}

// ==================== STEP 2: ASSE SIMMETRIA ====================

/**
 * Calcola asse di simmetria facciale (glabella→chin)
 * Usa landmarks MediaPipe: 9 (glabella) e 151 (chin)
 */
function calculateSymmetryAxis() {
  if (!window.currentLandmarks || window.currentLandmarks.length < 165) {
    console.error('❌ Landmarks insufficienti (richiesti almeno 165)');
    return null;
  }

  // MediaPipe landmarks: 9 = glabella (centro fronte), 164 = philtrum (area naso-labbro)
  // IMPORTANTE: Stessi landmarks usati in main.js drawSymmetryAxis() per coerenza
  const glabella = window.currentLandmarks[9];   // Centro fronte
  const philtrum = window.currentLandmarks[164]; // Philtrum (naso-labbro)

  if (!glabella || !philtrum) {
    console.error('❌ Landmarks asse non disponibili (9 o 164)');
    return null;
  }

  console.log('✅ Asse simmetria calcolato con landmarks 9 (glabella) e 164 (philtrum)');
  return {
    p1: { x: glabella.x, y: glabella.y },
    p2: { x: philtrum.x, y: philtrum.y }
  };
}

// ==================== STEP 3: RIFLESSIONE PUNTO ====================

/**
 * Riflette un punto rispetto all'asse di simmetria
 * Formula geometrica: P' = P + 2 * ((A-P)·n) * n
 * dove n è la normale all'asse
 */
function reflectPointAcrossAxis(point, axis) {
  // Vettore direzione asse
  const dx = axis.p2.x - axis.p1.x;
  const dy = axis.p2.y - axis.p1.y;
  const len = Math.sqrt(dx * dx + dy * dy);

  // Normale all'asse (perpendicolare)
  const nx = -dy / len;
  const ny = dx / len;

  // Vettore dal punto p1 dell'asse al punto da riflettere
  const px = point.x - axis.p1.x;
  const py = point.y - axis.p1.y;

  // Prodotto scalare (proiezione sulla normale)
  const dot = px * nx + py * ny;

  // Punto riflesso
  return {
    x: point.x - 2 * dot * nx,
    y: point.y - 2 * dot * ny
  };
}

// ==================== STEP 4: BOUNDING BOX INCLUSIVO ====================

/**
 * Calcola bounding box che include TUTTI i punti (verdi + rossi riflessi)
 * Scala le coordinate dal canvas display alle dimensioni originali dell'immagine
 */
function calculateInclusiveBoundingBox(greenDotsData, axis, side, scaleX, scaleY, fabricScaleX, fabricScaleY, expandFactor = 0.5) {
  console.log(`🔧 Inizio calcolo bbox per lato ${side}`);
  console.log(`🔧 scaleX/Y (backend→original): ${scaleX.toFixed(3)} / ${scaleY.toFixed(3)}`);
  console.log(`🔧 fabricScaleX/Y (display→original): ${fabricScaleX.toFixed(3)} / ${fabricScaleY.toFixed(3)}`);

  // Determina punti (già in coordinate backend dall'API)
  let greenDots, dotsToReflect;
  if (side === 'left') {
    greenDots = greenDotsData.groups.Sx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Dx.slice(0, 5);
  } else {
    greenDots = greenDotsData.groups.Dx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Sx.slice(0, 5);
  }

  console.log(`  📍 Green dots (coordinate backend):`, greenDots);
  console.log(`  📍 Dots to reflect (coordinate backend):`, dotsToReflect);

  // IMPORTANTE: L'asse viene dai landmarks che sono in coordinate CANVAS DISPLAY
  // I green dots sono in coordinate BACKEND (ridimensionate)
  // Dobbiamo portare l'asse dalle coordinate display alle coordinate backend!

  // Scala dalle coordinate display fabric alle coordinate backend
  // fabricScale è la scala applicata per visualizzare (es. 0.264 per 3024→800)
  // Ma i green dots sono in coordinate backend ridimensionate (es. 1600px)
  // Quindi: display * (1/fabricScale) = original, poi original * (backend/original) = backend

  // Calcola il fattore per portare dalle coordinate display alle coordinate backend
  const displayToBackendX = 1 / (fabricScaleX * scaleX);
  const displayToBackendY = 1 / (fabricScaleY * scaleY);

  console.log(`  📐 Fattore display→backend: X=${displayToBackendX.toFixed(3)}, Y=${displayToBackendY.toFixed(3)}`);

  const backendAxis = {
    p1: { x: axis.p1.x * displayToBackendX, y: axis.p1.y * displayToBackendY },
    p2: { x: axis.p2.x * displayToBackendX, y: axis.p2.y * displayToBackendY }
  };

  console.log(`  📏 Asse originale (display):`, axis);
  console.log(`  📏 Asse convertito (backend):`, backendAxis);

  // Calcola punti rossi riflessi (tutti in coordinate backend)
  const redDots = dotsToReflect.map((dot, idx) => {
    const reflected = reflectPointAcrossAxis(dot, backendAxis);
    console.log(`    🔄 Rifletto punto ${idx}: (${dot.x}, ${dot.y}) → (${reflected.x.toFixed(1)}, ${reflected.y.toFixed(1)})`);
    return reflected;
  });

  // Scala TUTTI i punti (backend → original) per il crop finale
  const allPointsOriginal = [
    ...greenDots.map(d => ({ x: d.x * scaleX, y: d.y * scaleY })),
    ...redDots.map(d => ({ x: d.x * scaleX, y: d.y * scaleY }))
  ];

  console.log(`  📊 Calcolo bbox su ${allPointsOriginal.length} punti totali (coordinate originali)`);

  // Trova min/max
  let xMin = Infinity, yMin = Infinity, xMax = -Infinity, yMax = -Infinity;
  allPointsOriginal.forEach((p, i) => {
    xMin = Math.min(xMin, p.x);
    yMin = Math.min(yMin, p.y);
    xMax = Math.max(xMax, p.x);
    yMax = Math.max(yMax, p.y);
  });

  console.log(`  📏 Range: X[${xMin.toFixed(1)} - ${xMax.toFixed(1)}], Y[${yMin.toFixed(1)} - ${yMax.toFixed(1)}]`);

  // Espandi bbox
  const width = xMax - xMin;
  const height = yMax - yMin;
  const expandW = width * expandFactor;
  const expandH = height * expandFactor;

  const bbox = {
    x: Math.max(0, Math.floor(xMin - expandW)),
    y: Math.max(0, Math.floor(yMin - expandH)),
    width: Math.ceil(width + 2 * expandW),
    height: Math.ceil(height + 2 * expandH)
  };

  console.log(`  ✅ Bbox finale (dimensioni originali):`, bbox);
  console.log(`  ✅ Bbox rispetto a sourceCanvas (${width}x${height}): X[${bbox.x} - ${bbox.x + bbox.width}], Y[${bbox.y} - ${bbox.y + bbox.height}]`);

  return bbox;
}

// ==================== STEP 6: RITAGLIO ====================

/**
 * Ritaglia canvas al bounding box
 */
function cropCanvasToBbox(sourceCanvas, bbox) {
  console.log(`✂️ CROP - Source: ${sourceCanvas.width}x${sourceCanvas.height}, Bbox:`, bbox);

  const croppedCanvas = document.createElement('canvas');
  croppedCanvas.width = bbox.width;
  croppedCanvas.height = bbox.height;
  const ctx = croppedCanvas.getContext('2d');

  // Copia la porzione dell'immagine SENZA riempimento magenta
  ctx.drawImage(
    sourceCanvas,
    bbox.x, bbox.y, bbox.width, bbox.height,  // source rect
    0, 0, bbox.width, bbox.height              // dest rect
  );

  // Test pixel per verificare cosa è stato copiato
  const testPixel = ctx.getImageData(Math.floor(bbox.width / 2), Math.floor(bbox.height / 2), 1, 1);
  console.log(`✂️ CROP - Pixel centrale ritaglio: R=${testPixel.data[0]} G=${testPixel.data[1]} B=${testPixel.data[2]} A=${testPixel.data[3]}`);

  return croppedCanvas;
}

// ==================== STEP 7: DISEGNA PUNTI SU RITAGLIO ====================

/**
 * Disegna punti verdi e rossi sull'immagine ritagliata
 * Con coordinate scalate alle dimensioni originali
 */
function drawPointsOnCroppedImage(croppedCanvas, greenDotsData, axis, side, bbox, scaleX, scaleY, fabricScaleX, fabricScaleY) {
  // Crea nuovo canvas con stesse dimensioni
  const resultCanvas = document.createElement('canvas');
  resultCanvas.width = croppedCanvas.width;
  resultCanvas.height = croppedCanvas.height;
  const ctx = resultCanvas.getContext('2d');

  // Copia immagine ritagliata
  ctx.drawImage(croppedCanvas, 0, 0);

  // Determina punti (già in coordinate backend)
  let greenDots, dotsToReflect;
  if (side === 'left') {
    greenDots = greenDotsData.groups.Sx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Dx.slice(0, 5);
  } else {
    greenDots = greenDotsData.groups.Dx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Sx.slice(0, 5);
  }

  console.log(`🎨 Disegno ${greenDots.length} punti verdi e ${dotsToReflect.length} punti rossi riflessi`);

  // Converti asse da coordinate display a coordinate backend
  const displayToBackendX = 1 / (fabricScaleX * scaleX);
  const displayToBackendY = 1 / (fabricScaleY * scaleY);

  const backendAxis = {
    p1: { x: axis.p1.x * displayToBackendX, y: axis.p1.y * displayToBackendY },
    p2: { x: axis.p2.x * displayToBackendX, y: axis.p2.y * displayToBackendY }
  };

  // 1. Disegna punti VERDI (backend → originali → relativi al ritaglio)
  ctx.fillStyle = 'green';
  greenDots.forEach((dot, i) => {
    // Scala coordinate backend alle dimensioni originali
    const originalX = dot.x * scaleX;
    const originalY = dot.y * scaleY;

    // Converti in coordinate relative al ritaglio
    const relX = originalX - bbox.x;
    const relY = originalY - bbox.y;

    ctx.beginPath();
    ctx.arc(relX, relY, 8, 0, 2 * Math.PI);
    ctx.fill();
    console.log(`    🟢 Punto verde ${i + 1}: backend(${dot.x},${dot.y}) → originale(${originalX.toFixed(1)},${originalY.toFixed(1)}) → ritaglio(${relX.toFixed(1)},${relY.toFixed(1)})`);
  });

  // 2. Calcola punti ROSSI riflessi (tutti in coordinate backend)
  const redDots = dotsToReflect.map(dot => reflectPointAcrossAxis(dot, backendAxis));

  // 3. Abbinamento verde-rosso basato su distanza minima (in coordinate backend)
  const pairs = [];
  const usedRed = new Set();

  greenDots.forEach((greenDot, greenIdx) => {
    let minDist = Infinity;
    let closestRedIdx = -1;
    let closestReflected = null;

    redDots.forEach((redDot, redIdx) => {
      if (usedRed.has(redIdx)) return;

      const dx = greenDot.x - redDot.x;
      const dy = greenDot.y - redDot.y;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < minDist) {
        minDist = dist;
        closestRedIdx = redIdx;
        closestReflected = redDot;
      }
    });

    if (closestRedIdx !== -1) {
      pairs.push({
        greenIdx,
        redIdx: closestRedIdx,
        distance: minDist,
        reflected: closestReflected
      });
      usedRed.add(closestRedIdx);
    }
  });

  // 4. Disegna frecce da verde a rosso
  ctx.strokeStyle = 'red';
  ctx.lineWidth = 3;

  pairs.forEach(({ greenIdx, redIdx, distance, reflected }) => {
    const greenDot = greenDots[greenIdx];

    // Coordinate verdi in ritaglio (backend → originale → ritaglio)
    const greenOriginalX = greenDot.x * scaleX;
    const greenOriginalY = greenDot.y * scaleY;
    const greenRelX = greenOriginalX - bbox.x;
    const greenRelY = greenOriginalY - bbox.y;

    // Coordinate rosse riflesse in ritaglio (backend → originale → ritaglio)
    const redOriginalX = reflected.x * scaleX;
    const redOriginalY = reflected.y * scaleY;
    const redRelX = redOriginalX - bbox.x;
    const redRelY = redOriginalY - bbox.y;

    // Disegna punto rosso SOLO se dentro il bbox con margine
    const margin = 20;
    if (redRelX >= -margin && redRelX <= croppedCanvas.width + margin &&
      redRelY >= -margin && redRelY <= croppedCanvas.height + margin) {
      ctx.beginPath();
      ctx.arc(redRelX, redRelY, 8, 0, 2 * Math.PI);
      ctx.fill();
      console.log(`    🔴 Punto rosso ${greenIdx + 1}: ritaglio(${redRelX.toFixed(1)},${redRelY.toFixed(1)})`);
    } else {
      console.log(`    ⚠️ Punto rosso ${greenIdx + 1} FUORI bbox: (${redRelX.toFixed(1)},${redRelY.toFixed(1)}), bbox: 0-${croppedCanvas.width}, 0-${croppedCanvas.height}`);
    }

    // Disegna freccia SEMPRE (indica direzione anche se punto è fuori)
    const dx = redRelX - greenRelX;
    const dy = redRelY - greenRelY;
    const len = Math.sqrt(dx * dx + dy * dy);

    if (len > 5) {
      // Freccia limitata a 60px max per restare nel bbox
      const maxArrowLen = Math.min(60, len * 0.3);
      const dirX = dx / len;
      const dirY = dy / len;

      const endX = greenRelX + dirX * maxArrowLen;
      const endY = greenRelY + dirY * maxArrowLen;

      // Disegna linea
      ctx.beginPath();
      ctx.moveTo(greenRelX, greenRelY);
      ctx.lineTo(endX, endY);
      ctx.stroke();

      // Punta freccia
      const arrowHeadLen = 10;
      const angle = Math.atan2(dy, dx);

      ctx.fillStyle = 'red';
      ctx.beginPath();
      ctx.moveTo(endX, endY);
      ctx.lineTo(endX - arrowHeadLen * Math.cos(angle - Math.PI / 6), endY - arrowHeadLen * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(endX - arrowHeadLen * Math.cos(angle + Math.PI / 6), endY - arrowHeadLen * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fill();

      console.log(`    ➡️ Freccia ${greenIdx + 1}: lunghezza ${maxArrowLen.toFixed(1)}px, direzione (${dirX.toFixed(2)},${dirY.toFixed(2)})`);
    }
  });

  return resultCanvas;
}

// ==================== STEP 8: FINESTRA RISULTATO ====================

/**
 * Mostra finestra modale con risultato
 */
function showEyebrowCorrectionWindow(croppedCanvas, side) {
  const sideName = side === 'left' ? 'Sinistro' : 'Destro';

  // Crea modal
  const modal = document.createElement('div');
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.9);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10000;
  `;

  const content = document.createElement('div');
  content.style.cssText = `
    background: white;
    padding: 30px;
    border-radius: 12px;
    width: 1400px;
    height: 1000px;
    max-width: 98vw;
    max-height: 98vh;
    display: flex;
    flex-direction: column;
  `;

  // Titolo
  const title = document.createElement('h2');
  title.textContent = `🔍 Correzione Sopracciglio ${sideName}`;
  title.style.cssText = 'margin: 0 0 15px 0; text-align: center; font-size: 24px;';
  content.appendChild(title);

  // Legenda
  const legend = document.createElement('div');
  legend.innerHTML = `
    <p style="margin: 10px 0; font-size: 14px;">
      <span style="color: green; font-weight: bold;">🟢 Verde:</span> Punti originali del lato selezionato<br>
      <span style="color: red; font-weight: bold;">🔴 Rosso:</span> Punti riflessi dal lato opposto
    </p>
  `;
  content.appendChild(legend);

  // Container immagine - con dimensioni fisse grandi
  const imgContainer = document.createElement('div');
  imgContainer.style.cssText = `
    flex: 1;
    overflow: auto;
    text-align: center;
    background: #2a2a2a;
    padding: 50px;
    border-radius: 8px;
    margin: 15px 0;
    display: flex;
    justify-content: center;
    align-items: center;
  `;

  // Calcola dimensioni ottimali per il display
  // Se il ritaglio è piccolo (< 400px), ingrandiscilo
  // Se il ritaglio è grande (> 1200px), riducilo
  // Altrimenti mantieni dimensioni originali
  const maxDisplaySize = 1200;
  const minDisplaySize = 400;

  let displayWidth = croppedCanvas.width;
  let displayHeight = croppedCanvas.height;
  let scale = 1;

  const maxDim = Math.max(croppedCanvas.width, croppedCanvas.height);

  if (maxDim > maxDisplaySize) {
    // Riduci se troppo grande
    scale = maxDisplaySize / maxDim;
    displayWidth = Math.round(croppedCanvas.width * scale);
    displayHeight = Math.round(croppedCanvas.height * scale);
    console.log(`📉 Riduzione ritaglio grande: ${croppedCanvas.width}x${croppedCanvas.height} → ${displayWidth}x${displayHeight} (scala ${scale.toFixed(2)}x)`);
  } else if (maxDim < minDisplaySize) {
    // Ingrandisci se troppo piccolo
    scale = minDisplaySize / maxDim;
    displayWidth = Math.round(croppedCanvas.width * scale);
    displayHeight = Math.round(croppedCanvas.height * scale);
    console.log(`📈 Ingrandimento ritaglio piccolo: ${croppedCanvas.width}x${croppedCanvas.height} → ${displayWidth}x${displayHeight} (scala ${scale.toFixed(2)}x)`);
  } else {
    console.log(`✅ Dimensioni ottimali: ${displayWidth}x${displayHeight} (nessuna scala)`);
  }

  const img = document.createElement('img');
  img.src = croppedCanvas.toDataURL();
  img.style.cssText = `
    max-width: 100%;
    max-height: 100%;
    width: ${displayWidth}px;
    height: ${displayHeight}px;
    image-rendering: ${scale < 1 ? 'auto' : 'pixelated'};
    cursor: ${scale < 1 ? 'default' : 'zoom-in'};
    object-fit: contain;
  `;

  console.log(`🖼️ Display finale: ${displayWidth}x${displayHeight}`);

  // Zoom al click solo per immagini piccole ingrandite
  if (scale > 1) {
    let zoomed = false;
    img.onclick = () => {
      zoomed = !zoomed;
      const newScale = zoomed ? scale * 2 : scale;
      img.style.width = `${Math.round(croppedCanvas.width * newScale)}px`;
      img.style.height = `${Math.round(croppedCanvas.height * newScale)}px`;
      img.style.cursor = zoomed ? 'zoom-out' : 'zoom-in';
      console.log(`🔍 Zoom ${zoomed ? 'IN' : 'OUT'}: scala ${newScale.toFixed(2)}x`);
    };
  }

  imgContainer.appendChild(img);
  content.appendChild(imgContainer);

  // Pulsanti
  const buttonsDiv = document.createElement('div');
  buttonsDiv.style.cssText = 'text-align: center; margin-top: 20px;';

  const saveBtn = document.createElement('button');
  saveBtn.textContent = '💾 Salva Immagine';
  saveBtn.className = 'btn btn-primary';
  saveBtn.style.cssText = 'margin-right: 10px; padding: 10px 20px; font-size: 16px;';
  saveBtn.onclick = () => {
    const link = document.createElement('a');
    link.download = `sopracciglio_${side}_${Date.now()}.png`;
    link.href = croppedCanvas.toDataURL('image/png');
    link.click();
  };

  const closeBtn = document.createElement('button');
  closeBtn.textContent = '❌ Chiudi';
  closeBtn.className = 'btn btn-secondary';
  closeBtn.style.cssText = 'padding: 10px 20px; font-size: 16px;';
  closeBtn.onclick = () => document.body.removeChild(modal);

  buttonsDiv.appendChild(saveBtn);
  buttonsDiv.appendChild(closeBtn);
  content.appendChild(buttonsDiv);

  modal.appendChild(content);
  document.body.appendChild(modal);

  console.log('✅ Finestra correzione aperta');
}

// ==================== ESPORTAZIONI GLOBALI ====================

window.showLeftEyebrow = showLeftEyebrow;
window.showRightEyebrow = showRightEyebrow;

console.log('✅ Eyebrow Processor caricato (versione COMPLETA desktop-replica)');
