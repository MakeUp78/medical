# Webapp Backend API (FastAPI) - Versione Semplificata

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from contextlib import asynccontextmanager
import cv2
import numpy as np
import json
import base64
import re
from io import BytesIO
from PIL import Image
import uuid
from datetime import datetime
import tempfile
import os
import sys

# Aggiunge il percorso src per importare green_dots_processor
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import MediaPipe solo quando necessario per evitare conflitti TensorFlow
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: MediaPipe not available: {e}")
    MEDIAPIPE_AVAILABLE = False

# Import del modulo green_dots_processor
try:
    from green_dots_processor import GreenDotsProcessor
    GREEN_DOTS_AVAILABLE = True
    print("✅ GreenDotsProcessor importato con successo")
except ImportError as e:
    print(f"❌ Warning: GreenDotsProcessor not available: {e}")
    GREEN_DOTS_AVAILABLE = False

# Import Voice Assistant
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
try:
    from voice.voice_assistant import IsabellaVoiceAssistant
    VOICE_ASSISTANT_AVAILABLE = True
    print("✅ IsabellaVoiceAssistant importato con successo")
except ImportError as e:
    print(f"❌ Warning: IsabellaVoiceAssistant not available: {e}")
    VOICE_ASSISTANT_AVAILABLE = False

# Import DeepFace for age estimation (lazy loading to avoid conflicts)
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    print("✅ DeepFace importato con successo")
except ImportError as e:
    print(f"❌ Warning: DeepFace not available: {e}")
    DEEPFACE_AVAILABLE = False

# === INIZIALIZZAZIONE MEDIAPIPE ===

mp_face_mesh = None
face_mesh = None

# === INIZIALIZZAZIONE VOICE ASSISTANT ===
voice_assistant = None

# === AGE ESTIMATION CONFIGURATION ===
# Default confidence level for age estimation when actual confidence is not available
AGE_ESTIMATION_DEFAULT_CONFIDENCE = 0.85
# DeepFace detector backend: opencv, ssd, dlib, mtcnn, retinaface, mediapipe
AGE_ESTIMATION_DETECTOR_BACKEND = os.getenv('AGE_DETECTOR_BACKEND', 'opencv')

def initialize_mediapipe():
    global mp_face_mesh, face_mesh
    if not MEDIAPIPE_AVAILABLE:
        return False
    
    try:
        mp_face_mesh = mp.solutions.face_mesh
        face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        return True
    except Exception as e:
        print(f"Error initializing MediaPipe: {e}")
        return False

