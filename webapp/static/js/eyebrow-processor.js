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

    // STEP 3: Accedi DIRETTAMENTE al canvas HTML sottostante di Fabric
    let sourceCanvas;

    if (window.fabricCanvas) {
      console.log('📸 Accesso diretto al canvas HTML di Fabric');

      // SOLUZIONE CORRETTA: Fabric.js ha un elemento canvas HTML sottostante
      // che contiene TUTTO il rendering (background + oggetti)
      const fabricLowerCanvas = window.fabricCanvas.lowerCanvasEl;

      if (fabricLowerCanvas) {
        console.log('✅ Trovato lowerCanvasEl (canvas HTML di rendering)');
        sourceCanvas = fabricLowerCanvas;
      } else {
        // Fallback: prova a ottenerlo dall'elemento wrapper
        const canvasElements = document.querySelectorAll('.canvas-container canvas');
        console.log(`🔍 Trovati ${canvasElements.length} elementi canvas`);

        if (canvasElements.length > 0) {
          sourceCanvas = canvasElements[0]; // Primo canvas è di solito quello di rendering
          console.log('✅ Usando primo canvas trovato nel wrapper');
        } else {
          alert('Impossibile trovare canvas di rendering');
          return;
        }
      }

      // Test pixel DIRETTO dal canvas HTML
      const ctx = sourceCanvas.getContext('2d');
      const testX = Math.floor(sourceCanvas.width / 2);
      const testY = Math.floor(sourceCanvas.height / 2);
      const testPixel = ctx.getImageData(testX, testY, 1, 1);
      console.log(`🔍 Test pixel centro canvas HTML (${testX},${testY}): R=${testPixel.data[0]} G=${testPixel.data[1]} B=${testPixel.data[2]} A=${testPixel.data[3]}`);

    } else {
      console.log('📸 Usando main-canvas diretto');
      sourceCanvas = document.getElementById('main-canvas');
      if (!sourceCanvas) {
        alert("Canvas non trovato");
        return;
      }
    }

    const greenDotsData = window.greenDotsData;
    if (!greenDotsData || !greenDotsData.success) {
      alert("Dati green dots non disponibili");
      return;
    }

    console.log('📍 Green dots con coordinate canvas:', greenDotsData.groups);

    // STEP 4: Calcola bounding box che include TUTTI i punti (verdi + rossi)
    console.log(`\n📐 STEP 4: Calcolo bounding box inclusivo...`);
    const bbox = calculateInclusiveBoundingBox(greenDotsData, axis, side);
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
    const croppedWithPoints = drawPointsOnCroppedImage(croppedImage, greenDotsData, axis, side, bbox);
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
  if (!window.currentLandmarks || window.currentLandmarks.length < 152) {
    console.error('❌ Landmarks insufficienti');
    return null;
  }

  const glabella = window.currentLandmarks[9];  // Centro fronte
  const chin = window.currentLandmarks[151];    // Mento

  if (!glabella || !chin) {
    console.error('❌ Landmarks asse non disponibili');
    return null;
  }

  return {
    p1: { x: glabella.x, y: glabella.y },
    p2: { x: chin.x, y: chin.y }
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
 */
function calculateInclusiveBoundingBox(greenDotsData, axis, side, expandFactor = 0.5) {
  console.log(`🔧 Inizio calcolo bbox per lato ${side}`);

  // Determina punti
  let greenDots, dotsToReflect;
  if (side === 'left') {
    greenDots = greenDotsData.groups.Sx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Dx.slice(0, 5);
  } else {
    greenDots = greenDotsData.groups.Dx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Sx.slice(0, 5);
  }

  console.log(`  📍 Green dots: ${greenDots.length}, Dots to reflect: ${dotsToReflect.length}`);

  // Calcola punti rossi riflessi
  const redDots = dotsToReflect.map(dot => {
    const reflected = reflectPointAcrossAxis({ x: dot.x, y: dot.y }, axis);
    console.log(`    🔄 Rifletto (${dot.x}, ${dot.y}) → (${reflected.x.toFixed(1)}, ${reflected.y.toFixed(1)})`);
    return reflected;
  });

  // Combina TUTTI i punti
  const allPoints = [
    ...greenDots.map(d => ({ x: d.x, y: d.y })),
    ...redDots
  ];

  console.log(`  📊 Calcolo bbox su ${allPoints.length} punti totali`);
  console.log(`  📊 Tutti i punti:`, allPoints);

  // Trova min/max
  let xMin = Infinity, yMin = Infinity, xMax = -Infinity, yMax = -Infinity;
  allPoints.forEach((p, i) => {
    xMin = Math.min(xMin, p.x);
    yMin = Math.min(yMin, p.y);
    xMax = Math.max(xMax, p.x);
    yMax = Math.max(yMax, p.y);
    console.log(`    📌 Punto ${i}: (${p.x.toFixed(1)}, ${p.y.toFixed(1)}) → xMin=${xMin.toFixed(1)}, xMax=${xMax.toFixed(1)}, yMin=${yMin.toFixed(1)}, yMax=${yMax.toFixed(1)}`);
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

  console.log(`  ✅ Bbox finale:`, bbox);
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
 */
function drawPointsOnCroppedImage(croppedCanvas, greenDotsData, axis, side, bbox) {
  // Crea nuovo canvas con stesse dimensioni
  const resultCanvas = document.createElement('canvas');
  resultCanvas.width = croppedCanvas.width;
  resultCanvas.height = croppedCanvas.height;
  const ctx = resultCanvas.getContext('2d');

  // Copia immagine ritagliata
  ctx.drawImage(croppedCanvas, 0, 0);

  // Determina punti
  let greenDots, dotsToReflect;
  if (side === 'left') {
    greenDots = greenDotsData.groups.Sx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Dx.slice(0, 5);
  } else {
    greenDots = greenDotsData.groups.Dx.slice(0, 5);
    dotsToReflect = greenDotsData.groups.Sx.slice(0, 5);
  }

  // Disegna punti VERDI (coordinate relative al bbox)
  ctx.fillStyle = 'rgb(0, 255, 0)';
  greenDots.forEach((dot, i) => {
    const relX = dot.x - bbox.x;
    const relY = dot.y - bbox.y;
    if (relX >= 0 && relX < resultCanvas.width && relY >= 0 && relY < resultCanvas.height) {
      ctx.beginPath();
      ctx.arc(relX, relY, 4, 0, 2 * Math.PI);
      ctx.fill();
      console.log(`    🟢 Punto verde ${i + 1}: canvas(${dot.x},${dot.y}) → ritaglio(${relX.toFixed(1)},${relY.toFixed(1)})`);
    }
  });

  // Disegna punti ROSSI riflessi (coordinate relative al bbox)
  ctx.fillStyle = 'rgb(255, 0, 0)';
  dotsToReflect.forEach((dot, i) => {
    const reflected = reflectPointAcrossAxis({ x: dot.x, y: dot.y }, axis);
    const relX = reflected.x - bbox.x;
    const relY = reflected.y - bbox.y;
    if (relX >= 0 && relX < resultCanvas.width && relY >= 0 && relY < resultCanvas.height) {
      ctx.beginPath();
      ctx.arc(relX, relY, 4, 0, 2 * Math.PI);
      ctx.fill();
      console.log(`    🔴 Punto rosso ${i + 1}: canvas(${dot.x},${dot.y}) → riflesso(${reflected.x.toFixed(1)},${reflected.y.toFixed(1)}) → ritaglio(${relX.toFixed(1)},${relY.toFixed(1)})`);
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

  // Immagine con ingrandimento automatico (minimo 4x)
  const minScale = 4;
  const displayWidth = Math.max(croppedCanvas.width * minScale, 600);
  const displayHeight = Math.max(croppedCanvas.height * minScale, 200);

  const img = document.createElement('img');
  img.src = croppedCanvas.toDataURL();
  img.style.cssText = `
    width: ${displayWidth}px;
    height: ${displayHeight}px;
    image-rendering: pixelated;
    cursor: zoom-in;
  `;

  console.log(`🖼️ Immagine ritagliata: ${croppedCanvas.width}x${croppedCanvas.height}, Display: ${displayWidth}x${displayHeight}`);

  // Zoom al click (toggle tra 4x e 8x)
  let zoomed = false;
  img.onclick = () => {
    zoomed = !zoomed;
    const scale = zoomed ? 8 : 4;
    img.style.width = `${croppedCanvas.width * scale}px`;
    img.style.height = `${croppedCanvas.height * scale}px`;
    img.style.cursor = zoomed ? 'zoom-out' : 'zoom-in';
    console.log(`🔍 Zoom ${zoomed ? 'IN' : 'OUT'}: scala ${scale}x`);
  };

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
