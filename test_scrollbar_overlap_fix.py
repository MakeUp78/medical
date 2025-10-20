#!/usr/bin/env python3
"""
Test per diagnosticare e risolvere il problema di sovrapposizione della scrollbar.
"""

import tkinter as tk
import ttkbootstrap as ttk

def test_scrollbar_overlap():
    """Test specifico per il problema di sovrapposizione scrollbar."""
    root = ttk.Window()
    root.title("Diagnosi Sovrapposizione Scrollbar")
    root.geometry("400x600")
    
    # Frame principale che simula la colonna destra
    main_frame = ttk.LabelFrame(root, text="Test Colonna Destra", padding=5)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Canvas SENZA larghezza fissa
    canvas = tk.Canvas(main_frame, highlightthickness=0, bg="lightblue")
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    
    # Frame scrollabile con contenuto che riempie lo spazio
    scrollable_frame = ttk.LabelFrame(canvas, text="Contenuto", padding=4)
    
    # Aggiungi contenuto di test largo per verificare sovrapposizione
    for i in range(15):
        # Frame che simula contenuto della colonna destra
        content_frame = ttk.Frame(scrollable_frame)
        content_frame.pack(fill="x", pady=2)
        
        # Testo largo che va fino al bordo
        ttk.Label(content_frame, 
                 text=f"Elemento {i+1} - Questo testo lungo serve per verificare se la scrollbar copre il contenuto",
                 background="lightyellow").pack(side="left", fill="x", expand=True)
        
        # Pulsante che deve essere sempre visibile
        ttk.Button(content_frame, text=f"Btn{i+1}", width=8).pack(side="right", padx=2)
    
    # Bind per aggiornare scroll region
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Layout CORRETTO con spazio garantito per scrollbar
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    main_frame.grid_rowconfigure(0, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)
    main_frame.grid_columnconfigure(1, weight=0, minsize=25)  # Spazio minimo per scrollbar
    
    # Mousewheel binding
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    canvas.bind("<MouseWheel>", _on_mousewheel)
    scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
    
    # Forza il frame scrollabile a utilizzare tutta la larghezza del canvas
    def configure_scroll_region(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        # Importante: Configura larghezza del frame scrollabile = larghezza canvas
        canvas_width = canvas.winfo_width()
        if canvas_width > 1:  # Solo se il canvas è stato renderizzato
            canvas.itemconfig(canvas.find_all()[0], width=canvas_width)
    
    canvas.bind("<Configure>", configure_scroll_region)
    scrollable_frame.bind("<Configure>", configure_scroll_region)
    
    print("🔍 Test avviato:")
    print("   ✅ Canvas senza larghezza fissa")
    print("   ✅ Grid con minsize=25 per scrollbar")
    print("   ✅ Frame scrollabile si adatta al canvas")
    print("   🎯 Verifica che la scrollbar NON copra i pulsanti a destra")
    
    root.mainloop()

if __name__ == "__main__":
    test_scrollbar_overlap()