"""
Interactive canvas application for facial analysis with measurement tools.
VERSIONE UNIFICATA - Include funzionalità professional canvas integrate
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import List, Tuple, Optional, Dict, Any
import uuid
from dataclasses import dataclass
from enum import Enum

# Import componenti core
from src.face_detector import FaceDetector
from src.video_analyzer import VideoAnalyzer
from src.measurement_tools import MeasurementTools
from src.green_dots_processor import GreenDotsProcessor
from src.scoring_config import ScoringConfig
from src.utils import resize_image_keep_aspect
from src.layout_manager import layout_manager

# Canvas system unificato - sistema integrato senza professional_canvas
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle, Polygon, FancyArrowPatch
from matplotlib.lines import Line2D
from matplotlib.text import Text
import matplotlib.patches as patches


# === ENUM E CLASSI PROFESSIONALI INTEGRATE ===


class Tool(Enum):
    """Strumenti canvas professionale integrati."""

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
    """Layer del canvas professionale."""

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
    """Oggetto di disegno."""

    id: str
    type: str
    layer_id: str
    artist: Any  # Matplotlib artist object
    properties: Dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}


class ToolTip:
    """Classe per creare tooltip su widget Tkinter."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)

    def on_enter(self, event=None):
        """Mostra il tooltip."""
        if self.tooltip_window or not self.text:
            return

        # Calcola la posizione del tooltip in modo più sicuro
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + 20
        except tk.TclError:
            return

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=("TkDefaultFont", "8", "normal"),
        )
        label.pack(ipadx=1)

    def on_leave(self, event=None):
        """Nasconde il tooltip."""
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except tk.TclError:
                pass
            self.tooltip_window = None


