/*
 * Sistema di misurazione webapp - Versione Semplificata
 * Auto-rilevamento landmarks + Calcoli immediati
 */

// Configurazione globale misurazioni
const MEASUREMENT_CONFIG = {
  precision: 1,
  defaultUnit: 'mm',
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

function calculateCentroid(points) {
  // points: array di oggetti {x,y}
  if (!points || points.length === 0) return { x: 0, y: 0 };
  let sx = 0, sy = 0;
  points.forEach(p => { sx += p.x; sy += p.y; });
  return { x: sx / points.length, y: sy / points.length };
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

function showMeasurementOverlay(measurementType) {
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
    case 'eyebrowAreas':
      performEyebrowAreasMeasurement();
      break;
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
}

function clearAllMeasurementOverlays() {
  /**
   * Rimuove tutti gli overlay di misurazione attivi
   */
  measurementOverlays.forEach((overlayObjects, measurementType) => {
    overlayObjects.forEach(obj => {
      if (fabricCanvas) {
        fabricCanvas.remove(obj);
      }
    });
  });

  measurementOverlays.clear();
  activeMeasurements.clear();

  // Reset tutti i pulsanti
  document.querySelectorAll('.btn-measure.btn-active').forEach(btn => {
    btn.classList.remove('btn-active');
  });

  if (fabricCanvas) {
    fabricCanvas.renderAll();
  }
}

// === FUNZIONI PRINCIPALI SISTEMA SEMPLIFICATO ===

function measureFaceWidth(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureFaceWidth"]');
  toggleMeasurementButton(button, 'faceWidth');
}

function performFaceWidthMeasurement() {
  console.log('📐 ===== INIZIO PERFORMFACEWIDTHMEASUREMENT =====');
  console.log('📐 Stato landmarks:', {
    currentLandmarks: !!currentLandmarks,
    length: currentLandmarks?.length || 0,
    primi3: currentLandmarks?.slice(0, 3) || 'none'
  });

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performFaceWidthMeasurement(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Usa zigomi per misura più precisa della larghezza del viso
    const leftCheekbone = currentLandmarks[447];  // Zigomo sinistro
    const rightCheekbone = currentLandmarks[227]; // Zigomo destro

    if (leftCheekbone && rightCheekbone) {
      console.log('📐 Misurazione larghezza viso (zigomi):', {
        leftCheekbone: { x: leftCheekbone.x.toFixed(1), y: leftCheekbone.y.toFixed(1) },
        rightCheekbone: { x: rightCheekbone.x.toFixed(1), y: rightCheekbone.y.toFixed(1) }
      });

      const distance = calculateDistance(leftCheekbone, rightCheekbone);

      // Crea gli oggetti overlay
      const overlayObjects = [];

      // Disegna linea e aggiungi alla lista overlay
      const measurementLine = createMeasurementLine(leftCheekbone, rightCheekbone, 'Larghezza Viso', '#FF6B35');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('faceWidth', overlayObjects);

      // Aggiungi alla tabella
      addMeasurementToTable('Larghezza Viso', distance, 'mm', 'faceWidth');
      showToast(`Larghezza viso: ${distance.toFixed(1)} mm`, 'success');
    } else {
      showToast('Landmarks degli zigomi non trovati', 'warning');
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
    const bottomChin = currentLandmarks[175];    // Punto più basso del mento

    if (topForehead && bottomChin) {
      console.log('📏 Misurazione altezza viso (fronte-mento):', {
        topForehead: { x: topForehead.x.toFixed(1), y: topForehead.y.toFixed(1) },
        bottomChin: { x: bottomChin.x.toFixed(1), y: bottomChin.y.toFixed(1) }
      });

      const distance = calculateDistance(topForehead, bottomChin);

      // Crea gli oggetti overlay
      const overlayObjects = [];
      const measurementLine = createMeasurementLine(topForehead, bottomChin, 'Altezza Viso', '#F7931E');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('faceHeight', overlayObjects);

      // Aggiungi alla tabella
      addMeasurementToTable('Altezza Viso', distance, 'mm', 'faceHeight');
      showToast(`Altezza viso: ${distance.toFixed(1)} mm`, 'success');
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
  console.log('👁️ Misurazione distanza occhi...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureEyeDistance(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Usa angoli interni degli occhi per misurazione corretta della distanza interpupillare
    const leftEyeInnerCorner = currentLandmarks[133];  // Angolo interno occhio sinistro
    const rightEyeInnerCorner = currentLandmarks[362]; // Angolo interno occhio destro

    if (leftEyeInnerCorner && rightEyeInnerCorner) {
      console.log('👁️ Misurazione distanza occhi (angoli interni):', {
        leftEyeInner: { x: leftEyeInnerCorner.x.toFixed(1), y: leftEyeInnerCorner.y.toFixed(1) },
        rightEyeInner: { x: rightEyeInnerCorner.x.toFixed(1), y: rightEyeInnerCorner.y.toFixed(1) }
      });

      const distance = calculateDistance(leftEyeInnerCorner, rightEyeInnerCorner);

      // Crea gli oggetti overlay
      const overlayObjects = [];
      const measurementLine = createMeasurementLine(leftEyeInnerCorner, rightEyeInnerCorner, 'Distanza Interpupillare', '#FFD23F');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('eyeDistance', overlayObjects);

      // Aggiungi alla tabella
      addMeasurementToTable('Distanza Interpupillare', distance, 'mm', 'eyeDistance');
      showToast(`Distanza interpupillare: ${distance.toFixed(1)} mm`, 'success');
    } else {
      showToast('Landmarks degli angoli interni degli occhi non trovati', 'warning');
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

      const distance = calculateDistance(leftNoseWing, rightNoseWing);

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

    if (leftMouthCorner && rightMouthCorner) {
      console.log('👄 Misurazione larghezza bocca (angoli):', {
        leftCorner: { x: leftMouthCorner.x.toFixed(1), y: leftMouthCorner.y.toFixed(1) },
        rightCorner: { x: rightMouthCorner.x.toFixed(1), y: rightMouthCorner.y.toFixed(1) }
      });

      const distance = calculateDistance(leftMouthCorner, rightMouthCorner);

      // Crea gli oggetti overlay
      const overlayObjects = [];
      const measurementLine = createMeasurementLine(leftMouthCorner, rightMouthCorner, 'Larghezza Bocca', '#118AB2');
      overlayObjects.push(measurementLine);

      // Salva overlay per questa misurazione
      measurementOverlays.set('mouthWidth', overlayObjects);

      // Aggiungi alla tabella
      addMeasurementToTable('Larghezza Bocca', distance, 'mm', 'mouthWidth');
      showToast(`Larghezza bocca: ${distance.toFixed(1)} mm`, 'success');
    } else {
      showToast('Landmarks degli angoli della bocca non trovati', 'warning');
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

      const distance = calculateDistance(noseBridge, noseTip);

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

function addMeasurementToTable(name, value, unit, measurementType = null) {
  // Aggiunge misurazione alla tabella risultati
  const measurementsTable = document.getElementById('measurements-table');
  if (!measurementsTable) {
    console.error('❌ Tabella misurazioni non trovata');
    return;
  }

  // Trova il tbody o crea se non esiste
  let tbody = measurementsTable.querySelector('tbody');
  if (!tbody) {
    tbody = document.createElement('tbody');
    measurementsTable.appendChild(tbody);
  }

  const row = tbody.insertRow();
  const typeCell = document.createElement('td');
  typeCell.textContent = name;
  if (measurementType) {
    typeCell.dataset.measurementType = measurementType;
  }

  row.appendChild(typeCell);
  row.innerHTML += `
    <td>${value.toFixed(1)}</td>
    <td>${unit}</td>
    <td>✅</td>
  `;

  console.log(`✅ Misurazione aggiunta: ${name} = ${value.toFixed(1)} ${unit}`);
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

  const distance = calculateDistance(point1, point2);
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

function calculateDistance(point1, point2) {
  // Calcola distanza euclidea tra due punti (coordinate raw)
  if (!point1 || !point2) return 0;

  const dx = point2.x - point1.x;
  const dy = point2.y - point1.y;
  return Math.sqrt(dx * dx + dy * dy);
}

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
  console.log('👁️ Misurazione aree occhi...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
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
    clearPreviousMeasurements();

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

      addMeasurementToTable('Area Occhio Sinistro', leftArea, 'mm²');
      addMeasurementToTable('Area Occhio Destro', rightArea, 'mm²');

      console.log('👁️ Aree occhi calcolate:', {
        leftArea: leftArea.toFixed(2),
        rightArea: rightArea.toFixed(2),
        leftPoints: leftEyePoints.length,
        rightPoints: rightEyePoints.length
      });

      showToast(`Aree occhi calcolate: S=${leftArea.toFixed(1)}mm², D=${rightArea.toFixed(1)}mm²`, 'success');
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
    clearPreviousMeasurements();

    // Usa landmark più precisi per la larghezza della fronte
    const leftTemple = currentLandmarks[21];   // Tempia sinistra
    const rightTemple = currentLandmarks[251]; // Tempia destra

    if (leftTemple && rightTemple) {
      console.log('🤔 Misurazione larghezza fronte (tempie):', {
        leftTemple: { x: leftTemple.x.toFixed(1), y: leftTemple.y.toFixed(1) },
        rightTemple: { x: rightTemple.x.toFixed(1), y: rightTemple.y.toFixed(1) }
      });

      const distance = calculateDistance(leftTemple, rightTemple);

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

    // Asse centrale del viso (usando punti anatomici centrali)
    const noseTip = currentLandmarks[1];           // Punta del naso
    const upperLip = currentLandmarks[12];         // Labbro superiore centro
    const lowerLip = currentLandmarks[15];         // Labbro inferiore centro
    const foreheadCenter = currentLandmarks[9];    // Centro fronte

    if (!noseTip || !upperLip || !lowerLip || !foreheadCenter) {
      showToast('Landmark centrali mancanti per calcolare l\'asse del viso', 'warning');
      return;
    }

    // Calcola l'asse centrale X come media dei punti centrali
    const faceCenterX = (noseTip.x + upperLip.x + lowerLip.x + foreheadCenter.x) / 4;

    console.log('⚖️ Asse centrale calcolato:', { faceCenterX, noseTipX: noseTip.x });

    // Estrai tutti i landmark del contorno validi
    const faceContourPoints = faceContourLandmarks
      .map(i => currentLandmarks[i])
      .filter(point => point && point.x !== undefined && point.y !== undefined);

    if (faceContourPoints.length < 10) {
      showToast('Landmark perimetrali insufficienti', 'warning');
      return;
    }

    // === METODO MIGLIORATO PER DIVISIONE EMIFACCE ===

    // Ordina tutti i punti del contorno per creare un percorso continuo
    const centerPoint = {
      x: faceCenterX,
      y: (Math.min(...faceContourPoints.map(p => p.y)) + Math.max(...faceContourPoints.map(p => p.y))) / 2
    };

    // Ordina i punti del contorno in senso orario partendo dall'alto
    const sortedContourPoints = faceContourPoints.sort((a, b) => {
      const angleA = Math.atan2(a.y - centerPoint.y, a.x - centerPoint.x);
      const angleB = Math.atan2(b.y - centerPoint.y, b.x - centerPoint.x);
      return angleA - angleB;
    });

    // Punti dell'asse centrale più dettagliati
    const detailedAxisPoints = [
      { x: faceCenterX, y: Math.min(...faceContourPoints.map(p => p.y)) },      // Top fronte
      { x: faceCenterX, y: foreheadCenter.y },                                   // Centro fronte  
      { x: faceCenterX, y: (foreheadCenter.y + noseTip.y) / 2 },               // Tra fronte e naso
      { x: faceCenterX, y: noseTip.y },                                         // Punta naso
      { x: faceCenterX, y: (noseTip.y + upperLip.y) / 2 },                     // Tra naso e bocca
      { x: faceCenterX, y: upperLip.y },                                        // Labbro superiore
      { x: faceCenterX, y: lowerLip.y },                                        // Labbro inferiore
      { x: faceCenterX, y: (lowerLip.y + Math.max(...faceContourPoints.map(p => p.y))) / 2 }, // Metà mento
      { x: faceCenterX, y: Math.max(...faceContourPoints.map(p => p.y)) }       // Bottom mento
    ];

    // === COSTRUZIONE POLIGONO EMIFACCIA SINISTRA ===
    const leftFacePolygon = [];

    // Aggiungi punti dell'asse centrale
    leftFacePolygon.push(...detailedAxisPoints);

    // Aggiungi tutti i punti del contorno che appartengono all'emifaccia sinistra
    for (const point of sortedContourPoints) {
      if (point.x <= faceCenterX + 8) { // Tolleranza aumentata a 8 pixel
        leftFacePolygon.push(point);
      }
    }

    // === COSTRUZIONE POLIGONO EMIFACCIA DESTRA ===  
    const rightFacePolygon = [];

    // Copia i punti dell'asse per evitare problemi con reverse()
    const rightAxisPoints = [...detailedAxisPoints];
    rightFacePolygon.push(...rightAxisPoints);

    // Aggiungi tutti i punti del contorno che appartengono all'emifaccia destra
    for (const point of sortedContourPoints) {
      if (point.x >= faceCenterX - 8) { // Tolleranza aumentata a 8 pixel
        rightFacePolygon.push(point);
      }
    }

    // Aggiungi punti specifici della fronte destra per colmare il gap
    const foreheadRightPoints = faceContourPoints.filter(p =>
      p.x > faceCenterX - 15 && p.x < faceCenterX + 15 &&
      p.y < foreheadCenter.y + 20 // Zona fronte
    );
    rightFacePolygon.push(...foreheadRightPoints);

    // Rimuovi duplicati e riordina i poligoni per garantire continuità
    const uniqueLeftPoints = leftFacePolygon.filter((point, index, arr) =>
      index === 0 || !(arr[index - 1].x === point.x && arr[index - 1].y === point.y)
    );

    const uniqueRightPoints = rightFacePolygon.filter((point, index, arr) =>
      index === 0 || !(arr[index - 1].x === point.x && arr[index - 1].y === point.y)
    );

    const leftFacePolygonSorted = uniqueLeftPoints.sort((a, b) => {
      const angleA = Math.atan2(a.y - centerPoint.y, a.x - centerPoint.x);
      const angleB = Math.atan2(b.y - centerPoint.y, b.x - centerPoint.x);
      return angleA - angleB;
    });

    const rightFacePolygonSorted = uniqueRightPoints.sort((a, b) => {
      const angleA = Math.atan2(a.y - centerPoint.y, a.x - centerPoint.x);
      const angleB = Math.atan2(b.y - centerPoint.y, b.x - centerPoint.x);
      return angleB - angleA;
    });

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

    // Calcola le aree delle emifacce con i poligoni migliorati
    const leftFaceArea = calculatePolygonArea(leftFacePolygonSorted);
    const rightFaceArea = calculatePolygonArea(rightFacePolygonSorted);

    // Crea overlay visuali
    const overlayObjects = [];

    // Poligono emifaccia SINISTRA con algoritmo migliorato
    const leftFaceAreaPolygon = createAreaPolygon(leftFacePolygonSorted, 'Emifaccia Sinistra', '#FF6B35');
    if (leftFaceAreaPolygon) overlayObjects.push(leftFaceAreaPolygon);

    // Poligono emifaccia DESTRA con algoritmo migliorato
    const rightFaceAreaPolygon = createAreaPolygon(rightFacePolygonSorted, 'Emifaccia Destra', '#6B73FF');
    if (rightFaceAreaPolygon) overlayObjects.push(rightFaceAreaPolygon);

    // Linea dell'asse centrale
    try {
      const axisTop = window.transformLandmarkCoordinate(axisPoints[0]);
      const axisBottom = window.transformLandmarkCoordinate(axisPoints[3]);

      const axisLine = new fabric.Line([axisTop.x, axisTop.y, axisBottom.x, axisBottom.y], {
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

    // Etichette comparative
    try {
      const transformedLeft = leftFacePolygonSorted.map(p => window.transformLandmarkCoordinate(p));
      const transformedRight = rightFacePolygonSorted.map(p => window.transformLandmarkCoordinate(p));
      const leftCentroid = calculateCentroid(transformedLeft);
      const rightCentroid = calculateCentroid(transformedRight);

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
      const labelLeft = new fabric.Text(`${leftFaceArea.toFixed(1)}mm²\n(${leftPercentage.toFixed(1)}%)`, {
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

      const labelRight = new fabric.Text(`${rightFaceArea.toFixed(1)}mm²\n(${rightPercentage.toFixed(1)}%)`, {
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

    // Aggiungi alla tabella risultati
    addMeasurementToTable('Area Emifaccia Sinistra', leftFaceArea, 'mm²');
    addMeasurementToTable('Area Emifaccia Destra', rightFaceArea, 'mm²');
    addMeasurementToTable('Asimmetria Totale', Math.abs(leftFaceArea - rightFaceArea), 'mm²');

    console.log('⚖️ RISULTATI emifacce:', {
      leftFaceArea: leftFaceArea.toFixed(2),
      rightFaceArea: rightFaceArea.toFixed(2),
      asymmetry: Math.abs(leftFaceArea - rightFaceArea).toFixed(2)
    });

    showToast(`Emifacce: S=${leftFaceArea.toFixed(1)}mm² | D=${rightFaceArea.toFixed(1)}mm²`, 'success');

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
      const distance = calculateDistance(leftCheek, rightCheek);

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

function measureEyebrowAreas(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureEyebrowAreas"]');
  toggleMeasurementButton(button, 'eyebrowAreas');
}

function performEyebrowAreasMeasurement() {
  console.log('✂️ NUOVO: Misurazione aree sopracciglia con landmark corretti...');

  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        performEyebrowAreasMeasurement();
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
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

    console.log('✂️ Landmark sopracciglia trovati:', {
      leftBrowPoints: leftBrowPoints.length,
      rightBrowPoints: rightBrowPoints.length,
      leftLandmarks: leftBrowLandmarks,
      rightLandmarks: rightBrowLandmarks
    });

    if (leftBrowPoints.length >= 3 && rightBrowPoints.length >= 3) {
      // Calcola aree
      const leftBrowArea = calculatePolygonArea(leftBrowPoints);
      const rightBrowArea = calculatePolygonArea(rightBrowPoints);

      // Crea overlay
      const overlayObjects = [];

      // Poligoni delle sopracciglia con colori distinti
      const leftBrowPolygon = createAreaPolygon(leftBrowPoints, 'Area Sopracciglio Sinistro', '#FF6B35');
      const rightBrowPolygon = createAreaPolygon(rightBrowPoints, 'Area Sopracciglio Destro', '#6B73FF');

      if (leftBrowPolygon) overlayObjects.push(leftBrowPolygon);
      if (rightBrowPolygon) overlayObjects.push(rightBrowPolygon);

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

        const labelLeft = new fabric.Text(`${leftBrowArea.toFixed(1)}mm²`, {
          left: leftCentroid.x - 20,
          top: leftCentroid.y - 25,
          fontSize: 12,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(255,107,53,0.9)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true
        });

        const labelRight = new fabric.Text(`${rightBrowArea.toFixed(1)}mm²`, {
          left: rightCentroid.x - 20,
          top: rightCentroid.y - 25,
          fontSize: 12,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(107,115,255,0.9)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true
        });

        const comparisonLabel = new fabric.Text(comparisonText, {
          left: (leftCentroid.x + rightCentroid.x) / 2 - 40,
          top: Math.min(leftCentroid.y, rightCentroid.y) - 50,
          fontSize: 14,
          fill: '#FFFFFF',
          backgroundColor: 'rgba(0,0,0,0.8)',
          selectable: false,
          evented: false,
          isMeasurementLabel: true
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

      // Aggiungi alla tabella
      addMeasurementToTable('Area Sopracciglio Sinistro', leftBrowArea, 'mm²');
      addMeasurementToTable('Area Sopracciglio Destro', rightBrowArea, 'mm²');

      console.log('✂️ RISULTATI sopracciglia:', {
        leftBrowArea: leftBrowArea.toFixed(2),
        rightBrowArea: rightBrowArea.toFixed(2),
        difference: Math.abs(leftBrowArea - rightBrowArea).toFixed(2)
      });

      showToast(`Aree sopracciglia: S=${leftBrowArea.toFixed(1)}mm², D=${rightBrowArea.toFixed(1)}mm²`, 'success');
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
    // Pulisce misurazioni precedenti
    clearPreviousMeasurements();

    // Punti del mento
    const leftJaw = currentLandmarks[172];  // Mandibola sinistra
    const rightJaw = currentLandmarks[397]; // Mandibola destra

    if (leftJaw && rightJaw) {
      drawMeasurementLine(leftJaw, rightJaw, 'Larghezza Mento');
      const distance = calculateDistance(leftJaw, rightJaw);
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
    // Pulisce misurazioni precedenti
    clearPreviousMeasurements();

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
    // Pulisce misurazioni precedenti
    clearPreviousMeasurements();

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
    // Pulisce misurazioni precedenti
    clearPreviousMeasurements();

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
    // Pulisce misurazioni precedenti
    clearPreviousMeasurements();

    // Calcola varie proporzioni
    const faceWidth = calculateDistance(currentLandmarks[234], currentLandmarks[454]);
    const faceHeight = calculateDistance(currentLandmarks[10], currentLandmarks[152]);
    const eyeDistance = calculateDistance(currentLandmarks[33], currentLandmarks[362]);

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
    // Pulisce misurazioni precedenti
    clearPreviousMeasurements();

    // Distanze chiave del viso
    const eyeToNose = calculateDistance(currentLandmarks[27], currentLandmarks[1]);
    const noseToMouth = calculateDistance(currentLandmarks[1], currentLandmarks[13]);
    const mouthToChin = calculateDistance(currentLandmarks[13], currentLandmarks[152]);

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
function calculatePolygonArea(points) {
  if (!points || points.length < 3) return 0;

  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length;
    if (points[i] && points[j]) {
      area += points[i].x * points[j].y;
      area -= points[j].x * points[i].y;
    }
  }
  return Math.abs(area) / 2;
}

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
  showToast('Misurazione proporzioni - In sviluppo', 'info');
}

function measureKeyDistances(event) {
  const button = event ? event.target : document.querySelector('[onclick*="measureKeyDistances"]');
  toggleMeasurementButton(button, 'keyDistances');
}

function performKeyDistancesMeasurement() {
  showToast('Misurazione distanze chiave - In sviluppo', 'info');
}

// === FINE DEL FILE ===