def initialize_voice_assistant():
    global voice_assistant
    if not VOICE_ASSISTANT_AVAILABLE:
        print("⚠️ Voice Assistant non disponibile")
        return False
    
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'voice', 'voice_config.json')
        voice_assistant = IsabellaVoiceAssistant(config_path=config_path)
        print("✅ Voice Assistant inizializzato")
        return True
    except Exception as e:
        print(f"❌ Errore inizializzazione Voice Assistant: {e}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestisce startup e shutdown dell'applicazione."""
    # Startup
    print("🚀 Avvio inizializzazione...", flush=True)
    success = initialize_mediapipe()
    if success:
        print("✅ MediaPipe inizializzato con successo", flush=True)
    else:
        print("❌ ERRORE: MediaPipe non disponibile - API NON FUNZIONERÀ", flush=True)
        raise RuntimeError("MediaPipe è OBBLIGATORIO - nessun fallback consentito")
    
    # Inizializza Voice Assistant (opzionale)
    print("🔍 Inizializzazione Voice Assistant...", flush=True)
    voice_success = initialize_voice_assistant()
    if voice_success:
        print("🎤 Voice Assistant disponibile", flush=True)
    else:
        print("⚠️ Voice Assistant NON inizializzato", flush=True)
    
    yield
    
    # Shutdown
    if voice_assistant and voice_assistant.is_active:
        voice_assistant.stop()
    print("🛑 Shutdown API server")

app = FastAPI(
    title="Medical Facial Analysis API",
    description="API per analisi facciale medica con MediaPipe",
    version="1.0.0",
    lifespan=lifespan
)

# CORS per comunicazione con frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta i file statici della webapp
webapp_dir = os.path.join(os.path.dirname(__file__), '..')
app.mount("/static", StaticFiles(directory=os.path.join(webapp_dir, "static")), name="static")
app.mount("/templates", StaticFiles(directory=os.path.join(webapp_dir, "templates")), name="templates")

print(f"📁 Webapp directory: {webapp_dir}")

# === MODELLI PYDANTIC ===

class ScoringConfig(BaseModel):
    weights: Dict[str, float] = {
        "nose": 0.30,
        "mouth": 0.25,
        "symmetry": 0.25,
        "eye": 0.20
    }
    tolerances: Dict[str, float] = {
        "nose": 0.3,
        "mouth": 0.4,
        "symmetry": 0.7
    }

class AnalysisRequest(BaseModel):
    image: str  # Base64 encoded image
    config: Optional[ScoringConfig] = None

class BatchAnalysisRequest(BaseModel):
    images: List[str]  # List of base64 encoded images
    config: Optional[ScoringConfig] = None

class LandmarkPoint(BaseModel):
    x: float
    y: float
    z: float
    visibility: float

class PoseAngles(BaseModel):
    pitch: float
    yaw: float
    roll: float

class AnalysisResult(BaseModel):
    session_id: str
    landmarks: List[LandmarkPoint]
    score: float
    score_components: Dict[str, float]
    pose_angles: PoseAngles
    frontality_score: float
    image_info: Dict[str, Any]
    timestamp: str

# === MODELLI PYDANTIC PER GREEN DOTS ===

class GreenDotPoint(BaseModel):
    x: int
    y: int
    size: int
    pixels: Optional[List[Dict]] = None

class GreenDotsGroup(BaseModel):
    label: str
    vertices: int
    area: float
    perimeter: float
    center: Dict[str, float]
    points: List[GreenDotPoint]

class GreenDotsDetectionResults(BaseModel):
    dots: List[GreenDotPoint]
    total_dots: int
    total_green_pixels: int
    image_size: Tuple[int, int]
    parameters: Dict[str, Any]

class GreenDotsAnalysisRequest(BaseModel):
    image: str  # Base64 encoded image
    hue_range: Optional[Tuple[int, int]] = (60, 150)
    saturation_min: Optional[int] = 15
    value_range: Optional[Tuple[int, int]] = (15, 95)
    cluster_size_range: Optional[Tuple[int, int]] = (2, 150)
    clustering_radius: Optional[int] = 2

class GreenDotsAnalysisResult(BaseModel):
    success: bool
    session_id: str
    error: Optional[str] = None
    detection_results: Optional[GreenDotsDetectionResults] = None
    groups: Optional[Dict[str, List[GreenDotPoint]]] = None
    coordinates: Optional[Dict[str, List[Tuple[int, int]]]] = None
    statistics: Optional[Dict[str, Any]] = None
    overlay_base64: Optional[str] = None
    image_size: Optional[Tuple[int, int]] = None
    timestamp: str

# === MODELLI PYDANTIC PER VOICE ASSISTANT ===

class VoiceCommand(BaseModel):
    command: str  # Comando vocale da processare

class VoiceSpeakRequest(BaseModel):
    text: str  # Testo da far pronunciare all'assistente

class VoiceStatusResponse(BaseModel):
    available: bool
    is_active: bool
    is_muted: bool
    config: Optional[Dict[str, Any]] = None

class VoiceCommandResponse(BaseModel):
    success: bool
    message: str
    command_recognized: Optional[str] = None
    action_executed: Optional[str] = None

class VoiceMessageRequest(BaseModel):
    message_key: str  # Chiave del messaggio predefinito

class VoiceWelcomeRequest(BaseModel):
    user_name: str  # Nome dell'utente per personalizzare il messaggio

class VoiceKeywordCommand(BaseModel):
    keyword: str  # Parola chiave pronunciata dall'utente
    
class VoiceKeywordResponse(BaseModel):
    success: bool
    keyword: str
    action: Optional[str] = None
    message: Optional[str] = None

# === MODELLI PYDANTIC PER AGE ESTIMATION ===

class AgeEstimationRequest(BaseModel):
    image: str  # Base64 encoded image

class AgeEstimationResult(BaseModel):
    success: bool
    age: Optional[float] = None
    confidence: Optional[float] = None
    error: Optional[str] = None

# === UTILITY FUNCTIONS ===

def decode_base64_image(base64_string: str) -> np.ndarray:
    """Decodifica immagine base64 in array numpy."""
    try:
        # Rimuovi prefisso data URL se presente
        if base64_string.startswith('data:image'):
            base64_string = base64_string.split(',')[1]
        
        # Decodifica base64
        image_data = base64.b64decode(base64_string)
        
        # Converti in PIL Image
        pil_image = Image.open(BytesIO(image_data))
        
        # Converti in RGB se necessario
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Converti in array numpy
        cv_image = np.array(pil_image)
        
        return cv_image
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore decodifica immagine: {str(e)}")

def detect_face_landmarks(image: np.ndarray) -> List[LandmarkPoint]:
    """Rileva landmarks facciali usando MediaPipe."""
    if not MEDIAPIPE_AVAILABLE or face_mesh is None:
        raise HTTPException(status_code=500, detail="MediaPipe non disponibile o non inizializzato")
    
    try:
        # Converti BGR to RGB se necessario
        if len(image.shape) == 3 and image.shape[2] == 3:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb_image = image
        
        # Esegui rilevamento
        results = face_mesh.process(rgb_image)
        
        if not results.multi_face_landmarks:
            return []
        
        # Estrai landmarks del primo volto
        face_landmarks = results.multi_face_landmarks[0]
        
        landmarks = []
        h, w = image.shape[:2]
        
        for landmark in face_landmarks.landmark:
            landmarks.append(LandmarkPoint(
                x=landmark.x * w,
                y=landmark.y * h,
                z=landmark.z,
                visibility=getattr(landmark, 'visibility', 1.0)
            ))
        
        return landmarks
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore rilevamento landmarks: {str(e)}")

def calculate_facial_score(landmarks: List[LandmarkPoint], config: ScoringConfig) -> Dict[str, float]:
    """Calcola score facciale basato sui landmarks."""
    try:
        if len(landmarks) < 468:
            return {"total": 0.0, "nose": 0.0, "mouth": 0.0, "symmetry": 0.0, "eye": 0.0}
        
        # Converti in formato compatibile
        points = [(lm.x, lm.y, lm.z) for lm in landmarks]
        
        # Calcola componenti score
        nose_score = calculate_nose_score(points, config)
        mouth_score = calculate_mouth_score(points, config)
        symmetry_score = calculate_symmetry_score(points, config)
        eye_score = calculate_eye_score(points, config)
        
        # Score pesato
        total_score = (
            nose_score * config.weights["nose"] +
            mouth_score * config.weights["mouth"] +
            symmetry_score * config.weights["symmetry"] +
            eye_score * config.weights["eye"]
        )
        
        return {
            "total": min(1.0, max(0.0, total_score)),
            "nose": nose_score,
            "mouth": mouth_score,
            "symmetry": symmetry_score,
            "eye": eye_score
        }
        
    except Exception as e:
        print(f"Errore calcolo score: {e}")
        return {"total": 0.0, "nose": 0.0, "mouth": 0.0, "symmetry": 0.0, "eye": 0.0}

def calculate_nose_score(points: List[tuple], config: ScoringConfig) -> float:
    """Calcola score del naso."""
    try:
        nose_tip = points[1]      # Punta del naso
        nose_left = points[31]    # Narice sinistra
        nose_right = points[35]   # Narice destra
        
        # Calcola centro del naso
        nose_center_x = (nose_left[0] + nose_right[0]) / 2
        
        # Deviazione dalla linea centrale
        deviation = abs(nose_tip[0] - nose_center_x)
        nose_width = abs(nose_right[0] - nose_left[0])
        
        if nose_width == 0:
            return 0.0
        
        symmetry_ratio = deviation / nose_width
        score = max(0.0, 1.0 - (symmetry_ratio / config.tolerances["nose"]))
        
        return min(1.0, score)
        
    except (IndexError, ZeroDivisionError):
        return 0.0

def calculate_mouth_score(points: List[tuple], config: ScoringConfig) -> float:
    """Calcola score della bocca."""
    try:
        mouth_left = points[61]   # Angolo sinistro
        mouth_right = points[291] # Angolo destro
        mouth_top = points[13]    # Centro superiore
        mouth_bottom = points[14] # Centro inferiore
        
        # Centro bocca
        mouth_center_x = (mouth_left[0] + mouth_right[0]) / 2
        
        # Deviazioni dal centro
        top_deviation = abs(mouth_top[0] - mouth_center_x)
        bottom_deviation = abs(mouth_bottom[0] - mouth_center_x)
        mouth_width = abs(mouth_right[0] - mouth_left[0])
        
        if mouth_width == 0:
            return 0.0
        
        avg_deviation = (top_deviation + bottom_deviation) / 2
        symmetry_ratio = avg_deviation / mouth_width
        
        score = max(0.0, 1.0 - (symmetry_ratio / config.tolerances["mouth"]))
        
        return min(1.0, score)
        
    except (IndexError, ZeroDivisionError):
        return 0.0

def calculate_symmetry_score(points: List[tuple], config: ScoringConfig) -> float:
    """Calcola score di simmetria globale."""
    try:
        left_eye = points[33]     # Occhio sinistro
        right_eye = points[362]   # Occhio destro  
        left_cheek = points[234]  # Guancia sinistra
        right_cheek = points[454] # Guancia destra
        
        # Asse centrale
        face_center_x = (left_eye[0] + right_eye[0]) / 2
        
        # Distanze dall'asse centrale
        left_eye_dist = abs(left_eye[0] - face_center_x)
        right_eye_dist = abs(right_eye[0] - face_center_x)
        left_cheek_dist = abs(left_cheek[0] - face_center_x)
        right_cheek_dist = abs(right_cheek[0] - face_center_x)
        
        # Asimmetria relativa
        eye_asymmetry = abs(left_eye_dist - right_eye_dist) / max(left_eye_dist, right_eye_dist, 0.001)
        cheek_asymmetry = abs(left_cheek_dist - right_cheek_dist) / max(left_cheek_dist, right_cheek_dist, 0.001)
        
        avg_asymmetry = (eye_asymmetry + cheek_asymmetry) / 2
        score = max(0.0, 1.0 - (avg_asymmetry / config.tolerances["symmetry"]))
        
        return min(1.0, score)
        
    except (IndexError, ZeroDivisionError):
        return 0.0

def calculate_eye_score(points: List[tuple], config: ScoringConfig) -> float:
    """Calcola score degli occhi."""
    try:
        left_eye_inner = points[133]  # Interno sinistro
        left_eye_outer = points[33]   # Esterno sinistro
        right_eye_inner = points[362] # Interno destro
        right_eye_outer = points[263] # Esterno destro
        
        # Larghezza occhi
        left_eye_width = abs(left_eye_outer[0] - left_eye_inner[0])
        right_eye_width = abs(right_eye_outer[0] - right_eye_inner[0])
        
        if left_eye_width == 0 or right_eye_width == 0:
            return 0.0
        
        # Simmetria larghezza
        width_ratio = min(left_eye_width, right_eye_width) / max(left_eye_width, right_eye_width)
        
        # Allineamento verticale
        left_eye_y = (left_eye_inner[1] + left_eye_outer[1]) / 2
        right_eye_y = (right_eye_inner[1] + right_eye_outer[1]) / 2
        alignment_diff = abs(left_eye_y - right_eye_y)
        
        eye_distance = abs(right_eye_inner[0] - left_eye_inner[0])
        alignment_ratio = alignment_diff / eye_distance if eye_distance > 0 else 0
        
        alignment_score = max(0.0, 1.0 - (alignment_ratio * 5))
        score = (width_ratio + alignment_score) / 2
        
        return min(1.0, score)
        
    except (IndexError, ZeroDivisionError):
        return 0.0

def calculate_head_pose_angles_enhanced(landmarks: List[LandmarkPoint]) -> Dict[str, float]:
    """
    Calcola gli angoli di posa della testa usando la logica migliorata
    di landmarkPredict_webcam_enhanced.py con MediaPipe landmarks (468 punti).
    """
    try:
        if len(landmarks) < 468:
            return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
        
        # Converti landmarks in coordinate numpy per compatibilità enhanced
        landmark_array = np.array([(lm.x, lm.y) for lm in landmarks])
        
        # Indici MediaPipe Face Mesh corretti (da landmarkPredict_webcam_enhanced.py)
        NOSE_TIP = 4        # Punta del naso (tip of nose)
        CHIN = 152          # Mento (chin)
        LEFT_EYE_CORNER = 33   # Angolo interno occhio sinistro  
        RIGHT_EYE_CORNER = 263 # Angolo interno occhio destro
        LEFT_MOUTH_CORNER = 78  # Angolo sinistro bocca
        RIGHT_MOUTH_CORNER = 308 # Angolo destro bocca
        
        # Verifica che abbiamo abbastanza landmark
        if len(landmark_array) < 468:
            return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
        
        # Punti chiave con indici MediaPipe corretti
        nose_tip = landmark_array[NOSE_TIP]
        chin = landmark_array[CHIN] 
        left_eye = landmark_array[LEFT_EYE_CORNER]
        right_eye = landmark_array[RIGHT_EYE_CORNER]
        left_mouth = landmark_array[LEFT_MOUTH_CORNER]
        right_mouth = landmark_array[RIGHT_MOUTH_CORNER]
        
        # Verifica validità punti
        points_2d = np.array([nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth])
        if np.any(np.isnan(points_2d)):
            return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
        
        # Modello 3D del volto - proporzioni anatomiche realistiche (enhanced)
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Punta del naso (origine)
            (0.0, -330.0, -65.0),        # Mento 
            (-225.0, 170.0, -135.0),     # Angolo interno occhio sinistro
            (225.0, 170.0, -135.0),      # Angolo interno occhio destro  
            (-150.0, -150.0, -125.0),    # Angolo sinistro bocca
            (150.0, -150.0, -125.0)      # Angolo destro bocca
        ], dtype=np.float32)
        
        image_points = np.array([
            nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
        ], dtype=np.float32)
        
        # 🔧 DEBUG: Verifica che le coordinate siano in pixel, non normalizzate
        min_x, max_x = min(landmark_array[:, 0]), max(landmark_array[:, 0])
        min_y, max_y = min(landmark_array[:, 1]), max(landmark_array[:, 1])
        
        print(f"🔍 LANDMARKS RANGE: X=[{min_x:.1f}, {max_x:.1f}] Y=[{min_y:.1f}, {max_y:.1f}]")
        
        # Stima dimensioni immagine dai landmarks (CORRETTA PER ENHANCED)
        img_width = max_x - min_x
        img_height = max_y - min_y
        
        # Se le coordinate sembrano normalizzate (0-1), usa dimensioni standard
        if max_x <= 1.0 and max_y <= 1.0:
            print("⚠️ Le coordinate sembrano normalizzate! Usando dimensioni standard.")
            img_width = 640
            img_height = 480
        else:
            # Aggiungi margine alle dimensioni reali
            img_width = max(640, img_width * 1.2)
            img_height = max(480, img_height * 1.2)
        
        print(f"📐 DIMENSIONI STIMATE: {img_width:.0f}x{img_height:.0f}")
        
        # Parametri camera (enhanced)
        focal_length = img_width
        center = (img_width/2, img_height/2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float32)
        
        dist_coeffs = np.zeros((4,1))
        
        # Risolvi PnP
        success, rotation_vector, translation_vector = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs)
        
        if success:
            # Converti il vettore di rotazione in matrice di rotazione
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            
            # Estrai gli angoli di Eulero (pitch, yaw, roll) - enhanced
            sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
            
            singular = sy < 1e-6
            
            if not singular:
                pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                yaw = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi
                roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2]) * 180.0 / np.pi
            else:
                pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                yaw = 0
                roll = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1]) * 180.0 / np.pi
            
            # Normalizza il Roll per la valutazione (da enhanced.py)
            normalized_roll = roll
            while normalized_roll > 90:
                normalized_roll -= 180
            while normalized_roll < -90:
                normalized_roll += 180
            
            # 🔧 DEBUG: Mostra angoli calcolati
            print(f"🎯 ANGOLI CALCOLATI: Pitch={pitch:.1f}° Yaw={yaw:.1f}° Roll={roll:.1f}° (Norm={normalized_roll:.1f}°)")
            
            clipped_pitch = float(np.clip(pitch, -90, 90))
            clipped_yaw = float(np.clip(yaw, -90, 90))
            clipped_roll = float(np.clip(normalized_roll, -90, 90))
            
            return {
                "pitch": clipped_pitch,
                "yaw": clipped_yaw,
                "roll": clipped_roll
            }
            
    except Exception as e:
        print(f"Errore calcolo pose enhanced: {e}")
    
    return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}

def is_frontal_pose_enhanced(pitch: float, yaw: float, roll: float, strict: bool = False) -> bool:
    """
    Determina se la pose è frontale con soglie normalizzate (da enhanced.py)
    """
    # Normalizza il Roll per la valutazione
    normalized_roll = roll
    while normalized_roll > 90:
        normalized_roll -= 180
    while normalized_roll < -90:
        normalized_roll += 180
    
    if strict:
        # Soglie rigide per pose perfettamente frontale
        return abs(pitch) <= 8 and abs(yaw) <= 8 and abs(normalized_roll) <= 5
    else:
        # Soglie permissive per pose accettabilmente frontale  
        return abs(pitch) <= 25 and abs(yaw) <= 25 and abs(normalized_roll) <= 15

