#!/usr/bin/env python3
"""
Test per verificare il sistema di debug con le tab
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.canvas_app import CanvasApp
import tkinter as tk

def test_debug_system():
    """Test rapido del sistema di debug."""
    root = tk.Tk()
    root.title("Test Debug System")
    
    app = CanvasApp(root)
    
    # Test debug functions
    print("🧪 Testing debug functions...")
    
    # Test debug canvas access
    for tab_type in ['landmarks', 'geometry', 'eyebrows', 'ideal', 'complete']:
        canvas = app.get_debug_canvas(tab_type)
        if canvas:
            print(f"✅ Canvas '{tab_type}' trovato: {type(canvas)}")
        else:
            print(f"❌ Canvas '{tab_type}' NON trovato")
    
    # Test toolbar functions
    print("\n🧪 Testing toolbar functions...")
    for tab_type in ['landmarks', 'geometry', 'eyebrows', 'ideal', 'complete']:
        try:
            app.fit_debug_image(tab_type)
            app.zoom_debug_image(tab_type, 1.2)
            app.save_debug_image(tab_type)
            print(f"✅ Funzioni toolbar per '{tab_type}' funzionano")
        except Exception as e:
            print(f"❌ Errore funzioni toolbar '{tab_type}': {e}")
    
    print("\n✅ Test completato!")
    root.after(3000, root.destroy)  # Chiude dopo 3 secondi
    root.mainloop()

if __name__ == "__main__":
    test_debug_system()