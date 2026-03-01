/**
 * Face Analysis Complete - Gestione analisi visagistica completa
 * Integrazione con face_analysis_module.py
 */

// Variabile globale per memorizzare il report corrente
let currentAnalysisReport = null;
let isReadingReport = false;
let reportTextForSpeech = null; // Testo ottimizzato per lettura vocale
let reportSections = {}; // Sezioni del report per lettura selettiva
let awaitingSectionSelection = false; // Flag per selezione sezione in corso

/**
 * Esegue l'analisi visagistica completa
 */
async function performCompleteAnalysis(event) {
    console.log('🧬 Avvio analisi visagistica completa...');

    // Verifica che ci sia un'immagine caricata
    if (!currentImage) {
        showToast('⚠️ Carica prima un\'immagine per eseguire l\'analisi', 'warning');
        return;
    }

    try {
        // Mostra il modal
        const modal = document.getElementById('analysis-modal');
        const loadingDiv = document.getElementById('analysis-loading');
        const reportDiv = document.getElementById('analysis-report');

        if (modal) modal.style.display = 'block';
        if (loadingDiv) loadingDiv.style.display = 'block';
        if (reportDiv) reportDiv.style.display = 'none';

        // Converti l'immagine corrente in Blob
        const imageBlob = await getCanvasImageAsBlob();

        // Crea FormData per l'upload
        const formData = new FormData();
        formData.append('file', imageBlob, 'analysis_image.jpg');

        // Chiamata API
        const response = await fetch(`${window.location.origin}/api/face-analysis/complete`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Errore durante l\'analisi');
        }

        const result = await response.json();

        if (result.success) {
            console.log('✅ Analisi completata con successo');
            currentAnalysisReport = result;

            // Mostra il report
            displayAnalysisReport(result);

            showToast('✅ Analisi visagistica completata', 'success');
        } else {
            throw new Error('Analisi non riuscita');
        }

    } catch (error) {
        console.error('❌ Errore analisi:', error);
        showToast(`Errore durante l'analisi: ${error.message}`, 'error');
        closeAnalysisModal();
    }
}

/**
 * Ottiene l'immagine del canvas come Blob
 */
async function getCanvasImageAsBlob() {
    return new Promise((resolve, reject) => {
        // Se abbiamo un'immagine corrente, usiamo quella
        if (currentImage && currentImage.src) {
            // Converti data URL in Blob
            fetch(currentImage.src)
                .then(res => res.blob())
                .then(blob => resolve(blob))
                .catch(reject);
        } else if (fabricCanvas) {
            // Altrimenti, usa il canvas Fabric
            fabricCanvas.getElement().toBlob((blob) => {
                if (blob) {
                    resolve(blob);
                } else {
                    reject(new Error('Impossibile convertire canvas in blob'));
                }
            }, 'image/jpeg', 0.95);
        } else {
            reject(new Error('Nessuna immagine disponibile'));
        }
    });
}

/**
 * Visualizza il report di analisi nel modal
 */
function displayAnalysisReport(result) {
    const loadingDiv = document.getElementById('analysis-loading');
    const reportDiv = document.getElementById('analysis-report');
    const reportContent = document.getElementById('report-content');

    if (loadingDiv) loadingDiv.style.display = 'none';
    if (reportDiv) reportDiv.style.display = 'block';

    if (reportContent) {
        reportContent.textContent = result.report;
    }

    // Crea versione ottimizzata del testo per la lettura vocale
    reportTextForSpeech = optimizeTextForSpeech(result.report);

    // Suddividi il report in sezioni per lettura selettiva
    reportSections = extractReportSections(result.report);

    // Opzionalmente mostra le immagini debug
    if (result.debug_images && Object.keys(result.debug_images).length > 0) {
        displayDebugImages(result.debug_images);
    }
}

/**
 * Ottimizza il testo del report per la lettura vocale
 * Rimuove simboli grafici e formatta per Isabella
 */
function optimizeTextForSpeech(reportText) {
    if (!reportText) return '';

    let optimized = reportText;

    // Rimuove linee di separazione fatte con caratteri ripetuti
    optimized = optimized.replace(/={3,}/g, ''); // Rimuove ====
    optimized = optimized.replace(/-{3,}/g, ''); // Rimuove ----
    optimized = optimized.replace(/•/g, ''); // Rimuove bullet points

    // Sostituisce simboli con pause o testo leggibile
    optimized = optimized.replace(/\*{2,}/g, ''); // Rimuove asterischi
    optimized = optimized.replace(/_{2,}/g, ''); // Rimuove underscore multipli

    // Gestisce le sezioni (SEZIONE 1: -> Sezione 1)
    optimized = optimized.replace(/SEZIONE (\d+):/g, 'Sezione $1.');

    // Rimuove spazi multipli
    optimized = optimized.replace(/\s{3,}/g, ' ');

    // Rimuove linee vuote multiple (più di 2)
    optimized = optimized.replace(/\n{3,}/g, '\n\n');

    // Aggiunge pause dopo i titoli delle sezioni
    optimized = optimized.replace(/SEZIONE (.*?)\n/g, 'Sezione $1. \n\n');

    // Sostituisce alcuni simboli comuni
    optimized = optimized.replace(/📏/g, '');
    optimized = optimized.replace(/📊/g, '');
    optimized = optimized.replace(/📐/g, '');
    optimized = optimized.replace(/✅/g, '');
    optimized = optimized.replace(/⚠️/g, 'Attenzione:');
    optimized = optimized.replace(/✓/g, '');
    optimized = optimized.replace(/❌/g, '');

    // Formatta i numeri con virgola per la lettura italiana
    // Es: "1.234" -> "1 virgola 234"
    optimized = optimized.replace(/(\d+)\.(\d+)/g, '$1 virgola $2');

    // Migliora la leggibilità delle percentuali
    optimized = optimized.replace(/(\d+)%/g, '$1 percento');

    // Rimuove caratteri speciali inutili alla fine delle righe
    optimized = optimized.replace(/\s*[:;]\s*$/gm, '.');

    // Normalizza gli spazi
    optimized = optimized.trim();

    console.log('📝 Testo ottimizzato per lettura vocale');
    return optimized;
}

/**
 * Estrae le sezioni del report per lettura selettiva
 * NOTA: Esclude la sezione 4 (immagini) dalla lettura vocale
 */
function extractReportSections(reportText) {
    const sections = {};
    const lines = reportText.split('\n');

    let currentSection = null;
    let currentContent = [];

    for (let line of lines) {
        // Rileva inizio di una nuova sezione (es. "SEZIONE 1: TITOLO")
        const sectionMatch = line.match(/^SEZIONE (\d+):\s*(.+)$/);

        if (sectionMatch) {
            // Salva la sezione precedente se esiste (esclusa sezione 4)
            if (currentSection && currentSection.number !== '4') {
                sections[currentSection.number] = {
                    title: currentSection.title,
                    content: optimizeTextForSpeech(currentContent.join('\n'))
                };
            }

            // Inizia nuova sezione
            currentSection = {
                number: sectionMatch[1],
                title: sectionMatch[2].trim()
            };
            currentContent = [];
        } else if (currentSection && currentSection.number !== '4') {
            // Aggiungi contenuto solo se non è la sezione 4
            currentContent.push(line);
        }
    }

    // Salva l'ultima sezione (esclusa sezione 4)
    if (currentSection && currentSection.number !== '4') {
        sections[currentSection.number] = {
            title: currentSection.title,
            content: optimizeTextForSpeech(currentContent.join('\n'))
        };
    }

    console.log('📚 Report suddiviso in', Object.keys(sections).length, 'sezioni (sezione 4 esclusa dalla lettura vocale)');
    return sections;
}

/**
 * Visualizza le immagini debug con supporto fullscreen
 */
