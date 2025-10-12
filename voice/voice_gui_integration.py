"""
🎨 VOICE GUI INTEGRATION - Integrazione GUI Assistente Vocale
============================================================

Modulo di integrazione GUI per Isabella Voice Assistant.
Separa completamente la logica vocale dall'interfaccia principale.

GARANTISCE:
- ✅ Interfaccia identica al 100%
- ✅ Stessi pulsanti, stesso layout
- ✅ Retrocompatibilità totale
- ✅ Zero modifiche visibili all'utente

Autore: AI Assistant
Data: 5 Ottobre 2025
Versione: 1.0.0
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Callable, Dict, Optional
import threading
import asyncio
import logging
import os
import json
import time

logger = logging.getLogger("VoiceGUIIntegration")

# Sistema di query intelligenti rimosso per semplificazione
logger.info("🎯 Voice GUI Integration - modalità semplificata")


class VoiceAssistantGUI:
    """
    Gestisce SOLO l'interfaccia grafica dell'assistente vocale.
    Mantiene identica l'interfaccia utente esistente.
    """

    def __init__(self, parent_frame: ttk.Frame, voice_assistant):
        """
        Inizializza GUI assistente vocale

        Args:
            parent_frame: Frame tkinter genitore
            voice_assistant: Istanza IsabellaVoiceAssistant
        """
        self.parent = parent_frame
        self.assistant = voice_assistant
        self.voice_enabled = True  # Microfono sempre attivo

        # Variabili GUI - microfono attivo, assistente in attesa
        self.voice_enabled_var = tk.BooleanVar(value=True)
        self.voice_listening_var = tk.BooleanVar(value=True)

        # Widget references
        self.status_label = None
        self.toggle_btn = None
        self.test_btn = None
        self.commands_btn = None

        # Crea interfaccia
        self._setup_gui()
        
        # Avvia solo il microfono (assistente si attiverà con keywords)
        self._start_microphone_only()

        logger.info("✅ VoiceAssistantGUI inizializzato")

    def _setup_gui(self):
        """Crea interfaccia IDENTICA a quella esistente"""
        # === FRAME PRINCIPALE (identico) ===
        voice_frame = ttk.LabelFrame(
            self.parent,
            text="🎤 ASSISTENTE VOCALE ISABELLA",
            padding=10,
            bootstyle="info",
        )
        voice_frame.pack(fill=tk.X, pady=(0, 10))

        # === STATUS (identico) ===
        status_frame = ttk.Frame(voice_frame)
        status_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(status_frame, text="Stato:", font=("Arial", 9, "bold")).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.status_label = ttk.Label(
            status_frame, text="⚫ Disattivato", bootstyle="secondary"
        )
        self.status_label.pack(side=tk.LEFT)

        # === CONTROLLO PRINCIPALE (identico) ===
        main_control_frame = ttk.Frame(voice_frame)
        main_control_frame.pack(fill=tk.X, pady=5)
        main_control_frame.columnconfigure(0, weight=1)

        self.toggle_btn = ttk.Button(
            main_control_frame,
            text="ℹ️ Info Assistente",
            command=self.toggle_assistant,
            bootstyle="info",
        )
        self.toggle_btn.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        # === CONTROLLI SECONDARI (identici) ===
        controls_frame = ttk.Frame(voice_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.columnconfigure(1, weight=1)

        self.test_btn = ttk.Button(
            controls_frame,
            text="🔊 Test Audio",
            command=self.test_audio,
            state="disabled",
            bootstyle="info-outline",
        )
        self.test_btn.grid(row=0, column=0, sticky="ew", padx=(2, 1))

        self.commands_btn = ttk.Button(
            controls_frame,
            text="📋 Comandi",
            command=self.show_commands,
            state="disabled",
            bootstyle="secondary-outline",
        )
        self.commands_btn.grid(row=0, column=1, sticky="ew", padx=(1, 2))

        # === INFO COMANDI RAPIDI (identica) ===
        commands_frame = ttk.LabelFrame(
            voice_frame, text="⚡ Comandi Rapidi", padding=5
        )
        commands_frame.pack(fill=tk.X, pady=(5, 0))

        commands_text = (
            "• 🎤 MICROFONO SEMPRE ATTIVO\n"
            "• 'Hey Symmetra' - Attiva assistente\n"
            "• 'Analizza volto' - Avvia analisi\n"
            "• 'Salva risultati' - Salva dati\n"
            "• 'Aiuto' - Lista completa comandi"
        )
        ttk.Label(
            commands_frame, text=commands_text, font=("Arial", 8), justify=tk.LEFT
        ).pack(anchor="w")

    def toggle_assistant(self):
        """MICROFONO SEMPRE ATTIVO - Solo info status, NO toggle"""
        if not self.assistant:
            from tkinter import messagebox
            messagebox.showinfo(
                "Assistente Vocale", 
                "Microfono sempre attivo.\n\nUsa 'Hey Symmetra' per attivare l'assistente!"
            )
            return

        # Solo feedback informativo - microfono rimane sempre attivo
        from tkinter import messagebox
        messagebox.showinfo(
            "Stato Assistente",
            "🎤 MICROFONO SEMPRE ATTIVO\n\n"
            "L'assistente risponde solo alla parola chiave:\n"
            "'Hey Symmetra' o 'Ciao Symmetra'\n\n"
            "Nessun toggle necessario!"
        )
        logger.info("ℹ️ Info stato assistente mostrata - microfono rimane sempre attivo")

    def test_audio(self):
        """Test audio - STESSA LOGICA"""
        if not self.assistant:
            return

        def test_speak():
            try:
                asyncio.run(
                    self.assistant.speak(
                        "Test audio assistente vocale Isabella. "
                        "Se senti questo messaggio, l'audio funziona correttamente."
                    )
                )
            except Exception as e:
                logger.error(f"Errore test vocale: {e}")

        threading.Thread(target=test_speak, daemon=True).start()
        logger.info("🔊 Test audio avviato")

    def _start_microphone_only(self):
        """Configura GUI per microfono già SEMPRE ATTIVO"""
        if not self.assistant:
            logger.warning("❌ Assistente non disponibile")
            return
            
        try:
            # Il microfono è già attivo da main.py - aggiorniamo solo la GUI
            
            # Il microfono verrà attivato con delay da main.py - NO fallback automatico
            logger.info("ℹ️ Configurazione GUI microfono - attesa attivazione delay main.py...")
            
            # Aggiorna GUI per riflettere stato SEMPRE ATTIVO
            self.toggle_btn.config(text="ℹ️ Info Assistente", bootstyle="info")
            self.status_label.config(text="🎤 SEMPRE ATTIVO - Usa 'Hey Symmetra'", bootstyle="success")
            self.test_btn.config(state="normal")
            self.commands_btn.config(state="normal")
            
            # Forza variabili sempre attive (no toggle)
            self.voice_enabled_var.set(True)
            self.voice_listening_var.set(True)
            self.voice_enabled = True
            
            logger.info("✅ GUI configurata per microfono SEMPRE ATTIVO")
            
        except Exception as e:
            logger.error(f"❌ Errore configurazione GUI microfono: {e}")
            # Anche in caso di errore, mostra stato attivo
            self.status_label.config(text="⚠️ Errore microfono", bootstyle="danger")

    def show_commands(self):
        """Mostra comandi - STESSA FINESTRA IDENTICA"""
        commands_window = tk.Toplevel()
        commands_window.title("Comandi Vocali Disponibili")
        commands_window.geometry("600x500")

        # Frame principale con scrollbar
        main_frame = ttk.Frame(commands_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(main_frame, bg="#1e1e1e")
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Titolo
        ttk.Label(
            scrollable_frame,
            text="🎤 Comandi Vocali Isabella",
            font=("Arial", 14, "bold"),
        ).pack(pady=10)

        # STESSA LISTA COMANDI COMPLETA
        commands_info = """
