"""
🎤 ISABELLA VOICE ASSISTANT - Modulo Unificato
=============================================

Assistente vocale completo con controllo vocale e messaggi personalizzabili
per integrazione rapida in qualsiasi applicazione esistente.

Caratteristiche:
- Text-to-speech con voce Isabella (Edge TTS)
- Speech-to-text con riconoscimento comandi italiani
- Comandi vocali personalizzabili con pattern avanzati
- Messaggi configurabili per ogni situazione
- Attivazione tramite parole chiave
- Configurazione JSON esterna

Autore: AI Assistant
Data: 29 Settembre 2025
Versione: 1.0.0

Usage:
    from isabella_voice_assistant import IsabellaVoiceAssistant

    assistant = IsabellaVoiceAssistant()

    # Messaggio di benvenuto
    await assistant.speak_startup("La Mia App")

    # Registra comando personalizzato
    assistant.add_command("avvia processo", "start_process", lambda: print("Processo avviato!"))

    # Avvia ascolto
    assistant.start_listening()
"""

import asyncio
import threading
import time
import json
import os
import re
import tempfile
from typing import Dict, Callable, Optional, Any, List, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Dipendenze esterne
try:
    import edge_tts
    import pygame
    import speech_recognition as sr
except ImportError as e:
    print(f"❌ Dipendenza mancante: {e}")
    print("💡 Installa con: pip install edge-tts pygame SpeechRecognition pyaudio")
    raise


# === CONFIGURAZIONE LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IsabellaVoiceAssistant")


# === DATACLASSES E STRUTTURE DATI ===


@dataclass
class VoiceCommand:
    """Rappresenta un comando vocale"""

    keywords: List[str]
    action: str
    handler: Optional[Callable] = None
    confirmation: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_regex: bool = False


@dataclass
class VoiceMessage:
    """Rappresenta un messaggio vocale personalizzabile"""

    key: str
    text: str
    context: Optional[str] = None
    parameters: Dict[str, str] = field(default_factory=dict)


# === CLASSE PRINCIPALE ===


