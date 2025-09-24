"""
Interactive canvas application for facial analysis with measurement tools.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import List, Tuple, Optional, Dict
from src.face_detector import FaceDetector
from src.video_analyzer import VideoAnalyzer
from src.measurement_tools import MeasurementTools
from src.green_dots_processor import GreenDotsProcessor
from src.scoring_config import ScoringConfig
from src.utils import resize_image_keep_aspect
from src.professional_canvas import ProfessionalCanvas
import matplotlib.pyplot as plt


class CanvasApp:
    def __init__(self, root):
        """Inizializza l'applicazione canvas."""
        self.root = root
        self.root.title("Facial Analysis Canvas")
        self.root.geometry("1600x1000")
        self.root.minsize(1200, 800)  # Dimensione minima
        self.root.resizable(True, True)  # Finestra ridimensionabile

        # Componenti principali
        self.face_detector = FaceDetector()
        self.video_analyzer = VideoAnalyzer()
        self.measurement_tools = MeasurementTools()
        self.green_dots_processor = GreenDotsProcessor()

        # Variabili di stato
        self.current_image = None
        self.current_landmarks = None
        self.canvas_image = None
        self.canvas_scale = 1.0
        self.canvas_offset = (0, 0)

        # Variabili per display e scaling del canvas professionale
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

    def setup_gui(self):
        """Configura l'interfaccia grafica con layout professionale stabile."""
        # Menu principale
        self.create_menu()

        # Imposta dimensioni finestra
        self.root.minsize(1400, 900)
        self.root.geometry("1600x1000")

        # Configura la griglia principale con dimensioni fisse per stabilità
        self.root.grid_rowconfigure(0, weight=1, minsize=600)  # Area principale
        self.root.grid_rowconfigure(
            1, weight=0, minsize=280
        )  # Area misurazioni (fissa)
        self.root.grid_rowconfigure(2, weight=0, minsize=30)  # Status bar (fisso)

        # Colonne con larghezze fisse per prevenire tremolii
        self.root.grid_columnconfigure(
            0, weight=0, minsize=420
        )  # Controlli (larghezza aumentata)
        self.root.grid_columnconfigure(1, weight=1, minsize=600)  # Canvas (espandibile)
        self.root.grid_columnconfigure(
            2, weight=0, minsize=400
        )  # Anteprima (larghezza fissa)

        # Setup area controlli (sinistra) con larghezza fissa
        control_main_frame = ttk.Frame(self.root, width=420)
        control_main_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=5)
        control_main_frame.grid_propagate(
            False
        )  # Impedisce ridimensionamento automatico
        control_main_frame.grid_rowconfigure(0, weight=1)
        control_main_frame.grid_columnconfigure(0, weight=1)

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

        # Funzione per scroll migliorata
        def _on_mousewheel(event):
            control_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Bind ricorsivo del mouse wheel per tutti i widget del frame controlli
        def bind_mousewheel_to_frame(widget):
            """Applica il binding del mouse wheel ricorsivamente."""
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel_to_frame(child)

        # Applica il binding iniziale
        control_canvas.bind("<MouseWheel>", _on_mousewheel)

        # Dopo aver creato i controlli, applicheremo il binding ricorsivo
        self.setup_controls(self.scrollable_control_frame)

        # Applica il binding a tutti i widget figli dopo la creazione
        bind_mousewheel_to_frame(self.scrollable_control_frame)

        # Setup area canvas principale (centro) - espandibile
        canvas_frame = ttk.LabelFrame(self.root, text="Canvas Principale", padding=10)
        canvas_frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=5)
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        self.setup_canvas(canvas_frame)

        # Setup area anteprima integrata (destra) con scrolling moderno
        preview_main_frame = ttk.Frame(self.root, width=400)
        preview_main_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 5), pady=5)
        preview_main_frame.grid_propagate(
            False
        )  # Impedisce ridimensionamento automatico
        preview_main_frame.grid_rowconfigure(0, weight=1)
        preview_main_frame.grid_columnconfigure(0, weight=1)

        # Canvas scrollabile per l'area anteprima
        preview_canvas = tk.Canvas(preview_main_frame, highlightthickness=0, width=380)
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

        # Funzione per scroll migliorata area anteprima
        def _on_preview_mousewheel(event):
            preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Bind ricorsivo del mouse wheel per l'area anteprima
        def bind_preview_mousewheel(widget):
            """Applica il binding del mouse wheel ricorsivamente all'area anteprima."""
            widget.bind("<MouseWheel>", _on_preview_mousewheel)
            for child in widget.winfo_children():
                bind_preview_mousewheel(child)

        preview_canvas.bind("<MouseWheel>", _on_preview_mousewheel)

        self.setup_integrated_preview(self.scrollable_preview_frame)

        # Setup area misurazioni (in basso) con altezza fissa
        measurements_frame = ttk.LabelFrame(
            self.root, text="Lista Misurazioni", padding=10, height=280
        )
        measurements_frame.grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=(0, 5)
        )
        measurements_frame.grid_propagate(
            False
        )  # Impedisce ridimensionamento automatico
        measurements_frame.grid_columnconfigure(0, weight=1)
        self.setup_measurements_area(measurements_frame)

        # Setup status bar con altezza fissa
        self.setup_status_bar()

        # Applica il binding del mouse wheel all'area anteprima dopo la creazione
        bind_preview_mousewheel(self.scrollable_preview_frame)

        # Gestisci chiusura applicazione
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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
        """Configura il canvas professionale per la visualizzazione."""
        # Inizializza il canvas professionale
        self.professional_canvas = ProfessionalCanvas(parent)

        # Mantieni riferimento al canvas per compatibilità
        self.canvas = self.professional_canvas.mpl_canvas.get_tk_widget()

        # Collega eventi del canvas professionale ai metodi esistenti
        self.professional_canvas.mpl_canvas.mpl_connect(
            "button_press_event", self.on_professional_canvas_click
        )

        # Configura callback per compatibilità con misurazione
        self.professional_canvas.measurement_callback = self.on_measurement_completed

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

        # Reset canvas centrale
        if hasattr(self, "professional_canvas"):
            self.professional_canvas.clear_canvas()
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
        """Configura l'area delle misurazioni."""
        # Treeview per le misurazioni esistenti (più compatta)
        self.measurements_tree = ttk.Treeview(
            parent,
            columns=("Type", "Value", "Unit"),
            show="headings",
            height=6,  # Altezza ridotta
        )

        self.measurements_tree.heading("Type", text="Tipo")
        self.measurements_tree.heading("Value", text="Valore")
        self.measurements_tree.heading("Unit", text="Unità")

        self.measurements_tree.column("Type", width=150)
        self.measurements_tree.column("Value", width=80)
        self.measurements_tree.column("Unit", width=50)

        # Scrollbar per la lista misurazioni
        tree_scroll = ttk.Scrollbar(
            parent, orient=tk.VERTICAL, command=self.measurements_tree.yview
        )
        self.measurements_tree.configure(yscrollcommand=tree_scroll.set)

        # Layout con grid
        self.measurements_tree.grid(row=0, column=0, sticky="ew")
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

            # Aggiorna le informazioni
            self.best_frame_info.config(
                text=f"Miglior frame: Score {score:.2f} (Auto-aggiornato)"
            )
            self.status_bar.config(
                text=f"Canvas aggiornato automaticamente - Score: {score:.2f}"
            )

            print(f"Canvas aggiornato automaticamente con score: {score:.2f}")

        except Exception as e:
            print(f"Errore nell'aggiornamento automatico del canvas: {e}")

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
        image: np.ndarray,
        landmarks: Optional[List[Tuple[float, float]]] = None,
        auto_resize: bool = True,
    ):
        """Imposta l'immagine corrente nel canvas."""
        self.current_image = image.copy()
        self.current_landmarks = landmarks

        if landmarks is None:
            # Rileva automaticamente i landmark
            self.detect_landmarks()

        # Usa refresh_canvas_only() se non vogliamo ridimensionare automaticamente
        if auto_resize:
            self.update_canvas_display()
        else:
            self.refresh_canvas_only()

    def detect_landmarks(self):
        """Rileva i landmark facciali nell'immagine corrente."""
        if self.current_image is not None:
            landmarks = self.face_detector.detect_face_landmarks(self.current_image)
            self.current_landmarks = landmarks
            # Non richiama update_canvas_display per mantenere la scala corrente
            # Richiama solo il refresh del canvas senza ricalcolare la scala
            self.refresh_canvas_only()

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

                # Aggiorna la visualizzazione del canvas
                self.refresh_canvas_only()

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

        # Aggiorna la visualizzazione
        self.refresh_canvas_only()

        status = "attivato" if self.show_green_dots_overlay else "disattivato"
        self.status_bar.config(text=f"Overlay puntini verdi {status}")

    def refresh_canvas_only(self):
        """Aggiorna solo il canvas senza ricalcolare la scala."""
        if self.current_image is None:
            return

        # Usa la scala già esistente per mantenere lo zoom corrente
        if not hasattr(self, "display_scale") or self.display_scale == 0:
            self.update_canvas_display()  # Fallback se non c'è scala
            return

        # Crea una copia dell'immagine per la visualizzazione
        display_image = self.current_image.copy()

        # Disegna tutti i landmark se abilitati
        if self.show_all_landmarks and self.current_landmarks:
            display_image = self.face_detector.draw_landmarks(
                display_image,
                self.current_landmarks,
                draw_all=True,
                key_only=False,
            )

        # Disegna l'asse di simmetria se abilitato
        if self.show_axis_var.get() and self.current_landmarks:
            display_image = self.face_detector.draw_symmetry_axis(
                display_image, self.current_landmarks
            )

        # Disegna le selezioni correnti
        for i, point in enumerate(self.selected_points):
            cv2.circle(display_image, point, 5, (255, 0, 255), -1)
            cv2.putText(
                display_image,
                str(i + 1),
                (point[0] + 10, point[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 255),
                1,
            )

        # Disegna i landmark selezionati in modalità landmark
        if self.landmark_measurement_mode and self.current_landmarks:
            for i, landmark_idx in enumerate(self.selected_landmarks):
                if landmark_idx < len(self.current_landmarks):
                    point = self.current_landmarks[landmark_idx]
                    # Cerchio più grande per landmark selezionati
                    cv2.circle(
                        display_image,
                        (int(point[0]), int(point[1])),
                        8,
                        (0, 255, 255),
                        3,
                    )

        # Sovrappone l'overlay dei puntini verdi se abilitato
        if self.show_green_dots_overlay and self.green_dots_overlay is not None:
            # Converte l'immagine OpenCV in PIL per la composizione
            display_pil = Image.fromarray(
                cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
            )

            # Compone l'overlay trasparente con l'immagine
            display_pil = Image.alpha_composite(
                display_pil.convert("RGBA"), self.green_dots_overlay.convert("RGBA")
            )

            # Riconverte in formato OpenCV
            display_image = cv2.cvtColor(
                np.array(display_pil.convert("RGB")), cv2.COLOR_RGB2BGR
            )

        # Usa la scala esistente per ridimensionare
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width > 1 and canvas_height > 1:
            # Ridimensiona usando la scala esistente
            display_image = resize_image_keep_aspect(
                display_image, canvas_width, canvas_height
            )

        # Converte per Tkinter
        display_image_rgb = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(display_image_rgb)
        self.canvas_image = ImageTk.PhotoImage(pil_image)

        # Aggiorna canvas professionale
        if hasattr(self, "professional_canvas"):
            self.update_canvas_display()

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

    def on_canvas_click(self, event):
        """Gestisce i click sul canvas."""
        if self.current_image is None:
            return

        # Converte coordinate canvas in coordinate immagine originale
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # Usa il metodo di conversione corretto
        image_x, image_y = self.canvas_to_image_coordinates(canvas_x, canvas_y)

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

        self.update_canvas_display()

    def on_canvas_zoom(self, event):
        """Gestisce lo zoom del canvas."""
        # TODO: Implementare zoom
        pass

    def on_canvas_drag(self, event):
        """Gestisce il trascinamento del canvas."""
        # TODO: Implementare pan
        pass

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

    def on_professional_canvas_click(self, event):
        """Gestisce i click sul canvas professionale per compatibilità con misurazione."""
        if event.inaxes and hasattr(self, "measurement_tools"):
            # Le coordinate matplotlib sono già nel sistema di coordinate dell'immagine
            x, y = event.xdata, event.ydata

            if x is None or y is None:
                return

            # Converte in coordinate intere per compatibilità
            image_x, image_y = int(x), int(y)

            # Gestisce la selezione diretta senza conversione coordinate
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

                self.status_bar.config(
                    text=f"Punto selezionato: ({image_x}, {image_y})"
                )

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

    def update_canvas_display(self):
        """Aggiorna la visualizzazione del canvas professionale con tutti gli overlay."""
        if not hasattr(self, "professional_canvas") or self.current_image is None:
            return

        # Crea una copia dell'immagine per la visualizzazione con tutti gli overlay
        display_image = self.current_image.copy()

        # Disegna tutti i landmark se abilitati
        if self.show_all_landmarks and self.current_landmarks:
            display_image = self.face_detector.draw_landmarks(
                display_image,
                self.current_landmarks,
                draw_all=True,
                key_only=False,
            )

        # Disegna l'asse di simmetria se abilitato
        if (
            hasattr(self, "show_axis_var")
            and self.show_axis_var.get()
            and self.current_landmarks
        ):
            display_image = self.face_detector.draw_symmetry_axis(
                display_image, self.current_landmarks
            )

        # Disegna le selezioni correnti
        for i, point in enumerate(self.selected_points):
            cv2.circle(display_image, point, 5, (255, 0, 255), -1)

        # Disegna i landmark selezionati in modalità landmark
        if (
            hasattr(self, "landmark_measurement_mode")
            and self.landmark_measurement_mode
            and self.current_landmarks
        ):
            for i, landmark_idx in enumerate(self.selected_landmarks):
                if landmark_idx < len(self.current_landmarks):
                    point = self.current_landmarks[landmark_idx]
                    # Cerchio più grande per landmark selezionati
                    cv2.circle(
                        display_image,
                        (int(point[0]), int(point[1])),
                        8,
                        (0, 255, 255),
                        3,
                    )

        # Sovrappone l'overlay dei puntini verdi se abilitato
        if (
            hasattr(self, "show_green_dots_overlay")
            and self.show_green_dots_overlay
            and hasattr(self, "green_dots_overlay")
            and self.green_dots_overlay is not None
        ):
            # Converte l'immagine OpenCV in PIL per la composizione
            display_pil = Image.fromarray(
                cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
            )

            # Compone l'overlay trasparente con l'immagine
            display_pil = Image.alpha_composite(
                display_pil.convert("RGBA"), self.green_dots_overlay.convert("RGBA")
            )

            # Riconverte in formato OpenCV
            display_image = cv2.cvtColor(
                np.array(display_pil.convert("RGB")), cv2.COLOR_RGB2BGR
            )

        # Disegna gli overlay delle misurazioni
        if (
            hasattr(self, "show_measurement_overlays")
            and self.show_measurement_overlays
        ):
            if hasattr(self, "draw_measurement_overlays"):
                display_image = self.draw_measurement_overlays(display_image)

        # Converte OpenCV image in PIL
        if isinstance(display_image, np.ndarray):
            # Converte BGR to RGB se necessario
            if len(display_image.shape) == 3:
                image_rgb = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = display_image
            pil_image = Image.fromarray(image_rgb)
        else:
            pil_image = display_image

        # Imposta l'immagine nel canvas professionale
        self.professional_canvas.set_image(pil_image)

        # Aggiunge i landmark aggiuntivi direttamente sul canvas matplotlib se presenti
        if self.current_landmarks is not None:
            self.draw_landmarks_on_professional_canvas()

        # Aggiunge le misurazioni se presenti
        if (
            hasattr(self, "measurement_overlays")
            and hasattr(self, "show_measurement_overlays")
            and self.show_measurement_overlays
        ):
            self.draw_measurements_on_professional_canvas()

    def draw_landmarks_on_professional_canvas(self):
        """Disegna i landmark sul canvas professionale."""
        if not self.current_landmarks or not hasattr(self, "professional_canvas"):
            return

        ax = self.professional_canvas.ax

        # Disegna i landmark principali
        if not self.show_all_landmarks:
            # Solo landmark principali (come nel sistema originale)
            important_landmarks = [
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
                9,
                10,
                151,
                337,
                299,
                333,
                298,
                301,
                366,
                389,
                356,
                454,
                323,
                361,
                435,
                103,
                67,
                109,
                10,
                151,
                9,
                175,
                136,
                150,
                149,
                176,
                148,
                152,
                377,
                400,
                378,
                379,
                365,
                397,
                288,
                361,
                323,
            ]

            for idx in important_landmarks:
                if idx < len(self.current_landmarks):
                    landmark = self.current_landmarks[idx]
                    # I landmark sono tuple (x, y), non oggetti con proprietà
                    ax.plot(landmark[0], landmark[1], "ro", markersize=2)
        else:
            # Tutti i 468 landmark
            for landmark in self.current_landmarks:
                # I landmark sono tuple (x, y), non oggetti con proprietà
                ax.plot(landmark[0], landmark[1], "bo", markersize=1)

        self.professional_canvas.mpl_canvas.draw()

    def draw_measurements_on_professional_canvas(self):
        """Disegna le misurazioni sul canvas professionale."""
        if not hasattr(self, "professional_canvas") or not hasattr(
            self, "measurement_overlays"
        ):
            return

        ax = self.professional_canvas.ax

        # Disegna gli overlay delle misurazioni
        for overlay in self.measurement_overlays:
            if overlay.get("visible", True):
                measurement_type = overlay.get("type", "line")
                color = overlay.get("color", "red")

                if measurement_type == "line":
                    points = overlay.get("points", [])
                    if len(points) >= 2:
                        x_coords = [p[0] for p in points]
                        y_coords = [p[1] for p in points]
                        ax.plot(x_coords, y_coords, color=color, linewidth=2)

                elif measurement_type == "circle":
                    center = overlay.get("center", (0, 0))
                    radius = overlay.get("radius", 10)
                    circle = plt.Circle(
                        center, radius, color=color, fill=False, linewidth=2
                    )
                    ax.add_patch(circle)

        self.professional_canvas.mpl_canvas.draw()

    def clear_canvas(self):
        """Pulisce il canvas professionale."""
        if hasattr(self, "professional_canvas"):
            self.professional_canvas.clear_canvas()

    def save_image(self):
        """Salva l'immagine corrente con le annotazioni."""
        if not self.current_image is None:
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
                # Salva l'immagine dal canvas professionale
                if hasattr(self, "professional_canvas"):
                    self.professional_canvas.fig.savefig(
                        file_path, dpi=300, bbox_inches="tight"
                    )
                    self.status_bar.config(text=f"Immagine salvata: {file_path}")
                else:
                    # Fallback al metodo originale
                    cv2.imwrite(file_path, self.current_image)

    def export_measurements(self):
        """Esporta le misurazioni in formato JSON."""
        if hasattr(self, "professional_canvas"):
            measurements = self.professional_canvas.export_measurements()

            if measurements:
                file_path = filedialog.asksaveasfilename(
                    title="Esporta Misurazioni",
                    defaultextension=".json",
                    filetypes=[("JSON", "*.json"), ("Tutti i file", "*.*")],
                )

                if file_path:
                    import json

                    with open(file_path, "w") as f:
                        json.dump(measurements, f, indent=2)
                    self.status_bar.config(text=f"Misurazioni esportate: {file_path}")
            else:
                messagebox.showinfo("Info", "Nessuna misurazione da esportare")


def main():
    """Funzione principale per avviare l'applicazione."""
    root = tk.Tk()
    app = CanvasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
