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
        
        # OVERLAY PREVIEW SETTINGS - Defaults attivi per landmarks e simmetria
        self.show_landmarks = True   # Abilitato di default
        self.show_symmetry = True    # Abilitato di default 
        self.show_green_polygon = False

        # Tracciamento sorgente video per timestamp
        self.is_video_file = False  # True per file video, False per webcam
        self.analysis_start_time = None  # Tempo di inizio per webcam

        # Controlli player video
        self.is_paused = False  # Stato di pausa
        self.playback_speed = 1.0  # Velocità di riproduzione (1.0 = normale)
        self.current_position_ms = 0  # Posizione corrente in ms
        self.total_duration_ms = 0  # Durata totale del video in ms
        self.fps = 30  # Frame rate del video

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

    def set_overlay_options(self, landmarks=False, symmetry=False, green_polygon=False):
        """Imposta le opzioni di overlay per l'anteprima."""
        self.show_landmarks = landmarks
        self.show_symmetry = symmetry
        self.show_green_polygon = green_polygon

    def set_scoring_config(self, scoring_config):
        """Imposta la configurazione dei pesi per lo scoring."""
        self.scoring_config = scoring_config

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

    def start_webcam(self, camera_index: int = 0) -> bool:
        """Avvia la webcam."""
        if self.start_camera_capture(camera_index):
            self.is_paused = False
            return self.start_live_analysis()
        return False
        
    def pause_webcam(self):
        """Mette in pausa la webcam."""
        if not self.is_video_file and self.is_capturing:
            self.is_paused = True
            print("📹 Webcam in pausa")
            
    def resume_webcam(self):
        """Riprende la webcam dalla pausa."""
        if not self.is_video_file and self.is_capturing:
            self.is_paused = False
            print("📹 Webcam ripresa")
            
    def stop_webcam(self):
        """Ferma completamente la webcam."""
        if not self.is_video_file:
            self.stop()
            
    def restart_webcam(self, camera_index: int = 0) -> bool:
        """Riavvia la webcam da zero."""
        self.stop_webcam()
        return self.start_webcam(camera_index)

    def play_pause(self) -> bool:
        """
        Toggle play/pause per il video.
        Returns: True se ora è in play, False se in pausa
        """
        if not self.is_video_file:
            # Per webcam - Play/Pause gestisce solo la pausa del flusso
            if self.is_capturing:
                self.is_paused = not self.is_paused
                print(f"📹 Webcam {'in pausa' if self.is_paused else 'ripresa'}")
                return not self.is_paused
            else:
                print("❌ Webcam non attiva - usa 'Avvia Webcam' per iniziare")
                return False

        # Per file video
        if not self.is_capturing:
            # Video finito o mai avviato - riavvia l'analisi
            print("🔄 Video finito, riavvio analisi...")
            if self.start_live_analysis():
                self.is_paused = False
                return True
            else:
                return False
        else:
            # Video in corso - toggle pausa
            self.is_paused = not self.is_paused
            print(f"🎬 Video {'in pausa' if self.is_paused else 'in riproduzione'}")
            return not self.is_paused

    def stop(self):
        """Ferma il video/webcam."""
        if not self.is_video_file:
            # Per webcam - Stop spegne completamente la webcam
            if self.is_capturing:
                self.is_capturing = False

            if self.capture and self.capture.isOpened():
                self.capture.release()
                self.capture = None

            self.is_paused = True
            print("📹 Webcam spenta")
        else:
            # Per file video - Stop riporta all'inizio
            if self.is_capturing:
                self.is_capturing = False

            if self.capture and self.capture.isOpened():
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.current_position_ms = 0

            self.is_paused = True
            print("⏹️ Video fermato e riportato all'inizio")

    def seek_to_time(self, time_ms: float):
        """
        Sposta la posizione del video al tempo specificato.
        Args:
            time_ms: Tempo in millisecondi
        """
        if not self.is_video_file or not self.capture or not self.capture.isOpened():
            return False

        # Limita ai bounds del video
        time_ms = max(0, min(time_ms, self.total_duration_ms))

        # Converte in frame number
        frame_number = int((time_ms / 1000.0) * self.fps)
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        self.current_position_ms = time_ms

        return True

    def set_playback_speed(self, speed: float):
        """
        Imposta la velocità di riproduzione.
        Args:
            speed: Velocità (0.5 = metà, 1.0 = normale, 2.0 = doppia)
        """
        self.playback_speed = max(0.1, min(speed, 5.0))

    def get_current_time_ms(self) -> float:
        """Restituisce la posizione corrente in millisecondi."""
        if self.is_video_file and self.capture and self.capture.isOpened():
            return self.capture.get(cv2.CAP_PROP_POS_MSEC)
        return 0

    def get_duration_ms(self) -> float:
        """Restituisce la durata totale in millisecondi."""
        return self.total_duration_ms

    def get_fps(self) -> float:
        """Restituisce il frame rate del video."""
        return self.fps

    def is_video_playing(self) -> bool:
        """Restituisce True se il video sta riproducendo."""
        return self.is_capturing and not self.is_paused

    # =============== FINE CONTROLLI PLAYER ===============

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

                        self.is_video_file = False  # Impostato come webcam
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
                    self.is_video_file = True  # Impostato come file video

                    # Inizializza proprietà video
                    self.fps = self.capture.get(cv2.CAP_PROP_FPS) or 30
                    total_frames = self.capture.get(cv2.CAP_PROP_FRAME_COUNT)
                    self.total_duration_ms = (
                        (total_frames / self.fps) * 1000 if total_frames > 0 else 0
                    )
                    self.current_position_ms = 0
                    self.is_paused = False

                    print(
                        f"📊 Video info: FPS={self.fps:.1f}, Durata={self.total_duration_ms/1000:.1f}s"
                    )
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

    def apply_preview_overlays(self, frame: np.ndarray) -> np.ndarray:
        """Applica overlay estetici al frame per l'anteprima (non influenza calcoli)."""
        overlay_frame = frame.copy()
        
        # Solo se ci sono overlay attivi
        if not (self.show_landmarks or self.show_symmetry or self.show_green_polygon):
            return overlay_frame
            
        # Rileva landmarks per gli overlay
        landmarks = self.face_detector.detect_face_landmarks(frame)
        if landmarks is None:
            return overlay_frame
            
        # Overlay landmarks
        if self.show_landmarks and landmarks:
            overlay_frame = self.face_detector.draw_landmarks(
                overlay_frame, landmarks, draw_all=True
            )
            
        # Overlay asse di simmetria
        if self.show_symmetry and landmarks:
            overlay_frame = self.face_detector.draw_symmetry_axis(
                overlay_frame, landmarks
            )
            
        # Overlay poligono punti verdi
        if self.show_green_polygon and landmarks:
            overlay_frame = self._draw_green_polygon_overlay(overlay_frame)
            
        return overlay_frame
        
    def _draw_green_polygon_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Disegna overlay poligono punti verdi se presenti."""
        try:
            from src.green_dots_processor import GreenDotsProcessor
            
            # Crea processor temporaneo per rilevamento
            processor = GreenDotsProcessor()
            
            # Converte frame in formato PIL per il rilevamento
            from PIL import Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            
            # Rileva punti verdi
            detection_results = processor.detect_green_dots(pil_image)
            if detection_results["total_dots"] < 3:
                return frame
                
            # Dividi punti in sinistro/destro
            image_width = frame.shape[1]
            left_dots, right_dots = processor.divide_dots_by_vertical_center(
                detection_results["dots"], image_width
            )
            
            # Disegna poligoni se ci sono abbastanza punti
            if len(left_dots) >= 3:
                points_left = [(int(p["x"]), int(p["y"])) for p in left_dots]
                cv2.polylines(frame, [np.array(points_left)], True, (0, 255, 0), 2)
                cv2.fillPoly(frame, [np.array(points_left)], (0, 255, 0, 50))
                
            if len(right_dots) >= 3:
                points_right = [(int(p["x"]), int(p["y"])) for p in right_dots]
                cv2.polylines(frame, [np.array(points_right)], True, (255, 0, 0), 2)
                cv2.fillPoly(frame, [np.array(points_right)], (255, 0, 0, 50))
                
        except Exception as e:
            print(f"Errore overlay poligono verde: {e}")
            
        return frame
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

        # Inizializza il tempo di start per webcam
        if not self.is_video_file:
            self.analysis_start_time = time.time()

        print("🎯 ANALYSIS_LOOP: Avvio analisi semplificata per frame frontale...")

        while self.is_capturing:
            # Gestione pausa
            if self.is_paused:
                time.sleep(0.1)  # Attesa durante la pausa
                continue

            ret, frame = self.capture.read()
            if not ret:
                print(
                    f"🎯 ANALYSIS_LOOP: Fine video raggiunta dopo {frames_processed} frame"
                )
                break

            self.current_frame = frame.copy()
            current_time = time.time()
            frames_processed += 1

            # Aggiorna posizione corrente per file video
            if self.is_video_file:
                self.current_position_ms = self.get_current_time_ms()

            # AGGIORNA ANTEPRIMA ogni 100ms con overlay
            if (
                self.preview_callback
                and (current_time - last_preview) >= preview_interval
            ):
                preview_frame = self.apply_preview_overlays(frame.copy())
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
                            # Calcola il timestamp appropriato
                            if self.is_video_file:
                                # Per file video: usa la posizione nel video
                                video_time_ms = self.capture.get(cv2.CAP_PROP_POS_MSEC)
                                video_time_seconds = video_time_ms / 1000.0
                            else:
                                # Per webcam: usa il tempo trascorso dall'inizio dell'analisi
                                video_time_seconds = (
                                    current_time - self.analysis_start_time
                                )

                            self.debug_callback(
                                video_time_seconds,
                                frames_processed,  # Numero del frame per l'ultima colonna
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

            # Controllo velocità di riproduzione
            if self.is_video_file and self.playback_speed != 1.0:
                # Calcola delay basato sulla velocità
                frame_delay = (1.0 / self.fps) / self.playback_speed
                time.sleep(
                    max(0.01, frame_delay - 0.01)
                )  # Sottrae il tempo di processing base
            else:
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
