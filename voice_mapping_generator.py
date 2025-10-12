#!/usr/bin/env python3
"""
🔧 VOICE MAPPING GENERATOR - Generatore Automatico Mappature
===========================================================

Utility per generare automaticamente il codice di integrazione
dei comandi vocali basato sulla configurazione dell'Admin Tool.

Genera:
- Codice Python per voice_gui_integration.py
- File di configurazione JSON aggiornato
- Documentazione delle mappature

Autore: AI Assistant
Data: 6 Ottobre 2025
Versione: 1.0.0
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime


class VoiceMappingGenerator:
    """Generatore automatico di mappature vocali"""
    
    def __init__(self, config_file: str = "admin_voice_config.json"):
        self.config_file = config_file
        self.mappings = {}
        self.load_mappings()
    
    def load_mappings(self):
        """Carica mappature da file configurazione"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.mappings = config.get('mappings', {})
            else:
                print(f"⚠️ File configurazione non trovato: {self.config_file}")
        except Exception as e:
            print(f"❌ Errore caricamento configurazione: {e}")
    
    def generate_integration_code(self) -> str:
        """Genera codice per voice_gui_integration.py"""
        
        code = '''"""
🎤 VOICE COMMANDS INTEGRATION - Generato Automaticamente
======================================================

ATTENZIONE: File generato automaticamente dall'Admin Voice Configurator
NON MODIFICARE MANUALMENTE - Usare l'Admin Tool per le modifiche

Generato il: {timestamp}
Mappature configurate: {count}
"""

from typing import Dict, Callable
import logging

logger = logging.getLogger("VoiceCommandsIntegration")


class VoiceCommandsIntegration:
    """Integrazione comandi vocali generata automaticamente"""
    
    def __init__(self, voice_assistant, app_callbacks: Dict[str, Callable]):
        self.assistant = voice_assistant
        self.callbacks = app_callbacks
        
        # Registra tutti i comandi configurati
        self._register_commands()
        
        logger.info(f"✅ VoiceCommandsIntegration: {{len(app_callbacks)}} callbacks registrate")

    def _register_commands(self):
        """Registra tutti i comandi con l'assistente"""

{commands_code}

        logger.info(f"✅ Registrati {{len(self.callbacks)}} comandi vocali")

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
                logger.debug(f"✅ Callback eseguita: {{callback_name}}")
            except Exception as e:
                logger.error(f"❌ Errore callback '{{callback_name}}': {{e}}")
        else:
            logger.warning(f"⚠️ Callback non trovata: {{callback_name}}")

'''.format(
            timestamp=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            count=len(self.mappings),
            commands_code=self._generate_commands_code()
        )
        
        return code
    
    def _generate_commands_code(self) -> str:
        """Genera codice per registrazione comandi"""
        code_blocks = []
        
        for action, mapping in self.mappings.items():
            handler = mapping.get('handler', 'unknown')
            keywords = mapping.get('keywords', [])
            confirmation = mapping.get('confirmation', f"Comando {action} eseguito")
            
            if not keywords:
                continue
            
            # Genera blocco codice per questo comando
            keywords_str = ', '.join(f'"{kw}"' for kw in keywords)
            
            code_block = f'''
        # {action.upper()}
        if "{handler}" in self.callbacks:
            self.assistant.add_command(
                keywords=[{keywords_str}],
                action="{action}",
                handler=lambda text, cmd: self._safe_callback("{handler}"),
                confirmation="{confirmation}",
            )'''
            
            code_blocks.append(code_block)
        
        return '\n'.join(code_blocks)
    
    def generate_config_json(self) -> Dict[str, Any]:
        """Genera configurazione JSON per Isabella"""
        config = {
            "activation_keywords": [
                "hey symmetra",
                "ciao symmetra", 
                "ehi symmetra",
                "symmetra"
            ],
            "language": "it-IT",
            "tts_voice": "it-IT-IsabellaNeural",
            "timeout": 5.0,
            "phrase_timeout": 2.0,
            "voice_settings": {
                "rate": "+0%",
                "volume": "+10%"
            },
            "stt_settings": {
                "energy_threshold": 300,
                "dynamic_energy_threshold": True,
                "pause_threshold": 0.8
            },
            "messages": {
                "startup": "Assistente vocale Symmetra attivato. Dimmi 'Hey Symmetra' quando hai bisogno di me.",
                "activation": "Ti ascolto! Cosa posso fare per te?",
                "deactivation": "Torno in modalità standby. Chiamami quando hai bisogno.",
                "command_not_found": "Comando non riconosciuto. Puoi ripetere o dire 'aiuto' per la lista dei comandi?",
                "listening_error": "Non ho sentito bene. Puoi ripetere più chiaramente?",
                "processing": "Un momento, sto elaborando...",
                "goodbye": "Assistente vocale disattivato. Arrivederci!",
                "help": "Ecco i comandi disponibili. Dimmi cosa vuoi fare.",
                "status": "Assistente attivo da {duration} secondi. Eseguiti {commands} comandi.",
                "feature_activated": "Funzionalità '{feature}' attivata con successo.",
                "operation_complete": "Operazione '{operation}' completata con successo.",
                "error_occurred": "Si è verificato un errore: {error}. Controlla i dettagli."
            },
            "custom_messages": self._generate_custom_messages(),
            "advanced_settings": {
                "auto_deactivate_timeout": 30,
                "confirmation_for_critical_actions": True,
                "background_listening": True,
                "voice_feedback_level": "normal"
            },
            "generated_by_admin_tool": True,
            "generation_timestamp": datetime.now().isoformat(),
            "mappings_count": len(self.mappings)
        }
        
        return config
    
    def _generate_custom_messages(self) -> Dict[str, str]:
        """Genera messaggi personalizzati basati sulle mappature"""
        messages = {}
        
        for action, mapping in self.mappings.items():
            # Messaggio di conferma
            messages[f"{action}_confirm"] = mapping.get('confirmation', f"Comando {action} eseguito")
            
            # Messaggio di completamento
            messages[f"{action}_complete"] = f"Operazione {action} completata con successo"
            
            # Messaggio di errore
            messages[f"{action}_error"] = f"Errore durante l'esecuzione di {action}"
        
        return messages
    
    def generate_documentation(self) -> str:
        """Genera documentazione delle mappature"""
        doc = f"""
# 📋 DOCUMENTAZIONE COMANDI VOCALI SYMMETRA

**Generato automaticamente il:** {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}  
**Mappature configurate:** {len(self.mappings)}

## 🎤 Comandi Disponibili

| Comando | Frasi di Attivazione | Funzione | Handler |
|---------|---------------------|----------|---------|
"""
        
        for action, mapping in self.mappings.items():
            keywords = ', '.join(f'"{kw}"' for kw in mapping.get('keywords', []))
            handler = mapping.get('handler', 'N/A')
            
            doc += f"| **{action}** | {keywords} | {action.replace('_', ' ').title()} | `{handler}()` |\n"
        
        doc += f"""

## 🔧 Configurazione Tecnica

### Parole di Attivazione
- "Hey Symmetra"
- "Ciao Symmetra" 
- "Ehi Symmetra"
- "Symmetra"

### Impostazioni Vocali
- **Voce:** Isabella Neural (Italiano)
- **Lingua:** it-IT
- **Timeout:** 5 secondi
- **Volume:** +10%

### Statistiche
- **Totale Comandi:** {len(self.mappings)}
- **Keywords Totali:** {sum(len(m.get('keywords', [])) for m in self.mappings.values())}
- **Handlers Unici:** {len(set(m.get('handler') for m in self.mappings.values()))}

---
*Documentazione generata dall'Admin Voice Configurator*
"""
        
        return doc
    
    def save_all_files(self, output_dir: str = "."):
        """Salva tutti i file generati"""
        try:
            # Codice integrazione
            integration_code = self.generate_integration_code()
            integration_path = os.path.join(output_dir, "voice", "voice_gui_integration_generated.py")
            
            os.makedirs(os.path.dirname(integration_path), exist_ok=True)
            with open(integration_path, 'w', encoding='utf-8') as f:
                f.write(integration_code)
            
            print(f"✅ Codice integrazione salvato: {integration_path}")
            
            # Configurazione JSON
            config_json = self.generate_config_json()
            config_path = os.path.join(output_dir, "voice", "isabella_voice_config_generated.json")
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_json, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Configurazione JSON salvata: {config_path}")
            
            # Documentazione
            documentation = self.generate_documentation()
            doc_path = os.path.join(output_dir, "VOICE_COMMANDS_DOCUMENTATION.md")
            
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(documentation)
            
            print(f"✅ Documentazione salvata: {doc_path}")
            
            print(f"\n🎉 Tutti i file generati con successo in: {os.path.abspath(output_dir)}")
            
        except Exception as e:
            print(f"❌ Errore durante il salvataggio: {e}")
    
    def preview_generation(self):
        """Anteprima della generazione"""
        print("\n🔍 ANTEPRIMA GENERAZIONE MAPPATURE")
        print("=" * 40)
        
        if not self.mappings:
            print("⚠️ Nessuna mappatura trovata")
            return
        
        print(f"📊 Mappature da generare: {len(self.mappings)}")
        
        for action, mapping in self.mappings.items():
            keywords = mapping.get('keywords', [])
            handler = mapping.get('handler', 'N/A')
            
            print(f"\n🎤 {action}")
            print(f"   Keywords: {', '.join(keywords)}")
            print(f"   Handler: {handler}")
        
        print("\n📁 File che verranno generati:")
        print("   - voice/voice_gui_integration_generated.py")
        print("   - voice/isabella_voice_config_generated.json") 
        print("   - VOICE_COMMANDS_DOCUMENTATION.md")


def main():
    """Funzione principale"""
    print("🔧 Voice Mapping Generator")
    print("=" * 30)
    
    generator = VoiceMappingGenerator()
    
    if not generator.mappings:
        print("⚠️ Nessuna mappatura trovata.")
        print("   Usa l'Admin Voice Configurator per creare le mappature.")
        return
    
    # Anteprima
    generator.preview_generation()
    
    # Conferma generazione
    confirm = input("\n❓ Procedere con la generazione? (s/N): ").strip().lower()
    if confirm in ['s', 'si', 'sì', 'y', 'yes']:
        generator.save_all_files()
    else:
        print("❌ Generazione annullata")


if __name__ == "__main__":
    main()