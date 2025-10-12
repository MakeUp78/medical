"""
Patch per correggere il sistema di attivazione dell'assistente vocale
"""

import logging
import asyncio
import time
import speech_recognition as sr

# Setup del logger
logger = logging.getLogger(__name__)

# Codice per sostituire il metodo _listen_continuously

def _listen_continuously_fixed(self):
    """Loop continuo di ascolto - gestisce attivazione e comandi CORRETTO"""
    logger.info("🎤 Loop ascolto avviato")
    
    # Verifica microfono disponibile
    try:
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        logger.info("🔧 Microfono calibrato")
    except Exception as e:
        logger.error(f"❌ Errore inizializzazione microfono: {e}")
        self.is_listening = False
        return
    
    while self.is_listening:
        try:
            with self.microphone as source:
                # Ascolto audio con timeout più breve per evitare blocchi
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

            # NUOVA LOGICA: activation keywords vs comandi
            if text and text.strip():
                if not self.is_active and self._check_activation(text):
                    # Activation keywords rilevate - attiva assistente
                    try:
                        asyncio.run(self._handle_activation(text))
                    except Exception as e:
                        logger.error(f"❌ Errore attivazione: {e}")
                elif self.is_active:
                    # Assistente attivo - elabora comandi
                    try:
                        asyncio.run(self._process_command(text))
                    except Exception as e:
                        logger.error(f"❌ Errore elaborazione comando: {e}")
                # Se assistente non attivo e non activation keywords, ignora silenziosamente
            else:
                logger.debug("🔇 Testo vuoto, ignorato")

        except sr.WaitTimeoutError:
            # Timeout normale, continua
            continue
        except sr.UnknownValueError:
            # Audio non comprensibile - normale, non mostrare errori continui
            if self.is_active:
                logger.debug("🔇 Audio non comprensibile (normale)")
            continue
        except sr.RequestError as e:
            logger.error(f"❌ Errore servizio riconoscimento: {e}")
            time.sleep(2)  # Pausa più lunga per errori di servizio
        except Exception as e:
            logger.error(f"❌ Errore critico riconoscimento: {e}")
            if self.is_listening:  # Solo se dovrebbe ancora ascoltare
                time.sleep(1)
            else:
                break  # Esci dal loop se fermato