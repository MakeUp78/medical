"""
Sistema di configurazione per il layout dell'interfaccia.
Gestisce salvataggio e ripristino delle dimensioni dei pannelli.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class LayoutConfig:
    """Configurazione del layout dell'interfaccia."""

    # Dimensioni finestra principale
    window_width: int = 1600
    window_height: int = 1000
    window_x: int = 100
    window_y: int = 100

    # Divisori PanedWindow - valori ottimizzati per massima visibilità
    main_paned_position: int = (
        480  # Divisore sinistra (controlli | canvas) - AUMENTATO per contenere controlli
    )
    right_column_position: int = (
        800  # Divisore destro (canvas | colonna destra) - RIDOTTO per mantenere visibilità
    )
    sidebar_paned_position: int = (
        300  # Divisore sidebar destro (layers | anteprima) - aumentato
    )
    vertical_paned_position: int = (
        800  # Divisore verticale (principale | misurazioni) - bilanciato
    )

    # NUOVO: Divisore interno colonna destra (layers | anteprima)
    layers_preview_divider_position: int = (
        250  # Posizione divisore tra layers e anteprima video
    )

    # Dimensioni pannelli specifici
    layers_panel_height: int = 300
    toolbar_height: int = 40
    status_bar_height: int = 30
    measurements_height: int = 200  # Altezza ridotta area misurazioni

    # Configurazioni specifiche canvas
    right_panel_width: int = 420

    # Configurazioni specifiche pannello destro
    right_sidebar_width: int = 420  # Larghezza totale colonna destra
    layers_frame_height: int = 300  # Altezza sezione layers
    preview_frame_height: int = 250  # Altezza sezione anteprima video

    # Configurazioni Treeview
    layers_tree_column_0: int = 280
    layers_tree_column_visible: int = 50
    layers_tree_column_locked: int = 50


