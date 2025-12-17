/*
 * Sistema di Scoring - Replica del sistema di scoring dell'app desktop
 */

// Configurazione scoring identica all'app desktop
let scoringSystem = {
    weights: {
        nose: 0.30,
        mouth: 0.25,
        symmetry: 0.25,
        eye: 0.20
    },
    
    tolerances: {
        nose: 0.3,
        mouth: 0.4,
        symmetry: 0.7
    },
    
    bonuses: {
        roll_high: 1.03,
        roll_med: 1.015
    },
    
    penalties: {
        threshold_nose: 0.4,
        threshold_mouth: 0.4,
        threshold_symmetry: 0.6,
        factor: 0.3
    }
};

// === GESTIONE SLIDERS PESI ===

function updateWeight(type, value) {
    const numValue = parseFloat(value);
    scoringSystem.weights[type] = numValue;
    
    // Aggiorna display valore
    const valueSpan = document.getElementById(`${type}-value`);
    if (valueSpan) {
        valueSpan.textContent = numValue.toFixed(2);
    }
    
    // Ricalcola score corrente
    recalculateCurrentScore();
    
    // Aggiorna colore slider
    updateSliderColor(type, numValue);
    
    console.log(`⚖️ Peso ${type} aggiornato:`, numValue);
}

function updateSliderColor(type, value) {
    const slider = document.getElementById(`${type}-slider`);
    if (!slider) return;
    
    // Colori basati sul valore (da rosso a verde)
    const hue = value * 120; // 0 = rosso, 120 = verde
    const color = `hsl(${hue}, 70%, 50%)`;
    
    // Aggiorna colore thumb dello slider
    const style = document.createElement('style');
    style.textContent = `
        #${type}-slider::-webkit-slider-thumb {
            background: ${color} !important;
        }
    `;
    
    // Rimuovi stile precedente se esiste
    const oldStyle = document.querySelector(`#${type}-slider-style`);
    if (oldStyle) {
        oldStyle.remove();
    }
    
    style.id = `${type}-slider-style`;
    document.head.appendChild(style);
}

function recalculateCurrentScore() {
    if (!currentLandmarks || currentLandmarks.length === 0) {
        updateScoringInfo(0);
        return;
    }
    
    try {
        // Calcola score con i pesi correnti
        const score = calculateFacialScore(currentLandmarks, currentImage);
        updateScoringInfo(score);
        
        // Aggiorna quality badge
        updateQualityBadge(score);
        
    } catch (error) {
        console.error('Errore calcolo score:', error);
        updateScoringInfo(0);
    }
}

function updateScoringInfo(score) {
    const info = document.getElementById('scoring-info');
    if (info) {
        info.textContent = `Score corrente: ${score.toFixed(3)}`;
        
        // Colore basato sul punteggio
        if (score >= 0.8) {
            info.style.color = '#28a745';
            info.style.borderColor = '#28a745';
        } else if (score >= 0.6) {
            info.style.color = '#ffc107';
            info.style.borderColor = '#ffc107';
        } else {
            info.style.color = '#dc3545';
            info.style.borderColor = '#dc3545';
        }
    }
}

// === PRESET PESI ===

function resetWeights() {
    scoringSystem.weights = {
        nose: 0.30,
        mouth: 0.25,
        symmetry: 0.25,
        eye: 0.20
    };
    
    updateAllSliders();
    recalculateCurrentScore();
    
    showToast('Pesi resettati ai valori default', 'info');
    console.log('🔄 Pesi resettati');
}

function presetNoseFocus() {
    scoringSystem.weights = {
        nose: 0.50,
        mouth: 0.25,
        symmetry: 0.15,
        eye: 0.10
    };
    
    updateAllSliders();
    recalculateCurrentScore();
    
    showToast('Preset "Focus Naso" applicato', 'info');
    console.log('👃 Preset Focus Naso');
}

function presetLessSymmetry() {
    scoringSystem.weights = {
        nose: 0.40,
        mouth: 0.35,
        symmetry: 0.15,
        eye: 0.10
    };
    
    updateAllSliders();
    recalculateCurrentScore();
    
    showToast('Preset "Meno Simmetria" applicato', 'info');
    console.log('⚖️ Preset Meno Simmetria');
}

function updateAllSliders() {
    Object.keys(scoringSystem.weights).forEach(type => {
        const slider = document.getElementById(`${type}-slider`);
        const value = document.getElementById(`${type}-value`);
        
        if (slider && value) {
            slider.value = scoringSystem.weights[type];
            value.textContent = scoringSystem.weights[type].toFixed(2);
            updateSliderColor(type, scoringSystem.weights[type]);
        }
    });
}

// === ALGORITMO SCORING ===