function displayDebugImages(debugImages) {
    const container = document.getElementById('debug-images-container');
    const grid = document.getElementById('debug-images-grid');

    if (!container || !grid) return;

    // Svuota il grid
    grid.innerHTML = '';

    // Aggiungi ciascuna immagine
    for (const [key, base64Data] of Object.entries(debugImages)) {
        const imgDiv = document.createElement('div');
        imgDiv.style.cssText = 'border: 1px solid #ddd; border-radius: 8px; overflow: hidden; cursor: pointer; transition: transform 0.3s;';

        // Effetto hover
        imgDiv.addEventListener('mouseenter', () => {
            imgDiv.style.transform = 'scale(1.05)';
        });
        imgDiv.addEventListener('mouseleave', () => {
            imgDiv.style.transform = 'scale(1)';
        });

        const img = document.createElement('img');
        const imgSrc = `data:image/jpeg;base64,${base64Data}`;
        img.src = imgSrc;
        img.alt = key;
        img.style.cssText = 'width: 100%; height: auto; display: block;';

        // Click per fullscreen
        imgDiv.addEventListener('click', () => {
            openImageFullscreen(imgSrc, key);
        });

        const label = document.createElement('p');
        label.textContent = key.replace(/_/g, ' ').toUpperCase();
        label.style.cssText = 'margin: 0; padding: 8px; background: #f0f0f0; text-align: center; font-size: 12px;';

        imgDiv.appendChild(img);
        imgDiv.appendChild(label);
        grid.appendChild(imgDiv);
    }

    container.style.display = 'block';
}

/**
 * Chiude il modal di analisi
 */
function closeAnalysisModal() {
    const modal = document.getElementById('analysis-modal');
    if (modal) modal.style.display = 'none';

    // Ferma la lettura vocale se attiva
    if (isReadingReport) {
        stopReportReading();
    }

    // Reset posizione del modal al centro per la prossima apertura
    resetModalPosition();
}

/**
 * Carica il logo Kimerika come immagine base64
 */
async function loadKimerikaLogo() {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = function() {
            // Converti in base64
            const canvas = document.createElement('canvas');
            canvas.width = img.width;
            canvas.height = img.height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            const dataURL = canvas.toDataURL('image/png');
            resolve(dataURL);
        };
        img.onerror = function() {
            console.warn('⚠️ Impossibile caricare il logo, uso testo come fallback');
            resolve(null);
        };
        img.src = '/Kimeriza DIGITAL DESIGN SYSTEM (2).png';
    });
}

/**
 * Genera didascalia scientifica personalizzata per ogni immagine di debug
 */
function getImageCaption(key, reportData) {
    const data = reportData && reportData.data ? reportData.data : {};
    const metrics = data.metriche_facciali || {};
    const features = data.caratteristiche_facciali || {};
    const faceShape = data.forma_viso || 'N/D';
    const vis = data.analisi_visagistica || {};

    const formaLabel = faceShape.charAt(0).toUpperCase() + faceShape.slice(1);
    const sopraLabel = vis.forma_sopracciglio ? vis.forma_sopracciglio.value || vis.forma_sopracciglio : 'N/D';

    const captions = {
        'face_mesh': `Visualizzazione della mesh facciale MediaPipe con 468 landmark rilevati in tempo reale ` +
            `sull'immagine analizzata. I punti colorati evidenziano le zone anatomiche chiave: arancione = occhi, ` +
            `verde = naso, rosso = bocca, giallo = sopracciglia, ciano = contorno viso. ` +
            `Forma viso classificata: ${formaLabel.toUpperCase()}. ` +
            `Distanza inter-oculare misurata: ${metrics.distanza_occhi ? metrics.distanza_occhi.toFixed(1) : 'N/D'} px.`,

        'geometria': `Analisi geometrica con misure estratte dai landmark reali del viso. ` +
            `Larghezza fronte: ${metrics.larghezza_fronte ? metrics.larghezza_fronte.toFixed(0) : 'N/D'} px, ` +
            `zigomi: ${metrics.larghezza_zigomi ? metrics.larghezza_zigomi.toFixed(0) : 'N/D'} px, ` +
            `mascella: ${metrics.larghezza_mascella ? metrics.larghezza_mascella.toFixed(0) : 'N/D'} px. ` +
            `Le linee orizzontali ciano indicano i terzi facciali rinascimentali. ` +
            `La linea blu indica il punto della sezione aurea (Phi = 1.618). ` +
            `Rapporto L/W misurato: ${metrics.rapporto_lunghezza_larghezza ? metrics.rapporto_lunghezza_larghezza.toFixed(3) : 'N/D'} (ideale: 1.30-1.40).`,

        'sopracciglia': `Mappa della zona sopraccigliare con le tre zone funzionali colorate: ` +
            `verde = INIZIO (ancoraggio nasale), giallo = ARCO/CORPO (zona di curvatura), ` +
            `rosso-arancio = CODA (terminazione laterale). ` +
            `Distanza occhio-sopracciglio misurata: ${metrics.distanza_occhio_sopracciglio ? metrics.distanza_occhio_sopracciglio.toFixed(1) : 'N/D'} px ` +
            `(media bilaterale). Distanza inter-oculare: ${metrics.distanza_occhi ? metrics.distanza_occhi.toFixed(1) : 'N/D'} px. ` +
            `Caratteristiche: occhi ${features.occhi_distanza || 'N/D'}, dimensione ${features.occhi_dimensione || 'N/D'}.`,

        'forma_ideale': `Guida professionale per la forma sopracciglio consigliata: ${sopraLabel.toUpperCase()}. ` +
            `La zona verde semi-trasparente indica l'area target di densita' del sopracciglio (bordo superiore e inferiore). ` +
            `Marcatori di riferimento: INIZIO (punto ciano) allineato all'ala nasale, ` +
            `punto massimo ARCO (punto magenta), CODA (punto arancione) allineata all'angolo laterale occhio. ` +
            `La freccia con misura indica lo spessore massimo consigliato nel punto centrale. ` +
            `Forma viso: ${formaLabel.toUpperCase()} — la scelta della forma sopracciglio e' calibrata su questa struttura.`,

        'mappa_completa': `Mappa di sintesi completa dell'analisi visagistica. ` +
            `La linea ciano verticale indica l'asse di simmetria (allineato alla punta del naso). ` +
            `Le linee gialle mostrano i terzi facciali, la linea blu la sezione aurea Phi. ` +
            `Forma viso: ${formaLabel.toUpperCase()}, rapporto L/W: ${metrics.rapporto_lunghezza_larghezza ? metrics.rapporto_lunghezza_larghezza.toFixed(3) : 'N/D'}, ` +
            `rapporto M/F: ${metrics.rapporto_mascella_fronte ? metrics.rapporto_mascella_fronte.toFixed(3) : 'N/D'}, ` +
            `prominenza zigomi: ${metrics.prominenza_zigomi ? metrics.prominenza_zigomi.toFixed(3) : 'N/D'}.`,

        'proporzione_aurea': `Analisi delle proporzioni auree (Phi = 1.618) sovrapposte al viso reale. ` +
            `Il rettangolo aureo (linee dorate) e' calcolato sulla larghezza degli zigomi e sull'altezza facciale misurata. ` +
            `La spirale di Fibonacci e' ancorata al naso come punto focale naturale del viso. ` +
            `Rapporto L/W misurato: ${metrics.rapporto_lunghezza_larghezza ? metrics.rapporto_lunghezza_larghezza.toFixed(3) : 'N/D'} ` +
            `(rapporto aureo ideale: 1.618). Le linee tratteggiate indicano dove le proporzioni del viso si avvicinano ` +
            `o si discostano dall'armonia aurea classica (basata su Marquardt Beauty Mask, 2002).`,

        'analisi_simmetria': `Analisi visiva della simmetria bilaterale. ` +
            `Colonna sinistra: viso originale. Colonna centrale: sovrapposizione con asse di simmetria. ` +
            `Colonna destra: proiezione simmetrica del lato sinistro — mostra come apparirebbe il viso ` +
            `con simmetria perfetta. Le differenze visibili tra colonna centrale e destra riflettono ` +
            `l'asimmetria naturale presente in ogni viso umano. ` +
            `L'asimmetria facciale moderata (< 5% di variazione) e' considerata fisiologicamente normale ` +
            `(Ferrario et al., 1993, Journal of Craniofacial Surgery).`,

        'guida_makeup': `Guida pratica per l'applicazione professionale del sopracciglio tipo ${sopraLabel.toUpperCase()}. ` +
            `La zona verde semi-trasparente indica l'area da riempire con matita o pomade. ` +
            `Le tre linee guida verticali calcolate sui landmark facciali reali indicano: ` +
            `INIZIO (linea gialla, allineato all'ala del naso), ARCO (linea arancione, allineato al bordo esterno ` +
            `dell'iride in posizione frontale), FINE/CODA (linea rossa, allineata all'angolo laterale dell'occhio). ` +
            `Tutte le misure sono personalizzate sui landmark del viso analizzato.`
    };

    return captions[key] || `Immagine di analisi facciale: ${key.replace(/_/g, ' ').toUpperCase()}.`;
}

