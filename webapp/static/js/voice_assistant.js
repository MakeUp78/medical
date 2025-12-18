/**
 * Voice Assistant Integration per Webapp
 * Sistema completo per Text-to-Speech (Isabella parla) e Speech-to-Text (utente comanda)
 */

class VoiceAssistant {
  constructor(apiUrl = window.location.origin) {
    this.apiUrl = apiUrl;
    this.audioPlayer = new Audio();
    this.recognition = null;
    this.isListening = false;
    this.isMuted = false;

    // Nuovo sistema: ascolto passivo/attivo
    this.listeningMode = "inactive";  // Può essere: "inactive", "passive", "active"
    this.activationKeyword = "kimerika";
    // Varianti fonetiche per il riconoscimento italiano (K→C, K→CH, K→G, etc.)
    this.activationKeywordVariants = [
      "kimerika", "chimerica", "cimerica", "kimerica", "chimerika",
      "kimeryka", "chimeryka", "cimeryka", "gimerica", "ghimerica",
      "gimeryka", "ghimeryka", "kimeriga", "chimeriga", "cimeriga",
      "kim erika", "chi merica", "ci merica", "gi merica",
      // Varianti problematiche riconosciute dal browser
      "in america", "in merica", "america", "merica", "ameryka"
    ];
    this.activeListeningDuration = 4000;  // 4 secondi in ms
    this.silenceThreshold = 3000;  // 3 secondi di pausa
    this.lastSpeechTime = null;
    this.lastHeardPhrase = "";
    this.activeTimeout = null;

    // Inizializza riconoscimento vocale (Web Speech API)
    this.initSpeechRecognition();
  }

  /**
   * Inizializza Web Speech API per riconoscimento vocale
   */
  initSpeechRecognition() {
    // Controlla supporto browser
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn('⚠️ Web Speech API non supportata in questo browser');
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.lang = 'it-IT';
    this.recognition.continuous = true;  // Ascolto continuo
    this.recognition.interimResults = false;  // Solo risultati finali
    this.recognition.maxAlternatives = 3;  // Più alternative per migliore matching

    // Event: risultato riconosciuto
    this.recognition.onresult = (event) => {
      const last = event.results.length - 1;
      const keyword = event.results[last][0].transcript.toLowerCase().trim();

      console.log(`🎤 Riconosciuto: "${keyword}"`);
      this.processKeyword(keyword);
    };

    // Event: errore
    this.recognition.onerror = (event) => {
      console.error('❌ Errore riconoscimento vocale:', event.error);

      if (event.error === 'not-allowed') {
        alert('⚠️ Permesso microfono negato. Abilita il microfono nelle impostazioni del browser.');
        this.stopListening();
      }
    };

    // Event: fine riconoscimento
    this.recognition.onend = () => {
      if (this.isListening) {
        // Riavvia se dovrebbe essere ancora in ascolto
        this.recognition.start();
      }
    };
  }

  /**
   * Avvia ascolto in modalità PASSIVA (ascolta solo "KIMERIKA")
   */
  startListening() {
    if (!this.recognition) {
      alert('⚠️ Riconoscimento vocale non disponibile in questo browser.\nProva Chrome, Edge o Safari.');
      return false;
    }

    try {
      this.isListening = true;
      this.listeningMode = "passive";
      this.lastHeardPhrase = "";
      this.recognition.start();
      console.log('🎤 Ascolto vocale avviato in modalità PASSIVA');
      this.updateUI();
      // Non chiamiamo speak() qui per evitare autoplay error
      return true;
    } catch (error) {
      console.error('Errore avvio ascolto:', error);
      return false;
    }
  }

  /**
   * Ferma ascolto
   */
  stopListening() {
    if (this.recognition && this.isListening) {
      this.isListening = false;
      this.listeningMode = "inactive";
      this.lastHeardPhrase = "";
      if (this.activeTimeout) {
        clearTimeout(this.activeTimeout);
        this.activeTimeout = null;
      }
      this.recognition.stop();
      console.log('🎤 Ascolto vocale fermato');
      this.updateUI();
      // Non chiamiamo speak() qui per evitare problemi
    }
  }

  /**
   * Toggle ascolto on/off
   */
  toggleListening() {
    if (this.isListening) {
      this.stopListening();
      return false;
    } else {
      return this.startListening();
    }
  }

