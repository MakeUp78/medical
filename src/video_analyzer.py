"""
Video analysis module for capturing and analyzing video streams to find the best frontal face frame.
"""

import cv2
import numpy as np
import threading
import time
from typing import Optional, Tuple, List, Callable
from src.face_detector import FaceDetector


class VideoAnalyzer:
    def __init__(self):
        """Inizializza l'analizzatore video."""
        self.face_detector = FaceDetector()
        self.capture = None
        self.is_capturing = False
        self.best_frame = None
        self.best_landmarks = None
        self.best_score = 0.0
        self.current_frame = None
        self.frame_callback = None
        self.preview_callback = None  # Callback per l'anteprima video
        self.completion_callback = None  # Callback per notificare la fine dell'analisi
        self.debug_callback = None  # Callback per debug logs

        # Contatori per frame processing
        self.frame_counter = 0  # Contatore totale frame processati
        self.best_frame_number = 0  # Numero del miglior frame

        # Parametri di analisi
        self.min_face_size = 100  # Dimensione minima del volto in pixel
        self.analysis_interval = 0.1  # Intervallo di analisi in secondi
        self.capture_duration = None  # RIMOSSO LIMITE DI DURATA
        self.preview_interval = 0.033  # ~30 FPS per l'anteprima

    def set_frame_callback(self, callback: Callable[[np.ndarray, float], None]):
        """Imposta la callback per i frame in tempo reale."""
        self.frame_callback = callback

    def set_preview_callback(self, callback: Callable[[np.ndarray], None]):
        """Imposta la callback per l'anteprima video in tempo reale."""
        self.preview_callback = callback

    def set_completion_callback(self, callback: Callable[[], None]):
        """Imposta la callback per notificare il completamento dell'analisi."""
        self.completion_callback = callback

    def set_debug_callback(self, callback: Callable[[str, dict], None]):
        """Imposta la callback per i debug logs."""
        self.debug_callback = callback

    def start_camera_capture(self, camera_index: int = 0) -> bool:
        """
        Avvia la cattura dalla webcam.

        Args:
            camera_index: Indice della webcam (0 per default)

        Returns:
            True se la cattura è stata avviata con successo
        """
        # Prova diversi indici di camera
        camera_indices = [0, 1, 2] if camera_index == 0 else [camera_index]

        for idx in camera_indices:
            try:
                print(f"Tentativo di connessione alla camera {idx}...")
                self.capture = cv2.VideoCapture(idx)

                # Aspetta un momento per l'inizializzazione
                import time

                time.sleep(1)

                if self.capture.isOpened():
                    # Testa se riesce a leggere un frame
                    ret, test_frame = self.capture.read()
                    if ret and test_frame is not None:
                        print(f"Camera {idx} funziona correttamente")

                        # Configura la risoluzione
                        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        self.capture.set(cv2.CAP_PROP_FPS, 30)

                        return True
                    else:
                        print(f"Camera {idx} aperta ma non legge frame")
                        self.capture.release()
                else:
                    print(f"Impossibile aprire camera {idx}")

            except Exception as e:
                print(f"Errore con camera {idx}: {e}")
                if self.capture:
                    self.capture.release()

        print("Nessuna camera funzionante trovata")
        return False

    def load_video_file(self, video_path: str) -> bool:
        """
        Carica un file video.

        Args:
            video_path: Percorso del file video

        Returns:
            True se il file è stato caricato con successo
        """
        try:
            self.capture = cv2.VideoCapture(video_path)
            return self.capture.isOpened()
        except Exception as e:
            print(f"Errore nel caricamento del video: {e}")
            return False

    def analyze_frame(
        self, frame: np.ndarray
    ) -> Tuple[Optional[List[Tuple[float, float]]], float]:
        """
        Analizza un singolo frame per rilevare volti e calcolare il punteggio di frontalità.

        Args:
            frame: Frame da analizzare

        Returns:
            Tupla (landmarks, frontal_score) o (None, 0.0) se nessun volto rilevato
        """
        landmarks = self.face_detector.detect_face_landmarks(frame)

        if landmarks is None:
            return None, 0.0

        # Verifica dimensione minima del volto usando landmark diretti
        # Landmark 33: occhio sinistro esterno, Landmark 362: occhio destro esterno
        if len(landmarks) > 362:
            left_eye_outer = landmarks[33]
            right_eye_outer = landmarks[362]
            face_width = abs(left_eye_outer[0] - right_eye_outer[0])
            if face_width < self.min_face_size:
                return None, 0.0

        # Calcola punteggio di frontalità
        frontal_score = self.face_detector.calculate_frontal_score(landmarks)

        return landmarks, frontal_score

    def start_live_analysis(self) -> bool:
        """
        Avvia l'analisi live del video per trovare il frame migliore.

        Returns:
            True se l'analisi è stata avviata con successo
        """
        if self.capture is None or not self.capture.isOpened():
            return False

        self.is_capturing = True
        self.best_frame = None
        self.best_landmarks = None
        self.best_score = 0.0
        self.frame_counter = 0  # Reset contatore frame
        self.best_frame_number = 0  # Reset numero miglior frame

        # Avvia il thread di analisi
        analysis_thread = threading.Thread(target=self._analysis_loop)
        analysis_thread.daemon = True
        analysis_thread.start()

        return True

    def _analysis_loop(self):
        """Loop principale di analisi video."""
        start_time = time.time()
        last_analysis = 0
        last_preview = 0

        # MODALITÀ ILLIMITATA: rimosso limite di durata
        while self.is_capturing:
            ret, frame = self.capture.read()
            if not ret:
                break

            self.frame_counter += 1  # Incrementa contatore frame
            self.current_frame = frame.copy()
            current_time = time.time()

            # Aggiorna l'anteprima più frequentemente
            if (
                self.preview_callback
                and current_time - last_preview >= self.preview_interval
            ):
                preview_frame = frame.copy()
                last_preview = current_time
                # Chiama la callback per l'anteprima
                self.preview_callback(preview_frame)

            # Analizza solo a intervalli regolari per ottimizzare le performance
            if current_time - last_analysis >= self.analysis_interval:
                landmarks, frontal_score = self.analyze_frame(frame)

                # Aggiorna il migliore frame se necessario
                if landmarks is not None and frontal_score > self.best_score:
                    self.best_frame = frame.copy()
                    self.best_landmarks = landmarks
                    self.best_score = frontal_score
                    self.best_frame_number = self.frame_counter  # Salva numero frame

                    # Debug callback per il nuovo miglior frame
                    if self.debug_callback:
                        try:
                            from src.utils import get_advanced_orientation_score

                            image_size = (frame.shape[1], frame.shape[0])
                            _, debug_data = get_advanced_orientation_score(
                                landmarks, image_size
                            )

                            # Calcola il timestamp relativo dall'inizio dell'analisi
                            elapsed = current_time - start_time

                            # Prepara i dati per il debug log
                            debug_info = {
                                "timestamp": f"{elapsed:.1f}s",
                                "score": f"{frontal_score:.3f}",
                                "yaw": f"{debug_data.get('yaw', 0):.1f}°",
                                "pitch": f"{debug_data.get('pitch', 0):.1f}°",
                                "roll": f"{debug_data.get('roll', 0):.1f}°",
                                "debug": debug_data.get(
                                    "debug", {}
                                ),  # Passa tutto il debug data
                                "description": f"#{self.frame_counter}",  # Numero del frame
                            }

                            self.debug_callback("Miglior frame aggiornato", debug_info)

                        except Exception as e:
                            # Fallback se il debug dettagliato fallisce
                            elapsed = current_time - start_time
                            debug_info = {
                                "timestamp": f"{elapsed:.1f}s",
                                "score": f"{frontal_score:.3f}",
                                "yaw": "N/A",
                                "pitch": "N/A",
                                "roll": "N/A",
                                "debug": {"symmetry_score": 0.0},
                                "description": f"#{self.frame_counter}",
                            }
                            self.debug_callback("Nuovo miglior frame", debug_info)

                # Chiama la callback per l'aggiornamento dell'interfaccia
                if self.frame_callback:
                    annotated_frame = frame.copy()
                    if landmarks:
                        annotated_frame = self.face_detector.draw_landmarks(
                            annotated_frame, landmarks, key_only=True
                        )
                    self.frame_callback(annotated_frame, frontal_score)

                last_analysis = current_time

            # Breve pausa per evitare sovraccarico CPU
            time.sleep(0.01)

        # L'analisi è terminata (timeout o interruzione manuale)
        self.is_capturing = False
        if self.completion_callback:
            self.completion_callback()

    def stop_analysis(self):
        """Ferma l'analisi video."""
        self.is_capturing = False

    def get_best_frame_data(
        self,
    ) -> Tuple[Optional[np.ndarray], Optional[List[Tuple[float, float]]], float]:
        """
        Restituisce i dati del frame migliore trovato.

        Returns:
            Tupla (frame, landmarks, score)
        """
        return self.best_frame, self.best_landmarks, self.best_score

    def analyze_video_file(
        self, max_frames: int = 300
    ) -> Tuple[Optional[np.ndarray], Optional[List[Tuple[float, float]]], float]:
        """
        Analizza un intero file video per trovare il frame migliore.

        Args:
            max_frames: Numero massimo di frame da analizzare

        Returns:
            Tupla (best_frame, best_landmarks, best_score)
        """
        if self.capture is None or not self.capture.isOpened():
            return None, None, 0.0

        best_frame = None
        best_landmarks = None
        best_score = 0.0
        frame_count = 0

        # Ottieni il numero totale di frame
        total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_step = (
            max(1, total_frames // max_frames) if total_frames > max_frames else 1
        )

        while True:
            ret, frame = self.capture.read()
            if not ret:
                break

            # Invia il frame all'anteprima se il callback è disponibile
            if self.preview_callback:
                self.preview_callback(frame.copy())

            # Analizza solo ogni N frame per ottimizzare
            if frame_count % frame_step == 0:
                landmarks, frontal_score = self.analyze_frame(frame)

                if landmarks is not None and frontal_score > best_score:
                    best_frame = frame.copy()
                    best_landmarks = landmarks
                    best_score = frontal_score

                # Aggiorna il callback di frame se disponibile
                if self.frame_callback:
                    annotated_frame = frame.copy()
                    if landmarks:
                        annotated_frame = self.face_detector.draw_landmarks(
                            annotated_frame, landmarks, key_only=True
                        )
                    self.frame_callback(annotated_frame, frontal_score)

            frame_count += 1

            # Breve pausa per permettere l'aggiornamento dell'interfaccia
            import time

            time.sleep(0.01)  # 10ms di pausa

            if frame_count >= max_frames * frame_step:
                break

        self.best_frame = best_frame
        self.best_landmarks = best_landmarks
        self.best_score = best_score

        return best_frame, best_landmarks, best_score

    def release(self):
        """Rilascia le risorse video."""
        self.stop_analysis()
        if self.capture is not None:
            self.capture.release()
            self.capture = None
