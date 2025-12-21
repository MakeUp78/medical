/**
 * =============================================================================
 * EYEBROW PREPROCESSING VISUALIZATION - WEBAPP VERSION v1.0
 * =============================================================================
 * Data: 2025-12-21
 * 
 * Gestisce la visualizzazione del preprocessing delle regioni sopraccigliare:
 * - Overlay delle immagini di debug sul canvas
 * - Visualizzazione bounding boxes
 * - Display metadati nella tabella Data Analysis
 * - Gestione layer separati per i vari step di preprocessing
 */

console.log('🔬 EYEBROW PREPROCESSING MODULE v1.0 LOADED');

// ==================== STATO GLOBALE ====================

window.eyebrowPreprocessingState = {
    active: false,
    currentSide: null,
    debugImages: {},
    metadata: {},
    overlayLayers: {
        bbox: null,
        mask: null,
        masked_region: null,
        color_corrected: null
    }
};

// ==================== API CALL ====================

/**
 * Chiama l'endpoint di preprocessing e ritorna i risultati
 */
async function callPreprocessingAPI(imageBase64, side, expandFactor = 0.5, applyColorCorrection = true) {
    try {
        console.log(`📡 Chiamata API preprocessing per sopracciglio ${side}...`);
        
        const response = await fetch('/api/eyebrow/preprocess', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                image: imageBase64,
                side: side,
                expand_factor: expandFactor,
                apply_color_correction: applyColorCorrection
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✅ Risposta API ricevuta:', data);
        
        return data;
        
    } catch (error) {
        console.error('❌ Errore chiamata API preprocessing:', error);
        throw error;
    }
}

// ==================== CANVAS OVERLAY ====================

/**
 * Aggiunge un'immagine di debug come overlay sul canvas
 */
function addDebugImageOverlay(imageDataUrl, layerName, opacity = 0.7) {
    if (!window.fabricCanvas) {
        console.error('❌ Canvas Fabric non disponibile');
        return null;
    }
    
    return new Promise((resolve, reject) => {
        fabric.Image.fromURL(imageDataUrl, function(img) {
            if (!img) {
                console.error(`❌ Impossibile caricare immagine per layer ${layerName}`);
                reject(new Error(`Impossibile caricare immagine per layer ${layerName}`));
                return;
            }
            
            // Scala per adattare al canvas
            const canvasWidth = window.fabricCanvas.width;
            const canvasHeight = window.fabricCanvas.height;
            
            const scaleX = canvasWidth / img.width;
            const scaleY = canvasHeight / img.height;
            const scale = Math.min(scaleX, scaleY);
            
            img.set({
                left: 0,
                top: 0,
                scaleX: scale,
                scaleY: scale,
                opacity: opacity,
                selectable: false,
                evented: false,
                name: `preprocessing_${layerName}`
            });
            
            window.fabricCanvas.add(img);
            window.fabricCanvas.renderAll();
            
            console.log(`✅ Layer ${layerName} aggiunto al canvas`);
            resolve(img);
        }, {
            crossOrigin: 'anonymous'
        }, function(error) {
            // Error callback
            console.error(`❌ Errore caricamento immagine ${layerName}:`, error);
            reject(error);
        });
    });
}

/**
 * Rimuove tutti i layer di preprocessing dal canvas
 */
function clearPreprocessingLayers() {
    if (!window.fabricCanvas) return;
    
    const objects = window.fabricCanvas.getObjects();
    const layersToRemove = objects.filter(obj => 
        obj.name && obj.name.startsWith('preprocessing_')
    );
    
    layersToRemove.forEach(obj => {
        window.fabricCanvas.remove(obj);
    });
    
    window.fabricCanvas.renderAll();
    console.log(`🗑️ Rimossi ${layersToRemove.length} layer di preprocessing`);
}

/**
 * Disegna bounding box sul canvas
 */
function drawBoundingBox(bbox, color = 'rgba(0, 255, 0, 0.8)', lineWidth = 3) {
    if (!window.fabricCanvas || !bbox) return null;
    
    const rect = new fabric.Rect({
        left: bbox.x_min,
        top: bbox.y_min,
        width: bbox.width,
        height: bbox.height,
        fill: 'transparent',
        stroke: color,
        strokeWidth: lineWidth,
        selectable: false,
        evented: false,
        name: 'preprocessing_bbox'
    });
    
    window.fabricCanvas.add(rect);
    window.fabricCanvas.renderAll();
    
    console.log('✅ Bounding box disegnato:', bbox);
    return rect;
}

/**
 * Disegna landmarks sul canvas
 */
function drawLandmarks(landmarks, color = 'rgba(255, 0, 0, 1)', radius = 3) {
    if (!window.fabricCanvas || !landmarks) return [];
    
    const circles = [];
    
    landmarks.forEach((lm, i) => {
        const circle = new fabric.Circle({
            left: lm.x - radius,
            top: lm.y - radius,
            radius: radius,
            fill: color,
            selectable: false,
            evented: false,
            name: `preprocessing_landmark_${i}`
        });
        
        window.fabricCanvas.add(circle);
        circles.push(circle);
    });
    
    window.fabricCanvas.renderAll();
    console.log(`✅ Disegnati ${landmarks.length} landmarks`);
    
    return circles;
}

// ==================== DATA TABLE UPDATES ====================

/**
 * Aggiunge i metadati di preprocessing alla tabella Data Analysis
 */
function addPreprocessingMetadataToTable(metadata, side) {
    const table = document.getElementById('measurements-table');
    if (!table) {
        console.warn('⚠️ Tabella measurements non trovata');
        return;
    }
    
    const tbody = table.querySelector('tbody');
    if (!tbody) {
        console.warn('⚠️ Tbody non trovato nella tabella');
        return;
    }
    
    // Crea sezione header per preprocessing
    const headerRow = document.createElement('tr');
    headerRow.className = 'preprocessing-header';
    headerRow.innerHTML = `
        <td colspan="4" style="background: #e3f2fd; font-weight: bold; text-align: center;">
            🔬 PREPROCESSING SOPRACCIGLIO ${side.toUpperCase()}
        </td>
    `;
    tbody.appendChild(headerRow);
    
    // Aggiungi righe per ogni metadato
    const metadataRows = [
        {label: 'Landmarks Rilevati', value: metadata.landmarks_count, unit: 'punti'},
        {label: 'Bounding Box Area', value: metadata.bbox_area, unit: 'px²'},
        {label: 'Mask Area', value: metadata.mask_area, unit: 'px²'},
        {label: 'Expand Factor', value: (metadata.expand_factor * 100).toFixed(0), unit: '%'},
        {label: 'Color Correction', value: metadata.color_correction_applied ? 'Applicata' : 'Non applicata', unit: ''}
    ];
    
    metadataRows.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'preprocessing-data-row';
        row.innerHTML = `
            <td>📊 ${item.label}</td>
            <td>${item.value}</td>
            <td>${item.unit}</td>
            <td>✅ OK</td>
        `;
        tbody.appendChild(row);
    });
    
    console.log('✅ Metadati aggiunti alla tabella');
}