class LayoutManager:
    """Gestisce la configurazione e persistenza del layout."""

    def __init__(self, config_file: str = "layout_config.json"):
        self.config_file = Path(config_file)
        self.config = LayoutConfig()
        self.load_config()

    def load_config(self) -> None:
        """Carica la configurazione da file."""
        if self.config_file.exists():
            try:
                print(f"🔄 Caricando configurazione layout da {self.config_file}")

                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                print(f"📖 Dati letti dal file:")
                print(
                    f"   • Finestra: {data.get('window_width', 'N/A')}x{data.get('window_height', 'N/A')}+{data.get('window_x', 'N/A')}+{data.get('window_y', 'N/A')}"
                )
                print(
                    f"   • Pannelli: main={data.get('main_paned_position', 'N/A')}, sidebar={data.get('sidebar_paned_position', 'N/A')}, vertical={data.get('vertical_paned_position', 'N/A')}"
                )

                # Aggiorna la configurazione con i dati salvati
                for key, value in data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)

                print(f"✅ Configurazione layout caricata con successo")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"⚠️ Errore caricamento configurazione: {e}, usando default")
                self.config = LayoutConfig()
        else:
            print(
                f"📁 File {self.config_file} non trovato, usando configurazione default"
            )
            self.config = LayoutConfig()

    def save_config(self) -> None:
        """Salva la configurazione su file."""
        try:
            # Crea la directory se non esiste
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # Log dei valori che stiamo per salvare
            config_dict = asdict(self.config)
            print(f"💾 Salvando layout_config.json con:")
            print(
                f"   • Finestra: {self.config.window_width}x{self.config.window_height}+{self.config.window_x}+{self.config.window_y}"
            )
            print(
                f"   • Pannelli: main={self.config.main_paned_position}, sidebar={self.config.sidebar_paned_position}, vertical={self.config.vertical_paned_position}"
            )

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            print(f"✅ Configurazione layout salvata in {self.config_file}")

            # Verifica immediata che il file sia stato scritto
            if self.config_file.exists():
                file_size = self.config_file.stat().st_size
                print(f"   • File creato con successo: {file_size} bytes")
            else:
                print("❌ ERRORE: File non trovato dopo il salvataggio!")

        except Exception as e:
            print(f"❌ Errore salvataggio configurazione: {e}")
            import traceback

            traceback.print_exc()

    def update_window_geometry(self, width: int, height: int, x: int, y: int) -> None:
        """Aggiorna le dimensioni e posizione della finestra."""
        self.config.window_width = width
        self.config.window_height = height
        self.config.window_x = x
        self.config.window_y = y

    def update_paned_positions(
        self, main_pos: Optional[int] = None, sidebar_pos: Optional[int] = None
    ) -> None:
        """Aggiorna le posizioni dei divisori."""
        if main_pos is not None:
            self.config.main_paned_position = main_pos
        if sidebar_pos is not None:
            self.config.sidebar_paned_position = sidebar_pos

    def update_panel_dimensions(self, **kwargs) -> None:
        """Aggiorna le dimensioni dei pannelli."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def get_window_geometry(self) -> str:
        """Restituisce la geometria della finestra in formato tkinter."""
        return f"{self.config.window_width}x{self.config.window_height}+{self.config.window_x}+{self.config.window_y}"

    def save_window_geometry(self, geometry_string: str) -> None:
        """Salva la geometria della finestra dal formato tkinter (WIDTHxHEIGHT+X+Y)."""
        try:
            # Parse del formato "1600x1000+100+50"
            size_part, pos_part = geometry_string.split("+", 1)
            width_str, height_str = size_part.split("x")

            # Se ci sono due '+' significa che ci sono coordinate negative
            if pos_part.count("+") == 1:
                x_str, y_str = pos_part.split("+")
            else:
                # Gestisce coordinate negative come "100+-50"
                parts = pos_part.split("+")
                x_str = parts[0] if not parts[0].startswith("-") else parts[0]
                y_str = parts[1] if len(parts) > 1 else "100"

            # Aggiorna configurazione
            self.config.window_width = int(width_str)
            self.config.window_height = int(height_str)
            self.config.window_x = int(x_str)
            self.config.window_y = int(y_str)

            # Salva immediatamente
            self.save_config()

        except Exception as e:
            print(f"Errore parsing geometria '{geometry_string}': {e}")

    def validate_and_test_config(self) -> bool:
        """Valida la configurazione corrente e testa il salvataggio/caricamento."""
        try:
            print("\n🔧 Test validazione configurazione layout:")

            # Salva stato corrente
            original_config = LayoutConfig(
                window_width=self.config.window_width,
                window_height=self.config.window_height,
                window_x=self.config.window_x,
                window_y=self.config.window_y,
                main_paned_position=self.config.main_paned_position,
                sidebar_paned_position=self.config.sidebar_paned_position,
                vertical_paned_position=self.config.vertical_paned_position,
            )

            # Test 1: Salvataggio
            print("1️⃣ Test salvataggio...")
            self.save_config()

            # Test 2: Verifica file esistente
            if not self.config_file.exists():
                print("❌ ERRORE: File non creato dopo salvataggio")
                return False
            print("✅ File salvato correttamente")

            # Test 3: Caricamento
            print("2️⃣ Test caricamento...")
            temp_config = self.config
            self.config = LayoutConfig()  # Reset a default
            self.load_config()

            # Test 4: Verifica dati
            print("3️⃣ Verifica integrità dati...")
            if (
                self.config.window_width == original_config.window_width
                and self.config.window_height == original_config.window_height
                and self.config.main_paned_position
                == original_config.main_paned_position
            ):
                print("✅ Dati ripristinati correttamente")
                return True
            else:
                print("❌ ERRORE: Dati non corrispondenti dopo caricamento")
                print(
                    f"   Originale: {original_config.window_width}x{original_config.window_height}, main={original_config.main_paned_position}"
                )
                print(
                    f"   Caricato: {self.config.window_width}x{self.config.window_height}, main={self.config.main_paned_position}"
                )
                return False

        except Exception as e:
            print(f"❌ Errore nel test configurazione: {e}")
            import traceback

            traceback.print_exc()
            return False

    def get_config_status(self) -> dict:
        """Restituisce lo stato attuale della configurazione per debug."""
        return {
            "config_file": str(self.config_file),
            "file_exists": self.config_file.exists(),
            "file_size": (
                self.config_file.stat().st_size if self.config_file.exists() else 0
            ),
            "window_geometry": f"{self.config.window_width}x{self.config.window_height}+{self.config.window_x}+{self.config.window_y}",
            "paned_positions": {
                "main": self.config.main_paned_position,
                "sidebar": self.config.sidebar_paned_position,
                "vertical": self.config.vertical_paned_position,
            },
        }


# Istanza globale del layout manager
layout_manager = LayoutManager()