function calculateFacialScore(landmarks, image) {
    if (!landmarks || landmarks.length < 468) {
        return 0.0;
    }
    
    try {
        // Calcola componenti del punteggio
        const noseScore = calculateNoseScore(landmarks);
        const mouthScore = calculateMouthScore(landmarks);
        const symmetryScore = calculateSymmetryScore(landmarks);
        const eyeScore = calculateEyeScore(landmarks);
        
        // Score pesato
        const weightedScore = 
            (noseScore * scoringSystem.weights.nose) +
            (mouthScore * scoringSystem.weights.mouth) +
            (symmetryScore * scoringSystem.weights.symmetry) +
            (eyeScore * scoringSystem.weights.eye);
        
        // Applica bonus/penalty per orientamento
        const orientationBonus = calculateOrientationBonus(landmarks);
        const finalScore = Math.min(1.0, Math.max(0.0, weightedScore * orientationBonus));
        
        console.log('📊 Score components:', {
            nose: noseScore.toFixed(3),
            mouth: mouthScore.toFixed(3),
            symmetry: symmetryScore.toFixed(3),
            eye: eyeScore.toFixed(3),
            weighted: weightedScore.toFixed(3),
            bonus: orientationBonus.toFixed(3),
            final: finalScore.toFixed(3)
        });
        
        return finalScore;
        
    } catch (error) {
        console.error('Errore calcolo score:', error);
        return 0.0;
    }
}

function calculateNoseScore(landmarks) {
    try {
        // Usa landmarks MediaPipe per il naso
        const noseTip = landmarks[1];      // Punta del naso
        const noseLeft = landmarks[31];    // Narice sinistra
        const noseRight = landmarks[35];   // Narice destra
        
        if (!noseTip || !noseLeft || !noseRight) {
            return 0.0;
        }
        
        // Calcola simmetria naso (distanza dalla linea centrale)
        const noseCenter = {
            x: (noseLeft.x + noseRight.x) / 2,
            y: (noseLeft.y + noseRight.y) / 2
        };
        
        const centerDeviation = Math.abs(noseTip.x - noseCenter.x);
        const noseWidth = Math.abs(noseRight.x - noseLeft.x);
        
        if (noseWidth === 0) return 0.0;
        
        const symmetryRatio = centerDeviation / noseWidth;
        const score = Math.max(0.0, 1.0 - (symmetryRatio / scoringSystem.tolerances.nose));
        
        return Math.min(1.0, score);
        
    } catch (error) {
        console.error('Errore calcolo nose score:', error);
        return 0.0;
    }
}

function calculateMouthScore(landmarks) {
    try {
        // Landmarks bocca MediaPipe
        const mouthLeft = landmarks[61];   // Angolo sinistro
        const mouthRight = landmarks[291]; // Angolo destro
        const mouthTop = landmarks[13];    // Centro superiore
        const mouthBottom = landmarks[14]; // Centro inferiore
        
        if (!mouthLeft || !mouthRight || !mouthTop || !mouthBottom) {
            return 0.0;
        }
        
        // Calcola simmetria orizzontale
        const mouthCenter = {
            x: (mouthLeft.x + mouthRight.x) / 2,
            y: (mouthLeft.y + mouthRight.y) / 2
        };
        
        const topDeviation = Math.abs(mouthTop.x - mouthCenter.x);
        const bottomDeviation = Math.abs(mouthBottom.x - mouthCenter.x);
        const mouthWidth = Math.abs(mouthRight.x - mouthLeft.x);
        
        if (mouthWidth === 0) return 0.0;
        
        const avgDeviation = (topDeviation + bottomDeviation) / 2;
        const symmetryRatio = avgDeviation / mouthWidth;
        
        const score = Math.max(0.0, 1.0 - (symmetryRatio / scoringSystem.tolerances.mouth));
        
        return Math.min(1.0, score);
        
    } catch (error) {
        console.error('Errore calcolo mouth score:', error);
        return 0.0;
    }
}

function calculateSymmetryScore(landmarks) {
    try {
        // Punti per calcolo simmetria facciale globale
        const leftEye = landmarks[33];     // Occhio sinistro esterno
        const rightEye = landmarks[362];   // Occhio destro esterno
        const leftCheek = landmarks[234];  // Guancia sinistra
        const rightCheek = landmarks[454]; // Guancia destra
        
        if (!leftEye || !rightEye || !leftCheek || !rightCheek) {
            return 0.0;
        }
        
        // Calcola asse centrale del viso
        const faceCenter = {
            x: (leftEye.x + rightEye.x) / 2,
            y: (leftEye.y + rightEye.y) / 2
        };
        
        // Distanze dall'asse centrale
        const leftEyeDist = Math.abs(leftEye.x - faceCenter.x);
        const rightEyeDist = Math.abs(rightEye.x - faceCenter.x);
        const leftCheekDist = Math.abs(leftCheek.x - faceCenter.x);
        const rightCheekDist = Math.abs(rightCheek.x - faceCenter.x);
        
        // Calcola asimmetria relativa
        const eyeAsymmetry = Math.abs(leftEyeDist - rightEyeDist) / Math.max(leftEyeDist, rightEyeDist, 0.001);
        const cheekAsymmetry = Math.abs(leftCheekDist - rightCheekDist) / Math.max(leftCheekDist, rightCheekDist, 0.001);
        
        const avgAsymmetry = (eyeAsymmetry + cheekAsymmetry) / 2;
        const score = Math.max(0.0, 1.0 - (avgAsymmetry / scoringSystem.tolerances.symmetry));
        
        return Math.min(1.0, score);
        
    } catch (error) {
        console.error('Errore calcolo symmetry score:', error);
        return 0.0;
    }
}

