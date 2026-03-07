/**
 * Canvas Modes - Sistema di modalità esclusiva per canvas
 * Gestisce PAN, ZOOM IN, ZOOM OUT, SELEZIONE con cursori e comportamenti specifici
 */

// === VARIABILI GLOBALI MODALITÀ ===
let currentCanvasMode = null; // null | 'pan' | 'zoom-in' | 'zoom-out' | 'selection' | 'line' | 'couple' | 'rectangle' | 'circle' | 'eyedropper'
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
    'couple': 'cell', // Cursore a croce per coppie di linee verticali speculari
    'rectangle': 'crosshair',
    'circle': 'crosshair',
    'eyedropper': 'crosshair' // Cursore per contagocce
};

/**
 * Imposta la modalità corrente del canvas con supporto TOGGLE
 */
function setCanvasMode(mode) {
    if (window.DEBUG_MODE) {
        console.log(`🔧 Cambio modalità canvas: ${currentCanvasMode} → ${mode}`);
    }

    // TOGGLE: se clicco sullo stesso pulsante, disattiva
    if (currentCanvasMode === mode) {
        if (window.DEBUG_MODE) {
            console.log(`🔄 Toggle OFF modalità: ${mode}`);
        }
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
            // Le linee perpendicolari e le coppie sono sempre selezionabili
            if (obj.isPerpendicularLine || obj.isCoupleVerticalLine) {
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

    // Imposta cursore su tutti gli oggetti, TRANNE le linee perpendicolari e coppie
    const objects = fabricCanvas.getObjects();
    objects.forEach(obj => {
        // Le linee perpendicolari e coppie mantengono sempre il cursore 'move'
        if (!obj.isPerpendicularLine && !obj.isCoupleVerticalLine) {
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
 * Cerca manualmente la linea più vicina al punto di tocco entro una tolleranza extra.
 * Fallback per dispositivi mobile dove la precisione del dito è limitata.
 * Fabric.js già usa padding:20 sulle linee; questo aggiunge ulteriori 25px di sicurezza.
 * @param {Object} pointer - Coordinate {x, y} sul canvas Fabric.js
 * @returns {fabric.Object|null}
 */
function findNearestTouchTarget(pointer) {
    if (!fabricCanvas) return null;
    const EXTRA_TOLERANCE = 25; // px extra oltre al padding già impostato nelle linee

    const objects = fabricCanvas.getObjects();
    // Scansiona dall'ultimo (in cima allo stack) al primo per rispettare lo z-order
    for (let i = objects.length - 1; i >= 0; i--) {
        const obj = objects[i];
        if (!obj.selectable || !obj.evented) continue;
        if (!obj.isPerpendicularLine && !obj.isCoupleVerticalLine) continue;

        const bounds = obj.getBoundingRect();
        if (pointer.x >= bounds.left - EXTRA_TOLERANCE &&
            pointer.x <= bounds.left + bounds.width + EXTRA_TOLERANCE &&
            pointer.y >= bounds.top - EXTRA_TOLERANCE &&
            pointer.y <= bounds.top + bounds.height + EXTRA_TOLERANCE) {
            console.log(`👆 findNearestTouchTarget: linea trovata (${obj.isPerpendicularLine ? 'orizzontale' : 'coppia verticale'})`);
            return obj;
        }
    }
    return null;
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
    fabricCanvas.on('mouse:down', function (opt) {
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

        // PRIORITÀ 3: In modalità default (null) permetti sempre il drag di linee esistenti.
        // Usa findNearestTouchTarget come fallback per tocchi imprecisi su mobile.
        if (currentCanvasMode === null) {
            const fallbackTarget = target || findNearestTouchTarget(pointer);
            if (fallbackTarget && (fallbackTarget.isPerpendicularLine || fallbackTarget.isCoupleVerticalLine)) {
                console.log('👆 Modalità default - linea rilevata, avvio drag nativo Fabric.js');
                fabricCanvas.setActiveObject(fallbackTarget);
                return;
            }
        }

        switch (currentCanvasMode) {
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

            case 'line': {
                // Cerca linea con tolleranza extra per tocco mobile (fallback)
                const resolvedLine = target || findNearestTouchTarget(pointer);
                if (resolvedLine && resolvedLine.isPerpendicularLine) {
                    console.log('🎯 Tocco su linea perpendicolare esistente - drag mode');
                    fabricCanvas.setActiveObject(resolvedLine);
                    return; // Lascia gestire a Fabric.js
                }
                // Altrimenti crea una nuova linea
                handleDrawStart(opt, pointer);
                break;
            }

            case 'couple': {
                // Cerca linea coppia con tolleranza extra per tocco mobile (fallback)
                const resolvedCouple = target || findNearestTouchTarget(pointer);
                if (resolvedCouple && resolvedCouple.isCoupleVerticalLine) {
                    console.log('🎯 Tocco su linea coppia verticale esistente - drag mode');
                    fabricCanvas.setActiveObject(resolvedCouple);
                    return; // Lascia gestire a Fabric.js
                }
                // Altrimenti crea una nuova coppia di linee speculari
                handleCoupleDrawStart(opt, pointer);
                break;
            }

            case 'rectangle':
            case 'circle':
                handleDrawStart(opt, pointer);
                break;

            case 'eyedropper':
                handleEyedropperCanvasClick(evt, pointer);
                break;
        }
    });

    // === MOUSE MOVE ===
    fabricCanvas.on('mouse:move', function (opt) {
        if (currentCanvasMode === 'pan' && isPanning) {
            handlePanMove(opt);
        } else if ((currentCanvasMode === 'line' || currentCanvasMode === 'rectangle' || currentCanvasMode === 'circle') && canvasModeIsDrawing) {
            handleDrawMove(opt);
        }
    });

    // === MOUSE UP ===
    fabricCanvas.on('mouse:up', function (opt) {
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

    // Aggiorna dinamicamente i range degli slider per white dots
    if (typeof updateSliderRangesForZoom === 'function') {
        updateSliderRangesForZoom(newZoom);
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

    // Aggiorna dinamicamente i range degli slider per white dots
    if (typeof updateSliderRangesForZoom === 'function') {
        updateSliderRangesForZoom(newZoom);
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
    switch (currentCanvasMode) {
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
    switch (currentCanvasMode) {
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

    const measureBtn = document.getElementById('measure-btn');
    const selectionBtn = document.querySelector('[data-tool="selection"]');

    console.log('🔧 toggleMeasureMode chiamato!', {
        measureModeActive,
        measureBtn: measureBtn ? 'trovato' : 'NON TROVATO',
        btnText: measureBtn ? measureBtn.innerHTML : 'N/A',
        hasActive: measureBtn ? measureBtn.classList.contains('active') : 'N/A'
    });

    if (measureModeActive) {
        // Attiva misura - PULISCI tutto prima di iniziare una nuova misurazione
        console.log('🔧 Attivazione modalità misura - Pulizia misurazioni precedenti');

        // Pulisci punti selezionati e overlay
        if (window.selectedLandmarksForMeasurement) {
            window.selectedLandmarksForMeasurement = [];
        }

        // Rimuovi tutti gli overlay di misurazione dal canvas
        if (typeof fabricCanvas !== 'undefined' && fabricCanvas) {
            const measurementObjects = fabricCanvas.getObjects().filter(obj => obj.isMeasurement);
            measurementObjects.forEach(obj => fabricCanvas.remove(obj));
            fabricCanvas.renderAll();
            console.log('🧹 Rimossi', measurementObjects.length, 'overlay di misurazione');
        }

        if (measureBtn) {
            measureBtn.classList.add('active');
            measureBtn.innerHTML = '🏁 Fine Misura';
            console.log('✅ Pulsante aggiornato:', measureBtn.innerHTML, measureBtn.className);
        } else {
            console.error('❌ Pulsante measure-btn NON TROVATO nel DOM!');
        }
        if (selectionBtn) {
            selectionBtn.disabled = false; // Abilita selezione
        }

        // Imposta modalità selezione automaticamente
        setCanvasMode('selection');

        // Attiva landmarks se non già visibili
        if (typeof window.toggleLandmarks === 'function' && !window.landmarkSelectionMode) {
            window.toggleLandmarks();
        }

        console.log('📐 Modalità MISURA attivata → Selezione abilitata');
    } else {
        // Disattiva misura - invia i dati alla tabella unificata
        console.log('🔧 Disattivazione misura, window.measurementResults:', window.measurementResults);

        if (window.measurementResults && window.measurementResults.length > 0) {
            // Marca TUTTE le misurazioni come completate quando si clicca "Fine Misura"
            window.measurementResults.forEach(m => {
                if (!m.completed) {
                    m.completed = true;
                    console.log('✅ Misurazione marcata come completata:', m.label);
                }
            });

            const completedMeasurements = window.measurementResults.filter(m => m.completed);
            console.log('🔧 Misurazioni completate:', completedMeasurements.length);

            if (completedMeasurements.length > 0) {
                // Espandi sezione DATI ANALISI prima di aggiungere i dati
                console.log('🔧 Verifico se ensureMeasurementsSectionOpen esiste:', typeof ensureMeasurementsSectionOpen);

                if (typeof ensureMeasurementsSectionOpen === 'function') {
                    console.log('🔧 Chiamo ensureMeasurementsSectionOpen()');
                    ensureMeasurementsSectionOpen();
                } else if (typeof window.ensureMeasurementsSectionOpen === 'function') {
                    console.log('🔧 Chiamo window.ensureMeasurementsSectionOpen()');
                    window.ensureMeasurementsSectionOpen();
                } else {
                    console.error('❌ ensureMeasurementsSectionOpen NON TROVATA!');
                }

                // Aggiungi ogni misurazione completata alla tabella unificata
                completedMeasurements.forEach(result => {
                    console.log('🔧 Aggiungo misurazione:', result.label, result.value, result.unit);
                    if (typeof addMeasurementToTable === 'function') {
                        addMeasurementToTable(result.label, result.value, result.unit, 'manual-measurement');
                    } else if (typeof window.addMeasurementToTable === 'function') {
                        window.addMeasurementToTable(result.label, result.value, result.unit, 'manual-measurement');
                    } else {
                        console.error('❌ addMeasurementToTable NON TROVATA!');
                    }
                });
                // Pulisci i risultati dopo averli inviati
                window.measurementResults = [];
                // Aggiorna anche la vecchia tabella
                if (typeof updateMeasurementsTable === 'function') {
                    updateMeasurementsTable();
                }
            }
        } else {
            console.warn('⚠️ Nessuna misurazione da inviare alla tabella');
        }

        if (measureBtn) {
            measureBtn.classList.remove('active');
            measureBtn.innerHTML = '📐 Misura';
            console.log('✅ Pulsante ripristinato:', measureBtn.innerHTML, measureBtn.className);
        } else {
            console.error('❌ Pulsante measure-btn NON TROVATO quando disattivo!');
        }
        if (selectionBtn) {
            selectionBtn.disabled = true; // Disabilita selezione
        }

        // Torna a modalità null
        setCanvasMode(null);
        updateCanvasCursor('default');

        console.log('📐 Modalità MISURA disattivata → Dati inviati alla tabella');
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

// === GESTIONE COPPIA LINEE VERTICALI SPECULARI ===

function handleCoupleDrawStart(opt, pointer) {
    /**
     * Gestisce il click per creare una coppia di linee verticali speculari rispetto all'asse
     */
    console.log(`⚖️ Inizio creazione coppia linee verticali speculari da`, pointer);

    // Verifica che l'asse di simmetria sia presente
    if (!window.currentLandmarks || !window.currentLandmarks[9] || !window.currentLandmarks[164]) {
        showToast('Attiva prima l\'asse di simmetria', 'warning');
        return;
    }

    // Attiva automaticamente il pulsante ASSE se non già attivo
    const axisBtn = document.getElementById('axis-btn');
    if (axisBtn && !axisBtn.classList.contains('active')) {
        console.log('⚖️ Attivazione automatica asse di simmetria');
        if (typeof toggleAxis === 'function') {
            toggleAxis();
        }
    }

    // Calcola le coordinate trasformate dell'asse
    const glabella = window.currentLandmarks[9];
    const philtrum = window.currentLandmarks[164];
    const transGlab = transformLandmarkCoordinate(glabella);
    const transPhil = transformLandmarkCoordinate(philtrum);

    // Vettore dell'asse di simmetria
    const axisVecX = transPhil.x - transGlab.x;
    const axisVecY = transPhil.y - transGlab.y;
    const axisLength = Math.sqrt(axisVecX * axisVecX + axisVecY * axisVecY);
    const axisNormX = axisVecX / axisLength;
    const axisNormY = axisVecY / axisLength;

    // Direzione perpendicolare all'asse (sinistra-destra)
    const perpX = -axisNormY;
    const perpY = axisNormX;

    // Calcola la proiezione del click sull'asse per trovare la posizione Y (lungo l'asse)
    const clickVecX = pointer.x - transGlab.x;
    const clickVecY = pointer.y - transGlab.y;
    const projectionOnAxis = (clickVecX * axisVecX + clickVecY * axisVecY) / (axisLength * axisLength);

    // Calcola la distanza perpendicolare del click dall'asse
    const distanceFromAxis = clickVecX * perpX + clickVecY * perpY;

    console.log(`📍 Click: (${pointer.x.toFixed(1)}, ${pointer.y.toFixed(1)})`);
    console.log(`📍 Proiezione sull'asse: ${projectionOnAxis.toFixed(3)}`);
    console.log(`📍 Distanza dall'asse: ${distanceFromAxis.toFixed(1)}`);

    // Chiama la funzione in main.js per creare la coppia
    if (typeof window.addCoupleVerticalLines === 'function') {
        window.addCoupleVerticalLines(projectionOnAxis, Math.abs(distanceFromAxis));
    } else {
        console.error('❌ Funzione addCoupleVerticalLines non trovata');
    }
}

// === GESTIONE EYEDROPPER (CONTAGOCCE) ===

/**
 * Gestisce il click sul canvas quando l'eyedropper è attivo
 * Converte le coordinate Fabric.js in coordinate immagine e chiama l'analisi
 */
function handleEyedropperCanvasClick(evt, pointer) {
    console.log('💧 Eyedropper click via canvas-modes', pointer);

    if (!window.currentImage) {
        if (typeof showToast === 'function') {
            showToast('Nessuna immagine caricata', 'warning');
        }
        return;
    }

    // Converti coordinate pointer (canvas Fabric.js) in coordinate immagine originale
    const scale = window.imageScale || 1;
    const offset = window.imageOffset || { x: 0, y: 0 };

    // Le coordinate sull'immagine originale
    const imgX = Math.round((pointer.x - offset.x) / scale);
    const imgY = Math.round((pointer.y - offset.y) / scale);

    console.log(`💧 Click: canvas(${pointer.x.toFixed(0)}, ${pointer.y.toFixed(0)}) → img(${imgX}, ${imgY})`);
    console.log(`   Scale: ${scale}, Offset: (${offset.x.toFixed(1)}, ${offset.y.toFixed(1)})`);

    // Chiama la funzione di analisi in main.js
    if (typeof window.analyzePixelArea === 'function') {
        window.analyzePixelArea(imgX, imgY);
    } else {
        console.error('❌ Funzione analyzePixelArea non trovata in window');
    }
}

// === ESPORTA FUNZIONI GLOBALI ===

window.setCanvasMode = setCanvasMode;
window.toggleMeasureMode = toggleMeasureMode;
window.initializeCanvasModes = initializeCanvasModes;
window.currentCanvasMode = currentCanvasMode;
window.handleCoupleDrawStart = handleCoupleDrawStart;
window.handleEyedropperCanvasClick = handleEyedropperCanvasClick;

console.log('✅ canvas-modes.js caricato');
