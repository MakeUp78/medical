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
from src.utils import resize_image_keep_aspect


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

        # Finestra anteprima video (ora integrata)
        self.preview_window = None  # Mantenuto per compatibilità, ma non usato
        self.preview_label = None  # Ora usato per l'anteprima integrata
        self.preview_enabled = None  # Inizializzato in setup_integrated_preview
        self.setup_gui()

        # Callback per il video analyzer
        self.video_analyzer.set_frame_callback(self.on_video_frame_update)
        self.video_analyzer.set_preview_callback(self.on_video_preview_update)
        self.video_analyzer.set_completion_callback(self.on_analysis_completion)

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
            0, weight=0, minsize=350
        )  # Controlli (larghezza fissa)
        self.root.grid_columnconfigure(1, weight=1, minsize=600)  # Canvas (espandibile)
        self.root.grid_columnconfigure(
            2, weight=0, minsize=400
        )  # Anteprima (larghezza fissa)

        # Setup area controlli (sinistra) con larghezza fissa
        control_main_frame = ttk.Frame(self.root, width=350)
        control_main_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=5)
        control_main_frame.grid_propagate(
            False
        )  # Impedisce ridimensionamento automatico
        control_main_frame.grid_rowconfigure(0, weight=1)
        control_main_frame.grid_columnconfigure(0, weight=1)

        # Canvas scrollabile per i controlli
        control_canvas = tk.Canvas(control_main_frame, highlightthickness=0, width=330)
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

        # Setup area anteprima integrata (destra) con larghezza fissa
        preview_frame = ttk.LabelFrame(
            self.root, text="Anteprima Video", padding=10, width=400
        )
        preview_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 5), pady=5)
        preview_frame.grid_propagate(False)  # Impedisce ridimensionamento automatico
        preview_frame.grid_rowconfigure(0, weight=0, minsize=40)  # Controlli
        preview_frame.grid_rowconfigure(1, weight=1, minsize=300)  # Video
        preview_frame.grid_rowconfigure(2, weight=0, minsize=60)  # Info
        preview_frame.grid_columnconfigure(0, weight=1)
        self.setup_integrated_preview(preview_frame)

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

        # Info frame migliore
        self.best_frame_info = ttk.Label(video_frame, text="Nessun frame analizzato")
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

    def setup_canvas(self, parent):
        """Configura il canvas per la visualizzazione."""
        # Canvas con scrollbar
        self.canvas = tk.Canvas(parent, bg="white", cursor="cross")

        h_scroll = ttk.Scrollbar(
            parent, orient=tk.HORIZONTAL, command=self.canvas.xview
        )
        v_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        # Grid layout per il canvas
        self.canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        # Eventi canvas
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<MouseWheel>", self.on_canvas_zoom)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)

    def setup_integrated_preview(self, parent):
        """Configura l'area anteprima integrata con layout stabile."""
        # Frame controlli anteprima con altezza fissa
        controls_frame = ttk.Frame(parent, height=40)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        controls_frame.grid_propagate(False)  # Mantiene altezza fissa

        # Checkbox per attivare/disattivare anteprima
        self.preview_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls_frame,
            text="Anteprima Attiva",
            variable=self.preview_enabled,
            command=self.toggle_video_preview,
        ).pack(side=tk.LEFT, pady=8)

        # Pulsante per catturare frame corrente
        ttk.Button(
            controls_frame,
            text="📸 Cattura",
            command=self.capture_current_frame,
        ).pack(side=tk.RIGHT, pady=8)

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
        """Carica e analizza un file video."""
        file_path = filedialog.askopenfilename(
            title="Seleziona Video",
            filetypes=[
                ("Video", "*.mp4 *.avi *.mov *.mkv *.wmv"),
                ("Tutti i file", "*.*"),
            ],
        )

        if file_path:
            if self.video_analyzer.load_video_file(file_path):
                self.status_bar.config(text="Avviando analisi video...")
                self.root.update()

                # Reset del miglior score per nuova analisi
                self.current_best_score = 0.0

                # Avvia l'analisi live che userà l'anteprima integrata
                if self.video_analyzer.start_live_analysis():
                    self.best_frame_info.config(text="Analizzando video file...")
                    self.status_bar.config(text=f"Analisi video avviata: {file_path}")
                else:
                    messagebox.showerror(
                        "Errore", "Impossibile avviare l'analisi video"
                    )
                    self.status_bar.config(text="Errore nell'analisi video")
            else:
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
        if self.video_analyzer.start_camera_capture():
            print("Webcam avviata con successo, iniziando analisi...")

            # Reset del miglior score per nuova analisi
            self.current_best_score = 0.0

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
            self.set_current_image(best_frame, best_landmarks)
            self.best_frame_info.config(text=f"Miglior frame: Score {best_score:.2f}")
            self.status_bar.config(text="Analisi completata - Frame migliore caricato")
        else:
            self.status_bar.config(text="Nessun frame valido trovato")

    def on_video_frame_update(self, frame: np.ndarray, score: float):
        """Callback per aggiornamento frame in tempo reale."""
        # Aggiorna info in tempo reale
        self.root.after(
            0, lambda: self.best_frame_info.config(text=f"Score attuale: {score:.2f}")
        )

        # Logica per aggiornamento automatico del canvas
        current_best_score = getattr(self, "current_best_score", 0.0)

        # Aggiorna il canvas se:
        # 1. Score > 0.7 E non abbiamo ancora un frame, OPPURE
        # 2. Score > current_best_score (sempre meglio)
        should_update = (score > 0.7 and self.current_image is None) or (
            score > current_best_score and score > 0.3
        )  # Soglia minima 0.3

        if should_update:
            # Ottieni i landmark del frame corrente
            landmarks = self.face_detector.detect_face_landmarks(frame)
            if landmarks is not None:
                # Aggiorna nel thread principale
                self.root.after(
                    0,
                    lambda: self.update_canvas_with_new_frame(frame, landmarks, score),
                )
                self.current_best_score = score

        # Aggiorna info anteprima se presente
        if self.preview_info:
            status_text = f"🎯 Score frontalità: {score:.2f}"
            if score > 0.7:
                status_text += " - Ottimo! 🟢"
            elif score > 0.5:
                status_text += " - Buono 🟡"
            else:
                status_text += " - Migliora posizione 🔴"
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
        """Callback chiamato quando l'analisi video termina automaticamente."""

        def handle_completion():
            # Carica il frame migliore
            best_frame, best_landmarks, best_score = (
                self.video_analyzer.get_best_frame_data()
            )

            if best_frame is not None:
                self.set_current_image(best_frame, best_landmarks)
                self.best_frame_info.config(
                    text=f"Miglior frame: Score {best_score:.2f} (Auto-completato)"
                )
                self.status_bar.config(text="Analisi completata automaticamente")
            else:
                self.status_bar.config(
                    text="Analisi completata - Nessun volto rilevato"
                )

            # Chiudi la finestra di anteprima
            self.close_preview_window()

        # Esegui nel thread principale
        self.root.after(0, handle_completion)

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
        self, image: np.ndarray, landmarks: Optional[List[Tuple[float, float]]] = None
    ):
        """Imposta l'immagine corrente nel canvas."""
        self.current_image = image.copy()
        self.current_landmarks = landmarks

        if landmarks is None:
            # Rileva automaticamente i landmark
            self.detect_landmarks()

        self.update_canvas_display()

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
            
            if results['success']:
                # Salva l'overlay generato
                self.green_dots_overlay = results['overlay']
                
                # Abilita automaticamente la visualizzazione dell'overlay
                self.show_green_dots_overlay = True
                self.green_dots_var.set(True)
                
                # Aggiorna la visualizzazione del canvas
                self.refresh_canvas_only()
                
                # Aggiunge misurazioni alla tabella
                left_stats = results['statistics']['left']
                right_stats = results['statistics']['right']
                combined_stats = results['statistics']['combined']
                
                # Aggiunge le statistiche delle aree sopraccigliare
                self.add_measurement(
                    "Area Sopracciglio Sx", 
                    f"{left_stats['area']:.1f}", 
                    "px²"
                )
                self.add_measurement(
                    "Area Sopracciglio Dx", 
                    f"{right_stats['area']:.1f}", 
                    "px²"
                )
                self.add_measurement(
                    "Perimetro Sopracciglio Sx", 
                    f"{left_stats['perimeter']:.1f}", 
                    "px"
                )
                self.add_measurement(
                    "Perimetro Sopracciglio Dx", 
                    f"{right_stats['perimeter']:.1f}", 
                    "px"
                )
                self.add_measurement(
                    "Differenza Aree Sopraccigli", 
                    f"{abs(left_stats['area'] - right_stats['area']):.1f}", 
                    "px²"
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
                self.status_bar.config(text=f"Puntini verdi rilevati: {results['detection_results']['total_dots']}")
                
            else:
                # Errore nel rilevamento
                error_msg = results.get('error', 'Errore sconosciuto nel rilevamento')
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
                "Nessun overlay disponibile. Esegui prima il rilevamento dei puntini verdi."
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
            display_pil = Image.fromarray(cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB))
            
            # Compone l'overlay trasparente con l'immagine
            display_pil = Image.alpha_composite(
                display_pil.convert('RGBA'), 
                self.green_dots_overlay.convert('RGBA')
            )
            
            # Riconverte in formato OpenCV
            display_image = cv2.cvtColor(np.array(display_pil.convert('RGB')), cv2.COLOR_RGB2BGR)

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

        # Aggiorna canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.canvas_image)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def update_canvas_display(self):
        """Aggiorna la visualizzazione del canvas."""
        if self.current_image is None:
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

        # Disegna le selezioni correnti
        for i, point in enumerate(self.selected_points):
            cv2.circle(display_image, point, 5, (255, 0, 255), -1)

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
            display_pil = Image.fromarray(cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB))
            
            # Compone l'overlay trasparente con l'immagine
            display_pil = Image.alpha_composite(
                display_pil.convert('RGBA'), 
                self.green_dots_overlay.convert('RGBA')
            )
            
            # Riconverte in formato OpenCV
            display_image = cv2.cvtColor(np.array(display_pil.convert('RGB')), cv2.COLOR_RGB2BGR)

        # Disegna gli overlay delle misurazioni
        if self.show_measurement_overlays:
            display_image = self.draw_measurement_overlays(display_image)

        # Ridimensiona per il canvas mantenendo le proporzioni
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width > 1 and canvas_height > 1:
            # Calcola il fattore di scala prima del ridimensionamento
            original_height, original_width = self.current_image.shape[:2]

            # Calcola il fattore di scala
            scale_w = canvas_width / original_width
            scale_h = canvas_height / original_height
            self.display_scale = min(scale_w, scale_h)

            # Ridimensiona l'immagine
            display_image = resize_image_keep_aspect(
                display_image, canvas_width, canvas_height
            )

            # Salva le dimensioni dell'immagine visualizzata
            self.display_size = display_image.shape[:2][::-1]  # (width, height)
        else:
            self.display_scale = 1.0
            self.display_size = display_image.shape[:2][::-1]

        # Converte per Tkinter
        display_image_rgb = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(display_image_rgb)
        self.canvas_image = ImageTk.PhotoImage(pil_image)

        # Aggiorna canvas
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.canvas_image)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

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
            self.set_current_image(current_frame, landmarks)

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


def main():
    """Funzione principale per avviare l'applicazione."""
    root = tk.Tk()
    app = CanvasApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
