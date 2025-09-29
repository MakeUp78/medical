"""
Configuration system for facial analysis application.
Provides centralized, user-configurable parameters for analysis.
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, fields


@dataclass
class AnalysisSettings:
    """Impostazioni per l'analisi dei frame."""

    # Rilevamento volti
    min_face_size: int = 100
    detection_confidence: float = 0.5
    tracking_confidence: float = 0.5

    # Intervalli temporali (secondi)
    analysis_interval: float = 0.1  # Frequenza analisi camera live
    preview_interval: float = 0.033  # ~30 FPS per preview

    # Scoring e aggiornamento canvas
    canvas_update_threshold: float = 0.3  # Score minimo per aggiornare canvas
    canvas_update_improvement: float = 0.05  # Miglioramento minimo richiesto
    excellent_score_threshold: float = 0.8  # Score considerato "eccellente"
    good_score_threshold: float = 0.6  # Score considerato "buono"

    # Orientamento testa - toleranze (gradi)
    pitch_tolerance: float = 15.0  # ±15° su/giù
    yaw_tolerance: float = 10.0  # ±10° sinistra/destra
    roll_tolerance: float = 8.0  # ±8° inclinazione

    # Pesi per calcolo score combinato
    pitch_weight: float = 0.3
    yaw_weight: float = 0.5  # Più importante per frontalità
    roll_weight: float = 0.2

    # Video processing
    max_video_duration_warning: float = 120.0  # Avviso dopo 2 minuti
    progress_update_interval: int = 100  # Aggiorna progress ogni N frame
    long_video_frame_skip: int = 2  # Skip frame per video molto lunghi

    # Threading e performance
    queue_maxsize: int = 10
    timeout_queue_get: float = 0.1
    cpu_pause_analysis: float = 0.005  # Pausa per evitare sovraccarico CPU (ms)
    cpu_pause_preview: float = 0.01


@dataclass
class UISettings:
    """Impostazioni per l'interfaccia utente."""

    # Finestra principale
    window_width: int = 1200
    window_height: int = 800

    # Canvas
    canvas_width: int = 800
    canvas_height: int = 600
    canvas_bg_color: str = "#f0f0f0"

    # Anteprima
    preview_width: int = 390
    preview_height: int = 290
    preview_update_fps: int = 30

    # Colori e stili
    accent_color: str = "#2196F3"
    success_color: str = "#4CAF50"
    warning_color: str = "#FF9800"
    error_color: str = "#F44336"

    # Messaggi
    show_orientation_details: bool = True
    show_score_indicators: bool = True
    auto_update_canvas: bool = True


@dataclass
class ApplicationConfig:
    """Configurazione completa dell'applicazione."""

    analysis: AnalysisSettings
    ui: UISettings

    # Paths
    config_file: str = "config.json"
    log_file: str = "facial_analysis.log"

    # Debug
    debug_mode: bool = False
    verbose_logging: bool = False