/**
 * Disegna una barra orizzontale con marker nel PDF (helper per dashboard dati)
 */
function drawMetricBar(doc, x, y, barWidth, barHeight, value, minVal, maxVal, idealMin, idealMax, label, unit) {
    const barBg = barWidth;

    // Sfondo barra grigio chiaro
    doc.setFillColor(230, 225, 232);
    doc.setDrawColor(180, 170, 185);
    doc.setLineWidth(0.2);
    doc.roundedRect(x, y, barBg, barHeight, 1, 1, 'FD');

    // Zona ideale in verde chiaro
    const idealX = x + ((idealMin - minVal) / (maxVal - minVal)) * barBg;
    const idealW = ((idealMax - idealMin) / (maxVal - minVal)) * barBg;
    doc.setFillColor(180, 230, 180);
    doc.setDrawColor(120, 190, 120);
    doc.setLineWidth(0.1);
    doc.roundedRect(idealX, y, Math.max(idealW, 1), barHeight, 0.5, 0.5, 'FD');

    // Barra valore misurato
    const clampedVal = Math.min(Math.max(value, minVal), maxVal);
    const valW = ((clampedVal - minVal) / (maxVal - minVal)) * barBg;
    doc.setFillColor(129, 29, 123);
    doc.roundedRect(x, y, Math.max(valW, 1.5), barHeight, 1, 1, 'F');

    // Marker valore (linea verticale gialla + punto)
    const valX = x + valW;
    doc.setDrawColor(200, 160, 0);
    doc.setLineWidth(0.7);
    doc.line(valX, y - 1, valX, y + barHeight + 1);
    doc.setFillColor(253, 210, 0);
    doc.circle(valX, y + barHeight / 2, 1.2, 'F');

    // Label a sinistra
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(7.5);
    doc.setTextColor(60, 40, 70);
    doc.text(label, x - 1, y + barHeight - 0.5, { align: 'right' });

    // Valore a destra
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(50, 50, 50);
    doc.text(`${value.toFixed(3)} ${unit}`, x + barBg + 1.5, y + barHeight - 0.5);
}

/**
 * Genera PDF del report con formattazione scientifica professionale,
 * dashboard dati, grafici a barre, pagina indice e immagini con didascalie
 */
