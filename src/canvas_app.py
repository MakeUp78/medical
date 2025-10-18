"""
Interactive canvas application for facial analysis with measurement tools.
VERSIONE UNIFICATA - Include funzionalità professional canvas integrate
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk  # Manteniamo per compatibilità con alcuni widget
from tkinter import filedialog, messagebox, colorchooser
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import List, Tuple, Optional, Dict, Any
import uuid
import os
import tempfile
import shutil
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
from src.layout_fix import LayoutRestorer, ImprovedLayoutSaver
from src.face_analysis_module import FaceVisagismAnalyzer

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
    def __init__(self, root, voice_assistant=None):
        """Inizializza l'applicazione canvas.
        
        Args:
            root: Finestra principale tkinter
            voice_assistant: Istanza IsabellaVoiceAssistant (opzionale)
        """
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
        self.face_analyzer = FaceVisagismAnalyzer()  # Analizzatore facciale professionale

        # Variabili di stato per canvas tkinter (RIPRISTINATE)
        self.current_image = None
        self.current_landmarks = None

        # Variabili canvas tkinter ripristinate
        self.canvas_image = None  # Per il canvas tkinter
        self.canvas_scale = 1.0  # Per lo zoom del canvas tkinter
        self.canvas_offset = (0, 0)  # Per il panning del canvas tkinter
        self.current_canvas_tool = "SELECTION"  # Tool attivo per il canvas
        # self.active_layer e self.layers_list già definiti sopra

        # *** NUOVO SISTEMA UNIFICATO DI TRASFORMAZIONE GRAFICHE ***
        # Singolo registro per tutte le grafiche utente con coordinate nell'immagine originale
        self.graphics_registry = (
            {}
        )  # {item_id: {"type": "line|oval|rectangle", "image_coords": [...], "style": {...}}}

        # Dizionari del vecchio sistema (mantenuti per compatibilità, ma non più usati)
        self.original_drawing_coords = {}
        self.original_unrotated_coords = {}

        # Variabili per display e scaling (MANTENUTE per retrocompatibilità)
        self.display_scale = 1.0
        self.display_size = (800, 600)  # Default size

        self.selected_points = []
        self.selected_landmarks = []  # Landmark selezionati per misurazione
        self.measurement_mode = "distance"
        self.measurement_result = None  # Risultato dell'ultima misurazione
        self.landmark_measurement_mode = True  # True per modalità landmark (default)
        self.hovered_landmark = None  # Landmark attualmente evidenziato
        self.show_all_landmarks = False  # True per mostrare tutti i 478 landmarks
        self.show_measurements = True

        # Sistema overlay per misurazioni
        self.measurement_overlays = []  # Lista di overlay delle misurazioni
        self.show_measurement_overlays = True
        self.original_measurement_overlays = []  # Backup delle coordinate originali

        # Sistema per puntini verdi sopraccigliare
        self.green_dots_results = None  # Risultati dell'ultimo rilevamento
        self.green_dots_overlay = None  # Overlay dei poligoni sopraccigliare
        self.show_green_dots_overlay = False  # Flag per mostrare l'overlay
        self.original_green_dots_overlay = None  # Backup coordinate originali

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
        # Backup delle coordinate originali per rotazioni assolute
        self.original_preset_overlays = {
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
        
        # NUOVO: Gestione finestra separata
        self.detached_preview_window = None
        self.detached_preview_label = None
        self.is_preview_detached = False

        # Sistema di rotazione immagini
        self.current_rotation = 0.0  # Angolo di rotazione corrente in gradi
        self.rotation_step = 1.0  # Passo di rotazione per ogni click (1 grado)
        self.original_unrotated_coords = (
            {}
        )  # Coordinate originali non ruotate per evitare accumulo errori
        self.original_base_image = (
            None  # Immagine originale non ruotata (base per tutte le rotazioni)
        )
        self.original_base_landmarks = None  # Landmarks originali non ruotati
        
        # Assistente vocale - riferimenti semplici
        self.voice_assistant = voice_assistant
        self.voice_gui = None

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

        # Variabili di controllo per la sezione RILEVAMENTI
        self.show_axis_var = None  # Inizializzato in setup_controls
        self.all_landmarks_var = None  # Inizializzato in setup_controls
        self.overlay_var = None  # Inizializzato in setup_controls (sempre True)
        self.green_dots_var = None  # Inizializzato in setup_controls
        
        # Variabile per modalità misurazione interattiva
        self.measurement_mode_active = None  # Inizializzato in setup_controls
        self.hovered_landmark = None  # Per hover effect sui landmarks

        # Imposta la configurazione nel video analyzer
        self.video_analyzer.set_scoring_config(self.scoring_config)

        # NUOVO: Inizializza le variabili degli overlay (prima del setup GUI)
        self.show_landmarks_var = tk.BooleanVar(value=True)  # Abilitato di default
        self.show_symmetry_var = tk.BooleanVar(value=True)   # Abilitato di default
        self.show_green_polygon_var = tk.BooleanVar(value=False)

        # Stato finestra separata anteprima
        self.is_preview_detached = False
        self.detached_preview_window = None
        self.detached_preview_label = None

        self.setup_gui()

        # CALLBACK ESSENZIALI
        self.video_analyzer.set_completion_callback(self.on_analysis_completion)
        self.video_analyzer.set_preview_callback(self.on_video_preview_update)
        self.video_analyzer.set_frame_callback(self.on_frame_update)  # *** AGGIUNTO ***
        self.video_analyzer.set_debug_callback(
            self.on_debug_update
        )  # *** NUOVO PER TABELLA ***

        # INIZIALIZZA OVERLAY DEFAULT (landmarks e simmetria attivi)
        self.update_overlay_settings()

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

        # PANNELLO CONTROLLI (sinistra) - Con stile ttkbootstrap
        control_main_frame = ttk.LabelFrame(
            self.main_horizontal_paned, text="🎛️ Controlli", padding=10, width=400, 
            bootstyle="primary"
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
            text="🎨 Canvas Professionale Unificato",
            padding=5,
            width=800,
            bootstyle="success"
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
            self.right_sidebar_paned, text="📋 Layers", padding=5, width=350,
            bootstyle="info"
        )
        layers_frame.grid_columnconfigure(0, weight=1)
        layers_frame.grid_rowconfigure(0, weight=1)
        self.right_sidebar_paned.add(layers_frame, weight=1)

        # Setup area anteprima integrata (sotto)
        preview_main_frame = ttk.LabelFrame(
            self.right_sidebar_paned, text="📺 Anteprima Video", padding=5,
            bootstyle="warning"
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

        # Setup area misurazioni (in basso) ridimensionabile con stile card
        measurements_frame = ttk.LabelFrame(
            self.main_vertical_paned, text="📊 Lista Misurazioni", padding=10,
            bootstyle="warning"
        )
        measurements_frame.grid_columnconfigure(0, weight=1)
        measurements_frame.grid_rowconfigure(0, weight=1)
        self.setup_measurements_area(measurements_frame)
        self.main_vertical_paned.add(measurements_frame, weight=0)

        # Setup status bar
        self.setup_status_bar()

        # *** NUOVO SISTEMA RIPRISTINO LAYOUT ROBUSTO ***
        print("🔧 Inizializzazione sistema layout robusto...")
        self.layout_restorer = LayoutRestorer(self)
        self.layout_saver = ImprovedLayoutSaver(self)
        
        # Avvia ripristino layout con timing migliorato
        self.layout_restorer.start_layout_restore()

        # Bind eventi per salvare layout - configurati DOPO il ripristino
        print("🔧 Configurazione bind eventi per ridimensionamento pannelli...")
        self.main_vertical_paned.bind(
            "<ButtonRelease-1>", self._on_vertical_paned_resize_improved
        )
        print("   ✅ Vertical paned bind configurato")

        self.main_horizontal_paned.bind("<ButtonRelease-1>", self._on_main_paned_resize_improved)
        print("   ✅ Main horizontal paned bind configurato")

        self.right_sidebar_paned.bind(
            "<ButtonRelease-1>", self._on_sidebar_paned_resize_improved
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
        # Sezione SORGENTE con layout migliorato
        video_frame = ttk.LabelFrame(parent, text="🎯 SORGENTE", padding=10, 
                                   bootstyle="primary")
        video_frame.pack(fill=tk.X, pady=(0, 10))

        # Configura griglia per layout ottimizzato
        video_frame.columnconfigure(0, weight=1)
        video_frame.columnconfigure(1, weight=1)

        # Prima riga: Carica Immagine (pulsante principale, spanning)
        ttk.Button(
            video_frame, text="📁 Carica Immagine", command=self.load_image,
            bootstyle="primary"
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5), padx=2)
        
        # Seconda riga: Webcam e Video
        ttk.Button(video_frame, text="📹 Avvia Webcam", command=self.start_webcam,
                  bootstyle="success-outline").grid(
            row=1, column=0, sticky="ew", pady=2, padx=(2, 1)
        )
        ttk.Button(video_frame, text="🎬 Carica Video", command=self.load_video,
                  bootstyle="info-outline").grid(
            row=1, column=1, sticky="ew", pady=2, padx=(1, 2)
        )
        
        # Terza riga: Controllo stop
        ttk.Button(
            video_frame, text="⏹️ Ferma Analisi", command=self.stop_video_analysis,
            bootstyle="danger"
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0), padx=2)

        # Info frame migliore con larghezza fissa
        self.best_frame_info = ttk.Label(
            video_frame, text="Nessun frame analizzato", width=60
        )
        self.best_frame_info.grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=5, padx=2
        )

        # === PANNELLO STATUS CON BADGE INFORMATIVI ===
        status_info_frame = ttk.LabelFrame(
            parent, text="📊 Stato Sistema", padding=10, bootstyle="secondary"
        )
        status_info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Frame per i badge orizzontali
        badges_frame = ttk.Frame(status_info_frame)
        badges_frame.pack(fill=tk.X)
        
        # Badge per stato webcam
        self.webcam_badge = ttk.Label(
            badges_frame, text="📷 Webcam: Disconnessa", 
            bootstyle="danger", padding=5
        )
        self.webcam_badge.grid(row=0, column=0, padx=(0, 5), pady=2, sticky="w")
        
        # Badge per landmarks
        self.landmarks_badge = ttk.Label(
            badges_frame, text="🎯 Landmarks: 0 rilevati", 
            bootstyle="warning", padding=5
        )
        self.landmarks_badge.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        # Badge per qualità immagine
        self.quality_badge = ttk.Label(
            badges_frame, text="✨ Qualità: N/A", 
            bootstyle="info", padding=5
        )
        self.quality_badge.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        
        # Badge per misurazioni attive
        self.measurements_badge = ttk.Label(
            badges_frame, text="📏 Misurazioni: 0 attive", 
            bootstyle="secondary", padding=5
        )
        self.measurements_badge.grid(row=1, column=0, padx=(0, 5), pady=2, sticky="w")
        
        # Badge per modalità corrente
        self.mode_badge = ttk.Label(
            badges_frame, text="🔧 Modalità: Selezione", 
            bootstyle="primary", padding=5
        )
        self.mode_badge.grid(row=1, column=1, padx=5, pady=2, sticky="w")

        # Sezione MISURAZIONI con layout migliorato
        measure_frame = ttk.LabelFrame(
            parent, text="📏 MISURAZIONI", padding=10, bootstyle="success"
        )
        measure_frame.pack(fill=tk.X, pady=(0, 8))



        # Sezione RILEVAMENTI
        detections_frame = ttk.LabelFrame(parent, text="🔍 RILEVAMENTI", padding=10,
                                        bootstyle="warning")
        detections_frame.pack(fill=tk.X, pady=(0, 10))

        # Inizializza le variabili di controllo
        self.show_axis_var = tk.BooleanVar(value=False)
        self.all_landmarks_var = tk.BooleanVar(value=False)
        self.overlay_var = tk.BooleanVar(value=True)  # Sempre attivo (grafiche sempre visibili)
        self.green_dots_var = tk.BooleanVar(value=False)

        # Frame per i tre pulsanti principali
        main_buttons_frame = ttk.Frame(detections_frame)
        main_buttons_frame.pack(fill=tk.X, pady=(0, 10))

        # Pulsante ASSE
        self.asse_button = ttk.Button(
            main_buttons_frame, 
            text="⚖️ ASSE", 
            command=self.toggle_asse_section
        )
        self.asse_button.grid(row=0, column=0, padx=(0, 2), sticky="ew")

        # Pulsante LANDMARKS  
        self.landmarks_button = ttk.Button(
            main_buttons_frame, 
            text="🎯 LANDMARKS", 
            command=self.toggle_landmarks_section
        )
        self.landmarks_button.grid(row=0, column=1, padx=2, sticky="ew")

        # Pulsante GREEN DOTS
        self.green_dots_button = ttk.Button(
            main_buttons_frame, 
            text="🟢 GREEN DOTS", 
            command=self.toggle_green_dots_section
        )
        self.green_dots_button.grid(row=0, column=2, padx=2, sticky="ew")

        # Pulsante ANALISI FACCIALE
        self.face_analysis_button = ttk.Button(
            main_buttons_frame, 
            text="🔍 ANALISI FACCIALE", 
            command=self.perform_face_analysis
        )
        self.face_analysis_button.grid(row=0, column=3, padx=(2, 0), sticky="ew")

        # Configura colonne con peso uguale
        main_buttons_frame.columnconfigure(0, weight=1)
        main_buttons_frame.columnconfigure(1, weight=1)
        main_buttons_frame.columnconfigure(2, weight=1)
        main_buttons_frame.columnconfigure(3, weight=1)

        # Misurazioni predefinite (sotto i pulsanti principali)
        self.predefined_frame = ttk.LabelFrame(
            detections_frame, text="Misurazioni Predefinite", padding=5
        )
        self.predefined_frame.pack(fill=tk.X, pady=(0, 0))

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

        # === NUOVO: TABELLA LANDMARKS RILEVATI ===
        landmarks_table_frame = ttk.LabelFrame(
            parent, text="🎯 Landmarks Rilevati", padding=10, bootstyle="info"
        )
        landmarks_table_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Treeview per landmarks con stile bootstrap
        self.landmarks_tree = ttk.Treeview(
            landmarks_table_frame,
            columns=("ID", "Nome", "X", "Y", "Visibilità"),
            show="headings",
            height=6,
            bootstyle="success"
        )
        
        # Intestazioni con emoji
        self.landmarks_tree.heading("ID", text="🆔 ID")
        self.landmarks_tree.heading("Nome", text="🏷️ Nome Landmark")
        self.landmarks_tree.heading("X", text="📍 Coord X")
        self.landmarks_tree.heading("Y", text="📍 Coord Y")
        self.landmarks_tree.heading("Visibilità", text="👁️ Visibile")
        
        # Configurazione colonne
        self.landmarks_tree.column("ID", width=40, minwidth=30)
        self.landmarks_tree.column("Nome", width=150, minwidth=100)
        self.landmarks_tree.column("X", width=80, minwidth=60)
        self.landmarks_tree.column("Y", width=80, minwidth=60)
        self.landmarks_tree.column("Visibilità", width=80, minwidth=60)
        
        # Scrollbar per landmarks
        landmarks_scroll = ttk.Scrollbar(
            landmarks_table_frame, orient=tk.VERTICAL, command=self.landmarks_tree.yview
        )
        self.landmarks_tree.configure(yscrollcommand=landmarks_scroll.set)
        
        # Layout
        self.landmarks_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        landmarks_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Eventi per interazione con la tabella
        self.landmarks_tree.bind('<Double-1>', self.on_landmark_double_click)
        
        # Dizionario per mappare ID landmarks a nomi anatomici
        self.landmark_names = {
            # Contorno viso
            10: "Fronte Centro",
            152: "Mento Centro", 
            127: "Tempia Sinistra",
            356: "Tempia Destra",
            
            # Occhi
            33: "Occhio Sinistro - Angolo Interno",
            133: "Occhio Sinistro - Angolo Esterno", 
            362: "Occhio Destro - Angolo Interno",
            263: "Occhio Destro - Angolo Esterno",
            159: "Occhio Sinistro - Centro Pupilla",
            145: "Occhio Destro - Centro Pupilla",
            
            # Sopracciglia
            70: "Sopracciglio Sinistro - Centro",
            107: "Sopracciglio Sinistro - Interno",
            55: "Sopracciglio Sinistro - Esterno",
            296: "Sopracciglio Destro - Centro", 
            334: "Sopracciglio Destro - Interno",
            285: "Sopracciglio Destro - Esterno",
            
            # Naso  
            1: "Ponte Nasale",
            2: "Punta Naso",
            19: "Narice Sinistra",
            20: "Narice Destra",
            131: "Ala Nasale Sinistra",
            360: "Ala Nasale Destra",
            
            # Bocca
            13: "Labbro Superiore Centro",
            14: "Labbro Inferiore Centro",
            78: "Angolo Bocca Sinistro",
            308: "Angolo Bocca Destro",
            61: "Labbro Superiore Sinistro",
            291: "Labbro Superiore Destro",
            17: "Labbro Inferiore Sinistro", 
            18: "Labbro Inferiore Destro",
            
            # Punti di riferimento chiave
            9: "Glabella (Centro Fronte)",
            168: "Centro Viso",
            6: "Ponte Naso Alto",
            151: "Mento Inferiore"
        }

        # === NUOVO: PANNELLO MISURAZIONI INTERATTIVE (SPOSTATO SOTTO RILEVAMENTI) ===
        self.interactive_measurements_frame = ttk.LabelFrame(
            detections_frame, text="📐 Misurazioni Interattive", padding=10
        )
        self.interactive_measurements_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Checkbox per attivare modalità misurazione interattiva
        self.measurement_mode_active = tk.BooleanVar(value=False)
        self.measurement_checkbox = ttk.Checkbutton(
            self.interactive_measurements_frame,
            text="🎯 Attiva Modalità Misurazione",
            variable=self.measurement_mode_active,
            command=self.toggle_measurement_mode,
        )
        self.measurement_checkbox.pack(anchor=tk.W, pady=(0, 10))

        # Griglia per modalità misurazione
        mode_subframe = ttk.Frame(self.interactive_measurements_frame)
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
        selection_subframe = ttk.Frame(self.interactive_measurements_frame)
        selection_subframe.pack(fill=tk.X, pady=3)
        selection_subframe.columnconfigure(0, weight=1)
        selection_subframe.columnconfigure(1, weight=1)

        ttk.Label(
            selection_subframe, text="Selezione:", font=("Arial", 9, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))

        self.selection_mode_var = tk.StringVar(value="landmark")
        ttk.Radiobutton(
            selection_subframe,
            text="📍 Landmark",
            variable=self.selection_mode_var,
            value="landmark",
            command=self.change_selection_mode,
        ).grid(row=1, column=0, sticky="w", padx=(0, 5))

        ttk.Radiobutton(
            selection_subframe,
            text="✋ Manuale",
            variable=self.selection_mode_var,
            value="manual",
            command=self.change_selection_mode,
        ).grid(row=1, column=1, sticky="w")

        # Pulsanti azione
        action_subframe = ttk.Frame(self.interactive_measurements_frame)
        action_subframe.pack(fill=tk.X, pady=5)
        action_subframe.columnconfigure(0, weight=1)
        action_subframe.columnconfigure(1, weight=1)

        ttk.Button(
            action_subframe, text="📊 Calcola", command=self.calculate_measurement
        ).grid(row=0, column=0, sticky="ew", padx=(0, 2))
        ttk.Button(
            action_subframe, text="🗑️ Cancella", command=self.clear_selections
        ).grid(row=0, column=1, sticky="ew", padx=(2, 0))

        # === SEZIONE CORREZIONE SOPRACCIGLIO ===
        self.setup_eyebrow_correction_controls(detections_frame)

        # Sezione Controlli Score Frontalità
        self.setup_scoring_controls(parent)

    def setup_scoring_controls(self, parent):
        """Configura il pannello dei controlli per i pesi dello scoring."""
        scoring_frame = ttk.LabelFrame(
            parent, text="⚖️ SCORING", padding=10
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

        # === INTEGRAZIONE ASSISTENTE VOCALE SEMPLICE ===
        if self.voice_assistant:
            try:
                # Setup riferimento app per comandi vocali
                self.voice_assistant.set_canvas_app(self)
                
                # Crea GUI semplice per controllo on/off
                self.voice_gui = self.voice_assistant.create_gui(parent)
                self.voice_gui.pack(fill=tk.X, pady=(10, 0))  # AGGIUNTO PACK!
                
                print("✅ Assistente vocale integrato con successo")
            except Exception as e:
                print(f"⚠️ Errore integrazione assistente vocale: {e}")

    def setup_eyebrow_correction_controls(self, parent):
        """Configura il pannello dei controlli per la correzione dei sopracciglio."""
        eyebrow_frame = ttk.LabelFrame(
            parent, text="✂️ CORREZIONE SOPRACCIGLIO", padding=10
        )
        eyebrow_frame.pack(fill=tk.X, pady=(10, 0))

        # Info sulla funzionalità
        info_label = ttk.Label(
            eyebrow_frame,
            text="Visualizza sopracciglio ritagliato con overlay dei punti verdi",
            font=("Arial", 9),
            foreground="gray"
        )
        info_label.pack(pady=(0, 10))

        # Frame per i pulsanti
        buttons_frame = ttk.Frame(eyebrow_frame)
        buttons_frame.pack(fill=tk.X)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        # Pulsante Correzione Sx
        self.correction_left_button = ttk.Button(
            buttons_frame,
            text="✂️ Correzione Sx",
            command=self.show_left_eyebrow_correction,
            state=tk.DISABLED  # Inizialmente disabilitato
        )
        self.correction_left_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # Pulsante Correzione Dx  
        self.correction_right_button = ttk.Button(
            buttons_frame,
            text="✂️ Correzione Dx", 
            command=self.show_right_eyebrow_correction,
            state=tk.DISABLED  # Inizialmente disabilitato
        )
        self.correction_right_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # Salva riferimenti per controllo stato
        self.eyebrow_correction_buttons = [
            self.correction_left_button,
            self.correction_right_button
        ]

    # === METODI VOCALI RIMOSSI ===
    # Tutti i metodi relativi all'assistente vocale sono stati spostati in:
    # voice/voice_gui_integration.py
    # 
    # Metodi rimossi:
    # - setup_voice_controls()
    # - init_voice_assistant()
    # - setup_voice_commands()
    # - toggle_voice_assistant()
    # - test_voice_output()
    # - show_voice_commands()
    # - voice_start_analysis()
    # - voice_save_results()
    # - voice_speak_feedback()

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
        # Stile per pulsanti della sezione RILEVAMENTI quando attivi
        style.configure(
            "Active.TButton", 
            background="#4CAF50",  # Verde per stato attivo
            foreground="white",
            relief="raised", 
            borderwidth=2
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
            btn = ttk.Button(view_frame, text=icon, width=4, command=command, 
                           bootstyle="secondary")
            btn.pack(side=tk.LEFT, padx=1)
            # TODO: Aggiungere tooltip se necessario

        # Gruppo rotazione
        rotation_frame = ttk.LabelFrame(
            self.canvas_toolbar_frame, text="Rotazione", padding=2
        )
        rotation_frame.pack(side=tk.LEFT, padx=(0, 3))

        rotation_buttons = [
            ("↶", self.rotate_clockwise, "Ruota antiorario (1°)"),
            ("↷", self.rotate_counterclockwise, "Ruota orario (1°)"),
            ("⌂", self.reset_rotation, "Reset rotazione (0°)"),
        ]

        for icon, command, tooltip in rotation_buttons:
            btn = ttk.Button(rotation_frame, text=icon, width=4, command=command,
                           bootstyle="warning-outline")
            btn.pack(side=tk.LEFT, padx=1)
            ToolTip(btn, tooltip)  # Aggiungi tooltip per i pulsanti di rotazione

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
        
        # 🎯 NUOVO: Pulsante pulizia overlay generale (mantiene solo landmark, asse, green dots)
        clear_overlays_btn = ttk.Button(
            draw_frame,
            text="🧹",
            width=4,
            command=self.clear_all_overlays_except_essentials,
        )
        clear_overlays_btn.pack(side=tk.LEFT, padx=1)

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
        """Adatta l'immagine alla finestra e ricalcola posizioni grafiche."""
        if self.current_image_on_canvas is not None:
            old_scale = self.canvas_scale
            old_offset_x = self.canvas_offset_x
            old_offset_y = self.canvas_offset_y

            self.canvas_scale = 1.0
            self.canvas_offset_x = 0
            self.canvas_offset_y = 0

            # *** NUOVO SISTEMA: Se scala o offset sono cambiati, applica trasformazioni
            if (
                old_scale != self.canvas_scale
                or old_offset_x != self.canvas_offset_x
                or old_offset_y != self.canvas_offset_y
            ):
                self.transform_all_graphics()

            self.update_canvas_display()
            print("🏠 Vista adattata alla finestra - grafiche ricalcolate")

    # Metodo reset_view rimosso - funzionalità consolidata in fit_to_window (pulsante 🏠)

    # *** FUNZIONE OBSOLETA - RIMOSSA ***
    # def recalculate_graphics_after_view_change() -> Sostituita da transform_all_graphics()
    def _obsolete_recalculate_graphics_placeholder(self):
        recalculated_count = 0

        # Ricalcola elementi in original_unrotated_coords (elementi ruotati)
        for item_id, data in self.original_unrotated_coords.items():
            try:
                if item_id in self.canvas.find_all():
                    # Calcola il fattore di scala
                    scale_factor = self.canvas_scale / data.get("canvas_scale", 1.0)

                    # Ottieni centro immagine corrente e memorizzato per calcolare offset
                    if self.current_image_on_canvas is not None:
                        current_image_center_x, current_image_center_y = (
                            self.get_image_center()
                        )
                        stored_center = data.get(
                            "rotation_center",
                            [current_image_center_x, current_image_center_y],
                        )

                        # Calcola offset dovuto al cambio posizione immagine
                        center_offset_x = (
                            current_image_center_x - stored_center[0] * scale_factor
                        )
                        center_offset_y = (
                            current_image_center_y - stored_center[1] * scale_factor
                        )
                    else:
                        center_offset_x = 0
                        center_offset_y = 0

                    # Ottieni coordinate attuali e tipo
                    item_type = data["type"]
                    original_coords = data["coords"]

                    # Ricalcola in base al tipo
                    if item_type == "line":
                        new_coords = []
                        for i in range(0, len(original_coords), 2):
                            new_x = original_coords[i] * scale_factor + center_offset_x
                            new_y = (
                                original_coords[i + 1] * scale_factor + center_offset_y
                            )
                            new_coords.extend([new_x, new_y])
                        self.canvas.coords(item_id, *new_coords)

                    elif item_type in ["oval", "rectangle", "polygon"]:
                        if len(original_coords) == 4:  # Rectangle/oval
                            x1, y1, x2, y2 = original_coords
                            new_x1 = x1 * scale_factor + center_offset_x
                            new_y1 = y1 * scale_factor + center_offset_y
                            new_x2 = x2 * scale_factor + center_offset_x
                            new_y2 = y2 * scale_factor + center_offset_y
                            self.canvas.coords(item_id, new_x1, new_y1, new_x2, new_y2)
                        else:  # Polygon with multiple points
                            new_coords = []
                            for i in range(0, len(original_coords), 2):
                                new_x = (
                                    original_coords[i] * scale_factor + center_offset_x
                                )
                                new_y = (
                                    original_coords[i + 1] * scale_factor
                                    + center_offset_y
                                )
                                new_coords.extend([new_x, new_y])
                            self.canvas.coords(item_id, *new_coords)

                    elif item_type == "text":
                        x, y = original_coords[:2]
                        new_x = x * scale_factor + center_offset_x
                        new_y = y * scale_factor + center_offset_y
                        self.canvas.coords(item_id, new_x, new_y)

                    # Aggiorna la scala memorizzata
                    data["canvas_scale"] = self.canvas_scale
                    recalculated_count += 1

            except Exception as e:
                print(f"⚠️ Errore ricalcolo elemento {item_id}: {e}")

        # Ricalcola elementi in original_drawing_coords (elementi normali)
        for item_id, data in self.original_drawing_coords.items():
            try:
                if item_id in self.canvas.find_all():
                    scale_factor = self.canvas_scale / data.get("canvas_scale", 1.0)

                    # Ottieni centro immagine corrente e memorizzato per calcolare offset
                    if self.current_image_on_canvas is not None:
                        current_image_center_x, current_image_center_y = (
                            self.get_image_center()
                        )
                        stored_center = data.get(
                            "image_center",
                            [current_image_center_x, current_image_center_y],
                        )

                        # Calcola offset dovuto al cambio posizione immagine
                        center_offset_x = (
                            current_image_center_x - stored_center[0] * scale_factor
                        )
                        center_offset_y = (
                            current_image_center_y - stored_center[1] * scale_factor
                        )
                    else:
                        center_offset_x = 0
                        center_offset_y = 0

                    item_type = data["type"]
                    original_coords = data["coords"]

                    if item_type == "line":
                        new_coords = []
                        for i in range(0, len(original_coords), 2):
                            new_x = original_coords[i] * scale_factor + center_offset_x
                            new_y = (
                                original_coords[i + 1] * scale_factor + center_offset_y
                            )
                            new_coords.extend([new_x, new_y])
                        self.canvas.coords(item_id, *new_coords)

                    elif item_type in ["oval", "rectangle", "polygon"]:
                        if len(original_coords) == 4:  # Rectangle/oval
                            x1, y1, x2, y2 = original_coords
                            new_x1 = x1 * scale_factor + center_offset_x
                            new_y1 = y1 * scale_factor + center_offset_y
                            new_x2 = x2 * scale_factor + center_offset_x
                            new_y2 = y2 * scale_factor + center_offset_y
                            self.canvas.coords(item_id, new_x1, new_y1, new_x2, new_y2)
                        else:  # Polygon with multiple points
                            new_coords = []
                            for i in range(0, len(original_coords), 2):
                                new_x = (
                                    original_coords[i] * scale_factor + center_offset_x
                                )
                                new_y = (
                                    original_coords[i + 1] * scale_factor
                                    + center_offset_y
                                )
                                new_coords.extend([new_x, new_y])
                            self.canvas.coords(item_id, *new_coords)

                    elif item_type == "text":
                        x, y = original_coords[:2]
                        new_x = x * scale_factor + center_offset_x
                        new_y = y * scale_factor + center_offset_y
                        self.canvas.coords(item_id, new_x, new_y)

                    # Aggiorna la scala memorizzata
                    data["canvas_scale"] = self.canvas_scale
                    recalculated_count += 1

            except Exception as e:
                print(f"⚠️ Errore ricalcolo elemento drawing {item_id}: {e}")

        if recalculated_count > 0:
            print(
                f"🔄 Ricalcolati {recalculated_count} elementi grafici per cambio vista"
            )

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

                # *** NUOVO SISTEMA: Applica trasformazioni unificate
                self.transform_all_graphics()

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

                # *** NUOVO SISTEMA: Applica trasformazioni unificate
                self.transform_all_graphics()

                print(f"🔍- Zoom out: {self.canvas_scale:.2f}")

    def rotate_clockwise(self):
        """Ruota l'immagine di 1 grado in senso orario."""
        self.current_rotation += self.rotation_step
        self.current_rotation %= 360  # Mantieni l'angolo tra 0 e 360 gradi
        self.apply_rotation()
        print(f"↷ Rotazione oraria: {self.current_rotation:.1f}°")

    def rotate_counterclockwise(self):
        """Ruota l'immagine di 1 grado in senso antiorario."""
        self.current_rotation -= self.rotation_step
        self.current_rotation %= 360  # Mantieni l'angolo tra 0 e 360 gradi
        self.apply_rotation()
        print(f"↶ Rotazione antioraria: {self.current_rotation:.1f}°")

    def reset_rotation(self):
        """Resetta la rotazione a 0 gradi tornando all'immagine originale."""
        self.current_rotation = 0.0

        # Ripristina l'immagine originale
        if self.original_base_image is not None:
            self.current_image = self.original_base_image.copy()
            self.current_image_on_canvas = self.original_base_image.copy()

        # Ripristina i landmarks originali
        if self.original_base_landmarks is not None:
            self.current_landmarks = self.original_base_landmarks.copy()

        # *** NUOVO SISTEMA: Le grafiche si aggiornano automaticamente quando l'immagine torna a 0°
        self.transform_all_graphics()

        # RESETTA ANCHE GLI OVERLAY
        self.reset_all_overlays()

        # Aggiorna la visualizzazione
        self.update_canvas_display()

        # Aggiorna status bar
        if hasattr(self, "status_bar"):
            self.status_bar.config(text="Rotazione resettata: 0°")

        print(f"⌂ Rotazione resettata: 0°")

    def apply_rotation(self):
        """Applica la rotazione corrente all'immagine originale attorno al landmark 9 (glabella)."""
        if self.original_base_image is None:
            print("⚠️ Nessuna immagine base da ruotare")
            return

        try:
            print(
                f"🔄 Applicando rotazione {self.current_rotation:.1f}° attorno al landmark 9 (glabella)"
            )

            # Trova il centro di rotazione (landmark 9 - glabella)
            rotation_center = self.get_rotation_center_from_landmarks()

            # Ruota SEMPRE dall'immagine originale non ruotata
            rotated_image = self.rotate_image_around_point(
                self.original_base_image, self.current_rotation, rotation_center
            )

            # Aggiorna l'immagine visualizzata sul canvas
            self.current_image_on_canvas = rotated_image
            self.current_image = rotated_image  # Mantieni coerenza

            # Ruota anche i landmarks se presenti (sempre dai landmarks originali)
            if self.original_base_landmarks is not None:
                old_landmarks = (
                    self.current_landmarks.copy() if self.current_landmarks else None
                )
                self.current_landmarks = self.rotate_landmarks_around_point(
                    self.original_base_landmarks, self.current_rotation, rotation_center
                )

                # DEBUG: Verifica aggiornamento landmarks
                if (
                    old_landmarks
                    and len(old_landmarks) > 9
                    and len(self.current_landmarks) > 9
                ):
                    print(
                        f"🎯 LANDMARK UPDATE: glabella {old_landmarks[9]} → {self.current_landmarks[9]}"
                    )
                else:
                    print(
                        f"🎯 LANDMARK UPDATE: landmarks aggiornati da {len(old_landmarks) if old_landmarks else 0} a {len(self.current_landmarks) if self.current_landmarks else 0}"
                    )

                # DEBUG CRITICO: Verifica rotazione landmarks (la glabella rimane fissa come centro)
                if (
                    self.original_base_landmarks
                    and self.current_landmarks
                    and len(self.original_base_landmarks) > 9
                    and len(self.current_landmarks) > 9
                ):
                    orig_glabella = self.original_base_landmarks[9]
                    curr_glabella = self.current_landmarks[9]
                    if orig_glabella == curr_glabella:
                        print("✅ Landmark 9 (glabella) rimane fisso come centro di rotazione - CORRETTO!")
                    else:
                        print(
                            f"⚠️ Centro di rotazione spostato: {orig_glabella} → {curr_glabella}"
                        )

            # *** NUOVO SISTEMA: Applica trasformazioni unificate alle grafiche
            self.transform_all_graphics()

            # NOTA: Non chiamare rotate_all_overlays_around_point() qui perché
            # gli overlay sono già stati ruotati dai metodi specifici sopra

            # Aggiorna la visualizzazione
            self.update_canvas_display()

            # Forza aggiornamento stato
            if hasattr(self, "status_bar"):
                self.status_bar.config(
                    text=f"Rotazione: {self.current_rotation:.1f}° (centro: glabella)"
                )

        except Exception as e:
            print(f"❌ Errore durante la rotazione: {e}")
            import traceback

            traceback.print_exc()

    def get_rotation_center_from_landmarks(self):
        """Ottiene il centro di rotazione dal landmark 9 (glabella) se disponibile, altrimenti usa centro immagine."""
        if (
            self.original_base_landmarks is not None
            and len(self.original_base_landmarks) > 9
        ):
            # Usa landmark 9 (glabella - punto tra le sopracciglia)
            glabella_x, glabella_y = self.original_base_landmarks[9]
            print(
                f"🎯 Centro rotazione: landmark 9 (glabella) a ({glabella_x:.1f}, {glabella_y:.1f})"
            )
            return (int(glabella_x), int(glabella_y))
        else:
            # Fallback al centro dell'immagine
            if self.original_base_image is not None:
                height, width = self.original_base_image.shape[:2]
                center = (width // 2, height // 2)
                print(f"⚠️ Landmarks non disponibili, uso centro immagine: {center}")
                return center
            else:
                print("❌ Impossibile determinare centro rotazione")
                return (0, 0)

    def rotate_image_around_point(self, image, angle, rotation_center):
        """Ruota l'immagine attorno a un punto specifico mantenendo le dimensioni originali del canvas."""
        if angle == 0:
            return image.copy()

        # Ottieni le dimensioni ORIGINALI dell'immagine
        height, width = image.shape[:2]
        center_x, center_y = rotation_center

        print(
            f"🔄 Rotazione {angle:.1f}° attorno a ({center_x}, {center_y}), dimensioni: {width}x{height}"
        )

        # Crea la matrice di rotazione attorno al punto specificato
        rotation_matrix = cv2.getRotationMatrix2D((center_x, center_y), angle, 1.0)

        # MANTIENI LE DIMENSIONI ORIGINALI - NON ESPANDERE
        # Questo farà sì che le parti che escono vengano automaticamente croppate
        rotated_image = cv2.warpAffine(
            image,
            rotation_matrix,
            (width, height),  # Usa le dimensioni ORIGINALI
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),  # Sfondo bianco per parti vuote
        )

        print(
            f"✅ Rotazione completata: dimensioni mantenute {width}x{height} (cropping automatico)"
        )
        return rotated_image

    def rotate_all_overlays_around_point(self, rotation_center):
        """Ruota tutti gli overlay (puntini verdi, punti selezionati, ecc.) attorno al punto di rotazione."""
        rotated_overlays = 0

        print(f"🔄 Rotazione overlay attorno al punto {rotation_center}")

        # 1. Ruota i punti selezionati dall'utente
        if hasattr(self, "selected_points") and self.selected_points:
            self.rotate_selected_points(rotation_center)
            rotated_overlays += len(self.selected_points)

        # 2. GREEN DOTS: Ora gestiti dal sistema graphics_registry 
        if hasattr(self, "green_dots_overlay") and self.green_dots_overlay is not None:
            rotated_overlays += 1

        # 3. NUOVO SISTEMA: Gli overlay sono ora gestiti automaticamente da transform_all_graphics()
        # tramite il graphics_registry - non serve rotazione manuale
        # Conta gli overlay che verranno trasformati automaticamente
        if hasattr(self, "measurement_overlays") and self.measurement_overlays:
            rotated_overlays += len(self.measurement_overlays)
        if hasattr(self, "preset_overlays") and self.preset_overlays:
            rotated_overlays += len([v for v in self.preset_overlays.values() if v is not None])

        if rotated_overlays > 0:
            print(
                f"✅ Ruotati {rotated_overlays} overlay attorno al punto {rotation_center}"
            )
        else:
            print("ℹ️ Nessun overlay da ruotare")

    # METODO RIMOSSO: rotate_measurement_overlays()
    # Gli overlay sono ora gestiti automaticamente dal sistema graphics_registry

    # METODO RIMOSSO: rotate_preset_overlays()
    # Gli overlay sono ora gestiti automaticamente dal sistema graphics_registry

    def draw_overlay_on_canvas(self, overlay):
        """Disegna un overlay sul canvas Tkinter e lo registra nel graphics_registry."""
        print(f"\n🎨 === DRAW_OVERLAY_ON_CANVAS CHIAMATO ===")
        print(f"🎨 Overlay ricevuto: {overlay}")
        
        if not overlay or "points" not in overlay or not overlay["points"]:
            print(f"⚠️ Overlay vuoto o senza punti: {overlay}")
            return
        
        overlay_type = overlay.get("type", "unknown")
        points = overlay["points"]
        print(f"🎨 Tipo: {overlay_type}, Punti: {len(points)} elementi")
        
        # Converti i punti da coordinate immagine a coordinate canvas per il disegno
        canvas_coords = []
        image_coords = []  # Mantieni le coordinate immagine per la registrazione
        
        for point in points:
            # Gestisce overlay di tipo "area" che contengono liste di poligoni
            if overlay_type == "area" and isinstance(point, list) and len(point) > 0 and isinstance(point[0], (list, tuple)):
                # È un poligono (lista di punti)
                for sub_point in point:
                    if isinstance(sub_point, (list, tuple)) and len(sub_point) >= 2:
                        img_x, img_y = sub_point[0], sub_point[1]
                        
                        image_coords.extend([img_x, img_y])
                        
                        # Converti a coordinate canvas per il disegno
                        canvas_x, canvas_y = self.convert_image_to_canvas_coords(img_x, img_y)
                        canvas_coords.extend([canvas_x, canvas_y])
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                # È un punto semplice (non area)
                img_x, img_y = point[0], point[1]
                
                image_coords.extend([img_x, img_y])
                
                # Converti a coordinate canvas per il disegno
                canvas_x, canvas_y = self.convert_image_to_canvas_coords(img_x, img_y)
                canvas_coords.extend([canvas_x, canvas_y])
        
        if len(canvas_coords) < 4:  # Serve almeno 2 punti (4 coordinate)
            print(f"⚠️ Coordinate insufficienti: {len(canvas_coords)} (serve almeno 4)")
            return
        
        # Disegna l'overlay sul canvas in base al tipo
        canvas_item = None
        
        if overlay_type == "distance" and len(canvas_coords) >= 4:
            # Disegna una linea per le distanze
            canvas_item = self.canvas.create_line(
                canvas_coords[0], canvas_coords[1],
                canvas_coords[2], canvas_coords[3],
                fill="red", width=2, tags="measurement_overlay"
            )
        
        elif overlay_type == "angle" and len(canvas_coords) >= 6:
            # Disegna linee per gli angoli (connette i 3 punti)
            line1 = self.canvas.create_line(
                canvas_coords[0], canvas_coords[1],
                canvas_coords[2], canvas_coords[3],
                fill="green", width=2, tags="measurement_overlay"
            )
            line2 = self.canvas.create_line(
                canvas_coords[2], canvas_coords[3],
                canvas_coords[4], canvas_coords[5],
                fill="green", width=2, tags="measurement_overlay"
            )
            canvas_item = line1  # Registra il primo elemento
            
            # Registra anche la seconda linea
            if len(image_coords) >= 6:
                self.register_graphic(
                    line2, "line",
                    [image_coords[2], image_coords[3], image_coords[4], image_coords[5]],
                    {"fill": "green", "width": 2}, is_overlay=True
                )
        
        elif overlay_type == "area":
            # Per le aree, potremmo avere multipli poligoni
            if overlay_type == "area" and isinstance(points[0], list) and len(points) > 1:
                # Multipli poligoni (es. sopracciglio sx + dx)
                colors = overlay.get("colors", [(255, 255, 0), (0, 255, 255)])  # Default giallo e ciano
                
                for poly_idx, polygon in enumerate(points):
                    poly_canvas_coords = []
                    poly_image_coords = []
                    
                    for point in polygon:
                        if isinstance(point, (list, tuple)) and len(point) >= 2:
                            img_x, img_y = point[0], point[1]
                            poly_image_coords.extend([img_x, img_y])
                            canvas_x, canvas_y = self.convert_image_to_canvas_coords(img_x, img_y)
                            poly_canvas_coords.extend([canvas_x, canvas_y])
                    
                    if len(poly_canvas_coords) >= 6:  # Almeno 3 punti per un poligono
                        # Colore diverso per ogni poligono
                        color_rgb = colors[poly_idx] if poly_idx < len(colors) else (255, 255, 0)
                        color_name = f"#{color_rgb[0]:02x}{color_rgb[1]:02x}{color_rgb[2]:02x}"
                        
                        poly_id = self.canvas.create_polygon(
                            poly_canvas_coords, outline=color_name, fill="", width=2,
                            tags="measurement_overlay"
                        )
                        
                        # Registra ogni poligono separatamente
                        self.register_graphic(
                            poly_id, "polygon", poly_image_coords,
                            {"outline": color_name, "fill": "", "width": 2}, is_overlay=True
                        )
                        
                        # DEBUG e z-order per poligoni area
                        bbox = self.canvas.bbox(poly_id)
                        print(f"🔍 POLIGONO DEBUG: ID={poly_id}, bbox={bbox}, colore={color_name}")
                        
                        # IMPORTANTE: Porta il poligono in primo piano
                        self.canvas.tag_raise(poly_id)
                        
                        if poly_idx == 0:  # Salva il primo come canvas_item principale
                            canvas_item = poly_id
                        

            elif len(canvas_coords) >= 6:  # Singolo poligono
                canvas_item = self.canvas.create_polygon(
                    canvas_coords, outline="yellow", fill="", width=2, 
                    tags="measurement_overlay"
                )
        
        # Registra l'elemento principale nel graphics_registry SOLO se non è un overlay area multiplo
        if canvas_item and len(image_coords) >= 4:
            # 🚨 FIX: Non registrare di nuovo gli overlay area multipli (già registrati individualmente)
            if overlay_type == "area" and isinstance(points[0], list) and len(points) > 1:
                # Skip - poligoni già registrati individualmente sopra
                pass
            else:
                # Registra normalmente per distance, angle, area singola
                if overlay_type == "distance":
                    graphic_type = "line"
                elif overlay_type == "area":
                    graphic_type = "polygon"
                else:
                    graphic_type = "line"
                
                self.register_graphic(
                    canvas_item, graphic_type, image_coords,
                    {"fill": "red" if overlay_type == "distance" else "yellow", "width": 2}, is_overlay=True
                )
            
            # Salva il riferimento nell'overlay per poterlo rimuovere
            overlay["canvas_item"] = canvas_item
            
            # DEBUG: Verifica posizionamento e z-order
            bbox = self.canvas.bbox(canvas_item)
            z_order = self.canvas.find_above(canvas_item)
            print(f"🔍 OVERLAY CREATO: ID={canvas_item}, bbox={bbox}, sopra={z_order}")
            
            # IMPORTANTE: Porta l'overlay in primo piano
            self.canvas.tag_raise(canvas_item)
            print(f"✅ Overlay {canvas_item} portato in primo piano")
            
            # Verifica se l'overlay è effettivamente sul canvas
            all_items = self.canvas.find_all()
            print(f"📊 Canvas items totali: {len(all_items)}, ultimo ID: {max(all_items) if all_items else 'nessuno'}")
            
        else:
            print(f"❌ OVERLAY NON CREATO: canvas_item={canvas_item}, coords_len={len(canvas_coords)}")
        
        print(f"🎨 === FINE DRAW_OVERLAY_ON_CANVAS ===\n")
            


    def rotate_selected_points(self, rotation_center):
        """Ruota i punti selezionati attorno al centro di rotazione."""
        if not hasattr(self, "original_selected_points"):
            # Salva i punti originali al primo utilizzo
            self.original_selected_points = (
                self.selected_points.copy() if self.selected_points else []
            )

        if not self.original_selected_points:
            return

        # Calcola l'angolo in radianti
        # INVERTO l'angolo per coerenza con gli altri disegni canvas
        inverted_angle = -self.current_rotation
        angle_rad = np.radians(inverted_angle)
        cos_angle = np.cos(angle_rad)
        sin_angle = np.sin(angle_rad)

        # rotation_center è già in coordinate canvas, ma i punti selezionati sono in coordinate immagine
        # Dobbiamo ottenere il centro di rotazione in coordinate immagine per i punti selezionati
        image_rotation_center = self.get_rotation_center_from_landmarks()
        center_x, center_y = image_rotation_center

        rotated_points = []
        for orig_x, orig_y in self.original_selected_points:
            # Ruota il punto attorno al centro (tutto in coordinate immagine)
            new_x, new_y = self.rotate_point_around_center(
                orig_x, orig_y, center_x, center_y, cos_angle, sin_angle
            )
            rotated_points.append((int(new_x), int(new_y)))

        self.selected_points = rotated_points
        print(
            f"🔄 Ruotati {len(rotated_points)} punti selezionati in coordinate immagine"
        )

    # METODO RIMOSSO: rotate_green_dots_overlay()
    # I green dots sono ora gestiti dal sistema graphics_registry

    def draw_green_dots_on_canvas(self, results):
        """Disegna i green dots sul canvas usando il sistema graphics_registry."""
        print(f"🟢 === DRAW_GREEN_DOTS_ON_CANVAS CHIAMATO ===")
        print(f"🟢 Results ricevuti: {type(results)}")
        
        # 🔧 FIX: Adattamento ai dati reali del green dots processor
        if not results:
            print("⚠️ Nessun risultato green dots")
            return
            
        # Controlla se abbiamo dati di coordinate o overlay
        green_dots_data = None
        if "coordinates" in results and results["coordinates"]:
            green_dots_data = results["coordinates"]
        elif "overlay" in results and results["overlay"]:
            green_dots_data = results["overlay"]
        elif "left_polygon" in results and "right_polygon" in results:
            # Formato legacy
            green_dots_data = {
                "left_polygon": results["left_polygon"],
                "right_polygon": results["right_polygon"]
            }
        
        if not green_dots_data:
            print("⚠️ Dati poligoni green dots mancanti")
            print(f"   Keys disponibili: {results.keys() if results else 'Nessuna'}")
            return
        
        # Estrai i poligoni (adattabile a diversi formati)
        left_polygon = None
        right_polygon = None
        
        if isinstance(green_dots_data, dict):
            left_polygon = green_dots_data.get("left_polygon") or green_dots_data.get("left") or green_dots_data.get("sx")
            right_polygon = green_dots_data.get("right_polygon") or green_dots_data.get("right") or green_dots_data.get("dx")
        elif isinstance(green_dots_data, list) and len(green_dots_data) >= 2:
            left_polygon = green_dots_data[0]
            right_polygon = green_dots_data[1]
        
        # 🔧 FALLBACK: Adattamento alla struttura del green_dots_processor.py
        if not left_polygon and not right_polygon:
            # Cerca nei gruppi (struttura reale del processor)
            if "groups" in results and isinstance(results["groups"], dict):
                left_group = results["groups"].get("Sx", [])  # Chiave corretta!
                right_group = results["groups"].get("Dx", [])  # Chiave corretta!
                
                # Converte da formato dict a coordinate semplici
                if left_group and isinstance(left_group[0], dict):
                    left_polygon = [(p["x"], p["y"]) for p in left_group]
                else:
                    left_polygon = left_group
                    
                if right_group and isinstance(right_group[0], dict):
                    right_polygon = [(p["x"], p["y"]) for p in right_group]
                else:
                    right_polygon = right_group
            
            # Cerca anche in coordinates come backup
            elif "coordinates" in results and isinstance(results["coordinates"], dict):
                left_polygon = results["coordinates"].get("Sx", [])
                right_polygon = results["coordinates"].get("Dx", [])
        
        # Debug per capire cosa abbiamo ricevuto
        print(f"🟢 DEBUG DATI GREEN DOTS:")
        print(f"   results keys: {list(results.keys())}")
        if "groups" in results:
            print(f"   groups keys: {list(results['groups'].keys()) if isinstance(results['groups'], dict) else 'not dict'}")
        if "coordinates" in results:
            print(f"   coordinates keys: {list(results['coordinates'].keys()) if isinstance(results['coordinates'], dict) else 'not dict'}")
        print(f"   left_polygon: {len(left_polygon) if left_polygon else 0} punti")
        print(f"   right_polygon: {len(right_polygon) if right_polygon else 0} punti")
        
        if not left_polygon and not right_polygon:
            print("⚠️ Nessun dato green dots trovato per disegnare poligoni")
            return
        
        left_count = len(left_polygon) if left_polygon else 0
        right_count = len(right_polygon) if right_polygon else 0
        print(f"🟢 Disegno green dots: sx={left_count} punti, dx={right_count} punti")
        
        # Disegna poligono sinistro (verde chiaro) 
        if left_polygon and len(left_polygon) >= 3:  # 🔧 FIX: Almeno 3 punti (non 6!)
            # Converti a coordinate canvas
            canvas_coords = []
            image_coords = []
            
            for point in left_polygon:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    img_x, img_y = point[0], point[1]
                    image_coords.extend([img_x, img_y])
                    canvas_x, canvas_y = self.convert_image_to_canvas_coords(img_x, img_y)
                    canvas_coords.extend([canvas_x, canvas_y])
            
            if len(canvas_coords) >= 6:
                left_poly_id = self.canvas.create_polygon(
                    canvas_coords, outline="green", fill="lightgreen", 
                    width=2, stipple="gray25", tags="green_dots_overlay"
                )
                
                # Registra nel graphics_registry come overlay
                self.register_graphic(
                    left_poly_id, "polygon", image_coords,
                    {"outline": "green", "fill": "lightgreen", "width": 2}, is_overlay=True
                )
                print(f"✅ Poligono sinistro disegnato: {left_poly_id}")
                print(f"   Canvas coords: {canvas_coords[:8]}...")
                print(f"   Image coords: {image_coords[:8]}...")
                
                # Verifica immediata posizione
                bbox = self.canvas.bbox(left_poly_id)
                print(f"   BBox sul canvas: {bbox}")
        
        # Disegna poligono destro (verde scuro)
        if right_polygon and len(right_polygon) >= 3:  # 🔧 FIX: Almeno 3 punti (non 6!)
            # Converti a coordinate canvas
            canvas_coords = []
            image_coords = []
            
            for point in right_polygon:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    img_x, img_y = point[0], point[1]
                    image_coords.extend([img_x, img_y])
                    canvas_x, canvas_y = self.convert_image_to_canvas_coords(img_x, img_y)
                    canvas_coords.extend([canvas_x, canvas_y])
            
            if len(canvas_coords) >= 6:
                right_poly_id = self.canvas.create_polygon(
                    canvas_coords, outline="darkgreen", fill="green",
                    width=2, stipple="gray25", tags="green_dots_overlay"
                )
                
                # Registra nel graphics_registry come overlay
                self.register_graphic(
                    right_poly_id, "polygon", image_coords,
                    {"outline": "darkgreen", "fill": "green", "width": 2}, is_overlay=True
                )
                print(f"✅ Poligono destro disegnato: {right_poly_id}")
                print(f"   Canvas coords: {canvas_coords[:8]}...")
                print(f"   Image coords: {image_coords[:8]}...")
                
                # Verifica immediata posizione
                bbox = self.canvas.bbox(right_poly_id)
                print(f"   BBox sul canvas: {bbox}")
        
        # 🏷️ NUOVO: Disegna le etichette per i puntini verdi
        self.draw_green_dots_labels(results)

    def draw_green_dots_labels(self, results):
        """Disegna le etichette per i puntini verdi rilevati con nomi specifici e posizionamento esterno."""
        print(f"🏷️ === DRAW_GREEN_DOTS_LABELS CHIAMATO ===")
        
        if not results or "groups" not in results:
            print("⚠️ Nessun dato per le etichette green dots")
            return
            
        groups = results["groups"]
        
        # Mappatura dei nomi per gruppo sinistro (SC1, SA0, SA, SC, SB) - SC1 e SC invertiti
        left_labels = ["SC1", "SA0", "SA", "SC", "SB"]
        
        # Mappatura dei nomi per gruppo destro (DC1, DB, DC, DA, DA0)
        right_labels = ["DC1", "DB", "DC", "DA", "DA0"]
        
        # Disegna etichette per gruppo sinistro
        if "Sx" in groups and groups["Sx"]:
            left_points = groups["Sx"]
            
            # Calcola il centroide del poligono sinistro per determinare la direzione esterna
            if len(left_points) > 2:
                centroid_x = sum(p["x"] for p in left_points) / len(left_points)
                centroid_y = sum(p["y"] for p in left_points) / len(left_points)
            else:
                centroid_x = centroid_y = 0
                
            for i, point in enumerate(left_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    # Usa il nome personalizzato se disponibile, altrimenti fallback
                    label_text = left_labels[i] if i < len(left_labels) else f"Sx-{i+1}"
                    
                    # Calcola offset per posizionare l'etichetta esternamente al poligono
                    # 🎯 SPECIALE: SC va sempre sotto il punto
                    if label_text == "SC":
                        offset_x = 0
                        offset_y = 20  # Sotto il punto
                    else:
                        # Direzione dal centroide verso il punto, estesa ulteriormente
                        if centroid_x != 0 or centroid_y != 0:
                            dx = point["x"] - centroid_x
                            dy = point["y"] - centroid_y
                            distance = np.sqrt(dx*dx + dy*dy)
                            if distance > 0:
                                # Normalizza e scala per offset di 15 pixel (avvicinato)
                                offset_x = (dx / distance) * 15
                                offset_y = (dy / distance) * 15
                            else:
                                offset_x, offset_y = -15, -10  # Fallback
                        else:
                            offset_x, offset_y = -15, -10  # Fallback per sinistra
                    
                    # Coordinate immagine per l'etichetta
                    label_img_x = point["x"] + offset_x
                    label_img_y = point["y"] + offset_y
                    
                    # Converti coordinate immagine in coordinate canvas
                    canvas_x, canvas_y = self.convert_image_to_canvas_coords(label_img_x, label_img_y)
                    
                    # Disegna SOLO il testo etichetta (nessun riquadro)
                    text_id = self.canvas.create_text(
                        canvas_x, canvas_y,
                        text=label_text, fill="green", font=("Arial", 10, "bold"),
                        tags="green_dots_labels"
                    )
                    
                    # Registra nel graphics_registry
                    self.register_graphic(
                        text_id, "text",
                        [label_img_x, label_img_y],
                        {"text": label_text, "fill": "green", "font": ("Arial", 10, "bold")}, is_overlay=True
                    )
                    
                    print(f"✅ Etichetta sinistra {i+1}: {label_text} a ({canvas_x}, {canvas_y}) [offset: {offset_x:.1f}, {offset_y:.1f}]")
        
        # Disegna etichette per gruppo destro
        if "Dx" in groups and groups["Dx"]:
            right_points = groups["Dx"]
            
            # Calcola il centroide del poligono destro per determinare la direzione esterna
            if len(right_points) > 2:
                centroid_x = sum(p["x"] for p in right_points) / len(right_points)
                centroid_y = sum(p["y"] for p in right_points) / len(right_points)
            else:
                centroid_x = centroid_y = 0
                
            for i, point in enumerate(right_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    # Usa il nome personalizzato se disponibile, altrimenti fallback
                    label_text = right_labels[i] if i < len(right_labels) else f"Dx-{i+1}"
                    
                    # Calcola offset per posizionare l'etichetta esternamente al poligono
                    # 🎯 SPECIALE: DC va sempre sotto il punto
                    if label_text == "DC":
                        offset_x = 0
                        offset_y = 20  # Sotto il punto
                    else:
                        if centroid_x != 0 or centroid_y != 0:
                            dx = point["x"] - centroid_x
                            dy = point["y"] - centroid_y
                            distance = np.sqrt(dx*dx + dy*dy)
                            if distance > 0:
                                # Normalizza e scala per offset di 15 pixel (avvicinato)
                                offset_x = (dx / distance) * 15
                                offset_y = (dy / distance) * 15
                            else:
                                offset_x, offset_y = 15, -10  # Fallback
                        else:
                            offset_x, offset_y = 15, -10  # Fallback per destra
                    
                    # Coordinate immagine per l'etichetta
                    label_img_x = point["x"] + offset_x
                    label_img_y = point["y"] + offset_y
                    
                    # Converti coordinate immagine in coordinate canvas
                    canvas_x, canvas_y = self.convert_image_to_canvas_coords(label_img_x, label_img_y)
                    
                    # Disegna SOLO il testo etichetta (nessun riquadro)
                    text_id = self.canvas.create_text(
                        canvas_x, canvas_y,
                        text=label_text, fill="darkgreen", font=("Arial", 10, "bold"),
                        tags="green_dots_labels"
                    )
                    
                    # Registra nel graphics_registry
                    self.register_graphic(
                        text_id, "text",
                        [label_img_x, label_img_y],
                        {"text": label_text, "fill": "darkgreen", "font": ("Arial", 10, "bold")}, is_overlay=True
                    )
                    
                    print(f"✅ Etichetta destra {i+1}: {label_text} a ({canvas_x}, {canvas_y}) [offset: {offset_x:.1f}, {offset_y:.1f}]")

    def calculate_green_dots_axis_distances(self, results):
        """Calcola le distanze perpendicolari di ogni punto verde dall'asse di simmetria."""
        print(f"📏 === CALCOLO DISTANZE DALL'ASSE DI SIMMETRIA ===")
        
        if not results or "groups" not in results:
            print("⚠️ Nessun dato green dots per calcolo distanze")
            return
            
        # Verifica che abbiamo i landmarks per l'asse di simmetria
        if not self.current_landmarks or len(self.current_landmarks) <= 164:
            print("⚠️ Landmarks non disponibili per calcolo asse di simmetria")
            # Prova a rilevare i landmarks se non ci sono
            self.detect_landmarks()
            if not self.current_landmarks or len(self.current_landmarks) <= 164:
                print("⚠️ Impossibile calcolare distanze senza landmarks")
                return
        
        # Ottieni i punti dell'asse di simmetria (glabella e philtrum)
        glabella = self.current_landmarks[9]   # Punto superiore
        philtrum = self.current_landmarks[164] # Punto inferiore
        
        print(f"🎯 Asse di simmetria: Glabella{glabella} -> Philtrum{philtrum}")
        
        groups = results["groups"]
        
        # Mappatura dei nomi per gruppo sinistro (SC1, SA0, SA, SC, SB) - SC1 e SC invertiti
        left_labels = ["SC1", "SA0", "SA", "SC", "SB"]
        
        # Mappatura dei nomi per gruppo destro (DC1, DB, DC, DA, DA0)
        right_labels = ["DC1", "DB", "DC", "DA", "DA0"]
        
        # Calcola distanze per gruppo sinistro
        if "Sx" in groups and groups["Sx"]:
            left_points = groups["Sx"]
            for i, point in enumerate(left_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    label_name = left_labels[i] if i < len(left_labels) else f"Sx-{i+1}"
                    distance = self.calculate_perpendicular_distance_to_line(
                        (point["x"], point["y"]), glabella, philtrum
                    )
                    
                    # Aggiungi alla tabella delle misurazioni
                    self.add_measurement(
                        f"Distanza {label_name} da Asse", f"{distance:.2f}", "px"
                    )
                    
                    print(f"📏 {label_name}: distanza = {distance:.2f} px")
        
        # Calcola distanze per gruppo destro
        if "Dx" in groups and groups["Dx"]:
            right_points = groups["Dx"]
            for i, point in enumerate(right_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    label_name = right_labels[i] if i < len(right_labels) else f"Dx-{i+1}"
                    distance = self.calculate_perpendicular_distance_to_line(
                        (point["x"], point["y"]), glabella, philtrum
                    )
                    
                    # Aggiungi alla tabella delle misurazioni
                    self.add_measurement(
                        f"Distanza {label_name} da Asse", f"{distance:.2f}", "px"
                    )
                    
                    print(f"📏 {label_name}: distanza = {distance:.2f} px")
        
        # 📊 NUOVO: Calcola differenze tra coppie simmetriche
        self.calculate_symmetric_pairs_differences(groups, glabella, philtrum, left_labels, right_labels)

    def calculate_symmetric_pairs_differences(self, groups, glabella, philtrum, left_labels, right_labels):
        """Calcola e riporta le differenze tra coppie simmetriche di punti green dots."""
        print(f"📊 === CALCOLO DIFFERENZE COPPIE SIMMETRICHE ===")
        
        # Definisci le coppie simmetriche: (label_sinistro, label_destro)
        pairs = [
            ("SA", "DA"),     # SA/DA
            ("SA0", "DA0"),   # SA0/DA0  
            ("SC1", "DC1"),   # SC1/DC1
            ("SC", "DC"),     # SC/DC
            ("SB", "DB")      # SB/DB
        ]
        
        # Calcola le distanze per entrambi i gruppi
        left_distances = {}
        right_distances = {}
        
        # Distanze gruppo sinistro
        if "Sx" in groups and groups["Sx"]:
            left_points = groups["Sx"]
            for i, point in enumerate(left_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    label_name = left_labels[i] if i < len(left_labels) else f"Sx-{i+1}"
                    distance = self.calculate_perpendicular_distance_to_line(
                        (point["x"], point["y"]), glabella, philtrum
                    )
                    left_distances[label_name] = distance
        
        # Distanze gruppo destro
        if "Dx" in groups and groups["Dx"]:
            right_points = groups["Dx"]
            for i, point in enumerate(right_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    label_name = right_labels[i] if i < len(right_labels) else f"Dx-{i+1}"
                    distance = self.calculate_perpendicular_distance_to_line(
                        (point["x"], point["y"]), glabella, philtrum
                    )
                    right_distances[label_name] = distance
        
        # Calcola e riporta differenze per ogni coppia
        for left_label, right_label in pairs:
            if left_label in left_distances and right_label in right_distances:
                left_dist = left_distances[left_label]
                right_dist = right_distances[right_label]
                difference = abs(left_dist - right_dist)
                
                # Aggiungi differenza alla tabella
                self.add_measurement(
                    f"Differenza {left_label}-{right_label}", f"{difference:.2f}", "px"
                )
                
                # Aggiungi descrizioni comparative
                if left_dist > right_dist:
                    # Il punto sinistro è più esterno
                    self.add_measurement(
                        f"{left_label} vs {right_label}", 
                        f"{left_label}= più esterno di {difference:.1f} px rispetto a {right_label}", 
                        ""
                    )
                    self.add_measurement(
                        f"{right_label} vs {left_label}", 
                        f"{right_label}= più interno di {difference:.1f} px rispetto a {left_label}", 
                        ""
                    )
                elif right_dist > left_dist:
                    # Il punto destro è più esterno
                    self.add_measurement(
                        f"{right_label} vs {left_label}", 
                        f"{right_label}= più esterno di {difference:.1f} px rispetto a {left_label}", 
                        ""
                    )
                    self.add_measurement(
                        f"{left_label} vs {right_label}", 
                        f"{left_label}= più interno di {difference:.1f} px rispetto a {right_label}", 
                        ""
                    )
                else:
                    # Distanze uguali
                    self.add_measurement(
                        f"{left_label}-{right_label} Simmetria", 
                        f"{left_label} e {right_label}= equidistanti dall'asse", 
                        ""
                    )
                
                print(f"📊 Coppia {left_label}/{right_label}: {left_dist:.2f} vs {right_dist:.2f} px (diff: {difference:.2f})")
        
        # 📏 NUOVO: Calcola differenze in altezza tra coppie
        self.calculate_height_differences(groups, glabella, philtrum, left_labels, right_labels, pairs)

    def calculate_height_differences(self, groups, glabella, philtrum, left_labels, right_labels, pairs):
        """Calcola le differenze in altezza tra coppie simmetriche su rette parallele all'asse."""
        print(f"📏 === CALCOLO DIFFERENZE IN ALTEZZA ===")
        
        # Calcola il vettore direzione dell'asse di simmetria
        axis_dx = philtrum[0] - glabella[0]
        axis_dy = philtrum[1] - glabella[1]
        
        # 🔍 VERIFICA: Il sistema di coordinate ruotato
        axis_length = np.sqrt(axis_dx * axis_dx + axis_dy * axis_dy)
        if axis_length > 0:
            # Vettore unitario dell'asse (direzione "altezza")
            axis_unit_x = axis_dx / axis_length
            axis_unit_y = axis_dy / axis_length
            
            # Vettore unitario perpendicolare all'asse (direzione "larghezza") 
            perp_unit_x = -axis_unit_y  # Ruota di 90° in senso orario
            perp_unit_y = axis_unit_x
            
            print(f"📐 SISTEMA COORDINATE RUOTATO:")
            print(f"   Asse altezza (parallelo): ({axis_unit_x:.3f}, {axis_unit_y:.3f})")
            print(f"   Asse larghezza (perpendicolare): ({perp_unit_x:.3f}, {perp_unit_y:.3f})")
            print(f"   → Le misure di altezza seguono il vettore parallelo all'asse")
        
        # Ottieni le coordinate per entrambi i gruppi
        left_points_coords = {}
        right_points_coords = {}
        
        # Coordinate gruppo sinistro
        if "Sx" in groups and groups["Sx"]:
            left_points = groups["Sx"]
            for i, point in enumerate(left_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    label_name = left_labels[i] if i < len(left_labels) else f"Sx-{i+1}"
                    left_points_coords[label_name] = (point["x"], point["y"])
        
        # Coordinate gruppo destro  
        if "Dx" in groups and groups["Dx"]:
            right_points = groups["Dx"]
            for i, point in enumerate(right_points):
                if isinstance(point, dict) and "x" in point and "y" in point:
                    label_name = right_labels[i] if i < len(right_labels) else f"Dx-{i+1}"
                    right_points_coords[label_name] = (point["x"], point["y"])
        
        # Calcola differenze in altezza per ogni coppia
        for left_label, right_label in pairs:
            if left_label in left_points_coords and right_label in right_points_coords:
                left_point = left_points_coords[left_label]
                right_point = right_points_coords[right_label]
                
                # Calcola l'altezza di ogni punto lungo la direzione dell'asse
                left_height = self.calculate_height_along_axis(left_point, glabella, axis_dx, axis_dy)
                right_height = self.calculate_height_along_axis(right_point, glabella, axis_dx, axis_dy)
                
                # 🔍 VERIFICA: Calcola anche la componente perpendicolare per debug
                left_perp = self.calculate_perpendicular_component(left_point, glabella, axis_dx, axis_dy)
                right_perp = self.calculate_perpendicular_component(right_point, glabella, axis_dx, axis_dy)
                
                print(f"🔍 Verifica coppia {left_label}/{right_label}:")
                print(f"   {left_label}: altezza={left_height:.2f}, larghezza={left_perp:.2f}")
                print(f"   {right_label}: altezza={right_height:.2f}, larghezza={right_perp:.2f}")
                print(f"   → Differenza ALTEZZA (parallela all'asse): {abs(left_height - right_height):.2f}")
                print(f"   → Differenza LARGHEZZA (perpendicolare): {abs(left_perp - right_perp):.2f}")
                
                # Differenza in altezza (valori positivi = più alto, negativi = più basso)
                height_difference = left_height - right_height
                abs_height_diff = abs(height_difference)
                
                # Aggiungi differenza numerica alla tabella
                self.add_measurement(
                    f"Differenza Altezza {left_label}-{right_label}", f"{abs_height_diff:.2f}", "px"
                )
                
                # Aggiungi descrizioni comparative di altezza
                if height_difference > 0:
                    # Il punto sinistro è più alto
                    self.add_measurement(
                        f"Altezza {left_label} vs {right_label}",
                        f"{left_label}= più alto di {abs_height_diff:.1f} px rispetto a {right_label}",
                        ""
                    )
                    self.add_measurement(
                        f"Altezza {right_label} vs {left_label}",
                        f"{right_label}= più basso di {abs_height_diff:.1f} px rispetto a {left_label}",
                        ""
                    )
                elif height_difference < 0:
                    # Il punto destro è più alto
                    self.add_measurement(
                        f"Altezza {right_label} vs {left_label}",
                        f"{right_label}= più alto di {abs_height_diff:.1f} px rispetto a {left_label}",
                        ""
                    )
                    self.add_measurement(
                        f"Altezza {left_label} vs {right_label}",
                        f"{left_label}= più basso di {abs_height_diff:.1f} px rispetto a {right_label}",
                        ""
                    )
                else:
                    # Stessa altezza
                    self.add_measurement(
                        f"Altezza {left_label}-{right_label}",
                        f"{left_label} e {right_label}= stessa altezza",
                        ""
                    )
                
                print(f"📏 Altezza coppia {left_label}/{right_label}: {left_height:.2f} vs {right_height:.2f} px (diff: {height_difference:.2f})")

    def calculate_height_along_axis(self, point, axis_start, axis_dx, axis_dy):
        """
        Calcola l'altezza di un punto proiettata lungo la direzione dell'asse di simmetria.
        IMPORTANTE: Questo calcolo è relativo alla rotazione dell'asse, NON a coordinate assolute.
        
        Args:
            point: Tupla (x, y) del punto da misurare
            axis_start: Tupla (x, y) del punto iniziale dell'asse (glabella)
            axis_dx, axis_dy: Componenti del vettore direzione dell'asse
            
        Returns:
            float: Altezza del punto lungo l'asse (positivo = verso philtrum)
        """
        # Vettore dal punto iniziale dell'asse al punto da misurare
        point_dx = point[0] - axis_start[0]
        point_dy = point[1] - axis_start[1]
        
        # Normalizza il vettore direzione dell'asse (QUESTO GESTISCE LA ROTAZIONE!)
        axis_length = np.sqrt(axis_dx * axis_dx + axis_dy * axis_dy)
        if axis_length == 0:
            return 0.0
            
        axis_unit_x = axis_dx / axis_length
        axis_unit_y = axis_dy / axis_length
        
        # 🔍 DEBUG: Calcolo dell'angolo dell'asse per verifica
        axis_angle_rad = np.arctan2(axis_dy, axis_dx)
        axis_angle_deg = np.degrees(axis_angle_rad)
        
        # Proiezione del punto sulla direzione dell'asse (prodotto scalare)
        # QUESTA È LA COMPONENTE DEL PUNTO LUNGO L'ASSE ROTATO
        projection = point_dx * axis_unit_x + point_dy * axis_unit_y
        
        # Debug per la prima chiamata (evita spam)
        if not hasattr(self, '_axis_debug_shown'):
            print(f"🔍 DEBUG ASSE DI SIMMETRIA:")
            print(f"   Glabella: {axis_start}")
            print(f"   Direzione: ({axis_dx:.1f}, {axis_dy:.1f})")
            print(f"   Vettore unitario: ({axis_unit_x:.3f}, {axis_unit_y:.3f})")
            print(f"   Angolo asse: {axis_angle_deg:.1f}°")
            print(f"   → Le altezze sono calcolate LUNGO questo asse inclinato")
            self._axis_debug_shown = True
        
        return projection

    def calculate_perpendicular_component(self, point, axis_start, axis_dx, axis_dy):
        """
        Calcola la componente perpendicolare all'asse di simmetria (per verifica).
        
        Args:
            point: Tupla (x, y) del punto da misurare
            axis_start: Tupla (x, y) del punto iniziale dell'asse (glabella)
            axis_dx, axis_dy: Componenti del vettore direzione dell'asse
            
        Returns:
            float: Componente perpendicolare (larghezza nel sistema ruotato)
        """
        # Vettore dal punto iniziale dell'asse al punto da misurare
        point_dx = point[0] - axis_start[0]
        point_dy = point[1] - axis_start[1]
        
        # Normalizza il vettore direzione dell'asse
        axis_length = np.sqrt(axis_dx * axis_dx + axis_dy * axis_dy)
        if axis_length == 0:
            return 0.0
            
        # Vettore perpendicolare unitario (ruotato 90° in senso orario)
        perp_unit_x = -axis_dy / axis_length
        perp_unit_y = axis_dx / axis_length
        
        # Proiezione del punto sulla direzione perpendicolare
        perpendicular_component = point_dx * perp_unit_x + point_dy * perp_unit_y
        
        return perpendicular_component

    def calculate_perpendicular_distance_to_line(self, point, line_point1, line_point2):
        """
        Calcola la distanza perpendicolare di un punto da una linea definita da due punti.
        
        Args:
            point: Tupla (x, y) del punto
            line_point1: Tupla (x, y) del primo punto della linea
            line_point2: Tupla (x, y) del secondo punto della linea
            
        Returns:
            float: Distanza perpendicolare in pixel
        """
        # Formula per calcolo distanza punto-linea
        # d = |ax + by + c| / sqrt(a² + b²)
        # dove la linea è ax + by + c = 0
        
        x0, y0 = point
        x1, y1 = line_point1
        x2, y2 = line_point2
        
        # Calcola coefficienti della linea ax + by + c = 0
        # Partendo da due punti: (y2-y1)x - (x2-x1)y + (x2-x1)y1 - (y2-y1)x1 = 0
        a = y2 - y1
        b = x1 - x2
        c = (x2 - x1) * y1 - (y2 - y1) * x1
        
        # Calcola distanza
        numerator = abs(a * x0 + b * y0 + c)
        denominator = np.sqrt(a * a + b * b)
        
        if denominator == 0:
            return 0.0  # Linea degenere
            
        distance = numerator / denominator
        return distance

    def reset_all_overlays(self):
        """Resetta tutti gli overlay alle posizioni originali."""
        # Resetta punti selezionati
        if hasattr(self, "original_selected_points"):
            self.selected_points = (
                self.original_selected_points.copy()
                if self.original_selected_points
                else []
            )
            self.original_selected_points = []
            print("🔄 Punti selezionati resettati alle posizioni originali")

        # Resetta measurement overlays
        if hasattr(self, "original_measurement_overlays") and self.original_measurement_overlays:
            for i, original_overlay in enumerate(self.original_measurement_overlays):
                if i < len(self.measurement_overlays):
                    self.measurement_overlays[i]["points"] = original_overlay["points"].copy()
            self.original_measurement_overlays = []
            print("🔄 Overlay di misurazione resettati alle posizioni originali")

        # Resetta preset overlays
        if hasattr(self, "original_preset_overlays"):
            for preset_name, original_overlay in self.original_preset_overlays.items():
                if (original_overlay is not None and 
                    self.preset_overlays.get(preset_name) is not None):
                    self.preset_overlays[preset_name]["points"] = original_overlay["points"].copy()
            # Resetta il dizionario originale
            self.original_preset_overlays = {
                "asse_naso": None, "larghezza_naso": None, "angolo_nasale": None,
                "sporgenza_mento": None, "larghezza_bocca": None, "altezza_bocca": None,
                "simmetria_sopracciglia": None, "forma_occhi": None,
            }
            print("🔄 Overlay predefiniti resettati alle posizioni originali")

        # Resetta overlay puntini verdi (se necessario)
        if hasattr(self, "original_green_dots_overlay") and self.original_green_dots_overlay is not None:
            self.green_dots_overlay = self.original_green_dots_overlay.copy()
            self.original_green_dots_overlay = None
            print("🔄 Overlay puntini verdi resettato alle posizioni originali")

        print("✅ Tutti gli overlay resettati")

    # *** NUOVO SISTEMA UNIFICATO DI TRASFORMAZIONE GRAFICHE ***

    def register_graphic(
        self, item_id, graphic_type, image_coordinates, style_info=None, is_overlay=False
    ):
        """Registra una grafica utente con coordinate nell'immagine originale."""
        self.graphics_registry[item_id] = {
            "type": graphic_type,
            "image_coords": image_coordinates.copy(),  # Coordinate nell'immagine NON ruotata
            "style": style_info or {},
            "is_overlay": is_overlay,
        }
        overlay_flag = " [OVERLAY]" if is_overlay else ""
        print(f"📝 Registrata grafica {graphic_type} {item_id}: {image_coordinates}{overlay_flag}")

    def transform_all_graphics(self):
        """Applica tutte le trasformazioni correnti (rotazione + scala + offset) alle grafiche."""
        if not self.graphics_registry:
            return

        transformed_count = 0

        for item_id, graphic_data in self.graphics_registry.items():
            try:
                if item_id in self.canvas.find_all():
                    # NUOVO: Trasforma TUTTI gli elementi (disegni + overlay) con lo STESSO metodo
                    if graphic_data.get("is_overlay", False):
                        # 🎯 OVERLAY: Usa trasformazioni IDENTICHE all'immagine
                        canvas_coords = self.transform_overlay_to_current_view(
                            graphic_data["image_coords"], graphic_data["type"]
                        )
                    else:
                        # 📏 DISEGNI: Usa il metodo esistente
                        canvas_coords = self.transform_image_coords_to_canvas(
                            graphic_data["image_coords"], graphic_data["type"]
                        )

                    # Aggiorna le coordinate sul canvas
                    try:
                        canvas_type = self.canvas.type(item_id)
                        self.canvas.coords(item_id, *canvas_coords)
                    except Exception as coord_error:
                        canvas_type = (
                            self.canvas.type(item_id)
                            if item_id in self.canvas.find_all()
                            else "DELETED"
                        )
                        print(
                            f"⚠️ Errore coordinate per {item_id} (tipo: {canvas_type}): {coord_error}"
                        )
                        print(
                            f"   Tipo grafica: {graphic_data['type']}, Coordinate: {len(canvas_coords)} valori: {canvas_coords}"
                        )

                    transformed_count += 1

            except Exception as e:
                print(f"⚠️ Errore trasformazione grafica {item_id}: {e}")

        if transformed_count > 0:
            print(f"🔄 Trasformate {transformed_count} grafiche")

    def transform_image_coords_to_canvas(self, image_coords, graphic_type):
        """Trasforma coordinate dall'immagine alle coordinate canvas correnti."""
        if self.current_image_on_canvas is None:
            return image_coords

        transformed_coords = []

        # Applica rotazione se necessaria
        if (
            self.current_rotation != 0
            and hasattr(self, "original_base_landmarks")
            and self.original_base_landmarks
        ):
            rotation_center = self.get_rotation_center_from_landmarks()

            if graphic_type == "line":
                # Ruota tutti i punti della linea
                for i in range(0, len(image_coords), 2):
                    x, y = image_coords[i], image_coords[i + 1]
                    rotated_x, rotated_y = self.rotate_point_around_center_simple(
                        x,
                        y,
                        rotation_center[0],
                        rotation_center[1],
                        -self.current_rotation,
                    )
                    transformed_coords.extend([rotated_x, rotated_y])

            elif graphic_type == "oval":
                # 🎯 FIX OVALIZZAZIONE: Tratta il cerchio come 4 punti del bounding box
                # che vengono ruotati indipendentemente per mantenere la forma corretta
                x1, y1, x2, y2 = image_coords
                
                # Definisci i 4 angoli del bounding box come punti separati
                corners = [
                    (x1, y1),  # top-left
                    (x2, y1),  # top-right
                    (x2, y2),  # bottom-right
                    (x1, y2)   # bottom-left
                ]
                
                # Ruota ogni angolo indipendentemente
                rotated_corners = []
                for corner_x, corner_y in corners:
                    rotated_x, rotated_y = self.rotate_point_around_center_simple(
                        corner_x,
                        corner_y,
                        rotation_center[0],
                        rotation_center[1],
                        -self.current_rotation,
                    )
                    rotated_corners.extend([rotated_x, rotated_y])
                
                # Calcola nuovo bounding box dai punti ruotati
                xs = [rotated_corners[i] for i in range(0, len(rotated_corners), 2)]
                ys = [rotated_corners[i] for i in range(1, len(rotated_corners), 2)]
                
                transformed_coords = [
                    min(xs), min(ys),  # nuovo top-left
                    max(xs), max(ys)   # nuovo bottom-right
                ]
            elif graphic_type == "polygon":
                # Ruota tutti i punti del poligono
                for i in range(0, len(image_coords), 2):
                    x, y = image_coords[i], image_coords[i + 1]
                    rotated_x, rotated_y = self.rotate_point_around_center_simple(
                        x,
                        y,
                        rotation_center[0],
                        rotation_center[1],
                        -self.current_rotation,
                    )
                    transformed_coords.extend([rotated_x, rotated_y])
            elif graphic_type == "circle_point":
                # 🎯 NUOVO: Gestione punti circolari (puntini fucsia e blu)
                center_x, center_y, radius = image_coords[0], image_coords[1], image_coords[2]
                rotated_x, rotated_y = self.rotate_point_around_center_simple(
                    center_x, center_y, rotation_center[0], rotation_center[1], -self.current_rotation
                )
                transformed_coords = [rotated_x, rotated_y, radius]
            elif graphic_type == "text":
                # Il testo ha solo una coordinata (x, y)
                x, y = image_coords[0], image_coords[1]
                rotated_x, rotated_y = self.rotate_point_around_center_simple(
                    x, y, rotation_center[0], rotation_center[1], -self.current_rotation
                )
                transformed_coords = [rotated_x, rotated_y]
            else:
                transformed_coords = image_coords.copy()
        else:
            transformed_coords = image_coords.copy()

        # Converti da coordinate immagine a coordinate canvas (scala + posizione)
        final_coords = []
        
        # 🎯 GESTIONE SPECIALE per circle_point
        if graphic_type == "circle_point":
            center_x, center_y, radius = transformed_coords[0], transformed_coords[1], transformed_coords[2]
            canvas_x, canvas_y = self.image_to_canvas_coords(center_x, center_y)
            # Scala il raggio con il fattore di zoom
            scaled_radius = radius * getattr(self, 'canvas_scale', 1.0)
            final_coords = [canvas_x - scaled_radius, canvas_y - scaled_radius, 
                           canvas_x + scaled_radius, canvas_y + scaled_radius]
        else:
            for i in range(0, len(transformed_coords), 2):
                canvas_x, canvas_y = self.image_to_canvas_coords(
                    transformed_coords[i], transformed_coords[i + 1]
                )
                final_coords.extend([canvas_x, canvas_y])

        return final_coords

    def rotate_point_around_center_simple(
        self, x, y, center_x, center_y, angle_degrees
    ):
        """Ruota un punto attorno a un centro - versione semplificata."""
        import math

        angle_rad = math.radians(angle_degrees)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)

        # Trasla, ruota, trasla indietro
        dx = x - center_x
        dy = y - center_y

        rotated_x = dx * cos_angle - dy * sin_angle + center_x
        rotated_y = dx * sin_angle + dy * cos_angle + center_y

        return rotated_x, rotated_y

    def transform_overlay_to_current_view(self, image_coords, graphic_type):
        """Trasforma coordinate overlay applicando le IDENTICHE trasformazioni dell'immagine.
        
        Questo metodo garantisce che gli overlay seguano esattamente l'immagine durante:
        - Rotazione attorno ai landmarks
        - Pan (spostamento) 
        - Zoom (scala)
        """
        if self.current_image_on_canvas is None:
            return image_coords

        transformed_coords = []

        # 🎯 STEP 1: Applica ROTAZIONE se presente (identica all'immagine)
        if (self.current_rotation != 0 and 
            hasattr(self, "original_base_landmarks") and 
            self.original_base_landmarks):
            
            # Usa lo STESSO centro di rotazione dell'immagine
            rotation_center = self.get_rotation_center_from_landmarks()
            
            # 🎯 GESTIONE SPECIALE per circle_point (puntini fucsia)
            if graphic_type == "circle_point":
                # Per i punti circolari: ruota solo il centro, mantieni il raggio
                center_x, center_y, radius = image_coords[0], image_coords[1], image_coords[2]
                rotated_x, rotated_y = self.rotate_point_around_center_simple(
                    center_x, center_y, rotation_center[0], rotation_center[1], -self.current_rotation
                )
                transformed_coords = [rotated_x, rotated_y, radius]
            else:
                # Applica rotazione a tutti i punti (stesso algoritmo dell'immagine)
                for i in range(0, len(image_coords), 2):
                    x, y = image_coords[i], image_coords[i + 1]
                    
                    # IDENTICA rotazione applicata all'immagine (angolo invertito)
                    rotated_x, rotated_y = self.rotate_point_around_center_simple(
                        x, y, rotation_center[0], rotation_center[1], -self.current_rotation
                    )
                    transformed_coords.extend([rotated_x, rotated_y])
        else:
            # Nessuna rotazione - usa coordinate originali
            transformed_coords = image_coords.copy()

        # 🎯 STEP 2: Converti in coordinate canvas (scala + offset)
        final_canvas_coords = []
        
        # 🎯 GESTIONE SPECIALE per circle_point
        if graphic_type == "circle_point":
            center_x, center_y, radius = transformed_coords[0], transformed_coords[1], transformed_coords[2]
            canvas_x, canvas_y = self.image_to_canvas_coords(center_x, center_y)
            # Scala il raggio con il fattore di zoom
            scaled_radius = radius * getattr(self, 'canvas_scale', 1.0)
            final_canvas_coords = [canvas_x - scaled_radius, canvas_y - scaled_radius, 
                                  canvas_x + scaled_radius, canvas_y + scaled_radius]
        else:
            for i in range(0, len(transformed_coords), 2):
                img_x, img_y = transformed_coords[i], transformed_coords[i + 1]
                
                # Usa lo STESSO metodo di conversione dell'immagine 
                canvas_x, canvas_y = self.image_to_canvas_coords(img_x, img_y)
                final_canvas_coords.extend([canvas_x, canvas_y])

        return final_canvas_coords

    def reset_all_drawings_to_original_positions(self):
        """*** OBSOLETA - Sostituita da transform_all_graphics() ***"""
        print(
            "⚠️ reset_all_drawings_to_original_positions è obsoleta, usa transform_all_graphics()"
        )
        self.transform_all_graphics()
        return

        # Ripristina ogni elemento alle coordinate originali
        for item_id, original_data in self.original_unrotated_coords.items():
            try:
                # Verifica che l'elemento esista ancora sul canvas
                if item_id in self.canvas.find_all():
                    original_coords = original_data["coords"]
                    self.canvas.coords(item_id, *original_coords)
                    reset_count += 1
                    print(f"🔄 Resettato elemento {item_id} alle coordinate originali")
            except Exception as e:
                print(f"⚠️ Errore reset elemento {item_id}: {e}")

        print(f"✅ Resettati {reset_count} elementi grafici alle posizioni originali")

    def migrate_rotated_elements_to_original_coords(self):
        """*** OBSOLETA - Non più necessaria con il nuovo sistema ***"""
        print(
            "⚠️ migrate_rotated_elements_to_original_coords è obsoleta e non necessaria"
        )
        return

    def rotate_landmarks_around_point(self, landmarks, angle, rotation_center):
        """Ruota i landmarks attorno a un punto specifico."""
        if landmarks is None or len(landmarks) == 0:
            return landmarks

        center_x, center_y = rotation_center

        # Converte l'angolo in radianti
        # INVERTO l'angolo per coerenza con i disegni canvas (stesso problema OpenCV vs Canvas)
        inverted_angle = -angle
        angle_rad = np.radians(inverted_angle)
        cos_angle = np.cos(angle_rad)
        sin_angle = np.sin(angle_rad)

        rotated_landmarks = []

        for x, y in landmarks:
            # Trasla il punto rispetto al centro di rotazione
            translated_x = x - center_x
            translated_y = y - center_y

            # Applica la rotazione
            rotated_x = translated_x * cos_angle - translated_y * sin_angle
            rotated_y = translated_x * sin_angle + translated_y * cos_angle

            # Trasla il punto ruotato rispetto al centro di rotazione
            final_x = rotated_x + center_x
            final_y = rotated_y + center_y

            rotated_landmarks.append((int(final_x), int(final_y)))

        # DEBUG DETTAGLIATO: Verifica primi landmark e altri punti
        if len(landmarks) > 9:
            original_landmark_9 = landmarks[9]
            rotated_landmark_9 = rotated_landmarks[9] if len(rotated_landmarks) > 9 else None
            print(f"🎯 DEBUG LANDMARK 9: originale={original_landmark_9}, ruotato={rotated_landmark_9}")
            
            # Verifica anche landmark 0 e 1 per vedere se si muovono
            if len(landmarks) > 1 and len(rotated_landmarks) > 1:
                original_0 = landmarks[0]
                rotated_0 = rotated_landmarks[0]
                original_1 = landmarks[1] 
                rotated_1 = rotated_landmarks[1]
                print(f"🎯 DEBUG LANDMARK 0: {original_0} -> {rotated_0}")
                print(f"🎯 DEBUG LANDMARK 1: {original_1} -> {rotated_1}")
                
                # Calcola distanze per verificare movimento
                dist_0 = ((original_0[0] - rotated_0[0])**2 + (original_0[1] - rotated_0[1])**2)**0.5
                dist_1 = ((original_1[0] - rotated_1[0])**2 + (original_1[1] - rotated_1[1])**2)**0.5
                print(f"🎯 MOVIMENTO: LM0 spostato di {dist_0:.1f}px, LM1 spostato di {dist_1:.1f}px")
        
        print(
            f"🔄 Ruotati {len(rotated_landmarks)} landmarks attorno a ({center_x}, {center_y}) con angolo {angle}° (invertito: {inverted_angle}°)"
        )

        # DEBUG: Controlla se il landmark 9 (glabella) si è mosso
        if len(rotated_landmarks) > 9:
            orig_glabella = landmarks[9] if landmarks and len(landmarks) > 9 else (0, 0)
            new_glabella = rotated_landmarks[9]
            print(
                f"🎯 DEBUG LANDMARK 9: originale={orig_glabella}, ruotato={new_glabella}"
            )

        return rotated_landmarks

    def rotate_all_drawings_around_point(self, rotation_center):
        """Ruota tutti i disegni sul canvas attorno al punto di rotazione specificato."""
        if not hasattr(self, "original_unrotated_coords"):
            self.original_unrotated_coords = {}

        rotated_items = 0
        center_x, center_y = rotation_center

        print(
            f"🔄 Rotazione disegni: angolo={self.current_rotation:.1f}°, centro rotazione=({center_x}, {center_y})"
        )

        # Ruota tutti gli elementi con tag "drawing" e "temp_drawing"
        for tag in ["drawing", "temp_drawing"]:
            items = self.canvas.find_withtag(tag)
            for item_id in items:
                rotated_items += self.rotate_drawing_item_around_point(
                    item_id, rotation_center
                )

        # Ruota anche gli elementi dei layer specifici
        if hasattr(self, "layers_list") and self.layers_list:
            for layer in self.layers_list:
                items = self.canvas.find_withtag(layer["tag"])
                for item_id in items:
                    item_tags = self.canvas.gettags(item_id)
                    if "drawing" not in item_tags:
                        rotated_items += self.rotate_drawing_item_around_point(
                            item_id, rotation_center
                        )

        if rotated_items > 0:
            print(
                f"🔄 Ruotati {rotated_items} disegni di {self.current_rotation:.1f}° attorno al punto ({center_x}, {center_y})"
            )
        else:
            print("⚠️ Nessun disegno ruotato - verifica presenza disegni")

    def rotate_drawing_item_around_point(self, item_id, rotation_center):
        """Ruota un elemento del disegno attorno a un punto specifico usando coordinate originali."""
        try:
            # USA LO STESSO CENTRO PER TUTTI I DISEGNI
            # Le coordinate sono già state convertite in coordinate canvas dal chiamante
            rotation_center_canvas = rotation_center

            # Se non abbiamo le coordinate originali non ruotate, memorizzale ora
            if item_id not in self.original_unrotated_coords:
                self.store_unrotated_coords_for_point_rotation(
                    item_id, rotation_center_canvas
                )

            # Ottieni le coordinate originali non ruotate
            original_data = self.original_unrotated_coords[item_id]
            item_type = original_data["type"]
            original_coords = original_data["coords"]
            rotation_center_orig = original_data["rotation_center"]

            # Calcola l'angolo di rotazione in radianti
            # INVERTO l'angolo per i disegni canvas perché OpenCV e canvas usano direzioni opposte
            # OpenCV: angolo positivo = antiorario, Canvas: angolo positivo = orario
            inverted_angle = -self.current_rotation
            angle_rad = np.radians(inverted_angle)
            cos_angle = np.cos(angle_rad)
            sin_angle = np.sin(angle_rad)

            print(
                f"🔄 Rotazione item {item_id}: tipo={item_type}, angolo={self.current_rotation:.1f}° attorno a {rotation_center_canvas}"
            )

            if item_type == "line":
                # Ruota tutte le coordinate della linea
                new_coords = []
                for i in range(0, len(original_coords), 2):
                    new_x, new_y = self.rotate_point_around_center(
                        original_coords[i],
                        original_coords[i + 1],
                        rotation_center_canvas[0],
                        rotation_center_canvas[1],
                        cos_angle,
                        sin_angle,
                    )
                    new_coords.extend([new_x, new_y])
                self.canvas.coords(item_id, *new_coords)

            elif item_type == "oval":
                # Per cerchi, ruota solo il centro mantenendo le dimensioni originali
                orig_x1, orig_y1, orig_x2, orig_y2 = original_coords

                # Calcola centro e dimensioni originali
                orig_center_x = (orig_x1 + orig_x2) / 2
                orig_center_y = (orig_y1 + orig_y2) / 2
                width = orig_x2 - orig_x1
                height = orig_y2 - orig_y1

                # Ruota solo il centro, mantieni le dimensioni
                new_center_x, new_center_y = self.rotate_point_around_center(
                    orig_center_x,
                    orig_center_y,
                    rotation_center_canvas[0],
                    rotation_center_canvas[1],
                    cos_angle,
                    sin_angle,
                )

                # Ricostruisci il bounding box con le dimensioni originali
                new_x1 = new_center_x - width / 2
                new_y1 = new_center_y - height / 2
                new_x2 = new_center_x + width / 2
                new_y2 = new_center_y + height / 2

                self.canvas.coords(item_id, new_x1, new_y1, new_x2, new_y2)

            elif item_type == "rectangle":
                # Per rettangoli, convertiamo a poligono per rotazione visiva corretta
                orig_x1, orig_y1, orig_x2, orig_y2 = original_coords

                # Ruota tutti e 4 gli angoli del rettangolo
                corners = [
                    (orig_x1, orig_y1),
                    (orig_x2, orig_y1),
                    (orig_x2, orig_y2),
                    (orig_x1, orig_y2),
                ]
                rotated_corners = []

                for corner_x, corner_y in corners:
                    new_x, new_y = self.rotate_point_around_center(
                        corner_x,
                        corner_y,
                        rotation_center_canvas[0],
                        rotation_center_canvas[1],
                        cos_angle,
                        sin_angle,
                    )
                    rotated_corners.extend([new_x, new_y])

                # Converti rettangolo in poligono per visualizzazione ruotata
                tags = self.canvas.gettags(item_id)
                outline_color = self.canvas.itemcget(item_id, "outline") or "purple"
                width = self.canvas.itemcget(item_id, "width") or 2

                self.canvas.delete(item_id)
                new_item_id = self.canvas.create_polygon(
                    *rotated_corners,
                    outline=outline_color,
                    fill="",
                    width=width,
                    tags=tags,
                )

                # Aggiorna il tipo e salva coordinate originali del rettangolo
                original_data["type"] = "polygon"
                original_data["original_rect_coords"] = [
                    orig_x1,
                    orig_y1,
                    orig_x2,
                    orig_y2,
                ]

                print(
                    f"🔳 Convertito rettangolo {item_id} in poligono {new_item_id} per rotazione"
                )

            elif item_type == "polygon":
                # Gestisce poligoni (inclusi ex-rettangoli)
                if "original_rect_coords" in original_data:
                    # È un ex-rettangolo, usa le coordinate originali del rettangolo
                    orig_x1, orig_y1, orig_x2, orig_y2 = original_data[
                        "original_rect_coords"
                    ]
                    corners = [
                        (orig_x1, orig_y1),
                        (orig_x2, orig_y1),
                        (orig_x2, orig_y2),
                        (orig_x1, orig_y2),
                    ]
                else:
                    # È un poligono originale, usa tutte le coordinate
                    corners = [
                        (original_coords[i], original_coords[i + 1])
                        for i in range(0, len(original_coords), 2)
                    ]

                rotated_coords = []
                for corner_x, corner_y in corners:
                    new_x, new_y = self.rotate_point_around_center(
                        corner_x,
                        corner_y,
                        rotation_center_canvas[0],
                        rotation_center_canvas[1],
                        cos_angle,
                        sin_angle,
                    )
                    rotated_coords.extend([new_x, new_y])

                self.canvas.coords(item_id, *rotated_coords)

            elif item_type == "text":
                # Ruota la posizione del testo
                orig_x, orig_y = original_coords

                new_x, new_y = self.rotate_point_around_center(
                    orig_x,
                    orig_y,
                    rotation_center_canvas[0],
                    rotation_center_canvas[1],
                    cos_angle,
                    sin_angle,
                )

                self.canvas.coords(item_id, new_x, new_y)

            return 1

        except Exception as e:
            print(f"⚠️ Errore rotazione item {item_id}: {e}")
            return 0

    def rotate_point_around_center(
        self, x, y, center_x, center_y, cos_angle, sin_angle
    ):
        """Ruota un punto attorno a un centro usando gli angoli precompuntati."""
        # Trasla il punto rispetto al centro
        translated_x = x - center_x
        translated_y = y - center_y

        # Applica la rotazione
        rotated_x = translated_x * cos_angle - translated_y * sin_angle
        rotated_y = translated_x * sin_angle + translated_y * cos_angle

        # Trasla il punto ruotato rispetto al centro
        final_x = rotated_x + center_x
        final_y = rotated_y + center_y

        return final_x, final_y

    def convert_image_to_canvas_coords(self, image_x, image_y):
        """Converte coordinate dell'immagine in coordinate del canvas (UNIFICATO)."""
        # Usa il metodo unificato per consistenza
        return self.image_to_canvas_coords(image_x, image_y)
    


    # NOTA: convert_canvas_to_image_coords() rimossa - usare canvas_to_image_coords()

    def store_unrotated_coords_for_point_rotation(self, item_id, rotation_center):
        """Memorizza le coordinate originali per la rotazione attorno a un punto specifico."""
        try:
            item_type = self.canvas.type(item_id)
            current_coords = self.canvas.coords(item_id)

            self.original_unrotated_coords[item_id] = {
                "type": item_type,
                "coords": current_coords.copy(),
                "rotation_center": rotation_center,
                "canvas_scale": self.canvas_scale,  # Memorizza scala corrente per calcoli corretti
            }

            # Per il testo, salva anche informazioni font
            if item_type == "text":
                try:
                    font_info = self.canvas.itemcget(item_id, "font")
                    if isinstance(font_info, tuple) and len(font_info) >= 2:
                        self.original_unrotated_coords[item_id]["font_size"] = (
                            font_info[1]
                        )
                        self.original_unrotated_coords[item_id]["font_info"] = font_info
                except:
                    pass

        except Exception as e:
            print(f"⚠️ Errore memorizzazione coordinate item {item_id}: {e}")

    def store_unrotated_coords(self, item_id, image_center_x, image_center_y):
        """Memorizza le coordinate originali non ruotate di un elemento per rotazioni precise."""
        try:
            item_type = self.canvas.type(item_id)
            current_coords = self.canvas.coords(item_id)

            if item_type == "line":
                self.original_unrotated_coords[item_id] = {
                    "type": item_type,
                    "coords": current_coords.copy(),
                    "image_center": [image_center_x, image_center_y],
                    "canvas_scale": self.canvas_scale,
                }

            elif item_type in ["oval", "rectangle"]:
                self.original_unrotated_coords[item_id] = {
                    "type": item_type,
                    "coords": current_coords.copy(),
                    "image_center": [image_center_x, image_center_y],
                    "canvas_scale": self.canvas_scale,
                }

            elif item_type == "text":
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

                self.original_unrotated_coords[item_id] = {
                    "type": item_type,
                    "coords": current_coords.copy(),
                    "image_center": [image_center_x, image_center_y],
                    "canvas_scale": self.canvas_scale,
                    "font_size": font_size,
                    "font_info": font_info,
                }

            print(
                f"✅ Memorizzate coordinate non ruotate per item {item_id} (tipo: {item_type})"
            )

        except Exception as e:
            print(f"⚠️ Errore memorizzazione coordinate non ruotate item {item_id}: {e}")

    # RIMOSSO: on_canvas_click() - sostituito da on_canvas_click_UNIFIED()

    def on_canvas_drag(self, event):
        """Gestisce il trascinamento sul canvas (SEMPLIFICATO)."""
        if not self.canvas_drag_start:
            return

        # FIX: usa canvasx/canvasy per precisione
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        if self.current_canvas_tool == "PAN":
            print(
                f"✋ PAN ATTIVO - elaboro drag da {self.canvas_drag_start} a ({canvas_x}, {canvas_y})"
            )
            # CORRETTO: Calcola movimento dalla posizione iniziale
            dx = canvas_x - self.canvas_drag_start[0]
            dy = canvas_y - self.canvas_drag_start[1]

            # Aggiorna offset dell'immagine
            self.canvas_offset_x += dx
            self.canvas_offset_y += dy

            # *** NUOVO SISTEMA: Le grafiche si aggiornano automaticamente
            self.transform_all_graphics()

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

            # *** NUOVO SISTEMA: Le grafiche si aggiornano automaticamente
            self.transform_all_graphics()

    def on_canvas_mouse_motion(self, event):
        """Gestisce il movimento del mouse sul canvas (SEMPLIFICATO)."""
        # FIX: usa canvasx/canvasy per precisione
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # TODO: Mostra coordinate nella status bar se necessario
        pass

    def on_touchpad_pan_start(self, event):
        """Inizia PAN con touchpad (middle mouse o gesture due dita)."""
        # FIX: usa canvasx/canvasy per precisione
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        self.touchpad_drag_start = (canvas_x, canvas_y)
        print("🖱️ Touchpad PAN iniziato")

    def on_touchpad_pan_drag(self, event):
        """PAN con touchpad - funziona sempre indipendentemente dal tool selezionato."""
        if not hasattr(self, "touchpad_drag_start") or not self.touchpad_drag_start:
            return

        # FIX: usa canvasx/canvasy per precisione
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

        # *** NUOVO SISTEMA: Le grafiche si aggiornano automaticamente con la nuova posizione dell'immagine
        self.transform_all_graphics()

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

        # Aggiorna gli offset
        if is_horizontal:
            # Movimento orizzontale (con Shift)
            self.canvas_offset_x += movement_amount
            print(f"↔️ Touchpad PAN orizzontale: offset_x={self.canvas_offset_x}")
        else:
            # Movimento verticale (normale)
            self.canvas_offset_y += movement_amount
            print(f"↕️ Touchpad PAN verticale: offset_y={self.canvas_offset_y}")

        # *** NUOVO SISTEMA: Le grafiche si aggiornano automaticamente
        self.transform_all_graphics()

        # Aggiorna immediatamente per movimento fluido
        self.update_canvas_display()

    # Metodo rimosso: on_touchpad_pan_horizontal - sostituito da on_touchpad_omnidirectional_pan

    # RIMOSSO: on_canvas_measurement_click_new() - logica integrata in on_canvas_click_UNIFIED()

    def canvas_to_image_coords(self, canvas_x, canvas_y):
        """Converte coordinate canvas a coordinate immagine (VERSIONE CORRETTA SINCRONIZZATA)."""
        if self.current_image_on_canvas is None:
            return 0, 0

        # 🎯 FIX CRITICO: Usa ESATTAMENTE la stessa logica di posizionamento di update_canvas_display
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Dimensioni immagine originale
        img_height, img_width = self.current_image_on_canvas.shape[:2]
        
        # Dimensioni immagine scalata (stesso calcolo di update_canvas_display)
        scaled_width = int(img_width * self.canvas_scale)
        scaled_height = int(img_height * self.canvas_scale)
        
        # Posizione immagine centrata (ESATTA copia da update_canvas_display)
        image_x_pos = max(0, (canvas_width - scaled_width) // 2) + self.canvas_offset_x
        image_y_pos = max(0, (canvas_height - scaled_height) // 2) + self.canvas_offset_y
        
        # Converte coordinate canvas -> coordinate immagine scalata -> coordinate immagine originale
        scaled_x = canvas_x - image_x_pos  # Posizione relativa nell'immagine scalata
        scaled_y = canvas_y - image_y_pos
        
        # Converte da coordinata scalata a coordinata originale
        img_x = scaled_x / self.canvas_scale
        img_y = scaled_y / self.canvas_scale

        # Limita alle dimensioni dell'immagine (con margine di sicurezza)
        img_x = max(0, min(img_width - 1, img_x))
        img_y = max(0, min(img_height - 1, img_y))

        return img_x, img_y

    def image_to_canvas_coords(self, img_x, img_y):
        """Converte coordinate immagine in coordinate canvas (VERSIONE CORRETTA SINCRONIZZATA)."""
        if self.current_image_on_canvas is None:
            return img_x, img_y

        # 🎯 FIX CRITICO: Usa ESATTAMENTE la stessa logica di posizionamento di update_canvas_display
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Dimensioni immagine originale
        img_height, img_width = self.current_image_on_canvas.shape[:2]
        
        # Dimensioni immagine scalata (stesso calcolo di update_canvas_display)  
        scaled_width = int(img_width * self.canvas_scale)
        scaled_height = int(img_height * self.canvas_scale)
        
        # Posizione immagine centrata (ESATTA copia da update_canvas_display)
        image_x_pos = max(0, (canvas_width - scaled_width) // 2) + self.canvas_offset_x
        image_y_pos = max(0, (canvas_height - scaled_height) // 2) + self.canvas_offset_y

        # Converte coordinate immagine -> coordinate canvas
        canvas_x = img_x * self.canvas_scale + image_x_pos
        canvas_y = img_y * self.canvas_scale + image_y_pos

        return canvas_x, canvas_y

    def on_canvas_click_UNIFIED(self, event):
        """Gestisce i click sul canvas - SISTEMA UNIFICATO CORRETTO."""
        # FIX CRITICO: usa canvasx/canvasy per considerare scrolling/zoom del canvas
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        print(
            f"CANVAS CLICK SEMPLIFICATO: tool={self.current_canvas_tool}, pos=({canvas_x:.1f}, {canvas_y:.1f})"
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
            # FIX: usa coordinate canvas corrette per conversione
            img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)

            # Chiama il callback per le misurazioni se esiste
            if hasattr(self, "measurement_callback") and self.measurement_callback:
                self.measurement_callback(img_x, img_y)

            print(
                f"🖱️ Click misurazione legacy: canvas({event.x}, {event.y}) -> immagine({img_x:.0f}, {img_y:.0f})"
            )

    def on_canvas_motion(self, event):
        """Gestisce il movimento del mouse sul canvas."""
        if self.current_image_on_canvas is not None:
            # FIX: usa coordinate canvas corrette
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)

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

            # *** NUOVO SISTEMA: Converti coordinate canvas in coordinate immagine e registra
            start_image_x, start_image_y = self.canvas_to_image_coords(
                start_x, start_y
            )
            end_image_x, end_image_y = self.canvas_to_image_coords(
                canvas_x, canvas_y
            )

            # Registra nel nuovo sistema unificato
            self.register_graphic(
                line_id,
                "line",
                [start_image_x, start_image_y, end_image_x, end_image_y],
                {"fill": "blue", "width": 2},
            )

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

            # *** NUOVO SISTEMA: Converti coordinate canvas in coordinate immagine e registra
            x1_img, y1_img = self.canvas_to_image_coords(
                center_x - radius, center_y - radius
            )
            x2_img, y2_img = self.canvas_to_image_coords(
                center_x + radius, center_y + radius
            )

            # Registra nel nuovo sistema unificato
            self.register_graphic(
                circle_id,
                "oval",
                [x1_img, y1_img, x2_img, y2_img],
                {"outline": "green", "width": 2},
            )

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
            # Disegna il rettangolo finale come poligono (per gestire meglio le rotazioni)
            rect_id = self.canvas.create_polygon(
                start_x,
                start_y,  # Angolo superiore sinistro
                canvas_x,
                start_y,  # Angolo superiore destro
                canvas_x,
                canvas_y,  # Angolo inferiore destro
                start_x,
                canvas_y,  # Angolo inferiore sinistro
                outline="purple",
                fill="",  # Trasparente
                width=2,
                tags=layer_tags,
            )

            # *** NUOVO SISTEMA: Converti coordinate canvas in coordinate immagine e registra
            x1_img, y1_img = self.canvas_to_image_coords(start_x, start_y)
            x2_img, y2_img = self.canvas_to_image_coords(canvas_x, canvas_y)

            # Registra nel nuovo sistema unificato come poligono con 4 punti
            corners_img = [
                x1_img,
                y1_img,
                x2_img,
                y1_img,
                x2_img,
                y2_img,
                x1_img,
                y2_img,
            ]
            self.register_graphic(
                rect_id,
                "polygon",
                corners_img,
                {"outline": "purple", "width": 2, "fill": ""},
            )

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

            # *** NUOVO SISTEMA: Converti coordinate canvas in coordinate immagine e registra
            # Linea di misurazione
            start_image_x, start_image_y = self.canvas_to_image_coords(
                start_x, start_y
            )
            end_image_x, end_image_y = self.canvas_to_image_coords(
                canvas_x, canvas_y
            )

            self.register_graphic(
                measure_line_id,
                "line",
                [start_image_x, start_image_y, end_image_x, end_image_y],
                {"fill": "orange", "width": 2},
            )

            # Testo della misurazione
            text_image_x, text_image_y = self.canvas_to_image_coords(
                mid_x, mid_y - 10
            )

            self.register_graphic(
                measure_text_id,
                "text",
                [text_image_x, text_image_y],
                {"fill": "orange", "font": ("Arial", 8), "text": f"{distance:.1f}px"},
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

            # *** NUOVO SISTEMA: Converti coordinate canvas in coordinate immagine e registra
            text_image_x, text_image_y = self.canvas_to_image_coords(
                canvas_x, canvas_y
            )

            self.register_graphic(
                text_id,
                "text",
                [text_image_x, text_image_y],
                {"fill": "red", "font": ("Arial", 12, "bold"), "text": text},
            )

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
        """Gestisce il tool SELECTION per selezionare disegni o fare misurazioni."""
        
        # PRIORITÀ: Se la modalità misurazione è attiva, gestisci come misurazione
        if (hasattr(self, 'measurement_mode_active') and 
            self.measurement_mode_active and self.measurement_mode_active.get()):
            
            print(f"🎯 MODALITÀ MISURAZIONE ATTIVA: Click su ({canvas_x:.1f}, {canvas_y:.1f})")
            
            # Converti coordinate canvas in coordinate immagine per misurazione
            try:
                img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
                
                # Gestisci come click per misurazione in base alla modalità
                mode_text = "LANDMARK" if self.landmark_measurement_mode else "MANUALE"
                print(f"📍 Modalità {mode_text} attiva")
                
                if self.landmark_measurement_mode:
                    # MODALITÀ LANDMARK: Snap magnetico sui landmarks esistenti
                    print("🎯 Cercando snap magnetico sui landmarks...")
                    print(f"🔍 DEBUG CLICK: canvas({canvas_x:.1f},{canvas_y:.1f}) -> img({img_x:.1f},{img_y:.1f})")
                    # Verifica che i landmarks siano visibili
                    if not self.all_landmarks_var.get():
                        self.status_bar.config(text="⚠️ Attiva prima i LANDMARKS nella sezione RILEVAMENTI")
                        print("⚠️ Landmarks non visibili - attiva prima il pulsante LANDMARKS")
                        return
                    self.handle_landmark_click_for_measurement(img_x, img_y)
                else:
                    # MODALITÀ MANUALE: Click libero senza snap sui landmarks
                    print("🖱️ Selezione libera sull'immagine...")
                    self.handle_manual_point_selection(img_x, img_y, canvas_x, canvas_y)
                    
            except Exception as e:
                print(f"⚠️ Errore conversione coordinate per misurazione: {e}")
            
            return
        
        # COMPORTAMENTO NORMALE: Selezione e modifica disegni
        try:
            closest_items = self.canvas.find_closest(canvas_x, canvas_y)
            if not closest_items:
                print("🎯 SELECTION: Nessun elemento nel canvas")
                return
            
            closest_item = closest_items[0]
        except (IndexError, tk.TclError) as e:
            print(f"🎯 SELECTION: Impossibile trovare elementi nel canvas: {e}")
            return

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

    def handle_landmark_click_for_measurement(self, img_x, img_y):
        """Gestisce il click sui landmark MediaPipe per le misurazioni con snap magnetico migliorato."""
        if not self.current_landmarks:
            self.status_bar.config(text="Nessun landmark rilevato - attiva LANDMARKS nella sezione RILEVAMENTI")
            return
        
        print(f"🎯 MODALITÀ LANDMARK: Click su ({img_x:.1f}, {img_y:.1f}) - landmarks disponibili: {len(self.current_landmarks)} (MediaPipe)")
            
        # SISTEMA DI SNAPPING MIGLIORATO: Usa tolleranza dinamica
        closest_idx = self.find_closest_landmark(img_x, img_y)
        if closest_idx is not None:
            landmark_pos = self.current_landmarks[closest_idx]
            distance = ((img_x - landmark_pos[0])**2 + (img_y - landmark_pos[1])**2)**0.5
            
            # Calcola raggio di snap dinamico basato sul zoom (più aggressivo)
            zoom_factor = getattr(self, 'canvas_scale', 1.0)
            if zoom_factor < 0.3:
                snap_radius = 120  # Raggio enorme per immagini estremamente piccole
            elif zoom_factor < 0.5:
                snap_radius = 80   # Raggio molto grande per immagini molto piccole
            elif zoom_factor < 0.8:
                snap_radius = 60   # Raggio grande per immagini piccole
            elif zoom_factor < 1.2:
                snap_radius = 45   # Raggio aumentato per zoom normale
            elif zoom_factor > 3.0:
                snap_radius = 12   # Raggio ridotto per immagini molto ingrandite
            else:
                snap_radius = 20   # Raggio ridotto per zoom medio-alto
            
            print(f"📍 Landmark più vicino: {closest_idx} a distanza {distance:.1f}px "
                  f"({landmark_pos[0]:.1f}, {landmark_pos[1]:.1f}) [raggio snap: {snap_radius}px, zoom: {zoom_factor:.2f}]")
            
            if distance <= snap_radius:
                self.add_landmark_selection(closest_idx)
                self.update_canvas_display()  # Aggiorna visualizzazione
                print(f"✅ Landmark {closest_idx} selezionato (snap magnetico, distanza: {distance:.1f}px)")
                self.status_bar.config(text=f"✅ Landmark {closest_idx} selezionato (snap automatico)")
            else:
                self.status_bar.config(text=f"Click troppo lontano (distanza: {distance:.0f}px, max: {snap_radius}px)")
                print(f"⚠️ Click a distanza {distance:.1f}px dal landmark più vicino (max {snap_radius}px)")
        else:
            self.status_bar.config(text="Nessun landmark trovato nelle vicinanze - prova ad ingrandire l'immagine")
            print("⚠️ Nessun landmark trovato con find_closest_landmark")

    def handle_manual_point_selection(self, img_x, img_y, canvas_x, canvas_y):
        """Gestisce la selezione libera di punti per le misurazioni (nessuno snap sui landmarks)."""
        # Limita il numero di punti in base alla modalità
        max_points = {"distance": 2, "angle": 3, "area": 4}
        max_count = max_points.get(self.measurement_mode, 2)
        
        if len(self.selected_points) >= max_count:
            # Rimuovi il primo punto se abbiamo raggiunto il limite
            removed_point = self.selected_points.pop(0)
            # Rimuovi anche il punto visualizzato dal canvas
            old_points = self.canvas.find_withtag("selection_point")
            if old_points:
                self.canvas.delete(old_points[0])
            print(f"🗑️ Punto rimosso: {removed_point}")
            
        # 🎯 FIX COORDINATE ROTAZIONE: Converti coordinate correnti a coordinate originali
        # Se l'immagine è ruotata, dobbiamo salvare le coordinate nel sistema originale
        if (self.current_rotation != 0 and 
            hasattr(self, "original_base_landmarks") and 
            self.original_base_landmarks):
            
            # Ottieni centro di rotazione e converti coordinate
            rotation_center = self.get_rotation_center_from_landmarks()
            
            # Ruota le coordinate nel sistema originale (rotazione opposta)
            original_x, original_y = self.rotate_point_around_center_simple(
                img_x, img_y, 
                rotation_center[0], rotation_center[1], 
                self.current_rotation  # Rotazione opposta per tornare al sistema originale
            )
            point = (original_x, original_y)
            print(f"🔄 Coordinate corrette per rotazione: ({img_x:.1f},{img_y:.1f}) -> ({original_x:.1f},{original_y:.1f})")
        else:
            # Nessuna rotazione - usa coordinate normali
            point = (img_x, img_y)
            
        self.selected_points.append(point)
        
        # 🎯 FIX: Registra puntini blu nel graphics_registry per seguire trasformazioni
        radius = 4
        point_id = self.canvas.create_oval(
            canvas_x - radius, canvas_y - radius, canvas_x + radius, canvas_y + radius,
            fill="blue", outline="white", width=2, tags="selection_point"
        )
        
        # 🎯 CRUCIALE: Registra punto blu come circle_point trasformabile
        self.register_graphic(
            point_id, "circle_point",
            [img_x, img_y, radius],  # [center_x, center_y, radius]
            {"fill": "blue", "outline": "white", "width": 2},
            is_overlay=True
        )
        
        # Aggiungi numero del punto per chiarezza - ANCHE questo deve seguire trasformazioni
        text_id = self.canvas.create_text(
            canvas_x + 8, canvas_y - 8,
            text=str(len(self.selected_points)),
            fill="blue", font=("Arial", 10, "bold"),
            tags="selection_point"
        )
        
        # 🎯 CRUCIALE: Registra anche il testo come trasformabile
        self.register_graphic(
            text_id, "text",
            [img_x + 8/getattr(self, 'canvas_scale', 1.0), img_y - 8/getattr(self, 'canvas_scale', 1.0)],  # Coordinate immagine del testo
            {"fill": "blue", "font": ("Arial", 10, "bold"), "text": str(len(self.selected_points))},
            is_overlay=True
        )
        
        self.status_bar.config(
            text=f"Punto manuale {len(self.selected_points)}/{max_count}: ({img_x:.1f}, {img_y:.1f})"
        )
        
        print(f"🎯 Punto manuale selezionato: ({img_x:.1f}, {img_y:.1f}) - NESSUNO snap ai landmarks")

    def enable_landmark_hover_effect(self):
        """Attiva l'effetto hover sui landmarks."""
        self.canvas.bind("<Motion>", self.on_landmark_hover)
        self.hovered_landmark = None
        print("✨ Hover effect sui landmarks ATTIVATO")
    
    def disable_landmark_hover_effect(self):
        """Disattiva l'effetto hover sui landmarks."""
        # Rimuovi evidenziazione se presente
        if hasattr(self, 'hovered_landmark') and self.hovered_landmark is not None:
            self.canvas.delete("landmark_hover")
            self.hovered_landmark = None
        # Ripristina binding originale
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.config(cursor="cross")
        print("✨ Hover effect sui landmarks DISATTIVATO")
    
    def on_landmark_hover(self, event):
        """Gestisce l'hover sui landmarks quando modalità misurazione è attiva."""
        if not (hasattr(self, 'measurement_mode_active') and 
                self.measurement_mode_active and self.measurement_mode_active.get()):
            return
            
        if not self.landmark_measurement_mode or not self.current_landmarks:
            return
            
        try:
            # FIX: usa canvasx/canvasy per conversione corretta delle coordinate
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
            
            # Debug temporaneo disabilitato
            # print(f"🔍 HOVER FIXED: canvas({canvas_x:.1f},{canvas_y:.1f}) -> img({img_x:.1f},{img_y:.1f})")
            
            # DEBUG: Mostra primi landmarks MediaPipe per confronto
            if len(self.current_landmarks) >= 3:
                print(f"# 🔍 LANDMARKS DEBUG (MediaPipe):")
                for i in range(3):
                    lm = self.current_landmarks[i]
                    print(f"   LM[{i}]: ({lm[0]:.1f}, {lm[1]:.1f})")
                print(f"# 🔍 MOUSE IMG: ({img_x:.1f}, {img_y:.1f})")
            
            # Sistema di selezione preciso con isteresi
            target_landmark = self.find_closest_landmark_with_hysteresis(img_x, img_y)
            
            if target_landmark is not None:
                landmark_pos = self.current_landmarks[target_landmark]
                distance = ((img_x - landmark_pos[0])**2 + (landmark_pos[1] - img_y)**2)**0.5
                
                # Nuovo landmark sotto il mouse
                if self.hovered_landmark != target_landmark:
                        # Landmark rilevato - aggiorna visuale
                        # Rimuovi evidenziazione precedente
                        self.canvas.delete("landmark_hover")
                        
                        # USA LA STESSA FUNZIONE UNIFICATA dei landmarks rossi per allineamento perfetto
                        canvas_lm_x, canvas_lm_y = self.image_to_canvas_coords(
                            landmark_pos[0], landmark_pos[1]
                        )
                        
                        print(f"🎯 HOVER DEBUG: landmark_pos=({landmark_pos[0]:.1f},{landmark_pos[1]:.1f}) -> canvas=({canvas_lm_x:.1f},{canvas_lm_y:.1f})")
                        
                        # Crea evidenziazione precisa (ridotta da raggio 8 a 6 pixel)
                        hover_radius = 6
                        self.canvas.create_oval(
                            canvas_lm_x - hover_radius, canvas_lm_y - hover_radius, 
                            canvas_lm_x + hover_radius, canvas_lm_y + hover_radius,
                            outline="yellow", width=2, tags="landmark_hover"
                        )
                        
                        self.hovered_landmark = target_landmark
                        self.canvas.config(cursor="hand2")
                        
                        # Update status bar
                        self.status_bar.config(text=f"🎯 Landmark {target_landmark} - Click per selezionare")
                else:
                    # Troppo lontano, rimuovi evidenziazione
                    if self.hovered_landmark is not None:
                        self.canvas.delete("landmark_hover")
                        self.hovered_landmark = None
                        self.canvas.config(cursor="cross")
                        self.status_bar.config(text="✅ Modalità Misurazione ATTIVA - LANDMARK (hover + click sui punti rossi)")
            else:
                # Nessun landmark vicino
                if self.hovered_landmark is not None:
                    self.canvas.delete("landmark_hover")
                    self.hovered_landmark = None
                    self.canvas.config(cursor="cross")
                    self.status_bar.config(text="✅ Modalità Misurazione ATTIVA - LANDMARK (hover + click sui punti rossi)")
                    
        except Exception as e:
            # Fallback silenzioso per evitare spam di errori
            pass

    def clear_all_drawings(self):
        """Cancella tutti i disegni e le misurazioni dal canvas."""
        # Rimuove tutti gli elementi con tag "drawing" e "temp_drawing"
        self.canvas.delete("drawing")
        self.canvas.delete("temp_drawing")

        # *** NUOVO SISTEMA: Pulisci anche il registry
        self.graphics_registry.clear()

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

    def clear_all_overlays_except_essentials(self):
        """🧹 Pulisce TUTTI gli overlay eccetto landmark, asse di simmetria e green dots."""
        print("🧹 PULIZIA OVERLAY GENERALE - Mantengo solo elementi essenziali...")
        
        # Lista tag da preservare (elementi essenziali)
        essential_tags = ["landmark_point", "symmetry_axis", "green_dot"]
        
        # Pulisci graphics_registry mantenendo solo overlay essenziali
        items_to_remove = []
        for item_id, graphic_data in self.graphics_registry.items():
            if graphic_data.get("is_overlay", False):
                # Verifica se è un overlay non essenziale
                canvas_tags = self.canvas.gettags(item_id) if item_id in self.canvas.find_all() else []
                is_essential = any(tag in essential_tags for tag in canvas_tags)
                
                if not is_essential:
                    items_to_remove.append(item_id)
        
        # Rimuovi overlay non essenziali
        for item_id in items_to_remove:
            try:
                self.canvas.delete(item_id)
                del self.graphics_registry[item_id]
                print(f"🧹 Rimosso overlay: {item_id}")
            except Exception as e:
                print(f"⚠️ Errore rimozione overlay {item_id}: {e}")
        
        # Pulisci specificamente le liste overlay
        self.clear_measurement_overlays()
        self.clear_selection_overlays()
        
        # Pulisci punti selezionati
        self.selected_points.clear()
        self.selected_landmarks.clear()
        
        # Pulisci tag canvas specifici
        self.canvas.delete("selection_overlay")
        self.canvas.delete("selection_point") 
        self.canvas.delete("measurement_overlay")
        
        # Aggiorna visualizzazione
        self.update_canvas_display()
        
        removed_count = len(items_to_remove)
        self.status_bar.config(text=f"🧹 Puliti {removed_count} overlay - mantenuti landmark, asse e green dots")
        print(f"✅ PULIZIA COMPLETATA - Rimossi {removed_count} overlay non essenziali")

    # *** FUNZIONE OBSOLETA - RIMOSSA ***
    # def move_all_drawings() -> Sostituita da transform_all_graphics()
    # Il nuovo sistema unificato gestisce automaticamente il PAN

    # *** FUNZIONE OBSOLETA - RIMOSSA ***
    # def scale_all_drawings() -> Sostituita da transform_all_graphics()
    # Il nuovo sistema unificato gestisce automaticamente il ZOOM

    def scale_drawing_item_coordinated(self, item_id, image_center_x, image_center_y):
        """Scala un elemento usando le coordinate originali memorizzate per evitare accumulo errori."""
        try:
            # Se non abbiamo le coordinate originali, memorizzale ora
            if item_id not in self.original_drawing_coords:
                # USA CENTRO ROTAZIONE (landmark 9) invece del centro immagine
                rotation_center = self.get_rotation_center_from_landmarks()
                rotation_center_canvas = self.convert_image_to_canvas_coords(
                    *rotation_center
                )
                self.store_original_coords(
                    item_id, rotation_center_canvas[0], rotation_center_canvas[1]
                )

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

    # *** FUNZIONE OBSOLETA - RIMOSSA ***
    # def store_original_coords() -> Sostituita da register_graphic()
    # Il nuovo sistema unificato usa graphics_registry invece di original_drawing_coords

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

    def bring_overlays_to_front(self):
        """Porta tutti gli overlay sopra l'immagine di sfondo."""
        try:
            overlay_count = 0
            
            # Porta in primo piano tutti gli overlay registrati
            for item_id, info in self.graphics_registry.items():
                if info.get("is_overlay", False):
                    # Verifica che l'elemento esista ancora sul canvas
                    if item_id in self.canvas.find_all():
                        self.canvas.tag_raise(item_id)
                        overlay_count += 1
            
            # Porta in primo piano anche tutti gli elementi con tag "measurement_overlay"
            tagged_items = self.canvas.find_withtag("measurement_overlay")
            for item in tagged_items:
                self.canvas.tag_raise(item)
                
            # Porta in primo piano anche i green dots
            green_dots_items = self.canvas.find_withtag("green_dots_overlay")
            for item in green_dots_items:
                self.canvas.tag_raise(item)
            
            total_tagged = len(tagged_items)
            total_green_dots = len(green_dots_items)
            print(f"🎯 Portati in primo piano {overlay_count} overlay registrati + {total_tagged} measurement + {total_green_dots} green dots")
            
        except Exception as e:
            print(f"❌ Errore nel portare overlay in primo piano: {e}")

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

        # NUOVO: Pulsanti overlay anteprima
        overlay_frame = ttk.LabelFrame(control_row1, text="Overlay", padding=2)
        overlay_frame.grid(row=0, column=1, padx=5, sticky="w")
        
        ttk.Checkbutton(
            overlay_frame, text="Landmarks", variable=self.show_landmarks_var,
            command=self.update_overlay_settings
        ).grid(row=0, column=0, padx=2)
        
        ttk.Checkbutton(
            overlay_frame, text="Simmetria", variable=self.show_symmetry_var,
            command=self.update_overlay_settings
        ).grid(row=0, column=1, padx=2)
        
        ttk.Checkbutton(
            overlay_frame, text="Poligono", variable=self.show_green_polygon_var,
            command=self.update_overlay_settings
        ).grid(row=0, column=2, padx=2)

        # Controlli playback
        playback_frame = ttk.Frame(control_row1)
        playback_frame.grid(row=0, column=2, padx=5)

        # Pulsanti controllo webcam/video
        self.start_btn = ttk.Button(
            playback_frame, text="▶️", width=3, command=self.start_webcam_analysis
        )
        self.start_btn.pack(side=tk.LEFT, padx=1)

        self.pause_btn = ttk.Button(
            playback_frame, text="⏸️", width=3, command=self.pause_webcam_analysis
        )
        self.pause_btn.pack(side=tk.LEFT, padx=1)

        self.stop_btn = ttk.Button(
            playback_frame, text="⏹️", width=3, command=self.stop_webcam_analysis
        )
        self.stop_btn.pack(side=tk.LEFT, padx=1)

        self.restart_btn = ttk.Button(
            playback_frame, text="🔄", width=3, command=self.restart_webcam_analysis
        )
        self.restart_btn.pack(side=tk.LEFT, padx=1)

        # Pulsante cattura e finestra separata
        capture_frame = ttk.Frame(control_row1)
        capture_frame.grid(row=0, column=3, padx=(5, 0), sticky="e")

        ttk.Button(
            capture_frame,
            text="📸",
            width=3,
            command=self.capture_current_frame,
        ).pack(side=tk.LEFT, padx=1)

        # NUOVO: Pulsante finestra separata
        self.detach_btn = ttk.Button(
            capture_frame,
            text="🗗",
            width=3,
            command=self.detach_preview_window,
        )
        self.detach_btn.pack(side=tk.LEFT, padx=1)
        ToolTip(self.detach_btn, "Scorpora anteprima in finestra separata")

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
                if hasattr(self, 'start_btn'):
                    self.start_btn.config(text="⏸️")
                # Se il video è ripartito dall'inizio, aggiorna anche i controlli
                if not self.video_analyzer.is_capturing:
                    self.update_video_controls_state()
                    if hasattr(self, "update_seek_position"):
                        self.update_seek_position()
            else:
                if hasattr(self, 'start_btn'):
                    self.start_btn.config(text="▶️")

            print(f"🎬 Video {'riprodotto' if is_playing else 'in pausa'}")

    def stop_video(self):
        """Ferma il video/webcam."""
        self.video_analyzer.stop()
        self.is_playing = False
        if hasattr(self, 'start_btn'):
            self.start_btn.config(text="▶️")

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

    def update_overlay_settings(self):
        """Aggiorna le impostazioni degli overlay per l'anteprima."""
        self.video_analyzer.set_overlay_options(
            landmarks=self.show_landmarks_var.get(),
            symmetry=self.show_symmetry_var.get(),
            green_polygon=self.show_green_polygon_var.get()
        )
        print(f"🎨 Overlay aggiornati: Landmarks={self.show_landmarks_var.get()}, "
              f"Simmetria={self.show_symmetry_var.get()}, Poligono={self.show_green_polygon_var.get()}")

    def start_webcam_analysis(self):
        """Avvia l'analisi webcam."""
        if self.video_analyzer.start_webcam():
            print("📹 Webcam avviata")
            self.update_preview_controls_state(True)
        else:
            print("❌ Impossibile avviare webcam")

    def pause_webcam_analysis(self):
        """Pausa l'analisi webcam."""
        self.video_analyzer.pause_webcam()

    def stop_webcam_analysis(self):
        """Ferma l'analisi webcam."""
        self.video_analyzer.stop_webcam()
        self.update_preview_controls_state(False)

    def restart_webcam_analysis(self):
        """Riavvia l'analisi webcam."""
        if self.video_analyzer.restart_webcam():
            print("🔄 Webcam riavviata")
            self.update_preview_controls_state(True)
        else:
            print("❌ Impossibile riavviare webcam")

    def update_preview_controls_state(self, active):
        """Aggiorna lo stato dei controlli dell'anteprima."""
        if hasattr(self, 'pause_btn'):
            state = "normal" if active else "disabled"
            self.pause_btn.config(state=state)
            self.stop_btn.config(state=state)
            self.restart_btn.config(state=state)

    def detach_preview_window(self):
        """Scorpora l'anteprima in una finestra separata con rilevamento automatico secondo monitor."""
        if self.is_preview_detached:
            # Reincorpora l'anteprima nell'interfaccia principale
            self.reattach_preview_window()
            return

        # Crea finestra separata
        self.detached_preview_window = tk.Toplevel(self.root)
        self.detached_preview_window.title("Anteprima Video - Monitor Secondario")
        self.detached_preview_window.configure(bg='black')
        
        # Rilevamento avanzato multi-monitor
        monitor_info = self.detect_multiple_monitors()
        
        if monitor_info['has_secondary']:
            print(f"🖥️ Rilevati {monitor_info['monitor_count']} monitor")
            print(f"📺 Monitor primario: {monitor_info['primary']['width']}x{monitor_info['primary']['height']}")
            print(f"📺 Monitor secondario: {monitor_info['secondary']['width']}x{monitor_info['secondary']['height']}")
            
            # Posiziona a schermo intero sul secondo monitor
            secondary = monitor_info['secondary']
            geometry = f"{secondary['width']}x{secondary['height']}+{secondary['x']}+{secondary['y']}"
            
            self.detached_preview_window.geometry(geometry)
            self.detached_preview_window.overrideredirect(True)  # Rimuove bordi finestra
            self.detached_preview_window.attributes('-fullscreen', True)  # Schermo intero
            self.detached_preview_window.attributes('-topmost', True)  # Sempre in primo piano
            
            print(f"🎯 Finestra anteprima aperta a schermo intero sul monitor 2")
        else:
            print("🖥️ Rilevato solo monitor primario")
            # Monitor singolo - finestra centrata ma grande
            primary_width = monitor_info['primary']['width']
            primary_height = monitor_info['primary']['height']
            
            # Finestra grande ma non a schermo intero su monitor singolo
            window_width = min(1200, int(primary_width * 0.8))
            window_height = min(900, int(primary_height * 0.8))
            pos_x = (primary_width - window_width) // 2
            pos_y = (primary_height - window_height) // 2
            
            self.detached_preview_window.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
            print(f"🎯 Finestra anteprima aperta centrata ({window_width}x{window_height})")

        # Label per l'anteprima separata
        self.detached_preview_label = tk.Label(
            self.detached_preview_window,
            bg="black",
            text="Anteprima Video Separata\n\nIn attesa del segnale...",
            fg="white",
            font=("Arial", 14),
            justify=tk.CENTER,
        )
        self.detached_preview_label.pack(expand=True, fill=tk.BOTH)

        # Frame controlli per finestra separata
        if monitor_info['has_secondary']:
            # Per schermo intero su secondo monitor: controlli minimali overlay
            control_frame = tk.Frame(self.detached_preview_window, bg='black', height=50)
            control_frame.pack(side=tk.BOTTOM, fill=tk.X)
            control_frame.pack_propagate(False)
            
            # Pulsanti con stile adatto per overlay su schermo nero
            btn_frame = tk.Frame(control_frame, bg='black')
            btn_frame.pack(expand=True)
            
            ttk.Button(
                btn_frame,
                text="↩️ Chiudi Fullscreen",
                command=self.reattach_preview_window
            ).pack(side=tk.LEFT, padx=10, pady=10)
            
            ttk.Button(
                btn_frame,
                text="🔄 Esci da Schermo Intero",
                command=lambda: self.toggle_fullscreen_preview(False)
            ).pack(side=tk.LEFT, padx=10, pady=10)
            
        else:
            # Per monitor singolo: controlli normali
            control_frame = ttk.Frame(self.detached_preview_window)
            control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
            
            ttk.Button(
                control_frame,
                text="↩️ Reincorpora nell'interfaccia",
                command=self.reattach_preview_window
            ).pack(side=tk.LEFT)

        # Aggiorna stato
        self.is_preview_detached = True
        self.detach_btn.config(text="↩️")
        if hasattr(self, 'detach_btn'):
            ToolTip(self.detach_btn, "Reincorpora anteprima nell'interfaccia")

        # Nascondi anteprima principale
        if hasattr(self, 'integrated_preview_frame'):
            self.integrated_preview_frame.grid_remove()

        # Gestisci eventi finestra
        self.detached_preview_window.protocol("WM_DELETE_WINDOW", self.reattach_preview_window)
        
        # Scorciatoie da tastiera per finestra fullscreen
        if monitor_info['has_secondary']:
            self.detached_preview_window.bind('<Escape>', lambda e: self.toggle_fullscreen_preview(False))
            self.detached_preview_window.bind('<F11>', lambda e: self.toggle_fullscreen_preview())
            self.detached_preview_window.bind('<Alt-Return>', lambda e: self.reattach_preview_window())
            self.detached_preview_window.focus_set()  # Abilita ricezione eventi tastiera
            
            print("🗗 Anteprima aperta a SCHERMO INTERO su monitor 2")
            print("⌨️  Tasti: ESC=Esci fullscreen, F11=Toggle, Alt+Enter=Chiudi")
        else:
            print("🗗 Anteprima scorporata in finestra separata")

    def reattach_preview_window(self):
        """Reincorpora l'anteprima nell'interfaccia principale."""
        if self.detached_preview_window:
            self.detached_preview_window.destroy()
            self.detached_preview_window = None
            self.detached_preview_label = None

        self.is_preview_detached = False
        self.detach_btn.config(text="🗗")
        if hasattr(self, 'detach_btn'):
            ToolTip(self.detach_btn, "Scorpora anteprima in finestra separata")

        # Ripristina anteprima principale
        if hasattr(self, 'integrated_preview_frame'):
            self.integrated_preview_frame.grid()

        print("↩️ Anteprima reincorporata nell'interfaccia principale")

    def toggle_fullscreen_preview(self, fullscreen=None):
        """Toggle modalità fullscreen per finestra anteprima."""
        if not self.detached_preview_window:
            return
            
        try:
            if fullscreen is None:
                # Toggle automatico
                current_fullscreen = self.detached_preview_window.attributes('-fullscreen')
                new_fullscreen = not current_fullscreen
            else:
                new_fullscreen = fullscreen
                
            if new_fullscreen:
                # Attiva fullscreen
                self.detached_preview_window.attributes('-fullscreen', True)
                self.detached_preview_window.attributes('-topmost', True)
                print("🔲 Finestra anteprima: Schermo intero ON")
            else:
                # Disattiva fullscreen
                self.detached_preview_window.attributes('-fullscreen', False)
                self.detached_preview_window.attributes('-topmost', False)
                self.detached_preview_window.overrideredirect(False)
                
                # Ridimensiona a finestra normale
                self.detached_preview_window.geometry("1200x900+100+100")
                print("🔳 Finestra anteprima: Schermo intero OFF")
                
        except Exception as e:
            print(f"❌ Errore toggle fullscreen: {e}")

    def detect_multiple_monitors(self):
        """Rileva la presenza e configurazione di monitor multipli."""
        try:
            import subprocess
            import json
            
            # Metodo 1: Usa wmic per Windows (più affidabile)
            try:
                result = subprocess.run(
                    ['wmic', 'desktopmonitor', 'get', 'screenwidth,screenheight', '/format:csv'],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    lines = [line.strip() for line in result.stdout.split('\n') if line.strip() and 'Node' not in line and 'ScreenHeight' not in line]
                    monitors = []
                    for line in lines:
                        parts = line.split(',')
                        if len(parts) >= 3:
                            try:
                                height = int(parts[1]) if parts[1] else 0
                                width = int(parts[2]) if parts[2] else 0
                                if width > 0 and height > 0:
                                    monitors.append({'width': width, 'height': height})
                            except (ValueError, IndexError):
                                continue
                    
                    if len(monitors) >= 2:
                        # Configura monitor primario e secondario
                        primary = monitors[0]
                        secondary = monitors[1]
                        
                        return {
                            'has_secondary': True,
                            'monitor_count': len(monitors),
                            'primary': {
                                'width': primary['width'],
                                'height': primary['height'],
                                'x': 0,
                                'y': 0
                            },
                            'secondary': {
                                'width': secondary['width'],
                                'height': secondary['height'],
                                'x': primary['width'],  # Posiziona a destra del primario
                                'y': 0
                            }
                        }
            except Exception as e:
                print(f"⚠️ Errore rilevamento wmic: {e}")
            
            # Metodo 2: Fallback con tkinter
            try:
                # Ottieni dimensioni schermo totali
                total_width = self.root.winfo_screenwidth()
                total_height = self.root.winfo_screenheight()
                
                # Ottieni dimensioni finestra root per stimare monitor primario
                self.root.update_idletasks()
                root_width = self.root.winfo_width()
                
                # Euristica: se larghezza totale > 1.5 * altezza, probabilmente dual monitor
                aspect_ratio = total_width / total_height
                if aspect_ratio > 2.5:  # Tipico di configurazione dual monitor 16:9
                    estimated_primary_width = total_width // 2
                    
                    return {
                        'has_secondary': True,
                        'monitor_count': 2,
                        'primary': {
                            'width': estimated_primary_width,
                            'height': total_height,
                            'x': 0,
                            'y': 0
                        },
                        'secondary': {
                            'width': estimated_primary_width,
                            'height': total_height,
                            'x': estimated_primary_width,
                            'y': 0
                        }
                    }
                
            except Exception as e:
                print(f"⚠️ Errore rilevamento tkinter: {e}")
            
            # Fallback: solo monitor primario
            return {
                'has_secondary': False,
                'monitor_count': 1,
                'primary': {
                    'width': self.root.winfo_screenwidth(),
                    'height': self.root.winfo_screenheight(),
                    'x': 0,
                    'y': 0
                },
                'secondary': None
            }
            
        except Exception as e:
            print(f"❌ Errore generale rilevamento monitor: {e}")
            # Fallback sicuro
            return {
                'has_secondary': False,
                'monitor_count': 1,
                'primary': {
                    'width': 1920,
                    'height': 1080,
                    'x': 0,
                    'y': 0
                },
                'secondary': None
            }

    def update_video_controls_state(self):
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

    def update_landmarks_table(self):
        """Aggiorna la tabella dei landmarks rilevati."""
        # Pulisce la tabella
        for item in self.landmarks_tree.get_children():
            self.landmarks_tree.delete(item)
        
        if not hasattr(self, 'current_landmarks') or self.current_landmarks is None:
            # Mostra esempi di landmarks che verranno rilevati
            example_landmarks = [
                ("9", "🎯 Glabella (Centro Fronte)", "Richiede", "rilevamento", "⏳"),
                ("10", "🏠 Fronte Centro", "landmarks", "facciali", "⏳"),
                ("152", "🎭 Mento Centro", "Carica", "immagine", "⏳"),
                ("1", "👃 Ponte Nasale", "o avvia", "webcam", "⏳"),
                ("33", "👁️ Occhio Sinistro", "per", "rilevare", "⏳")
            ]
            
            for landmark_data in example_landmarks:
                self.landmarks_tree.insert('', 'end', values=landmark_data, tags=("example",))
            
            # Stile per gli esempi
            self.landmarks_tree.tag_configure("example", background="#f8f9fa", foreground="#6c757d")
            return
            
        # Popola con landmarks importanti
        important_landmarks = [9, 10, 152, 1, 2, 33, 133, 362, 263, 13, 14, 78, 308]
        
        for idx in important_landmarks:
            if idx < len(self.current_landmarks):
                landmark = self.current_landmarks[idx]
                
                # Gestisce diversi formati di landmark (oggetto vs tuple)
                try:
                    if hasattr(landmark, 'x') and hasattr(landmark, 'y'):
                        # Formato oggetto MediaPipe (coordinate normalizzate 0-1)
                        lm_x = landmark.x
                        lm_y = landmark.y
                        visibility = getattr(landmark, 'visibility', 1.0)
                        
                        # Calcola coordinate pixel
                        img_width = self.original_image_for_rotations.shape[1] if hasattr(self, 'original_image_for_rotations') and self.original_image_for_rotations is not None else 640
                        img_height = self.original_image_for_rotations.shape[0] if hasattr(self, 'original_image_for_rotations') and self.original_image_for_rotations is not None else 480
                        
                        x = int(lm_x * img_width)
                        y = int(lm_y * img_height)
                        
                    elif isinstance(landmark, (tuple, list)) and len(landmark) >= 2:
                        # Formato tuple/lista (coordinate già in pixel)
                        x = int(landmark[0])
                        y = int(landmark[1])
                        visibility = 1.0  # Assume visibile se non specificato
                    else:
                        continue  # Salta landmarks in formato non riconosciuto
                        
                except Exception as e:
                    print(f"⚠️ Errore nel processare landmark {idx}: {e}")
                    continue
                
                # Nome del landmark
                name = self.landmark_names.get(idx, f"Landmark {idx}")
                
                # Visibilità (usando la variabile visibility già calcolata)
                visibility_icon = "✅" if visibility > 0.5 else "⚠️" if visibility > 0.3 else "❌"
                
                # Colore riga basato su visibilità
                tags = ()
                if visibility > 0.7:
                    tags = ("high_vis",)
                elif visibility > 0.4:  
                    tags = ("med_vis",)
                else:
                    tags = ("low_vis",)
                
                self.landmarks_tree.insert('', 'end', values=(
                    str(idx), name, str(x), str(y), visibility_icon
                ), tags=tags)
        
        # Configurazione colori per le righe
        self.landmarks_tree.tag_configure("high_vis", background="#d4edda")  # Verde chiaro
        self.landmarks_tree.tag_configure("med_vis", background="#fff3cd")   # Giallo chiaro  
        self.landmarks_tree.tag_configure("low_vis", background="#f8d7da")   # Rosso chiaro

    def on_landmark_double_click(self, event):
        """Gestisce il doppio click su un landmark nella tabella per centrarlo sul canvas."""
        selection = self.landmarks_tree.selection()
        if not selection:
            return
            
        # Ottieni i dati del landmark selezionato
        item_values = self.landmarks_tree.item(selection[0], 'values')
        if len(item_values) < 4 or item_values[0] == "N/A":
            return
            
        try:
            landmark_id = int(item_values[0])
            x = int(item_values[2])
            y = int(item_values[3])
            
            # Centra il canvas su questo punto
            if hasattr(self, 'canvas') and self.canvas:
                # Converti coordinate immagine in coordinate canvas
                canvas_x = x * self.canvas_scale + self.canvas_offset_x
                canvas_y = y * self.canvas_scale + self.canvas_offset_y
                
                # Calcola offset per centrare
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                
                target_offset_x = (canvas_width // 2) - canvas_x
                target_offset_y = (canvas_height // 2) - canvas_y
                
                # Aggiorna offset
                self.canvas_offset_x = target_offset_x
                self.canvas_offset_y = target_offset_y
                
                # Aggiorna la visualizzazione
                self.update_canvas_display()
                
                # Feedback all'utente
                landmark_name = item_values[1]
                self.status_bar.config(text=f"🎯 Centrato su: {landmark_name} (ID: {landmark_id})")
                
        except (ValueError, IndexError) as e:
            print(f"Errore nel centrare landmark: {e}")

    def setup_measurements_area(self, parent):
        """Configura l'area delle misurazioni in modo compatto."""
        # Frame principale per l'area misurazioni
        main_frame = ttk.Frame(parent)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Treeview per le misurazioni esistenti con stile bootstrap
        self.measurements_tree = ttk.Treeview(
            main_frame,
            columns=("Type", "Value", "Unit", "Status"),
            show="headings",
            height=8,
            bootstyle="info"  # Stile bootstrap azzurro
        )

        # Intestazioni con emoji per miglior UX
        self.measurements_tree.heading("Type", text="📏 Tipo Misurazione")
        self.measurements_tree.heading("Value", text="📊 Valore")
        self.measurements_tree.heading("Unit", text="📐 Unità")
        self.measurements_tree.heading("Status", text="✅ Stato")

        # Configurazione colonne ottimizzata
        self.measurements_tree.column("Type", width=200, minwidth=150)
        self.measurements_tree.column("Value", width=100, minwidth=80)
        self.measurements_tree.column("Unit", width=80, minwidth=60)
        self.measurements_tree.column("Status", width=100, minwidth=80)

        # Scrollbar per la lista misurazioni
        tree_scroll = ttk.Scrollbar(
            main_frame, orient=tk.VERTICAL, command=self.measurements_tree.yview
        )
        self.measurements_tree.configure(yscrollcommand=tree_scroll.set)

        # Layout ottimizzato con grid
        self.measurements_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")

    def setup_status_bar(self):
        """Configura la status bar con progressbar moderna."""
        # Frame per la status bar con layout orizzontale
        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        status_frame.grid_columnconfigure(0, weight=1)
        
        # Label di stato principale con stile info
        self.status_bar = ttk.Label(status_frame, text="✅ Pronto", bootstyle="info")
        self.status_bar.grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        # Progressbar per operazioni lunghe con stile success
        self.progress_bar = ttk.Progressbar(
            status_frame, 
            mode="determinate", 
            length=200,
            bootstyle="success-striped"
        )
        self.progress_bar.grid(row=0, column=1, padx=(0, 10))
        self.progress_bar.grid_remove()  # Nascosta inizialmente
        
        # Label per percentuale progresso
        self.progress_label = ttk.Label(status_frame, text="", bootstyle="secondary")
        self.progress_label.grid(row=0, column=2, padx=(0, 10))
        self.progress_label.grid_remove()  # Nascosta inizialmente
    
    def show_progress(self, message="Elaborazione in corso...", max_value=100):
        """Mostra la progressbar con un messaggio."""
        self.status_bar.config(text=f"⏳ {message}")
        self.progress_bar.config(maximum=max_value, value=0)
        self.progress_bar.grid()
        self.progress_label.grid()
        self.progress_label.config(text="0%")
        self.root.update_idletasks()
    
    def update_progress(self, value, percentage_text=""):
        """Aggiorna il valore della progressbar."""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.config(value=value)
            if percentage_text:
                self.progress_label.config(text=percentage_text)
            else:
                max_val = self.progress_bar.cget('maximum')
                percent = int((value / max_val) * 100) if max_val > 0 else 0
                self.progress_label.config(text=f"{percent}%")
            self.root.update_idletasks()
    
    def hide_progress(self, success_message="✅ Completato"):
        """Nasconde la progressbar e mostra messaggio finale."""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.grid_remove()
            self.progress_label.grid_remove()
        self.status_bar.config(text=success_message)
    
    def update_webcam_badge(self, connected=False):
        """Aggiorna il badge dello stato webcam."""
        if hasattr(self, 'webcam_badge'):
            if connected:
                self.webcam_badge.config(text="📷 Webcam: Attiva", bootstyle="success")
            else:
                self.webcam_badge.config(text="📷 Webcam: Disconnessa", bootstyle="danger")
    
    def update_landmarks_badge(self, count=0):
        """Aggiorna il badge dei landmarks rilevati."""
        if hasattr(self, 'landmarks_badge'):
            if count > 0:
                self.landmarks_badge.config(
                    text=f"🎯 Landmarks: {count} rilevati", 
                    bootstyle="success"
                )
            else:
                self.landmarks_badge.config(text="🎯 Landmarks: 0 rilevati", bootstyle="warning")
    
    def update_quality_badge(self, score=None):
        """Aggiorna il badge della qualità immagine."""
        if hasattr(self, 'quality_badge'):
            if score is not None:
                if score > 0.8:
                    style = "success"
                    quality = "Ottima"
                elif score > 0.6:
                    style = "info"
                    quality = "Buona"
                elif score > 0.4:
                    style = "warning"
                    quality = "Media"
                else:
                    style = "danger"
                    quality = "Bassa"
                self.quality_badge.config(
                    text=f"✨ Qualità: {quality} ({score:.2f})", 
                    bootstyle=style
                )
            else:
                self.quality_badge.config(text="✨ Qualità: N/A", bootstyle="secondary")
    
    def update_mode_badge(self, mode="Selezione"):
        """Aggiorna il badge della modalità corrente."""
        if hasattr(self, 'mode_badge'):
            mode_styles = {
                "Selezione": "primary",
                "Pan": "info", 
                "Misurazione": "success",
                "Rotazione": "warning"
            }
            style = mode_styles.get(mode, "secondary")
            self.mode_badge.config(text=f"🔧 Modalità: {mode}", bootstyle=style)

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

    # *** METODO test_webcam() RIMOSSO ***
    # La funzionalità di test webcam è stata rimossa per semplificare l'interfaccia.
    # L'avvio della webcam ora gestisce automaticamente i test di disponibilità.

    def start_webcam(self):
        """Avvia l'analisi dalla webcam."""
        print("Tentativo di avvio webcam...")

        # Reset completo interfaccia per nuova analisi webcam
        self.reset_interface_for_new_analysis()

        if self.video_analyzer.start_camera_capture():
            print("Webcam avviata con successo, iniziando analisi...")

            # Cattura il primo frame per impostare la scala appropriata
            self._setup_webcam_scale()

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

    def _setup_webcam_scale(self):
        """Imposta una scala appropriata per la webcam basata sulle dimensioni del primo frame."""
        try:
            # Cattura un frame di test per determinare le dimensioni
            if self.video_analyzer.capture and self.video_analyzer.capture.isOpened():
                ret, frame = self.video_analyzer.capture.read()
                if ret and frame is not None:
                    # Calcola scala ottimale basata sulle dimensioni del frame
                    optimal_scale = self._calculate_optimal_scale(frame.shape)
                    self.canvas_scale = optimal_scale
                    
                    print(f"🎥 Scala webcam impostata: {self.canvas_scale:.3f} per frame {frame.shape[1]}x{frame.shape[0]}")
                    
                    # Reset offset per centrare
                    self.canvas_offset_x = 0
                    self.canvas_offset_y = 0
                else:
                    print("⚠️ Impossibile catturare frame per calcolare scala webcam")
            else:
                print("⚠️ Capture webcam non disponibile per calcolo scala")
        except Exception as e:
            print(f"❌ Errore setup scala webcam: {e}")

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
            self.set_current_image(best_frame, best_landmarks, auto_resize=True)
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
        if self.preview_enabled and self.preview_enabled.get():
            try:
                # Calcola dimensioni proporzionate mantenendo aspect ratio
                frame_height, frame_width = frame.shape[:2]
                aspect_ratio = frame_width / frame_height

                # Area disponibile nell'anteprima
                if self.is_preview_detached and self.detached_preview_label:
                    # Per finestra separata: dimensioni più grandi
                    max_width = 1200
                    max_height = 900
                    target_label = self.detached_preview_label
                else:
                    # Per anteprima integrata
                    max_width = 390
                    max_height = 290
                    target_label = self.preview_label

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
                    0, lambda: self.update_preview_display(photo, target_label)
                )
            except Exception as e:
                print(f"Errore nell'aggiornamento anteprima: {e}")

    def update_preview_display(self, photo, target_label):
        """Aggiorna il display dell'anteprima (integrata o separata)."""
        try:
            if target_label:
                target_label.configure(image=photo, text="")
                target_label.image = photo  # Mantiene riferimento
        except Exception as e:
            print(f"Errore nell'aggiornamento display anteprima: {e}")

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
            if hasattr(self, 'start_btn'):
                self.start_btn.config(text="▶️")

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

    def update_integrated_preview_display(self, photo):
        """Aggiorna il display dell'anteprima integrata."""
        try:
            if self.preview_label:
                self.preview_label.configure(image=photo, text="")
                self.preview_label.image = photo  # Mantiene riferimento
        except Exception as e:
            print(f"Errore nell'aggiornamento display anteprima integrata: {e}")
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

        # SALVA IMMAGINE CORRENTE E ORIGINALE NON RUOTATA
        self.current_image = image_array.copy()
        self.current_image_on_canvas = image_array.copy()
        self.current_landmarks = landmarks

        # SALVA L'IMMAGINE ORIGINALE PER LE ROTAZIONI
        self.original_base_image = image_array.copy()
        self.original_base_landmarks = landmarks.copy() if landmarks else None

        # DEBUG: Verifica salvataggio landmarks
        if self.original_base_landmarks:
            print(
                f"💾 Salvati {len(self.original_base_landmarks)} landmarks per rotazioni"
            )
            if len(self.original_base_landmarks) > 9:
                glabella = self.original_base_landmarks[9]
                print(f"🎯 Landmark 9 (glabella) salvato a: {glabella}")
        else:
            print("⚠️ Nessun landmark salvato per rotazioni!")

        # RESETTA LA ROTAZIONE QUANDO SI CARICA UNA NUOVA IMMAGINE
        self.current_rotation = 0.0
        self.original_unrotated_coords = {}  # Resetta anche le coordinate dei disegni

        print(
            f"💾 Salvata immagine originale per rotazioni: {self.original_base_image.shape}"
        )

        # RIPRISTINA SCALA E OFFSET se auto_resize
        if auto_resize:
            # Calcola scala ottimale per adattare l'immagine al canvas
            self.canvas_scale = self._calculate_optimal_scale(image_array.shape)
            self.canvas_offset_x = 0
            self.canvas_offset_y = 0
            print(f"Auto-resize attivato: scala={self.canvas_scale:.3f}")

        # Se non ci sono landmarks, rileva automaticamente
        if landmarks is None:
            print("Rilevamento automatico landmarks...")
            self.detect_landmarks()
            # detect_landmarks chiama già update_canvas_display
        else:
            # Visualizza direttamente
            print("Visualizzazione immagine con landmarks forniti...")
            self.update_canvas_display()

        # Aggiorna la tabella landmarks se esiste
        if hasattr(self, 'landmarks_tree'):
            self.update_landmarks_table()

        print("✅ set_current_image completato")

    def _calculate_optimal_scale(self, image_shape):
        """Calcola la scala ottimale per adattare l'immagine al canvas."""
        try:
            # Attendi che il canvas sia renderizzato per ottenere dimensioni reali
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Se il canvas non è ancora pronto, usa dimensioni di default
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width = 800  # Larghezza di default
                canvas_height = 600  # Altezza di default
                print(f"Canvas non pronto, usando dimensioni default: {canvas_width}x{canvas_height}")
            
            # Ottieni dimensioni immagine
            img_height, img_width = image_shape[:2]
            
            # Calcola fattori di scala per adattare al canvas (con margine del 10%)
            margin_factor = 0.9  # Lascia un 10% di margine
            scale_x = (canvas_width * margin_factor) / img_width
            scale_y = (canvas_height * margin_factor) / img_height
            
            # Usa la scala minore per mantenere proporzioni
            optimal_scale = min(scale_x, scale_y)
            
            # Limita la scala tra 0.1 e 2.0 per evitare estremi
            optimal_scale = max(0.1, min(2.0, optimal_scale))
            
            print(f"📐 Calcolo scala ottimale:")
            print(f"   Canvas: {canvas_width}x{canvas_height}")
            print(f"   Immagine: {img_width}x{img_height}")
            print(f"   Scala X: {scale_x:.3f}, Scala Y: {scale_y:.3f}")
            print(f"   Scala ottimale: {optimal_scale:.3f}")
            
            return optimal_scale
            
        except Exception as e:
            print(f"❌ Errore calcolo scala ottimale: {e}")
            return 1.0  # Fallback alla scala 1:1

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
            
            # Evidenzia il landmark più vicino al mouse per feedback visivo
            hovered_landmark = getattr(self, 'hovered_landmark', None)
            
            display_image = self.face_detector.draw_landmarks(
                display_image,
                self.current_landmarks,
                draw_all=True,
                key_only=False,
                zoom_factor=getattr(self, 'canvas_scale', 1.0),
                highlight_landmark=hovered_landmark,  # Passa l'indice del landmark da evidenziare
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

        # DISABILITATO: Green dots ora disegnati sul canvas, non sull'immagine PIL
        # Il sistema graphics_registry gestisce automaticamente rotazione, zoom e pan
        #
        # # Disegna puntini verdi SOLO se abilitati nell'interfaccia  
        # if (
        #     hasattr(self, "green_dots_var")
        #     and hasattr(self.green_dots_var, "get")
        #     and self.green_dots_var.get()
        #     and hasattr(self, "green_dots_overlay")
        #     and self.green_dots_overlay is not None
        # ):
        #     print("🎯 Disegno puntini verdi - abilitati nell'interfaccia")
        #     # Applica overlay trasparente puntini verdi
        #     try:
        #         display_pil = Image.fromarray(
        #             cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
        #         )
        #         display_pil = Image.alpha_composite(
        #             display_pil.convert("RGBA"), self.green_dots_overlay.convert("RGBA")
        #         )
        #         display_image = cv2.cvtColor(
        #             np.array(display_pil.convert("RGB")), cv2.COLOR_RGB2BGR
        #         )
        #     except Exception as e:
        #         print(f"Errore overlay puntini verdi: {e}")

        # DISABILITATO: Gli overlay ora sono disegnati sul canvas Tkinter, non sull'immagine OpenCV
        # Il sistema graphics_registry gestisce automaticamente rotazione, zoom e pan
        # 
        # # Disegna overlay misurazioni SOLO se abilitati nell'interfaccia
        # if (
        #     hasattr(self, "overlay_var")
        #     and hasattr(self.overlay_var, "get")
        #     and self.overlay_var.get()
        #     and hasattr(self, "draw_measurement_overlays")
        # ):
        #     print("🎯 Disegno overlay misurazioni - abilitati nell'interfaccia")
        #     display_image = self.draw_measurement_overlays(display_image)
        # 
        # # Disegna SEMPRE i preset_overlays (misurazioni predefinite)
        # if hasattr(self, "preset_overlays") and self.preset_overlays:
        #     print("🎯 Disegno preset overlays (misurazioni predefinite)")
        #     display_image = self.draw_preset_overlays(display_image)

        # 🎯 SOLUZIONE PROBLEMA 2: I punti selezionati sono ora gestiti come overlay rotanti
        # NON disegnare più qui - sono gestiti dal sistema graphics_registry unificato
        # I punti selezionati vengono convertiti automaticamente in overlay con linee
        if hasattr(self, "selected_points") and self.selected_points:
            # I punti sono ora overlay registrati - niente da disegnare qui
            pass  # Il disegno è gestito dal sistema unificato overlay

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

                # Centra l'immagine nel canvas
                x_pos = max(0, (canvas_width - new_width) // 2) + self.canvas_offset_x
                y_pos = max(0, (canvas_height - new_height) // 2) + self.canvas_offset_y

                # Riutilizza l'immagine esistente invece di ricrearla
                if hasattr(self, 'canvas_image_id') and self.canvas_image_id and self.canvas_image_id in self.canvas.find_all():
                    # Aggiorna solo posizione e immagine dell'elemento esistente
                    self.canvas.coords(self.canvas_image_id, x_pos, y_pos)
                    self.canvas.itemconfig(self.canvas_image_id, image=self.tk_image)
                    print(f"🔄 Aggiornata immagine esistente ID {self.canvas_image_id} a ({x_pos}, {y_pos})")
                else:
                    # Crea nuova immagine solo se necessario
                    # Prima rimuovi eventuali immagini vecchie
                    for item in self.canvas.find_all():
                        tags = self.canvas.gettags(item)
                        if not any(tag in ["drawing", "temp_drawing", "measurement_overlay"] for tag in tags):
                            item_type = self.canvas.type(item)
                            if item_type == "image":
                                self.canvas.delete(item)
                    
                    self.canvas_image_id = self.canvas.create_image(
                        x_pos, y_pos, anchor=tk.NW, image=self.tk_image
                    )
                    print(f"🆕 Creata nuova immagine ID {self.canvas_image_id} a ({x_pos}, {y_pos})")
                    
                    # IMPORTANTE: Porta immediatamente gli overlay sopra la nuova immagine
                    self.bring_overlays_to_front()

                # IMPORTANTE: Mantieni riferimento per evitare garbage collection
                self.canvas.image = self.tk_image

                # CRITICO: Porta i disegni in primo piano sopra l'immagine
                self.canvas.tag_raise("drawing")
                self.canvas.tag_raise("temp_drawing")

                # Porta in primo piano anche i disegni dei layer specifici
                if hasattr(self, "layers_list") and self.layers_list:
                    for layer in self.layers_list:
                        self.canvas.tag_raise(layer["tag"])

                # IMPORTANTE: Porta gli overlay SOPRA l'immagine
                self.bring_overlays_to_front()

                print(
                    f"✅ Immagine posizionata a ({x_pos}, {y_pos}) con ID {self.canvas_image_id} - Disegni portati in primo piano"
                )

                # LANDMARKS CANVAS RIMOSSI - ora sono disegnati solo sull'immagine per evitare duplicazioni
                # Se necessario il disegno diretto sul canvas, usare draw_landmarks_on_canvas()
                print("📍 Landmarks gestiti tramite immagine overlay (no duplicazioni canvas)")

                # Forza l'aggiornamento visivo
                self.canvas.update_idletasks()

        except Exception as e:
            print(f"❌ Errore aggiornamento canvas: {e}")
            import traceback

            traceback.print_exc()

    def draw_landmarks_on_canvas(self, img_x_offset, img_y_offset, scale):
        """Disegna i landmarks sul canvas tkinter (VERSIONE UNIFICATA + ANTI-DUPLICAZIONE)."""
        if not self.current_landmarks:
            return
            
        # CRITICO: Pulisci i landmarks precedenti per evitare accumulo
        self.canvas.delete("landmark_canvas")
        print("🧹 Landmarks precedenti rimossi dal canvas")

        for landmark_idx, (x, y) in enumerate(self.current_landmarks):
            # USA LA FUNZIONE UNIFICATA per consistenza con l'hover
            canvas_x, canvas_y = self.image_to_canvas_coords(x, y)
            
            # Debug solo per i primi 3 landmarks per evitare spam
            if landmark_idx < 3:
                print(f"🔴 LANDMARK {landmark_idx}: img({x:.1f},{y:.1f}) -> canvas({canvas_x:.1f},{canvas_y:.1f})")

            # Disegna punto landmark con tag per identificazione
            radius = max(1, int(2 * scale))
            self.canvas.create_oval(
                canvas_x - radius,
                canvas_y - radius,
                canvas_x + radius,
                canvas_y + radius,
                fill="red",
                outline="darkred",
                width=1,
                tags="landmark_canvas"
            )

        print(f"✅ Disegnati {len(self.current_landmarks)} landmarks con conversione unificata")

    def detect_landmarks(self):
        """Rileva i landmark facciali nell'immagine corrente."""
        if self.current_image is not None:
            landmarks = self.face_detector.detect_face_landmarks(self.current_image)
            self.current_landmarks = landmarks

            # CRITICO: Aggiorna anche i landmarks originali per le rotazioni
            if landmarks and not self.original_base_landmarks:
                self.original_base_landmarks = landmarks.copy()
                print(
                    f"💾 Salvati {len(landmarks)} landmarks per rotazioni (detect_landmarks)"
                )
                if len(landmarks) > 9:
                    glabella = landmarks[9]
                    print(f"🎯 Landmark 9 (glabella) salvato a: {glabella}")

            # Aggiorna la visualizzazione del canvas tkinter
            self.update_canvas_display()
            
            # Aggiorna la tabella landmarks se esiste
            if hasattr(self, 'landmarks_tree'):
                self.update_landmarks_table()

            if landmarks:
                self.status_bar.config(text=f"Rilevati {len(landmarks)} landmark")
            else:
                self.status_bar.config(text="Nessun volto rilevato")

    def voice_landmarks_command(self):
        """Comando vocale per landmarks: rileva e attiva overlay come il pulsante."""
        if self.current_image is None:
            self.status_bar.config(text="❌ Carica prima un'immagine")
            return
        
        # Se non ci sono landmarks, rileva prima
        if self.current_landmarks is None:
            self.detect_landmarks()
        
        # Attiva l'overlay dei landmarks (comportamento identico al pulsante)
        if hasattr(self, 'all_landmarks_var'):
            if not self.all_landmarks_var.get():
                self.all_landmarks_var.set(True)
                # Aggiorna il pulsante landmarks
                if hasattr(self, 'landmarks_button'):
                    self.update_button_style(self.landmarks_button, True)
                print("🔵 Overlay landmarks attivato tramite comando vocale")
                self.update_canvas_display()
                
                if self.current_landmarks:
                    self.status_bar.config(text=f"✅ Overlay landmarks attivato - {len(self.current_landmarks)} punti visibili")
                else:
                    self.status_bar.config(text="❌ Nessun landmark da visualizzare")
            else:
                # Se già attivo, ririleva i landmarks
                self.detect_landmarks()
                self.status_bar.config(text="🔄 Landmarks aggiornati")
        else:
            self.status_bar.config(text="❌ Sistema landmarks non disponibile")

    def voice_which_eyebrow_bigger(self):
        """Comando vocale: analizza quale sopracciglio è più grande."""
        if self.current_image is None:
            self.status_bar.config(text="❌ Carica prima un'immagine")
            return
        
        # FASE 1: Simula click sul pulsante "Mostra Aree Sopraccigli"
        print("🎯 Fase 1: Attivazione misurazione aree sopraccigli...")
        
        # Verifica che i landmarks siano disponibili
        if not self.current_landmarks:
            self.detect_landmarks()
            if not self.current_landmarks:
                self.status_bar.config(text="❌ Impossibile rilevare landmarks per l'analisi")
                return
        
        # Attiva la misurazione delle aree sopraccigli (simula click pulsante)
        if self.preset_overlays["eyebrow_areas"] is None:
            self.measure_eyebrow_areas()
            print("✅ Misurazione aree sopraccigli completata")
        
        # FASE 2: Legge i valori dalla tabella misurazioni
        print("🎯 Fase 2: Lettura valori dalla tabella misurazioni...")
        
        if not hasattr(self, 'measurements_tree') or not self.measurements_tree:
            self.status_bar.config(text="❌ Tabella misurazioni non disponibile")
            return
        
        # Cerca le misurazioni delle aree sopraccigli nella tabella
        left_area_value = None
        right_area_value = None
        
        for item in self.measurements_tree.get_children():
            values = self.measurements_tree.item(item, 'values')
            if len(values) >= 2:
                measurement_type = values[0]  # Colonna "Tipo Misurazione"
                measurement_value = values[1]  # Colonna "Valore"
                
                if "Area Sopracciglio Sinistro" in measurement_type:
                    try:
                        left_area_value = float(measurement_value)
                        print(f"📊 Area sopracciglio sinistro: {left_area_value} px²")
                    except ValueError:
                        print(f"⚠️ Errore conversione valore sinistro: {measurement_value}")
                
                elif "Area Sopracciglio Destro" in measurement_type:
                    try:
                        right_area_value = float(measurement_value)
                        print(f"📊 Area sopracciglio destro: {right_area_value} px²")
                    except ValueError:
                        print(f"⚠️ Errore conversione valore destro: {measurement_value}")
        
        # Analisi e risposta vocale
        if left_area_value is not None and right_area_value is not None:
            difference = abs(left_area_value - right_area_value)
            
            if left_area_value > right_area_value:
                bigger_eyebrow = "sinistro"
                bigger_value = left_area_value
                smaller_value = right_area_value
            elif right_area_value > left_area_value:
                bigger_eyebrow = "destro"
                bigger_value = right_area_value
                smaller_value = left_area_value
            else:
                # Caso molto raro: aree identiche
                response_text = f"Le aree dei sopraccigli sono identiche: {left_area_value:.1f} pixel quadrati ciascuno"
                self.status_bar.config(text=f"⚖️ Sopraccigli identici: {left_area_value:.1f} px²")
                print(f"🔊 Risposta vocale: {response_text}")
                return
            
            # Calcola percentuale di differenza
            percentage_diff = (difference / smaller_value) * 100
            
            # Prepara risposta dettagliata
            if percentage_diff < 5:
                comparison = "leggermente più grande"
            elif percentage_diff < 15:
                comparison = "moderatamente più grande"  
            else:
                comparison = "significativamente più grande"
            
            # Nome del sopracciglio opposto
            opposite_eyebrow = "destro" if bigger_eyebrow == "sinistro" else "sinistro"
            
            response_text = f"Il sopracciglio {bigger_eyebrow} è {comparison} con {bigger_value:.1f} pixel quadrati, rispetto ai {smaller_value:.1f} del {opposite_eyebrow}. Differenza: {difference:.1f} pixel quadrati, pari al {percentage_diff:.1f} percento."
            
            # Aggiorna status bar
            status_text = f"🏆 Sopracciglio {bigger_eyebrow} più grande: {bigger_value:.1f} px² (+{percentage_diff:.1f}%)"
            self.status_bar.config(text=status_text)
            
            print(f"🔊 Risposta vocale completa: {response_text}")
            
            # Pronuncia la risposta tramite assistente vocale  
            try:
                # Risposta completa che include l'analisi
                full_response = f"Analisi completata. Il sopracciglio {bigger_eyebrow} è più grande con {bigger_value:.1f} pixel quadrati, contro i {smaller_value:.1f} del {opposite_eyebrow}. Differenza del {percentage_diff:.1f} percento."
                
                # Usa l'assistente vocale se disponibile
                if hasattr(self, 'voice_commands') and self.voice_commands:
                    # Pronuncia usando l'integrazione vocale esistente
                    self.voice_commands.speak_feedback(full_response)
                    print(f"🔊 Pronunciato: {full_response}")
                else:
                    print(f"📢 Risposta (TTS non disponibile): {full_response}")
                        
            except Exception as e:
                print(f"⚠️ Errore TTS: {e}")
                print(f"📢 Risposta (solo testo): {full_response}")
            
        else:
            error_msg = "❌ Non riesco a trovare le misurazioni delle aree sopraccigli nella tabella"
            self.status_bar.config(text=error_msg)
            print(f"⚠️ Valori non trovati - Sinistro: {left_area_value}, Destro: {right_area_value}")
            
            # Debug: mostra contenuto tabella
            print("🔍 Debug - Contenuto tabella misurazioni:")
            for i, item in enumerate(self.measurements_tree.get_children()):
                values = self.measurements_tree.item(item, 'values')
                print(f"  Riga {i+1}: {values}")

    def calculate_axis(self):
        """Calcola e mostra l'asse di simmetria facciale."""
        if self.current_image is None:
            messagebox.showwarning("Attenzione", "Nessuna immagine caricata")
            return
            
        # Prima rileva i landmarks se non esistono
        if not self.current_landmarks:
            self.detect_landmarks()
            
        if self.current_landmarks:
            # Attiva la visualizzazione dell'asse
            self.show_axis_var.set(True)
            self.update_canvas_display()
            self.status_bar.config(text="Asse di simmetria calcolato")
        else:
            messagebox.showwarning("Attenzione", "Impossibile rilevare landmarks per calcolare l'asse")

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
                print("🟢 DEBUG: Green dots rilevati con successo")
                
                # NUOVO SISTEMA: Estrai i poligoni e disegnali sul canvas
                self.draw_green_dots_on_canvas(results)
                
                # Salva l'overlay generato (per compatibilità)
                self.green_dots_overlay = results["overlay"]

                # Abilita automaticamente la visualizzazione dell'overlay
                self.show_green_dots_overlay = True
                self.green_dots_var.set(True)
                print("🟢 DEBUG: Green dots overlay abilitato")

                # Aggiorna la visualizzazione del canvas unificato
                self.update_canvas_display()
                print("🟢 DEBUG: Canvas aggiornato dopo green dots")

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

                # 📏 NUOVO: Calcola distanze dall'asse di simmetria per ogni punto verde
                self.calculate_green_dots_axis_distances(results)
                
                # Aggiornamento dati punti verdi completato

                # Mostra messaggio di successo
                message = f"""Rilevamento completato con successo!
                
Puntini rilevati: {results['detection_results']['total_dots']}
• Sopracciglio sinistro: {len(results['groups']['Sx'])} punti
• Sopracciglio destro: {len(results['groups']['Dx'])} punti

Aree calcolate:
• Sinistra: {left_stats['area']:.1f} px²
• Destra: {right_stats['area']:.1f} px²
• Differenza: {abs(left_stats['area'] - right_stats['area']):.1f} px²"""

                # Imposta flag di successo per il rilevamento
                self.green_dots_detected = True
                
                # Aggiorna lo stato dei pulsanti di correzione sopracciglio
                self.update_eyebrow_correction_buttons_state()
                
                # Popup di successo rimosso come richiesto dall'utente
                # messagebox.showinfo("Rilevamento Puntini Verdi", message)
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
                self.green_dots_detected = False
                
                # Aggiorna lo stato dei pulsanti
                self.update_eyebrow_correction_buttons_state()

        except Exception as e:
            error_msg = f"Errore durante il rilevamento dei puntini verdi: {str(e)}"
            messagebox.showerror("Errore", error_msg)
            self.status_bar.config(text="Errore nel rilevamento puntini verdi")

            # Reset dei dati in caso di errore
            self.green_dots_results = None
            self.green_dots_overlay = None
            self.show_green_dots_overlay = False
            self.green_dots_var.set(False)
            self.green_dots_detected = False
            
            # Aggiorna lo stato dei pulsanti
            self.update_eyebrow_correction_buttons_state()

    def toggle_green_dots_overlay(self):
        """Attiva/disattiva la visualizzazione dell'overlay dei puntini verdi."""
        self.show_green_dots_overlay = self.green_dots_var.get()

        if not self.show_green_dots_overlay:
            # RIMUOVI i poligoni green dots dal canvas quando disattivati
            self.clear_green_dots_from_canvas()

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
    
    def clear_green_dots_from_canvas(self):
        """Rimuove tutti i poligoni green dots e le etichette dal canvas."""
        try:
            # Trova tutti gli elementi con tag green_dots_overlay
            green_items = self.canvas.find_withtag("green_dots_overlay")
            
            # 🏷️ NUOVO: Trova anche le etichette dei green dots
            label_items = self.canvas.find_withtag("green_dots_labels")
            
            # Rimuovi poligoni green dots
            for item in green_items:
                # Rimuovi dal graphics_registry
                if item in self.graphics_registry:
                    del self.graphics_registry[item]
                # Rimuovi dal canvas
                self.canvas.delete(item)
            
            # 🏷️ NUOVO: Rimuovi etichette green dots
            for item in label_items:
                # Rimuovi dal graphics_registry
                if item in self.graphics_registry:
                    del self.graphics_registry[item]
                # Rimuovi dal canvas
                self.canvas.delete(item)
            
            total_removed = len(green_items) + len(label_items)
            if total_removed > 0:
                print(f"🧹 Rimossi {len(green_items)} poligoni e {len(label_items)} etichette green dots dal canvas")
        except Exception as e:
            print(f"⚠️ Errore rimozione green dots: {e}")

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

    def draw_preset_overlays(self, image):
        """Disegna gli overlay delle misurazioni predefinite sull'immagine."""
        overlay_image = image.copy()

        for preset_name, overlay in self.preset_overlays.items():
            if overlay is not None and "points" in overlay and overlay["points"]:
                overlay_type = overlay.get("type", "distance")  # Default a distance
                
                if overlay_type == "distance":
                    self.draw_distance_overlay(overlay_image, overlay)
                elif overlay_type == "angle":
                    self.draw_angle_overlay(overlay_image, overlay)
                elif overlay_type == "area":
                    self.draw_area_overlay(overlay_image, overlay)

        return overlay_image

    def draw_distance_overlay(self, image, overlay):
        """Disegna overlay per misurazione di distanza."""
        point1 = overlay["points"][0]
        point2 = overlay["points"][1]

        # Linea principale
        cv2.line(image, point1, point2, (0, 255, 0), 3)

        # Cerchi sui punti
        point1_int = (int(round(point1[0])), int(round(point1[1])))
        point2_int = (int(round(point2[0])), int(round(point2[1])))
        cv2.circle(image, point1_int, 6, (0, 255, 0), -1)
        cv2.circle(image, point2_int, 6, (0, 255, 0), -1)

    def draw_angle_overlay(self, image, overlay):
        """Disegna overlay per misurazione di angolo."""
        points = overlay["points"]

        if len(points) >= 3:
            p1, p2, p3 = points[0], points[1], points[2]

            # Linee che formano l'angolo
            cv2.line(image, p1, p2, (255, 165, 0), 3)
            cv2.line(image, p2, p3, (255, 165, 0), 3)

            # Cerchi sui punti
            p1_int = (int(round(p1[0])), int(round(p1[1])))
            p2_int = (int(round(p2[0])), int(round(p2[1])))
            p3_int = (int(round(p3[0])), int(round(p3[1])))
            cv2.circle(image, p1_int, 6, (255, 165, 0), -1)
            cv2.circle(image, p2_int, 6, (255, 0, 0), -1)  # Vertice in rosso
            cv2.circle(image, p3_int, 6, (255, 165, 0), -1)

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
                        point_int = (int(round(point[0])), int(round(point[1])))
                        cv2.circle(image, point_int, 4, color, -1)

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
                    point_int = (int(round(point[0])), int(round(point[1])))
                    cv2.circle(image, point_int, 6, (0, 200, 200), -1)

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

        # NUOVO SISTEMA: Disegna l'overlay sul canvas e registralo nel graphics_registry
        self.draw_overlay_on_canvas(overlay)
        
        # Aggiorna la visualizzazione se gli overlay sono attivi
        if self.show_measurement_overlays:
            self.update_canvas_display()

    def clear_measurement_overlays(self):
        """Pulisce tutti gli overlay delle misurazioni."""
        
        # NUOVO SISTEMA: Rimuovi tutti gli overlay dal canvas
        overlays_to_clean = list(self.measurement_overlays) + [v for v in self.preset_overlays.values() if v is not None]
        
        for overlay in overlays_to_clean:
            if "canvas_item" in overlay:
                canvas_item = overlay["canvas_item"]
                try:
                    self.canvas.delete(canvas_item)
                    # Rimuovi dal graphics_registry
                    if canvas_item in self.graphics_registry:
                        del self.graphics_registry[canvas_item]
                    print(f"🧹 Rimosso overlay canvas: {canvas_item}")
                except Exception as e:
                    print(f"⚠️ Errore rimozione overlay canvas: {e}")
        
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
        self, x: int, y: int, max_distance: int = 30
    ) -> Optional[int]:
        """
        Trova il landmark più vicino alle coordinate specificate.
        Ottimizzato per selezione precisa con tolleranza dinamica basata sul zoom.

        Args:
            x, y: Coordinate del click nell'immagine originale
            max_distance: Distanza massima base per considerare un landmark (aumentata a 30px per migliore usabilità)

        Returns:
            Indice del landmark più vicino o None se nessuno trovato
        """
        # Usa sempre landmarks MediaPipe 
        if not self.current_landmarks:
            return None

        # 🎯 SOLUZIONE PROBLEMA 1: Tolleranza dinamica MIGLIORATA per selezione precisa senza zoom
        # Usa il metodo dedicato per calcolo tolleranza adattiva
        adjusted_max_distance = self.calculate_adaptive_tolerance(max_distance)

        min_distance = float("inf")
        closest_idx = None

        for i, landmark in enumerate(self.current_landmarks):
            distance = ((landmark[0] - x) ** 2 + (landmark[1] - y) ** 2) ** 0.5
            if distance < min_distance and distance <= adjusted_max_distance:
                min_distance = distance
                closest_idx = i

        # DEBUG per troubleshooting precisione con più dettagli
        zoom_factor = getattr(self, 'canvas_scale', 1.0)
        if closest_idx is not None:
            print(f"🎯 Landmark {closest_idx} selezionato (distanza: {min_distance:.1f}px, "
                  f"tolleranza: {adjusted_max_distance:.1f}px, zoom: {zoom_factor:.2f}) "
                  f"- Facilità selezione: {'FACILE' if min_distance < adjusted_max_distance/2 else 'LIMITE'}")
        else:
            # Trova il landmark più vicino comunque per dare feedback
            nearest_distance = float("inf")
            for i, landmark in enumerate(self.current_landmarks):
                distance = ((landmark[0] - x) ** 2 + (landmark[1] - y) ** 2) ** 0.5
                if distance < nearest_distance:
                    nearest_distance = distance
            print(f"❌ Nessun landmark selezionabile (landmark più vicino a {nearest_distance:.1f}px, "
                  f"tolleranza necessaria: {adjusted_max_distance:.1f}px, zoom: {zoom_factor:.2f})")

        return closest_idx

    def calculate_adaptive_tolerance(self, base_tolerance: int = 30) -> float:
        """
        Calcola la tolleranza adattiva per la selezione landmark basata sul zoom.
        
        Args:
            base_tolerance: Tolleranza base in pixel (default 30)
            
        Returns:
            Tolleranza adattiva in pixel
        """
        zoom_factor = getattr(self, 'canvas_scale', 1.0)
        
        if zoom_factor < 0.2:  # Immagine estremamente piccola
            return base_tolerance * 8.0  # Tolleranza massima
        elif zoom_factor < 0.4:  # Immagine molto piccola  
            return base_tolerance * 6.0  # Tolleranza molto alta
        elif zoom_factor < 0.6:  # Immagine piccola
            return base_tolerance * 5.0  # Tolleranza alta
        elif zoom_factor < 0.8:  # Immagine ridotta
            return base_tolerance * 4.0  # Tolleranza elevata
        elif zoom_factor < 1.0:  # Quasi normale
            return base_tolerance * 2.5  # Tolleranza media-alta
        elif zoom_factor < 1.5:  # Zoom normale
            return base_tolerance * 1.2  # Tolleranza leggermente aumentata
        elif zoom_factor > 3.0:  # Immagine molto ingrandita
            return base_tolerance * 0.6  # Tolleranza ridotta per precisione
        else:  # Zoom medio-alto
            return base_tolerance * 0.8  # Tolleranza standard

    def find_closest_landmark_with_hysteresis(self, x: int, y: int) -> Optional[int]:
        """
        Trova il landmark più vicino con isteresi per evitare salti indesiderati.
        Sistema ottimizzato per selezione precisa: attivazione quando mouse passa
        sopra il centro del landmark e in una piccola area circostante.
        
        Args:
            x, y: Coordinate del mouse nell'immagine originale
            
        Returns:
            Indice del landmark più vicino o None se nessuno trovato
        """
        if not self.current_landmarks:
            return None
        
        # Debug: sistema unificato MediaPipe
        print(f"🎯 HOVER SYSTEM: Usando MediaPipe con {len(self.current_landmarks)} landmarks")
        
        # Raggio ottimizzato per selezione precisa con tolleranza dinamica (pi\u00f9 aggressiva)
        # MIGLIORAMENTO: Adatta il raggio in base al zoom come nella find_closest_landmark
        zoom_factor = getattr(self, 'canvas_scale', 1.0)
        
        if zoom_factor < 0.3:  # Immagine estremamente piccola
            base_radius = 40  # Raggio enorme per massima facilità
        elif zoom_factor < 0.5:  # Immagine molto piccola
            base_radius = 32  # Raggio molto grande per facilità
        elif zoom_factor < 0.8:  # Immagine piccola
            base_radius = 24  # Raggio grande
        elif zoom_factor < 1.2:  # Zoom normale
            base_radius = 18  # Raggio aumentato
        elif zoom_factor > 3.0:  # Immagine molto ingrandita
            base_radius = 6   # Raggio molto ridotto per massima precisione
        else:  # Zoom medio-alto
            base_radius = 10  # Raggio ridotto per buona precisione
        
        # Se c'è già un landmark attivo, usa isteresi più reattiva
        if hasattr(self, 'hovered_landmark') and self.hovered_landmark is not None:
            # Verifica che l'indice sia valido per i landmarks MediaPipe
            if self.hovered_landmark < len(self.current_landmarks):
                current_landmark = self.current_landmarks[self.hovered_landmark] 
                current_distance = ((current_landmark[0] - x) ** 2 + (current_landmark[1] - y) ** 2) ** 0.5
                
                # Zona di priorità leggermente estesa (solo 20% più grande per maggiore precisione)
                priority_radius = base_radius * 1.2
                
                # Se siamo ancora nella zona di priorità del landmark attuale, mantienilo
                if current_distance <= priority_radius:
                    return self.hovered_landmark
                
                # Tolleranza ridotta per transizioni più rapide (ridotta da 5 a 2 pixel)
                if current_distance <= base_radius + 2:  # Zona grigia di 2 pixel
                    return self.hovered_landmark
        
        # Trova il landmark più vicino con criterio di prossimità stretto
        min_distance = float("inf")
        closest_idx = None
        
        # DEBUG: Verifica coordinate
        print(f"# 🔍 COORDINATE DEBUG: mouse_img=({x:.1f},{y:.1f}), offset=({self.canvas_offset_x:.1f},{self.canvas_offset_y:.1f}), scale={self.canvas_scale:.2f}")
        if len(self.current_landmarks) >= 1:
            lm0 = self.current_landmarks[0]
            print(f"# 🔍 LANDMARK[0] ORIGINALE: ({lm0[0]:.1f}, {lm0[1]:.1f})")
        
        for i, landmark in enumerate(self.current_landmarks):
            distance = ((landmark[0] - x) ** 2 + (landmark[1] - y) ** 2) ** 0.5
            # Solo landmark molto vicini vengono considerati (raggio ridotto)
            if distance < min_distance and distance <= base_radius:
                min_distance = distance
                closest_idx = i
                print(f"🎯 MATCH TROVATO: landmark[{i}]=({landmark[0]:.1f},{landmark[1]:.1f}), distance={distance:.1f}px")
        
        return closest_idx

    def add_landmark_selection(self, landmark_idx: int):
        """Aggiunge un landmark alla selezione per misurazioni."""
        # Ottieni coordinate landmark
        landmark_pos = self.current_landmarks[landmark_idx]
        landmark_point = (landmark_pos[0], landmark_pos[1])
        
        # Gestisci limiti punti per misurazioni
        max_points = {"distance": 2, "angle": 3, "area": 4}
        max_count = max_points.get(self.measurement_mode, 2)

        # 🎯 SOLUZIONE PROBLEMA 2: Pulisci overlay precedenti se necessario
        if len(self.selected_points) >= max_count:
            # Rimuovi il primo punto se abbiamo raggiunto il limite
            removed_point = self.selected_points.pop(0)
            print(f"🗑️ Punto rimosso: {removed_point}")
            # Pulisci anche gli overlay precedenti
            self.clear_selection_overlays()
            
        # Aggiungi coordinate landmark ai punti selezionati per misurazione
        self.selected_points.append(landmark_point)
        
        # Aggiorna anche la lista landmark per compatibilità
        if landmark_idx in self.selected_landmarks:
            self.selected_landmarks.remove(landmark_idx)
        self.selected_landmarks.append(landmark_idx)
        
        # 🎯 NUOVO: Crea immediatamente overlay per i punti selezionati
        self.create_selection_overlays()
        
        print(f"✅ Landmark {landmark_idx} aggiunto ai punti di misurazione: {landmark_point}")
        self.status_bar.config(text=f"✅ Landmark {landmark_idx} selezionato - Punti: {len(self.selected_points)}/{max_count}")
        
        # Verifica se possiamo calcolare misurazione
        if len(self.selected_points) >= 2:
            self.calculate_measurement()
            
        # Pulisci evidenziazione hover dopo selezione
        self.canvas.delete("landmark_hover")
        self.hovered_landmark = None

    def create_selection_overlays(self):
        """🎯 SOLUZIONE PROBLEMA 2: Crea overlay per punti selezionati che ruotano con l'immagine."""
        if not hasattr(self, 'selection_overlay_ids'):
            self.selection_overlay_ids = []
        
        # Pulisci overlay precedenti
        self.clear_selection_overlays()
        
        if not self.selected_points:
            return
        
        # Disegna i punti selezionati come cerchi
        for i, point in enumerate(self.selected_points):
            # Converti coordinate immagine in coordinate canvas
            canvas_x, canvas_y = self.image_to_canvas_coords(point[0], point[1])
            
            # 🎯 FIX OVALIZZAZIONE: Usa coordinate canvas per disegno ma coordinate immagine per registro
            radius = 6  # Raggio del cerchio
            point_id = self.canvas.create_oval(
                canvas_x - radius, canvas_y - radius,
                canvas_x + radius, canvas_y + radius,
                fill="magenta", outline="white", width=2,
                tags="selection_overlay"
            )
            
            # 🎯 CRUCIALE: Registra coordinate immagine SINGOLO PUNTO per evitare ovalizzazione
            # Invece di bounding box [x1,y1,x2,y2], usa punto centrale [x,y] + raggio per gestione speciale
            self.register_graphic(
                point_id, "circle_point", 
                [point[0], point[1], radius],  # [center_x, center_y, radius]
                {"fill": "magenta", "outline": "white", "width": 2}, 
                is_overlay=True
            )
            
            self.selection_overlay_ids.append(point_id)
            print(f"🎯 Punto {i+1} registrato come overlay rotante: {point_id}")
        
        # 🎯 NUOVO: Se abbiamo 2+ punti, disegna linea di collegamento
        if len(self.selected_points) >= 2:
            self.create_connection_line()
    
    def create_connection_line(self):
        """Crea linea di collegamento tra punti selezionati."""
        if len(self.selected_points) < 2:
            return
        
        # Crea linea tra primo e secondo punto
        point1 = self.selected_points[0]
        point2 = self.selected_points[1]
        
        # Converti a coordinate canvas
        canvas_x1, canvas_y1 = self.image_to_canvas_coords(point1[0], point1[1])
        canvas_x2, canvas_y2 = self.image_to_canvas_coords(point2[0], point2[1])
        
        # Crea linea
        line_id = self.canvas.create_line(
            canvas_x1, canvas_y1, canvas_x2, canvas_y2,
            fill="cyan", width=3, dash=(5, 3),
            tags="selection_overlay"
        )
        
        # 🎯 CRUCIALE: Registra nel graphics_registry per rotazione automatica
        self.register_graphic(
            line_id, "line",
            [point1[0], point1[1], point2[0], point2[1]],
            {"fill": "cyan", "width": 3}, 
            is_overlay=True
        )
        
        self.selection_overlay_ids.append(line_id)
        print(f"🔗 Linea collegamento registrata come overlay rotante: {line_id}")
        
        # Porta in primo piano
        self.canvas.tag_raise("selection_overlay")
    
    def clear_selection_overlays(self):
        """Pulisce gli overlay dei punti selezionati."""
        if not hasattr(self, 'selection_overlay_ids'):
            return
        
        for overlay_id in self.selection_overlay_ids:
            try:
                self.canvas.delete(overlay_id)
                # Rimuovi dal graphics_registry
                if overlay_id in self.graphics_registry:
                    del self.graphics_registry[overlay_id]
                print(f"🧹 Rimosso overlay selezione: {overlay_id}")
            except Exception as e:
                print(f"⚠️ Errore rimozione overlay selezione: {e}")
        
        self.selection_overlay_ids.clear()

    def change_selection_mode(self):
        """Cambia la modalità di selezione tra manuale e landmark."""
        mode = self.selection_mode_var.get()
        self.landmark_measurement_mode = mode == "landmark"

        # Pulisci le selezioni quando cambi modalità
        self.clear_selections()

        # Se modalità misurazione è attiva e si seleziona "landmark", attiva automaticamente i landmarks
        if (hasattr(self, 'measurement_mode_active') and 
            self.measurement_mode_active and self.measurement_mode_active.get() and 
            self.landmark_measurement_mode):
            
            if not self.all_landmarks_var.get():
                self.all_landmarks_var.set(True)
                self.update_button_style(self.landmarks_button, True)
                if self.current_landmarks is None:
                    self.detect_landmarks()
                else:
                    self.toggle_all_landmarks()

        # Aggiorna il messaggio di stato
        if (hasattr(self, 'measurement_mode_active') and 
            self.measurement_mode_active and self.measurement_mode_active.get()):
            # Se modalità misurazione è attiva, aggiorna con info dettagliate
            mode_text = "LANDMARK (snap magnetico)" if self.landmark_measurement_mode else "MANUALE (click libero)"
            self.status_bar.config(text=f"✅ Modalità Misurazione ATTIVA - {mode_text}")
        else:
            # Modalità normale (non misurazione)
            if self.landmark_measurement_mode:
                self.status_bar.config(
                    text="Modalità Landmark selezionata - attiva misurazione per usarla"
                )
            else:
                self.status_bar.config(
                    text="Modalità Manuale selezionata - attiva misurazione per usarla"
                )

    def change_measurement_mode(self):
        """Cambia la modalità di misurazione."""
        self.measurement_mode = self.measure_var.get()
        self.clear_selections()
        self.status_bar.config(text=f"Modalità: {self.measurement_mode}")

    def clear_selections(self):
        """Pulisce le selezioni correnti e gli overlay misurazioni."""
        self.selected_points.clear()
        self.selected_landmarks.clear()
        
        # NUOVO: Rimuovi overlay di selezione dal graphics_registry
        self.clear_selection_overlays()
        
        # Rimuovi evidenziazione hover se presente
        self.canvas.delete("landmark_hover")
        if hasattr(self, 'hovered_landmark'):
            self.hovered_landmark = None
        
        # NUOVO: Pulisci anche tutti gli overlay misurazioni
        self.clear_measurement_overlays()
        
        self.update_canvas_display()
        self.status_bar.config(text="Selezioni e misurazioni cancellate")
        print("🗑️ Tutte le selezioni e overlay misurazioni puliti")

    def calculate_measurement(self):
        """Calcola la misurazione in base ai punti selezionati."""
        print(f"🧮 CALCOLO MISURAZIONE - Modalità: {'Landmark' if self.landmark_measurement_mode else 'Manuale'}")
        
        # Verifica che la modalità misurazione sia attiva
        if not (hasattr(self, 'measurement_mode_active') and 
                self.measurement_mode_active and self.measurement_mode_active.get()):
            messagebox.showwarning("Attenzione", "Attiva prima la modalità misurazione")
            return
        
        # Ottieni i punti dalla modalità corrente
        if self.landmark_measurement_mode:
            if not self.selected_landmarks:
                messagebox.showwarning("Attenzione", "Seleziona almeno un landmark (modalità Landmark attiva)")
                return
            # Converti indici landmark in coordinate
            points = []
            for landmark_idx in self.selected_landmarks:
                if landmark_idx < len(self.current_landmarks):
                    point = self.current_landmarks[landmark_idx]
                    points.append((int(point[0]), int(point[1])))
                    print(f"📍 Landmark {landmark_idx}: ({point[0]:.1f}, {point[1]:.1f})")
            print(f"🎯 {len(points)} landmarks convertiti in coordinate")
        else:
            if not self.selected_points:
                messagebox.showwarning("Attenzione", "Seleziona almeno un punto (modalità Manuale attiva)")
                return
            points = self.selected_points
            print(f"🎯 {len(points)} punti manuali selezionati")

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

                    # Aggiungi overlay per misurazioni manuali - CORREZIONE COORDINATE
                    if not self.landmark_measurement_mode:
                        # Le coordinate in selected_points sono già coordinate immagine corrette
                        # Assicurati che siano nel formato intero per cv2
                        corrected_coordinates = []
                        for point in points[:2]:
                            corrected_coordinates.append((int(round(point[0])), int(round(point[1]))))
                        
                        print(f"🎯 Coordinate overlay corrette: {corrected_coordinates}")
                        
                        point_indices = list(range(len(points)))[:2]
                        self.add_measurement_overlay(
                            measurement_type="distance",
                            points=point_indices,
                            value=f"{result:.2f}",
                            label=f"Distanza {mode_text}",
                            use_coordinates=True,
                            coordinates=corrected_coordinates,
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

                    # Aggiungi overlay per misurazioni angolo - CORREZIONE COORDINATE CON ROTAZIONE
                    if not self.landmark_measurement_mode:
                        # Per modalità manuale: applica stessa logica conversione punti singoli
                        corrected_coordinates = []
                        for point in points[:3]:
                            # CORREZIONE: Converti coordinate se immagine è ruotata (come per punti singoli)
                            if self.current_rotation != 0:
                                center = self.get_rotation_center_from_landmarks()
                                if center:
                                    # Converti al sistema originale per consistenza con altri overlay
                                    orig_x, orig_y = self.rotate_point_around_center_simple(
                                        point[0], point[1], center[0], center[1], -self.current_rotation
                                    )
                                    corrected_coordinates.append((int(round(orig_x)), int(round(orig_y))))
                                    print(f"🔄 Angolo punto {point} -> sistema originale ({orig_x:.1f},{orig_y:.1f})")
                                else:
                                    print("❌ Impossibile determinare centro rotazione per angolo")
                                    corrected_coordinates.append((int(round(point[0])), int(round(point[1]))))
                            else:
                                corrected_coordinates.append((int(round(point[0])), int(round(point[1]))))
                        
                        print(f"🎯 Coordinate overlay angolo corrette: {corrected_coordinates}")
                        
                        point_indices = list(range(len(points)))[:3]
                        self.add_measurement_overlay(
                            measurement_type="angle",
                            points=point_indices,
                            value=f"{result:.2f}",
                            label=f"Angolo {mode_text}",
                            use_coordinates=True,
                            coordinates=corrected_coordinates,
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

                    # Aggiungi overlay per misurazioni di area - CORREZIONE COORDINATE CON ROTAZIONE
                    if not self.landmark_measurement_mode:
                        # Per modalità manuale: applica stessa logica conversione punti singoli
                        corrected_coordinates = []
                        for point in points:
                            # CORREZIONE: Converti coordinate se immagine è ruotata (come per punti singoli)
                            if self.current_rotation != 0:
                                center = self.get_rotation_center_from_landmarks()
                                if center:
                                    # Converti al sistema originale per consistenza con altri overlay
                                    orig_x, orig_y = self.rotate_point_around_center_simple(
                                        point[0], point[1], center[0], center[1], -self.current_rotation
                                    )
                                    corrected_coordinates.append((int(round(orig_x)), int(round(orig_y))))
                                    print(f"🔄 Area punto {point} -> sistema originale ({orig_x:.1f},{orig_y:.1f})")
                                else:
                                    print("❌ Impossibile determinare centro rotazione per area")
                                    corrected_coordinates.append((int(round(point[0])), int(round(point[1]))))
                            else:
                                corrected_coordinates.append((int(round(point[0])), int(round(point[1]))))
                        print(f"🎯 Coordinate overlay area corrette: {corrected_coordinates}")
                    else:
                        # Per modalità landmark: usa coordinate originali (già corrette)
                        corrected_coordinates = points
                    
                    point_indices = list(range(len(points)))
                    self.add_measurement_overlay(
                        measurement_type="area",
                        points=point_indices,
                        value=f"{result:.2f}",
                        label=f"Area {mode_text}",
                        use_coordinates=True,
                        coordinates=corrected_coordinates,
                    )
                else:
                    messagebox.showwarning(
                        "Attenzione", "Seleziona almeno 3 punti per l'area"
                    )

        except Exception as e:
            print(f"❌ Errore nel calcolo misurazione: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Errore Calcolo", f"Errore nel calcolo della misurazione:\n\n{str(e)}\n\nControlla la console per dettagli.")

    def calculate_predefined_measurement(self):
        """Calcola la misurazione predefinita senza controllo modalità attiva."""
        print(f"🧮 CALCOLO MISURAZIONE PREDEFINITA - Landmark Mode: {self.landmark_measurement_mode}")
        
        # Ottieni i punti dalla modalità corrente (solo landmark per predefinite)
        if not self.selected_landmarks:
            messagebox.showwarning("Attenzione", "Seleziona almeno un landmark per la misurazione predefinita")
            return
            
        # Converti indici landmark in coordinate
        points = []
        for landmark_idx in self.selected_landmarks:
            if landmark_idx < len(self.current_landmarks):
                point = self.current_landmarks[landmark_idx]
                points.append((int(point[0]), int(point[1])))
                print(f"📍 Landmark {landmark_idx}: ({point[0]:.1f}, {point[1]:.1f})")
        print(f"🎯 {len(points)} landmarks convertiti in coordinate")

        try:
            if self.measurement_mode == "distance":
                if len(points) >= 2:
                    result = self.measurement_tools.calculate_distance(
                        points[0], points[1]
                    )
                    self.add_measurement(
                        f"Distanza (Predefinita)", f"{result:.2f}", "px"
                    )

                    # Memorizza il risultato per eventuali overlay
                    self.measurement_result = f"{result:.2f}"
                else:
                    messagebox.showwarning(
                        "Attenzione", "Seleziona 2 punti per la distanza"
                    )

            elif self.measurement_mode == "angle":
                if len(points) >= 3:
                    result = self.measurement_tools.calculate_angle(
                        points[0], points[1], points[2]
                    )
                    self.add_measurement(f"Angolo (Predefinito)", f"{result:.2f}", "°")

                    # Memorizza il risultato per eventuali overlay
                    self.measurement_result = f"{result:.2f}"
                else:
                    messagebox.showwarning(
                        "Attenzione", "Seleziona 3 punti per l'angolo"
                    )

            elif self.measurement_mode == "area":
                if len(points) >= 3:
                    result = self.measurement_tools.calculate_polygon_area(points)
                    self.add_measurement(f"Area (Predefinita)", f"{result:.2f}", "px²")

                    # Memorizza il risultato per eventuali overlay
                    self.measurement_result = f"{result:.2f}"
                else:
                    messagebox.showwarning(
                        "Attenzione", "Seleziona almeno 3 punti per l'area"
                    )

        except Exception as e:
            print(f"❌ Errore nel calcolo misurazione predefinita: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Errore Calcolo", f"Errore nel calcolo della misurazione predefinita:\n\n{str(e)}\n\nControlla la console per dettagli.")

    # Metodi toggle per misurazioni predefinite
    def toggle_face_width(self):
        """Toggle per overlay larghezza volto."""
        print("🔴 PULSANTE PREMUTO: toggle_face_width")
        if self.preset_overlays["face_width"] is None:
            # Mostra: esegui misurazione e crea overlay
            print("🔴 CHIAMANDO: measure_face_width")
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
            
            # NUOVO SISTEMA: Rimuovi l'overlay dal canvas se presente
            if "canvas_item" in overlay_to_remove:
                canvas_item = overlay_to_remove["canvas_item"]
                try:
                    self.canvas.delete(canvas_item)
                    # Rimuovi dal graphics_registry
                    if canvas_item in self.graphics_registry:
                        del self.graphics_registry[canvas_item]
                    print(f"🗑️ Rimosso overlay canvas: {canvas_item}")
                except Exception as e:
                    print(f"⚠️ Errore rimozione overlay canvas: {e}")
            
            if overlay_to_remove in self.measurement_overlays:
                self.measurement_overlays.remove(overlay_to_remove)
            self.preset_overlays[preset_key] = None
            self.update_canvas_display()

    # Metodi per misurazioni predefinite
    def measure_face_width(self):
        """Misura automatica della larghezza del volto."""
        print("🔴 ESEGUO: measure_face_width")
        if not self.current_landmarks:
            print("🔴 ERRORE: Nessun landmark disponibile")
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
            )
            return

        # Usa landmark predefiniti per la larghezza del volto
        left_face = 234  # Lato sinistro del volto
        right_face = 454  # Lato destro del volto

        if len(self.current_landmarks) > max(left_face, right_face):
            self.selected_landmarks = [left_face, right_face]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_predefined_measurement()

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
                self.preset_overlays["face_width"] = overlay
                self.draw_overlay_on_canvas(overlay)
                # Aggiorna sempre il display per mostrare i preset
                self.update_canvas_display()

            self.status_bar.config(text="Larghezza volto misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_face_height(self):
        """Misura automatica dell'altezza del volto."""
        if not self.current_landmarks:
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
            )
            return

        # Usa landmark predefiniti per l'altezza del volto
        top_face = 10  # Parte superiore della fronte
        bottom_face = 175  # Parte inferiore del mento

        if len(self.current_landmarks) > max(top_face, bottom_face):
            self.selected_landmarks = [top_face, bottom_face]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_predefined_measurement()

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
                self.preset_overlays["face_height"] = overlay
                self.draw_overlay_on_canvas(overlay)
                # Aggiorna sempre il display per mostrare i preset
                self.update_canvas_display()

            self.status_bar.config(text="Altezza volto misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_eye_distance(self):
        """Misura automatica della distanza tra gli occhi."""
        if not self.current_landmarks:
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
            )
            return

        # FIX CORRETTO: Landmark per distanza ANGOLI INTERNI degli occhi (MediaPipe Face Mesh)
        left_eye_inner = 133   # Angolo INTERNO occhio sinistro
        right_eye_inner = 362  # Angolo INTERNO occhio destro - CORREGGERE SE SBAGLIATO DOPO TEST

        if len(self.current_landmarks) > max(left_eye_inner, right_eye_inner):
            self.selected_landmarks = [left_eye_inner, right_eye_inner]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_predefined_measurement()

            # Aggiungi overlay per la misurazione
            if self.measurement_result:
                overlay = {
                    "type": "distance",
                    "points": [
                        (
                            int(self.current_landmarks[left_eye_inner][0]),
                            int(self.current_landmarks[left_eye_inner][1]),
                        ),
                        (
                            int(self.current_landmarks[right_eye_inner][0]),
                            int(self.current_landmarks[right_eye_inner][1]),
                        ),
                    ],
                    "value": self.measurement_result,
                    "label": "Distanza Occhi (Angoli Interni)",
                }
                self.preset_overlays["eye_distance"] = overlay
                self.draw_overlay_on_canvas(overlay)
                # Aggiorna sempre il display per mostrare i preset
                self.update_canvas_display()

            self.status_bar.config(text="Distanza occhi misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_nose_width(self):
        """Misura automatica della larghezza del naso."""
        if not self.current_landmarks:
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
            )
            return

        # Usa landmark predefiniti per la larghezza del naso
        nose_left = 131  # Lato sinistro del naso
        nose_right = 360  # Lato destro del naso

        if len(self.current_landmarks) > max(nose_left, nose_right):
            self.selected_landmarks = [nose_left, nose_right]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_predefined_measurement()

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
                self.preset_overlays["nose_width"] = overlay
                self.draw_overlay_on_canvas(overlay)
                # Aggiorna sempre il display per mostrare i preset
                self.update_canvas_display()

            self.status_bar.config(text="Larghezza naso misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_mouth_width(self):
        """Misura automatica della larghezza della bocca."""
        if not self.current_landmarks:
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
            )
            return

        # Usa landmark predefiniti per la larghezza della bocca
        mouth_left = 61  # Angolo sinistro della bocca
        mouth_right = 291  # Angolo destro della bocca

        if len(self.current_landmarks) > max(mouth_left, mouth_right):
            self.selected_landmarks = [mouth_left, mouth_right]
            self.measurement_mode = "distance"
            self.measure_var.set("distance")
            self.calculate_predefined_measurement()

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
                self.preset_overlays["mouth_width"] = overlay
                self.draw_overlay_on_canvas(overlay)
                # Aggiorna sempre il display per mostrare i preset
                self.update_canvas_display()

            self.status_bar.config(text="Larghezza bocca misurata automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_eyebrow_areas(self):
        """Misura automatica delle aree dei sopraccigli."""
        if not self.current_landmarks:
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
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

            # Crea overlay per visualizzazione usando i landmarks ORIGINALI (non trasformati)
            # CORREZIONE: Usa original_base_landmarks per evitare doppia trasformazione
            landmarks_to_use = self.original_base_landmarks if self.original_base_landmarks else self.current_landmarks
            if len(landmarks_to_use) >= 468:
                print(f"🔄 Creando overlay sopraccigli - usando landmarks {'originali' if self.original_base_landmarks else 'correnti'}")
                
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
                        int(landmarks_to_use[idx][0]),
                        int(landmarks_to_use[idx][1]),
                    )
                    for idx in left_eyebrow_indices
                ]

                # Landmarks per sopracciglio DESTRO
                # Ordinati secondo NUOVA SEQUENZA PERIMETRALE PERSONALIZZATA
                # RIMOSSO landmark 46
                right_eyebrow_indices = [53, 52, 65, 55, 107, 66, 105, 63, 70, 53]
                right_eyebrow_points = [
                    (
                        int(landmarks_to_use[idx][0]),
                        int(landmarks_to_use[idx][1]),
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
                
                # NUOVO SISTEMA: Disegna l'overlay sul canvas
                self.draw_overlay_on_canvas(overlay)
                
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Aree sopraccigli misurate automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_eye_areas(self):
        """Misura automatica delle aree degli occhi."""
        if not self.current_landmarks:
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
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

            # Crea overlay per visualizzazione usando landmarks ORIGINALI (non trasformati)  
            # CORREZIONE: Usa original_base_landmarks per evitare doppia trasformazione
            landmarks_to_use = self.original_base_landmarks if self.original_base_landmarks else self.current_landmarks
            if len(landmarks_to_use) >= 468:
                print(f"🔄 Creando overlay occhi - usando landmarks {'originali' if self.original_base_landmarks else 'correnti'}")
                
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
                        int(landmarks_to_use[idx][0]),
                        int(landmarks_to_use[idx][1]),
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
                        int(landmarks_to_use[idx][0]),
                        int(landmarks_to_use[idx][1]),
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
                self.draw_overlay_on_canvas(overlay)
                if self.show_measurement_overlays:
                    self.update_canvas_display()

            self.status_bar.config(text="Aree occhi misurate automaticamente")
        else:
            messagebox.showerror(
                "Errore", "Landmark non sufficienti per questa misurazione"
            )

    def measure_facial_symmetry(self):
        """Calcola automaticamente l'indice di simmetria facciale."""
        if not self.current_landmarks:
            messagebox.showwarning(
                "Attenzione",
                "Assicurati che i landmark siano rilevati nell'immagine",
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
        try:
            if hasattr(self, 'measurements_tree') and self.measurements_tree:
                self.measurements_tree.insert(
                    "", 0, values=(measurement_type, value, unit)
                )  # 0 = inserisce in cima
                print(f"✅ Misurazione aggiunta: {measurement_type} = {value} {unit}")
            else:
                print(f"⚠️ measurements_tree non disponibile, misurazione: {measurement_type} = {value} {unit}")
                
            # Aggiornamento misurazione completato
                
            self.status_bar.config(
                text=f"✅ {measurement_type}: {value} {unit}"
            )
            
            # Aggiorna lo stato dei pulsanti di correzione sopracciglio
            self.update_eyebrow_correction_buttons_state()
        except Exception as e:
            print(f"❌ Errore aggiunta misurazione: {e}")
            self.status_bar.config(
                text=f"Misurazione calcolata: {measurement_type} = {value} {unit}"
            )



    def get_measurement_value_from_table(self, measurement_type: str) -> Optional[str]:
        """Legge un valore dalla tabella delle misurazioni basato sul tipo di misurazione.
        
        Args:
            measurement_type: Il tipo di misurazione da cercare nella colonna 'Tipo Misurazione'
            
        Returns:
            Tuple (value, unit) se trovato, altrimenti None
        """
        try:
            if not (hasattr(self, 'measurements_tree') and self.measurements_tree):
                return None
                
            # Scorre tutte le righe della tabella
            for item in self.measurements_tree.get_children():
                values = self.measurements_tree.item(item, 'values')
                if len(values) >= 3:  # Tipo, Valore, Unità
                    table_type = values[0]  # Colonna 'Tipo Misurazione'
                    table_value = values[1]  # Colonna 'Valore'
                    table_unit = values[2] if len(values) > 2 else ""  # Colonna 'Unità'
                    
                    # Confronto case-insensitive
                    if table_type.lower() == measurement_type.lower():
                        return (table_value, table_unit)
            
            return None
            
        except Exception as e:
            print(f"❌ Errore lettura valore dalla tabella: {e}")
            return None



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
                        zoom_factor=getattr(self, 'canvas_scale', 1.0),
                        highlight_landmark=getattr(self, 'hovered_landmark', None),
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

    def toggle_asse_section(self):
        """Gestisce il toggle del pulsante ASSE nella sezione RILEVAMENTI."""
        self.show_axis_var.set(not self.show_axis_var.get())
        
        # Aggiorna l'aspetto del pulsante
        self.update_button_style(self.asse_button, self.show_axis_var.get())
        
        if self.show_axis_var.get():
            if self.current_landmarks is None:
                # Se non ci sono landmarks, calcola l'asse automaticamente
                self.calculate_axis()
            else:
                self.update_canvas_display()
        else:
            self.update_canvas_display()

    def toggle_landmarks_section(self):
        """Gestisce il toggle del pulsante LANDMARKS nella sezione RILEVAMENTI."""
        self.all_landmarks_var.set(not self.all_landmarks_var.get())
        
        # Aggiorna l'aspetto del pulsante  
        self.update_button_style(self.landmarks_button, self.all_landmarks_var.get())
        
        if self.all_landmarks_var.get():
            if self.current_landmarks is None:
                # Se non ci sono landmarks, rilevali automaticamente
                self.detect_landmarks()
            else:
                self.toggle_all_landmarks()
        else:
            self.toggle_all_landmarks()

    def toggle_measurement_mode(self):
        """Gestisce l'attivazione/disattivazione della modalità misurazione interattiva."""
        is_active = self.measurement_mode_active.get()
        
        if is_active:
            # Imposta automaticamente modalità landmark come default
            if hasattr(self, 'selection_mode_var'):
                self.selection_mode_var.set("landmark")
                self.landmark_measurement_mode = True
                print("🎯 Modalità misurazione: LANDMARK impostata come default")
            
            # Attiva automaticamente i landmarks
            if not self.all_landmarks_var.get():
                self.all_landmarks_var.set(True)
                self.update_button_style(self.landmarks_button, True)
                if self.current_landmarks is None:
                    self.detect_landmarks()
                else:
                    self.toggle_all_landmarks()
            
            mode_text = "LANDMARK (hover + click sui punti rossi)"
            self.status_bar.config(text=f"✅ Modalità Misurazione ATTIVA - {mode_text}")
            
            # Attiva hover effect sui landmarks
            self.enable_landmark_hover_effect()
                        
            print(f"🎯 Modalità misurazione ATTIVATA: {mode_text}")
        else:
            # Disattiva modalità misurazione
            self.status_bar.config(text="❌ Modalità Misurazione DISATTIVATA")
            # Disattiva hover effect
            self.disable_landmark_hover_effect()
            # Pulisci le selezioni quando disattivi
            self.clear_selections()
            print("🎯 Modalità misurazione DISATTIVATA")

    def toggle_green_dots_section(self):
        """Gestisce il toggle del pulsante GREEN DOTS nella sezione RILEVAMENTI."""
        self.green_dots_var.set(not self.green_dots_var.get())
        
        # Aggiorna l'aspetto del pulsante
        self.update_button_style(self.green_dots_button, self.green_dots_var.get())
        
        if self.green_dots_var.get():
            # Se non ci sono green dots rilevati, rilevali automaticamente
            if not hasattr(self, 'green_dots_detected') or not self.green_dots_detected:
                self.detect_green_dots()
            else:
                self.toggle_green_dots_overlay()
        else:
            self.toggle_green_dots_overlay()

    def update_button_style(self, button, is_active):
        """Aggiorna lo stile del pulsante in base allo stato attivo/inattivo."""
        if is_active:
            # Stile attivo - cambio colore di background
            button.configure(style='Active.TButton')
        else:
            # Stile normale
            button.configure(style='TButton')

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

    # RIMOSSO: on_canvas_measurement_click_old_professional() - funzione obsoleta
    # RIMOSSO: on_measurement_completed() - callback obsoleto
    # RIMOSSO: Altri metodi canvas professional obsoleti

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
    def analyze_current_image(self):
        """Analizza l'immagine corrente con rilevamento volti."""
        if not hasattr(self, 'current_image') or self.current_image is None:
            messagebox.showwarning("Nessuna Immagine", "Carica prima un'immagine da analizzare")
            return
            
        try:
            # Usa il sistema esistente di analisi
            if hasattr(self, 'face_detector'):
                results = self.face_detector.detect_face_landmarks(self.current_image)
                if results:
                    self.current_landmarks = results
                    self.update_canvas_display()
                    print("✅ Analisi facciale completata")
                else:
                    print("⚠️ Nessun volto rilevato nell'immagine")
        except Exception as e:
            print(f"❌ Errore durante l'analisi: {e}")

    def save_current_results(self):
        """Salva i risultati correnti dell'analisi."""
        try:
            if hasattr(self, 'current_image') and self.current_image is not None:
                from tkinter import filedialog
                
                # Chiedi dove salvare
                filename = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
                )
                
                if filename:
                    # Salva l'immagine con le annotazioni correnti
                    if hasattr(self, 'canvas') and self.canvas:
                        # Implementa il salvataggio dell'immagine corrente
                        # Per ora, semplice salvataggio dell'immagine
                        import cv2
                        cv2.imwrite(filename, self.current_image)
                        print(f"✅ Immagine salvata: {filename}")
                        return True
                        
            print("⚠️ Nessuna immagine da salvare")
            return False
            
        except Exception as e:
            print(f"❌ Errore durante il salvataggio: {e}")
            return False

    # *** NUOVI METODI CALLBACK MIGLIORATI PER LAYOUT ***
    
    def _on_vertical_paned_resize_improved(self, event):
        """Callback migliorato per ridimensionamento pannello verticale."""
        try:
            # Non salvare se siamo in fase di ripristino
            if hasattr(self, 'layout_restorer') and self.layout_restorer.is_restoring:
                return
                
            if self.main_vertical_paned.panes():
                position = self.main_vertical_paned.sashpos(0)
                print(f"📏 VERTICAL PANED RESIZE: posizione {position}")
                layout_manager.config.vertical_paned_position = position
                
                # Usa il nuovo sistema di salvataggio con debounce
                if hasattr(self, 'layout_saver'):
                    self.layout_saver.schedule_save()
                else:
                    layout_manager.save_config()
                    
        except Exception as e:
            print(f"❌ Errore aggiornamento vertical paned: {e}")

    def _on_main_paned_resize_improved(self, event):
        """Callback migliorato per ridimensionamento pannello principale."""
        try:
            # Non salvare se siamo in fase di ripristino
            if hasattr(self, 'layout_restorer') and self.layout_restorer.is_restoring:
                return
                
            if self.main_horizontal_paned.panes():
                # SASHPOS(0): Divisore controlli | canvas
                left_position = self.main_horizontal_paned.sashpos(0)
                print(f"📏 MAIN PANED RESIZE (controlli|canvas): posizione {left_position}")
                layout_manager.config.main_paned_position = left_position

                # SASHPOS(1): Divisore canvas | colonna destra (SE ESISTE)
                panes_count = len(self.main_horizontal_paned.panes())
                if panes_count >= 3:
                    right_position = self.main_horizontal_paned.sashpos(1)
                    print(f"📏 RIGHT COLUMN RESIZE (canvas|destra): posizione {right_position}")
                    layout_manager.config.right_column_position = right_position

                # Usa il nuovo sistema di salvataggio con debounce
                if hasattr(self, 'layout_saver'):
                    self.layout_saver.schedule_save()
                else:
                    layout_manager.save_config()
                    
        except Exception as e:
            print(f"❌ Errore aggiornamento main paned: {e}")

    def _on_sidebar_paned_resize_improved(self, event):
        """Callback migliorato per ridimensionamento sidebar destro."""
        try:
            # Non salvare se siamo in fase di ripristino
            if hasattr(self, 'layout_restorer') and self.layout_restorer.is_restoring:
                return
                
            if self.right_sidebar_paned.panes():
                position = self.right_sidebar_paned.sashpos(0)
                print(f"📏 SIDEBAR PANED RESIZE: posizione {position}")
                layout_manager.config.layers_preview_divider_position = position
                
                # Usa il nuovo sistema di salvataggio con debounce
                if hasattr(self, 'layout_saver'):
                    self.layout_saver.schedule_save()
                else:
                    layout_manager.save_config()
                    
        except Exception as e:
            print(f"❌ Errore aggiornamento sidebar paned: {e}")

    # === FUNZIONI PER CORREZIONE SOPRACCIGLIO ===
    
    def has_green_dots_and_measurements(self) -> bool:
        """
        Verifica se sono disponibili i punti verdi rilevati e le misurazioni nella tabella.
        
        Returns:
            bool: True se entrambi sono disponibili
        """
        # Verifica se ci sono punti verdi rilevati
        has_green_dots = (
            hasattr(self, 'green_dots_detected') and 
            self.green_dots_detected and
            hasattr(self, 'green_dots_processor') and
            (len(self.green_dots_processor.left_dots) > 0 or len(self.green_dots_processor.right_dots) > 0)
        )
        
        # Verifica se ci sono misurazioni nella tabella
        has_measurements = (
            hasattr(self, 'measurements_tree') and
            len(self.measurements_tree.get_children()) > 0
        )
        
        return has_green_dots and has_measurements

# FUNZIONI RIMOSSE: crop_eyebrow_image e create_eyebrow_overlay
# Nel nuovo flusso, l'overlay viene creato sull'intera immagine prima del ritaglio

    def show_eyebrow_correction_window(self, side: str):
        """
        Mostra una finestra con l'immagine del sopracciglio ritagliata e gli overlay.
        NUOVO FLUSSO: Prima crea overlay sull'intera immagine, poi ritaglia.
        
        Args:
            side: 'left' per sopracciglio sinistro, 'right' per quello destro
        """
        try:
            # Verifica prerequisiti
            if not self.has_green_dots_and_measurements():
                messagebox.showwarning(
                    "Prerequisiti mancanti",
                    "Per utilizzare la correzione sopracciglio è necessario:\n"
                    "1. Rilevare i punti verdi (GREEN DOTS)\n"
                    "2. Avere almeno una misurazione nella tabella\n"
                    "3. Calcolare l'asse di simmetria (pulsante ASSE)"
                )
                return
            
            print(f"🚀 NUOVO FLUSSO: Correzione sopracciglio {side}")
            
            # STEP 1: Crea overlay sull'intera immagine con punti verdi originali + rossi riflessi
            full_image_with_overlay = self.create_full_canvas_eyebrow_overlay(side)
            if full_image_with_overlay is None:
                messagebox.showerror("Errore", "Impossibile creare overlay completo dell'immagine")
                return
            
            print(f"✅ Overlay completo creato per {side}")
            
            # STEP 2: Ritaglia il sopracciglio dall'immagine con overlay
            bbox = None
            if side == 'left':
                bbox = self.green_dots_processor.get_left_eyebrow_bbox(expand_factor=0.5)
            else:  # side == 'right'
                bbox = self.green_dots_processor.get_right_eyebrow_bbox(expand_factor=0.5)
            
            if bbox == (0, 0, 0, 0):
                messagebox.showerror("Errore", f"Bounding box non valido per sopracciglio {side}")
                return
            
            x_min, y_min, x_max, y_max = bbox
            
            # Verifica che il bounding box sia valido
            if x_max <= x_min or y_max <= y_min:
                messagebox.showerror("Errore", f"Bounding box non valido: {bbox}")
                return
            
            # Assicurati che le coordinate siano nell'immagine
            height, width = full_image_with_overlay.shape[:2]
            x_min = max(0, min(x_min, width-1))
            y_min = max(0, min(y_min, height-1))
            x_max = max(x_min+1, min(x_max, width))
            y_max = max(y_min+1, min(y_max, height))
            
            # Ritaglia l'immagine con overlay
            cropped_image_with_overlay = full_image_with_overlay[y_min:y_max, x_min:x_max]
            
            print(f"✅ Ritaglio completato: {cropped_image_with_overlay.shape}")
            
            # SEMPRE: Mostra temporaneamente l'overlay completo sul canvas principale per verifica
            self.status_bar.config(text="🎨 Mostra overlay completo per 3 secondi, poi finestra ritaglio...")
            
            # Programma la continuazione dopo l'overlay temporaneo
            self._continue_function = self._show_cropped_window_after_overlay
            self._continue_params = {
                'cropped_image': cropped_image_with_overlay,
                'side': side
            }
            
            self.show_temp_overlay_on_canvas(full_image_with_overlay)
            return  # Esce qui, continuerà dopo l'overlay
            
        except Exception as e:
            print(f"❌ Errore nell'apertura finestra correzione: {e}")
            messagebox.showerror(
                "Errore",
                f"Errore nell'apertura finestra correzione:\n{e}"
            )

    def _show_cropped_window_after_overlay(self, cropped_image: np.ndarray, side: str):
        """
        Continua mostrando la finestra di correzione dopo l'overlay temporaneo.
        
        Args:
            cropped_image: Immagine ritagliata con overlay
            side: Lato del sopracciglio ('left' o 'right')
        """
        try:
            image_with_overlay = cropped_image
            
            # Crea una nuova finestra
            side_name = "Sinistro" if side == 'left' else "Destro"
            window_title = f"Correzione Sopracciglio {side_name} - NUOVO FLUSSO"
            
            correction_window = tk.Toplevel(self.root)
            correction_window.title(window_title)
            
            # Frame principale
            main_frame = ttk.Frame(correction_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Titolo
            title_label = ttk.Label(
                main_frame, 
                text=f"🔍 {window_title}",
                font=("Arial", 14, "bold")
            )
            title_label.pack(pady=(0, 10))
            
            # Legenda aggiornata per il nuovo flusso
            legend_frame = ttk.Frame(main_frame)
            legend_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(
                legend_frame,
                text="🟢 Verde: Punti originali del lato selezionato (SA, SA0, SC, SC1, SB)",
                foreground="green",
                font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=(0, 20))
            
            ttk.Label(
                legend_frame,
                text="🔴 Rosso: Punti riflessi dal lato opposto rispetto all'asse di simmetria",
                foreground="red",
                font=("Arial", 9)
            ).pack(side=tk.LEFT)
            
            # Converte l'immagine per Tkinter
            if len(image_with_overlay.shape) == 3:
                # BGR -> RGB per la visualizzazione
                display_image = cv2.cvtColor(image_with_overlay, cv2.COLOR_BGR2RGB)
            else:
                display_image = image_with_overlay
                
            pil_image = Image.fromarray(display_image)
            
            # Calcola le dimensioni dello schermo per adattare l'immagine
            screen_width = correction_window.winfo_screenwidth()
            screen_height = correction_window.winfo_screenheight()
            
            # Riserva spazio per la barra del titolo, legenda e pulsanti (circa 200px)
            available_width = screen_width - 100  # Margini laterali
            available_height = screen_height - 200  # Spazio per UI elements
            
            # Calcola il fattore di scala per utilizzare quasi tutto lo schermo disponibile
            width_ratio = available_width / pil_image.width
            height_ratio = available_height / pil_image.height
            
            # Usa il rapporto minore per mantenere le proporzioni
            scale_factor = min(width_ratio, height_ratio)
            # Assicurati che l'immagine sia ingrandita significativamente (minimo 4x per il nuovo flusso)
            scale_factor = max(scale_factor, 4.0)
            
            # Applica il fattore di scala
            new_width = int(pil_image.width * scale_factor)
            new_height = int(pil_image.height * scale_factor)
            
            # Usa LANCZOS per un ingrandimento di alta qualità
            pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(pil_image)
            
            # Calcola le dimensioni della finestra in base all'immagine + spazio per UI
            ui_height = 180  # Aumentato spazio per titolo, legenda e pulsanti (evita taglio)
            window_width = pil_image.width + 40  # Margini laterali
            window_height = pil_image.height + ui_height
            
            # Imposta le dimensioni della finestra
            correction_window.geometry(f"{window_width}x{window_height}")
            
            # Centra la finestra sullo schermo
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            correction_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Canvas semplice senza scrollbar - l'immagine si adatta perfettamente
            image_canvas = tk.Canvas(
                main_frame,
                width=pil_image.width,
                height=pil_image.height,
                bg="white",
                highlightthickness=1,
                highlightbackground="gray"
            )
            image_canvas.pack(pady=10)
            
            # Aggiungi l'immagine al centro del canvas
            image_canvas.create_image(
                pil_image.width // 2,
                pil_image.height // 2,
                image=photo
            )
            
            # Mantieni riferimento all'immagine
            image_canvas.image = photo
            
            # Frame per i pulsanti
            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(fill=tk.X, pady=(10, 0))
            
            # Pulsante per salvare l'immagine
            def save_image():
                from tkinter import filedialog
                file_path = filedialog.asksaveasfilename(
                    title="Salva immagine sopracciglio",
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
                )
                if file_path:
                    try:
                        save_image = Image.fromarray(display_image)
                        save_image.save(file_path)
                        self.status_bar.config(text=f"✅ Immagine salvata: {file_path}")
                    except Exception as e:
                        messagebox.showerror("Errore", f"Impossibile salvare l'immagine:\n{e}")
            
            ttk.Button(
                buttons_frame,
                text="💾 Salva Immagine",
                command=save_image
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            # Pulsante per chiudere
            ttk.Button(
                buttons_frame,
                text="❌ Chiudi",
                command=correction_window.destroy
            ).pack(side=tk.RIGHT)
            
            self.status_bar.config(text=f"✅ Finestra correzione sopracciglio {side_name.lower()} aperta - NUOVO FLUSSO")
            
        except Exception as e:
            print(f"❌ Errore apertura finestra ritagliata: {e}")
            messagebox.showerror(
                "Errore",
                f"Errore nell'apertura finestra ritagliata:\n{e}"
            )
            
            # Crea una nuova finestra
            side_name = "Sinistro" if side == 'left' else "Destro"
            window_title = f"Correzione Sopracciglio {side_name}"
            
            correction_window = tk.Toplevel(self.root)
            correction_window.title(window_title)
            # Le dimensioni verranno calcolate automaticamente dopo aver preparato l'immagine
            
            # Frame principale
            main_frame = ttk.Frame(correction_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Titolo
            title_label = ttk.Label(
                main_frame, 
                text=f"🔍 {window_title}",
                font=("Arial", 14, "bold")
            )
            title_label.pack(pady=(0, 10))
            
            # Legenda
            legend_frame = ttk.Frame(main_frame)
            legend_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(
                legend_frame,
                text="🟢 Verde: Punti del sopracciglio corrente",
                foreground="green"
            ).pack(side=tk.LEFT, padx=(0, 20))
            
            ttk.Label(
                legend_frame,
                text="🔴 Rosso: Punti del sopracciglio controlaterale (riflesso)",
                foreground="red"
            ).pack(side=tk.LEFT)
            
            # Converte l'immagine per Tkinter
            if len(image_with_overlay.shape) == 3:
                # BGR -> RGB per la visualizzazione
                display_image = cv2.cvtColor(image_with_overlay, cv2.COLOR_BGR2RGB)
            else:
                display_image = image_with_overlay
                
            pil_image = Image.fromarray(display_image)
            
            # Calcola le dimensioni dello schermo per adattare l'immagine
            screen_width = correction_window.winfo_screenwidth()
            screen_height = correction_window.winfo_screenheight()
            
            # Riserva spazio per la barra del titolo, legenda e pulsanti (circa 200px)
            available_width = screen_width - 100  # Margini laterali
            available_height = screen_height - 200  # Spazio per UI elements
            
            # Calcola il fattore di scala per utilizzare quasi tutto lo schermo disponibile
            width_ratio = available_width / pil_image.width
            height_ratio = available_height / pil_image.height
            
            # Usa il rapporto minore per mantenere le proporzioni
            scale_factor = min(width_ratio, height_ratio)
            # Assicurati che l'immagine sia ingrandita significativamente (minimo 3x)
            scale_factor = max(scale_factor, 3.0)
            
            # Applica il fattore di scala
            new_width = int(pil_image.width * scale_factor)
            new_height = int(pil_image.height * scale_factor)
            
            # Usa LANCZOS per un ingrandimento di alta qualità
            pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(pil_image)
            
            # Calcola le dimensioni della finestra in base all'immagine + spazio per UI
            ui_height = 180  # Aumentato spazio per titolo, legenda e pulsanti (evita taglio)
            window_width = pil_image.width + 40  # Margini laterali
            window_height = pil_image.height + ui_height
            
            # Imposta le dimensioni della finestra
            correction_window.geometry(f"{window_width}x{window_height}")
            
            # Centra la finestra sullo schermo
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            correction_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            # Canvas semplice senza scrollbar - l'immagine si adatta perfettamente
            image_canvas = tk.Canvas(
                main_frame,
                width=pil_image.width,
                height=pil_image.height,
                bg="white",
                highlightthickness=1,
                highlightbackground="gray"
            )
            image_canvas.pack(pady=10)
            
            # Aggiungi l'immagine al centro del canvas
            image_canvas.create_image(
                pil_image.width // 2,
                pil_image.height // 2,
                image=photo
            )
            
            # Mantieni riferimento all'immagine
            image_canvas.image = photo
            
            # Frame per i pulsanti
            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(fill=tk.X, pady=(10, 0))
            
            # Pulsante per salvare l'immagine
            def save_image():
                from tkinter import filedialog
                file_path = filedialog.asksaveasfilename(
                    title="Salva immagine sopracciglio",
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
                )
                if file_path:
                    try:
                        save_image = Image.fromarray(display_image)
                        save_image.save(file_path)
                        self.status_bar.config(text=f"✅ Immagine salvata: {file_path}")
                    except Exception as e:
                        messagebox.showerror("Errore", f"Impossibile salvare l'immagine:\n{e}")
            
            ttk.Button(
                buttons_frame,
                text="💾 Salva Immagine",
                command=save_image
            ).pack(side=tk.LEFT, padx=(0, 10))
            
            # Pulsante per chiudere
            ttk.Button(
                buttons_frame,
                text="❌ Chiudi",
                command=correction_window.destroy
            ).pack(side=tk.RIGHT)
            
            self.status_bar.config(text=f"✅ Finestra correzione sopracciglio {side_name.lower()} aperta")
            
        except Exception as e:
            print(f"❌ Errore nell'apertura finestra correzione: {e}")
            messagebox.showerror(
                "Errore",
                f"Errore nell'apertura finestra correzione:\n{e}"
            )

    def show_left_eyebrow_correction(self):
        """Mostra la finestra di correzione per il sopracciglio sinistro."""
        self.show_eyebrow_correction_window('left')

    def show_right_eyebrow_correction(self):
        """Mostra la finestra di correzione per il sopracciglio destro."""  
        self.show_eyebrow_correction_window('right')

    def get_facial_symmetry_axis(self) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        Calcola l'asse di simmetria facciale basato sui landmarks.
        
        Returns:
            Optional[Tuple]: ((x1, y1), (x2, y2)) punti dell'asse di simmetria, None se non disponibile
        """
        try:
            if not self.current_landmarks or len(self.current_landmarks) < 10:
                print("❌ Landmarks non disponibili per calcolo asse")
                return None
            
            # MediaPipe landmark indices per asse di simmetria
            # 9: glabella (centro fronte), 151: mento
            glabella_idx = 9
            chin_idx = 151
            
            if len(self.current_landmarks) <= max(glabella_idx, chin_idx):
                print("❌ Landmarks insufficienti per asse di simmetria")
                return None
            
            # Ottieni i landmarks
            glabella = self.current_landmarks[glabella_idx]
            chin = self.current_landmarks[chin_idx]
            
            # Gestisce diversi formati di landmark (oggetto vs tuple)
            if hasattr(glabella, 'x') and hasattr(glabella, 'y'):
                # Formato MediaPipe (coordinate normalizzate 0-1)
                img_width = self.current_image.shape[1] if hasattr(self.current_image, 'shape') else 640
                img_height = self.current_image.shape[0] if hasattr(self.current_image, 'shape') else 480
                
                glabella_point = (glabella.x * img_width, glabella.y * img_height)
                chin_point = (chin.x * img_width, chin.y * img_height)
            elif isinstance(glabella, (tuple, list)) and len(glabella) >= 2:
                # Formato tuple/lista (coordinate già in pixel)
                glabella_point = (float(glabella[0]), float(glabella[1]))
                chin_point = (float(chin[0]), float(chin[1]))
            else:
                print("❌ Formato landmark non riconosciuto")
                return None
            
            print(f"🎯 Asse di simmetria calcolato: Glabella{glabella_point} -> Mento{chin_point}")
            return (glabella_point, chin_point)
            
        except Exception as e:
            print(f"❌ Errore calcolo asse di simmetria: {e}")
            return None

    def reflect_point_across_axis(self, point: Tuple[float, float], axis: Tuple[Tuple[float, float], Tuple[float, float]]) -> Tuple[float, float]:
        """
        Riflette un punto rispetto all'asse di simmetria.
        
        Args:
            point: (x, y) coordinate del punto da riflettere
            axis: ((x1, y1), (x2, y2)) punti dell'asse di simmetria
            
        Returns:
            Tuple[float, float]: Coordinate del punto riflesso
        """
        try:
            px, py = point
            (x1, y1), (x2, y2) = axis
            
            # Vettore direzione dell'asse
            dx = x2 - x1
            dy = y2 - y1
            
            # Normalizza il vettore
            length = np.sqrt(dx*dx + dy*dy)
            if length == 0:
                return point  # Asse degenere, restituisci punto originale
            
            dx_norm = dx / length
            dy_norm = dy / length
            
            # Vettore dal punto di partenza dell'asse al punto da riflettere
            px_rel = px - x1
            py_rel = py - y1
            
            # Proiezione del punto sull'asse
            dot_product = px_rel * dx_norm + py_rel * dy_norm
            proj_x = x1 + dot_product * dx_norm
            proj_y = y1 + dot_product * dy_norm
            
            # Punto riflesso (simmetrico rispetto all'asse)
            reflected_x = 2 * proj_x - px
            reflected_y = 2 * proj_y - py
            
            return (reflected_x, reflected_y)
            
        except Exception as e:
            print(f"❌ Errore riflessione punto: {e}")
            return point

    def create_full_canvas_eyebrow_overlay(self, side: str) -> Optional[np.ndarray]:
        """
        Crea un overlay sull'intera immagine canvas con:
        - Punti verdi originali del lato richiesto (SOLO SA, SA0, SC, SC1, SB)
        - Punti rossi riflessi dal lato opposto
        
        Args:
            side: 'left' o 'right' - il lato per cui creare la correzione
            
        Returns:
            Optional[np.ndarray]: Immagine con overlay completo o None se errore
        """
        try:
            print(f"🎨 Creazione overlay canvas completo per lato {side}")
            
            # Verifica prerequisiti
            if not self.has_green_dots_and_measurements():
                print("❌ Prerequisiti non soddisfatti per overlay")
                return None
            
            # Calcola l'asse di simmetria
            axis = self.get_facial_symmetry_axis()
            if axis is None:
                print("❌ Impossibile calcolare asse di simmetria")
                return None
            
            # Crea una copia dell'immagine originale
            if isinstance(self.current_image, Image.Image):
                base_image = np.array(self.current_image)
            else:
                base_image = self.current_image.copy()
            
            # Assicurati che sia in formato BGR per OpenCV
            if len(base_image.shape) == 3 and base_image.shape[2] == 3:
                # Se è RGB, convertilo in BGR
                base_image = cv2.cvtColor(base_image, cv2.COLOR_RGB2BGR)
            
            # Parametri per il disegno
            green_color = (0, 255, 0)  # Verde per punti originali del lato richiesto
            red_color = (0, 0, 255)    # Rosso per punti riflessi dal lato opposto
            circle_radius = 0  # Ridotto a 0 per puntini piccolissimi (punti minimi)
            circle_thickness = -1  # Riempiti
            
            # Ottieni i punti per il lato richiesto e quello opposto
            # FILTRO: Usa solo i punti specifici richiesti (SA, SA0, SC, SC1, SB)
            if side == 'left':
                target_dots = self.green_dots_processor.left_dots   # Punti verdi originali (sinistra)
                source_dots = self.green_dots_processor.right_dots  # Punti da riflettere (destra->sinistra)
                target_labels = ["SC1", "SA0", "SA", "SC", "SB"]  # Ordine punti sinistri
                print(f"🔍 Lato sinistro: {len(target_dots)} punti verdi originali, {len(source_dots)} punti da riflettere")
            else:  # side == 'right'
                target_dots = self.green_dots_processor.right_dots  # Punti verdi originali (destra)
                source_dots = self.green_dots_processor.left_dots   # Punti da riflettere (sinistra->destra)
                target_labels = ["DC1", "DB", "DC", "DA", "DA0"]  # Ordine punti destri
                print(f"🔍 Lato destro: {len(target_dots)} punti verdi originali, {len(source_dots)} punti da riflettere")
            
            # Disegna i punti verdi originali del lato richiesto (SOLO i 5 principali)
            points_drawn = 0
            for i, dot in enumerate(target_dots):
                # Limita ai primi 5 punti (SA, SA0, SC, SC1, SB o equivalenti destri)
                if i >= 5:  # Prendi solo i primi 5 punti
                    break
                    
                x, y = int(dot["x"]), int(dot["y"])
                cv2.circle(base_image, (x, y), circle_radius, green_color, circle_thickness)
                points_drawn += 1
                
                label = target_labels[i] if i < len(target_labels) else f"{side[0].upper()}{i+1}"
                print(f"  ✅ Punto verde {label}: ({x}, {y})")
            
            # Rifletti e disegna i punti rossi dal lato opposto (SOLO i 5 principali)
            # Salva anche le coordinate per disegnare le frecce
            green_points_coords = []  # Coordinate punti verdi originali
            red_points_coords = []    # Coordinate punti rossi riflessi
            
            # Prima salva le coordinate dei punti verdi già disegnati
            for i, dot in enumerate(target_dots):
                if i >= 5:
                    break
                green_points_coords.append((int(dot["x"]), int(dot["y"])))
            
            reflected_points = 0
            for i, dot in enumerate(source_dots):
                # Limita ai primi 5 punti
                if i >= 5:
                    break
                    
                original_point = (dot["x"], dot["y"])
                reflected_point = self.reflect_point_across_axis(original_point, axis)
                
                x, y = int(reflected_point[0]), int(reflected_point[1])
                
                # Verifica che il punto riflesso sia dentro i confini dell'immagine
                if 0 <= x < base_image.shape[1] and 0 <= y < base_image.shape[0]:
                    cv2.circle(base_image, (x, y), circle_radius, red_color, circle_thickness)
                    red_points_coords.append((x, y))
                    reflected_points += 1
                    print(f"  ✅ Punto rosso riflesso {i+1}: ({original_point[0]:.1f}, {original_point[1]:.1f}) -> ({x}, {y})")
                else:
                    red_points_coords.append(None)  # Segna punto fuori confini
                    print(f"  ⚠️ Punto riflesso fuori confini: ({x}, {y})")
            
            # NUOVA FUNZIONALITÀ: Disegna frecce verdi tra coppie SPECIFICHE (A-A, A0-A0, C-C, C1-C1, B-B)
            arrows_drawn = 0
            arrow_color = (0, 180, 0)  # Verde per le frecce
            
            # Funzione per trovare un punto specifico per nome in una lista di punti
            def find_point_by_name(dots_list, point_name):
                """Trova un punto specifico per nome nella lista dei punti."""
                for dot in dots_list:
                    if 'name' in dot and dot['name'] == point_name:
                        return (int(dot['x']), int(dot['y']))
                return None
            
            # SOLUZIONE CORRETTA: Usa gli indici per associare punti verdi alle coordinate riflesse
            # I punti riflessi sono già calcolati e salvati in red_points_coords
            
            # CORREZIONE MAPPATURA: I punti riflessi seguono l'ordine dei source_dots, non target_dots!
            # Devo mappare correttamente gli indici per le coppie anatomiche
            if side == 'left':
                # Lato sinistro: punti verdi = left_dots, punti da riflettere = right_dots  
                # Ma devo trovare quale indice di right_dots corrisponde a quale anatomico
                target_anatomic = ["SC1", "SA0", "SA", "SC", "SB"]  # Quello che voglio (sinistro)
                source_anatomic = ["DC1", "DA0", "DA", "DC", "DB"]  # Quello che rifletto (destro)
            else:  # side == 'right'
                # Lato destro: punti verdi = right_dots, punti da riflettere = left_dots
                target_anatomic = ["DC1", "DA0", "DA", "DC", "DB"]  # Quello che voglio (destro) 
                source_anatomic = ["SC1", "SA0", "SA", "SC", "SB"]  # Quello che rifletto (sinistro)
            
            # Mappatura delle coppie anatomiche corrette (indipendentemente dall'ordine nell'array)
            anatomic_pairs = [
                ("C1", "C1"),  # SC1 ↔ DC1
                ("A0", "A0"),  # SA0 ↔ DA0  
                ("A", "A"),    # SA ↔ DA
                ("C", "C"),    # SC ↔ DC
                ("B", "B")     # SB ↔ DB
            ]
            
            # MAPPATURA CORRETTA BASATA SUL LOG OSSERVATO:
            # Dal log: Lato destro verdi = DC1, DB, DC, DA, DA0 (indici 0,1,2,3,4)  
            # Dal log: Punti riflessi = da SC1, SA0, SA, SC, SB (indici 0,1,2,3,4)
            # DEVO MAPPARE: DC1→SC1, DB→SB, DC→SC, DA→SA, DA0→SA0
            
            if side == 'left':
                # Lato sinistro: punti verdi sinistri → riflessi destri
                # Ordine punti verdi sinistri: SC1, SA0, SA, SC, SB
                # Devono collegarsi a: DC1, DA0, DA, DC, DB (riflessi)
                correct_mapping = [0, 1, 2, 3, 4]  # Mappatura diretta per lato sinistro
                point_names = [
                    ("SC1", "DC1"), ("SA0", "DA0"), ("SA", "DA"), 
                    ("SC", "DC"), ("SB", "DB")
                ]
            else:  # side == 'right'
                # Lato destro: punti verdi destri → riflessi sinistri  
                # Ordine punti verdi destri: DC1, DB, DC, DA, DA0 (dal log)
                # Devono collegarsi a: SC1, SB, SC, SA, SA0 (corrispondenti anatomici)
                # Ma i punti riflessi sono nell'ordine: SC1, SA0, SA, SC, SB
                # MAPPATURA CORRETTA:
                # DC1(0) → SC1(0) ✓
                # DB(1) → SB(4) ✓  
                # DC(2) → SC(3) ✓
                # DA(3) → SA(2) ✓
                # DA0(4) → SA0(1) ✓
                correct_mapping = [0, 4, 3, 2, 1]  # Mappatura corretta per destro!
                point_names = [
                    ("DC1", "SC1"), ("DB", "SB"), ("DC", "SC"),
                    ("DA", "SA"), ("DA0", "SA0")
                ]
            
            # FRECCE COMPLETAMENTE DISABILITATE
            arrows_drawn = 0
            print(f"🚫 Frecce disabilitate - overlay solo con puntini verdi e rossi")
            
            print(f"🎨 Overlay creato: {points_drawn} punti verdi, {reflected_points} punti rossi, {arrows_drawn} piccole frecce verdi")
            return base_image
            
        except Exception as e:
            print(f"❌ Errore creazione overlay canvas: {e}")
            return None

    def show_temp_overlay_on_canvas(self, overlay_image: np.ndarray):
        """
        Mostra temporaneamente l'overlay completo sul canvas principale per debug.
        
        Args:
            overlay_image: Immagine con overlay da mostrare temporaneamente
        """
        try:
            # Salva l'immagine corrente
            original_image = self.current_image
            
            # Converte overlay in formato PIL
            if len(overlay_image.shape) == 3:
                # BGR -> RGB per PIL
                rgb_image = cv2.cvtColor(overlay_image, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = overlay_image
                
            overlay_pil = Image.fromarray(rgb_image)
            
            # Mostra temporaneamente sul canvas
            self.current_image = overlay_pil
            self.update_canvas_display()
            
            # Programma il ripristino dell'immagine originale dopo 3 secondi
            # e salva i parametri per continuare dopo il ripristino
            self._temp_overlay_params = {
                'original_image': original_image,
                'continue_function': getattr(self, '_continue_after_overlay', None),
                'continue_params': getattr(self, '_continue_params', None)
            }
            self.root.after(3000, lambda: self.restore_and_continue())
            
            print("🎨 Overlay temporaneo mostrato sul canvas (3 secondi)")
            
        except Exception as e:
            print(f"❌ Errore visualizzazione overlay temporaneo: {e}")
    
    def restore_and_continue(self):
        """Ripristina l'immagine originale e continua con la funzione programmata."""
        try:
            # Ripristina immagine originale dai parametri temporanei
            if hasattr(self, '_temp_overlay_params'):
                params = self._temp_overlay_params
                self.current_image = params['original_image']
                self.update_canvas_display()
                print("🔄 Immagine originale ripristinata")
                
                # Pulisci parametri temporanei
                delattr(self, '_temp_overlay_params')
            
            # Continua con la funzione programmata se presente
            if hasattr(self, '_continue_function') and hasattr(self, '_continue_params'):
                continue_func = self._continue_function
                continue_params = self._continue_params
                
                print(f"🔄 Continuando con: {continue_func.__name__} con parametri {list(continue_params.keys())}")
                
                # Pulisci i riferimenti PRIMA di chiamare la funzione
                delattr(self, '_continue_function')
                delattr(self, '_continue_params')
                
                # Chiama la funzione di continuazione
                continue_func(**continue_params)
            else:
                print("⚠️ Nessuna funzione di continuazione programmata")
                    
        except Exception as e:
            print(f"❌ Errore ripristino e continuazione: {e}")
            import traceback
            traceback.print_exc()
    
    def restore_original_image(self, original_image):
        """Ripristina l'immagine originale sul canvas (metodo legacy)."""
        try:
            self.current_image = original_image
            self.update_canvas_display()
            print("🔄 Immagine originale ripristinata")
        except Exception as e:
            print(f"❌ Errore ripristino immagine: {e}")
            
    def toggle_debug_overlay_mode(self):
        """Attiva/disattiva la modalità debug per mostrare overlay completo."""
        if not hasattr(self, 'debug_show_full_overlay'):
            self.debug_show_full_overlay = False
        
        self.debug_show_full_overlay = not self.debug_show_full_overlay
        status = "attivata" if self.debug_show_full_overlay else "disattivata"
        print(f"🐛 Modalità debug overlay {status}")
        self.status_bar.config(text=f"Debug overlay: {status}")

    def update_eyebrow_correction_buttons_state(self):
        """Aggiorna lo stato (abilitato/disabilitato) dei pulsanti di correzione sopracciglio."""
        try:
            if hasattr(self, 'eyebrow_correction_buttons'):
                # Verifica se la funzionalità può essere utilizzata
                can_use_correction = self.has_green_dots_and_measurements()
                
                # Aggiorna lo stato di tutti i pulsanti di correzione
                for button in self.eyebrow_correction_buttons:
                    if can_use_correction:
                        button.configure(state=tk.NORMAL)
                    else:
                        button.configure(state=tk.DISABLED)
                        
                # Log per debug
                status = "abilitati" if can_use_correction else "disabilitati"
                print(f"🔧 Pulsanti correzione sopracciglio {status}")
                
        except Exception as e:
            print(f"❌ Errore aggiornamento stato pulsanti correzione: {e}")


    # === ANALISI FACCIALE PROFESSIONALE ===
    def perform_face_analysis(self):
        """
        Esegue l'analisi facciale completa utilizzando il modulo professionale.
        Mostra i risultati nella tabella misurazioni e genera nuove finestre per le immagini.
        """
        try:
            # Verifica se c'è un'immagine nel canvas
            if self.current_image is None:
                messagebox.showwarning("Nessuna Immagine", 
                                     "Carica prima un'immagine nel canvas per procedere con l'analisi facciale.")
                return

            # Aggiorna status bar
            self.status_bar.config(text="🔍 Esecuzione analisi facciale professionale...")
            self.root.update()

            # Salva temporaneamente l'immagine corrente
            import tempfile
            import os
            temp_dir = tempfile.mkdtemp(prefix="face_analysis_")
            temp_image_path = os.path.join(temp_dir, "current_image.jpg")
            
            # Converti l'immagine PIL in formato OpenCV e salva
            if isinstance(self.current_image, Image.Image):
                # Converti PIL Image in array numpy
                img_array = np.array(self.current_image)
                if len(img_array.shape) == 3:
                    # Converti RGB a BGR per OpenCV
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                cv2.imwrite(temp_image_path, img_array)
            else:
                # Se è già un array numpy
                cv2.imwrite(temp_image_path, self.current_image)

            # Esegui l'analisi facciale
            print("🔍 Avvio analisi facciale professionale...")
            result = self.face_analyzer.analyze_face(temp_image_path, output_dir=temp_dir)
            
            # Genera il report testuale
            report_path = os.path.join(temp_dir, "report_completo.txt")
            report_text = self.face_analyzer.generate_text_report(result, output_path=report_path)
            
            # Aggiorna la tabella misurazioni con i risultati dell'analisi
            self._update_measurements_table_with_analysis(result)
            
            # Mostra le immagini generate dall'analisi
            self._display_analysis_images(result)
            
            # Mostra finestra con il report completo
            self._show_analysis_report_window(report_text, result)
            
            # Aggiorna status bar
            self.status_bar.config(text="✅ Analisi facciale completata con successo")
            
            # Log dei risultati
            print(f"✅ Analisi facciale completata")
            print(f"📊 Forma viso rilevata: {result['forma_viso']}")
            print(f"🎯 Sopracciglio consigliato: {result['analisi_visagistica']['forma_sopracciglio']}")
            print(f"📁 Risultati salvati in: {temp_dir}")
            
            # Cleanup temporaneo dopo qualche secondo (opzionale)
            # self.root.after(30000, lambda: self._cleanup_temp_dir(temp_dir))
            
        except Exception as e:
            error_msg = f"❌ Errore durante l'analisi facciale: {str(e)}"
            print(error_msg)
            self.status_bar.config(text="❌ Errore nell'analisi facciale")
            messagebox.showerror("Errore Analisi Facciale", error_msg)

    def _update_measurements_table_with_analysis(self, result: dict):
        """
        Aggiorna la tabella misurazioni con i risultati dell'analisi facciale.
        """
        try:
            # Aggiungi voce per la forma del viso
            self.measurements_tree.insert(
                "", "end", 
                values=("Forma Viso", result['forma_viso'], "", "✅ Rilevata")
            )
            
            # Aggiungi raccomandazione sopracciglio
            eyebrow_rec = result['analisi_visagistica']['forma_sopracciglio']
            self.measurements_tree.insert(
                "", "end",
                values=("Sopracciglio Consigliato", eyebrow_rec, "", "✅ Raccomandato")  
            )
            
            # Aggiungi metriche facciali principali
            metrics = result['metriche_facciali']
            key_metrics = [
                ("Rapporto L/W", f"{metrics['rapporto_lunghezza_larghezza']:.2f}", "ratio"),
                ("Larghezza Fronte", f"{metrics['larghezza_fronte']:.1f}", "px"),
                ("Larghezza Zigomi", f"{metrics['larghezza_zigomi']:.1f}", "px"),
                ("Larghezza Mascella", f"{metrics['larghezza_mascella']:.1f}", "px"),
                ("Distanza Occhi", f"{metrics['distanza_occhi']:.1f}", "px"),
                ("Larghezza Naso", f"{metrics['larghezza_naso']:.1f}", "px"),
                ("Larghezza Bocca", f"{metrics['larghezza_bocca']:.1f}", "px")
            ]
            
            for metric_name, value, unit in key_metrics:
                self.measurements_tree.insert(
                    "", "end",
                    values=(metric_name, value, unit, "📊 Calcolata")
                )
                
        except Exception as e:
            print(f"❌ Errore aggiornamento tabella misurazioni: {e}")

    def _display_analysis_images(self, result: dict):
        """
        Mostra le immagini generate dall'analisi in nuove finestre.
        """
        try:
            images_info = result.get('immagini_debug', {})
            
            for image_name, image_path in images_info.items():
                if os.path.exists(image_path):
                    self._create_image_window(image_name, image_path)
                    
        except Exception as e:
            print(f"❌ Errore visualizzazione immagini analisi: {e}")

    def _create_image_window(self, title: str, image_path: str):
        """
        Crea una nuova finestra per visualizzare un'immagine dell'analisi.
        """
        try:
            # Crea una nuova finestra
            window = tk.Toplevel(self.root)
            window.title(f"Analisi Facciale - {title}")
            window.geometry("600x500")
            
            # Carica e ridimensiona l'immagine
            img = Image.open(image_path)
            img.thumbnail((580, 450), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            # Frame per l'immagine
            frame = ttk.Frame(window)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Label per l'immagine
            label = ttk.Label(frame, image=photo)
            label.pack(pady=5)
            
            # Mantieni riferimento all'immagine
            label.image = photo
            
            # Pulsante per salvare l'immagine
            save_btn = ttk.Button(
                frame, 
                text="💾 Salva Immagine",
                command=lambda: self._save_analysis_image(image_path)
            )
            save_btn.pack(pady=5)
            
        except Exception as e:
            print(f"❌ Errore creazione finestra immagine: {e}")

    def _save_analysis_image(self, source_path: str):
        """
        Salva un'immagine dell'analisi in una posizione scelta dall'utente.
        """
        try:
            file_path = filedialog.asksaveasfilename(
                title="Salva Immagine Analisi",
                defaultextension=".png",
                filetypes=[
                    ("PNG", "*.png"),
                    ("JPEG", "*.jpg"),
                    ("Tutti i file", "*.*")
                ]
            )
            
            if file_path:
                # Copia il file
                import shutil
                shutil.copy2(source_path, file_path)
                print(f"💾 Immagine salvata in: {file_path}")
                messagebox.showinfo("Salvataggio", f"Immagine salvata con successo in:\n{file_path}")
                
        except Exception as e:
            error_msg = f"Errore nel salvataggio: {e}"
            print(f"❌ {error_msg}")
            messagebox.showerror("Errore", error_msg)

    def _show_analysis_report_window(self, report_text: str, result: dict):
        """
        Mostra una finestra con il report completo dell'analisi facciale.
        """
        try:
            # Crea finestra per il report
            report_window = tk.Toplevel(self.root)
            report_window.title("📋 Report Analisi Facciale Completa")
            report_window.geometry("800x600")
            
            # Frame principale
            main_frame = ttk.Frame(report_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Area di testo con scrollbar
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            text_area = tk.Text(
                text_frame,
                wrap=tk.WORD,
                font=("Consolas", 10),
                bg="#f8f9fa",
                fg="#212529"
            )
            
            scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_area.yview)
            text_area.configure(yscrollcommand=scrollbar.set)
            
            text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Inserisci il testo del report
            text_area.insert(tk.END, report_text)
            text_area.config(state=tk.DISABLED)  # Read-only
            
            # Frame per i pulsanti
            buttons_frame = ttk.Frame(main_frame)
            buttons_frame.pack(fill=tk.X, pady=(10, 0))
            
            # Pulsante per salvare il report
            save_report_btn = ttk.Button(
                buttons_frame,
                text="💾 Salva Report",
                command=lambda: self._save_analysis_report(report_text)
            )
            save_report_btn.pack(side=tk.LEFT, padx=(0, 5))
            
            # Pulsante per copiare negli appunti
            copy_btn = ttk.Button(
                buttons_frame,
                text="📋 Copia negli Appunti",
                command=lambda: self._copy_to_clipboard(report_text)
            )
            copy_btn.pack(side=tk.LEFT, padx=5)
            
            # Pulsante chiudi
            close_btn = ttk.Button(
                buttons_frame,
                text="❌ Chiudi",
                command=report_window.destroy
            )
            close_btn.pack(side=tk.RIGHT)
            
        except Exception as e:
            print(f"❌ Errore creazione finestra report: {e}")

    def _save_analysis_report(self, report_text: str):
        """Salva il report dell'analisi in un file."""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Salva Report Analisi",
                defaultextension=".txt",
                filetypes=[
                    ("File di testo", "*.txt"),
                    ("Tutti i file", "*.*")
                ]
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                print(f"💾 Report salvato in: {file_path}")
                messagebox.showinfo("Salvataggio", f"Report salvato con successo in:\n{file_path}")
                
        except Exception as e:
            error_msg = f"Errore nel salvataggio del report: {e}"
            print(f"❌ {error_msg}")
            messagebox.showerror("Errore", error_msg)

    def _copy_to_clipboard(self, text: str):
        """Copia il testo negli appunti."""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Copia", "Report copiato negli appunti!")
            
        except Exception as e:
            print(f"❌ Errore copia negli appunti: {e}")

    def perform_face_analysis_with_voice(self):
        """
        Esegue l'analisi facciale completa e legge il report ad alta voce.
        Versione specifica per comandi vocali.
        """
        try:
            # Verifica se c'è un'immagine nel canvas
            if self.current_image is None:
                error_msg = "Nessuna immagine caricata. Carica prima un'immagine per procedere con l'analisi facciale."
                print(f"❌ {error_msg}")
                
                # Usa l'assistente vocale per comunicare l'errore
                if hasattr(self, 'voice_assistant') and self.voice_assistant:
                    self.voice_assistant.speak(error_msg)
                
                messagebox.showwarning("Nessuna Immagine", error_msg)
                return

            # Informa l'utente che l'analisi sta iniziando
            if hasattr(self, 'voice_assistant') and self.voice_assistant:
                self.voice_assistant.speak("Analisi facciale in corso, attendere...")

            # Aggiorna status bar
            self.status_bar.config(text="🔍 Esecuzione analisi facciale professionale via comando vocale...")
            self.root.update()

            # Salva temporaneamente l'immagine corrente
            import tempfile
            import os
            temp_dir = tempfile.mkdtemp(prefix="face_analysis_voice_")
            temp_image_path = os.path.join(temp_dir, "current_image.jpg")
            
            # Converti l'immagine PIL in formato OpenCV e salva
            if isinstance(self.current_image, Image.Image):
                # Converti PIL Image in array numpy
                img_array = np.array(self.current_image)
                if len(img_array.shape) == 3:
                    # Converti RGB a BGR per OpenCV
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                cv2.imwrite(temp_image_path, img_array)
            else:
                # Se è già un array numpy
                cv2.imwrite(temp_image_path, self.current_image)

            # Esegui l'analisi facciale
            print("🎤 Avvio analisi facciale professionale da comando vocale...")
            result = self.face_analyzer.analyze_face(temp_image_path, output_dir=temp_dir)
            
            # Genera il report testuale
            report_path = os.path.join(temp_dir, "report_completo.txt")
            report_text = self.face_analyzer.generate_text_report(result, output_path=report_path)
            
            # Aggiorna la tabella misurazioni con i risultati dell'analisi
            self._update_measurements_table_with_analysis(result)
            
            # Mostra le immagini generate dall'analisi (opzionale per comando vocale)
            self._display_analysis_images(result)
            
            # **NUOVA FUNZIONALITÀ**: Leggi il report ad alta voce
            self._read_analysis_report_aloud(result, report_text)
            
            # Aggiorna status bar
            self.status_bar.config(text="✅ Analisi facciale completata e report letto")
            
            # Log dei risultati
            print(f"✅ Analisi facciale vocale completata")
            print(f"📊 Forma viso rilevata: {result['forma_viso']}")
            print(f"🎯 Sopracciglio consigliato: {result['analisi_visagistica']['forma_sopracciglio']}")
            print(f"📁 Risultati salvati in: {temp_dir}")
            
        except Exception as e:
            error_msg = f"❌ Errore durante l'analisi facciale: {str(e)}"
            print(error_msg)
            self.status_bar.config(text="❌ Errore nell'analisi facciale")
            
            # Comunica l'errore vocalmente
            if hasattr(self, 'voice_assistant') and self.voice_assistant:
                self.voice_assistant.speak("Si è verificato un errore durante l'analisi facciale.")
            
            messagebox.showerror("Errore Analisi Facciale", error_msg)

    def _read_analysis_report_aloud(self, result: dict, full_report_text: str):
        """
        Legge ad alta voce un riassunto del report di analisi facciale.
        
        Args:
            result: Risultati dell'analisi facciale
            full_report_text: Testo completo del report (per riferimento)
        """
        try:
            if not hasattr(self, 'voice_assistant') or not self.voice_assistant:
                print("❌ Assistente vocale non disponibile per lettura report")
                return

            print("🔊 Preparazione lettura report ad alta voce...")

            # Crea un riassunto vocale dei risultati principali
            forma_viso = result['forma_viso']
            analisi_visagistica = result['analisi_visagistica']
            metriche = result['metriche_facciali']
            
            # Costruisci il report vocale
            report_vocale = []
            
            # Introduzione
            report_vocale.append("Analisi facciale completata.")
            
            # Forma del viso
            report_vocale.append(f"La forma del viso rilevata è: {forma_viso}.")
            
            # Raccomandazione sopracciglio
            forma_sopracciglio = analisi_visagistica['forma_sopracciglio']
            # Converte l'enum in stringa se necessario
            if hasattr(forma_sopracciglio, 'value'):
                forma_sopracciglio_str = forma_sopracciglio.value
            else:
                forma_sopracciglio_str = str(forma_sopracciglio)
            
            report_vocale.append(f"Il tipo di sopracciglio consigliato è: {forma_sopracciglio_str}.")
            
            # Metriche principali
            rapporto_lw = metriche['rapporto_lunghezza_larghezza']
            report_vocale.append(f"Il rapporto lunghezza larghezza del viso è {rapporto_lw:.2f}.")
            
            # Raccomandazione principale
            motivazione = analisi_visagistica['motivazione_scientifica']
            # Prendi solo la prima frase della motivazione per non essere troppo lungo
            prima_frase = motivazione.split('.')[0] + '.'
            report_vocale.append(f"Motivazione: {prima_frase}")
            
            # Metriche aggiuntive interessanti
            larghezza_fronte = metriche['larghezza_fronte']
            larghezza_zigomi = metriche['larghezza_zigomi']  
            larghezza_mascella = metriche['larghezza_mascella']
            
            report_vocale.append(f"Misure facciali: fronte {larghezza_fronte:.0f} pixel, zigomi {larghezza_zigomi:.0f} pixel, mascella {larghezza_mascella:.0f} pixel.")
            
            # Conclusione
            report_vocale.append("Report completo disponibile nella finestra di dettaglio. Analisi completata.")
            
            # Unisci tutto il testo
            testo_completo = " ".join(report_vocale)
            
            print(f"🔊 Lettura report: {len(testo_completo)} caratteri")
            
            # Leggi il report ad alta voce
            self.voice_assistant.speak(testo_completo)
            
            print("✅ Lettura report completata")
            
        except Exception as e:
            print(f"❌ Errore durante lettura report vocale: {e}")
            # Fallback: lettura di base
            if hasattr(self, 'voice_assistant') and self.voice_assistant:
                self.voice_assistant.speak("Analisi facciale completata. Controlla i risultati nella tabella misurazioni.")

    # === FUNZIONI PER COMANDI VOCALI ===
    def show_help(self):
        """Mostra aiuto per comandi vocali"""
        print("Comandi vocali disponibili:")
        print("- Analizza volto, Carica immagine, Avvia webcam")
        print("- Calcola misura, Salva risultati, Asse simmetria") 
        print("- Landmarks, Punti verdi, Cancella tutto")
        print("- Zoom in/out, Aiuto, Stato")
    
    def show_status(self):
        """Mostra stato del sistema"""
        has_image = self.image is not None
        has_landmarks = len(self.landmarks) > 0
        print(f"Sistema: Attivo | Immagine: {'Sì' if has_image else 'No'} | Landmarks: {'Sì' if has_landmarks else 'No'}")


def main():
    """Funzione principale per avviare l'applicazione."""
    root = tk.Tk()
    app = CanvasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
