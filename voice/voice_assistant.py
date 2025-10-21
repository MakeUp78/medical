"""
Assistente Vocale Isabella - Sistema Semplificato
Gestisce riconoscimento vocale e sintesi vocale per Kimerika 2.0
"""

import speech_recognition as sr
import edge_tts
import pygame
import asyncio
import json
import threading
import time
import tkinter as tk
from tkinter import ttk
import tempfile
import os

class IsabellaVoiceAssistant:
    def __init__(self, config_path="voice/voice_config.json"):
        """Inizializza l'assistente vocale Isabella"""
        self.config_path = config_path
        self.config = self.load_config()
        
        # Stato dell'assistente
        self.is_active = False
        self.is_listening = False
        self.is_muted = False
        
        # Setup riconoscimento vocale
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Setup sintesi vocale con edge-tts e pygame (ORIGINALE)
        pygame.mixer.init()
        self.tts_voice = self.config.get("tts_voice", "it-IT-IsabellaNeural")
        
        # Calibrazione microfono
        self.calibrate_microphone()
        
        # GUI e funzioni dell'app
        self.canvas_app = None
        self.gui_frame = None
        
    def load_config(self):
        """Carica la configurazione da file JSON"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"File config non trovato: {self.config_path}")
            return self.get_default_config()
        except Exception as e:
            print(f"Errore caricamento config: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """Configurazione di default"""
        return {
            "activation_keywords": ["simmètra", "simmetra", "symmetra"],
            "language": "it-IT",
            "tts_voice": "it-IT-IsabellaNeural",
            "commands": []
        }
    
    async def _generate_speech_async(self, text):
        """Genera audio usando edge-tts in modo asincrono (ORIGINALE)"""
        try:
            communicate = edge_tts.Communicate(text, self.tts_voice)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            await communicate.save(temp_file.name)
            return temp_file.name
        except Exception as e:
            print(f"Errore generazione TTS: {e}")
            return None
    
    def calibrate_microphone(self):
        """Calibra il microfono per il rumore di fondo"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"Errore calibrazione microfono: {e}")
    
    def speak(self, text):
        """Pronuncia il testo usando edge-tts e pygame"""
        if not self.is_muted and text.strip():
            try:
                # Esegui TTS in thread separato per non bloccare
                threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()
            except Exception as e:
                print(f"Errore TTS: {e}")
    
    def _speak_thread(self, text):
        """Esegue TTS in thread separato (ORIGINALE edge-tts + pygame)"""
        try:
            # Crea nuovo event loop per questo thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Genera file audio con edge-tts
            audio_file = loop.run_until_complete(self._generate_speech_async(text))
            
            if audio_file:
                # Riproduci con pygame
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                
                # Aspetta che finisca
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                
                # Pulisci file temporaneo
                try:
                    os.unlink(audio_file)
                except:
                    pass
            else:
                # Fallback se edge-tts non funziona
                print(f"🔊 Isabella: {text}")
                    
            loop.close()
        except Exception as e:
            print(f"Errore thread TTS: {e}")
            print(f"🔊 Isabella: {text}")
    
    def listen_for_activation(self):
        """Ascolta continuamente per parole di attivazione"""
        while self.is_active:
            try:
                with self.microphone as source:
                    # Timeout appropriato per frasi complete
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                
                text = self.recognizer.recognize_google(audio, language=self.config["language"])
                text_lower = text.lower()
                print(f"🎤 Riconosciuto: '{text}' -> '{text_lower}'")
                
                # Controlla parole di attivazione
                for keyword in self.config["activation_keywords"]:
                    if keyword in text_lower:
                        # Rimuovi parola di attivazione dal comando
                        command = text_lower.replace(keyword, "").strip()
                        print(f"✅ Attivazione rilevata con '{keyword}', comando estratto: '{command}'")
                        if command:
                            self.process_command(command)
                        else:
                            self.speak("Ti ascolto! Dimmi cosa devo fare.")
                        break
                        
            except sr.WaitTimeoutError:
                # Timeout normale, continua ad ascoltare
                continue
            except sr.UnknownValueError:
                # Non ha capito, continua ad ascoltare
                continue
            except Exception as e:
                print(f"Errore ascolto: {e}")
                time.sleep(1)
    
    def process_command(self, command_text):
        """Elabora un comando vocale"""
        command_text = command_text.strip().lower()
        print(f"🔍 Elaborazione comando: '{command_text}'")
        
        # Raccoglie tutti i possibili match e li ordina per specificità (pattern più lungo prima)
        all_matches = []
        for cmd in self.config.get("commands", []):
            if not cmd.get("enabled", True):
                continue
                
            for pattern in cmd.get("patterns", []):
                if pattern.lower() in command_text:
                    all_matches.append((len(pattern), pattern, cmd))
                    print(f"  ✅ Match trovato: '{pattern}' -> {cmd['name']}")
        
        # Ordina per lunghezza del pattern (più lungo = più specifico)
        if all_matches:
            all_matches.sort(key=lambda x: -x[0])  # Dal più lungo al più corto
            selected_cmd = all_matches[0][2]
            print(f"🎯 Comando selezionato: {selected_cmd['name']}")
            self.execute_command(selected_cmd)  # Prendi il match più specifico
            return
        
        # Comando non trovato
        print(f"❌ Nessun comando trovato per: '{command_text}'")
        self.speak("Non ho riconosciuto il comando. Prova a ripetere.")
    
    def execute_command(self, command):
        """Esegue un comando"""
        try:
            function_name = command["action"]["function"]
            confirmation = command.get("confirmation", "")
            
            if confirmation:
                self.speak(confirmation)
            
            # Esegui la funzione se disponibile
            if self.canvas_app and hasattr(self.canvas_app, function_name):
                func = getattr(self.canvas_app, function_name)
                func()
            else:
                print(f"Funzione non trovata: {function_name}")
                
        except Exception as e:
            print(f"Errore esecuzione comando: {e}")
            self.speak("Si è verificato un errore durante l'esecuzione del comando.")
    
    def start(self):
        """Avvia l'assistente vocale"""
        if not self.is_active:
            self.is_active = True
            self.speak("Assistente vocale Simmètra attivato.")
            
            # Avvia thread per ascolto in background
            self.listen_thread = threading.Thread(target=self.listen_for_activation, daemon=True)
            self.listen_thread.start()
            
            # Aggiorna GUI immediatamente
            self.update_gui_status()
    
    def stop(self):
        """Ferma l'assistente vocale"""
        if self.is_active:
            self.is_active = False
            self.speak("Assistente vocale disattivato.")
            
            # Aggiorna GUI immediatamente
            self.update_gui_status()
    
    def toggle(self):
        """Attiva/disattiva l'assistente"""
        if self.is_active:
            self.stop()
        else:
            self.start()
    
    def mute(self):
        """Silenzia la voce"""
        self.is_muted = True
    
    def unmute(self):
        """Riattiva la voce"""
        self.is_muted = False
        self.speak("Voce riattivata")
    
    def start_listening(self, activate_immediately=True):
        """Avvia l'ascolto (compatibilità con vecchio sistema)"""
        # Non fare niente - lasciare il controllo all'utente tramite GUI
        print("ℹ️ Assistente vocale pronto. Usa i pulsanti nell'interfaccia per attivarlo.")
    
    def get_message(self, message_type):
        """Ottiene un messaggio dalla configurazione (compatibilità)"""
        messages = {
            "welcome_user": "Benvenuto in Kimerika eiai! Io sono Simmètra e ti assisterò nella progettazione di questa dermopigmentazione sopraccigliare",
            "goodbye": "Arrivederci! Assistente vocale disattivato."
        }
        return messages.get(message_type, "")
    
    async def speak_complete(self, text):
        """Parla e attende completamento (compatibilità asincrona)"""
        if not self.is_muted and text.strip():
            try:
                # Genera file audio con edge-tts
                audio_file = await self._generate_speech_async(text)
                
                if audio_file:
                    # Riproduci con pygame e aspetta
                    pygame.mixer.music.load(audio_file)
                    pygame.mixer.music.play()
                    
                    # Aspetta che finisca
                    while pygame.mixer.music.get_busy():
                        await asyncio.sleep(0.1)
                    
                    # Pulisci file temporaneo
                    try:
                        os.unlink(audio_file)
                    except:
                        pass
                else:
                    # Fallback se edge-tts non funziona
                    print(f"🔊 Isabella: {text}")
                        
            except Exception as e:
                print(f"Errore speak_complete: {e}")
                print(f"🔊 Isabella: {text}")
    
    def set_canvas_app(self, canvas_app):
        """Imposta il riferimento all'app principale"""
        self.canvas_app = canvas_app
    
    def create_gui(self, parent):
        """Crea l'interfaccia grafica semplice per l'assistente"""
        self.gui_frame = ttk.LabelFrame(parent, text="Assistente Vocale Isabella", padding="10")
        
        # Pulsante on/off
        self.toggle_btn = ttk.Button(
            self.gui_frame,
            text="Attiva Assistente",
            command=self.toggle
        )
        self.toggle_btn.pack(pady=5)
        
        # Indicatore stato
        self.status_label = ttk.Label(self.gui_frame, text="Spento", foreground="red")
        self.status_label.pack(pady=2)
        
        # Pulsante mute
        self.mute_btn = ttk.Button(
            self.gui_frame,
            text="Silenzia",
            command=self.toggle_mute
        )
        self.mute_btn.pack(pady=2)
        
        # Aggiorna stato GUI e avvia loop di aggiornamento
        self.update_gui_status()
        
        return self.gui_frame
    
    def toggle_mute(self):
        """Attiva/disattiva muto"""
        if self.is_muted:
            self.unmute()
        else:
            self.mute()
        self.update_gui_status()
    
    def update_gui_status(self):
        """Aggiorna lo stato visivo della GUI"""
        if self.gui_frame is None:
            return
            
        if self.is_active:
            self.toggle_btn.config(text="Spegni Assistente")
            self.status_label.config(text="Attivo", foreground="green")
        else:
            self.toggle_btn.config(text="Attiva Assistente")
            self.status_label.config(text="Spento", foreground="red")
        
        if self.is_muted:
            self.mute_btn.config(text="Riattiva Voce")
        else:
            self.mute_btn.config(text="Silenzia")
        
        # Aggiorna ogni secondo
        if hasattr(self, 'gui_frame') and self.gui_frame:
            self.gui_frame.after(1000, self.update_gui_status)
    
    def cleanup(self):
        """
        METODO MANCANTE - Cleanup completo per chiusura applicazione
        
        Risolve il problema del microfono che rimane attivo dopo la chiusura dell'app.
        Questo metodo viene chiamato da main.py nel graceful_shutdown().
        """
        print("🛑 Cleanup assistente vocale - rilascio risorse microfono")
        
        try:
            # STEP 1: Ferma immediatamente l'ascolto
            self.is_active = False
            self.is_listening = False
            
            # STEP 2: Aspetta che i thread terminino
            if hasattr(self, 'listen_thread') and self.listen_thread and self.listen_thread.is_alive():
                print("🔄 Aspettando terminazione thread ascolto...")
                self.listen_thread.join(timeout=3.0)  # Timeout di 3 secondi
                if self.listen_thread.is_alive():
                    print("⚠️ Thread ascolto non terminato entro il timeout")
                else:
                    print("✅ Thread ascolto terminato correttamente")
            
            # STEP 3: Cleanup pygame mixer
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
                print("✅ Pygame mixer chiuso")
            except:
                pass
            
            # STEP 4: Rilascia esplicitamente il microfono
            try:
                if hasattr(self, 'microphone'):
                    # Forza il rilascio del microfono
                    self.microphone = None
                if hasattr(self, 'recognizer'):
                    self.recognizer = None
                print("✅ Microfono rilasciato")
            except:
                pass
                
            print("✅ Cleanup assistente vocale completato")
            
        except Exception as e:
            print(f"❌ Errore durante cleanup: {e}")
            # Anche in caso di errore, forza la pulizia
            self.is_active = False
            self.is_listening = False