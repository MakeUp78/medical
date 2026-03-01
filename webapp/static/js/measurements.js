/*
 * Sistema di misurazione webapp - Versione Semplificata
 * Auto-rilevamento landmarks + Calcoli immediati
 */

function calculateDistanceBetweenPoints(point1, point2) {
  if (!point1 || !point2) return 0;
  if (typeof point1.x === 'undefined' || typeof point2.x === 'undefined') return 0;
  if (typeof point1.y === 'undefined' || typeof point2.y === 'undefined') return 0;

  const dx = point2.x - point1.x;
  const dy = point2.y - point1.y;
  return Math.sqrt(dx * dx + dy * dy);
}

// Configurazione globale misurazioni
const MEASUREMENT_CONFIG = {
  precision: 1,
  defaultUnit: 'px',
  colors: ['#FF6B35', '#F7931E', '#FFD23F', '#06FFA5', '#118AB2', '#073B4C']
};

// Variabili globali misurazioni
let measurementLines = [];
let measurementHistory = [];
let measurementColorIndex = 0;
let currentMeasurementType = null;
let measurementPoints = [];

// Sistema toggle per misurazioni predefinite
let activeMeasurements = new Map(); // Traccia quali misurazioni sono attive
let measurementOverlays = new Map(); // Traccia gli overlay delle misurazioni
window._eyebrowSymmetryCache = null; // Cache ultimo overlay sopracciglia {b64, natW, natH}

// === DEBUG MODE PER ELABORAZIONE SOPRACCIGLIA ===
let eyebrowDebugMode = true; // Attiva/disattiva visualizzazioni debug
let eyebrowDebugObjects = []; // Array per memorizzare oggetti di debug
let labelBoundingBoxes = []; // Array globale per tracciare tutte le bounding box delle etichette

// Controlli visibilità overlay debug (separati per tipo)
let debugVisibility = {
  landmarkPolygons: true,  // Poligoni perimetri landmarks (arancione/magenta)
  scaledMasks: true,       // Maschere espanse (verde/ciano)
  binaryPixels: true,      // Pixel binari (rosso)
  measurementOutput: true  // Overlay risultati misurazione (etichette aree)
};

// Esponi le variabili globalmente per l'accesso da altri moduli
window.activeMeasurements = activeMeasurements;
window.measurementOverlays = measurementOverlays;
window.debugVisibility = debugVisibility;
window.eyebrowDebugMode = eyebrowDebugMode;
window.toggleEyebrowDebug = function () {
  eyebrowDebugMode = !eyebrowDebugMode;
  console.log(`🐛 Debug Mode Sopracciglia: ${eyebrowDebugMode ? 'ATTIVO' : 'DISATTIVO'}`);
  return eyebrowDebugMode;
};

// === FUNZIONI DI UTILITÀ PER OVERLAY ===

function createMeasurementLine(point1, point2, label, color = '#FF6B35') {
  /**
   * Crea un oggetto linea di misurazione senza aggiungerlo al canvas
   * @returns {fabric.Line} L'oggetto linea da aggiungere agli overlay
   */
  if (!fabricCanvas || !point1 || !point2) {
    console.error('❌ Parametri mancanti per createMeasurementLine');
    return null;
  }

  // Trasforma le coordinate se la funzione è disponibile
  let transformedPoint1, transformedPoint2;

  if (window.transformLandmarkCoordinate && typeof window.transformLandmarkCoordinate === 'function') {
    transformedPoint1 = window.transformLandmarkCoordinate(point1);
    transformedPoint2 = window.transformLandmarkCoordinate(point2);
  } else {
    // Fallback: usa le coordinate dirette
    transformedPoint1 = point1;
    transformedPoint2 = point2;
  }

  // Crea la linea
  const line = new fabric.Line([
    transformedPoint1.x, transformedPoint1.y,
    transformedPoint2.x, transformedPoint2.y
  ], {
    stroke: color,
    strokeWidth: 2,
    selectable: false,
    evented: false,
    isMeasurementLine: true,
    measurementType: label
  });

  // Aggiungi al canvas per questa misurazione
  fabricCanvas.add(line);
  fabricCanvas.bringToFront(line);

  return line;
}

function createAreaPolygon(points, label, color = '#FF6B35') {
  /**
   * Crea un poligono per visualizzare un'area
   * @param {Array} points - Array di punti landmark
   * @param {string} label - Label dell'area
   * @param {string} color - Colore del poligono
   * @returns {fabric.Polygon} Il poligono creato
   */
  if (!fabricCanvas || !points || points.length < 3) {
    console.error('❌ Parametri mancanti o insufficienti per createAreaPolygon');
    return null;
  }

  // Trasforma tutte le coordinate
  const transformedPoints = points.map(point => {
    if (window.transformLandmarkCoordinate && typeof window.transformLandmarkCoordinate === 'function') {
      return window.transformLandmarkCoordinate(point);
    }
    return point;
  });

  // Converti in formato Fabric.js
  const fabricPoints = transformedPoints.map(p => ({ x: p.x, y: p.y }));

  // Crea il poligono
  const polygon = new fabric.Polygon(fabricPoints, {
    fill: color + '40', // Trasparenza del 25%
    stroke: color,
    strokeWidth: 1,
    selectable: false,
    evented: false,
    isAreaPolygon: true,
    measurementType: label
  });

  // Aggiungi al canvas
  fabricCanvas.add(polygon);
  fabricCanvas.bringToFront(polygon);

  return polygon;
}

function createAreaPolygonDirect(transformedPoints, label, color = '#FF6B35') {
  /**
   * Crea un poligono per visualizzare un'area usando punti GIÀ TRASFORMATI
   * @param {Array} transformedPoints - Array di punti già in coordinate canvas
   * @param {string} label - Label dell'area
   * @param {string} color - Colore del poligono
   * @returns {fabric.Polygon} Il poligono creato
   */
  if (!fabricCanvas || !transformedPoints || transformedPoints.length < 3) {
    console.error('❌ Parametri mancanti o insufficienti per createAreaPolygonDirect');
    return null;
  }

  // I punti sono già trasformati, converti solo in formato Fabric.js
  const fabricPoints = transformedPoints.map(p => ({ x: p.x, y: p.y }));

  // Crea il poligono
  const polygon = new fabric.Polygon(fabricPoints, {
    fill: color + '40', // Trasparenza del 25%
    stroke: color,
    strokeWidth: 2,
    selectable: false,
    evented: false,
    isAreaPolygon: true,
    measurementType: label
  });

  // Aggiungi al canvas
  fabricCanvas.add(polygon);
  fabricCanvas.bringToFront(polygon);

  return polygon;
}

function removeMeasurementFromTable(measurementType) {
  /**
   * Rimuove una misurazione specifica dalla tabella
   */
  const table = document.getElementById('measurements-table');
  if (!table) return;

  const rows = table.querySelectorAll('tbody tr');
  rows.forEach(row => {
    const typeCell = row.cells[0];
    if (typeCell && typeCell.dataset.measurementType === measurementType) {
      row.remove();
    }
  });
}

// === FUNZIONI TOGGLE MISURAZIONI ===

function toggleMeasurementButton(buttonElement, measurementType) {
  /**
   * Gestisce il toggle di un pulsante di misurazione
   * @param {HTMLElement} buttonElement - Il pulsante cliccato
   * @param {string} measurementType - Il tipo di misurazione
   */
  console.log('🔄 toggleMeasurementButton chiamata:', { buttonElement, measurementType });

  if (!buttonElement) {
    console.error('❌ Elemento pulsante non trovato!');
    return;
  }

  const isActive = buttonElement.classList.contains('btn-active');
  console.log('🔍 Stato pulsante:', { isActive, classList: buttonElement.classList.toString() });

  if (isActive) {
    // Disattiva: rimuovi classe e overlay
    buttonElement.classList.remove('btn-active');
    hideMeasurementOverlay(measurementType);
    activeMeasurements.delete(measurementType);
    console.log(`❌ Disattivata misurazione: ${measurementType}`);
  } else {
    // Attiva: aggiungi classe e mostra overlay
    buttonElement.classList.add('btn-active');
    showMeasurementOverlay(measurementType);
    activeMeasurements.set(measurementType, true);
    console.log(`✅ Attivata misurazione: ${measurementType}`);
  }
}

function showMeasurementOverlay(measurementType, silent = false) {
  /**
   * Mostra l'overlay di una misurazione specifica
   */
  switch (measurementType) {
    case 'faceWidth':
      performFaceWidthMeasurement();
      break;
    case 'faceHeight':
      performFaceHeightMeasurement();
      break;
    case 'eyeDistance':
      performEyeDistanceMeasurement();
      break;
    case 'noseWidth':
      performNoseWidthMeasurement();
      break;
    case 'noseHeight':
      performNoseHeightMeasurement();
      break;
    case 'mouthWidth':
      performMouthWidthMeasurement();
      break;
    // case 'eyebrowAreas': // DISABILITATO - Aree Sopracciglia nascosto
    //   performEyebrowAreasMeasurement(silent);
    //   break;
    case 'eyeAreas':
      performEyeAreasMeasurement();
      break;
    case 'cheekWidth':
      performCheekWidthMeasurement();
      break;
    case 'foreheadWidth':
      performForeheadWidthMeasurement();
      break;
    case 'chinWidth':
      performChinWidthMeasurement();
      break;
    case 'faceProfile':
      performFaceProfileMeasurement();
      break;
    case 'noseAngle':
      performNoseAngleMeasurement();
      break;
    case 'mouthAngle':
      performMouthAngleMeasurement();
      break;
    case 'faceProportions':
      performFaceProportionsMeasurement();
      break;
    case 'keyDistances':
      performKeyDistancesMeasurement();
      break;
    case 'facialSymmetry':
      performFacialSymmetryMeasurement();
      break;
    case 'eyebrowSymmetry':
      _repositionEyebrowSymmetryOverlay();
      break;
    case 'eyeRotation':
      performEyeRotationMeasurement();
      break;
    default:
      console.warn(`Tipo misurazione non riconosciuto: ${measurementType}`);
  }
}

function hideMeasurementOverlay(measurementType) {
  /**
   * Nasconde l'overlay di una misurazione specifica
   */
  if (measurementOverlays.has(measurementType)) {
    const overlayObjects = measurementOverlays.get(measurementType);
    overlayObjects.forEach(obj => {
      if (fabricCanvas) {
        fabricCanvas.remove(obj);
      }
    });
    measurementOverlays.delete(measurementType);

    // Rimuovi dalla tabella se presente
    removeMeasurementFromTable(measurementType);

    if (fabricCanvas) {
      fabricCanvas.renderAll();
    }
  }

  // Pulizia specifica per eyeRotation
  if (measurementType === 'eyeRotation') {
    window.eyeRotationOverlayActive = false;
    window._eyeRotationCachedAngles = null;
    // Fallback: rimuovi per tag qualsiasi oggetto residuo
    if (fabricCanvas) {
      fabricCanvas.getObjects()
        .filter(o => o.isEyeRotationOverlay)
        .forEach(o => fabricCanvas.remove(o));
      fabricCanvas.renderAll();
    }
    // Rimuovi righe tabella eye-rotation
    const tableBody = document.getElementById('unified-table-body');
    if (tableBody) {
      tableBody.querySelectorAll('[data-measurement="eye-rotation"]').forEach(r => r.remove());
    }
  }
}

// Funzione clearAllMeasurementOverlays gestita in main.js (non duplicare)

// === FUNZIONI PRINCIPALI SISTEMA SEMPLIFICATO ===

function measureFaceWidth(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureFaceWidth"]');
  toggleMeasurementButton(button, 'faceWidth');
}

function performFaceWidthMeasurement() {
  if (!currentLandmarks || currentLandmarks.length === 0) {
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performFaceWidthMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    const leftCheekbone = currentLandmarks[447];
    const rightCheekbone = currentLandmarks[227];
    const glabella = currentLandmarks[9];
    const philtrum = currentLandmarks[164];

    if (!leftCheekbone || !rightCheekbone || !glabella || !philtrum) {
      showToast('Landmark del viso non rilevati correttamente', 'error');
      return;
    }

    if (leftCheekbone && rightCheekbone && glabella && philtrum) {

      // Calcola asse centrale
      const faceCenterX = (glabella.x + philtrum.x) / 2;

      // Punto di intersezione sull'asse centrale (altezza media degli zigomi)
      const cheekboneY = (leftCheekbone.y + rightCheekbone.y) / 2;
      const centerPoint = { x: faceCenterX, y: cheekboneY };

      // Calcola distanze da centro a ogni zigomo
      const leftDistance = calculateDistanceBetweenPoints(centerPoint, leftCheekbone);
      const rightDistance = calculateDistanceBetweenPoints(centerPoint, rightCheekbone);
      const totalWidth = calculateDistanceBetweenPoints(leftCheekbone, rightCheekbone);

      if (!leftDistance || !rightDistance || !totalWidth || isNaN(leftDistance) || isNaN(rightDistance) || isNaN(totalWidth)) {
        showToast('Errore nel calcolo delle distanze', 'error');
        return;
      }

      // Determina quale lato è più largo
      const difference = Math.abs(leftDistance - rightDistance);
      const percentDiff = (difference / Math.max(leftDistance, rightDistance) * 100);

      let comparisonText = '';
      let voiceMessage = '';

      if (percentDiff < 2) {
        comparisonText = 'Larghezze equilibrate';
        voiceMessage = `Larghezza viso ${totalWidth.toFixed(0)} pixel. I due lati sono equilibrati.`;
      } else if (leftDistance > rightDistance) {
        comparisonText = `Lato sinistro più largo di ${difference.toFixed(1)}px (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `Larghezza viso ${totalWidth.toFixed(0)} pixel. Il lato sinistro è più largo di ${difference.toFixed(0)} pixel.`;
      } else {
        comparisonText = `Lato destro più largo di ${difference.toFixed(1)}px (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `Larghezza viso ${totalWidth.toFixed(0)} pixel. Il lato destro è più largo di ${difference.toFixed(0)} pixel.`;
      }

      // Crea gli oggetti overlay
      const overlayObjects = [];

      // Disegna linea principale
      const measurementLine = createMeasurementLine(leftCheekbone, rightCheekbone, 'Larghezza Viso', '#FF6B35');
      overlayObjects.push(measurementLine);

      // Disegna linee dai lati al centro
      const leftToCenter = createMeasurementLine(leftCheekbone, centerPoint, 'Lato Sinistro', '#FF9B35');
      const rightToCenter = createMeasurementLine(rightCheekbone, centerPoint, 'Lato Destro', '#FF9B35');
      overlayObjects.push(leftToCenter, rightToCenter);

      // Disegna asse centrale
      try {
        const transformedGlabella = window.transformLandmarkCoordinate(glabella);
        const transformedPhiltrum = window.transformLandmarkCoordinate(philtrum);

        const dx = transformedPhiltrum.x - transformedGlabella.x;
        const dy = transformedPhiltrum.y - transformedGlabella.y;
        const length = Math.sqrt(dx * dx + dy * dy);
        const dirX = dx / length;
        const dirY = dy / length;

        const maxExtension = Math.sqrt(fabricCanvas.getWidth() ** 2 + fabricCanvas.getHeight() ** 2);
        const axisTopX = transformedGlabella.x - dirX * maxExtension;
        const axisTopY = transformedGlabella.y - dirY * maxExtension;
        const axisBottomX = transformedPhiltrum.x + dirX * maxExtension;
        const axisBottomY = transformedPhiltrum.y + dirY * maxExtension;

        const axisLine = new fabric.Line([axisTopX, axisTopY, axisBottomX, axisBottomY], {
          stroke: '#FFFFFF',
          strokeWidth: 1,
          strokeDashArray: [5, 3],
          selectable: false,
          evented: false,
          isMeasurementLabel: true
        });

        fabricCanvas.add(axisLine);
        overlayObjects.push(axisLine);
        fabricCanvas.sendToBack(axisLine);
      } catch (e) {
        console.warn('Impossibile disegnare asse centrale:', e);
      }

      // Salva overlay per questa misurazione
      measurementOverlays.set('faceWidth', overlayObjects);

      // Aggiungi alla tabella - ESPANDI LA SEZIONE
      ensureMeasurementsSectionOpen();
      addMeasurementToTable('Larghezza Viso Totale', totalWidth, 'px', 'faceWidth');
      addMeasurementToTable('Larghezza Lato Sinistro', leftDistance, 'px');
      addMeasurementToTable('Larghezza Lato Destro', rightDistance, 'px');
      addMeasurementToTable('Differenza Lati', difference, 'px');
      addMeasurementToTable('Valutazione Simmetria', comparisonText, '');

      // Feedback vocale
      if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
        voiceAssistant.speak(voiceMessage);
      }

      console.log('📐 Larghezza viso completata:', {
        totalWidth: totalWidth.toFixed(1),
        leftDistance: leftDistance.toFixed(1),
        rightDistance: rightDistance.toFixed(1),
        difference: difference.toFixed(1)
      });
    } else {
      showToast('Landmarks degli zigomi o asse centrale non trovati', 'warning');
    }
  } catch (error) {
    console.error('Errore misurazione larghezza viso:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureFaceHeight(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureFaceHeight"]');
  toggleMeasurementButton(button, 'faceHeight');
}

function performFaceHeightMeasurement() {
  console.log('📏 Misurazione altezza viso...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureFaceHeight(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Usa landmark più precisi per l'altezza del viso
    const topForehead = currentLandmarks[10];    // Centro fronte superiore
    const bottomChin = currentLandmarks[152];    // Punto più basso del mento (più accurato del 175)

    if (topForehead && bottomChin) {
      console.log('📏 Misurazione altezza viso (fronte-mento):', {
        topForehead: { x: topForehead.x.toFixed(1), y: topForehead.y.toFixed(1) },
        bottomChin: { x: bottomChin.x.toFixed(1), y: bottomChin.y.toFixed(1) }
      });

      const height = calculateDistanceBetweenPoints(topForehead, bottomChin);

      // Calcola anche la larghezza per il rapporto
      const leftCheekbone = currentLandmarks[447];
      const rightCheekbone = currentLandmarks[227];

      if (leftCheekbone && rightCheekbone) {
        const width = calculateDistanceBetweenPoints(leftCheekbone, rightCheekbone);
        const ratio = height / width;

        // Valutazione descrittiva basata sul rapporto altezza/larghezza
        let evaluation = '';
        let voiceMessage = '';

        if (ratio < 1.2) {
          evaluation = 'Viso poco allungato (tendente al largo)';
          voiceMessage = `Altezza viso ${height.toFixed(0)} pixel. Il viso risulta poco allungato, con proporzioni tendenti al largo.`;
        } else if (ratio >= 1.2 && ratio < 1.35) {
          evaluation = 'Viso moderatamente allungato';
          voiceMessage = `Altezza viso ${height.toFixed(0)} pixel. Il viso presenta un allungamento moderato, con proporzioni equilibrate.`;
        } else if (ratio >= 1.35 && ratio < 1.5) {
          evaluation = 'Viso correttamente allungato';
          voiceMessage = `Altezza viso ${height.toFixed(0)} pixel. Il viso è correttamente allungato, con proporzioni armoniose.`;
        } else if (ratio >= 1.5 && ratio < 1.65) {
          evaluation = 'Viso notevolmente allungato';
          voiceMessage = `Altezza viso ${height.toFixed(0)} pixel. Il viso risulta notevolmente allungato.`;
        } else {
          evaluation = 'Viso molto allungato';
          voiceMessage = `Altezza viso ${height.toFixed(0)} pixel. Il viso risulta molto allungato, con proporzioni verticali marcate.`;
        }

        // Crea gli oggetti overlay
        const overlayObjects = [];

        // Linea principale altezza
        const measurementLine = createMeasurementLine(topForehead, bottomChin, 'Altezza Viso', '#F7931E');
        overlayObjects.push(measurementLine);

        // Aggiungi linea larghezza di riferimento
        const widthLine = createMeasurementLine(leftCheekbone, rightCheekbone, 'Larghezza Riferimento', '#FFD23F');
        overlayObjects.push(widthLine);

        // Salva overlay per questa misurazione
        measurementOverlays.set('faceHeight', overlayObjects);

        // Aggiungi alla tabella - ESPANDI LA SEZIONE
        ensureMeasurementsSectionOpen();
        addMeasurementToTable('Altezza Viso', height, 'px', 'faceHeight');
        addMeasurementToTable('Larghezza Viso (rif.)', width, 'px');
        addMeasurementToTable('Rapporto Altezza/Larghezza', ratio.toFixed(2), '');
        addMeasurementToTable('Valutazione Proporzioni', evaluation, '');

        // Feedback vocale
        if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
          voiceAssistant.speak(voiceMessage);
        }

        console.log('📏 Altezza viso completata:', {
          height: height.toFixed(1),
          width: width.toFixed(1),
          ratio: ratio.toFixed(2),
          evaluation: evaluation
        });
      } else {
        // Fallback se non ci sono i landmark della larghezza
        const overlayObjects = [];
        const measurementLine = createMeasurementLine(topForehead, bottomChin, 'Altezza Viso', '#F7931E');
        overlayObjects.push(measurementLine);
        measurementOverlays.set('faceHeight', overlayObjects);

        ensureMeasurementsSectionOpen();
        addMeasurementToTable('Altezza Viso', height, 'px', 'faceHeight');

        const simpleMessage = `Altezza viso ${height.toFixed(0)} pixel.`;
        if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
          voiceAssistant.speak(simpleMessage);
        }
      }
    } else {
      showToast('Landmarks della fronte o del mento non trovati', 'warning');
    }
  } catch (error) {
    console.error('Errore misurazione altezza viso:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureEyeDistance(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureEyeDistance"]');
  toggleMeasurementButton(button, 'eyeDistance');
}

function performEyeDistanceMeasurement() {
  if (!currentLandmarks || currentLandmarks.length === 0) {
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performEyeDistanceMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    const leftEyeInnerCorner = currentLandmarks[133];
    const rightEyeInnerCorner = currentLandmarks[362];
    const glabella = currentLandmarks[9];
    const philtrum = currentLandmarks[164];

    if (!leftEyeInnerCorner || !rightEyeInnerCorner || !glabella || !philtrum) {
      showToast('Landmark degli occhi non rilevati correttamente', 'error');
      return;
    }

    // Calcola asse centrale
    const faceCenterX = (glabella.x + philtrum.x) / 2;
    const eyeY = (leftEyeInnerCorner.y + rightEyeInnerCorner.y) / 2;
    const centerPoint = { x: faceCenterX, y: eyeY };

    // Calcola distanze da centro a ogni angolo interno
    const leftDistance = calculateDistanceBetweenPoints(centerPoint, leftEyeInnerCorner);
    const rightDistance = calculateDistanceBetweenPoints(centerPoint, rightEyeInnerCorner);
    const totalDistance = calculateDistanceBetweenPoints(leftEyeInnerCorner, rightEyeInnerCorner);

    if (!leftDistance || !rightDistance || !totalDistance || isNaN(leftDistance) || isNaN(rightDistance) || isNaN(totalDistance)) {
      showToast('Errore nel calcolo delle distanze', 'error');
      return;
    }

    // Determina quale occhio è più vicino al centro
    const difference = Math.abs(leftDistance - rightDistance);
    const percentDiff = (difference / Math.max(leftDistance, rightDistance) * 100);

    let comparisonText = '';
    let voiceMessage = '';

    if (percentDiff < 2) {
      comparisonText = 'Occhi equidistanti dal centro';
      voiceMessage = `Distanza angoli interni ${totalDistance.toFixed(0)} pixel. Gli occhi sono equidistanti.`;
    } else if (leftDistance < rightDistance) {
      comparisonText = `Occhio sinistro più vicino di ${difference.toFixed(1)}px (-${percentDiff.toFixed(1)}%)`;
      voiceMessage = `Distanza angoli interni ${totalDistance.toFixed(0)} pixel. L'occhio sinistro è più vicino al centro di ${difference.toFixed(0)} pixel.`;
    } else {
      comparisonText = `Occhio destro più vicino di ${difference.toFixed(1)}px (-${percentDiff.toFixed(1)}%)`;
      voiceMessage = `Distanza angoli interni ${totalDistance.toFixed(0)} pixel. L'occhio destro è più vicino al centro di ${difference.toFixed(0)} pixel.`;
    }

    // Crea overlay
    const overlayObjects = [];
    const measurementLine = createMeasurementLine(leftEyeInnerCorner, rightEyeInnerCorner, 'Distanza Occhi', '#FFD23F');
    overlayObjects.push(measurementLine);

    const leftToCenter = createMeasurementLine(leftEyeInnerCorner, centerPoint, 'Sin', '#FFD93F');
    const rightToCenter = createMeasurementLine(rightEyeInnerCorner, centerPoint, 'Dex', '#FFD93F');
    overlayObjects.push(leftToCenter, rightToCenter);

    measurementOverlays.set('eyeDistance', overlayObjects);

    // Aggiungi a tabella - ESPANDI LA SEZIONE
    ensureMeasurementsSectionOpen();
    addMeasurementToTable('Distanza Angoli Interni Occhi', totalDistance, 'px', 'eyeDistance');
    addMeasurementToTable('Distanza Occhio Sinistro', leftDistance, 'px');
    addMeasurementToTable('Distanza Occhio Destro', rightDistance, 'px');
    addMeasurementToTable('Differenza Distanze', difference, 'px');
    addMeasurementToTable('Valutazione Simmetria', comparisonText, '');

    // Feedback vocale
    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
      voiceAssistant.speak(voiceMessage);
    }
  } catch (error) {
    console.error('Errore misurazione distanza occhi:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureNoseWidth(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureNoseWidth"]');
  toggleMeasurementButton(button, 'noseWidth');
}

