/**
 * Canvas Modes - Sistema di modalità esclusiva per canvas
 * Gestisce PAN, ZOOM IN, ZOOM OUT, SELEZIONE con cursori e comportamenti specifici
 */

// === VARIABILI GLOBALI MODALITÀ ===
let currentCanvasMode = null; // null | 'pan' | 'zoom-in' | 'zoom-out' | 'selection' | 'line' | 'rectangle' | 'circle'
let isPanning = false;
let panStart = { x: 0, y: 0 };
let measureModeActive = false;
let canvasModeIsDrawing = false; // Prefisso per evitare conflitti con main.js
let canvasModeDrawStart = { x: 0, y: 0 };

// === CURSORI PERSONALIZZATI ===
const CURSORS = {
    'default': 'default',
    'pan': 'move',
    'panning': 'grabbing',
    'zoom-in': 'zoom-in',
    'zoom-out': 'zoom-out',
    'selection': 'crosshair',
    'line': 'cell', // Cursore a croce per linee perpendicolari
    'rectangle': 'crosshair',
    'circle': 'crosshair'
};

/**
 * Imposta la modalità corrente del canvas con supporto TOGGLE
 */
function setCanvasMode(mode) {
    console.log(`🔧 Cambio modalità canvas: ${currentCanvasMode} → ${mode}`);

    // TOGGLE: se clicco sullo stesso pulsante, disattiva
    if (currentCanvasMode === mode) {
        console.log(`🔄 Toggle OFF modalità: ${mode}`);
        currentCanvasMode = null;

        // Quando disattivi una modalità, torna al cursore predefinito (non pan)
        if (fabricCanvas) {
            fabricCanvas.defaultCursor = 'default';
            fabricCanvas.renderAll();
        }

        updateCanvasCursor('default');
        updateToolbarButtons(null); // Rimuove active da tutti i pulsanti
        isPanning = false;
        return;
    }

    // Reset stato precedente
    isPanning = false;

    // Aggiorna modalità
    currentCanvasMode = mode;

    // Aggiorna cursore
    updateCanvasCursor(mode);

    // Aggiorna UI toolbar
    updateToolbarButtons(mode);

    // Abilita/disabilita selezione Fabric.js in base al mode
    if (fabricCanvas) {
        // Disabilita selezione multipla (drag area), ma permetti selezione singoli oggetti
        fabricCanvas.selection = false;

        // Permetti sempre la selezione di oggetti singoli trascinabili
        const objects = fabricCanvas.getObjects();
        objects.forEach(obj => {
            // Le linee perpendicolari sono sempre selezionabili
            if (obj.isPerpendicularLine) {
                obj.selectable = true;
                obj.evented = true;
            }
        });
    }

    console.log(`✅ Modalità canvas impostata: ${mode}`);
}

/**
 * Aggiorna il cursore del canvas
 */
function updateCanvasCursor(mode) {
    if (!fabricCanvas) return;

    const cursor = CURSORS[mode] || CURSORS['default'];

    // Imposta cursore predefinito del canvas (quando non sei sopra un oggetto)
    fabricCanvas.defaultCursor = cursor;

    // NON impostare hoverCursor globale - lascia che ogni oggetto gestisca il proprio
    // fabricCanvas.hoverCursor viene gestito automaticamente dagli oggetti

    // Imposta cursore su tutti gli oggetti, TRANNE le linee perpendicolari
    const objects = fabricCanvas.getObjects();
    objects.forEach(obj => {
        // Le linee perpendicolari mantengono sempre il cursore 'move'
        if (!obj.isPerpendicularLine) {
            obj.hoverCursor = cursor;
            obj.moveCursor = cursor;
        }
    });

    // IMPORTANTE: Imposta cursore anche sull'elemento canvas DOM direttamente
    const canvasElement = document.getElementById('main-canvas');
    if (canvasElement) {
        canvasElement.style.cursor = cursor;
    }

    // Imposta cursore anche sul wrapper del canvas
    const canvasWrapper = canvasElement?.parentElement;
    if (canvasWrapper) {
        canvasWrapper.style.cursor = cursor;
    }

    fabricCanvas.renderAll();

    console.log(`🖱️ Cursore canvas impostato: ${cursor}`);
}

/**
 * Aggiorna stato visivo pulsanti toolbar
 */
