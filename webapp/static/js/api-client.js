/*
 * Configurazione API Backend
 * Gestisce la comunicazione con il server FastAPI
 */

// Configurazione endpoint API
const API_CONFIG = {
  baseURL: 'http://127.0.0.1:8001',
  endpoints: {
    analyze: '/api/analyze',
    batch: '/api/batch-analyze',
    health: '/health',
    config: '/api/config/validate',
    landmarks: '/api/landmarks/info',
    greenDotsAnalyze: '/api/green-dots/analyze',
    greenDotsInfo: '/api/green-dots/info',
    greenDotsTest: '/api/green-dots/test'
  },
  timeout: 30000 // 30 secondi
};

// Debug log per verificare la configurazione
console.log('🔧 API_CONFIG caricata:', API_CONFIG.baseURL);
console.log('🔧 Timestamp caricamento:', new Date().toISOString());

// === FUNZIONI API ===

/**
 * Controlla se l'API backend è disponibile
 */
async function checkAPIHealth() {
  try {
    // Usa la configurazione API_CONFIG 
    const baseURL = API_CONFIG.baseURL;

    // Aggiungi timestamp per evitare cache
    const timestamp = new Date().getTime();
    const healthURL = `${baseURL}${API_CONFIG.endpoints.health}?t=${timestamp}`;
    console.log('🔍 Checking API Health at:', healthURL);
    console.log('🔍 API_CONFIG.baseURL:', API_CONFIG.baseURL);

    const response = await fetch(healthURL, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache'
      }
    });

    if (response.ok) {
      const data = await response.json();
      console.log('✅ API Backend connesso:', data);
      updateAPIStatus(true, data);
      return data;
    } else {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (error) {
    console.error('❌ API Backend non disponibile:', error);
    updateAPIStatus(false, error.message);
    return null;
  }
}

/**
 * Aggiorna lo status dell'API nell'interfaccia
 */
function updateAPIStatus(isConnected, data) {
  const statusElement = document.getElementById('api-status');
  if (statusElement) {
    if (isConnected) {
      statusElement.className = 'badge badge-success';
      statusElement.textContent = `🌐 API: ${data.status}`;
    } else {
      statusElement.className = 'badge badge-error';
      statusElement.textContent = '🔴 API: offline';
    }
  }
}

/**
 * Analizza un'immagine tramite l'API backend
 */
async function analyzeImageViaAPI(imageBase64, config = null) {
  try {
    console.log('🔍 Invio analisi immagine all\'API...');

    const payload = {
      image: imageBase64,
      config: config || {
        weights: scoringWeights,
        tolerances: {
          nose: 0.3,
          mouth: 0.4,
          symmetry: 0.7
        }
      }
    };

    // Usa la configurazione API_CONFIG
    const baseURL = API_CONFIG.baseURL;
    const analyzeURL = `${baseURL}${API_CONFIG.endpoints.analyze}`;
    console.log('🔍 Sending analysis request to:', analyzeURL);
    console.log('🔍 API_CONFIG.baseURL:', API_CONFIG.baseURL);

    const response = await fetch(analyzeURL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (response.ok) {
      const result = await response.json();
      console.log('🎯 API Response Details:', {
        session_id: result.session_id,
        landmarks_count: result.landmarks?.length || 0,
        score: result.score,
        frontality_score: result.frontality_score,
        pose_angles: result.pose_angles,
        image_info: result.image_info,
        first_3_landmarks: result.landmarks?.slice(0, 3) || []
      });

      // Aggiorna interfaccia con risultati
      updateAnalysisResults(result);
      return result;
    } else {
      const error = await response.json();
      console.error('❌ Dettagli errore API:', error);
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

  } catch (error) {
    console.error('❌ Errore analisi API:', error);
    console.error('❌ Payload inviato:', payload);
    updateStatus(`Errore analisi: ${error.message}`);
    return null;
  }
}

/**
 * Valida la configurazione scoring tramite API
 */
async function validateScoringConfig(config) {
  try {
    const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.config}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(config)
    });

    if (response.ok) {
      const result = await response.json();
      console.log('✅ Config validata:', result);
      return result;
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Errore validazione');
    }

  } catch (error) {
    console.error('❌ Errore validazione config:', error);
    return { valid: false, issues: [error.message] };
  }
}