def calculate_head_pose_angles(landmarks: List[LandmarkPoint]) -> Dict[str, float]:
    """
    Calcola gli angoli di posa della testa usando la logica enhanced come default
    """
    return calculate_head_pose_angles_enhanced(landmarks)

def get_pose_status_and_score_enhanced(pitch: float, yaw: float, roll: float) -> tuple:
    """
    Restituisce stato della pose e score con valori normalizzati 
    ESATTAMENTE come in landmarkPredict_webcam_enhanced.py
    """
    # Normalizza il Roll ESATTAMENTE come nel file enhanced
    normalized_roll = roll
    while normalized_roll > 90:
        normalized_roll -= 180
    while normalized_roll < -90:
        normalized_roll += 180
    
    # Usa il Roll normalizzato per il calcolo ESATTAMENTE come enhanced
    max_angle = max(abs(pitch), abs(yaw), abs(normalized_roll))
    
    if max_angle <= 8:
        return "🎯 PERFETTO FRONTALE", 0.95  # Score molto alto per frontale perfetto
    elif max_angle <= 15:
        return "✅ Ottimo frontale", 0.85     # Score alto per ottimo
    elif max_angle <= 25:
        return "👍 Buono frontale", 0.75     # Score buono per accettabile
    elif max_angle <= 40:
        return "⚠️ Accettabile", 0.55        # Score medio per accettabile
    else:
        return "❌ Non frontale", 0.25       # Score basso per non frontale

def calculate_frontality_score_from_landmarks(landmarks_3d, frame_shape) -> float:
    """
    Calcola un punteggio di frontalità basato sui landmarks MediaPipe
    usando ESATTAMENTE la logica di landmarkPredict_webcam_enhanced.py
    """
    try:
        # Converti landmarks in formato LandmarkPoint se necessario
        if hasattr(landmarks_3d, 'landmark'):
            # È un oggetto MediaPipe
            landmark_list = []
            for lm in landmarks_3d.landmark:
                landmark_list.append(LandmarkPoint(
                    x=lm.x * frame_shape[1],
                    y=lm.y * frame_shape[0], 
                    z=lm.z,
                    visibility=getattr(lm, 'visibility', 1.0)
                ))
        else:
            # È già una lista di LandmarkPoint
            landmark_list = landmarks_3d
        
        # Calcola angoli di posa usando la logica enhanced
        pose_angles = calculate_head_pose_angles_enhanced(landmark_list)
        
        # Usa ESATTAMENTE la logica enhanced per determinare la frontalità
        pitch = pose_angles["pitch"]
        yaw = pose_angles["yaw"] 
        roll = pose_angles["roll"]
        
        # 🔧 USA LA FUNZIONE ENHANCED ORIGINALE
        status, score = get_pose_status_and_score_enhanced(pitch, yaw, roll)
        
        # Aggiungi debug per verificare il calcolo
        print(f"🎯 ENHANCED POSE: Pitch={pitch:.1f}° Yaw={yaw:.1f}° Roll={roll:.1f}° → Status='{status}' Score={score:.3f}")
        
        return float(score)
        
        # Aggiungi controlli aggiuntivi per simmetria e qualità landmarks
        if len(landmark_list) >= 468:
            h, w = frame_shape[:2]
            
            # Simmetria occhi (stessi indici usati sopra)
            left_eye = landmark_list[33]
            right_eye = landmark_list[263]
            eye_diff = abs(left_eye.y - right_eye.y)
            eye_distance = abs(left_eye.x - right_eye.x)
            eye_symmetry_bonus = max(0, 1.0 - (eye_diff / max(eye_distance * 0.1, 1))) * 0.1
            
            # Qualità generale landmarks (visibilità media)
            avg_visibility = sum(lm.visibility for lm in landmark_list) / len(landmark_list)
            visibility_bonus = avg_visibility * 0.05
            
            base_score = min(1.0, base_score + eye_symmetry_bonus + visibility_bonus)
        
        return max(0.0, min(1.0, base_score))
        
    except Exception as e:
        print(f"Errore calcolo frontalità: {e}")
        return 0.0

# === UTILITY FUNCTIONS PER GREEN DOTS ===

def convert_numpy_types(obj):
    """
    Converte ricorsivamente tipi NumPy in tipi Python nativi per serializzazione JSON.
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    else:
        return obj

def convert_pil_image_to_base64(pil_image: Image.Image) -> str:
    """Converte un'immagine PIL in stringa base64."""
    try:
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore conversione immagine: {str(e)}")

def decode_base64_to_pil_image(base64_string: str) -> Image.Image:
    """Decodifica stringa base64 in immagine PIL."""
    try:
        # Rimuovi prefisso data URL se presente
        if base64_string.startswith('data:image'):
            base64_string = base64_string.split(',')[1]
        
        # Decodifica base64
        image_data = base64.b64decode(base64_string)
        
        # Converti in PIL Image
        pil_image = Image.open(BytesIO(image_data))
        
        # Converti in RGB se necessario
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        return pil_image
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore decodifica immagine: {str(e)}")

def process_green_dots_analysis(
    image_base64: str,
    hue_range: Tuple[int, int] = (60, 150),
    saturation_min: int = 15,
    value_range: Tuple[int, int] = (15, 95),
    cluster_size_range: Tuple[int, int] = (2, 150),
    clustering_radius: int = 2
) -> Dict:
    """Processa un'immagine per il rilevamento dei green dots."""
    
    if not GREEN_DOTS_AVAILABLE:
        raise HTTPException(
            status_code=500, 
            detail="Modulo GreenDotsProcessor non disponibile. Verificare l'installazione delle dipendenze."
        )
    
    try:
        # Decodifica l'immagine
        pil_image = decode_base64_to_pil_image(image_base64)
        
        # Inizializza il processore con parametri personalizzati
        processor = GreenDotsProcessor(
            hue_range=hue_range,
            saturation_min=saturation_min,
            value_range=value_range,
            cluster_size_range=cluster_size_range,
            clustering_radius=clustering_radius
        )
        
        # Processa l'immagine
        results = processor.process_pil_image(pil_image)
        
        # Converte l'overlay in base64 se disponibile
        if results.get('success') and 'overlay' in results:
            overlay_base64 = convert_pil_image_to_base64(results['overlay'])
            results['overlay_base64'] = overlay_base64
            # Rimuove l'oggetto PIL dall'output JSON
            del results['overlay']
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'analisi green dots: {str(e)}")

# === API ENDPOINTS ===

@app.get("/")
async def root():
    """Serve la webapp index.html"""
    webapp_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
    if os.path.exists(webapp_path):
        return FileResponse(webapp_path)
    return {"message": "Medical Facial Analysis API", "version": "1.0.0", "status": "active"}

@app.get("/index.html")
async def serve_index():
    """Serve la webapp index.html"""
    webapp_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
    if os.path.exists(webapp_path):
        return FileResponse(webapp_path)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/health")