function performNoseWidthMeasurement() {
  console.log('👃 Misurazione larghezza naso...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureNoseWidth(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Usa i punti laterali delle ali nasali per larghezza massima del naso
    const leftNoseWing = currentLandmarks[218];  // Ala nasale sinistra (punto più esterno)
    const rightNoseWing = currentLandmarks[438]; // Ala nasale destra (punto più esterno)

    if (leftNoseWing && rightNoseWing) {
      console.log('👃 Misurazione larghezza naso (ali nasali):', {
        leftWing: { x: leftNoseWing.x.toFixed(1), y: leftNoseWing.y.toFixed(1) },
        rightWing: { x: rightNoseWing.x.toFixed(1), y: rightNoseWing.y.toFixed(1) }
      });

      const distance = calculateDistanceBetweenPoints(leftNoseWing, rightNoseWing);

      // Crea gli oggetti overlay
      const overlayObjects = [];
      const measurementLine = createMeasurementLine(leftNoseWing, rightNoseWing, 'Larghezza Naso', '#06FFA5');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('noseWidth', overlayObjects);

      // Aggiungi alla tabella
      addMeasurementToTable('Larghezza Naso', distance, 'mm', 'noseWidth');
      showToast(`Larghezza naso: ${distance.toFixed(1)} mm`, 'success');
    } else {
      showToast('Landmarks delle ali nasali non trovati', 'warning');
    }
  } catch (error) {
    console.error('Errore misurazione larghezza naso:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureMouthWidth(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureMouthWidth"]');
  toggleMeasurementButton(button, 'mouthWidth');
}

function performMouthWidthMeasurement() {
  console.log('👄 Misurazione larghezza bocca...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureMouthWidth(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // I landmark 61 e 291 sono corretti per gli angoli della bocca in MediaPipe
    const leftMouthCorner = currentLandmarks[61];   // Angolo sinistro bocca
    const rightMouthCorner = currentLandmarks[291]; // Angolo destro bocca

    // Punto centrale del viso (glabella e philtrum per asse simmetria)
    const glabella = currentLandmarks[9];
    const philtrum = currentLandmarks[164];

    if (leftMouthCorner && rightMouthCorner && glabella && philtrum) {
      console.log('👄 Misurazione larghezza bocca (angoli):', {
        leftCorner: { x: leftMouthCorner.x.toFixed(1), y: leftMouthCorner.y.toFixed(1) },
        rightCorner: { x: rightMouthCorner.x.toFixed(1), y: rightMouthCorner.y.toFixed(1) }
      });

      // Calcola asse centrale
      const faceCenterX = (glabella.x + philtrum.x) / 2;

      // Punto di intersezione sull'asse centrale (altezza bocca)
      const mouthY = (leftMouthCorner.y + rightMouthCorner.y) / 2;
      const centerPoint = { x: faceCenterX, y: mouthY };

      // Calcola distanze da centro a ogni angolo
      const leftDistance = calculateDistanceBetweenPoints(centerPoint, leftMouthCorner);
      const rightDistance = calculateDistanceBetweenPoints(centerPoint, rightMouthCorner);
      const totalWidth = calculateDistanceBetweenPoints(leftMouthCorner, rightMouthCorner);

      // Determina quale lato è più largo
      const difference = Math.abs(leftDistance - rightDistance);
      const percentDiff = (difference / Math.max(leftDistance, rightDistance) * 100);

      let comparisonText = '';
      let voiceMessage = '';

      if (percentDiff < 2) {
        comparisonText = 'Larghezze equilibrate';
        voiceMessage = `Larghezza bocca ${totalWidth.toFixed(0)} pixel. I due lati sono equilibrati.`;
      } else if (leftDistance > rightDistance) {
        comparisonText = `Lato sinistro più largo di ${difference.toFixed(1)}mm (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `Larghezza bocca ${totalWidth.toFixed(0)} pixel. Il lato sinistro è più largo di ${difference.toFixed(0)} pixel.`;
      } else {
        comparisonText = `Lato destro più largo di ${difference.toFixed(1)}mm (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `Larghezza bocca ${totalWidth.toFixed(0)} pixel. Il lato destro è più largo di ${difference.toFixed(0)} pixel.`;
      }

      // Crea gli oggetti overlay
      const overlayObjects = [];

      // Disegna linea principale
      const measurementLine = createMeasurementLine(leftMouthCorner, rightMouthCorner, 'Larghezza Bocca', '#118AB2');
      overlayObjects.push(measurementLine);

      // Disegna linee dai lati al centro
      const leftToCenter = createMeasurementLine(leftMouthCorner, centerPoint, 'Lato Sinistro', '#3DABC2');
      const rightToCenter = createMeasurementLine(rightMouthCorner, centerPoint, 'Lato Destro', '#3DABC2');
      overlayObjects.push(leftToCenter, rightToCenter);

      // Disegna asse centrale
      try {
        const transformedGlabella = window.transformLandmarkCoordinate(glabella);
        const transformedPhiltrum = window.transformLandmarkCoordinate(philtrum);

        const dx = transformedPhiltrum.x - transformedGlabella.x;
        const dy = transformedPhiltrum.y - transformedGlabella.y;
        const length = Math.sqrt(dx * dx + dy * dy);
        const dirX = dx / length;
        const dirY = dy / length;

        const maxExtension = Math.sqrt(fabricCanvas.getWidth() ** 2 + fabricCanvas.getHeight() ** 2);
        const axisTopX = transformedGlabella.x - dirX * maxExtension;
        const axisTopY = transformedGlabella.y - dirY * maxExtension;
        const axisBottomX = transformedPhiltrum.x + dirX * maxExtension;
        const axisBottomY = transformedPhiltrum.y + dirY * maxExtension;

        const axisLine = new fabric.Line([axisTopX, axisTopY, axisBottomX, axisBottomY], {
          stroke: '#FFFFFF',
          strokeWidth: 1,
          strokeDashArray: [5, 3],
          selectable: false,
          evented: false,
          isMeasurementLabel: true
        });

        fabricCanvas.add(axisLine);
        overlayObjects.push(axisLine);
        fabricCanvas.sendToBack(axisLine);
      } catch (e) {
        console.warn('Impossibile disegnare asse centrale:', e);
      }

      // Salva overlay per questa misurazione
      measurementOverlays.set('mouthWidth', overlayObjects);

      // Aggiungi alla tabella - ESPANDI LA SEZIONE
      ensureMeasurementsSectionOpen();
      addMeasurementToTable('Larghezza Bocca Totale', totalWidth, 'px', 'mouthWidth');
      addMeasurementToTable('Larghezza Lato Sinistro', leftDistance, 'px');
      addMeasurementToTable('Larghezza Lato Destro', rightDistance, 'px');
      addMeasurementToTable('Differenza Lati', difference, 'px');
      addMeasurementToTable('Valutazione Simmetria', comparisonText, '');

      // Feedback vocale
      if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
        voiceAssistant.speak(voiceMessage);
      }

      console.log('👄 Larghezza bocca completata:', {
        totalWidth: totalWidth.toFixed(1),
        leftDistance: leftDistance.toFixed(1),
        rightDistance: rightDistance.toFixed(1),
        difference: difference.toFixed(1)
      });
    } else {
      showToast('Landmarks degli angoli della bocca o asse centrale non trovati', 'warning');
    }
  } catch (error) {
    console.error('Errore misurazione larghezza bocca:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureNoseHeight(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureNoseHeight"]');
  toggleMeasurementButton(button, 'noseHeight');
}

function performNoseHeightMeasurement() {
  console.log('👃 Misurazione altezza naso...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureNoseHeight();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Usa landmark precisi per l'altezza del naso
    const noseBridge = currentLandmarks[6];   // Ponte del naso (punto superiore)
    const noseTip = currentLandmarks[1];      // Punta del naso (punto inferiore)

    if (noseBridge && noseTip) {
      console.log('👃 Misurazione altezza naso (ponte-punta):', {
        bridge: { x: noseBridge.x.toFixed(1), y: noseBridge.y.toFixed(1) },
        tip: { x: noseTip.x.toFixed(1), y: noseTip.y.toFixed(1) }
      });

      const distance = calculateDistanceBetweenPoints(noseBridge, noseTip);

      // Crea gli oggetti overlay
      const overlayObjects = [];
      const measurementLine = createMeasurementLine(noseBridge, noseTip, 'Altezza Naso', '#9D4EDD');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('noseHeight', overlayObjects);

      // Aggiungi alla tabella
      addMeasurementToTable('Altezza Naso', distance, 'mm', 'noseHeight');
      showToast(`Altezza naso: ${distance.toFixed(1)} mm`, 'success');
    } else {
      showToast('Landmarks del ponte o della punta del naso non trovati', 'warning');
    }
  } catch (error) {
    console.error('Errore misurazione altezza naso:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

// === FUNZIONI SUPPORTO ===

// Variabile globale per salvare i dati regionali per il ricalcolo dinamico
window.eyebrowRegionData = null;

function addMeasurementToTable(name, value, unit, measurementType = null, options = {}) {
  // Aggiunge misurazione alla TABELLA UNIFICATA e TABELLA ORIGINALE
  const unifiedTableBody = document.getElementById('unified-table-body');
  const originalTableBody = document.getElementById('measurements-data');

  if (!unifiedTableBody) {
    console.error('❌ Tabella unificata non trovata');
    return;
  }

  // Crea riga per tabella unificata (inserisci in ALTO)
  const row = unifiedTableBody.insertRow(0);
  const typeCell = document.createElement('td');
  typeCell.textContent = name;
  if (measurementType) {
    typeCell.dataset.measurementType = measurementType;
  }

  row.appendChild(typeCell);

  // Gestisci sia valori numerici che stringhe, o slider
  let valueFormatted;
  let valueHTML = '';

  if (options.slider) {
    // Crea slider interattivo
    valueHTML = `<input type="range" min="${options.slider.min}" max="${options.slider.max}" value="${value}" step="${options.slider.step || 1}" style="width:100px;vertical-align:middle;" oninput="window.updateEyebrowTolerance(this.value)"><span style="margin-left:8px;font-weight:bold;" id="tolerance-value">${value}</span>`;
    valueFormatted = value; // Per la tabella originale
  } else {
    valueFormatted = typeof value === 'number' ? value.toFixed(1) : value;
    valueHTML = valueFormatted;
  }

  row.innerHTML += `
    <td>${valueHTML}</td>
    <td>${unit}</td>
    <td>✅</td>
  `;

  // Aggiungi anche alla tabella originale nascosta per sincronizzazione
  if (originalTableBody) {
    const originalRow = originalTableBody.insertRow(0);
    originalRow.innerHTML = `
      <td>${name}</td>
      <td>${valueFormatted}</td>
      <td>${unit}</td>
      <td>✅</td>
    `;
    if (measurementType) {
      originalRow.firstElementChild.dataset.measurementType = measurementType;
    }
  }

  console.log(`✅ Misurazione aggiunta: ${name} = ${valueFormatted} ${unit}`);

  // Apri automaticamente la sezione misurazioni se è chiusa
  ensureMeasurementsSectionOpen();
}

function ensureMeasurementsSectionOpen() {
  /**
   * Apre automaticamente la sezione DATI ANALISI e switcha al tab Misurazioni
   */
  console.log('🔧 ensureMeasurementsSectionOpen() chiamata');

  // Trova la sezione DATI ANALISI
  const sections = document.querySelectorAll('.right-sidebar .section');
  let measurementsSection = null;

  for (const section of sections) {
    const header = section.querySelector('.section-header');
    if (header && header.textContent.includes('DATI ANALISI')) {
      measurementsSection = section;
      break;
    }
  }

  console.log('🔧 Sezione trovata:', measurementsSection ? 'SI' : 'NO');

  if (measurementsSection) {
    const sectionContent = measurementsSection.querySelector('.section-content');

    // Apri la sezione se è chiusa
    if (measurementsSection.dataset.expanded === 'false' || sectionContent.style.display === 'none') {
      measurementsSection.dataset.expanded = 'true';
      sectionContent.style.display = 'block';
      const icon = measurementsSection.querySelector('.icon');
      if (icon) icon.textContent = '▼';
      console.log('📂 Sezione DATI ANALISI aperta automaticamente');
    } else {
      console.log('📂 Sezione DATI ANALISI già aperta');
    }

    // Switcha al tab Misurazioni se esiste la funzione
    if (typeof switchUnifiedTab === 'function') {
      console.log('🔧 Chiamo switchUnifiedTab("measurements") per forzare il cambio tab');
      switchUnifiedTab('measurements');
    } else if (typeof window.switchUnifiedTab === 'function') {
      console.log('🔧 Chiamo window.switchUnifiedTab("measurements") per forzare il cambio tab');
      window.switchUnifiedTab('measurements');
    } else {
      console.error('❌ switchUnifiedTab NON TROVATA!');
    }
  } else {
    console.warn('⚠️ Sezione DATI ANALISI non trovata');
  }
}

function drawMeasurementLine(point1, point2, label) {
  // Disegna linea di misurazione sul canvas con trasformazione coordinate
  console.log('🎯 ===== INIZIO DRAWMEASUREMENTLINE =====');
  console.log('🎯 Parametri ricevuti:', { point1, point2, label, fabricCanvas: !!fabricCanvas });

  if (!fabricCanvas || !point1 || !point2) {
    console.error('❌ Parametri mancanti:', { fabricCanvas: !!fabricCanvas, point1: !!point1, point2: !!point2 });
    return;
  }

  console.log('🎯 Drawing measurement line:', {
    point1: { x: point1.x.toFixed(1), y: point1.y.toFixed(1) },
    point2: { x: point2.x.toFixed(1), y: point2.y.toFixed(1) },
    label: label
  });

  // Assicurati che le informazioni di trasformazione siano aggiornate
  if (window.recalculateImageTransformation && typeof window.recalculateImageTransformation === 'function') {
    console.log('🔄 Ricalcolo trasformazione prima della misurazione...');
    window.recalculateImageTransformation();
  } else {
    console.warn('⚠️ Funzione recalculateImageTransformation non disponibile');
  }

  // Verifica informazioni di scala disponibili
  console.log('🔍 Informazioni scala:', {
    imageScale: window.imageScale,
    imageOffset: window.imageOffset,
    currentImage: !!currentImage,
    fabricCanvas: !!fabricCanvas
  });

  // Trasforma le coordinate per la posizione/scala dell'immagine
  if (!window.transformLandmarkCoordinate || typeof window.transformLandmarkCoordinate !== 'function') {
    console.error('❌ transformLandmarkCoordinate non disponibile');
    showToast('Errore nel sistema di trasformazione coordinate', 'error');
    return;
  }

  const transformedPoint1 = window.transformLandmarkCoordinate(point1);
  const transformedPoint2 = window.transformLandmarkCoordinate(point2);

  console.log('📐 DEBUG COORDINATE DETTAGLIATO:', {
    raw1: { x: point1.x.toFixed(1), y: point1.y.toFixed(1) },
    raw2: { x: point2.x.toFixed(1), y: point2.y.toFixed(1) },
    transformed1: { x: transformedPoint1.x.toFixed(1), y: transformedPoint1.y.toFixed(1) },
    transformed2: { x: transformedPoint2.x.toFixed(1), y: transformedPoint2.y.toFixed(1) },
    canvas: { width: fabricCanvas.width, height: fabricCanvas.height },
    imageScale: window.imageScale,
    imageOffset: window.imageOffset,
    coordinateTransformation: {
      formula: 'landmark.x * imageScale + imageOffset.x',
      esempio: `${point1.x.toFixed(1)} * ${window.imageScale?.toFixed(3)} + ${window.imageOffset?.x?.toFixed(1)} = ${transformedPoint1.x.toFixed(1)}`
    }
  });

  // Debug aggiuntivo: verifica posizione dell'immagine nel canvas
  const fabricImages = fabricCanvas.getObjects().filter(obj => obj.type === 'image');
  if (fabricImages.length > 0) {
    const img = fabricImages[0];
    console.log('🖼️ Posizione immagine nel canvas:', {
      left: img.left,
      top: img.top,
      width: img.width,
      height: img.height,
      scaleX: img.scaleX,
      scaleY: img.scaleY,
      scaledWidth: (img.width * img.scaleX).toFixed(1),
      scaledHeight: (img.height * img.scaleY).toFixed(1)
    });
  }

  const line = new fabric.Line([
    transformedPoint1.x, transformedPoint1.y,
    transformedPoint2.x, transformedPoint2.y
  ], {
    stroke: getRandomMeasurementColor(),
    strokeWidth: 3,
    selectable: false,
    evented: false,
    isMeasurementLine: true,
    measurementLabel: label
  });

  // Aggiungi etichetta della misurazione
  const midX = (transformedPoint1.x + transformedPoint2.x) / 2;
  const midY = (transformedPoint1.y + transformedPoint2.y) / 2;

  const distance = calculateDistanceBetweenPoints(point1, point2);
  const labelText = new fabric.Text(`${distance.toFixed(1)} mm`, {
    left: midX,
    top: midY - 10,
    fontSize: 14,
    fill: '#FFFFFF',
    backgroundColor: 'rgba(0,0,0,0.7)',
    selectable: false,
    evented: false,
    isMeasurementLabel: true,
    textBaseline: 'middle' // Impostazione esplicita per evitare errori
  });

  fabricCanvas.add(line);
  fabricCanvas.add(labelText);
  fabricCanvas.renderAll();

  console.log('✅ Measurement line drawn successfully');
}

// transformLandmarkCoordinate è definita in main.js
// calculateDistance è definita all'inizio del file

function getRandomMeasurementColor() {
  const colors = MEASUREMENT_CONFIG?.colors || ['#FF6B35', '#F7931E', '#FFD23F', '#06FFA5', '#118AB2', '#073B4C'];
  const color = colors[measurementColorIndex % colors.length];
  measurementColorIndex++;
  return color;
}

function removeMeasurement(button) {
  // Rimuove misurazione dalla tabella
  const row = button.closest('tr');
  if (row) row.remove();
}

function clearPreviousMeasurements() {
  // Pulisce misurazioni precedenti dal canvas
  if (fabricCanvas) {
    const measurementObjects = fabricCanvas.getObjects().filter(obj =>
      obj.isMeasurementLine || obj.isMeasurementLabel || obj.isAreaPolygon
    );
    measurementObjects.forEach(obj => fabricCanvas.remove(obj));
    fabricCanvas.renderAll();
  }
}

// === FUNZIONI AGGIUNTIVE MANCANTI ===

function measureEyeAreas(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureEyeAreas"]');
  toggleMeasurementButton(button, 'eyeAreas');
}

function performEyeAreasMeasurement() {
  if (!currentLandmarks || currentLandmarks.length === 0) {
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performEyeAreasMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Verifica che fabricCanvas sia disponibile
    if (!fabricCanvas || typeof fabricCanvas === 'undefined') {
      showToast('Canvas non inizializzato. Riprova.', 'error');
      return;
    }

    // Verifica che window.transformLandmarkCoordinate esista
    if (!window.transformLandmarkCoordinate || typeof window.transformLandmarkCoordinate !== 'function') {
      showToast('Funzione di trasformazione coordinate non disponibile', 'error');
      return;
    }

    // Contorno preciso occhio sinistro secondo MediaPipe Face Mesh
    const leftEyeContour = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246];
    // Contorno preciso occhio destro secondo MediaPipe Face Mesh  
    const rightEyeContour = [362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382];

    // Filtra solo i landmark validi per evitare errori
    const leftEyePoints = leftEyeContour
      .map(i => currentLandmarks[i])
      .filter(point => point && point.x !== undefined && point.y !== undefined);

    const rightEyePoints = rightEyeContour
      .map(i => currentLandmarks[i])
      .filter(point => point && point.x !== undefined && point.y !== undefined);

    if (leftEyePoints.length >= 3 && rightEyePoints.length >= 3) {
      // Calcola aree usando il metodo Shoelace
      const leftArea = calculatePolygonArea(leftEyePoints);
      const rightArea = calculatePolygonArea(rightEyePoints);

      // Crea gli oggetti overlay
      const overlayObjects = [];

      // Disegna i poligoni delle aree degli occhi
      const leftEyePolygon = createAreaPolygon(leftEyePoints, 'Area Occhio Sinistro', '#4CAF50');
      const rightEyePolygon = createAreaPolygon(rightEyePoints, 'Area Occhio Destro', '#2196F3');

      if (leftEyePolygon) overlayObjects.push(leftEyePolygon);
      if (rightEyePolygon) overlayObjects.push(rightEyePolygon);

      // Aggiungi etichette che indicano quale occhio è più grande
      try {
        const transformedLeft = leftEyePoints.map(p => window.transformLandmarkCoordinate(p));
        const transformedRight = rightEyePoints.map(p => window.transformLandmarkCoordinate(p));
        const leftCentroid = calculateCentroid(transformedLeft);
        const rightCentroid = calculateCentroid(transformedRight);

        let largerText = '';
        if (leftArea > rightArea) largerText = 'Occhio sinistro più grande';
        else if (rightArea > leftArea) largerText = 'Occhio destro più grande';
        else largerText = 'Occhi uguali';

        const labelLeft = new fabric.Text(largerText, {
          left: leftCentroid.x,
          top: leftCentroid.y - 16,
          fontSize: 12,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(0,0,0,0.6)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true
        });

        const labelRight = new fabric.Text(largerText, {
          left: rightCentroid.x,
          top: rightCentroid.y - 16,
          fontSize: 12,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(0,0,0,0.6)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true
        });

        fabricCanvas.add(labelLeft);
        fabricCanvas.add(labelRight);
        overlayObjects.push(labelLeft, labelRight);
        fabricCanvas.bringToFront(labelLeft);
        fabricCanvas.bringToFront(labelRight);
      } catch (e) {
        console.warn('Impossibile aggiungere etichette aree occhi:', e);
      }

      // Salva overlay per questa misurazione
      measurementOverlays.set('eyeAreas', overlayObjects);

      // Determina quale occhio è più grande
      const areaDifference = Math.abs(leftArea - rightArea);
      const percentDiff = (areaDifference / Math.max(leftArea, rightArea) * 100);

      let comparisonText = '';
      let voiceMessage = '';

      if (percentDiff < 3) {
        comparisonText = 'Occhi di dimensioni equilibrate';
        voiceMessage = `Area occhio sinistro ${leftArea.toFixed(0)} pixel quadrati, occhio destro ${rightArea.toFixed(0)} pixel quadrati. Gli occhi hanno dimensioni equilibrate.`;
      } else if (leftArea > rightArea) {
        comparisonText = `Occhio sinistro più grande di ${areaDifference.toFixed(1)}px² (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `L'occhio sinistro è più grande, con un'area di ${leftArea.toFixed(0)} pixel quadrati, rispetto ai ${rightArea.toFixed(0)} dell'occhio destro.`;
      } else {
        comparisonText = `Occhio destro più grande di ${areaDifference.toFixed(1)}px² (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `L'occhio destro è più grande, con un'area di ${rightArea.toFixed(0)} pixel quadrati, rispetto ai ${leftArea.toFixed(0)} dell'occhio sinistro.`;
      }

      // Aggiungi alla tabella - ESPANDI LA SEZIONE
      ensureMeasurementsSectionOpen();
      addMeasurementToTable('Area Occhio Sinistro', leftArea, 'px²');
      addMeasurementToTable('Area Occhio Destro', rightArea, 'px²');
      addMeasurementToTable('Differenza Aree', areaDifference, 'px²');
      addMeasurementToTable('Valutazione Dimensioni', comparisonText, '');

      // Feedback vocale
      if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
        voiceAssistant.speak(voiceMessage);
      }
    } else {
      showToast('Landmark insufficienti per calcolare le aree degli occhi', 'warning');
    }
  } catch (error) {
    console.error('Errore misurazione aree occhi:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureForeheadWidth(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureForeheadWidth"]');
  toggleMeasurementButton(button, 'foreheadWidth');
}

function performForeheadWidthMeasurement() {
  console.log('🤔 Misurazione larghezza fronte...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performForeheadWidthMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Usa landmark più precisi per la larghezza della fronte
    const leftTemple = currentLandmarks[21];   // Tempia sinistra
    const rightTemple = currentLandmarks[251]; // Tempia destra

    if (leftTemple && rightTemple) {
      console.log('🤔 Misurazione larghezza fronte (tempie):', {
        leftTemple: { x: leftTemple.x.toFixed(1), y: leftTemple.y.toFixed(1) },
        rightTemple: { x: rightTemple.x.toFixed(1), y: rightTemple.y.toFixed(1) }
      });

      const distance = calculateDistanceBetweenPoints(leftTemple, rightTemple);

      // Crea gli oggetti overlay
      const overlayObjects = [];
      const measurementLine = createMeasurementLine(leftTemple, rightTemple, 'Larghezza Fronte', '#9C27B0');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('foreheadWidth', overlayObjects);

      addMeasurementToTable('Larghezza Fronte', distance, 'mm', 'foreheadWidth');
      showToast(`Larghezza fronte: ${distance.toFixed(1)} mm`, 'success');
    } else {
      showToast('Landmarks delle tempie non trovati', 'warning');
    }
  } catch (error) {
    console.error('Errore misurazione fronte:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureFacialSymmetry(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureFacialSymmetry"]');
  toggleMeasurementButton(button, 'facialSymmetry');
}

function performFacialSymmetryMeasurement() {
  console.log('⚖️ NUOVO: Misurazione aree emifacce (simmetria)...');

  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performFacialSymmetryMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // === LANDMARK PERIMETRALI MediaPipe Face Mesh ===
    // Contorno completo del viso
    const faceContourLandmarks = [
      10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
      397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
      172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10
    ];

    // Asse centrale del viso - USA GLI STESSI LANDMARKS DI drawSymmetryAxis()
    // Landmarks MediaPipe: Glabella (9) e Philtrum (164)
    const glabella = currentLandmarks[9];   // Punto superiore: glabella (tra le sopracciglia)
    const philtrum = currentLandmarks[164]; // Punto inferiore: philtrum (area naso-labbro)

    if (!glabella || !philtrum) {
      showToast('Landmark centrali mancanti per calcolare l\'asse del viso', 'warning');
      return;
    }

    // Calcola l'asse centrale X come media tra glabella e philtrum (coordinate originali)
    const faceCenterX = (glabella.x + philtrum.x) / 2;

    console.log('⚖️ Asse centrale calcolato (landmarks 9+164):', {
      faceCenterX,
      glabellaX: glabella.x,
      philtrumX: philtrum.x
    });

    // === SEQUENZE SPECIFICHE DI LANDMARKS PER LE EMIFACCE ===
    // Invece di filtrare tutti i punti, usiamo sequenze precise

    // EMIFACCIA SINISTRA: landmarks dal 148 al 152 passando per il 10
    // Sequenza: 10 (top) → 338 → ... → 152 (bottom lato sinistro)
    const leftFaceLandmarkSequence = [
      10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
      397, 365, 379, 378, 400, 377, 152
    ];

    // EMIFACCIA DESTRA: landmarks dal 338 al 10 poi verso il 152
    // Sequenza: 152 → 148 → ... → 10 (top lato destro)
    const rightFaceLandmarkSequence = [
      152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10
    ];

    // Trasforma i landmark dell'asse (STESSI di drawSymmetryAxis)
    const transformedGlabella = window.transformLandmarkCoordinate(glabella);
    const transformedPhiltrum = window.transformLandmarkCoordinate(philtrum);

    // Calcola direzione dell'asse (stesso algoritmo di drawSymmetryAxis)
    const dx = transformedPhiltrum.x - transformedGlabella.x;
    const dy = transformedPhiltrum.y - transformedGlabella.y;
    const length = Math.sqrt(dx * dx + dy * dy);
    const dirX = dx / length;
    const dirY = dy / length;

    // Estendi l'asse per trovare i punti top/bottom
    const maxExtension = Math.sqrt(fabricCanvas.getWidth() ** 2 + fabricCanvas.getHeight() ** 2);
    const axisTopX = transformedGlabella.x - dirX * maxExtension;
    const axisTopY = transformedGlabella.y - dirY * maxExtension;
    const axisBottomX = transformedPhiltrum.x + dirX * maxExtension;
    const axisBottomY = transformedPhiltrum.y + dirY * maxExtension;

    // Estrai e trasforma i landmarks delle emifacce
    const leftFacePoints = leftFaceLandmarkSequence
      .map(i => currentLandmarks[i])
      .filter(p => p && p.x !== undefined && p.y !== undefined)
      .map(p => window.transformLandmarkCoordinate(p));

    const rightFacePoints = rightFaceLandmarkSequence
      .map(i => currentLandmarks[i])
      .filter(p => p && p.x !== undefined && p.y !== undefined)
      .map(p => window.transformLandmarkCoordinate(p));

    if (leftFacePoints.length < 5 || rightFacePoints.length < 5) {
      showToast('Landmark delle emifacce insufficienti', 'warning');
      return;
    }

    // === COSTRUZIONE POLIGONO EMIFACCIA SINISTRA ===
    // Percorso: 10 (asse) → contorno sinistro → 152 (asse) → chiudi lungo asse
    const leftFacePolygonSorted = [
      ...leftFacePoints,                                          // Contorno da 10 a 152
      { x: transformedPhiltrum.x, y: transformedPhiltrum.y }     // Philtrum (chiude sul 152)
    ];

    // === COSTRUZIONE POLIGONO EMIFACCIA DESTRA ===  
    // Percorso: 152 (asse) → contorno destro → 10 (asse) → chiudi lungo asse
    const rightFacePolygonSorted = [
      ...rightFacePoints,                                         // Contorno da 152 a 10
      { x: transformedGlabella.x, y: transformedGlabella.y }     // Glabella (chiude sul 10)
    ];

    console.log('⚖️ Poligoni emifacce migliorati:', {
      leftPoints: leftFacePolygonSorted.length,
      rightPoints: rightFacePolygonSorted.length,
      faceCenterX: faceCenterX,
      leftPointsRange: {
        minX: Math.min(...leftFacePolygonSorted.map(p => p.x)),
        maxX: Math.max(...leftFacePolygonSorted.map(p => p.x))
      },
      rightPointsRange: {
        minX: Math.min(...rightFacePolygonSorted.map(p => p.x)),
        maxX: Math.max(...rightFacePolygonSorted.map(p => p.x))
      }
    });

    console.log('⚖️ Poligoni emifacce (coordinate trasformate):', {
      leftPoints: leftFacePolygonSorted.length,
      rightPoints: rightFacePolygonSorted.length,
      sampleLeftPoint: leftFacePolygonSorted[0],
      sampleRightPoint: rightFacePolygonSorted[0]
    });

    // Calcola le aree delle emifacce (già in coordinate trasformate/canvas = pixel²)
    // Usa la funzione locale, non quella globale di main.js
    const leftFaceAreaPixels = calculatePolygonAreaFromPoints(leftFacePolygonSorted);
    const rightFaceAreaPixels = calculatePolygonAreaFromPoints(rightFacePolygonSorted);

    // Converti da pixel² a px² usando il pixel ratio globale
    const pixelToMmRatio = window.pixelToMmRatio || 0.1; // Default se non definito
    const leftFaceArea = leftFaceAreaPixels * pixelToMmRatio * pixelToMmRatio;
    const rightFaceArea = rightFaceAreaPixels * pixelToMmRatio * pixelToMmRatio;

    console.log('⚖️ Aree calcolate:', {
      leftFaceAreaPixels: leftFaceAreaPixels,
      rightFaceAreaPixels: rightFaceAreaPixels,
      leftFaceArea: leftFaceArea,
      rightFaceArea: rightFaceArea,
      pixelToMmRatio: pixelToMmRatio,
      leftFaceAreaType: typeof leftFaceArea,
      rightFaceAreaType: typeof rightFaceArea
    });

    // Verifica che le aree siano valide numeri
    if (typeof leftFaceArea !== 'number' || typeof rightFaceArea !== 'number' ||
      isNaN(leftFaceArea) || isNaN(rightFaceArea) ||
      leftFaceArea <= 0 || rightFaceArea <= 0) {
      console.error('❌ Aree non valide:', { leftFaceArea, rightFaceArea });
      showToast('Errore nel calcolo delle aree delle emifacce', 'error');
      return;
    }

    // Crea overlay visuali
    const overlayObjects = [];

    // Poligono emifaccia SINISTRA (punti già trasformati, non servono ulteriori trasformazioni)
    const leftFaceAreaPolygon = createAreaPolygonDirect(leftFacePolygonSorted, 'Emifaccia Sinistra', '#FF6B35');
    if (leftFaceAreaPolygon) overlayObjects.push(leftFaceAreaPolygon);

    // Poligono emifaccia DESTRA (punti già trasformati)
    const rightFaceAreaPolygon = createAreaPolygonDirect(rightFacePolygonSorted, 'Emifaccia Destra', '#6B73FF');
    if (rightFaceAreaPolygon) overlayObjects.push(rightFaceAreaPolygon);

    // Linea dell'asse centrale (usa punti già calcolati)
    try {
      const axisLine = new fabric.Line([axisTopX, axisTopY, axisBottomX, axisBottomY], {
        stroke: '#FFFFFF',
        strokeWidth: 2,
        strokeDashArray: [10, 5],
        selectable: false,
        evented: false,
        isMeasurementLabel: true
      });

      fabricCanvas.add(axisLine);
      overlayObjects.push(axisLine);
      fabricCanvas.bringToFront(axisLine);
    } catch (e) {
      console.warn('Impossibile disegnare asse centrale:', e);
    }

    // Etichette comparative (punti già trasformati)
    try {
      const leftCentroid = calculateCentroid(leftFacePolygonSorted);
      const rightCentroid = calculateCentroid(rightFacePolygonSorted);

      // Calcola differenza percentuale
      const totalArea = leftFaceArea + rightFaceArea;
      const leftPercentage = (leftFaceArea / totalArea * 100);
      const rightPercentage = (rightFaceArea / totalArea * 100);
      const asymmetry = Math.abs(leftPercentage - rightPercentage);

      let comparisonText = '';
      if (asymmetry < 2) {
        comparisonText = 'Emifacce equilibrate';
      } else if (leftFaceArea > rightFaceArea) {
        comparisonText = `Sinistra +${asymmetry.toFixed(1)}%`;
      } else {
        comparisonText = `Destra +${asymmetry.toFixed(1)}%`;
      }

      // Etichette per ciascuna emifaccia
      const labelLeft = new fabric.Text(`${leftFaceArea.toFixed(1)}px²\n(${leftPercentage.toFixed(1)}%)`, {
        left: leftCentroid.x - 30,
        top: leftCentroid.y - 20,
        fontSize: 11,
        fill: '#FFFFFF',
        backgroundColor: 'rgba(255,107,53,0.9)',
        textAlign: 'center',
        selectable: false,
        evented: false,
        isMeasurementLabel: true
      });

      const labelRight = new fabric.Text(`${rightFaceArea.toFixed(1)}px²\n(${rightPercentage.toFixed(1)}%)`, {
        left: rightCentroid.x - 30,
        top: rightCentroid.y - 20,
        fontSize: 11,
        fill: '#FFFFFF',
        backgroundColor: 'rgba(107,115,255,0.9)',
        textAlign: 'center',
        selectable: false,
        evented: false,
        isMeasurementLabel: true
      });

      // Etichetta di confronto (rimossa per evitare sovrapposizioni indesiderate)
      // Solo se la differenza è significativa e posizionata meglio
      if (asymmetry > 3) { // Solo se asimmetria > 3%
        const comparisonLabel = new fabric.Text(comparisonText, {
          left: (leftCentroid.x + rightCentroid.x) / 2 - 40,
          top: Math.min(leftCentroid.y, rightCentroid.y) - 80, // Più in alto per evitare sovrapposizioni
          fontSize: 12,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(50,50,50,0.9)',
          textAlign: 'center',
          selectable: false,
          evented: false,
          isMeasurementLabel: true
        });

        fabricCanvas.add(comparisonLabel);
        overlayObjects.push(comparisonLabel);
        fabricCanvas.bringToFront(comparisonLabel);
      }

      fabricCanvas.add(labelLeft);
      fabricCanvas.add(labelRight);
      overlayObjects.push(labelLeft, labelRight);

      fabricCanvas.bringToFront(labelLeft);
      fabricCanvas.bringToFront(labelRight);
    } catch (e) {
      console.warn('Impossibile aggiungere etichette:', e);
    }

    // Salva overlay
    measurementOverlays.set('facialSymmetry', overlayObjects);

    // Calcola differenza e percentuale
    const totalArea = leftFaceArea + rightFaceArea;
    const leftPercentage = (leftFaceArea / totalArea * 100);
    const rightPercentage = (rightFaceArea / totalArea * 100);
    const asymmetryPercent = Math.abs(leftPercentage - rightPercentage);
    const asymmetryAbsolute = Math.abs(leftFaceArea - rightFaceArea);

    // Determina quale lato è più grande e genera messaggio DETTAGLIATO
    let biggerSideMessage = '';
    let voiceMessage = '';
    let resultDescription = '';

    if (asymmetryPercent < 2) {
      biggerSideMessage = 'Simmetria Eccellente';
      resultDescription = 'Emifacce della cliente quasi perfettamente equilibrate';
      voiceMessage = `Le emifacce della cliente sono quasi perfettamente equilibrate, con una differenza inferiore al 2%`;
    } else if (leftFaceArea > rightFaceArea) {
      biggerSideMessage = `Lato SINISTRO maggiore`;
      resultDescription = `Il lato sinistro della cliente supera il destro del ${asymmetryPercent.toFixed(1)}%`;
      voiceMessage = `Il lato sinistro della cliente è più grande del ${asymmetryPercent.toFixed(1)}% rispetto al destro`;
    } else {
      biggerSideMessage = `Lato DESTRO maggiore`;
      resultDescription = `Il lato destro della cliente supera il sinistro del ${asymmetryPercent.toFixed(1)}%`;
      voiceMessage = `Il lato destro della cliente è più grande del ${asymmetryPercent.toFixed(1)}% rispetto al sinistro`;
    }

    // Salva il messaggio VOCALE dettagliato
    window.lastSymmetryMessage = voiceMessage;

    // Aggiungi alla tabella MISURAZIONI con informazioni complete
    addMeasurementToTable('Area Emifaccia Sinistra', leftFaceArea, 'px²');
    addMeasurementToTable('Area Emifaccia Destra', rightFaceArea, 'px²');
    addMeasurementToTable('Differenza Assoluta', asymmetryAbsolute, 'px²');
    addMeasurementToTable('Differenza Percentuale', asymmetryPercent, '%');
    addMeasurementToTable('Risultato Simmetria', resultDescription, '');

    // Feedback vocale
    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
      voiceAssistant.speak(voiceMessage);
    }

    console.log('⚖️ RISULTATI emifacce:', {
      leftFaceArea: leftFaceArea.toFixed(2),
      rightFaceArea: rightFaceArea.toFixed(2),
      asymmetry: asymmetryAbsolute.toFixed(2),
      asymmetryPercent: asymmetryPercent.toFixed(2),
      biggerSide: biggerSideMessage,
      description: resultDescription
    });

    showToast(resultDescription, 'success');

  } catch (error) {
    console.error('❌ Errore misurazione emifacce:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

// === FUNZIONI MANCANTI ===

function measureCheekWidth(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureCheekWidth"]');
  toggleMeasurementButton(button, 'cheekWidth');
}

function performCheekWidthMeasurement() {
  console.log('😊 Misurazione larghezza guance...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performCheekWidthMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Punti delle guance (zona più prominente)
    const leftCheek = currentLandmarks[205];  // Guancia sinistra
    const rightCheek = currentLandmarks[425]; // Guancia destra

    if (leftCheek && rightCheek) {
      const distance = calculateDistanceBetweenPoints(leftCheek, rightCheek);

      // Crea gli oggetti overlay
      const overlayObjects = [];
      const measurementLine = createMeasurementLine(leftCheek, rightCheek, 'Larghezza Guance', '#E91E63');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('cheekWidth', overlayObjects);

      addMeasurementToTable('Larghezza Guance', distance, 'mm', 'cheekWidth');
      showToast(`Larghezza guance: ${distance.toFixed(1)} mm`, 'success');
    } else {
      showToast('Landmarks delle guance non trovati', 'warning');
    }

  } catch (error) {
    console.error('❌ Errore misurazione guance:', error);
    showToast('Errore durante la misurazione delle guance', 'error');
  }
}

/* DISABILITATO - Aree Sopracciglia nascosto */
function measureEyebrowAreas(event) {
  // DISABILITATO: funzione nascosta su richiesta
  console.log('measureEyebrowAreas disabilitato');
}

function performEyebrowAreasMeasurement(silent = false) {
  return; // DISABILITATO - Aree Sopracciglia nascosto
  if (!currentLandmarks || currentLandmarks.length === 0) { // eslint-disable-line no-unreachable
    if (!silent) showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performEyebrowAreasMeasurement(silent);
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Verifica che fabricCanvas sia disponibile
    if (!fabricCanvas || typeof fabricCanvas === 'undefined') {
      showToast('Canvas non inizializzato. Riprova.', 'error');
      return;
    }

    // Verifica che window.transformLandmarkCoordinate esista
    if (!window.transformLandmarkCoordinate || typeof window.transformLandmarkCoordinate !== 'function') {
      showToast('Funzione di trasformazione coordinate non disponibile', 'error');
      return;
    }

    // Rimuovi overlay sopracciglia precedenti prima di ridisegnare
    if (measurementOverlays.has('eyebrowAreas')) {
      measurementOverlays.get('eyebrowAreas').forEach(obj => fabricCanvas && fabricCanvas.remove(obj));
      measurementOverlays.delete('eyebrowAreas');
    }

    // === LANDMARK CORRETTI MediaPipe Face Mesh per SOPRACCIGLIA ===
    // Sopracciglio SINISTRO (dal punto di vista dell'osservatore - è il destro del soggetto)
    const leftBrowLandmarks = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46];

    // Sopracciglio DESTRO (dal punto di vista dell'osservatore - è il sinistro del soggetto)  
    const rightBrowLandmarks = [296, 334, 293, 300, 276, 283, 282, 295, 285, 336];

    // Estrai punti validi
    const leftBrowPoints = leftBrowLandmarks
      .map(i => currentLandmarks[i])
      .filter(point => point && point.x !== undefined && point.y !== undefined);

    const rightBrowPoints = rightBrowLandmarks
      .map(i => currentLandmarks[i])
      .filter(point => point && point.x !== undefined && point.y !== undefined);

    if (leftBrowPoints.length >= 3 && rightBrowPoints.length >= 3) {
      // Calcola aree dei poligoni base
      const leftBrowArea = calculatePolygonArea(leftBrowPoints);
      const rightBrowArea = calculatePolygonArea(rightBrowPoints);

      // Crea overlay
      const overlayObjects = [];

      // === NUOVO FLUSSO: ELABORAZIONE CON MASCHERE ESPANSE DA 5 PUNTI ===
      console.log('🔬 Inizio elaborazione sopracciglia con maschere espanse (5 punti per sopracciglio)');

      // DEBUG PANEL DISABILITATO
      // createDebugControlPanel();
      // clearEyebrowDebugObjects();

      // 1. Trasforma i punti landmark originali in coordinate canvas (per riferimento)
      // const transformedLeftBrow = leftBrowPoints.map(p => window.transformLandmarkCoordinate(p));
      // const transformedRightBrow = rightBrowPoints.map(p => window.transformLandmarkCoordinate(p));

      // 2. Genera maschere espanse usando 5 punti specifici (già in coordinate canvas)
      const leftExpandedMask = generateLeftEyebrowExpandedMask(currentLandmarks);
      const rightExpandedMask = generateRightEyebrowExpandedMask(currentLandmarks);

      if (!leftExpandedMask || !rightExpandedMask) {
        console.error('❌ Impossibile generare maschere espanse');
        showToast('Errore generazione maschere sopracciglia', 'error');
        return;
      }

      // Le maschere sono già in coordinate canvas
      const scaledLeftBrow = leftExpandedMask;
      const scaledRightBrow = rightExpandedMask;

      console.log('✅ Maschere espanse generate:', {
        leftPoints: scaledLeftBrow.length,
        rightPoints: scaledRightBrow.length
      });

      // DEBUG OVERLAY DISABILITATI
      // drawLandmarkPolygonDebug(transformedLeftBrow, leftBrowLandmarks, 'left');
      // drawLandmarkPolygonDebug(transformedRightBrow, rightBrowLandmarks, 'right');
      // drawOffsetDebug(currentLandmarks, 'left');
      // drawOffsetDebug(currentLandmarks, 'right');
      // drawExpandedMaskDebug(scaledLeftBrow, 'left');
      // drawExpandedMaskDebug(scaledRightBrow, 'right');

      // 3. Ottieni l'immagine dal canvas
      const canvasImage = fabricCanvas.backgroundImage || fabricCanvas.getObjects().find(obj => obj.type === 'image');

      if (!canvasImage) {
        console.warn('⚠️ Immagine non trovata, uso overlay classico');
        // Fallback: usa il metodo classico
        const leftBrowPolygon = createAreaPolygon(leftBrowPoints, 'Area Sopracciglio Sinistro', '#FF6B35');
        const rightBrowPolygon = createAreaPolygon(rightBrowPoints, 'Area Sopracciglio Destro', '#6B73FF');
        if (leftBrowPolygon) overlayObjects.push(leftBrowPolygon);
        if (rightBrowPolygon) overlayObjects.push(rightBrowPolygon);
      } else {
        console.log('🖼️ Immagine trovata, procedo con estrazione e binarizzazione');

        // Prepara landmarks di riferimento per sopracciglio SINISTRO
        const leftLandmarkRefs = {
          lm52: window.transformLandmarkCoordinate(currentLandmarks[52]),
          lm105: window.transformLandmarkCoordinate(currentLandmarks[105]),
          lm107: window.transformLandmarkCoordinate(currentLandmarks[107]),
          lm107ext: leftExpandedMask[0] // 107EXT è il primo punto della maschera sinistra
        };

        // Prepara landmarks di riferimento per sopracciglio DESTRO
        const rightLandmarkRefs = {
          lm52: window.transformLandmarkCoordinate(currentLandmarks[282]), // Speculare di 52
          lm105: window.transformLandmarkCoordinate(currentLandmarks[334]), // Speculare di 105
          lm107: window.transformLandmarkCoordinate(currentLandmarks[336]), // Speculare di 107
          lm107ext: rightExpandedMask[0] // 336EXT è il primo punto della maschera destra
        };

        // 4. Estrai e binarizza le regioni con le maschere scalate
        const leftRegionData = extractAndBinarizeImageRegion(scaledLeftBrow, canvasImage, leftLandmarkRefs);
        const rightRegionData = extractAndBinarizeImageRegion(scaledRightBrow, canvasImage, rightLandmarkRefs);

        if (leftRegionData && rightRegionData) {
          console.log('✅ Regioni estratte e binarizzate (INTERO POLIGONO, no bbox)');

          // DEBUG: Visualizza maschere binarie (DISABILITATO)
          // drawBinaryMaskDebug(leftRegionData, 'left');
          // drawBinaryMaskDebug(rightRegionData, 'right');

          // 5. Crea poligoni overlay basati sui pixel reali delle sopracciglia
          const leftBrowPolygon = createPolygonFromBinaryMask(
            leftRegionData,
            'Area Sopracciglio Sinistro (Reale)',
            '#FF6B35'
          );
          const rightBrowPolygon = createPolygonFromBinaryMask(
            rightRegionData,
            'Area Sopracciglio Destro (Reale)',
            '#6B73FF'
          );

          if (leftBrowPolygon) {
            fabricCanvas.add(leftBrowPolygon);
            fabricCanvas.bringToFront(leftBrowPolygon);
            overlayObjects.push(leftBrowPolygon);
            console.log('✅ Overlay sinistro creato da pixel reali');
          }
          if (rightBrowPolygon) {
            fabricCanvas.add(rightBrowPolygon);
            fabricCanvas.bringToFront(rightBrowPolygon);
            overlayObjects.push(rightBrowPolygon);
            console.log('✅ Overlay destro creato da pixel reali');
          }

          // Calcola le aree reali dai pixel binarizzati
          const leftRealArea = leftRegionData.binaryMask.flat().filter(p => p === 1).length;
          const rightRealArea = rightRegionData.binaryMask.flat().filter(p => p === 1).length;

          console.log('📊 Aree reali calcolate:', {
            leftLandmarks: leftBrowArea.toFixed(1),
            leftReal: leftRealArea,
            rightLandmarks: rightBrowArea.toFixed(1),
            rightReal: rightRealArea
          });

          // Salva i dati regionali globalmente per ricalcolo dinamico
          window.eyebrowRegionData = {
            leftRegionData: leftRegionData,
            rightRegionData: rightRegionData,
            scaledLeftBrow: scaledLeftBrow,
            scaledRightBrow: scaledRightBrow,
            canvasImage: canvasImage,
            overlayObjects: overlayObjects
          };

          // Aggiungi riga per la tolleranza Magic Wand con slider interattivo
          if (!silent && leftRegionData.tolerance !== undefined) {
            // Aggiungi anche info seed color
            if (leftRegionData.seedColor) {
              const rgb = leftRegionData.seedColor;
              const lab = rgbToLab(rgb.r, rgb.g, rgb.b);
              const colorPreview = `<div style="display:inline-block;width:15px;height:15px;background-color:rgb(${Math.round(rgb.r)},${Math.round(rgb.g)},${Math.round(rgb.b)});border:1px solid #999;vertical-align:middle;margin-right:5px;"></div>`;
              const rgbText = `RGB(${Math.round(rgb.r)},${Math.round(rgb.g)},${Math.round(rgb.b)})`;

              addMeasurementToTable(
                'Tolleranza Magic Wand',
                leftRegionData.tolerance,
                colorPreview + rgbText,
                'eyebrow-tolerance',
                {
                  slider: {
                    min: 10,
                    max: 200,
                    step: 5
                  }
                }
              );
            } else {
              addMeasurementToTable(
                'Tolleranza Magic Wand',
                leftRegionData.tolerance,
                'distanza RGB',
                'eyebrow-tolerance',
                {
                  slider: {
                    min: 10,
                    max: 200,
                    step: 5
                  }
                }
              );
            }
          }

        } else {
          console.warn('⚠️ Errore estrazione regioni, uso overlay classico');
          // Fallback
          const leftBrowPolygon = createAreaPolygon(leftBrowPoints, 'Area Sopracciglio Sinistro', '#FF6B35');
          const rightBrowPolygon = createAreaPolygon(rightBrowPoints, 'Area Sopracciglio Destro', '#6B73FF');
          if (leftBrowPolygon) overlayObjects.push(leftBrowPolygon);
          if (rightBrowPolygon) overlayObjects.push(rightBrowPolygon);
        }
      }

      console.log('🎯 Elaborazione maschere sopracciglia completata');

      // Etichette comparative
      try {
        const transformedLeft = leftBrowPoints.map(p => window.transformLandmarkCoordinate(p));
        const transformedRight = rightBrowPoints.map(p => window.transformLandmarkCoordinate(p));
        const leftCentroid = calculateCentroid(transformedLeft);
        const rightCentroid = calculateCentroid(transformedRight);

        let comparisonText = '';
        const difference = Math.abs(leftBrowArea - rightBrowArea);
        const percentDiff = (difference / Math.max(leftBrowArea, rightBrowArea) * 100);

        if (percentDiff < 5) {
          comparisonText = 'Sopracciglia equilibrate';
        } else if (leftBrowArea > rightBrowArea) {
          comparisonText = `Sinistro +${percentDiff.toFixed(1)}%`;
        } else {
          comparisonText = `Destro +${percentDiff.toFixed(1)}%`;
        }

        const labelLeft = new fabric.Text(`${leftBrowArea.toFixed(1)}px²`, {
          left: leftCentroid.x - 20,
          top: leftCentroid.y - 25,
          fontSize: 12,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(255,107,53,0.9)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true,
          visible: debugVisibility.measurementOutput
        });

        const labelRight = new fabric.Text(`${rightBrowArea.toFixed(1)}px²`, {
          left: rightCentroid.x - 20,
          top: rightCentroid.y - 25,
          fontSize: 12,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(107,115,255,0.9)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true,
          visible: debugVisibility.measurementOutput
        });

        const comparisonLabel = new fabric.Text(comparisonText, {
          left: (leftCentroid.x + rightCentroid.x) / 2 - 40,
          top: Math.min(leftCentroid.y, rightCentroid.y) - 50,
          fontSize: 14,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(0,0,0,0.8)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true,
          visible: debugVisibility.measurementOutput
        });

        fabricCanvas.add(labelLeft);
        fabricCanvas.add(labelRight);
        fabricCanvas.add(comparisonLabel);
        overlayObjects.push(labelLeft, labelRight, comparisonLabel);

        fabricCanvas.bringToFront(labelLeft);
        fabricCanvas.bringToFront(labelRight);
        fabricCanvas.bringToFront(comparisonLabel);
      } catch (e) {
        console.warn('Impossibile aggiungere etichette:', e);
      }

      // Salva overlay
      measurementOverlays.set('eyebrowAreas', overlayObjects);

      // Determina quale sopracciglio è più grande
      const areaDifference = Math.abs(leftBrowArea - rightBrowArea);
      const percentDiff = (areaDifference / Math.max(leftBrowArea, rightBrowArea) * 100);

      let comparisonText = '';
      let voiceMessage = '';

      if (percentDiff < 5) {
        comparisonText = 'Sopracciglia di dimensioni equilibrate';
        voiceMessage = `Area sopracciglio sinistro ${leftBrowArea.toFixed(0)} pixel quadrati, sopracciglio destro ${rightBrowArea.toFixed(0)} pixel quadrati. Le sopracciglia hanno dimensioni equilibrate.`;
      } else if (leftBrowArea > rightBrowArea) {
        comparisonText = `Sopracciglio sinistro più grande di ${areaDifference.toFixed(1)}px² (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `Il sopracciglio sinistro è più grande, con un'area di ${leftBrowArea.toFixed(0)} pixel quadrati, rispetto ai ${rightBrowArea.toFixed(0)} del sopracciglio destro.`;
      } else {
        comparisonText = `Sopracciglio destro più grande di ${areaDifference.toFixed(1)}px² (+${percentDiff.toFixed(1)}%)`;
        voiceMessage = `Il sopracciglio destro è più grande, con un'area di ${rightBrowArea.toFixed(0)} pixel quadrati, rispetto ai ${leftBrowArea.toFixed(0)} del sopracciglio sinistro.`;
      }

      // Aggiungi alla tabella - ESPANDI LA SEZIONE (solo se non è un ridisegno silenzioso)
      if (!silent) {
        ensureMeasurementsSectionOpen();
        addMeasurementToTable('Area Sopracciglio Sinistro', leftBrowArea, 'px²');
        addMeasurementToTable('Area Sopracciglio Destro', rightBrowArea, 'px²');
        addMeasurementToTable('Differenza Aree', areaDifference, 'px²');
        addMeasurementToTable('Valutazione Dimensioni', comparisonText, '');

        // Feedback vocale
        if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
          voiceAssistant.speak(voiceMessage);
        }
      }
    } else {
      showToast('Landmark insufficienti per calcolare le aree delle sopracciglia', 'warning');
    }
  } catch (error) {
    console.error('❌ Errore misurazione sopracciglia:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureChinWidth() {
  console.log('😮 Misurazione larghezza mento...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureChinWidth(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Punti del mento
    const leftJaw = currentLandmarks[172];  // Mandibola sinistra
    const rightJaw = currentLandmarks[397]; // Mandibola destra

    if (leftJaw && rightJaw) {
      drawMeasurementLine(leftJaw, rightJaw, 'Larghezza Mento');
      const distance = calculateDistanceBetweenPoints(leftJaw, rightJaw);
      showToast(`Larghezza mento: ${distance.toFixed(1)}mm`, 'success');
    }

  } catch (error) {
    console.error('❌ Errore misurazione mento:', error);
    showToast('Errore durante la misurazione del mento', 'error');
  }
}

function measureFaceProfile() {
  console.log('👤 Misurazione profilo viso...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureFaceProfile(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Punti per il profilo del viso
    const forehead = currentLandmarks[9];   // Fronte
    const noseTip = currentLandmarks[1];    // Punta naso
    const chinTip = currentLandmarks[175];  // Punta mento

    if (forehead && noseTip && chinTip) {
      drawMeasurementLine(forehead, noseTip, 'Fronte-Naso');
      drawMeasurementLine(noseTip, chinTip, 'Naso-Mento');
      drawMeasurementLine(forehead, chinTip, 'Profilo Totale');
      showToast('Misurazione profilo completata', 'success');
    }

  } catch (error) {
    console.error('❌ Errore misurazione profilo:', error);
    showToast('Errore durante la misurazione del profilo', 'error');
  }
}

function measureNoseAngle() {
  console.log('👃 Misurazione angolo naso...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureNoseAngle(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Punti per l'angolo del naso
    const noseBridge = currentLandmarks[6];   // Ponte naso
    const noseTip = currentLandmarks[1];      // Punta naso
    const noseBase = currentLandmarks[2];     // Base naso

    if (noseBridge && noseTip && noseBase) {
      drawMeasurementLine(noseBridge, noseTip, 'Ponte-Punta');
      drawMeasurementLine(noseTip, noseBase, 'Punta-Base');
      showToast('Misurazione angolo naso completata', 'success');
    }

  } catch (error) {
    console.error('❌ Errore misurazione angolo naso:', error);
    showToast('Errore durante la misurazione dell\'angolo del naso', 'error');
  }
}

function measureMouthAngle() {
  console.log('👄 Misurazione angolo bocca...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureMouthAngle(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Punti per l'angolo della bocca
    const leftMouth = currentLandmarks[61];   // Angolo sx bocca
    const rightMouth = currentLandmarks[291]; // Angolo dx bocca
    const topLip = currentLandmarks[13];      // Labbro superiore
    const bottomLip = currentLandmarks[14];   // Labbro inferiore

    if (leftMouth && rightMouth && topLip && bottomLip) {
      drawMeasurementLine(leftMouth, rightMouth, 'Larghezza Bocca');
      drawMeasurementLine(topLip, bottomLip, 'Altezza Bocca');
      showToast('Misurazione angolo bocca completata', 'success');
    }

  } catch (error) {
    console.error('❌ Errore misurazione angolo bocca:', error);
    showToast('Errore durante la misurazione dell\'angolo della bocca', 'error');
  }
}

function measureFaceProportions() {
  console.log('📏 Misurazione proporzioni...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureFaceProportions(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Calcola varie proporzioni
    const faceWidth = calculateDistanceBetweenPoints(currentLandmarks[234], currentLandmarks[454]);
    const faceHeight = calculateDistanceBetweenPoints(currentLandmarks[10], currentLandmarks[152]);
    const eyeDistance = calculateDistanceBetweenPoints(currentLandmarks[33], currentLandmarks[362]);

    const ratio = faceWidth / faceHeight;
    drawMeasurementLine(currentLandmarks[234], currentLandmarks[454], `Larghezza: ${faceWidth.toFixed(1)}mm`);
    drawMeasurementLine(currentLandmarks[10], currentLandmarks[152], `Altezza: ${faceHeight.toFixed(1)}mm`);

    showToast(`Rapporto L/A: ${ratio.toFixed(2)}`, 'success');

  } catch (error) {
    console.error('❌ Errore misurazione proporzioni:', error);
    showToast('Errore durante la misurazione delle proporzioni', 'error');
  }
}

function measureKeyDistances() {
  console.log('🔍 Misurazione distanze chiave...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureKeyDistances(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // NON pulire le misurazioni precedenti - ogni pulsante gestisce il proprio overlay

    // Distanze chiave del viso
    const eyeToNose = calculateDistanceBetweenPoints(currentLandmarks[27], currentLandmarks[1]);
    const noseToMouth = calculateDistanceBetweenPoints(currentLandmarks[1], currentLandmarks[13]);
    const mouthToChin = calculateDistanceBetweenPoints(currentLandmarks[13], currentLandmarks[152]);

    drawMeasurementLine(currentLandmarks[27], currentLandmarks[1], `Occhi-Naso: ${eyeToNose.toFixed(1)}mm`);
    drawMeasurementLine(currentLandmarks[1], currentLandmarks[13], `Naso-Bocca: ${noseToMouth.toFixed(1)}mm`);
    drawMeasurementLine(currentLandmarks[13], currentLandmarks[152], `Bocca-Mento: ${mouthToChin.toFixed(1)}mm`);

    showToast('Distanze chiave misurate', 'success');

  } catch (error) {
    console.error('❌ Errore misurazione distanze chiave:', error);
    showToast('Errore durante la misurazione delle distanze chiave', 'error');
  }
}

// Funzione di supporto per calcolare area poligono
function calculatePolygonAreaFromPoints(points) {
  if (!points || points.length < 3) return 0;

  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length;
    if (points[i] && points[j] &&
      typeof points[i].x === 'number' && typeof points[i].y === 'number' &&
      typeof points[j].x === 'number' && typeof points[j].y === 'number') {
      area += points[i].x * points[j].y;
      area -= points[j].x * points[i].y;
    }
  }

  return Math.abs(area) / 2;
}

// Mantieni anche il nome vecchio per compatibilità con altro codice
function calculatePolygonArea(points) {
  return calculatePolygonAreaFromPoints(points);
}

// === FUNZIONI PER ELABORAZIONE AVANZATA SOPRACCIGLIA ===

/**
 * Calcola la distanza euclidea tra due punti
 * @param {Object} p1 - Primo punto {x, y}
 * @param {Object} p2 - Secondo punto {x, y}
 * @returns {number} Distanza
 */
function calculateDistancePoints(p1, p2) {
  if (!p1 || !p2) {
    console.error('❌ calculateDistance: p1 o p2 null/undefined');
    return 0;
  }

  // Gli oggetti hanno anche z e visibility, ma a noi servono solo x e y
  const x1 = p1.x;
  const y1 = p1.y;
  const x2 = p2.x;
  const y2 = p2.y;

  if (typeof x1 !== 'number' || typeof y1 !== 'number' ||
    typeof x2 !== 'number' || typeof y2 !== 'number') {
    console.error('❌ calculateDistance: coordinate non valide', {
      x1, y1, x2, y2,
      x1Type: typeof x1,
      y1Type: typeof y1,
      x2Type: typeof x2,
      y2Type: typeof y2
    });
    return 0;
  }

  const dx = x2 - x1;
  const dy = y2 - y1;
  const dist = Math.sqrt(dx * dx + dy * dy);

  return dist;
}

/**
 * Calcola il centroide (centro geometrico) di un poligono
 * @param {Array} points - Array di punti {x, y}
 * @returns {Object} Centroide {x, y}
 */
function calculateCentroid(points) {
  if (!points || points.length === 0) return { x: 0, y: 0 };

  let sumX = 0;
  let sumY = 0;

  points.forEach(p => {
    sumX += p.x;
    sumY += p.y;
  });

  return {
    x: sumX / points.length,
    y: sumY / points.length
  };
}

/**
 * Genera il poligono maschera espanso per il sopracciglio sinistro usando 6 punti specifici
 * @param {Array} landmarks - Array completo dei landmarks (coordinate normalizzate)
 * @returns {Array} Array di 6 punti con nome che costituiscono la maschera espansa
 */
function generateLeftEyebrowExpandedMask(landmarks) {
  // Landmarks di riferimento per sopracciglio sinistro
  const lm107 = landmarks[107];
  const lm55 = landmarks[55];
  const lm52 = landmarks[52];
  const lm70 = landmarks[70];
  const lm105 = landmarks[105];

  if (!lm107 || !lm55 || !lm52 || !lm70 || !lm105) {
    console.error('❌ Landmarks mancanti per sopracciglio sinistro');
    return null;
  }

  // Trasforma i landmarks in coordinate canvas
  const lm107Canvas = window.transformLandmarkCoordinate(lm107);
  const lm55Canvas = window.transformLandmarkCoordinate(lm55);
  const lm52Canvas = window.transformLandmarkCoordinate(lm52);
  const lm70Canvas = window.transformLandmarkCoordinate(lm70);
  const lm105Canvas = window.transformLandmarkCoordinate(lm105);

  if (!lm107Canvas || !lm55Canvas || !lm52Canvas || !lm70Canvas || !lm105Canvas) {
    console.error('❌ Errore trasformazione landmarks per sopracciglio sinistro');
    return null;
  }

  // Calcola ALPHA = metà della distanza tra 107 e 55
  const distance107_55 = calculateDistancePoints(lm107Canvas, lm55Canvas);
  const ALPHA = distance107_55 / 2;

  console.log(`📐 SOPRACCIGLIO SINISTRO - ALPHA: ${ALPHA.toFixed(2)}px`);

  if (!isFinite(ALPHA) || ALPHA <= 0) {
    console.error('❌ ALPHA non valido:', ALPHA);
    return null;
  }

  // Genera i 5 punti spostando i landmark di origine usando ALPHA come offset
  // Origine 107: x+ALPHA, y-ALPHA
  const lm107EXT = {
    name: '107EXT',
    x: lm107Canvas.x + ALPHA,
    y: lm107Canvas.y - ALPHA
  };
  console.log(`  ✓ 107EXT: origine(${lm107Canvas.x.toFixed(1)}, ${lm107Canvas.y.toFixed(1)}) + offset(+${ALPHA.toFixed(1)}, -${ALPHA.toFixed(1)}) = (${lm107EXT.x.toFixed(1)}, ${lm107EXT.y.toFixed(1)})`);

  // Origine 55: x+ALPHA, y+ALPHA
  const lm55EXT = {
    name: '55EXT',
    x: lm55Canvas.x + ALPHA,
    y: lm55Canvas.y + ALPHA
  };
  console.log(`  ✓ 55EXT: origine(${lm55Canvas.x.toFixed(1)}, ${lm55Canvas.y.toFixed(1)}) + offset(+${ALPHA.toFixed(1)}, +${ALPHA.toFixed(1)}) = (${lm55EXT.x.toFixed(1)}, ${lm55EXT.y.toFixed(1)})`);

  // Origine 52: x invariata, y+ALPHA
  const lm52EXT = {
    name: '52EXT',
    x: lm52Canvas.x,
    y: lm52Canvas.y + ALPHA
  };
  console.log(`  ✓ 52EXT: origine(${lm52Canvas.x.toFixed(1)}, ${lm52Canvas.y.toFixed(1)}) + offset(0, +${ALPHA.toFixed(1)}) = (${lm52EXT.x.toFixed(1)}, ${lm52EXT.y.toFixed(1)})`);

  // Origine 70: x-ALPHA, y+ALPHA
  const lm70EXT = {
    name: '70EXT',
    x: lm70Canvas.x - ALPHA,
    y: lm70Canvas.y + ALPHA
  };
  console.log(`  ✓ 70EXT: origine(${lm70Canvas.x.toFixed(1)}, ${lm70Canvas.y.toFixed(1)}) + offset(-${ALPHA.toFixed(1)}, +${ALPHA.toFixed(1)}) = (${lm70EXT.x.toFixed(1)}, ${lm70EXT.y.toFixed(1)})`);

  // Origine 105: x-ALPHA, y-ALPHA
  const lm105EXT = {
    name: '105EXT',
    x: lm105Canvas.x - ALPHA,
    y: lm105Canvas.y - ALPHA
  };
  console.log(`  ✓ 105EXT: origine(${lm105Canvas.x.toFixed(1)}, ${lm105Canvas.y.toFixed(1)}) + offset(-${ALPHA.toFixed(1)}, -${ALPHA.toFixed(1)}) = (${lm105EXT.x.toFixed(1)}, ${lm105EXT.y.toFixed(1)})`);

  // Nuovo 6° punto: 70EXT2 calcolato da 70EXT aggiungendo ALPHA a x e y
  const lm70EXT2 = {
    name: '70EXT2',
    x: lm70EXT.x + ALPHA,
    y: lm70EXT.y + ALPHA
  };
  console.log(`  ✓ 70EXT2: origine(${lm70EXT.x.toFixed(1)}, ${lm70EXT.y.toFixed(1)}) + offset(+${ALPHA.toFixed(1)}, +${ALPHA.toFixed(1)}) = (${lm70EXT2.x.toFixed(1)}, ${lm70EXT2.y.toFixed(1)})`);

  return [lm107EXT, lm55EXT, lm52EXT, lm70EXT2, lm70EXT, lm105EXT];
}

/**
 * Genera il poligono maschera espanso per il sopracciglio destro usando 6 punti specifici (speculare)
 * @param {Array} landmarks - Array completo dei landmarks (coordinate normalizzate)
 * @returns {Array} Array di 6 punti con nome che costituiscono la maschera espansa
 */
function generateRightEyebrowExpandedMask(landmarks) {
  // Landmarks di riferimento per sopracciglio destro (speculare)
  const lm336 = landmarks[336];
  const lm285 = landmarks[285];
  const lm282 = landmarks[282];
  const lm300 = landmarks[300];
  const lm334 = landmarks[334];

  if (!lm336 || !lm285 || !lm282 || !lm300 || !lm334) {
    console.error('❌ Landmarks mancanti per sopracciglio destro');
    return null;
  }

  // Trasforma i landmarks in coordinate canvas
  const lm336Canvas = window.transformLandmarkCoordinate(lm336);
  const lm285Canvas = window.transformLandmarkCoordinate(lm285);
  const lm282Canvas = window.transformLandmarkCoordinate(lm282);
  const lm300Canvas = window.transformLandmarkCoordinate(lm300);
  const lm334Canvas = window.transformLandmarkCoordinate(lm334);

  if (!lm336Canvas || !lm285Canvas || !lm282Canvas || !lm300Canvas || !lm334Canvas) {
    console.error('❌ Errore trasformazione landmarks per sopracciglio destro');
    return null;
  }

  // Calcola BETA = metà della distanza tra 336 e 285 (speculare ad ALPHA)
  const distance336_285 = calculateDistancePoints(lm336Canvas, lm285Canvas);
  const BETA = distance336_285 / 2;

  console.log(`📐 SOPRACCIGLIO DESTRO - BETA: ${BETA.toFixed(2)}px`);

  if (!isFinite(BETA) || BETA <= 0) {
    console.error('❌ BETA non valido:', BETA);
    return null;
  }

  // Genera i 5 punti spostando i landmark di origine usando BETA come offset (speculare)
  // Origine 336: x-BETA, y-BETA
  const lm336EXT = {
    name: '336EXT',
    x: lm336Canvas.x - BETA,
    y: lm336Canvas.y - BETA
  };
  console.log(`  ✓ 336EXT: origine(${lm336Canvas.x.toFixed(1)}, ${lm336Canvas.y.toFixed(1)}) + offset(-${BETA.toFixed(1)}, -${BETA.toFixed(1)}) = (${lm336EXT.x.toFixed(1)}, ${lm336EXT.y.toFixed(1)})`);

  // Origine 285: x-BETA, y+BETA
  const lm285EXT = {
    name: '285EXT',
    x: lm285Canvas.x - BETA,
    y: lm285Canvas.y + BETA
  };
  console.log(`  ✓ 285EXT: origine(${lm285Canvas.x.toFixed(1)}, ${lm285Canvas.y.toFixed(1)}) + offset(-${BETA.toFixed(1)}, +${BETA.toFixed(1)}) = (${lm285EXT.x.toFixed(1)}, ${lm285EXT.y.toFixed(1)})`);

  // Origine 282: x invariata, y+BETA
  const lm282EXT = {
    name: '282EXT',
    x: lm282Canvas.x,
    y: lm282Canvas.y + BETA
  };
  console.log(`  ✓ 282EXT: origine(${lm282Canvas.x.toFixed(1)}, ${lm282Canvas.y.toFixed(1)}) + offset(0, +${BETA.toFixed(1)}) = (${lm282EXT.x.toFixed(1)}, ${lm282EXT.y.toFixed(1)})`);

  // Origine 300: x+BETA, y+BETA
  const lm300EXT = {
    name: '300EXT',
    x: lm300Canvas.x + BETA,
    y: lm300Canvas.y + BETA
  };
  console.log(`  ✓ 300EXT: origine(${lm300Canvas.x.toFixed(1)}, ${lm300Canvas.y.toFixed(1)}) + offset(+${BETA.toFixed(1)}, +${BETA.toFixed(1)}) = (${lm300EXT.x.toFixed(1)}, ${lm300EXT.y.toFixed(1)})`);

  // Origine 334: x+BETA, y-BETA
  const lm334EXT = {
    name: '334EXT',
    x: lm334Canvas.x + BETA,
    y: lm334Canvas.y - BETA
  };
  console.log(`  ✓ 334EXT: origine(${lm334Canvas.x.toFixed(1)}, ${lm334Canvas.y.toFixed(1)}) + offset(+${BETA.toFixed(1)}, -${BETA.toFixed(1)}) = (${lm334EXT.x.toFixed(1)}, ${lm334EXT.y.toFixed(1)})`);

  // Nuovo 6° punto: 300EXT2 calcolato da 300EXT sottraendo BETA a x e aggiungendo BETA a y (speculare)
  const lm300EXT2 = {
    name: '300EXT2',
    x: lm300EXT.x - BETA,
    y: lm300EXT.y + BETA
  };
  console.log(`  ✓ 300EXT2: origine(${lm300EXT.x.toFixed(1)}, ${lm300EXT.y.toFixed(1)}) + offset(-${BETA.toFixed(1)}, +${BETA.toFixed(1)}) = (${lm300EXT2.x.toFixed(1)}, ${lm300EXT2.y.toFixed(1)})`);

  return [lm336EXT, lm285EXT, lm282EXT, lm300EXT2, lm300EXT, lm334EXT];
}

/**
 * Converte RGB in LAB (CIELAB color space)
 * @param {number} r - Valore rosso (0-255)
 * @param {number} g - Valore verde (0-255)
 * @param {number} b - Valore blu (0-255)
 * @returns {Object} {L, a, b} Valori LAB
 */
function rgbToLab(r, g, b) {
  // Normalizza RGB a 0-1
  r = r / 255;
  g = g / 255;
  b = b / 255;

  // Converti a linear RGB
  r = r > 0.04045 ? Math.pow((r + 0.055) / 1.055, 2.4) : r / 12.92;
  g = g > 0.04045 ? Math.pow((g + 0.055) / 1.055, 2.4) : g / 12.92;
  b = b > 0.04045 ? Math.pow((b + 0.055) / 1.055, 2.4) : b / 12.92;

  // Converti a XYZ (usando illuminante D65)
  let x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) * 100;
  let y = (r * 0.2126729 + g * 0.7151522 + b * 0.0721750) * 100;
  let z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) * 100;

  // Normalizza per illuminante D65
  x = x / 95.047;
  y = y / 100.000;
  z = z / 108.883;

  // Converti a LAB
  x = x > 0.008856 ? Math.pow(x, 1 / 3) : (7.787 * x + 16 / 116);
  y = y > 0.008856 ? Math.pow(y, 1 / 3) : (7.787 * y + 16 / 116);
  z = z > 0.008856 ? Math.pow(z, 1 / 3) : (7.787 * z + 16 / 116);

  const L = (116 * y) - 16;
  const a = 500 * (x - y);
  const bVal = 200 * (y - z);

  return { L: L, a: a, b: bVal };
}

/**
 * Estrae il bounding box di un poligono
 * @param {Array} points - Array di punti del poligono
 * @returns {Object} {minX, minY, maxX, maxY, width, height}
 */
function getPolygonBoundingBox(points) {
  if (!points || points.length === 0) return null;

  let minX = Infinity, minY = Infinity;
  let maxX = -Infinity, maxY = -Infinity;

  points.forEach(p => {
    // Validazione punto
    if (!p || !isFinite(p.x) || !isFinite(p.y)) {
      console.warn('⚠️ Punto non valido ignorato:', p);
      return;
    }

    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  });

  // Verifica che abbiamo trovato valori validi
  if (!isFinite(minX) || !isFinite(minY) || !isFinite(maxX) || !isFinite(maxY)) {
    console.error('❌ Impossibile calcolare bounding box, tutti i punti non validi');
    return null;
  }

  return {
    minX: Math.floor(minX),
    minY: Math.floor(minY),
    maxX: Math.ceil(maxX),
    maxY: Math.ceil(maxY),
    width: Math.ceil(maxX - minX),
    height: Math.ceil(maxY - minY)
  };
}

/**
 * Verifica se un punto è all'interno di un poligono (Ray casting algorithm)
 * @param {Object} point - Punto {x, y}
 * @param {Array} polygon - Array di punti del poligono
 * @returns {boolean}
 */
function isPointInPolygon(point, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y;
    const xj = polygon[j].x, yj = polygon[j].y;

    const intersect = ((yi > point.y) !== (yj > point.y))
      && (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

/**
 * Estrae i pixel dell'immagine all'interno di una maschera poligonale e li binarizza
 * con threshold adattivo basato sulla luminosità media
 * @param {Array} maskPolygon - Poligono della maschera (già scalato)
 * @param {fabric.Image} canvasImage - Immagine del canvas
 * @returns {Object} {pixels: Array2D, bbox: Object, binaryMask: Array2D, adaptiveThreshold: number}
 */
function extractAndBinarizeImageRegion(maskPolygon, canvasImage, landmarkReferences) {
  // Usa tolleranza predefinita di 120
  return extractAndBinarizeImageRegionWithTolerance(maskPolygon, canvasImage, landmarkReferences, 120);
}

/**
 * Estrae e binarizza con tolleranza personalizzata (per uso dinamico)
 * @param {Array} maskPolygon - Poligono della maschera
 * @param {fabric.Image} canvasImage - Immagine del canvas
 * @param {Object} landmarkReferences - Riferimenti ai landmarks
 * @param {number} customTolerance - Tolleranza Magic Wand personalizzata
 * @returns {Object} Dati della regione estratta
 */
function extractAndBinarizeImageRegionWithTolerance(maskPolygon, canvasImage, landmarkReferences, customTolerance) {
  if (!maskPolygon || !canvasImage || !landmarkReferences) return null;

  try {
    // Validazione poligono
    const isValid = maskPolygon.every(p =>
      p && typeof p.x === 'number' && isFinite(p.x) && typeof p.y === 'number' && isFinite(p.y)
    );
    if (!isValid) {
      console.error('❌ Poligono non valido:', maskPolygon);
      return null;
    }

    // Ottieni immagine completa dal canvas
    const imgElement = canvasImage.getElement();
    const scaleX = canvasImage.scaleX || 1;
    const scaleY = canvasImage.scaleY || 1;

    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = fabricCanvas.width;
    tempCanvas.height = fabricCanvas.height;
    const tempCtx = tempCanvas.getContext('2d');

    // Renderizza l'immagine tenendo conto di posizione, scala E rotazione
    // (come fa transformLandmarkCoordinate) per allineamento corretto dei landmark
    const drawW = imgElement.width * scaleX;
    const drawH = imgElement.height * scaleY;
    const imgAngle = canvasImage.angle || 0;
    if (imgAngle !== 0) {
      const center = canvasImage.getCenterPoint();
      tempCtx.save();
      tempCtx.translate(center.x, center.y);
      tempCtx.rotate(imgAngle * Math.PI / 180);
      tempCtx.drawImage(imgElement, -drawW / 2, -drawH / 2, drawW, drawH);
      tempCtx.restore();
    } else {
      tempCtx.drawImage(imgElement, canvasImage.left || 0, canvasImage.top || 0, drawW, drawH);
    }

    const imageData = tempCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);
    const pixels = imageData.data;
    const canvasWidth = tempCanvas.width;
    const canvasHeight = tempCanvas.height;

    console.log(`🖼️ Canvas: ${canvasWidth}x${canvasHeight}px`);

    // 1. APPLICAZIONE CONTRASTO (DISABILITATO - interferisce con Magic Wand)
    // console.log('🎨 Applicazione contrasto x2.0...');
    // const contrastFactor = 2.0;
    console.log('🎨 Contrasto disabilitato - uso colori originali per Magic Wand');

    // Calcola bounds del poligono
    const xs = maskPolygon.map(p => p.x);
    const ys = maskPolygon.map(p => p.y);
    const minX = Math.max(0, Math.floor(Math.min(...xs)));
    const maxX = Math.min(canvasWidth - 1, Math.ceil(Math.max(...xs)));
    const minY = Math.max(0, Math.floor(Math.min(...ys)));
    const maxY = Math.min(canvasHeight - 1, Math.ceil(Math.max(...ys)));

    // CONTRASTO DISABILITATO - lascia i pixel originali
    // for (let y = minY; y <= maxY; y++) {
    //   for (let x = minX; x <= maxX; x++) {
    //     if (isPointInPolygon({x, y}, maskPolygon)) {
    //       const idx = (y * canvasWidth + x) * 4;
    //       const r = pixels[idx];
    //       const g = pixels[idx + 1];
    //       const b = pixels[idx + 2];
    //       
    //       // Applica contrasto
    //       const rNew = Math.max(0, Math.min(255, ((r/255 - 0.5) * contrastFactor + 0.5) * 255));
    //       const gNew = Math.max(0, Math.min(255, ((g/255 - 0.5) * contrastFactor + 0.5) * 255));
    //       const bNew = Math.max(0, Math.min(255, ((b/255 - 0.5) * contrastFactor + 0.5) * 255));
    //       
    //       pixels[idx] = rNew;
    //       pixels[idx + 1] = gNew;
    //       pixels[idx + 2] = bNew;
    //     }
    //   }
    // }

    // 2. BINARIZZAZIONE CON MAGIC WAND (selezione basata su colore seed)
    console.log('🪄 Binarizzazione Magic Wand...');

    // Calcola seed point (centro tra lm107 e lm107ext - zona pelle)
    const seedX = Math.floor((landmarkReferences.lm107.x + landmarkReferences.lm107ext.x) / 2);
    const seedY = Math.floor((landmarkReferences.lm107.y + landmarkReferences.lm107ext.y) / 2);

    // Campiona colore seed (pattern 2x2)
    let seedR = 0, seedG = 0, seedB = 0, seedCount = 0;
    for (let dy = 0; dy < 2; dy++) {
      for (let dx = 0; dx < 2; dx++) {
        const sx = seedX + dx;
        const sy = seedY + dy;
        if (sx >= 0 && sx < canvasWidth && sy >= 0 && sy < canvasHeight) {
          const idx = (sy * canvasWidth + sx) * 4;
          seedR += pixels[idx];
          seedG += pixels[idx + 1];
          seedB += pixels[idx + 2];
          seedCount++;
        }
      }
    }
    seedR /= seedCount;
    seedG /= seedCount;
    seedB /= seedCount;

    console.log(`   Seed @ (${seedX}, ${seedY}): RGB(${seedR.toFixed(0)}, ${seedG.toFixed(0)}, ${seedB.toFixed(0)})`);

    // Tolleranza Magic Wand (distanza euclidea nello spazio RGB)
    const tolerance = customTolerance || 120;
    console.log(`   Tolleranza: ${tolerance}`);

    // Selezione pixel pelle (sfondo) con Magic Wand
    const binaryMask = [];
    for (let y = 0; y < canvasHeight; y++) {
      binaryMask[y] = [];
      for (let x = 0; x < canvasWidth; x++) {
        binaryMask[y][x] = 0;
      }
    }

    let pixelsSkin = 0;
    let pixelsEyebrow = 0;

    for (let y = minY; y <= maxY; y++) {
      for (let x = minX; x <= maxX; x++) {
        if (isPointInPolygon({ x, y }, maskPolygon)) {
          const idx = (y * canvasWidth + x) * 4;
          const r = pixels[idx];
          const g = pixels[idx + 1];
          const b = pixels[idx + 2];

          // Calcola distanza euclidea dal colore seed
          const dr = r - seedR;
          const dg = g - seedG;
          const db = b - seedB;
          const distance = Math.sqrt(dr * dr + dg * dg + db * db);

          // Se distanza <= tolleranza → è pelle (sfondo)
          // Altrimenti → è sopracciglio (inversione)
          if (distance > tolerance) {
            binaryMask[y][x] = 1;
            pixelsEyebrow++;
          } else {
            pixelsSkin++;
          }
        }
      }
    }
    console.log(`   Pixel pelle (sfondo): ${pixelsSkin}`);
    console.log(`   Pixel sopracciglio: ${pixelsEyebrow}`);

    // 3. MORFOLOGIA: 1 DILATAZIONE
    console.log('🔧 Morfologia: 1 dilatazione...');
    for (let iter = 0; iter < 1; iter++) {
      const dilated = [];
      for (let y = 0; y < canvasHeight; y++) {
        dilated[y] = [];
        for (let x = 0; x < canvasWidth; x++) {
          dilated[y][x] = 0;
        }
      }

      for (let y = 1; y < canvasHeight - 1; y++) {
        for (let x = 1; x < canvasWidth - 1; x++) {
          if (binaryMask[y][x] === 1 ||
            binaryMask[y - 1][x] === 1 || binaryMask[y + 1][x] === 1 ||
            binaryMask[y][x - 1] === 1 || binaryMask[y][x + 1] === 1 ||
            binaryMask[y - 1][x - 1] === 1 || binaryMask[y - 1][x + 1] === 1 ||
            binaryMask[y + 1][x - 1] === 1 || binaryMask[y + 1][x + 1] === 1) {
            dilated[y][x] = 1;
          }
        }
      }

      for (let y = 0; y < canvasHeight; y++) {
        for (let x = 0; x < canvasWidth; x++) {
          binaryMask[y][x] = dilated[y][x];
        }
      }
    }

    // 4. MORFOLOGIA: 1 EROSIONE
    console.log('🔧 Morfologia: 1 erosione...');
    for (let iter = 0; iter < 1; iter++) {
      const eroded = [];
      for (let y = 0; y < canvasHeight; y++) {
        eroded[y] = [];
        for (let x = 0; x < canvasWidth; x++) {
          eroded[y][x] = 0;
        }
      }

      for (let y = 1; y < canvasHeight - 1; y++) {
        for (let x = 1; x < canvasWidth - 1; x++) {
          if (binaryMask[y][x] === 1 &&
            binaryMask[y - 1][x] === 1 && binaryMask[y + 1][x] === 1 &&
            binaryMask[y][x - 1] === 1 && binaryMask[y][x + 1] === 1 &&
            binaryMask[y - 1][x - 1] === 1 && binaryMask[y - 1][x + 1] === 1 &&
            binaryMask[y + 1][x - 1] === 1 && binaryMask[y + 1][x + 1] === 1) {
            eroded[y][x] = 1;
          }
        }
      }

      for (let y = 0; y < canvasHeight; y++) {
        for (let x = 0; x < canvasWidth; x++) {
          binaryMask[y][x] = eroded[y][x];
        }
      }
    }
    console.log('✅ Morfologia applicata - 1 dilatazione + 1 erosione');

    return {
      binaryMask: binaryMask,
      imageData: imageData,
      canvasWidth: canvasWidth,
      canvasHeight: canvasHeight,
      adaptiveThreshold: 0,
      seedColor: { r: seedR, g: seedG, b: seedB },
      tolerance: tolerance
    };

  } catch (error) {
    console.error('❌ Errore estrazione regione:', error);
    return null;
  }
}

/**
 * Crea un poligono overlay basato sui pixel reali binarizzati
 * @param {Object} regionData - Dati della regione {bbox, binaryMask}
 * @param {string} label - Etichetta
 * @param {string} color - Colore
 * @returns {fabric.Polygon} Poligono creato
 */
function createPolygonFromBinaryMask(regionData, label, color = '#FF6B35') {
  if (!regionData || !regionData.binaryMask) return null;

  try {
    const { binaryMask, canvasWidth, canvasHeight } = regionData;

    console.log(`🔬 Inizio elaborazione morfologica per ${label}`);

    // FASE 1: Rimuovi componenti piccole (noise)
    const cleanedMask = removeSmallComponents(binaryMask);
    console.log('✅ Pixel sparsi rimossi');

    // FASE 2: Mantieni solo il componente più grande (sopracciglio centrale)
    const largestComponentMask = keepLargestComponent(cleanedMask);
    console.log('✅ Mantenuto solo componente centrale');

    // FASE 3: Nessuna operazione morfologica - preserva forma originale precisa
    // Con il preprocessing a contrasto elevato, la maschera binaria è già precisa
    const finalMask = largestComponentMask;
    console.log('✅ Forma originale preservata (nessuna morfologia applicata)');

    // Traccia il contorno con algoritmo Moore-Neighbor
    const contourPoints = traceMooreNeighborContour(finalMask, canvasWidth, canvasHeight);

    if (contourPoints.length < 3) {
      console.warn('⚠️ Troppo pochi punti contorno');
      return null;
    }

    // Semplificazione contorno più aggressiva
    const simplificationFactor = Math.max(2, Math.floor(contourPoints.length / 100));
    const simplifiedPoints = contourPoints.filter((_, idx) => idx % simplificationFactor === 0);

    console.log(`📐 Contorno: ${contourPoints.length} → ${simplifiedPoints.length} punti`);

    // Crea il poligono
    const fabricPoints = simplifiedPoints.map(p => ({ x: p.x, y: p.y }));

    const polygon = new fabric.Polygon(fabricPoints, {
      fill: color + '40',
      stroke: color,
      strokeWidth: 2,
      selectable: false,
      evented: false,
      isAreaPolygon: true,
      measurementType: label
    });

    // NON aggiungere al canvas qui - lascia che il chiamante lo faccia
    // fabricCanvas.add(polygon);
    // fabricCanvas.bringToFront(polygon);

    return polygon;

  } catch (error) {
    console.error('❌ Errore creazione poligono:', error);
    return null;
  }
}

// === OPERAZIONI MORFOLOGICHE ===

/**
 * Traccia il contorno esterno con algoritmo Moore-Neighbor
 * @param {Array2D} mask - Maschera binaria
 * @param {number} canvasWidth - Larghezza canvas
 * @param {number} canvasHeight - Altezza canvas
 * @returns {Array} Punti del contorno in ordine
 */
function traceMooreNeighborContour(mask, canvasWidth, canvasHeight) {
  const height = mask.length;
  const width = mask[0].length;

  // Trova il primo pixel nero (partenza)
  let startX = -1, startY = -1;

  outerLoop:
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (mask[y][x] === 1) {
        startX = x;
        startY = y;
        break outerLoop;
      }
    }
  }

  if (startX === -1) {
    console.warn('⚠️ Nessun pixel nero trovato nella maschera');
    return [];
  }

  // Direzioni: N, NE, E, SE, S, SW, W, NW (senso orario)
  const directions = [
    [0, -1], [1, -1], [1, 0], [1, 1],
    [0, 1], [-1, 1], [-1, 0], [-1, -1]
  ];

  const contour = [];
  let currentX = startX;
  let currentY = startY;
  let dir = 7; // Inizia guardando a NW

  let iterations = 0;
  const maxIterations = width * height; // Sicurezza per evitare loop infiniti

  do {
    contour.push({
      x: currentX,
      y: currentY
    });

    // Moore-Neighbor: cerca il prossimo pixel nero in senso orario
    let found = false;

    for (let i = 0; i < 8; i++) {
      const checkDir = (dir + i) % 8;
      const [dx, dy] = directions[checkDir];
      const nextX = currentX + dx;
      const nextY = currentY + dy;

      // Verifica bounds
      if (nextX >= 0 && nextX < width && nextY >= 0 && nextY < height) {
        if (mask[nextY][nextX] === 1) {
          // Trovato il prossimo pixel
          currentX = nextX;
          currentY = nextY;
          dir = (checkDir + 6) % 8; // Gira a sinistra per il prossimo giro
          found = true;
          break;
        }
      }
    }

    if (!found) break; // Nessun vicino trovato

    iterations++;

    // Chiude il loop quando torna al punto di partenza
  } while ((currentX !== startX || currentY !== startY) && iterations < maxIterations);

  console.log(`🔄 Contorno tracciato: ${contour.length} punti (${iterations} iterazioni)`);

  return contour;
}

/**
 * Rimuove componenti connesse piccole (noise)
 * @param {Array2D} mask - Maschera binaria
 * @param {number} minSize - Dimensione minima componente (default 300 pixel)
 * @returns {Array2D} Maschera pulita
 */
function removeSmallComponents(mask, minSize = 300) {
  const height = mask.length;
  const width = mask[0].length;
  const labels = Array(height).fill(0).map(() => Array(width).fill(0));
  const componentSizes = {};
  let currentLabel = 1;

  // Connected component labeling (flood fill)
  function floodFill(startY, startX, label) {
    const stack = [[startY, startX]];
    let size = 0;

    while (stack.length > 0) {
      const [y, x] = stack.pop();

      if (y < 0 || y >= height || x < 0 || x >= width) continue;
      if (mask[y][x] === 0 || labels[y][x] !== 0) continue;

      labels[y][x] = label;
      size++;

      // 8-connectivity
      stack.push([y - 1, x], [y + 1, x], [y, x - 1], [y, x + 1]);
      stack.push([y - 1, x - 1], [y - 1, x + 1], [y + 1, x - 1], [y + 1, x + 1]);
    }

    return size;
  }

  // Etichetta tutte le componenti
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (mask[y][x] === 1 && labels[y][x] === 0) {
        const size = floodFill(y, x, currentLabel);
        componentSizes[currentLabel] = size;
        currentLabel++;
      }
    }
  }

  // Crea maschera pulita (rimuovi componenti piccole)
  const cleanedMask = Array(height).fill(0).map(() => Array(width).fill(0));

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const label = labels[y][x];
      if (label > 0 && componentSizes[label] >= minSize) {
        cleanedMask[y][x] = 1;
      }
    }
  }

  console.log(`🧹 Componenti trovate: ${currentLabel - 1}, rimosse quelle < ${minSize} pixel`);

  return cleanedMask;
}

