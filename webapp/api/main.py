# Webapp Backend API (FastAPI) - Versione Semplificata

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Optional, Dict, Any, Tuple
from contextlib import asynccontextmanager
import cv2
import numpy as np
import math
import json
import base64
from io import BytesIO
from PIL import Image
import uuid
from datetime import datetime
import tempfile
import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

# Carica variabili d'ambiente da .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Variabili d'ambiente caricate da .env")
except ImportError:
    print("⚠️ python-dotenv non installato, usa variabili d'ambiente di sistema")
except Exception as e:
    print(f"⚠️ Errore caricamento .env: {e}")

# Aggiunge il percorso src per importare green_dots_processor
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Aggiunge il percorso per importare eyebrow_overlay.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'face-landmark-localization-master'))

# Istanza globale EyebrowOverlay (lazy loading: carica il modello una sola volta)
_eyebrow_overlay_instance = None
def _get_eyebrow_overlay():
    global _eyebrow_overlay_instance
    if _eyebrow_overlay_instance is None:
        from eyebrow_overlay import EyebrowOverlay
        _eyebrow_overlay_instance = EyebrowOverlay()
    return _eyebrow_overlay_instance

# Import MediaPipe solo quando necessario per evitare conflitti TensorFlow
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: MediaPipe not available: {e}")
    MEDIAPIPE_AVAILABLE = False

# Import del modulo WhiteDotsProcessorV2 (sostituisce GreenDotsProcessor)
# Aggiunge src/ al path per trovare il modulo indipendentemente dalla cwd
_SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src')
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)
try:
    from white_dots_processor_v2 import WhiteDotsProcessorV2
    WHITE_DOTS_AVAILABLE = True
    print("✅ WhiteDotsProcessorV2 importato con successo")
except ImportError as e:
    print(f"⚠️ WhiteDotsProcessorV2 non disponibile: {e}")
    WHITE_DOTS_AVAILABLE = False

# Retrocompatibilità: mantieni alias per codice esistente
GREEN_DOTS_AVAILABLE = WHITE_DOTS_AVAILABLE

# ── Parametri fissi condivisi tra production e debug ─────────────────────────
# Modificare QUI per cambiare i parametri: vengono usati da:
#   • _detect_white_dots_v3()  (default degli argomenti)
#   • process_green_dots_analysis()  (chiamata esplicita)
#   • /api/white-dots/debug-images  (default del modello Pydantic)
#   • finestra debug HTML: slider wdots-perc default=25 → 100-25=75, wdots-sat default=28
WHITE_DOTS_THRESH_PERC   = 75    # percentile luminosità (top 25% = percentile 75)
WHITE_DOTS_SAT_MAX_FRAC  = 0.28  # saturazione max (28% → sat_max_pct=28 nella finestra debug)
WHITE_DOTS_MAX_BLOB      = 2500  # area max blob dopo dilatazione merge 8px (LA0/RA0 raggiungono ~1200–1500px²)

# Import Voice Assistant
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
try:
    from voice.voice_assistant import IsabellaVoiceAssistant
    VOICE_ASSISTANT_AVAILABLE = True
    print("✅ IsabellaVoiceAssistant importato con successo")
except ImportError as e:
    print(f"❌ Warning: IsabellaVoiceAssistant not available: {e}")
    VOICE_ASSISTANT_AVAILABLE = False

# EyebrowOverlay via MediaPipe FaceMesh (dlib non disponibile su questo server)
# L'overlay viene generato interamente con OpenCV+MediaPipe, stessa filosofia
# di eyebrow_overlay.py: fill semi-trasparente + contorno colorato (verde=sx, arancio=dx)
EYEBROW_OVERLAY_AVAILABLE = MEDIAPIPE_AVAILABLE  # dipende solo da MediaPipe

# === INIZIALIZZAZIONE MEDIAPIPE ===

mp_face_mesh = None
face_mesh = None

# === INIZIALIZZAZIONE VOICE ASSISTANT ===
voice_assistant = None

# === DATABASE CONNECTION ===
def get_db_connection():
    """Crea e restituisce una connessione al database PostgreSQL"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("⚠️ DATABASE_URL non configurato")
            return None
        
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"❌ Errore connessione database: {e}")
        return None

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

# Middleware per disabilitare cache completamente
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

# CORS per comunicazione con frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Aggiungi middleware no-cache
app.add_middleware(NoCacheMiddleware)

# Monta i file statici della webapp
webapp_dir = os.path.join(os.path.dirname(__file__), '..')
app.mount("/static", StaticFiles(directory=os.path.join(webapp_dir, "static")), name="static")
app.mount("/templates", StaticFiles(directory=os.path.join(webapp_dir, "templates")), name="templates")

# Monta la cartella best_frontal_frames per video preprocessati
best_frontal_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'best_frontal_frames')
os.makedirs(best_frontal_dir, exist_ok=True)
app.mount("/best_frontal_frames", StaticFiles(directory=best_frontal_dir), name="best_frontal_frames")

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
    score: Optional[float] = None
    eyebrow: Optional[str] = None
    compactness: Optional[float] = None
    h: Optional[int] = None
    s: Optional[int] = None
    v: Optional[int] = None
    anatomical_name: Optional[str] = None

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
    # Parametri legacy (mantenuti per retrocompatibilità, ignorati)
    hue_range: Optional[Tuple[int, int]] = (60, 150)
    value_range: Optional[Tuple[int, int]] = (15, 95)
    cluster_size_range: Optional[Tuple[int, int]] = (9, 40)
    clustering_radius: Optional[int] = 2
    # Parametri per white dots (usati dal frontend sliders)
    saturation_min: Optional[int] = None
    saturation_max: Optional[int] = None
    saturation_max_tail: Optional[int] = None   # dual-pass legacy
    cluster_min_tail: Optional[int] = None       # dual-pass legacy
    value_min: Optional[int] = None
    value_max: Optional[int] = None
    cluster_size_min: Optional[int] = None
    cluster_size_max: Optional[int] = None
    min_distance: Optional[int] = None
    # ── Modalità adattiva ───────────────────────────────────
    adaptive: Optional[bool] = True
    brightness_percentile: Optional[int] = None
    sat_cap: Optional[int] = None
    # Parametri 2-pass (se None usa i valori fissi del backend: 50/30 e 80/25)
    pass1_percentile: Optional[int] = None
    pass1_sat_cap: Optional[int] = None
    pass2_percentile: Optional[int] = None
    pass2_sat_cap: Optional[int] = None

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

# === MODELLI PYDANTIC PER CONTACT FORM ===

class ContactFormRequest(BaseModel):
    firstname: str
    lastname: str
    email: EmailStr
    phone: Optional[str] = ""
    subject: str
    message: str
    newsletter: bool = False
    recaptcha_token: Optional[str] = ""
    timestamp: str

class ContactFormResponse(BaseModel):
    success: bool
    message: str
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
    global face_mesh, mp_face_mesh
    
    # DEBUG: Verifica stato
    print(f"🔍 DEBUG detect_face_landmarks:")
    print(f"   MEDIAPIPE_AVAILABLE: {MEDIAPIPE_AVAILABLE}")
    print(f"   face_mesh: {face_mesh}")
    print(f"   face_mesh is None: {face_mesh is None}")
    
    # Se face_mesh è None, prova a reinizializzare
    if face_mesh is None and MEDIAPIPE_AVAILABLE:
        print("⚠️ face_mesh è None - tentativo reinizializzazione...")
        success = initialize_mediapipe()
        print(f"   Reinizializzazione: {'✅ OK' if success else '❌ FALLITA'}")
    
    if not MEDIAPIPE_AVAILABLE or face_mesh is None:
        raise HTTPException(status_code=500, detail="MediaPipe non disponibile o non inizializzato")
    
    try:
        print(f"🎨 Conversione immagine - shape: {image.shape}, dtype: {image.dtype}")
        
        # Converti BGR to RGB se necessario
        if len(image.shape) == 3 and image.shape[2] == 3:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb_image = image
        
        print(f"🔍 Chiamata face_mesh.process...")
        # Esegui rilevamento
        results = face_mesh.process(rgb_image)
        print(f"✅ face_mesh.process completato - multi_face_landmarks: {results.multi_face_landmarks is not None}")
        
        if not results.multi_face_landmarks:
            print("⚠️ Nessun volto rilevato")
            return []
        
        print(f"📊 Estrazione {len(results.multi_face_landmarks[0].landmark)} landmarks...")
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
        
        print(f"✅ {len(landmarks)} landmarks estratti con successo")
        return landmarks
        
    except Exception as e:
        print(f"❌ ERRORE in detect_face_landmarks: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Modello 3D del volto — convenzione Y-UP (standard dlib/OpenCV tutorials):
        # X: positivo a destra, Y: positivo verso l'alto, Z: positivo verso la camera
        model_points = np.array([
            (0.0,    0.0,    0.0),          # Punta del naso (origine)
            (0.0,  -330.0,  -65.0),         # Mento  (più in basso → Y-)
            (-225.0,  170.0, -135.0),       # Angolo interno occhio sinistro (più in alto → Y+)
            ( 225.0,  170.0, -135.0),       # Angolo interno occhio destro
            (-150.0, -150.0, -125.0),       # Angolo sinistro bocca
            ( 150.0, -150.0, -125.0)        # Angolo destro bocca
        ], dtype=np.float32)
        
        image_points = np.array([
            nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
        ], dtype=np.float32)
        
        # 🔧 DEBUG: Verifica che le coordinate siano in pixel, non normalizzate
        min_x, max_x = min(landmark_array[:, 0]), max(landmark_array[:, 0])
        min_y, max_y = min(landmark_array[:, 1]), max(landmark_array[:, 1])
        
        # Stima dimensioni immagine dai landmarks (CORRETTA PER ENHANCED)
        img_width = max_x - min_x
        img_height = max_y - min_y
        
        # Se le coordinate sembrano normalizzate (0-1), usa dimensioni standard
        if max_x <= 1.0 and max_y <= 1.0:
            img_width = 640
            img_height = 480
        else:
            # Aggiungi margine alle dimensioni reali
            img_width = max(640, img_width * 1.2)
            img_height = max(480, img_height * 1.2)
        
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
            
            # Normalizza il Roll a [-90, 90]
            normalized_roll = roll % 360
            if normalized_roll > 180: normalized_roll -= 360
            if normalized_roll > 90:  normalized_roll = 180 - normalized_roll
            elif normalized_roll < -90: normalized_roll = -180 - normalized_roll
            
            clipped_pitch = float(np.clip(pitch, -90, 90))
            clipped_yaw   = float(np.clip(yaw, -90, 90))
            clipped_roll  = float(np.clip(normalized_roll, -90, 90))
            
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

def load_white_dots_config() -> Dict:
    """Carica parametri di rilevamento dal file di configurazione.
    
    Returns:
        Dict con parametri di detection, clustering e filtering
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config_white_dots_detection.json')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Estrai valori dai parametri strutturati
        detection = config.get('detection_parameters', {})
        clustering = config.get('clustering_parameters', {})
        filtering = config.get('filtering_parameters', {})
        
        params = {
            'saturation_max': detection.get('saturation_max', {}).get('value', 21),
            'saturation_min': detection.get('saturation_min', {}).get('value', 0),
            'value_min': detection.get('value_min', {}).get('value', 62),
            'value_max': detection.get('value_max', {}).get('value', 100),
            'clustering_radius': clustering.get('clustering_radius', {}).get('value', 2),
            'cluster_size_min': clustering.get('cluster_size_range', {}).get('value', [64, 616])[0],
            'cluster_size_max': clustering.get('cluster_size_range', {}).get('value', [64, 616])[1],
            'min_distance': filtering.get('min_distance', {}).get('value', 22),
            'large_cluster_threshold': filtering.get('large_cluster_threshold', {}).get('value', 35)
        }
        
        print(f"✅ Config caricato da {config_path}:")
        print(f"   saturation_max={params['saturation_max']}%, value_min={params['value_min']}%, value_max={params['value_max']}%")
        print(f"   cluster_size=[{params['cluster_size_min']}, {params['cluster_size_max']}]px, radius={params['clustering_radius']}px")
        
        return params
        
    except Exception as e:
        print(f"⚠️ Errore caricamento config: {e}, uso valori ottimali di default")
        # Fallback su valori calibrati con dot_selector su IMG_8116 (lato lungo 2112px)
        # cluster_size_min=64 → scala a 45px @ 2112px  (res_scale=0.698)
        # cluster_size_max=616 → scala a 430px @ 2112px
        return {
            'saturation_max': 21,
            'saturation_min': 0,
            'value_min': 62,
            'value_max': 100,
            'clustering_radius': 2,
            'cluster_size_min': 64,
            'cluster_size_max': 616,
            'min_distance': 22,
            'large_cluster_threshold': 35
        }

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