/**
 * Rimuove i metadati di preprocessing dalla tabella
 */
function removePreprocessingMetadataFromTable() {
    const table = document.getElementById('measurements-table');
    if (!table) return;
    
    const tbody = table.querySelector('tbody');
    if (!tbody) return;
    
    // Rimuovi tutte le righe di preprocessing
    const rows = tbody.querySelectorAll('.preprocessing-header, .preprocessing-data-row');
    rows.forEach(row => row.remove());
    
    console.log('🗑️ Metadati rimossi dalla tabella');
}

// ==================== WORKFLOW PRINCIPALE ====================

/**
 * Esegue il preprocessing completo e visualizza i risultati
 */
async function preprocessAndVisualize(side) {
    try {
        console.log(`\n🚀 === AVVIO PREPROCESSING SOPRACCIGLIO ${side.toUpperCase()} ===`);
        
        // 1. Verifica prerequisiti
        if (!window.currentImage) {
            alert('Carica prima un\'immagine!');
            return;
        }
        
        // 2. Ottieni immagine base64 dal canvas
        let imageBase64;
        if (window.fabricCanvas) {
            imageBase64 = window.fabricCanvas.toDataURL({format: 'png'});
        } else {
            const canvas = document.getElementById('main-canvas');
            if (!canvas) {
                alert('Canvas non trovato!');
                return;
            }
            imageBase64 = canvas.toDataURL('image/png');
        }
        
        // 3. Chiama API di preprocessing
        console.log('📡 Step 1: Chiamata API...');
        const result = await callPreprocessingAPI(imageBase64, side, 0.5, true);
        
        if (!result.success) {
            alert(`Errore preprocessing: ${result.error}`);
            return;
        }
        
        console.log('✅ Step 1: Risposta API ricevuta');
        
        // 4. Salva stato
        window.eyebrowPreprocessingState.active = true;
        window.eyebrowPreprocessingState.currentSide = side;
        window.eyebrowPreprocessingState.debugImages = result.debug_images;
        window.eyebrowPreprocessingState.metadata = result.preprocessing_metadata;
        
        // 5. Pulisci layer esistenti
        console.log('🗑️ Step 2: Pulizia layer esistenti...');
        clearPreprocessingLayers();
        removePreprocessingMetadataFromTable();
        
        // 6. Visualizza debug images
        console.log('🎨 Step 3: Visualizzazione debug images...');
        
        // Mostra una finestra con tutte le debug images
        showDebugImagesWindow(result.debug_images, side, result.bbox, result.landmarks);
        
        // 7. Aggiungi metadati alla tabella
        console.log('📊 Step 4: Aggiunta metadati alla tabella...');
        addPreprocessingMetadataToTable(result.preprocessing_metadata, side);
        
        // 8. Disegna bounding box e landmarks sul canvas principale (opzionale)
        if (result.bbox) {
            drawBoundingBox(result.bbox);
        }
        
        if (result.landmarks) {
            drawLandmarks(result.landmarks);
        }
        
        console.log('✅ === PREPROCESSING COMPLETATO ===\n');
        
    } catch (error) {
        console.error('❌ Errore nel preprocessing:', error);
        alert(`Errore preprocessing: ${error.message}`);
    }
}