class CanvasApp:
    def __init__(self, root):
        """Inizializza l'applicazione canvas."""
        self.root = root
        self.root.title("Facial Analysis Canvas")
        # Geometria gestita da main.py - non sovrascrivere
        self.root.minsize(1200, 800)  # Dimensione minima
        self.root.resizable(True, True)  # Finestra ridimensionabile

        # Componenti principali
        self.face_detector = FaceDetector()
        self.video_analyzer = VideoAnalyzer()
        self.measurement_tools = MeasurementTools()
        self.green_dots_processor = GreenDotsProcessor()

        # Variabili di stato per canvas tkinter (RIPRISTINATE)
        self.current_image = None
        self.current_landmarks = None

        # Variabili canvas tkinter ripristinate
        self.canvas_image = None  # Per il canvas tkinter
        self.canvas_scale = 1.0  # Per lo zoom del canvas tkinter
        self.canvas_offset = (0, 0)  # Per il panning del canvas tkinter
        self.current_canvas_tool = "SELECTION"  # Tool attivo per il canvas
        # self.active_layer e self.layers_list già definiti sopra

        # Sistema di memorizzazione coordinate originali per scaling corretto
        self.original_drawing_coords = {}  # Dizionario per coordinate originali

        # Variabili per display e scaling (MANTENUTE per retrocompatibilità)
        self.display_scale = 1.0
        self.display_size = (800, 600)  # Default size

        self.selected_points = []
        self.selected_landmarks = []  # Landmark selezionati per misurazione
        self.measurement_mode = "distance"
        self.measurement_result = None  # Risultato dell'ultima misurazione
        self.landmark_measurement_mode = True  # True per modalità landmark (default)
        self.show_all_landmarks = False  # True per mostrare tutti i 468 landmarks
        self.show_measurements = True

        # Sistema overlay per misurazioni
        self.measurement_overlays = []  # Lista di overlay delle misurazioni
        self.show_measurement_overlays = True

        # Sistema per puntini verdi sopraccigliare
        self.green_dots_results = None  # Risultati dell'ultimo rilevamento
        self.green_dots_overlay = None  # Overlay dei poligoni sopraccigliare
        self.show_green_dots_overlay = False  # Flag per mostrare l'overlay

        # === STATO CANVAS PROFESSIONALE INTEGRATO ===
        self.current_tool = Tool.SELECTION
        self.draw_mode = DrawMode.DRAWING
        self.is_drawing = False
        self.start_point = None
        self.current_color = "#FF0000"
        self.line_width = 2
        self.font_size = 12
        self.snap_to_grid = False
        self.grid_size = 20

        # Variabili per PAN (trascinamento vista) - INTEGRATE
        self.is_panning = False
        self.pan_start_point = None
        self.pan_start_xlim = None
        self.pan_start_ylim = None

        # Sistema layer unificato
        self.layers_list = []  # Lista unificata dei layer
        self.active_layer = None  # Layer attualmente attivo per i nuovi disegni
        self.create_default_layer_unified()

        # Oggetti disegnati integrati
        self.drawing_objects = {}
        self.selected_objects = []
        self.temp_artist = None  # Per preview durante il disegno

        # Rulers e guide integrate
        self.rulers = {"horizontal": [], "vertical": []}
        self.show_grid = True
        self.show_rulers = True

        # Stato per overlay di misurazioni predefinite (per logica toggle)
        self.preset_overlays = {
            "face_width": None,
            "face_height": None,
            "eye_distance": None,
            "nose_width": None,
            "mouth_width": None,
            "eyebrow_areas": None,
            "eye_areas": None,
        }

        # Variabile per tracciare il miglior score corrente per aggiornamento dinamico
        self.current_best_score = 0.0

        # Buffer per salvare i migliori frame per il doppio click
        self.frame_buffer = {}  # {frame_number: (frame, landmarks)}
        self.max_buffer_size = (
            100  # Massimo numero di frame nel buffer - AUMENTATO per debug table
        )

        # Variabili per interfaccia semplificata
        self.preview_enabled = None  # Inizializzato nel setup GUI
        self.preview_label = None
        self.preview_window = None  # Per compatibilità con close_preview_window

        # Controlli player video
        self.is_playing = False
        self.current_time_var = tk.StringVar(value="00:00")
        self.total_time_var = tk.StringVar(value="00:00")
        self.seek_var = tk.DoubleVar(value=0)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.updating_seek = (
            False  # Flag per evitare loop durante aggiornamento seek bar
        )

        # Configurazione pesi per scoring
        self.scoring_config = ScoringConfig()
        self.scoring_config.set_callback(self.on_scoring_config_change)

        # Imposta la configurazione nel video analyzer
        self.video_analyzer.set_scoring_config(self.scoring_config)

        self.setup_gui()

        # CALLBACK ESSENZIALI
        self.video_analyzer.set_completion_callback(self.on_analysis_completion)
        self.video_analyzer.set_preview_callback(self.on_video_preview_update)
        self.video_analyzer.set_frame_callback(self.on_frame_update)  # *** AGGIUNTO ***
        self.video_analyzer.set_debug_callback(
            self.on_debug_update
        )  # *** NUOVO PER TABELLA ***

    def create_default_layer_unified(self):
        """Crea il layer di default per il sistema unificato."""
        import uuid

        default_layer = {
            "id": str(uuid.uuid4()),
            "name": "Layer Base",
            "tag": "layer_base",
            "visible": True,
            "locked": False,
        }
        self.layers_list.append(default_layer)
        self.active_layer = default_layer
        print("🏗️ Layer Base creato e impostato come attivo")

    def setup_gui(self):
        """Configura l'interfaccia grafica con layout ridimensionabile."""
        # Menu principale
        self.create_menu()

        # Configura la griglia principale per espandersi (geometria già impostata da main.py)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # PANNELLO VERTICALE PRINCIPALE (area principale | misurazioni)
        self.main_vertical_paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.main_vertical_paned.grid(row=0, column=0, sticky="nsew")

        # PANNELLI PRINCIPALI: Controlli | Canvas | (Layers + Anteprima)
        # PanedWindow orizzontale per la parte superiore (controlli | canvas | sidebar)
        self.main_horizontal_paned = ttk.PanedWindow(
            self.main_vertical_paned, orient=tk.HORIZONTAL
        )
        self.main_vertical_paned.add(self.main_horizontal_paned, weight=1)

        # PANNELLO CONTROLLI (sinistra)
        control_main_frame = ttk.LabelFrame(
            self.main_horizontal_paned, text="Controlli", padding=2, width=400
        )
        control_main_frame.grid_columnconfigure(0, weight=1)
        control_main_frame.grid_rowconfigure(0, weight=1)
        self.main_horizontal_paned.add(control_main_frame, weight=1)

        # Canvas scrollabile per i controlli
        control_canvas = tk.Canvas(control_main_frame, highlightthickness=0, width=400)
        control_scrollbar = ttk.Scrollbar(
            control_main_frame, orient="vertical", command=control_canvas.yview
        )
        self.scrollable_control_frame = ttk.Frame(control_canvas, padding=10)

        self.scrollable_control_frame.bind(
            "<Configure>",
            lambda e: control_canvas.configure(scrollregion=control_canvas.bbox("all")),
        )

        control_canvas.create_window(
            (0, 0), window=self.scrollable_control_frame, anchor="nw"
        )
        control_canvas.configure(yscrollcommand=control_scrollbar.set)

        control_canvas.grid(row=0, column=0, sticky="nsew")
        control_scrollbar.grid(row=0, column=1, sticky="ns")
        control_main_frame.grid_rowconfigure(0, weight=1)
        control_main_frame.grid_columnconfigure(0, weight=1)

        # AREA CANVAS UNIFICATO (centro) - Sistema professionale integrato
        canvas_frame = ttk.LabelFrame(
            self.main_horizontal_paned,
            text="Canvas Professionale Unificato",
            padding=2,
            width=800,
        )
        canvas_frame.grid_columnconfigure(0, weight=1)
        canvas_frame.grid_rowconfigure(0, weight=1)
        self.main_horizontal_paned.add(canvas_frame, weight=3)

        # PANNELLO DESTRO: Layers + Anteprima
        # PanedWindow verticale per layers | anteprima
        self.right_sidebar_paned = ttk.PanedWindow(
            self.main_horizontal_paned, orient=tk.VERTICAL, width=350
        )
        self.main_horizontal_paned.add(self.right_sidebar_paned, weight=1)

        # Area Layers (sopra)
        layers_frame = ttk.LabelFrame(
            self.right_sidebar_paned, text="Layers", padding=2, width=350
        )
        layers_frame.grid_columnconfigure(0, weight=1)
        layers_frame.grid_rowconfigure(0, weight=1)
        self.right_sidebar_paned.add(layers_frame, weight=1)

        # Setup area anteprima integrata (sotto)
        preview_main_frame = ttk.LabelFrame(
            self.right_sidebar_paned, text="Anteprima Video", padding=2
        )
        preview_main_frame.grid_columnconfigure(0, weight=1)
        preview_main_frame.grid_rowconfigure(0, weight=1)
        self.right_sidebar_paned.add(preview_main_frame, weight=1)

        # Canvas scrollabile per l'area anteprima
        preview_canvas = tk.Canvas(preview_main_frame, highlightthickness=0, width=330)
        preview_scrollbar = ttk.Scrollbar(
            preview_main_frame, orient="vertical", command=preview_canvas.yview
        )

        # Frame scrollabile per il contenuto anteprima
        self.scrollable_preview_frame = ttk.LabelFrame(
            preview_canvas, text="Anteprima Video", padding=10
        )

        self.scrollable_preview_frame.bind(
            "<Configure>",
            lambda e: preview_canvas.configure(scrollregion=preview_canvas.bbox("all")),
        )

        preview_canvas.create_window(
            (0, 0), window=self.scrollable_preview_frame, anchor="nw"
        )
        preview_canvas.configure(yscrollcommand=preview_scrollbar.set)

        preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        preview_main_frame.grid_rowconfigure(0, weight=1)
        preview_main_frame.grid_columnconfigure(0, weight=1)

        # Funzioni per il binding dello scroll
        def _on_mousewheel(event):
            control_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_mousewheel_to_frame(widget):
            """Applica il binding del mouse wheel ricorsivamente."""
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel_to_frame(child)

        def _on_preview_mousewheel(event):
            preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_preview_mousewheel(widget):
            """Applica il binding del mouse wheel ricorsivamente all'area anteprima."""
            widget.bind("<MouseWheel>", _on_preview_mousewheel)
            for child in widget.winfo_children():
                bind_preview_mousewheel(child)

        # Applica il binding iniziale
        control_canvas.bind("<MouseWheel>", _on_mousewheel)
        preview_canvas.bind("<MouseWheel>", _on_preview_mousewheel)

        # Setup dei contenuti
        self.setup_controls(self.scrollable_control_frame)
        self.setup_canvas(canvas_frame)
        self.setup_layers_panel(layers_frame)
        self.setup_integrated_preview(self.scrollable_preview_frame)

        # Applica il binding a tutti i widget figli
        bind_mousewheel_to_frame(self.scrollable_control_frame)
        bind_preview_mousewheel(self.scrollable_preview_frame)

        # Setup area misurazioni (in basso) ridimensionabile
        measurements_frame = ttk.LabelFrame(
            self.main_vertical_paned, text="Lista Misurazioni", padding=2
        )
        measurements_frame.grid_columnconfigure(0, weight=1)
        measurements_frame.grid_rowconfigure(0, weight=1)
        self.setup_measurements_area(measurements_frame)
        self.main_vertical_paned.add(measurements_frame, weight=0)

        # Setup status bar
        self.setup_status_bar()

        # Ripristina posizioni dei pannelli dalla configurazione dell'utente
        self.root.after(200, self._simple_restore_layout)

        # Bind eventi per salvare layout
        print("🔧 Configurazione bind eventi per ridimensionamento pannelli...")
        self.main_vertical_paned.bind(
            "<ButtonRelease-1>", self._on_vertical_paned_resize
        )
        print("   ✅ Vertical paned bind configurato")

        self.main_horizontal_paned.bind("<ButtonRelease-1>", self._on_main_paned_resize)
        print("   ✅ Main horizontal paned bind configurato")

        self.right_sidebar_paned.bind(
            "<ButtonRelease-1>", self._on_sidebar_paned_resize
        )
        print("   ✅ Right sidebar paned bind configurato")

        # Aggiungiamo anche eventi per il trascinamento continuo
        self.main_vertical_paned.bind("<B1-Motion>", self._on_vertical_paned_drag)
        self.main_horizontal_paned.bind("<B1-Motion>", self._on_main_paned_drag)
        self.right_sidebar_paned.bind("<B1-Motion>", self._on_sidebar_paned_drag)

        # AGGIUNTA: Bind alternativo per catturare eventi Configure sui pannelli
        self.right_sidebar_paned.bind("<Configure>", self._on_sidebar_paned_configure)
        print("   ✅ Right sidebar Configure bind configurato")

        # Gestione chiusura delegata a main.py - non sovrascrivere
        # self.root.protocol("WM_DELETE_WINDOW", self.on_closing_with_layout_save)  # DISABILITATO per evitare conflitti

    def create_menu(self):
        """Crea il menu principale."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Menu File
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Carica Immagine", command=self.load_image)
        file_menu.add_command(label="Carica Video", command=self.load_video)
        file_menu.add_separator()
        file_menu.add_command(label="Salva Immagine", command=self.save_image)
        file_menu.add_command(
            label="Esporta Misurazioni", command=self.export_measurements
        )

        # Menu Video
        video_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Video", menu=video_menu)
        video_menu.add_command(label="Avvia Webcam", command=self.start_webcam)
        video_menu.add_command(label="Ferma Analisi", command=self.stop_video_analysis)
        video_menu.add_separator()
        video_menu.add_checkbutton(
            label="Mostra Anteprima Video",
            variable=self.preview_enabled,
            command=self.toggle_video_preview,
        )

        # Menu Visualizza
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Visualizza", menu=view_menu)
        view_menu.add_checkbutton(
            label="Mostra Misurazioni",
            variable=tk.BooleanVar(value=self.show_measurements),
            command=self.toggle_measurements,
        )

    def setup_controls(self, parent):
        """Configura il pannello dei controlli con layout migliorato."""
        # Sezione Video con layout a griglia compatto
        video_frame = ttk.LabelFrame(parent, text="📹 Controlli Video", padding=8)
        video_frame.pack(fill=tk.X, pady=(0, 8))

        # Configura griglia per layout compatto
        video_frame.columnconfigure(0, weight=1)
        video_frame.columnconfigure(1, weight=1)

        ttk.Button(
            video_frame, text="📁 Carica Immagine", command=self.load_image
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=2, padx=2)
        ttk.Button(video_frame, text="🧪 Test Webcam", command=self.test_webcam).grid(
            row=1, column=0, sticky="ew", pady=2, padx=(2, 1)
        )
        ttk.Button(video_frame, text="📹 Avvia Webcam", command=self.start_webcam).grid(
            row=1, column=1, sticky="ew", pady=2, padx=(1, 2)
        )
        ttk.Button(video_frame, text="🎬 Carica Video", command=self.load_video).grid(
            row=2, column=0, sticky="ew", pady=2, padx=(2, 1)
        )
        ttk.Button(
            video_frame, text="⏹️ Ferma Analisi", command=self.stop_video_analysis
        ).grid(row=2, column=1, sticky="ew", pady=2, padx=(1, 2))

        # Info frame migliore con larghezza fissa
        self.best_frame_info = ttk.Label(
            video_frame, text="Nessun frame analizzato", width=60
        )
        self.best_frame_info.grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=5, padx=2
        )

        # Sezione Strumenti con layout compatto
        measure_frame = ttk.LabelFrame(
            parent, text="🔧 Strumenti di Misurazione", padding=8
        )
        measure_frame.pack(fill=tk.X, pady=(0, 8))

        # Griglia per modalità misurazione
        mode_subframe = ttk.Frame(measure_frame)
        mode_subframe.pack(fill=tk.X, pady=2)
        mode_subframe.columnconfigure(0, weight=1)
        mode_subframe.columnconfigure(1, weight=1)
        mode_subframe.columnconfigure(2, weight=1)

        ttk.Label(mode_subframe, text="Modalità:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 3)
        )

        self.measure_var = tk.StringVar(value="distance")
        ttk.Radiobutton(
            mode_subframe,
            text="📏 Distanza",
            variable=self.measure_var,
            value="distance",
            command=self.change_measurement_mode,
        ).grid(row=1, column=0, sticky="w", padx=(0, 5))

        ttk.Radiobutton(
            mode_subframe,
            text="📐 Angolo",
            variable=self.measure_var,
            value="angle",
            command=self.change_measurement_mode,
        ).grid(row=1, column=1, sticky="w", padx=(0, 5))

        ttk.Radiobutton(
            mode_subframe,
            text="📦 Area",
            variable=self.measure_var,
            value="area",
            command=self.change_measurement_mode,
        ).grid(row=1, column=2, sticky="w")

        # Modalità selezione
        selection_subframe = ttk.Frame(measure_frame)
        selection_subframe.pack(fill=tk.X, pady=3)
        selection_subframe.columnconfigure(0, weight=1)
        selection_subframe.columnconfigure(1, weight=1)

        ttk.Label(
            selection_subframe, text="Selezione:", font=("Arial", 9, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))

        self.selection_mode_var = tk.StringVar(value="landmark")
        ttk.Radiobutton(
            selection_subframe,
            text="🎯 Manuale",
            variable=self.selection_mode_var,
            value="manual",
            command=self.change_selection_mode,
        ).grid(row=1, column=0, sticky="w", padx=(0, 5))

        ttk.Radiobutton(
            selection_subframe,
            text="📍 Landmark",
            variable=self.selection_mode_var,
            value="landmark",
            command=self.change_selection_mode,
        ).grid(row=1, column=1, sticky="w")

        # Pulsanti azione
        action_subframe = ttk.Frame(measure_frame)
        action_subframe.pack(fill=tk.X, pady=5)
        action_subframe.columnconfigure(0, weight=1)
        action_subframe.columnconfigure(1, weight=1)

        ttk.Button(
            action_subframe, text="🗑️ Pulisci", command=self.clear_selections
        ).grid(row=0, column=0, sticky="ew", padx=(0, 2))

        ttk.Button(
            action_subframe, text="📊 Calcola", command=self.calculate_measurement
        ).grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # Misurazioni predefinite (solo in modalità landmark)
        self.predefined_frame = ttk.LabelFrame(
            measure_frame, text="Misurazioni Predefinite", padding=5
        )
        self.predefined_frame.pack(fill=tk.X, pady=(10, 0))

        predefined_buttons = [
            ("Larghezza Volto", self.toggle_face_width),
            ("Altezza Volto", self.toggle_face_height),
            ("Distanza Occhi", self.toggle_eye_distance),
            ("Larghezza Naso", self.toggle_nose_width),
            ("Larghezza Bocca", self.toggle_mouth_width),
            ("Aree Sopraccigli", self.toggle_eyebrow_areas),
            ("Aree Occhi", self.toggle_eye_areas),
            ("Simmetria Facciale", self.measure_facial_symmetry),
        ]

        # Mantieni riferimenti ai pulsanti per aggiornare il testo
        self.preset_buttons = {}
        for i, (text, command) in enumerate(predefined_buttons):
            row = i // 2
            col = i % 2
            btn = ttk.Button(
                self.predefined_frame, text=f"Mostra {text}", command=command
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")

            # Salva riferimento al pulsante (escludi simmetria che non ha toggle)
            if "Simmetria" not in text:
                preset_key = (
                    text.lower()
                    .replace(" ", "_")
                    .replace("larghezza_", "")
                    .replace("distanza_", "")
                    .replace("altezza_", "face_height")
                    .replace("aree_", "")
                )
                if preset_key == "volto":
                    preset_key = "face_width"
                elif preset_key == "occhi" and "distanza" in text.lower():
                    preset_key = "eye_distance"
                elif preset_key == "sopraccigli":
                    preset_key = "eyebrow_areas"
                elif preset_key == "occhi":
                    preset_key = "eye_areas"
                self.preset_buttons[preset_key] = btn

        # Configura le colonne per espandersi uniformemente
        self.predefined_frame.columnconfigure(0, weight=1)
        self.predefined_frame.columnconfigure(1, weight=1)

        # Sezione Landmark
        landmark_frame = ttk.LabelFrame(parent, text="Controlli Landmark", padding=10)
        landmark_frame.pack(fill=tk.X, pady=(0, 10))

        self.all_landmarks_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            landmark_frame,
            text="Mostra Tutti i Landmark (468)",
            variable=self.all_landmarks_var,
            command=self.toggle_all_landmarks,
        ).pack(anchor=tk.W)

        self.overlay_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            landmark_frame,
            text="Mostra Overlay Misurazioni",
            variable=self.overlay_var,
            command=self.toggle_measurement_overlays,
        ).pack(anchor=tk.W)

        ttk.Button(
            landmark_frame, text="Rileva Landmark", command=self.detect_landmarks
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            landmark_frame,
            text="Pulisci Overlay",
            command=self.clear_measurement_overlays,
        ).pack(fill=tk.X, pady=2)

        ttk.Button(
            landmark_frame,
            text="🟢 Rileva Dots",
            command=self.detect_green_dots,
        ).pack(fill=tk.X, pady=2)

        self.green_dots_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            landmark_frame,
            text="Mostra Overlay Puntini Verdi",
            variable=self.green_dots_var,
            command=self.toggle_green_dots_overlay,
        ).pack(anchor=tk.W)

        # Sezione Controlli Score Frontalità
        self.setup_scoring_controls(parent)

    def setup_scoring_controls(self, parent):
        """Configura il pannello dei controlli per i pesi dello scoring."""
        scoring_frame = ttk.LabelFrame(
            parent, text="⚖️ Pesi Scoring Frontalità", padding=8
        )
        scoring_frame.pack(fill=tk.X, pady=(0, 8))

        # Info correnti
        info_frame = ttk.Frame(scoring_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.scoring_info_label = ttk.Label(
            info_frame,
            text=f"Score corrente: {self.current_best_score:.3f}",
            font=("Arial", 9, "bold"),
        )
        self.scoring_info_label.pack()

        # Sliders per i pesi
        sliders_frame = ttk.Frame(scoring_frame)
        sliders_frame.pack(fill=tk.X)

        # Nose weight
        nose_frame = ttk.Frame(sliders_frame)
        nose_frame.pack(fill=tk.X, pady=2)
        ttk.Label(nose_frame, text="Naso:", width=12).pack(side=tk.LEFT)
        self.nose_scale = ttk.Scale(
            nose_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            command=self.on_nose_weight_change,
        )
        self.nose_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.nose_value_label = ttk.Label(nose_frame, text="0.40", width=6)
        self.nose_value_label.pack(side=tk.RIGHT)
        self.nose_scale.set(self.scoring_config.nose_weight)

        # Mouth weight
        mouth_frame = ttk.Frame(sliders_frame)
        mouth_frame.pack(fill=tk.X, pady=2)
        ttk.Label(mouth_frame, text="Bocca:", width=12).pack(side=tk.LEFT)
        self.mouth_scale = ttk.Scale(
            mouth_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            command=self.on_mouth_weight_change,
        )
        self.mouth_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.mouth_value_label = ttk.Label(mouth_frame, text="0.30", width=6)
        self.mouth_value_label.pack(side=tk.RIGHT)
        self.mouth_scale.set(self.scoring_config.mouth_weight)

        # Symmetry weight
        symmetry_frame = ttk.Frame(sliders_frame)
        symmetry_frame.pack(fill=tk.X, pady=2)
        ttk.Label(symmetry_frame, text="Simmetria:", width=12).pack(side=tk.LEFT)
        self.symmetry_scale = ttk.Scale(
            symmetry_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            command=self.on_symmetry_weight_change,
        )
        self.symmetry_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.symmetry_value_label = ttk.Label(symmetry_frame, text="0.20", width=6)
        self.symmetry_value_label.pack(side=tk.RIGHT)
        self.symmetry_scale.set(self.scoring_config.symmetry_weight)

        # Eye weight
        eye_frame = ttk.Frame(sliders_frame)
        eye_frame.pack(fill=tk.X, pady=2)
        ttk.Label(eye_frame, text="Occhi:", width=12).pack(side=tk.LEFT)
        self.eye_scale = ttk.Scale(
            eye_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            command=self.on_eye_weight_change,
        )
        self.eye_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        self.eye_value_label = ttk.Label(eye_frame, text="0.10", width=6)
        self.eye_value_label.pack(side=tk.RIGHT)
        self.eye_scale.set(self.scoring_config.eye_weight)

        # Pulsanti preset
        preset_frame = ttk.Frame(scoring_frame)
        preset_frame.pack(fill=tk.X, pady=(10, 5))

        preset_frame.columnconfigure(0, weight=1)
        preset_frame.columnconfigure(1, weight=1)
        preset_frame.columnconfigure(2, weight=1)

        ttk.Button(
            preset_frame, text="Reset Default", command=self.reset_scoring_weights
        ).grid(row=0, column=0, sticky="ew", padx=2)

        ttk.Button(preset_frame, text="Più Naso", command=self.preset_nose_focus).grid(
            row=0, column=1, sticky="ew", padx=2
        )

        ttk.Button(
            preset_frame, text="Meno Simmetria", command=self.preset_less_symmetry
        ).grid(row=0, column=2, sticky="ew", padx=2)

        # Controllo asse di simmetria
        axis_frame = ttk.Frame(scoring_frame)
        axis_frame.pack(fill=tk.X, pady=(10, 5))

        self.show_axis_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            axis_frame,
            text="Asse",
            variable=self.show_axis_var,
            command=self.toggle_axis,
        ).pack(anchor=tk.W)

    def setup_canvas(self, parent):
        """Configura il canvas principale per la visualizzazione (RIPRISTINO ORIGINALE)."""
        print("🔧 Ripristino canvas originale tkinter...")

        # CANVAS TKINTER TRADIZIONALE (come era originalmente)
        self.canvas = tk.Canvas(
            parent,
            bg="white",
            highlightthickness=1,
            highlightbackground="gray",
            cursor="cross",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # TOOLBAR INTEGRATA (sistema unificato)
        self.setup_canvas_toolbar(parent)

        # EVENTI MOUSE UNIFICATI (PAN + MISURAZIONE)
        self.canvas.bind("<Button-1>", self.on_canvas_click_UNIFIED)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<Leave>", lambda e: self.update_cursor_info(""))
        # RIMOSSO: self.canvas.bind("<MouseWheel>", self.on_canvas_mousewheel)  # Causava zoom con due dita!
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)

        # EVENTI TOUCHPAD per PAN universale (funziona sempre, anche senza tool PAN)
        self.canvas.bind(
            "<Button-2>", self.on_touchpad_pan_start
        )  # Middle mouse/touchpad
        self.canvas.bind("<B2-Motion>", self.on_touchpad_pan_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_touchpad_pan_release)

        # TOUCHPAD GESTURE: Due dita = PAN omnidirezionale
        self.canvas.bind(
            "<MouseWheel>", self.on_touchpad_omnidirectional_pan
        )  # Due dita qualsiasi direzione
        self.canvas.bind(
            "<Shift-MouseWheel>", self.on_touchpad_omnidirectional_pan
        )  # Due dita con shift

        # Variabili per movimento touchpad unificato
        self.touchpad_last_time = 0
        self.touchpad_accumulator_x = 0
        self.touchpad_accumulator_y = 0

        # ZOOM solo con Ctrl+MouseWheel (opzionale)
        self.canvas.bind("<Control-MouseWheel>", self.on_canvas_mousewheel)

        # VARIABILI DI STATO ORIGINALI
        self.current_image_on_canvas = None
        self.canvas_image_id = None
        self.canvas_scale = 1.0
        self.canvas_offset_x = 0
        self.canvas_offset_y = 0
        self.canvas_drag_start = None
        self.touchpad_drag_start = None  # Per PAN universale con touchpad
        self.current_canvas_tool = (
            "SELECTION"  # Tool predefinito: SELECTION invece di PAN
        )

        # CALLBACK PER MISURAZIONI (retrocompatibilità)
        self.measurement_callback = self.on_canvas_measurement_click_legacy

        # Imposta il cursore iniziale per il tool SELECTION
        self.canvas.configure(cursor="arrow")

        print("✅ Canvas tkinter originale ripristinato!")

    def setup_canvas_toolbar(self, parent):
        """Configura la toolbar per il canvas unificato."""
        print("🔧 Configurazione toolbar canvas...")

        # Configura stili per pulsanti attivi/inattivi
        style = ttk.Style()
        style.configure(
            "Pressed.TButton", background="lightblue", relief="sunken", borderwidth=2
        )

        # Toolbar compatta con controlli essenziali
        self.canvas_toolbar_frame = ttk.Frame(parent)
        self.canvas_toolbar_frame.pack(side=tk.TOP, fill=tk.X, padx=2, pady=1)

        # Gruppo controlli visualizzazione
        view_frame = ttk.LabelFrame(self.canvas_toolbar_frame, text="Vista", padding=2)
        view_frame.pack(side=tk.LEFT, padx=(0, 3))

        view_buttons = [
            ("🏠", self.fit_to_window, "Adatta alla finestra"),
            ("🔍+", self.zoom_in, "Zoom In"),
            ("🔍-", self.zoom_out, "Zoom Out"),
        ]

        for icon, command, tooltip in view_buttons:
            btn = ttk.Button(view_frame, text=icon, width=4, command=command)
            btn.pack(side=tk.LEFT, padx=1)
            # TODO: Aggiungere tooltip se necessario

        # Gruppo navigazione
        nav_frame = ttk.LabelFrame(
            self.canvas_toolbar_frame, text="Navigazione", padding=2
        )
        nav_frame.pack(side=tk.LEFT, padx=(0, 3))

        # Memorizza riferimenti ai pulsanti per feedback visivo
        self.tool_buttons = {}

        nav_buttons = [
            ("✋", "PAN", "Pan (trascina vista)"),
            (
                "🎯",
                "SELECTION",
                "Selezione disegni (clicca per selezionare/modificare)",
            ),
            ("📐", "MEASURE", "Strumento misura"),
        ]

        for icon, tool, tooltip in nav_buttons:
            btn = ttk.Button(
                nav_frame,
                text=icon,
                width=4,
                command=lambda t=tool: self.set_canvas_tool(t),
            )
            btn.pack(side=tk.LEFT, padx=1)
            # Memorizza riferimento per feedback visivo
            self.tool_buttons[tool] = btn

        # Gruppo disegno
        draw_frame = ttk.LabelFrame(
            self.canvas_toolbar_frame, text="Disegno", padding=2
        )
        draw_frame.pack(side=tk.LEFT, padx=(0, 3))

        draw_buttons = [
            ("📏", "LINE", "Linea"),
            ("○", "CIRCLE", "Cerchio"),
            ("▢", "RECTANGLE", "Rettangolo"),
            ("✏️", "TEXT", "Testo"),
        ]

        for icon, tool, tooltip in draw_buttons:
            btn = ttk.Button(
                draw_frame,
                text=icon,
                width=4,
                command=lambda t=tool: self.set_canvas_tool(t),
            )
            btn.pack(side=tk.LEFT, padx=1)
            # Memorizza riferimento per feedback visivo
            self.tool_buttons[tool] = btn

        # Pulsante per cancellare tutti i disegni
        clear_btn = ttk.Button(
            draw_frame,
            text="🗑️",
            width=4,
            command=self.clear_all_drawings,
        )
        clear_btn.pack(side=tk.LEFT, padx=1)

        # Inizializza stato visivo dei pulsanti
        self.update_button_states()

        print("✅ Toolbar canvas configurata")

    def set_canvas_tool(self, tool_name):
        """Imposta il tool corrente del canvas con supporto toggle per PAN e feedback visivo."""
        # Comportamento toggle per il pulsante PAN
        if tool_name == "PAN" and self.current_canvas_tool == "PAN":
            # Se PAN è già attivo, torna a SELECTION
            tool_name = "SELECTION"
            print(f"🔧 PAN disattivato - torno a: {tool_name}")
        else:
            print(f"🔧 Tool selezionato: {tool_name}")

        self.current_canvas_tool = tool_name

        # Aggiorna feedback visivo dei pulsanti
        self.update_button_states()

        # Cambia cursore in base al tool
        if tool_name == "PAN":
            self.canvas.configure(cursor="fleur")
        elif tool_name in ["LINE", "CIRCLE", "RECTANGLE"]:
            self.canvas.configure(cursor="cross")
        elif tool_name == "MEASURE":
            self.canvas.configure(cursor="target")
        else:
            self.canvas.configure(cursor="arrow")

    def update_button_states(self):
        """Aggiorna lo stato visivo dei pulsanti (attivo/inattivo)."""
        if hasattr(self, "tool_buttons") and hasattr(self, "current_canvas_tool"):
            print(
                f"🔄 Aggiornamento stati pulsanti - tool attivo: {self.current_canvas_tool}"
            )
            for tool, button in self.tool_buttons.items():
                try:
                    if tool == self.current_canvas_tool:
                        # Pulsante attivo - evidenziato
                        button.configure(style="Pressed.TButton")
                        print(f"🔵 Pulsante {tool} ATTIVATO")
                    else:
                        # Pulsante inattivo - normale
                        button.configure(style="TButton")
                except Exception as e:
                    print(f"⚠️ Errore aggiornamento pulsante {tool}: {e}")
        else:
            print("⚠️ tool_buttons o current_canvas_tool non inizializzati")

    def fit_to_window(self):
        """Adatta l'immagine alla finestra."""
        if self.current_image_on_canvas is not None:
            self.canvas_scale = 1.0
            self.canvas_offset_x = 0
            self.canvas_offset_y = 0
            self.update_canvas_display()
            print("🏠 Vista adattata alla finestra")

    # Metodo reset_view rimosso - funzionalità consolidata in fit_to_window (pulsante 🏠)

    def zoom_in(self):
        """Zoom in sul canvas."""
        if self.current_image_on_canvas is not None:
            center_x = self.canvas.winfo_width() / 2
            center_y = self.canvas.winfo_height() / 2

            old_scale = self.canvas_scale
            self.canvas_scale *= 1.2
            self.canvas_scale = min(10.0, self.canvas_scale)

            if self.canvas_scale != old_scale:
                scale_change = self.canvas_scale / old_scale

                # Prima aggiorna gli offset dell'immagine
                self.canvas_offset_x = (
                    center_x - (center_x - self.canvas_offset_x) * scale_change
                )
                self.canvas_offset_y = (
                    center_y - (center_y - self.canvas_offset_y) * scale_change
                )

                # Poi aggiorna il display dell'immagine
                self.update_canvas_display()

                # Infine scala i disegni con le coordinate corrette dell'immagine
                self.scale_all_drawings(scale_change, center_x, center_y)

                print(f"🔍+ Zoom in: {self.canvas_scale:.2f}")

    def zoom_out(self):
        """Zoom out sul canvas."""
        if self.current_image_on_canvas is not None:
            center_x = self.canvas.winfo_width() / 2
            center_y = self.canvas.winfo_height() / 2

            old_scale = self.canvas_scale
            self.canvas_scale /= 1.2
            self.canvas_scale = max(0.1, self.canvas_scale)

            if self.canvas_scale != old_scale:
                scale_change = self.canvas_scale / old_scale

                # Prima aggiorna gli offset dell'immagine
                self.canvas_offset_x = (
                    center_x - (center_x - self.canvas_offset_x) * scale_change
                )
                self.canvas_offset_y = (
                    center_y - (center_y - self.canvas_offset_y) * scale_change
                )

                # Poi aggiorna il display dell'immagine
                self.update_canvas_display()

                # Infine scala i disegni con le coordinate corrette dell'immagine
                self.scale_all_drawings(scale_change, center_x, center_y)
                print(f"🔍- Zoom out: {self.canvas_scale:.2f}")

    def on_canvas_click(self, event):
        """Gestisce il click sul canvas."""
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        print(
            f"CANVAS CLICK: tool={self.current_canvas_tool}, pos=({canvas_x:.1f}, {canvas_y:.1f})"
        )

        if self.current_canvas_tool == "PAN":
            self.canvas_drag_start = (canvas_x, canvas_y)
            print(
                f"PAN TOOL ATTIVATO - drag iniziato da ({canvas_x:.1f}, {canvas_y:.1f})"
            )
        elif self.current_canvas_tool in ["LINE", "CIRCLE", "RECTANGLE", "MEASURE"]:
            # Gestisci disegno/misurazione
            self.on_canvas_measurement_click_new(event)
            print(
                f"📐 Click con tool {self.current_canvas_tool}: ({canvas_x:.1f}, {canvas_y:.1f})"
            )

    def on_canvas_drag(self, event):
        """Gestisce il trascinamento sul canvas (CORRETTO per PAN)."""
        if not self.canvas_drag_start:
            return

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        if self.current_canvas_tool == "PAN":
            print(
                f"✋ PAN ATTIVO - elaboro drag da {self.canvas_drag_start} a ({canvas_x}, {canvas_y})"
            )
            # CORRETTO: Calcola movimento dalla posizione iniziale
            dx = canvas_x - self.canvas_drag_start[0]
            dy = canvas_y - self.canvas_drag_start[1]

            # Sposta tutti i disegni esistenti insieme all'immagine
            self.move_all_drawings(dx, dy)

            # Aggiorna offset dell'immagine
            self.canvas_offset_x += dx
            self.canvas_offset_y += dy

            print(
                f"�️ PAN: spostamento dx={dx:.1f}, dy={dy:.1f} -> offset=({self.canvas_offset_x:.1f}, {self.canvas_offset_y:.1f})"
            )

            # Aggiorna posizione di riferimento per il prossimo movimento
            self.canvas_drag_start = (canvas_x, canvas_y)

            # Ridisegna canvas con nuova posizione
            self.update_canvas_display()

    def on_canvas_release(self, event):
        """Gestisce il rilascio del mouse sul canvas."""
        self.canvas_drag_start = None

    def on_canvas_double_click(self, event):
        """Gestisce il doppio click sul canvas."""
        if self.current_canvas_tool == "PAN":
            self.fit_to_window()

    def on_canvas_right_click(self, event):
        """Gestisce il click destro sul canvas."""
        # Torna al tool PAN
        self.set_canvas_tool("PAN")

    def on_canvas_scroll(self, event):
        """Gestisce lo scroll del mouse per zoom."""
        if self.current_image_on_canvas is None:
            return

        # Calcola il fattore di zoom
        if event.delta > 0 or event.num == 4:  # Scroll up / Linux
            zoom_factor = 1.1
        else:  # Scroll down
            zoom_factor = 0.9

        # Applica zoom centrato sulla posizione del mouse
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        old_scale = self.canvas_scale
        self.canvas_scale *= zoom_factor

        # Limita il range di zoom
        self.canvas_scale = max(0.1, min(10.0, self.canvas_scale))

        if self.canvas_scale != old_scale:
            scale_change = self.canvas_scale / old_scale

            # Aggiusta offset per zoom centrato
            self.canvas_offset_x = (
                canvas_x - (canvas_x - self.canvas_offset_x) * scale_change
            )
            self.canvas_offset_y = (
                canvas_y - (canvas_y - self.canvas_offset_y) * scale_change
            )

            # Aggiorna la visualizzazione dell'immagine
            self.update_canvas_display()

            # Scala i disegni esistenti DOPO l'aggiornamento della posizione
            self.scale_all_drawings(scale_change, canvas_x, canvas_y)

    def on_canvas_mouse_motion(self, event):
        """Gestisce il movimento del mouse sul canvas."""
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # TODO: Mostra coordinate nella status bar se necessario
        pass

    def on_touchpad_pan_start(self, event):
        """Inizia PAN con touchpad (middle mouse o gesture due dita)."""
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self.touchpad_drag_start = (canvas_x, canvas_y)
        print("🖱️ Touchpad PAN iniziato")

    def on_touchpad_pan_drag(self, event):
        """PAN con touchpad - funziona sempre indipendentemente dal tool selezionato."""
        if not hasattr(self, "touchpad_drag_start") or not self.touchpad_drag_start:
            return

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # Calcola movimento
        dx = canvas_x - self.touchpad_drag_start[0]
        dy = canvas_y - self.touchpad_drag_start[1]

        # Aggiorna offset dell'immagine (PAN universale)
        self.canvas_offset_x += dx
        self.canvas_offset_y += dy

        print(
            f"👆 Touchpad PAN: dx={dx:.1f}, dy={dy:.1f} -> offset=({self.canvas_offset_x:.1f}, {self.canvas_offset_y:.1f})"
        )

        # Aggiorna posizione di riferimento
        self.touchpad_drag_start = (canvas_x, canvas_y)

        # Ridisegna canvas
        self.update_canvas_display()

    def on_touchpad_pan_release(self, event):
        """Fine PAN con touchpad."""
        if hasattr(self, "touchpad_drag_start"):
            self.touchpad_drag_start = None
        print("🖱️ Touchpad PAN terminato")

    def on_touchpad_omnidirectional_pan(self, event):
        """PAN omnidirezionale con touchpad - due dita in qualsiasi direzione."""
        if self.current_image_on_canvas is None:
            return

        import time

        current_time = time.time()

        # Determina se è movimento orizzontale (con Shift) o verticale (normale)
        is_horizontal = hasattr(event, "state") and (event.state & 0x1)  # Shift pressed

        # Movimento più fluido e sensibile
        movement_amount = 25 if event.delta > 0 else -25

        # PRIMA sposta i disegni, POI aggiorna gli offset
        if is_horizontal:
            # Movimento orizzontale (con Shift)
            self.move_all_drawings(movement_amount, 0)
            self.canvas_offset_x += movement_amount
            print(f"↔️ Touchpad PAN orizzontale: offset_x={self.canvas_offset_x}")
        else:
            # Movimento verticale (normale)
            self.move_all_drawings(0, movement_amount)
            self.canvas_offset_y += movement_amount
            print(f"↕️ Touchpad PAN verticale: offset_y={self.canvas_offset_y}")

        # Aggiorna immediatamente per movimento fluido
        self.update_canvas_display()

    # Metodo rimosso: on_touchpad_pan_horizontal - sostituito da on_touchpad_omnidirectional_pan

    def on_canvas_measurement_click_new(self, event):
        """Gestisce i click per misurazioni e disegno (NUOVO SISTEMA - SEMPLIFICATO)."""
        try:
            # Converte coordinate event -> coordinate immagine
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)

            # Converti coordinate canvas -> coordinate immagine
            img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)

            # Chiama il metodo legacy per compatibilità
            self.on_canvas_measurement_click_legacy(img_x, img_y)
            print(
                f"📐 Click misurazione: canvas({canvas_x:.1f},{canvas_y:.1f}) -> img({img_x},{img_y})"
            )
        except Exception as e:
            print(f"⚠️ Errore callback misurazione: {e}")

    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """Converte coordinate canvas in coordinate immagine."""
        if self.current_image_on_canvas is None:
            return int(canvas_x), int(canvas_y)

        # Prendi in considerazione scala e offset
        img_height, img_width = self.current_image_on_canvas.shape[:2]

        # Calcola posizione immagine sul canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Dimensioni scalate
        scaled_width = int(img_width * self.canvas_scale)
        scaled_height = int(img_height * self.canvas_scale)

        # Centro se l'immagine è più piccola del canvas
        img_x_offset = max(0, (canvas_width - scaled_width) // 2) + self.canvas_offset_x
        img_y_offset = (
            max(0, (canvas_height - scaled_height) // 2) + self.canvas_offset_y
        )

        # Coordinate relative all'immagine
        rel_x = canvas_x - img_x_offset
        rel_y = canvas_y - img_y_offset

        # Scala alle coordinate immagine originale
        img_x = int(rel_x / self.canvas_scale)
        img_y = int(rel_y / self.canvas_scale)

        # Limita alle dimensioni dell'immagine
        img_x = max(0, min(img_width - 1, img_x))
        img_y = max(0, min(img_height - 1, img_y))

        return img_x, img_y

    def image_to_canvas_coords(self, img_x, img_y):
        """Converte coordinate immagine in coordinate canvas."""
        if self.current_image_on_canvas is None:
            return img_x, img_y

        # Prendi in considerazione scala e offset
        img_height, img_width = self.current_image_on_canvas.shape[:2]

        # Calcola posizione immagine sul canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Dimensioni scalate
        scaled_width = int(img_width * self.canvas_scale)
        scaled_height = int(img_height * self.canvas_scale)

        # Centro se l'immagine è più piccola del canvas
        img_x_offset = max(0, (canvas_width - scaled_width) // 2) + self.canvas_offset_x
        img_y_offset = (
            max(0, (canvas_height - scaled_height) // 2) + self.canvas_offset_y
        )

        # Scala e trasla
        canvas_x = img_x * self.canvas_scale + img_x_offset
        canvas_y = img_y * self.canvas_scale + img_y_offset

        return canvas_x, canvas_y

    def on_canvas_click_UNIFIED(self, event):
        """Gestisce i click sul canvas - SISTEMA UNIFICATO (PAN + MISURAZIONI)."""
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        print(
            f"CANVAS CLICK UNIFICATO: tool={self.current_canvas_tool}, pos=({canvas_x:.1f}, {canvas_y:.1f})"
        )

        # GESTIONE PAN TOOL
        if self.current_canvas_tool == "PAN":
            self.canvas_drag_start = (canvas_x, canvas_y)
            print(
                f"PAN TOOL ATTIVATO - drag iniziato da ({canvas_x:.1f}, {canvas_y:.1f})"
            )
            return  # Non processare come misurazione

        # GESTIONE TOOL DISEGNO/MISURAZIONE - FIX COORDINATE
        elif self.current_canvas_tool in [
            "LINE",
            "CIRCLE",
            "RECTANGLE",
            "MEASURE",
            "TEXT",
            "SELECTION",
        ]:
            # Usa direttamente le coordinate canvas senza doppia conversione
            if self.current_canvas_tool == "LINE":
                self.handle_line_tool(canvas_x, canvas_y)
            elif self.current_canvas_tool == "CIRCLE":
                self.handle_circle_tool(canvas_x, canvas_y)
            elif self.current_canvas_tool == "RECTANGLE":
                self.handle_rectangle_tool(canvas_x, canvas_y)
            elif self.current_canvas_tool == "MEASURE":
                self.handle_measure_tool(canvas_x, canvas_y)
            elif self.current_canvas_tool == "TEXT":
                self.handle_text_tool(canvas_x, canvas_y)
            elif self.current_canvas_tool == "SELECTION":
                self.handle_selection_tool(canvas_x, canvas_y)
            print(
                f"🎯 Click DIRETTO con tool {self.current_canvas_tool}: ({canvas_x:.1f}, {canvas_y:.1f})"
            )
            return

        # FALLBACK: Comportamento legacy per misurazioni
        if self.current_image_on_canvas is not None:
            # Converti coordinate canvas a coordinate immagine
            img_x, img_y = self.canvas_to_image_coords(event.x, event.y)

            # Chiama il callback per le misurazioni se esiste
            if hasattr(self, "measurement_callback") and self.measurement_callback:
                self.measurement_callback(img_x, img_y)

            print(
                f"🖱️ Click misurazione legacy: canvas({event.x}, {event.y}) -> immagine({img_x:.0f}, {img_y:.0f})"
            )

    def on_canvas_motion(self, event):
        """Gestisce il movimento del mouse sul canvas (RIPRISTINO ORIGINALE)."""
        if self.current_image_on_canvas is not None:
            # Converti coordinate canvas a coordinate immagine
            img_x, img_y = self.canvas_to_image_coords(event.x, event.y)

            # Aggiorna info cursore
            self.update_cursor_info(f"({img_x:.0f}, {img_y:.0f})")

    def on_canvas_mousewheel(self, event):
        """Gestisce lo zoom con rotellina mouse (RIPRISTINO ORIGINALE)."""
        if self.current_image_on_canvas is not None:
            # Zoom in/out
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()

    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """Converte coordinate canvas a coordinate immagine (RIPRISTINO ORIGINALE)."""
        if self.current_image_on_canvas is None:
            return 0, 0

        # Applica offset e scala inversa
        img_x = (canvas_x - self.canvas_offset_x) / self.canvas_scale
        img_y = (canvas_y - self.canvas_offset_y) / self.canvas_scale

        # Limita alle dimensioni dell'immagine
        img_height, img_width = self.current_image_on_canvas.shape[:2]
        img_x = max(0, min(img_width - 1, img_x))
        img_y = max(0, min(img_height - 1, img_y))

        return img_x, img_y

    def update_cursor_info(self, info):
        """Aggiorna le informazioni del cursore (RIPRISTINO ORIGINALE)."""
        if hasattr(self, "status_bar"):
            if info:
                self.status_bar.config(text=f"Cursore: {info}")
            else:
                self.status_bar.config(text="Pronto")

    def on_canvas_measurement_click_legacy(self, img_x, img_y):
        """Callback per i click di misurazione sul canvas (RETROCOMPATIBILITÀ)."""
        print(
            f"📏 Click misurazione tool={self.current_canvas_tool}: ({img_x:.0f}, {img_y:.0f})"
        )

        # Converte coordinate immagine -> coordinate canvas per il disegno
        canvas_x, canvas_y = self.image_to_canvas_coords(img_x, img_y)

        if self.current_canvas_tool == "LINE":
            self.handle_line_tool(canvas_x, canvas_y)
        elif self.current_canvas_tool == "CIRCLE":
            self.handle_circle_tool(canvas_x, canvas_y)
        elif self.current_canvas_tool == "RECTANGLE":
            self.handle_rectangle_tool(canvas_x, canvas_y)
        elif self.current_canvas_tool == "MEASURE":
            self.handle_measure_tool(canvas_x, canvas_y)
        elif self.current_canvas_tool == "TEXT":
            self.handle_text_tool(canvas_x, canvas_y)
        elif self.current_canvas_tool == "SELECTION":
            self.handle_selection_tool(canvas_x, canvas_y)
        else:
            print(f"⚠️ Strumento non riconosciuto: {self.current_canvas_tool}")

    def handle_line_tool(self, canvas_x, canvas_y):
        """Gestisce il tool LINE per disegnare linee."""
        if not hasattr(self, "line_start_point"):
            # Primo click - memorizza punto di partenza
            self.line_start_point = (canvas_x, canvas_y)
            print(f"📏 LINE: punto iniziale ({canvas_x:.1f}, {canvas_y:.1f})")
            # Disegna un punto di partenza temporaneo
            self.canvas.create_oval(
                canvas_x - 3,
                canvas_y - 3,
                canvas_x + 3,
                canvas_y + 3,
                fill="red",
                outline="red",
                tags="temp_drawing",
            )
        else:
            # Secondo click - disegna la linea
            start_x, start_y = self.line_start_point
            print(
                f"📏 LINE: da ({start_x:.1f}, {start_y:.1f}) a ({canvas_x:.1f}, {canvas_y:.1f})"
            )
            # Rimuovi il punto temporaneo
            self.canvas.delete("temp_drawing")
            # Determina i tag per il layer
            layer_tags = self.get_drawing_tags()
            # Disegna la linea finale
            line_id = self.canvas.create_line(
                start_x,
                start_y,
                canvas_x,
                canvas_y,
                fill="blue",
                width=2,
                tags=layer_tags,
            )

            # Memorizza coordinate originali per scaling futuro (solo se non già memorizzate)
            if line_id not in self.original_drawing_coords:
                image_center_x, image_center_y = self.get_image_center()
                print(
                    f"🔍 CENTER DEBUG: Centro immagine al momento creazione linea: ({image_center_x:.1f}, {image_center_y:.1f})"
                )
                print(
                    f"🔍 COORDS DEBUG: Coordinate linea: start=({start_x:.1f}, {start_y:.1f}), end=({canvas_x:.1f}, {canvas_y:.1f})"
                )
                self.store_original_coords(line_id, image_center_x, image_center_y)

            # Reset per una nuova linea
            del self.line_start_point

    def handle_circle_tool(self, canvas_x, canvas_y):
        """Gestisce il tool CIRCLE per disegnare cerchi."""
        if not hasattr(self, "circle_center_point"):
            # Primo click - memorizza centro
            self.circle_center_point = (canvas_x, canvas_y)
            print(f"⭕ CIRCLE: centro ({canvas_x:.1f}, {canvas_y:.1f})")
            # Disegna un punto centrale temporaneo
            self.canvas.create_oval(
                canvas_x - 3,
                canvas_y - 3,
                canvas_x + 3,
                canvas_y + 3,
                fill="green",
                outline="green",
                tags="temp_drawing",
            )
        else:
            # Secondo click - disegna il cerchio
            center_x, center_y = self.circle_center_point
            radius = ((canvas_x - center_x) ** 2 + (canvas_y - center_y) ** 2) ** 0.5
            print(
                f"⭕ CIRCLE: centro ({center_x:.1f}, {center_y:.1f}) raggio {radius:.1f}"
            )
            # Rimuovi il punto temporaneo
            self.canvas.delete("temp_drawing")
            # Determina i tag per il layer
            layer_tags = self.get_drawing_tags()
            # Disegna il cerchio finale
            circle_id = self.canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                outline="green",
                width=2,
                tags=layer_tags,
            )

            # Memorizza coordinate originali per scaling futuro (solo se non già memorizzate)
            if circle_id not in self.original_drawing_coords:
                image_center_x, image_center_y = self.get_image_center()
                self.store_original_coords(circle_id, image_center_x, image_center_y)

            # Reset per un nuovo cerchio
            del self.circle_center_point

    def handle_rectangle_tool(self, canvas_x, canvas_y):
        """Gestisce il tool RECTANGLE per disegnare rettangoli."""
        if not hasattr(self, "rect_start_point"):
            # Primo click - memorizza primo angolo
            self.rect_start_point = (canvas_x, canvas_y)
            print(f"🔳 RECTANGLE: primo angolo ({canvas_x:.1f}, {canvas_y:.1f})")
            # Disegna un punto di partenza temporaneo
            self.canvas.create_oval(
                canvas_x - 3,
                canvas_y - 3,
                canvas_x + 3,
                canvas_y + 3,
                fill="purple",
                outline="purple",
                tags="temp_drawing",
            )
        else:
            # Secondo click - disegna il rettangolo
            start_x, start_y = self.rect_start_point
            print(
                f"🔳 RECTANGLE: da ({start_x:.1f}, {start_y:.1f}) a ({canvas_x:.1f}, {canvas_y:.1f})"
            )
            # Rimuovi il punto temporaneo
            self.canvas.delete("temp_drawing")
            # Determina i tag per il layer
            layer_tags = self.get_drawing_tags()
            # Disegna il rettangolo finale
            rect_id = self.canvas.create_rectangle(
                start_x,
                start_y,
                canvas_x,
                canvas_y,
                outline="purple",
                width=2,
                tags=layer_tags,
            )

            # Memorizza coordinate originali per scaling futuro (solo se non già memorizzate)
            if rect_id not in self.original_drawing_coords:
                image_center_x, image_center_y = self.get_image_center()
                self.store_original_coords(rect_id, image_center_x, image_center_y)

            # Reset per un nuovo rettangolo
            del self.rect_start_point

    def handle_measure_tool(self, canvas_x, canvas_y):
        """Gestisce il tool MEASURE per misurazioni con righello."""
        if not hasattr(self, "measure_start_point"):
            # Primo click - memorizza punto di partenza
            self.measure_start_point = (canvas_x, canvas_y)
            print(f"📐 MEASURE: punto iniziale ({canvas_x:.1f}, {canvas_y:.1f})")
            # Disegna un punto di partenza temporaneo
            self.canvas.create_oval(
                canvas_x - 3,
                canvas_y - 3,
                canvas_x + 3,
                canvas_y + 3,
                fill="orange",
                outline="orange",
                tags="temp_drawing",
            )
        else:
            # Secondo click - disegna la misurazione
            start_x, start_y = self.measure_start_point
            distance = ((canvas_x - start_x) ** 2 + (canvas_y - start_y) ** 2) ** 0.5
            print(f"📐 MEASURE: distanza {distance:.1f} pixel")
            # Rimuovi il punto temporaneo
            self.canvas.delete("temp_drawing")
            # Determina i tag per il layer
            layer_tags = self.get_drawing_tags()
            # Disegna la linea di misurazione con etichetta
            measure_line_id = self.canvas.create_line(
                start_x,
                start_y,
                canvas_x,
                canvas_y,
                fill="orange",
                width=2,
                tags=layer_tags,
            )

            # Aggiungi testo con la misurazione
            mid_x = (start_x + canvas_x) / 2
            mid_y = (start_y + canvas_y) / 2
            measure_text_id = self.canvas.create_text(
                mid_x,
                mid_y - 10,
                text=f"{distance:.1f}px",
                fill="orange",
                font=("Arial", 8),
                tags=layer_tags,
            )

            # Memorizza coordinate originali per entrambi gli elementi (solo se non già memorizzate)
            image_center_x, image_center_y = self.get_image_center()
            if measure_line_id not in self.original_drawing_coords:
                self.store_original_coords(
                    measure_line_id, image_center_x, image_center_y
                )
            if measure_text_id not in self.original_drawing_coords:
                self.store_original_coords(
                    measure_text_id, image_center_x, image_center_y
                )

            # Reset per una nuova misurazione
            del self.measure_start_point

    def handle_text_tool(self, canvas_x, canvas_y):
        """Gestisce il tool TEXT per inserire testo."""
        import tkinter.simpledialog as simpledialog

        # Richiedi il testo da inserire
        text = simpledialog.askstring("Inserisci Testo", "Scrivi il testo da inserire:")
        if text:
            print(f"✏️ TEXT: '{text}' a ({canvas_x:.1f}, {canvas_y:.1f})")
            # Determina i tag per il layer
            layer_tags = self.get_drawing_tags()
            # Disegna il testo sul canvas
            text_id = self.canvas.create_text(
                canvas_x,
                canvas_y,
                text=text,
                fill="red",
                font=("Arial", 12, "bold"),
                tags=layer_tags,
            )

            # Memorizza coordinate originali per scaling futuro (solo se non già memorizzate)
            if text_id not in self.original_drawing_coords:
                image_center_x, image_center_y = self.get_image_center()
                self.store_original_coords(text_id, image_center_x, image_center_y)

            print(
                f"✏️ Testo inserito con ID: {text_id} nel layer: {self.active_layer['name'] if self.active_layer else 'Default'}"
            )

    def get_drawing_tags(self):
        """Restituisce i tag appropriati per i nuovi disegni basati sul layer attivo."""
        tags = ["drawing"]
        if self.active_layer:
            tags.append(self.active_layer["tag"])
            print(
                f"🎨 Disegno nel layer: {self.active_layer['name']} (tag: {self.active_layer['tag']})"
            )
        else:
            tags.append("default_layer")
            print("🎨 Disegno nel layer: Default")
        return tags

    def handle_selection_tool(self, canvas_x, canvas_y):
        """Gestisce il tool SELECTION per selezionare e modificare disegni."""
        # Trova l'elemento più vicino al click
        closest_item = self.canvas.find_closest(canvas_x, canvas_y)[0]

        # Verifica se è un disegno (ha il tag 'drawing')
        if "drawing" in self.canvas.gettags(closest_item):
            # Evidenzia l'elemento selezionato
            current_outline = self.canvas.itemcget(closest_item, "outline")
            if current_outline == "yellow":
                # Deseleziona se già selezionato
                self.canvas.itemconfig(closest_item, outline="blue")
                print(f"🎯 SELECTION: Deselezionato elemento ID {closest_item}")
            else:
                # Seleziona elemento
                self.canvas.itemconfig(closest_item, outline="yellow", width=3)
                print(
                    f"🎯 SELECTION: Selezionato elemento ID {closest_item} per modifica"
                )
                print(
                    "   💡 Suggerimento: Click destro per eliminare, doppio click per modificare"
                )
        else:
            print(
                f"🎯 SELECTION: Click su ({canvas_x:.1f}, {canvas_y:.1f}) - nessun disegno trovato"
            )
            print(
                "   💡 Il tool SELECTION serve per selezionare e modificare i disegni esistenti"
            )

    def clear_all_drawings(self):
        """Cancella tutti i disegni e le misurazioni dal canvas."""
        # Rimuove tutti gli elementi con tag "drawing" e "temp_drawing"
        self.canvas.delete("drawing")
        self.canvas.delete("temp_drawing")

        # Reset di eventuali operazioni in corso
        if hasattr(self, "line_start_point"):
            del self.line_start_point
        if hasattr(self, "circle_center_point"):
            del self.circle_center_point
        if hasattr(self, "rect_start_point"):
            del self.rect_start_point
        if hasattr(self, "measure_start_point"):
            del self.measure_start_point

        print("🗑️ Tutti i disegni sono stati cancellati")

    def move_all_drawings(self, dx, dy):
        """Sposta tutti i disegni di dx, dy pixels per seguire l'immagine durante il PAN."""
        moved_items = 0

        # Sposta tutti gli elementi con tag "drawing" e "temp_drawing"
        for tag in ["drawing", "temp_drawing"]:
            items = self.canvas.find_withtag(tag)
            for item_id in items:
                self.canvas.move(item_id, dx, dy)
                moved_items += 1

        # Sposta anche gli elementi dei layer specifici
        if hasattr(self, "layers_list") and self.layers_list:
            for layer in self.layers_list:
                items = self.canvas.find_withtag(layer["tag"])
                for item_id in items:
                    # Evita di spostare due volte lo stesso elemento
                    if (
                        "drawing" not in self.canvas.gettags(item_id)
                        or moved_items == 0
                    ):
                        self.canvas.move(item_id, dx, dy)
                        moved_items += 1

        print(f"🔄 Spostati {moved_items} disegni di ({dx:.1f}, {dy:.1f})")

    def scale_all_drawings(self, scale_factor, center_x, center_y):
        """Scala tutti i disegni usando coordinate memorizzate per eliminare accumulo errori."""
        # Inizializza il dizionario delle coordinate originali se non esiste
        if not hasattr(self, "original_drawing_coords"):
            self.original_drawing_coords = {}

        # Calcola il centro dell'immagine corrente
        image_center_x, image_center_y = self.get_image_center()
        scaled_items = 0

        print(
            f"📏 Scaling COORDINATO: fattore={self.canvas_scale:.2f}, centro=({image_center_x:.1f}, {image_center_y:.1f})"
        )

        # Scala tutti gli elementi con tag "drawing" e "temp_drawing"
        for tag in ["drawing", "temp_drawing"]:
            items = self.canvas.find_withtag(tag)
            for item_id in items:
                scaled_items += self.scale_drawing_item_coordinated(
                    item_id, image_center_x, image_center_y
                )

        # Scala anche gli elementi dei layer specifici
        if hasattr(self, "layers_list") and self.layers_list:
            for layer in self.layers_list:
                items = self.canvas.find_withtag(layer["tag"])
                for item_id in items:
                    item_tags = self.canvas.gettags(item_id)
                    if "drawing" not in item_tags:
                        scaled_items += self.scale_drawing_item_coordinated(
                            item_id, image_center_x, image_center_y
                        )

        if scaled_items > 0:
            print(
                f"📏 Scalati {scaled_items} disegni alla scala {self.canvas_scale:.2f}x"
            )
            print(f"🎯 Centro immagine: ({image_center_x:.1f}, {image_center_y:.1f})")
        else:
            print(
                "⚠️ Nessun disegno scalato - verifica presence disegni e coordinate memorizzate"
            )

    def scale_drawing_item_coordinated(self, item_id, image_center_x, image_center_y):
        """Scala un elemento usando le coordinate originali memorizzate per evitare accumulo errori."""
        try:
            # Se non abbiamo le coordinate originali, memorizzale ora
            if item_id not in self.original_drawing_coords:
                self.store_original_coords(item_id, image_center_x, image_center_y)

            # Ottieni le coordinate originali
            original_data = self.original_drawing_coords[item_id]
            item_type = original_data["type"]
            original_coords = original_data["coords"]
            original_center = original_data["image_center"]
            original_scale = original_data["canvas_scale"]

            print(f"🔍 SCALE DEBUG item {item_id}: tipo={item_type}")
            print(
                f"🔍 SCALE DEBUG: orig_center=({original_center[0]:.1f}, {original_center[1]:.1f}), orig_scale={original_scale:.2f}"
            )
            print(
                f"🔍 SCALE DEBUG: new_center=({image_center_x:.1f}, {image_center_y:.1f}), new_scale={self.canvas_scale:.2f}"
            )

            if item_type == "line":
                # Calcola le nuove coordinate basate sulla posizione relativa originale
                new_coords = []
                for i in range(0, len(original_coords), 2):
                    # Coordinate originali assolute
                    orig_x, orig_y = original_coords[i], original_coords[i + 1]

                    # Calcola posizione relativa al centro originale
                    rel_x = (orig_x - original_center[0]) / original_scale
                    rel_y = (orig_y - original_center[1]) / original_scale

                    # Applica la nuova scala e posizione
                    new_x = image_center_x + rel_x * self.canvas_scale
                    new_y = image_center_y + rel_y * self.canvas_scale

                    print(
                        f"🔍 SCALE DEBUG punto {i//2}: orig=({orig_x:.1f}, {orig_y:.1f}) -> rel=({rel_x:.1f}, {rel_y:.1f}) -> new=({new_x:.1f}, {new_y:.1f})"
                    )
                    new_coords.extend([new_x, new_y])
                self.canvas.coords(item_id, *new_coords)

            elif item_type in ["oval", "rectangle"]:
                # Calcola il nuovo bounding box
                orig_x1, orig_y1, orig_x2, orig_y2 = original_coords

                # Calcola posizioni relative al centro originale
                rel_x1 = (orig_x1 - original_center[0]) / original_scale
                rel_y1 = (orig_y1 - original_center[1]) / original_scale
                rel_x2 = (orig_x2 - original_center[0]) / original_scale
                rel_y2 = (orig_y2 - original_center[1]) / original_scale

                # Applica la nuova scala e posizione
                new_x1 = image_center_x + rel_x1 * self.canvas_scale
                new_y1 = image_center_y + rel_y1 * self.canvas_scale
                new_x2 = image_center_x + rel_x2 * self.canvas_scale
                new_y2 = image_center_y + rel_y2 * self.canvas_scale
                self.canvas.coords(item_id, new_x1, new_y1, new_x2, new_y2)

            elif item_type == "text":
                # Calcola la nuova posizione del testo
                orig_x, orig_y = original_coords

                # Calcola posizione relativa al centro originale
                rel_x = (orig_x - original_center[0]) / original_scale
                rel_y = (orig_y - original_center[1]) / original_scale
                new_x = image_center_x + rel_x * self.canvas_scale
                new_y = image_center_y + rel_y * self.canvas_scale
                self.canvas.coords(item_id, new_x, new_y)

                # Scala il font se memorizzato
                if "font_size" in original_data:
                    try:
                        original_font_size = original_data["font_size"]
                        new_font_size = max(
                            8, int(original_font_size * self.canvas_scale)
                        )
                        font_info = original_data.get(
                            "font_info", ("Arial", original_font_size)
                        )
                        if isinstance(font_info, tuple):
                            new_font = (
                                (font_info[0], new_font_size) + font_info[2:]
                                if len(font_info) > 2
                                else (font_info[0], new_font_size)
                            )
                            self.canvas.itemconfig(item_id, font=new_font)
                    except Exception:
                        pass

            return 1

        except Exception as e:
            print(f"⚠️ Errore scaling coordinato item {item_id}: {e}")
            return 0

    def store_original_coords(self, item_id, image_center_x, image_center_y):
        """Memorizza le coordinate originali assolute di un elemento e le info di scala."""
        try:
            item_type = self.canvas.type(item_id)
            current_coords = self.canvas.coords(item_id)

            if item_type == "line":
                # Memorizza le coordinate assolute
                self.original_drawing_coords[item_id] = {
                    "type": item_type,
                    "coords": current_coords.copy(),
                    "image_center": [image_center_x, image_center_y],
                    "canvas_scale": self.canvas_scale,
                }

            elif item_type in ["oval", "rectangle"]:
                # Memorizza il bounding box assoluto
                self.original_drawing_coords[item_id] = {
                    "type": item_type,
                    "coords": current_coords.copy(),
                    "image_center": [image_center_x, image_center_y],
                    "canvas_scale": self.canvas_scale,
                }

            elif item_type == "text":
                # Memorizza la posizione assoluta del testo
                font_info = None
                font_size = 12  # default
                try:
                    font_info = self.canvas.itemcget(item_id, "font")
                    if isinstance(font_info, tuple) and len(font_info) >= 2:
                        font_size = font_info[1]
                    elif isinstance(font_info, str):
                        import re

                        size_match = re.search(r"\s(\d+)(?:\s|$)", font_info)
                        if size_match:
                            font_size = int(size_match.group(1))
                except Exception:
                    pass

                self.original_drawing_coords[item_id] = {
                    "type": item_type,
                    "coords": current_coords.copy(),
                    "image_center": [image_center_x, image_center_y],
                    "canvas_scale": self.canvas_scale,
                    "font_size": font_size,
                    "font_info": font_info,
                }

            print(f"✅ Memorizzate coordinate per item {item_id} (tipo: {item_type})")

        except Exception as e:
            print(f"⚠️ Errore memorizzazione coordinate item {item_id}: {e}")

    def scale_drawing_item(self, item_id, scale_factor, center_x, center_y):
        """Scala manualmente un singolo elemento del disegno rispetto al centro specificato."""
        try:
            # Ottieni il tipo di elemento
            item_type = self.canvas.type(item_id)

            if item_type == "line":
                # Per le linee, scala tutti i punti
                coords = self.canvas.coords(item_id)
                new_coords = []
                for i in range(0, len(coords), 2):
                    x, y = coords[i], coords[i + 1]
                    # Calcola la nuova posizione scalata rispetto al centro
                    new_x = center_x + (x - center_x) * scale_factor
                    new_y = center_y + (y - center_y) * scale_factor
                    new_coords.extend([new_x, new_y])
                self.canvas.coords(item_id, *new_coords)

            elif item_type == "oval":
                # Per i cerchi/ovali, scala le coordinate del bounding box
                x1, y1, x2, y2 = self.canvas.coords(item_id)
                # Scala ogni angolo del bounding box
                new_x1 = center_x + (x1 - center_x) * scale_factor
                new_y1 = center_y + (y1 - center_y) * scale_factor
                new_x2 = center_x + (x2 - center_x) * scale_factor
                new_y2 = center_y + (y2 - center_y) * scale_factor
                self.canvas.coords(item_id, new_x1, new_y1, new_x2, new_y2)

            elif item_type == "rectangle":
                # Per i rettangoli, scala le coordinate del bounding box
                x1, y1, x2, y2 = self.canvas.coords(item_id)
                new_x1 = center_x + (x1 - center_x) * scale_factor
                new_y1 = center_y + (y1 - center_y) * scale_factor
                new_x2 = center_x + (x2 - center_x) * scale_factor
                new_y2 = center_y + (y2 - center_y) * scale_factor
                self.canvas.coords(item_id, new_x1, new_y1, new_x2, new_y2)

            elif item_type == "text":
                # Per il testo, scala solo la posizione del punto di ancoraggio
                x, y = self.canvas.coords(item_id)
                new_x = center_x + (x - center_x) * scale_factor
                new_y = center_y + (y - center_y) * scale_factor
                self.canvas.coords(item_id, new_x, new_y)

                # Scala anche la dimensione del font se possibile
                try:
                    font_info = self.canvas.itemcget(item_id, "font")
                    if font_info:
                        # Estrai le informazioni del font se è una tupla
                        if isinstance(font_info, tuple) and len(font_info) >= 2:
                            font_family, font_size = font_info[0], font_info[1]
                            new_font_size = max(8, int(font_size * scale_factor))
                            new_font = (font_family, new_font_size)
                            if len(font_info) > 2:
                                new_font = (
                                    font_info[:2] + (new_font_size,) + font_info[3:]
                                )
                            self.canvas.itemconfig(item_id, font=new_font)
                        elif isinstance(font_info, str):
                            # Se è una stringa, cerca di estrarre la dimensione
                            import re

                            size_match = re.search(r"\s(\d+)(?:\s|$)", font_info)
                            if size_match:
                                old_size = int(size_match.group(1))
                                new_size = max(8, int(old_size * scale_factor))
                                new_font_info = font_info.replace(
                                    f" {old_size}", f" {new_size}"
                                )
                                self.canvas.itemconfig(item_id, font=new_font_info)
                except Exception as font_e:
                    # Se non riusciamo a scalare il font, continua comunque
                    pass

        except Exception as e:
            print(f"⚠️ Errore scaling item {item_id} (tipo: {item_type}): {e}")

    def get_image_center(self):
        """Calcola il centro dell'immagine corrente per il punto di riferimento dello scaling."""
        if self.current_image_on_canvas is not None:
            # Ottieni le dimensioni del canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Ottieni le dimensioni dell'immagine scalata
            current_width = int(
                self.current_image_on_canvas.shape[1] * self.canvas_scale
            )
            current_height = int(
                self.current_image_on_canvas.shape[0] * self.canvas_scale
            )

            # Calcola la posizione dell'immagine esattamente come in update_canvas_display
            x_pos = max(0, (canvas_width - current_width) // 2) + self.canvas_offset_x
            y_pos = max(0, (canvas_height - current_height) // 2) + self.canvas_offset_y

            # Il centro dell'immagine è la posizione + metà delle dimensioni
            image_center_x = x_pos + current_width / 2
            image_center_y = y_pos + current_height / 2

            print(
                f"🔍 GET_CENTER DEBUG: canvas={canvas_width}x{canvas_height}, img_scaled={current_width}x{current_height}"
            )
            print(
                f"🔍 GET_CENTER DEBUG: offset=({self.canvas_offset_x:.1f}, {self.canvas_offset_y:.1f}), scale={self.canvas_scale:.2f}"
            )
            print(
                f"🔍 GET_CENTER DEBUG: img_pos=({x_pos:.1f}, {y_pos:.1f}), center=({image_center_x:.1f}, {image_center_y:.1f})"
            )

            return image_center_x, image_center_y
        else:
            # Fallback al centro del canvas se non c'è immagine
            return self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2

    def setup_layers_panel(self, parent):
        """Configura il pannello dei layer per il professional canvas."""
        # Frame principale per i layer
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar layer
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        # Bottoni layer con tooltip
        add_btn = ttk.Button(toolbar_frame, text="➕", width=3, command=self.add_layer)
        add_btn.pack(side=tk.LEFT, padx=(0, 2))
        ToolTip(add_btn, "Aggiungi nuovo layer\nCtrl+L per quick-add")

        remove_btn = ttk.Button(
            toolbar_frame, text="➖", width=3, command=self.remove_layer
        )
        remove_btn.pack(side=tk.LEFT, padx=(0, 2))
        ToolTip(remove_btn, "Rimuovi layer selezionato\n⚠️ Operazione irreversibile")

        visibility_btn = ttk.Button(
            toolbar_frame, text="👁", width=3, command=self.toggle_layer_visibility
        )
        visibility_btn.pack(side=tk.LEFT, padx=(0, 2))
        ToolTip(
            visibility_btn,
            "Toggle visibilità layer\nPuoi anche cliccare sull'icona occhio",
        )

        lock_btn = ttk.Button(
            toolbar_frame, text="🔒", width=3, command=self.toggle_layer_lock
        )
        lock_btn.pack(side=tk.LEFT)
        ToolTip(
            lock_btn,
            "Blocca/sblocca layer\nI layer bloccati non possono essere modificati",
        )

        # Treeview per i layer con tooltip
        self.layers_tree = ttk.Treeview(
            main_frame,
            columns=("Status", "Visible", "Locked"),
            show="tree headings",
            height=8,
        )

        self.layers_tree.heading("#0", text="Layer")
        self.layers_tree.heading("Status", text="🎯")
        self.layers_tree.heading("Visible", text="👁")
        self.layers_tree.heading("Locked", text="🔒")

        self.layers_tree.column("#0", width=140)
        self.layers_tree.column("Status", width=35)
        self.layers_tree.column("Visible", width=35)
        self.layers_tree.column("Locked", width=35)

        # Tooltip per la treeview
        ToolTip(
            self.layers_tree,
            "GESTIONE LAYERS:\n"
            "• Click su nome: seleziona layer attivo\n"
            "• Click su 👁: toggle visibilità\n"
            "• Click su 🔒: toggle blocco\n"
            "• Doppio click: rinomina layer\n"
            "• 🎯 = layer attivo per nuovi disegni",
        )

        # Scrollbar per layer
        layer_scrollbar = ttk.Scrollbar(
            main_frame, orient="vertical", command=self.layers_tree.yview
        )
        self.layers_tree.configure(yscrollcommand=layer_scrollbar.set)

        self.layers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        layer_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind eventi per gestione layer
        self.layers_tree.bind("<<TreeviewSelect>>", self.on_layer_select)
        self.layers_tree.bind("<Button-1>", self.on_layer_click)
        self.layers_tree.bind("<Double-Button-1>", self.on_layer_double_click)

        # Bind keyboard shortcuts per layers
        self.layers_tree.bind("<Delete>", self.on_delete_key)
        self.root.bind(
            "<Control-l>", self.quick_add_layer
        )  # Ctrl+L per quick add layer

        # Inizializza layer di default
        self.update_layers_display()

        # Layers tree ora collegato al canvas tkinter integrato
        # self.layers_tree è collegato al canvas principale

    def add_layer(self):
        """Aggiunge un nuovo layer."""
        import tkinter.simpledialog as simpledialog

        # Inizializza la lista layers se non esiste
        if not hasattr(self, "layers_list"):
            self.layers_list = []

        # Richiedi nome del layer
        layer_count = len(self.layers_list) + 1
        layer_name = simpledialog.askstring(
            "Nuovo Layer", "Nome del layer:", initialvalue=f"Layer {layer_count}"
        )
        if layer_name:
            # Crea un nuovo "layer" virtuale (gruppo di oggetti con tag comune)
            layer_tag = f"layer_{layer_count}"
            layer_info = {
                "name": layer_name,
                "tag": layer_tag,
                "visible": True,
                "locked": False,
            }
            self.layers_list.append(layer_info)

            # Imposta come layer attivo
            self.active_layer = layer_info
            print(
                f"➕ Layer '{layer_name}' creato con tag '{layer_tag}' e impostato come ATTIVO"
            )

            # Aggiorna la visualizzazione dei layers
            self.update_layers_display()

            # Feedback visivo
            print(
                f"✅ Layer aggiunto: {len(self.layers_list)} layers totali - Attivo: {layer_name}"
            )
        else:
            print("➕ Creazione layer annullata")

    def add_to_current_layer(self, canvas_item_id, item_type="generic"):
        """Aggiunge un elemento del canvas al layer correntemente attivo."""
        if hasattr(self, "active_layer") and self.active_layer and canvas_item_id:
            layer_tag = self.active_layer.get("tag", "default")
            # Assegna il tag del layer all'elemento del canvas
            self.canvas.itemconfig(canvas_item_id, tags=layer_tag)
            print(
                f"📌 Elemento {canvas_item_id} ({item_type}) aggiunto al layer '{self.active_layer['name']}'"
            )
            return True
        else:
            # Se non c'è layer attivo, usa tag default
            self.canvas.itemconfig(canvas_item_id, tags="default")
            print(
                f"📌 Elemento {canvas_item_id} ({item_type}) aggiunto al layer default"
            )
            return False

    def get_active_layer_info(self):
        """Restituisce informazioni sul layer attivo."""
        if hasattr(self, "active_layer") and self.active_layer:
            return {
                "name": self.active_layer.get("name", "Unknown"),
                "tag": self.active_layer.get("tag", "default"),
                "visible": self.active_layer.get("visible", True),
                "locked": self.active_layer.get("locked", False),
            }
        return {"name": "Default", "tag": "default", "visible": True, "locked": False}

    def remove_layer(self):
        """Rimuove il layer selezionato."""
        if not hasattr(self, "layers_tree"):
            return

        selection = self.layers_tree.selection()
        if not selection:
            print("⚠️ Nessun layer selezionato per la rimozione")
            return

        # Trova il layer selezionato
        selected_item = selection[0]
        layer_display_name = self.layers_tree.item(selected_item)["text"]
        layer_name = self._get_layer_base_name(layer_display_name)

        # Conferma rimozione
        import tkinter.messagebox as messagebox

        if not messagebox.askyesno(
            "Conferma Rimozione",
            f"Sei sicuro di voler rimuovere il layer '{layer_name}'?\n\nTutti gli elementi del layer verranno cancellati permanentemente.",
        ):
            print(f"➖ Rimozione layer '{layer_name}' annullata")
            return

        # Rimuovi dal sistema layers_list
        if hasattr(self, "layers_list") and self.layers_list:
            for i, layer in enumerate(self.layers_list):
                if layer["name"] == layer_name:
                    # Rimuovi tutti gli elementi del layer dal canvas
                    layer_tag = layer["tag"]
                    items_to_remove = self.canvas.find_withtag(layer_tag)
                    for item_id in items_to_remove:
                        self.canvas.delete(item_id)

                    # Se questo era il layer attivo, resetta il layer attivo
                    if (
                        hasattr(self, "active_layer")
                        and self.active_layer
                        and self.active_layer.get("name") == layer_name
                    ):
                        self.active_layer = None
                        print(f"🎯 Layer attivo resettato (layer rimosso)")

                    # Rimuovi dalla lista
                    self.layers_list.pop(i)
                    print(f"➖ Layer '{layer_name}' rimosso con successo")
                    print(f"   • {len(items_to_remove)} elementi rimossi dal canvas")
                    print(f"   • Layers rimanenti: {len(self.layers_list)}")

                    # Aggiorna la visualizzazione
                    self.update_layers_display()
                    return

        # Se non è un layer dell'utente, potrebbe essere un layer di esempio
        print(
            f"⚠️ Il layer '{layer_name}' non può essere rimosso (layer di sistema o non trovato)"
        )
        self.update_layers_display()

    def toggle_layer_visibility(self):
        """Toglie/mostra il layer selezionato."""
        if not hasattr(self, "layers_tree"):
            return

        selection = self.layers_tree.selection()
        if not selection:
            print("⚠️ Nessun layer selezionato")
            return

        # Trova il layer selezionato
        selected_item = selection[0]
        layer_name = self.layers_tree.item(selected_item)["text"]

        if not self._toggle_layer_visibility_by_name(layer_name):
            print(f"⚠️ Layer '{self._get_layer_base_name(layer_name)}' non trovato")

    def toggle_layer_lock(self):
        """Blocca/sblocca il layer selezionato."""
        if not hasattr(self, "layers_tree"):
            return

        selection = self.layers_tree.selection()
        if not selection:
            print("⚠️ Nessun layer selezionato")
            return

        # Trova il layer selezionato
        selected_item = selection[0]
        layer_name = self.layers_tree.item(selected_item)["text"]

        if not self._toggle_layer_lock_by_name(layer_name):
            print(f"⚠️ Layer '{self._get_layer_base_name(layer_name)}' non trovato")

    def on_layer_click(self, event):
        """Gestisce il click singolo su layer per azioni dirette sulle icone."""
        # Identifica su cosa ha cliccato l'utente
        item = self.layers_tree.identify("item", event.x, event.y)
        column = self.layers_tree.identify("column", event.x, event.y)

        if not item:
            return

        layer_name = self.layers_tree.item(item)["text"]

        # Click sulla colonna "Visible" (👁)
        if column == "#2":  # Colonna Visible
            self._toggle_layer_visibility_by_name(layer_name)
        # Click sulla colonna "Locked" (🔒)
        elif column == "#3":  # Colonna Locked
            self._toggle_layer_lock_by_name(layer_name)
        # Click sulla colonna "Status" o nome layer - imposta come attivo
        elif column == "#1" or column == "#0":  # Colonna Status o nome
            self._set_active_layer_by_name(layer_name)

    def on_layer_double_click(self, event):
        """Gestisce il doppio click per rinominare layer."""
        item = self.layers_tree.identify("item", event.x, event.y)
        if not item:
            return

        layer_name = self.layers_tree.item(item)["text"]
        self._rename_layer(layer_name)

    def _get_layer_base_name(self, display_name):
        """Estrae il nome base del layer dal nome visualizzato (che include il conteggio)."""
        # Rimuove la parte " (N)" dal nome
        import re

        match = re.match(r"^(.*?)\s*\(\d+\)$", display_name)
        return match.group(1) if match else display_name

    def _toggle_layer_visibility_by_name(self, layer_name):
        """Toggle visibilità layer per nome."""
        base_name = self._get_layer_base_name(layer_name)

        if hasattr(self, "layers_list") and self.layers_list:
            for layer in self.layers_list:
                if layer["name"] == base_name:
                    # Toggle visibilità
                    layer["visible"] = not layer["visible"]

                    # Nasconde/mostra gli elementi del layer sul canvas
                    if layer["visible"]:
                        # Mostra elementi del layer
                        for item_id in self.canvas.find_withtag(layer["tag"]):
                            self.canvas.itemconfig(item_id, state="normal")
                        print(f"👁 Layer '{base_name}' MOSTRATO")
                    else:
                        # Nasconde elementi del layer
                        for item_id in self.canvas.find_withtag(layer["tag"]):
                            self.canvas.itemconfig(item_id, state="hidden")
                        print(f"👁‍🗨 Layer '{base_name}' NASCOSTO")

                    self.update_layers_display()
                    return True
        return False

    def _toggle_layer_lock_by_name(self, layer_name):
        """Toggle lock layer per nome."""
        base_name = self._get_layer_base_name(layer_name)

        if hasattr(self, "layers_list") and self.layers_list:
            for layer in self.layers_list:
                if layer["name"] == base_name:
                    # Toggle lock
                    layer["locked"] = not layer["locked"]

                    if layer["locked"]:
                        print(f"🔒 Layer '{base_name}' BLOCCATO")
                    else:
                        print(f"🔓 Layer '{base_name}' SBLOCCATO")

                    self.update_layers_display()
                    return True
        return False

    def _set_active_layer_by_name(self, layer_name):
        """Imposta layer attivo per nome."""
        base_name = self._get_layer_base_name(layer_name)

        if hasattr(self, "layers_list") and self.layers_list:
            for layer in self.layers_list:
                if layer["name"] == base_name:
                    # Imposta come layer attivo
                    self.active_layer = layer
                    print(f"🎯 Layer ATTIVO impostato su: '{base_name}'")
                    self.update_layers_display()
                    return True

        # Se non è un layer dell'utente, imposta None (layer di default)
        self.active_layer = None
        print(f"🎯 Layer ATTIVO impostato su: Default ('{base_name}')")
        self.update_layers_display()
        return False

    def _rename_layer(self, old_name):
        """Rinomina un layer."""
        import tkinter.simpledialog as simpledialog

        base_name = self._get_layer_base_name(old_name)

        new_name = simpledialog.askstring(
            "Rinomina Layer", "Nuovo nome del layer:", initialvalue=base_name
        )

        if new_name and new_name != base_name:
            if hasattr(self, "layers_list") and self.layers_list:
                for layer in self.layers_list:
                    if layer["name"] == base_name:
                        layer["name"] = new_name
                        print(f"✏️ Layer rinominato da '{base_name}' a '{new_name}'")
                        self.update_layers_display()
                        return True
        return False

    def on_delete_key(self, event):
        """Gestisce la pressione del tasto Delete per rimuovere layer."""
        self.remove_layer()

    def quick_add_layer(self, event=None):
        """Aggiunge velocemente un nuovo layer con nome automatico."""
        if not hasattr(self, "layers_list"):
            self.layers_list = []

        layer_count = len(self.layers_list) + 1
        layer_name = f"Layer {layer_count}"

        import uuid

        layer_tag = f"layer_{layer_count}"
        layer_info = {
            "id": str(uuid.uuid4()),
            "name": layer_name,
            "tag": layer_tag,
            "visible": True,
            "locked": False,
        }
        self.layers_list.append(layer_info)

        # Imposta come layer attivo
        self.active_layer = layer_info
        print(f"⚡ Quick-add: Layer '{layer_name}' creato e attivato")

        # Aggiorna la visualizzazione dei layers
        self.update_layers_display()
        return "break"  # Previene ulteriore propagazione dell'evento

    def on_layer_select(self, event):
        """Gestisce la selezione di un layer nel tree per impostarlo come attivo."""
        selection = self.layers_tree.selection()
        if not selection:
            return

        selected_item = selection[0]
        layer_name = self.layers_tree.item(selected_item)["text"]

        # Non fare nulla qui - lascia che on_layer_click gestisca l'azione
        # Questo evita conflitti tra selezione e click
        pass

    def update_layers_display(self):
        """Aggiorna la visualizzazione dei layer."""
        if not hasattr(self, "layers_tree"):
            return

        # Pulisci tree
        for item in self.layers_tree.get_children():
            self.layers_tree.delete(item)

        # Visualizza i layer creati dall'utente e il layer base
        if hasattr(self, "layers_list") and self.layers_list:
            print(f"🔄 Visualizzazione {len(self.layers_list)} layers totali")
            for layer in self.layers_list:
                # Determina se questo è il layer attivo
                is_active = (
                    hasattr(self, "active_layer")
                    and self.active_layer
                    and self.active_layer.get("name") == layer["name"]
                )

                # Conta elementi nel layer
                element_count = len(
                    self.canvas.find_withtag(layer.get("tag", "default"))
                )

                # Prepara icone e testo
                status_icon = "🎯" if is_active else ""
                visible_icon = "👁" if layer["visible"] else "👁‍🗨"
                locked_icon = "🔒" if layer.get("locked", False) else "🔓"

                # Nome layer con conteggio elementi
                layer_display_name = f"{layer['name']} ({element_count})"

                item_id = self.layers_tree.insert(
                    "",
                    "end",
                    text=layer_display_name,
                    values=(status_icon, visible_icon, locked_icon),
                )

                # Evidenzia visivamente il layer attivo
                if is_active:
                    self.layers_tree.set(item_id, "Status", "🎯")
                    # Opzionalmente, seleziona il layer attivo nella tree
                    self.layers_tree.selection_set(item_id)
        else:
            # Crea layer base se non esiste
            self.create_default_layer_unified()

    def setup_integrated_preview(self, parent):
        """Configura l'area anteprima integrata con layout scrollabile moderno."""
        # Configura il grid del parent
        parent.grid_rowconfigure(0, weight=0, minsize=40)  # Controlli
        parent.grid_rowconfigure(1, weight=0, minsize=300)  # Video
        parent.grid_rowconfigure(2, weight=0, minsize=60)  # Info
        parent.grid_rowconfigure(3, weight=1, minsize=200)  # Debug logs (espandibile)
        parent.grid_columnconfigure(0, weight=1)

        # Frame controlli video avanzati
        controls_frame = ttk.LabelFrame(parent, text="🎬 Controlli Video", padding=5)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        controls_frame.grid_columnconfigure(1, weight=1)  # Seek bar espandibile

        # Prima riga: controlli di base
        control_row1 = ttk.Frame(controls_frame)
        control_row1.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 5))
        control_row1.grid_columnconfigure(2, weight=1)  # Spazio centrale espandibile

        # Checkbox anteprima attiva
        self.preview_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            control_row1,
            text="Attiva",
            variable=self.preview_enabled,
            command=self.toggle_video_preview,
        ).grid(row=0, column=0, padx=(0, 5), sticky="w")

        # Controlli playback
        playback_frame = ttk.Frame(control_row1)
        playback_frame.grid(row=0, column=1, padx=5)

        # Pulsanti controllo
        self.play_pause_btn = ttk.Button(
            playback_frame, text="▶️", width=3, command=self.toggle_play_pause
        )
        self.play_pause_btn.pack(side=tk.LEFT, padx=1)

        ttk.Button(playback_frame, text="⏹️", width=3, command=self.stop_video).pack(
            side=tk.LEFT, padx=1
        )

        # Pulsante cattura
        ttk.Button(
            control_row1,
            text="📸",
            width=3,
            command=self.capture_current_frame,
        ).grid(row=0, column=3, padx=(5, 0), sticky="e")

        # Seconda riga: seek bar e indicatori tempo (solo per file video)
        self.seek_frame = ttk.Frame(controls_frame)
        self.seek_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=2)
        self.seek_frame.grid_columnconfigure(1, weight=1)

        # Tempo corrente
        self.current_time_label = ttk.Label(
            self.seek_frame, textvariable=self.current_time_var, width=6
        )
        self.current_time_label.grid(row=0, column=0, padx=(0, 5))

        # Seek bar
        self.seek_scale = ttk.Scale(
            self.seek_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.seek_var,
            command=self.on_seek_change,
        )
        self.seek_scale.grid(row=0, column=1, sticky="ew", padx=5)

        # Tempo totale
        self.total_time_label = ttk.Label(
            self.seek_frame, textvariable=self.total_time_var, width=6
        )
        self.total_time_label.grid(row=0, column=2, padx=(5, 0))

        # Terza riga: controlli velocità
        speed_frame = ttk.Frame(controls_frame)
        speed_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(2, 0))
        speed_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(speed_frame, text="Velocità:").grid(
            row=0, column=0, padx=(0, 5), sticky="w"
        )

        speed_scale = ttk.Scale(
            speed_frame,
            from_=0.25,
            to=3.0,
            orient="horizontal",
            variable=self.speed_var,
            command=self.on_speed_change,
        )
        speed_scale.grid(row=0, column=1, sticky="ew", padx=5)

        self.speed_label = ttk.Label(speed_frame, text="1.0x", width=6)
        self.speed_label.grid(row=0, column=2, padx=(5, 0))

        # Area anteprima video con dimensioni responsive
        self.integrated_preview_frame = ttk.Frame(
            parent, relief="sunken", borderwidth=2, width=400, height=300
        )
        self.integrated_preview_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        self.integrated_preview_frame.grid_propagate(False)  # Mantiene dimensioni base

        # Label per l'anteprima che si adatta al contenuto
        self.preview_label = tk.Label(
            self.integrated_preview_frame,
            bg="black",
            text="Anteprima non attiva\n\nCarica un video o\navvia la webcam",
            fg="white",
            font=("Arial", 10),
            justify=tk.CENTER,
        )
        self.preview_label.pack(expand=True, fill=tk.BOTH)

        # Info frame per statistiche con altezza fissa
        self.preview_info_frame = ttk.Frame(parent, height=60)
        self.preview_info_frame.grid(row=2, column=0, sticky="ew")
        self.preview_info_frame.grid_propagate(False)  # Mantiene altezza fissa

        self.preview_info = ttk.Label(
            self.preview_info_frame,
            text="In attesa...",
            font=("Arial", 9),
            anchor="center",
            width=50,
        )
        self.preview_info.pack(pady=5)

        # NUOVO: Area Debug Logs con tabella migliori frame
        debug_frame = ttk.LabelFrame(
            parent, text="🔍 Debug - Migliori Frame", padding=5
        )
        debug_frame.grid(row=3, column=0, sticky="nsew", pady=(5, 0))
        debug_frame.grid_rowconfigure(0, weight=1)
        debug_frame.grid_columnconfigure(0, weight=1)

        # Frame per contenere treeview + scrollbar
        debug_container = ttk.Frame(debug_frame)
        debug_container.pack(fill="both", expand=True)
        debug_container.grid_rowconfigure(0, weight=1)
        debug_container.grid_columnconfigure(0, weight=1)

        # Treeview per i logs con colonne personalizzate
        columns = (
            "timestamp",
            "score",
            "yaw",
            "pitch",
            "roll",
            "symmetry",
            "description",
        )
        self.debug_tree = ttk.Treeview(
            debug_container, columns=columns, show="headings", height=8
        )

        # Configura le colonne
        self.debug_tree.heading("timestamp", text="Tempo")
        self.debug_tree.heading("score", text="Score")
        self.debug_tree.heading("yaw", text="Yaw")
        self.debug_tree.heading("pitch", text="Pitch")
        self.debug_tree.heading("roll", text="Roll")
        self.debug_tree.heading("symmetry", text="Sym")
        self.debug_tree.heading("description", text="Frame")

        # Imposta larghezze colonne ottimizzate per mostrare tutto senza scroll orizzontale
        self.debug_tree.column("timestamp", width=45, minwidth=40)
        self.debug_tree.column("score", width=55, minwidth=50)
        self.debug_tree.column("yaw", width=40, minwidth=35)
        self.debug_tree.column("pitch", width=40, minwidth=35)
        self.debug_tree.column("roll", width=40, minwidth=35)
        self.debug_tree.column("symmetry", width=50, minwidth=45)
        self.debug_tree.column("description", width=50, minwidth=45)

        # Solo scrollbar verticale
        debug_scrollbar_v = ttk.Scrollbar(
            debug_container, orient="vertical", command=self.debug_tree.yview
        )
        self.debug_tree.configure(yscrollcommand=debug_scrollbar_v.set)

        # Grid layout semplificato
        self.debug_tree.grid(row=0, column=0, sticky="nsew")
        debug_scrollbar_v.grid(row=0, column=1, sticky="ns")

        # Binding per doppio click su righe della tabella
        self.debug_tree.bind("<Double-1>", self.on_debug_row_double_click)

        # Configura il grid container
        debug_container.grid_rowconfigure(0, weight=1)
        debug_container.grid_columnconfigure(0, weight=1)

        # Frame controlli debug
        debug_controls = ttk.Frame(debug_frame)
        debug_controls.pack(fill="x", pady=(5, 0))

        ttk.Button(
            debug_controls, text="Pulisci Log", command=self.clear_debug_logs
        ).pack(side="left")

        self.debug_auto_scroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            debug_controls, text="Auto-scroll", variable=self.debug_auto_scroll
        ).pack(side="right")

        # Inizializza lista debug logs
        self.debug_logs = []
        self.max_debug_logs = 50  # Limite massimo entries

        # Inizializza stato controlli video
        self.update_video_controls_state()

    # =============== CONTROLLI VIDEO PLAYER ===============

    def toggle_play_pause(self):
        """Toggle play/pause per il video."""
        if self.video_analyzer.capture and self.video_analyzer.capture.isOpened():
            is_playing = self.video_analyzer.play_pause()
            self.is_playing = is_playing

            # Aggiorna icona pulsante
            if is_playing:
                self.play_pause_btn.config(text="⏸️")
                # Se il video è ripartito dall'inizio, aggiorna anche i controlli
                if not self.video_analyzer.is_capturing:
                    self.update_video_controls_state()
                    if hasattr(self, "update_seek_position"):
                        self.update_seek_position()
            else:
                self.play_pause_btn.config(text="▶️")

            print(f"🎬 Video {'riprodotto' if is_playing else 'in pausa'}")

    def stop_video(self):
        """Ferma il video/webcam."""
        self.video_analyzer.stop()
        self.is_playing = False
        self.play_pause_btn.config(text="▶️")

        if self.video_analyzer.is_video_file:
            # Per file video - Reset seek bar
            if not self.updating_seek:
                self.updating_seek = True
                self.seek_var.set(0)
                self.current_time_var.set("00:00")
                self.updating_seek = False
            print("🎬 Video fermato e riportato all'inizio")
        else:
            # Per webcam - Aggiorna interfaccia
            self.update_video_controls_state()
            self.preview_label.config(
                text="Webcam spenta\n\nUsa 'Avvia Webcam'\nper riattivare"
            )
            print("📹 Webcam spenta")

    def on_seek_change(self, value):
        """Gestisce il cambio della seek bar."""
        if self.updating_seek or not self.video_analyzer.is_video_file:
            return

        try:
            # Converte percentuale in millisecondi
            total_duration = self.video_analyzer.get_duration_ms()
            if total_duration > 0:
                seek_time = (float(value) / 100.0) * total_duration
                self.video_analyzer.seek_to_time(seek_time)

                # Aggiorna tempo corrente
                minutes = int(seek_time // 60000)
                seconds = int((seek_time % 60000) // 1000)
                self.current_time_var.set(f"{minutes:02d}:{seconds:02d}")

                print(f"🎬 Seek to {minutes:02d}:{seconds:02d}")
        except ValueError:
            pass

    def on_speed_change(self, value):
        """Gestisce il cambio di velocità."""
        try:
            speed = float(value)
            self.video_analyzer.set_playback_speed(speed)
            self.speed_label.config(text=f"{speed:.1f}x")
            print(f"🎬 Velocità impostata a {speed:.1f}x")
        except ValueError:
            pass

    def update_video_controls_state(self):
        """Aggiorna lo stato dei controlli video in base alla sorgente."""
        if hasattr(self, "seek_frame") and hasattr(self, "play_button"):
            if self.video_analyzer.is_video_file:
                # Abilita controlli per file video
                self.seek_frame.grid()
                self.seek_scale.config(state="normal")
                self.play_button.config(state="normal")
                self.stop_button.config(state="normal")

                # Aggiorna durata totale
                duration_ms = self.video_analyzer.get_duration_ms()
                if duration_ms > 0:
                    minutes = int(duration_ms // 60000)
                    seconds = int((duration_ms % 60000) // 1000)
                    self.total_time_var.set(f"{minutes:02d}:{seconds:02d}")

                # Aggiorna il testo del pulsante play/pause
                if self.video_analyzer.is_paused:
                    self.play_button.config(text="▶ Play")
                else:
                    self.play_button.config(text="⏸ Pause")
            else:
                # Per webcam, nascondi seek bar ma mantieni controlli base
                self.seek_frame.grid_remove()
                self.total_time_var.set("LIVE")
                self.current_time_var.set("LIVE")
                self.play_button.config(state="normal")
                self.stop_button.config(state="normal")

                # Per webcam: Play/Pause per il flusso live
                if self.video_analyzer.is_paused:
                    self.play_button.config(text="▶ Resume")
                else:
                    self.play_button.config(text="⏸ Pause")

    def update_seek_position(self):
        """Aggiorna la posizione della seek bar (chiamato periodicamente)."""
        if (
            self.video_analyzer.is_video_file
            and self.video_analyzer.is_capturing
            and not self.updating_seek
        ):

            current_ms = self.video_analyzer.get_current_time_ms()
            total_ms = self.video_analyzer.get_duration_ms()

            if total_ms > 0:
                self.updating_seek = True
                percentage = (current_ms / total_ms) * 100
                self.seek_var.set(percentage)

                # Aggiorna tempo corrente
                minutes = int(current_ms // 60000)
                seconds = int((current_ms % 60000) // 1000)
                self.current_time_var.set(f"{minutes:02d}:{seconds:02d}")
                self.updating_seek = False

        # Schedula prossimo aggiornamento
        self.root.after(500, self.update_seek_position)  # Ogni 500ms

    # =============== FINE CONTROLLI VIDEO ===============

    def add_debug_log(self, score, debug_data, elapsed_time):
        """Aggiunge una entry ai debug logs."""
        import datetime

        # Timestamp formattato
        timestamp = f"{elapsed_time:.1f}s"

        # Estrai dati dal debug_data e gestisci stringhe formattate
        yaw_str = debug_data.get("yaw", "0°")
        yaw = float(str(yaw_str).replace("°", "")) if yaw_str != "N/A" else 0

        pitch_str = debug_data.get("pitch", "0°")
        pitch = float(str(pitch_str).replace("°", "")) if pitch_str != "N/A" else 0

        roll_str = debug_data.get("roll", "0°")
        roll = float(str(roll_str).replace("°", "")) if roll_str != "N/A" else 0

        # Per symmetry, controlla prima nella sezione debug, poi nei dati principali
        symmetry_str = debug_data.get("debug", {}).get(
            "symmetry_score", debug_data.get("symmetry", "0")
        )
        symmetry = float(str(symmetry_str)) if symmetry_str != "N/A" else 0

        description = debug_data.get("description", "N/A")

        # Non troncare il numero del frame
        # (la descrizione ora contiene solo il numero del frame come #123)

        # Aggiungi alla lista
        log_entry = {
            "timestamp": timestamp,
            "score": f"{score:.3f}",
            "yaw": f"{yaw:.1f}°",
            "pitch": f"{pitch:.1f}°",
            "roll": f"{roll:.1f}°",
            "symmetry": f"{symmetry:.3f}",
            "description": description,
        }

        self.debug_logs.append(log_entry)

        # Rimuovi entries vecchie se troppo lunghe
        if len(self.debug_logs) > self.max_debug_logs:
            self.debug_logs.pop(0)

        # Aggiorna la treeview
        self.update_debug_tree()

    def update_debug_tree(self):
        """Aggiorna la visualizzazione della tabella debug."""
        # Pulisci treeview esistente
        for item in self.debug_tree.get_children():
            self.debug_tree.delete(item)

        # Ordina per score dal più alto al più basso
        sorted_logs = sorted(
            self.debug_logs, key=lambda x: float(x["score"]), reverse=True
        )

        for log_entry in sorted_logs:
            self.debug_tree.insert(
                "",
                "end",
                values=(
                    log_entry["timestamp"],
                    log_entry["score"],
                    log_entry["yaw"],
                    log_entry["pitch"],
                    log_entry["roll"],
                    log_entry["symmetry"],
                    log_entry["description"],
                ),
            )

        # Auto-scroll all'ultima entry se abilitato
        if hasattr(self, "debug_auto_scroll") and self.debug_auto_scroll.get():
            children = self.debug_tree.get_children()
            if children:
                self.debug_tree.selection_set(children[0])
                self.debug_tree.focus(children[0])
                self.debug_tree.see(children[0])

    def clear_debug_logs(self):
        """Pulisce tutti i debug logs."""
        self.debug_logs.clear()
        self.update_debug_tree()

    def reset_interface_for_new_analysis(self):
        """Reset completo dell'interfaccia per una nuova analisi."""
        # Reset debug logs
        self.debug_logs.clear()
        self.update_debug_tree()

        # Reset buffer frame per doppio click
        self.frame_buffer.clear()

        # Reset canvas centrale tkinter
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.delete("all")
            print("🧽 Canvas tkinter cleared")
        self.current_image = None
        self.current_landmarks = None

        # Reset contatori e stato
        self.current_best_score = 0.0

        # Reset info miglior frame
        self.best_frame_info.config(text="Nessun frame analizzato")

        # Reset status bar
        self.status_bar.config(text="Pronto per nuova analisi")

        # Reset anteprima se presente
        if hasattr(self, "preview_info") and self.preview_info:
            self.preview_info.config(text="🎯 Anteprima: Nessun frame")

        print("Interfaccia resettata per nuova analisi")

    def setup_measurements_area(self, parent):
        """Configura l'area delle misurazioni in modo compatto."""
        # Frame principale per l'area misurazioni
        main_frame = ttk.Frame(parent)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Treeview per le misurazioni esistenti (compatta)
        self.measurements_tree = ttk.Treeview(
            main_frame,
            columns=("Type", "Value", "Unit"),
            show="headings",
            height=8,  # Altezza ottimizzata
        )

        self.measurements_tree.heading("Type", text="Tipo")
        self.measurements_tree.heading("Value", text="Valore")
        self.measurements_tree.heading("Unit", text="Unità")

        self.measurements_tree.column("Type", width=200, minwidth=150)
        self.measurements_tree.column("Value", width=100, minwidth=80)
        self.measurements_tree.column("Unit", width=80, minwidth=60)

        # Scrollbar per la lista misurazioni
        tree_scroll = ttk.Scrollbar(
            main_frame, orient=tk.VERTICAL, command=self.measurements_tree.yview
        )
        self.measurements_tree.configure(yscrollcommand=tree_scroll.set)

        # Layout ottimizzato con grid
        self.measurements_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")

    def setup_status_bar(self):
        """Configura la status bar."""
        self.status_bar = ttk.Label(self.root, text="Pronto", relief="sunken")
        self.status_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

    def load_image(self):
        """Carica un'immagine dal file system."""
        file_path = filedialog.askopenfilename(
            title="Seleziona Immagine",
            filetypes=[
                ("Immagini", "*.jpg *.jpeg *.png *.bmp *.tiff"),
                ("Tutti i file", "*.*"),
            ],
        )

        if file_path:
            try:
                image = cv2.imread(file_path)
                if image is not None:
                    self.set_current_image(image)
                    self.status_bar.config(text=f"Immagine caricata: {file_path}")
                else:
                    messagebox.showerror("Errore", "Impossibile caricare l'immagine")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nel caricamento: {e}")

    def load_video(self):
        """Carica e analizza un file video con logging dettagliato per debug."""
        file_path = filedialog.askopenfilename(
            title="Seleziona Video",
            filetypes=[
                ("Video", "*.mp4 *.avi *.mov *.mkv *.wmv"),
                ("Tutti i file", "*.*"),
            ],
        )

        if file_path:
            print(f"🎬 STEP 1: File selezionato: {file_path}")

            # Reset completo interfaccia per nuovo video
            self.reset_interface_for_new_analysis()
            print("🎬 STEP 2: Interfaccia resettata")

            if self.video_analyzer.load_video_file(file_path):
                print("🎬 STEP 3: Video caricato correttamente in VideoAnalyzer")

                # Aggiorna controlli video per file video
                self.update_video_controls_state()
                self.update_seek_position()  # Inizia aggiornamenti seek bar

                self.status_bar.config(text="Avviando analisi video...")
                self.root.update()

                # Avvia l'analisi live
                if self.video_analyzer.start_live_analysis():
                    print("🎬 STEP 4: Analisi live avviata")
                    self.best_frame_info.config(text="Analizzando video file...")
                    self.status_bar.config(text=f"Analisi video avviata: {file_path}")
                else:
                    print("❌ ERRORE STEP 4: Impossibile avviare l'analisi live")
                    messagebox.showerror(
                        "Errore", "Impossibile avviare l'analisi video"
                    )
                    self.status_bar.config(text="Errore nell'analisi video")
            else:
                print("❌ ERRORE STEP 3: Impossibile caricare il video")
                messagebox.showerror("Errore", "Impossibile caricare il video")

    def test_webcam(self):
        """Testa la disponibilità della webcam."""
        import cv2

        available_cameras = []
        for i in range(5):  # Testa i primi 5 indici
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    available_cameras.append(i)
                cap.release()

        if available_cameras:
            message = f"Webcam disponibili agli indici: {available_cameras}\n"
            message += "La prima disponibile verrà usata automaticamente."
            messagebox.showinfo("Test Webcam", message)
        else:
            message = "Nessuna webcam trovata.\n\n"
            message += "Possibili cause:\n"
            message += "• Webcam non collegata\n"
            message += "• Driver non installati\n"
            message += "• Webcam in uso da altra applicazione\n"
            message += "• Permessi camera negati"
            messagebox.showwarning("Test Webcam", message)

    def start_webcam(self):
        """Avvia l'analisi dalla webcam."""
        print("Tentativo di avvio webcam...")

        # Reset completo interfaccia per nuova analisi webcam
        self.reset_interface_for_new_analysis()

        if self.video_analyzer.start_camera_capture():
            print("Webcam avviata con successo, iniziando analisi...")

            # Aggiorna controlli video per webcam
            self.update_video_controls_state()

            if self.video_analyzer.start_live_analysis():
                # Aggiorna l'anteprima integrata
                self.update_integrated_preview_status("Webcam Live - In analisi...")
                self.status_bar.config(text="Analisi webcam avviata")
                print("Analisi live avviata")
            else:
                messagebox.showerror("Errore", "Impossibile avviare l'analisi live")
                print("Errore nell'avvio dell'analisi live")
        else:
            error_msg = "Impossibile avviare la webcam. Verifica:\n"
            error_msg += "1. Che la webcam sia collegata\n"
            error_msg += "2. Che non sia usata da altre applicazioni\n"
            error_msg += "3. Che i driver siano installati"
            messagebox.showerror("Errore Webcam", error_msg)
            print("Errore nell'avvio della webcam")

    def update_integrated_preview_status(self, text):
        """Aggiorna il testo di status dell'anteprima integrata."""
        if hasattr(self, "preview_info") and self.preview_info:
            self.preview_info.config(text=text)

    def check_and_create_preview(self):
        """Controlla se l'analisi è attiva e crea la finestra anteprima."""
        if self.preview_enabled.get() and self.video_analyzer.is_capturing:
            self.create_preview_window("Anteprima Webcam - Analisi Live")

    def stop_video_analysis(self):
        """Ferma l'analisi video e carica il frame migliore."""
        self.video_analyzer.stop_analysis()

        # Chiudi la finestra di anteprima
        self.close_preview_window()

        best_frame, best_landmarks, best_score = (
            self.video_analyzer.get_best_frame_data()
        )

        if best_frame is not None:
            self.set_current_image(best_frame, best_landmarks, auto_resize=False)
            self.best_frame_info.config(text=f"Miglior frame: Score {best_score:.2f}")
            self.status_bar.config(text="Analisi completata - Frame migliore caricato")
        else:
            self.status_bar.config(text="Nessun frame valido trovato")

    def on_video_frame_update(self, frame: np.ndarray, score: float):
        """Callback per aggiornamento frame in tempo reale - CON AGGIORNAMENTO ISTANTANEO."""

        # Ottieni info dettagliate sull'orientamento se disponibili
        try:
            from src.utils import get_advanced_orientation_score

            landmarks = self.face_detector.detect_face_landmarks(frame)
            if landmarks:
                image_size = (frame.shape[1], frame.shape[0])
                _, head_pose_data = get_advanced_orientation_score(
                    landmarks, image_size
                )

                if head_pose_data.get("method") in [
                    "head_pose_3d",
                    "geometric_improved",
                    "pure_frontal",  # AGGIUNTO il nuovo metodo
                ]:
                    # Mostra info dettagliate con il NUOVO ALGORITMO
                    pitch = head_pose_data.get("pitch", 0)
                    yaw = head_pose_data.get("yaw", 0)
                    roll = head_pose_data.get("roll", 0)

                    # Ottieni dati di debug del NUOVO algoritmo
                    debug = head_pose_data.get("debug", {})
                    if debug and head_pose_data.get("method") == "pure_frontal":
                        nose_score = debug.get("nose_score", 0)
                        eye_score = debug.get("eye_level_score", 0)
                        mouth_score = debug.get("mouth_score", 0)
                        nose_ratio = debug.get("nose_symmetry_ratio", 0)

                        info_text = (
                            f"Score: {score:.4f} | Naso:{nose_score:.3f} Occhi:{eye_score:.3f} "
                            f"Bocca:{mouth_score:.3f} | Y:{yaw:.1f}° R:{roll:.1f}°"
                        )
                    else:
                        info_text = f"Score: {score:.4f} | Y:{yaw:.1f}° P:{pitch:.1f}° R:{roll:.1f}°"
                else:
                    info_text = f"Score: {score:.3f} (fallback)"
            else:
                info_text = f"Score: {score:.2f}"
        except Exception as e:
            info_text = f"Score: {score:.2f} (error: {str(e)[:30]})"

        # Aggiorna info in tempo reale
        self.root.after(0, lambda: self.best_frame_info.config(text=info_text))

        # AGGIORNAMENTO FREQUENTE: ad ogni miglioramento dello score
        current_best_score = getattr(self, "current_best_score", 0.0)

        # NUOVO APPROCCIO: aggiorna ad OGNI miglioramento, anche minimo
        should_update = (
            score > 0.3 and self.current_image is None
        ) or (  # Primo frame decente
            score > current_best_score + 0.01
        )  # QUALSIASI miglioramento

        if should_update:
            # Ottieni i landmark del frame corrente se non li abbiamo già
            if landmarks is None:
                landmarks = self.face_detector.detect_face_landmarks(frame)

            if landmarks is not None:
                # Salva nel buffer per il doppio click
                frame_number = getattr(self.video_analyzer, "frame_counter", 0)
                self.save_frame_to_buffer(frame_number, frame.copy(), landmarks)

                # Aggiorna nel thread principale IMMEDIATAMENTE
                frame_copy = frame.copy()
                landmarks_copy = (
                    landmarks.copy() if hasattr(landmarks, "copy") else list(landmarks)
                )
                self.root.after(
                    0,
                    lambda: self.update_canvas_with_new_frame(
                        frame_copy, landmarks_copy, score
                    ),
                )
                self.current_best_score = score

                print(
                    f"Canvas aggiornato! Score: {score:.4f} (era: {current_best_score:.4f})"
                )

        # Salva TUTTI i frame con score discreto nel buffer (per debug table)
        elif (
            score > 0.2 and landmarks is not None
        ):  # Soglia molto bassa per buffer completo
            frame_number = getattr(self.video_analyzer, "frame_counter", 0)
            self.save_frame_to_buffer(frame_number, frame.copy(), landmarks)

        # Aggiorna info anteprima se presente con nuovi parametri YAW/ROLL
        if hasattr(self, "preview_info") and self.preview_info:
            try:
                if head_pose_data and head_pose_data.get("method") in [
                    "head_pose_3d",
                    "geometric_improved",
                    "pure_frontal",  # AGGIUNTO nuovo metodo
                ]:
                    desc = head_pose_data.get("description", "N/A")
                    suitable = head_pose_data.get("suitable_for_measurement", False)

                    # Debug specifico per il nuovo algoritmo
                    debug = head_pose_data.get("debug", {})
                    if debug and head_pose_data.get("method") == "pure_frontal":
                        nose_score = debug.get("nose_score", 0)
                        eye_score = debug.get("eye_level_score", 0)
                        debug_text = f" | N:{nose_score:.2f} E:{eye_score:.2f}"
                        desc_with_debug = desc + debug_text
                    else:
                        desc_with_debug = desc

                    if suitable:
                        status_text = f"🎯 Score: {score:.4f} - {desc_with_debug} ✅"
                    else:
                        status_text = f"🎯 Score: {score:.4f} - {desc_with_debug} ⚠️"
                else:
                    # Fallback al sistema originale
                    status_text = f"🎯 Score frontalità: {score:.2f}"
                    if score > 0.7:
                        status_text += " - Ottimo! 🟢"
                    elif score > 0.5:
                        status_text += " - Buono 🟡"
                    else:
                        status_text += " - Migliora posizione 🔴"
            except Exception:
                status_text = f"🎯 Score: {score:.2f}"

            self.root.after(0, lambda: self.preview_info.config(text=status_text))

    def on_video_preview_update(self, frame: np.ndarray):
        """Callback per aggiornamento anteprima video in tempo reale."""
        if self.preview_enabled and self.preview_enabled.get() and self.preview_label:
            try:
                # Calcola dimensioni proporzionate mantenendo aspect ratio
                frame_height, frame_width = frame.shape[:2]
                aspect_ratio = frame_width / frame_height

                # Area disponibile nell'anteprima
                max_width = 390  # Leggermente meno del frame per bordi
                max_height = 290

                # Calcola dimensioni finali mantenendo aspect ratio
                if aspect_ratio > max_width / max_height:
                    # Video più largo che alto
                    preview_width = max_width
                    preview_height = int(max_width / aspect_ratio)
                else:
                    # Video più alto che largo
                    preview_height = max_height
                    preview_width = int(max_height * aspect_ratio)

                # Ridimensiona il frame mantenendo proporzioni
                preview_frame = cv2.resize(frame, (preview_width, preview_height))

                # Converti per Tkinter
                preview_rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(preview_rgb)
                photo = ImageTk.PhotoImage(pil_image)

                # Aggiorna la label dell'anteprima nel thread principale
                self.root.after(
                    0, lambda: self.update_integrated_preview_display(photo)
                )
            except Exception as e:
                print(f"Errore nell'aggiornamento anteprima: {e}")

    def update_integrated_preview_display(self, photo):
        """Aggiorna il display dell'anteprima integrata."""
        try:
            if self.preview_label:
                self.preview_label.configure(image=photo, text="")
                self.preview_label.image = photo  # Mantiene riferimento
        except Exception as e:
            print(f"Errore nell'aggiornamento display anteprima integrata: {e}")

    def update_canvas_with_new_frame(self, frame: np.ndarray, landmarks, score: float):
        """Aggiorna il canvas con un nuovo frame migliore."""
        try:
            # Usa il metodo esistente per impostare l'immagine corrente
            self.set_current_image(frame, landmarks)

            # Forza il refresh del canvas unificato
            self._force_canvas_refresh()
            print("🔄 Canvas unified refreshed")

            # Aggiorna le informazioni
            self.best_frame_info.config(
                text=f"Miglior frame: Score {score:.2f} (Auto-aggiornato)"
            )
            self.status_bar.config(
                text=f"Canvas aggiornato automaticamente - Score: {score:.2f}"
            )

            print(
                f"🖼️ Canvas aggiornato e refreshed automaticamente - Score: {score:.2f}"
            )

        except Exception as e:
            print(f"❌ Errore nell'aggiornamento automatico del canvas: {e}")

    def _force_canvas_refresh(self):
        """Metodo di utilità per forzare il refresh del canvas unificato"""
        try:
            # Refresh del canvas tkinter unificato
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.update()
                self.canvas.update_idletasks()
                print("✅ Canvas tkinter unified refreshed")
        except Exception as e:
            print(f"❌ Errore nel refresh del canvas: {e}")

    def on_analysis_completion(self):
        """Callback chiamato quando l'analisi video termina. SEMPLIFICATO."""

        def handle_completion():
            # Aggiorna stato interfaccia
            self.is_playing = False
            self.play_pause_btn.config(text="▶️")

            # Carica direttamente il frame migliore
            best_frame, best_landmarks, best_score = (
                self.video_analyzer.get_best_frame_data()
            )

            if best_frame is not None:
                print(f"🎯 Analisi completata! Miglior score: {best_score:.3f}")
                self.set_current_image(best_frame, best_landmarks, auto_resize=False)
                self.best_frame_info.config(
                    text=f"✅ MIGLIOR FRAME FRONTALE: Score {best_score:.3f}"
                )
                self.status_bar.config(
                    text="Analisi completata - Frame frontale caricato"
                )
            else:
                print("❌ Nessun volto frontale trovato")
                self.status_bar.config(
                    text="Analisi completata - Nessun volto frontale rilevato"
                )

        # Esegui nel thread principale
        self.root.after(0, handle_completion)

    def on_frame_update(self, frame, landmarks, score):
        """
        Callback per aggiornare il canvas principale in tempo reale con i frame migliori.
        *** NUOVO METODO PER CANVAS DINAMICO ***
        """

        def update_canvas():
            try:
                print(f"🔄 INIZIO aggiornamento canvas dinamico - Score: {score:.3f}")

                # Aggiorna canvas principale con il nuovo frame migliore
                self.set_current_image(frame, landmarks, auto_resize=False)

                # Forza il refresh del canvas per assicurarsi che si veda
                self.root.update_idletasks()  # AGGIUNTO: forza aggiornamento UI

                # Aggiorna info score
                self.best_frame_info.config(
                    text=f"📸 FRAME FRONTALE IN TEMPO REALE: Score {score:.3f}"
                )

                # Aggiorna status
                self.status_bar.config(
                    text=f"Trovato frame frontale - Score: {score:.3f}"
                )

                print(f"✅ Canvas aggiornato e UI forzata - Score: {score:.3f}")

            except Exception as e:
                print(f"❌ Errore aggiornamento canvas in tempo reale: {e}")
                import traceback

                traceback.print_exc()

        # Esegui nel thread principale
        self.root.after(0, update_canvas)

    def on_debug_update(
        self, video_time_seconds, frame_number, score, debug_info, frame
    ):
        """
        Callback per aggiungere dati debug alla tabella GUI e al buffer.
        *** METODO PER TABELLA DEBUG CLICCABILE CON TEMPO IN SECONDI ***
        """

        def update_debug_table():
            try:
                # Genera un ID unico basato sul timestamp per il buffer
                buffer_id = f"t_{video_time_seconds:.3f}"

                # Salva frame nel buffer per click
                self.frame_buffer[buffer_id] = (
                    frame.copy(),
                    None,
                )  # Landmarks verranno calcolati se necessario

                # Mantieni buffer limitato
                if len(self.frame_buffer) > self.max_buffer_size:
                    # Rimuovi il frame più vecchio
                    oldest_frame = min(self.frame_buffer.keys())
                    del self.frame_buffer[oldest_frame]

                # Estrai dati debug
                yaw_score = debug_info.get("yaw_score", 0) * 100
                pitch_score = debug_info.get("pitch_score", 0) * 100
                simmetria_score = debug_info.get("simmetria_score", 0) * 100
                dimensione_score = debug_info.get("dimensione_score", 0) * 100

                # Aggiungi alla tabella
                new_item = self.debug_tree.insert(
                    "",
                    "end",
                    values=(
                        f"{video_time_seconds:.1f}s",  # tempo in secondi
                        f"{score:.3f}",  # score finale
                        f"{yaw_score:.0f}",  # yaw (rotazione sx/dx)
                        f"{pitch_score:.0f}",  # pitch (su/giù)
                        f"{dimensione_score:.0f}",  # roll -> dimensione
                        f"{simmetria_score:.0f}",  # simmetria
                        f"#{frame_number}",  # numero del frame
                    ),
                    tags=(buffer_id,),  # Tag per identificare il frame
                )

                # Riordina la tabella per score decrescente (migliori in cima)
                self._sort_debug_table_by_score()

                # Scroll all'inizio per mostrare i migliori frame
                self.debug_tree.yview_moveto(0.0)

                # *** AGGIORNAMENTO AUTOMATICO CANVAS SE NUOVO MIGLIOR FRAME ***
                if score > self.current_best_score:
                    print(
                        f"🆕 Nuovo miglior frame! Score: {score:.3f} (precedente: {self.current_best_score:.3f})"
                    )
                    self.current_best_score = score
                    # Aggiorna il canvas con il nuovo frame migliore
                    self.set_current_image(frame, None, auto_resize=False)
                    # Aggiorna info score
                    self.best_frame_info.config(
                        text=f"Miglior frame: Score {score:.3f}"
                    )

                    # *** SALVA AUTOMATICAMENTE IL MIGLIOR FRAME COME PNG ***
                    try:
                        import cv2

                        png_filename = "best_frontal_frame.png"
                        # Converti da BGR (OpenCV) a RGB per il salvataggio
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        cv2.imwrite(
                            png_filename, cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                        )
                        print(
                            f"💾 Salvato automaticamente: {png_filename} (Score: {score:.3f})"
                        )
                    except Exception as save_error:
                        print(f"❌ Errore salvataggio PNG: {save_error}")

                    print(
                        f"🖼️ Canvas aggiornato automaticamente con frame #{frame_number} al tempo {video_time_seconds:.1f}s"
                    )

            except Exception as e:
                print(f"❌ Errore aggiornamento tabella debug: {e}")

        # Esegui nel thread principale
        self.root.after(0, update_debug_table)

    def _sort_debug_table_by_score(self):
        """
        Riordina la tabella debug per score decrescente (migliori in cima).
        """
        try:
            # Ottieni tutti gli elementi
            items = []
            for child in self.debug_tree.get_children():
                item = self.debug_tree.item(child)
                values = item["values"]
                score = float(values[1])  # Score è nella seconda colonna
                items.append((score, child, values, item["tags"]))

            # Ordina per score decrescente
            items.sort(key=lambda x: x[0], reverse=True)

            # Rimuovi tutti gli elementi
            for child in self.debug_tree.get_children():
                self.debug_tree.delete(child)

            # Reinserisci in ordine
            for score, old_child, values, tags in items:
                self.debug_tree.insert("", "end", values=values, tags=tags)

        except Exception as e:
            print(f"❌ Errore ordinamento tabella debug: {e}")

    def on_debug_row_double_click(self, event):
        """
        Gestisce il doppio click sulle righe della tabella debug.
        Carica il frame corrispondente nel canvas principale.
        """
        try:
            selection = self.debug_tree.selection()
            if not selection:
                return

            item = self.debug_tree.item(selection[0])

            # Ottieni il tag che contiene l'ID del buffer
            tags = item["tags"]
            if not tags:
                return

            buffer_id = tags[0]  # Il tag contiene l'ID del buffer (es. "t_12.345")

            # Cerca frame nel buffer
            if buffer_id in self.frame_buffer:
                frame, landmarks = self.frame_buffer[buffer_id]

                # Carica nel canvas
                self.set_current_image(frame, landmarks, auto_resize=False)

                # Aggiorna info
                timestamp = item["values"][0]  # Primo valore è il tempo (es. "12.3s")
                score = float(item["values"][1])  # Secondo valore è lo score
                self.best_frame_info.config(
                    text=f"📸 FRAME DA TABELLA: {timestamp} - Score {score:.3f}"
                )
                self.status_bar.config(
                    text=f"Caricato frame al tempo {timestamp} dalla tabella debug"
                )

                print(f"📸 Caricato frame al tempo {timestamp} dalla tabella debug")
            else:
                self.status_bar.config(
                    text=f"Frame al tempo {item['values'][0]} non disponibile nel buffer"
                )

        except Exception as e:
            print(f"❌ Errore caricamento frame da tabella: {e}")
            self.status_bar.config(text="Errore nel caricamento del frame")

    def update_preview_display(self, photo):
        """Aggiorna il display dell'anteprima nel thread principale."""
        try:
            if (
                self.preview_label
                and self.preview_window
                and self.preview_window.winfo_exists()
            ):
                self.preview_label.configure(image=photo)
                self.preview_label.image = (
                    photo  # Mantiene riferimento per evitare garbage collection
                )
        except tk.TclError:
            # Finestra chiusa, ignora l'errore
            pass
        except Exception as e:
            print(f"Errore nell'aggiornamento display anteprima: {e}")

    def set_current_image(
        self,
        image,  # Può essere np.ndarray o PIL.Image
        landmarks: Optional[List[Tuple[float, float]]] = None,
        auto_resize: bool = True,
    ):
        """Imposta l'immagine corrente nel canvas tkinter (RIPRISTINO ORIGINALE + PIL)."""

        # Gestisce sia np.ndarray che PIL.Image nel sistema unificato
        if isinstance(image, Image.Image):
            # È una PIL Image, converti in numpy array
            image_array = np.array(image)
            # PIL è già RGB, OpenCV è BGR, quindi potrebbe servire conversione
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                # Se è RGB (PIL), converti in BGR per compatibilità con OpenCV
                image_array = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
            print(
                f"🖼️ Caricamento PIL Image nel canvas tkinter: {image.size} -> {image_array.shape}"
            )
        else:
            # È già un numpy array (OpenCV format BGR)
            image_array = image
            print(f"🖼️ Caricamento numpy array nel canvas tkinter: {image_array.shape}")

        # SALVA IMMAGINE CORRENTE
        self.current_image = image_array.copy()
        self.current_image_on_canvas = image_array.copy()
        self.current_landmarks = landmarks

        # RIPRISTINA SCALA E OFFSET se auto_resize
        if auto_resize:
            self.canvas_scale = 1.0
            self.canvas_offset_x = 0
            self.canvas_offset_y = 0
            print(f"Auto-resize attivato: scala={self.canvas_scale}")

        # Se non ci sono landmarks, rileva automaticamente
        if landmarks is None:
            print("Rilevamento automatico landmarks...")
            self.detect_landmarks()
            # detect_landmarks chiama già update_canvas_display
        else:
            # Visualizza direttamente
            print("Visualizzazione immagine con landmarks forniti...")
            self.update_canvas_display()

        print("✅ set_current_image completato")

    def set_image_no_resize(self, image):
        """Imposta l'immagine senza auto-resize nel sistema unificato."""
        print("🖼️ set_image_no_resize chiamato - usa set_current_image")
        self.set_current_image(
            image, landmarks=self.current_landmarks, auto_resize=False
        )

    def update_canvas_display(self):
        """Aggiorna la visualizzazione del canvas tkinter (RIPRISTINO ORIGINALE + OVERLAY)."""
        if self.current_image_on_canvas is None:
            return

        # CREA IMMAGINE CON OVERLAY CONDIZIONALI (solo se abilitati nell'interfaccia)
        display_image = self.current_image_on_canvas.copy()

        # Disegna landmarks SOLO se abilitati nell'interfaccia
        if (
            hasattr(self, "all_landmarks_var")
            and hasattr(self.all_landmarks_var, "get")
            and self.all_landmarks_var.get()
            and self.current_landmarks
        ):

            print("🎯 Disegno landmarks - abilitati nell'interfaccia")
            display_image = self.face_detector.draw_landmarks(
                display_image,
                self.current_landmarks,
                draw_all=True,
                key_only=False,
            )
        elif self.current_landmarks:
            print("⚪ Landmarks presenti ma NON abilitati nell'interfaccia")

        # Disegna asse di simmetria SOLO se abilitato nell'interfaccia
        if (
            hasattr(self, "show_axis_var")
            and hasattr(self.show_axis_var, "get")
            and self.show_axis_var.get()
            and self.current_landmarks
        ):

            print("🎯 Disegno asse di simmetria - abilitato nell'interfaccia")
            display_image = self.face_detector.draw_symmetry_axis(
                display_image, self.current_landmarks
            )

        # Disegna puntini verdi SOLO se abilitati nell'interfaccia
        if (
            hasattr(self, "green_dots_var")
            and hasattr(self.green_dots_var, "get")
            and self.green_dots_var.get()
            and hasattr(self, "green_dots_overlay")
            and self.green_dots_overlay is not None
        ):

            print("🎯 Disegno puntini verdi - abilitati nell'interfaccia")
            # Applica overlay trasparente puntini verdi
            try:
                display_pil = Image.fromarray(
                    cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
                )
                display_pil = Image.alpha_composite(
                    display_pil.convert("RGBA"), self.green_dots_overlay.convert("RGBA")
                )
                display_image = cv2.cvtColor(
                    np.array(display_pil.convert("RGB")), cv2.COLOR_RGB2BGR
                )
            except Exception as e:
                print(f"Errore overlay puntini verdi: {e}")

        # Disegna overlay misurazioni SOLO se abilitati nell'interfaccia
        if (
            hasattr(self, "overlay_var")
            and hasattr(self.overlay_var, "get")
            and self.overlay_var.get()
            and hasattr(self, "draw_measurement_overlays")
        ):

            print("🎯 Disegno overlay misurazioni - abilitati nell'interfaccia")
            display_image = self.draw_measurement_overlays(display_image)

        # Disegna sempre le selezioni correnti (punti selezionati dall'utente)
        if hasattr(self, "selected_points") and self.selected_points:
            print(f"🎯 Disegno {len(self.selected_points)} punti selezionati")
            for i, point in enumerate(self.selected_points):
                cv2.circle(display_image, point, 5, (255, 0, 255), -1)

        # ORA VISUALIZZA NEL CANVAS TKINTER
        try:
            # Attendi che il canvas sia renderizzato
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width <= 1 or canvas_height <= 1:
                # Canvas non ancora renderizzato, riprova dopo
                print("Canvas non ancora pronto, riprovo tra 100ms...")
                self.canvas.after(100, self.update_canvas_display)
                return

            print(f"Canvas pronto: {canvas_width}x{canvas_height}")

            # Converti l'immagine OpenCV (BGR) in PIL (RGB)
            image_rgb = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)

            # Ridimensiona secondo la scala
            height, width = image_rgb.shape[:2]
            new_width = int(width * self.canvas_scale)
            new_height = int(height * self.canvas_scale)

            print(
                f"Immagine: {width}x{height} -> {new_width}x{new_height} (scala {self.canvas_scale})"
            )

            if new_width > 0 and new_height > 0:
                # Ridimensiona l'immagine
                image_resized = cv2.resize(image_rgb, (new_width, new_height))

                # Converte in PIL per tkinter
                pil_image = Image.fromarray(image_resized)
                self.tk_image = ImageTk.PhotoImage(pil_image)

                # Pulisce solo l'immagine, NON i disegni
                for item in self.canvas.find_all():
                    if not "drawing" in self.canvas.gettags(
                        item
                    ) and not "temp_drawing" in self.canvas.gettags(item):
                        self.canvas.delete(item)

                # Centra l'immagine nel canvas
                x_pos = max(0, (canvas_width - new_width) // 2) + self.canvas_offset_x
                y_pos = max(0, (canvas_height - new_height) // 2) + self.canvas_offset_y

                # Posiziona l'immagine
                self.canvas_image_id = self.canvas.create_image(
                    x_pos, y_pos, anchor=tk.NW, image=self.tk_image
                )

                # IMPORTANTE: Mantieni riferimento per evitare garbage collection
                self.canvas.image = self.tk_image

                # CRITICO: Porta i disegni in primo piano sopra l'immagine
                self.canvas.tag_raise("drawing")
                self.canvas.tag_raise("temp_drawing")

                # Porta in primo piano anche i disegni dei layer specifici
                if hasattr(self, "layers_list") and self.layers_list:
                    for layer in self.layers_list:
                        self.canvas.tag_raise(layer["tag"])

                print(
                    f"✅ Immagine posizionata a ({x_pos}, {y_pos}) con ID {self.canvas_image_id} - Disegni portati in primo piano"
                )

                # DISEGNA LANDMARKS AGGIUNTIVI direttamente sul canvas SOLO se abilitati
                if (
                    self.current_landmarks
                    and hasattr(self, "all_landmarks_var")
                    and hasattr(self.all_landmarks_var, "get")
                    and self.all_landmarks_var.get()
                ):

                    print("🔴 Disegno landmarks rossi aggiuntivi sul canvas")
                    self.draw_landmarks_on_canvas(x_pos, y_pos, self.canvas_scale)
                else:
                    print("⚪ Landmarks presenti ma overlay rosso DISABILITATO")

                # Forza l'aggiornamento visivo
                self.canvas.update_idletasks()

        except Exception as e:
            print(f"❌ Errore aggiornamento canvas: {e}")
            import traceback

            traceback.print_exc()

    def draw_landmarks_on_canvas(self, img_x_offset, img_y_offset, scale):
        """Disegna i landmarks sul canvas tkinter (RIPRISTINO ORIGINALE)."""
        if not self.current_landmarks:
            return

        for x, y in self.current_landmarks:
            # Applica scala e offset
            canvas_x = img_x_offset + (x * scale)
            canvas_y = img_y_offset + (y * scale)

            # Disegna punto landmark
            radius = max(1, int(2 * scale))
            self.canvas.create_oval(
                canvas_x - radius,
                canvas_y - radius,
                canvas_x + radius,
                canvas_y + radius,
                fill="red",
                outline="darkred",
                width=1,
            )

        print(f"✅ Disegnati {len(self.current_landmarks)} landmarks")

    def detect_landmarks(self):
        """Rileva i landmark facciali nell'immagine corrente (RIPRISTINO ORIGINALE)."""
        if self.current_image is not None:
            landmarks = self.face_detector.detect_face_landmarks(self.current_image)
            self.current_landmarks = landmarks

            # Aggiorna la visualizzazione del canvas tkinter
            self.update_canvas_display()

            if landmarks:
                self.status_bar.config(text=f"Rilevati {len(landmarks)} landmark")
            else:
                self.status_bar.config(text="Nessun volto rilevato")

    def detect_green_dots(self):
        """Rileva i puntini verdi nell'immagine corrente per mappare i perimetri sopraccigliare."""
        if self.current_image is None:
            messagebox.showwarning("Attenzione", "Nessuna immagine caricata")
            return

        try:
            # Converte l'immagine OpenCV in formato PIL
            image_rgb = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)

            # Processa l'immagine per rilevare i puntini verdi
            results = self.green_dots_processor.process_pil_image(pil_image)

            # Salva i risultati
            self.green_dots_results = results

            if results["success"]:
                # Salva l'overlay generato
                self.green_dots_overlay = results["overlay"]

                # Abilita automaticamente la visualizzazione dell'overlay
                self.show_green_dots_overlay = True
                self.green_dots_var.set(True)

                # Aggiorna la visualizzazione del canvas unificato
                self.update_canvas_display()

                # Aggiunge misurazioni alla tabella
                left_stats = results["statistics"]["left"]
                right_stats = results["statistics"]["right"]
                combined_stats = results["statistics"]["combined"]

                # Aggiunge le statistiche delle aree sopraccigliare
                self.add_measurement(
                    "Area Sopracciglio Sx", f"{left_stats['area']:.1f}", "px²"
                )
                self.add_measurement(
                    "Area Sopracciglio Dx", f"{right_stats['area']:.1f}", "px²"
                )
                self.add_measurement(
                    "Perimetro Sopracciglio Sx", f"{left_stats['perimeter']:.1f}", "px"
                )
                self.add_measurement(
                    "Perimetro Sopracciglio Dx", f"{right_stats['perimeter']:.1f}", "px"
                )
                self.add_measurement(
                    "Differenza Aree Sopraccigli",
                    f"{abs(left_stats['area'] - right_stats['area']):.1f}",
                    "px²",
                )

                # Mostra messaggio di successo
                message = f"""Rilevamento completato con successo!
                
Puntini rilevati: {results['detection_results']['total_dots']}
• Sopracciglio sinistro: {len(results['groups']['Sx'])} punti
• Sopracciglio destro: {len(results['groups']['Dx'])} punti

Aree calcolate:
• Sinistra: {left_stats['area']:.1f} px²
• Destra: {right_stats['area']:.1f} px²
• Differenza: {abs(left_stats['area'] - right_stats['area']):.1f} px²"""

                messagebox.showinfo("Rilevamento Puntini Verdi", message)
                self.status_bar.config(
                    text=f"Puntini verdi rilevati: {results['detection_results']['total_dots']}"
                )

            else:
                # Errore nel rilevamento
                error_msg = results.get("error", "Errore sconosciuto nel rilevamento")
                messagebox.showerror("Errore Rilevamento", error_msg)
                self.status_bar.config(text="Errore nel rilevamento puntini verdi")

                # Reset dei dati
                self.green_dots_results = None
                self.green_dots_overlay = None
                self.show_green_dots_overlay = False
                self.green_dots_var.set(False)

        except Exception as e:
            error_msg = f"Errore durante il rilevamento dei puntini verdi: {str(e)}"
            messagebox.showerror("Errore", error_msg)
            self.status_bar.config(text="Errore nel rilevamento puntini verdi")

            # Reset dei dati in caso di errore
            self.green_dots_results = None
            self.green_dots_overlay = None
            self.show_green_dots_overlay = False
            self.green_dots_var.set(False)

    def toggle_green_dots_overlay(self):
        """Attiva/disattiva la visualizzazione dell'overlay dei puntini verdi."""
        self.show_green_dots_overlay = self.green_dots_var.get()

        if self.show_green_dots_overlay and self.green_dots_overlay is None:
            messagebox.showwarning(
                "Attenzione",
                "Nessun overlay disponibile. Esegui prima il rilevamento dei puntini verdi.",
            )
            self.green_dots_var.set(False)
            self.show_green_dots_overlay = False
            return

        # Aggiorna la visualizzazione utilizzando il canvas unificato
        self.update_canvas_display()

        status = "attivato" if self.show_green_dots_overlay else "disattivato"
        self.status_bar.config(text=f"Overlay puntini verdi {status}")

    def canvas_to_image_coordinates(
        self, canvas_x: float, canvas_y: float
    ) -> Tuple[int, int]:
        """
        Converte le coordinate del canvas alle coordinate dell'immagine originale.

        Args:
            canvas_x, canvas_y: Coordinate nel canvas

        Returns:
            Tuple con le coordinate nell'immagine originale
        """
        if self.current_image is None or self.display_scale == 0:
            return int(canvas_x), int(canvas_y)

        # Converti coordinate canvas a coordinate immagine visualizzata
        display_x = canvas_x
        display_y = canvas_y

        # Converti coordinate immagine visualizzata a coordinate immagine originale
        original_x = int(display_x / self.display_scale)
        original_y = int(display_y / self.display_scale)

        # Assicurati che le coordinate siano nei limiti dell'immagine
        original_height, original_width = self.current_image.shape[:2]
        original_x = max(0, min(original_x, original_width - 1))
        original_y = max(0, min(original_y, original_height - 1))

        return original_x, original_y

    def image_to_canvas_coordinates(
        self, image_x: float, image_y: float
    ) -> Tuple[int, int]:
        """
        Converte le coordinate dell'immagine originale alle coordinate del canvas.

        Args:
            image_x, image_y: Coordinate nell'immagine originale

        Returns:
            Tuple con le coordinate nel canvas
        """
        if self.display_scale == 0:
            return int(image_x), int(image_y)

        canvas_x = int(image_x * self.display_scale)
        canvas_y = int(image_y * self.display_scale)

        return canvas_x, canvas_y

    def draw_measurement_overlays(self, image):
        """Disegna gli overlay delle misurazioni sull'immagine."""
        overlay_image = image.copy()

        for overlay in self.measurement_overlays:
            if overlay["type"] == "distance":
                self.draw_distance_overlay(overlay_image, overlay)
            elif overlay["type"] == "angle":
                self.draw_angle_overlay(overlay_image, overlay)
            elif overlay["type"] == "area":
                self.draw_area_overlay(overlay_image, overlay)

        return overlay_image

    def draw_distance_overlay(self, image, overlay):
        """Disegna overlay per misurazione di distanza."""
        point1 = overlay["points"][0]
        point2 = overlay["points"][1]

        # Linea principale
        cv2.line(image, point1, point2, (0, 255, 0), 3)

        # Cerchi sui punti
        cv2.circle(image, point1, 6, (0, 255, 0), -1)
        cv2.circle(image, point2, 6, (0, 255, 0), -1)

    def draw_angle_overlay(self, image, overlay):
        """Disegna overlay per misurazione di angolo."""
        points = overlay["points"]

        if len(points) >= 3:
            p1, p2, p3 = points[0], points[1], points[2]

            # Linee che formano l'angolo
            cv2.line(image, p1, p2, (255, 165, 0), 3)
            cv2.line(image, p2, p3, (255, 165, 0), 3)

            # Cerchi sui punti
            cv2.circle(image, p1, 6, (255, 165, 0), -1)
            cv2.circle(image, p2, 6, (255, 0, 0), -1)  # Vertice in rosso
            cv2.circle(image, p3, 6, (255, 165, 0), -1)

            # Arco per indicare l'angolo
            import math

            angle1 = math.atan2(p1[1] - p2[1], p1[0] - p2[0])
            angle2 = math.atan2(p3[1] - p2[1], p3[0] - p2[0])

            # Disegna un piccolo arco
            radius = 30
            start_angle = int(math.degrees(angle1))
            end_angle = int(math.degrees(angle2))
            cv2.ellipse(
                image, p2, (radius, radius), 0, start_angle, end_angle, (255, 165, 0), 2
            )

    def draw_area_overlay(self, image, overlay):
        """Disegna overlay per misurazione di area."""
        points = overlay["points"]

        # Supporta sia singole aree che aree multiple
        if isinstance(points[0][0], (list, tuple)) and len(points[0]) > 2:
            # Multiple aree (per sopraccigli e occhi)
            colors = overlay.get("colors", [(0, 255, 255), (255, 255, 0)])

            for i, area_points in enumerate(points):
                if len(area_points) >= 3:
                    # Crea un poligono con i punti
                    pts = np.array(area_points, np.int32)
                    pts = pts.reshape((-1, 1, 2))

                    color = colors[i] if i < len(colors) else (0, 255, 255)

                    # Overlay colorato trasparente
                    overlay_img = image.copy()
                    cv2.fillPoly(overlay_img, [pts], color)
                    cv2.addWeighted(image, 0.7, overlay_img, 0.3, 0, image)

                    # Contorno del poligono - CHIUSO (True = ultimo punto connesso al primo)
                    cv2.polylines(image, [pts], True, color, 2)

                    # Cerchi sui punti
                    for point in area_points:
                        cv2.circle(image, point, 4, color, -1)

        else:
            # Singola area (comportamento originale)
            if len(points) >= 3:
                # Crea un poligono con i punti
                pts = np.array(points, np.int32)
                pts = pts.reshape((-1, 1, 2))

                # Overlay colorato trasparente
                overlay_img = image.copy()
                cv2.fillPoly(overlay_img, [pts], (0, 255, 255))  # Giallo trasparente
                cv2.addWeighted(image, 0.7, overlay_img, 0.3, 0, image)

                # Contorno del poligono - CHIUSO (True = ultimo punto connesso al primo)
                cv2.polylines(image, [pts], True, (0, 200, 200), 3)

                # Cerchi sui punti
                for point in points:
                    cv2.circle(image, point, 6, (0, 200, 200), -1)

    def add_measurement_overlay(
        self,
        measurement_type,
        points,
        value,
        label=None,
        use_coordinates=False,
        coordinates=None,
    ):
        """Aggiunge un overlay di misurazione."""
        if use_coordinates and coordinates:
            # Usa le coordinate fornite direttamente
            overlay_points = [(int(p[0]), int(p[1])) for p in coordinates]
        else:
            # Converti gli indici dei landmark in coordinate
            overlay_points = []
            for point_idx in points:
                if isinstance(point_idx, int) and point_idx < len(
                    self.current_landmarks
                ):
                    landmark = self.current_landmarks[point_idx]
                    overlay_points.append((int(landmark[0]), int(landmark[1])))
                elif isinstance(point_idx, (list, tuple)) and len(point_idx) >= 2:
                    overlay_points.append((int(point_idx[0]), int(point_idx[1])))

        overlay = {
            "type": measurement_type,
            "points": overlay_points,
            "value": value,
            "label": label or measurement_type.title(),
        }
        self.measurement_overlays.append(overlay)

        # Aggiorna la visualizzazione se gli overlay sono attivi
        if self.show_measurement_overlays:
            self.update_canvas_display()

    def clear_measurement_overlays(self):
        """Pulisce tutti gli overlay delle misurazioni."""
        self.measurement_overlays.clear()
        # Reset stato preset overlays
        for key in self.preset_overlays:
            self.preset_overlays[key] = None
        # Reset testo pulsanti
        self.reset_preset_buttons()
        self.update_canvas_display()

    def reset_preset_buttons(self):
        """Resetta il testo dei pulsanti preset a 'Mostra'."""
        button_texts = {
            "face_width": "Mostra Larghezza Volto",
            "face_height": "Mostra Altezza Volto",
            "eye_distance": "Mostra Distanza Occhi",
            "nose_width": "Mostra Larghezza Naso",
            "mouth_width": "Mostra Larghezza Bocca",
            "eyebrow_areas": "Mostra Aree Sopraccigli",
            "eye_areas": "Mostra Aree Occhi",
        }
        for key, text in button_texts.items():
            if key in self.preset_buttons:
                self.preset_buttons[key].config(text=text)

    def toggle_measurement_overlays(self):
        """Attiva/disattiva la visualizzazione degli overlay."""
        self.show_measurement_overlays = self.overlay_var.get()
        self.update_canvas_display()

    # NOTA: I metodi canvas zoom e drag sono gestiti dal sistema unificato

    def find_closest_landmark(
        self, x: int, y: int, max_distance: int = 20
    ) -> Optional[int]:
        """
        Trova il landmark più vicino alle coordinate specificate.

        Args:
            x, y: Coordinate del click nell'immagine originale
            max_distance: Distanza massima per considerare un landmark (in pixel dell'immagine originale)

        Returns:
            Indice del landmark più vicino o None se nessuno trovato
        """
        if not self.current_landmarks:
            return None

        # Aggiusta la distanza massima in base al fattore di scala
        # Se l'immagine è ridimensionata, la soglia deve essere proporzionale
        adjusted_max_distance = max_distance
        if self.display_scale > 0 and self.display_scale != 1.0:
            adjusted_max_distance = max_distance / self.display_scale

        min_distance = float("inf")
        closest_idx = None

        for i, landmark in enumerate(self.current_landmarks):
            distance = ((landmark[0] - x) ** 2 + (landmark[1] - y) ** 2) ** 0.5
            if distance < min_distance and distance <= adjusted_max_distance:
                min_distance = distance
                closest_idx = i

        return closest_idx

    def add_landmark_selection(self, landmark_idx: int):
        """Aggiunge un landmark alla selezione."""
        if landmark_idx in self.selected_landmarks:
            # Se già selezionato, rimuovilo
            self.selected_landmarks.remove(landmark_idx)
            self.status_bar.config(text=f"Landmark {landmark_idx} deselezionato")
        else:
            # Limita il numero di landmark in base alla modalità
            max_landmarks = {"distance": 2, "angle": 3, "area": 4}
            max_count = max_landmarks.get(self.measurement_mode, 2)

            if len(self.selected_landmarks) >= max_count:
                # Rimuovi il primo se abbiamo raggiunto il limite
                removed = self.selected_landmarks.pop(0)
                self.status_bar.config(
                    text=f"Landmark {removed} rimosso, {landmark_idx} aggiunto"
                )
            else:
                self.status_bar.config(text=f"Landmark {landmark_idx} selezionato")

            self.selected_landmarks.append(landmark_idx)

    def change_selection_mode(self):
        """Cambia la modalità di selezione tra manuale e landmark."""
        mode = self.selection_mode_var.get()
        self.landmark_measurement_mode = mode == "landmark"

        # Pulisci le selezioni quando cambi modalità
        self.clear_selections()

        # Mostra/nascondi i pulsanti predefiniti
        if self.landmark_measurement_mode:
            self.predefined_frame.pack(fill=tk.X, pady=(10, 0))
            self.status_bar.config(
                text="Modalità Landmark: clicca sui punti landmark visualizzati"
            )
        else:
            self.predefined_frame.pack_forget()
            self.status_bar.config(
                text="Modalità Manuale: clicca liberamente sull'immagine"
            )

    def change_measurement_mode(self):
        """Cambia la modalità di misurazione."""
        self.measurement_mode = self.measure_var.get()
        self.clear_selections()
        self.status_bar.config(text=f"Modalità: {self.measurement_mode}")

    def clear_selections(self):
        """Pulisce le selezioni correnti."""
        self.selected_points.clear()
        self.selected_landmarks.clear()
        self.update_canvas_display()
        self.status_bar.config(text="Selezioni cancellate")

    def calculate_measurement(self):
        """Calcola la misurazione in base ai punti selezionati."""
        # Ottieni i punti dalla modalità corrente
        if self.landmark_measurement_mode:
            if not self.selected_landmarks:
                messagebox.showwarning("Attenzione", "Seleziona almeno un landmark")
                return
            # Converti indici landmark in coordinate
            points = []
            for landmark_idx in self.selected_landmarks:
                if landmark_idx < len(self.current_landmarks):
                    point = self.current_landmarks[landmark_idx]
                    points.append((int(point[0]), int(point[1])))
        else:
            if not self.selected_points:
                messagebox.showwarning("Attenzione", "Seleziona almeno un punto")
                return
            points = self.selected_points

        try:
            if self.measurement_mode == "distance":
                if len(points) >= 2:
                    result = self.measurement_tools.calculate_distance(
                        points[0], points[1]
                    )
                    mode_text = (
                        "Landmark" if self.landmark_measurement_mode else "Manuale"
                    )
                    self.add_measurement(
                        f"Distanza ({mode_text})", f"{result:.2f}", "px"
                    )

                    # Memorizza il risultato per eventuali overlay
                    self.measurement_result = f"{result:.2f}"

                    # Aggiungi overlay per misurazioni manuali
                    if not self.landmark_measurement_mode:
                        point_indices = list(range(len(points)))[:2]
                        self.add_measurement_overlay(
                            measurement_type="distance",
                            points=point_indices,
                            value=f"{result:.2f}",
                            label=f"Distanza {mode_text}",
                            use_coordinates=True,
                            coordinates=points[:2],
                        )
                else:
                    messagebox.showwarning(
                        "Attenzione", "Seleziona 2 punti per la distanza"
                    )

            elif self.measurement_mode == "angle":
                if len(points) >= 3:
                    result = self.measurement_tools.calculate_angle(
                        points[0], points[1], points[2]
                    )
                    mode_text = (
                        "Landmark" if self.landmark_measurement_mode else "Manuale"
                    )
                    self.add_measurement(f"Angolo ({mode_text})", f"{result:.2f}", "°")

                    # Memorizza il risultato per eventuali overlay
                    self.measurement_result = f"{result:.2f}"

                    # Aggiungi overlay per misurazioni manuali
                    if not self.landmark_measurement_mode:
                        point_indices = list(range(len(points)))[:3]
                        self.add_measurement_overlay(
                            measurement_type="angle",
                            points=point_indices,
                            value=f"{result:.2f}",
                            label=f"Angolo {mode_text}",
                            use_coordinates=True,
                            coordinates=points[:3],
                        )
                else:
                    messagebox.showwarning(
                        "Attenzione", "Seleziona 3 punti per l'angolo"
                    )

            elif self.measurement_mode == "area":
                if len(points) >= 3:
                    result = self.measurement_tools.calculate_polygon_area(points)
                    mode_text = (
                        "Landmark" if self.landmark_measurement_mode else "Manuale"
                    )
                    self.add_measurement(f"Area ({mode_text})", f"{result:.2f}", "px²")

                    # Memorizza il risultato per eventuali overlay
                    self.measurement_result = f"{result:.2f}"

                    # Aggiungi overlay per tutte le misurazioni di area
                    point_indices = list(range(len(points)))
                    self.add_measurement_overlay(
                        measurement_type="area",
                        points=point_indices,
                        value=f"{result:.2f}",
                        label=f"Area {mode_text}",
                        use_coordinates=True,
                        coordinates=points,
                    )
                else:
                    messagebox.showwarning(
                        "Attenzione", "Seleziona almeno 3 punti per l'area"
                    )

        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel calcolo: {e}")

    # Metodi toggle per misurazioni predefinite
    def toggle_face_width(self):
        """Toggle per overlay larghezza volto."""
        if self.preset_overlays["face_width"] is None:
            # Mostra: esegui misurazione e crea overlay
            self.measure_face_width()
            if self.preset_buttons.get("face_width"):
                self.preset_buttons["face_width"].config(
                    text="Nascondi Larghezza Volto"
                )
        else:
            # Nascondi: rimuovi overlay
            self.remove_preset_overlay("face_width")
            if self.preset_buttons.get("face_width"):
                self.preset_buttons["face_width"].config(text="Mostra Larghezza Volto")

    def toggle_face_height(self):
        """Toggle per overlay altezza volto."""
        if self.preset_overlays["face_height"] is None:
            self.measure_face_height()
            if self.preset_buttons.get("face_height"):
                self.preset_buttons["face_height"].config(text="Nascondi Altezza Volto")
        else:
            self.remove_preset_overlay("face_height")
            if self.preset_buttons.get("face_height"):
                self.preset_buttons["face_height"].config(text="Mostra Altezza Volto")

    def toggle_eye_distance(self):
        """Toggle per overlay distanza occhi."""
        if self.preset_overlays["eye_distance"] is None:
            self.measure_eye_distance()
            if self.preset_buttons.get("eye_distance"):
                self.preset_buttons["eye_distance"].config(
                    text="Nascondi Distanza Occhi"
                )
        else:
            self.remove_preset_overlay("eye_distance")
            if self.preset_buttons.get("eye_distance"):
                self.preset_buttons["eye_distance"].config(text="Mostra Distanza Occhi")

    def toggle_nose_width(self):
        """Toggle per overlay larghezza naso."""
        if self.preset_overlays["nose_width"] is None:
            self.measure_nose_width()
            if self.preset_buttons.get("nose_width"):
                self.preset_buttons["nose_width"].config(text="Nascondi Larghezza Naso")
        else:
            self.remove_preset_overlay("nose_width")
            if self.preset_buttons.get("nose_width"):
                self.preset_buttons["nose_width"].config(text="Mostra Larghezza Naso")

    def toggle_mouth_width(self):
        """Toggle per overlay larghezza bocca."""
        if self.preset_overlays["mouth_width"] is None:
            self.measure_mouth_width()
            if self.preset_buttons.get("mouth_width"):
                self.preset_buttons["mouth_width"].config(
                    text="Nascondi Larghezza Bocca"
                )
        else:
            self.remove_preset_overlay("mouth_width")
            if self.preset_buttons.get("mouth_width"):
                self.preset_buttons["mouth_width"].config(text="Mostra Larghezza Bocca")

    def toggle_eyebrow_areas(self):
        """Toggle per overlay aree sopraccigli."""
        if self.preset_overlays["eyebrow_areas"] is None:
            self.measure_eyebrow_areas()
            if self.preset_buttons.get("eyebrow_areas"):
                self.preset_buttons["eyebrow_areas"].config(
                    text="Nascondi Aree Sopraccigli"
                )
        else:
            self.remove_preset_overlay("eyebrow_areas")
            if self.preset_buttons.get("eyebrow_areas"):
                self.preset_buttons["eyebrow_areas"].config(
                    text="Mostra Aree Sopraccigli"
                )

    def toggle_eye_areas(self):
        """Toggle per overlay aree occhi."""
        if self.preset_overlays["eye_areas"] is None:
            self.measure_eye_areas()
            if self.preset_buttons.get("eye_areas"):
                self.preset_buttons["eye_areas"].config(text="Nascondi Aree Occhi")
        else:
            self.remove_preset_overlay("eye_areas")
            if self.preset_buttons.get("eye_areas"):
                self.preset_buttons["eye_areas"].config(text="Mostra Aree Occhi")

    def remove_preset_overlay(self, preset_key):
        """Rimuove un overlay di preset specifico."""
        if self.preset_overlays[preset_key] is not None:
            # Trova e rimuovi l'overlay dalla lista
            overlay_to_remove = self.preset_overlays[preset_key]
            if overlay_to_remove in self.measurement_overlays:
                self.measurement_overlays.remove(overlay_to_remove)
            self.preset_overlays[preset_key] = None
            self.update_canvas_display()

    # Metodi per misurazioni predefinite
    def measure_face_width(self):
        """Misura automatica della larghezza del volto."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        # Usa landmark predefiniti per la larghezza del volto
        left_face = 234  # Lato sinistro del volto
        right_face = 454  # Lato destro del volto

        if len(self.current_landmarks) > max(left_face, right_face):
            self.selected_landmarks = [left_face, right_face]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_measurement()

            # Aggiungi overlay per la misurazione
            if self.measurement_result:
                overlay = {
                    "type": "distance",
                    "points": [
                        (
                            int(self.current_landmarks[left_face][0]),
                            int(self.current_landmarks[left_face][1]),
                        ),
                        (
                            int(self.current_landmarks[right_face][0]),
                            int(self.current_landmarks[right_face][1]),
                        ),
                    ],
                    "value": self.measurement_result,
                    "label": "Larghezza Volto",
                }
                self.measurement_overlays.append(overlay)
                self.preset_overlays["face_width"] = overlay
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Larghezza volto misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_face_height(self):
        """Misura automatica dell'altezza del volto."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        # Usa landmark predefiniti per l'altezza del volto
        top_face = 10  # Parte superiore della fronte
        bottom_face = 175  # Parte inferiore del mento

        if len(self.current_landmarks) > max(top_face, bottom_face):
            self.selected_landmarks = [top_face, bottom_face]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_measurement()

            # Aggiungi overlay per la misurazione
            if self.measurement_result:
                overlay = {
                    "type": "distance",
                    "points": [
                        (
                            int(self.current_landmarks[top_face][0]),
                            int(self.current_landmarks[top_face][1]),
                        ),
                        (
                            int(self.current_landmarks[bottom_face][0]),
                            int(self.current_landmarks[bottom_face][1]),
                        ),
                    ],
                    "value": self.measurement_result,
                    "label": "Altezza Volto",
                }
                self.measurement_overlays.append(overlay)
                self.preset_overlays["face_height"] = overlay
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Altezza volto misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_eye_distance(self):
        """Misura automatica della distanza tra gli occhi."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        # Usa landmark predefiniti per la distanza tra gli occhi
        left_eye_outer = 33  # Angolo esterno occhio sinistro
        right_eye_outer = 362  # Angolo esterno occhio destro

        if len(self.current_landmarks) > max(left_eye_outer, right_eye_outer):
            self.selected_landmarks = [left_eye_outer, right_eye_outer]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_measurement()

            # Aggiungi overlay per la misurazione
            if self.measurement_result:
                overlay = {
                    "type": "distance",
                    "points": [
                        (
                            int(self.current_landmarks[left_eye_outer][0]),
                            int(self.current_landmarks[left_eye_outer][1]),
                        ),
                        (
                            int(self.current_landmarks[right_eye_outer][0]),
                            int(self.current_landmarks[right_eye_outer][1]),
                        ),
                    ],
                    "value": self.measurement_result,
                    "label": "Distanza Occhi",
                }
                self.measurement_overlays.append(overlay)
                self.preset_overlays["eye_distance"] = overlay
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Distanza occhi misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_nose_width(self):
        """Misura automatica della larghezza del naso."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        # Usa landmark predefiniti per la larghezza del naso
        nose_left = 131  # Lato sinistro del naso
        nose_right = 360  # Lato destro del naso

        if len(self.current_landmarks) > max(nose_left, nose_right):
            self.selected_landmarks = [nose_left, nose_right]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_measurement()

            # Aggiungi overlay per la misurazione
            if self.measurement_result:
                overlay = {
                    "type": "distance",
                    "points": [
                        (
                            int(self.current_landmarks[nose_left][0]),
                            int(self.current_landmarks[nose_left][1]),
                        ),
                        (
                            int(self.current_landmarks[nose_right][0]),
                            int(self.current_landmarks[nose_right][1]),
                        ),
                    ],
                    "value": self.measurement_result,
                    "label": "Larghezza Naso",
                }
                self.measurement_overlays.append(overlay)
                self.preset_overlays["nose_width"] = overlay
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Larghezza naso misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_mouth_width(self):
        """Misura automatica della larghezza della bocca."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        # Usa landmark predefiniti per la larghezza della bocca
        mouth_left = 61  # Angolo sinistro della bocca
        mouth_right = 291  # Angolo destro della bocca

        if len(self.current_landmarks) > max(mouth_left, mouth_right):
            self.selected_landmarks = [mouth_left, mouth_right]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_measurement()

            # Aggiungi overlay per la misurazione
            if self.measurement_result:
                overlay = {
                    "type": "distance",
                    "points": [
                        (
                            int(self.current_landmarks[mouth_left][0]),
                            int(self.current_landmarks[mouth_left][1]),
                        ),
                        (
                            int(self.current_landmarks[mouth_right][0]),
                            int(self.current_landmarks[mouth_right][1]),
                        ),
                    ],
                    "value": self.measurement_result,
                    "label": "Larghezza Bocca",
                }
                self.measurement_overlays.append(overlay)
                self.preset_overlays["mouth_width"] = overlay
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Larghezza bocca misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_eyebrow_areas(self):
        """Misura automatica delle aree dei sopraccigli."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        # Calcola le aree dei sopraccigli
        areas = self.measurement_tools.calculate_eyebrow_areas(self.current_landmarks)

        if areas:
            # Aggiungi le misurazioni alla tabella
            self.add_measurement(
                "Area Sopracciglio Sinistro", f"{areas['left_eyebrow_area']:.1f}", "px²"
            )
            self.add_measurement(
                "Area Sopracciglio Destro", f"{areas['right_eyebrow_area']:.1f}", "px²"
            )
            self.add_measurement(
                "Differenza Aree Sopraccigli",
                f"{areas['eyebrow_area_difference']:.1f}",
                "px²",
            )
            self.add_measurement("Sopracciglio Più Grande", areas["larger_eyebrow"], "")

            # Crea overlay per visualizzazione usando i landmarks UFFICIALI MediaPipe
            if len(self.current_landmarks) >= 468:
                # Landmarks per sopracciglio SINISTRO
                # Ordinati secondo NUOVA SEQUENZA PERIMETRALE PERSONALIZZATA
                # RIMOSSO landmark 276 e DUPLICATO 285
                left_eyebrow_indices = [
                    334,
                    296,
                    336,
                    285,
                    295,
                    282,
                    283,
                    300,
                    293,
                    334,  # Chiude il perimetro
                ]
                left_eyebrow_points = [
                    (
                        int(self.current_landmarks[idx][0]),
                        int(self.current_landmarks[idx][1]),
                    )
                    for idx in left_eyebrow_indices
                ]

                # Landmarks per sopracciglio DESTRO
                # Ordinati secondo NUOVA SEQUENZA PERIMETRALE PERSONALIZZATA
                # RIMOSSO landmark 46
                right_eyebrow_indices = [53, 52, 65, 55, 107, 66, 105, 63, 70, 53]
                right_eyebrow_points = [
                    (
                        int(self.current_landmarks[idx][0]),
                        int(self.current_landmarks[idx][1]),
                    )
                    for idx in right_eyebrow_indices
                ]

                overlay = {
                    "type": "area",
                    "points": [left_eyebrow_points, right_eyebrow_points],
                    "value": f"S:{areas['left_eyebrow_area']:.1f} D:{areas['right_eyebrow_area']:.1f}",
                    "label": "Aree Sopraccigli",
                    "colors": [
                        (0, 255, 255),
                        (255, 255, 0),
                    ],  # Giallo per sinistro, ciano per destro
                }
                self.measurement_overlays.append(overlay)
                self.preset_overlays["eyebrow_areas"] = overlay
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Aree sopraccigli misurate automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_eye_areas(self):
        """Misura automatica delle aree degli occhi."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        # Calcola le aree degli occhi
        areas = self.measurement_tools.calculate_eye_areas(self.current_landmarks)

        if areas:
            # Aggiungi le misurazioni alla tabella
            self.add_measurement(
                "Area Occhio Sinistro", f"{areas['left_eye_area']:.1f}", "px²"
            )
            self.add_measurement(
                "Area Occhio Destro", f"{areas['right_eye_area']:.1f}", "px²"
            )
            self.add_measurement(
                "Differenza Aree Occhi", f"{areas['eye_area_difference']:.1f}", "px²"
            )
            self.add_measurement("Occhio Più Grande", areas["larger_eye"], "")

            # Crea overlay per visualizzazione usando gli stessi landmarks del calcolo
            if len(self.current_landmarks) >= 468:
                # Landmarks per occhio sinistro (contorno completo degli occhi)
                left_eye_indices = [
                    33,
                    7,
                    163,
                    144,
                    145,
                    153,
                    154,
                    155,
                    133,
                    173,
                    157,
                    158,
                    159,
                    160,
                    161,
                    246,
                ]
                left_eye_points = [
                    (
                        int(self.current_landmarks[idx][0]),
                        int(self.current_landmarks[idx][1]),
                    )
                    for idx in left_eye_indices
                ]

                # Landmarks per occhio destro (contorno completo degli occhi)
                right_eye_indices = [
                    362,
                    398,
                    384,
                    385,
                    386,
                    387,
                    388,
                    466,
                    263,
                    249,
                    390,
                    373,
                    374,
                    380,
                    381,
                    382,
                ]
                right_eye_points = [
                    (
                        int(self.current_landmarks[idx][0]),
                        int(self.current_landmarks[idx][1]),
                    )
                    for idx in right_eye_indices
                ]

                overlay = {
                    "type": "area",
                    "points": [left_eye_points, right_eye_points],
                    "value": f"S:{areas['left_eye_area']:.1f} D:{areas['right_eye_area']:.1f}",
                    "label": "Aree Occhi",
                    "colors": [
                        (255, 0, 255),
                        (0, 255, 0),
                    ],  # Magenta per sinistro, verde per destro
                }
                self.measurement_overlays.append(overlay)
                self.preset_overlays["eye_areas"] = overlay
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Aree occhi misurate automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_facial_symmetry(self):
        """Calcola automaticamente l'indice di simmetria facciale."""
        if not self.current_landmarks or not self.landmark_measurement_mode:
            messagebox.showwarning(
                "Attenzione",
                "Attiva modalità Landmark e assicurati che i landmark siano rilevati",
            )
            return

        try:
            symmetry_score = self.measurement_tools.calculate_facial_symmetry(
                self.current_landmarks
            )
            self.add_measurement("Simmetria Facciale", f"{symmetry_score:.3f}", "0-1")
            self.status_bar.config(
                text=f"Simmetria facciale calcolata: {symmetry_score:.3f}"
            )
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel calcolo simmetria: {e}")

    def add_measurement(self, measurement_type: str, value: str, unit: str):
        """Aggiunge una misurazione alla lista (in cima per vedere l'ultima)."""
        self.measurements_tree.insert(
            "", 0, values=(measurement_type, value, unit)
        )  # 0 = inserisce in cima
        self.status_bar.config(
            text=f"Misurazione aggiunta: {measurement_type} = {value} {unit}"
        )

    def toggle_all_landmarks(self):
        """Attiva/disattiva la visualizzazione di tutti i landmark."""
        self.show_all_landmarks = self.all_landmarks_var.get()
        self.update_canvas_display()

    def toggle_measurements(self):
        """Attiva/disattiva la visualizzazione delle misurazioni."""
        self.show_measurements = not self.show_measurements
        self.update_canvas_display()

    def save_image(self):
        """Salva l'immagine corrente con annotazioni."""
        if self.current_image is None:
            messagebox.showwarning("Attenzione", "Nessuna immagine da salvare")
            return

        file_path = filedialog.asksaveasfilename(
            title="Salva Immagine",
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("Tutti i file", "*.*")],
        )

        if file_path:
            try:
                # Crea immagine con annotazioni
                annotated_image = self.current_image.copy()

                if self.show_all_landmarks and self.current_landmarks:
                    annotated_image = self.face_detector.draw_landmarks(
                        annotated_image,
                        self.current_landmarks,
                        draw_all=True,
                        key_only=False,
                    )

                # Disegna l'asse di simmetria se abilitato
                if self.show_axis_var.get() and self.current_landmarks:
                    annotated_image = self.face_detector.draw_symmetry_axis(
                        annotated_image, self.current_landmarks
                    )

                cv2.imwrite(file_path, annotated_image)
                self.status_bar.config(text=f"Immagine salvata: {file_path}")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nel salvataggio: {e}")

    def export_measurements(self):
        """Esporta le misurazioni in un file CSV."""
        if not self.measurements_tree.get_children():
            messagebox.showwarning("Attenzione", "Nessuna misurazione da esportare")
            return

        file_path = filedialog.asksaveasfilename(
            title="Esporta Misurazioni",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tutti i file", "*.*")],
        )

        if file_path:
            try:
                with open(file_path, "w", newline="", encoding="utf-8") as file:
                    file.write("Tipo,Valore,Unità\\n")
                    for item in self.measurements_tree.get_children():
                        values = self.measurements_tree.item(item)["values"]
                        file.write(f"{values[0]},{values[1]},{values[2]}\\n")

                self.status_bar.config(text=f"Misurazioni esportate: {file_path}")
            except Exception as e:
                messagebox.showerror("Errore", f"Errore nell'esportazione: {e}")

    def create_preview_window(self, title="Anteprima Video - Analisi in corso"):
        """Crea la finestra di anteprima video."""
        if self.preview_window is not None:
            return  # Finestra già esistente

        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title(title)
        self.preview_window.geometry("660x500")
        self.preview_window.resizable(False, False)

        # Posiziona la finestra accanto alla finestra principale
        x = self.root.winfo_x() + self.root.winfo_width() + 10
        y = self.root.winfo_y()
        self.preview_window.geometry(f"660x500+{x}+{y}")

        # Frame principale
        main_frame = ttk.Frame(self.preview_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Titolo
        title_label = ttk.Label(
            main_frame, text="Anteprima Video Live", font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Label per il video
        self.preview_label = tk.Label(
            main_frame,
            bg="black",
            text="Caricamento anteprima...",
            fg="white",
            font=("Arial", 10),
        )
        self.preview_label.pack(expand=True, fill=tk.BOTH)

        # Frame info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        # Info in tempo reale
        self.preview_info = ttk.Label(
            info_frame, text="In attesa del video...", font=("Arial", 9)
        )
        self.preview_info.pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(info_frame, text="💡 Suggerimenti:", font=("Arial", 9, "bold")).pack(
            anchor=tk.W
        )
        ttk.Label(
            info_frame,
            text="• Mantieni il volto frontale alla camera",
            font=("Arial", 8),
        ).pack(anchor=tk.W, padx=(10, 0))
        ttk.Label(
            info_frame,
            text="• Assicurati di avere buona illuminazione",
            font=("Arial", 8),
        ).pack(anchor=tk.W, padx=(10, 0))
        ttk.Label(
            info_frame,
            text="• Chiudi la finestra per fermare l'anteprima",
            font=("Arial", 8),
        ).pack(anchor=tk.W, padx=(10, 0))
        ttk.Label(
            info_frame,
            text="• L'analisi si ferma automaticamente dopo 30 secondi",
            font=("Arial", 8),
            foreground="orange",
        ).pack(anchor=tk.W, padx=(10, 0))

        # Pulsante per salvare frame corrente
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(
            button_frame,
            text="📸 Cattura Frame Corrente",
            command=self.capture_current_frame,
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            button_frame, text="❌ Chiudi Anteprima", command=self.close_preview_window
        ).pack(side=tk.LEFT)

        # Gestione chiusura finestra
        self.preview_window.protocol("WM_DELETE_WINDOW", self.close_preview_window)

    def close_preview_window(self):
        """Chiude la finestra di anteprima video."""
        if self.preview_window is not None:
            try:
                self.preview_window.destroy()
            except:
                pass
            self.preview_window = None
            self.preview_label = None
            self.preview_info = None

    def toggle_video_preview(self):
        """Attiva/disattiva l'anteprima video."""
        if self.preview_enabled.get():
            if self.video_analyzer.is_capturing:
                self.create_preview_window()
        else:
            self.close_preview_window()

    def capture_current_frame(self):
        """Cattura il frame corrente dal video e lo carica nel canvas principale."""
        if self.video_analyzer.current_frame is not None:
            # Rileva landmarks nel frame corrente
            current_frame = self.video_analyzer.current_frame.copy()
            landmarks = self.face_detector.detect_face_landmarks(current_frame)

            # Carica nel canvas principale
            self.set_current_image(current_frame, landmarks, auto_resize=False)

            # Mostra messaggio di conferma
            if landmarks:
                score = self.face_detector.calculate_frontal_score(landmarks)
                self.status_bar.config(text=f"Frame catturato! Score: {score:.2f}")
                messagebox.showinfo(
                    "Cattura Completata",
                    f"Frame catturato con successo!\nScore frontalità: {score:.2f}",
                )
            else:
                self.status_bar.config(text="Frame catturato (nessun volto rilevato)")
                messagebox.showwarning(
                    "Cattura Completata", "Frame catturato, ma nessun volto rilevato."
                )
        else:
            messagebox.showwarning("Errore", "Nessun frame disponibile per la cattura.")

    def save_frame_to_buffer(self, frame_number: int, frame: np.ndarray, landmarks):
        """Salva un frame nel buffer per il doppio click."""
        try:
            # Aggiungi al buffer
            self.frame_buffer[frame_number] = (frame, landmarks)

            # Mantieni solo i frame più recenti per evitare uso eccessivo della memoria
            if len(self.frame_buffer) > self.max_buffer_size:
                # Rimuovi il frame più vecchio (numero più basso)
                oldest_frame = min(self.frame_buffer.keys())
                del self.frame_buffer[oldest_frame]

        except Exception as e:
            print(f"Errore nel salvare frame nel buffer: {e}")

    def _save_layout_only(self):
        """Salva solo la configurazione del layout senza chiudere l'applicazione."""
        try:
            print("\n💾 Salvataggio layout in corso...")

            # Ottieni posizioni PanedWindow usando sashpos SENZA validazione per rispettare le scelte dell'utente
            main_pos = (
                self.main_horizontal_paned.sashpos(0)
                if self.main_horizontal_paned.panes()
                else layout_manager.config.main_paned_position
            )

            # NUOVO: Ottieni posizione divisore canvas | colonna destra
            right_column_pos = None
            if self.main_horizontal_paned.panes():
                panes_count = len(self.main_horizontal_paned.panes())
                if panes_count >= 3:
                    right_column_pos = self.main_horizontal_paned.sashpos(1)
                else:
                    right_column_pos = layout_manager.config.right_column_position

            # Divisore INTERNO layers/anteprima
            layers_preview_pos = (
                self.right_sidebar_paned.sashpos(0)
                if self.right_sidebar_paned.panes()
                else layout_manager.config.layers_preview_divider_position
            )

            vertical_pos = (
                self.main_vertical_paned.sashpos(0)
                if self.main_vertical_paned.panes()
                else layout_manager.config.vertical_paned_position
            )

            # Salva le dimensioni aggiuntive per la colonna destra
            try:
                # Dimensioni del pannello destro
                if hasattr(self, "right_sidebar_paned"):
                    right_sidebar_width = self.right_sidebar_paned.winfo_width()
                    layout_manager.config.right_sidebar_width = right_sidebar_width
                    print(f"📐 Right sidebar width: {right_sidebar_width}")

                # Dimensioni specifiche dei frame interni
                if hasattr(self, "layers_tree"):
                    layers_frame_height = self.layers_tree.winfo_height()
                    layout_manager.config.layers_frame_height = layers_frame_height
                    print(f"📐 Layers frame height: {layers_frame_height}")

            except Exception as e:
                print(f"⚠️ Errore lettura dimensioni colonna destra: {e}")

            print(f"📏 Posizioni pannelli rilevate REALI dell'utente:")
            print(f"   • Main paned (controlli|canvas): {main_pos}")
            print(f"   • Right column (canvas|destra): {right_column_pos}")
            print(f"   • Layers/Anteprima divisore: {layers_preview_pos}")
            print(f"   • Vertical paned: {vertical_pos}")

            # Aggiorna configurazione nell'istanza layout_manager SENZA correzioni
            layout_manager.config.main_paned_position = main_pos
            if right_column_pos is not None:
                layout_manager.config.right_column_position = right_column_pos
            layout_manager.config.layers_preview_divider_position = layers_preview_pos
            layout_manager.config.vertical_paned_position = vertical_pos

            # Salva immediatamente e verifica
            layout_manager.save_config()

            # Verifica salvataggio
            status = layout_manager.get_config_status()
            print(
                f"📊 Status post-salvataggio: File={status['file_exists']}, Size={status['file_size']}B"
            )

            print(f"✅ Layout pannelli dell'utente salvato con successo")

        except Exception as e:
            print(f"❌ Errore nel salvataggio layout pannelli: {e}")
            import traceback

            traceback.print_exc()

    def _check_and_load_test_image_for_pan(self):
        """Carica immagine di test solo se non c'è già un'immagine caricata."""
        if self.current_image is None:
            self._load_test_image_for_pan()
        else:
            print("📷 Immagine già presente, non carico immagine di test")

    def _load_test_image_for_pan(self):
        """Carica un'immagine di test per rendere il PAN visibile e funzionale."""
        try:
            from PIL import Image, ImageDraw
            import numpy as np

            # Crea un'immagine di test con griglia
            test_img = Image.new("RGB", (800, 600), "lightgray")
            draw = ImageDraw.Draw(test_img)

            # Disegna griglia per visualizzare il PAN
            for x in range(0, 800, 100):
                draw.line([(x, 0), (x, 600)], fill="blue", width=2)
                draw.text((x + 5, 5), str(x), fill="darkblue")

            for y in range(0, 600, 100):
                draw.line([(0, y), (800, y)], fill="red", width=2)
                draw.text((5, y + 5), str(y), fill="darkred")

            # Aggiungi testo di istruzioni
            draw.text((50, 300), "IMMAGINE DI TEST - PROVA IL PAN!", fill="black")
            draw.text(
                (50, 320), "1. Clicca su PAN (✋) nella toolbar in alto", fill="black"
            )
            draw.text(
                (50, 340),
                "2. Trascina con il mouse per muovere l'immagine",
                fill="black",
            )
            draw.text(
                (50, 360), "3. Oppure usa Ctrl+click o pulsante centrale", fill="black"
            )

            # Imposta l'immagine nel canvas unificato
            self.current_image = cv2.cvtColor(np.array(test_img), cv2.COLOR_RGB2BGR)
            self.display_image(self.current_image)

            print("🖼️ Immagine di test caricata per testare PAN")
            print("📝 ISTRUZIONI PAN:")
            print("   1. Clicca sul pulsante PAN (✋) nella toolbar")
            print("   2. Trascina con il mouse per muovere l'immagine")
            print("   3. Alternativamente: Ctrl+click o pulsante centrale mouse")

        except Exception as e:
            print(f"⚠️ Errore caricamento immagine test: {e}")

    def on_closing_with_layout_save(self):
        """Salva la configurazione del layout prima di chiudere l'applicazione."""
        try:
            # Ottieni dimensioni e posizione finestra
            geometry_str = self.root.winfo_geometry()
            # Parse geometry string: "widthxheight+x+y"
            size_pos = geometry_str.split("+")
            size_part = size_pos[0]
            width, height = map(int, size_part.split("x"))
            x = int(size_pos[1]) if len(size_pos) > 1 else 100
            y = int(size_pos[2]) if len(size_pos) > 2 else 100

            # Ottieni posizioni PanedWindow usando sashpos con validazione
            main_pos = (
                self.main_horizontal_paned.sashpos(0)
                if self.main_horizontal_paned.panes()
                else 400
            )
            # Non salvare valori troppo piccoli che renderebbero invisibili i pannelli
            main_pos = max(main_pos, 300)

            sidebar_pos = (
                self.right_sidebar_paned.sashpos(0)
                if self.right_sidebar_paned.panes()
                else 250
            )
            sidebar_pos = max(sidebar_pos, 200)

            vertical_pos = (
                self.main_vertical_paned.sashpos(0)
                if self.main_vertical_paned.panes()
                else 600
            )
            vertical_pos = max(vertical_pos, 400)

            # Aggiorna configurazione nell'istanza layout_manager
            layout_manager.config.window_width = width
            layout_manager.config.window_height = height
            layout_manager.config.window_x = x
            layout_manager.config.window_y = y
            layout_manager.config.main_paned_position = main_pos
            layout_manager.config.sidebar_paned_position = sidebar_pos
            layout_manager.config.vertical_paned_position = vertical_pos
            layout_manager.save_config()

            print(
                f"✅ Layout salvato: finestra={width}x{height}+{x}+{y}, main={main_pos}, sidebar={sidebar_pos}, vertical={vertical_pos}"
            )

        except Exception as e:
            print(f"❌ Errore nel salvataggio layout: {e}")
        finally:
            # Chiudi l'applicazione
            self.root.destroy()

    def _simple_restore_layout(self):
        """Ripristina semplicemente il layout salvato dall'utente senza correzioni."""
        try:
            config = layout_manager.config
            print(
                f"🔄 Ripristino layout utente: main={config.main_paned_position}, right_column={config.right_column_position}, vertical={config.vertical_paned_position}, layers_preview={config.layers_preview_divider_position}"
            )

            # Ripristina le posizioni ESATTE salvate dall'utente
            if self.main_horizontal_paned.panes() and config.main_paned_position > 0:
                # SASHPOS(0): Divisore controlli | canvas
                self.main_horizontal_paned.sashpos(0, config.main_paned_position)
                print(f"📍 Main paned (controlli|canvas): {config.main_paned_position}")

                # SASHPOS(1): Divisore canvas | colonna destra
                panes_count = len(self.main_horizontal_paned.panes())
                if panes_count >= 3 and config.right_column_position > 0:
                    self.main_horizontal_paned.sashpos(1, config.right_column_position)
                    print(
                        f"📍 Right column (canvas|destra): {config.right_column_position}"
                    )

            if self.main_vertical_paned.panes() and config.vertical_paned_position > 0:
                self.main_vertical_paned.sashpos(0, config.vertical_paned_position)
                print(f"📍 Vertical paned: {config.vertical_paned_position}")

            # Ripristina posizione divisore layers/anteprima nella colonna destra
            if (
                self.right_sidebar_paned.panes()
                and config.layers_preview_divider_position > 0
            ):
                self.right_sidebar_paned.sashpos(
                    0, config.layers_preview_divider_position
                )
                print(
                    f"📍 Layers/Anteprima divisore: {config.layers_preview_divider_position}"
                )

            print("✅ Layout utente ripristinato")

        except Exception as e:
            print(f"❌ Errore ripristino layout: {e}")

    def _final_canvas_refresh(self):
        """Refresh finale del canvas unificato."""
        try:
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.update()
                self.canvas.update_idletasks()
                print("🔄 Canvas unificato refreshed")
        except Exception as e:
            print(f"❌ Errore nel refresh canvas: {e}")

    def _on_vertical_paned_resize(self, event):
        """Callback per quando viene ridimensionato il pannello verticale."""
        try:
            if self.main_vertical_paned.panes():
                position = self.main_vertical_paned.sashpos(0)
                print(f"📏 VERTICAL PANED RESIZE: posizione {position}")
                layout_manager.config.vertical_paned_position = position
                layout_manager.save_config()
        except Exception as e:
            print(f"❌ Errore aggiornamento vertical paned: {e}")

    def _on_main_paned_resize(self, event):
        """Callback per quando viene ridimensionato il pannello principale."""
        try:
            if self.main_horizontal_paned.panes():
                # SASHPOS(0): Divisore controlli | canvas
                left_position = self.main_horizontal_paned.sashpos(0)
                print(
                    f"📏 MAIN PANED RESIZE (controlli|canvas): posizione {left_position}"
                )
                layout_manager.config.main_paned_position = left_position

                # SASHPOS(1): Divisore canvas | colonna destra (SE ESISTE)
                panes_count = len(self.main_horizontal_paned.panes())
                if (
                    panes_count >= 3
                ):  # Abbiamo 3 pannelli: controlli, canvas, colonna destra
                    right_position = self.main_horizontal_paned.sashpos(1)
                    print(
                        f"📏 RIGHT COLUMN RESIZE (canvas|destra): posizione {right_position}"
                    )
                    layout_manager.config.right_column_position = right_position

                layout_manager.save_config()
        except Exception as e:
            print(f"❌ Errore aggiornamento main paned: {e}")
            import traceback

            traceback.print_exc()

    def _on_sidebar_paned_resize(self, event):
        """Callback per quando viene ridimensionato il pannello sidebar destro."""
        try:
            print(f"🔍 SIDEBAR RESIZE EVENT: {event}")
            print(f"🔍 Panes disponibili: {self.right_sidebar_paned.panes()}")

            if self.right_sidebar_paned.panes():
                position = self.right_sidebar_paned.sashpos(0)
                print(f"📏 SIDEBAR PANED RESIZE: posizione {position}")
                layout_manager.config.sidebar_paned_position = position
                layout_manager.save_config()
            else:
                print("⚠️ Nessun pane disponibile per sidebar_paned!")
        except Exception as e:
            print(f"❌ Errore aggiornamento sidebar paned: {e}")
            import traceback

            traceback.print_exc()

    def _on_vertical_paned_drag(self, event):
        """Callback durante il trascinamento del pannello verticale (senza salvataggio continuo)."""
        try:
            if self.main_vertical_paned.panes():
                position = self.main_vertical_paned.sashpos(0)
                print(f"📏 Vertical paned trascinato a: {position}")
        except Exception as e:
            print(f"❌ Errore drag vertical paned: {e}")

    def _on_main_paned_drag(self, event):
        """Callback durante il trascinamento del pannello principale (senza salvataggio continuo)."""
        try:
            if self.main_horizontal_paned.panes():
                # Traccia entrambi i divisori durante il drag
                left_position = self.main_horizontal_paned.sashpos(0)
                print(f"📏 Main paned (controlli|canvas) trascinato a: {left_position}")

                panes_count = len(self.main_horizontal_paned.panes())
                if panes_count >= 3:
                    right_position = self.main_horizontal_paned.sashpos(1)
                    print(
                        f"📏 Right column (canvas|destra) trascinato a: {right_position}"
                    )
        except Exception as e:
            print(f"❌ Errore drag main paned: {e}")

    def _on_sidebar_paned_drag(self, event):
        """Callback durante il trascinamento del pannello sidebar (senza salvataggio continuo)."""
        try:
            print(f"🔍 SIDEBAR DRAG EVENT: {event}")
            print(f"🔍 Panes disponibili: {self.right_sidebar_paned.panes()}")

            if self.right_sidebar_paned.panes():
                position = self.right_sidebar_paned.sashpos(0)
                print(f"📏 Sidebar paned trascinato a: {position}")
            else:
                print("⚠️ Nessun pane disponibile per sidebar_paned!")
        except Exception as e:
            print(f"❌ Errore drag sidebar paned: {e}")
            import traceback

            traceback.print_exc()

    def _on_sidebar_paned_configure(self, event):
        """Callback alternativo per eventi Configure sul sidebar paned."""
        try:
            print(f"🔄 SIDEBAR CONFIGURE EVENT: {event}")

            if self.right_sidebar_paned.panes():
                # Il right_sidebar_paned ha un SASH VERTICALE (sashpos(0)) che divide layers da anteprima
                layers_preview_position = self.right_sidebar_paned.sashpos(0)
                print(
                    f"📐 Divisore layers/anteprima - posizione: {layers_preview_position}"
                )

                # Salva posizione divisore layers/anteprima
                if hasattr(self, "_last_layers_preview_position"):
                    if (
                        abs(
                            layers_preview_position - self._last_layers_preview_position
                        )
                        > 5
                    ):
                        print(
                            f"📏 LAYERS/ANTEPRIMA POSIZIONE CAMBIATA: {self._last_layers_preview_position} → {layers_preview_position}"
                        )
                        layout_manager.config.layers_preview_divider_position = (
                            layers_preview_position
                        )
                        layout_manager.save_config()
                        self._last_layers_preview_position = layers_preview_position
                else:
                    self._last_layers_preview_position = layers_preview_position

            else:
                print("⚠️ Configure: Nessun pane disponibile per sidebar_paned!")
        except Exception as e:
            print(f"❌ Errore configure sidebar paned: {e}")
            import traceback

            traceback.print_exc()

    def on_closing(self):
        """Gestisce la chiusura dell'applicazione."""
        # Ferma l'analisi video se in corso
        if self.video_analyzer.is_capturing:
            self.video_analyzer.stop_analysis()

        # Chiudi finestra anteprima
        self.close_preview_window()

        # Rilascia risorse video
        self.video_analyzer.release()

        # Chiudi applicazione
        self.root.destroy()

    def on_debug_log(self, message: str, debug_info: dict):
        """Callback per ricevere debug logs dal video analyzer."""
        try:
            # Estrai i parametri necessari dal debug_info
            score_str = debug_info.get("score", "0.0").replace("°", "")
            score = float(score_str)

            # Estrai il tempo numerico dalla stringa timestamp
            timestamp_str = debug_info.get("timestamp", "0.0s")
            elapsed_time = float(timestamp_str.replace("s", ""))

            # Assicurati che l'aggiornamento avvenga nel thread principale
            self.root.after(
                0, lambda: self.add_debug_log(score, debug_info, elapsed_time)
            )
        except Exception as e:
            print(f"Errore nel debug log callback: {e}")

    # CALLBACK SCORING CONFIG
    def on_nose_weight_change(self, value):
        """Callback per cambio peso naso."""
        weight = float(value)
        self.scoring_config.set_nose_weight(weight)
        self.nose_value_label.config(text=f"{weight:.2f}")
        self.recalculate_current_score()

    def on_mouth_weight_change(self, value):
        """Callback per cambio peso bocca."""
        weight = float(value)
        self.scoring_config.set_mouth_weight(weight)
        self.mouth_value_label.config(text=f"{weight:.2f}")
        self.recalculate_current_score()

    def on_symmetry_weight_change(self, value):
        """Callback per cambio peso simmetria."""
        weight = float(value)
        self.scoring_config.set_symmetry_weight(weight)
        self.symmetry_value_label.config(text=f"{weight:.2f}")
        self.recalculate_current_score()

    def on_eye_weight_change(self, value):
        """Callback per cambio peso occhi."""
        weight = float(value)
        self.scoring_config.set_eye_weight(weight)
        self.eye_value_label.config(text=f"{weight:.2f}")
        self.recalculate_current_score()

    def on_scoring_config_change(self):
        """Callback chiamato quando la configurazione scoring cambia."""
        self.recalculate_current_score()

    def recalculate_current_score(self):
        """Ricalcola lo score del frame corrente con i nuovi pesi."""
        if self.current_landmarks is not None and self.current_image is not None:
            # Importa qui per evitare dipendenze circolari
            from src.utils import calculate_pure_frontal_score

            new_score = calculate_pure_frontal_score(
                self.current_landmarks,
                self.current_image.shape,
                config=self.scoring_config,
            )

            self.current_best_score = new_score
            self.scoring_info_label.config(text=f"Score corrente: {new_score:.3f}")

            # Aggiorna anche il display del best frame se presente
            if hasattr(self, "best_frame_info") and self.best_frame_info:
                self.best_frame_info.config(
                    text=f"Score frame corrente: {new_score:.3f} - Pesi: N:{self.scoring_config.nose_weight:.2f} B:{self.scoring_config.mouth_weight:.2f} S:{self.scoring_config.symmetry_weight:.2f} O:{self.scoring_config.eye_weight:.2f}"
                )

    def reset_scoring_weights(self):
        """Reset ai pesi di default."""
        self.scoring_config.set_nose_weight(0.30)
        self.scoring_config.set_mouth_weight(0.25)
        self.scoring_config.set_symmetry_weight(0.25)
        self.scoring_config.set_eye_weight(0.20)
        self.update_slider_values()

    def preset_nose_focus(self):
        """Preset con focus sul naso."""
        self.scoring_config.set_nose_weight(0.50)
        self.scoring_config.set_mouth_weight(0.25)
        self.scoring_config.set_symmetry_weight(0.15)
        self.scoring_config.set_eye_weight(0.10)
        self.update_slider_values()

    def preset_less_symmetry(self):
        """Preset with meno enfasi sulla simmetria."""
        self.scoring_config.set_nose_weight(0.40)
        self.scoring_config.set_mouth_weight(0.35)
        self.scoring_config.set_symmetry_weight(0.15)
        self.scoring_config.set_eye_weight(0.10)
        self.update_slider_values()

    def toggle_axis(self):
        """Gestisce il toggle dell'asse di simmetria."""
        if self.current_landmarks:
            self.update_canvas_display()

    def update_slider_values(self):
        """Aggiorna i valori degli slider dall'oggetto config."""
        self.nose_scale.set(self.scoring_config.nose_weight)
        self.mouth_scale.set(self.scoring_config.mouth_weight)
        self.symmetry_scale.set(self.scoring_config.symmetry_weight)
        self.eye_scale.set(self.scoring_config.eye_weight)

        self.nose_value_label.config(text=f"{self.scoring_config.nose_weight:.2f}")
        self.mouth_value_label.config(text=f"{self.scoring_config.mouth_weight:.2f}")
        self.symmetry_value_label.config(
            text=f"{self.scoring_config.symmetry_weight:.2f}"
        )
        self.eye_value_label.config(text=f"{self.scoring_config.eye_weight:.2f}")

    # === METODI INTEGRAZIONE CANVAS PROFESSIONALE ===

    def on_canvas_measurement_click_old_professional(self, event):
        """Gestisce i click del canvas professionale per le misurazioni (DEPRECATO - NON USARE)."""
        if not event.inaxes or not hasattr(self, "measurement_tools"):
            return

        # Le coordinate matplotlib sono già nel sistema di coordinate dell'immagine
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return

        # Converte in coordinate intere per compatibilità
        image_x, image_y = int(x), int(y)

        # Gestisce la selezione in base alla modalità corrente
        if self.landmark_measurement_mode:
            # Modalità landmark: trova il landmark più vicino
            if self.current_landmarks:
                closest_landmark_idx = self.find_closest_landmark(image_x, image_y)
                if closest_landmark_idx is not None:
                    self.add_landmark_selection(closest_landmark_idx)
        else:
            # Modalità manuale: aggiunge punto diretto
            self.selected_points.append((image_x, image_y))

            # Limita il numero di punti in base alla modalità
            max_points = {"distance": 2, "angle": 3, "area": 4}
            if len(self.selected_points) > max_points.get(self.measurement_mode, 2):
                self.selected_points.pop(0)

            self.status_bar.config(text=f"Punto selezionato: ({image_x}, {image_y})")

        # Aggiorna la visualizzazione
        self.update_canvas_display()

    def on_measurement_completed(self, measurement_data):
        """Callback quando una misurazione è completata nel canvas professionale."""
        if hasattr(self, "measurement_result"):
            self.measurement_result = measurement_data
            # Aggiorna la visualizzazione se necessario
            if hasattr(self, "status_bar"):
                self.status_bar.config(
                    text=f"Misurazione completata: {measurement_data}"
                )

    # Metodo rimosso: update_canvas_display_OLD_PROFESSIONAL - deprecato e non più necessario

    # Metodo rimosso: draw_landmarks_on_professional_canvas - non più necessario

    # Metodo rimosso: draw_measurements_on_professional_canvas - non più necessario

    def clear_canvas(self):
        """Pulisce il canvas unificato."""
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.delete("all")
            print("✅ Canvas unificato pulito")

    def save_image(self):
        """Salva l'immagine corrente con le annotazioni."""
        if self.current_image is not None:
            file_path = filedialog.asksaveasfilename(
                title="Salva Immagine",
                defaultextension=".png",
                filetypes=[
                    ("PNG", "*.png"),
                    ("JPEG", "*.jpg"),
                    ("Tutti i file", "*.*"),
                ],
            )

            if file_path:
                # Salva l'immagine corrente
                cv2.imwrite(file_path, self.current_image)
                self.status_bar.config(text=f"Immagine salvata: {file_path}")

    def export_measurements(self):
        """Esporta le misurazioni in formato JSON."""
        # TODO: Implementare esportazione misurazioni dal sistema unificato
        messagebox.showinfo("Info", "Funzionalità in sviluppo nel sistema unificato")


def main():
    """Funzione principale per avviare l'applicazione."""
    root = tk.Tk()
    app = CanvasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