def sort_points_anatomical(points: List[Dict], is_left: bool) -> List[Dict]:
    """
    Ordina i punti in base a criteri anatomici fissi per garantire mappatura consistente.
    Adattato da green_dots_processor.py per white dots.
    
    Criteri di identificazione:
    1. Coppia B (LB/RB): Punti più esterni
       - LB: x minima (più a sinistra)
       - RB: x massima (più a destra)
    
    2. Coppia C1 (LC1/RC1): Punto più alto E tra i 3 più esterni
       - y minima (più in alto)
       - Deve essere tra i 3 punti con x più estrema
    
    3. Coppia A/A0: Dai 2 punti più interni, quello più basso è A, quello più alto è A0
       - Trovare i 2 punti più interni (verso il centro)
       - Il più basso (y massima) è A
       - Il più alto (y minima) è A0
    
    4. Coppia C (LC/RC): Per esclusione
    
    Ordine finale:
    - Sinistro: [LC1, LA0, LA, LC, LB]
    - Destro: [RC1, RB, RC, RA, RA0]
    
    Se ci sono meno di 5 punti, ordina dall'alto al basso (y crescente).
    """
    if len(points) < 5:
        # Ordinamento semplice per meno di 5 punti
        sorted_pts = sorted(points, key=lambda p: p['y'])
        # Aggiungi nomi semplici
        for i, pt in enumerate(sorted_pts):
            prefix = 'L' if is_left else 'R'
            pt['anatomical_name'] = f"{prefix}{i + 1}"
        return sorted_pts
    
    if is_left:
        # Sopracciglio sinistro
        # 1. B: punto più esterno (x minima)
        b_point = min(points, key=lambda p: p['x'])
        b_point['anatomical_name'] = 'LB'
        
        # 2. C1: tra i 3 punti più esterni, quello più alto
        sorted_by_x = sorted(points, key=lambda p: p['x'])
        three_most_external = sorted_by_x[:3]
        c1_point = min(three_most_external, key=lambda p: p['y'])
        c1_point['anatomical_name'] = 'LC1'
        
        # 3. A e A0: dai 2 punti più interni, quello più basso è A, più alto è A0
        sorted_by_x_desc = sorted(points, key=lambda p: p['x'], reverse=True)
        two_most_internal = sorted_by_x_desc[:2]
        a_point = max(two_most_internal, key=lambda p: p['y'])  # più basso
        a_point['anatomical_name'] = 'LA'
        a0_point = min(two_most_internal, key=lambda p: p['y'])  # più alto
        a0_point['anatomical_name'] = 'LA0'
        print(f"📍 Punti interni Sx: LA=({a_point['x']:.0f},{a_point['y']:.0f}), LA0=({a0_point['x']:.0f},{a0_point['y']:.0f})")
        
        # 4. C: per esclusione
        identified = [b_point, c1_point, a_point, a0_point]
        c_point = [p for p in points if p not in identified][0]
        c_point['anatomical_name'] = 'LC'
        
        # Ordine finale: [LC1, LA0, LA, LC, LB]
        return [c1_point, a0_point, a_point, c_point, b_point]
        
    else:
        # Sopracciglio destro
        # 1. B: punto più esterno (x massima)
        b_point = max(points, key=lambda p: p['x'])
        b_point['anatomical_name'] = 'RB'
        
        # 2. C1: tra i 3 punti più esterni, quello più alto
        sorted_by_x = sorted(points, key=lambda p: p['x'], reverse=True)
        three_most_external = sorted_by_x[:3]
        c1_point = min(three_most_external, key=lambda p: p['y'])
        c1_point['anatomical_name'] = 'RC1'
        
        # 3. A e A0: dai 2 punti più interni, quello più basso è A, più alto è A0
        sorted_by_x_asc = sorted(points, key=lambda p: p['x'])
        two_most_internal = sorted_by_x_asc[:2]
        a_point = max(two_most_internal, key=lambda p: p['y'])  # più basso
        a_point['anatomical_name'] = 'RA'
        a0_point = min(two_most_internal, key=lambda p: p['y'])  # più alto
        a0_point['anatomical_name'] = 'RA0'
        
        # 4. C: per esclusione
        identified = [b_point, c1_point, a_point, a0_point]
        c_point = [p for p in points if p not in identified][0]
        c_point['anatomical_name'] = 'RC'
        
        # Ordine finale: [RC1, RB, RC, RA, RA0]
        return [c1_point, b_point, c_point, a_point, a0_point]