function updateToolbarButtons(activeMode) {
    // Rimuovi classe active da tutti i pulsanti tool
    document.querySelectorAll('.tool-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Aggiungi active al pulsante corrispondente
    if (activeMode) {
        const activeBtn = document.querySelector(`.tool-btn[data-tool="${activeMode}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
    }
}

/**
 * Gestisce eventi mouse per le diverse modalità
 */
function setupCanvasModesHandlers() {
    if (!fabricCanvas) {
        console.error('❌ fabricCanvas non inizializzato');
        return;
    }

    console.log('🎯 Configurazione handlers modalità canvas...');

    // === MOUSE DOWN ===
    fabricCanvas.on('mouse:down', function(opt) {
        const evt = opt.e;
        const pointer = fabricCanvas.getPointer(evt);
        const target = opt.target;

        console.log(`🖱️ Mouse down - Mode: ${currentCanvasMode}`, pointer);

        // PRIORITÀ 1: Se è un landmark e la modalità MISURAZIONE è attiva
        // (ha priorità sulla selezione normale)
        if (target && target.isLandmark && window.measurementMode) {
            console.log(`📏 Click su landmark ${target.landmarkIndex} per MISURAZIONE`);
            if (typeof window.handleMeasurementLandmarkSelection === 'function') {
                // Passa indice e coordinate del centro del landmark
                const landmarkX = target.left + target.radius;
                const landmarkY = target.top + target.radius;
                window.handleMeasurementLandmarkSelection(landmarkX, landmarkY, target.landmarkIndex);
            }
            return; // Non processare ulteriori eventi
        }

        // PRIORITÀ 2: Se è un landmark e la modalità SELEZIONE è attiva (solo se MISURA non è attivo)
        if (target && target.isLandmark && window.landmarkSelectionMode && !window.measurementMode) {
            console.log(`🎯 Click su landmark ${target.landmarkIndex} per SELEZIONE`);
            if (typeof window.handleLandmarkSelection === 'function') {
                // Passa le coordinate del centro del landmark
                const landmarkX = target.left + target.radius;
                const landmarkY = target.top + target.radius;
                window.handleLandmarkSelection(landmarkX, landmarkY);
            }
            return; // Non processare ulteriori eventi
        }

        switch(currentCanvasMode) {
            case 'pan':
                handlePanStart(opt, pointer);
                break;

            case 'zoom-in':
                handleZoomInClick(pointer);
                break;

            case 'zoom-out':
                handleZoomOutClick(pointer);
                break;

            case 'selection':
                // Solo se measure mode è attivo
                if (measureModeActive) {
                    handleLandmarkSelectionClick(pointer);
                }
                break;

            case 'line':
                // Se clicchiamo su una linea perpendicolare esistente, NON creare una nuova linea
                // Lascia che Fabric.js gestisca il drag
                if (target && target.isPerpendicularLine) {
                    console.log('🎯 Click su linea perpendicolare esistente - drag mode');
                    fabricCanvas.setActiveObject(target);
                    return; // Lascia gestire a Fabric.js
                }
                // Altrimenti crea una nuova linea
                handleDrawStart(opt, pointer);
                break;

            case 'rectangle':
            case 'circle':
                handleDrawStart(opt, pointer);
                break;
        }
    });

    // === MOUSE MOVE ===
    fabricCanvas.on('mouse:move', function(opt) {
        if (currentCanvasMode === 'pan' && isPanning) {
            handlePanMove(opt);
        } else if ((currentCanvasMode === 'line' || currentCanvasMode === 'rectangle' || currentCanvasMode === 'circle') && canvasModeIsDrawing) {
            handleDrawMove(opt);
        }
    });

    // === MOUSE UP ===
    fabricCanvas.on('mouse:up', function(opt) {
        if (currentCanvasMode === 'pan' && isPanning) {
            handlePanEnd(opt);
        } else if ((currentCanvasMode === 'line' || currentCanvasMode === 'rectangle' || currentCanvasMode === 'circle') && canvasModeIsDrawing) {
            handleDrawEnd(opt);
        }
    });

    console.log('✅ Handlers modalità canvas configurati');
}

// === GESTIONE PAN ===

function handlePanStart(opt, pointer) {
    isPanning = true;
    panStart = { x: pointer.x, y: pointer.y };

    // Cambia cursore in "grabbing"
    fabricCanvas.defaultCursor = CURSORS['panning'];
    fabricCanvas.renderAll();

    console.log('👆 Pan iniziato', panStart);
}

function handlePanMove(opt) {
    if (!isPanning) return;

    const evt = opt.e;
    const pointer = fabricCanvas.getPointer(evt);

    // Calcola delta
    const deltaX = pointer.x - panStart.x;
    const deltaY = pointer.y - panStart.y;

    // Applica pan a tutti gli oggetti
    const objects = fabricCanvas.getObjects();
    objects.forEach(obj => {
        obj.left += deltaX;
        obj.top += deltaY;
        obj.setCoords();
    });

    // Aggiorna punto di partenza
    panStart = { x: pointer.x, y: pointer.y };

    fabricCanvas.renderAll();
}

function handlePanEnd(opt) {
    isPanning = false;

    // Ripristina cursore move
    fabricCanvas.defaultCursor = CURSORS['pan'];
    fabricCanvas.renderAll();

    console.log('👆 Pan terminato');
}

// === GESTIONE ZOOM IN ===

function handleZoomInClick(pointer) {
    console.log('🔍+ Zoom IN al punto', pointer);

    // Ottieni zoom corrente
    let zoom = fabricCanvas.getZoom();

    // Aumenta zoom del 20%
    let newZoom = zoom * 1.2;

    // Limita zoom massimo
    if (newZoom > 20) newZoom = 20;

    // Applica zoom centrato sul punto cliccato
    fabricCanvas.zoomToPoint(new fabric.Point(pointer.x, pointer.y), newZoom);

    // Aggiorna display zoom
    if (typeof updateZoomDisplay === 'function') {
        updateZoomDisplay(newZoom);
    }

    console.log(`✅ Zoom: ${zoom.toFixed(2)} → ${newZoom.toFixed(2)}`);
}

// === GESTIONE ZOOM OUT ===

function handleZoomOutClick(pointer) {
    console.log('🔍- Zoom OUT al punto', pointer);

    // Ottieni zoom corrente
    let zoom = fabricCanvas.getZoom();

    // Diminuisci zoom del 20%
    let newZoom = zoom * 0.8;

    // Limita zoom minimo
    if (newZoom < 0.1) newZoom = 0.1;

    // Applica zoom centrato sul punto cliccato
    fabricCanvas.zoomToPoint(new fabric.Point(pointer.x, pointer.y), newZoom);

    // Aggiorna display zoom
    if (typeof updateZoomDisplay === 'function') {
        updateZoomDisplay(newZoom);
    }

    console.log(`✅ Zoom: ${zoom.toFixed(2)} → ${newZoom.toFixed(2)}`);
}

// === GESTIONE SELEZIONE LANDMARKS ===

function handleLandmarkSelectionClick(pointer) {
    console.log('🎯 Selezione landmark al punto', pointer);

    // Delega a funzione esistente se disponibile
    if (typeof window.handleLandmarkSelection === 'function') {
        window.handleLandmarkSelection(pointer.x, pointer.y);
    } else if (typeof window.handleMeasurementLandmarkSelection === 'function') {
        window.handleMeasurementLandmarkSelection(pointer.x, pointer.y);
    } else {
        console.warn('⚠️ Nessun handler per selezione landmark disponibile');
    }
}

// === GESTIONE DISEGNO (LINE, RECTANGLE, CIRCLE) ===

let currentDrawingObject = null;

function handleDrawStart(opt, pointer) {
    canvasModeIsDrawing = true;
    canvasModeDrawStart = { x: pointer.x, y: pointer.y };

    console.log(`✏️ Inizio disegno ${currentCanvasMode} da`, canvasModeDrawStart);

    // Crea oggetto temporaneo in base al tool
    switch(currentCanvasMode) {
        case 'line':
            // LINEA PERPENDICOLARE ALL'ASSE DI SIMMETRIA
            // Verifica che l'asse di simmetria sia presente
            if (!window.currentLandmarks || !window.currentLandmarks[9] || !window.currentLandmarks[164]) {
                showToast('Attiva prima l\'asse di simmetria', 'warning');
                canvasModeIsDrawing = false;
                return;
            }

            // Calcola la posizione normalizzata lungo l'asse (0-1)
            const glabella = window.currentLandmarks[9];
            const philtrum = window.currentLandmarks[164];
            const transGlab = transformLandmarkCoordinate(glabella);
            const transPhil = transformLandmarkCoordinate(philtrum);

            // Proiezione del punto di click sull'asse
            const axisVecX = transPhil.x - transGlab.x;
            const axisVecY = transPhil.y - transGlab.y;
            const axisLength = Math.sqrt(axisVecX * axisVecX + axisVecY * axisVecY);

            const clickVecX = pointer.x - transGlab.x;
            const clickVecY = pointer.y - transGlab.y;

            // Prodotto scalare per trovare la proiezione
            const projection = (clickVecX * axisVecX + clickVecY * axisVecY) / (axisLength * axisLength);
            // NON clampare - permetti linee ovunque lungo l'asse
            const normalizedPos = projection;

            console.log(`📍 Click: (${pointer.x.toFixed(1)}, ${pointer.y.toFixed(1)})`);
            console.log(`📍 Glabella: (${transGlab.x.toFixed(1)}, ${transGlab.y.toFixed(1)})`);
            console.log(`📍 Philtrum: (${transPhil.x.toFixed(1)}, ${transPhil.y.toFixed(1)})`);
            console.log(`📍 Proiezione: ${projection.toFixed(3)} (usato senza clamp)`);

            // Aggiungi la linea perpendicolare
            if (typeof window.addPerpendicularLine === 'function') {
                window.addPerpendicularLine(normalizedPos);
            }

            canvasModeIsDrawing = false;
            console.log(`➕ Linea perpendicolare creata alla posizione normalizzata ${normalizedPos.toFixed(3)}`);
            return;

        case 'rectangle':
            currentDrawingObject = new fabric.Rect({
                left: canvasModeDrawStart.x,
                top: canvasModeDrawStart.y,
                width: 0,
                height: 0,
                fill: 'transparent',
                stroke: '#ff0000',
                strokeWidth: 2,
                selectable: false,
                evented: false
            });
            break;

        case 'circle':
            currentDrawingObject = new fabric.Circle({
                left: canvasModeDrawStart.x,
                top: canvasModeDrawStart.y,
                radius: 0,
                fill: 'transparent',
                stroke: '#ff0000',
                strokeWidth: 2,
                selectable: false,
                evented: false,
                originX: 'center',
                originY: 'center'
            });
            break;
    }

    if (currentDrawingObject) {
        fabricCanvas.add(currentDrawingObject);
    }
}

function handleDrawMove(opt) {
    if (!canvasModeIsDrawing || !currentDrawingObject) return;

    const pointer = fabricCanvas.getPointer(opt.e);

    // Aggiorna oggetto in base al tool
    switch(currentCanvasMode) {
        case 'line':
            // Linea orizzontale gestita direttamente, non serve mouse move
            return;

        case 'rectangle':
            const width = pointer.x - canvasModeDrawStart.x;
            const height = pointer.y - canvasModeDrawStart.y;

            currentDrawingObject.set({
                width: Math.abs(width),
                height: Math.abs(height),
                left: width > 0 ? canvasModeDrawStart.x : pointer.x,
                top: height > 0 ? canvasModeDrawStart.y : pointer.y
            });
            break;

        case 'circle':
            const radius = Math.sqrt(
                Math.pow(pointer.x - canvasModeDrawStart.x, 2) +
                Math.pow(pointer.y - canvasModeDrawStart.y, 2)
            );
            currentDrawingObject.set({ radius: radius });
            break;
    }

    fabricCanvas.renderAll();
}

function handleDrawEnd(opt) {
    canvasModeIsDrawing = false;
    currentDrawingObject = null;

    console.log(`✏️ Fine disegno ${currentCanvasMode}`);
}

// === TOGGLE MEASURE MODE ===

/**
 * Attiva/disattiva modalità misura
 * Quando attiva, abilita il pulsante Selezione
 */
function toggleMeasureMode() {
    measureModeActive = !measureModeActive;

    const measureBtn = document.querySelector('[data-tool="measure"]');
    const selectionBtn = document.querySelector('[data-tool="selection"]');

    if (measureModeActive) {
        // Attiva misura
        measureBtn.classList.add('active');
        selectionBtn.disabled = false; // Abilita selezione

        // Imposta modalità selezione automaticamente
        setCanvasMode('selection');

        // Attiva landmarks se non già visibili
        if (typeof window.toggleLandmarks === 'function' && !window.landmarkSelectionMode) {
            window.toggleLandmarks();
        }

        console.log('📐 Modalità MISURA attivata → Selezione abilitata');
    } else {
        // Disattiva misura
        measureBtn.classList.remove('active');
        selectionBtn.disabled = true; // Disabilita selezione

        // Torna a modalità null
        setCanvasMode(null);
        updateCanvasCursor('default');

        console.log('📐 Modalità MISURA disattivata → Selezione disabilitata');
    }

    // Aggiorna variabile globale per compatibilità con codice esistente
    window.measurementMode = measureModeActive;
}

// === INIZIALIZZAZIONE ===

/**
 * Inizializza il sistema di modalità
 * Chiamare dopo initializeFabricCanvas()
 */
function initializeCanvasModes() {
    console.log('🎯 Inizializzazione sistema modalità canvas...');

    // Setup handlers
    setupCanvasModesHandlers();

    // Disabilita trasformazioni immagine di default
    if (window.currentImage) {
        window.currentImage.set({
            selectable: false,
            evented: false,
            lockMovementX: true,
            lockMovementY: true,
            lockScalingX: true,
            lockScalingY: true,
            lockRotation: true,
            hasControls: false,
            hasBorders: false
        });
        fabricCanvas.renderAll();
    }

    // Modalità iniziale: null (nessuna modalità attiva)
    setCanvasMode(null);

    // Disabilita pulsante selezione inizialmente
    const selectionBtn = document.querySelector('[data-tool="selection"]');
    if (selectionBtn) {
        selectionBtn.disabled = true;
    }

    console.log('✅ Sistema modalità canvas inizializzato');
}

// === ESPORTA FUNZIONI GLOBALI ===

window.setCanvasMode = setCanvasMode;
window.toggleMeasureMode = toggleMeasureMode;
window.initializeCanvasModes = initializeCanvasModes;
window.currentCanvasMode = currentCanvasMode;

console.log('✅ canvas-modes.js caricato');