async function generateAnalysisPDF() {
    if (!currentAnalysisReport) {
        showToast('⚠️ Nessun report disponibile', 'warning');
        return;
    }

    try {
        // Carica il logo Kimerika
        const logoImg = await loadKimerikaLogo();

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

        const pageWidth = doc.internal.pageSize.getWidth();
        const pageHeight = doc.internal.pageSize.getHeight();
        const margin = 15;
        const maxWidth = pageWidth - (margin * 2);

        // LineHeight dinamico per tipo di elemento
        const LH = { section: 10, subsection: 8.5, body: 6.5, biblio: 5.5, empty: 3 };

        // Helper: aggiungi nuova pagina con header minimale
        const addContentPage = () => {
            doc.addPage();
            // Header viola sottile
            doc.setFillColor(129, 29, 123);
            doc.rect(0, 0, pageWidth, 12, 'F');
            doc.setFontSize(7.5);
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(255, 255, 255);
            doc.text('KIMERIKA  |  Analisi Visagistica Professionale', margin, 8.5);
            return 18; // currentY dopo header
        };

        // Helper: controlla spazio e aggiungi pagina se necessario
        const checkPageSpace = (currentY, needed) => {
            if (currentY + needed > pageHeight - margin - 18) {
                return addContentPage();
            }
            return currentY;
        };

        // Helper: aggiunge logo in posizione
        const addLogo = (x, y, maxW) => {
            if (!logoImg) {
                doc.setFontSize(11);
                doc.setFont('helvetica', 'bold');
                doc.setTextColor(129, 29, 123);
                doc.text('KIMERIKA', x, y);
                return;
            }
            try {
                const props = doc.getImageProperties(logoImg);
                const ratio = props.width / props.height;
                const w = maxW;
                const h = w / ratio;
                doc.addImage(logoImg, 'PNG', x, y - h / 2, w, h);
            } catch(e) {
                doc.setFontSize(11);
                doc.setFont('helvetica', 'bold');
                doc.setTextColor(129, 29, 123);
                doc.text('KIMERIKA', x, y);
            }
        };

        // ============================================================
        // PAGINA 1 — COPERTINA PROFESSIONALE
        // ============================================================
        // Sfondo a bande
        doc.setFillColor(255, 252, 230);
        doc.rect(0, 0, pageWidth, pageHeight * 0.38, 'F');
        doc.setFillColor(250, 244, 250);
        doc.rect(0, pageHeight * 0.38, pageWidth, pageHeight * 0.35, 'F');
        doc.setFillColor(244, 238, 244);
        doc.rect(0, pageHeight * 0.73, pageWidth, pageHeight * 0.27, 'F');

        // Bordo doppio
        doc.setDrawColor(129, 29, 123);
        doc.setLineWidth(1.8);
        doc.rect(9, 9, pageWidth - 18, pageHeight - 18);
        doc.setLineWidth(0.4);
        doc.rect(12, 12, pageWidth - 24, pageHeight - 24);

        // Banda viola in alto
        doc.setFillColor(129, 29, 123);
        doc.rect(9, 9, pageWidth - 18, 22, 'F');
        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(253, 242, 0);
        doc.text('FACIAL ANALYSIS & VISAGISM  |  PROFESSIONAL SCIENTIFIC REPORT', pageWidth / 2, 22, { align: 'center' });

        // Logo centrato
        addLogo(pageWidth / 2 - 35, 58, 70);

        // Sottotitolo logo
        doc.setFontSize(8.5);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(110, 80, 120);
        doc.text('Sistema di Analisi Facciale Avanzato', pageWidth / 2, 78, { align: 'center' });

        // Linea decorativa
        doc.setDrawColor(253, 242, 0);
        doc.setLineWidth(1.2);
        doc.line(pageWidth / 2 - 50, 83, pageWidth / 2 + 50, 83);

        // Titolo principale
        doc.setFontSize(30);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(80, 55, 85);
        doc.text('ANALISI VISAGISTICA', pageWidth / 2, pageHeight / 2 - 8, { align: 'center' });

        doc.setFontSize(26);
        doc.setTextColor(129, 29, 123);
        doc.text('COMPLETA', pageWidth / 2, pageHeight / 2 + 10, { align: 'center' });

        // Linea divisoria
        doc.setDrawColor(253, 242, 0);
        doc.setLineWidth(0.6);
        doc.line(margin + 20, pageHeight / 2 + 18, pageWidth - margin - 20, pageHeight / 2 + 18);

        // Sottotitolo
        doc.setFontSize(12);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(90, 70, 95);
        doc.text('Report Scientifico Professionale Personalizzato', pageWidth / 2, pageHeight / 2 + 28, { align: 'center' });

        // Data (senza emoji)
        const dateStr = new Date().toLocaleDateString('it-IT', { year: 'numeric', month: 'long', day: 'numeric' });
        doc.setFontSize(10);
        doc.setTextColor(110, 90, 115);
        doc.text(`Data: ${dateStr}`, pageWidth / 2, pageHeight / 2 + 42, { align: 'center' });

        // Box forma viso se disponibile
        const dataObj = currentAnalysisReport.data || {};
        const metrics = dataObj.metriche_facciali || {};
        const features = dataObj.caratteristiche_facciali || {};
        const faceShape = dataObj.forma_viso || '';
        if (faceShape) {
            doc.setFillColor(129, 29, 123);
            doc.roundedRect(pageWidth / 2 - 30, pageHeight / 2 + 50, 60, 14, 3, 3, 'F');
            doc.setFontSize(10);
            doc.setFont('helvetica', 'bold');
            doc.setTextColor(255, 255, 255);
            doc.text(`VISO ${faceShape.toUpperCase()}`, pageWidth / 2, pageHeight / 2 + 59, { align: 'center' });
        }

        // Box disclaimer in basso
        const boxY = pageHeight - 58;
        doc.setFillColor(252, 248, 255);
        doc.setDrawColor(253, 242, 0);
        doc.setLineWidth(0.8);
        doc.roundedRect(margin + 10, boxY, maxWidth - 20, 32, 3, 3, 'FD');
        doc.setFontSize(8.5);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(90, 70, 95);
        doc.text('Analisi basata su evidenze scientifiche peer-reviewed', pageWidth / 2, boxY + 10, { align: 'center' });
        doc.text('Metodologie di visagismo professionale, neuroscienze e proporzione aurea', pageWidth / 2, boxY + 20, { align: 'center' });

        // Copyright
        doc.setFontSize(7.5);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(130, 110, 135);
        doc.text(`© ${new Date().getFullYear()} Kimerika - Facial Analysis System`, pageWidth / 2, pageHeight - 15, { align: 'center' });

        // ============================================================
        // PAGINA 2 — INDICE / SOMMARIO
        // ============================================================
        let currentY = addContentPage();

        // Titolo pagina
        doc.setFillColor(248, 242, 250);
        doc.setDrawColor(253, 242, 0);
        doc.setLineWidth(0.5);
        doc.roundedRect(margin, currentY, maxWidth, 14, 2, 2, 'FD');
        doc.setFontSize(13);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(129, 29, 123);
        doc.text('INDICE DEL REPORT', pageWidth / 2, currentY + 10, { align: 'center' });
        currentY += 20;

        // Estrai titoli sezioni dal report
        const reportLines = currentAnalysisReport.report.split('\n');
        const sectionTitles = [];
        for (const line of reportLines) {
            const m = line.match(/^(SEZIONE \d+):\s*(.+)$/);
            if (m) sectionTitles.push({ num: m[1], title: m[2].trim() });
            if (line.match(/^CONCLUSIONE\s*$/)) sectionTitles.push({ num: 'CONCLUSIONE', title: '' });
        }

        // Voci indice con puntini leader
        const tocItems = [
            { label: 'Pagina 2', desc: 'Indice del Report' },
            { label: 'Pagina 3', desc: 'Dashboard Dati e Grafici Metrici' },
            { label: 'Pagina 4+', desc: 'Report Completo di Analisi Visagistica' },
        ];
        for (const s of sectionTitles) {
            tocItems.push({ label: '  -', desc: `${s.num}${s.title ? ': ' + s.title : ''}` });
        }

        for (const item of tocItems) {
            currentY = checkPageSpace(currentY, 10);
            const isSection = item.label.startsWith('  -');

            if (isSection) {
                doc.setFont('helvetica', 'normal');
                doc.setFontSize(8.5);
                doc.setTextColor(70, 50, 80);
                doc.text(item.desc, margin + 8, currentY);
            } else {
                // Sfondo evidenziato per voci principali
                doc.setFillColor(252, 248, 255);
                doc.setDrawColor(220, 200, 225);
                doc.setLineWidth(0.2);
                doc.roundedRect(margin, currentY - 4, maxWidth, 9, 1, 1, 'FD');

                doc.setFont('helvetica', 'bold');
                doc.setFontSize(9);
                doc.setTextColor(129, 29, 123);
                doc.text(item.label, margin + 2, currentY + 1);
                doc.setFont('helvetica', 'normal');
                doc.setTextColor(50, 40, 55);
                doc.text(item.desc, margin + 22, currentY + 1);
                currentY += 2;
            }
            currentY += LH.body;
        }

        // Box info
        currentY += 5;
        currentY = checkPageSpace(currentY, 28);
        doc.setFillColor(255, 254, 240);
        doc.setDrawColor(253, 242, 0);
        doc.setLineWidth(0.4);
        doc.roundedRect(margin, currentY, maxWidth, 22, 2, 2, 'FD');
        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(80, 60, 80);
        doc.text(`Generato il: ${new Date().toLocaleString('it-IT')}`, margin + 4, currentY + 8);
        doc.text('Modulo: face_analysis_module.py v1.2.0  |  Engine: MediaPipe FaceMesh 468 landmarks', margin + 4, currentY + 16);

        // ============================================================
        // PAGINA 3 — DASHBOARD DATI E GRAFICI
        // ============================================================
        currentY = addContentPage();

        // Titolo dashboard
        doc.setFillColor(129, 29, 123);
        doc.setDrawColor(129, 29, 123);
        doc.roundedRect(margin, currentY, maxWidth, 14, 2, 2, 'F');
        doc.setFontSize(12);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(255, 255, 255);
        doc.text('DASHBOARD DATI METRICI', pageWidth / 2, currentY + 10, { align: 'center' });
        currentY += 18;

        // --- BOX FORMA VISO ---
        doc.setFillColor(248, 242, 252);
        doc.setDrawColor(129, 29, 123);
        doc.setLineWidth(0.6);
        doc.roundedRect(margin, currentY, maxWidth * 0.42, 32, 3, 3, 'FD');

        doc.setFontSize(8);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(129, 29, 123);
        doc.text('FORMA VISO CLASSIFICATA', margin + (maxWidth * 0.42) / 2, currentY + 7, { align: 'center' });

        doc.setFontSize(18);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(80, 55, 85);
        doc.text(faceShape ? faceShape.toUpperCase() : 'N/D', margin + (maxWidth * 0.42) / 2, currentY + 22, { align: 'center' });

        // --- BOX CARATTERISTICHE QUALITATIVE ---
        const qBoxX = margin + maxWidth * 0.44;
        const qBoxW = maxWidth * 0.56;
        doc.setFillColor(255, 254, 240);
        doc.setDrawColor(200, 170, 0);
        doc.setLineWidth(0.4);
        doc.roundedRect(qBoxX, currentY, qBoxW, 32, 3, 3, 'FD');

        doc.setFontSize(7.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(150, 110, 0);
        doc.text('CARATTERISTICHE QUALITATIVE', qBoxX + qBoxW / 2, currentY + 7, { align: 'center' });

        const qualFeatures = [
            ['Occhi distanza', features.occhi_distanza || 'N/D'],
            ['Occhi dimensione', features.occhi_dimensione || 'N/D'],
            ['Zigomi', features.zigomi_prominenza || 'N/D'],
            ['Naso larghezza', features.naso_larghezza || 'N/D'],
        ];
        let qfy = currentY + 13;
        for (const [k, v] of qualFeatures) {
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(7);
            doc.setTextColor(60, 50, 60);
            doc.text(k + ':', qBoxX + 4, qfy);
            doc.setFont('helvetica', 'bold');
            doc.setTextColor(129, 29, 123);
            doc.text(v, qBoxX + qBoxW - 4, qfy, { align: 'right' });
            qfy += 5;
        }
        currentY += 38;

        // --- TABELLA METRICHE FACCIALI ---
        doc.setFontSize(8.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(60, 40, 70);
        doc.text('MISURE GEOMETRICHE RILEVATE', margin, currentY + 4);
        currentY += 8;

        const metricRows = [
            ['Larghezza Fronte', metrics.larghezza_fronte, 'px'],
            ['Larghezza Zigomi', metrics.larghezza_zigomi, 'px'],
            ['Larghezza Mascella', metrics.larghezza_mascella, 'px'],
            ['Lunghezza Viso', metrics.lunghezza_viso, 'px'],
            ['Larghezza Viso (max)', metrics.larghezza_viso, 'px'],
            ['Distanza Occhi', metrics.distanza_occhi, 'px'],
            ['Larghezza Naso', metrics.larghezza_naso, 'px'],
            ['Larghezza Bocca', metrics.larghezza_bocca, 'px'],
        ];
        const colW = maxWidth / 3;
        // Intestazione tabella
        doc.setFillColor(129, 29, 123);
        doc.rect(margin, currentY, maxWidth, 7, 'F');
        doc.setFontSize(7.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(255, 255, 255);
        doc.text('METRICA', margin + 2, currentY + 5);
        doc.text('VALORE', margin + colW * 1.5, currentY + 5, { align: 'center' });
        doc.text('STIMA ~mm*', margin + colW * 2.6, currentY + 5, { align: 'center' });
        currentY += 7;

        const mmPerPx = metrics.larghezza_viso ? (140.0 / metrics.larghezza_viso) : 0;
        for (let ri = 0; ri < metricRows.length; ri++) {
            const [lbl, val, unit] = metricRows[ri];
            const bg = ri % 2 === 0 ? [250, 246, 252] : [255, 255, 255];
            doc.setFillColor(...bg);
            doc.rect(margin, currentY, maxWidth, 6.5, 'F');
            doc.setDrawColor(210, 195, 215);
            doc.setLineWidth(0.1);
            doc.line(margin, currentY + 6.5, margin + maxWidth, currentY + 6.5);

            doc.setFont('helvetica', 'normal');
            doc.setFontSize(7.5);
            doc.setTextColor(50, 40, 55);
            doc.text(lbl, margin + 2, currentY + 4.5);

            doc.setFont('helvetica', 'bold');
            doc.setTextColor(129, 29, 123);
            const valStr = val !== undefined && val !== null ? val.toFixed(1) + ' ' + unit : 'N/D';
            doc.text(valStr, margin + colW * 1.5, currentY + 4.5, { align: 'center' });

            doc.setFont('helvetica', 'normal');
            doc.setTextColor(80, 70, 85);
            const mmStr = (val && mmPerPx) ? (val * mmPerPx).toFixed(0) + ' mm~' : '—';
            doc.text(mmStr, margin + colW * 2.6, currentY + 4.5, { align: 'center' });
            currentY += 6.5;
        }
        // Bordo tabella
        doc.setDrawColor(129, 29, 123);
        doc.setLineWidth(0.4);
        doc.rect(margin, currentY - metricRows.length * 6.5 - 7, maxWidth, metricRows.length * 6.5 + 7);
        currentY += 4;

        // Nota stima mm
        doc.setFontSize(6.5);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(120, 100, 125);
        doc.text('* Stima basata su viso adulto medio 140mm. Le misure in mm sono indicative, non calibrate.', margin, currentY);
        currentY += 8;

        // --- GRAFICI A BARRE RAPPORTI ---
        currentY = checkPageSpace(currentY, 70);
        doc.setFontSize(8.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(60, 40, 70);
        doc.text('GRAFICI RAPPORTI FACCIALI', margin, currentY + 4);
        currentY += 10;

        // Legenda grafici
        doc.setFillColor(180, 230, 180);
        doc.rect(margin, currentY, 8, 4, 'F');
        doc.setFontSize(6.5);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(60, 90, 60);
        doc.text('= zona ideale', margin + 10, currentY + 3.5);
        doc.setFillColor(129, 29, 123);
        doc.rect(margin + 38, currentY, 8, 4, 'F');
        doc.setTextColor(60, 40, 70);
        doc.text('= valore misurato', margin + 48, currentY + 3.5);
        doc.setFillColor(253, 210, 0);
        doc.circle(margin + 80, currentY + 2, 2, 'F');
        doc.text('= marker valore', margin + 85, currentY + 3.5);
        currentY += 10;

        // Larghezza label + barra
        const labelColW = 32;
        const barColW = maxWidth - labelColW - 18;

        if (metrics.rapporto_lunghezza_larghezza !== undefined) {
            currentY = checkPageSpace(currentY, 14);
            drawMetricBar(doc, margin + labelColW, currentY, barColW, 6,
                metrics.rapporto_lunghezza_larghezza, 0.9, 1.9, 1.3, 1.45,
                'Rapporto L/W', '');
            currentY += 12;
        }
        if (metrics.rapporto_mascella_fronte !== undefined) {
            currentY = checkPageSpace(currentY, 14);
            drawMetricBar(doc, margin + labelColW, currentY, barColW, 6,
                metrics.rapporto_mascella_fronte, 0.7, 1.4, 0.94, 1.06,
                'Rapporto M/F', '');
            currentY += 12;
        }
        if (metrics.prominenza_zigomi !== undefined) {
            currentY = checkPageSpace(currentY, 14);
            drawMetricBar(doc, margin + labelColW, currentY, barColW, 6,
                metrics.prominenza_zigomi, 0.7, 1.3, 0.95, 1.05,
                'Prom. Zigomi', '');
            currentY += 12;
        }
        if (metrics.distanza_occhi !== undefined && metrics.larghezza_viso) {
            const eyeRatio = metrics.distanza_occhi / metrics.larghezza_viso;
            currentY = checkPageSpace(currentY, 14);
            drawMetricBar(doc, margin + labelColW, currentY, barColW, 6,
                eyeRatio, 0.1, 0.55, 0.25, 0.36,
                'Dist. Occhi/Viso', '');
            currentY += 12;
        }

        // ============================================================
        // PAGINA 4+ — CONTENUTO DEL REPORT TESTUALE
        // ============================================================
        currentY = addContentPage();

        let inSection4 = false;
        let inBibliography = false;

        for (const [lineIdx, line] of reportLines.entries()) {
            // Gestione flag sezione 4
            if (line.match(/^SEZIONE 4:/)) {
                inSection4 = true;
            } else if (line.match(/^SEZIONE [5-9]:|^CONCLUSIONE/)) {
                inSection4 = false;
            }

            // Rileva sezione 8 (bibliografia)
            if (line.includes('BIBLIOGRAFIA E FONTI SCIENTIFICHE')) {
                inBibliography = true;
            }

            // Linee vuote
            if (line.trim().length === 0) {
                currentY += LH.empty;
                continue;
            }

            // Separatori === → linea decorativa (saltati se la riga successiva è un titolo SEZIONE)
            if (line.match(/^={3,}$/)) {
                // Guarda la prossima riga non vuota usando l'indice corretto
                const nextMeaningful = reportLines.slice(lineIdx + 1).find(l => l.trim().length > 0) || '';
                if (nextMeaningful.match(/^SEZIONE \d+:|^CONCLUSIONE/)) {
                    // Il box sezione è già un separatore visivo — salta la linea gialla
                    continue;
                }
                currentY = checkPageSpace(currentY, 4);
                doc.setDrawColor(253, 242, 0);
                doc.setLineWidth(0.5);
                doc.line(margin, currentY, pageWidth - margin, currentY);
                currentY += 3;
                continue;
            }

            // Titoli SEZIONE N:
            if (line.match(/^SEZIONE \d+:/)) {
                currentY = checkPageSpace(currentY, 20);
                currentY += 4; // spazio sopra il box

                // Box viola/giallo
                doc.setFillColor(248, 242, 254);
                doc.setDrawColor(129, 29, 123);
                doc.setLineWidth(0.6);
                doc.roundedRect(margin - 2, currentY, maxWidth + 4, 12, 1.5, 1.5, 'FD');

                doc.setFont('helvetica', 'bold');
                doc.setFontSize(10.5);
                doc.setTextColor(129, 29, 123);

                // Sezione 4: titolo + immagini
                if (line.match(/^SEZIONE 4:/) && currentAnalysisReport.debug_images) {
                    doc.text(line, margin, currentY + 8);
                    currentY += 14;

                    const debugImages = currentAnalysisReport.debug_images;
                    for (const [key, base64Data] of Object.entries(debugImages)) {
                        const imgSrc = `data:image/jpeg;base64,${base64Data}`;
                        const imageLabel = key.replace(/_/g, ' ').toUpperCase();

                        try {
                            const imgProps = doc.getImageProperties(imgSrc);
                            const aspectRatio = imgProps.width / imgProps.height;
                            const maxImgH = 100;
                            let finalW = maxWidth;
                            let finalH = finalW / aspectRatio;
                            if (finalH > maxImgH) { finalH = maxImgH; finalW = finalH * aspectRatio; }
                            const imgX = margin + (maxWidth - finalW) / 2;

                            // Controlla spazio per label + immagine + didascalia
                            const caption = getImageCaption(key, currentAnalysisReport);
                            const capLines = doc.splitTextToSize(caption, maxWidth - 6);
                            const capH = capLines.length * 5 + 10;
                            const totalBlockH = 12 + finalH + 4 + capH + 8;

                            currentY = checkPageSpace(currentY, totalBlockH);

                            // Label header
                            doc.setFillColor(129, 29, 123);
                            doc.roundedRect(margin, currentY, maxWidth, 10, 1, 1, 'F');
                            doc.setFont('helvetica', 'bold');
                            doc.setFontSize(8.5);
                            doc.setTextColor(255, 255, 255);
                            doc.text(imageLabel, pageWidth / 2, currentY + 7, { align: 'center' });
                            currentY += 12;

                            // Bordo immagine
                            doc.setDrawColor(180, 160, 185);
                            doc.setLineWidth(0.4);
                            doc.rect(imgX - 0.5, currentY - 0.5, finalW + 1, finalH + 1);

                            doc.addImage(imgSrc, 'JPEG', imgX, currentY, finalW, finalH);
                            currentY += finalH + 4;

                            // Didascalia
                            doc.setFillColor(250, 247, 253);
                            doc.setDrawColor(200, 185, 210);
                            doc.setLineWidth(0.2);
                            doc.roundedRect(margin, currentY, maxWidth, capH, 1, 1, 'FD');
                            doc.setFont('helvetica', 'italic');
                            doc.setFontSize(7.5);
                            doc.setTextColor(75, 55, 85);
                            let capY = currentY + 6;
                            for (const capLine of capLines) {
                                doc.text(capLine, margin + 3, capY);
                                capY += 5;
                            }
                            currentY = capY + 4;

                        } catch (err) {
                            console.error(`Errore immagine ${key}:`, err);
                            currentY = checkPageSpace(currentY, 10);
                            doc.setFont('helvetica', 'normal');
                            doc.setFontSize(8);
                            doc.setTextColor(150, 50, 50);
                            doc.text(`[Immagine non disponibile: ${imageLabel}]`, margin, currentY);
                            currentY += 10;
                        }
                    }
                    continue;
                } else {
                    // Titolo sezione normale
                    doc.text(line, margin, currentY + 8);
                    currentY += LH.section;
                }
                continue;
            }

            // Salta testo sezione 4 (già sostituito con immagini)
            if (inSection4) continue;

            // Sottotitoli numerati (1. 2. ecc.)
            if (line.match(/^\s*\d+\.\s/)) {
                currentY = checkPageSpace(currentY, LH.subsection + 4);
                currentY += 2;
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(9);
                doc.setTextColor(80, 55, 85);
                const wl = doc.splitTextToSize(line, maxWidth);
                for (const wline of wl) {
                    currentY = checkPageSpace(currentY, LH.subsection);
                    doc.text(wline, margin, currentY);
                    currentY += LH.subsection;
                }
                continue;
            }

            // Sottosezioni in MAIUSCOLO (ARCO, SPESSORE, LUNGHEZZA, ecc.)
            if (line.match(/^\s{2,}[A-ZÀÈÌÒÙÉ]{4}/) && !line.match(/^SEZIONE/)) {
                currentY = checkPageSpace(currentY, LH.subsection + 2);
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(8.5);
                doc.setTextColor(129, 29, 123);
                const wl = doc.splitTextToSize(line, maxWidth);
                for (const wline of wl) {
                    currentY = checkPageSpace(currentY, LH.subsection);
                    doc.text(wline, margin, currentY);
                    currentY += LH.subsection;
                }
                continue;
            }

            // CONCLUSIONE (titolo speciale)
            if (line.match(/^CONCLUSIONE\s*$/)) {
                currentY = checkPageSpace(currentY, 20);
                currentY += 3;
                doc.setFillColor(129, 29, 123);
                doc.roundedRect(margin - 2, currentY - 2, maxWidth + 4, 12, 1.5, 1.5, 'F');
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(11);
                doc.setTextColor(255, 255, 255);
                doc.text('CONCLUSIONE', margin, currentY + 8);
                currentY += LH.section + 2;
                continue;
            }

            // Fine report
            if (line.match(/^FINE REPORT\s*$/)) continue;

            // Testo bibliografia
            if (inBibliography) {
                doc.setFont('helvetica', 'normal');
                doc.setFontSize(7.5);
                doc.setTextColor(70, 60, 75);
                const wl = doc.splitTextToSize(line, maxWidth);
                for (const wline of wl) {
                    currentY = checkPageSpace(currentY, LH.biblio);
                    doc.text(wline, margin, currentY);
                    currentY += LH.biblio;
                }
                continue;
            }

            // Testo normale
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(8.5);
            doc.setTextColor(45, 35, 50);
            const wrappedLines = doc.splitTextToSize(line, maxWidth);
            for (const wline of wrappedLines) {
                currentY = checkPageSpace(currentY, LH.body);
                doc.text(wline, margin, currentY);
                currentY += LH.body;
            }
        }

        // ============================================================
        // FOOTER + WATERMARK SU OGNI PAGINA (eccetto copertina)
        // ============================================================
        const pageCount = doc.internal.getNumberOfPages();
        for (let i = 2; i <= pageCount; i++) {
            doc.setPage(i);

            // Watermark leggerissimo
            doc.setFontSize(38);
            doc.setFont('helvetica', 'bold');
            doc.setTextColor(250, 247, 252);
            doc.text('KIMERIKA', pageWidth / 2, pageHeight / 2, { align: 'center', angle: 45 });

            // Linea footer
            doc.setDrawColor(253, 242, 0);
            doc.setLineWidth(0.3);
            doc.line(margin, pageHeight - 16, pageWidth - margin, pageHeight - 16);

            // Logo mini a sinistra
            addLogo(margin, pageHeight - 10, 22);

            // Numero pagina al centro
            doc.setFontSize(7);
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(100, 80, 110);
            doc.text(`Pagina ${i} di ${pageCount}`, pageWidth / 2, pageHeight - 9, { align: 'center' });

            // Confidenziale a destra
            doc.setFontSize(6.5);
            doc.setFont('helvetica', 'italic');
            doc.setTextColor(130, 110, 135);
            doc.text('Confidenziale', pageWidth - margin, pageHeight - 9, { align: 'right' });
        }

        // Salva
        const filename = `Analisi_Visagistica_${new Date().toISOString().slice(0, 10)}.pdf`;
        doc.save(filename);
        showToast('PDF professionale generato con successo', 'success');

    } catch (error) {
        console.error('❌ Errore generazione PDF:', error);
        showToast(`Errore generazione PDF: ${error.message}`, 'error');
    }
}

/**
 * Toggle lettura vocale del report
 */
function toggleReportReading() {
    if (isReadingReport) {
        stopReportReading();
    } else {
        startReportReading();
    }
}

/**
 * Avvia il processo di lettura vocale interattiva
 * INTEGRATO CON IL SISTEMA WAKE-WORD "KIMERIKA"
 */
async function startReportReading() {
    if (!currentAnalysisReport || !reportSections || Object.keys(reportSections).length === 0) {
        showToast('⚠️ Nessun report disponibile', 'warning');
        return;
    }

    // Verifica che voiceAssistant sia disponibile
    if (typeof voiceAssistant === 'undefined') {
        showToast('⚠️ Assistente vocale Isabella non disponibile', 'warning');
        console.error('voiceAssistant non definito');
        return;
    }

    try {
        isReadingReport = true;
        awaitingSectionSelection = true;
        updateReadButton(true);

        // Isabella fornisce istruzioni per l'uso con wake-word
        await provideReadingInstructions();

    } catch (error) {
        console.error('❌ Errore avvio lettura Isabella:', error);
        isReadingReport = false;
        awaitingSectionSelection = false;
        updateReadButton(false);
        showToast(`Errore lettura vocale: ${error.message}`, 'error');
    }
}

/**
 * Fornisce istruzioni per l'uso del report con wake-word
 */
async function provideReadingInstructions() {
    // Crea lista delle sezioni (esclude sezione 4 che è già filtrata)
    const sectionsList = Object.entries(reportSections)
        .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))  // Ordina per numero
        .map(([num, data]) => `Sezione ${num}, ${data.title}`)
        .join('. ');

    const instructions = `Report di analisi pronto. Per ascoltarlo, di' prima la parola Kimerika,
        poi scegli cosa vuoi ascoltare. Puoi dire: ${sectionsList}.
        Oppure di' Kimerika tutte, per ascoltare l'intero report.
        Per fermare la lettura, di' Kimerika ferma.`;

    await voiceAssistant.speak(instructions);
    console.log('🎤 Isabella ha fornito le istruzioni. In attesa di comando wake-word...');
    showToast('🎤 Di\' "Kimerika" seguito dalla sezione che vuoi ascoltare', 'info');
}

/**
 * Legge una sezione specifica o tutto il report
 * NOTA: La sezione 4 (immagini) viene automaticamente esclusa
 */
async function readReportSection(sectionNumber = null) {
    try {
        isReadingReport = true;
        awaitingSectionSelection = false;
        updateReadButton(true);

        let textToRead = '';

        if (sectionNumber === null || sectionNumber === 'tutte') {
            // Leggi tutto il report (esclusa sezione 4)
            console.log('📖 Lettura completa del report (esclusa sezione 4 - immagini)...');

            // Ordina le sezioni per numero
            const sortedSections = Object.entries(reportSections).sort((a, b) => parseInt(a[0]) - parseInt(b[0]));

            for (const [num, data] of sortedSections) {
                textToRead += `Sezione ${num}. ${data.title}. ${data.content} `;
            }
        } else {
            // Verifica che non sia la sezione 4
            if (sectionNumber === '4') {
                await voiceAssistant.speak('La sezione 4 contiene solo immagini e non può essere letta. Scegli un\'altra sezione.');
                isReadingReport = false;
                awaitingSectionSelection = true;
                updateReadButton(false);
                return;
            }

            // Leggi solo la sezione specificata
            const section = reportSections[sectionNumber];

            if (section) {
                console.log(`📖 Lettura sezione ${sectionNumber}: ${section.title}`);
                textToRead = `Sezione ${sectionNumber}. ${section.title}. ${section.content}`;
            } else {
                await voiceAssistant.speak(`Sezione ${sectionNumber} non trovata o non disponibile per la lettura. Riprova.`);
                isReadingReport = false;
                updateReadButton(false);
                return;
            }
        }

        // Isabella legge il contenuto
        await voiceAssistant.speak(textToRead);

        console.log('🔊 Lettura completata');
        showToast('✅ Lettura completata', 'success');

        // Reset stati
        isReadingReport = false;
        updateReadButton(false);

    } catch (error) {
        console.error('❌ Errore durante la lettura:', error);
        isReadingReport = false;
        updateReadButton(false);
        showToast(`Errore durante la lettura: ${error.message}`, 'error');
    }
}

/**
 * Ferma la lettura vocale di Isabella
 */
function stopReportReading() {
    if (typeof voiceAssistant !== 'undefined' && voiceAssistant.audioPlayer) {
        // Ferma l'audio player di Isabella
        voiceAssistant.audioPlayer.pause();
        voiceAssistant.audioPlayer.currentTime = 0;
    }

    isReadingReport = false;
    awaitingSectionSelection = false;
    updateReadButton(false);
    console.log('🔊 Lettura report fermata');
    showToast('🔇 Lettura fermata', 'info');
}

/**
 * Aggiorna il pulsante di lettura
 */
function updateReadButton(isReading) {
    const btn = document.getElementById('read-report-btn');
    if (btn) {
        if (isReading) {
            btn.textContent = '🔇 Ferma Lettura';
            btn.classList.remove('btn-info');
            btn.classList.add('btn-warning');
        } else {
            btn.textContent = '🔊 Leggi Report';
            btn.classList.remove('btn-warning');
            btn.classList.add('btn-info');
        }
    }
}

// ========================================
// FUNZIONALITÀ DRAGGABLE (POPUP TRASCINABILE)
// ========================================

let isDragging = false;
let currentX;
let currentY;
let initialX;
let initialY;
let xOffset = 0;
let yOffset = 0;

/**
 * Inizializza il popup come draggable
 */
function initDraggableModal() {
    const modal = document.getElementById('analysis-modal');
    const modalContent = modal?.querySelector('.modal-content');
    const modalHeader = modal?.querySelector('.modal-header');

    if (!modal || !modalContent || !modalHeader) {
        console.warn('⚠️ Elementi modal non trovati per inizializzare draggable');
        return;
    }

    // Rende il header draggable (cursore move)
    modalHeader.style.cursor = 'move';
    modalHeader.style.userSelect = 'none';

    // Eventi mouse
    modalHeader.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);

    // Eventi touch per mobile
    modalHeader.addEventListener('touchstart', dragStart);
    document.addEventListener('touchmove', drag);
    document.addEventListener('touchend', dragEnd);

    console.log('✅ Modal reso draggable');
}

function dragStart(e) {
    const modal = document.getElementById('analysis-modal');
    const modalContent = modal?.querySelector('.modal-content');

    if (!modalContent) return;

    if (e.type === 'touchstart') {
        initialX = e.touches[0].clientX - xOffset;
        initialY = e.touches[0].clientY - yOffset;
    } else {
        initialX = e.clientX - xOffset;
        initialY = e.clientY - yOffset;
    }

    // Solo se clicchiamo sull'header
    if (e.target.closest('.modal-header')) {
        isDragging = true;
        modalContent.style.transition = 'none'; // Disabilita transizioni durante il drag
    }
}

function drag(e) {
    if (!isDragging) return;

    e.preventDefault();

    const modal = document.getElementById('analysis-modal');
    const modalContent = modal?.querySelector('.modal-content');

    if (!modalContent) return;

    if (e.type === 'touchmove') {
        currentX = e.touches[0].clientX - initialX;
        currentY = e.touches[0].clientY - initialY;
    } else {
        currentX = e.clientX - initialX;
        currentY = e.clientY - initialY;
    }

    xOffset = currentX;
    yOffset = currentY;

    setTranslate(currentX, currentY, modalContent);
}

function dragEnd(e) {
    if (!isDragging) return;

    const modal = document.getElementById('analysis-modal');
    const modalContent = modal?.querySelector('.modal-content');

    if (modalContent) {
        modalContent.style.transition = ''; // Re-abilita transizioni
    }

    initialX = currentX;
    initialY = currentY;

    isDragging = false;
}

function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate(${xPos}px, ${yPos}px)`;
}

/**
 * Reset posizione del modal al centro
 */
function resetModalPosition() {
    const modal = document.getElementById('analysis-modal');
    const modalContent = modal?.querySelector('.modal-content');

    if (modalContent) {
        xOffset = 0;
        yOffset = 0;
        currentX = 0;
        currentY = 0;
        initialX = 0;
        initialY = 0;
        modalContent.style.transform = 'translate(0px, 0px)';
    }
}

// ========================================
// VISUALIZZAZIONE FULLSCREEN IMMAGINI
// ========================================

/**
 * Apre un'immagine in modalità fullscreen
 */
function openImageFullscreen(imageSrc, imageTitle) {
    // Crea overlay fullscreen
    const overlay = document.createElement('div');
    overlay.id = 'fullscreen-image-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.95);
        z-index: 10000;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        cursor: zoom-out;
    `;

    // Immagine fullscreen
    const img = document.createElement('img');
    img.src = imageSrc;
    img.alt = imageTitle;
    img.style.cssText = `
        max-width: 90vw;
        max-height: 85vh;
        object-fit: contain;
        box-shadow: 0 0 50px rgba(255, 255, 255, 0.3);
    `;

    // Titolo immagine
    const title = document.createElement('div');
    title.textContent = imageTitle.replace(/_/g, ' ').toUpperCase();
    title.style.cssText = `
        color: white;
        font-size: 18px;
        margin-top: 20px;
        padding: 10px 20px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 5px;
    `;

    // Pulsante chiudi
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✖';
    closeBtn.style.cssText = `
        position: absolute;
        top: 20px;
        right: 20px;
        background: rgba(255, 255, 255, 0.2);
        color: white;
        border: none;
        font-size: 30px;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        cursor: pointer;
        transition: background 0.3s;
    `;

    closeBtn.addEventListener('mouseenter', () => {
        closeBtn.style.background = 'rgba(255, 255, 255, 0.3)';
    });

    closeBtn.addEventListener('mouseleave', () => {
        closeBtn.style.background = 'rgba(255, 255, 255, 0.2)';
    });

    // Funzione di chiusura
    const closeFullscreen = () => {
        document.body.removeChild(overlay);
    };

    closeBtn.addEventListener('click', closeFullscreen);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeFullscreen();
        }
    });

    // Tasto ESC per chiudere
    const escHandler = (e) => {
        if (e.key === 'Escape') {
            closeFullscreen();
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);

    // Assembla e mostra
    overlay.appendChild(closeBtn);
    overlay.appendChild(img);
    overlay.appendChild(title);
    document.body.appendChild(overlay);

    console.log('🖼️ Immagine aperta in fullscreen:', imageTitle);
}