ATTIVAZIONE:
• "Hey Symmetra" / "Ciao Symmetra" - Attiva assistente per comando

📊 ANALISI FACCIALE:
• "Analizza volto" / "Avvia analisi" / "Inizia scansione" / "Analizza faccia"
• "Rileva landmarks" / "Trova punti" / "Analizza landmarks"
• "Punti verdi" / "Rileva punti verdi" / "Trova sopracciglia"

📂 CARICAMENTO FILE:
• "Carica immagine" / "Apri immagine" / "Carica foto" / "Importa immagine"
• "Avvia webcam" / "Avvia camera" / "Attiva webcam" / "Accendi camera"
• "Carica video" / "Apri video" / "Importa video"

📏 MISURAZIONE E SIMMETRIA:
• "Calcola misura" / "Misura distanza" / "Effettua misurazione"
• "Asse di simmetria" / "Asse" / "Linea centrale" / "Centro faccia"
• "Cancella selezioni" / "Pulisci selezioni" / "Resetta selezioni"

🎨 INTERFACCIA:
• "Zoom" / "Ingrandisci" / "Zoom in"
• "Zoom out" / "Riduci zoom" / "Zoom indietro"
• "Cancella disegni" / "Pulisci canvas" / "Reset canvas"

💾 SALVATAGGIO:
• "Salva risultati" / "Salva immagine" / "Esporta risultati"

