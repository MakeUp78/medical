"""
Fix per il problema del layout non renderizzato correttamente all'avvio.
Soluzione implementata con timing migliore e prevenzione             # Ricollega i bind usando i metodi disponibili (migliorati o originali)
            if hasattr(self.canvas_app, 'main_vertical_paned'):
                if hasattr(self.canvas_app, '_on_vertical_paned_resize_improved'):
                    self.canvas_app.main_vertical_paned.bind(
                        \"<ButtonRelease-1>\", self.canvas_app._on_vertical_paned_resize_improved
                    )
                elif hasattr(self.canvas_app, '_on_vertical_paned_resize'):
                    self.canvas_app.main_vertical_paned.bind(
                        \"<ButtonRelease-1>\", self.canvas_app._on_vertical_paned_resize
                    )
                
            if hasattr(self.canvas_app, 'main_horizontal_paned'):
                if hasattr(self.canvas_app, '_on_main_paned_resize_improved'):
                    self.canvas_app.main_horizontal_paned.bind(
                        \"<ButtonRelease-1>\", self.canvas_app._on_main_paned_resize_improved
                    )
                elif hasattr(self.canvas_app, '_on_main_paned_resize'):
                    self.canvas_app.main_horizontal_paned.bind(
                        \"<ButtonRelease-1>\", self.canvas_app._on_main_paned_resize
                    )
                
            if hasattr(self.canvas_app, 'right_sidebar_paned'):
                if hasattr(self.canvas_app, '_on_sidebar_paned_resize_improved'):
                    self.canvas_app.right_sidebar_paned.bind(
                        \"<ButtonRelease-1>\", self.canvas_app._on_sidebar_paned_resize_improved
                    )
                elif hasattr(self.canvas_app, '_on_sidebar_paned_resize'):
                    self.canvas_app.right_sidebar_paned.bind(
                        \"<ButtonRelease-1>\", self.canvas_app._on_sidebar_paned_resize
                    ).
"""

import tkinter as tk
from typing import Optional
from src.layout_manager import layout_manager