async def health_check():
    """Check salute sistema."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mediapipe": "available" if MEDIAPIPE_AVAILABLE else "mock_mode",
        "green_dots": "available" if GREEN_DOTS_AVAILABLE else "not_available",
        "version": "1.0.0",
        "endpoints": {
            "analyze": "/api/analyze",
            "batch": "/api/batch-analyze", 
            "config": "/api/config/validate",
            "landmarks": "/api/landmarks/info",
            "green_dots_analyze": "/api/green-dots/analyze",
            "green_dots_info": "/api/green-dots/info",
            "green_dots_test": "/api/green-dots/test"
        }
    }

@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_image(request: AnalysisRequest):
    """Analizza singola immagine."""
    try:
        # Genera ID sessione
        session_id = str(uuid.uuid4())
        
        # Decodifica immagine
        image = decode_base64_image(request.image)
        
        # Rileva landmarks
        landmarks = detect_face_landmarks(image)
        
        if not landmarks:
            raise HTTPException(status_code=422, detail="Nessun volto rilevato nell'immagine")
        
        # Configura scoring
        config = request.config or ScoringConfig()
        
        # Calcola score facial
        score_components = calculate_facial_score(landmarks, config or ScoringConfig())
        
        # Calcola angoli di posa usando la nuova logica migliorata
        pose_angles_dict = calculate_head_pose_angles(landmarks)
        pose_angles = PoseAngles(**pose_angles_dict)
        
        # Calcola score di frontalità usando la nuova logica
        frontality_score = calculate_frontality_score_from_landmarks(landmarks, image.shape)
        
        # Info immagine
        image_info = {
            "width": image.shape[1],
            "height": image.shape[0],
            "channels": image.shape[2] if len(image.shape) > 2 else 1,
            "landmarks_count": len(landmarks)
        }
        
        return AnalysisResult(
            session_id=session_id,
            landmarks=landmarks,
            score=score_components["total"],
            score_components=score_components,
            pose_angles=pose_angles,
            frontality_score=frontality_score,
            image_info=image_info,
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'analisi: {str(e)}")

@app.post("/api/batch-analyze")
async def batch_analyze_images(request: BatchAnalysisRequest):
    """Analizza multiple immagini in batch."""
    try:
        results = []
        
        for i, image_b64 in enumerate(request.images):
            try:
                # Crea richiesta singola
                single_request = AnalysisRequest(
                    image=image_b64,
                    config=request.config
                )
                
                # Analizza immagine
                result = await analyze_image(single_request)
                results.append({
                    "index": i,
                    "success": True,
                    "result": result
                })
                
            except Exception as e:
                results.append({
                    "index": i,
                    "success": False,
                    "error": str(e)
                })
        
        # Statistiche batch
        successful = len([r for r in results if r["success"]])
        total = len(results)
        
        return {
            "batch_id": str(uuid.uuid4()),
            "results": results,
            "summary": {
                "total": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate": successful / total if total > 0 else 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore batch processing: {str(e)}")

@app.post("/api/config/validate")
async def validate_config(config: ScoringConfig):
    """Valida configurazione scoring."""
    try:
        # Verifica somma pesi
        total_weight = sum(config.weights.values())
        
        # Verifica range valori
        valid_weights = all(0 <= w <= 1 for w in config.weights.values())
        valid_tolerances = all(0 < t <= 2 for t in config.tolerances.values())
        
        issues = []
        
        if abs(total_weight - 1.0) > 0.01:
            issues.append(f"Somma pesi deve essere 1.0 (attuale: {total_weight:.3f})")
        
        if not valid_weights:
            issues.append("Pesi devono essere tra 0 e 1")
        
        if not valid_tolerances:
            issues.append("Tolleranze devono essere tra 0 e 2")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "normalized_weights": {
                k: v / total_weight for k, v in config.weights.items()
            } if total_weight > 0 else config.weights
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore validazione: {str(e)}")

@app.post("/api/analyze-video")
async def analyze_video(file: UploadFile = File(...)):
    """
    Analizza video per trovare il miglior frame frontale.
    Replica la funzionalità di video_analyzer.py
    """
    try:
        print(f"🎥 Analisi video iniziata: {file.filename}")
        
        # Leggi il file video
        content = await file.read()
        print(f"📁 File letto: {len(content)} bytes")
        
        # Scrivi temporaneamente il file (opencv richiede un file)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            tmp_file.write(content)
            temp_path = tmp_file.name
        
        print(f"💾 File temporaneo creato: {temp_path}")
        
        # Analizza il video frame per frame
        cap = cv2.VideoCapture(temp_path)
        
        if not cap.isOpened():
            print(f"❌ Impossibile aprire video: {temp_path}")
            try:
                os.remove(temp_path)
            except Exception as e:
                print(f"⚠️ Errore rimozione file temp: {e}")
            raise HTTPException(status_code=400, detail="Impossibile aprire il file video")
        
        best_frame = None
        best_landmarks = None
        best_score = 0.0
        frame_count = 0
        
        # Parametri analisi (replica video_analyzer.py)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        skip_frames = max(1, int(fps / 5))  # Analizza 5 frame al secondo
        
        print(f"🎬 Video info: {total_frames} frames, {fps} FPS, skip ogni {skip_frames} frames")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            
            # Salta frame per ottimizzazione
            if frame_count % skip_frames != 0:
                continue
            
            if MEDIAPIPE_AVAILABLE and face_mesh:
                # Usa MediaPipe se disponibile
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb_frame)
                
                if results.multi_face_landmarks:
                    landmarks_3d = results.multi_face_landmarks[0]
                    
                    # Calcola score frontalità usando funzione esistente
                    score = calculate_frontality_score_from_landmarks(landmarks_3d, frame.shape)
                    
                    if score > best_score:
                        best_score = score
                        best_frame = frame.copy()
                        
                        # Converti landmarks per risposta
                        h, w = frame.shape[:2]
                        landmarks_list = []
                        for landmark in landmarks_3d.landmark:
                            x = landmark.x * w
                            y = landmark.y * h
                            z = landmark.z
                            landmarks_list.append({
                                "x": float(x),
                                "y": float(y), 
                                "z": float(z),
                                "visibility": float(getattr(landmark, 'visibility', 1.0))
                            })
                        best_landmarks = landmarks_list
            else:
                # Fallback: prendi il frame centrale come "miglior" frame
                # Calcola indice frame centrale considerando lo skip
                central_frame = total_frames // 2
                if abs(frame_count - central_frame) <= skip_frames:
                    best_frame = frame.copy()
                    best_score = 0.5  # Score neutro
                    best_landmarks = []  # Nessun landmark
                    print(f"📸 Frame centrale selezionato: {frame_count}/{total_frames}")
        
        cap.release()
        
        # Rimuovi file temporaneo
        try:
            os.remove(temp_path)
            print(f"🗑️ File temporaneo rimosso")
        except Exception as e:
            print(f"⚠️ Errore rimozione file temp: {e}")
        
        if best_frame is None:
            print("❌ Nessun frame trovato")
            raise HTTPException(status_code=404, detail="Nessun frame valido trovato nel video")
        
        print(f"✅ Miglior frame trovato con score: {best_score}")
        
        # Converti miglior frame in base64
        _, buffer = cv2.imencode('.jpg', best_frame)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        
        print(f"📤 Frame convertito in base64: {len(frame_b64)} caratteri")
        
        return {
            "success": True,
            "best_frame": frame_b64,
            "landmarks": best_landmarks,
            "score": best_score,
            "total_frames": total_frames,
            "analyzed_frames": frame_count // skip_frames,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Errore analisi video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore analisi video: {str(e)}")

@app.get("/api/landmarks/info")
async def get_landmarks_info():
    """Restituisce informazioni sui landmarks MediaPipe."""
    return {
        "total_landmarks": 468,
        "categories": {
            "face_oval": {"range": [0, 16], "description": "Contorno del viso"},
            "eyebrows": {"range": [17, 26], "description": "Sopracciglia"},
            "nose": {"range": [27, 35], "description": "Naso"},
            "eyes": {"range": [36, 47], "description": "Occhi"},
            "mouth": {"range": [48, 67], "description": "Bocca"},
            "face_mesh": {"range": [68, 467], "description": "Mesh facciale dettagliata"}
        },
        "key_points": {
            "nose_tip": 1,
            "left_eye_outer": 33,
            "right_eye_outer": 362,
            "mouth_left": 61,
            "mouth_right": 291
        }
    }

# === API ENDPOINT PER MIGLIORI FRAME ===

@app.get("/api/best-frames")
async def get_best_frames():
    """Ritorna i dati dei migliori frame salvati"""
    try:
        json_path = "best_frontal_frames/best_frames_data.json"
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                frames_data = json.load(f)
            return {
                "success": True,
                "frames": frames_data
            }
        else:
            return {
                "success": False,
                "message": "Nessun dato frame disponibile"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Errore lettura dati frame: {e}"
        }

# === API ENDPOINTS PER GREEN DOTS ===

@app.post("/api/green-dots/analyze", response_model=GreenDotsAnalysisResult)
async def analyze_green_dots(request: GreenDotsAnalysisRequest):
    """
    Analizza un'immagine per rilevare puntini verdi e genera overlay grafico.
    
    Questo endpoint utilizza le funzioni del modulo src/green_dots_processor.py
    per rilevare puntini verdi, dividerli in gruppi sinistro/destro,
    calcolare statistiche delle forme e generare overlay trasparenti.
    """
    try:
        # Genera ID sessione
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        print(f"🟢 Inizio analisi green dots - Sessione: {session_id}")
        
        # Verifica disponibilità del modulo
        if not GREEN_DOTS_AVAILABLE:
            return GreenDotsAnalysisResult(
                success=False,
                session_id=session_id,
                error="Modulo GreenDotsProcessor non disponibile. Verificare l'installazione delle dipendenze.",
                timestamp=timestamp
            )
        
        # Processa l'immagine con i parametri forniti
        results = process_green_dots_analysis(
            image_base64=request.image,
            hue_range=request.hue_range,
            saturation_min=request.saturation_min,
            value_range=request.value_range,
            cluster_size_range=request.cluster_size_range,
            clustering_radius=request.clustering_radius
        )
        
        print(f"🟢 Analisi completata - Successo: {results.get('success', False)}")
        
        # Costruisce la risposta
        if results['success']:
            # Converte tutti i tipi NumPy in tipi Python nativi
            clean_results = convert_numpy_types(results)
            
            # Converte i dati nelle strutture Pydantic
            detection_results = GreenDotsDetectionResults(
                dots=[GreenDotPoint(**dot) for dot in clean_results['detection_results']['dots']],
                total_dots=clean_results['detection_results']['total_dots'],
                total_green_pixels=clean_results['detection_results']['total_green_pixels'],
                image_size=clean_results['detection_results']['image_size'],
                parameters=clean_results['detection_results']['parameters']
            )
            
            return GreenDotsAnalysisResult(
                success=True,
                session_id=session_id,
                detection_results=detection_results,
                groups=clean_results['groups'],
                coordinates=clean_results['coordinates'],
                statistics=clean_results['statistics'],
                overlay_base64=clean_results.get('overlay_base64'),
                image_size=clean_results['image_size'],
                timestamp=timestamp
            )
        else:
            # Converte anche i dati di errore
            clean_results = convert_numpy_types(results)
            
            return GreenDotsAnalysisResult(
                success=False,
                session_id=session_id,
                error=clean_results.get('error', 'Errore sconosciuto durante l\'analisi'),
                detection_results=GreenDotsDetectionResults(
                    dots=[GreenDotPoint(**dot) for dot in clean_results['detection_results']['dots']],
                    total_dots=clean_results['detection_results']['total_dots'],
                    total_green_pixels=clean_results['detection_results']['total_green_pixels'],
                    image_size=clean_results['detection_results']['image_size'],
                    parameters=clean_results['detection_results']['parameters']
                ) if 'detection_results' in clean_results else None,
                timestamp=timestamp
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Errore endpoint green dots: {str(e)}")
        return GreenDotsAnalysisResult(
            success=False,
            session_id=session_id if 'session_id' in locals() else str(uuid.uuid4()),
            error=f"Errore interno del server: {str(e)}",
            timestamp=datetime.now().isoformat()
        )

@app.get("/api/green-dots/info")
async def get_green_dots_info():
    """
    Restituisce informazioni sui parametri e funzionalità del modulo GreenDotsProcessor.
    """
    try:
        return {
            "available": GREEN_DOTS_AVAILABLE,
            "module_info": {
                "description": "Modulo per il rilevamento di puntini verdi e generazione di overlay trasparenti",
                "functions": [
                    "Rilevamento puntini verdi usando analisi HSV",
                    "Divisione dei puntini in gruppi sinistro (Sx) e destro (Dx)",
                    "Generazione di overlay trasparenti con i perimetri",
                    "Calcolo delle coordinate e statistiche delle forme"
                ]
            },
            "default_parameters": {
                "hue_range": [60, 150],
                "saturation_min": 15,
                "value_range": [15, 95],
                "cluster_size_range": [2, 150],
                "clustering_radius": 2
            },
            "output_format": {
                "success": "bool - Indica se l'analisi è riuscita",
                "groups": "Dict - Gruppi di puntini (Sx/Dx)",
                "coordinates": "Dict - Coordinate dei puntini per gruppo",
                "statistics": "Dict - Statistiche delle forme (area, perimetro, etc.)",
                "overlay_base64": "str - Overlay grafico in formato base64",
                "image_size": "Tuple - Dimensioni originali dell'immagine"
            },
            "requirements": {
                "min_dots_total": 6,
                "min_dots_per_side": 3,
                "dependencies": ["opencv-python", "numpy", "pillow"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore recupero informazioni: {str(e)}")

@app.post("/api/green-dots/test")
async def test_green_dots():
    """
    Endpoint di test per verificare il funzionamento del modulo GreenDotsProcessor.
    """
    try:
        if not GREEN_DOTS_AVAILABLE:
            return {
                "success": False,
                "message": "Modulo GreenDotsProcessor non disponibile",
                "available": False
            }
        
        # Test di inizializzazione del processore
        try:
            processor = GreenDotsProcessor()
            return {
                "success": True,
                "message": "Modulo GreenDotsProcessor funzionante",
                "available": True,
                "processor_initialized": True,
                "default_config": {
                    "hue_range": [processor.hue_min, processor.hue_max],
                    "saturation_min": processor.saturation_min,
                    "value_range": [processor.value_min, processor.value_max],
                    "cluster_size_range": [processor.cluster_min, processor.cluster_max],
                    "clustering_radius": processor.clustering_radius
                }
            }
        except Exception as init_error:
            return {
                "success": False,
                "message": f"Errore inizializzazione processore: {str(init_error)}",
                "available": True,
                "processor_initialized": False
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore test modulo: {str(e)}")

# === API ENDPOINTS SPECIFICI PER CORREZIONE SOPRACCIGLIA ===

class EyebrowAnalysisRequest(BaseModel):
    image: str  # Base64 encoded image
    side: str   # "left" o "right"
    expand_factor: float = 0.5  # Fattore espansione bounding box
    hue_range: Tuple[int, int] = (60, 150)
    saturation_min: int = 15
    value_range: Tuple[int, int] = (15, 95)
    cluster_size_range: Tuple[int, int] = (2, 150)
    clustering_radius: int = 2

class EyebrowAnalysisResult(BaseModel):
    success: bool
    session_id: str
    side: str
    dots: Optional[List[Dict[str, Any]]] = None
    coordinates: Optional[List[Tuple[float, float]]] = None
    statistics: Optional[Dict[str, Any]] = None
    bbox: Optional[Dict[str, float]] = None
    overlay_base64: Optional[str] = None
    error: Optional[str] = None
    timestamp: str

@app.post("/api/eyebrow/analyze", response_model=EyebrowAnalysisResult)
async def analyze_eyebrow(request: EyebrowAnalysisRequest):
    """
    Analizza un sopracciglio specifico (sinistro o destro) generando gli stessi
    output di src/green_dots_processor.py per i pulsanti della webapp.
    """
    try:
        # Genera ID sessione
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        print(f"✂️ Inizio analisi sopracciglio {request.side} - Sessione: {session_id}")
        
        # Verifica disponibilità del modulo
        if not GREEN_DOTS_AVAILABLE:
            return EyebrowAnalysisResult(
                success=False,
                session_id=session_id,
                side=request.side,
                error="Modulo GreenDotsProcessor non disponibile. Verificare l'installazione delle dipendenze.",
                timestamp=timestamp
            )
        
        # Valida il lato richiesto
        if request.side not in ["left", "right"]:
            return EyebrowAnalysisResult(
                success=False,
                session_id=session_id,
                side=request.side,
                error="Il parametro 'side' deve essere 'left' o 'right'",
                timestamp=timestamp
            )
        
        # Processa l'immagine con i parametri forniti
        results = process_green_dots_analysis(
            image_base64=request.image,
            hue_range=request.hue_range,
            saturation_min=request.saturation_min,
            value_range=request.value_range,
            cluster_size_range=request.cluster_size_range,
            clustering_radius=request.clustering_radius
        )
        
        if not results['success']:
            return EyebrowAnalysisResult(
                success=False,
                session_id=session_id,
                side=request.side,
                error=results.get('error', 'Errore sconosciuto durante l\'analisi'),
                timestamp=timestamp
            )
        
        # Converte tutti i tipi NumPy in tipi Python nativi
        clean_results = convert_numpy_types(results)
        
        # Estrai dati del sopracciglio richiesto
        if request.side == "left":
            eyebrow_dots = clean_results['groups']['Sx']
            eyebrow_coordinates = clean_results['coordinates']['Sx']
            eyebrow_statistics = clean_results['statistics']['left']
        else:  # right
            eyebrow_dots = clean_results['groups']['Dx']
            eyebrow_coordinates = clean_results['coordinates']['Dx']
            eyebrow_statistics = clean_results['statistics']['right']
        
        # Calcola bounding box con espansione
        if eyebrow_dots:
            # Usa il processore per calcolare il bounding box
            processor = GreenDotsProcessor()
            processor.left_dots = clean_results['groups']['Sx'] if request.side == "left" else []
            processor.right_dots = clean_results['groups']['Dx'] if request.side == "right" else []
            
            if request.side == "left":
                bbox_tuple = processor.get_left_eyebrow_bbox(request.expand_factor)
            else:
                bbox_tuple = processor.get_right_eyebrow_bbox(request.expand_factor)
            
            bbox = {
                "x_min": bbox_tuple[0],
                "y_min": bbox_tuple[1], 
                "x_max": bbox_tuple[2],
                "y_max": bbox_tuple[3]
            }
        else:
            bbox = {"x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0}
        
        # Genera overlay specifico per il lato richiesto
        overlay_base64 = None
        if 'overlay_base64' in clean_results:
            # L'overlay originale contiene entrambi i lati
            # Per un uso specifico, potremmo generare un overlay solo per un lato
            # Ma per compatibilità, usiamo quello completo
            overlay_base64 = clean_results['overlay_base64']
        
        print(f"✂️ Analisi sopracciglio {request.side} completata - Punti: {len(eyebrow_dots)}")
        
        return EyebrowAnalysisResult(
            success=True,
            session_id=session_id,
            side=request.side,
            dots=eyebrow_dots,
            coordinates=eyebrow_coordinates,
            statistics=eyebrow_statistics,
            bbox=bbox,
            overlay_base64=overlay_base64,
            timestamp=timestamp
        )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Errore endpoint sopracciglio {request.side}: {str(e)}")
        return EyebrowAnalysisResult(
            success=False,
            session_id=session_id if 'session_id' in locals() else str(uuid.uuid4()),
            side=request.side,
            error=f"Errore interno del server: {str(e)}",
            timestamp=datetime.now().isoformat()
        )

@app.post("/api/eyebrow/left")
async def analyze_left_eyebrow(request: Dict[str, str]):
    """
    Endpoint specifico per il sopracciglio sinistro - equivalente alla funzione 
    showLeftEyebrow() del JavaScript.
    """
    try:
        # Crea richiesta per il sopracciglio sinistro
        eyebrow_request = EyebrowAnalysisRequest(
            image=request["image"],
            side="left"
        )
        
        # Analizza il sopracciglio sinistro
        result = await analyze_eyebrow(eyebrow_request)
        
        # Restituisce un formato semplificato compatibile con il frontend
        return {
            "success": result.success,
            "side": "left",
            "data": {
                "dots": result.dots,
                "coordinates": result.coordinates,
                "statistics": result.statistics,
                "bbox": result.bbox
            } if result.success else None,
            "error": result.error,
            "timestamp": result.timestamp
        }
        
    except Exception as e:
        return {
            "success": False,
            "side": "left", 
            "error": f"Errore analisi sopracciglio sinistro: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/eyebrow/right")
async def analyze_right_eyebrow(request: Dict[str, str]):
    """
    Endpoint specifico per il sopracciglio destro - equivalente alla funzione
    showRightEyebrow() del JavaScript.
    """
    try:
        # Crea richiesta per il sopracciglio destro
        eyebrow_request = EyebrowAnalysisRequest(
            image=request["image"],
            side="right"
        )
        
        # Analizza il sopracciglio destro
        result = await analyze_eyebrow(eyebrow_request)
        
        # Restituisce un formato semplificato compatibile con il frontend
        return {
            "success": result.success,
            "side": "right",
            "data": {
                "dots": result.dots,
                "coordinates": result.coordinates,
                "statistics": result.statistics,
                "bbox": result.bbox
            } if result.success else None,
            "error": result.error,
            "timestamp": result.timestamp
        }
        
    except Exception as e:
        return {
            "success": False,
            "side": "right",
            "error": f"Errore analisi sopracciglio destro: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

# === ENDPOINT UNIFICATO PER ANALISI COMPLETA ===

class CanvasAnalysisRequest(BaseModel):
    image: str  # Base64 encoded image from canvas
    analysis_types: List[str] = [
        "face_width", "face_height", "eye_distance", "nose_width", 
        "mouth_width", "eyebrow_areas", "eye_areas", "facial_symmetry",
        "cheek_width", "forehead_width", "chin_width", "face_profile",
        "nose_angle", "mouth_angle", "face_proportions", "key_distances"
    ]
    config: Optional[ScoringConfig] = None

class MeasurementResult(BaseModel):
    type: str
    value: float
    unit: str = "pixels"
    coordinates: Optional[List[Tuple[float, float]]] = None
    metadata: Optional[Dict[str, Any]] = None

class CanvasAnalysisResult(BaseModel):
    session_id: str
    landmarks: List[LandmarkPoint]
    measurements: List[MeasurementResult]
    facial_scores: Dict[str, float]
    pose_angles: PoseAngles
    frontality_score: float
    symmetry_analysis: Dict[str, Any]
    image_info: Dict[str, Any]
    timestamp: str

def calculate_all_facial_measurements(landmarks: List[LandmarkPoint], image_shape: Tuple[int, int]) -> List[MeasurementResult]:
    """Calcola tutte le misurazioni facciali disponibili."""
    measurements = []
    
    if len(landmarks) < 468:
        return measurements
    
    try:
        # Converti landmarks in formato compatibile
        points = [(lm.x, lm.y) for lm in landmarks]
        
        # === MISURAZIONI BASE ===
        
        # 1. Larghezza Volto (punti 234-454)
        if len(points) > 454:
            face_left = points[234]
            face_right = points[454] 
            face_width = calculate_distance(face_left, face_right)
            measurements.append(MeasurementResult(
                type="face_width",
                value=face_width,
                coordinates=[face_left, face_right],
                metadata={"description": "Larghezza del volto"}
            ))
        
        # 2. Altezza Volto (punti 10-175)
        if len(points) > 175:
            face_top = points[10]
            face_bottom = points[175]
            face_height = calculate_distance(face_top, face_bottom)
            measurements.append(MeasurementResult(
                type="face_height", 
                value=face_height,
                coordinates=[face_top, face_bottom],
                metadata={"description": "Altezza del volto"}
            ))
        
        # 3. Distanza Occhi (punti 33-362)
        if len(points) > 362:
            left_eye_outer = points[33]
            right_eye_outer = points[362]
            eye_distance = calculate_distance(left_eye_outer, right_eye_outer)
            measurements.append(MeasurementResult(
                type="eye_distance",
                value=eye_distance,
                coordinates=[left_eye_outer, right_eye_outer],
                metadata={"description": "Distanza tra gli occhi esterni"}
            ))
        
        # 4. Larghezza Naso (punti 131-360)
        if len(points) > 360:
            nose_left = points[131]
            nose_right = points[360]
            nose_width = calculate_distance(nose_left, nose_right)
            measurements.append(MeasurementResult(
                type="nose_width",
                value=nose_width,
                coordinates=[nose_left, nose_right],
                metadata={"description": "Larghezza del naso"}
            ))
        
        # 5. Larghezza Bocca (punti 61-291)
        if len(points) > 291:
            mouth_left = points[61]
            mouth_right = points[291]
            mouth_width = calculate_distance(mouth_left, mouth_right)
            measurements.append(MeasurementResult(
                type="mouth_width",
                value=mouth_width,
                coordinates=[mouth_left, mouth_right],
                metadata={"description": "Larghezza della bocca"}
            ))
        
        # === MISURAZIONI AREE ===
        
        # 6. Aree Sopracciglia
        if len(points) > 300:
            # Sopracciglio sinistro
            left_eyebrow_points = [points[i] for i in [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]]
            left_eyebrow_area = calculate_polygon_area(left_eyebrow_points)
            
            # Sopracciglio destro  
            right_eyebrow_points = [points[i] for i in [296, 334, 293, 300, 276, 283, 282, 295, 285]]
            right_eyebrow_area = calculate_polygon_area(right_eyebrow_points)
            
            measurements.extend([
                MeasurementResult(
                    type="left_eyebrow_area",
                    value=left_eyebrow_area,
                    unit="pixels²",
                    coordinates=left_eyebrow_points,
                    metadata={"description": "Area sopracciglio sinistro"}
                ),
                MeasurementResult(
                    type="right_eyebrow_area", 
                    value=right_eyebrow_area,
                    unit="pixels²",
                    coordinates=right_eyebrow_points,
                    metadata={"description": "Area sopracciglio destro"}
                )
            ])
        
        # 7. Aree Occhi
        if len(points) > 374:
            # Occhio sinistro
            left_eye_points = [points[i] for i in [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]]
            left_eye_area = calculate_polygon_area(left_eye_points)
            
            # Occhio destro
            right_eye_points = [points[i] for i in [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]]
            right_eye_area = calculate_polygon_area(right_eye_points)
            
            measurements.extend([
                MeasurementResult(
                    type="left_eye_area",
                    value=left_eye_area,
                    unit="pixels²",
                    coordinates=left_eye_points,
                    metadata={"description": "Area occhio sinistro"}
                ),
                MeasurementResult(
                    type="right_eye_area",
                    value=right_eye_area, 
                    unit="pixels²",
                    coordinates=right_eye_points,
                    metadata={"description": "Area occhio destro"}
                )
            ])
        
        # === MISURAZIONI AVANZATE ===
        
        # 8. Simmetria Facciale
        symmetry_score = calculate_facial_symmetry_detailed(points)
        measurements.append(MeasurementResult(
            type="facial_symmetry",
            value=symmetry_score,
            unit="score",
            metadata={"description": "Punteggio simmetria facciale (0-1)"}
        ))
        
        # 9. Proporzioni Auree
        if len(measurements) >= 2:  # Abbiamo larghezza e altezza
            face_width_val = next((m.value for m in measurements if m.type == "face_width"), 0)
            face_height_val = next((m.value for m in measurements if m.type == "face_height"), 0)
            
            if face_height_val > 0:
                face_ratio = face_width_val / face_height_val
                golden_ratio_diff = abs(face_ratio - 1.618)
                
                measurements.append(MeasurementResult(
                    type="face_proportions",
                    value=face_ratio,
                    unit="ratio",
                    metadata={
                        "description": "Rapporto larghezza/altezza volto",
                        "golden_ratio": 1.618,
                        "deviation": golden_ratio_diff
                    }
                ))
        
    except Exception as e:
        print(f"Errore calcolo misurazioni: {e}")
    
    return measurements

def calculate_distance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    """Calcola distanza euclidea tra due punti."""
    return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

def calculate_polygon_area(points: List[Tuple[float, float]]) -> float:
    """Calcola area di un poligono usando formula shoelace."""
    if len(points) < 3:
        return 0.0
    
    area = 0.0
    n = len(points)
    
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    
    return abs(area) / 2.0

def calculate_facial_symmetry_detailed(points: List[Tuple[float, float]]) -> float:
    """Calcola simmetria facciale dettagliata."""
    if len(points) < 468:
        return 0.0
    
    try:
        # Asse centrale (punta del naso)
        nose_tip = points[4] if len(points) > 4 else points[1]
        
        # Coppie di punti simmetrici
        symmetric_pairs = [
            (points[33], points[362]),   # Angoli esterni occhi
            (points[133], points[362]),  # Angoli interni occhi  
            (points[61], points[291]),   # Angoli bocca
            (points[234], points[454]),  # Guance larghe
            (points[70], points[300]),   # Sopracciglia esterne
        ]
        
        symmetry_scores = []
        
        for left_point, right_point in symmetric_pairs:
            # Distanza dall'asse centrale
            left_distance = abs(left_point[0] - nose_tip[0])
            right_distance = abs(right_point[0] - nose_tip[0])
            
            # Score simmetria per questa coppia
            if left_distance + right_distance > 0:
                symmetry = 1.0 - abs(left_distance - right_distance) / (left_distance + right_distance)
                symmetry_scores.append(max(0, symmetry))
        
        return sum(symmetry_scores) / len(symmetry_scores) if symmetry_scores else 0.0
        
    except Exception as e:
        print(f"Errore calcolo simmetria: {e}")
        return 0.0

@app.post("/api/canvas-analysis", response_model=CanvasAnalysisResult)
async def analyze_canvas_image(request: CanvasAnalysisRequest):
    """
    Endpoint unificato per l'analisi completa dell'immagine del canvas.
    Applica tutte le funzioni di misurazione richieste all'immagine corrente.
    """
    try:
        # Genera ID sessione
        session_id = str(uuid.uuid4())
        
        # Decodifica immagine dal canvas
        image = decode_base64_image(request.image)
        
        # Rileva landmarks
        landmarks = detect_face_landmarks(image)
        
        if not landmarks:
            raise HTTPException(status_code=422, detail="Nessun volto rilevato nell'immagine del canvas")
        
        # Configura scoring
        config = request.config or ScoringConfig()
        
        # === ANALISI COMPLETA ===
        
        # 1. Calcola tutte le misurazioni richieste
        measurements = calculate_all_facial_measurements(landmarks, image.shape)
        
        # 2. Calcola score facciali
        facial_scores = calculate_facial_score(landmarks, config)
        
        # 3. Calcola angoli di posa
        pose_angles_dict = calculate_head_pose_angles(landmarks)
        pose_angles = PoseAngles(**pose_angles_dict)
        
        # 4. Calcola score frontalità
        frontality_score = calculate_frontality_score_from_landmarks(landmarks, image.shape)
        
        # 5. Analisi simmetria dettagliata
        points = [(lm.x, lm.y) for lm in landmarks]
        symmetry_analysis = {
            "overall_score": calculate_facial_symmetry_detailed(points),
            "pose_angles": pose_angles_dict,
            "frontality_score": frontality_score,
            "symmetry_components": {
                "eyes": calculate_eye_symmetry(points),
                "mouth": calculate_mouth_symmetry(points),
                "face_outline": calculate_face_outline_symmetry(points)
            }
        }
        
        # Info immagine
        image_info = {
            "width": image.shape[1],
            "height": image.shape[0],
            "channels": image.shape[2] if len(image.shape) > 2 else 1,
            "landmarks_count": len(landmarks),
            "analysis_types": request.analysis_types
        }
        
        return CanvasAnalysisResult(
            session_id=session_id,
            landmarks=landmarks,
            measurements=measurements,
            facial_scores=facial_scores,
            pose_angles=pose_angles,
            frontality_score=frontality_score,
            symmetry_analysis=symmetry_analysis,
            image_info=image_info,
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'analisi canvas: {str(e)}")

def calculate_eye_symmetry(points: List[Tuple[float, float]]) -> float:
    """Calcola simmetria specifica degli occhi."""
    try:
        if len(points) < 400:
            return 0.0
        
        # Larghezza occhi
        left_eye_width = calculate_distance(points[33], points[133])   # Occhio sinistro
        right_eye_width = calculate_distance(points[362], points[263]) # Occhio destro
        
        # Altezza occhi
        left_eye_height = calculate_distance(points[159], points[145])  # Occhio sinistro
        right_eye_height = calculate_distance(points[386], points[374]) # Occhio destro
        
        # Score simmetria larghezza
        width_symmetry = 1.0 - abs(left_eye_width - right_eye_width) / max(left_eye_width, right_eye_width, 1)
        
        # Score simmetria altezza  
        height_symmetry = 1.0 - abs(left_eye_height - right_eye_height) / max(left_eye_height, right_eye_height, 1)
        
        return (width_symmetry + height_symmetry) / 2
        
    except:
        return 0.0

def calculate_mouth_symmetry(points: List[Tuple[float, float]]) -> float:
    """Calcola simmetria specifica della bocca."""
    try:
        if len(points) < 300:
            return 0.0
        
        # Centro bocca
        mouth_center = points[13] if len(points) > 13 else points[0]
        
        # Angoli bocca
        mouth_left = points[61]
        mouth_right = points[291]
        
        # Distanze dal centro
        left_distance = calculate_distance(mouth_center, mouth_left)
        right_distance = calculate_distance(mouth_center, mouth_right)
        
        # Score simmetria
        if left_distance + right_distance > 0:
            return 1.0 - abs(left_distance - right_distance) / (left_distance + right_distance)
        
        return 0.0
        
    except:
        return 0.0

def calculate_face_outline_symmetry(points: List[Tuple[float, float]]) -> float:
    """Calcola simmetria del contorno del volto."""
    try:
        if len(points) < 400:
            return 0.0
        
        # Punti contorno volto
        face_outline_left = [points[i] for i in [234, 127, 162, 21, 54, 103, 67, 109]]
        face_outline_right = [points[i] for i in [454, 356, 389, 251, 284, 332, 297, 338]]
        
        # Centro del volto (punta naso)
        face_center = points[4] if len(points) > 4 else points[1]
        
        # Calcola distanze medie dal centro per ogni lato
        left_distances = [calculate_distance(face_center, p) for p in face_outline_left]
        right_distances = [calculate_distance(face_center, p) for p in face_outline_right]
        
        avg_left = sum(left_distances) / len(left_distances) if left_distances else 0
        avg_right = sum(right_distances) / len(right_distances) if right_distances else 0
        
        # Score simmetria
        if avg_left + avg_right > 0:
            return 1.0 - abs(avg_left - avg_right) / (avg_left + avg_right)
        
        return 0.0
        
    except:
        return 0.0

# ========================================
# VOICE ASSISTANT ENDPOINTS
# ========================================

@app.get("/api/voice/status", response_model=VoiceStatusResponse)
async def get_voice_status():
    """Ottiene lo stato corrente del voice assistant."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        return VoiceStatusResponse(
            available=False,
            is_active=False,
            is_muted=False,
            config=None
        )
    
    return VoiceStatusResponse(
        available=True,
        is_active=voice_assistant.is_active,
        is_muted=voice_assistant.is_muted,
        config=voice_assistant.config
    )

