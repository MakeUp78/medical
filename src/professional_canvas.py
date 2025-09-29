"""
Canvas professionale avanzato per gestione immagini con strumenti di disegno e navigazione.
"""

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, simpledialog
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.patches import Rectangle, Circle, Polygon, FancyArrowPatch
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.widgets import RectangleSelector, EllipseSelector
import matplotlib.patches as patches
from typing import List, Tuple, Optional, Dict, Any
import uuid
from dataclasses import dataclass
from enum import Enum

# Importa il sistema di configurazione layout
from src.layout_manager import layout_manager


class Tool(Enum):
    """Enumerazione degli strumenti disponibili."""

    SELECTION = "selection"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN = "pan"
    LINE = "line"
    ARROW = "arrow"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"
    TEXT = "text"
    MEASURE = "measure"
    RULER_H = "ruler_horizontal"
    RULER_V = "ruler_vertical"


class DrawMode(Enum):
    """Modalità di disegno."""

    DRAWING = "drawing"
    EDITING = "editing"
    MOVING = "moving"


@dataclass
class Layer:
    """Rappresenta un layer del canvas."""

    id: str
    name: str
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    objects: List[Any] = None

    def __post_init__(self):
        if self.objects is None:
            self.objects = []


@dataclass
class DrawingObject:
    """Oggetto di disegno generico."""

    id: str
    type: str
    layer_id: str
    artist: Any  # Matplotlib artist object
    properties: Dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}


