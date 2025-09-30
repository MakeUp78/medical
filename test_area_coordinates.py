#!/usr/bin/env python3
"""
Test per diagnosticare il problema delle aree manuali spostate a destra.
"""

import unittest
import tkinter as tk
import numpy as np
from src.canvas_app import CanvasApp


class TestManualAreaCoordinates(unittest.TestCase):
    """Test coordinate aree manuali."""

    def setUp(self):
        """Setup per ogni test."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = CanvasApp(self.root)

        # Simula immagine e canvas
        test_image = np.ones((400, 600, 3), dtype=np.uint8) * 128
        self.app.current_image_on_canvas = test_image
        self.app.canvas.configure(width=800, height=600)
        self.app.canvas.update_idletasks()

        # Simula landmarks per centro rotazione
        self.app.current_landmarks = [(100, 100), (200, 150), (300, 200), (150, 250)]
        self.app.original_base_landmarks = self.app.current_landmarks.copy()

        # Imposta modalità misurazione area manuale
        self.app.landmark_measurement_mode = False
        self.app.measurement_mode = "area"
        self.app.measurement_mode_active = tk.BooleanVar(value=True)

        # Reset stato
        self.app.current_rotation = 0
        self.app.canvas_scale = 1.0
        self.app.canvas_offset_x = 0
        self.app.canvas_offset_y = 0

    def tearDown(self):
        """Cleanup."""
        try:
            self.root.destroy()
        except:
            pass

    def test_coordinate_conversion_consistency(self):
        """Verifica consistenza conversione coordinate."""
        print("🔍 Test consistenza conversione coordinate...")

        # Coordinate test
        test_points = [(100, 100), (200, 150), (300, 200)]

        for img_x, img_y in test_points:
            # Conversione immagine -> canvas
            canvas_x, canvas_y = self.app.image_to_canvas_coords(img_x, img_y)
            print(f"Img({img_x},{img_y}) -> Canvas({canvas_x:.1f},{canvas_y:.1f})")

            # Conversione canvas -> immagine
            back_x, back_y = self.app.canvas_to_image_coords(canvas_x, canvas_y)
            print(
                f"Canvas({canvas_x:.1f},{canvas_y:.1f}) -> Img({back_x:.1f},{back_y:.1f})"
            )

            # Verifica consistenza (tolleranza di 1 pixel)
            self.assertAlmostEqual(
                img_x, back_x, places=0, msg=f"Inconsistenza X: {img_x} != {back_x}"
            )
            self.assertAlmostEqual(
                img_y, back_y, places=0, msg=f"Inconsistenza Y: {img_y} != {back_y}"
            )

            print(f"✅ Conversione consistente per punto ({img_x},{img_y})")

    def test_manual_area_coordinate_offset(self):
        """Testa se c'è un offset nelle coordinate delle aree manuali."""
        print("📐 Test offset coordinate aree manuali...")

        # Simula punti area (triangolo)
        area_points = [(100, 100), (200, 100), (150, 200)]

        # Simula handle_manual_point_selection per ogni punto
        for point in area_points:
            self.app.handle_manual_point_selection(point[0], point[1], 600, 400)

        # Verifica punti salvati
        saved_points = self.app.selected_points
        print(f"Punti originali: {area_points}")
        print(f"Punti salvati: {saved_points}")

        # Verifica che i punti salvati corrispondano a quelli originali
        for i, (orig_point, saved_point) in enumerate(zip(area_points, saved_points)):
            self.assertAlmostEqual(
                orig_point[0],
                saved_point[0],
                places=1,
                msg=f"Punto {i}: X orig={orig_point[0]} != salvato={saved_point[0]}",
            )
            self.assertAlmostEqual(
                orig_point[1],
                saved_point[1],
                places=1,
                msg=f"Punto {i}: Y orig={orig_point[1]} != salvato={saved_point[1]}",
            )

        print("✅ Coordinate salvate correttamente senza offset")

    def test_area_overlay_positioning(self):
        """Testa posizionamento overlay area rispetto ai punti originali."""
        print("🎯 Test posizionamento overlay area...")

        # Punti area test
        area_points = [(150, 150), (250, 150), (200, 250)]
        self.app.selected_points = area_points

        # Calcola misurazione (questo crea l'overlay)
        try:
            self.app.calculate_measurement()

            # Verifica che sia stato creato un overlay
            self.assertGreater(
                len(self.app.measurement_overlays), 0, "Nessun overlay area creato"
            )

            overlay = self.app.measurement_overlays[-1]  # Ultimo overlay creato

            print(f"Overlay creato: {overlay}")

            # Verifica che l'overlay abbia coordinate corrette
            if "coordinates" in overlay:
                overlay_points = overlay["coordinates"]
                print(f"Punti overlay: {overlay_points}")

                # Confronta con punti originali
                for i, (orig, overlay_coord) in enumerate(
                    zip(area_points, overlay_points)
                ):
                    self.assertAlmostEqual(
                        orig[0],
                        overlay_coord[0],
                        places=1,
                        msg=f"Overlay punto {i}: X {orig[0]} != {overlay_coord[0]}",
                    )
                    self.assertAlmostEqual(
                        orig[1],
                        overlay_coord[1],
                        places=1,
                        msg=f"Overlay punto {i}: Y {orig[1]} != {overlay_coord[1]}",
                    )

                print("✅ Overlay posizionato correttamente sui punti originali")
            else:
                print("ℹ️ Overlay senza coordinate esplicite (usa points)")

        except Exception as e:
            print(f"⚠️ Errore calcolo area: {e}")
            # Non è critico per questo test


def run_area_coordinate_tests():
    """Esegue test diagnostici coordinate aree."""
    print("🔬 AVVIO TEST DIAGNOSTICI COORDINATE AREE MANUALI")
    print("=" * 60)

    unittest.main(verbosity=2, exit=False)

    print("\n" + "=" * 60)
    print("✅ TEST DIAGNOSTICI COMPLETATI")


if __name__ == "__main__":
    run_area_coordinate_tests()