/**
 * Ottiene informazioni sui landmarks dall'API
 */
async function getLandmarksInfo() {
  try {
    const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.landmarks}`);

    if (response.ok) {
      const info = await response.json();
      console.log('📍 Info landmarks ricevute:', info);
      return info;
    } else {
      throw new Error(`HTTP ${response.status}`);
    }

  } catch (error) {
    console.error('❌ Errore info landmarks:', error);
    return null;
  }
}

/**
 * Aggiorna l'interfaccia con i risultati dell'analisi
 */
function updateAnalysisResults(analysisResult) {
  // Aggiorna score principale
  const scoreElement = document.getElementById('current-score');
  if (scoreElement) {
    // Usa frontality_score invece di score se disponibile
    const displayScore = analysisResult.frontality_score || analysisResult.score;
    scoreElement.textContent = displayScore.toFixed(3);
    scoreElement.style.color = getFrontalityColor(displayScore);
  }

  // Aggiorna angoli di posa se disponibili
  if (analysisResult.pose_angles) {
    updatePoseAnglesDisplay(analysisResult.pose_angles);
  }

  // Aggiorna componenti score
  updateScoreComponents(analysisResult.score_components);

  // Aggiorna landmarks
  if (analysisResult.landmarks) {
    currentLandmarks = analysisResult.landmarks;
    updateLandmarksTable(analysisResult.landmarks);

    // Ridisegna canvas con landmarks
    if (currentImage && typeof drawLandmarksOnCanvas === 'function') {
      console.log('🎨 Chiamando drawLandmarksOnCanvas con', analysisResult.landmarks.length, 'landmarks');
      drawLandmarksOnCanvas(analysisResult.landmarks);
    } else {
      if (!currentImage) {
        console.warn('⚠️ currentImage non definita, landmarks non disegnati');
      }
      if (typeof drawLandmarksOnCanvas !== 'function') {
        console.warn('⚠️ drawLandmarksOnCanvas non disponibile, landmarks non disegnati');
      }
    }
  }

  // Aggiorna info sessione
  updateSessionInfo(analysisResult);

  const frontalityScore = analysisResult.frontality_score || analysisResult.score;
  const poseInfo = analysisResult.pose_angles ?
    `P:${analysisResult.pose_angles.pitch.toFixed(1)}° Y:${analysisResult.pose_angles.yaw.toFixed(1)}° R:${analysisResult.pose_angles.roll.toFixed(1)}°` : '';

  updateStatus(`✅ Analisi completata - Score: ${frontalityScore.toFixed(3)} | ${poseInfo}`);
}

/**
 * Aggiorna la visualizzazione degli angoli di posa
 */
function updatePoseAnglesDisplay(poseAngles) {
  // Aggiorna elementi esistenti se presenti
  const elements = [
    { id: 'pitch-display', value: poseAngles.pitch, label: 'Pitch' },
    { id: 'yaw-display', value: poseAngles.yaw, label: 'Yaw' },
    { id: 'roll-display', value: poseAngles.roll, label: 'Roll' }
  ];

  elements.forEach(({ id, value, label }) => {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = `${label}: ${value.toFixed(1)}°`;
      element.style.color = getPoseAngleColor(Math.abs(value));
    }
  });

  // Crea display se non esiste
  createPoseAnglesDisplayIfNeeded(poseAngles);
}

/**
 * Crea il display degli angoli di posa se non esiste
 */
function createPoseAnglesDisplayIfNeeded(poseAngles) {
  const container = document.getElementById('frontality-score') ||
    document.querySelector('.frontality-display');

  if (!container) return;

  // Verifica se gli elementi esistono già
  if (document.getElementById('pitch-display')) return;

  // Crea elementi di visualizzazione angoli
  const anglesDiv = document.createElement('div');
  anglesDiv.className = 'pose-angles-display';
  anglesDiv.style.cssText = 'margin-top: 10px; font-size: 12px; display: flex; gap: 10px;';

  anglesDiv.innerHTML = `
    <span id="pitch-display">Pitch: ${poseAngles.pitch.toFixed(1)}°</span>
    <span id="yaw-display">Yaw: ${poseAngles.yaw.toFixed(1)}°</span>  
    <span id="roll-display">Roll: ${poseAngles.roll.toFixed(1)}°</span>
  `;

  container.appendChild(anglesDiv);

  // Applica colori
  updatePoseAnglesDisplay(poseAngles);
}

/**
 * Restituisce il colore per un angolo di posa
 */
function getPoseAngleColor(absoluteAngle) {
  if (absoluteAngle <= 10) return '#00ff00';  // Verde - ottimo
  if (absoluteAngle <= 20) return '#ffff00';  // Giallo - buono
  if (absoluteAngle <= 30) return '#ff8800';  // Arancione - accettabile
  return '#ff0000';  // Rosso - scarso
}

/**
 * Restituisce il colore per il punteggio di frontalità (se non definita altrove)
 */
function getFrontalityColor(score) {
  if (score >= 0.8) return '#00ff00'; // Verde - ottima frontalità
  if (score >= 0.6) return '#ffff00'; // Giallo - buona frontalità
  if (score >= 0.4) return '#ff8800'; // Arancione - media frontalità
  return '#ff0000'; // Rosso - scarsa frontalità
}

/**
 * Aggiorna i componenti dello score nell'interfaccia
 */
function updateScoreComponents(components) {
  const elements = {
    'nose-score': components.nose,
    'mouth-score': components.mouth,
    'symmetry-score': components.symmetry,
    'eye-score': components.eye
  };

  for (const [elementId, score] of Object.entries(elements)) {
    const element = document.getElementById(elementId);
    if (element) {
      element.textContent = `${(score * 100).toFixed(1)}%`;
    }
  }
}

/**
 * Aggiorna le informazioni della sessione
 */
function updateSessionInfo(result) {
  const infoElement = document.getElementById('session-info');
  if (infoElement) {
    const frontalityInfo = result.frontality_score ?
      `<div>Frontalità: ${result.frontality_score.toFixed(3)}</div>` : '';
    const poseInfo = result.pose_angles ?
      `<div>Pose: P${result.pose_angles.pitch.toFixed(0)}° Y${result.pose_angles.yaw.toFixed(0)}° R${result.pose_angles.roll.toFixed(0)}°</div>` : '';

    infoElement.innerHTML = `
            <div>Session: ${result.session_id.substring(0, 8)}...</div>
            <div>Landmarks: ${result.landmarks.length}</div>
            ${frontalityInfo}
            ${poseInfo}
            <div>Timestamp: ${new Date(result.timestamp).toLocaleTimeString()}</div>
        `;
  }
}

// === INIZIALIZZAZIONE ===

// Controlla connessione API all'avvio
document.addEventListener('DOMContentLoaded', function () {
  console.log('🌐 Inizializzazione connessione API...');

  // Controlla API dopo 1 secondo per dare tempo al caricamento
  setTimeout(checkAPIHealth, 1000);

  // Controlla API ogni 30 secondi
  setInterval(checkAPIHealth, 30000);
});

/**
 * Analizza immagine per rilevare green dots tramite API
 */
async function analyzeGreenDotsViaAPI(imageBase64, parameters = {}) {
  try {
    const url = `${API_CONFIG.baseURL}${API_CONFIG.endpoints.greenDotsAnalyze}`;
    console.log('🟢 API Green Dots URL:', url);

    const defaultParams = {
      hue_range: [60, 150],
      saturation_min: 15,
      value_range: [15, 95],
      cluster_size_range: [2, 150],
      clustering_radius: 2
    };

    const payload = {
      image: imageBase64,
      ...defaultParams,
      ...parameters
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(API_CONFIG.timeout)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('🟢 Risposta API Green Dots:', result);

    return result;

  } catch (error) {
    console.error('❌ Errore API Green Dots:', error);
    throw error;
  }
}

/**
 * Ottiene informazioni sui parametri Green Dots
 */
async function getGreenDotsInfo() {
  try {
    const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.greenDotsInfo}`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();

  } catch (error) {
    console.error('❌ Errore recupero info Green Dots:', error);
    throw error;
  }
}

// Esporta funzioni per uso globale
window.analyzeImageViaAPI = analyzeImageViaAPI;
window.validateScoringConfig = validateScoringConfig;
window.getLandmarksInfo = getLandmarksInfo;
window.analyzeGreenDotsViaAPI = analyzeGreenDotsViaAPI;
window.getGreenDotsInfo = getGreenDotsInfo;
window.checkAPIHealth = checkAPIHealth;