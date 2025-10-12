#!/usr/bin/env python3
"""
Script dimostrativo per visualizzare i temi disponibili in ttkbootstrap
per l'applicazione di analisi facciale.
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

def show_available_themes():
    """Mostra i temi disponibili in ttkbootstrap."""
    
    # Temi disponibili
    themes = [
        ("cyborg", "Tema scuro cyberpunk - ATTUALE"),
        ("darkly", "Tema scuro elegante"),
        ("superhero", "Tema scuro con accenti blu"),
        ("vapor", "Tema scuro con viola"),
        ("solar", "Tema scuro con arancione"),
        ("cosmo", "Tema chiaro moderno"),
        ("flatly", "Tema chiaro minimalista"),
        ("journal", "Tema chiaro professionale"),
        ("litera", "Tema chiaro elegante"),
        ("lumen", "Tema chiaro luminoso"),
        ("minty", "Tema chiaro con verde"),
        ("pulse", "Tema chiaro con viola"),
        ("sandstone", "Tema chiaro neutro"),
        ("united", "Tema chiaro arancione"),
        ("yeti", "Tema chiaro blu"),
    ]
    
    print("=" * 70)
    print("🎨 TEMI DISPONIBILI PER FACIAL ANALYSIS APPLICATION")
    print("=" * 70)
    
    print("\n🌟 TEMI SCURI (consigliati per applicazioni mediche):")
    for theme, description in themes[:5]:
        print(f"   • {theme:<12} - {description}")
    
    print("\n☀️  TEMI CHIARI:")
    for theme, description in themes[5:]:
        print(f"   • {theme:<12} - {description}")
    
    print("\n" + "=" * 70)
    print("📝 Per cambiare tema, modifica questa riga in main.py:")
    print("   self.root = ttk.Window(themename=\"NOME_TEMA\")")
    print("=" * 70)

def demo_theme_selector():
    """Piccola demo per testare diversi temi."""
    
    def change_theme():
        theme = theme_var.get()
        # Chiude la finestra attuale
        root.quit()
        
        # Crea una nuova finestra con il tema selezionato
        new_root = ttk.Window(themename=theme)
        new_root.title(f"Demo Tema: {theme}")
        new_root.geometry("400x300")
        
        # Widgets demo
        ttk.Label(new_root, text=f"Tema: {theme}", font=("Arial", 16)).pack(pady=10)
        
        frame = ttk.LabelFrame(new_root, text="🎛️ Controlli", padding=10, bootstyle="primary")
        frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Button(frame, text="📁 Carica Immagine", bootstyle="primary-outline").pack(fill="x", pady=2)
        ttk.Button(frame, text="📹 Avvia Webcam", bootstyle="success").pack(fill="x", pady=2)
        ttk.Button(frame, text="🎬 Carica Video", bootstyle="info").pack(fill="x", pady=2)
        ttk.Button(frame, text="⏹️ Stop", bootstyle="danger").pack(fill="x", pady=2)
        
        ttk.Button(new_root, text="Chiudi", command=new_root.quit).pack(pady=20)
        
        new_root.mainloop()
    
    root = ttk.Window(themename="cyborg")
    root.title("🎨 Selettore Tema - Facial Analysis")
    root.geometry("350x400")
    
    ttk.Label(root, text="🎨 Seleziona un Tema", font=("Arial", 14, "bold")).pack(pady=10)
    
    theme_var = ttk.StringVar(value="cyborg")
    
    themes = ["cyborg", "darkly", "superhero", "vapor", "solar", 
             "cosmo", "flatly", "journal", "litera", "pulse"]
    
    for theme in themes:
        ttk.Radiobutton(root, text=theme.capitalize(), variable=theme_var, 
                       value=theme).pack(anchor="w", padx=20, pady=2)
    
    ttk.Button(root, text="Applica Tema", command=change_theme, 
              bootstyle="success").pack(pady=20)
    
    root.mainloop()

if __name__ == "__main__":
    print("\n🎯 FACIAL ANALYSIS - CONFIGURATORE TEMI TTKBOOTSTRAP\n")
    
    show_available_themes()
    
    print("\n🔧 Vuoi testare i temi? (s/n): ", end="")
    choice = input().lower().strip()
    
    if choice in ['s', 'si', 'y', 'yes']:
        print("\n🚀 Avvio demo selettore temi...")
        demo_theme_selector()
    else:
        print("\n✅ Configurazione completata!")