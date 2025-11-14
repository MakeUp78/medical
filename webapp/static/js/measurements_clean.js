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

// === FUNZIONI PRINCIPALI SISTEMA SEMPLIFICATO ===

function measureFaceWidth() {
  console.log('📐 Misurazione larghezza viso...');

  // === SISTEMA SEMPLIFICATO ===
  if (!currentLandmarks || currentLandmarks.length === 0) {
    console.log('🔍 Nessun landmark - Tentativo auto-rilevamento...');
    showToast('Rilevamento landmarks per misurazione...', 'info');
    autoDetectLandmarksOnImageChange().then(success => {
      if (success) {
        measureFaceWidth(); // Richiama se stesso
      } else {
        showToast('Impossibile rilevare landmarks per la misurazione', 'error');
      }
    });
    return;
  }

  try {
    // Punti estremi del viso (MediaPipe landmarks)
    const leftCheek = currentLandmarks[234];  // Punto sinistro
    const rightCheek = currentLandmarks[454]; // Punto destro

    if (leftCheek && rightCheek) {
      const distance = calculateDistance(leftCheek, rightCheek);
      addMeasurementToTable('Larghezza Viso', distance, 'mm');
      drawMeasurementLine(leftCheek, rightCheek, 'Larghezza Viso');
      showToast(`Larghezza viso: ${distance.toFixed(1)} mm`, 'success');
    }
  } catch (error) {
    console.error('Errore misurazione larghezza viso:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureFaceHeight() {
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
    // Punti estremi del viso
    const topForehead = currentLandmarks[10];  // Punto superiore
    const bottomChin = currentLandmarks[152];  // Punto inferiore

    if (topForehead && bottomChin) {
      const distance = calculateDistance(topForehead, bottomChin);
      addMeasurementToTable('Altezza Viso', distance, 'mm');
      drawMeasurementLine(topForehead, bottomChin, 'Altezza Viso');
      showToast(`Altezza viso: ${distance.toFixed(1)} mm`, 'success');
    }
  } catch (error) {
    console.error('Errore misurazione altezza viso:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureEyeDistance() {
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
    const leftEyeCenter = currentLandmarks[33];   // Centro occhio sinistro
    const rightEyeCenter = currentLandmarks[362]; // Centro occhio destro

    if (leftEyeCenter && rightEyeCenter) {
      const distance = calculateDistance(leftEyeCenter, rightEyeCenter);
      addMeasurementToTable('Distanza Occhi', distance, 'mm');
      drawMeasurementLine(leftEyeCenter, rightEyeCenter, 'Distanza Occhi');
      showToast(`Distanza occhi: ${distance.toFixed(1)} mm`, 'success');
    }
  } catch (error) {
    console.error('Errore misurazione distanza occhi:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureNoseWidth() {
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
    const leftNostril = currentLandmarks[31];  // Narice sinistra
    const rightNostril = currentLandmarks[35]; // Narice destra

    if (leftNostril && rightNostril) {
      const distance = calculateDistance(leftNostril, rightNostril);
      addMeasurementToTable('Larghezza Naso', distance, 'mm');
      drawMeasurementLine(leftNostril, rightNostril, 'Larghezza Naso');
      showToast(`Larghezza naso: ${distance.toFixed(1)} mm`, 'success');
    }
  } catch (error) {
    console.error('Errore misurazione larghezza naso:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

function measureMouthWidth() {
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
    const leftMouth = currentLandmarks[61];  // Angolo sinistro bocca
    const rightMouth = currentLandmarks[291]; // Angolo destro bocca

    if (leftMouth && rightMouth) {
      const distance = calculateDistance(leftMouth, rightMouth);
      addMeasurementToTable('Larghezza Bocca', distance, 'mm');
      drawMeasurementLine(leftMouth, rightMouth, 'Larghezza Bocca');
      showToast(`Larghezza bocca: ${distance.toFixed(1)} mm`, 'success');
    }
  } catch (error) {
    console.error('Errore misurazione larghezza bocca:', error);
    showToast('Errore durante la misurazione', 'error');
  }
}

// === FUNZIONI SUPPORTO ===

function addMeasurementToTable(name, value, unit) {
  // Aggiunge misurazione alla tabella risultati
  const measurementsTable = document.getElementById('measurements-table');
  if (!measurementsTable) return;

  const row = measurementsTable.insertRow();
  row.innerHTML = `
    <td>${name}</td>
    <td>${value.toFixed(1)} ${unit}</td>
    <td><button onclick="removeMeasurement(this)">Rimuovi</button></td>
  `;
}

function drawMeasurementLine(point1, point2, label) {
  // Disegna linea di misurazione sul canvas
  if (!fabricCanvas || !point1 || !point2) return;

  const line = new fabric.Line([point1.x, point1.y, point2.x, point2.y], {
    stroke: getRandomMeasurementColor(),
    strokeWidth: 2,
    selectable: false,
    evented: false,
    isMeasurementLine: true
  });

  fabricCanvas.add(line);
  fabricCanvas.renderAll();
}

function calculateDistance(point1, point2) {
  // Calcola distanza euclidea tra due punti
  if (!point1 || !point2) return 0;

  const dx = point2.x - point1.x;
  const dy = point2.y - point1.y;
  return Math.sqrt(dx * dx + dy * dy);
}

function getRandomMeasurementColor() {
  const color = MEASUREMENT_CONFIG.colors[measurementColorIndex % MEASUREMENT_CONFIG.colors.length];
  measurementColorIndex++;
  return color;
}

function removeMeasurement(button) {
  // Rimuove misurazione dalla tabella
  const row = button.closest('tr');
  if (row) row.remove();
}