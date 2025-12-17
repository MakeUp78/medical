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
    this.recognition.maxAlternatives = 1;

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
   * Avvia ascolto continuo per parole chiave
   */
  startListening() {
    if (!this.recognition) {
      alert('⚠️ Riconoscimento vocale non disponibile in questo browser.\nProva Chrome, Edge o Safari.');
      return false;
    }

    try {
      this.isListening = true;
      this.recognition.start();
      console.log('🎤 Ascolto vocale avviato');
      this.speak('Ascolto attivato. Pronuncia le tue parole chiave.');
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
      this.recognition.stop();
      console.log('🎤 Ascolto vocale fermato');
      this.speak('Ascolto disattivato.');
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
   * Processa parola chiave riconosciuta
   */
  async processKeyword(keyword) {
    try {
      // Prima controlla se è un comando per il report di analisi
      if (typeof window.processReportVoiceCommand === 'function') {
        const reportHandled = await window.processReportVoiceCommand(keyword);
        if (reportHandled) {
          return; // Il comando è stato gestito dal sistema di report
        }
      }

      const response = await fetch(`${this.apiUrl}/api/voice/process-keyword`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: keyword })
      });

      const data = await response.json();

      if (data.success && data.action) {
        console.log(`✅ Azione riconosciuta: ${data.action}`);

        // Esegui azione corrispondente
        this.executeAction(data.action);

        // Conferma vocale
        if (data.message) {
          this.speak(data.message);
        }
      } else {
        console.log(`❌ Parola chiave non riconosciuta: "${keyword}"`);
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
        await this.audioPlayer.play();
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
        await this.audioPlayer.play();
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
        await this.audioPlayer.play();
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
