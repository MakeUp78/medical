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

    // Unlock audio autoplay
    this.audioUnlocked = false;
    this.pendingQueue = [];  // { src, text } in attesa di unlock
    this._flushRunning = false; // mutex: evita riproduzioni concorrenti
    this._audioCache = new Map(); // cache audio pre-fetched per latenza zero
    this._registerUnlockListeners();

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
   * Registra listener per sbloccare autoplay al primo gesto utente
   */
  _isDesktop() {
    // Desktop = nessun touch primario e nessun User-Agent mobile
    return !('ontouchstart' in window) &&
      navigator.maxTouchPoints === 0 &&
      !/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  }

  _registerUnlockListeners() {
    const unlock = () => this._unlockAudio();
    document.addEventListener('click', unlock, { once: true, capture: true });
    document.addEventListener('keydown', unlock, { once: true, capture: true });
    document.addEventListener('touchend', unlock, { once: true, capture: true });

    // Desktop: tenta sblocco automatico senza aspettare gesture utente.
    // Chrome/Firefox desktop consentono l'autoplay audio quando il sito ha
    // media engagement score (visite precedenti) oppure per file audio brevi.
    // Se play() fallisce con NotAllowedError, _unlockAudio ripristina il flag
    // a false e il listener 'click' resta come fallback.
    if (this._isDesktop()) {
      setTimeout(() => this._unlockAudio(), 0);
    }
  }

  /**
   * Sblocca l'audio e svuota la coda di messaggi in attesa
   */
  _unlockAudio() {
    if (this.audioUnlocked) return;
    this.audioUnlocked = true;

    // Sblocca AudioContext (necessario su iOS 13+ per rilascio vincolo autoplay)
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        const ctx = new AudioCtx();
        ctx.resume().catch(() => { });
      }
    } catch (_) { }

    // Strategia mobile: se c'è già audio in coda (es. benvenuto scaricato),
    // reproducilo DIRETTAMENTE nel contesto del gesto utente (non in .then async)
    // così iOS Safari non lo blocca come NotAllowedError.
    if (this.pendingQueue.length > 0) {
      const item = this.pendingQueue.shift();
      this.audioPlayer.src = item.src;
      this.audioPlayer.load(); // Obbligatorio su iOS dopo cambio src
      this.audioPlayer.play().then(() => {
        // Aspetta la fine e poi svuota la coda rimanente
        this.audioPlayer.onended = () => {
          this.audioPlayer.onended = null;
          this._flushQueue();
        };
        setTimeout(() => {
          if (this.audioPlayer.onended) {
            this.audioPlayer.onended = null;
            this._flushQueue();
          }
        }, 15000); // safety timeout
      }).catch((e) => {
        if (e.name === 'NotAllowedError') {
          // Rimetti in coda e riprova al prossimo gesto
          this.pendingQueue.unshift(item);
          this.audioUnlocked = false;
          this._registerUnlockListeners();
        } else if (e.name === 'AbortError') {
          // Audio interrotto volontariamente (stop/reset sessione): ignora silenziosamente.
          // Non è un errore reale: stopPoseVoiceGuidance ha chiamato pause() durante play().
        } else {
          console.warn('Errore unlock diretto:', e);
          this._flushQueue();
        }
      });
      return;
    }

    // Nessun audio in coda: play silenzioso per preparare l'elemento audio
    const silentSrc = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
    this.audioPlayer.src = silentSrc;
    this.audioPlayer.load();
    this.audioPlayer.play().then(() => {
      console.log('🔊 Audio sbloccato (silent) - pronto per coda futura');
    }).catch(() => {
      // Non è ancora possibile sbloccare — ci riprova al prossimo gesto
      this.audioUnlocked = false;
      this._registerUnlockListeners();
    });
  }

  /**
   * Sospende l'elaborazione dei comandi vocali durante la riproduzione TTS.
   * Usa due meccanismi complementari:
   * 1. _ignoringResults: scarta immediatamente ogni onresult (funziona anche se
   *    recognition.stop() non ha ancora effetto per via dell'asincronismo del browser)
   * 2. recognition.stop(): riduce il carico e il rischio di catturare audio TTS
   */
  _pauseRecognition() {
    if (!this._ignoringResults) {
      this._ignoringResults = true;
      console.log('🔇 Riconoscimento vocale in pausa (TTS attivo)');
    }
    if (this.recognition && this.isListening && !this._recognitionPausedByTTS) {
      this._recognitionPausedByTTS = true;
      try {
        this.recognition.stop();
      } catch (_) {}
    }
    // Cancella eventuale cooldown precedente ancora in attesa
    if (this._resumeCooldownTimer) {
      clearTimeout(this._resumeCooldownTimer);
      this._resumeCooldownTimer = null;
    }
  }

  /**
   * Riattiva il riconoscimento vocale dopo la riproduzione TTS.
   * Il cooldown di 800ms garantisce che:
   * - l'audio sia fisicamente terminato dagli altoparlanti
   * - il browser non consegni più onresult in ritardo relativi al TTS
   */
  _resumeRecognition() {
    // Cooldown: aspetta che gli altoparlanti smettano di risuonare.
    // 1500ms per coprire anche frasi TTS lunghe (es. risposta simmetria ~3s)
    // il microfono riprende solo dopo che l'audio è fisicamente finito + margine.
    const COOLDOWN_MS = 1500;
    this._resumeCooldownTimer = setTimeout(() => {
      this._resumeCooldownTimer = null;
      this._ignoringResults = false;
      this._recognitionPausedByTTS = false;
      console.log(`🎤 Riconoscimento vocale riattivato (cooldown ${COOLDOWN_MS}ms completato)`);
      if (this.isListening && !this._flushRunning) {
        try {
          this.recognition.start();
        } catch (_) {}
      }
    }, COOLDOWN_MS);
  }

  async _flushQueue() {
    if (this._flushRunning) return;
    this._flushRunning = true;
    // Sospendi microfono prima di iniziare a riprodurre audio
    this._pauseRecognition();
    while (this.pendingQueue.length > 0) {
      const item = this.pendingQueue.shift();
      if (item.text) console.log(`🔊 (coda) ${item.text}`);
      this.audioPlayer.src = item.src;
      this.audioPlayer.load(); // iOS richiede .load() dopo cambio src
      try {
        await this.audioPlayer.play();
        this._hideMobileWelcomeBadge(); // Audio partito: nascondi badge mobile
        // Aspetta fine riproduzione prima del prossimo
        await new Promise(res => {
          this.audioPlayer.onended = res;
          setTimeout(res, 12000); // safety timeout
        });
      } catch (e) {
        if (e.name === 'NotAllowedError') {
          // Rimetti in testa alla coda e attendi sblocco
          this.pendingQueue.unshift(item);
          this.audioUnlocked = false;
          this._flushRunning = false;
          this._resumeRecognition();
          this._registerUnlockListeners();
          return;
        }
        console.warn('Errore riproduzione coda:', e);
      }
    }
    this._flushRunning = false;
    // Riattiva microfono dopo che tutta la coda è svuotata
    this._resumeRecognition();
  }

  /**
   * Metodo interno per riprodurre un src audio (accodam sempre, flush serializzato)
   */
  async _playAudio(src, label) {
    // Accoda sempre: evita race condition con _flushQueue in corso
    this.pendingQueue.push({ src, text: label || '' });
    if (!this.audioUnlocked) {
      return;
    }
    // Avvia il flush solo se non è già in esecuzione
    if (!this._flushRunning) {
      this._flushQueue();
    }
  }

  /**
   * Pre-carica in parallelo una lista di frasi in cache (nessuna riproduzione)
   */
  async prefetchAudio(texts) {
    const jobs = texts.map(async (text) => {
      if (this._audioCache.has(text)) return;
      try {
        const r = await fetch(`${this.apiUrl}/api/voice/speak`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        const d = await r.json();
        if (d.success && d.audio) this._audioCache.set(text, d.audio);
      } catch (_) { /* silent fail */ }
    });
    await Promise.all(jobs);
    console.log(`🎧 Cache audio: ${this._audioCache.size} frasi pre-caricate`);
  }

  /**
   * Pre-carica il messaggio di benvenuto personalizzato (nessuna riproduzione)
   */
  async prefetchWelcome(userName) {
    const key = '__welcome__' + userName;
    if (this._audioCache.has(key)) return;
    try {
      const r = await fetch(`${this.apiUrl}/api/voice/speak-welcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_name: userName })
      });
      const d = await r.json();
      if (d.success && d.audio) {
        this._audioCache.set(key, { src: d.audio, text: d.text });
        console.log('🎧 Audio benvenuto pre-caricato');
      }
    } catch (_) { /* silent fail */ }
  }

  /**
   * Coaching di posa: fire-and-forget — se l'audio è in cache riproduce subito,
   * altrimenti avvia il download in background e salta questa istanza
   * (la prossima call, dopo il cooldown 12s, troverà la cache pronta).
   */
  async speakCoach(text) {
    if (this.isMuted) return;
    // Rimuovi eventuali coaching precedenti ancora in coda (stale)
    this.pendingQueue = this.pendingQueue.filter(item => !item.isCoach);
    // Controlla cache
    const src = this._audioCache.get(text);
    if (!src) {
      // Cache miss: avvia download in background, NON bloccare.
      // La guida vocale salterà questa istanza ma la prossima avrà l'audio pronto.
      this._prefetchSingle(text);
      return;
    }
    this.pendingQueue.push({ src, text: `coach: ${text.substring(0, 50)}`, isCoach: true });
    if (!this.audioUnlocked) return;
    if (!this._flushRunning) this._flushQueue();
  }

  /**
   * Scarica un singolo audio in cache (fire-and-forget, nessuna riproduzione)
   */
  async _prefetchSingle(text) {
    if (this._audioCache.has(text)) return;
    try {
      const r = await fetch(`${this.apiUrl}/api/voice/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const d = await r.json();
      if (d.success && d.audio) this._audioCache.set(text, d.audio);
    } catch (_) { /* silent fail */ }
  }

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
      // Scarta qualsiasi risultato arrivato mentre il TTS è in riproduzione o
      // durante il cooldown post-TTS. recognition.stop() è asincrono e il browser
      // può consegnare risultati in ritardo anche dopo la chiamata.
      if (this._ignoringResults) {
        const last = event.results.length - 1;
        const ignored = event.results[last][0].transcript;
        console.log(`🔇 Risultato ignorato durante TTS: "${ignored}"`);
        return;
      }

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
      // Non riavviare se sospeso volontariamente durante TTS
      if (this.isListening && !this._recognitionPausedByTTS) {
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
      // Cancella eventuale cooldown TTS in sospeso
      if (this._resumeCooldownTimer) {
        clearTimeout(this._resumeCooldownTimer);
        this._resumeCooldownTimer = null;
      }
      // Cancella debounce comando in sospeso
      if (this._commandDebounceTimer) {
        clearTimeout(this._commandDebounceTimer);
        this._commandDebounceTimer = null;
      }
      this._pendingCommandText = null;
      this._ignoringResults = false;
      this._recognitionPausedByTTS = false;
      this.recognition.stop();
      console.log('🎤 Ascolto vocale fermato');
      this.updateUI();
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

    // Rimuove la wake word e le sue varianti dal testo (utile in modalità ATTIVA
    // quando il browser include ancora "chimerica" nell'utterance)
    const stripWakeWord = (text) => {
      let result = text;
      for (const variant of this.activationKeywordVariants) {
        // Rimuove la variante ovunque appaia nel testo
        result = result.replace(new RegExp(variant.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), '');
      }
      // Rimuove anche con matching fonetico: parole simili a "kimerika"
      result = result.split(/\s+/).filter(word => {
        if (!word) return false;
        if (this.isSimilarPhonetically(word, 'kimerika', 2)) return false;
        if (this.isSimilarPhonetically(word, 'chimerica', 2)) return false;
        return true;
      }).join(' ').trim();
      return result;
    };

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

        // Estrae il comando dalla stessa frase rimuovendo tutte le varianti della wake word
        const commandPart = stripWakeWord(keywordLower);

        if (commandPart) {
          // Ha detto KIMERIKA + COMANDO nella stessa frase.
          // Usa debounce anche qui: il browser può consegnare versioni
          // parziali dello stesso utterance ("kimerika asse di", poi
          // "kimerika asse di simmetria") — esegui solo l'ultima versione.
          console.log(`🟢 [ATTIVO] Candidato comando immediato: '${commandPart}'`);
          this.lastHeardPhrase = `🟢 ATTIVO: ${commandPart}`;
          this.listeningMode = "active";
          this.lastSpeechTime = Date.now();
          this.updateUI();

          if (this._commandDebounceTimer) clearTimeout(this._commandDebounceTimer);
          this._pendingCommandText = commandPart;
          this._commandDebounceTimer = setTimeout(async () => {
            this._commandDebounceTimer = null;
            const commandToRun = this._pendingCommandText;
            this._pendingCommandText = null;
            console.log(`🟢 [ATTIVO] Esecuzione comando immediato (debounce): '${commandToRun}'`);
            this.listeningMode = "passive";
            this.lastHeardPhrase = "";
            this.updateUI();
            await this.executeVoiceCommand(commandToRun);
          }, 600);
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

    // MODALITÀ ATTIVA: Processa comandi vocali con debounce
    // Il browser consegna lo stesso utterance in versioni sempre più lunghe
    // ("asse di", "asse di si", "asse di simmetria") — il debounce aspetta
    // che l'utterance sia stabile prima di eseguire.
    if (this.listeningMode === "active") {
      // Rimuove la wake word se il browser la include ancora nell'utterance
      // (es: "chimerica altezza viso" → "altezza viso")
      const cleanedKeyword = stripWakeWord(keywordLower);
      this.lastHeardPhrase = `🟢 ATTIVO: ${cleanedKeyword || keywordLower}`;
      console.log(`🟢 [ATTIVO] Candidato comando: '${cleanedKeyword || keywordLower}'`);
      this.lastSpeechTime = Date.now();
      this.updateUI();

      // Cancella debounce precedente (utterance ancora in evoluzione)
      if (this._commandDebounceTimer) {
        clearTimeout(this._commandDebounceTimer);
      }

      // Salva il testo più aggiornato (già pulito dalla wake word) e aspetta stabilità
      this._pendingCommandText = cleanedKeyword || keywordLower;
      this._commandDebounceTimer = setTimeout(async () => {
        this._commandDebounceTimer = null;
        const commandToRun = this._pendingCommandText;
        this._pendingCommandText = null;

        console.log(`🟢 [ATTIVO] Esecuzione comando (debounce): '${commandToRun}'`);

        // Torna subito in modalità passiva: un comando = una esecuzione
        this.listeningMode = "passive";
        this.lastHeardPhrase = "";
        if (this.activeTimeout) {
          clearTimeout(this.activeTimeout);
          this.activeTimeout = null;
        }
        this.updateUI();

        await this.executeVoiceCommand(commandToRun);
      }, 600);
    }
  }

  /**
   * Esegue un comando vocale (metodo estratto per riuso)
   */
  async executeVoiceCommand(commandText) {
    // Protezione anti-doppia-esecuzione: ignora comando se identico
    // a quello appena eseguito nei 2 secondi precedenti.
    const now = Date.now();
    if (commandText === this._lastExecutedCommand &&
        now - (this._lastExecutedTime || 0) < 2000) {
      console.log(`⚠️ Comando duplicato ignorato (${commandText}) — eseguito ${now - this._lastExecutedTime}ms fa`);
      return;
    }
    this._lastExecutedCommand = commandText;
    this._lastExecutedTime = now;

    try {
      // Svuota la coda audio pendente: evita che TTS del comando precedente
      // venga riprodotto di nuovo quando arriva un nuovo comando vocale.
      this.pendingQueue = this.pendingQueue.filter(item => item.isCoach);

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
        console.log(`✅ Azione riconosciuta: ${data.action}${data.param ? ` (param: ${data.param})` : ''}`);
        // Sopprime il feedback vocale dei wrapper toggleAxis/toggleLandmarks/etc.
        // in index.html, che altrimenti generano TTS con parole trigger ("asse",
        // "simmetria"...) che il riconoscimento ri-cattura come nuovi comandi.
        window.suppressVoiceFeedback = true;
        this.executeAction(data.action, data.param);
        // Ripristina dopo un tick (i wrapper leggono il flag in modo sincrono)
        setTimeout(() => { window.suppressVoiceFeedback = false; }, 0);
        // Il backend non restituisce message per i comandi toggle,
        // quindi questo blocco non genera TTS aggiuntivo in quei casi.
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
  executeAction(action, param) {
    console.log(`🎯 Esecuzione azione: ${action}${param ? ` (param: ${param})` : ''}`);

    // DEBUG: Verifica azione ricevuta
    if (action === 'stopWebcam') {
      console.log('⚠️ AZIONE STOP WEBCAM RILEVATA');
    } else if (action === 'startWebcam') {
      console.log('⚠️ AZIONE START WEBCAM RILEVATA');
    }

    // Helper generico: clicca pulsante con selector o chiama funzione globale
    const clickBtn = (selector, fallbackFn) => {
      const btn = document.querySelector(selector);
      if (btn) btn.click();
      else if (typeof fallbackFn === 'function') fallbackFn();
    };

    // Mappa azioni -> funzioni globali della webapp
    const actionMap = {
      // --- SORGENTE ---
      'loadImage': () => {
        const btn = document.querySelector('button[onclick*="loadImage"]');
        if (btn) btn.click();
        else window.loadImage?.();
      },
      'loadVideo': () => {
        const btn = document.querySelector('button[onclick*="loadVideo"]');
        if (btn) btn.click();
        else window.loadVideo?.();
      },
      'startWebcam': () => clickBtn('button[onclick*="startWebcam"]', window.startWebcam),
      'stopWebcam': () => clickBtn('button[onclick*="stopWebcam"]', window.stopWebcam),

      // --- TOGGLE OVERLAY ---
      'toggleAxis': () => {
        const btn = document.querySelector('#axis-btn');
        if (btn) btn.click();
        else window.toggleAxis?.();
      },
      'toggleLandmarks': () => {
        const btn = document.querySelector('#landmarks-btn');
        if (btn) btn.click();
        else window.toggleLandmarks?.();
      },
      'toggleGreenDots': () => {
        const btn = document.querySelector('#green-dots-btn');
        if (btn) btn.click();
        else window.toggleGreenDots?.();
      },
      'toggleMeasureMode': () => {
        const btn = document.querySelector('#measure-btn');
        if (btn) btn.click();
        else window.toggleMeasureMode?.();
      },

      // --- CANVAS / ROTAZIONI ---
      'clearCanvas': () => window.clearCanvas?.(),
      'clearMeasurements': () => {
        if (typeof window.clearAllMeasurementOverlays === 'function') window.clearAllMeasurementOverlays();
      },
      'rotateLeft90': () => window.rotateImage90CounterClockwise?.(),
      'rotateRight90': () => window.rotateImage90Clockwise?.(),
      'rotateLeft1': () => window.rotateImageCounterClockwise?.(),
      'rotateRight1': () => window.rotateImageClockwise?.(),
      'autoAlignAxis': () => window.autoRotateToVerticalAxis?.(),

      // --- ANALISI FACCIALE ---
      'analyzeFace': () => window.analyzeFace?.(),
      'performCompleteAnalysis': () => {
        const btn = document.querySelector('button[onclick*="performCompleteAnalysis"]');
        if (btn) btn.click();
        else window.performCompleteAnalysis?.();
      },

      // --- MISURAZIONI ---
      'measureFacialSymmetry': () => {
        const btn = document.querySelector('button[onclick*="measureFacialSymmetry"]');
        if (btn) btn.click();
        else window.measureFacialSymmetry?.();
      },
      'estimate_age': () => {
        const btn = document.querySelector('button[onclick*="estimateAge"]');
        if (btn) btn.click();
        else window.estimateAge?.();
      },
      'measureFaceWidth': () => window.measureFaceWidth?.(null),
      'measureFaceHeight': () => window.measureFaceHeight?.(null),
      'measureEyeDistance': () => window.measureEyeDistance?.(null),
      'measureNoseWidth': () => window.measureNoseWidth?.(null),
      'measureNoseHeight': () => window.measureNoseHeight?.(null),
      'measureMouthWidth': () => window.measureMouthWidth?.(null),
      'measureEyeAreas': () => window.measureEyeAreas?.(null),
      'measureForeheadWidth': () => window.measureForeheadWidth?.(null),
      'measureFaceProportions': () => window.measureFaceProportions?.(null),
      'measureEyeRotationDiff': () => window.measureEyeRotationDiff?.(null),
      'measureNosalWingSymmetry': () => window.measureNosalWingSymmetry?.(null),
      'measureEyebrowSymmetry': () => window.measureEyebrowSymmetry?.(null),

      // --- CORREZIONE SOPRACCIGLIA ---
      'analyzeLeftEyebrow': () => window.analyzeLeftEyebrow?.(),
      'analyzeRightEyebrow': () => window.analyzeRightEyebrow?.(),
      'analyze_eyebrow_design': () => {
        if (typeof window.analyze_eyebrow_design === 'function') {
          window.analyze_eyebrow_design();
        } else {
          voiceAssistant.speak('Funzione non disponibile');
        }
      },
      'show_left_eyebrow_with_voice': () => {
        if (typeof window.show_left_eyebrow_with_voice === 'function') {
          window.show_left_eyebrow_with_voice();
        } else {
          voiceAssistant.speak('Funzione non disponibile');
        }
      },
      'show_right_eyebrow_with_voice': () => {
        if (typeof window.show_right_eyebrow_with_voice === 'function') {
          window.show_right_eyebrow_with_voice();
        } else {
          voiceAssistant.speak('Funzione non disponibile');
        }
      },
    };

    // Azioni con parametro (non in actionMap statica)
    if (action === 'readGreenDotComparison') {
      if (typeof window.readGreenDotComparison === 'function' && param) {
        window.readGreenDotComparison(param);
      } else {
        console.warn(`⚠️ readGreenDotComparison: funzione non trovata o param mancante`);
      }
      return;
    }

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
    // Usa cache se disponibile (latenza zero)
    const cachedSrc = this._audioCache.get(text);
    if (cachedSrc) {
      await this._playAudio(cachedSrc, `speak: ${text.substring(0, 40)}`);
      return;
    }
    try {
      const response = await fetch(`${this.apiUrl}/api/voice/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });
      const data = await response.json();
      if (data.success && data.audio) {
        this._audioCache.set(text, data.audio); // Cache per le prossime volte
        await this._playAudio(data.audio, `speak: ${text.substring(0, 40)}`);
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
        await this._playAudio(data.audio, `Isabella: ${data.text}`);
      }
    } catch (error) {
      console.error('Errore TTS messaggio:', error);
    }
  }

  /**
   * Mostra un badge mobile "Tappa per ascoltare il benvenuto"
   * che scompare quando l'audio viene riprodotto o dopo 30 secondi.
   */
  _showMobileWelcomeBadge(replayFn) {
    // Solo su mobile (≤768px)
    if (window.innerWidth > 768) return;
    // Rimuovi badge precedenti
    const existing = document.getElementById('mobile-welcome-badge');
    if (existing) existing.remove();

    const badge = document.createElement('button');
    badge.id = 'mobile-welcome-badge';
    badge.innerHTML = '🔊 Tappa per il benvenuto';
    badge.setAttribute('aria-label', 'Riproduci messaggio di benvenuto');
    Object.assign(badge.style, {
      position: 'fixed',
      bottom: 'calc(68px + env(safe-area-inset-bottom, 0px))',
      left: '50%',
      transform: 'translateX(-50%)',
      zIndex: '9999',
      background: 'linear-gradient(135deg, #667eea, #764ba2)',
      color: 'white',
      border: 'none',
      borderRadius: '24px',
      padding: '12px 24px',
      fontSize: '15px',
      fontWeight: '600',
      boxShadow: '0 4px 20px rgba(102,126,234,0.5)',
      cursor: 'pointer',
      animation: 'mwbPulse 2s ease-in-out infinite',
      whiteSpace: 'nowrap',
      webkitTapHighlightColor: 'transparent',
    });

    // Aggiungi keyframe se non esiste
    if (!document.getElementById('mwb-style')) {
      const style = document.createElement('style');
      style.id = 'mwb-style';
      style.textContent = `@keyframes mwbPulse {
        0%,100%{box-shadow:0 4px 20px rgba(102,126,234,0.5);}
        50%{box-shadow:0 4px 28px rgba(102,126,234,0.9), 0 0 0 6px rgba(102,126,234,0.2);}
      }`;
      document.head.appendChild(style);
    }

    const dismiss = () => {
      badge.remove();
      clearTimeout(autoHide);
    };
    badge.addEventListener('click', () => {
      dismiss();
      replayFn();
    });
    const autoHide = setTimeout(dismiss, 30000);

    // Esporta dismiss per poterlo chiamare quando l'audio parte
    badge._dismiss = dismiss;
    document.body.appendChild(badge);
    console.log('📱 Mobile welcome badge mostrato');
  }

  /**
   * Nasconde il badge di benvenuto mobile (chiamato quando l'audio inizia)
   */
  _hideMobileWelcomeBadge() {
    const badge = document.getElementById('mobile-welcome-badge');
    if (badge && badge._dismiss) badge._dismiss();
  }

  /**
   * Fa parlare Isabella con messaggio di benvenuto personalizzato
   */
  async speakWelcome(userName) {
    if (this.isMuted) return;
    // Usa cache se disponibile (pre-fetch in background aveva già scaricato l'audio)
    const key = '__welcome__' + userName;
    const cached = this._audioCache.get(key);

    const doPlay = async (src, text) => {
      console.log(`🔊 Kimerika: "${text}"`);
      await this._playAudio(src, `Kimerika: ${text}`);
      // Nascondi il badge appena l'audio parte
      this._hideMobileWelcomeBadge();
    };

    // Mostra badge mobile di fallback dopo 3s se l'audio non parte ancora
    let badgeShown = false;
    const badgeTimer = setTimeout(() => {
      if (!this.audioUnlocked || this.pendingQueue.length > 0) {
        badgeShown = true;
        this._showMobileWelcomeBadge(() => this.speakWelcome(userName));
      }
    }, 3000);

    if (cached) {
      clearTimeout(badgeTimer);
      await doPlay(cached.src, cached.text);
      return;
    }
    try {
      const response = await fetch(`${this.apiUrl}/api/voice/speak-welcome`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_name: userName })
      });
      const data = await response.json();
      if (data.success && data.audio) {
        clearTimeout(badgeTimer);
        this._audioCache.set(key, { src: data.audio, text: data.text });
        await doPlay(data.audio, data.text);
      } else {
        clearTimeout(badgeTimer);
      }
    } catch (error) {
      clearTimeout(badgeTimer);
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
