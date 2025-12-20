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
 * Genera PDF del report con bibliografia, formattazione scientifica e immagini incorporate
 */
async function generateAnalysisPDF() {
    if (!currentAnalysisReport) {
        showToast('⚠️ Nessun report disponibile', 'warning');
        return;
    }

    try {
        // Carica il logo Kimerika
        const logoImg = await loadKimerikaLogo();

        // Usa jsPDF
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({
            orientation: 'portrait',
            unit: 'mm',
            format: 'a4'
        });

        // Configurazione
        const pageWidth = doc.internal.pageSize.getWidth();
        const pageHeight = doc.internal.pageSize.getHeight();
        const margin = 15;
        const lineHeight = 6;
        const maxWidth = pageWidth - (margin * 2);

        let currentY = margin;
        let inSection4 = false; // Flag per rilevare la sezione 4 (immagini)

        // === PAGINA DI COPERTINA PROFESSIONALE ===
        // Palette: #811d7b (viola), #fdf200 (giallo), #5f5f5f (grigio)

        // Sfondo decorativo leggerissimo (senza alpha - non supportato da jsPDF)
        doc.setFillColor(255, 252, 230); // Giallo chiarissimo
        doc.rect(0, 0, pageWidth, pageHeight / 3, 'F');
        doc.setFillColor(248, 240, 247); // Viola chiarissimo
        doc.rect(0, pageHeight / 3, pageWidth, pageHeight / 3, 'F');

        // Bordo decorativo elegante
        doc.setDrawColor(129, 29, 123); // #811d7b
        doc.setLineWidth(1.5);
        doc.rect(10, 10, pageWidth - 20, pageHeight - 20);
        doc.setLineWidth(0.5);
        doc.rect(12, 12, pageWidth - 24, pageHeight - 24);

        // Logo KIMERIKA (immagine o testo come fallback)
        const logoY = 50;
        if (logoImg) {
            try {
                // Calcola dimensioni mantenendo le proporzioni ORIGINALI
                const imgProps = doc.getImageProperties(logoImg);
                const aspectRatio = imgProps.width / imgProps.height;

                // Larghezza massima 70mm, altezza calcolata per mantenere proporzioni
                const maxLogoWidth = 70;
                const logoWidth = maxLogoWidth;
                const logoHeight = logoWidth / aspectRatio;
                const logoX = (pageWidth - logoWidth) / 2;

                doc.addImage(logoImg, 'PNG', logoX, logoY - logoHeight/2, logoWidth, logoHeight);
                console.log(`✅ Logo aggiunto con proporzioni originali: ${logoWidth}x${logoHeight}mm (ratio: ${aspectRatio.toFixed(2)})`);
            } catch (error) {
                console.error('Errore aggiunta logo:', error);
                // Fallback a testo
                doc.setFontSize(28);
                doc.setFont('helvetica', 'bold');
                doc.setTextColor(60, 100, 180);
                doc.text('KIMERIKA', pageWidth / 2, logoY, { align: 'center' });
            }
        } else {
            // Fallback: Logo testuale
            doc.setDrawColor(100, 150, 200);
            doc.setLineWidth(2);
            doc.rect(pageWidth/2 - 40, logoY - 15, 80, 25);

            doc.setFontSize(28);
            doc.setFont('helvetica', 'bold');
            doc.setTextColor(60, 100, 180);
            doc.text('KIMERIKA', pageWidth / 2, logoY, { align: 'center' });
        }

        // Sottotitolo logo
        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 100, 100);
        doc.text('Facial Analysis & Visagism', pageWidth / 2, logoY + 20, { align: 'center' });

        // Linea divisoria decorativa
        doc.setDrawColor(253, 242, 0); // #fdf200
        doc.setLineWidth(0.8);
        doc.line(pageWidth / 2 - 60, logoY + 30, pageWidth / 2 + 60, logoY + 30);

        // Titolo principale
        doc.setFontSize(28);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(95, 95, 95); // #5f5f5f
        doc.text('ANALISI VISAGISTICA', pageWidth / 2, pageHeight / 2 - 10, { align: 'center' });

        doc.setFontSize(24);
        doc.setTextColor(129, 29, 123); // #811d7b
        doc.text('COMPLETA', pageWidth / 2, pageHeight / 2 + 8, { align: 'center' });

        // Sottotitolo
        doc.setFontSize(13);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(80, 80, 80);
        doc.text('Report Scientifico Professionale Personalizzato', pageWidth / 2, pageHeight / 2 + 25, { align: 'center' });

        // Data con icona
        doc.setFontSize(11);
        doc.setTextColor(100, 100, 100);
        const dataText = `📅 ${new Date().toLocaleDateString('it-IT', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        })}`;
        doc.text(dataText, pageWidth / 2, pageHeight / 2 + 40, { align: 'center' });

        // Box informativo in basso
        const boxY = pageHeight - 60;
        doc.setFillColor(250, 245, 249); // Viola chiarissimo
        doc.setDrawColor(253, 242, 0); // #fdf200
        doc.roundedRect(30, boxY, pageWidth - 60, 35, 3, 3, 'FD');

        doc.setFontSize(9);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(95, 95, 95); // #5f5f5f
        doc.text('Analisi basata su evidenze scientifiche peer-reviewed', pageWidth / 2, boxY + 12, { align: 'center' });
        doc.text('Metodologie di visagismo professionale e neuroscienze', pageWidth / 2, boxY + 22, { align: 'center' });

        // Footer con copyright
        doc.setFontSize(8);
        doc.setTextColor(120, 120, 120);
        doc.text('© 2025 Kimerika - Facial Analysis System', pageWidth / 2, pageHeight - 10, { align: 'center' });

        // Nuova pagina per il contenuto
        doc.addPage();
        currentY = margin;

        // === INTESTAZIONE PROFESSIONALE ===
        // Box header colorato
        doc.setFillColor(129, 29, 123); // #811d7b
        doc.rect(0, 0, pageWidth, 25, 'F');

        doc.setFontSize(18);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(255, 255, 255);
        doc.text('REPORT DI ANALISI VISAGISTICA', margin, 16);

        // Ripristina colore testo
        doc.setTextColor(95, 95, 95); // #5f5f5f
        currentY = 35;

        // Box informazioni con bordo
        doc.setDrawColor(253, 242, 0); // #fdf200
        doc.setLineWidth(0.5);
        doc.setFillColor(255, 254, 240); // Giallo chiarissimo
        doc.roundedRect(margin, currentY, maxWidth, 22, 2, 2, 'FD');

        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(95, 95, 95); // #5f5f5f
        doc.text(`📅 Generato il: ${new Date().toLocaleString('it-IT')}`, margin + 5, currentY + 8);
        doc.text(`⚙️ Modulo: face_analysis_module.py v1.2.0`, margin + 5, currentY + 16);

        currentY += 30;
        doc.setTextColor(50, 50, 50); // Grigio scuro leggibile

        // === CONTENUTO DEL REPORT ===
        doc.setFontSize(8.5);
        doc.setFont('courier', 'normal');

        const reportLines = currentAnalysisReport.report.split('\n');
        let inBibliography = false;

        for (let line of reportLines) {
            // Rileva inizio/fine sezione 4 (immagini)
            if (line.match(/^SEZIONE 4:/)) {
                inSection4 = true;
            } else if (line.match(/^SEZIONE [5-8]:/)) {
                inSection4 = false;
            }

            // Rileva inizio bibliografia
            if (line.includes('BIBLIOGRAFIA E FONTI SCIENTIFICHE')) {
                inBibliography = true;
            }

            // Controlla se serve una nuova pagina
            if (currentY > pageHeight - margin - 15) {
                doc.addPage();
                currentY = 20; // Margine per header
            }

            // Linee vuote
            if (line.trim().length === 0) {
                currentY += lineHeight / 2;
                continue;
            }

            // Formattazione speciale per titoli sezioni (linee con ===)
            if (line.includes('===')) {
                // Linea divisoria decorativa invece di ===
                doc.setDrawColor(253, 242, 0); // #fdf200
                doc.setLineWidth(0.8);
                doc.line(margin, currentY, pageWidth - margin, currentY);
                currentY += lineHeight / 2;
                continue;
            }
            // Titoli sezioni (SEZIONE N:) con box colorato
            else if (line.match(/^SEZIONE \d+:/)) {
                // Verifica spazio per box sezione
                if (currentY > pageHeight - margin - 30) {
                    doc.addPage();
                    currentY = 20; // Margine per header
                }

                // Spazio prima della sezione
                currentY += 3;

                // Box colorato per sezione (colore molto chiaro)
                doc.setFillColor(252, 248, 251); // Viola leggerissimo
                doc.setDrawColor(253, 242, 0); // #fdf200
                doc.setLineWidth(0.5);
                doc.roundedRect(margin - 2, currentY - 2, maxWidth + 4, 13, 1, 1, 'FD');

                doc.setFont('helvetica', 'bold');
                doc.setFontSize(11);
                doc.setTextColor(129, 29, 123); // #811d7b
                currentY += 5;

                // Se è la sezione 4, aggiungi le immagini dopo il titolo
                if (line.match(/^SEZIONE 4:/) && currentAnalysisReport.debug_images) {
                    // Scrivi il titolo
                    const wrappedTitle = doc.splitTextToSize(line, maxWidth);
                    for (let wrappedLine of wrappedTitle) {
                        if (currentY > pageHeight - margin - 15) {
                            doc.addPage();
                            currentY = 20; // Margine per header
                        }
                        doc.text(wrappedLine, margin, currentY);
                        currentY += lineHeight;
                    }

                    // Aggiungi le immagini
                    currentY += 8; // Spazio prima delle immagini
                    const debugImages = currentAnalysisReport.debug_images;
                    const imageKeys = Object.keys(debugImages);

                    for (let i = 0; i < imageKeys.length; i++) {
                        const key = imageKeys[i];
                        const base64Data = debugImages[key];
                        const imgSrc = `data:image/jpeg;base64,${base64Data}`;

                        // Box per etichetta immagine
                        const imageLabel = key.replace(/_/g, ' ').toUpperCase();

                        // Verifica spazio per etichetta e immagine
                        if (currentY + 20 > pageHeight - margin) {
                            doc.addPage();
                            currentY = 20; // Margine per header
                        }

                        // Box etichetta professionale
                        doc.setFillColor(255, 253, 235); // Giallo chiarissimo
                        doc.setDrawColor(129, 29, 123); // #811d7b
                        doc.setLineWidth(0.3);
                        const labelWidth = maxWidth;
                        doc.roundedRect(margin, currentY, labelWidth, 10, 1, 1, 'FD');

                        doc.setFont('helvetica', 'bold');
                        doc.setFontSize(9);
                        doc.setTextColor(129, 29, 123); // #811d7b

                        // Aggiungi immagine con calcolo automatico aspect ratio
                        try {
                            // Ottieni dimensioni originali
                            const imgProps = doc.getImageProperties(imgSrc);
                            const imgWidth = imgProps.width;
                            const imgHeight = imgProps.height;
                            const aspectRatio = imgWidth / imgHeight;

                            // Calcola dimensioni finali mantenendo aspect ratio
                            const maxImgWidth = maxWidth;
                            const maxImgHeight = 120; // mm - limite massimo altezza

                            let finalWidth = maxImgWidth;
                            let finalHeight = maxImgWidth / aspectRatio;

                            // Se l'altezza supera il massimo, ridimensiona in base all'altezza
                            if (finalHeight > maxImgHeight) {
                                finalHeight = maxImgHeight;
                                finalWidth = maxImgHeight * aspectRatio;
                            }

                            // Centra l'immagine se è più stretta della larghezza massima
                            const imgX = margin + (maxImgWidth - finalWidth) / 2;

                            // Verifica se c'è spazio per etichetta + immagine, altrimenti nuova pagina
                            const totalHeight = 12 + finalHeight + 5; // etichetta + immagine + margine
                            if (currentY + totalHeight > pageHeight - margin - 25) {
                                doc.addPage();
                                currentY = 22; // Margine per header + spazio

                                // Ridisegna l'etichetta sulla nuova pagina
                                doc.setFillColor(255, 253, 235);
                                doc.setDrawColor(129, 29, 123);
                                doc.setLineWidth(0.3);
                                doc.roundedRect(margin, currentY, labelWidth, 10, 1, 1, 'FD');
                            }

                            // Scrivi label centrata
                            doc.setFont('helvetica', 'bold');
                            doc.setFontSize(9);
                            doc.setTextColor(129, 29, 123);
                            doc.text(imageLabel, margin + labelWidth / 2, currentY + 7, { align: 'center' });
                            currentY += 12;

                            // Aggiungi immagine con bordo decorativo
                            doc.setDrawColor(95, 95, 95); // #5f5f5f
                            doc.setLineWidth(0.5);
                            doc.rect(imgX - 1, currentY - 1, finalWidth + 2, finalHeight + 2);

                            doc.addImage(imgSrc, 'JPEG', imgX, currentY, finalWidth, finalHeight);
                            currentY += finalHeight + 10;

                            console.log(`✅ Immagine ${imageLabel} aggiunta: ${finalWidth.toFixed(1)}mm x ${finalHeight.toFixed(1)}mm (ratio: ${aspectRatio.toFixed(2)})`);

                        } catch (error) {
                            console.error(`Errore aggiunta immagine ${key}:`, error);

                            // Verifica se c'è spazio per il messaggio di errore
                            if (currentY + 20 > pageHeight - margin) {
                                doc.addPage();
                                currentY = 20; // Margine per header
                            }

                            doc.setFont('courier', 'normal');
                            doc.setFontSize(8);
                            doc.setTextColor(150, 50, 50);
                            doc.text(`[Errore caricamento immagine: ${imageLabel}]`, margin, currentY);
                            currentY += 12;
                        }
                    }

                    // Salta al prossimo ciclo per non riscrivere il titolo
                    continue;
                }
            }
            // Sottotitoli
            else if (line.match(/^\d+\./)) {
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(9.5);
                doc.setTextColor(95, 95, 95);
                currentY += 3; // Più spazio prima dei sottotitoli
            }
            // Bibliografia - font più piccolo
            else if (inBibliography) {
                doc.setFont('courier', 'normal');
                doc.setFontSize(7.5);
                doc.setTextColor(70, 70, 70);
            }
            // Testo normale
            else {
                doc.setFont('courier', 'normal');
                doc.setFontSize(8.5);
                doc.setTextColor(50, 50, 50);
            }

            // Salta il contenuto testuale della sezione 4 (già sostituito con immagini)
            if (inSection4) {
                continue;
            }

            // Split linee lunghe
            const wrappedLines = doc.splitTextToSize(line, maxWidth);

            for (let wrappedLine of wrappedLines) {
                // Controlla spazio disponibile
                if (currentY > pageHeight - margin - 20) {
                    doc.addPage();
                    currentY = 20; // Margine superiore per evitare sovrapposizione con header
                }

                doc.text(wrappedLine, margin, currentY);
                currentY += lineHeight;
            }
        }

        // === HEADER E FOOTER PROFESSIONALE SU OGNI PAGINA ===
        const pageCount = doc.internal.getNumberOfPages();
        for (let i = 1; i <= pageCount; i++) {
            doc.setPage(i);

            if (i === 2) {
                // Pagina 2 ha già il suo header custom, skippa
            } else if (i > 2) {
                // Header minimale sulle pagine successive alla seconda
                doc.setDrawColor(253, 242, 0); // #fdf200
                doc.setLineWidth(0.3);
                doc.line(margin, 12, pageWidth - margin, 12);

                doc.setFontSize(8);
                doc.setFont('helvetica', 'normal');
                doc.setTextColor(129, 29, 123);
                doc.text('KIMERIKA - Analisi Visagistica', margin, 9);
            }

            if (i > 1) { // Non sulla copertina
                // Linea divisoria footer
                doc.setDrawColor(253, 242, 0); // #fdf200
                doc.setLineWidth(0.3);
                doc.line(margin, pageHeight - 18, pageWidth - margin, pageHeight - 18);

                // Logo piccolo a sinistra (immagine o testo)
                if (logoImg) {
                    try {
                        // Calcola proporzioni originali per logo mini
                        const imgProps = doc.getImageProperties(logoImg);
                        const aspectRatio = imgProps.width / imgProps.height;

                        const miniLogoWidth = 25;
                        const miniLogoHeight = miniLogoWidth / aspectRatio;
                        doc.addImage(logoImg, 'PNG', margin, pageHeight - 16, miniLogoWidth, miniLogoHeight);
                    } catch (error) {
                        // Fallback a testo
                        doc.setFontSize(8);
                        doc.setFont('helvetica', 'bold');
                        doc.setTextColor(60, 100, 180);
                        doc.text('KIMERIKA', margin, pageHeight - 10);
                    }
                } else {
                    doc.setFontSize(8);
                    doc.setFont('helvetica', 'bold');
                    doc.setTextColor(60, 100, 180);
                    doc.text('KIMERIKA', margin, pageHeight - 10);
                }

                // Numero pagina al centro
                doc.setFontSize(7);
                doc.setFont('helvetica', 'normal');
                doc.setTextColor(100, 100, 100);
                doc.text(
                    `Pagina ${i} di ${pageCount}`,
                    pageWidth / 2,
                    pageHeight - 10,
                    { align: 'center' }
                );

                // Disclaimer a destra
                doc.setFontSize(6);
                doc.setFont('helvetica', 'italic');
                doc.text(
                    'Confidenziale',
                    pageWidth - margin,
                    pageHeight - 10,
                    { align: 'right' }
                );

                // Watermark molto leggero al centro della pagina
                doc.setFontSize(60);
                doc.setTextColor(245, 240, 244); // Viola estremamente chiaro (quasi invisibile)
                doc.setFont('helvetica', 'bold');
                doc.text('KIMERIKA', pageWidth / 2, pageHeight / 2, {
                    align: 'center',
                    angle: 45,
                    renderingMode: 'stroke',
                    lineWidth: 0.1
                });
            }
        }

        // Salva il PDF con nome descrittivo
        const filename = `Analisi_Visagistica_Scientifica_${new Date().toISOString().slice(0, 10)}.pdf`;
        doc.save(filename);

        showToast('✅ PDF scientifico generato con successo', 'success');

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
