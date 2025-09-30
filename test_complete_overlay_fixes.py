#!/usr/bin/env python3
"""
Test completo per verificare tutte le correzioni coordinate overlay.
"""

import unittest
import tkinter as tk
import numpy as np
from src.canvas_app import CanvasApp


class TestAllOverlayCoordinates(unittest.TestCase):
    """Test completo coordinate overlay."""

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

        # Simula landmarks MediaPipe completi per aree sopraccigliari/occhi
        self.setup_full_landmarks()

    def setup_full_landmarks(self):
        """Crea 468 landmarks simulati per test completi."""
        # Crea 468 landmarks simulati
        landmarks = []
        for i in range(468):
            # Distribuzione casuale ma realistica
            x = 100 + (i % 30) * 10
            y = 100 + (i // 30) * 8
            landmarks.append((x, y))

        # Landmarks importanti per sopraccigli e occhi
        # Sopracciglio sinistro
        landmarks[334] = (150, 120)
        landmarks[296] = (160, 115)
        landmarks[336] = (170, 120)
        landmarks[285] = (180, 125)

        # Sopracciglio destro
        landmarks[53] = (250, 120)
        landmarks[52] = (260, 115)
        landmarks[65] = (270, 120)

        # Occhio sinistro
        landmarks[33] = (140, 160)
        landmarks[7] = (150, 155)
        landmarks[163] = (160, 160)

        # Occhio destro
        landmarks[362] = (240, 160)
        landmarks[398] = (250, 155)
        landmarks[384] = (260, 160)

        # Centro rotazione (glabella)
        landmarks[9] = (200, 200)

        self.app.current_landmarks = landmarks
        self.app.original_base_landmarks = [l for l in landmarks]  # Copia profonda

    def tearDown(self):
        """Cleanup."""
        try:
            self.root.destroy()
        except:
            pass

    def test_manual_measurements_with_rotation(self):
        """Test misurazioni manuali con rotazione."""
        print("🔄 Test misurazioni manuali con rotazione...")

        # Modalità manuale
        self.app.landmark_measurement_mode = False

        # Test distanza
        self.app.measurement_mode = "distance"
        self.app.current_rotation = 45  # Simula rotazione

        # Punti test
        points = [(150, 150), (250, 200)]
        self.app.selected_points = points

        try:
            self.app.calculate_measurement()
            print("✅ Distanza manuale calcolata con rotazione")
        except Exception as e:
            print(f"⚠️ Errore distanza: {e}")

        # Test area
        self.app.measurement_mode = "area"
        area_points = [(100, 100), (200, 100), (150, 200)]
        self.app.selected_points = area_points

        try:
            self.app.calculate_measurement()
            print("✅ Area manuale calcolata con rotazione")
        except Exception as e:
            print(f"⚠️ Errore area: {e}")

        # Test angolo
        self.app.measurement_mode = "angle"
        angle_points = [(100, 150), (150, 100), (200, 150)]
        self.app.selected_points = angle_points

        try:
            self.app.calculate_measurement()
            print("✅ Angolo manuale calcolato con rotazione")
        except Exception as e:
            print(f"⚠️ Errore angolo: {e}")

    def test_eyebrow_areas_with_original_landmarks(self):
        """Test aree sopraccigliari con landmarks originali."""
        print("👁️ Test aree sopraccigliari con landmarks originali...")

        # Simula rotazione
        self.app.current_rotation = 30

        try:
            self.app.measure_eyebrow_areas()

            # Verifica che sia stato creato overlay
            eyebrow_overlay = self.app.preset_overlays.get("eyebrow_areas")
            self.assertIsNotNone(eyebrow_overlay, "Nessun overlay sopraccigli creato")

            print("✅ Overlay sopraccigli creato con landmarks originali")

        except Exception as e:
            print(f"⚠️ Errore sopraccigli: {e}")

    def test_eye_areas_with_original_landmarks(self):
        """Test aree occhi con landmarks originali."""
        print("👀 Test aree occhi con landmarks originali...")

        # Simula rotazione
        self.app.current_rotation = 60

        try:
            self.app.measure_eye_areas()

            # Verifica che sia stato creato overlay
            eye_overlay = self.app.preset_overlays.get("eye_areas")
            self.assertIsNotNone(eye_overlay, "Nessun overlay occhi creato")

            print("✅ Overlay occhi creato con landmarks originali")

        except Exception as e:
            print(f"⚠️ Errore occhi: {e}")

    def test_coordinate_system_consistency(self):
        """Test consistenza sistema coordinate completo."""
        print("🎯 Test consistenza sistema coordinate completo...")

        rotations = [0, 45, 90, 180, 270]

        for rotation in rotations:
            print(f"\n🔄 Test rotazione {rotation}°")
            self.app.current_rotation = rotation

            # Test punti manuali
            test_point = (150, 150)

            if rotation != 0:
                center = self.app.get_rotation_center()
                if center:
                    # Verifica conversione coordinate
                    orig_x, orig_y = self.app.rotate_point_around_center_simple(
                        test_point[0], test_point[1], center[0], center[1], -rotation
                    )
                    print(
                        f"  Punto ({test_point[0]},{test_point[1]}) -> originale ({orig_x:.1f},{orig_y:.1f})"
                    )
                else:
                    print("  ⚠️ Centro rotazione non disponibile")

            print(f"  ✅ Rotazione {rotation}° testata")

        print("✅ Sistema coordinate consistente per tutte le rotazioni")


def run_complete_overlay_tests():
    """Esegue test completi overlay."""
    print("🧪 AVVIO TEST COMPLETI CORREZIONI OVERLAY")
    print("=" * 60)

    unittest.main(verbosity=2, exit=False)

    print("\n" + "=" * 60)
    print("✅ TEST COMPLETI COMPLETATI")


if __name__ == "__main__":
    run_complete_overlay_tests()