/**
 * Mantiene solo la componente connessa più grande
 * @param {Array2D} mask - Maschera binaria
 * @returns {Array2D} Maschera con solo componente principale
 */
function keepLargestComponent(mask) {
  const height = mask.length;
  const width = mask[0].length;
  const labels = Array(height).fill(0).map(() => Array(width).fill(0));
  const componentSizes = {};
  let currentLabel = 1;

  // Connected component labeling
  function floodFill(startY, startX, label) {
    const stack = [[startY, startX]];
    let size = 0;

    while (stack.length > 0) {
      const [y, x] = stack.pop();

      if (y < 0 || y >= height || x < 0 || x >= width) continue;
      if (mask[y][x] === 0 || labels[y][x] !== 0) continue;

      labels[y][x] = label;
      size++;

      stack.push([y - 1, x], [y + 1, x], [y, x - 1], [y, x + 1]);
      stack.push([y - 1, x - 1], [y - 1, x + 1], [y + 1, x - 1], [y + 1, x + 1]);
    }

    return size;
  }

  // Etichetta tutte le componenti
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (mask[y][x] === 1 && labels[y][x] === 0) {
        const size = floodFill(y, x, currentLabel);
        componentSizes[currentLabel] = size;
        currentLabel++;
      }
    }
  }

  // Trova la componente più grande
  let largestLabel = 0;
  let largestSize = 0;

  for (const [label, size] of Object.entries(componentSizes)) {
    if (size > largestSize) {
      largestSize = size;
      largestLabel = parseInt(label);
    }
  }

  // Crea maschera con solo la componente più grande
  const resultMask = Array(height).fill(0).map(() => Array(width).fill(0));

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (labels[y][x] === largestLabel) {
        resultMask[y][x] = 1;
      }
    }
  }

  console.log(`🎯 Componente più grande: ${largestSize} pixel (label ${largestLabel})`);

  return resultMask;
}