  /**
   * Verifica similarit\u00e0 fonetica tra due stringhe (algoritmo Levenshtein semplificato)
   */
  isSimilarPhonetically(str1, str2, maxDistance = 3) {
    const s1 = str1.toLowerCase().replace(/\s+/g, '');
    const s2 = str2.toLowerCase().replace(/\s+/g, '');

    if (s1 === s2) return true;
    if (Math.abs(s1.length - s2.length) > maxDistance) return false;

    let distance = 0;
    const maxLen = Math.max(s1.length, s2.length);

    for (let i = 0; i < maxLen; i++) {
      if (s1[i] !== s2[i]) distance++;
      if (distance > maxDistance) return false;
    }

    return true;
  }

  /**
   * Processa parola chiave riconosciuta con sistema passivo/attivo
   */
  async processKeyword(keyword) {
    let keywordLower = keyword.toLowerCase();

    // PRE-PROCESSING: Correggi errori comuni di riconoscimento
    keywordLower = keywordLower.replace(/in america/gi, 'kimerika');
    keywordLower = keywordLower.replace(/in merica/gi, 'kimerika');
    keywordLower = keywordLower.replace(/\bamerica\b/gi, 'kimerika');
    keywordLower = keywordLower.replace(/\bmerica\b/gi, 'kimerika');

    // MODALITÀ PASSIVA: Ascolta solo "KIMERIKA" + eventuale comando
    if (this.listeningMode === "passive") {
      this.lastHeardPhrase = `🔵 PASSIVO: ${keyword} → ${keywordLower}`;
      console.log(`🔵 [PASSIVO] Riconosciuto: '${keyword}' → Pre-processed: '${keywordLower}'`);
      this.updateUI();

      // Controlla se ha detto "KIMERIKA" (con varianti fonetiche E similarit\u00e0)
      let foundVariant = this.activationKeywordVariants.find(variant => keywordLower.includes(variant));

      // Se non trovato esatto, prova con similarit\u00e0 fonetica
      if (!foundVariant) {
        const words = keywordLower.split(/\s+/);
        for (const word of words) {
          if (this.isSimilarPhonetically(word, "kimerika", 2) ||
            this.isSimilarPhonetically(word, "chimerica", 2)) {
            foundVariant = word;
            console.log(`\ud83d\udd0d Trovata variante simile: '${word}'`);
            break;
          }
        }
      }

      if (foundVariant) {
        console.log(`✅ PAROLA CHIAVE RILEVATA: '${foundVariant.toUpperCase()}' → ATTIVAZIONE`);

        // Estrae il comando dalla stessa frase (es: "KIMERIKA avvia webcam" → "avvia webcam")
        const commandPart = keywordLower.replace(foundVariant, "").trim();

        if (commandPart) {
          // Ha detto KIMERIKA + COMANDO nella stessa frase → esegui subito
          console.log(`🟢 [ATTIVO] Comando immediato: '${commandPart}'`);
          this.lastHeardPhrase = `🟢 ATTIVO: ${commandPart}`;
          this.listeningMode = "active";
          this.lastSpeechTime = Date.now();
          this.updateUI();

          // Processa il comando immediatamente
          await this.executeVoiceCommand(commandPart);

          // Torna in modalità passiva dopo l'esecuzione
          setTimeout(() => {
            this.listeningMode = "passive";
            this.lastHeardPhrase = "";
            this.updateUI();
          }, 1000);
        } else {
          // Ha detto solo KIMERIKA → entra in modalità attiva per 4 secondi
          this.listeningMode = "active";
          this.lastSpeechTime = Date.now();
          console.log(`🟢 [ATTIVO] Modalità ascolto ATTIVO per ${this.activeListeningDuration / 1000} secondi`);
          this.updateUI();

          // Imposta timeout per tornare passivo
          this.setActiveTimeout();
        }
      }
      return;
    }

    // MODALITÀ ATTIVA: Processa comandi vocali
    if (this.listeningMode === "active") {
      this.lastHeardPhrase = `🟢 ATTIVO: ${keyword}`;
      console.log(`🟢 [ATTIVO] Comando riconosciuto: '${keyword}'`);
      this.lastSpeechTime = Date.now();
      this.updateUI();

      // Resetta timeout
      this.setActiveTimeout();

      // Esegui il comando
      await this.executeVoiceCommand(keywordLower);
    }
  }