class ConfigManager:
    """Gestisce caricamento e salvataggio configurazione."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> ApplicationConfig:
        """Carica configurazione da file o crea default."""

        # Configurazione di default
        default_config = ApplicationConfig(analysis=AnalysisSettings(), ui=UISettings())

        if not os.path.exists(self.config_path):
            print(f"File configurazione non trovato, creo {self.config_path}")
            self.save_config(default_config)
            return default_config

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Crea configurazione da dati JSON
            analysis_data = data.get("analysis", {})
            ui_data = data.get("ui", {})

            # Aggiorna solo i campi presenti nel JSON (preserva nuovi campi default)
            analysis = AnalysisSettings()
            for field in fields(analysis):
                if field.name in analysis_data:
                    setattr(analysis, field.name, analysis_data[field.name])

            ui = UISettings()
            for field in fields(ui):
                if field.name in ui_data:
                    setattr(ui, field.name, ui_data[field.name])

            config = ApplicationConfig(analysis=analysis, ui=ui)

            # Aggiorna altri campi top-level
            for key, value in data.items():
                if key not in ["analysis", "ui"] and hasattr(config, key):
                    setattr(config, key, value)

            print(f"Configurazione caricata da {self.config_path}")
            return config

        except Exception as e:
            print(f"Errore nel caricamento configurazione: {e}")
            print("Uso configurazione di default")
            return default_config

    def save_config(self, config: ApplicationConfig):
        """Salva configurazione su file."""
        try:
            data = {
                "analysis": asdict(config.analysis),
                "ui": asdict(config.ui),
                "config_file": config.config_file,
                "log_file": config.log_file,
                "debug_mode": config.debug_mode,
                "verbose_logging": config.verbose_logging,
            }

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"Configurazione salvata in {self.config_path}")

        except Exception as e:
            print(f"Errore nel salvataggio configurazione: {e}")

    # def get_analysis_config(self):
    #     """Restituisce configurazione per VideoAnalyzer."""
    #     from src.video_analyzer import AnalysisConfig
    #
    #     return AnalysisConfig(
    #         min_face_size=self.config.analysis.min_face_size,
    #         analysis_interval=self.config.analysis.analysis_interval,
    #         preview_interval=self.config.analysis.preview_interval,
    #         canvas_update_threshold=self.config.analysis.canvas_update_threshold,
    #         canvas_update_improvement=self.config.analysis.canvas_update_improvement,
    #         max_video_duration_warning=self.config.analysis.max_video_duration_warning,
    #         progress_update_interval=self.config.analysis.progress_update_interval,
    #         queue_maxsize=self.config.analysis.queue_maxsize,
    #         timeout_queue_get=self.config.analysis.timeout_queue_get,
    #     )

    def update_setting(self, category: str, setting: str, value: Any):
        """Aggiorna una singola impostazione."""
        try:
            if category == "analysis":
                setattr(self.config.analysis, setting, value)
            elif category == "ui":
                setattr(self.config.ui, setting, value)
            else:
                setattr(self.config, setting, value)

            self.save_config(self.config)
            print(f"Impostazione aggiornata: {category}.{setting} = {value}")

        except Exception as e:
            print(f"Errore nell'aggiornamento impostazione: {e}")

    def reset_to_defaults(self):
        """Reset configurazione ai valori di default."""
        self.config = ApplicationConfig(analysis=AnalysisSettings(), ui=UISettings())
        self.save_config(self.config)
        print("Configurazione ripristinata ai valori di default")

    def get_score_description(self, score: float) -> tuple[str, str]:
        """
        Restituisce descrizione e colore per un dato score.

        Returns:
            Tupla (descrizione, colore_hex)
        """
        if score >= self.config.analysis.excellent_score_threshold:
            return "Eccellente! 🟢", self.config.ui.success_color
        elif score >= self.config.analysis.good_score_threshold:
            return "Buono 🟡", self.config.ui.warning_color
        elif score >= self.config.analysis.canvas_update_threshold:
            return "Sufficiente 🟠", self.config.ui.warning_color
        else:
            return "Migliora posizione 🔴", self.config.ui.error_color

    def export_config(self, export_path: str):
        """Esporta configurazione in un file specificato."""
        try:
            import shutil

            shutil.copy2(self.config_path, export_path)
            print(f"Configurazione esportata in {export_path}")
        except Exception as e:
            print(f"Errore nell'esportazione: {e}")

    def import_config(self, import_path: str):
        """Importa configurazione da un file specificato."""
        try:
            import shutil

            backup_path = f"{self.config_path}.backup"

            # Backup configurazione corrente
            if os.path.exists(self.config_path):
                shutil.copy2(self.config_path, backup_path)

            # Importa nuova configurazione
            shutil.copy2(import_path, self.config_path)
            self.config = self.load_config()

            print(f"Configurazione importata da {import_path}")
            print(f"Backup precedente salvato in {backup_path}")

        except Exception as e:
            print(f"Errore nell'importazione: {e}")


# Istanza globale per accesso facilitato
config_manager = ConfigManager()