/**
 * Smoothing del contorno usando Moving Average per livellare i bordi
 * @param {Array} points - Array di punti {x, y}
 * @param {number} windowSize - Dimensione finestra (deve essere dispari, es. 3, 5, 7)
 * @returns {Array} Array di punti smoothati
 */
function smoothContourMovingAverage(points, windowSize = 5) {
  if (points.length < 3) return points;

  // Assicura che windowSize sia dispari
  if (windowSize % 2 === 0) windowSize++;

  const halfWindow = Math.floor(windowSize / 2);
  const smoothed = [];

  for (let i = 0; i < points.length; i++) {
    let sumX = 0, sumY = 0;
    let count = 0;

    // Media mobile circolare (considera il contorno come un loop chiuso)
    for (let j = -halfWindow; j <= halfWindow; j++) {
      const idx = (i + j + points.length) % points.length;
      sumX += points[idx].x;
      sumY += points[idx].y;
      count++;
    }

    smoothed.push({
      x: sumX / count,
      y: sumY / count
    });
  }

  return smoothed;
}

/**
 * Dilatazione morfologica (espande le regioni nere)
 * @param {Array2D} mask - Maschera binaria
 * @param {number} iterations - Numero di iterazioni
 * @returns {Array2D} Maschera dilatata
 */