// ========================================
// COMANDI VOCALI PER CONTROLLO REPORT
// ========================================

/**
 * Gestione comandi vocali personalizzati per il report
 */
function setupReportVoiceCommands() {
    // Estendi la mappa dei comandi vocali dell'assistente
    if (typeof window.voiceCommandHandlers === 'undefined') {
        window.voiceCommandHandlers = {};
    }

    // Comando: "Leggi report" (per avviare il processo)
    window.voiceCommandHandlers['leggi report'] = async function () {
        console.log('🎤 Comando vocale riconosciuto: Leggi report');

        if (!currentAnalysisReport) {
            await voiceAssistant.speak('Non c\'è nessun report di analisi disponibile.');
            return;
        }

        // Avvia il processo di lettura interattiva
        await startReportReading();
    };

    // Comando: "Ferma" (con wake-word integrata)
    window.voiceCommandHandlers['ferma'] = function () {
        console.log('🎤 Comando vocale riconosciuto: Ferma lettura report');
        if (isReadingReport || awaitingSectionSelection) {
            stopReportReading();
        }
    };

    // Comando: "Tutte" (leggi tutte le sezioni - richiede wake-word)
    window.voiceCommandHandlers['tutte'] = async function () {
        if (awaitingSectionSelection) {
            console.log('🎤 Comando vocale: Leggi tutte le sezioni del report');
            await readReportSection('tutte');
        }
    };

    // Comandi per sezioni numeriche (1-8, esclusa 4) - richiedono wake-word
    for (let i = 1; i <= 8; i++) {
        if (i === 4) continue; // Salta sezione 4 (immagini)

        // Aggiungi comando "sezione N"
        window.voiceCommandHandlers[`sezione ${i}`] = async function () {
            if (awaitingSectionSelection) {
                console.log(`🎤 Comando vocale: Leggi sezione ${i} del report`);
                await readReportSection(i.toString());
            }
        };

        // Aggiungi anche supporto per "numero N" (es. "kimerika uno", "kimerika due")
        const numeriItaliani = ['uno', 'due', 'tre', 'cinque', 'sei', 'sette', 'otto'];
        if (i !== 4 && i <= numeriItaliani.length) {
            window.voiceCommandHandlers[numeriItaliani[i - 1]] = async function () {
                if (awaitingSectionSelection) {
                    console.log(`🎤 Comando vocale: Leggi sezione ${i} (numero italiano)`);
                    await readReportSection(i.toString());
                }
            };
        }
    }

    console.log('✅ Comandi vocali per report configurati');
}