// ==================== DEBUG IMAGES WINDOW ====================

/**
 * Mostra finestra modale con tutte le debug images
 */
function showDebugImagesWindow(debugImages, side, bbox, landmarks) {
    const sideName = side === 'left' ? 'Sinistro' : 'Destro';
    
    // Crea modal
    const modal = document.createElement('div');
    modal.id = 'preprocessing-debug-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.95);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        overflow: auto;
    `;
    
    const content = document.createElement('div');
    content.style.cssText = `
        background: white;
        padding: 30px;
        border-radius: 12px;
        max-width: 95vw;
        max-height: 95vh;
        overflow: auto;
    `;
    
    // Titolo
    content.innerHTML = `
        <h2 style="margin: 0 0 20px 0; text-align: center; color: #333;">
            🔬 Debug Preprocessing - Sopracciglio ${sideName}
        </h2>
    `;
    
    // Griglia debug images
    const grid = document.createElement('div');
    grid.style.cssText = `
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
        gap: 20px;
        margin-bottom: 20px;
    `;
    
    const imageLabels = {
        'bbox_overlay': '📐 Bounding Box + Landmarks',
        'mask': '🎭 Maschera Regione',
        'masked_region': '✂️ Regione Estratta',
        'color_corrected': '🎨 Correzione Colore'
    };
    
    Object.entries(debugImages).forEach(([key, imageDataUrl]) => {
        const imageCard = document.createElement('div');
        imageCard.style.cssText = `
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 10px;
            background: #f9f9f9;
        `;
        
        imageCard.innerHTML = `
            <h4 style="margin: 0 0 10px 0; color: #555;">${imageLabels[key] || key}</h4>
            <img src="${imageDataUrl}" style="width: 100%; height: auto; border-radius: 4px; cursor: zoom-in;" 
                 onclick="window.open(this.src, '_blank')">
        `;
        
        grid.appendChild(imageCard);
    });
    
    content.appendChild(grid);
    
    // Info bbox e landmarks
    if (bbox || landmarks) {
        const infoDiv = document.createElement('div');
        infoDiv.style.cssText = `
            background: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        `;
        
        let infoHTML = '<h4 style="margin: 0 0 10px 0;">📊 Metadata Preprocessing:</h4>';
        
        if (bbox) {
            infoHTML += `
                <p style="margin: 5px 0;"><strong>Bounding Box:</strong> 
                   (${bbox.x_min}, ${bbox.y_min}) → (${bbox.x_max}, ${bbox.y_max}), 
                   Size: ${bbox.width}x${bbox.height}px
                </p>
            `;
        }
        
        if (landmarks) {
            infoHTML += `
                <p style="margin: 5px 0;"><strong>Landmarks:</strong> ${landmarks.length} punti rilevati</p>
            `;
        }
        
        infoDiv.innerHTML = infoHTML;
        content.appendChild(infoDiv);
    }
    
    // Pulsanti
    const buttonsDiv = document.createElement('div');
    buttonsDiv.style.cssText = 'text-align: center; display: flex; gap: 10px; justify-content: center;';
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '❌ Chiudi';
    closeBtn.className = 'btn btn-secondary';
    closeBtn.style.cssText = 'padding: 10px 20px; font-size: 16px;';
    closeBtn.onclick = () => document.body.removeChild(modal);
    
    const clearBtn = document.createElement('button');
    clearBtn.textContent = '🗑️ Pulisci Overlay';
    clearBtn.className = 'btn btn-warning';
    clearBtn.style.cssText = 'padding: 10px 20px; font-size: 16px;';
    clearBtn.onclick = () => {
        clearPreprocessingLayers();
        removePreprocessingMetadataFromTable();
        alert('Overlay e metadati rimossi');
    };
    
    buttonsDiv.appendChild(clearBtn);
    buttonsDiv.appendChild(closeBtn);
    content.appendChild(buttonsDiv);
    
    modal.appendChild(content);
    document.body.appendChild(modal);
    
    console.log('✅ Finestra debug aperta');
}

// ==================== PULSANTI UI ====================

/**
 * Handler per pulsante preprocessing sopracciglio sinistro
 */
async function preprocessLeftEyebrow() {
    await preprocessAndVisualize('left');
}

/**
 * Handler per pulsante preprocessing sopracciglio destro
 */
async function preprocessRightEyebrow() {
    await preprocessAndVisualize('right');
}

/**
 * Pulisce tutti i layer e metadati di preprocessing
 */
function clearAllPreprocessing() {
    clearPreprocessingLayers();
    removePreprocessingMetadataFromTable();
    
    window.eyebrowPreprocessingState.active = false;
    window.eyebrowPreprocessingState.currentSide = null;
    window.eyebrowPreprocessingState.debugImages = {};
    window.eyebrowPreprocessingState.metadata = {};
    
    console.log('✅ Preprocessing completamente pulito');
}

// ==================== ESPORTAZIONI GLOBALI ====================

window.preprocessLeftEyebrow = preprocessLeftEyebrow;
window.preprocessRightEyebrow = preprocessRightEyebrow;
window.clearAllPreprocessing = clearAllPreprocessing;
window.callPreprocessingAPI = callPreprocessingAPI;
window.addDebugImageOverlay = addDebugImageOverlay;

console.log('✅ Eyebrow Preprocessing Module caricato correttamente');