function morphologicalDilation(mask, iterations = 1) {
  let result = mask.map(row => [...row]); // Copia

  for (let iter = 0; iter < iterations; iter++) {
    const temp = result.map(row => [...row]);

    for (let y = 1; y < result.length - 1; y++) {
      for (let x = 1; x < result[y].length - 1; x++) {
        // Se almeno un vicino è nero, diventa nero
        if (
          result[y - 1][x] === 1 || result[y + 1][x] === 1 ||
          result[y][x - 1] === 1 || result[y][x + 1] === 1 ||
          result[y - 1][x - 1] === 1 || result[y - 1][x + 1] === 1 ||
          result[y + 1][x - 1] === 1 || result[y + 1][x + 1] === 1
        ) {
          temp[y][x] = 1;
        }
      }
    }

    result = temp;
  }

  return result;
}

/**
 * Erosione morfologica (riduce le regioni nere)
 * @param {Array2D} mask - Maschera binaria
 * @param {number} iterations - Numero di iterazioni
 * @returns {Array2D} Maschera erosa
 */
function morphologicalErosion(mask, iterations = 1) {
  let result = mask.map(row => [...row]); // Copia

  for (let iter = 0; iter < iterations; iter++) {
    const temp = result.map(row => [...row]);

    for (let y = 1; y < result.length - 1; y++) {
      for (let x = 1; x < result[y].length - 1; x++) {
        // Se almeno un vicino è bianco, diventa bianco
        if (
          result[y - 1][x] === 0 || result[y + 1][x] === 0 ||
          result[y][x - 1] === 0 || result[y][x + 1] === 0 ||
          result[y - 1][x - 1] === 0 || result[y - 1][x + 1] === 0 ||
          result[y + 1][x - 1] === 0 || result[y + 1][x + 1] === 0
        ) {
          temp[y][x] = 0;
        }
      }
    }

    result = temp;
  }

  return result;
}