class LayoutRestorer:
    """Gestisce il ripristino robusto del layout con retry e validazione."""
    
    def __init__(self, canvas_app):
        self.canvas_app = canvas_app
        self.root = canvas_app.root
        self.restore_attempts = 0
        self.max_attempts = 3
        self.is_restoring = False
        self.initial_restore_done = False
        
    def start_layout_restore(self):
        """Avvia il processo di ripristino del layout con timing migliorato."""
        if self.is_restoring:
            return
            
        print("🔄 Avvio ripristino layout robusto...")
        self.is_restoring = True
        
        # Primo tentativo dopo che la GUI è completamente renderizzata
        self.root.after(500, self._attempt_restore_layout)
        
    def _attempt_restore_layout(self):
        """Tenta di ripristinare il layout con validazione."""
        try:
            self.restore_attempts += 1
            print(f"🔄 Tentativo ripristino layout #{self.restore_attempts}")
            
            # Verifica che i pannelli siano pronti
            if not self._are_panels_ready():
                if self.restore_attempts < self.max_attempts:
                    print("⏱️ Pannelli non ancora pronti, ritento tra 300ms...")
                    self.root.after(300, self._attempt_restore_layout)
                    return
                else:
                    print("⚠️ Pannelli non pronti dopo 3 tentativi, uso configurazione default")
                    self._apply_fallback_layout()
                    return
            
            # Disabilita temporaneamente eventi resize per evitare interferenze
            self._disable_resize_events()
            
            # Applica il layout salvato
            success = self._apply_saved_layout()
            
            if success:
                print("✅ Layout ripristinato con successo")
                self.initial_restore_done = True
            else:
                print("❌ Fallback a layout default")
                self._apply_fallback_layout()
            
            # Riabilita eventi resize dopo un breve delay
            self.root.after(200, self._enable_resize_events)
            
        except Exception as e:
            print(f"❌ Errore nel ripristino layout: {e}")
            self._apply_fallback_layout()
            
        finally:
            self.is_restoring = False
            
    def _are_panels_ready(self) -> bool:
        """Verifica che tutti i pannelli siano inizializzati e abbiano dimensioni valide."""
        try:
            # Verifica che i pannelli esistano e abbiano panes
            required_panels = [
                ('main_horizontal_paned', 2),  # Almeno 2 panes
                ('main_vertical_paned', 2),    # Almeno 2 panes  
                ('right_sidebar_paned', 2)     # Almeno 2 panes
            ]
            
            for panel_name, min_panes in required_panels:
                panel = getattr(self.canvas_app, panel_name, None)
                if not panel:
                    print(f"   ❌ Pannello {panel_name} non trovato")
                    return False
                    
                panes = panel.panes()
                if len(panes) < min_panes:
                    print(f"   ❌ Pannello {panel_name} ha solo {len(panes)} panes (min: {min_panes})")
                    return False
                    
                # Verifica che il pannello abbia dimensioni sensate
                try:
                    width = panel.winfo_width()
                    height = panel.winfo_height()
                    if width < 100 or height < 100:
                        print(f"   ❌ Pannello {panel_name} troppo piccolo: {width}x{height}")
                        return False
                except:
                    print(f"   ❌ Impossibile ottenere dimensioni pannello {panel_name}")
                    return False
            
            print("   ✅ Tutti i pannelli sono pronti")
            return True
            
        except Exception as e:
            print(f"   ❌ Errore verifica pannelli: {e}")
            return False
    
    def _disable_resize_events(self):
        """Disabilita temporaneamente gli eventi di resize."""
        try:
            # Salva i bind originali
            self.original_binds = {}
            
            panels_to_disable = [
                'main_horizontal_paned',
                'main_vertical_paned', 
                'right_sidebar_paned'
            ]
            
            for panel_name in panels_to_disable:
                panel = getattr(self.canvas_app, panel_name, None)
                if panel:
                    # Unbind temporaneamente l'evento
                    panel.unbind("<ButtonRelease-1>")
                    print(f"   🔇 Eventi resize disabilitati per {panel_name}")
                    
        except Exception as e:
            print(f"⚠️ Errore disabilitazione eventi: {e}")
    
    def _enable_resize_events(self):
        """Riabilita gli eventi di resize."""
        try:
            # Ricollega i bind originali 
            if hasattr(self.canvas_app, 'main_vertical_paned'):
                self.canvas_app.main_vertical_paned.bind(
                    "<ButtonRelease-1>", self.canvas_app._on_vertical_paned_resize
                )
                
            if hasattr(self.canvas_app, 'main_horizontal_paned'):
                self.canvas_app.main_horizontal_paned.bind(
                    "<ButtonRelease-1>", self.canvas_app._on_main_paned_resize
                )
                
            if hasattr(self.canvas_app, 'right_sidebar_paned'):
                self.canvas_app.right_sidebar_paned.bind(
                    "<ButtonRelease-1>", self.canvas_app._on_sidebar_paned_resize
                )
                
            print("   🔊 Eventi resize riabilitati")
            
        except Exception as e:
            print(f"⚠️ Errore riabilitazione eventi: {e}")
    
    def _apply_saved_layout(self) -> bool:
        """Applica il layout salvato dall'utente."""
        try:
            config = layout_manager.config
            print(f"📐 Applicazione layout salvato:")
            print(f"   • Main: {config.main_paned_position}")
            print(f"   • Right column: {config.right_column_position}")
            print(f"   • Vertical: {config.vertical_paned_position}")
            print(f"   • Layers/preview: {config.layers_preview_divider_position}")
            
            # Applica main horizontal paned con VALIDAZIONE BILANCIATA
            if (hasattr(self.canvas_app, 'main_horizontal_paned') and 
                self.canvas_app.main_horizontal_paned.panes() and 
                config.main_paned_position > 0):
                
                window_width = self.root.winfo_width()
                
                # Assicura che la sidebar sinistra abbia spazio sufficiente (min 480px)
                min_left_width = 480
                max_left_width = window_width * 0.4  # Non più del 40% della finestra
                safe_main_position = max(min_left_width, min(config.main_paned_position, max_left_width))
                
                self.canvas_app.main_horizontal_paned.sashpos(0, safe_main_position)
                print(f"   ✅ Sidebar sinistra posizionata a {safe_main_position}px (bilanciata)")
                
                # Se abbiamo 3 panes, applica anche right column con VALIDAZIONE BILANCIATA
                if (len(self.canvas_app.main_horizontal_paned.panes()) >= 3 and 
                    config.right_column_position > 0):
                    
                    # Assicura che la sidebar destra abbia spazio sufficiente (min 480px)
                    min_right_width = 480
                    max_safe_right = window_width - min_right_width
                    min_safe_right = safe_main_position + 400  # Canvas minimo 400px
                    
                    safe_right_position = max(min_safe_right, min(config.right_column_position, max_safe_right))
                    
                    self.canvas_app.main_horizontal_paned.sashpos(1, safe_right_position)
                    actual_right_width = window_width - safe_right_position
                    print(f"   ✅ Sidebar destra: {actual_right_width}px (bilanciata per finestra {window_width}px)")
            
            # Applica vertical paned
            if (hasattr(self.canvas_app, 'main_vertical_paned') and 
                self.canvas_app.main_vertical_paned.panes() and 
                config.vertical_paned_position > 0):
                
                self.canvas_app.main_vertical_paned.sashpos(0, config.vertical_paned_position)
            
            # Applica sidebar paned (layers/preview)
            if (hasattr(self.canvas_app, 'right_sidebar_paned') and 
                self.canvas_app.right_sidebar_paned.panes() and 
                config.layers_preview_divider_position > 0):
                
                self.canvas_app.right_sidebar_paned.sashpos(0, config.layers_preview_divider_position)
            
            # Force update della GUI
            self.root.update_idletasks()
            self.root.update()
            
            return True
            
        except Exception as e:
            print(f"❌ Errore applicazione layout: {e}")
            return False
    
    def _apply_fallback_layout(self):
        """Applica un layout di fallback ragionevole BILANCIATO per entrambe le colonne."""
        try:
            print("🔧 Applicazione layout fallback BILANCIATO...")
            
            # Valori di fallback BILANCIATI basati sulle dimensioni effettive
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()
            
            # CORREZIONE: Garantisce spazio sufficiente per entrambe le colonne
            min_left_sidebar = 480   # Minimo per contenere i controlli senza tagliare
            min_right_sidebar = 480  # Minimo per contenere le tabelle
            min_canvas = 400         # Minimo per area canvas centrale
            
            required_total = min_left_sidebar + min_canvas + min_right_sidebar  # 1360px minimo
            
            if window_width >= required_total:
                # Finestra abbastanza grande: usa spazi ottimali
                fallback_main = min_left_sidebar
                fallback_right = window_width - min_right_sidebar
            else:
                # Finestra piccola: distribuzione proporzionale ma con minimi garantiti
                available_space = window_width - min_canvas  # Spazio per le sidebar
                left_ratio = 0.5  # 50% dello spazio disponibile per la sidebar sinistra
                
                fallback_main = max(min_left_sidebar, int(available_space * left_ratio))
                fallback_right = max(window_width - min_right_sidebar, fallback_main + min_canvas)
            
            fallback_vertical = max(600, window_height - 200)
            fallback_layers_preview = 250
            
            print(f"   📐 Finestra: {window_width}x{window_height}")
            print(f"   📐 Fallback main: {fallback_main} (garantisce controlli visibili)")
            print(f"   📐 Fallback right: {fallback_right} (garantisce tabelle visibili)")
            
            if hasattr(self.canvas_app, 'main_horizontal_paned'):
                if self.canvas_app.main_horizontal_paned.panes():
                    self.canvas_app.main_horizontal_paned.sashpos(0, fallback_main)
                    if len(self.canvas_app.main_horizontal_paned.panes()) >= 3:
                        self.canvas_app.main_horizontal_paned.sashpos(1, fallback_right)
                        print(f"   ✅ Layout bilanciato applicato: {fallback_main}px | canvas | {window_width - fallback_right}px")
            
            if hasattr(self.canvas_app, 'main_vertical_paned'):
                if self.canvas_app.main_vertical_paned.panes():
                    self.canvas_app.main_vertical_paned.sashpos(0, fallback_vertical)
            
            if hasattr(self.canvas_app, 'right_sidebar_paned'):
                if self.canvas_app.right_sidebar_paned.panes():
                    self.canvas_app.right_sidebar_paned.sashpos(0, fallback_layers_preview)
            
            print("✅ Layout fallback applicato")
            
        except Exception as e:
            print(f"❌ Errore layout fallback: {e}")


class ImprovedLayoutSaver:
    """Migliora il salvataggio del layout con debounce e validazione."""
    
    def __init__(self, canvas_app):
        self.canvas_app = canvas_app
        self.save_pending = False
        self.save_delay = 500  # ms di delay per debounce
        
    def schedule_save(self):
        """Programma il salvataggio con debounce per evitare salvataggi multipli."""
        if self.save_pending:
            return
            
        self.save_pending = True
        self.canvas_app.root.after(self.save_delay, self._perform_save)
    
    def _perform_save(self):
        """Esegue il salvataggio effettivo."""
        try:
            if hasattr(self.canvas_app, 'layout_restorer') and self.canvas_app.layout_restorer.is_restoring:
                print("⏸️ Salvataggio sospeso: ripristino in corso")
                self.save_pending = False
                return
            
            self.canvas_app._save_layout_only()
            
        except Exception as e:
            print(f"❌ Errore salvataggio layout: {e}")
        finally:
            self.save_pending = False