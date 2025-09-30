#!/usr/bin/env python3
"""
Facial Analysis Application - Main Entry Point

Applicazione per l'analisi facciale che utilizza OpenCV e MediaPipe per:
- Catturare e analizzare flussi video
- Rilevare volti e selezionare il frame migliore con volto frontale
- Fornire strumenti di misurazione facciale interattivi con landmark
- Canvas interattivo per visualizzazione e misurazione

Autore: Sistema di Analisi Facciale
Versione: 2.0
Data: 2025-09-23
"""

import sys
import os
import signal
import tkinter as tk
from tkinter import messagebox
import logging

# Configurazione logging con supporto UTF-8
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("facial_analysis.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)

# Aggiunge il percorso src al PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


class FacialAnalysisApp:
    """Classe principale per l'applicazione di analisi facciale."""

    def __init__(self):
        self.root = None
        self.app = None
        self.running = False
        self.voice_assistant = None
        self.voice_enabled = False

    def setup_signal_handlers(self):
        """Configura i gestori per i segnali di interruzione."""

        def signal_handler(signum, frame):
            logger.info(f"Ricevuto segnale {signum}. Chiusura dell'applicazione...")
            self.graceful_shutdown()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def check_dependencies(self):
        """Verifica che tutte le dipendenze necessarie siano installate."""
        required_modules = {
            "cv2": "opencv-python",
            "mediapipe": "mediapipe",
            "numpy": "numpy",
            "PIL": "Pillow",
            "matplotlib": "matplotlib",
            "scipy": "scipy",
        }

        # Dipendenze opzionali per assistente vocale
        voice_modules = {
            "edge_tts": "edge-tts",
            "pygame": "pygame",
            "speech_recognition": "SpeechRecognition",
        }

        missing_modules = []

        for module, package in required_modules.items():
            try:
                __import__(module)
                logger.debug(f"Modulo {module} trovato")
            except ImportError:
                missing_modules.append(package)
                logger.error(f"Modulo {module} non trovato")

        # Verifica dipendenze vocali (opzionali)
        missing_voice_modules = []
        for module, package in voice_modules.items():
            try:
                __import__(module)
                logger.debug(f"Modulo vocale {module} trovato")
            except ImportError:
                missing_voice_modules.append(package)
                logger.warning(
                    f"Modulo vocale {module} non trovato - assistente vocale disabilitato"
                )

        if missing_modules:
            error_msg = f"""
DIPENDENZE MANCANTI
==================
Moduli non trovati: {', '.join(missing_modules)}

SOLUZIONI:
1. Installa tutte le dipendenze:
   pip install -r requirements.txt

2. Oppure installa manualmente:
   pip install {' '.join(missing_modules)}

3. Se usi conda:
   conda install {' '.join(missing_modules)}
            """
            logger.error(error_msg)

            # Mostra messaggio GUI se possibile
            try:
                temp_root = tk.Tk()
                temp_root.withdraw()
                messagebox.showerror("Dipendenze Mancanti", error_msg)
                temp_root.destroy()
            except Exception as e:
                logger.warning(f"Impossibile mostrare messaggio GUI: {e}")

            return False

        # Informazioni sui moduli vocali opzionali
        if missing_voice_modules:
            logger.info(
                f"Moduli vocali non disponibili: {', '.join(missing_voice_modules)}"
            )
            logger.info(
                "Assistente vocale disabilitato. Installa: pip install edge-tts pygame SpeechRecognition pyaudio"
            )
        else:
            logger.info(
                "Tutti i moduli vocali sono disponibili - Assistente vocale abilitato"
            )

        logger.info("Tutte le dipendenze sono installate correttamente")
        return True

    def import_modules(self):
        """Importa i moduli dell'applicazione."""
        try:
            from src.canvas_app import CanvasApp

            self.CanvasApp = CanvasApp
            logger.info("Moduli dell'applicazione importati con successo")

            # Importa assistente vocale se disponibile
            self.init_voice_assistant()

            return True
        except ImportError as e:
            error_msg = f"Errore nell'importazione dei moduli dell'applicazione: {e}"
            logger.error(error_msg)

            try:
                temp_root = tk.Tk()
                temp_root.withdraw()
                messagebox.showerror("Errore di Importazione", error_msg)
                temp_root.destroy()
            except:
                pass

            return False

    def init_voice_assistant(self):
        """Inizializza l'assistente vocale se le dipendenze sono disponibili."""
        try:
            # Verifica se le dipendenze vocali sono disponibili
            import edge_tts
            import pygame
            import speech_recognition as sr

            # Importa l'assistente vocale
            from voice.isabella_voice_assistant import IsabellaVoiceAssistant

            # Inizializza l'assistente
            self.voice_assistant = IsabellaVoiceAssistant()
            self.voice_enabled = True
            logger.info("Assistente vocale Isabella inizializzato con successo")

        except ImportError as e:
            logger.info(f"Assistente vocale non disponibile: {e}")
            self.voice_enabled = False
        except Exception as e:
            logger.warning(f"Errore nell'inizializzazione dell'assistente vocale: {e}")
            self.voice_enabled = False

    async def play_welcome_message(self):
        """Riproduce il messaggio di benvenuto vocale."""
        if self.voice_assistant and self.voice_enabled:
            try:
                await self.voice_assistant.speak_startup("Kimerika 2.0")
                logger.info("Messaggio di benvenuto vocale riprodotto")
            except Exception as e:
                logger.warning(f"Errore nella riproduzione messaggio vocale: {e}")

    def create_gui(self):
        """Crea e configura l'interfaccia grafica."""
        try:
            # Importa layout manager per geometria finestra
            from src.layout_manager import layout_manager

            # Crea la finestra principale
            self.root = tk.Tk()
            self.root.title("Facial Analysis Application v2.0")

            # Ripristina geometria salvata PRIMA di creare l'app
            try:
                from src.layout_manager import layout_manager

                print("\n🔄 Caricamento configurazione layout all'avvio...")
                saved_geometry = layout_manager.get_window_geometry()
                self.root.geometry(saved_geometry)
                logger.info(f"Geometria finestra ripristinata: {saved_geometry}")

                # Mostra status della configurazione
                status = layout_manager.get_config_status()
                print(f"📊 Status configurazione: {status}")

            except Exception as e:
                # Fallback se non c'è geometria salvata
                self.root.geometry("1600x1000")
                logger.warning(f"Impossibile ripristinare geometria, uso default: {e}")

                # Crea configurazione default se non esiste
                try:
                    from src.layout_manager import layout_manager

                    layout_manager.save_config()  # Crea file con valori default
                except Exception as create_e:
                    logger.warning(
                        f"Impossibile creare configurazione default: {create_e}"
                    )

            self.root.minsize(1400, 900)

            # Configura il comportamento di chiusura
            self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

            # NUOVO: Imposta finestra a schermo intero all'avvio
            self.root.state("zoomed")  # Windows: massimizza la finestra
            # Alternativa per Linux/macOS: self.root.attributes('-zoomed', True)
            logger.info("Finestra impostata a schermo intero")

            # Gestisce l'interruzione da tastiera nella GUI
            self.root.bind("<Control-c>", lambda e: self.graceful_shutdown())

            # Configura icona (se disponibile)
            try:
                # self.root.iconbitmap('assets/icon.ico')  # Decommentare se hai un'icona
                pass
            except Exception as e:
                logger.debug(f"Icona non disponibile: {e}")

            # Crea l'applicazione principale
            self.app = self.CanvasApp(self.root)

            logger.info("Interfaccia grafica creata con successo")
            return True

        except Exception as e:
            error_msg = f"Errore nella creazione dell'interfaccia grafica: {e}"
            logger.error(error_msg)

            try:
                messagebox.showerror("Errore GUI", error_msg)
            except:
                pass

            return False

    def on_window_close(self):
        """Gestisce la chiusura della finestra."""
        logger.info("Richiesta chiusura finestra")

        # Salva geometria finestra E layout pannelli prima di chiudere
        try:
            if self.root and self.root.winfo_exists():
                from src.layout_manager import layout_manager

                print("\n🔄 Salvataggio configurazione alla chiusura...")

                current_geometry = self.root.geometry()
                layout_manager.save_window_geometry(current_geometry)
                logger.info(f"Geometria finestra salvata: {current_geometry}")

                # Salva anche layout pannelli se l'app esiste
                if (
                    hasattr(self, "app")
                    and self.app
                    and hasattr(self.app, "on_closing_with_layout_save")
                ):
                    # Chiama solo la parte di salvataggio layout, non la distruzione
                    try:
                        self.app._save_layout_only()
                        logger.info("Layout pannelli salvato")
                    except Exception as layout_e:
                        logger.warning(
                            f"Errore salvataggio layout pannelli: {layout_e}"
                        )

                # Test di validazione finale
                try:
                    if layout_manager.validate_and_test_config():
                        print("✅ Configurazione validata e salvata correttamente")
                    else:
                        print("⚠️ Problemi nella validazione configurazione")

                    # Mostra stato finale
                    status = layout_manager.get_config_status()
                    print(f"📊 Status finale: {status}")

                except Exception as test_e:
                    logger.warning(f"Errore test validazione: {test_e}")

        except Exception as e:
            logger.warning(f"Errore salvataggio geometria: {e}")

        self.graceful_shutdown()

    def graceful_shutdown(self):
        """Chiusura controllata dell'applicazione."""
        if not self.running:
            return

        logger.info("Avvio procedura di chiusura...")
        self.running = False

        try:
            # Cleanup assistente vocale
            if self.voice_assistant and self.voice_enabled:
                try:
                    # Messaggio di arrivederci vocale
                    import asyncio

                    def goodbye_message():
                        try:
                            asyncio.run(self.voice_assistant.speak("goodbye"))
                        except:
                            pass

                    import threading

                    goodbye_thread = threading.Thread(
                        target=goodbye_message, daemon=True
                    )
                    goodbye_thread.start()
                    goodbye_thread.join(timeout=2)  # Aspetta max 2 secondi

                    # Cleanup assistente
                    if hasattr(self.voice_assistant, "cleanup"):
                        self.voice_assistant.cleanup()
                    logger.info("Assistente vocale chiuso")
                except Exception as e:
                    logger.warning(f"Errore chiusura assistente vocale: {e}")

            if self.app:
                # Se l'app ha metodi di cleanup, chiamali qui
                if hasattr(self.app, "cleanup"):
                    self.app.cleanup()

            if self.root:
                self.root.quit()
                self.root.destroy()

        except Exception as e:
            logger.error(f"Errore durante la chiusura: {e}")

        logger.info("Applicazione chiusa correttamente")
        sys.exit(0)

    def print_welcome_message(self):
        """Stampa il messaggio di benvenuto e le istruzioni."""
        welcome_msg = """
========================================
  FACIAL ANALYSIS APPLICATION v2.0
========================================

FUNZIONALITÀ DISPONIBILI:
• Cattura da webcam: Menu Video > Avvia Webcam
• Analisi file video: Menu File > Carica Video  
• Caricamento immagini: Menu File > Carica Immagine
• Strumenti di misurazione: Pannello laterale
• Canvas interattivo: Click per selezionare punti
• Rilevamento automatico volti con MediaPipe

CONTROLLI:
• Ctrl+C: Chiudi applicazione
• ESC: Annulla operazione corrente
• Click destro: Menu contestuale (se disponibile)

LOG: Le attività vengono salvate in 'facial_analysis.log'

Per supporto, controlla la documentazione nel README.md
========================================
        """
        print(welcome_msg)
        logger.info("Applicazione avviata - Messaggio di benvenuto mostrato")

    def run(self):
        """Metodo principale per avviare l'applicazione."""
        try:
            logger.info("=== AVVIO FACIAL ANALYSIS APPLICATION ===")

            # Configura gestori di segnale
            self.setup_signal_handlers()

            # Verifica dipendenze
            logger.info("Verifica dipendenze...")
            if not self.check_dependencies():
                logger.error("Dipendenze mancanti. Uscita.")
                return 1

            # Importa moduli
            logger.info("Importazione moduli...")
            if not self.import_modules():
                logger.error("Errore importazione moduli. Uscita.")
                return 1

            # Crea GUI
            logger.info("Creazione interfaccia grafica...")
            if not self.create_gui():
                logger.error("Errore creazione GUI. Uscita.")
                return 1

            # Mostra messaggio di benvenuto
            self.print_welcome_message()

            # Riproduce messaggio di benvenuto vocale se disponibile
            if self.voice_enabled and self.voice_assistant:
                try:
                    import asyncio

                    # Avvia il messaggio vocale in background
                    def play_welcome():
                        try:
                            asyncio.run(self.play_welcome_message())
                        except Exception as e:
                            logger.warning(f"Errore messaggio vocale: {e}")

                    import threading

                    threading.Thread(target=play_welcome, daemon=True).start()
                except Exception as e:
                    logger.warning(f"Errore avvio messaggio vocale: {e}")

            # Avvia loop principale
            self.running = True
            logger.info("Avvio loop principale...")

            try:
                self.root.mainloop()
            except KeyboardInterrupt:
                logger.info("Interruzione da tastiera ricevuta")
                self.graceful_shutdown()

            return 0

        except Exception as e:
            error_msg = f"Errore critico durante l'avvio: {e}"
            logger.error(error_msg, exc_info=True)

            try:
                messagebox.showerror("Errore Critico", error_msg)
            except:
                pass

            return 1


def main():
    """Funzione principale - entry point dell'applicazione."""
    app = FacialAnalysisApp()
    exit_code = app.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