// === FUNZIONI DEBUG VISUALIZZAZIONE ===

/**
 * Pulisce tutti gli oggetti di debug dal canvas
 */
function clearEyebrowDebugObjects() {
  if (!fabricCanvas) return;

  eyebrowDebugObjects.forEach(obj => {
    fabricCanvas.remove(obj);
  });
  eyebrowDebugObjects = [];
  labelBoundingBoxes = []; // Reset bounding boxes
  fabricCanvas.renderAll();
}

/**
 * Verifica se due bounding box si sovrappongono
 * @param {Object} bbox1 - {left, top, width, height}
 * @param {Object} bbox2 - {left, top, width, height}
 * @returns {boolean}
 */
function checkBBoxCollision(bbox1, bbox2) {
  return !(bbox1.left + bbox1.width < bbox2.left ||
    bbox2.left + bbox2.width < bbox1.left ||
    bbox1.top + bbox1.height < bbox2.top ||
    bbox2.top + bbox2.height < bbox1.top);
}

/**
 * Trova una posizione libera per un'etichetta lungo una direzione verticale
 * @param {number} x - Posizione x dell'etichetta
 * @param {number} baseY - Posizione y iniziale
 * @param {number} width - Larghezza etichetta
 * @param {number} height - Altezza etichetta
 * @param {number} direction - 1 per verso basso, -1 per verso alto
 * @param {number} step - Passo di incremento (default 15px)
 * @returns {number} - Y position libera
 */
function findFreeVerticalPosition(x, baseY, width, height, direction = 1, step = 15) {
  const margin = 5; // Margine di sicurezza
  let currentY = baseY;
  let attempts = 0;
  const maxAttempts = 50;

  while (attempts < maxAttempts) {
    const testBBox = {
      left: x - margin,
      top: currentY - margin,
      width: width + 2 * margin,
      height: height + 2 * margin
    };

    // Verifica collisioni con tutte le bounding box esistenti
    let collision = false;
    for (let existingBBox of labelBoundingBoxes) {
      if (checkBBoxCollision(testBBox, existingBBox)) {
        collision = true;
        break;
      }
    }

    if (!collision) {
      // Posizione libera trovata, registra la bounding box
      labelBoundingBoxes.push(testBBox);
      return currentY;
    }

    // Prova posizione successiva
    currentY += step * direction;
    attempts++;
  }

  // Se non trova posizione libera, usa l'ultima tentata
  const finalBBox = {
    left: x - margin,
    top: currentY - margin,
    width: width + 2 * margin,
    height: height + 2 * margin
  };
  labelBoundingBoxes.push(finalBBox);
  return currentY;
}

/**
 * Visualizza il perimetro del poligono generato dai landmarks sopraccigliari
 * @param {Array} landmarkPolygon - Poligono dei landmarks (coordinate canvas)
 * @param {Array} landmarkIndices - Array degli indici dei landmarks
 * @param {string} side - 'left' o 'right'
 */
function drawLandmarkPolygonDebug(landmarkPolygon, landmarkIndices, side) {
  if (!eyebrowDebugMode || !fabricCanvas || !landmarkPolygon) return;
  if (!debugVisibility.landmarkPolygons) return;

  const color = side === 'left' ? '#FF9500' : '#FF00FF'; // Arancione per sinistro, magenta per destro

  // Disegna solo il poligono landmarks (senza ID per evitare sovrapposizioni)
  const fabricPoints = landmarkPolygon.map(p => ({ x: p.x, y: p.y }));

  const landmarkOverlay = new fabric.Polyline(fabricPoints, {
    fill: 'transparent',
    stroke: color,
    strokeWidth: 2,
    strokeDashArray: [3, 3],
    selectable: false,
    evented: false,
    isDebugObject: true,
    debugType: 'landmarkPolygon'
  });

  fabricCanvas.add(landmarkOverlay);
  eyebrowDebugObjects.push(landmarkOverlay);

  console.log(`🐛 DEBUG: Perimetro landmarks ${side} visualizzato (${landmarkPolygon.length} punti)`);
}

/**
 * Visualizza graficamente come vengono calcolati i punti EXT partendo dai landmarks
 * @param {Array} landmarks - Array completo dei landmarks
 * @param {string} side - 'left' o 'right'
 */
