#!/usr/bin/env python3
"""
Script per inizializzare il tracciamento attività utenti
Crea la tabella user_activity nel database
"""

import sys
import os

# Aggiungi il percorso corrente al path di Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_server import app, db

def init_activity_tracking():
    """Inizializza la tabella user_activity"""
    print("🔧 Inizializzazione tracciamento attività utenti...")
    
    with app.app_context():
        try:
            # Crea tutte le tabelle (inclusa user_activity)
            db.create_all()
            print("✅ Tabella user_activity creata con successo!")
            print("")
            print("📊 La tabella user_activity è ora pronta per tracciare:")
            print("  - Login degli utenti")
            print("  - Upload di immagini")
            print("  - Upload di video")
            print("  - Avvio webcam")
            print("  - Analisi completate")
            print("")
            print("✨ Sistema di tracciamento attivato!")
            
        except Exception as e:
            print(f"❌ Errore durante l'inizializzazione: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    success = init_activity_tracking()
    sys.exit(0 if success else 1)