def _detect_white_dots_v3(img_bgr: np.ndarray,
                         thresh_perc: int   = WHITE_DOTS_THRESH_PERC,
                         sat_max_frac: float = WHITE_DOTS_SAT_MAX_FRAC) -> dict:
    """
    Rileva i 10 puntini bianchi del tatuaggio sopracciglio.

    Flusso semplificato (3 passi):
    1. eyebrows.py (dlib) → maschera binaria sopracciglio sx e dx.
    2. Striscia di 50px centrata sul perimetro dlib:
         expanded  = dilate(mask, 25px)   → 25px fuori
         shrunk    = erode(mask,  25px)   → 25px dentro
         strip     = expanded − shrunk
    3. Blob bianchi brillanti nella striscia → top-5 per lato.

    Non genera overlay né audio.
    """
    try:
        from eyebrows import extract_eyebrows_from_array
    except ImportError:
        return {'error': 'Modulo eyebrows (dlib) non disponibile.', 'dots': [], 'total_white_pixels': 0}

    _dat = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..',
        'face-landmark-localization-master', 'shape_predictor_68_face_landmarks.dat'
    ))

    # Passo 1 – maschere dlib (identiche a "Sim. Sopracciglia")
    res_dlib = extract_eyebrows_from_array(img_bgr, predictor_path=_dat)
    if not res_dlib["face_detected"]:
        return {'error': 'Volto non rilevato da dlib.', 'dots': [], 'total_white_pixels': 0}

    h, w = img_bgr.shape[:2]
    hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    v_ch = hsv[:, :, 2].astype(np.float32)
    s_ch = hsv[:, :, 1].astype(np.float32)

    # Striscia simmetrica: 25px fuori + 25px dentro al perimetro dlib.
    OUTER_PX = 25
    INNER_PX = 25
    k_outer = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OUTER_PX*2+1, OUTER_PX*2+1))
    k_inner = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (INNER_PX*2+1, INNER_PX*2+1))
    # Kernel di merge: fonde pixel adiacenti per evitare frammentazione
    MERGE_PX = 8
    k_merge  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MERGE_PX*2+1, MERGE_PX*2+1))

    all_dots      = []
    left_polygon  = None
    right_polygon = None

    for side, mask in [('left', res_dlib['left_mask']), ('right', res_dlib['right_mask'])]:
        if not np.any(mask):
            continue

        # Passo 2 – striscia simmetrica: 25px fuori + 25px dentro
        expanded   = cv2.dilate(mask, k_outer, iterations=1)
        shrunk     = cv2.erode(mask,  k_inner, iterations=1)
        strip_mask = cv2.subtract(expanded, shrunk)

        # Salva contorno espanso per l'overlay del frontend
        cnts, _ = cv2.findContours(expanded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            polygon = max(cnts, key=cv2.contourArea).squeeze()
            if side == 'left':
                left_polygon = polygon
            else:
                right_polygon = polygon

        # Passo 3 – pixel bianchi nella striscia
        strip_v  = v_ch[strip_mask > 0]
        if len(strip_v) < 10:
            continue

        # Soglia adattiva: configurabile (default top 25%, sat 28%)
        thresh_v = float(np.percentile(strip_v, thresh_perc))
        thresh_s = sat_max_frac * 255

        bright = np.zeros((h, w), dtype=np.uint8)
        bright[(v_ch >= thresh_v) & (s_ch <= thresh_s) & (strip_mask > 0)] = 255

        # Fondi pixel adiacenti per evitare che un singolo punto bianco
        # venga spezzato in più blob separati (causa di selezione errata nel top-5)
        bright_m = cv2.dilate(bright, k_merge, iterations=1)

        # Connected components sul merged → un blob = un punto bianco
        MAX_BLOB = WHITE_DOTS_MAX_BLOB  # dilation merge 8px gonfia i blob: LA0/RA0 arrivano a ~1500px²
        n_lbl, lbl_map, stats_cc, centroids = cv2.connectedComponentsWithStats(bright_m, 8)
        candidates = []
        for lbl in range(1, n_lbl):
            area = int(stats_cc[lbl, cv2.CC_STAT_AREA])
            if area < 3 or area > MAX_BLOB:
                continue
            cx     = float(centroids[lbl, 0])
            cy     = float(centroids[lbl, 1])
            b_mask = lbl_map == lbl
            # Valuta luminosità e saturazione sui pixel del blob (sul merged)
            mean_v = float(np.mean(v_ch[b_mask]))
            mean_s = float(np.mean(s_ch[b_mask]))
            # Score: luminosità media, penalizza blob troppo grandi (pelle)
            score = round(mean_v * (1.0 - area / (MAX_BLOB * 2.0)), 2)
            candidates.append({
                'x':           int(round(cx)),
                'y':           int(round(cy)),
                'size':        area,
                'score':       max(0.0, score),
                'compactness': 0.0,
                'h':           0,
                's':           int(round(mean_s / 255.0 * 100)),
                'v':           int(round(mean_v / 255.0 * 100)),
            })

        candidates.sort(key=lambda d: -d['score'])
        all_dots.extend(candidates[:5])
        print(f"🔍 v3-strip [{side}]: {len(candidates)} candidati (merged) → top-{min(5, len(candidates))} selezionati")

    return {
        'dots':               all_dots,
        'total_white_pixels': int(np.sum(v_ch > 153)),
        'left_polygon':       left_polygon,
        'right_polygon':      right_polygon,
    }


def _select_best_5_for_eyebrow(dots: list, is_left: bool) -> list:
    """
    Seleziona i 5 dots migliori per un sopracciglio garantendo che il punto
    più esterno (LB/RB) sia SEMPRE incluso, indipendentemente dal suo score.
    LB/RB è spesso il puntino più piccolo e perciò ha score basso, ma è
    fondamentale per l'ordinamento anatomico corretto.
    """
    if len(dots) <= 5:
        return dots
    if is_left:
        extreme = min(dots, key=lambda p: p['x'])   # LB: x minima
    else:
        extreme = max(dots, key=lambda p: p['x'])   # RB: x massima
    others = [d for d in dots if d is not extreme]
    top4 = sorted(others, key=lambda d: d['score'], reverse=True)[:4]
    return [extreme] + top4


def process_green_dots_analysis(
    image_base64: str,
    # Tutti i parametri legacy sotto sono ignorati: il backend usa _detect_white_dots_v3
    # con parametri fissi (OUTER_PX=25, INNER_PX=25, thresh_perc=75, sat_max_frac=0.28).
    # Mantenuti solo per retrocompatibilità con i caller esistenti.
    **kwargs
) -> Dict:
    """
    Rileva i puntini bianchi del tatuaggio sopracciglio via _detect_white_dots_v3 (dlib perimeter strip).
    Tutti i parametri HSV/cluster/pass1/pass2 sono ignorati: usa valori fissi hardcoded.
    """
    if not WHITE_DOTS_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Modulo WhiteDotsProcessorV2 non disponibile. Verificare l'installazione delle dipendenze."
        )

    try:

        pil_image = decode_base64_to_pil_image(image_base64)

        # ── Rilevamento via dlib perimeter strip ──────────────────────────────
        # Usa le stesse maschere del pulsante "Sim. Sopracciglia",
        # le espande per includere i punti sul bordo, poi rileva blob bianchi.
        img_array = np.array(pil_image)
        if img_array.ndim == 3 and img_array.shape[2] == 4:
            img_bgr_v3 = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        else:
            img_bgr_v3 = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        det_v3 = _detect_white_dots_v3(img_bgr_v3,
                                        thresh_perc=WHITE_DOTS_THRESH_PERC,
                                        sat_max_frac=WHITE_DOTS_SAT_MAX_FRAC)

        if 'error' in det_v3:
            return {
                'success': False,
                'error': det_v3['error'],
                'detection_results': {
                    'dots': [], 'total_dots': 0, 'total_green_pixels': 0,
                    'image_size': [pil_image.width, pil_image.height], 'parameters': {}
                }
            }

        results = {
            'dots':               det_v3['dots'],
            'total_white_pixels': det_v3['total_white_pixels'],
            'total_clusters':     len(det_v3['dots']),
            'image_size':         (pil_image.width, pil_image.height),
            'parameters':         {'adaptive': True, 'method': 'dlib_perimeter_v3'},
            'left_polygon':       det_v3.get('left_polygon'),
            'right_polygon':      det_v3.get('right_polygon'),
        }
        print(f"✅ [v3] Totale punti rilevati: {len(results['dots'])}/10")

        # Adatta al formato atteso dal frontend
        
        if 'error' in results:
            return {
                'success': False,
                'error': results['error'],
                'detection_results': {'dots': [], 'total_dots': 0, 'total_green_pixels': 0,
                                     'image_size': [0, 0], 'parameters': {}}
            }
        
        # Converti formato dots per compatibilità (mantieni tutti i campi dal processore)
        dots = results.get('dots', [])
        print(f"🔍 DEBUG: Dots ricevuti dal processor: {len(dots)}")
        if len(dots) > 0:
            print(f"   Sample dot: {dots[0]}")
        
        # DIVISIONE SEMPLICE: usa centro verticale dell'immagine
        image_width = pil_image.width
        middle_x = image_width // 2
        
        formatted_dots = []
        for dot in dots:
            # Determina eyebrow in base alla posizione X rispetto al centro
            if dot['x'] < middle_x:
                eyebrow_side = 'left'
            else:
                eyebrow_side = 'right'
            
            formatted_dots.append({
                'x': dot['x'],
                'y': dot['y'],
                'size': dot['size'],
                'score': dot.get('score', dot['size'] * 1.5),
                'eyebrow': eyebrow_side,
                'compactness': dot.get('compactness', 0),
                'h': dot.get('h', 0),
                's': dot.get('s', 0),
                'v': dot.get('v', 0)
            })
        
        print(f"✅ Formatted dots: {len(formatted_dots)}")
        print(f"   📍 Centro verticale immagine: x={middle_x} (width={image_width})")
        if len(formatted_dots) > 0:
            print(f"   📌 Sample formatted dot with eyebrow: {formatted_dots[0]}")
        
        # Dividi in Sx/Dx per compatibilità con frontend
        left_dots = [d for d in formatted_dots if d.get('eyebrow') == 'left']
        right_dots = [d for d in formatted_dots if d.get('eyebrow') == 'right']
        unknown_dots = [d for d in formatted_dots if d.get('eyebrow') not in ['left', 'right']]

        left_dots  = _select_best_5_for_eyebrow(left_dots,  is_left=True)
        right_dots = _select_best_5_for_eyebrow(right_dots, is_left=False)

        # ORDINAMENTO ANATOMICO: usa criteri fissi LC1, LA0, LA, LC, LB (sinistra) e RC1, RB, RC, RA, RA0 (destra)
        left_dots = sort_points_anatomical(left_dots, is_left=True)
        right_dots = sort_points_anatomical(right_dots, is_left=False)
        
        print(f"📊 Left dots: {len(left_dots)}, Right dots: {len(right_dots)}, Unknown: {len(unknown_dots)}")
        if len(left_dots) > 0:
            print(f"   📍 Left ordinato: {[(d.get('anatomical_name', '?'), d['y']) for d in left_dots]}")
        if len(right_dots) > 0:
            print(f"   📍 Right ordinato: {[(d.get('anatomical_name', '?'), d['y']) for d in right_dots]}")
        if len(unknown_dots) > 0:
            print(f"   ⚠️ Unknown dots eyebrow values: {[d.get('eyebrow') for d in unknown_dots]}")
        
        # Calcola statistiche area (approssimativa da somma cluster sizes)
        left_area = sum(d['size'] for d in left_dots) if left_dots else 0
        right_area = sum(d['size'] for d in right_dots) if right_dots else 0
        total_area = left_area + right_area
        
        # Calcola perimetri approssimativi (convex hull semplificato)
        left_perimeter = calculate_approximate_perimeter(left_dots) if len(left_dots) >= 3 else 0
        right_perimeter = calculate_approximate_perimeter(right_dots) if len(right_dots) >= 3 else 0
        
        # Estrai poligoni maschere per disegnare contorni
        left_polygon = results.get('left_polygon', None)
        right_polygon = results.get('right_polygon', None)
        
        # Genera overlay con cerchi, labels E contorni maschere
        overlay_img = generate_white_dots_overlay(
            pil_image.size, 
            formatted_dots, 
            left_polygon=left_polygon, 
            right_polygon=right_polygon
        )
        overlay_base64 = convert_pil_image_to_base64(overlay_img)
        
        # Struttura risposta compatibile con frontend esistente
        adapted_results = {
            'success': True,
            'detection_results': {
                'dots': formatted_dots,
                'total_dots': len(formatted_dots),
                'total_green_pixels': results.get('total_white_pixels', 0),  # Alias
                'image_size': list(pil_image.size),
                'parameters': results.get('parameters', {})
            },
            'config_parameters': {'method': 'dlib_perimeter_v3',
                                  'thresh_perc': WHITE_DOTS_THRESH_PERC,
                                  'sat_max_frac': WHITE_DOTS_SAT_MAX_FRAC},
            'groups': {
                'Sx': left_dots,
                'Dx': right_dots
            },
            'coordinates': {
                'Sx': [(d['x'], d['y']) for d in left_dots],
                'Dx': [(d['x'], d['y']) for d in right_dots]
            },
            'statistics': {
                'left': {
                    'count': len(left_dots),
                    'area': float(left_area),
                    'perimeter': float(left_perimeter)
                },
                'right': {
                    'count': len(right_dots),
                    'area': float(right_area),
                    'perimeter': float(right_perimeter)
                },
                'combined': {
                    'total_vertices': len(formatted_dots),
                    'total_area': float(total_area)
                }
            },
            'overlay_base64': overlay_base64,
            'image_size': list(pil_image.size)
        }
        
        print(f"📤 Risposta al frontend:")
        print(f"   detection_results.dots: {len(adapted_results['detection_results']['dots'])}")
        print(f"   groups.Sx: {len(adapted_results['groups']['Sx'])}")
        print(f"   groups.Dx: {len(adapted_results['groups']['Dx'])}")
        print(f"   coordinates.Sx: {len(adapted_results['coordinates']['Sx'])}")
        print(f"   coordinates.Dx: {len(adapted_results['coordinates']['Dx'])}")
        
        return adapted_results
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore durante l'analisi white dots: {str(e)}")


def create_curved_eyebrow_polygon(points: List[Tuple[float, float]], is_left: bool, arc_segments: int = 20) -> List[Tuple[float, float]]:
    """
    Crea un poligono con arco curvato convesso tra LB-LC1 (sinistro) o RB-RC1 (destro).
    Il raggio di curvatura è pari alla distanza tra i punti da collegare.
    
    Args:
        points: Lista di 5 punti nell'ordine [LA, LC, LB, LC1, LA0] o [RA, RC, RB, RC1, RA0]
        is_left: True per sopracciglio sinistro, False per destro
        arc_segments: Numero di segmenti per l'arco
    
    Returns:
        Lista di punti con arco Bezier tra LB-LC1 (o RB-RC1)
    """
    if len(points) != 5:
        return points
    
    # L'arco è sempre tra l'indice 2 (LB/RB) e 3 (LC1/RC1)
    start_point = points[2]  # LB o RB
    end_point = points[3]    # LC1 o RC1
    
    # Calcola distanza tra i punti
    dx = end_point[0] - start_point[0]
    dy = end_point[1] - start_point[1]
    distance = (dx**2 + dy**2)**0.5
    
    if distance == 0:
        return points
    
    # Punto medio
    mid_x = (start_point[0] + end_point[0]) / 2
    mid_y = (start_point[1] + end_point[1]) / 2
    
    # Vettore perpendicolare verso l'esterno
    perp_x = -dy / distance
    perp_y = dx / distance
    
    # CORREZIONE: Per curvatura convessa verso l'esterno del poligono
    # Sinistro (LB→LC1): curva verso sinistra (-), Destro (RB→RC1): curva verso destra (+)
    direction = -1 if is_left else 1
    
    # Punto di controllo Bezier con raggio ridotto al 45% della distanza
    curve_radius = distance * 0.45
    control_x = mid_x + direction * perp_x * curve_radius
    control_y = mid_y + direction * perp_y * curve_radius
    
    # Genera punti lungo la curva di Bezier quadratica
    arc_points = []
    for i in range(arc_segments + 1):
        t = i / arc_segments
        one_minus_t = 1 - t
        x = (one_minus_t**2 * start_point[0] + 
             2 * one_minus_t * t * control_x + 
             t**2 * end_point[0])
        y = (one_minus_t**2 * start_point[1] + 
             2 * one_minus_t * t * control_y + 
             t**2 * end_point[1])
        arc_points.append((x, y))
    
    # Costruisci poligono: LA, LC, [arco da LB a LC1], LA0
    result = [points[0], points[1]] + arc_points + [points[4]]
    return result