function drawOffsetDebug(landmarks, side) {
  if (!eyebrowDebugMode || !fabricCanvas || !landmarks) return;
  if (!debugVisibility.scaledMasks) return;

  const color = side === 'left' ? '#00FF00' : '#00FFFF';

  if (side === 'left') {
    // Landmarks di riferimento per sopracciglio sinistro
    const lm107 = landmarks[107];
    const lm55 = landmarks[55];
    const lm52 = landmarks[52];
    const lm70 = landmarks[70];
    const lm105 = landmarks[105];

    if (!lm107 || !lm55 || !lm52 || !lm70 || !lm105) return;

    // Trasforma in coordinate canvas
    const lm107Canvas = window.transformLandmarkCoordinate(lm107);
    const lm55Canvas = window.transformLandmarkCoordinate(lm55);
    const lm52Canvas = window.transformLandmarkCoordinate(lm52);
    const lm70Canvas = window.transformLandmarkCoordinate(lm70);
    const lm105Canvas = window.transformLandmarkCoordinate(lm105);

    // Calcola ALPHA
    const distance107_55 = calculateDistancePoints(lm107Canvas, lm55Canvas);
    const ALPHA = distance107_55 / 2;

    // Array di landmark origine -> punto EXT con offset
    const offsets = [
      { origin: lm107Canvas, originId: 107, offsetX: ALPHA, offsetY: -ALPHA, extName: '107EXT' },
      { origin: lm55Canvas, originId: 55, offsetX: ALPHA, offsetY: ALPHA, extName: '55EXT' },
      { origin: lm52Canvas, originId: 52, offsetX: 0, offsetY: ALPHA, extName: '52EXT' },
      { origin: lm70Canvas, originId: 70, offsetX: -ALPHA, offsetY: ALPHA, extName: '70EXT' },
      { origin: lm105Canvas, originId: 105, offsetX: -ALPHA, offsetY: -ALPHA, extName: '105EXT' }
    ];

    offsets.forEach(({ origin, originId, offsetX, offsetY, extName }) => {
      const extPoint = { x: origin.x + offsetX, y: origin.y + offsetY };

      // Cerchio landmark origine (giallo)
      const originCircle = new fabric.Circle({
        left: origin.x,
        top: origin.y,
        radius: 3,
        fill: '#FFFF00',
        stroke: '#000000',
        strokeWidth: 1,
        originX: 'center',
        originY: 'center',
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(originCircle);
      eyebrowDebugObjects.push(originCircle);

      // Etichetta con ID e coordinate assolute - SOTTO il punto (direzione verticale)
      const idLabelText = `LM${originId}\n(${Math.round(origin.x)},${Math.round(origin.y)})`;

      // Stima dimensioni etichetta
      const estimatedWidth = 50;
      const estimatedHeight = 25;

      // Posizione base: sotto il punto
      const baseY = origin.y + 20;
      const labelX = origin.x - estimatedWidth / 2;

      // Trova posizione libera verticalmente verso il basso
      const labelY = findFreeVerticalPosition(labelX, baseY, estimatedWidth, estimatedHeight, 1, 12);

      // Linea di collegamento tra punto e etichetta ID
      const labelConnector = new fabric.Line([origin.x, origin.y, origin.x, labelY], {
        stroke: '#FFFF00',
        strokeWidth: 0.5,
        opacity: 0.5,
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(labelConnector);
      eyebrowDebugObjects.push(labelConnector);

      const idLabel = new fabric.Text(idLabelText, {
        left: labelX,
        top: labelY,
        fontSize: 8,
        fill: '#FFFF00',
        fontWeight: 'bold',
        backgroundColor: 'rgba(0,0,0,0.85)',
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(idLabel);
      eyebrowDebugObjects.push(idLabel);

      // Freccia dall'origine al punto EXT
      const arrow = new fabric.Line([origin.x, origin.y, extPoint.x, extPoint.y], {
        stroke: color,
        strokeWidth: 1,
        strokeDashArray: [3, 2],
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(arrow);
      eyebrowDebugObjects.push(arrow);
    });

    // Aggiungi etichetta con valore ALPHA
    const alphaLabel = new fabric.Text(`ALPHA = ${ALPHA.toFixed(1)}px`, {
      left: lm105Canvas.x - 30,
      top: lm105Canvas.y + 15,
      fontSize: 11,
      fill: '#FFFF00',
      fontWeight: 'bold',
      backgroundColor: 'rgba(0,0,0,0.9)',
      selectable: false,
      evented: false,
      isDebugObject: true,
      debugType: 'offsetDebug'
    });
    fabricCanvas.add(alphaLabel);
    eyebrowDebugObjects.push(alphaLabel);

  } else {
    // Landmarks di riferimento per sopracciglio destro (speculare)
    const lm336 = landmarks[336];
    const lm285 = landmarks[285];
    const lm282 = landmarks[282];
    const lm300 = landmarks[300];
    const lm334 = landmarks[334];

    if (!lm336 || !lm285 || !lm282 || !lm300 || !lm334) return;

    // Trasforma in coordinate canvas
    const lm336Canvas = window.transformLandmarkCoordinate(lm336);
    const lm285Canvas = window.transformLandmarkCoordinate(lm285);
    const lm282Canvas = window.transformLandmarkCoordinate(lm282);
    const lm300Canvas = window.transformLandmarkCoordinate(lm300);
    const lm334Canvas = window.transformLandmarkCoordinate(lm334);

    // Calcola BETA
    const distance336_285 = calculateDistancePoints(lm336Canvas, lm285Canvas);
    const BETA = distance336_285 / 2;

    // Array di landmark origine -> punto EXT con offset (speculare)
    const offsets = [
      { origin: lm336Canvas, originId: 336, offsetX: -BETA, offsetY: -BETA, extName: '336EXT' },
      { origin: lm285Canvas, originId: 285, offsetX: -BETA, offsetY: BETA, extName: '285EXT' },
      { origin: lm282Canvas, originId: 282, offsetX: 0, offsetY: BETA, extName: '282EXT' },
      { origin: lm300Canvas, originId: 300, offsetX: BETA, offsetY: BETA, extName: '300EXT' },
      { origin: lm334Canvas, originId: 334, offsetX: BETA, offsetY: -BETA, extName: '334EXT' }
    ];

    offsets.forEach(({ origin, originId, offsetX, offsetY, extName }) => {
      const extPoint = { x: origin.x + offsetX, y: origin.y + offsetY };

      // Cerchio landmark origine (giallo)
      const originCircle = new fabric.Circle({
        left: origin.x,
        top: origin.y,
        radius: 3,
        fill: '#FFFF00',
        stroke: '#000000',
        strokeWidth: 1,
        originX: 'center',
        originY: 'center',
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(originCircle);
      eyebrowDebugObjects.push(originCircle);

      // Etichetta con ID e coordinate assolute - SOTTO il punto (direzione verticale)
      const idLabelText = `LM${originId}\n(${Math.round(origin.x)},${Math.round(origin.y)})`;

      // Stima dimensioni etichetta
      const estimatedWidth = 50;
      const estimatedHeight = 25;

      // Posizione base: sotto il punto
      const baseY = origin.y + 20;
      const labelX = origin.x - estimatedWidth / 2;

      // Trova posizione libera verticalmente verso il basso
      const labelY = findFreeVerticalPosition(labelX, baseY, estimatedWidth, estimatedHeight, 1, 12);

      // Linea di collegamento tra punto e etichetta ID
      const labelConnector = new fabric.Line([origin.x, origin.y, origin.x, labelY], {
        stroke: '#FFFF00',
        strokeWidth: 0.5,
        opacity: 0.5,
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(labelConnector);
      eyebrowDebugObjects.push(labelConnector);

      const idLabel = new fabric.Text(idLabelText, {
        left: labelX,
        top: labelY,
        fontSize: 8,
        fill: '#FFFF00',
        fontWeight: 'bold',
        backgroundColor: 'rgba(0,0,0,0.85)',
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(idLabel);
      eyebrowDebugObjects.push(idLabel);

      // Freccia dall'origine al punto EXT
      const arrow = new fabric.Line([origin.x, origin.y, extPoint.x, extPoint.y], {
        stroke: color,
        strokeWidth: 1,
        strokeDashArray: [3, 2],
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'offsetDebug'
      });
      fabricCanvas.add(arrow);
      eyebrowDebugObjects.push(arrow);
    });

    // Aggiungi etichetta con valore BETA
    const betaLabel = new fabric.Text(`BETA = ${BETA.toFixed(1)}px`, {
      left: lm334Canvas.x - 30,
      top: lm334Canvas.y + 15,
      fontSize: 11,
      fill: '#FFFF00',
      fontWeight: 'bold',
      backgroundColor: 'rgba(0,0,0,0.9)',
      selectable: false,
      evented: false,
      isDebugObject: true,
      debugType: 'offsetDebug'
    });
    fabricCanvas.add(betaLabel);
    eyebrowDebugObjects.push(betaLabel);
  }

  console.log(`🐛 DEBUG: Offset visualizzati per ${side}`);
}

/**
 * Visualizza la maschera espansa (5 punti) nel debug
 * @param {Array} expandedPolygon - Poligono espanso a 5 punti
 * @param {string} side - 'left' o 'right'
 */
function drawExpandedMaskDebug(expandedPolygon, side) {
  if (!eyebrowDebugMode || !fabricCanvas || !expandedPolygon) return;
  if (!debugVisibility.scaledMasks) return;

  const color = side === 'left' ? '#00FF00' : '#00FFFF'; // Verde per sx, Ciano per dx

  // Disegna il poligono espanso
  const expandedPoly = new fabric.Polygon(expandedPolygon, {
    fill: color + '30',
    stroke: color,
    strokeWidth: 3,
    selectable: false,
    evented: false,
    opacity: 0.9,
    isDebugObject: true,
    debugType: 'scaledMask'
  });

  fabricCanvas.add(expandedPoly);
  eyebrowDebugObjects.push(expandedPoly);

  // Calcola il centroide del poligono per determinare la direzione verso l'esterno
  const centroid = calculateCentroid(expandedPolygon);

  // Disegna solo i cerchi sui 5 vertici con etichette coordinate SOPRA (direzione verticale)
  expandedPolygon.forEach((point, index) => {
    const vertexMarker = new fabric.Circle({
      left: point.x - 3,
      top: point.y - 3,
      radius: 3,
      fill: color,
      stroke: '#FFFFFF',
      strokeWidth: 1,
      selectable: false,
      evented: false,
      isDebugObject: true,
      debugType: 'scaledMask'
    });

    fabricCanvas.add(vertexMarker);
    eyebrowDebugObjects.push(vertexMarker);

    // Etichetta con nome punto e coordinate - SOPRA il punto (direzione verticale)
    const labelText = `${point.name}\n(${Math.round(point.x)}, ${Math.round(point.y)})`;

    // Stima dimensioni etichetta
    const estimatedWidth = 60;
    const estimatedHeight = 25;

    // Posizione base: sopra il punto
    const baseY = point.y - 30;
    const labelX = point.x - estimatedWidth / 2;

    // Trova posizione libera verticalmente verso l'alto
    const labelY = findFreeVerticalPosition(labelX, baseY, estimatedWidth, estimatedHeight, -1, 12);

    // Linea di collegamento verticale tra punto e etichetta
    const connector = new fabric.Line([point.x, point.y, point.x, labelY + estimatedHeight], {
      stroke: color,
      strokeWidth: 0.5,
      opacity: 0.4,
      selectable: false,
      evented: false,
      isDebugObject: true,
      debugType: 'scaledMask'
    });
    fabricCanvas.add(connector);
    eyebrowDebugObjects.push(connector);

    const vertexLabel = new fabric.Text(labelText, {
      left: labelX,
      top: labelY,
      fontSize: 8,
      fill: '#FFFFFF',
      backgroundColor: 'rgba(0,0,0,0.85)',
      selectable: false,
      evented: false,
      isDebugObject: true,
      debugType: 'scaledMask'
    });

    fabricCanvas.add(vertexLabel);
    eyebrowDebugObjects.push(vertexLabel);
  });

  console.log(`🐛 DEBUG: Maschera espansa ${side} visualizzata (5 punti)`);
}

/**
 * Visualizza la maschera binaria come immagine sovrapposta
 * @param {Object} regionData - Dati della regione {bbox, binaryMask}
 * @param {string} side - 'left' o 'right'
 */
function drawBinaryMaskDebug(regionData, side) {
  if (!eyebrowDebugMode || !fabricCanvas || !regionData) return;
  if (!debugVisibility.binaryPixels) return; // Controlla visibilità

  try {
    const { binaryMask, canvasWidth, canvasHeight } = regionData;

    // Crea canvas temporaneo per la maschera binaria
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvasWidth;
    tempCanvas.height = canvasHeight;
    const ctx = tempCanvas.getContext('2d');

    // Disegna la maschera binaria
    const imageData = ctx.createImageData(canvasWidth, canvasHeight);
    const data = imageData.data;

    for (let y = 0; y < canvasHeight; y++) {
      for (let x = 0; x < canvasWidth; x++) {
        const idx = (y * canvasWidth + x) * 4;
        const value = binaryMask[y] && binaryMask[y][x] === 1;

        if (value) {
          // Pixel nero (sopracciglio) - visualizza in rosso per debug
          data[idx] = 255;     // R
          data[idx + 1] = 0;   // G
          data[idx + 2] = 0;   // B
          data[idx + 3] = 180; // A (70% opacità)
        } else {
          // Pixel bianco (sfondo) - trasparente
          data[idx] = 255;
          data[idx + 1] = 255;
          data[idx + 2] = 255;
          data[idx + 3] = 0;   // Completamente trasparente
        }
      }
    }

    ctx.putImageData(imageData, 0, 0);

    // Crea immagine Fabric.js dalla maschera
    const imgSrc = tempCanvas.toDataURL();
    fabric.Image.fromURL(imgSrc, function (img) {
      img.set({
        left: 0,
        top: 0,
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'binaryPixel'
      });

      fabricCanvas.add(img);
      eyebrowDebugObjects.push(img);
      fabricCanvas.renderAll();

      console.log(`🐛 DEBUG: Maschera binaria ${side} visualizzata (rosso = pixel sopracciglio)`);
    });

    // Conta pixel neri (sopracciglia)
    const blackPixels = binaryMask.flat().filter(p => p === 1).length;
    const totalPixels = canvasWidth * canvasHeight;
    const percentage = ((blackPixels / totalPixels) * 100).toFixed(1);

    // Aggiungi statistiche
    const stats = new fabric.Text(
      `Pixels: ${blackPixels}/${totalPixels} (${percentage}%)`,
      {
        left: 10,
        top: side === 'left' ? 10 : 40,
        fontSize: 12,
        fill: '#FFFFFF',
        backgroundColor: '#FF0000',
        selectable: false,
        evented: false,
        isDebugObject: true,
        debugType: 'binaryPixel'
      }
    );

    fabricCanvas.add(stats);
    eyebrowDebugObjects.push(stats);

  } catch (error) {
    console.error('❌ Errore visualizzazione maschera binaria:', error);
  }
}

/**
 * Crea pannello di controllo debug nell'interfaccia
 */
function createDebugControlPanel() {
  // Verifica se esiste già
  if (document.getElementById('eyebrow-debug-panel')) return;

  const panel = document.createElement('div');
  panel.id = 'eyebrow-debug-panel';
  panel.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    z-index: 10000;
    font-family: 'Segoe UI', sans-serif;
    min-width: 250px;
  `;

  panel.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
      <strong>🐛 Debug Sopracciglia</strong>
      <button onclick="document.getElementById('eyebrow-debug-panel').remove()" 
              style="background: rgba(255,255,255,0.2); border: none; color: white; 
                     padding: 2px 8px; border-radius: 5px; cursor: pointer;">✕</button>
    </div>
    <div style="font-size: 12px; line-height: 1.8;">
      <div style="margin: 8px 0;">
        <label style="display: flex; align-items: center; cursor: pointer;">
          <input type="checkbox" id="debug-toggle" ${eyebrowDebugMode ? 'checked' : ''} 
                 onchange="window.toggleEyebrowDebug(); 
                           document.getElementById('debug-status').textContent = 
                           window.eyebrowDebugMode ? 'ATTIVO' : 'DISATTIVO';"
                 style="margin-right: 8px;">
          Debug Mode: <strong id="debug-status" style="margin-left: 5px;">
            ${eyebrowDebugMode ? 'ATTIVO' : 'DISATTIVO'}
          </strong>
        </label>
      </div>
      <hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.3); margin: 10px 0;">
      <div style="font-size: 10px; opacity: 0.9; margin-bottom: 10px;">
        <strong>Mostra/Nascondi Overlay:</strong>
        <div style="margin: 5px 0;">
          <label style="display: flex; align-items: center; cursor: pointer;">
            <input type="checkbox" id="toggle-landmarks" checked 
                   onchange="window.toggleDebugOverlay('landmarkPolygons')"
                   style="margin-right: 5px;">
            🟠🟣 Perimetri landmarks
          </label>
        </div>
        <div style="margin: 5px 0;">
          <label style="display: flex; align-items: center; cursor: pointer;">
            <input type="checkbox" id="toggle-scaled" checked 
                   onchange="window.toggleDebugOverlay('scaledMasks')"
                   style="margin-right: 5px;">
            🟢🔵 Maschere espanse (5 punti)
          </label>
        </div>
        <div style="margin: 5px 0;">
          <label style="display: flex; align-items: center; cursor: pointer;">
            <input type="checkbox" id="toggle-binary" checked 
                   onchange="window.toggleDebugOverlay('binaryPixels')"
                   style="margin-right: 5px;">
            🔴 Pixel binari + statistiche
          </label>
        </div>
        <div style="margin: 5px 0;">
          <label style="display: flex; align-items: center; cursor: pointer;">
            <input type="checkbox" id="toggle-output" checked 
                   onchange="window.toggleDebugOverlay('measurementOutput')"
                   style="margin-right: 5px;">
            📊 Etichette risultati misurazione
          </label>
        </div>
      </div>
      <hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.3); margin: 10px 0;">
      <div style="font-size: 11px; opacity: 0.9;">
        <div>� Arancione: Poligono originale SX + ID landmarks</div>
        <div>🟣 Magenta: Perimetro landmarks DX + ID</div>
        <div>� Giallo: Landmark origine (LM) + frecce offset</div>
        <div>🟢 Verde: Maschera espansa SX (5 punti EXT)</div>
        <div>🔵 Ciano: Maschera espansa DX (5 punti EXT)</div>
        <div>🔴 Rosso: Pixel binari (threshold adattivo)</div>
      </div>
      <button onclick="clearEyebrowDebugObjects(); console.log('🧹 Debug objects cleared');" 
              style="width: 100%; margin-top: 10px; padding: 8px; background: rgba(255,255,255,0.2); 
                     border: none; color: white; border-radius: 5px; cursor: pointer; font-weight: bold;">
        🧹 Pulisci Debug
      </button>
    </div>
  `;

  document.body.appendChild(panel);
  console.log('🐛 Pannello debug creato');
}

// Funzione per toggle visibilità overlay di debug
window.toggleDebugOverlay = function (type) {
  // Aggiorna lo stato di visibilità
  debugVisibility[type] = !debugVisibility[type];

  // Filtra gli oggetti debug per tipo e aggiorna la visibilità
  eyebrowDebugObjects.forEach(obj => {
    if (obj.debugType === type) {
      obj.visible = debugVisibility[type];
    }
  });

  // Gestisci anche gli overlay di misurazione (etichette dei risultati)
  if (type === 'measurementOutput') {
    const eyebrowOverlays = measurementOverlays.get('eyebrowAreas');
    if (eyebrowOverlays) {
      eyebrowOverlays.forEach(obj => {
        if (obj.isMeasurementLabel) {
          obj.visible = debugVisibility[type];
        }
      });
    }
  }

  // Renderizza il canvas
  if (fabricCanvas) {
    fabricCanvas.renderAll();
  }

  console.log(`🔄 Debug overlay '${type}' ${debugVisibility[type] ? 'MOSTRATO' : 'NASCOSTO'}`);
};

// === IMPLEMENTAZIONI MANCANTI ===

function measureChinWidth(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureChinWidth"]');
  toggleMeasurementButton(button, 'chinWidth');
}

function performChinWidthMeasurement() {
  showToast('Misurazione larghezza mento - In sviluppo', 'info');
}

function measureFaceProfile(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureFaceProfile"]');
  toggleMeasurementButton(button, 'faceProfile');
}

function performFaceProfileMeasurement() {
  showToast('Misurazione profilo viso - In sviluppo', 'info');
}

function measureNoseAngle(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureNoseAngle"]');
  toggleMeasurementButton(button, 'noseAngle');
}

function performNoseAngleMeasurement() {
  showToast('Misurazione angolo naso - In sviluppo', 'info');
}

function measureMouthAngle(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureMouthAngle"]');
  toggleMeasurementButton(button, 'mouthAngle');
}

function performMouthAngleMeasurement() {
  showToast('Misurazione angolo bocca - In sviluppo', 'info');
}

function measureFaceProportions(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureFaceProportions"]');
  toggleMeasurementButton(button, 'faceProportions');
}

function performFaceProportionsMeasurement() {
  console.log('📏 Misurazione proporzioni viso...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performFaceProportionsMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // === CALCOLO MISURE FONDAMENTALI ===

    // Altezza viso
    const topForehead = currentLandmarks[10];
    const bottomChin = currentLandmarks[152];
    const faceHeight = calculateDistanceBetweenPoints(topForehead, bottomChin);

    // Larghezza viso (zigomi)
    const leftCheekbone = currentLandmarks[447];
    const rightCheekbone = currentLandmarks[227];
    const faceWidth = calculateDistanceBetweenPoints(leftCheekbone, rightCheekbone);

    // Distanza interpupillare
    const leftEye = currentLandmarks[133];
    const rightEye = currentLandmarks[362];
    const eyeDistance = calculateDistanceBetweenPoints(leftEye, rightEye);

    // Larghezza naso
    const leftNostril = currentLandmarks[98];
    const rightNostril = currentLandmarks[327];
    const noseWidth = calculateDistanceBetweenPoints(leftNostril, rightNostril);

    // Larghezza bocca
    const leftMouth = currentLandmarks[61];
    const rightMouth = currentLandmarks[291];
    const mouthWidth = calculateDistanceBetweenPoints(leftMouth, rightMouth);

    // Altezza terzo medio (occhi-naso)
    const nasion = currentLandmarks[6];
    const subnasale = currentLandmarks[2];
    const middleThirdHeight = calculateDistanceBetweenPoints(nasion, subnasale);

    // Altezza terzo inferiore (naso-mento)
    const lowerThirdHeight = calculateDistanceBetweenPoints(subnasale, bottomChin);

    // === CALCOLO RAPPORTI PROPORZIONALI ===

    // Rapporto altezza/larghezza
    const heightWidthRatio = faceHeight / faceWidth;

    // Rapporto naso/larghezza viso (ideale ~20-25%)
    const noseWidthRatio = (noseWidth / faceWidth) * 100;

    // Rapporto bocca/larghezza viso (ideale ~40-50%)
    const mouthWidthRatio = (mouthWidth / faceWidth) * 100;

    // Rapporto distanza occhi/larghezza viso (ideale ~45-48%)
    const eyeDistanceRatio = (eyeDistance / faceWidth) * 100;

    // Rapporto terzi viso (ideale: terzo medio ≈ terzo inferiore)
    const thirdsRatio = middleThirdHeight / lowerThirdHeight;

    // === VALUTAZIONE COMPLESSIVA ===
    let score = 100; // Punteggio di partenza
    let issues = []; // Lista problematiche
    let positives = []; // Lista aspetti positivi

    // Valutazione rapporto altezza/larghezza
    if (heightWidthRatio >= 1.3 && heightWidthRatio <= 1.5) {
      positives.push('Rapporto altezza/larghezza armonico');
    } else if (heightWidthRatio < 1.2) {
      score -= 10;
      issues.push('Viso troppo largo rispetto all\'altezza');
    } else if (heightWidthRatio > 1.6) {
      score -= 10;
      issues.push('Viso troppo allungato rispetto alla larghezza');
    }

    // Valutazione larghezza naso
    if (noseWidthRatio >= 18 && noseWidthRatio <= 28) {
      positives.push('Larghezza naso proporzionata');
    } else if (noseWidthRatio < 18) {
      score -= 5;
      issues.push('Naso proporzionalmente stretto');
    } else {
      score -= 8;
      issues.push('Naso proporzionalmente largo');
    }

    // Valutazione larghezza bocca
    if (mouthWidthRatio >= 38 && mouthWidthRatio <= 52) {
      positives.push('Larghezza bocca proporzionata');
    } else if (mouthWidthRatio < 38) {
      score -= 7;
      issues.push('Bocca proporzionalmente stretta');
    } else {
      score -= 7;
      issues.push('Bocca proporzionalmente larga');
    }

    // Valutazione distanza occhi
    if (eyeDistanceRatio >= 42 && eyeDistanceRatio <= 50) {
      positives.push('Distanza occhi armoniosa');
    } else if (eyeDistanceRatio < 42) {
      score -= 6;
      issues.push('Occhi proporzionalmente vicini');
    } else {
      score -= 6;
      issues.push('Occhi proporzionalmente distanti');
    }

    // Valutazione terzi viso
    if (thirdsRatio >= 0.9 && thirdsRatio <= 1.1) {
      positives.push('Terzi del viso equilibrati');
    } else if (thirdsRatio < 0.9) {
      score -= 8;
      issues.push('Terzo medio proporzionalmente corto');
    } else {
      score -= 8;
      issues.push('Terzo medio proporzionalmente lungo');
    }

    // Valutazione finale
    let finalEvaluation = '';
    let voiceMessage = '';

    if (score >= 90) {
      finalEvaluation = 'Proporzioni eccellenti';
      voiceMessage = 'Le proporzioni del viso risultano eccellenti, con tutti i parametri in range ottimale.';
    } else if (score >= 75) {
      finalEvaluation = 'Proporzioni buone';
      voiceMessage = 'Le proporzioni del viso risultano buone, con la maggior parte dei parametri armonici.';
    } else if (score >= 60) {
      finalEvaluation = 'Proporzioni accettabili';
      voiceMessage = 'Le proporzioni del viso risultano accettabili, con alcuni aspetti da considerare.';
    } else {
      finalEvaluation = 'Proporzioni da valutare';
      voiceMessage = 'Le proporzioni del viso presentano alcuni aspetti che meritano attenzione.';
    }

    // === CREA OVERLAY VISUALI ===
    const overlayObjects = [];

    // Linea altezza viso
    const heightLine = createMeasurementLine(topForehead, bottomChin, 'Altezza', '#FF6B35');
    overlayObjects.push(heightLine);

    // Linea larghezza viso
    const widthLine = createMeasurementLine(leftCheekbone, rightCheekbone, 'Larghezza', '#F7931E');
    overlayObjects.push(widthLine);

    // Linea distanza occhi
    const eyeLine = createMeasurementLine(leftEye, rightEye, 'Dist. Occhi', '#FFD23F');
    overlayObjects.push(eyeLine);

    // Linea larghezza naso
    const noseLine = createMeasurementLine(leftNostril, rightNostril, 'Larg. Naso', '#06FFA5');
    overlayObjects.push(noseLine);

    // Linea larghezza bocca
    const mouthLine = createMeasurementLine(leftMouth, rightMouth, 'Larg. Bocca', '#118AB2');
    overlayObjects.push(mouthLine);

    // Linea terzo medio
    const middleThirdLine = createMeasurementLine(nasion, subnasale, 'Terzo Medio', '#9C27B0');
    overlayObjects.push(middleThirdLine);

    // Linea terzo inferiore
    const lowerThirdLine = createMeasurementLine(subnasale, bottomChin, 'Terzo Inf.', '#E91E63');
    overlayObjects.push(lowerThirdLine);

    // Salva overlay
    measurementOverlays.set('faceProportions', overlayObjects);

    // === AGGIUNGI ALLA TABELLA - ESPANDI LA SEZIONE ===
    ensureMeasurementsSectionOpen();

    // Misure assolute
    addMeasurementToTable('Altezza Viso', faceHeight, 'px');
    addMeasurementToTable('Larghezza Viso', faceWidth, 'px');
    addMeasurementToTable('Distanza Occhi', eyeDistance, 'px');
    addMeasurementToTable('Larghezza Naso', noseWidth, 'px');
    addMeasurementToTable('Larghezza Bocca', mouthWidth, 'px');

    // Rapporti percentuali
    addMeasurementToTable('─── RAPPORTI ───', '───', '');
    addMeasurementToTable('Rapporto Alt/Larg', heightWidthRatio.toFixed(2), '');
    addMeasurementToTable('Naso/Viso', noseWidthRatio.toFixed(1), '%');
    addMeasurementToTable('Bocca/Viso', mouthWidthRatio.toFixed(1), '%');
    addMeasurementToTable('Occhi/Viso', eyeDistanceRatio.toFixed(1), '%');
    addMeasurementToTable('Rapporto Terzi', thirdsRatio.toFixed(2), '');

    // Valutazione
    addMeasurementToTable('─── VALUTAZIONE ───', '───', '');
    addMeasurementToTable('Punteggio Proporzioni', score.toFixed(0), '/100');
    addMeasurementToTable('Valutazione Finale', finalEvaluation, '');

    // Aspetti positivi
    if (positives.length > 0) {
      addMeasurementToTable('─── ASPETTI POSITIVI ───', '───', '');
      positives.forEach(positive => {
        addMeasurementToTable('✓', positive, '');
      });
    }

    // Problematiche
    if (issues.length > 0) {
      addMeasurementToTable('─── NOTE ───', '───', '');
      issues.forEach(issue => {
        addMeasurementToTable('•', issue, '');
      });
    }

    // Feedback vocale
    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
      voiceAssistant.speak(voiceMessage);
    }

    console.log('📏 Proporzioni completate:', {
      score: score,
      heightWidthRatio: heightWidthRatio.toFixed(2),
      noseWidthRatio: noseWidthRatio.toFixed(1),
      mouthWidthRatio: mouthWidthRatio.toFixed(1),
      eyeDistanceRatio: eyeDistanceRatio.toFixed(1),
      evaluation: finalEvaluation
    });

  } catch (error) {
    console.error('Errore misurazione proporzioni:', error);
    showToast('Errore durante la misurazione delle proporzioni', 'error');
  }
}

function measureKeyDistances(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureKeyDistances"]');
  toggleMeasurementButton(button, 'keyDistances');
}

function performKeyDistancesMeasurement() {
  showToast('Misurazione distanze chiave - In sviluppo', 'info');
}

// === STIMA ETÀ ===

async function estimateAge(event) {
  const button = event ? event.target : document.querySelector('[onclick*="estimateAge"]');

  if (!button) {
    console.error('❌ Pulsante Stima Età non trovato');
    showToast('Errore: pulsante non trovato', 'error');
    return;
  }

  // Verifica che ci sia un'immagine caricata sul canvas
  const currentImage = fabricCanvas ? fabricCanvas.getObjects().find(obj => obj.isBackgroundImage) : null;
  if (!currentImage) {
    showToast('⚠️ Carica prima un\'immagine', 'warning');
    return;
  }

  // Disabilita il pulsante durante l'elaborazione
  button.disabled = true;
  button.textContent = '⏳ Analisi in corso...';

  try {
    // Ottieni l'immagine dal canvas Fabric.js (più affidabile)
    const imageDataUrl = fabricCanvas.toDataURL({
      format: 'jpeg',
      quality: 0.95
    });

    if (!imageDataUrl) {
      throw new Error('Impossibile estrarre immagine dal canvas');
    }

    console.log('📤 Invio richiesta stima età...');

    // Chiamata API
    const response = await fetch('/api/estimate-age', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: imageDataUrl
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Errore nella richiesta');
    }

    const result = await response.json();

    if (result.success && result.age) {
      const confidence = result.confidence || 'unknown';
      const ratios = result.ratios || {};

      console.log('✅ Età stimata:', result.age, 'anni', result);

      // Determina range età
      let ageRangeDescription;
      if (result.age < 20) {
        ageRangeDescription = 'Under 20';
      } else if (result.age < 25) {
        ageRangeDescription = 'Giovane adulto (20-24)';
      } else if (result.age < 30) {
        ageRangeDescription = 'Adulto giovane (25-29)';
      } else if (result.age < 40) {
        ageRangeDescription = 'Adulto (30-39)';
      } else if (result.age < 50) {
        ageRangeDescription = 'Adulto maturo (40-49)';
      } else if (result.age < 60) {
        ageRangeDescription = 'Senior (50-59)';
      } else if (result.age < 70) {
        ageRangeDescription = 'Senior avanzato (60-69)';
      } else {
        ageRangeDescription = 'Over 70';
      }

      // Confidenza in italiano
      const confidenceIT = { high: 'Alta', medium: 'Media', low: 'Bassa' }[confidence] || confidence;

      // Rimuovi righe precedenti stima età
      const tableBody = document.getElementById('unified-table-body');
      if (tableBody) {
        tableBody.querySelectorAll('[data-measurement="age-estimate"]').forEach(r => r.remove());
      }

      // Aggiungi dati alla tabella
      addMeasurementToTable('🎂 Età Stimata', result.age, 'anni', 'age-estimate');
      addMeasurementToTable('👤 Fascia', ageRangeDescription, '', 'age-estimate');
      addMeasurementToTable('📊 Confidenza', confidenceIT, '', 'age-estimate');

      // Dettagli opzionali (solo se presenti)
      if (ratios.eye_openness !== undefined) {
        const eyeDesc = ratios.eye_openness > 0.30 ? 'Ampia' : ratios.eye_openness > 0.24 ? 'Normale' : 'Ridotta';
        addMeasurementToTable('👁️ Apertura occhi', eyeDesc, '', 'age-estimate');
      }
      if (ratios.brow_drop !== undefined) {
        const browDesc = ratios.brow_drop > 0.055 ? 'Alte' : ratios.brow_drop > 0.035 ? 'Normali' : 'Abbassate';
        addMeasurementToTable('🔼 Sopracciglia', browDesc, '', 'age-estimate');
      }

      ensureMeasurementsSectionOpen();

      const voiceMessage = `Età stimata: ${result.age} anni. ${ageRangeDescription}.`;
      if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
        voiceAssistant.speak(voiceMessage);
      }

      showToast('✅ Stima età completata', 'success', 2000);
    } else {
      throw new Error('Risposta non valida dal server');
    }

  } catch (error) {
    console.error('❌ Errore stima età:', error);
    showToast(`❌ Errore: ${error.message}`, 'error');
  } finally {
    // Ripristina il pulsante
    button.disabled = false;
    button.textContent = '🎂 Stima Età';
  }
}

// Esporta funzioni globali necessarie per altri moduli
window.ensureMeasurementsSectionOpen = ensureMeasurementsSectionOpen;
window.addMeasurementToTable = addMeasurementToTable;

// === DIFFERENZA ROTAZIONE OCCHI ===

/**
 * Calcola la differenza di rotazione (tilt) tra occhio sinistro e occhio destro.
 *
 * Landmark MediaPipe (confermati da face_analysis_module.py):
 *   Occhio SINISTRO: esterno=33, interno=133, sup=159, inf=145
 *   Occhio DESTRO:   interno=362, esterno=263, sup=386, inf=374
 *
 * L'angolo è calcolato come inclinazione del vettore
 * canto-interno → canto-esterno rispetto all'orizzontale.
 * Positivo = canto esterno più alto = "cat eye up".
 * Negativo = canto esterno più basso = "downturned eye".
 *
 * Auto-rileva landmarks silenziosamente se non già presenti.
 */
async function measureEyeRotationDiff(event) {
  /**
   * Entry-point del pulsante: gestisce il toggle ON/OFF come tutti gli altri
   * pulsanti di misurazione (verde = attivo, arancione = disattivo).
   */
  const button = event
    ? (event.currentTarget || event.target)
    : document.querySelector('[onclick*="measureEyeRotationDiff"]');
  toggleMeasurementButton(button, 'eyeRotation');
}

async function performEyeRotationMeasurement() {
  /**
   * Calcola l'angolo di rotazione di ciascun occhio rispetto all'asse orizzontale.
   *
   * CONVENZIONE ANGOLI (richiesta dall'utente):
   *   Occhio DX (destra nell'immagine, outer = lm 263):
   *     angolo positivo = senso ANTIORARIO → cat-eye (canto esterno rialzato)
   *     Formula: atan2(dxInt.y − dxExt.y,  dxExt.x − dxInt.x)
   *              numeratore > 0 quando outer è più in alto (canvas Y↓)
   *              denominatore > 0 perché outer è a destra di inner
   *
   *   Occhio SX (sinistra nell'immagine, outer = lm 33):
   *     angolo positivo = senso ORARIO → cat-eye
   *     Formula: atan2(sxInt.y − sxExt.y,  sxInt.x − sxExt.x)
   *              numeratore > 0 quando outer è più in alto
   *              denominatore > 0 perché inner è a destra di outer (eye on left)
   */
  try {
    // Auto-detect landmarks se non presenti
    if (!currentLandmarks || currentLandmarks.length === 0) {
      const ok = await autoDetectLandmarksOnImageChange();
      if (!ok || !currentLandmarks || currentLandmarks.length === 0) {
        showToast('⚠️ Impossibile rilevare il viso nell\'immagine', 'warning');
        // Rimuovi classe attiva perché non siamo riusciti ad attivarci
        const btn = document.querySelector('[onclick*="measureEyeRotationDiff"]');
        if (btn) btn.classList.remove('btn-active');
        return;
      }
    }

    const required = [33, 133, 159, 145, 263, 362, 386, 374];
    for (const idx of required) {
      if (!currentLandmarks[idx]) {
        showToast(`⚠️ Landmark ${idx} non disponibile`, 'warning');
        const btn = document.querySelector('[onclick*="measureEyeRotationDiff"]');
        if (btn) btn.classList.remove('btn-active');
        return;
      }
    }

    function tpt(idx) {
      const lm = currentLandmarks[idx];
      return (window.transformLandmarkCoordinate) ? window.transformLandmarkCoordinate(lm) : lm;
    }

    // ── Occhio SX nell'immagine (outer = lm 33, inner = lm 133) ─────────────
    const sxExt = tpt(33);   // canto esterno, lato tempia SX
    const sxInt = tpt(133);  // canto interno, lato naso
    const sxTop = tpt(159);
    const sxBot = tpt(145);

    // ── Occhio DX nell'immagine (inner = lm 362, outer = lm 263) ────────────
    const dxInt = tpt(362);  // canto interno, lato naso
    const dxExt = tpt(263);  // canto esterno, lato tempia DX
    const dxTop = tpt(386);
    const dxBot = tpt(374);

    // ── Calcolo angoli ───────────────────────────────────────────────────────
    // Occhio DX: outer è a DESTRA di inner  → dxExt.x > dxInt.x → denominatore > 0
    // angolo positivo = antiorario (cat-eye: outer più alto → numeratore > 0)
    const angleDx = Math.atan2(dxInt.y - dxExt.y, dxExt.x - dxInt.x) * 180 / Math.PI;

    // Occhio SX: outer è a SINISTRA di inner → sxInt.x > sxExt.x → denominatore > 0
    // angolo positivo = orario (cat-eye: outer più alto → numeratore > 0)
    const angleSx = Math.atan2(sxInt.y - sxExt.y, sxInt.x - sxExt.x) * 180 / Math.PI;

    // ── Metriche derivate ────────────────────────────────────────────────────
    const openSx = Math.sqrt(Math.pow(sxTop.x - sxBot.x, 2) + Math.pow(sxTop.y - sxBot.y, 2));
    const openDx = Math.sqrt(Math.pow(dxTop.x - dxBot.x, 2) + Math.pow(dxTop.y - dxBot.y, 2));

    const absDiff = Math.abs(angleDx - angleSx);

    let symDesc;
    if (absDiff < 1.5) symDesc = 'Simmetrica (< 1.5°)';
    else if (absDiff < 4) symDesc = 'Lieve asimmetria (1.5–4°)';
    else if (absDiff < 8) symDesc = 'Asimmetria moderata (4–8°)';
    else symDesc = 'Asimmetria marcata (> 8°)';

    function eyeShape(angle) {
      if (angle > 3) return 'Cat eye ↗';
      if (angle > 0) return 'Liev. rialzato';
      if (angle > -3) return 'Neutro';
      return 'Downturned ↘';
    }

    let higherEye = '';
    if (absDiff >= 1.5) {
      higherEye = angleDx > angleSx
        ? 'Occhio Dx più inclinato verso l\'alto'
        : 'Occhio Sx più inclinato verso l\'alto';
    }

    // ── Tabella misurazioni ──────────────────────────────────────────────────
    const tableBody = document.getElementById('unified-table-body');
    if (tableBody) {
      tableBody.querySelectorAll('[data-measurement="eye-rotation"]').forEach(r => r.remove());
    }

    addMeasurementToTable('👁️ Angolo Occhio Sx', angleSx.toFixed(1), '°', 'eye-rotation');
    addMeasurementToTable('👁️ Forma Sx', eyeShape(angleSx), '', 'eye-rotation');
    addMeasurementToTable('👁️ Angolo Occhio Dx', angleDx.toFixed(1), '°', 'eye-rotation');
    addMeasurementToTable('👁️ Forma Dx', eyeShape(angleDx), '', 'eye-rotation');
    addMeasurementToTable('↔️ Diff. Rotazione', absDiff.toFixed(1), '°', 'eye-rotation');
    addMeasurementToTable('⚖️ Simmetria', symDesc, '', 'eye-rotation');
    if (higherEye) addMeasurementToTable('📐 Predominanza', higherEye, '', 'eye-rotation');
    addMeasurementToTable('📏 Apertura Sx', openSx.toFixed(1), 'px', 'eye-rotation');
    addMeasurementToTable('📏 Apertura Dx', openDx.toFixed(1), 'px', 'eye-rotation');

    ensureMeasurementsSectionOpen();

    // ── Overlay visivo ───────────────────────────────────────────────────────
    const overlayObjs = _drawEyeRotationOverlay(sxExt, sxInt, dxInt, dxExt, angleSx, angleDx);
    measurementOverlays.set('eyeRotation', overlayObjs);

    window.eyeRotationOverlayActive = true;
    window._eyeRotationCachedAngles = { angleSx, angleDx };

    const voiceMsg = `Rotazione occhi: sinistro ${angleSx.toFixed(1)} gradi, destro ${angleDx.toFixed(1)} gradi. Differenza: ${absDiff.toFixed(1)} gradi. ${symDesc}.`;
    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
      voiceAssistant.speak(voiceMsg);
    }

    showToast(`✅ Rotazione occhi: diff ${absDiff.toFixed(1)}°`, 'success', 2500);

  } catch (err) {
    console.error('❌ Errore rotazione occhi:', err);
    showToast(`❌ Errore: ${err.message}`, 'error');
    const btn = document.querySelector('[onclick*="measureEyeRotationDiff"]');
    if (btn) btn.classList.remove('btn-active');
  }
}

/**
 * Disegna sul canvas le linee degli assi oculari con etichette angolo.
 * sxExt/sxInt = canto esterno/interno occhio SINISTRO nell'immagine (canvas coords)
 * dxInt/dxExt = canto interno/esterno occhio DESTRO nell'immagine (canvas coords)
 * Restituisce l'array di oggetti Fabric creati (per measurementOverlays).
 */
function _drawEyeRotationOverlay(sxExt, sxInt, dxInt, dxExt, angleSx, angleDx) {
  if (!fabricCanvas) return [];

  // Rimuovi overlay precedenti
  fabricCanvas.getObjects().filter(o => o.isEyeRotationOverlay).forEach(o => fabricCanvas.remove(o));

  const COL_SX = '#00E5FF';  // ciano = occhio sinistro (sinistra immagine)
  const COL_DX = '#FF6B35';  // arancione = occhio destro (destra immagine)
  const objs = [];

  function mkLine(p1, p2, color) {
    const o = new fabric.Line([p1.x, p1.y, p2.x, p2.y], {
      stroke: color, strokeWidth: 2.5, selectable: false, evented: false,
      isEyeRotationOverlay: true
    });
    fabricCanvas.add(o); objs.push(o); return o;
  }

  function mkDot(p, color) {
    const o = new fabric.Circle({
      left: p.x - 4, top: p.y - 4, radius: 4,
      fill: color, stroke: '#fff', strokeWidth: 1,
      selectable: false, evented: false, isEyeRotationOverlay: true
    });
    fabricCanvas.add(o); objs.push(o); return o;
  }

  function mkLabel(text, x, y, color) {
    const o = new fabric.Text(text, {
      left: x, top: y, fontSize: 13, fill: color, fontFamily: 'monospace',
      fontWeight: 'bold', selectable: false, evented: false,
      isEyeRotationOverlay: true,
      shadow: new fabric.Shadow({ color: 'rgba(0,0,0,0.85)', blur: 4, offsetX: 1, offsetY: 1 })
    });
    fabricCanvas.add(o); objs.push(o); return o;
  }

  // Linee asse oculare (inner → outer)
  mkLine(sxInt, sxExt, COL_SX);
  mkLine(dxInt, dxExt, COL_DX);

  // Pallini sui canti
  mkDot(sxExt, COL_SX); mkDot(sxInt, COL_SX);
  mkDot(dxInt, COL_DX); mkDot(dxExt, COL_DX);

  // Etichette angolo centrate sopra ogni asse
  const sxMidX = (sxInt.x + sxExt.x) / 2;
  const sxMidY = (sxInt.y + sxExt.y) / 2;
  const dxMidX = (dxInt.x + dxExt.x) / 2;
  const dxMidY = (dxInt.y + dxExt.y) / 2;

  mkLabel(`Sx ${angleSx.toFixed(1)}°`, sxMidX - 24, sxMidY - 20, COL_SX);
  mkLabel(`Dx ${angleDx.toFixed(1)}°`, dxMidX - 24, dxMidY - 20, COL_DX);

  fabricCanvas.renderAll();
  return objs;
}

// Registra globalmente
window.measureEyeRotationDiff = measureEyeRotationDiff;

/**
 * Ridisegna l'overlay rotazione occhi con le coordinate aggiornate dell'immagine.
 * Chiamato da main.js ad ogni trasformazione (rotazione, spostamento, zoom).
 */
window.redrawEyeRotationOverlay = function () {
  if (!window.eyeRotationOverlayActive) return;
  if (!currentLandmarks || currentLandmarks.length === 0) return;
  if (typeof window.transformLandmarkCoordinate !== 'function') return;
  const needed = [33, 133, 362, 263];
  if (needed.some(i => !currentLandmarks[i])) return;
  const tpt = idx => window.transformLandmarkCoordinate(currentLandmarks[idx]);
  const { angleSx = 0, angleDx = 0 } = window._eyeRotationCachedAngles || {};
  // sxExt=33, sxInt=133, dxInt=362, dxExt=263
  const objs = _drawEyeRotationOverlay(tpt(33), tpt(133), tpt(362), tpt(263), angleSx, angleDx);
  // Aggiorna il registro overlay così hideMeasurementOverlay può rimuoverli
  measurementOverlays.set('eyeRotation', objs);
};

/**
 * Aggiorna la tolleranza Magic Wand e ricalcola i contorni sopracciglia in tempo reale
 * @param {number} newTolerance - Nuova tolleranza da applicare
 */
window.updateEyebrowTolerance = function (newTolerance) {
  console.log(`🔄 Aggiornamento tolleranza: ${newTolerance}`);

  // Aggiorna il display del valore
  const valueDisplay = document.getElementById('tolerance-value');
  if (valueDisplay) {
    valueDisplay.textContent = newTolerance;
  }

  // Verifica che i dati regionali siano disponibili
  if (!window.eyebrowRegionData) {
    console.warn('⚠️ Dati regionali non disponibili per ricalcolo');
    return;
  }

  const { leftRegionData, rightRegionData, scaledLeftBrow, scaledRightBrow, canvasImage } = window.eyebrowRegionData;

  try {
    // Prepara landmarks di riferimento per sopracciglio SINISTRO
    const leftLandmarkRefs = {
      lm52: window.transformLandmarkCoordinate(currentLandmarks[52]),
      lm105: window.transformLandmarkCoordinate(currentLandmarks[105]),
      lm107: window.transformLandmarkCoordinate(currentLandmarks[107]),
      lm107ext: scaledLeftBrow[0]
    };

    // Prepara landmarks di riferimento per sopracciglio DESTRO
    const rightLandmarkRefs = {
      lm52: window.transformLandmarkCoordinate(currentLandmarks[282]),
      lm105: window.transformLandmarkCoordinate(currentLandmarks[334]),
      lm107: window.transformLandmarkCoordinate(currentLandmarks[336]),
      lm107ext: scaledRightBrow[0]
    };

    // Ricalcola le regioni con la nuova tolleranza
    const newLeftRegionData = extractAndBinarizeImageRegionWithTolerance(
      scaledLeftBrow, canvasImage, leftLandmarkRefs, parseInt(newTolerance)
    );
    const newRightRegionData = extractAndBinarizeImageRegionWithTolerance(
      scaledRightBrow, canvasImage, rightLandmarkRefs, parseInt(newTolerance)
    );

    if (!newLeftRegionData || !newRightRegionData) {
      console.error('❌ Errore ricalcolo regioni');
      return;
    }

    // Rimuovi i vecchi overlay sopracciglia dal canvas
    const objectsToRemove = fabricCanvas.getObjects().filter(obj =>
      obj.isAreaPolygon && (
        obj.measurementType === 'Area Sopracciglio Sinistro (Reale)' ||
        obj.measurementType === 'Area Sopracciglio Destro (Reale)'
      )
    );

    console.log(`🗑️ Rimozione ${objectsToRemove.length} overlay precedenti`);
    objectsToRemove.forEach(obj => {
      fabricCanvas.remove(obj);
    });

    // Crea nuovi poligoni overlay
    const leftBrowPolygon = createPolygonFromBinaryMask(
      newLeftRegionData,
      'Area Sopracciglio Sinistro (Reale)',
      '#FF6B35'
    );
    const rightBrowPolygon = createPolygonFromBinaryMask(
      newRightRegionData,
      'Area Sopracciglio Destro (Reale)',
      '#6B73FF'
    );

    if (leftBrowPolygon) {
      fabricCanvas.add(leftBrowPolygon);
      fabricCanvas.bringToFront(leftBrowPolygon);
    }
    if (rightBrowPolygon) {
      fabricCanvas.add(rightBrowPolygon);
      fabricCanvas.bringToFront(rightBrowPolygon);
    }

    // Aggiorna la mappa degli overlay (questo gestisce correttamente il pan)
    if (window.measurementOverlays) {
      const currentOverlays = window.measurementOverlays.get('eyebrowAreas') || [];
      const newOverlays = currentOverlays.filter(obj =>
        !obj.isAreaPolygon ||
        (obj.measurementType !== 'Area Sopracciglio Sinistro (Reale)' &&
          obj.measurementType !== 'Area Sopracciglio Destro (Reale)')
      );
      if (leftBrowPolygon) newOverlays.push(leftBrowPolygon);
      if (rightBrowPolygon) newOverlays.push(rightBrowPolygon);
      window.measurementOverlays.set('eyebrowAreas', newOverlays);
    }

    // Calcola nuove aree
    const leftRealArea = newLeftRegionData.binaryMask.flat().filter(p => p === 1).length;
    const rightRealArea = newRightRegionData.binaryMask.flat().filter(p => p === 1).length;

    console.log(`📊 Nuove aree: Left=${leftRealArea}px, Right=${rightRealArea}px`);

    fabricCanvas.renderAll();

  } catch (error) {
    console.error('❌ Errore aggiornamento tolleranza:', error);
  }
};

/**
 * Ridisegna tutti gli overlay di misurazione attivi
 * Chiamata quando il canvas viene ridimensionato o l'immagine cambia
 */
function redrawAllMeasurementOverlays() {
  console.log('🔄 Ridisegno overlay misurazioni attivi...');

  if (!window.measurementOverlays || window.measurementOverlays.size === 0) {
    console.log('📊 Nessun overlay da ridisegnare');
    return;
  }

  // Rimuovi tutti gli overlay esistenti dal canvas
  window.measurementOverlays.forEach((overlayObjects, measurementType) => {
    overlayObjects.forEach(obj => {
      if (fabricCanvas) {
        fabricCanvas.remove(obj);
      }
    });
  });

  // Riattiva tutte le misurazioni che erano attive
  const activeTypes = Array.from(window.activeMeasurements.keys());

  // Pulisci le mappe per evitare duplicati
  window.measurementOverlays.clear();

  // Ricrea ogni misurazione attiva
  activeTypes.forEach(measurementType => {
    console.log(`🔄 Ridisegno: ${measurementType}`);
    showMeasurementOverlay(measurementType, true); // silent: no tabella, no voce
  });

  if (fabricCanvas) {
    fabricCanvas.renderAll();
  }

  console.log('✅ Ridisegno overlay completato');
}

window.redrawAllMeasurementOverlays = redrawAllMeasurementOverlays;

/**
 * Ridisegna l'overlay aree sopracciglia con debounce per limitare le elaborazioni
 * pixel costose durante rotazioni rapide successive.
 * Chiamato da main.js sulle stesse trasformazioni che ridisegnano l'asse di simmetria.
 */
(function () {
  let _eyebrowRedrawTimer = null;
  window.redrawEyebrowAreasOverlay = function () {
    return; // DISABILITATO - Aree Sopracciglia nascosto
  };
}());

// =============================================================================
// === SIMMETRIA ALI NASALI ===
// =============================================================================

/**
 * Calcola la simmetria delle ale nasali misurando la distanza
 * dal Nose Bridge Top (lm 1) verso Bridge Nose Left (lm 2) e Bridge Nose Right (lm 98).
 * Disegna overlay colorato sul canvas e annuncia vocalmente il risultato.
 *
 * Landmark MediaPipe:
 *   Nose Bridge Top  : 1
 *   Bridge Nose Left : 2   (lato sinistro immagine)
 *   Bridge Nose Right: 98  (lato destro immagine)
 */
async function measureNosalWingSymmetry(event) {
  const button = event ? event.currentTarget || event.target : null;
  if (button) {
    button.disabled = true;
    button._origText = button.textContent;
    button.textContent = '⏳...';
  }

  try {
    if (!currentLandmarks || currentLandmarks.length === 0) {
      const ok = await autoDetectLandmarksOnImageChange();
      if (!ok || !currentLandmarks || currentLandmarks.length === 0) {
        showToast('⚠️ Impossibile rilevare il viso', 'warning');
        return;
      }
    }

    // Landmark: 1 = Nose Bridge Top, 2 = Bridge Nose Left, 98 = Bridge Nose Right
    const required = [1, 2, 98];
    for (const idx of required) {
      if (!currentLandmarks[idx]) {
        showToast(`⚠️ Landmark ${idx} non disponibile`, 'warning');
        return;
      }
    }

    function tpt(idx) {
      const lm = currentLandmarks[idx];
      return (window.transformLandmarkCoordinate) ? window.transformLandmarkCoordinate(lm) : lm;
    }

    const top = tpt(1);   // Nose Bridge Top
    const wingL = tpt(2);  // Bridge Nose Left
    const wingR = tpt(98); // Bridge Nose Right

    function dist2D(a, b) {
      return Math.sqrt(Math.pow(b.x - a.x, 2) + Math.pow(b.y - a.y, 2));
    }

    const distL = dist2D(top, wingL);
    const distR = dist2D(top, wingR);

    // Disegna overlay
    _drawNosalWingOverlay(top, wingL, wingR, distL, distR);

    // Calcola differenza %
    const maxDist = Math.max(distL, distR);
    const asymPercent = maxDist > 0 ? (Math.abs(distL - distR) / maxDist) * 100 : 0;
    const largerSide = distL > distR ? 'sinistra' : distL < distR ? 'destra' : null;

    // Aggiorna tabella
    const tableBody = document.getElementById('unified-table-body');
    if (tableBody) {
      tableBody.querySelectorAll('[data-measurement="nasal-wing"]').forEach(r => r.remove());
    }
    ensureMeasurementsSectionOpen();
    addMeasurementToTable('👃 Ala Nasale SX', distL.toFixed(1), 'px', 'nasal-wing');
    addMeasurementToTable('👃 Ala Nasale DX', distR.toFixed(1), 'px', 'nasal-wing');
    addMeasurementToTable('⚖️ Asimmetria Naso', asymPercent.toFixed(1), '%', 'nasal-wing');

    // Stato globale per ridisegno su trasformazioni
    window.nosalWingOverlayActive = true;

    // Voce
    let voiceMsg;
    if (largerSide) {
      voiceMsg = `L'ala nasale ${largerSide} è più larga di circa ${asymPercent.toFixed(0)} percento.`;
    } else {
      voiceMsg = 'Le due ali nasali sono perfettamente simmetriche.';
    }
    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
      voiceAssistant.speak(voiceMsg);
    }

    const toastMsg = largerSide
      ? `Ala ${largerSide} più larga (${asymPercent.toFixed(1)}%)`
      : 'Ali nasali simmetriche';
    showToast(`👃 ${toastMsg}`, asymPercent < 5 ? 'success' : 'warning', 3000);

  } catch (error) {
    console.error('❌ Errore simmetria ali nasali:', error);
    showToast(`❌ Errore: ${error.message}`, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = button._origText || '👃 Sim. Naso';
    }
  }
}

/**
 * Disegna le linee e i punti dell'overlay simmetria ali nasali.
 * Separato dalla funzione principale per essere richiamato al ridisegno.
 */
function _drawNosalWingOverlay(top, wingL, wingR, distL, distR) {
  if (!fabricCanvas) return;

  fabricCanvas.getObjects().filter(o => o.isNosalWingOverlay).forEach(o => fabricCanvas.remove(o));

  const COL_L = '#00E5FF';  // ciano = lato sinistro
  const COL_R = '#FF6B35';  // arancione = lato destro
  const COL_T = '#FFFFFF';  // bianco = punto apicale

  function addLine(p1, p2, color) {
    fabricCanvas.add(new fabric.Line([p1.x, p1.y, p2.x, p2.y], {
      stroke: color, strokeWidth: 2.5, selectable: false, evented: false,
      isNosalWingOverlay: true
    }));
  }

  function addDot(p, color) {
    fabricCanvas.add(new fabric.Circle({
      left: p.x - 4, top: p.y - 4, radius: 4,
      fill: color, stroke: '#000', strokeWidth: 1,
      selectable: false, evented: false, isNosalWingOverlay: true
    }));
  }

  function addLabel(text, x, y, color) {
    fabricCanvas.add(new fabric.Text(text, {
      left: x, top: y, fontSize: 13, fill: color, fontFamily: 'monospace',
      fontWeight: 'bold', selectable: false, evented: false,
      isNosalWingOverlay: true,
      shadow: new fabric.Shadow({ color: 'rgba(0,0,0,0.85)', blur: 4, offsetX: 1, offsetY: 1 })
    }));
  }

  addLine(top, wingL, COL_L);
  addLine(top, wingR, COL_R);

  addDot(top, COL_T);
  addDot(wingL, COL_L);
  addDot(wingR, COL_R);

  addLabel(`SX ${distL.toFixed(1)}`, (top.x + wingL.x) / 2 - 28, (top.y + wingL.y) / 2 - 18, COL_L);
  addLabel(`DX ${distR.toFixed(1)}`, (top.x + wingR.x) / 2 + 4, (top.y + wingR.y) / 2 - 18, COL_R);

  fabricCanvas.renderAll();
}

window.measureNosalWingSymmetry = measureNosalWingSymmetry;

/**
 * Ridisegna l'overlay simmetria ali nasali con coordinate aggiornate.
 * Chiamato da main.js ad ogni trasformazione canvas.
 */
window.redrawNosalWingOverlay = function () {
  if (!window.nosalWingOverlayActive) return;
  if (!currentLandmarks || currentLandmarks.length === 0) return;
  if (typeof window.transformLandmarkCoordinate !== 'function') return;
  if (!currentLandmarks[1] || !currentLandmarks[2] || !currentLandmarks[98]) return;

  const tpt = idx => window.transformLandmarkCoordinate(currentLandmarks[idx]);
  const top = tpt(1);
  const wingL = tpt(2);
  const wingR = tpt(98);

  function dist2D(a, b) {
    return Math.sqrt(Math.pow(b.x - a.x, 2) + Math.pow(b.y - a.y, 2));
  }

  _drawNosalWingOverlay(top, wingL, wingR, dist2D(top, wingL), dist2D(top, wingR));
};


// =============================================================================
// === SIMMETRIA SOPRACCIGLIA ===
// Stesso pattern di measureEyeAreas: usa currentLandmarks + createAreaPolygon.
// I poligoni Fabric.js seguono automaticamente scala, posizione e rotazione
// dell'immagine sul canvas → nessun problema di proporzionalita'.
// =============================================================================

function measureEyebrowSymmetry(event) {
  const button = event
    ? (event.currentTarget || event.target)
    : document.querySelector('[onclick*="measureEyebrowSymmetry"]');

  // Toggle OFF
  if (button && button.classList.contains('btn-active')) {
    button.classList.remove('btn-active');
    activeMeasurements.delete('eyebrowSymmetry');
    window._eyebrowSymmetryCache = null;
    if (measurementOverlays.has('eyebrowSymmetry')) {
      measurementOverlays.get('eyebrowSymmetry').forEach(o => fabricCanvas && fabricCanvas.remove(o));
      measurementOverlays.delete('eyebrowSymmetry');
      fabricCanvas && fabricCanvas.renderAll();
    }
    return;
  }

  // Toggle ON
  if (button) button.classList.add('btn-active');
  activeMeasurements.set('eyebrowSymmetry', true);
  _performEyebrowSymmetryAPI(button).catch(err => {
    console.error('❌ Simmetria sopracciglia:', err);
    showToast(`Errore: ${err.message}`, 'error');
    activeMeasurements.delete('eyebrowSymmetry');
    if (button) button.classList.remove('btn-active');
  });
}

/**
 * Riposiziona (o ricostruisce dalla cache) il fabric.Image dell'overlay sopracciglia
 * dopo rotazione/allineamento. NON richiama l'API.
 */
function _repositionEyebrowSymmetryOverlay() {
  if (!fabricCanvas || !currentImage) return;

  const existing = measurementOverlays.get('eyebrowSymmetry');
  if (existing && existing.length > 0) {
    // Overlay ancora in canvas: aggiorna solo la trasformata
    const img = existing[0];
    const natW = img._eyebrowNatW || img.width;
    const natH = img._eyebrowNatH || img.height;
    img.set({
      left: currentImage.left,
      top: currentImage.top,
      scaleX: currentImage.scaleX * (natW / img.width),
      scaleY: currentImage.scaleY * (natH / img.height),
      angle: currentImage.angle,
      originX: currentImage.originX || 'left',
      originY: currentImage.originY || 'top',
    });
    img.setCoords();
    fabricCanvas.renderAll();
    return;
  }

  // Overlay rimosso dalla mappa (es. da redrawAllMeasurementOverlays): ricostruisci dalla cache
  if (!window._eyebrowSymmetryCache) return;
  const { b64, natW, natH } = window._eyebrowSymmetryCache;
  fabric.Image.fromURL(b64, (img) => {
    if (!img || !fabricCanvas || !currentImage) return;
    img._eyebrowNatW = natW;
    img._eyebrowNatH = natH;
    img.set({
      left: currentImage.left,
      top: currentImage.top,
      scaleX: currentImage.scaleX * (natW / img.width),
      scaleY: currentImage.scaleY * (natH / img.height),
      angle: currentImage.angle,
      originX: currentImage.originX || 'left',
      originY: currentImage.originY || 'top',
      selectable: false, evented: false, hasControls: false, hasBorders: false, opacity: 1,
    });
    img.setCoords();
    fabricCanvas.add(img);
    fabricCanvas.renderAll();
    measurementOverlays.set('eyebrowSymmetry', [img]);
  });
}

async function _performEyebrowSymmetryAPI(button) {
  if (!fabricCanvas || !currentImage) {
    showToast('Carica prima un\'immagine', 'error');
    if (button) button.classList.remove('btn-active');
    return;
  }

  showToast('Analisi sopracciglia in corso...', 'info', 0);

  // 1. Ottieni l'elemento immagine originale e creane una copia alla risoluzione nativa
  const imgEl = currentImage.getElement();
  const natW = imgEl.naturalWidth || imgEl.width;
  const natH = imgEl.naturalHeight || imgEl.height;

  const offscreen = document.createElement('canvas');
  offscreen.width = natW;
  offscreen.height = natH;
  const ctx = offscreen.getContext('2d');
  ctx.drawImage(imgEl, 0, 0, natW, natH);
  const imageB64 = offscreen.toDataURL('image/jpeg', 0.92);

  // 2. Chiamata API
  const resp = await fetch('/api/eyebrow-symmetry', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: imageB64 }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Errore API');
  }
  const data = await resp.json();

  if (!data.face_detected) {
    showToast('Nessun volto rilevato', 'warning', 3000);
    if (button) button.classList.remove('btn-active');
    return;
  }

  // 3. Rimuovi overlay precedente se esiste
  if (measurementOverlays.has('eyebrowSymmetry')) {
    measurementOverlays.get('eyebrowSymmetry').forEach(o => fabricCanvas.remove(o));
    measurementOverlays.delete('eyebrowSymmetry');
  }

  // 4. Crea fabric.Image dall'overlay PNG trasparente
  await new Promise((resolve, reject) => {
    fabric.Image.fromURL(data.overlay_b64, (img) => {
      if (!img) { reject(new Error('Impossibile creare overlay')); return; }

      // Posiziona esattamente sopra currentImage (stessa scala, rotazione, posizione)
      img.set({
        left: currentImage.left,
        top: currentImage.top,
        scaleX: currentImage.scaleX * (natW / img.width),
        scaleY: currentImage.scaleY * (natH / img.height),
        angle: currentImage.angle,
        originX: currentImage.originX || 'left',
        originY: currentImage.originY || 'top',
        selectable: false,
        evented: false,
        hasControls: false,
        hasBorders: false,
        opacity: 1,
      });

      // Salva dimensioni native sull'oggetto e nella cache per riposizionamenti futuri senza API
      img._eyebrowNatW = natW;
      img._eyebrowNatH = natH;
      window._eyebrowSymmetryCache = { b64: data.overlay_b64, natW, natH };
      fabricCanvas.add(img);
      fabricCanvas.renderAll();
      measurementOverlays.set('eyebrowSymmetry', [img]);
      resolve();
    });
  });

  // 5. Aggiorna tabella misurazioni
  const leftArea = data.left_area;
  const rightArea = data.right_area;
  const maxArea = Math.max(leftArea, rightArea);
  const asymPercent = maxArea > 0 ? (Math.abs(leftArea - rightArea) / maxArea) * 100 : 0;

  let comparisonText, voiceMsg;
  if (asymPercent < 5) {
    comparisonText = 'Sopracciglia simmetriche';
    voiceMsg = 'Le due sopracciglia risultano simmetriche.';
  } else if (leftArea > rightArea) {
    comparisonText = `Sopracciglia sinistra più ampia (+${asymPercent.toFixed(1)}%)`;
    voiceMsg = `La sopracciglia sinistra è più ampia di circa ${asymPercent.toFixed(0)} percento.`;
  } else {
    comparisonText = `Sopracciglia destra più ampia (+${asymPercent.toFixed(1)}%)`;
    voiceMsg = `La sopracciglia destra è più ampia di circa ${asymPercent.toFixed(0)} percento.`;
  }

  ensureMeasurementsSectionOpen();
  addMeasurementToTable('✂️ Sopracciglio SX', leftArea.toFixed(0), 'px²');
  addMeasurementToTable('✂️ Sopracciglio DX', rightArea.toFixed(0), 'px²');
  addMeasurementToTable('⚖️ Asimmetria Sopr.', asymPercent.toFixed(1), '%');
  addMeasurementToTable('Valutazione', comparisonText, '');

  if (typeof voiceAssistant !== 'undefined' && voiceAssistant.speak) {
    voiceAssistant.speak(voiceMsg);
  }

  showToast(`✂️ ${comparisonText}`, asymPercent < 5 ? 'success' : 'warning', 3000);
}

window.measureEyebrowSymmetry = measureEyebrowSymmetry;

// Versione debounced per rotazioni/allineamenti rapidi (no API, solo reposizionamento)
(function () {
  let _ebSymTimer = null;
  window.redrawEyebrowSymmetryOverlay = function () {
    if (!window.activeMeasurements || !window.activeMeasurements.has('eyebrowSymmetry')) return;
    clearTimeout(_ebSymTimer);
    _ebSymTimer = setTimeout(_repositionEyebrowSymmetryOverlay, 50);
  };
}());

// === FINE DEL FILE ===