class ProfessionalCanvas:
    """Canvas professionale con strumenti avanzati di navigazione e disegno."""

    def __init__(self, parent, width=800, height=600, standalone=False):
        """Inizializza il canvas professionale.

        Args:
            parent: Widget parent
            width: Larghezza di default
            height: Altezza di default
            standalone: Se True, crea interfaccia completa; se False, solo canvas
        """
        self.parent = parent
        self.width = width
        self.height = height
        self.standalone = standalone

        # Stato del canvas
        self.current_image = None
        self.current_tool = Tool.SELECTION
        self.draw_mode = DrawMode.DRAWING
        self.is_drawing = False
        self.start_point = None
        self.current_color = "#FF0000"
        self.line_width = 2
        self.font_size = 12
        self.snap_to_grid = False
        self.grid_size = 20

        # Variabili per PAN (trascinamento vista)
        self.is_panning = False
        self.pan_start_point = None
        self.pan_start_xlim = None
        self.pan_start_ylim = None

        # Sistema callback unificato per integrazione con CanvasApp
        self.measurement_callback = None  # Callback per misurazioni

        # Sistema layer
        self.layers = []
        self.current_layer_id = None
        self.create_default_layer()

        # Oggetti disegnati
        self.drawing_objects = {}
        self.selected_objects = []
        self.temp_artist = None  # Per preview durante il disegno

        # Rulers e guide
        self.rulers = {"horizontal": [], "vertical": []}
        self.show_grid = True  # Mostra griglia di default
        self.show_rulers = True

        # Setup GUI in base alla modalità
        if self.standalone:
            self.setup_standalone_gui()
        else:
            self.setup_embedded_gui()

        self.setup_matplotlib_canvas()
        if self.standalone:
            self.setup_toolbar()
            self.setup_layers_panel()

        self.bind_events()

        # Inizializza il canvas con griglia visibile
        self.initialize_empty_canvas()

    def _restore_paned_position(self):
        """Ripristina la posizione del divisore dalla configurazione salvata."""
        try:
            # Calcola la posizione del divisore basata sulla larghezza totale
            total_width = self.main_paned.winfo_width()
            if total_width > 1:
                # Posiziona il divisore per dare al pannello destro la larghezza desiderata
                position = total_width - layout_manager.config.right_panel_width
                if position > 0:
                    self.main_paned.sashpos(0, position)
        except:
            pass  # Ignora errori durante il ripristino

    def _on_canvas_resize(self, event=None):
        """Callback chiamato quando il canvas viene ridimensionato."""
        try:
            # Ottieni dimensioni attuali del widget canvas
            widget = self.mpl_canvas.get_tk_widget()
            canvas_width = widget.winfo_width()
            canvas_height = widget.winfo_height()

            # Ignora se le dimensioni non sono ancora valide
            if canvas_width <= 1 or canvas_height <= 1:
                return

            # Se abbiamo un'immagine, adattala
            if self.current_image is not None:
                # Calcola il rapporto per adattare l'immagine al canvas
                img_width = self.current_image.width
                img_height = self.current_image.height

                # Calcola scala mantenendo proporzioni (margine più generoso per migliore visualizzazione)
                scale_x = canvas_width / img_width
                scale_y = canvas_height / img_height
                scale = (
                    min(scale_x, scale_y) * 0.85
                )  # Margine più ampio per migliore visibilità

                # Calcola dimensioni adattate
                new_width = img_width * scale
                new_height = img_height * scale

                # Centra l'immagine
                margin_x = (canvas_width - new_width) / 2
                margin_y = (canvas_height - new_height) / 2

                # Aggiorna i limiti degli assi per centrare e adattare l'immagine
                self.ax.set_xlim(-margin_x / scale, img_width + margin_x / scale)
                self.ax.set_ylim(img_height + margin_y / scale, -margin_y / scale)

                # Mantieni griglia sottile
                if self.show_grid:
                    self.ax.grid(True, alpha=0.1, linewidth=0.5)

            else:
                # Canvas vuoto: mantieni proporzioni ma adatta alle dimensioni
                aspect_ratio = canvas_width / canvas_height
                base_size = 1000

                if aspect_ratio > 1.25:  # Canvas largo
                    x_range = base_size * aspect_ratio
                    y_range = base_size
                else:  # Canvas alto o quadrato
                    x_range = base_size
                    y_range = base_size / aspect_ratio

                self.ax.set_xlim(-50, x_range + 50)
                self.ax.set_ylim(y_range + 50, -50)

                # Mantieni griglia più visibile per canvas vuoto
                if self.show_grid:
                    self.ax.grid(True, alpha=0.2, linewidth=0.5)

            # Ridisegna il canvas
            self.mpl_canvas.draw_idle()

        except Exception as e:
            # Log errore ma non interrompere
            print(f"Errore resize canvas: {e}")

    def _on_paned_resize(self, event=None):
        """Callback chiamato quando l'utente ridimensiona i pannelli."""
        try:
            # Calcola la larghezza attuale del pannello destro
            total_width = self.main_paned.winfo_width()
            sash_position = self.main_paned.sashpos(0)
            right_panel_width = total_width - sash_position

            # Aggiorna la configurazione
            layout_manager.config.right_panel_width = max(
                200, right_panel_width
            )  # Minimo 200px

        except:
            pass  # Ignora errori

    def save_layout_config(self):
        """Salva la configurazione corrente del layout."""
        try:
            # Aggiorna configurazione pannelli
            self._on_paned_resize()

            # Salva su file
            layout_manager.save_config()

        except Exception as e:
            print(f"Errore salvataggio configurazione layout: {e}")

    def restore_layout_config(self):
        """Ripristina la configurazione del layout."""
        try:
            # Ripristina posizioni pannelli
            self._restore_paned_position()

        except Exception as e:
            print(f"Errore ripristino configurazione layout: {e}")

    def create_default_layer(self):
        """Crea il layer di default."""
        default_layer = Layer(
            id=str(uuid.uuid4()), name="Layer Base", visible=True, locked=False
        )
        self.layers.append(default_layer)
        self.current_layer_id = default_layer.id

    def setup_embedded_gui(self):
        """Configura interfaccia minima per uso embedded in canvas_app con controlli essenziali."""
        # Frame principale semplice che si espande nel parent
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar compatta con controlli essenziali
        self.toolbar_frame = ttk.Frame(self.main_frame)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X, padx=2, pady=1)

        # Gruppo controlli visualizzazione
        view_frame = ttk.LabelFrame(self.toolbar_frame, text="Vista", padding=2)
        view_frame.pack(side=tk.LEFT, padx=(0, 3))

        view_buttons = [
            ("🏠", self.fit_to_window, "Adatta alla finestra"),
            ("🔄", self.reset_view, "Reset vista"),
            ("⊞", self.toggle_grid, "Griglia"),
        ]

        for icon, command, tooltip in view_buttons:
            btn = ttk.Button(view_frame, text=icon, width=3, command=command)
            btn.pack(side=tk.LEFT, padx=1)
            self.create_tooltip(btn, tooltip)

        # Gruppo zoom/navigazione
        nav_frame = ttk.LabelFrame(self.toolbar_frame, text="Navigazione", padding=2)
        nav_frame.pack(side=tk.LEFT, padx=(0, 3))

        # Pulsanti zoom separati
        zoom_in_btn = ttk.Button(nav_frame, text="🔍+", width=4, command=self.zoom_in)
        zoom_in_btn.pack(side=tk.LEFT, padx=1)
        self.create_tooltip(zoom_in_btn, "Zoom In (ingrandisci)")

        zoom_out_btn = ttk.Button(nav_frame, text="🔍-", width=4, command=self.zoom_out)
        zoom_out_btn.pack(side=tk.LEFT, padx=1)
        self.create_tooltip(zoom_out_btn, "Zoom Out (rimpicciolisci)")

        # Altri pulsanti navigazione
        nav_buttons = [
            ("✋", Tool.PAN, "Pan"),
            ("🎯", Tool.SELECTION, "Selezione"),
        ]

        for icon, tool, tooltip in nav_buttons:
            btn = ttk.Button(
                nav_frame, text=icon, width=3, command=lambda t=tool: self.set_tool(t)
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.create_tooltip(btn, tooltip)

        # Gruppo misurazione essenziale
        measure_frame = ttk.LabelFrame(self.toolbar_frame, text="Misure", padding=2)
        measure_frame.pack(side=tk.LEFT, padx=(0, 3))

        measure_buttons = [
            ("📐", Tool.MEASURE, "Strumento misura"),
            ("📏", Tool.LINE, "Linea"),
        ]

        for icon, tool, tooltip in measure_buttons:
            btn = ttk.Button(
                measure_frame,
                text=icon,
                width=3,
                command=lambda t=tool: self.set_tool(t),
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.create_tooltip(btn, tooltip)

        # Frame del canvas
        self.canvas_frame = ttk.Frame(self.main_frame)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Status bar minimale
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=1)

        self.status_var = tk.StringVar(value="Canvas pronto")
        self.status_label = ttk.Label(
            self.status_frame, textvariable=self.status_var, font=("Arial", 8)
        )
        self.status_label.pack(side=tk.LEFT)

        # Coordinate mouse
        self.coords_var = tk.StringVar(value="(0, 0)")
        self.coords_label = ttk.Label(
            self.status_frame, textvariable=self.coords_var, font=("Arial", 8)
        )
        self.coords_label.pack(side=tk.RIGHT)

    def setup_standalone_gui(self):
        """Configura l'interfaccia completa per uso standalone."""
        # Frame principale
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar superiore
        self.toolbar_frame = ttk.Frame(self.main_frame)
        self.toolbar_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

        # PANNELLO CENTRALE RIDIMENSIONABILE con PanedWindow
        # PanedWindow orizzontale principale per canvas + pannello destro
        self.main_paned = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Frame del canvas (parte sinistra/centrale)
        self.canvas_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.canvas_frame, weight=1)

        # Pannello destro per strumenti e layer (ridimensionabile)
        self.right_panel = ttk.Frame(
            self.main_paned, width=layout_manager.config.right_panel_width
        )
        self.main_paned.add(self.right_panel, weight=0)

        # Ripristina posizione del divisore dalla configurazione
        self.main_paned.after(100, self._restore_paned_position)

        # Status bar
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

        self.status_var = tk.StringVar(value="Pronto")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT)

        # Coordinate mouse
        self.coords_var = tk.StringVar(value="(0, 0)")
        self.coords_label = ttk.Label(self.status_frame, textvariable=self.coords_var)
        self.coords_label.pack(side=tk.RIGHT)

        # Bind eventi per salvare posizioni pannelli
        self.main_paned.bind("<ButtonRelease-1>", self._on_paned_resize)

    def setup_matplotlib_canvas(self):
        """Configura il canvas matplotlib."""
        # Crea figura matplotlib con dimensioni relative al contenitore
        self.fig, self.ax = plt.subplots(figsize=(10, 7), dpi=100)
        self.fig.patch.set_facecolor("white")
        self.fig.subplots_adjust(left=0.08, right=0.98, top=0.95, bottom=0.08)

        # Configura assi per una migliore visualizzazione iniziale
        self.ax.set_aspect("equal")
        self.ax.set_xlim(0, 800)
        self.ax.set_ylim(600, 0)  # Invertito: Y cresce verso il basso

        # Griglia più sottile e discreta
        self.ax.grid(True, alpha=0.2, linewidth=0.5)
        self.ax.set_xlabel("X (pixel)", fontsize=9)
        self.ax.set_ylabel("Y (pixel)", fontsize=9)

        # Tick più piccoli
        self.ax.tick_params(axis="both", which="major", labelsize=8)

        # Canvas tkinter per matplotlib
        self.mpl_canvas = FigureCanvasTkAgg(self.fig, self.canvas_frame)
        canvas_widget = self.mpl_canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Bind evento resize per adattamento automatico
        canvas_widget.bind("<Configure>", self._on_canvas_resize)

        # Toolbar matplotlib solo in modalità standalone
        if self.standalone:
            toolbar_frame = ttk.Frame(self.canvas_frame)
            toolbar_frame.pack(side=tk.TOP, fill=tk.X)

            self.mpl_toolbar = NavigationToolbar2Tk(self.mpl_canvas, toolbar_frame)
            self.mpl_toolbar.update()

            # Nasconde alcuni pulsanti non necessari
            for child in self.mpl_toolbar.winfo_children():
                if isinstance(child, tk.Button):
                    text = child.cget("text")
                    if text in ["Configure", "Subplots"]:
                        child.pack_forget()

    def initialize_empty_canvas(self):
        """Inizializza il canvas vuoto con griglia e assi visibili."""
        try:
            # Assicura che la griglia sia visibile ma discreta
            self.ax.grid(True, alpha=0.2, linewidth=0.5)
            self.ax.set_xlabel("X (pixel)", fontsize=9)
            self.ax.set_ylabel("Y (pixel)", fontsize=9)

            # Tick più piccoli e discreti
            self.ax.tick_params(axis="both", which="major", labelsize=8)

            # Imposta limiti di default con margini
            self.ax.set_xlim(-50, 1050)
            self.ax.set_ylim(850, -50)

            # Disegna il canvas
            self.mpl_canvas.draw()

            self.update_status(
                "Canvas pronto - Carica un'immagine o inizia a disegnare"
            )
        except Exception as e:
            print(f"Errore inizializzazione canvas: {e}")

    def setup_toolbar(self):
        """Configura la toolbar degli strumenti (solo in modalità standalone)."""
        if not self.standalone or not hasattr(self, "toolbar_frame"):
            return

        # Gruppo strumenti di navigazione
        nav_frame = ttk.LabelFrame(self.toolbar_frame, text="Navigazione", padding=3)
        nav_frame.pack(side=tk.LEFT, padx=(0, 5))

        nav_buttons = [
            ("🔍+", self.zoom_in, "Zoom In (ingrandisci)"),
            ("🔍-", self.zoom_out, "Zoom Out (rimpicciolisci)"),
            ("✋", Tool.PAN, "Pan"),
            ("🎯", Tool.SELECTION, "Selezione"),
            ("🏠", self.fit_to_window, "Adatta alla finestra"),
            ("📱", self.fit_image_to_canvas, "Adatta immagine al canvas"),
            ("🔄", self.reset_view, "Reset vista"),
        ]

        for i, (icon, command, tooltip) in enumerate(nav_buttons):
            if callable(command):
                btn = ttk.Button(nav_frame, text=icon, width=3, command=command)
            else:
                btn = ttk.Button(
                    nav_frame,
                    text=icon,
                    width=3,
                    command=lambda t=command: self.set_tool(t),
                )
            btn.pack(side=tk.LEFT, padx=1)
            self.create_tooltip(btn, tooltip)

        # Gruppo strumenti di disegno
        draw_frame = ttk.LabelFrame(self.toolbar_frame, text="Disegno", padding=3)
        draw_frame.pack(side=tk.LEFT, padx=(0, 5))

        draw_buttons = [
            ("📏", Tool.LINE, "Linea"),
            ("➡️", Tool.ARROW, "Freccia"),
            ("⬜", Tool.RECTANGLE, "Rettangolo"),
            ("⭕", Tool.CIRCLE, "Cerchio"),
            ("🔷", Tool.POLYGON, "Poligono"),
            ("📝", Tool.TEXT, "Testo"),
        ]

        for icon, tool, tooltip in draw_buttons:
            btn = ttk.Button(
                draw_frame, text=icon, width=3, command=lambda t=tool: self.set_tool(t)
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.create_tooltip(btn, tooltip)

        # Gruppo strumenti di misurazione
        measure_frame = ttk.LabelFrame(
            self.toolbar_frame, text="Misurazione", padding=3
        )
        measure_frame.pack(side=tk.LEFT, padx=(0, 5))

        measure_buttons = [
            ("📐", Tool.MEASURE, "Strumento misura"),
            ("📊", Tool.RULER_H, "Righello orizzontale"),
            ("📏", Tool.RULER_V, "Righello verticale"),
            ("⊞", self.toggle_grid, "Griglia"),
        ]

        for icon, command, tooltip in measure_buttons:
            if callable(command):
                btn = ttk.Button(measure_frame, text=icon, width=3, command=command)
            else:
                btn = ttk.Button(
                    measure_frame,
                    text=icon,
                    width=3,
                    command=lambda t=command: self.set_tool(t),
                )
            btn.pack(side=tk.LEFT, padx=1)
            self.create_tooltip(btn, tooltip)

        # Controlli colore e stile
        style_frame = ttk.LabelFrame(self.toolbar_frame, text="Stile", padding=3)
        style_frame.pack(side=tk.LEFT, padx=(0, 5))

        # Colore
        self.color_button = tk.Button(
            style_frame,
            text="🎨",
            width=3,
            bg=self.current_color,
            command=self.choose_color,
        )
        self.color_button.pack(side=tk.LEFT, padx=2)
        self.create_tooltip(self.color_button, "Scegli colore")

        # Spessore linea
        ttk.Label(style_frame, text="Spessore:").pack(side=tk.LEFT, padx=(5, 2))
        self.width_var = tk.IntVar(value=self.line_width)
        width_spin = ttk.Spinbox(
            style_frame,
            from_=1,
            to=20,
            width=4,
            textvariable=self.width_var,
            command=self.on_line_width_change,
        )
        width_spin.pack(side=tk.LEFT)

        # Controlli snap
        snap_frame = ttk.Frame(style_frame)
        snap_frame.pack(side=tk.LEFT, padx=(10, 0))

        self.snap_var = tk.BooleanVar(value=self.snap_to_grid)
        snap_check = ttk.Checkbutton(
            snap_frame, text="Snap", variable=self.snap_var, command=self.toggle_snap
        )
        snap_check.pack()

    def setup_layers_panel(self):
        """Configura il pannello dei layer con supporto ridimensionamento (solo in modalità standalone)."""
        if not self.standalone or not hasattr(self, "right_panel"):
            return

        # PanedWindow verticale per dividere strumenti e layers
        self.right_paned = ttk.PanedWindow(self.right_panel, orient=tk.VERTICAL)
        self.right_paned.pack(fill=tk.BOTH, expand=True)

        # Frame per gli strumenti (parte superiore)
        tools_frame = ttk.LabelFrame(self.right_paned, text="Strumenti", padding=5)
        self.right_paned.add(tools_frame, weight=0)

        # Pannello layer (parte inferiore, ridimensionabile)
        layers_frame = ttk.LabelFrame(self.right_paned, text="Layer", padding=8)
        self.right_paned.add(layers_frame, weight=1)

        # Controlli layer
        layer_controls = ttk.Frame(layers_frame)
        layer_controls.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(layer_controls, text="➕", width=3, command=self.add_layer).pack(
            side=tk.LEFT, padx=1
        )
        ttk.Button(layer_controls, text="➖", width=3, command=self.remove_layer).pack(
            side=tk.LEFT, padx=1
        )
        ttk.Button(layer_controls, text="⬆️", width=3, command=self.move_layer_up).pack(
            side=tk.LEFT, padx=1
        )
        ttk.Button(
            layer_controls, text="⬇️", width=3, command=self.move_layer_down
        ).pack(side=tk.LEFT, padx=1)

        # Lista layer - CONFIGURAZIONE RIDIMENSIONABILE
        self.layers_tree = ttk.Treeview(
            layers_frame, columns=("visible", "locked"), show="tree headings", height=8
        )
        self.layers_tree.heading("#0", text="Nome Layer")
        self.layers_tree.heading("visible", text="👁️")
        self.layers_tree.heading("locked", text="🔒")

        # Dimensioni colonne ripristinate dalla configurazione
        config = layout_manager.config
        self.layers_tree.column(
            "#0", width=config.layers_tree_column_0, minwidth=150, stretch=True
        )
        self.layers_tree.column(
            "visible",
            width=config.layers_tree_column_visible,
            minwidth=35,
            stretch=False,
        )
        self.layers_tree.column(
            "locked", width=config.layers_tree_column_locked, minwidth=35, stretch=False
        )

        # Scrollbar per la lista layers
        layers_scroll = ttk.Scrollbar(
            layers_frame, orient=tk.VERTICAL, command=self.layers_tree.yview
        )
        self.layers_tree.configure(yscrollcommand=layers_scroll.set)

        # Layout con pack per layers_tree e scrollbar
        self.layers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(5, 0))
        layers_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(5, 0))

        self.layers_tree.bind("<Button-1>", self.on_layer_click)
        self.layers_tree.bind("<Double-1>", self.on_layer_double_click)

        # Bind per salvare configurazione colonne quando cambiano
        self.layers_tree.bind("<Button1-Motion>", self._on_tree_column_resize)
        self.layers_tree.bind("<ButtonRelease-1>", self._on_tree_column_resize_end)

        # Pannello proprietà oggetti nel frame strumenti
        props_frame = ttk.LabelFrame(tools_frame, text="Proprietà", padding=5)
        props_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.props_text = tk.Text(props_frame, height=4, wrap=tk.WORD)
        props_scroll = ttk.Scrollbar(
            props_frame, orient=tk.VERTICAL, command=self.props_text.yview
        )
        self.props_text.configure(yscrollcommand=props_scroll.set)

        self.props_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        props_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.update_layers_tree()

        # Ripristina posizione divisore verticale
        self.right_paned.after(100, self._restore_vertical_paned)

    def _restore_vertical_paned(self):
        """Ripristina la posizione del divisore verticale."""
        try:
            # Imposta una divisione 30/70 tra strumenti e layers
            height = self.right_paned.winfo_height()
            if height > 100:
                position = int(height * 0.3)  # 30% per strumenti, 70% per layers
                self.right_paned.sashpos(0, position)
        except:
            pass

    def _on_tree_column_resize(self, event=None):
        """Callback per ridimensionamento colonne del tree."""
        pass  # Durante il trascinamento non facciamo nulla

    def _on_tree_column_resize_end(self, event=None):
        """Callback finale per salvare dimensioni colonne."""
        try:
            # Salva le dimensioni attuali delle colonne
            config = layout_manager.config
            config.layers_tree_column_0 = self.layers_tree.column("#0", "width")
            config.layers_tree_column_visible = self.layers_tree.column(
                "visible", "width"
            )
            config.layers_tree_column_locked = self.layers_tree.column(
                "locked", "width"
            )
        except:
            pass

    def create_tooltip(self, widget, text):
        """Crea un tooltip per un widget."""

        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(
                tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1
            )
            label.pack()
            widget.tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, "tooltip"):
                widget.tooltip.destroy()
                del widget.tooltip

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def bind_events(self):
        """Collega gli eventi del mouse al canvas."""
        self.mpl_canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.mpl_canvas.mpl_connect("button_release_event", self.on_mouse_release)
        self.mpl_canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        self.mpl_canvas.mpl_connect("scroll_event", self.on_scroll)
        self.mpl_canvas.mpl_connect("key_press_event", self.on_key_press)

        # Gestione focus per migliorare responsività
        canvas_widget = self.mpl_canvas.get_tk_widget()
        canvas_widget.bind("<Enter>", self._on_canvas_enter)
        canvas_widget.bind("<Leave>", self._on_canvas_leave)
        canvas_widget.bind("<Button-1>", self._on_canvas_focus)

    def _on_canvas_enter(self, event):
        """Chiamato quando il mouse entra nel canvas."""
        self.mpl_canvas.get_tk_widget().focus_set()
        # Assicura che tutti i binding siano attivi
        self.mpl_canvas.get_tk_widget().focus_force()

    def _on_canvas_leave(self, event):
        """Chiamato quando il mouse esce dal canvas."""
        if self.is_panning:
            self.stop_panning()

    def _on_canvas_focus(self, event):
        """Assicura che il canvas abbia sempre il focus per gli eventi."""
        self.mpl_canvas.get_tk_widget().focus_set()
        self.mpl_canvas.get_tk_widget().focus_force()

    def set_tool(self, tool):
        """Imposta lo strumento corrente."""
        self.current_tool = tool
        self.selected_objects.clear()
        self.update_status(f"Strumento: {tool.value}")

        # Debug per PAN
        if tool == Tool.PAN:
            print(f"🔧 Tool PAN attivato: {tool}")

        # Aggiorna cursore
        if tool == Tool.PAN:
            self.mpl_canvas.get_tk_widget().configure(cursor="fleur")
        elif tool in [Tool.ZOOM_IN, Tool.ZOOM_OUT]:
            self.mpl_canvas.get_tk_widget().configure(cursor="sizing")
        elif tool in [Tool.LINE, Tool.ARROW, Tool.RECTANGLE, Tool.CIRCLE]:
            self.mpl_canvas.get_tk_widget().configure(cursor="cross")
        else:
            self.mpl_canvas.get_tk_widget().configure(cursor="arrow")

    def on_mouse_press(self, event):
        """Gestisce il click del mouse."""
        if event.inaxes != self.ax:
            return

        self.start_point = (event.xdata, event.ydata)

        # Gestione PAN - può essere attivato con:
        # 1. Tool PAN attivo + click sinistro
        # 2. Click con pulsante medio (per touchpad gesture)
        # 3. Ctrl + click sinistro
        if (
            (self.current_tool == Tool.PAN and event.button == 1)
            or event.button == 2
            or (event.button == 1 and event.key == "control")
        ):
            print(
                f"🖱️ PAN attivato - Tool: {self.current_tool}, Button: {event.button}, Key: {event.key}"
            )
            self.start_panning(event)
            # IMPORTANTE: Imposta is_drawing per ricevere eventi move e fai return per evitare altri tool
            self.is_drawing = True
            return  # IMPORTANTE: Return qui per evitare che altri tool interferiscano

        # Altri tool
        if self.current_tool == Tool.SELECTION:
            self.handle_selection(event)
        elif self.current_tool in [
            Tool.LINE,
            Tool.ARROW,
            Tool.RECTANGLE,
            Tool.CIRCLE,
            Tool.POLYGON,
        ]:
            self.start_drawing(event)
        elif self.current_tool == Tool.TEXT:
            self.add_text(event)
        elif self.current_tool in [Tool.RULER_H, Tool.RULER_V]:
            self.add_ruler(event)

        self.is_drawing = True

    def on_mouse_release(self, event):
        """Gestisce il rilascio del mouse."""
        # Termina panning (anche se mouse esce dall'area)
        if self.is_panning:
            self.stop_panning()
            self.is_drawing = False  # Reset is_drawing per PAN
            return

        if not self.is_drawing or event.inaxes != self.ax:
            return

        end_point = (event.xdata, event.ydata)

        if self.current_tool in [Tool.LINE, Tool.ARROW, Tool.RECTANGLE, Tool.CIRCLE]:
            self.finish_drawing(end_point)
        elif self.current_tool == Tool.POLYGON and event.dblclick:
            self.finish_polygon()

        self.is_drawing = False
        self.cleanup_temp_artist()

    def on_mouse_move(self, event):
        """Gestisce il movimento del mouse."""
        if event.inaxes != self.ax:
            return

        # Aggiorna coordinate
        if event.xdata is not None and event.ydata is not None:
            self.coords_var.set(f"({int(event.xdata)}, {int(event.ydata)})")

        # Gestione PAN (trascinamento vista)
        if self.is_panning:
            self.update_panning(event)
            return

        # Gestione normale disegno
        if self.is_drawing and self.start_point:
            current_point = (event.xdata, event.ydata)
            self.preview_drawing(current_point)

    def start_drawing(self, event):
        """Inizia il disegno di una forma."""
        self.cleanup_temp_artist()

    def preview_drawing(self, current_point):
        """Mostra anteprima durante il disegno."""
        if not self.start_point:
            return

        self.cleanup_temp_artist()

        x1, y1 = self.start_point
        x2, y2 = current_point

        if self.current_tool == Tool.LINE:
            self.temp_artist = Line2D(
                [x1, x2],
                [y1, y2],
                color=self.current_color,
                linewidth=self.line_width,
                alpha=0.7,
            )
            self.ax.add_artist(self.temp_artist)

        elif self.current_tool == Tool.RECTANGLE:
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            x = min(x1, x2)
            y = min(y1, y2)
            self.temp_artist = Rectangle(
                (x, y),
                width,
                height,
                fill=False,
                edgecolor=self.current_color,
                linewidth=self.line_width,
                alpha=0.7,
            )
            self.ax.add_patch(self.temp_artist)

        elif self.current_tool == Tool.CIRCLE:
            radius = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            self.temp_artist = Circle(
                (x1, y1),
                radius,
                fill=False,
                edgecolor=self.current_color,
                linewidth=self.line_width,
                alpha=0.7,
            )
            self.ax.add_patch(self.temp_artist)

        elif self.current_tool == Tool.ARROW:
            self.temp_artist = FancyArrowPatch(
                (x1, y1),
                (x2, y2),
                arrowstyle="->",
                mutation_scale=20,
                color=self.current_color,
                linewidth=self.line_width,
                alpha=0.7,
            )
            self.ax.add_patch(self.temp_artist)

        self.mpl_canvas.draw_idle()

    def finish_drawing(self, end_point):
        """Completa il disegno di una forma."""
        if not self.start_point:
            return

        x1, y1 = self.start_point
        x2, y2 = end_point

        artist = None
        obj_type = self.current_tool.value

        if self.current_tool == Tool.LINE:
            artist = Line2D(
                [x1, x2], [y1, y2], color=self.current_color, linewidth=self.line_width
            )
            self.ax.add_artist(artist)

        elif self.current_tool == Tool.RECTANGLE:
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            x = min(x1, x2)
            y = min(y1, y2)
            artist = Rectangle(
                (x, y),
                width,
                height,
                fill=False,
                edgecolor=self.current_color,
                linewidth=self.line_width,
            )
            self.ax.add_patch(artist)

        elif self.current_tool == Tool.CIRCLE:
            radius = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            artist = Circle(
                (x1, y1),
                radius,
                fill=False,
                edgecolor=self.current_color,
                linewidth=self.line_width,
            )
            self.ax.add_patch(artist)

        elif self.current_tool == Tool.ARROW:
            artist = FancyArrowPatch(
                (x1, y1),
                (x2, y2),
                arrowstyle="->",
                mutation_scale=20,
                color=self.current_color,
                linewidth=self.line_width,
            )
            self.ax.add_patch(artist)

        if artist:
            self.add_drawing_object(artist, obj_type)

        self.mpl_canvas.draw()

    def add_drawing_object(self, artist, obj_type):
        """Aggiunge un oggetto disegnato al sistema di gestione."""
        obj_id = str(uuid.uuid4())
        drawing_obj = DrawingObject(
            id=obj_id,
            type=obj_type,
            layer_id=self.current_layer_id,
            artist=artist,
            properties={"color": self.current_color, "line_width": self.line_width},
        )

        self.drawing_objects[obj_id] = drawing_obj

        # Aggiunge all'oggetto corrente del layer
        current_layer = self.get_current_layer()
        if current_layer:
            current_layer.objects.append(drawing_obj)

    def cleanup_temp_artist(self):
        """Rimuove l'artist temporaneo."""
        if self.temp_artist:
            if hasattr(self.temp_artist, "remove"):
                self.temp_artist.remove()
            else:
                # Per Line2D che usa add_artist
                try:
                    self.ax.artists.remove(self.temp_artist)
                except ValueError:
                    pass
            self.temp_artist = None

    def add_text(self, event):
        """Aggiunge testo al canvas."""
        text = simpledialog.askstring("Testo", "Inserisci il testo:")
        if text:
            artist = self.ax.text(
                event.xdata,
                event.ydata,
                text,
                fontsize=self.font_size,
                color=self.current_color,
            )
            self.add_drawing_object(artist, Tool.TEXT.value)
            self.mpl_canvas.draw()

    def add_ruler(self, event):
        """Aggiunge un righello."""
        if self.current_tool == Tool.RULER_H:
            line = self.ax.axhline(
                y=event.ydata, color="red", linestyle="--", alpha=0.7
            )
            self.rulers["horizontal"].append(line)
        else:
            line = self.ax.axvline(
                x=event.xdata, color="red", linestyle="--", alpha=0.7
            )
            self.rulers["vertical"].append(line)

        self.mpl_canvas.draw()

    def handle_selection(self, event):
        """Gestisce la selezione di oggetti e chiamate per misurazioni."""
        # Se abbiamo un callback per misurazioni (integrazione con CanvasApp), chiamalo
        if self.measurement_callback and callable(self.measurement_callback):
            self.measurement_callback(event)

        # TODO: Implementare logica di selezione oggetti disegnati
        # (per ora deleghiamo tutto al callback del CanvasApp)

    def choose_color(self):
        """Apre il selettore colore."""
        color = colorchooser.askcolor(title="Scegli colore", color=self.current_color)
        if color[1]:
            self.current_color = color[1]
            self.color_button.config(bg=self.current_color)

    def on_line_width_change(self):
        """Gestisce il cambio di spessore linea."""
        self.line_width = self.width_var.get()

    def toggle_snap(self):
        """Attiva/disattiva lo snap alla griglia."""
        self.snap_to_grid = self.snap_var.get()

    def toggle_grid(self):
        """Attiva/disattiva la griglia."""
        self.show_grid = not self.show_grid
        self.ax.grid(self.show_grid)
        self.mpl_canvas.draw()

    def fit_to_window(self):
        """Adatta l'immagine alla finestra."""
        if self.current_image is not None:
            # Usa _on_canvas_resize per adattare automaticamente
            self._on_canvas_resize()
        else:
            self.reset_view()

    def fit_image_to_canvas(self):
        """Forza l'adattamento dell'immagine alle dimensioni correnti del canvas."""
        if self.current_image is not None:
            # Forza il ricalcolo delle dimensioni
            self.parent.after(50, self._on_canvas_resize)
            self.update_status("Immagine adattata al canvas")
        else:
            self.update_status("Nessuna immagine da adattare")

    def reset_view(self):
        """Reimposta la vista del canvas."""
        if self.current_image is not None:
            # Se abbiamo un'immagine, adatta alla finestra
            self.fit_to_window()
        else:
            # Canvas vuoto: inizializza con griglia
            self.initialize_empty_canvas()

    def clear_canvas(self):
        """Pulisce il canvas e reimposta la vista di default."""
        self.current_image = None
        self.ax.clear()
        self.initialize_empty_canvas()

    def set_image(self, image):
        """Imposta l'immagine di sfondo del canvas con ridimensionamento automatico."""
        if isinstance(image, Image.Image):
            self.current_image = image
            # Converte PIL Image in array numpy
            img_array = np.array(image)

            # Pulisce il canvas
            self.ax.clear()

            # Mostra l'immagine
            im = self.ax.imshow(img_array, aspect="equal")

            # Mantieni griglia se abilitata (più sottile per non coprire l'immagine)
            if self.show_grid:
                self.ax.grid(True, alpha=0.1, linewidth=0.5)

            # Etichette degli assi più discrete
            self.ax.set_xlabel("X (pixel)", fontsize=9)
            self.ax.set_ylabel("Y (pixel)", fontsize=9)
            self.ax.tick_params(axis="both", which="major", labelsize=8)

            # Adatta immediatamente alle dimensioni dell'immagine per una visualizzazione ottimale
            self.ax.set_xlim(0, image.width)
            self.ax.set_ylim(image.height, 0)

            # Ridisegna subito
            self.mpl_canvas.draw()

            # Poi adatta automaticamente al canvas dopo un breve delay
            self.parent.after(200, self._on_canvas_resize)

            self.update_status(f"Immagine caricata: {image.width}x{image.height}")

    def set_image_no_resize(self, image):
        """Imposta l'immagine di sfondo del canvas SENZA ridimensionamento automatico."""
        if isinstance(image, Image.Image):
            self.current_image = image
            # Converte PIL Image in array numpy
            img_array = np.array(image)

            # Ottieni dimensioni dell'immagine
            img_height, img_width = img_array.shape[:2]

            # Pulisce il canvas e salva i limiti attuali
            current_xlim = self.ax.get_xlim()
            current_ylim = self.ax.get_ylim()

            self.ax.clear()

            # Mostra l'immagine
            self.ax.imshow(img_array, aspect="equal")

            # Verifica se i limiti attuali sono ragionevoli per l'immagine
            xlim_range = current_xlim[1] - current_xlim[0]
            ylim_range = current_ylim[1] - current_ylim[0]

            # Se i limiti sono troppo piccoli o troppo grandi rispetto all'immagine, resettali
            if (
                xlim_range < img_width * 0.1
                or xlim_range > img_width * 10
                or ylim_range < img_height * 0.1
                or ylim_range > img_height * 10
                or current_xlim[0] < -img_width
                or current_xlim[1] > img_width * 2
                or current_ylim[0] < -img_height
                or current_ylim[1] > img_height * 2
            ):
                # Usa limiti predefiniti basati sulle dimensioni dell'immagine
                self.ax.set_xlim(0, img_width)
                self.ax.set_ylim(img_height, 0)  # Inverti Y per coordinate immagine
                print(
                    f"🔧 Limiti canvas resettati per immagine {img_width}x{img_height}"
                )
            else:
                # Ripristina limiti precedenti se sono ragionevoli
                self.ax.set_xlim(current_xlim)
                self.ax.set_ylim(current_ylim)
                print(f"✅ Limiti canvas mantenuti: X{current_xlim}, Y{current_ylim}")

            # Mantieni griglia e etichette se abilitati
            if self.show_grid:
                self.ax.grid(True, alpha=0.3)

            self.ax.set_xlabel("X (pixel)", fontsize=10)
            self.ax.set_ylabel("Y (pixel)", fontsize=10)

            # Ridisegna senza modificare dimensioni
            self.mpl_canvas.draw()

    # === GESTIONE LAYER ===

    def add_layer(self):
        """Aggiunge un nuovo layer."""
        name = simpledialog.askstring("Nuovo layer", "Nome del layer:")
        if name:
            new_layer = Layer(
                id=str(uuid.uuid4()), name=name, visible=True, locked=False
            )
            self.layers.append(new_layer)
            self.current_layer_id = new_layer.id
            self.update_layers_tree()

    def remove_layer(self):
        """Rimuove il layer corrente."""
        if len(self.layers) <= 1:
            messagebox.showwarning("Errore", "Non puoi rimuovere l'ultimo layer")
            return

        current_layer = self.get_current_layer()
        if current_layer:
            # Rimuove tutti gli oggetti del layer
            for obj in current_layer.objects:
                if obj.artist and hasattr(obj.artist, "remove"):
                    obj.artist.remove()
                del self.drawing_objects[obj.id]

            self.layers.remove(current_layer)
            self.current_layer_id = self.layers[0].id
            self.update_layers_tree()
            self.mpl_canvas.draw()

    def move_layer_up(self):
        """Sposta il layer corrente verso l'alto."""
        current_layer = self.get_current_layer()
        if current_layer:
            index = self.layers.index(current_layer)
            if index > 0:
                self.layers[index], self.layers[index - 1] = (
                    self.layers[index - 1],
                    self.layers[index],
                )
                self.update_layers_tree()

    def move_layer_down(self):
        """Sposta il layer corrente verso il basso."""
        current_layer = self.get_current_layer()
        if current_layer:
            index = self.layers.index(current_layer)
            if index < len(self.layers) - 1:
                self.layers[index], self.layers[index + 1] = (
                    self.layers[index + 1],
                    self.layers[index],
                )
                self.update_layers_tree()

    def get_current_layer(self):
        """Restituisce il layer corrente."""
        for layer in self.layers:
            if layer.id == self.current_layer_id:
                return layer
        return None

    def update_layers_tree(self):
        """Aggiorna la visualizzazione dei layer."""
        # Usa il layers_tree esterno se disponibile, altrimenti il proprio
        layers_tree = getattr(self, "external_layers_tree", None) or getattr(
            self, "layers_tree", None
        )

        if not layers_tree:
            return

        # Pulisce la tree
        for item in layers_tree.get_children():
            layers_tree.delete(item)

        # Aggiunge i layer
        for i, layer in enumerate(reversed(self.layers)):
            visible = "👁️" if layer.visible else "👁️‍🗨️"
            locked = "🔒" if layer.locked else "🔓"

            item = layers_tree.insert(
                "", "end", text=layer.name, values=(visible, locked)
            )

            # Evidenzia il layer corrente
            if layer.id == self.current_layer_id:
                layers_tree.selection_set(item)

    def on_layer_click(self, event):
        """Gestisce il click sui layer."""
        try:
            item = self.layers_tree.identify("item", event.x, event.y)
            if not item:
                return

            # Ottiene l'indice del layer (invertito)
            index = len(self.layers) - 1 - self.layers_tree.index(item)
            if index < 0 or index >= len(self.layers):
                return

            layer = self.layers[index]

            # Approccio semplificato: usa le coordinate per determinare la colonna
            bbox = self.layers_tree.bbox(item)
            if bbox:
                item_x, item_y, item_width, item_height = bbox
                relative_x = event.x - item_x

                # Calcola approssimativamente su quale colonna si è cliccato
                # Colonna #0 (nome) è ampia, #1 e #2 sono larghe 50 pixel ciascuna
                name_col_width = (
                    item_width - 100
                )  # Sottrai larghezza delle altre due colonne (50+50)

                if relative_x > name_col_width and relative_x <= name_col_width + 50:
                    # Click sulla colonna visible (#1)
                    layer.visible = not layer.visible
                    self.toggle_layer_visibility(layer)
                elif relative_x > name_col_width + 50:
                    # Click sulla colonna locked (#2)
                    layer.locked = not layer.locked
                else:
                    # Click sul nome del layer
                    self.current_layer_id = layer.id
            else:
                # Fallback: seleziona il layer
                self.current_layer_id = layer.id

            self.update_layers_tree()

        except Exception as e:
            # Se c'è qualsiasi errore, semplicemente seleziona il layer
            try:
                item = self.layers_tree.identify("item", event.x, event.y)
                if item:
                    index = len(self.layers) - 1 - self.layers_tree.index(item)
                    if 0 <= index < len(self.layers):
                        self.current_layer_id = self.layers[index].id
                        self.update_layers_tree()
            except:
                pass  # Ignora errori nel fallback

    def on_layer_double_click(self, event):
        """Gestisce il doppio click sui layer per rinominare."""
        item = self.layers_tree.identify("item", event.x, event.y)
        if item:
            index = len(self.layers) - 1 - self.layers_tree.index(item)
            layer = self.layers[index]

            new_name = simpledialog.askstring(
                "Rinomina layer", "Nuovo nome:", initialvalue=layer.name
            )
            if new_name:
                layer.name = new_name
                self.update_layers_tree()

    def toggle_layer_visibility(self, layer):
        """Attiva/disattiva la visibilità di un layer."""
        for obj in layer.objects:
            if obj.artist:
                obj.artist.set_visible(layer.visible)
        self.mpl_canvas.draw()

    def on_scroll(self, event):
        """Gestisce lo scroll del mouse per zoom."""
        # Zoom sempre attivo con Ctrl o quando si è in modalità zoom
        if event.key == "control" or self.current_tool in [Tool.ZOOM_IN, Tool.ZOOM_OUT]:
            base_scale = 1.2
            # CORRETTO: scroll up = zoom in (ingrandisce), scroll down = zoom out (rimpicciolisce)
            if event.button == "up":
                scale_factor = 1 / base_scale  # Zoom IN (ingrandisce)
            else:
                scale_factor = base_scale  # Zoom OUT (rimpicciolisce)

            # Se il mouse è fuori dall'area dati, usa il centro dell'immagine
            if event.xdata is None or event.ydata is None:
                xlim = self.ax.get_xlim()
                ylim = self.ax.get_ylim()
                x = (xlim[0] + xlim[1]) / 2
                y = (ylim[0] + ylim[1]) / 2
            else:
                x, y = event.xdata, event.ydata

            self.zoom_at_point(x, y, scale_factor)

    def zoom_at_point(self, x, y, scale_factor):
        """Effettua zoom intorno a un punto specifico."""
        if x is None or y is None:
            return

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # Calcola nuovo range
        xrange = (xlim[1] - xlim[0]) * scale_factor
        yrange = (ylim[1] - ylim[0]) * scale_factor

        # Centro il zoom sul punto
        new_xlim = (x - xrange / 2, x + xrange / 2)
        new_ylim = (y - yrange / 2, y + yrange / 2)

        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.mpl_canvas.draw()

    def zoom_in(self):
        """Zoom in (ingrandisce) centrato sull'area visibile."""
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # Centro dell'area visibile
        center_x = (xlim[0] + xlim[1]) / 2
        center_y = (ylim[0] + ylim[1]) / 2

        # Zoom in con fattore 1.2 (ingrandisce)
        self.zoom_at_point(center_x, center_y, 1 / 1.2)
        self.update_status("Zoom in applicato")

    def zoom_out(self):
        """Zoom out (rimpicciolisce) centrato sull'area visibile."""
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # Centro dell'area visibile
        center_x = (xlim[0] + xlim[1]) / 2
        center_y = (ylim[0] + ylim[1]) / 2

        # Zoom out con fattore 1.2 (rimpicciolisce)
        self.zoom_at_point(center_x, center_y, 1.2)
        self.update_status("Zoom out applicato")

    def start_panning(self, event):
        """Inizia il panning (trascinamento vista)."""
        if event.xdata is None or event.ydata is None:
            return

        self.is_panning = True
        self.pan_start_point = (event.xdata, event.ydata)
        self.pan_start_xlim = self.ax.get_xlim()
        self.pan_start_ylim = self.ax.get_ylim()

        # Assicura che il canvas abbia il focus per ricevere tutti gli eventi
        self.mpl_canvas.get_tk_widget().focus_set()

        # Cambia cursore per indicare panning attivo
        self.mpl_canvas.get_tk_widget().configure(cursor="fleur")
        self.update_status("Panning attivo - trascina per muovere la vista")

    def update_panning(self, event):
        """Aggiorna la vista durante il panning."""
        if not self.is_panning or event.xdata is None or event.ydata is None:
            return

        if (
            self.pan_start_point is None
            or self.pan_start_xlim is None
            or self.pan_start_ylim is None
        ):
            return

        # Calcola lo spostamento
        dx = event.xdata - self.pan_start_point[0]
        dy = event.ydata - self.pan_start_point[1]

        # Applica lo spostamento (inverso per simulare trascinamento)
        new_xlim = (self.pan_start_xlim[0] - dx, self.pan_start_xlim[1] - dx)
        new_ylim = (self.pan_start_ylim[0] - dy, self.pan_start_ylim[1] - dy)

        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)

        # USA draw() invece di draw_idle() per evitare sfarfallio
        self.mpl_canvas.draw()

        # Debug: mostra le coordinate durante il panning
        self.update_status(
            f"Panning: dx={dx:.1f}, dy={dy:.1f} | Limiti: x={new_xlim[0]:.0f}-{new_xlim[1]:.0f}, y={new_ylim[0]:.0f}-{new_ylim[1]:.0f}"
        )

    def stop_panning(self):
        """Termina il panning."""
        if not self.is_panning:
            return

        self.is_panning = False
        self.pan_start_point = None
        self.pan_start_xlim = None
        self.pan_start_ylim = None

        # Ripristina cursore normale o del tool corrente
        if self.current_tool == Tool.PAN:
            self.mpl_canvas.get_tk_widget().configure(cursor="fleur")
        elif self.current_tool in [Tool.ZOOM_IN, Tool.ZOOM_OUT]:
            self.mpl_canvas.get_tk_widget().configure(cursor="sizing")
        elif self.current_tool in [Tool.LINE, Tool.ARROW, Tool.RECTANGLE, Tool.CIRCLE]:
            self.mpl_canvas.get_tk_widget().configure(cursor="cross")
        else:
            self.mpl_canvas.get_tk_widget().configure(cursor="arrow")

        self.update_status("Panning terminato")

    def on_key_press(self, event):
        """Gestisce la pressione dei tasti."""
        if event.key == "delete":
            self.delete_selected_objects()
        elif event.key == "ctrl+z":
            self.undo()
        elif event.key == "ctrl+y":
            self.redo()

    def delete_selected_objects(self):
        """Elimina gli oggetti selezionati."""
        for obj_id in self.selected_objects:
            if obj_id in self.drawing_objects:
                obj = self.drawing_objects[obj_id]
                if obj.artist and hasattr(obj.artist, "remove"):
                    obj.artist.remove()
                del self.drawing_objects[obj_id]

                # Rimuove dal layer
                for layer in self.layers:
                    layer.objects = [o for o in layer.objects if o.id != obj_id]

        self.selected_objects.clear()
        self.mpl_canvas.draw()

    def undo(self):
        """Annulla l'ultima operazione."""
        # TODO: Implementare sistema di undo/redo
        pass

    def redo(self):
        """Ripete l'ultima operazione annullata."""
        # TODO: Implementare sistema di undo/redo
        pass

    def update_status(self, message):
        """Aggiorna la barra di stato."""
        self.status_var.set(message)

    def clear_canvas(self):
        """Pulisce tutto il canvas."""
        self.ax.clear()
        self.drawing_objects.clear()
        self.selected_objects.clear()

        for layer in self.layers:
            layer.objects.clear()

        self.rulers = {"horizontal": [], "vertical": []}

        if self.current_image:
            self.set_image(self.current_image)
        else:
            self.mpl_canvas.draw()

    def export_measurements(self):
        """Esporta le misurazioni in formato JSON."""
        measurements = {}

        for obj_id, obj in self.drawing_objects.items():
            if obj.type in ["line", "measure"]:
                # Calcola lunghezza linea
                if hasattr(obj.artist, "get_xydata"):
                    data = obj.artist.get_xydata()
                    if len(data) >= 2:
                        length = np.sqrt(
                            (data[1][0] - data[0][0]) ** 2
                            + (data[1][1] - data[0][1]) ** 2
                        )
                        measurements[obj_id] = {
                            "type": "distance",
                            "value": length,
                            "start": data[0].tolist(),
                            "end": data[1].tolist(),
                        }

        return measurements


# Funzione di utilità per integrare il canvas professionale
def create_professional_canvas(parent, width=800, height=600):
    """Crea e restituisce un'istanza del canvas professionale."""
    return ProfessionalCanvas(parent, width, height)


if __name__ == "__main__":
    # Test del canvas professionale
    root = tk.Tk()
    root.title("Professional Canvas Test")
    root.geometry("1400x900")

    canvas = ProfessionalCanvas(root)

    # Test con un'immagine di esempio
    test_image = Image.new("RGB", (800, 600), color="lightblue")
    canvas.set_image(test_image)

    root.mainloop()
