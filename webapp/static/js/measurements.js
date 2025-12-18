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

  // Gestisci sia valori numerici che stringhe
  const valueFormatted = typeof value === 'number' ? value.toFixed(1) : value;

  row.innerHTML += `
    <td>${valueFormatted}</td>
    <td>${unit}</td>
    <td>✅</td>
  `;

  console.log(`✅ Misurazione aggiunta: ${name} = ${valueFormatted} ${unit}`);

  // Apri automaticamente la sezione misurazioni se è chiusa
  ensureMeasurementsSectionOpen();
}

function ensureMeasurementsSectionOpen() {
  /**
   * Apre automaticamente la sezione Misurazioni se è chiusa
   */
  const measurementsSection = document.querySelector('.right-sidebar .section[data-expanded="false"]');
  if (measurementsSection) {
    const sectionHeader = measurementsSection.querySelector('.section-header');
    const sectionContent = measurementsSection.querySelector('.section-content');

    if (sectionHeader && sectionContent && sectionContent.style.display === 'none') {
      // Apri la sezione
      measurementsSection.dataset.expanded = 'true';
      sectionContent.style.display = 'block';
      const icon = sectionHeader.querySelector('.icon');
      if (icon) icon.textContent = '▼';
      console.log('📂 Sezione Misurazioni aperta automaticamente');
    }
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

    // Converti da pixel² a mm² usando il pixel ratio globale
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
    addMeasurementToTable('Area Emifaccia Sinistra', leftFaceArea, 'mm²');
    addMeasurementToTable('Area Emifaccia Destra', rightFaceArea, 'mm²');
    addMeasurementToTable('Differenza Assoluta', asymmetryAbsolute, 'mm²');
    addMeasurementToTable('Differenza Percentuale', asymmetryPercent, '%');
    addMeasurementToTable('Risultato Simmetria', resultDescription, '');

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
function calculatePolygonAreaFromPoints(points) {
  /**
   * Calcola l'area di un poligono usando la formula Shoelace (Gauss)
   * @param {Array} points - Array di punti con proprietà x e y
   * @returns {number} Area in unità quadrate
   */
  if (!points || points.length < 3) {
    console.warn('⚠️ calculatePolygonAreaFromPoints: punti insufficienti', points?.length);
    return 0;
  }

  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length;
    if (points[i] && points[j] &&
      typeof points[i].x === 'number' && typeof points[i].y === 'number' &&
      typeof points[j].x === 'number' && typeof points[j].y === 'number') {
      area += points[i].x * points[j].y;
      area -= points[j].x * points[i].y;
    } else {
      console.warn('⚠️ Punto non valido al calcolo area:', { i, point_i: points[i], point_j: points[j] });
    }
  }

  const result = Math.abs(area) / 2;
  console.log(`📐 Area calcolata: ${result.toFixed(2)} px² da ${points.length} punti`);
  return result;
}

// Mantieni anche il nome vecchio per compatibilità con altro codice
function calculatePolygonArea(points) {
  return calculatePolygonAreaFromPoints(points);
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