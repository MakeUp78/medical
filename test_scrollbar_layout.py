#!/usr/bin/env python3
"""
Test per verificare che la scrollbar della colonna destra non copra il contenuto.
"""

import tkinter as tk
import ttkbootstrap as ttk

def test_scrollbar_layout():
    """Test del layout della scrollbar."""
    root = ttk.Window()
    root.title("Test Scrollbar Layout")
    root.geometry("400x600")
    
    # Crea frame principale simile alla colonna destra
    main_frame = ttk.LabelFrame(root, text="Test Colonna Destra", padding=5)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Canvas e scrollbar come nell'applicazione
    canvas = tk.Canvas(main_frame, highlightthickness=0, width=245, bg="lightgray")
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    
    # Frame scrollabile con contenuto
    scrollable_frame = ttk.LabelFrame(canvas, text="Contenuto", padding=4)
    
    # Aggiungi contenuto di test
    for i in range(20):
        ttk.Label(scrollable_frame, text=f"Elemento {i+1} - Questo è un test molto lungo per verificare il layout").pack(pady=2, anchor="w")
        ttk.Button(scrollable_frame, text=f"Pulsante {i+1}", width=25).pack(pady=1, anchor="w")
    
    # Bind per aggiornare scroll region
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Layout con configurazione corretta
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    main_frame.grid_rowconfigure(0, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=0)  # Spazio fisso per scrollbar
    
    # Mousewheel binding
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    canvas.bind("<MouseWheel>", _on_mousewheel)
    scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
    
    print("✅ Test scrollbar layout avviato")
    print("📋 Verifica che:")
    print("   - La scrollbar sia posizionata a destra del contenuto")
    print("   - La scrollbar NON copra il contenuto")
    print("   - Il contenuto sia completamente visibile")
    
    root.mainloop()

if __name__ == "__main__":
    test_scrollbar_layout()