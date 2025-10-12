"""
🎤 ISABELLA VOICE ASSISTANT - VERSIONE SEMPLIFICATA
==================================================

Assistente vocale semplificato per il controllo dell'applicazione medica.
Ottimizzazioni principali:
✅ Codice pulito senza duplicazioni
✅ Gestione comandi unificata
✅ Performance migliorate
✅ Nessuna dipendenza da query intelligenti
"""

import asyncio
import threading
import time
import json
import os
import tempfile
import uuid
from typing import Dict, Callable, Optional, Any, Set
from dataclasses import dataclass
import logging

# Dipendenze esterne
try:
    import edge_tts
    import pygame
    import speech_recognition as sr
except ImportError as e:
    print(f"❌ Dipendenza mancante: {e}")
    raise

# === CONFIGURAZIONE LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IsabellaVoice")

# === DATACLASSES ===

@dataclass(frozen=True)
class VoiceCommand:
    """Comando vocale semplificato"""
    patterns: frozenset
    action: str
    handler: Optional[Callable] = None
    confirmation: str = ""
    enabled: bool = True

# === CLASSE PRINCIPALE ===

class IsabellaVoiceAssistant:
    """
    Assistente Vocale Isabella - Versione Semplificata
    
    Gestisce riconoscimento vocale e sintesi vocale per l'applicazione medica.
    """

    def __init__(self, config_file: str = "isabella_voice_config.json"):
        """Inizializzazione semplificata"""
        
        self.config_file = config_file
        self._is_listening = False  # Variabile interna protetta
        self.is_active = False
        self.recognition_thread = None
        self._shutdown_mode = False  # Flag per permettere disattivazione SOLO durante shutdown
        self._tts_speaking = False  # Flag per bloccare processing durante TTS
        
        # Mutex per proteggere accesso al microfono
        self.microphone_lock = threading.Lock()
        
        # RIMOSSO: Monitor sicurezza - il microfono rimane sempre attivo
        
        # Performance tracking
        self.session_start = time.time()
        self.command_count = 0
        
        # Configurazione e componenti
        self._config = None
        self._recognizer = None
        self._microphone = None
        
        # Comandi disponibili
        self.commands: Dict[str, VoiceCommand] = {}
        self.activation_patterns: Set[str] = {"simmètra", "hey simmètra", "ciao simmètra"}
        
        # Handler fallback per comandi non riconosciuti
        self.fallback_handler = None
        
        # Inizializzazione base
        self._init_basic_setup()
        
        logger.info("🚀 Assistente vocale inizializzato")

    # === PROPRIETÀ ===

    @property
    def config(self) -> Dict[str, Any]:
        """Configurazione con cache"""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    @property
    def recognizer(self):
        """Speech recognizer con lazy init"""
        if self._recognizer is None:
            self._recognizer = sr.Recognizer()
            stt = self.config.get("stt_settings", {})
            self._recognizer.energy_threshold = stt.get("energy_threshold", 200)
            self._recognizer.dynamic_energy_threshold = stt.get("dynamic_energy_threshold", True)
            self._recognizer.pause_threshold = stt.get("pause_threshold", 0.8)
        return self._recognizer
    
    @property
    def microphone(self):
        """Microfono con lazy init"""
        if self._microphone is None:
            self._microphone = sr.Microphone()
        return self._microphone

    # === PROPERTY PROTETTA PER MICROFONO ===
    @property
    def is_listening(self):
        """Getter per stato microfono"""
        return self._is_listening
    
    @is_listening.setter
    def is_listening(self, value):
        """Setter BLINDATO per microfono - SEMPRE ATTIVO tranne shutdown finale"""
        if value == False:
            if not self._shutdown_mode:
                # BLOCCA QUALSIASI tentativo di disattivare il microfono durante uso normale
                logger.error(f"🚫🚫🚫 TENTATIVO BLOCCATO: MICROFONO DEVE RIMANERE SEMPRE ATTIVO!")
                logger.error(f"🔴 RICHIESTA DISATTIVAZIONE IGNORATA - is_listening rimane SEMPRE True")
                logger.error(f"🔴 SOLO IL PROCESSING AUDIO SI ATTIVA/DISATTIVA, NON IL MICROFONO!")
                return
            else:
                # Permetti disattivazione SOLO durante shutdown finale
                logger.error(f"🔴 SHUTDOWN FINALE: Disattivazione microfono autorizzata")
        
        # Aggiorna valore solo se cambiato
        old_value = self._is_listening
        self._is_listening = value
        
        if old_value != value:
            if value:
                logger.error(f"🔴 MICROFONO ATTIVATO - is_listening={value}")
            else:
                logger.error(f"🔴 MICROFONO DISATTIVATO PER SHUTDOWN FINALE - is_listening={value}")
    
    def _enable_shutdown_mode(self):
        """Abilita modalità shutdown per permettere disattivazione microfono"""
        self._shutdown_mode = True
        logger.error("🔴 MODALITÀ SHUTDOWN ATTIVATA - disattivazione microfono ora permessa")

    # === INIZIALIZZAZIONE ===

    def _init_basic_setup(self):
        """Setup base dei comandi essenziali"""
        try:
            # Comandi di sistema essenziali
            self.commands = {
                "aiuto": VoiceCommand(
                    patterns=frozenset(["aiuto", "help", "comandi"]),
                    action="show_help",
                    confirmation="Comandi disponibili"
                ),
                "stato": VoiceCommand(
                    patterns=frozenset(["stato", "status", "come va"]),
                    action="show_status",
                    confirmation="Sistema operativo"
                ),
                "zitto": VoiceCommand(
                    patterns=frozenset(["zitto", "silenzio", "muto", "stop"]),
                    action="mute",
                    confirmation=""
                )
            }
            
            logger.debug("⚡ Setup base completato")
            
        except Exception as e:
            logger.error(f"❌ Errore setup base: {e}")

    def _load_config(self) -> Dict[str, Any]:
        """Caricamento configurazione"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                logger.debug("📋 Configurazione caricata")
                return config
                
        except Exception as e:
            logger.error(f"❌ Errore caricamento config: {e}")
            
        # Configurazione di fallback
        return {
            "activation_keywords": ["simmètra"],
            "language": "it-IT",
            "tts_voice": "it-IT-IsabellaNeural",
            "timeout": 5.0,
            "phrase_timeout": 2.0
        }

    # === GESTIONE COMANDI ===

    def load_commands_from_config(self):
        """Carica comandi dalla configurazione"""
        try:
            commands_config = self.config.get("commands", [])
            loaded_count = 0
            
            for cmd_config in commands_config:
                if not cmd_config.get("enabled", True):
                    continue
                    
                patterns = cmd_config.get("patterns", [])
                if not patterns:
                    continue
                    
                pattern_set = frozenset(p.lower() for p in patterns)
                
                command = VoiceCommand(
                    patterns=pattern_set,
                    action=cmd_config.get("name", "unnamed"),
                    confirmation=cmd_config.get("confirmation", ""),
                    enabled=True
                )
                
                cmd_key = cmd_config.get("name", f"cmd_{loaded_count}")
                self.commands[cmd_key] = command
                loaded_count += 1
                
            logger.info(f"📚 Caricati {loaded_count} comandi dalla configurazione")
            
        except Exception as e:
            logger.error(f"❌ Errore caricamento comandi: {e}")

    # === TEXT-TO-SPEECH ===

    async def speak(self, text: str, wait_for_completion: bool = True) -> bool:
        """Sintesi vocale"""
        try:
            # Genera audio
            communicate = edge_tts.Communicate(
                text,
                self.config.get("tts_voice", "it-IT-IsabellaNeural"),
                rate="+10%"
            )
            
            # File temporaneo
            temp_filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
            temp_path = os.path.join(tempfile.gettempdir(), temp_filename)
            await communicate.save(temp_path)
            
            # Riproduzione
            success = await self._play_audio(temp_path, wait_for_completion)
            return success
                
        except Exception as e:
            logger.error(f"❌ Errore TTS: {e}")
            return False

    async def _play_audio(self, file_path: str, wait_for_completion: bool = True) -> bool:
        """Riproduzione audio con attesa robusta del completamento"""
        try:
            # BLOCCA processing audio durante TTS per evitare feedback
            self._tts_speaking = True
            logger.debug("🔇 TTS AVVIATO - processing audio bloccato per evitare feedback")
            
            # DISATTIVA SOLO L'ASSISTENTE durante TTS - microfono rimane sempre attivo
            was_active = self.is_active
            if was_active:
                self.is_active = False  # Solo assistente, NON microfono
                logger.debug("🔇 Assistente disattivato durante TTS - microfono rimane attivo")
                await asyncio.sleep(0.1)  # Breve pausa
            
            # Inizializza pygame mixer se necessario
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # Attendi completamento se richiesto con timeout più lungo
            if wait_for_completion:
                max_wait_time = 30.0  # Massimo 30 secondi per messaggi lunghi
                start_time = time.time()
                
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                    # Timeout di sicurezza
                    if time.time() - start_time > max_wait_time:
                        logger.warning("⏰ Timeout TTS - interrotto dopo 30s")
                        pygame.mixer.music.stop()
                        break
                
                # Attesa aggiuntiva per assicurarsi che l'audio sia completato
                await asyncio.sleep(0.3)
            
            # Riattiva ASSISTENTE se era attivo - microfono non viene mai toccato
            if was_active:
                await asyncio.sleep(0.2)  # Pausa prima di riattivare
                self.is_active = True
                logger.debug("🔊 Assistente riattivato dopo TTS - microfono sempre attivo")
            
            # RIATTIVA processing audio dopo TTS
            self._tts_speaking = False
            logger.debug("🔊 TTS COMPLETATO - processing audio riattivato")
            
            # Cleanup con delay più lungo
            threading.Timer(5.0, lambda: self._safe_cleanup(file_path)).start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Errore riproduzione: {e}")
            # Riattiva ASSISTENTE anche in caso di errore - microfono sempre attivo
            if 'was_active' in locals() and was_active:
                self.is_active = True
            # SEMPRE riattiva processing audio anche in caso di errore
            self._tts_speaking = False
            logger.debug("🔊 TTS ERROR - processing audio riattivato per sicurezza")
            return False

    def _safe_cleanup(self, file_path: str):
        """Cleanup sicuro del file temporaneo"""
        for attempt in range(3):
            try:
                if os.path.exists(file_path):
                    pygame.mixer.music.stop()
                    time.sleep(0.1)
                    os.unlink(file_path)
                    break
            except (PermissionError, OSError):
                if attempt < 2:
                    time.sleep(0.5)

    def speak_sync(self, text: str) -> bool:
        """Versione sincrona per compatibilità"""
        try:
            return asyncio.run(self.speak(text, wait_for_completion=True))
        except RuntimeError:
            # Se siamo già in un loop asincrono, usa un nuovo loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.speak(text, wait_for_completion=True))
            finally:
                loop.close()
    
    async def speak_complete(self, text: str) -> bool:
        """Sintesi vocale che garantisce il completamento - versione prioritaria"""
        logger.info(f"🔊 TTS Completo: '{text[:50]}...'") 
        
        # Forza il completamento con attesa estesa
        return await self.speak(text, wait_for_completion=True)

    # === SPEECH-TO-TEXT ===

    def start_listening(self, activate_immediately=False):
        """Avvia ascolto vocale"""
        if self.is_listening:
            logger.info("ℹ️ Ascolto già attivo - ignoro chiamata duplicata")
            return
            
        # Verifica che non ci sia già un thread attivo
        if self.recognition_thread and self.recognition_thread.is_alive():
            logger.info("⚠️ Thread riconoscimento già attivo - fermo vecchio thread")
            # NON disattivare is_listening durante il restart del thread
            old_listening_state = self.is_listening
            self.recognition_thread.join(timeout=2)
            self.is_listening = old_listening_state  # Ripristina stato precedente
            logger.error(f"🔴 RIPRISTINO STATO MICROFONO - is_listening={self.is_listening}")
            
        self.is_listening = True
        logger.error(f"🔴 MICROFONO ATTIVATO - is_listening={self.is_listening}")
        self.is_active = activate_immediately
        
        # RIMOSSO: Monitor sicurezza - il microfono rimane SEMPRE attivo con protezione property
        
        # Calibrazione microfono
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
        except Exception as e:
            logger.warning(f"⚠️ Calibrazione fallita: {e}")
        
        # Avvia thread di ascolto
        self.recognition_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True
        )
        self.recognition_thread.start()
        
        status = "attivo" if activate_immediately else "in attesa parola chiave"
        logger.info(f"🎤 Ascolto avviato ({status})")

    def stop_listening(self):
        """SHUTDOWN FINALE - MICROFONO MAI DISATTIVATO tranne per chiusura app"""
        logger.warning("🛑 SHUTDOWN FINALE - Chiusura assistente vocale")
        # SOLO per chiusura finale dell'app - NON disattivare microfono mai durante uso normale
        self.is_active = False  # Disattiva assistente
        
        if self.recognition_thread:
            self.recognition_thread.join(timeout=2)
            
        # Abilita modalità shutdown per permettere disattivazione microfono
        self._enable_shutdown_mode()
        
        # MICROFONO DISATTIVATO SOLO per chiusura finale app
        logger.error("🔴 DISATTIVAZIONE MICROFONO PER SHUTDOWN FINALE!")
        self.is_listening = False
        logger.info("🛑 Shutdown finale completato")
    


    def _listen_loop(self):
        """Loop principale di ascolto con protezione mutex"""
        logger.error("🔴 THREAD ASCOLTO AVVIATO")
        while self.is_listening:
            try:
                # Usa mutex per evitare accessi multipli al microfono
                with self.microphone_lock:
                    if not self.is_listening:  # Double check dopo acquisizione lock
                        break
                        
                    with self.microphone as source:
                        audio = self.recognizer.listen(
                            source, 
                            timeout=3.0,
                            phrase_time_limit=4.0
                        )
                
                # Processamento fuori dal mutex per non bloccare troppo a lungo
                text = self.recognizer.recognize_google(
                    audio, 
                    language=self.config.get("language", "it-IT")
                ).lower().strip()
                
                # BLOCCA processing durante TTS per evitare feedback audio
                if self._tts_speaking:
                    logger.debug(f"🔇 AUDIO IGNORATO durante TTS: '{text[:30]}...'")
                    continue
                
                if text:
                    self._process_command(text)
                    
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                continue
            except Exception as e:
                logger.error(f"❌ Errore ascolto: {e}")
                time.sleep(0.5)
        
        logger.error("🔴 THREAD ASCOLTO TERMINATO - is_listening è diventato False!")

    # === PROCESSAMENTO COMANDI ===

    def _process_command(self, text: str):
        """Processa comando vocale"""
        logger.debug(f"🗣️ Testo riconosciuto: '{text}'")
        
        # Check attivazione
        if not self.is_active:
            logger.error(f"🔴 CHECK ATTIVAZIONE - testo='{text}', is_listening={self.is_listening}")
            if self._check_activation(text):
                logger.error(f"🔴 PAROLA CHIAVE RICONOSCIUTA - attivando assistente")
                self._activate()
            else:
                logger.error(f"🔴 PAROLA CHIAVE NON RICONOSCIUTA - assistente rimane inattivo")
            return
        
        # Carica comandi se necessario
        if len(self.commands) <= 3:  # Solo comandi base
            self.load_commands_from_config()
        
        # Cerca comando corrispondente
        command_found = False
        for cmd_name, command in self.commands.items():
            if self._matches_command(text, command):
                command_found = True
                
                # Risposta di conferma con sistema TTS integrato
                if command.confirmation:
                    # Usa sistema TTS integrato (niente più RobustTTSManager)
                    asyncio.run(self.speak_complete(command.confirmation))
                
                # Esegui handler se presente
                if command.handler:
                    try:
                        if asyncio.iscoroutinefunction(command.handler):
                            asyncio.run(command.handler(text, command))
                        else:
                            command.handler(text, command)
                    except Exception as e:
                        logger.error(f"❌ Errore handler per {cmd_name}: {e}")
                else:
                    # Handler default per comandi integrati
                    self._handle_built_in_command(command.action, text)
                
                self.command_count += 1
                break
        
        # Fallback se comando non trovato
        if not command_found:
            if self.fallback_handler:
                try:
                    self.fallback_handler(text)
                except Exception as e:
                    logger.error(f"❌ Errore fallback handler: {e}")
            else:
                asyncio.run(self.speak("Comando non riconosciuto", wait_for_completion=False))

    def _check_activation(self, text: str) -> bool:
        """Verifica parola chiave di attivazione"""
        text_words = set(text.lower().split())
        
        # Check parole chiave di attivazione
        for pattern in self.activation_patterns:
            if pattern.lower() in text.lower():
                return True
        
        # Varianti di "simmètra"
        simmetra_variants = {"simmètra", "simme", "symmetra", "simetra"}
        if simmetra_variants & text_words:
            return True
            
        return False

    def _matches_command(self, text: str, command: VoiceCommand) -> bool:
        """Verifica se il testo corrisponde al comando"""
        text_lower = text.lower()
        
        # Check esatto
        if text_lower in command.patterns:
            return True
            
        # Check substring
        return any(pattern in text_lower for pattern in command.patterns)

    def _activate(self):
        """Attiva assistente - SEMPRE ATTIVO"""
        logger.error(f"🔴 ATTIVAZIONE ASSISTENTE - is_listening={self.is_listening} -> is_active={self.is_active}->True")
        self.is_active = True
        logger.error(f"🔴 NUOVO STATO DOPO ATTIVAZIONE - is_listening={self.is_listening}, is_active={self.is_active}")
        asyncio.run(self.speak("Ti ascolto", wait_for_completion=False))
        
        # RIMOSSO: Auto-disattivazione - microfono rimane sempre attivo
        logger.debug("✅ Assistente attivato - modalità sempre attiva")

    def _deactivate(self):
        """Disattiva assistente - METODO DISABILITATO"""
        # NON disattivare più automaticamente - rimane sempre attivo
        logger.debug("ℹ️ Richiesta disattivazione ignorata - modalità sempre attiva")

    def pause_assistant_for_tts(self):
        """Pausa temporanea dell'assistente durante TTS - microfono rimane attivo"""
        if self.is_active:
            self.is_active = False
            logger.debug("🔇 Assistente in pausa per TTS - microfono sempre attivo")
            return True
        return False

    def resume_assistant_after_tts(self):
        """Riattiva assistente dopo TTS"""
        self.is_active = True
        logger.debug("🔊 Assistente riattivato dopo TTS")

    def force_keep_microphone_active(self):
        """FORZA il microfono a rimanere attivo - sistema di sicurezza"""
        if not self.is_listening:
            logger.error("🚨 EMERGENZA: MICROFONO DISATTIVATO RILEVATO - RIATTIVAZIONE FORZATA!")
            self.is_listening = True
            logger.error("🔴 RIATTIVAZIONE FORZATA - is_listening=True")
            
            # Riavvia thread se necessario
            if not self.recognition_thread or not self.recognition_thread.is_alive():
                logger.warning("🔄 Riavvio thread riconoscimento dopo emergenza")
                self.recognition_thread = threading.Thread(
                    target=self._listen_loop,
                    daemon=True
                )
                self.recognition_thread.start()

    def emergency_microphone_check(self):
        """Controllo di emergenza completo dello stato microfono"""
        logger.info("🔍 CONTROLLO EMERGENZA MICROFONO:")
        logger.info(f"   📡 is_listening: {self.is_listening}")
        logger.info(f"   🤖 is_active: {self.is_active}")
        logger.info(f"   🧵 thread_alive: {self.recognition_thread.is_alive() if self.recognition_thread else False}")
        # RIMOSSO: Monitor non più utilizzato
        
        # Forza riattivazione se necessario
        if not self.is_listening:
            logger.error("🚨 MICROFONO DISATTIVO - CORREZIONE FORZATA!")
            self.force_keep_microphone_active()

    # RIMOSSO: _start_microphone_monitor
    # Il microfono rimane SEMPRE attivo grazie alla property protetta

    def _handle_built_in_command(self, action: str, text: str):
        """Handler per comandi integrati"""
        if action == "show_help":
            help_text = "Comandi disponibili: analizza volto, carica immagine, avvia webcam, calcola misura, salva risultati"
            asyncio.run(self.speak(help_text))
            
        elif action == "show_status":
            uptime = int(time.time() - self.session_start)
            status_text = f"Sistema attivo da {uptime} secondi. {self.command_count} comandi eseguiti."
            asyncio.run(self.speak(status_text))
            
        elif action == "mute":
            # NON disattivare l'assistente - rimane sempre attivo, solo muta la voce TTS
            logger.info("🔇 Voce silenziata - assistente rimane attivo per comandi")

    # === METODI DI COMPATIBILITÀ ===

    def add_command(self, keywords, action, handler=None, confirmation=None, **kwargs):
        """Aggiunge comando personalizzato"""
        if isinstance(keywords, str):
            keywords = [keywords]
        
        pattern_set = frozenset(k.lower() for k in keywords)
        
        command = VoiceCommand(
            patterns=pattern_set,
            action=action,
            handler=handler,
            confirmation=confirmation or "",
            enabled=True
        )
        
        self.commands[action] = command
        logger.info(f"⚡ Comando aggiunto: '{keywords[0]}' -> {action}")

    def set_query_handler(self, handler: Callable):
        """Imposta handler per comandi non riconosciuti (compatibilità)"""
        self.fallback_handler = handler

    def set_query_fallback_handler(self, handler: Callable):
        """Alias per compatibilità"""
        self.set_query_handler(handler)

    def get_stats(self) -> dict:
        """Statistiche utilizzo"""
        return {
            "uptime": time.time() - self.session_start,
            "commands_executed": self.command_count,
            "is_active": self.is_active,
            "is_listening": self.is_listening,
            "loaded_commands": len(self.commands)
        }

    def get_performance_stats(self) -> dict:
        """Alias per get_stats"""
        return self.get_stats()

    # === GESTIONE MESSAGGI ===

    async def speak_message(self, key: str, **kwargs) -> bool:
        """Pronuncia messaggio dalla configurazione"""
        message = self.get_message(key, **kwargs)
        return await self.speak(message)

    def get_message(self, key: str, **kwargs) -> str:
        """Recupera messaggio dalla configurazione"""
        messages = self.config.get("messages", {})
        custom_messages = self.config.get("custom_messages", {})
        
        if key in custom_messages:
            text = custom_messages[key]
        elif key in messages:
            text = messages[key]
        else:
            text = f"Messaggio '{key}' non trovato."
            logger.warning(f"⚠️ Messaggio non trovato: {key}")

        # Sostituisci parametri
        try:
            return text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"⚠️ Parametro mancante in '{key}': {e}")
            return text

    def add_message(self, key: str, text: str, context: str = None):
        """Aggiunge messaggio personalizzato"""
        if "custom_messages" not in self.config:
            self.config["custom_messages"] = {}
        
        self.config["custom_messages"][key] = text
        logger.info(f"💬 Messaggio aggiunto: '{key}'")

    # === SHUTDOWN ===

    async def shutdown_fast(self):
        """Shutdown veloce - SOLO per chiusura finale applicazione"""
        logger.info("🛑 Shutdown assistente vocale - chiusura finale")
        
        # RIMOSSO: Monitor sicurezza non più utilizzato
            
        # Ferma tutto solo per chiusura finale
        self.stop_listening()
        logger.info("🛑 Shutdown completato")

    def shutdown(self):
        """Shutdown sincrono"""
        asyncio.run(self.shutdown_fast())


# === FUNZIONE FACTORY ===

def create_assistant(config_file: str = "isabella_voice_config.json") -> IsabellaVoiceAssistant:
    """Crea assistente semplificato"""
    return IsabellaVoiceAssistant(config_file)


if __name__ == "__main__":
    """Test funzionalità"""
    
    async def test_assistant():
        assistant = create_assistant()
        
        # Test TTS
        await assistant.speak("Test assistente vocale Isabella")
        
        # Statistiche
        stats = assistant.get_stats()
        print(f"📊 Statistiche: {stats}")
    
    asyncio.run(test_assistant())