/**
 * Processa comandi vocali catturati dal riconoscimento
 */
async function processReportVoiceCommand(transcript) {
    const command = transcript.toLowerCase().trim();

    // IMPORTANTE: Escludi comandi che contengono "webcam" o "camera" per evitare conflitti
    if (command.includes('webcam') || command.includes('camera')) {
        console.log(`⚠️ Comando "${command}" contiene webcam/camera - skip report processing`);
        return false;
    }

    // Cerca match nei comandi disponibili
    for (const [keyword, handler] of Object.entries(window.voiceCommandHandlers || {})) {
        if (command.includes(keyword)) {
            console.log(`🎯 Comando report riconosciuto: "${keyword}" da "${command}"`);
            await handler();
            return true;
        }
    }

    return false;
}

// Rendi la funzione disponibile globalmente
window.processReportVoiceCommand = processReportVoiceCommand;

// Inizializza draggable quando il DOM è pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initDraggableModal();
        setupReportVoiceCommands();
    });
} else {
    initDraggableModal();
    setupReportVoiceCommands();
}

// Chiudi il modal quando si clicca fuori (solo sul background, non sul contenuto)
window.addEventListener('click', (event) => {
    const modal = document.getElementById('analysis-modal');
    if (event.target === modal) {
        closeAnalysisModal();
    }
});

console.log('✅ face-analysis-complete.js caricato');