🧠 DOMANDE INTELLIGENTI (Dopo l'analisi):
• "Qual è la distanza tra gli occhi?"
• "Il mio viso è simmetrico?" / "Sono simmetrico?"
• "Quale sopracciglio è più alto?"
• "Il punto SC è più alto del punto RC?"
• "Quanto è simmetrico questo viso?"
• "Sono bello/bella?" / "Qual è il mio punteggio?"
• "Hai i dati?" / "È disponibile l'analisi?"
• "Dimmi i risultati" / "Cosa dice l'analisi?"

⚙️ SISTEMA:
• "Aiuto" / "Comandi disponibili" - Mostra questa lista
• "Stato" / "Status" / "Come va" - Informazioni sistema
• "Zitto" / "Silenzio" / "Muto" - Silenzia voce
• "Riattiva voce" / "Torna a parlare" - Riattiva voce

💡 SUGGERIMENTI:
✓ Parla chiaramente dopo "Hey Symmetra"
✓ Attendi il segnale di conferma "Ti ascolto!"
✓ Usa frasi naturali per le domande intelligenti
✓ Esegui prima "Punti verdi" per avere dati da analizzare
        """

        ttk.Label(
            scrollable_frame, text=commands_info, font=("Arial", 10), justify=tk.LEFT
        ).pack(anchor="w", padx=20, pady=10)

        ttk.Button(
            scrollable_frame,
            text="✓ Chiudi",
            command=commands_window.destroy,
            bootstyle="primary",
        ).pack(pady=20)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


class VoiceCommandsIntegration:
    """
    Collega comandi vocali con funzioni dell'applicazione.
    Gestisce la registrazione e l'esecuzione dei comandi.
    """

    def __init__(self, voice_assistant, canvas_app_instance=None, app_callbacks: Dict[str, Callable] = None):
        """
        Inizializza integrazione comandi

        Args:
            voice_assistant: Istanza IsabellaVoiceAssistant
            canvas_app_instance: Istanza CanvasApp per risoluzione automatica metodi
            app_callbacks: Dict {nome_callback: funzione} (deprecato)
        """
        self.assistant = voice_assistant
        self.canvas_app = canvas_app_instance
        self.callbacks = app_callbacks or {}
        
        # Sistema semplificato senza query intelligenti
        self.query_integration = None
        logger.info("🎯 Voice Command Handler inizializzato in modalità semplificata")
        
        if self.canvas_app:
            logger.info("🎯 Modalità risoluzione automatica metodi attivata")
        else:
            logger.warning("⚠️ Modalità callback legacy (usa canvas_app_instance invece)")
            
        self._register_commands()

        callback_count = len(self.callbacks) if not self.canvas_app else "risoluzione automatica"
        logger.info(f"✅ VoiceCommandsIntegration: {callback_count} callbacks")

    def update_measurement_data(self, measurement_data: Dict):
        """Aggiorna i dati di misurazione per le query intelligenti"""
        if self.query_integration and hasattr(self.query_integration, 'query_handler'):
            try:
                self.query_integration.query_handler.analyzer.update_data(measurement_data)
                logger.info(f"📊 Dati misurazione aggiornati per query intelligenti: {len(measurement_data)} valori")
            except Exception as e:
                logger.error(f"❌ Errore aggiornamento dati query: {e}")

    def _register_commands(self):
        """Registra tutti i comandi caricandoli dal file di configurazione"""
        
        # Carica configurazione comandi da JSON
        config_path = os.path.join(os.path.dirname(__file__), "isabella_voice_config.json")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            commands = config.get("commands", [])
            logger.info(f"📋 Caricamento {len(commands)} comandi da configurazione JSON")
            
            for cmd_config in commands:
                if not cmd_config.get("enabled", True):
                    logger.debug(f"⏭️ Comando '{cmd_config.get('name')}' disabilitato")
                    continue
                    
                # Risolvi il metodo automaticamente
                action = cmd_config.get("action", {})
                action_type = action.get("type", "gui")
                method_name = action.get("function")
                
                if action_type == "intelligent":
                    # Comando per query intelligenti - sarà gestito da VoiceQueryIntegration
                    # Non registriamo nulla qui, il sistema è già configurato
                    logger.info(f"🧠 Comando query intelligenti riconosciuto: '{cmd_config.get('name')}'")
                    continue
                elif method_name:
                    # Cerca il metodo nell'istanza canvas_app
                    method = self._resolve_method(method_name)
                    
                    if method:
                        # Registra il comando con il metodo risolto
                        self.assistant.add_command(
                            keywords=cmd_config.get("patterns", []),
                            action=cmd_config.get("name", "unnamed_command"),
                            handler=lambda text, cmd, m=method: self._safe_method_call(m, method_name),
                            confirmation=cmd_config.get("confirmation", "Comando eseguito"),
                        )
                        logger.info(f"✅ Comando registrato: '{cmd_config.get('name')}' -> {method_name}")
                    else:
                        logger.warning(f"⚠️ Metodo '{method_name}' non trovato per comando '{cmd_config.get('name')}'")
                else:
                    logger.warning(f"⚠️ Nessun metodo specificato per comando '{cmd_config.get('name')}'")
                        
        except FileNotFoundError:
            logger.error(f"❌ File configurazione non trovato: {config_path}")
            logger.error("❌ Impossibile continuare senza configurazione comandi")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Errore parsing JSON configurazione: {e}")
            logger.error("❌ Verifica sintassi file isabella_voice_config.json")
        except Exception as e:
            logger.error(f"❌ Errore caricamento comandi: {e}")
    
    def _resolve_method(self, method_name: str):
        """
        Risolve un metodo dall'istanza canvas_app o dalle callback legacy
        
        Args:
            method_name: Nome del metodo da cercare
            
        Returns:
            Callable o None se non trovato
        """
        # Prima prova nell'istanza canvas_app (nuovo sistema)
        if self.canvas_app and hasattr(self.canvas_app, method_name):
            return getattr(self.canvas_app, method_name)
        
        # Fallback alle callback legacy
        if method_name in self.callbacks:
            return self.callbacks[method_name]
        
        # Metodi speciali di sistema
        system_methods = {
            "show_help": lambda: logger.info("🎤 Comandi vocali: analizza volto, carica immagine, avvia webcam, calcola asse, rileva landmarks, punti verdi, zoom, salva, cancella"),
            "show_system_help": lambda: logger.info("🔧 Sistema: aiuto, stato, esci, zitto, riattiva voce"),
            "show_system_status": lambda: logger.info("✅ Sistema attivo e funzionante"),
            "exit_assistant": lambda: logger.info("👋 Uscita assistente (disabilitata per sicurezza)"),
            "mute_voice": self._mute_voice if hasattr(self, '_mute_voice') else lambda: logger.info("🔇 Voce silenziata"),
            "unmute_voice": self._unmute_voice if hasattr(self, '_unmute_voice') else lambda: logger.info("🔊 Voce riattivata")
        }
        
        if method_name in system_methods:
            return system_methods[method_name]
        
        # Mappature per metodi con nomi diversi o mancanti
        method_mappings = {
            'start_analysis': 'detect_landmarks',
            'save_results': 'save_image',
            'calculate': 'calculate_measurement',
            'clear_selections': 'clear_measurement_overlays',
        }
        
        # Prova con il nome mappato
        mapped_name = method_mappings.get(method_name)
        if mapped_name and self.canvas_app and hasattr(self.canvas_app, mapped_name):
            return getattr(self.canvas_app, mapped_name)
        
        return None
    
    def _safe_method_call(self, method, method_name: str):
        """
        Esegue un metodo in modo sicuro con gestione errori
        
        Args:
            method: Metodo da chiamare
            method_name: Nome del metodo (per logging)
        """
        try:
            if callable(method):
                method()
                logger.debug(f"✅ Metodo eseguito: {method_name}")
            else:
                logger.error(f"❌ {method_name} non è callable")
        except Exception as e:
            logger.error(f"❌ Errore esecuzione metodo '{method_name}': {e}")

    def _safe_callback(self, callback_name: str):
        """
        Esegue callback in modo sicuro con gestione errori

        Args:
            callback_name: Nome della callback da eseguire
        """
        callback = self.callbacks.get(callback_name)
        if callback:
            try:
                callback()
                logger.debug(f"✅ Callback eseguita: {callback_name}")
            except Exception as e:
                logger.error(f"❌ Errore callback '{callback_name}': {e}")
        else:
            logger.warning(f"⚠️ Callback non trovata: {callback_name}")

    def speak_feedback(self, message: str):
        """
        Sistema TTS ROBUSTO - Previene troncamenti e sovrapposizioni

        Args:
            message: Messaggio da pronunciare
        """
        # Usa sistema TTS integrato (niente più RobustTTSManager)
        try:
            if hasattr(self.assistant, 'speak_complete'):
                asyncio.run(self.assistant.speak_complete(message))
            else:
                asyncio.run(self.assistant.speak(message, wait_for_completion=True))
        except Exception as e:
            logger.error(f"❌ Errore TTS integrato: {e}")


# === SISTEMA TTS UNIFICATO ===
# Rimosso RobustTTSManager - ora usiamo solo il sistema TTS integrato nell'assistente vocale
# per evitare conflitti threading che causavano attivazione/disattivazione del microfono

# === FUNZIONI DI UTILITÀ ===


def setup_voice_integration(
    parent_frame: ttk.Frame, voice_assistant, app_callbacks: Dict[str, Callable]
) -> tuple:
    """
    Setup completo integrazione assistente vocale

    Args:
        parent_frame: Frame tkinter per GUI
        voice_assistant: Istanza IsabellaVoiceAssistant
        app_callbacks: Dict callbacks applicazione

    Returns:
        Tupla (voice_gui, voice_commands)
    """
    try:
        voice_gui = VoiceAssistantGUI(parent_frame, voice_assistant)
        voice_commands = VoiceCommandsIntegration(voice_assistant, app_callbacks)

        logger.info("✅ Integrazione assistente vocale completata")
        return voice_gui, voice_commands

    except Exception as e:
        logger.error(f"❌ Errore setup integrazione vocale: {e}")
        return None, None