function calculateEyeScore(landmarks) {
    try {
        // Landmarks occhi MediaPipe
        const leftEyeInner = landmarks[133];  // Angolo interno sinistro
        const leftEyeOuter = landmarks[33];   // Angolo esterno sinistro
        const rightEyeInner = landmarks[362]; // Angolo interno destro
        const rightEyeOuter = landmarks[263]; // Angolo esterno destro
        
        if (!leftEyeInner || !leftEyeOuter || !rightEyeInner || !rightEyeOuter) {
            return 0.0;
        }
        
        // Calcola larghezza degli occhi
        const leftEyeWidth = Math.abs(leftEyeOuter.x - leftEyeInner.x);
        const rightEyeWidth = Math.abs(rightEyeOuter.x - rightEyeInner.x);
        
        if (leftEyeWidth === 0 || rightEyeWidth === 0) return 0.0;
        
        // Simmetria larghezza occhi
        const widthRatio = Math.min(leftEyeWidth, rightEyeWidth) / Math.max(leftEyeWidth, rightEyeWidth);
        
        // Allineamento orizzontale
        const leftEyeY = (leftEyeInner.y + leftEyeOuter.y) / 2;
        const rightEyeY = (rightEyeInner.y + rightEyeOuter.y) / 2;
        const alignmentDiff = Math.abs(leftEyeY - rightEyeY);
        
        // Calcola distanza inter-pupillare normalizzata
        const eyeDistance = Math.abs(rightEyeInner.x - leftEyeInner.x);
        const alignmentRatio = eyeDistance > 0 ? alignmentDiff / eyeDistance : 0;
        
        // Score combinato
        const alignmentScore = Math.max(0.0, 1.0 - (alignmentRatio * 5)); // Fattore 5 per sensibilità
        const score = (widthRatio + alignmentScore) / 2;
        
        return Math.min(1.0, score);
        
    } catch (error) {
        console.error('Errore calcolo eye score:', error);
        return 0.0;
    }
}

function calculateOrientationBonus(landmarks) {
    try {
        // Calcola orientamento 3D del viso
        const leftEye = landmarks[33];
        const rightEye = landmarks[362];
        const noseTip = landmarks[1];
        const chin = landmarks[175];
        
        if (!leftEye || !rightEye || !noseTip || !chin) {
            return 1.0; // Nessun bonus/penalty se non possiamo calcolare
        }
        
        // Calcola roll (rotazione laterale)
        const eyeVector = {
            x: rightEye.x - leftEye.x,
            y: rightEye.y - leftEye.y
        };
        const rollAngle = Math.abs(Math.atan2(eyeVector.y, eyeVector.x) * 180 / Math.PI);
        
        // Calcola pitch (inclinazione su/giù) approssimativo
        const faceHeight = Math.abs(chin.y - ((leftEye.y + rightEye.y) / 2));
        const nosePosition = (noseTip.y - ((leftEye.y + rightEye.y) / 2)) / faceHeight;
        
        // Bonus basato su frontalità
        let bonus = 1.0;
        
        // Penalty per roll eccessivo
        if (rollAngle > 15) {
            bonus *= 0.9;
        } else if (rollAngle > 8) {
            bonus *= scoringSystem.bonuses.roll_med;
        } else if (rollAngle < 3) {
            bonus *= scoringSystem.bonuses.roll_high;
        }
        
        // Penalty per pitch eccessivo
        if (Math.abs(nosePosition) > 0.3) {
            bonus *= 0.85;
        }
        
        return bonus;
        
    } catch (error) {
        console.error('Errore calcolo orientation bonus:', error);
        return 1.0;
    }
}

// === EXPORT CONFIGURAZIONE ===

function exportScoringConfig() {
    const config = {
        weights: { ...scoringSystem.weights },
        tolerances: { ...scoringSystem.tolerances },
        timestamp: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'scoring_config.json';
    a.click();
    
    URL.revokeObjectURL(url);
    showToast('Configurazione scoring esportata', 'success');
}

function importScoringConfig(file) {
    const reader = new FileReader();
    
    reader.onload = function(e) {
        try {
            const config = JSON.parse(e.target.result);
            
            if (config.weights) {
                scoringSystem.weights = { ...config.weights };
                updateAllSliders();
                recalculateCurrentScore();
                showToast('Configurazione scoring importata', 'success');
            } else {
                showToast('File configurazione non valido', 'error');
            }
        } catch (error) {
            console.error('Errore import config:', error);
            showToast('Errore lettura file configurazione', 'error');
        }
    };
    
    reader.readAsText(file);
}