class IsabellaVoiceAssistant:
    """
    Assistente Vocale Isabella - Modulo Unificato

    Gestisce tutte le funzionalità vocali in un'unica classe:
    - Text-to-Speech con Isabella
    - Speech-to-Text con riconoscimento comandi
    - Messaggi personalizzabili
    - Comandi vocali avanzati
    """

    def __init__(self, config_file: str = "voice_config.json"):
        """
        Inizializza l'assistente vocale

        Args:
            config_file: Percorso al file di configurazione JSON
        """
        self.config_file = config_file
        self.is_listening = False
        self.is_active = False
        self.recognition_thread = None

        # Stato assistente
        self.session_start = time.time()
        self.command_count = 0
        self.last_activation = None

        # Configurazione
        self.config = self._load_config()

        # Componenti vocali
        self._init_voice_components()

        # Comandi e messaggi
        self.commands: Dict[str, VoiceCommand] = {}
        self.messages: Dict[str, VoiceMessage] = {}

        # Setup iniziale
        self._load_default_commands()
        self._load_default_messages()

        logger.info("🎤 Isabella Voice Assistant inizializzato")

    # === INIZIALIZZAZIONE ===

    def _init_voice_components(self):
        """Inizializza componenti vocali (TTS/STT)"""
        try:
            # Text-to-Speech (Isabella)
            self.tts_voice = self.config.get("tts_voice", "it-IT-IsabellaNeural")
            self.tts_rate = self.config.get("voice_settings", {}).get("rate", "+0%")
            self.tts_volume = self.config.get("voice_settings", {}).get("volume", "+0%")

            # Speech-to-Text
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()

            # Configurazione STT
            stt_config = self.config.get("stt_settings", {})
            self.recognizer.energy_threshold = stt_config.get("energy_threshold", 300)
            self.recognizer.dynamic_energy_threshold = stt_config.get(
                "dynamic_energy_threshold", True
            )
            self.recognizer.pause_threshold = stt_config.get("pause_threshold", 0.8)

            # Calibrazione microfono
            self._calibrate_microphone()

            logger.info("✅ Componenti vocali inizializzati")

        except Exception as e:
            logger.error(f"❌ Errore inizializzazione componenti vocali: {e}")
            raise

    def _calibrate_microphone(self):
        """Calibra automaticamente il microfono"""
        try:
            logger.info("🎤 Calibrazione microfono...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.info("✅ Microfono calibrato")
        except Exception as e:
            logger.warning(f"⚠️ Errore calibrazione microfono: {e}")

    def _load_config(self) -> Dict[str, Any]:
        """Carica configurazione da file JSON"""
        default_config = {
            "activation_keywords": ["hey isabella", "ciao isabella", "isabella"],
            "language": "it-IT",
            "tts_voice": "it-IT-IsabellaNeural",
            "timeout": 5.0,
            "phrase_timeout": 2.0,
            "voice_settings": {"rate": "+0%", "volume": "+0%"},
            "stt_settings": {
                "energy_threshold": 300,
                "dynamic_energy_threshold": True,
                "pause_threshold": 0.8,
            },
            "messages": {},
            "custom_messages": {},
            "advanced_settings": {
                "auto_deactivate_timeout": 30,
                "confirmation_for_critical_actions": True,
                "background_listening": True,
                "voice_feedback_level": "normal",
            },
        }

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # Merge con configurazione predefinita
                    self._deep_merge(default_config, loaded_config)
            else:
                logger.info(f"📄 Creazione file configurazione: {self.config_file}")
                self._save_config(default_config)
        except Exception as e:
            logger.error(f"⚠️ Errore caricamento configurazione: {e}")

        return default_config

    def _deep_merge(self, base: dict, update: dict):
        """Merge ricorsivo di dizionari"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _save_config(self, config: Dict[str, Any] = None):
        """Salva configurazione su file"""
        config_to_save = config or self.config
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Configurazione salvata: {self.config_file}")
        except Exception as e:
            logger.error(f"❌ Errore salvataggio configurazione: {e}")

    # === TEXT-TO-SPEECH ===

    async def speak(self, text: str, wait_for_completion: bool = True) -> bool:
        """
        Pronuncia testo con voce Isabella

        Args:
            text: Testo da pronunciare
            wait_for_completion: Se attendere completamento

        Returns:
            True se successo, False se errore
        """
        try:
            # Crea comunicazione TTS
            communicate = edge_tts.Communicate(
                text, self.tts_voice, rate=self.tts_rate, volume=self.tts_volume
            )

            # Salva in file temporaneo
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                temp_path = tmp_file.name
                await communicate.save(temp_path)

            # Riproduce audio
            pygame.mixer.init()
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()

            if wait_for_completion:
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)

            # Pulizia
            pygame.mixer.quit()
            os.unlink(temp_path)

            logger.debug(
                f"🔊 Pronunciato: '{text[:50]}{'...' if len(text) > 50 else ''}'"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Errore TTS: {e}")
            return False

    def speak_sync(self, text: str) -> bool:
        """Versione sincrona di speak()"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.speak(text))
        except RuntimeError:
            # Se non c'è un loop attivo, creane uno nuovo
            return asyncio.run(self.speak(text))

    # === MESSAGGI PERSONALIZZATI ===

    def add_message(self, key: str, text: str, context: str = None):
        """
        Aggiunge messaggio personalizzato

        Args:
            key: Chiave identificativa del messaggio
            text: Testo del messaggio
            context: Contesto d'uso (opzionale)
        """
        self.messages[key] = VoiceMessage(key=key, text=text, context=context)

        # Salva anche in configurazione
        if "custom_messages" not in self.config:
            self.config["custom_messages"] = {}
        self.config["custom_messages"][key] = text
        self._save_config()

        logger.info(f"💬 Messaggio aggiunto: '{key}'")

    def get_message(self, key: str, **kwargs) -> str:
        """
        Recupera messaggio con sostituzione parametri

        Args:
            key: Chiave del messaggio
            **kwargs: Parametri per sostituzione {placeholder}

        Returns:
            Testo del messaggio formattato
        """
        # Cerca in messaggi personalizzati
        if key in self.messages:
            text = self.messages[key].text
        # Cerca in configurazione
        elif key in self.config.get("custom_messages", {}):
            text = self.config["custom_messages"][key]
        elif key in self.config.get("messages", {}):
            text = self.config["messages"][key]
        else:
            text = f"Messaggio '{key}' non trovato."
            logger.warning(f"⚠️ Messaggio non trovato: {key}")

        # Sostituisci parametri
        try:
            return text.format(**kwargs)
        except KeyError as e:
            logger.warning(f"⚠️ Parametro mancante in '{key}': {e}")
            return text

    async def speak_message(self, key: str, **kwargs) -> bool:
        """
        Pronuncia messaggio personalizzato

        Args:
            key: Chiave del messaggio
            **kwargs: Parametri per sostituzione

        Returns:
            True se successo
        """
        message = self.get_message(key, **kwargs)
        return await self.speak(message)

    def _load_default_messages(self):
        """Carica messaggi predefiniti"""
        default_messages = {
            "startup": "Assistente vocale Isabella attivato. Dimmi 'Hey Isabella' per iniziare.",
            "activation": "Ti ascolto! Cosa posso fare per te?",
            "deactivation": "Torno in modalità standby.",
            "command_not_found": "Comando non riconosciuto. Puoi ripetere o dire 'aiuto'?",
            "listening_error": "Non ho sentito bene. Puoi ripetere più chiaramente?",
            "processing": "Un momento, sto elaborando...",
            "goodbye": "Assistente vocale disattivato. Arrivederci!",
            "help": "Comandi disponibili: aiuto, stato, esci. Puoi aggiungere comandi personalizzati.",
            "status": "Assistente attivo da {duration} secondi. Eseguiti {commands} comandi.",
            "feature_activated": "Funzionalità '{feature}' attivata.",
            "operation_complete": "Operazione '{operation}' completata con successo.",
            "error_occurred": "Si è verificato un errore: {error}.",
        }

        for key, text in default_messages.items():
            if key not in self.messages:
                self.messages[key] = VoiceMessage(key=key, text=text)

    # === COMANDI VOCALI ===

    def add_command(
        self,
        keywords: Union[str, List[str]],
        action: str,
        handler: Callable = None,
        confirmation: str = None,
        is_regex: bool = False,
        **parameters,
    ) -> str:
        """
        Aggiunge comando vocale personalizzato

        Args:
            keywords: Parole chiave o lista di parole chiave (o pattern regex)
            action: Nome identificativo dell'azione
            handler: Funzione da chiamare (opzionale)
            confirmation: Messaggio di conferma (opzionale)
            is_regex: Se keywords è un pattern regex
            **parameters: Parametri aggiuntivi

        Returns:
            ID del comando registrato
        """
        if isinstance(keywords, str):
            keywords = [keywords]

        command = VoiceCommand(
            keywords=keywords,
            action=action,
            handler=handler,
            confirmation=confirmation,
            is_regex=is_regex,
            parameters=parameters,
        )

        # Registra comando per ogni keyword
        command_id = f"{action}_{len(self.commands)}"
        for keyword in keywords:
            key = f"REGEX:{keyword}" if is_regex else keyword.lower()
            self.commands[key] = command

        logger.info(f"⚡ Comando registrato: '{keywords[0]}' -> {action}")
        return command_id

    def remove_command(self, keywords: Union[str, List[str]]):
        """Rimuove comando vocale"""
        if isinstance(keywords, str):
            keywords = [keywords]

        for keyword in keywords:
            key = keyword.lower()
            if key in self.commands:
                del self.commands[key]
                logger.info(f"🗑️ Comando rimosso: '{keyword}'")

    def _load_default_commands(self):
        """Carica comandi predefiniti"""
        default_commands = [
            # Comandi sistema
            (["aiuto", "help", "cosa puoi fare"], "help", self._handle_help),
            (["stato", "status", "come va"], "status", self._handle_status),
            (["esci", "chiudi", "termina", "bye"], "exit", self._handle_exit),
            (["zitto", "silenzio", "basta parlare"], "mute", self._handle_mute),
            (["riattiva voce", "torna a parlare"], "unmute", self._handle_unmute),
            # Comandi generici app
            (["pausa", "metti in pausa"], "pause", None, "Applicazione in pausa."),
            (["riprendi", "continua", "vai"], "resume", None, "Ripresa applicazione."),
            (["salva", "salva tutto"], "save", None, "Salvataggio in corso."),
            (
                ["ricarica", "aggiorna", "refresh"],
                "reload",
                None,
                "Ricaricamento dati.",
            ),
        ]

        for cmd_data in default_commands:
            keywords, action = cmd_data[0], cmd_data[1]
            handler = cmd_data[2] if len(cmd_data) > 2 else None
            confirmation = cmd_data[3] if len(cmd_data) > 3 else None

            self.add_command(keywords, action, handler, confirmation)

    # === GESTORI COMANDI PREDEFINITI ===

    async def _handle_help(self, text: str, command: VoiceCommand):
        """Gestisce comando aiuto"""
        commands_list = []
        seen_actions = set()

        for cmd in self.commands.values():
            if cmd.action not in seen_actions:
                commands_list.append(
                    f"- {', '.join(cmd.keywords[:2])} per {cmd.action}"
                )
                seen_actions.add(cmd.action)

        help_text = "Comandi disponibili:\n" + "\n".join(commands_list[:8])  # Primi 8
        if len(seen_actions) > 8:
            help_text += f"\n... e altri {len(seen_actions) - 8} comandi."

        await self.speak(help_text)

    async def _handle_status(self, text: str, command: VoiceCommand):
        """Gestisce comando status"""
        duration = int(time.time() - self.session_start)
        await self.speak_message(
            "status", duration=duration, commands=self.command_count
        )

    async def _handle_exit(self, text: str, command: VoiceCommand):
        """Gestisce comando uscita"""
        await self.speak_message("goodbye")
        self.stop_listening()
        # Termina processo dopo breve delay
        threading.Timer(2.0, lambda: os._exit(0)).start()

    async def _handle_mute(self, text: str, command: VoiceCommand):
        """Disabilita feedback vocale"""
        self.config["advanced_settings"]["voice_feedback_level"] = "muted"
        # Non pronuncia nulla (è mutato)
        logger.info("🔇 Feedback vocale disabilitato")

    async def _handle_unmute(self, text: str, command: VoiceCommand):
        """Riabilita feedback vocale"""
        self.config["advanced_settings"]["voice_feedback_level"] = "normal"
        await self.speak("Feedback vocale riattivato.")
        logger.info("🔊 Feedback vocale riattivato")

    # === SPEECH-TO-TEXT E RICONOSCIMENTO ===

    def start_listening(self):
        """Avvia ascolto comandi vocali"""
        if self.is_listening:
            logger.warning("⚠️ Ascolto già attivo")
            return

        self.is_listening = True
        self.recognition_thread = threading.Thread(
            target=self._listen_continuously, daemon=True
        )
        self.recognition_thread.start()

        logger.info("👂 Ascolto comandi vocali avviato")

    def stop_listening(self):
        """Ferma ascolto comandi vocali"""
        self.is_listening = False
        self.is_active = False

        if self.recognition_thread:
            self.recognition_thread.join(timeout=2)

        logger.info("🛑 Ascolto comandi vocali fermato")

    def _listen_continuously(self):
        """Loop continuo di ascolto"""
        while self.is_listening:
            try:
                with self.microphone as source:
                    # Ascolto audio
                    audio = self.recognizer.listen(
                        source,
                        timeout=self.config["timeout"],
                        phrase_time_limit=self.config["phrase_timeout"],
                    )

                # Riconoscimento vocale
                text = (
                    self.recognizer.recognize_google(
                        audio, language=self.config["language"]
                    )
                    .lower()
                    .strip()
                )

                logger.debug(f"🎤 Riconosciuto: '{text}'")

                # Verifica attivazione o elaborazione comando
                if self._check_activation(text):
                    asyncio.run(self._handle_activation(text))
                elif self.is_active:
                    asyncio.run(self._process_command(text))

            except sr.WaitTimeoutError:
                # Timeout normale, continua
                continue
            except sr.UnknownValueError:
                if self.is_active:
                    asyncio.run(self.speak_message("listening_error"))
            except Exception as e:
                logger.error(f"❌ Errore riconoscimento: {e}")
                time.sleep(1)  # Pausa prima di riprovare

    def _check_activation(self, text: str) -> bool:
        """Verifica se il testo contiene parole di attivazione"""
        activation_keywords = self.config.get("activation_keywords", [])
        return any(keyword in text for keyword in activation_keywords)

    async def _handle_activation(self, text: str):
        """Gestisce attivazione assistente"""
        self.is_active = True
        self.last_activation = time.time()

        # Feedback vocale se non mutato
        if (
            self.config.get("advanced_settings", {}).get("voice_feedback_level")
            != "muted"
        ):
            await self.speak_message("activation")

        # Timer disattivazione automatica
        timeout = self.config.get("advanced_settings", {}).get(
            "auto_deactivate_timeout", 30
        )
        threading.Timer(timeout, self._auto_deactivate).start()

        logger.info("🎯 Assistente attivato")

    def _auto_deactivate(self):
        """Disattivazione automatica dopo timeout"""
        if self.is_active:
            self.is_active = False
            asyncio.run(self.speak_message("deactivation"))
            logger.info("⏰ Disattivazione automatica")

    async def _process_command(self, text: str):
        """Elabora comando vocale riconosciuto"""
        command_found = False

        # Cerca comando corrispondente
        for key, command in self.commands.items():
            if self._match_command(key, text, command):
                command_found = True
                self.command_count += 1

                # Messaggio di conferma
                if command.confirmation:
                    if (
                        self.config.get("advanced_settings", {}).get(
                            "voice_feedback_level"
                        )
                        != "muted"
                    ):
                        await self.speak(command.confirmation)

                # Esegui handler se presente
                if command.handler:
                    try:
                        if asyncio.iscoroutinefunction(command.handler):
                            await command.handler(text, command)
                        else:
                            command.handler(text, command)
                    except Exception as e:
                        logger.error(
                            f"❌ Errore esecuzione comando '{command.action}': {e}"
                        )
                        await self.speak_message("error_occurred", error=str(e))

                logger.info(f"⚡ Comando eseguito: {command.action}")
                break

        if not command_found:
            if (
                self.config.get("advanced_settings", {}).get("voice_feedback_level")
                != "muted"
            ):
                await self.speak_message("command_not_found")
            logger.debug(f"❓ Comando non riconosciuto: '{text}'")

    def _match_command(self, key: str, text: str, command: VoiceCommand) -> bool:
        """Verifica se testo corrisponde a comando"""
        if key.startswith("REGEX:"):
            # Pattern regex
            pattern = key[6:]  # Rimuovi "REGEX:"
            return bool(re.search(pattern, text, re.IGNORECASE))
        else:
            # Keyword semplice
            return key in text

    # === METODI DI CONVENIENZA ===

    async def speak_startup(self, app_name: str = None, custom_message: str = None):
        """Messaggio di avvio personalizzato"""
        if custom_message:
            await self.speak(custom_message)
        elif app_name:
            message = f"Benvenuto in {app_name}! Sono Isabella, il tuo assistente vocale. Dimmi 'Hey Isabella' quando hai bisogno di me."
            await self.speak(message)
        else:
            await self.speak_message("startup")

    async def speak_feature_activation(
        self, feature_name: str, additional_info: str = None
    ):
        """Notifica attivazione funzionalità"""
        message = self.get_message("feature_activated", feature=feature_name)
        if additional_info:
            message += f" {additional_info}"
        await self.speak(message)

    async def speak_operation_complete(
        self, operation_name: str, duration: float = None
    ):
        """Notifica operazione completata"""
        kwargs = {"operation": operation_name}
        if duration:
            kwargs["duration"] = f"{duration:.1f}"
        await self.speak_message("operation_complete", **kwargs)

    async def speak_error(self, error_message: str):
        """Notifica errore"""
        await self.speak_message("error_occurred", error=error_message)

    def add_app_commands(self, commands_config: List[Dict[str, Any]]):
        """
        Aggiunge comandi specifici dell'app da configurazione

        Args:
            commands_config: Lista di dizionari con configurazione comandi
                Formato: [
                    {
                        "keywords": ["comando1", "comando2"],
                        "action": "nome_azione",
                        "confirmation": "Messaggio conferma",
                        "handler": funzione_handler  # opzionale
                    }
                ]
        """
        for cmd_config in commands_config:
            self.add_command(
                keywords=cmd_config["keywords"],
                action=cmd_config["action"],
                handler=cmd_config.get("handler"),
                confirmation=cmd_config.get("confirmation"),
                is_regex=cmd_config.get("is_regex", False),
            )

        logger.info(f"📝 Aggiunti {len(commands_config)} comandi dell'app")

    def get_stats(self) -> Dict[str, Any]:
        """Restituisce statistiche d'uso"""
        uptime = time.time() - self.session_start
        return {
            "uptime_seconds": uptime,
            "commands_executed": self.command_count,
            "is_listening": self.is_listening,
            "is_active": self.is_active,
            "last_activation": self.last_activation,
            "registered_commands": len(self.commands),
            "registered_messages": len(self.messages),
        }

    # === CONFIGURAZIONE DINAMICA ===

    def update_config(self, key: str, value: Any):
        """Aggiorna configurazione"""
        keys = key.split(".")
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        self._save_config()
        logger.info(f"⚙️ Configurazione aggiornata: {key} = {value}")

    def add_activation_keyword(self, keyword: str):
        """Aggiunge parola di attivazione"""
        if "activation_keywords" not in self.config:
            self.config["activation_keywords"] = []

        if keyword.lower() not in [
            kw.lower() for kw in self.config["activation_keywords"]
        ]:
            self.config["activation_keywords"].append(keyword.lower())
            self._save_config()
            logger.info(f"🔑 Parola di attivazione aggiunta: '{keyword}'")

    async def shutdown(self):
        """Chiusura pulita dell'assistente"""
        logger.info("🛑 Shutdown assistente vocale...")
        self.stop_listening()
        await self.speak_message("goodbye")


# === FUNZIONI DI CONVENIENZA ===


def create_assistant(config_file: str = "voice_config.json") -> IsabellaVoiceAssistant:
    """
    Crea istanza dell'assistente vocale

    Args:
        config_file: Percorso file configurazione

    Returns:
        Istanza IsabellaVoiceAssistant configurata
    """
    return IsabellaVoiceAssistant(config_file)


def create_facial_analysis_commands() -> List[Dict[str, Any]]:
    """
    Crea comandi predefiniti per app di analisi facciale

    Returns:
        Lista configurazioni comandi
    """
    return [
        {
            "keywords": ["inizia analisi", "avvia scansione", "analizza volto"],
            "action": "start_facial_analysis",
            "confirmation": "Avvio analisi facciale. Mantieni la posizione.",
        },
        {
            "keywords": ["ferma analisi", "interrompi scansione", "stop"],
            "action": "stop_facial_analysis",
            "confirmation": "Analisi interrotta.",
        },
        {
            "keywords": ["qualità alta", "massima qualità"],
            "action": "set_quality_high",
            "confirmation": "Qualità impostata al massimo.",
        },
        {
            "keywords": ["qualità media", "qualità normale"],
            "action": "set_quality_medium",
            "confirmation": "Qualità impostata su media.",
        },
        {
            "keywords": ["salva risultati", "salva analisi"],
            "action": "save_results",
            "confirmation": "Salvataggio risultati in corso.",
        },
        {
            "keywords": ["esporta dati", "esporta risultati"],
            "action": "export_data",
            "confirmation": "Esportazione dati avviata.",
        },
    ]


def create_productivity_commands() -> List[Dict[str, Any]]:
    """Crea comandi per app di produttività"""
    return [
        {
            "keywords": ["nuova attività", "crea task", "aggiungi promemoria"],
            "action": "create_task",
            "confirmation": "Nuova attività creata.",
        },
        {
            "keywords": ["cerca documento", "trova file"],
            "action": "search_documents",
            "confirmation": "Ricerca documenti avviata.",
        },
        {
            "keywords": ["backup dati", "salva tutto", "sincronizza"],
            "action": "backup_data",
            "confirmation": "Backup dei dati in corso.",
        },
    ]


# === ESEMPIO D'USO ===


async def example_usage():
    """Esempio completo d'uso dell'assistente"""

    # Crea assistente
    assistant = create_assistant("voice_config.json")

    # Messaggio di benvenuto
    await assistant.speak_startup("La Mia App di Esempio")

    # Aggiungi messaggi personalizzati
    assistant.add_message("process_start", "Avvio elaborazione dati in corso...")
    assistant.add_message(
        "process_complete", "Elaborazione completata! Risultati disponibili."
    )

    # Aggiungi comandi personalizzati
    def my_process_handler(text: str, command):
        print("🚀 Eseguo il mio processo personalizzato!")
        # Qui la tua logica...

    assistant.add_command(
        keywords=["avvia processo", "inizia elaborazione"],
        action="start_my_process",
        handler=my_process_handler,
        confirmation="Processo personalizzato avviato!",
    )

    # Oppure aggiungi comandi predefiniti per tipo di app
    facial_commands = create_facial_analysis_commands()
    assistant.add_app_commands(facial_commands)

    # Avvia ascolto
    assistant.start_listening()

    # L'assistente è ora attivo e in ascolto!
    # Prova a dire: "Hey Isabella, aiuto"

    # Esempio di utilizzo programmatico
    await assistant.speak_message("process_start")
    # ... esegui la tua logica ...
    await assistant.speak_message("process_complete")

    # Statistiche
    stats = assistant.get_stats()
    print(f"📊 Statistiche: {stats}")

    # Mantieni attivo (in un'app reale useresti il tuo loop principale)
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await assistant.shutdown()


if __name__ == "__main__":
    """
    Test rapido del modulo

    Per usarlo nella tua app:
    1. Copia questo file nella tua app: isabella_voice_assistant.py
    2. Copia il file di configurazione: voice_config.json
    3. Installa dipendenze: pip install edge-tts pygame SpeechRecognition pyaudio
    4. Importa e usa: from isabella_voice_assistant import create_assistant
    """

    print("🎤 Isabella Voice Assistant - Test Rapido")
    print("=" * 50)

    try:
        asyncio.run(example_usage())
    except KeyboardInterrupt:
        print("\n👋 Test interrotto")
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback

        traceback.print_exc()