@app.post("/api/voice/start")
async def start_voice_assistant():
    """Avvia l'assistente vocale."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        voice_assistant.start()
        return {"success": True, "message": "Assistente vocale avviato"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore avvio assistente: {str(e)}")

@app.post("/api/voice/stop")
async def stop_voice_assistant():
    """Ferma l'assistente vocale."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        voice_assistant.stop()
        return {"success": True, "message": "Assistente vocale fermato"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore stop assistente: {str(e)}")

@app.post("/api/voice/toggle")
async def toggle_voice_assistant():
    """Attiva/disattiva l'assistente vocale."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        voice_assistant.toggle()
        status = "attivato" if voice_assistant.is_active else "disattivato"
        return {
            "success": True, 
            "message": f"Assistente vocale {status}",
            "is_active": voice_assistant.is_active
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore toggle assistente: {str(e)}")

@app.post("/api/voice/mute")
async def mute_voice_assistant():
    """Silenzia l'assistente vocale."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        voice_assistant.mute()
        return {"success": True, "message": "Assistente vocale silenziato", "is_muted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore mute assistente: {str(e)}")

@app.post("/api/voice/unmute")
async def unmute_voice_assistant():
    """Riattiva l'audio dell'assistente vocale."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        voice_assistant.unmute()
        return {"success": True, "message": "Audio assistente riattivato", "is_muted": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore unmute assistente: {str(e)}")

@app.post("/api/voice/speak")
async def speak_text(request: VoiceSpeakRequest):
    """Genera audio con voce Isabella e lo restituisce al browser."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        # Importa edge_tts per generazione diretta
        import edge_tts
        import asyncio
        
        print(f"🎙️ Generazione TTS per: '{request.text[:50]}...'")
        
        # Genera audio con voce Isabella
        voice = voice_assistant.config.get("tts_voice", "it-IT-IsabellaNeural")
        print(f"🔊 Voce selezionata: {voice}")
        
        # Crea file temporaneo
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()  # Chiudi subito il file per permettere a edge-tts di scriverci
        print(f"📁 File temporaneo: {temp_path}")
        
        # Genera audio con edge-tts
        communicate = edge_tts.Communicate(request.text, voice)
        await communicate.save(temp_path)
        print(f"✅ Audio generato")
        
        # Leggi file e converti in base64
        with open(temp_path, 'rb') as f:
            audio_data = f.read()
        
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        print(f"📦 Audio codificato in base64 ({len(audio_base64)} chars)")
        
        # Elimina file temporaneo (con retry per Windows)
        import time
        max_retries = 5
        for i in range(max_retries):
            try:
                os.unlink(temp_path)
                print(f"✅ File temporaneo eliminato")
                break
            except PermissionError:
                if i < max_retries - 1:
                    time.sleep(0.1)  # Aspetta 100ms e riprova
                else:
                    print(f"⚠️ Non è stato possibile eliminare il file temporaneo: {temp_path}")
            except Exception as e:
                print(f"⚠️ Errore eliminazione file: {e}")
                break
        
        return {
            "success": True, 
            "message": "Audio generato con successo",
            "audio": f"data:audio/mp3;base64,{audio_base64}",
            "voice": voice
        }
    except Exception as e:
        print(f"❌ ERRORE generazione audio: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore generazione audio: {str(e)}")

@app.post("/api/voice/command", response_model=VoiceCommandResponse)
async def process_voice_command(request: VoiceCommand):
    """Processa un comando vocale testuale (per testing senza microfono)."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        # Processa il comando
        voice_assistant.process_command(request.command)
        
        return VoiceCommandResponse(
            success=True,
            message="Comando processato",
            command_recognized=request.command
        )
    except Exception as e:
        return VoiceCommandResponse(
            success=False,
            message=f"Errore processamento comando: {str(e)}",
            command_recognized=request.command
        )

@app.get("/api/voice/commands")
async def get_voice_commands():
    """Ottiene la lista dei comandi vocali disponibili."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    try:
        commands = voice_assistant.config.get("commands", [])
        return {
            "success": True,
            "commands": commands,
            "activation_keywords": voice_assistant.config.get("activation_keywords", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore recupero comandi: {str(e)}")

@app.get("/api/voice/messages")
async def get_voice_messages():
    """Ottiene i messaggi predefiniti che Isabella può pronunciare."""
    messages = {
        "welcome": "Benvenuto nella webapp di analisi facciale. Io sono Isabella, la tua assistente vocale.",
        "analysis_start": "Avvio analisi del volto. Attendere prego.",
        "analysis_complete": "Analisi completata con successo. I risultati sono visibili sullo schermo.",
        "analysis_failed": "Mi dispiace, l'analisi non è riuscita. Riprova con un'immagine migliore.",
        "webcam_started": "Webcam attivata correttamente.",
        "webcam_stopped": "Webcam disattivata.",
        "image_loaded": "Immagine caricata con successo.",
        "axis_on": "Asse di simmetria attivato.",
        "axis_off": "Asse di simmetria disattivato.",
        "landmarks_on": "Landmarks attivati.",
        "landmarks_off": "Landmarks disattivati.",
        "green_dots_on": "Rilevamento punti verdi attivato.",
        "green_dots_off": "Rilevamento punti verdi disattivato.",
        "measurement_started": "Misurazione avviata. Seleziona i punti richiesti.",
        "error": "Si è verificato un errore. Riprova.",
        "command_not_recognized": "Comando non riconosciuto. Prova a ripetere."
    }
    return {"success": True, "messages": messages}

@app.post("/api/voice/speak-message")
async def speak_predefined_message(request: VoiceMessageRequest):
    """Fa pronunciare un messaggio predefinito a Isabella."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")
    
    # Messaggi predefiniti
    messages = {
        "welcome": "Benvenuto nella webapp di analisi facciale. Io sono Isabella, la tua assistente vocale.",
        "analysis_start": "Avvio analisi del volto. Attendere prego.",
        "analysis_complete": "Analisi completata con successo. I risultati sono visibili sullo schermo.",
        "analysis_failed": "Mi dispiace, l'analisi non è riuscita. Riprova con un'immagine migliore.",
        "webcam_started": "Webcam attivata correttamente.",
        "webcam_stopped": "Webcam disattivata.",
        "image_loaded": "Immagine caricata con successo.",
        "axis_on": "Asse di simmetria attivato.",
        "axis_off": "Asse di simmetria disattivato.",
        "landmarks_on": "Landmarks attivati.",
        "landmarks_off": "Landmarks disattivati.",
        "green_dots_on": "Rilevamento punti verdi attivato.",
        "green_dots_off": "Rilevamento punti verdi disattivato.",
        "measurement_started": "Misurazione avviata. Seleziona i punti richiesti.",
        "error": "Si è verificato un errore. Riprova.",
        "command_not_recognized": "Comando non riconosciuto. Prova a ripetere."
    }
    
    text = messages.get(request.message_key)
    if not text:
        raise HTTPException(status_code=404, detail=f"Messaggio '{request.message_key}' non trovato")
    
    try:
        import edge_tts
        
        voice = voice_assistant.config.get("tts_voice", "it-IT-IsabellaNeural")
        
        # Crea file temporaneo
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()
        
        # Genera audio
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_path)
        
        # Leggi e codifica
        with open(temp_path, 'rb') as f:
            audio_data = f.read()
        
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # Elimina file temporaneo
        import time
        for i in range(5):
            try:
                os.unlink(temp_path)
                break
            except PermissionError:
                if i < 4:
                    time.sleep(0.1)
        
        return {
            "success": True,
            "message": "Audio generato",
            "audio": f"data:audio/mp3;base64,{audio_base64}",
            "text": text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore generazione audio: {str(e)}")

@app.post("/api/voice/speak-welcome")
async def speak_welcome_message(request: VoiceWelcomeRequest):
    """Fa pronunciare un messaggio di benvenuto personalizzato con il nome dell'utente."""
    if not VOICE_ASSISTANT_AVAILABLE or voice_assistant is None:
        raise HTTPException(status_code=503, detail="Voice Assistant non disponibile")

    # Messaggio di benvenuto personalizzato con il nome utente
    user_name = request.user_name or "utente"
    text = f"Ciao {user_name}, io sono Kimerika e ti aiuterò nelle progettazioni delle tue dermopigmentazioni."

    try:
        import edge_tts

        voice = voice_assistant.config.get("tts_voice", "it-IT-IsabellaNeural")

        # Crea file temporaneo
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()

        # Genera audio
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_path)

        # Leggi e codifica
        with open(temp_path, 'rb') as f:
            audio_data = f.read()

        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Elimina file temporaneo
        import time
        for i in range(5):
            try:
                os.unlink(temp_path)
                break
            except PermissionError:
                if i < 4:
                    time.sleep(0.1)

        return {
            "success": True,
            "message": "Messaggio di benvenuto generato",
            "audio": f"data:audio/mp3;base64,{audio_base64}",
            "text": text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore generazione audio: {str(e)}")

@app.post("/api/voice/process-keyword", response_model=VoiceKeywordResponse)
async def process_voice_keyword(request: VoiceKeywordCommand):
    """Processa una parola chiave vocale e restituisce l'azione da eseguire nel frontend."""
    keyword = request.keyword.lower().strip()
    
    # Mappa parole chiave -> azioni frontend
    # IMPORTANTE: pattern più specifici PRIMA per evitare conflitti
    keyword_map = {
        # Stop webcam - PRIMA di "webcam" (senza message per evitare doppio feedback)
        "ferma webcam": {"action": "stopWebcam"},
        "stop webcam": {"action": "stopWebcam"},
        "chiudi webcam": {"action": "stopWebcam"},
        "disattiva webcam": {"action": "stopWebcam"},
        "spegni webcam": {"action": "stopWebcam"},
        "ferma camera": {"action": "stopWebcam"},
        "stop camera": {"action": "stopWebcam"},
        "chiudi camera": {"action": "stopWebcam"},
        # Start webcam - DOPO stop (senza message per evitare doppio feedback)
        "avvia webcam": {"action": "startWebcam"},
        "avvia camera": {"action": "startWebcam"},
        "attiva webcam": {"action": "startWebcam"},
        "accendi webcam": {"action": "startWebcam"},
        "apri webcam": {"action": "startWebcam"},
        "webcam": {"action": "startWebcam"},
        # Altri comandi
        "carica immagine": {"action": "loadImage", "message": "Apertura caricamento immagine"},
        "carica video": {"action": "loadVideo", "message": "Apertura caricamento video"},
        "punti verdi": {"action": "toggleGreenDots", "message": "Attivazione/disattivazione punti verdi"},
        "sopracciglio sinistro": {"action": "analyzeLeftEyebrow", "message": "Analisi sopracciglio sinistro"},
        "sopracciglio destro": {"action": "analyzeRightEyebrow", "message": "Analisi sopracciglio destro"},
        "asse": {"action": "toggleAxis", "message": "Attivazione/disattivazione asse di simmetria"},
        "landmarks": {"action": "toggleLandmarks", "message": "Attivazione/disattivazione landmarks"},
        "verde": {"action": "toggleGreenDots", "message": "Attivazione/disattivazione punti verdi"},
        "immagine": {"action": "loadImage", "message": "Apertura caricamento immagine"},
        "video": {"action": "loadVideo", "message": "Apertura caricamento video"},
        "analizza": {"action": "analyzeFace", "message": "Avvio analisi facciale"},
        "analisi": {"action": "analyzeFace", "message": "Avvio analisi facciale"},
        "cancella": {"action": "clearCanvas", "message": "Pulizia canvas"},
        "pulisci": {"action": "clearCanvas", "message": "Pulizia canvas"},
        # Comandi per simmetria facciale (con tutte le varianti: viso/volto/faccia)
        "simmetria": {"action": "measureFacialSymmetry", "message": "Analisi simmetria facciale"},
        "simmetrico": {"action": "measureFacialSymmetry", "message": "Analisi simmetria facciale"},
        "simmetrica": {"action": "measureFacialSymmetry", "message": "Analisi simmetria facciale"},
        "lato più grande": {"action": "measureFacialSymmetry", "message": "Analisi simmetria facciale"},
        "quale lato": {"action": "measureFacialSymmetry", "message": "Analisi simmetria facciale"},
        # Comando per correzione progettazione sopraccigliare
        "correggimi la progettazione": {"action": "analyze_eyebrow_design", "message": "Avvio analisi della progettazione sopraccigliare"},
        "correggi progettazione": {"action": "analyze_eyebrow_design", "message": "Avvio analisi della progettazione sopraccigliare"},
        "correzione progettazione": {"action": "analyze_eyebrow_design", "message": "Avvio analisi della progettazione sopraccigliare"},
        "analizza progettazione": {"action": "analyze_eyebrow_design", "message": "Avvio analisi della progettazione sopraccigliare"},
        # Comando per preferenza destra (correzione sopracciglio sinistro)
        "preferenza destra": {"action": "show_left_eyebrow_with_voice", "message": ""},
        "preferenza a destra": {"action": "show_left_eyebrow_with_voice", "message": ""},
        "correzione destra": {"action": "show_left_eyebrow_with_voice", "message": ""},
        "correzione a destra": {"action": "show_left_eyebrow_with_voice", "message": ""},
        # Comando per preferenza sinistra (correzione sopracciglio destro)
        "preferenza sinistra": {"action": "show_right_eyebrow_with_voice", "message": ""},
        "preferenza a sinistra": {"action": "show_right_eyebrow_with_voice", "message": ""},
        "correzione sinistra": {"action": "show_right_eyebrow_with_voice", "message": ""},
        "correzione a sinistra": {"action": "show_right_eyebrow_with_voice", "message": ""},
    }
    
    # Cerca match
    for key, value in keyword_map.items():
        if key in keyword:
            return VoiceKeywordResponse(
                success=True,
                keyword=keyword,
                action=value["action"],
                message=value.get("message", "")
            )
    
    return VoiceKeywordResponse(
        success=False,
        keyword=keyword,
        message="Parola chiave non riconosciuta"
    )

@app.post("/api/face-analysis/complete")
async def complete_face_analysis(file: UploadFile = File(...)):
    """
    Esegue un'analisi visagistica completa usando face_analysis_module.py
    Ritorna il report testuale completo dell'analisi.
    """
    try:
        # Importa il modulo di analisi visagistica
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
        from face_analysis_module import FaceVisagismAnalyzer

        print(f"🎯 Analisi visagistica completa richiesta per: {file.filename}")

        # Leggi il file immagine
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Impossibile decodificare l'immagine")

        # Crea un file temporaneo per l'immagine
        temp_dir = tempfile.mkdtemp()
        temp_image_path = os.path.join(temp_dir, "analysis_image.jpg")
        cv2.imwrite(temp_image_path, img)

        # Output directory per i risultati
        output_dir = os.path.join(temp_dir, "analysis_results")
        os.makedirs(output_dir, exist_ok=True)

        # Inizializza l'analizzatore
        analyzer = FaceVisagismAnalyzer()

        # Esegui l'analisi completa
        result = analyzer.analyze_face(temp_image_path, output_dir=output_dir)

        # Genera il report testuale
        report_text = analyzer.generate_text_report(result)

        # Leggi le immagini debug generate e convertile in base64
        debug_images_b64 = {}
        for key, img_path in result['immagini_debug'].items():
            if os.path.exists(img_path):
                with open(img_path, 'rb') as f:
                    img_data = f.read()
                    debug_images_b64[key] = base64.b64encode(img_data).decode('utf-8')

        # Cleanup dei file temporanei
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"⚠️ Warning: impossibile eliminare directory temporanea: {e}")

        return {
            "success": True,
            "report": report_text,
            "data": {
                "forma_viso": result['forma_viso'],
                "metriche_facciali": result['metriche_facciali'],
                "caratteristiche_facciali": result['caratteristiche_facciali'],
                "analisi_visagistica": result['analisi_visagistica'],
                "analisi_espressiva": result['analisi_espressiva']
            },
            "debug_images": debug_images_b64,
            "timestamp": result['timestamp']
        }

    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Errore import modulo analisi: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante l'analisi completa: {str(e)}")

@app.post("/api/estimate-age", response_model=AgeEstimationResult)
async def estimate_age(request: AgeEstimationRequest):
    """
    Stima l'età del volto nell'immagine fornita usando DeepFace
    """
    try:
        print("👤 [AGE ESTIMATION] Richiesta ricevuta")
        
        if not request.image:
            return AgeEstimationResult(
                success=False,
                error='Immagine mancante'
            )
        
        # Decodifica l'immagine base64
        image_data = request.image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        
        # Converti in RGB se necessario
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        print("👤 [AGE ESTIMATION] Immagine decodificata, inizio analisi...")
        
        # Stima l'età usando il modello (restituisce age e confidence)
        estimated_age, confidence = estimate_age_from_image_deepface(image)
        
        print(f"✅ [AGE ESTIMATION] Età stimata: {estimated_age} anni (confidence: {confidence})")
        
        return AgeEstimationResult(
            success=True,
            age=float(estimated_age),
            confidence=float(confidence)
        )
        
    except Exception as e:
        print(f"❌ [AGE ESTIMATION] Errore: {str(e)}")
        return AgeEstimationResult(
            success=False,
            error=str(e)
        )


def estimate_age_from_image_deepface(image: Image.Image) -> Tuple[float, float]:
    """
    Stima l'età da un'immagine PIL usando la libreria DeepFace
    
    Returns:
        Tuple[float, float]: (età stimata, confidenza del rilevamento volto)
    """
    # Verifica che DeepFace sia disponibile
    if not DEEPFACE_AVAILABLE:
        raise Exception("DeepFace non installato. Eseguire: pip install deepface")
    
    try:
        # Converti PIL Image in numpy array
        img_np = np.array(image)
        
        print(f"👤 [AGE ESTIMATION] Immagine shape: {img_np.shape}")
        print(f"👤 [AGE ESTIMATION] Usando detector backend: {AGE_ESTIMATION_DETECTOR_BACKEND}")
        
        # Analizza l'immagine con DeepFace
        # enforce_detection=True solleva un'eccezione se non trova volti
        result = DeepFace.analyze(
            img_np, 
            actions=['age'], 
            enforce_detection=True,
            detector_backend=AGE_ESTIMATION_DETECTOR_BACKEND
        )
        
        # DeepFace può restituire una lista se ci sono più volti
        if isinstance(result, list):
            if len(result) == 0:
                raise ValueError("Nessun volto rilevato nell'immagine")
            # Prendi il primo volto (solitamente il più grande/centrale)
            face_result = result[0]
        else:
            face_result = result
        
        age = face_result['age']
        
        # Estrai la confidence della detection del volto se disponibile
        # DeepFace restituisce 'face_confidence' per alcuni detector backends
        confidence = face_result.get('face_confidence', AGE_ESTIMATION_DEFAULT_CONFIDENCE)
        
        print(f"✅ [AGE ESTIMATION] DeepFace ha stimato l'età: {age} (confidence: {confidence})")
        
        return float(age), float(confidence)
    
    # Gestione specifica delle eccezioni DeepFace
    except ValueError as e:
        # ValueError viene sollevato quando non ci sono volti o dati non validi
        error_msg = str(e)
        # Usa regex per pattern più robusto
        if re.search(r'\b(face|volto)\b', error_msg, re.IGNORECASE):
            raise Exception("Nessun volto rilevato nell'immagine. Assicurati che il volto sia ben visibile e frontale.")
        else:
            raise Exception(f"Dati non validi: {error_msg}")
    
    except AttributeError as e:
        # AttributeError può verificarsi se il modello non è caricato correttamente
        raise Exception(f"Errore caricamento modello DeepFace: {str(e)}")
    
    except Exception as e:
        # Gestione generica per altri errori con pattern matching robusto
        error_msg = str(e)
        
        # Pattern per errori di rilevamento volto
        face_patterns = [
            r'face\s+could\s+not\s+be\s+detected',
            r'no\s+face',
            r'detect.*face',
            r'face.*not.*found'
        ]
        
        # Pattern per errori di modello
        model_patterns = [
            r'\bmodel\b',
            r'\bweight\b',
            r'download',
            r'checkpoint'
        ]
        
        # Controlla pattern di errore volto
        if any(re.search(pattern, error_msg, re.IGNORECASE) for pattern in face_patterns):
            raise Exception("Nessun volto rilevato nell'immagine. Assicurati che il volto sia ben visibile e frontale.")
        
        # Controlla pattern di errore modello
        elif any(re.search(pattern, error_msg, re.IGNORECASE) for pattern in model_patterns):
            raise Exception(f"Errore modello DeepFace: {error_msg}. Potrebbe essere necessario scaricare i modelli.")
        
        # Errore generico
        else:
            raise Exception(f"Errore DeepFace: {error_msg}")

if __name__ == "__main__":
    import uvicorn
    import socket
    
    def find_free_port(start_port=8000, max_attempts=10):
        """Trova una porta libera a partire da start_port"""
        for port in range(start_port, start_port + max_attempts):
            try:
                # Testa se la porta è disponibile
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                return port
            except OSError:
                continue
        return None
    
    try:
        # Forza la porta 8001 per compatibilità con il client
        target_port = 8001
        print(f"🚀 Avvio server API sulla porta {target_port}")
        print(f"📡 Server disponibile su: http://0.0.0.0:{target_port} (tutte le interfacce)")
        print(f"📚 Documentazione API: http://localhost:{target_port}/docs")
        print("🛑 Premi Ctrl+C per fermare il server\n")
        uvicorn.run(app, host="0.0.0.0", port=target_port, log_level="info")
    except KeyboardInterrupt:
        print("\n🛑 Server fermato dall'utente")
    except Exception as e:
        print(f"❌ Errore avvio server: {e}")
        print("💡 Prova a eseguire come amministratore o usa una porta diversa")