  /**
   * Esegue un comando vocale (metodo estratto per riuso)
   */
  async executeVoiceCommand(commandText) {
    try {
      // Prima controlla se è un comando per il report di analisi
      if (typeof window.processReportVoiceCommand === 'function') {
        const reportHandled = await window.processReportVoiceCommand(commandText);
        if (reportHandled) {
          return;
        }
      }

      const response = await fetch(`${this.apiUrl}/api/voice/process-keyword`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: commandText })
      });

      const data = await response.json();

      if (data.success && data.action) {
        console.log(`✅ Azione riconosciuta: ${data.action}`);
        this.executeAction(data.action);
        // Feedback vocale solo se esplicitamente fornito dal backend
        // (evita doppio feedback con toast delle funzioni)
        if (data.message && data.message.trim()) {
          console.log(`🔊 Feedback vocale: ${data.message}`);
          this.speak(data.message);
        }
      } else {
        console.log(`❌ Parola chiave non riconosciuta: "${commandText}"`);
      }
    } catch (error) {
      console.error('Errore processamento keyword:', error);
    }
  }

  /**
   * Esegue azione nel frontend
   */
  executeAction(action) {
    console.log(`🎯 Esecuzione azione: ${action}`);

    // DEBUG: Verifica azione ricevuta
    if (action === 'stopWebcam') {
      console.log('⚠️ AZIONE STOP WEBCAM RILEVATA');
    } else if (action === 'startWebcam') {
      console.log('⚠️ AZIONE START WEBCAM RILEVATA');
    }

    // Mappa azioni -> funzioni globali della webapp
    const actionMap = {
      'toggleAxis': () => {
        const btn = document.querySelector('#axis-btn');
        console.log('toggleAxis - Pulsante trovato:', btn);
        if (btn) btn.click();
        else window.toggleAxis?.();
      },
      'toggleLandmarks': () => {
        const btn = document.querySelector('#landmarks-btn');
        console.log('toggleLandmarks - Pulsante trovato:', btn);
        if (btn) btn.click();
        else window.toggleLandmarks?.();
      },
      'toggleGreenDots': () => {
        const btn = document.querySelector('#green-dots-btn');
        console.log('toggleGreenDots - Pulsante trovato:', btn);
        if (btn) btn.click();
        else window.toggleGreenDots?.();
      },
      'startWebcam': () => {
        const btn = document.querySelector('button[onclick*="startWebcam"]');
        console.log('startWebcam - Pulsante trovato:', btn);
        if (btn) btn.click();
        else window.startWebcam?.();
      },
      'stopWebcam': () => {
        const btn = document.querySelector('button[onclick*="stopWebcam"]');
        console.log('stopWebcam - Pulsante trovato:', btn);
        if (btn) btn.click();
        else window.stopWebcam?.();
      },
      'loadVideo': () => {
        const btn = document.querySelector('button[onclick*="loadVideo"]');
        console.log('loadVideo - Pulsante trovato:', btn);
        if (btn) btn.click();
        else window.loadVideo?.();
      },
      'analyzeFace': () => window.analyzeFace?.(),
      'clearCanvas': () => window.clearCanvas?.(),
      'analyzeLeftEyebrow': () => window.analyzeLeftEyebrow?.(),
      'analyzeRightEyebrow': () => window.analyzeRightEyebrow?.(),
      'measureFacialSymmetry': () => {
        console.log('🎯 Esecuzione comando measureFacialSymmetry');
        const btn = document.querySelector('button[onclick*="measureFacialSymmetry"]');
        console.log('measureFacialSymmetry - Pulsante trovato:', btn);
        if (btn) {
          console.log('✅ Click sul pulsante simmetria');
          btn.click();
          // Dopo 2 secondi, leggi il risultato della simmetria
          setTimeout(() => {
            if (window.lastSymmetryMessage) {
              console.log('🔊 Pronuncia risultato simmetria:', window.lastSymmetryMessage);
              voiceAssistant.speak(window.lastSymmetryMessage);
            } else {
              console.warn('⚠️ Nessun messaggio simmetria disponibile');
            }
          }, 2000);
        } else {
          console.warn('⚠️ Pulsante non trovato, provo funzione globale');
          if (typeof window.measureFacialSymmetry === 'function') {
            window.measureFacialSymmetry();
          } else {
            console.error('❌ Funzione measureFacialSymmetry non disponibile');
          }
        }
      },
    };

    const func = actionMap[action];
    if (func) {
      func();
    } else {
      console.warn(`⚠️ Azione non trovata: ${action}`);
    }
  }

  /**
   * Fa parlare Isabella con testo personalizzato
   */
  async speak(text) {
    if (this.isMuted) return;

    try {
      const response = await fetch(`${this.apiUrl}/api/voice/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });

      const data = await response.json();

      if (data.success && data.audio) {
        this.audioPlayer.src = data.audio;
        try {
          await this.audioPlayer.play();
        } catch (playError) {
          // Gestisci errore autoplay silenziosamente
          console.log('ℹ️ Audio non riprodotto (autoplay bloccato dal browser)');
        }
      }
    } catch (error) {
      console.error('Errore TTS:', error);
    }
  }

  /**
   * Fa parlare Isabella con messaggio predefinito
   */
  async speakMessage(messageKey) {
    if (this.isMuted) return;

    try {
      const response = await fetch(`${this.apiUrl}/api/voice/speak-message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_key: messageKey })
      });

      const data = await response.json();

      if (data.success && data.audio) {
        console.log(`🔊 Isabella: "${data.text}"`);
        this.audioPlayer.src = data.audio;
        try {
          await this.audioPlayer.play();
        } catch (playError) {
          console.log('ℹ️ Audio non riprodotto (autoplay bloccato dal browser)');
        }
      }
    } catch (error) {
      console.error('Errore TTS messaggio:', error);
    }
  }

  /**
   * Fa parlare Isabella con messaggio di benvenuto personalizzato
   */
  async speakWelcome(userName) {
    if (this.isMuted) return;

    try {
      const response = await fetch(`${this.apiUrl}/api/voice/speak-welcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_name: userName })
      });

      const data = await response.json();

      if (data.success && data.audio) {
        console.log(`🔊 Kimerika: "${data.text}"`);
        this.audioPlayer.src = data.audio;
        try {
          await this.audioPlayer.play();
        } catch (playError) {
          console.log('ℹ️ Audio non riprodotto (autoplay bloccato dal browser)');
        }
      }
    } catch (error) {
      console.error('Errore TTS benvenuto:', error);
    }
  }

  /**
   * Silenzia/riattiva audio
   */
  toggleMute() {
    this.isMuted = !this.isMuted;
    return this.isMuted;
  }

  /**
   * Imposta timeout per tornare in modalità passiva
   */
  setActiveTimeout() {
    if (this.activeTimeout) {
      clearTimeout(this.activeTimeout);
    }

    this.activeTimeout = setTimeout(() => {
      if (this.listeningMode === "active") {
        console.log(`🔵 Timeout ascolto attivo (${this.activeListeningDuration / 1000}s) - torno PASSIVO`);
        this.listeningMode = "passive";
        this.lastHeardPhrase = "";
        this.updateUI();
      }
    }, this.activeListeningDuration);
  }

  /**
   * Aggiorna l'interfaccia utente con lo stato corrente
   */
  updateUI() {
    const statusIndicator = document.getElementById('status-indicator-sidebar');
    const statusText = document.getElementById('status-text-sidebar');
    const lastCommandText = document.getElementById('last-command-text-sidebar');

    if (!statusIndicator || !statusText) return;

    // Aggiorna stato
    if (!this.isListening) {
      statusIndicator.textContent = '🔴';
      statusIndicator.className = 'status-indicator-sidebar inactive';
      statusText.textContent = 'Spento';
    } else if (this.listeningMode === "passive") {
      statusIndicator.textContent = '🔵';
      statusIndicator.className = 'status-indicator-sidebar passive';
      statusText.textContent = `PASSIVO (di' '${this.activationKeyword.toUpperCase()}')`;
    } else if (this.listeningMode === "active") {
      statusIndicator.textContent = '🟢';
      statusIndicator.className = 'status-indicator-sidebar active';
      statusText.textContent = 'ATTIVO (ascolto comandi)';
    }

    // Aggiorna ultima frase ascoltata
    if (lastCommandText) {
      if (this.lastHeardPhrase) {
        lastCommandText.textContent = this.lastHeardPhrase;
        lastCommandText.style.color = 'black';
      } else {
        lastCommandText.textContent = 'Nessuno';
        lastCommandText.style.color = 'gray';
      }
    }
  }

  /**
   * Ottiene lo stato del voice assistant
   */
  async getStatus() {
    try {
      const response = await fetch(`${this.apiUrl}/api/voice/status`);
      return await response.json();
    } catch (error) {
      console.error('Errore status voice assistant:', error);
      return { available: false };
    }
  }

  /**
   * Ottiene lista messaggi predefiniti disponibili
   */
  async getMessages() {
    try {
      const response = await fetch(`${this.apiUrl}/api/voice/messages`);
      const data = await response.json();
      return data.messages || {};
    } catch (error) {
      console.error('Errore recupero messaggi:', error);
      return {};
    }
  }
}

// Crea istanza globale (usa window.location.origin per percorso relativo)
const voiceAssistant = new VoiceAssistant();

// Export per uso in altri script
if (typeof module !== 'undefined' && module.exports) {
  module.exports = VoiceAssistant;
}