def generate_white_dots_overlay(
    image_size: Tuple[int, int],
    dots: List[Dict],
    left_polygon: np.ndarray = None,
    right_polygon: np.ndarray = None
) -> Image.Image:
    """
    Genera overlay con:
    - Poligoni colorati semi-trasparenti quando ci sono esattamente 5 punti per lato
    - Cerchi colorati sui puntini con etichette ID
    - Colori dei cerchi basati sulla dimensione del cluster

    Significato colori cerchi:
    - VERDE: Cluster piccolo (≤15px) - dimensione ideale, puntino ben definito
    - GIALLO: Cluster medio (16-25px) - accettabile ma più grande del normale
    - ARANCIONE: Cluster grande (26-35px) - potrebbe essere un'area riflettente
    - ROSSO: Cluster molto grande (>35px) - sospetto, probabilmente non è un puntino
    """
    from PIL import ImageDraw, ImageFont

    # Crea immagine trasparente
    overlay = Image.new('RGBA', image_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Prova a caricare un font, fallback su default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()

    # Separa puntini per sopracciglio
    left_dots_list = [d for d in dots if d.get('eyebrow') == 'left']
    right_dots_list = [d for d in dots if d.get('eyebrow') == 'right']

    # ========== DISEGNA POLIGONI AREA SOPRACCIGLIARE (se 5 punti per lato) ==========

    # Colori per i poligoni delle aree sopracciliari
    LEFT_AREA_COLOR = (0, 200, 255, 60)    # Ciano trasparente per sinistra
    LEFT_BORDER_COLOR = (0, 200, 255, 180)  # Ciano più opaco per bordo
    RIGHT_AREA_COLOR = (255, 100, 50, 60)   # Arancione trasparente per destra
    RIGHT_BORDER_COLOR = (255, 100, 50, 180) # Arancione più opaco per bordo

    # Disegna poligono SINISTRO SOLO se ci sono esattamente 5 punti con tutti i nomi anatomici
    if len(left_dots_list) == 5:
        try:
            # Ordine anatomico corretto per perimetro sopracciglio SINISTRO:
            # Partendo da LA (esterno), verso LC (centro alto), LB (basso), LC1 (interno alto), LA0 (interno)
            # Questo forma un pentagono che segue il contorno del sopracciglio
            LEFT_PERIMETER_ORDER = ['LA', 'LC', 'LB', 'LC1', 'LA0']

            # Crea dizionario nome → coordinate
            left_dots_by_name = {d.get('anatomical_name'): (d['x'], d['y']) for d in left_dots_list if d.get('anatomical_name')}

            # Verifica che tutti i punti anatomici siano presenti
            if all(name in left_dots_by_name for name in LEFT_PERIMETER_ORDER):
                # Ordina secondo il perimetro anatomico
                left_points_sorted = [left_dots_by_name[name] for name in LEFT_PERIMETER_ORDER]
                # Crea poligono con curva convessa tra LB-LC1
                left_points_curved = create_curved_eyebrow_polygon(left_points_sorted, is_left=True)
                draw.polygon(left_points_curved, fill=LEFT_AREA_COLOR, outline=LEFT_BORDER_COLOR, width=3)
                print(f"✅ Poligono SINISTRO disegnato con ordine: {LEFT_PERIMETER_ORDER} (con curva LB-LC1)")
            else:
                # Non disegnare il poligono se mancano i nomi anatomici
                missing = [n for n in LEFT_PERIMETER_ORDER if n not in left_dots_by_name]
                print(f"⚠️ Poligono SINISTRO NON disegnato - mancano i nomi anatomici: {missing}")
        except Exception as e:
            print(f"⚠️ Errore disegno poligono sinistro: {e}")
            import traceback
            traceback.print_exc()

    # Disegna poligono DESTRO SOLO se ci sono esattamente 5 punti con tutti i nomi anatomici
    if len(right_dots_list) == 5:
        try:
            # Ordine anatomico corretto per perimetro: RA → RC → RB → RC1 → RA0 → (chiude su RA)
            RIGHT_PERIMETER_ORDER = ['RA', 'RC', 'RB', 'RC1', 'RA0']

            # Crea dizionario nome → coordinate
            right_dots_by_name = {d.get('anatomical_name'): (d['x'], d['y']) for d in right_dots_list if d.get('anatomical_name')}

            # Verifica che tutti i punti anatomici siano presenti
            if all(name in right_dots_by_name for name in RIGHT_PERIMETER_ORDER):
                # Ordina secondo il perimetro anatomico
                right_points_sorted = [right_dots_by_name[name] for name in RIGHT_PERIMETER_ORDER]
                # Crea poligono con curva convessa tra RB-RC1
                right_points_curved = create_curved_eyebrow_polygon(right_points_sorted, is_left=False)
                draw.polygon(right_points_curved, fill=RIGHT_AREA_COLOR, outline=RIGHT_BORDER_COLOR, width=3)
                print(f"✅ Poligono DESTRO disegnato con ordine: {RIGHT_PERIMETER_ORDER} (con curva RB-RC1)")
            else:
                # Non disegnare il poligono se mancano i nomi anatomici
                missing = [n for n in RIGHT_PERIMETER_ORDER if n not in right_dots_by_name]
                print(f"⚠️ Poligono DESTRO NON disegnato - mancano i nomi anatomici: {missing}")
        except Exception as e:
            print(f"⚠️ Errore disegno poligono destro: {e}")

    # ========== DISEGNA CERCHI E ETICHETTE SUI PUNTINI ==========

    # Prepara lista con indici per etichette
    left_dots = [(i, d) for i, d in enumerate(dots) if d.get('eyebrow') == 'left']
    right_dots = [(i, d) for i, d in enumerate(dots) if d.get('eyebrow') == 'right']

    # Disegna cerchi e ID per ogni puntino (sopra i poligoni)
    for idx, (original_idx, dot) in enumerate(left_dots + right_dots):
        x, y = dot['x'], dot['y']
        size = dot.get('size', 10)
        eyebrow = dot.get('eyebrow', 'unknown')

        # USA NOME ANATOMICO se presente, altrimenti fallback su numerazione semplice
        if 'anatomical_name' in dot and dot['anatomical_name']:
            label = dot['anatomical_name']
        else:
            # Fallback per retrocompatibilità
            if eyebrow == 'left':
                local_idx = [i for i, (_, d) in enumerate(left_dots) if d == dot][0]
                label = f"L{local_idx + 1}"
            else:
                local_idx = [i for i, (_, d) in enumerate(right_dots) if d == dot][0]
                label = f"R{local_idx + 1}"

        # Colore basato su dimensione del cluster
        # VERDE: ≤15px (ideale), GIALLO: 16-25px, ARANCIONE: 26-35px, ROSSO: >35px
        if size > 35:
            color = (255, 0, 0, 200)      # Rosso - cluster troppo grande, sospetto
        elif size > 25:
            color = (255, 165, 0, 200)    # Arancione - cluster grande
        elif size > 15:
            color = (255, 255, 0, 200)    # Giallo - cluster medio
        else:
            color = (0, 255, 0, 200)      # Verde - cluster piccolo, ideale

        # Raggio cerchio proporzionale a size
        radius = int(np.sqrt(size / np.pi)) + 8

        # Cerchio
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                    outline=color, width=4)

        # Centro
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)

        # Etichetta ID (sopra il puntino)
        # Sfondo semi-trasparente per leggibilità
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        label_x = x - text_width // 2
        label_y = y - radius - text_height - 5

        # Rettangolo sfondo
        padding = 3
        draw.rectangle(
            [label_x - padding, label_y - padding,
             label_x + text_width + padding, label_y + text_height + padding],
            fill=(0, 0, 0, 180)
        )

        # Testo ID
        draw.text((label_x, label_y), label, fill=(255, 255, 255, 255), font=font)

    return overlay


def calculate_approximate_perimeter(dots: List[Dict]) -> float:
    """Calcola perimetro approssimativo usando convex hull dei punti."""
    if len(dots) < 3:
        return 0.0
    
    try:
        from scipy.spatial import ConvexHull
        
        # Estrai coordinate (x, y)
        points = np.array([[d['x'], d['y']] for d in dots])
        
        # Calcola convex hull
        hull = ConvexHull(points)
        
        # Perimetro = somma distanze tra vertici consecutivi
        perimeter = 0.0
        vertices = hull.vertices
        for i in range(len(vertices)):
            p1 = points[vertices[i]]
            p2 = points[vertices[(i + 1) % len(vertices)]]
            distance = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            perimeter += distance
        
        return perimeter
        
    except ImportError:
        # Fallback: usa bounding box se scipy non disponibile
        xs = [d['x'] for d in dots]
        ys = [d['y'] for d in dots]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        return 2 * (width + height)
    except Exception as e:
        print(f"⚠️ Errore calcolo perimetro: {e}")
        return 0.0

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

@app.get("/landing.html")
async def serve_landing():
    """Serve la landing page"""
    landing_path = os.path.join(os.path.dirname(__file__), '..', 'landing.html')
    if os.path.exists(landing_path):
        return FileResponse(landing_path)
    raise HTTPException(status_code=404, detail="landing.html not found")

@app.get("/contatti.html")
async def serve_contatti():
    """Serve la pagina contatti"""
    contatti_path = os.path.join(os.path.dirname(__file__), '..', 'contatti.html')
    if os.path.exists(contatti_path):
        return FileResponse(contatti_path)
    raise HTTPException(status_code=404, detail="contatti.html not found")

@app.get("/health")
async def health_check():
    """Check salute sistema."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mediapipe": "available" if MEDIAPIPE_AVAILABLE else "mock_mode",
        "white_dots": "available" if WHITE_DOTS_AVAILABLE else "not_available",
        "green_dots": "available (legacy)" if WHITE_DOTS_AVAILABLE else "not_available",
        "version": "2.0.0",  # v2 con WhiteDotsProcessorV2
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

@app.get("/api/health-check")
async def full_health_check():
    """
    Verifica completa dello stato di tutti i servizi necessari.
    Controlla: API server, WebApp, WebSocket, Nginx
    """
    import socket
    import subprocess
    
    services_status = {}
    
    # 1. API Server (auto-check - se questo risponde, è operativo)
    services_status['api_server'] = {
        'name': 'API Server',
        'status': 'operational',
        'port': 8001,
        'message': 'API server risponde correttamente'
    }
    
    # 2. WebSocket Server (porta tipica per websocket_frame_api.py)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', 8765))  # Porta WebSocket tipica
        sock.close()
        
        if result == 0:
            services_status['websocket'] = {
                'name': 'WebSocket Server',
                'status': 'operational',
                'port': 8765,
                'message': 'WebSocket server in ascolto'
            }
        else:
            services_status['websocket'] = {
                'name': 'WebSocket Server',
                'status': 'down',
                'port': 8765,
                'message': 'WebSocket server non risponde'
            }
    except Exception as e:
        services_status['websocket'] = {
            'name': 'WebSocket Server',
            'status': 'down',
            'port': 8765,
            'message': f'Errore: {str(e)}'
        }
    
    # 3. WebApp (start_webapp.py - verifica processo)
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'start_webapp.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            services_status['webapp'] = {
                'name': 'Web Application',
                'status': 'operational',
                'message': 'WebApp in esecuzione'
            }
        else:
            services_status['webapp'] = {
                'name': 'Web Application',
                'status': 'down',
                'message': 'WebApp non in esecuzione'
            }
    except Exception as e:
        services_status['webapp'] = {
            'name': 'Web Application',
            'status': 'down',
            'message': f'Errore: {str(e)}'
        }
    
    # 4. Nginx
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'nginx'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip() == 'active':
            services_status['nginx'] = {
                'name': 'Nginx Web Server',
                'status': 'operational',
                'message': 'Nginx attivo e funzionante'
            }
        else:
            services_status['nginx'] = {
                'name': 'Nginx Web Server',
                'status': 'down',
                'message': 'Nginx non attivo'
            }
    except Exception as e:
        services_status['nginx'] = {
            'name': 'Nginx Web Server',
            'status': 'down',
            'message': f'Errore: {str(e)}'
        }
    
    # Determina lo stato complessivo
    all_operational = all(s['status'] == 'operational' for s in services_status.values())
    any_down = any(s['status'] == 'down' for s in services_status.values())
    
    if all_operational:
        overall_status = 'operational'
    elif any_down:
        overall_status = 'down'
    else:
        overall_status = 'degraded'
    
    return {
        'overall_status': overall_status,
        'timestamp': datetime.now().isoformat(),
        'services': services_status,
        'summary': {
            'total': len(services_status),
            'operational': sum(1 for s in services_status.values() if s['status'] == 'operational'),
            'down': sum(1 for s in services_status.values() if s['status'] == 'down')
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
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        error_detail = f"Errore durante l'analisi: {str(e)}"
        full_traceback = traceback.format_exc()
        
        # Scrivi l'errore in un file per debug
        with open('/tmp/analyze_error.log', 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write(f"Error: {error_detail}\n")
            f.write(f"Traceback:\n{full_traceback}\n")
        
        logger.error(f"❌ ERRORE /api/analyze: {error_detail}\n{full_traceback}")
        raise HTTPException(status_code=500, detail=error_detail)

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
    
    ✅ OTTIMIZZAZIONE: Accetta anche singole immagini JPEG/PNG come "video" (frame centrale)
    """
    try:
        print(f"🎥 Analisi video iniziata: {file.filename}")
        
        # Leggi il file video
        content = await file.read()
        print(f"📁 File letto: {len(content)} bytes")
        
        # ✅ OTTIMIZZAZIONE: Se è un'immagine JPEG/PNG, analizzala direttamente
        if file.content_type and file.content_type.startswith('image/'):
            print(f"🖼️ Rilevato singolo frame (immagine), analisi diretta...")
            
            # Decodifica immagine
            nparr = np.frombuffer(content, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                raise HTTPException(status_code=400, detail="Impossibile decodificare l'immagine")
            
            best_landmarks = []
            best_score = 0.5
            
            if MEDIAPIPE_AVAILABLE and face_mesh:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb_frame)
                
                if results.multi_face_landmarks:
                    landmarks_3d = results.multi_face_landmarks[0]
                    best_score = calculate_frontality_score_from_landmarks(landmarks_3d, frame.shape)
                    
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
            
            # Converti frame in base64
            _, buffer = cv2.imencode('.jpg', frame)
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            
            print(f"✅ Immagine analizzata con score: {best_score}")
            
            return {
                "success": True,
                "best_frame": frame_b64,
                "landmarks": best_landmarks,
                "score": best_score,
                "total_frames": 1,
                "analyzed_frames": 1,
                "timestamp": datetime.now().isoformat()
            }
        
        # Altrimenti procedi con analisi video normale
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
        skip_frames = max(1, int(fps / 10))  # ✅ OTTIMIZZATO: Analizza 10 frame al secondo (era 5) per velocità
        
        # ✅ LIMITA DURATA: Analizza max 30 secondi per video molto lunghi
        max_frames_to_analyze = int(min(total_frames, fps * 30))
        
        print(f"🎬 Video info: {total_frames} frames, {fps} FPS, skip ogni {skip_frames} frames, max {max_frames_to_analyze} frames")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            
            # ✅ LIMITA DURATA: Ferma analisi dopo max_frames_to_analyze
            if frame_count > max_frames_to_analyze:
                print(f"⏸️ Limite frame raggiunto: {max_frames_to_analyze}")
                break
            
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

