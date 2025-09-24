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
        """Inizializza l'analizzatore video SEMPLIFICATO per massima efficacia."""
        self.face_detector = FaceDetector()
        self.capture = None
        self.is_capturing = False
        self.best_frame = None
        self.best_landmarks = None
        self.best_score = 0.0
        self.current_frame = None
        self.scoring_config = None  # Sarà impostato tramite set_scoring_config

        # CALLBACK ESSENZIALI
        self.completion_callback = None  # Solo per notificare la fine
        self.preview_callback = None  # RIPRISTINATO: Per anteprima video
        self.frame_callback = None  # NUOVO: Per aggiornare canvas principale
        self.debug_callback = None  # NUOVO: Per inviare dati alla tabella debug GUI

        # Parametri di analisi ottimizzati per trovare il miglior frame frontale
        self.min_face_size = 100  # Dimensione minima del volto in pixel
        self.analysis_interval = 0.05  # Analizza ogni 50ms per più precisione
        self.min_score_threshold = (
            0.1  # MOLTO BASSO: Accetta quasi tutti per testare nuovo algoritmo
        )

    def set_completion_callback(self, callback: Callable[[], None]):
        """Imposta la callback per notificare il completamento dell'analisi."""
        self.completion_callback = callback

    def set_preview_callback(self, callback: Callable[[np.ndarray], None]):
        """Imposta la callback per l'anteprima video in tempo reale."""
        self.preview_callback = callback

    def set_frame_callback(self, callback: Callable[[np.ndarray, list, float], None]):
        """Imposta la callback per aggiornare il canvas principale con frame migliori."""
        self.frame_callback = callback

    def set_debug_callback(
        self, callback: Callable[[int, float, dict, np.ndarray], None]
    ):
        """Imposta la callback per inviare dati debug alla tabella GUI."""
        self.debug_callback = callback

    def set_scoring_config(self, scoring_config):
        """Imposta la configurazione dei pesi per lo scoring."""
        self.scoring_config = scoring_config

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
        Carica un file video con logging dettagliato per debug.
        """
        try:
            print(f"📹 VIDEO_ANALYZER: Tentativo caricamento {video_path}")
            self.capture = cv2.VideoCapture(video_path)

            if self.capture.isOpened():
                # Verifica che il video sia effettivamente leggibile
                ret, test_frame = self.capture.read()
                if ret:
                    print(
                        f"✅ VIDEO_ANALYZER: Video caricato correttamente, primo frame letto"
                    )
                    # Riporta al frame 0
                    self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    return True
                else:
                    print(
                        f"❌ VIDEO_ANALYZER: Video aperto ma impossibile leggere frame"
                    )
                    return False
            else:
                print(f"❌ VIDEO_ANALYZER: Impossibile aprire il video")
                return False
        except Exception as e:
            print(f"❌ VIDEO_ANALYZER: Errore nel caricamento del video: {e}")
            return False

    def analyze_frame(
        self, frame: np.ndarray
    ) -> Tuple[Optional[List[Tuple[float, float]]], float]:
        """
        Analizza un singolo frame per rilevare volti e calcolare il punteggio di frontalità.
        SEMPLIFICATO per massima efficacia nel trovare frame frontali.
        """
        # Rileva landmark 2D standard
        landmarks = self.face_detector.detect_face_landmarks(frame)

        if landmarks is None:
            return None, 0.0

        # Verifica dimensione minima del volto
        if len(landmarks) > 362:
            left_eye_outer = landmarks[33]
            right_eye_outer = landmarks[362]
            face_width = abs(left_eye_outer[0] - right_eye_outer[0])
            if face_width < self.min_face_size:
                return None, 0.0

        # Calcola punteggio di frontalità usando l'algoritmo puro
        frontal_score = self.face_detector.calculate_frontal_score(
            landmarks, config=self.scoring_config
        )

        # Solo frame con un minimo di qualità frontale
        if frontal_score < self.min_score_threshold:
            return None, 0.0

        return landmarks, frontal_score

    def start_live_analysis(self) -> bool:
        """
        Avvia l'analisi live del video per trovare il frame migliore.
        SEMPLIFICATO per massima efficacia.
        """
        if self.capture is None or not self.capture.isOpened():
            return False

        self.is_capturing = True
        self.best_frame = None
        self.best_landmarks = None
        self.best_score = 0.0

        # Avvia il thread di analisi semplificato
        analysis_thread = threading.Thread(target=self._simple_analysis_loop)
        analysis_thread.daemon = True
        analysis_thread.start()

        return True

    def _simple_analysis_loop(self):
        """
        Loop semplificato di analisi video con anteprima e logging dettagliato.
        FOCUS: Trova il frame più frontale possibile + mostra anteprima.
        """
        last_analysis = 0
        last_preview = 0
        frames_processed = 0
        frames_analyzed = 0
        preview_interval = 0.1  # Aggiorna anteprima ogni 100ms

        print("🎯 ANALYSIS_LOOP: Avvio analisi semplificata per frame frontale...")

        while self.is_capturing:
            ret, frame = self.capture.read()
            if not ret:
                print(
                    f"🎯 ANALYSIS_LOOP: Fine video raggiunta dopo {frames_processed} frame"
                )
                break

            self.current_frame = frame.copy()
            current_time = time.time()
            frames_processed += 1

            # AGGIORNA ANTEPRIMA ogni 100ms
            if (
                self.preview_callback
                and (current_time - last_preview) >= preview_interval
            ):
                preview_frame = frame.copy()
                self.preview_callback(preview_frame)
                last_preview = current_time

            # Log ogni 100 frame per vedere il progresso
            if frames_processed % 100 == 0:
                print(
                    f"🎯 ANALYSIS_LOOP: Processati {frames_processed} frame, analizzati {frames_analyzed}"
                )

            # Analizza solo a intervalli per ottimizzare le performance
            if current_time - last_analysis >= self.analysis_interval:
                frames_analyzed += 1
                landmarks, frontal_score = self.analyze_frame(frame)

                if landmarks is not None:
                    # *** INVIO DATI ALLA TABELLA GUI (SOLO SE SCORE ALTO) ***
                    if frontal_score >= 0.3:  # Soglia per mostrare nella tabella debug
                        # Ottieni dati debug dall'algoritmo di utils.py
                        from src.utils import calculate_pure_frontal_score

                        debug_info = getattr(
                            calculate_pure_frontal_score, "_debug_info", {}
                        )

                        # Invia alla tabella GUI
                        if self.debug_callback:
                            self.debug_callback(
                                frames_processed,
                                frontal_score,
                                debug_info,
                                frame.copy(),
                            )

                    # Aggiorna il migliore frame se necessario
                    if frontal_score > self.best_score:
                        self.best_frame = frame.copy()
                        self.best_landmarks = landmarks
                        self.best_score = frontal_score

                        # Solo messaggi essenziali nel terminale
                        print(
                            f"📸 NUOVO MIGLIOR FRAME: Score {frontal_score:.3f} (frame #{frames_processed})"
                        )

                        print(
                            f"📸 NUOVO MIGLIOR FRAME: Score {frontal_score:.3f} (frame #{frames_processed})"
                        )

                        # *** AGGIORNA CANVAS PRINCIPALE CON NUOVO FRAME MIGLIORE ***
                        if self.frame_callback:
                            try:
                                # Mostra immediatamente il nuovo frame migliore nel canvas
                                self.frame_callback(
                                    frame.copy(), landmarks, frontal_score
                                )
                                print(
                                    f"🖼️ CANVAS AGGIORNATO con nuovo miglior frame (score: {frontal_score:.3f})"
                                )
                            except Exception as e:
                                print(f"❌ Errore aggiornamento canvas: {e}")
                        else:
                            print("⚠️ Nessun frame_callback per aggiornare canvas")
                else:
                    # Log solo occasionalmente per frame senza volto
                    if frames_analyzed % 50 == 0:
                        print(
                            f"🎯 ANALYSIS_LOOP: Frame #{frames_processed} - Nessun volto rilevato"
                        )

                last_analysis = current_time

            # Pausa minima per evitare sovraccarico CPU
            time.sleep(0.01)

        # Fine analisi
        self.is_capturing = False
        print(f"✅ ANALYSIS_LOOP: Analisi completata")
        print(f"   - Frame totali processati: {frames_processed}")
        print(f"   - Frame analizzati: {frames_analyzed}")
        print(f"   - Miglior score finale: {self.best_score:.3f}")

        if self.completion_callback:
            print("🎯 ANALYSIS_LOOP: Chiamando completion_callback")
            self.completion_callback()
        else:
            print("⚠️ ANALYSIS_LOOP: Nessun completion_callback impostato")

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