# === API ENDPOINT PER PREPROCESSING VIDEO ===

@app.post("/api/preprocess-video")
async def preprocess_video(file: UploadFile = File(...)):
    """
    Preprocessa video riducendolo a larghezza 464px (altezza proporzionale per mantenere aspect ratio).
    Salva il video preprocessato e restituisce un URL temporaneo.
    Target: ~1.5MB, H264, bitrate 1500k
    """
    import subprocess
    import hashlib
    from datetime import datetime
    
    try:
        print(f"🎬 Preprocessing video: {file.filename}")
        
        # Leggi contenuto originale
        content = await file.read()
        original_size_mb = len(content) / (1024*1024)
        print(f"📦 Dimensione originale: {original_size_mb:.2f} MB")
        
        # File temporanei
        with tempfile.NamedTemporaryFile(delete=False, suffix='_input.mp4') as tmp_input:
            tmp_input.write(content)
            input_path = tmp_input.name
        
        # Genera nome univoco per file output
        file_hash = hashlib.md5((file.filename + str(datetime.now())).encode()).hexdigest()[:12]
        output_filename = f"preprocessed_{file_hash}.mp4"
        
        # Salva nella cartella best_frontal_frames (già esistente)
        output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'best_frontal_frames')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        
        # Comando ffmpeg per ridimensionare e comprimere
        # Target: larghezza 464px, altezza proporzionale (-2 forza dimensione pari per H264)
        # H264, bitrate 1500k, audio rimosso
        ffmpeg_cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', 'scale=464:-2',  # Larghezza 464px, altezza pari (richiesto da libx264)
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-b:v', '1500k',
            '-maxrate', '1500k',
            '-bufsize', '3000k',
            '-an',  # Rimuovi audio
            '-movflags', '+faststart',  # Ottimizzazione streaming
            '-y',  # Sovrascrivi se esiste
            output_path
        ]
        
        print(f"🔧 Esecuzione ffmpeg...")
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=60  # Max 60 secondi
        )
        
        if result.returncode != 0:
            print(f"❌ Errore ffmpeg: {result.stderr}")
            # Cleanup
            try:
                os.remove(input_path)
                if os.path.exists(output_path):
                    os.remove(output_path)
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Errore preprocessing: {result.stderr[:200]}")
        
        # Cleanup file input temporaneo
        try:
            os.remove(input_path)
        except Exception as e:
            print(f"⚠️ Errore cleanup input: {e}")
        
        # Ottieni dimensione file output
        output_size_mb = os.path.getsize(output_path) / (1024*1024)
        compression_ratio = (1 - output_size_mb / original_size_mb) * 100
        
        print(f"✅ Video preprocessato:")
        print(f"   Dimensione finale: {output_size_mb:.2f} MB")
        print(f"   Compressione: {compression_ratio:.1f}%")
        print(f"   Salvato in: {output_path}")
        
        # Ritorna URL per scaricare il video preprocessato
        video_url = f"/best_frontal_frames/{output_filename}"
        
        return {
            "success": True,
            "original_size_mb": original_size_mb,
            "processed_size_mb": output_size_mb,
            "compression_ratio": f"{compression_ratio:.1f}%",
            "video_url": video_url,
            "mime_type": "video/mp4"
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Timeout preprocessing video (>60s)")
    except Exception as e:
        print(f"❌ Errore preprocessing: {e}")
        raise HTTPException(status_code=500, detail=f"Errore preprocessing: {str(e)}")

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

        # Log parametri ricevuti dal frontend
        if request.saturation_max is not None or request.value_min is not None:
            print(f"⚙️ Parametri custom dal frontend: sat_max={request.saturation_max}, val_min={request.value_min}, val_max={request.value_max}, cluster_min={request.cluster_size_min}, cluster_max={request.cluster_size_max}, min_dist={request.min_distance}")

        # Verifica disponibilità del modulo
        if not GREEN_DOTS_AVAILABLE:
            return GreenDotsAnalysisResult(
                success=False,
                session_id=session_id,
                error="Modulo GreenDotsProcessor non disponibile. Verificare l'installazione delle dipendenze.",
                timestamp=timestamp
            )

        # Processa l'immagine con i parametri forniti
        # I nuovi parametri dinamici sovrascrivono il config se specificati
        results = process_green_dots_analysis(
            image_base64=request.image,
            hue_range=request.hue_range,
            saturation_min=request.saturation_min,
            value_range=request.value_range,
            cluster_size_range=request.cluster_size_range,
            clustering_radius=request.clustering_radius,
            # Nuovi parametri dinamici dal frontend sliders
            saturation_max=request.saturation_max,
            saturation_max_tail=request.saturation_max_tail,
            cluster_min_tail=request.cluster_min_tail,
            value_min=request.value_min,
            value_max=request.value_max,
            cluster_size_min=request.cluster_size_min,
            cluster_size_max=request.cluster_size_max,
            min_distance=request.min_distance,
            adaptive=request.adaptive,
            brightness_percentile=request.brightness_percentile,
            sat_cap=request.sat_cap,
            pass1_percentile=request.pass1_percentile,
            pass1_sat_cap=request.pass1_sat_cap,
            pass2_percentile=request.pass2_percentile,
            pass2_sat_cap=request.pass2_sat_cap,
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
    Restituisce informazioni sui parametri e funzionalità del modulo WhiteDotsProcessorV2.
    Endpoint mantenuto per retrocompatibilità (era /api/green-dots/info).
    """
    try:
        # Carica parametri attivi dal config
        config_params = load_white_dots_config()
        
        return {
            "available": WHITE_DOTS_AVAILABLE,
            "module_info": {
                "description": "Modulo WhiteDotsProcessorV2 per rilevamento puntini BIANCHI sulle sopracciglia",
                "functions": [
                    "Rilevamento puntini bianchi usando maschere sopracciglia MediaPipe",
                    "Ricerca limitata alle regioni sopracciglia (no scan intera immagine)",
                    "Divisione automatica in gruppo sinistro/destro",
                    "Generazione overlay con cerchi colorati + contorni maschere",
                    "Filtro anti-bloom per cluster > large_cluster_threshold"
                ],
                "config_source": "config_white_dots_detection.json"
            },
            "active_parameters": {
                "saturation_max": f"{config_params['saturation_max']}%",
                "value_min": f"{config_params['value_min']}%",
                "value_max": f"{config_params['value_max']}%",
                "cluster_size_range": [config_params['cluster_size_min'], config_params['cluster_size_max']],
                "clustering_radius": f"{config_params['clustering_radius']}px",
                "min_distance": f"{config_params['min_distance']}px",
                "large_cluster_threshold": f"{config_params['large_cluster_threshold']}px"
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
                "dependencies": ["opencv-python", "numpy", "pillow", "mediapipe"]
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
        "measurement_started": "Misurazione in corso.",
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
        "measurement_started": "Misurazione in corso.",
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

@app.post("/api/estimate-age")
async def estimate_age(request: AnalysisRequest):
    """Endpoint per stimare l'età dal viso usando proporzioni facciali multi-parametro."""
    try:
        # Decodifica immagine base64
        image_data = base64.b64decode(request.image.split(',')[1] if ',' in request.image else request.image)
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise HTTPException(status_code=400, detail="Impossibile decodificare l'immagine")

        # Usa MediaPipe per rilevare landmarks facciali
        if not MEDIAPIPE_AVAILABLE or face_mesh is None:
            raise HTTPException(status_code=500, detail="MediaPipe non disponibile")

        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_image)

        if not results.multi_face_landmarks:
            raise HTTPException(status_code=404, detail="Nessun volto rilevato nell'immagine")

        landmarks = results.multi_face_landmarks[0]
        h, w = image.shape[:2]
        lm = landmarks.landmark

        def pt(idx):
            """Restituisce (x_px, y_px) del landmark idx."""
            return (lm[idx].x * w, lm[idx].y * h)

        def dist(a, b):
            return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

        # ── Punti chiave ──────────────────────────────────────────────────────
        forehead      = pt(10)   # fronte alta
        chin          = pt(152)  # mento
        left_eye_out  = pt(33)   # canto esterno occhio sx
        right_eye_out = pt(263)  # canto esterno occhio dx
        left_eye_in   = pt(133)  # canto interno occhio sx
        right_eye_in  = pt(362)  # canto interno occhio dx
        left_eye_top  = pt(159)  # palpebra sup sx
        left_eye_bot  = pt(145)  # palpebra inf sx
        right_eye_top = pt(386)  # palpebra sup dx
        right_eye_bot = pt(374)  # palpebra inf dx
        nose_tip      = pt(1)    # punta naso
        nose_root     = pt(168)  # radice naso (nasion)
        upper_lip     = pt(13)   # labbro superiore
        lower_lip     = pt(14)   # labbro inferiore
        left_jaw      = pt(234)  # mascella sinistra
        right_jaw     = pt(454)  # mascella destra
        left_cheek    = pt(116)  # zigomo sinistro
        right_cheek   = pt(345)  # zigomo destro
        left_brow_in  = pt(55)   # sopracciglio sx interno
        right_brow_in = pt(285)  # sopracciglio dx interno
        left_brow_out = pt(46)   # sopracciglio sx esterno
        right_brow_out= pt(276)  # sopracciglio dx esterno
        mouth_left    = pt(61)   # angolo bocca sx
        mouth_right   = pt(291)  # angolo bocca dx

        # ── Misure base ───────────────────────────────────────────────────────
        face_height      = dist(forehead, chin)
        biiocular_w      = dist(left_eye_out, right_eye_out)    # larghezza biinoculare
        interocular_d    = dist(left_eye_in, right_eye_in)      # distanza inter-occhi
        jaw_width        = dist(left_jaw, right_jaw)
        cheek_width      = dist(left_cheek, right_cheek)
        mouth_width      = dist(mouth_left, mouth_right)
        nose_height      = dist(nose_root, nose_tip)
        nose_to_chin     = dist(nose_tip, chin)
        forehead_to_eye  = dist(forehead, pt(159))              # fronte → palpebra sup sx
        eye_to_nose      = dist(left_eye_bot, nose_tip)         # occhio → punta naso
        lip_height_top   = abs(upper_lip[1] - lower_lip[1])     # altezza labbra
        eye_h_left       = dist(left_eye_top, left_eye_bot)     # apertura occhio sx
        eye_h_right      = dist(right_eye_top, right_eye_bot)   # apertura occhio dx
        eye_h_avg        = (eye_h_left + eye_h_right) / 2
        eye_w_left       = dist(left_eye_out, left_eye_in)
        eye_w_right      = dist(right_eye_out, right_eye_in)
        eye_w_avg        = (eye_w_left + eye_w_right) / 2
        brow_eye_sx      = abs(left_brow_in[1] - left_eye_top[1])
        brow_eye_dx      = abs(right_brow_in[1] - right_eye_top[1])
        brow_eye_avg     = (brow_eye_sx + brow_eye_dx) / 2

        # ── Ratio facciali normalizzati ────────────────────────────────────────
        # Ogni ratio viene normalizzato su face_height per essere invariante alla scala
        r_jaw_face       = jaw_width / max(face_height, 1)          # più alto = viso giovane
        r_cheek_jaw      = cheek_width / max(jaw_width, 1)          # cheekbone prominence
        r_lower_face     = nose_to_chin / max(face_height, 1)       # terzo inferiore
        r_upper_face     = forehead_to_eye / max(face_height, 1)    # terzo superiore
        r_nose           = nose_height / max(face_height, 1)        # altezza naso
        r_mouth          = mouth_width / max(biiocular_w, 1)        # larghezza bocca
        r_eye_open       = eye_h_avg / max(eye_w_avg, 1)            # apertura occhio
        r_brow_eye       = brow_eye_avg / max(face_height, 1)       # distanza sopracciglio-occhio
        r_interocular    = interocular_d / max(biiocular_w, 1)      # spaziatura occhi

        # ── Sistema a punteggio pesato ────────────────────────────────────────
        # Ogni feature contribuisce con un punteggio età parziale
        # Basato su studi antropometrici: con l'età
        #   - la mandibola si allarga relativamente (ptosi)
        #   - il terzo inferiore del viso aumenta
        #   - le sopracciglia scendono verso gli occhi
        #   - l'apertura oculare si riduce (blefaroptosi senile)
        #   - il naso si allunga
        #   - la bocca si restringe

        age_votes = []

        # 1) Rapporto mascella/altezza viso
        # giovani (20): ~0.55-0.60 | medi (40): ~0.58-0.65 | anziani (60+): ~0.62-0.70
        v1 = 20 + (r_jaw_face - 0.55) / (0.15) * 40
        age_votes.append(("jaw_face", float(np.clip(v1, 16, 75)), 1.5))

        # 2) Terzo inferiore (naso-mento / altezza viso)
        # giovani: ~0.30-0.35 | anziani: ~0.38-0.45
        v2 = 20 + (r_lower_face - 0.30) / (0.15) * 50
        age_votes.append(("lower_face", float(np.clip(v2, 16, 80)), 1.8))

        # 3) Terzo superiore (fronte-occhio / altezza viso)
        # giovani: ~0.28-0.32 | anziani: ~0.24-0.28 (fronte sembra più piccola)
        v3 = 20 + (0.32 - r_upper_face) / (0.08) * 50
        age_votes.append(("upper_face", float(np.clip(v3, 16, 75)), 1.0))

        # 4) Altezza naso normalizzata
        # giovani: ~0.35-0.40 | anziani: ~0.42-0.50
        v4 = 18 + (r_nose - 0.35) / (0.15) * 55
        age_votes.append(("nose_height", float(np.clip(v4, 16, 80)), 1.2))

        # 5) Distanza sopracciglio-occhio
        # giovani: brow_eye/face_height ~0.05-0.07 (alte) | anziani: ~0.02-0.04 (basse, ptosi)
        v5 = 20 + (0.07 - r_brow_eye) / (0.05) * 50
        age_votes.append(("brow_drop", float(np.clip(v5, 16, 75)), 1.4))

        # 6) Apertura oculare (eye_h / eye_w)
        # giovani: ~0.28-0.35 | anziani: ~0.20-0.27 (blefaroptosi)
        v6 = 18 + (0.35 - r_eye_open) / (0.15) * 55
        age_votes.append(("eye_open", float(np.clip(v6, 16, 80)), 1.3))

        # 7) Larghezza bocca relativa
        # giovani: ~0.65-0.75 | anziani: ~0.55-0.65 (labbra più sottili, assottigliamento)
        v7 = 18 + (0.72 - r_mouth) / (0.20) * 55
        age_votes.append(("mouth_width", float(np.clip(v7, 16, 80)), 0.8))

        # ── Media pesata ──────────────────────────────────────────────────────
        total_weight = sum(w_ for _, _, w_ in age_votes)
        estimated_age = sum(age * w_ for _, age, w_ in age_votes) / total_weight

        # Limita range plausibile
        estimated_age = float(np.clip(estimated_age, 16, 80))

        # ── Confidenza ────────────────────────────────────────────────────────
        visibility_lms = [10, 152, 33, 263, 1, 13, 159, 145]
        visibility_avg = sum(lm[i].visibility for i in visibility_lms) / len(visibility_lms)
        # Dispersion dei voti come misura di incertezza interna
        ages_only = [a for _, a, _ in age_votes]
        spread = max(ages_only) - min(ages_only)
        if visibility_avg > 0.85 and spread < 20:
            confidence = "high"
        elif visibility_avg > 0.65 and spread < 35:
            confidence = "medium"
        else:
            confidence = "low"

        return JSONResponse({
            "success": True,
            "age": int(round(estimated_age)),
            "confidence": confidence,
            "method": "multi_parameter_proportions",
            "ratios": {
                "face_ratio": round(face_height / max(biiocular_w, 1), 2),
                "lower_face_ratio": round(r_lower_face, 3),
                "jaw_face_ratio": round(r_jaw_face, 3),
                "nose_ratio": round(r_nose, 3),
                "eye_openness": round(r_eye_open, 3),
                "brow_drop": round(r_brow_eye, 3),
                "vote_spread": round(spread, 1)
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore durante la stima età: {str(e)}")

# === ENDPOINT CAMERA IPHONE ===

# Importa librerie per QR code (lazy import per evitare errori se non installato)
def get_qr_module():
    """Import qrcode solo quando necessario"""
    try:
        import qrcode
        return qrcode
    except ImportError:
        return None

def get_local_ip():
    """Ottiene l'IP locale del server"""
    import socket as sock
    try:
        s = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@app.get("/api/qrcode.png")
async def generate_qr_code(request: Request, st: str = ""):
    """
    Genera un QR code dinamico per connettere iPhone alla camera.
    Il QR code contiene l'URL della pagina /camera?st=<session_token> con l'IP locale del server.
    Il parametro 'st' (session_token) è obbligatorio per l'isolamento sicuro tra utenti.
    """
    qrcode = get_qr_module()
    if not qrcode:
        raise HTTPException(
            status_code=500,
            detail="Modulo qrcode non installato. Esegui: pip install qrcode[pil]"
        )

    try:
        # Determina protocollo e host
        # Usa l'header X-Forwarded-Proto se dietro reverse proxy
        proto = request.headers.get('x-forwarded-proto', 'http')

        # Ottieni l'host dalla richiesta
        host = request.headers.get('host', '')

        # Costruisci URL base della camera
        if 'localhost' in host or '127.0.0.1' in host or host.startswith('192.168.') or host.startswith('10.'):
            local_ip = get_local_ip()
            port = host.split(':')[1] if ':' in host else '80'
            base_camera_url = f"http://{local_ip}:{port}/camera"
        else:
            base_camera_url = f"{proto}://{host}/camera"

        # Aggiungi session_token all'URL se fornito (isolamento sessione utente)
        if st:
            camera_url = f"{base_camera_url}?st={st}"
        else:
            camera_url = base_camera_url

        print(f"QR Code generato per URL: {camera_url}")

        # Genera QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4
        )
        qr.add_data(camera_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Converti in bytes
        from io import BytesIO as QRBytesIO
        buf = QRBytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        from fastapi.responses import Response
        return Response(
            content=buf.getvalue(),
            media_type="image/png",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache"
            }
        )

    except Exception as e:
        print(f"Errore generazione QR code: {e}")
        raise HTTPException(status_code=500, detail=f"Errore generazione QR: {str(e)}")

# /camera route defined below (single definition with no-cache headers)

# === CONTACT FORM HELPERS ===

def send_email_sync(to_email: str, subject: str, html_body: str, text_body: str, reply_to: str = None):
    """
    Invia email in modo sincrono (da usare in thread separato).
    """
    try:
        smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER', '')
        smtp_password = os.getenv('SMTP_PASSWORD', '')
        smtp_from_name = os.getenv('SMTP_FROM_NAME', 'Kimerika Evolution')
        
        if not smtp_user or not smtp_password:
            print("⚠️ SMTP non configurato")
            return False
        
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = f"{smtp_from_name} <{smtp_user}>"
        message['To'] = to_email
        if reply_to:
            message['Reply-To'] = reply_to
        
        message.attach(MIMEText(text_body, 'plain', 'utf-8'))
        message.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.send_message(message)
        
        print(f"✅ Email inviata a: {to_email}")
        return True
    except Exception as e:
        print(f"❌ Errore invio email: {e}")
        return False

# === CONTACT FORM ENDPOINT ===

@app.post("/api/contact", response_model=ContactFormResponse)
async def submit_contact_form(form_data: ContactFormRequest):
    """
    Gestisce l'invio del form contatti.
    Salva i dati localmente e tenta invio email in background.
    """
    try:
        # Log ricevimento
        print(f"\n📧 === NUOVO CONTATTO RICEVUTO ===")
        print(f"Nome: {form_data.firstname} {form_data.lastname}")
        print(f"Email: {form_data.email}")
        print(f"Oggetto: {form_data.subject}")
        print(f"================================\n")
        
        # Salva immediatamente su file
        backup_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'contact_submissions')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        email_safe = form_data.email.replace('@', '_at_').replace('.', '_')
        backup_file = os.path.join(backup_dir, f"contact_{timestamp_str}_{email_safe}.json")
        
        contact_data = {
            'firstname': form_data.firstname,
            'lastname': form_data.lastname,
            'email': form_data.email,
            'phone': form_data.phone,
            'subject': form_data.subject,
            'message': form_data.message,
            'newsletter': form_data.newsletter,
            'timestamp': form_data.timestamp,
            'saved_at': datetime.now().isoformat()
        }
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(contact_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Dati salvati in: {backup_file}")
        
        # Prepara email
        subject = f"[Kimerika Contact] {form_data.subject}"
        html_body = f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f8f9fa; padding: 30px; }}
                    .field {{ margin-bottom: 15px; }}
                    .label {{ font-weight: bold; color: #667eea; }}
                    .value {{ margin-top: 5px; padding: 10px; background: white; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header"><h2>📧 Nuovo Contatto</h2></div>
                    <div class="content">
                        <div class="field"><div class="label">👤 Da:</div><div class="value">{form_data.firstname} {form_data.lastname}</div></div>
                        <div class="field"><div class="label">📧 Email:</div><div class="value"><a href="mailto:{form_data.email}">{form_data.email}</a></div></div>
                        {f'<div class="field"><div class="label">📱 Telefono:</div><div class="value">{form_data.phone}</div></div>' if form_data.phone else ''}
                        <div class="field"><div class="label">📋 Oggetto:</div><div class="value">{form_data.subject}</div></div>
                        <div class="field"><div class="label">💬 Messaggio:</div><div class="value">{form_data.message}</div></div>
                    </div>
                </div>
            </body>
        </html>
        """
        
        text_body = f"Nuovo contatto da: {form_data.firstname} {form_data.lastname}\nEmail: {form_data.email}\nOggetto: {form_data.subject}\n\n{form_data.message}"
        
        # Invia email in thread separato (non blocca la risposta)
        threading.Thread(
            target=send_email_sync,
            args=("info@ennioorsini.com", subject, html_body, text_body, form_data.email),
            daemon=True
        ).start()
        
        # Rispondi immediatamente
        return ContactFormResponse(
            success=True,
            message="Messaggio ricevuto! Ti risponderemo entro 24 ore."
        )
            
    except Exception as e:
        print(f"❌ Errore form contatti: {e}")
        import traceback
        traceback.print_exc()
        return ContactFormResponse(
            success=False,
            message="Si è verificato un errore. Contattaci via WhatsApp: +39 371 1441066",
            error=str(e)
        )

async def verify_recaptcha(token: str) -> bool:
    """
    Verifica token reCAPTCHA v3 con Google.
    Richiede RECAPTCHA_SECRET_KEY nelle variabili d'ambiente.
    """
    try:
        secret_key = os.getenv('RECAPTCHA_SECRET_KEY', '')
        if not secret_key:
            print("⚠️ RECAPTCHA_SECRET_KEY non configurata, skip verifica")
            return True  # Skip verifica se non configurata
        
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': secret_key,
                'response': token
            },
            timeout=5
        )
        
        result = response.json()
        
        # reCAPTCHA v3 restituisce uno score (0.0 - 1.0)
        # 0.0 = bot, 1.0 = umano
        score = result.get('score', 0)
        success = result.get('success', False)
        
        print(f"🔒 reCAPTCHA score: {score}")
        
        # Accetta se score > 0.5 (soglia consigliata)
        return success and score >= 0.5
        
    except Exception as e:
        print(f"⚠️ Errore verifica reCAPTCHA: {e}")
        return True  # In caso di errore, accetta comunque (graceful degradation)

async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    reply_to: Optional[str] = None
) -> bool:
    """
    Invia email usando SMTP.
    Configurazione tramite variabili d'ambiente:
    - SMTP_HOST (es: mail.ennioorsini.com)
    - SMTP_PORT (465 per SSL, 587 per TLS)
    - SMTP_USER (email mittente)
    - SMTP_PASSWORD (password)
    - SMTP_FROM_NAME (nome mittente, default: Kimerika Evolution)
    """
    try:
        # Leggi configurazione SMTP da variabili d'ambiente
        smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER', '')
        smtp_password = os.getenv('SMTP_PASSWORD', '')
        smtp_from_name = os.getenv('SMTP_FROM_NAME', 'Kimerika Evolution')
        
        if not smtp_user or not smtp_password:
            print("⚠️ SMTP non configurato (SMTP_USER/SMTP_PASSWORD mancanti)")
            print(f"📧 Email che sarebbe stata inviata a: {to_email}")
            print(f"📧 Oggetto: {subject}")
            print(f"📧 Testo:\n{text_body}")
            return True  # Simula successo per testing
        
        # Crea messaggio
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = f"{smtp_from_name} <{smtp_user}>"
        message['To'] = to_email
        
        if reply_to:
            message['Reply-To'] = reply_to
        
        # Aggiungi body testuale e HTML
        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')
        
        message.attach(part1)
        message.attach(part2)
        
        # Crea contesto SSL
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Usa SMTP_SSL per porta 465, SMTP con starttls per porta 587
        if smtp_port == 465:
            # Porta 465: usa SMTP_SSL
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=5) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(message)
        else:
            # Porta 587: usa SMTP con starttls
            with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.send_message(message)
        
        print(f"✅ Email inviata con successo a: {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Errore autenticazione SMTP: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ Errore SMTP: {e}")
        return False
    except TimeoutError as e:
        print(f"❌ Timeout connessione SMTP: {e}")
        return False
    except Exception as e:
        print(f"❌ Errore invio email: {e}")
        return False

@app.get("/camera")
async def camera_page():
    """
    Serve la pagina camera per iPhone.
    Questa pagina usa getUserMedia per accedere alla camera e invia frame via WebSocket.
    """
    import os
    template_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'templates', 'camera.html'
    )

    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template camera.html non trovato")

    return FileResponse(
        template_path,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate"
        }
    )

@app.get("/api/camera/info")
async def camera_info(request: Request):
    """
    Restituisce informazioni sulla configurazione camera per iPhone.
    Utile per debugging e verifica connessione.
    """
    host = request.headers.get('host', '')
    proto = request.headers.get('x-forwarded-proto', 'http')
    local_ip = get_local_ip()

    return {
        "local_ip": local_ip,
        "host": host,
        "protocol": proto,
        "camera_url": f"{proto}://{host}/camera",
        "websocket_port": 8765,
        "qrcode_url": f"{proto}://{host}/qrcode.png"
    }


# ---------------------------------------------------------------------------
# WHITE DOTS DEBUG – immagini diagnostiche per _detect_white_dots_v3
# ---------------------------------------------------------------------------

class WhiteDotsDebugRequest(BaseModel):
    image: str  # dataURL base64
    # default = WHITE_DOTS_THRESH_PERC / WHITE_DOTS_SAT_MAX_FRAC*100 → coincidono con production
    thresh_percentile: int = WHITE_DOTS_THRESH_PERC        # 75 = top 25%
    sat_max_pct: int      = round(WHITE_DOTS_SAT_MAX_FRAC * 100)  # 28


@app.post("/api/white-dots/debug-images")
async def white_dots_debug_images(payload: WhiteDotsDebugRequest):
    """
    Genera due immagini di debug per _detect_white_dots_v3:
      1. zone_image  – strip di ricerca dal convex hull dlib (60px fuori + 10px dentro)
      2. detect_image – pixel bianchi rilevati + blobs + top-5 punti selezionati

    Risposta: { zone_b64: "data:image/jpeg...", detect_b64: "data:image/jpeg..." }
    """
    try:
        from eyebrows import extract_eyebrows_from_array
        import base64 as _b64

        # Decodifica immagine
        b64 = payload.image
        if ',' in b64:
            b64 = b64.split(',', 1)[1]
        img_bytes = _b64.b64decode(b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("Impossibile decodificare l'immagine")

        _dat = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..',
            'face-landmark-localization-master', 'shape_predictor_68_face_landmarks.dat'
        ))

        res_dlib = extract_eyebrows_from_array(img_bgr, predictor_path=_dat)
        if not res_dlib["face_detected"]:
            raise ValueError("Volto non rilevato da dlib")

        h, w = img_bgr.shape[:2]
        hsv  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        v_ch = hsv[:, :, 2].astype(np.float32)
        s_ch = hsv[:, :, 1].astype(np.float32)

        # Parametri morfologici fissi (identici a _detect_white_dots_v3)
        OUTER_PX = 25
        INNER_PX = 25
        k_outer = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OUTER_PX*2+1, OUTER_PX*2+1))
        k_inner = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (INNER_PX*2+1, INNER_PX*2+1))
        MERGE_PX = 8
        k_merge  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MERGE_PX*2+1, MERGE_PX*2+1))

        # Parametri configurabili dal frontend
        THRESH_PERC = max(1, min(99, int(payload.thresh_percentile)))
        SAT_MAX     = max(0, min(100, int(payload.sat_max_pct))) / 100.0 * 255

        # ── Dot canonici: STESSA chiamata di "Trova Differenze" ─────────────
        # Garantisce che debug e output del pulsante mostrino esattamente gli stessi punti.
        v3_result = _detect_white_dots_v3(img_bgr,
                                          thresh_perc=THRESH_PERC,
                                          sat_max_frac=SAT_MAX / 255.0)
        if 'error' in v3_result:
            raise ValueError(v3_result['error'])

        middle_x = w // 2
        left_v3  = [d for d in v3_result['dots'] if d['x'] <  middle_x]
        right_v3 = [d for d in v3_result['dots'] if d['x'] >= middle_x]
        left_v3  = _select_best_5_for_eyebrow(left_v3,  is_left=True)
        right_v3 = _select_best_5_for_eyebrow(right_v3, is_left=False)
        all_selected = left_v3 + right_v3

        # ── Immagine 1: zone di ricerca ──────────────────────────────────────
        zone_img = img_bgr.copy()

        # ── Immagine 2: rilevamento pixel bianchi ─────────────────────────────
        detect_img = img_bgr.copy()

        for side, mask, c_mask, c_zone, c_bright in [
            ('left',  res_dlib['left_mask'],
             (0, 255, 255),
             (0, 255, 0),
             (255, 0, 255)),
            ('right', res_dlib['right_mask'],
             (255, 255, 0),
             (0, 200, 200),
             (0, 100, 255)),
        ]:
            if not np.any(mask):
                continue

            # Striscia 25px fuori + 25px dentro
            expanded    = cv2.dilate(mask, k_outer, iterations=1)
            shrunk      = cv2.erode(mask,  k_inner, iterations=1)
            search_zone = cv2.subtract(expanded, shrunk)

            # IMG 1 — dlib mask + striscia con tinte semi-trasparenti
            overlay_tmp = zone_img.copy()
            overlay_tmp[mask > 0]        = c_mask
            overlay_tmp[search_zone > 0] = c_zone
            cv2.addWeighted(overlay_tmp, 0.35, zone_img, 0.65, 0, zone_img)

            # Contorno della striscia
            cnts_sz, _ = cv2.findContours(search_zone, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(zone_img, cnts_sz, -1, c_zone, max(2, h // 400))

            # IMG 2 — pixel bianchi con parametri configurabili
            zone_v = v_ch[search_zone > 0]
            if len(zone_v) < 10:
                continue
            thresh_v = float(np.percentile(zone_v, THRESH_PERC))
            thresh_s = SAT_MAX

            bright = np.zeros((h, w), dtype=np.uint8)
            bright[(v_ch >= thresh_v) & (s_ch <= thresh_s) & (search_zone > 0)] = 255

            # Colora i pixel bianchi sull'immagine di rilevamento
            overlay_d = detect_img.copy()
            overlay_d[bright > 0] = c_bright
            cv2.addWeighted(overlay_d, 0.5, detect_img, 0.5, 0, detect_img)

            # Fondi frammenti adiacenti (stesso kernel di _detect_white_dots_v3)
            bright_m = cv2.dilate(bright, k_merge, iterations=1)
            MAX_BLOB = WHITE_DOTS_MAX_BLOB
            n_lbl, lbl_map, stats_cc, centroids = cv2.connectedComponentsWithStats(bright_m, 8)
            cands = []
            for lbl in range(1, n_lbl):
                area = int(stats_cc[lbl, cv2.CC_STAT_AREA])
                if area < 3 or area > MAX_BLOB:
                    continue
                cx_ = float(centroids[lbl, 0])
                cy_ = float(centroids[lbl, 1])
                bm  = lbl_map == lbl
                mv  = float(np.mean(v_ch[bm]))
                score = mv * (1.0 - area / (MAX_BLOB * 2.0))
                cands.append({'x': int(round(cx_)), 'y': int(round(cy_)),
                              'size': area, 'score': score})

            # Dots canonici per questo lato (identici a "Trova Differenze")
            side_selected = left_v3 if side == 'left' else right_v3
            sel_xy_side   = {(d['x'], d['y']) for d in side_selected}

            # Cerchi: grigio = candidato non selezionato, colorato = selezionato canonico
            dot_r = max(5, h // 200)
            for cc in cands:
                if (cc['x'], cc['y']) not in sel_xy_side:
                    cv2.circle(detect_img, (cc['x'], cc['y']), dot_r, (80, 80, 80), 1)
            for i, cc in enumerate(side_selected):
                cv2.circle(detect_img, (cc['x'], cc['y']), dot_r + 4, c_bright, -1)
                cv2.circle(detect_img, (cc['x'], cc['y']), dot_r + 6, (255, 255, 255), 2)
                cv2.putText(detect_img, str(i + 1),
                            (cc['x'] - dot_r, cc['y'] - dot_r - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, max(0.5, h / 3000.0),
                            (255, 255, 255), max(1, h // 800))

            # Info testo su zona
            ys_m, xs_m = np.where(mask > 0)
            x_txt = int(xs_m.min())
            y_txt = max(20, int(ys_m.min()) - 10)
            txt = f"{side} strip=25+25px cand={len(cands)} sel={len(side_selected)}"
            cv2.putText(zone_img, txt, (x_txt, y_txt),
                        cv2.FONT_HERSHEY_SIMPLEX, max(0.5, h / 3000.0),
                        (255, 255, 255), max(1, h // 800))

        # Disegna anche i top-5 sull'immagine 1 (zone) per riferimento
        for cc in all_selected:
            cv2.circle(zone_img, (cc['x'], cc['y']),
                       max(6, h // 200), (0, 0, 255), -1)
            cv2.circle(zone_img, (cc['x'], cc['y']),
                       max(8, h // 200) + 2, (255, 255, 255), 2)

        # Immagine 3: porzione ORIGINALE visibile solo nella strip (nero fuori)
        # Mostra esattamente i pixel analizzati per il rilevamento
        both_strips = cv2.bitwise_or(
            *[cv2.subtract(
                cv2.dilate(res_dlib[f'{s}_mask'], k_outer, iterations=1),
                cv2.erode( res_dlib[f'{s}_mask'], k_inner, iterations=1)
              ) for s in ('left', 'right')]
        )
        masked_img = np.zeros_like(img_bgr)
        masked_img[both_strips > 0] = img_bgr[both_strips > 0]
        # Bordo verde della strip per chiarezza
        cnts_all, _ = cv2.findContours(both_strips, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(masked_img, cnts_all, -1, (0, 230, 0), max(2, h // 500))
        # Disegna top-5 selezionati anche qui
        for cc in all_selected:
            cv2.circle(masked_img, (cc['x'], cc['y']), max(6, h // 200), (0, 0, 255), -1)
            cv2.circle(masked_img, (cc['x'], cc['y']), max(8, h // 200) + 2, (255, 255, 255), 2)

        # Ridimensiona a max 1200px per il trasferimento
        def _resize_for_transfer(img, max_side=1200):
            mh, mw = img.shape[:2]
            s = min(1.0, max_side / max(mh, mw))
            if s < 1.0:
                img = cv2.resize(img, (int(mw * s), int(mh * s)), interpolation=cv2.INTER_AREA)
            return img

        zone_img   = _resize_for_transfer(zone_img)
        detect_img = _resize_for_transfer(detect_img)
        masked_img = _resize_for_transfer(masked_img)

        _, buf_z = cv2.imencode('.jpg', zone_img,   [cv2.IMWRITE_JPEG_QUALITY, 88])
        _, buf_d = cv2.imencode('.jpg', detect_img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        _, buf_m = cv2.imencode('.jpg', masked_img, [cv2.IMWRITE_JPEG_QUALITY, 88])

        return {
            "success":        True,
            "zone_b64":       "data:image/jpeg;base64," + _b64.b64encode(buf_z.tobytes()).decode(),
            "detect_b64":     "data:image/jpeg;base64," + _b64.b64encode(buf_d.tobytes()).decode(),
            "masked_b64":     "data:image/jpeg;base64," + _b64.b64encode(buf_m.tobytes()).decode(),
            "total_selected": len(all_selected),
            "params": {
                "outer_px":          OUTER_PX,
                "inner_px":          INNER_PX,
                "merge_px":          MERGE_PX,
                "thresh_percentile": THRESH_PERC,
                "sat_max_pct":       int(payload.sat_max_pct),
                "min_blob_area":     3,
                "max_blob_area":     WHITE_DOTS_MAX_BLOB,
                "top_n_per_side":    5,
            },
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore debug images: {e}")


# ---------------------------------------------------------------------------
# EYEBROW SYMMETRY – usa modulo eyebrows.py (dlib + segmentazione pixel)
# ---------------------------------------------------------------------------

_DAT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..',
                 'face-landmark-localization-master',
                 'shape_predictor_68_face_landmarks.dat')
)


class EyebrowSymmetryRequest(BaseModel):
    image: str  # dataURL base64 (con o senza prefisso data:image/...)


@app.post("/api/eyebrow-symmetry")
async def eyebrow_symmetry(payload: EyebrowSymmetryRequest):
    """
    Analizza la simmetria delle sopracciglia tramite eyebrows.py (dlib).
    Decodifica l'immagine base64, esegue la segmentazione pixel e restituisce:
      - overlay_b64: PNG trasparente (verde=sx, arancio=dx) con stessa dimensione dell'immagine inviata
      - left_area, right_area: pixel count
      - face_detected: bool
    """
    import base64
    from eyebrows import extract_eyebrows_from_array
    try:
        # --- decodifica base64 ---
        b64 = payload.image
        if ',' in b64:
            b64 = b64.split(',', 1)[1]
        img_bytes = base64.b64decode(b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("Impossibile decodificare l'immagine base64.")

        # --- segmentazione dlib ---
        res = extract_eyebrows_from_array(img_bgr, predictor_path=_DAT_PATH)
        if not res["face_detected"]:
            return {"face_detected": False, "overlay_b64": "", "left_area": 0, "right_area": 0}

        # --- crea PNG BGRA trasparente ---
        h, w = img_bgr.shape[:2]
        bgra = np.zeros((h, w, 4), dtype=np.uint8)
        lm, rm = res["left_mask"], res["right_mask"]

        # Usa il contorno smoothed (approxPolyDP ε=1.5) sia per il fill che per l'outline:
        # il perimetro risulta lineare senza frastagliature; le aree restituite (left_area/
        # right_area) restano calcolate sul mask grezzo → nessuna distorsione nell'analisi.
        for mask, fill_color, edge_color in [
            (lm, (128, 222, 74, 115), (60, 255, 74, 220)),   # verde sx
            (rm, (60, 147, 251, 115), (60, 165, 251, 220)),  # arancio dx
        ]:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
            if not contours:
                continue
            # prendi solo il contorno più grande, smoothing leggero con ε=1.5
            main_cnt = max(contours, key=cv2.contourArea)
            smooth = cv2.approxPolyDP(main_cnt, 1.5, True)

            # fill semi-trasparente
            tmp_fill = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(tmp_fill, [smooth], 255)
            for c_idx, c_val in enumerate(fill_color):
                bgra[tmp_fill > 0, c_idx] = c_val

            # outline opaco
            tmp_edge = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(tmp_edge, [smooth], -1, 255, 2)
            for c_idx, c_val in enumerate(edge_color):
                bgra[tmp_edge > 0, c_idx] = c_val

        # encoding PNG
        ok, buf = cv2.imencode('.png', bgra)
        if not ok:
            raise ValueError("Errore encoding PNG overlay.")
        overlay_b64 = "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore analisi sopracciglia: {e}")

    return {
        "face_detected": True,
        "overlay_b64":   overlay_b64,
        "left_area":     res["left_area"],
        "right_area":    res["right_area"],
    }


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


# ============================================
# PAYPAL PAYMENT INTEGRATION
# ============================================

# PayPal Configuration
PAYPAL_API = os.environ.get('PAYPAL_API', 'https://api-m.sandbox.paypal.com')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET', '')

# Pydantic Models for PayPal
class PayPalOrderRequest(BaseModel):
    plan_type: str  # 'monthly' or 'annual'

class PayPalOrderResponse(BaseModel):
    order_id: str
    approval_url: str

class PayPalCaptureRequest(BaseModel):
    order_id: str

class PayPalCaptureResponse(BaseModel):
    success: bool
    transaction_id: str
    message: str

def get_paypal_access_token():
    """Ottiene access token da PayPal usando Client ID e Secret"""
    try:
        auth_url = f"{PAYPAL_API}/v1/oauth2/token"
        auth = (PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)
        headers = {
            'Accept': 'application/json',
            'Accept-Language': 'it_IT'
        }
        data = {'grant_type': 'client_credentials'}
        
        response = requests.post(auth_url, auth=auth, headers=headers, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        return token_data.get('access_token')
    except Exception as e:
        print(f"❌ Errore ottenimento PayPal access token: {e}")
        return None

@app.post("/api/paypal/create-order", response_model=PayPalOrderResponse)
async def create_paypal_order(order_request: PayPalOrderRequest):
    """
    Crea un ordine PayPal per il piano selezionato
    """
    try:
        # Definisci i prezzi
        plan_prices = {
            'monthly': {'amount': '69.00', 'description': 'Piano Mensile Kimerika Evolution'},
            'annual': {'amount': '588.00', 'description': 'Piano Annuale Kimerika Evolution'}
        }
        
        if order_request.plan_type not in plan_prices:
            raise HTTPException(status_code=400, detail="Piano non valido")
        
        plan = plan_prices[order_request.plan_type]
        
        # Ottieni access token
        access_token = get_paypal_access_token()
        if not access_token:
            raise HTTPException(status_code=500, detail="Errore autenticazione PayPal")
        
        # Crea l'ordine
        order_url = f"{PAYPAL_API}/v2/checkout/orders"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        order_data = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {
                    'currency_code': 'EUR',
                    'value': plan['amount']
                },
                'description': plan['description']
            }],
            'application_context': {
                'return_url': f"{os.environ.get('APP_URL', 'http://localhost:3000')}/payment-success",
                'cancel_url': f"{os.environ.get('APP_URL', 'http://localhost:3000')}/payment-cancel",
                'brand_name': 'Kimerika Evolution',
                'landing_page': 'LOGIN',
                'user_action': 'PAY_NOW',
                'locale': 'it-IT'
            }
        }
        
        response = requests.post(order_url, headers=headers, json=order_data)
        response.raise_for_status()
        
        order = response.json()
        
        # Trova l'approval URL
        approval_url = None
        for link in order.get('links', []):
            if link.get('rel') == 'approve':
                approval_url = link.get('href')
                break
        
        if not approval_url:
            raise HTTPException(status_code=500, detail="Impossibile ottenere URL di approvazione")
        
        return PayPalOrderResponse(
            order_id=order['id'],
            approval_url=approval_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Errore creazione ordine PayPal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/paypal/capture-order", response_model=PayPalCaptureResponse)
async def capture_paypal_order(capture_request: PayPalCaptureRequest, request: Request):
    """
    Cattura il pagamento dopo l'approvazione dell'utente
    Aggiorna il database con i dettagli dell'utente e del piano acquistato
    """
    try:
        # Ottieni access token
        access_token = get_paypal_access_token()
        if not access_token:
            raise HTTPException(status_code=500, detail="Errore autenticazione PayPal")
        
        # Cattura l'ordine
        capture_url = f"{PAYPAL_API}/v2/checkout/orders/{capture_request.order_id}/capture"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.post(capture_url, headers=headers)
        response.raise_for_status()
        
        capture_data = response.json()
        
        # Verifica che il pagamento sia stato completato
        if capture_data.get('status') != 'COMPLETED':
            return PayPalCaptureResponse(
                success=False,
                transaction_id='',
                message='Pagamento non completato'
            )
        
        # Estrai i dati della transazione
        transaction_id = capture_data['id']
        payer_info = capture_data.get('payer', {})
        payer_email = payer_info.get('email_address', '')
        payer_name = payer_info.get('name', {})
        firstname = payer_name.get('given_name', 'Utente')
        lastname = payer_name.get('surname', 'PayPal')
        amount = capture_data['purchase_units'][0]['payments']['captures'][0]['amount']['value']
        
        # Determina il tipo di piano in base all'importo
        plan_type = 'monthly' if float(amount) < 100 else 'annual'
        
        # Salva nel database
        db_conn = None
        user_id = None
        
        try:
            db_conn = get_db_connection()
            if not db_conn:
                raise Exception("Connessione database non disponibile")
            
            cursor = db_conn.cursor()
            
            # Cerca se l'utente esiste già
            cursor.execute("SELECT id, plan FROM \"user\" WHERE email = %s", (payer_email,))
            user = cursor.fetchone()
            
            if user:
                # Aggiorna utente esistente
                user_id = user['id']
                cursor.execute("""
                    UPDATE \"user\" 
                    SET plan = %s, subscription_ends_at = NOW() + INTERVAL '30 days'
                    WHERE id = %s
                """, (plan_type, user_id))
                print(f"✅ Utente aggiornato: {payer_email}")
            else:
                # Crea nuovo utente
                cursor.execute("""
                    INSERT INTO \"user\" (email, firstname, lastname, plan, is_active, subscription_ends_at)
                    VALUES (%s, %s, %s, %s, true, NOW() + INTERVAL '30 days')
                    RETURNING id
                """, (payer_email, firstname, lastname, plan_type))
                user_id = cursor.fetchone()['id']
                print(f"✅ Nuovo utente creato: {payer_email}")
            
            # Inserisci la transazione
            cursor.execute("""
                INSERT INTO payment_transactions 
                (user_id, transaction_id, plan_type, amount, currency, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, transaction_id, plan_type, amount, 'EUR', 'completed'))
            
            db_conn.commit()
            print(f"✅ Transazione salvata: {transaction_id}")
            
        except Exception as db_error:
            if db_conn:
                db_conn.rollback()
            print(f"❌ Errore database: {db_error}")
            # Continua comunque, il pagamento è stato completato
        finally:
            if db_conn:
                cursor.close()
                db_conn.close()
        
        print(f"✅ Pagamento completato: {transaction_id}")
        print(f"📧 Email: {payer_email}")
        print(f"💰 Importo: €{amount}")
        print(f"📦 Piano: {plan_type}")
        
        return PayPalCaptureResponse(
            success=True,
            transaction_id=transaction_id,
            message='Pagamento completato con successo'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Errore cattura ordine PayPal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/paypal/config")
async def get_paypal_config():
    """
    Restituisce la configurazione PayPal per il client
    """
    return {
        'client_id': PAYPAL_CLIENT_ID,
        'currency': 'EUR'
    }
