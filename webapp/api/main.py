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

# Aggiunge src/ al path per trovare moduli Python locali
_SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src')
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

# Disponibilità white dots: dipende solo da dlib/eyebrows
WHITE_DOTS_AVAILABLE = True

# ── Parametri pipeline white-dots (condivisi tra production e debug) ──────────
WHITE_DOTS_TARGET_WIDTH  = 1200  # larghezza normalizzazione immagine
WHITE_DOTS_OUTER_PX      = 35    # espansione maschera dlib (zona intera, non striscia)
WHITE_DOTS_LUMA_MIN      = 200   # soglia luma minima punti centrali (0-255)
WHITE_DOTS_LUMA_MAX      = 255   # soglia luma massima punti centrali
WHITE_DOTS_LUMA_LB       = 120   # soglia luma minima esclusiva LB/RB (estremi X)
WHITE_DOTS_LUMA_MAX_LB   = 255   # soglia luma massima esclusiva LB/RB
WHITE_DOTS_HIGHLIGHT_THRESH_INNER    = 160   # soglia luma boost — zona interna
WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER  = 0.8   # intensità boost zona interna (0.0–1.0)
WHITE_DOTS_HIGHLIGHT_THRESH_OUTER    = 140   # soglia luma boost — strip esterna LB/RB
WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER  = 0.6   # intensità boost strip esterna (0.0–1.0)
WHITE_DOTS_MIN_CIRCULARITY_INNER = 0.5  # circolarità minima blob zona interna
WHITE_DOTS_MAX_CIRCULARITY_INNER = 1.0  # circolarità massima blob zona interna
WHITE_DOTS_MIN_PERIMETER_INNER   = 3    # perimetro minimo px blob zona interna
WHITE_DOTS_MAX_PERIMETER_INNER   = 60   # perimetro massimo px blob zona interna
WHITE_DOTS_MIN_CIRCULARITY_OUTER = 0.3  # circolarità minima blob strip esterna LB/RB
WHITE_DOTS_MAX_CIRCULARITY_OUTER = 1.0  # circolarità massima blob strip esterna LB/RB
WHITE_DOTS_MIN_PERIMETER_OUTER   = 2    # perimetro minimo px blob strip esterna LB/RB
WHITE_DOTS_MAX_PERIMETER_OUTER   = 40   # perimetro massimo px blob strip esterna LB/RB
WHITE_DOTS_MIN_DISTANCE          = 12   # distanza minima px tra blob (NMS deduplicazione)

# ---------------------------------------------------------------------------
# Persistenza parametri white-dots: file JSON sovrascrive le costanti al boot
# ---------------------------------------------------------------------------
_PARAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'white_dots_params.json')

def _load_white_dots_params() -> dict:
    """Carica parametri da file JSON; fallback alle costanti hardcoded se non esiste."""
    raw: dict = {}
    try:
        if os.path.exists(_PARAMS_FILE):
            with open(_PARAMS_FILE) as _f:
                raw = json.load(_f)
    except Exception:
        pass
    return {
        "target_width":           int(raw.get("target_width",           WHITE_DOTS_TARGET_WIDTH)),
        "outer_px":               int(raw.get("outer_px",               WHITE_DOTS_OUTER_PX)),
        "luma_min":               int(raw.get("luma_min",               WHITE_DOTS_LUMA_MIN)),
        "luma_max":               int(raw.get("luma_max",               WHITE_DOTS_LUMA_MAX)),
        "luma_lb":                int(raw.get("luma_lb",                WHITE_DOTS_LUMA_LB)),
        "luma_max_lb":            int(raw.get("luma_max_lb",            WHITE_DOTS_LUMA_MAX_LB)),
        "highlight_thresh_inner":       int(raw.get("highlight_thresh_inner",       WHITE_DOTS_HIGHLIGHT_THRESH_INNER)),
        "highlight_strength_inner":     float(raw.get("highlight_strength_inner",   WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER)),
        "highlight_thresh_outer":       int(raw.get("highlight_thresh_outer",       WHITE_DOTS_HIGHLIGHT_THRESH_OUTER)),
        "highlight_strength_outer":     float(raw.get("highlight_strength_outer",   WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER)),
        "min_circularity_inner":  float(raw.get("min_circularity_inner", WHITE_DOTS_MIN_CIRCULARITY_INNER)),
        "max_circularity_inner":  float(raw.get("max_circularity_inner", WHITE_DOTS_MAX_CIRCULARITY_INNER)),
        "min_perimeter_inner":    int(raw.get("min_perimeter_inner",    WHITE_DOTS_MIN_PERIMETER_INNER)),
        "max_perimeter_inner":    int(raw.get("max_perimeter_inner",    WHITE_DOTS_MAX_PERIMETER_INNER)),
        "min_circularity_outer":  float(raw.get("min_circularity_outer", WHITE_DOTS_MIN_CIRCULARITY_OUTER)),
        "max_circularity_outer":  float(raw.get("max_circularity_outer", WHITE_DOTS_MAX_CIRCULARITY_OUTER)),
        "min_perimeter_outer":    int(raw.get("min_perimeter_outer",    WHITE_DOTS_MIN_PERIMETER_OUTER)),
        "max_perimeter_outer":    int(raw.get("max_perimeter_outer",    WHITE_DOTS_MAX_PERIMETER_OUTER)),
        "min_distance":           int(raw.get("min_distance",           WHITE_DOTS_MIN_DISTANCE)),
    }

def _save_white_dots_params(params: dict) -> None:
    """Salva parametri su file JSON."""
    with open(_PARAMS_FILE, 'w') as _f:
        json.dump(params, _f, indent=2)

# Carica override da file al boot (sovrascrive le costanti se il file esiste)
_boot_params = _load_white_dots_params()
WHITE_DOTS_TARGET_WIDTH          = int(_boot_params.get("target_width",          WHITE_DOTS_TARGET_WIDTH))
WHITE_DOTS_OUTER_PX              = int(_boot_params.get("outer_px",              WHITE_DOTS_OUTER_PX))
WHITE_DOTS_LUMA_MIN              = int(_boot_params.get("luma_min",              WHITE_DOTS_LUMA_MIN))
WHITE_DOTS_LUMA_MAX              = int(_boot_params.get("luma_max",              WHITE_DOTS_LUMA_MAX))
WHITE_DOTS_LUMA_LB               = int(_boot_params.get("luma_lb",               WHITE_DOTS_LUMA_LB))
WHITE_DOTS_LUMA_MAX_LB           = int(_boot_params.get("luma_max_lb",           WHITE_DOTS_LUMA_MAX_LB))
WHITE_DOTS_HIGHLIGHT_THRESH_INNER    = int(_boot_params.get("highlight_thresh_inner",    WHITE_DOTS_HIGHLIGHT_THRESH_INNER))
WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER  = float(_boot_params.get("highlight_strength_inner",  WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER))
WHITE_DOTS_HIGHLIGHT_THRESH_OUTER    = int(_boot_params.get("highlight_thresh_outer",    WHITE_DOTS_HIGHLIGHT_THRESH_OUTER))
WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER  = float(_boot_params.get("highlight_strength_outer",  WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER))
WHITE_DOTS_MIN_CIRCULARITY_INNER = float(_boot_params.get("min_circularity_inner", WHITE_DOTS_MIN_CIRCULARITY_INNER))
WHITE_DOTS_MAX_CIRCULARITY_INNER = float(_boot_params.get("max_circularity_inner", WHITE_DOTS_MAX_CIRCULARITY_INNER))
WHITE_DOTS_MIN_PERIMETER_INNER   = int(_boot_params.get("min_perimeter_inner",   WHITE_DOTS_MIN_PERIMETER_INNER))
WHITE_DOTS_MAX_PERIMETER_INNER   = int(_boot_params.get("max_perimeter_inner",   WHITE_DOTS_MAX_PERIMETER_INNER))
WHITE_DOTS_MIN_CIRCULARITY_OUTER = float(_boot_params.get("min_circularity_outer", WHITE_DOTS_MIN_CIRCULARITY_OUTER))
WHITE_DOTS_MAX_CIRCULARITY_OUTER = float(_boot_params.get("max_circularity_outer", WHITE_DOTS_MAX_CIRCULARITY_OUTER))
WHITE_DOTS_MIN_PERIMETER_OUTER   = int(_boot_params.get("min_perimeter_outer",   WHITE_DOTS_MIN_PERIMETER_OUTER))
WHITE_DOTS_MAX_PERIMETER_OUTER   = int(_boot_params.get("max_perimeter_outer",   WHITE_DOTS_MAX_PERIMETER_OUTER))
WHITE_DOTS_MIN_DISTANCE          = int(_boot_params.get("min_distance",          WHITE_DOTS_MIN_DISTANCE))

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

# === MODELLO PYDANTIC PER WHITE DOTS (trova differenze) ===

class WhiteDotsRequest(BaseModel):
    image: str  # Base64 encoded image
    min_distance: Optional[int] = None
    outer_px: Optional[int] = None

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
    param: Optional[str] = None  # parametro aggiuntivo per azioni che lo richiedono

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
    Usata da process_green_dots_analysis() e _generate_debug_steps().
    
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
                         target_width: int        = None,
                         outer_px: int            = None,
                         luma_min: int            = None,
                         luma_max: int            = None,
                         luma_lb: int             = None,
                         luma_max_lb: int         = None,
                         highlight_thresh_inner: int    = None,
                         highlight_strength_inner: float = None,
                         highlight_thresh_outer: int    = None,
                         highlight_strength_outer: float = None,
                         min_circularity_inner: float = None,
                         max_circularity_inner: float = None,
                         min_perimeter_inner: int = None,
                         max_perimeter_inner: int = None,
                         min_circularity_outer: float = None,
                         max_circularity_outer: float = None,
                         min_perimeter_outer: int = None,
                         max_perimeter_outer: int = None,
                         min_distance: int = None,
                         **_kw) -> dict:
    """
    Rileva i puntini bianchi del tatuaggio sopracciglio.

    Flusso:
    1. dlib → maschera binaria sopracciglio sx e dx
    2. Maschera espansa outer_px (zona intera, NON striscia perimetrale)
    3. Highlight boost: pixel sopra highlight_thresh vengono potenziati verso 255
    4. Soglia assoluta: pixel con luma_min <= gray <= luma_max → candidati principali
       Soglia separata luma_lb/luma_max_lb → ricerca LB/RB agli estremi X
    5. Connected components → filtro circolarità+perimetro per zona interna e strip esterna
    """
    try:
        from eyebrows import extract_eyebrows_from_array
    except ImportError:
        return {'error': 'Modulo eyebrows (dlib) non disponibile.', 'dots': [], 'total_white_pixels': 0}

    _dat = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..',
        'face-landmark-localization-master', 'shape_predictor_68_face_landmarks.dat'
    ))

    # Parametri con fallback ai globali
    TARGET_WIDTH           = target_width           if target_width           is not None else WHITE_DOTS_TARGET_WIDTH
    OUTER_PX               = outer_px               if outer_px               is not None else WHITE_DOTS_OUTER_PX
    LUMA_MIN               = luma_min               if luma_min               is not None else WHITE_DOTS_LUMA_MIN
    LUMA_MAX               = luma_max               if luma_max               is not None else WHITE_DOTS_LUMA_MAX
    LUMA_LB                = luma_lb                if luma_lb                is not None else WHITE_DOTS_LUMA_LB
    LUMA_MAX_LB            = luma_max_lb            if luma_max_lb            is not None else WHITE_DOTS_LUMA_MAX_LB
    HL_THRESH_INNER        = highlight_thresh_inner   if highlight_thresh_inner   is not None else WHITE_DOTS_HIGHLIGHT_THRESH_INNER
    HL_STRENGTH_INNER      = highlight_strength_inner if highlight_strength_inner is not None else WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER
    HL_THRESH_OUTER        = highlight_thresh_outer   if highlight_thresh_outer   is not None else WHITE_DOTS_HIGHLIGHT_THRESH_OUTER
    HL_STRENGTH_OUTER      = highlight_strength_outer if highlight_strength_outer is not None else WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER
    MIN_CIRC_INNER         = min_circularity_inner  if min_circularity_inner  is not None else WHITE_DOTS_MIN_CIRCULARITY_INNER
    MAX_CIRC_INNER         = max_circularity_inner  if max_circularity_inner  is not None else WHITE_DOTS_MAX_CIRCULARITY_INNER
    MIN_PERI_INNER         = min_perimeter_inner    if min_perimeter_inner    is not None else WHITE_DOTS_MIN_PERIMETER_INNER
    MAX_PERI_INNER         = max_perimeter_inner    if max_perimeter_inner    is not None else WHITE_DOTS_MAX_PERIMETER_INNER
    MIN_CIRC_OUTER         = min_circularity_outer  if min_circularity_outer  is not None else WHITE_DOTS_MIN_CIRCULARITY_OUTER
    MAX_CIRC_OUTER         = max_circularity_outer  if max_circularity_outer  is not None else WHITE_DOTS_MAX_CIRCULARITY_OUTER
    MIN_PERI_OUTER         = min_perimeter_outer    if min_perimeter_outer    is not None else WHITE_DOTS_MIN_PERIMETER_OUTER
    MAX_PERI_OUTER         = max_perimeter_outer    if max_perimeter_outer    is not None else WHITE_DOTS_MAX_PERIMETER_OUTER
    MIN_DISTANCE           = min_distance           if min_distance           is not None else WHITE_DOTS_MIN_DISTANCE

    # Normalizza risoluzione
    _orig_h, _orig_w = img_bgr.shape[:2]
    if _orig_w != TARGET_WIDTH:
        _scale  = TARGET_WIDTH / _orig_w
        img_bgr = cv2.resize(img_bgr, (TARGET_WIDTH, max(1, round(_orig_h * _scale))),
                             interpolation=cv2.INTER_AREA if _orig_w > TARGET_WIDTH else cv2.INTER_LINEAR)
        print(f"   📐 resize {_orig_w}×{_orig_h} → {img_bgr.shape[1]}×{img_bgr.shape[0]}")

    # Maschere dlib
    res_dlib = extract_eyebrows_from_array(img_bgr, predictor_path=_dat)
    if not res_dlib["face_detected"]:
        return {'error': 'Volto non rilevato da dlib.', 'dots': [], 'total_white_pixels': 0}

    h, w = img_bgr.shape[:2]

    # Highlight boost separato: zona interna (inner) e strip esterna (outer)
    gray_raw = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # boost zona interna
    gray_inner_f = gray_raw.copy()
    mask_hi_inner = gray_raw >= HL_THRESH_INNER
    gray_inner_f[mask_hi_inner] = np.clip(
        gray_raw[mask_hi_inner] + HL_STRENGTH_INNER * (255.0 - gray_raw[mask_hi_inner]), 0, 255)
    gray_inner = gray_inner_f.astype(np.uint8)
    # boost strip esterna LB/RB
    gray_outer_f = gray_raw.copy()
    mask_hi_outer = gray_raw >= HL_THRESH_OUTER
    gray_outer_f[mask_hi_outer] = np.clip(
        gray_raw[mask_hi_outer] + HL_STRENGTH_OUTER * (255.0 - gray_raw[mask_hi_outer]), 0, 255)
    gray_outer = gray_outer_f.astype(np.uint8)

    k_outer = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OUTER_PX*2+1, OUTER_PX*2+1))

    all_dots      = []
    left_polygon  = None
    right_polygon = None
    total_white   = 0
    col_idx = np.indices((h, w))[1]   # matrice degli indici di colonna (calcolata una sola volta)

    def _filter_by_circularity(cc_mask, lbl_map, stats_cc, centroids, n_lbl, gray_img,
                                min_circ, max_circ, min_peri, max_peri, forced=False):
        """Filtra blob CC per circolarità e perimetro; restituisce lista di dict punto."""
        result = []
        for lbl in range(1, n_lbl):
            area = int(stats_cc[lbl, cv2.CC_STAT_AREA])
            blob_mask = (lbl_map == lbl).astype(np.uint8)
            cnts, _ = cv2.findContours(blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not cnts:
                continue
            perimeter = cv2.arcLength(cnts[0], True)
            if perimeter < min_peri or perimeter > max_peri:
                continue
            circularity = (4.0 * math.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
            if circularity < min_circ or circularity > max_circ:
                continue
            cx = float(centroids[lbl, 0])
            cy = float(centroids[lbl, 1])
            mean_luma = float(np.mean(gray_img[lbl_map == lbl]))
            d = {
                'x':     int(round(cx)),
                'y':     int(round(cy)),
                'size':  area,
                'score': round(mean_luma / 255.0 * 100.0, 2),
                'circ':  round(circularity, 4),
            }
            if forced:
                d['forced'] = True
            result.append(d)
        return result

    for side, mask in [('left', res_dlib['left_mask']), ('right', res_dlib['right_mask'])]:
        if not np.any(mask):
            continue

        # Zona di ricerca: maschera espansa (INTERA, non solo bordo)
        expanded = cv2.dilate(mask, k_outer, iterations=1)

        # Salva contorno per overlay frontend
        cnts, _ = cv2.findContours(expanded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            polygon = max(cnts, key=cv2.contourArea).squeeze()
            if side == 'left':
                left_polygon = polygon
            else:
                right_polygon = polygon

        # Candidati principali: range luminanza su gray_inner (boost zona interna)
        white_mask = np.zeros((h, w), dtype=np.uint8)
        white_mask[(gray_inner >= LUMA_MIN) & (gray_inner <= LUMA_MAX) & (expanded > 0)] = 255

        # Candidati LB/RB: soglie dedicate su gray_outer (boost strip esterna)
        ys_m, xs_m = np.where(mask > 0)
        x_min_mask, x_max_mask = int(xs_m.min()), int(xs_m.max())
        if side == 'left':
            lb_zone = (expanded > 0) & (col_idx <= x_min_mask + OUTER_PX)
        else:
            lb_zone = (expanded > 0) & (col_idx >= x_max_mask - OUTER_PX)
        lb_mask = np.zeros((h, w), dtype=np.uint8)
        lb_mask[(gray_outer >= LUMA_LB) & (gray_outer <= LUMA_MAX_LB) & lb_zone] = 255

        n_white = int(np.sum(white_mask > 0))
        total_white += n_white
        print(f"   [{side}] pixel bianchi (luma {LUMA_MIN}-{LUMA_MAX}): {n_white} | LB/RB strip (luma {LUMA_LB}-{LUMA_MAX_LB}): {int(np.sum(lb_mask > 0))}")

        # Connected components + filtro circolarità+perimetro (zona interna — parametri INNER)
        n_lbl, lbl_map, stats_cc, centroids = cv2.connectedComponentsWithStats(white_mask, 8)
        candidates = _filter_by_circularity(
            white_mask, lbl_map, stats_cc, centroids, n_lbl, gray_inner,
            MIN_CIRC_INNER, MAX_CIRC_INNER, MIN_PERI_INNER, MAX_PERI_INNER, forced=False
        )

        # Connected components + filtro circolarità+perimetro (strip esterna — parametri OUTER)
        n_lb, lbl_lb, stats_lb, ctr_lb = cv2.connectedComponentsWithStats(lb_mask, 8)
        lb_candidates = _filter_by_circularity(
            lb_mask, lbl_lb, stats_lb, ctr_lb, n_lb, gray_outer,
            MIN_CIRC_OUTER, MAX_CIRC_OUTER, MIN_PERI_OUTER, MAX_PERI_OUTER, forced=True
        )

        selected = candidates + lb_candidates
        for d in selected:
            d['eyebrow'] = side
        all_dots.extend(selected)
        print(f"🔍 white-dots [{side}]: {len(candidates)} inner + {len(lb_candidates)} outer candidati selezionati")

    # Applica NMS per rimuovere blob duplicati troppo vicini
    if len(all_dots) > 0:
        before_nms = len(all_dots)
        all_dots, _ = _nms_by_distance(all_dots, MIN_DISTANCE, debug=False)
        print(f"🔍 NMS deduplicazione: {before_nms} → {len(all_dots)} blob (distanza minima {MIN_DISTANCE} px)")

    # Rimappa coordinate a spazio originale
    if _orig_w != TARGET_WIDTH:
        _inv = _orig_w / TARGET_WIDTH
        for d in all_dots:
            d['x'] = int(round(d['x'] * _inv))
            d['y'] = int(round(d['y'] * _inv))

    return {
        'dots':               all_dots,
        'total_white_pixels': total_white,
        'left_polygon':       left_polygon,
        'right_polygon':      right_polygon,
    }


def _nms_by_distance(pts: list, min_dist: float, debug: bool = False) -> tuple:
    """NMS per distanza: rimuove punti troppo vicini, tenendo quello con score più alto.
    I punti forzati (flag 'forced'=True) vengono sempre mantenuti.
    Criterio di selezione: score più alto, poi circolarità più alta.
    Restituisce: (blob_kept, blob_rejected_by_nms)"""
    if min_dist <= 0:
        if debug:
            print(f"   [NMS] Disabilitato (min_dist={min_dist})")
        return pts, []
    # Prima ordina: forzati prima, poi per score decrescente, poi circolarità decrescente
    ordered = sorted(pts, key=lambda d: (0 if d.get('forced') else 1, -d.get('score', 0), -d.get('circ', 0)))
    
    if debug:
        print(f"   [NMS] Ordine elaborazione (forzati prima, poi score/circ decrescente):")
        for idx, p in enumerate(ordered):
            forced_tag = " [FORCED]" if p.get('forced') else ""
            print(f"      #{idx+1}: ({p['x']}, {p['y']}) score={p.get('score',0):.1f} circ={p.get('circ',0):.3f}{forced_tag}")
    
    kept = []
    rejected = []
    for p in ordered:
        too_close = False
        closest_dist = float('inf')
        closest_blob = None
        for k in kept:
            dist = math.hypot(p['x'] - k['x'], p['y'] - k['y'])
            if debug and dist <= min_dist:
                print(f"      ⚠️  Blob ({p['x']}, {p['y']}) è vicino a ({k['x']}, {k['y']}): dist={dist:.1f}px <= {min_dist}px")
            if dist <= min_dist:  # <= invece di < per includere anche distanza esatta
                too_close = True
                if dist < closest_dist:
                    closest_dist = dist
                    closest_blob = k
        if not too_close:
            kept.append(p)
            if debug:
                forced_tag = " [FORCED]" if p.get('forced') else ""
                print(f"      ✅ KEPT: ({p['x']}, {p['y']}) score={p.get('score',0):.1f}{forced_tag}")
        else:
            # Aggiungi informazioni sul perché è stato eliminato
            p['nms_rejected'] = True
            p['nms_reason'] = f"troppo vicino a blob score={closest_blob.get('score',0):.0f} (dist={closest_dist:.1f}px <= {min_dist}px)"
            rejected.append(p)
            if debug:
                print(f"      ❌ REJECTED: ({p['x']}, {p['y']}) score={p.get('score',0):.1f} - {p['nms_reason']}")
    
    if debug:
        print(f"   [NMS] Risultato finale: {len(pts)} → {len(kept)} blob (eliminati {len(rejected)})")
    
    return kept, rejected




def process_green_dots_analysis(image_base64: str, **kwargs) -> Dict:
    """
    Rileva i puntini bianchi del tatuaggio sopracciglio via _detect_white_dots_v3.
    Parametri letti dai globali WHITE_DOTS_* (configurabili via white_dots_params.json).
    """
    try:
        pil_image = decode_base64_to_pil_image(image_base64)

        img_array = np.array(pil_image)
        if img_array.ndim == 3 and img_array.shape[2] == 4:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        else:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        det = _detect_white_dots_v3(img_bgr, **kwargs)

        if 'error' in det:
            return {
                'success': False,
                'error': det['error'],
                'detection_results': {
                    'dots': [], 'total_dots': 0, 'total_green_pixels': 0,
                    'image_size': [pil_image.width, pil_image.height], 'parameters': {}
                }
            }

        dots = det['dots']
        print(f"✅ Punti rilevati: {len(dots)}")

        # I punti arrivano già taggati con eyebrow='left'/'right' da _detect_white_dots_v3
        left_dots  = sort_points_anatomical(
            [d for d in dots if d.get('eyebrow') == 'left'], is_left=True)
        right_dots = sort_points_anatomical(
            [d for d in dots if d.get('eyebrow') == 'right'], is_left=False)

        print(f"📊 Sx: {len(left_dots)}, Dx: {len(right_dots)}")

        left_area  = sum(d['size'] for d in left_dots)  if left_dots  else 0
        right_area = sum(d['size'] for d in right_dots) if right_dots else 0
        all_dots   = left_dots + right_dots

        overlay_img    = generate_white_dots_overlay(
            pil_image.size, all_dots,
            left_polygon=det.get('left_polygon'),
            right_polygon=det.get('right_polygon'),
        )
        overlay_base64 = convert_pil_image_to_base64(overlay_img)

        return {
            'success': True,
            'detection_results': {
                'dots': all_dots,
                'total_dots': len(all_dots),
                'total_green_pixels': det.get('total_white_pixels', 0),
                'image_size': list(pil_image.size),
                'parameters': {'method': 'dlib_clahe_v3'},
            },
            'config_parameters': {
                'method': 'dlib_clahe_v3',
                'luma_min': WHITE_DOTS_LUMA_MIN,
                'luma_max': WHITE_DOTS_LUMA_MAX,
            },
            'groups':      {'Sx': left_dots, 'Dx': right_dots},
            'coordinates': {
                'Sx': [(d['x'], d['y']) for d in left_dots],
                'Dx': [(d['x'], d['y']) for d in right_dots],
            },
            'statistics': {
                'left':     {'count': len(left_dots),  'area': float(left_area)},
                'right':    {'count': len(right_dots), 'area': float(right_area)},
                'combined': {'total_vertices': len(all_dots), 'total_area': float(left_area + right_area)},
            },
            'overlay_base64': overlay_base64,
            'image_size': list(pil_image.size),
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore analisi white dots: {str(e)}")


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

    left_polygon_drawn  = False
    right_polygon_drawn = False

    # Disegna poligono SINISTRO SOLO se ci sono esattamente 5 punti con tutti i nomi anatomici
    if len(left_dots_list) == 5:
        try:
            LEFT_PERIMETER_ORDER = ['LA', 'LC', 'LB', 'LC1', 'LA0']
            left_dots_by_name = {d.get('anatomical_name'): (d['x'], d['y']) for d in left_dots_list if d.get('anatomical_name')}
            if all(name in left_dots_by_name for name in LEFT_PERIMETER_ORDER):
                left_points_sorted = [left_dots_by_name[name] for name in LEFT_PERIMETER_ORDER]
                left_points_curved = create_curved_eyebrow_polygon(left_points_sorted, is_left=True)
                draw.polygon(left_points_curved, fill=LEFT_AREA_COLOR, outline=LEFT_BORDER_COLOR, width=3)
                left_polygon_drawn = True
            else:
                missing = [n for n in LEFT_PERIMETER_ORDER if n not in left_dots_by_name]
                print(f"⚠️ Poligono SINISTRO NON disegnato - mancano: {missing}")
        except Exception as e:
            print(f"⚠️ Errore disegno poligono sinistro: {e}")

    # Disegna poligono DESTRO SOLO se ci sono esattamente 5 punti con tutti i nomi anatomici
    if len(right_dots_list) == 5:
        try:
            RIGHT_PERIMETER_ORDER = ['RA', 'RC', 'RB', 'RC1', 'RA0']
            right_dots_by_name = {d.get('anatomical_name'): (d['x'], d['y']) for d in right_dots_list if d.get('anatomical_name')}
            if all(name in right_dots_by_name for name in RIGHT_PERIMETER_ORDER):
                right_points_sorted = [right_dots_by_name[name] for name in RIGHT_PERIMETER_ORDER]
                right_points_curved = create_curved_eyebrow_polygon(right_points_sorted, is_left=False)
                draw.polygon(right_points_curved, fill=RIGHT_AREA_COLOR, outline=RIGHT_BORDER_COLOR, width=3)
                right_polygon_drawn = True
            else:
                missing = [n for n in RIGHT_PERIMETER_ORDER if n not in right_dots_by_name]
                print(f"⚠️ Poligono DESTRO NON disegnato - mancano: {missing}")
        except Exception as e:
            print(f"⚠️ Errore disegno poligono destro: {e}")

    # ========== DISEGNA CERCHI, LINEE DI CONNESSIONE E ETICHETTE ==========
    # Colori fissi per nome anatomico (identici a debug_trova_differenze.py)
    ANAT_COLORS_RGBA = {
        'LC1': (0, 255, 0, 230),    'LA0': (0, 204, 255, 230),
        'LA':  (0, 136, 255, 230),  'LC':  (255, 136, 0, 230),
        'LB':  (255, 50, 50, 230),
        'RC1': (255, 255, 0, 230),  'RB':  (255, 0, 255, 230),
        'RC':  (255, 100, 0, 230),  'RA':  (0, 255, 170, 230),
        'RA0': (170, 255, 255, 230),
    }
    DEFAULT_LEFT_COLOR  = (68, 255, 170, 230)
    DEFAULT_RIGHT_COLOR = (255, 170, 68, 230)

    # Linee di connessione: disegnate solo se il poligono NON è stato disegnato
    # (il poligono copre già la geometria del bordo → evita doppio disegno RC1→RB)
    LEFT_LINE_ORDER  = ['LC1', 'LA0', 'LA', 'LC', 'LB']
    RIGHT_LINE_ORDER = ['RC1', 'RB', 'RC', 'RA', 'RA0']

    for side_dots_list, line_order, poly_drawn in [
        (left_dots_list,  LEFT_LINE_ORDER,  left_polygon_drawn),
        (right_dots_list, RIGHT_LINE_ORDER, right_polygon_drawn),
    ]:
        if poly_drawn:
            continue  # Il poligono copre già la geometria, le linee sarebbero doppioni
        if len(side_dots_list) < 2:
            continue
        by_name = {d.get('anatomical_name', ''): d for d in side_dots_list if d.get('anatomical_name')}
        pts_in_order = [by_name[n] for n in line_order if n in by_name]
        for i in range(len(pts_in_order) - 1):
            p1 = pts_in_order[i];  p2 = pts_in_order[i + 1]
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])],
                      fill=(200, 200, 200, 160), width=3)

    # Raggio fisso proporzionale alla larghezza immagine: ~1% della larghezza, min 8 max 30px
    img_w = image_size[0]
    radius = max(8, min(30, round(img_w * 0.01)))

    # Disegna i cerchi sopra le linee (senza etichette testuali)
    for dot in left_dots_list + right_dots_list:
        x, y    = dot['x'], dot['y']
        aname   = dot.get('anatomical_name', '')
        eyebrow = dot.get('eyebrow', 'unknown')

        if aname in ANAT_COLORS_RGBA:
            color = ANAT_COLORS_RGBA[aname]
        elif eyebrow == 'left':
            color = DEFAULT_LEFT_COLOR
        else:
            color = DEFAULT_RIGHT_COLOR

        # Cerchio esterno nero (outline)
        draw.ellipse([x - radius - 3, y - radius - 3,
                      x + radius + 3, y + radius + 3],
                     fill=(0, 0, 0, 200))
        # Cerchio colorato
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                     fill=color)
        # Bordo bianco sottile
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                     outline=(255, 255, 255, 180), width=2)

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

# === API ENDPOINT WHITE DOTS (trova differenze) ===

@app.post("/api/green-dots/analyze")
async def analyze_green_dots(request: WhiteDotsRequest):
    """Rileva i puntini bianchi sulle sopracciglia e restituisce overlay + punti anatomici."""
    try:
        extra = {}
        if request.min_distance is not None:
            extra['min_distance'] = request.min_distance
        if request.outer_px is not None:
            extra['outer_px'] = request.outer_px
        results = process_green_dots_analysis(image_base64=request.image, **extra)
        results = convert_numpy_types(results)
        return results
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore analisi white dots: {e}")

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
        # ── STOP WEBCAM (prima di "webcam" generica per evitare conflitti) ──
        "ferma webcam": {"action": "stopWebcam"},
        "stop webcam": {"action": "stopWebcam"},
        "chiudi webcam": {"action": "stopWebcam"},
        "disattiva webcam": {"action": "stopWebcam"},
        "spegni webcam": {"action": "stopWebcam"},
        "ferma camera": {"action": "stopWebcam"},
        "stop camera": {"action": "stopWebcam"},
        "chiudi camera": {"action": "stopWebcam"},
        # ── START WEBCAM ──
        "avvia webcam": {"action": "startWebcam"},
        "avvia camera": {"action": "startWebcam"},
        "attiva webcam": {"action": "startWebcam"},
        "accendi webcam": {"action": "startWebcam"},
        "apri webcam": {"action": "startWebcam"},
        "webcam": {"action": "startWebcam"},
        # ── SORGENTE ──
        "carica immagine": {"action": "loadImage"},
        "apri immagine": {"action": "loadImage"},
        "immagine": {"action": "loadImage"},
        "carica video": {"action": "loadVideo"},
        "apri video": {"action": "loadVideo"},
        "video": {"action": "loadVideo"},
        # ── TOGGLE OVERLAY ──
        # NOTA: "allinea asse" deve stare prima di "asse" per evitare conflitti substring
        "asse di simmetria": {"action": "toggleAxis"},
        "allinea asse": {"action": "autoAlignAxis"},
        "asse": {"action": "toggleAxis"},
        "landmarks": {"action": "toggleLandmarks"},
        "punti facciali": {"action": "toggleLandmarks"},
        "trova differenze": {"action": "toggleGreenDots"},
        "punti verdi": {"action": "toggleGreenDots"},
        # ── LETTURA COMPARAZIONI GREEN DOTS ──
        # IMPORTANTE: le keyword specifiche devono stare PRIMA di "differenze" generica.
        # Ogni punto anatomico ha molti sinonimi fonetici perché il browser STT
        # può restituire varianti diverse della stessa lettera pronunciata.
        #
        # PUNTO A0 (inizio sopracciglio, versione zero)
        "differenze a zero": {"action": "readGreenDotComparison", "param": "LA0 vs RA0"},
        "differenze ah zero": {"action": "readGreenDotComparison", "param": "LA0 vs RA0"},
        "differenze alfa zero": {"action": "readGreenDotComparison", "param": "LA0 vs RA0"},
        "differenze punto a zero": {"action": "readGreenDotComparison", "param": "LA0 vs RA0"},
        "differenze a0": {"action": "readGreenDotComparison", "param": "LA0 vs RA0"},
        # PUNTO C1 (picco/apice sopracciglio, versione 1)
        "differenze ci uno": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        "differenze c uno": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        "differenze che uno": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        "differenze chi uno": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        "differenze c1": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        "differenze ci 1": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        "differenze punto c uno": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        "differenze punto c1": {"action": "readGreenDotComparison", "param": "LC1 vs RC1"},
        # PUNTO B (coda sopracciglio)
        "differenze bi": {"action": "readGreenDotComparison", "param": "LB vs RB"},
        "differenze b": {"action": "readGreenDotComparison", "param": "LB vs RB"},
        "differenze bee": {"action": "readGreenDotComparison", "param": "LB vs RB"},
        "differenze punto b": {"action": "readGreenDotComparison", "param": "LB vs RB"},
        "differenze coda": {"action": "readGreenDotComparison", "param": "LB vs RB"},
        # PUNTO C (apice sopracciglio)
        "differenze ci": {"action": "readGreenDotComparison", "param": "LC vs RC"},
        "differenze c": {"action": "readGreenDotComparison", "param": "LC vs RC"},
        "differenze che": {"action": "readGreenDotComparison", "param": "LC vs RC"},
        "differenze chi": {"action": "readGreenDotComparison", "param": "LC vs RC"},
        "differenze punto c": {"action": "readGreenDotComparison", "param": "LC vs RC"},
        "differenze apice": {"action": "readGreenDotComparison", "param": "LC vs RC"},
        # PUNTO A (inizio sopracciglio)
        "differenze a": {"action": "readGreenDotComparison", "param": "LA vs RA"},
        "differenze ah": {"action": "readGreenDotComparison", "param": "LA vs RA"},
        "differenze alfa": {"action": "readGreenDotComparison", "param": "LA vs RA"},
        "differenze punto a": {"action": "readGreenDotComparison", "param": "LA vs RA"},
        "differenze inizio": {"action": "readGreenDotComparison", "param": "LA vs RA"},
        # GENERICA: attiva/disattiva overlay
        "differenze": {"action": "toggleGreenDots"},
        "verde": {"action": "toggleGreenDots"},
        "modalità misura": {"action": "toggleMeasureMode"},
        "modalita misura": {"action": "toggleMeasureMode"},
        "misura manuale": {"action": "toggleMeasureMode"},
        # ── ANALISI FACCIALE ──
        "analizza": {"action": "analyzeFace"},
        "analisi viso": {"action": "analyzeFace"},
        "analisi visagistica completa": {"action": "performCompleteAnalysis"},
        "analisi completa": {"action": "performCompleteAnalysis"},
        "visagistica": {"action": "performCompleteAnalysis"},
        # ── MISURAZIONI (specifiche PRIMA delle generiche per evitare conflitti) ──
        "simmetria sopracciglia": {"action": "measureEyebrowSymmetry"},
        "simmetria naso": {"action": "measureNosalWingSymmetry"},
        "dominance score": {"action": "measureDominanceScore"},
        "dominanza": {"action": "measureDominanceScore"},
        "dominante": {"action": "measureDominanceScore"},
        "geometria dominanza": {"action": "measureDominanceScore"},
        "simmetria viso": {"action": "measureFacialSymmetry"},
        "simmetrico": {"action": "measureFacialSymmetry"},
        "simmetrica": {"action": "measureFacialSymmetry"},
        "lato piu grande": {"action": "measureFacialSymmetry"},
        "lato più grande": {"action": "measureFacialSymmetry"},
        "quale lato": {"action": "measureFacialSymmetry"},
        "simmetria": {"action": "measureFacialSymmetry"},
        "proporzioni viso": {"action": "measureFaceProportions"},
        "proporzioni": {"action": "measureFaceProportions"},
        "rotazione occhi": {"action": "measureEyeRotationDiff"},
        "aree occhi": {"action": "measureEyeAreas"},
        "distanza occhi": {"action": "measureEyeDistance"},
        "larghezza viso": {"action": "measureFaceWidth"},
        "altezza viso": {"action": "measureFaceHeight"},
        "larghezza naso": {"action": "measureNoseWidth"},
        "altezza naso": {"action": "measureNoseHeight"},
        "larghezza bocca": {"action": "measureMouthWidth"},
        "larghezza fronte": {"action": "measureForeheadWidth"},
        "stima eta": {"action": "estimate_age"},
        "stima età": {"action": "estimate_age"},
        "quanti anni": {"action": "estimate_age"},
        "età": {"action": "estimate_age"},
        "eta": {"action": "estimate_age"},
        # ── CANVAS ──
        "resetta canvas": {"action": "clearCanvas"},
        "cancella canvas": {"action": "clearCanvas"},
        "pulisci canvas": {"action": "clearCanvas"},
        "pulisci misurazioni": {"action": "clearMeasurements"},
        "cancella misurazioni": {"action": "clearMeasurements"},
        "cancella": {"action": "clearCanvas"},
        # ── ROTAZIONI ──
        "ruota sinistra": {"action": "rotateLeft90"},
        "ruota antiorario": {"action": "rotateLeft90"},
        "ruota destra": {"action": "rotateRight90"},
        "ruota orario": {"action": "rotateRight90"},
        "ruota un grado sinistra": {"action": "rotateLeft1"},
        "ruota un grado destra": {"action": "rotateRight1"},
        "allinea": {"action": "autoAlignAxis"},
        "raddrizza": {"action": "autoAlignAxis"},
        # ── CORREZIONE SOPRACCIGLIA ──
        "sopracciglio sinistro": {"action": "analyzeLeftEyebrow"},
        "sopracciglio destro": {"action": "analyzeRightEyebrow"},
        "correggimi la progettazione": {"action": "analyze_eyebrow_design"},
        "correggi progettazione": {"action": "analyze_eyebrow_design"},
        "correzione progettazione": {"action": "analyze_eyebrow_design"},
        "analizza progettazione": {"action": "analyze_eyebrow_design"},
        "preferenza destra": {"action": "show_left_eyebrow_with_voice"},
        "preferenza a destra": {"action": "show_left_eyebrow_with_voice"},
        "correzione destra": {"action": "show_left_eyebrow_with_voice"},
        "correzione a destra": {"action": "show_left_eyebrow_with_voice"},
        "preferenza sinistra": {"action": "show_right_eyebrow_with_voice"},
        "preferenza a sinistra": {"action": "show_right_eyebrow_with_voice"},
        "correzione sinistra": {"action": "show_right_eyebrow_with_voice"},
        "correzione a sinistra": {"action": "show_right_eyebrow_with_voice"},
    }
    
    # Cerca match
    for key, value in keyword_map.items():
        if key in keyword:
            return VoiceKeywordResponse(
                success=True,
                keyword=keyword,
                action=value["action"],
                message=value.get("message", ""),
                param=value.get("param", None)
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
# DEBUG PIPELINE TROVA DIFFERENZE – step-by-step con immagini
# ---------------------------------------------------------------------------

def _img_to_b64(img_bgr: np.ndarray, quality: int = 82) -> str:
    """Codifica un'immagine BGR in base64 JPEG per la risposta JSON."""
    _, buf = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def _resize_debug(img: np.ndarray, max_side: int = 1200) -> np.ndarray:
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img


def _upscale_for_labels(img: np.ndarray, target_w: int = 2400) -> tuple:
    """Ingrandisce l'immagine per disegnarci sopra etichette leggibili; restituisce (img_up, scale)."""
    h, w = img.shape[:2]
    scale = target_w / w
    img_up = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
    return img_up, scale


def _generate_debug_steps(img_bgr: np.ndarray,
                           target_width: int        = None,
                           outer_px: int            = None,
                           luma_min: int            = None,
                           luma_max: int            = None,
                           luma_lb: int             = None,
                           luma_max_lb: int         = None,
                           highlight_thresh_inner: int    = None,
                           highlight_strength_inner: float = None,
                           highlight_thresh_outer: int    = None,
                           highlight_strength_outer: float = None,
                           min_circularity_inner: float = None,
                           max_circularity_inner: float = None,
                           min_perimeter_inner: int = None,
                           max_perimeter_inner: int = None,
                           min_circularity_outer: float = None,
                           max_circularity_outer: float = None,
                           min_perimeter_outer: int = None,
                           max_perimeter_outer: int = None,
                           min_distance: int = None,
                           **_kwargs) -> list:
    """
    Pipeline debug step-by-step: zona espansa → highlight boost → rilevamento → anatomico.
    """
    try:
        from eyebrows import extract_eyebrows_from_array
    except ImportError:
        return [{"step": 0, "name": "Errore", "description": "Modulo eyebrows (dlib) non disponibile.", "image_b64": ""}]

    _dat = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..',
        'face-landmark-localization-master', 'shape_predictor_68_face_landmarks.dat'
    ))

    steps = []

    def _push(step_n, name, desc, img, hires=False, extra=None):
        max_s = 2400 if hires else 1200
        qual  = 90   if hires else 82
        entry = {
            "step": step_n,
            "name": name,
            "description": desc,
            "image_b64": _img_to_b64(_resize_debug(img.copy(), max_side=max_s), quality=qual)
        }
        if extra:
            entry.update(extra)
        steps.append(entry)

    TARGET_WIDTH       = target_width           if target_width           is not None else WHITE_DOTS_TARGET_WIDTH
    OUTER_PX           = outer_px               if outer_px               is not None else WHITE_DOTS_OUTER_PX
    LUMA_MIN           = luma_min               if luma_min               is not None else WHITE_DOTS_LUMA_MIN
    LUMA_MAX           = luma_max               if luma_max               is not None else WHITE_DOTS_LUMA_MAX
    LUMA_LB            = luma_lb                if luma_lb                is not None else WHITE_DOTS_LUMA_LB
    LUMA_MAX_LB        = luma_max_lb            if luma_max_lb            is not None else WHITE_DOTS_LUMA_MAX_LB
    HL_THRESH_INNER    = highlight_thresh_inner   if highlight_thresh_inner   is not None else WHITE_DOTS_HIGHLIGHT_THRESH_INNER
    HL_STRENGTH_INNER  = highlight_strength_inner if highlight_strength_inner is not None else WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER
    HL_THRESH_OUTER    = highlight_thresh_outer   if highlight_thresh_outer   is not None else WHITE_DOTS_HIGHLIGHT_THRESH_OUTER
    HL_STRENGTH_OUTER  = highlight_strength_outer if highlight_strength_outer is not None else WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER
    MIN_CIRC_INNER     = min_circularity_inner  if min_circularity_inner  is not None else WHITE_DOTS_MIN_CIRCULARITY_INNER
    MAX_CIRC_INNER     = max_circularity_inner  if max_circularity_inner  is not None else WHITE_DOTS_MAX_CIRCULARITY_INNER
    MIN_PERI_INNER     = min_perimeter_inner    if min_perimeter_inner    is not None else WHITE_DOTS_MIN_PERIMETER_INNER
    MAX_PERI_INNER     = max_perimeter_inner    if max_perimeter_inner    is not None else WHITE_DOTS_MAX_PERIMETER_INNER
    MIN_CIRC_OUTER     = min_circularity_outer  if min_circularity_outer  is not None else WHITE_DOTS_MIN_CIRCULARITY_OUTER
    MAX_CIRC_OUTER     = max_circularity_outer  if max_circularity_outer  is not None else WHITE_DOTS_MAX_CIRCULARITY_OUTER
    MIN_PERI_OUTER     = min_perimeter_outer    if min_perimeter_outer    is not None else WHITE_DOTS_MIN_PERIMETER_OUTER
    MAX_PERI_OUTER     = max_perimeter_outer    if max_perimeter_outer    is not None else WHITE_DOTS_MAX_PERIMETER_OUTER
    MIN_DISTANCE       = min_distance           if min_distance           is not None else WHITE_DOTS_MIN_DISTANCE

    _orig_h, _orig_w = img_bgr.shape[:2]
    if _orig_w != TARGET_WIDTH:
        _scale  = TARGET_WIDTH / _orig_w
        img_bgr = cv2.resize(img_bgr, (TARGET_WIDTH, max(1, round(_orig_h * _scale))),
                             interpolation=cv2.INTER_AREA if _orig_w > TARGET_WIDTH else cv2.INTER_LINEAR)

    h, w = img_bgr.shape[:2]

    res_dlib = extract_eyebrows_from_array(img_bgr, predictor_path=_dat)
    if not res_dlib["face_detected"]:
        _push(1, "Errore dlib", "Volto non rilevato da dlib — impossibile procedere.", img_bgr)
        return steps

    # Highlight boost separato per zona interna e strip esterna
    gray_raw = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_inner_f = gray_raw.copy()
    mask_hi_inner = gray_raw >= HL_THRESH_INNER
    gray_inner_f[mask_hi_inner] = np.clip(
        gray_raw[mask_hi_inner] + HL_STRENGTH_INNER * (255.0 - gray_raw[mask_hi_inner]), 0, 255)
    gray_inner = gray_inner_f.astype(np.uint8)
    gray_outer_f = gray_raw.copy()
    mask_hi_outer = gray_raw >= HL_THRESH_OUTER
    gray_outer_f[mask_hi_outer] = np.clip(
        gray_raw[mask_hi_outer] + HL_STRENGTH_OUTER * (255.0 - gray_raw[mask_hi_outer]), 0, 255)
    gray_outer = gray_outer_f.astype(np.uint8)

    k_outer = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OUTER_PX*2+1, OUTER_PX*2+1))

    # Step 1 – zona di ricerca espansa con strip LB/RB evidenziata
    step1 = img_bgr.copy()
    side_colors = {'left': (0, 255, 255), 'right': (0, 255, 0)}
    expanded_masks = {}
    col_idx = np.indices((h, w))[1]
    for side, mask_key in [('left', 'left_mask'), ('right', 'right_mask')]:
        mask = res_dlib[mask_key]
        if not np.any(mask):
            continue
        expanded = cv2.dilate(mask, k_outer, iterations=1)
        expanded_masks[side] = expanded

        ys_m, xs_m = np.where(mask > 0)
        x_min_mask, x_max_mask = int(xs_m.min()), int(xs_m.max())
        if side == 'left':
            lb_strip = (expanded > 0) & (col_idx <= x_min_mask + OUTER_PX)
        else:
            lb_strip = (expanded > 0) & (col_idx >= x_max_mask - OUTER_PX)

        col = side_colors[side]
        ov = step1.copy()
        ov[(expanded > 0) & ~lb_strip] = (col[0]//2, col[1]//2, col[2]//2)
        ov[mask > 0] = (col[0]//3, col[1]//3, col[2]//2)
        ov[lb_strip] = (0, 120, 255)
        cv2.addWeighted(ov, 0.40, step1, 0.60, 0, step1)

        cnts, _ = cv2.findContours(expanded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(step1, cnts, -1, col, max(2, h//400))

    _push(1, "Zona di ricerca espansa",
          f"Ciano/Verde=zona principale | Arancio=strip LB/RB esclusiva | espansione {OUTER_PX}px",
          step1)

    # Step 2 – highlight boost + pixel rilevati + circolarità/perimetro
    # Colori pixel overlay:
    #   Giallo  (0,220,255) = passa soglie PRINCIPALI (luma_min/max)
    #   Arancio (0,140,255) = passa solo soglie LB/RB (luma_lb/luma_max_lb)
    # Colori blob:
    #   Grigio pieno   = scartato per circolarità o perimetro
    #   Ciano/Verde    = selezionato (zona interna)
    #   Arancio vivace = selezionato (strip LB/RB)
    # Usa gray_inner come sfondo (zona principale)
    gray_bgr = cv2.cvtColor(gray_inner, cv2.COLOR_GRAY2BGR)
    step2 = gray_bgr.copy()
    all_candidates_pre_nms = []  # Tutti i blob prima di NMS globale
    all_discarded_inner = []     # Blob scartati da filtri inner
    all_discarded_outer = []     # Blob scartati da filtri outer
    total_hit = 0
    R_up = max(6, h // 200)  # raggio cerchio blob sull'immagine
    # blob con area < 4px = rumore sub-pixel: cerchietto minimo, nessun popup
    _MIN_AREA_LABEL = 4

    for side in ['left', 'right']:
        expanded = expanded_masks.get(side)
        if expanded is None:
            continue

        white_mask = np.zeros((h, w), dtype=np.uint8)
        white_mask[(gray_inner >= LUMA_MIN) & (gray_inner <= LUMA_MAX) & (expanded > 0)] = 255

        mask_dbg = res_dlib[f'{side}_mask']
        ys_m, xs_m = np.where(mask_dbg > 0)
        x_min_mask, x_max_mask = int(xs_m.min()), int(xs_m.max())
        if side == 'left':
            lb_zone = (expanded > 0) & (col_idx <= x_min_mask + OUTER_PX)
        else:
            lb_zone = (expanded > 0) & (col_idx >= x_max_mask - OUTER_PX)
        lb_mask = np.zeros((h, w), dtype=np.uint8)
        lb_mask[(gray_outer >= LUMA_LB) & (gray_outer <= LUMA_MAX_LB) & lb_zone] = 255

        n_hit = int(np.sum(white_mask > 0))
        total_hit += n_hit

        # Pixel overlay su step2 a 1200px
        step2[white_mask > 0] = (0, 220, 255)
        lb_only = lb_mask.copy()
        lb_only[white_mask > 0] = 0
        step2[lb_only > 0] = (0, 140, 255)

        # ── Connected components principali (INNER) ───────────────────────────
        n_lbl, lbl_map, stats_cc, centroids = cv2.connectedComponentsWithStats(white_mask, 8)
        cands = []
        discarded_inner = []
        for lbl in range(1, n_lbl):
            area = int(stats_cc[lbl, cv2.CC_STAT_AREA])
            cx = int(round(float(centroids[lbl, 0])))
            cy = int(round(float(centroids[lbl, 1])))
            blob_mask = (lbl_map == lbl).astype(np.uint8)
            cnts_b, _ = cv2.findContours(blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not cnts_b:
                discarded_inner.append((cx, cy, area, 0.0, 0.0, "no cnt"))
                continue
            perimeter = cv2.arcLength(cnts_b[0], True)
            circularity = (4.0 * math.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
            if perimeter < MIN_PERI_INNER or perimeter > MAX_PERI_INNER:
                discarded_inner.append((cx, cy, area, perimeter, circularity, f"peri={perimeter:.0f}"))
                continue
            if circularity < MIN_CIRC_INNER or circularity > MAX_CIRC_INNER:
                discarded_inner.append((cx, cy, area, perimeter, circularity, f"circ={circularity:.2f}"))
                continue
            mean_luma = float(np.mean(gray_inner[lbl_map == lbl]))
            cands.append({'x': cx, 'y': cy, 'size': area, 'score': mean_luma / 255.0 * 100.0,
                          'perim': perimeter, 'circ': circularity, 'side': side, 'zone': 'inner'})

        # ── Connected components LB/RB (OUTER) ───────────────────────────────
        n_lb, lbl_lb, stats_lb, ctr_lb = cv2.connectedComponentsWithStats(lb_mask, 8)
        lb_cands = []
        discarded_outer = []
        for lbl in range(1, n_lb):
            area = int(stats_lb[lbl, cv2.CC_STAT_AREA])
            cx = int(round(float(ctr_lb[lbl, 0])))
            cy = int(round(float(ctr_lb[lbl, 1])))
            blob_mask = (lbl_lb == lbl).astype(np.uint8)
            cnts_b, _ = cv2.findContours(blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not cnts_b:
                discarded_outer.append((cx, cy, area, 0.0, 0.0, "no cnt"))
                continue
            perimeter = cv2.arcLength(cnts_b[0], True)
            circularity = (4.0 * math.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
            if perimeter < MIN_PERI_OUTER or perimeter > MAX_PERI_OUTER:
                discarded_outer.append((cx, cy, area, perimeter, circularity, f"peri={perimeter:.0f}"))
                continue
            if circularity < MIN_CIRC_OUTER or circularity > MAX_CIRC_OUTER:
                discarded_outer.append((cx, cy, area, perimeter, circularity, f"circ={circularity:.2f}"))
                continue
            mean_luma = float(np.mean(gray_outer[lbl_lb == lbl]))
            lb_cands.append({'x': cx, 'y': cy, 'size': area,
                              'score': mean_luma / 255.0 * 100.0, 'forced': True,
                              'perim': perimeter, 'circ': circularity, 'side': side, 'zone': 'outer'})

        # Accumula tutti i candidati (inner + outer) per NMS globale
        all_candidates_pre_nms.extend(cands + lb_cands)
        # Accumula i blob scartati con tag del lato
        for item in discarded_inner:
            all_discarded_inner.append(item + (side,))
        for item in discarded_outer:
            all_discarded_outer.append(item + (side,))

    # ── Applica NMS GLOBALMENTE su tutti i blob di entrambi i lati ────────────────
    before_nms = len(all_candidates_pre_nms)
    rejected_by_nms = []  # Blob eliminati da NMS
    if MIN_DISTANCE > 0 and before_nms > 0:
        print(f"\n   [DEBUG] ===== NMS GLOBALE =====")
        print(f"   [DEBUG] min_distance = {MIN_DISTANCE}px")
        print(f"   [DEBUG] Blob pre-NMS = {before_nms}")
        # Stampa coordinate di tutti i blob pre-NMS
        for i, b in enumerate(all_candidates_pre_nms):
            forced_tag = " [FORCED]" if b.get('forced') else ""
            print(f"   [PRE-NMS #{i+1}] ({b['x']}, {b['y']}) score={b.get('score',0):.1f} circ={b.get('circ',0):.3f} side={b.get('side')} zone={b.get('zone')}{forced_tag}")
        
        all_candidates_post_nms, rejected_by_nms = _nms_by_distance(all_candidates_pre_nms, MIN_DISTANCE, debug=True)
        
        print(f"   [DEBUG] Blob post-NMS = {len(all_candidates_post_nms)} (eliminati {len(rejected_by_nms)})")
        print(f"   [DEBUG] ===== FINE NMS =====\n")
    else:
        all_candidates_post_nms = all_candidates_pre_nms
    after_nms = len(all_candidates_post_nms)
    
    # Separa nuovamente per lato
    top_per_side = {
        'left': [d for d in all_candidates_post_nms if d.get('side') == 'left'],
        'right': [d for d in all_candidates_post_nms if d.get('side') == 'right']
    }

    # ── Prepara lista blob da disegnare sullo Step 2 (post-NMS) ──────────────────
    _all_blobs_draw = []  # lista dict blob da disegnare e inviare al frontend

    # Blob scartati da filtri circolarità/perimetro (inner)
    for cx, cy, area, perim, circ, reason, side in all_discarded_inner:
        side_tag = "SX" if side == 'left' else "DX"
        is_noise = area < _MIN_AREA_LABEL
        if "peri" in reason:
            verdict = f"peri {perim:.0f}px fuori range [{MIN_PERI_INNER}–{MAX_PERI_INNER}]"
        elif "circ" in reason:
            verdict = f"circ {circ:.3f} fuori range [{MIN_CIRC_INNER:.1f}–{MAX_CIRC_INNER:.1f}]"
        else:
            verdict = reason
        _all_blobs_draw.append({
            "cx": cx, "cy": cy, "area": area, "perim": round(perim, 1),
            "circ": round(circ, 4), "luma": None,
            "type": "noise" if is_noise else "rejected",
            "zone": "inner", "side": side_tag,
            "verdict": verdict,
            "hex": "#a06464" if not is_noise else "#504040",
            "cv_color": (160, 100, 100) if not is_noise else (80, 55, 55),
        })

    # Blob scartati da filtri circolarità/perimetro (outer)
    for cx, cy, area, perim, circ, reason, side in all_discarded_outer:
        side_tag = "SX" if side == 'left' else "DX"
        is_noise = area < _MIN_AREA_LABEL
        if "peri" in reason:
            verdict = f"peri {perim:.0f}px fuori range [{MIN_PERI_OUTER}–{MAX_PERI_OUTER}]"
        elif "circ" in reason:
            verdict = f"circ {circ:.3f} fuori range [{MIN_CIRC_OUTER:.1f}–{MAX_CIRC_OUTER:.1f}]"
        else:
            verdict = reason
        _all_blobs_draw.append({
            "cx": cx, "cy": cy, "area": area, "perim": round(perim, 1),
            "circ": round(circ, 4), "luma": None,
            "type": "noise" if is_noise else "rejected",
            "zone": "outer", "side": side_tag,
            "verdict": verdict,
            "hex": "#c89650" if not is_noise else "#504030",
            "cv_color": (200, 150, 80) if not is_noise else (80, 65, 40),
        })

    # Blob eliminati da NMS (disegna PRIMA degli accettati per sovrapposizione corretta)
    for d in rejected_by_nms:
        side = d.get('side')
        side_tag = "SX" if side == 'left' else "DX"
        zone = d.get('zone', 'unknown')
        _all_blobs_draw.append({
            "cx": d['x'], "cy": d['y'], "area": d['size'],
            "perim": round(d.get('perim', 0), 1),
            "circ": round(d.get('circ', 0), 4),
            "luma": round(d['score'], 1),
            "type": "rejected_nms",
            "zone": zone, "side": side_tag,
            "verdict": f"Eliminato NMS: {d.get('nms_reason', 'troppo vicino')}",
            "hex": "#ff6644",  # Arancione/rosso per NMS
            "cv_color": (255, 102, 68),
        })

    # Blob accettati (post-NMS globale)
    for i, d in enumerate(all_candidates_post_nms):
        side = d.get('side')
        side_tag = "SX" if side == 'left' else "DX"
        col_main = (0, 255, 255) if side == 'left' else (0, 255, 0)
        col_lb   = (0, 160, 255)
        is_lb = d.get('forced', False)
        col_hex = "#00a0ff" if is_lb else ("#00ffff" if side == 'left' else "#00ff00")
        _all_blobs_draw.append({
            "cx": d['x'], "cy": d['y'], "area": d['size'],
            "perim": round(d.get('perim', 0), 1),
            "circ": round(d.get('circ', 0), 4),
            "luma": round(d['score'], 1),
            "type": "accepted",
            "zone": "outer/LB" if is_lb else "inner",
            "side": side_tag,
            "verdict": f"OK #{i+1}  score={d['score']:.0f}%",
            "hex": col_hex,
            "cv_color": col_lb if is_lb else col_main,
        })

    # ── Disegna solo cerchietti sull'immagine (niente etichette) ─────────────
    for b in _all_blobs_draw:
        cx, cy, col = b["cx"], b["cy"], b["cv_color"]
        if b["type"] == "noise":
            cv2.circle(step2, (cx, cy), 2, col, -1)
        elif b["type"] == "rejected" or b["type"] == "rejected_nms":
            cv2.circle(step2, (cx, cy), max(4, R_up // 2), (45, 30, 30), -1)
            cv2.circle(step2, (cx, cy), max(4, R_up // 2) + 1, col, 1)
        else:  # accepted
            cv2.circle(step2, (cx, cy), R_up, col, -1)
            cv2.circle(step2, (cx, cy), R_up + 2, (255, 255, 255), 2)

    # serializza blob per il frontend (coordinate normalizzate 0–1)
    _blobs_json = []
    for b in _all_blobs_draw:
        _blobs_json.append({
            "x": round(b["cx"] / w, 5),  # normalizzato larghezza immagine pipeline
            "y": round(b["cy"] / h, 5),
            "area": b["area"], "perim": b["perim"], "circ": b["circ"],
            "luma": b["luma"], "type": b["type"],
            "zone": b["zone"], "side": b["side"],
            "verdict": b["verdict"], "hex": b["hex"],
        })

    # Legenda in alto a sinistra
    legend = [
        ((0, 220, 255),  "pixel inner (luma_min-luma_max su gray_inner)"),
        ((0, 140, 255),  "pixel outer LB/RB (luma_lb-luma_max_lb su gray_outer)"),
        ((0, 255, 255),  "blob SX accettato (inner)"),
        ((0, 255,   0),  "blob DX accettato (inner)"),
        ((0, 160, 255),  "blob accettato (outer LB/RB)"),
        ((255, 102, 68), "blob eliminato NMS (troppo vicino)"),
        ((160,100,100),  "blob scartato inner (area>=4px, circ/peri fuori range)"),
        ((200,150, 80),  "blob scartato outer (area>=4px, circ/peri fuori range)"),
        ((80, 60, 60),   "rumore sub-pixel (area<4px, nessuna etichetta)"),
    ]
    lx, ly = 8, 16
    leg_lh = 18
    leg_fs = 0.38
    box_h  = len(legend) * leg_lh + 8
    cv2.rectangle(step2, (lx - 4, ly - 14), (lx + 450, ly + box_h - 6), (20, 20, 20), -1)
    for color, text in legend:
        cv2.circle(step2, (lx + 6, ly - 3), 5, color, -1)
        cv2.putText(step2, text, (lx + 16, ly), cv2.FONT_HERSHEY_SIMPLEX,
                    leg_fs, (220, 220, 220), 1, cv2.LINE_AA)
        ly += leg_lh

    n_top = sum(len(v) for v in top_per_side.values())
    nms_info = f"NMS: {before_nms}→{after_nms} blob (eliminati {before_nms - after_nms}, min_dist={MIN_DISTANCE}px)" if MIN_DISTANCE > 0 else "NMS disattivato (min_dist=0)"
    _push(2, f"Rilevamento blob — click sui cerchietti per dettagli",
          f"Ciano/Verde=accettato inner | Blu=accettato outer | Rosso=scartato | Grigio=rumore (<4px) | "
          f"inner circ[{MIN_CIRC_INNER:.1f}–{MAX_CIRC_INNER:.1f}] peri[{MIN_PERI_INNER}–{MAX_PERI_INNER}] | "
          f"outer circ[{MIN_CIRC_OUTER:.1f}–{MAX_CIRC_OUTER:.1f}] peri[{MIN_PERI_OUTER}–{MAX_PERI_OUTER}] | "
          f"⚡ {nms_info}",
          step2, extra={"blobs": _blobs_json, "img_w": w, "img_h": h})

    # Step 3 – ordine anatomico finale
    step3 = img_bgr.copy()
    final_left  = sort_points_anatomical(top_per_side.get('left', []),  is_left=True)
    final_right = sort_points_anatomical(top_per_side.get('right', []), is_left=False)
    anat_colors = [(255,100,100),(100,255,100),(100,100,255),(255,255,100),(255,100,255)]
    for pts, is_left in [(final_left, True), (final_right, False)]:
        for i, d in enumerate(pts):
            col = anat_colors[i % len(anat_colors)]
            cv2.circle(step3, (d['x'], d['y']), max(8, h//180), col, -1)
            cv2.circle(step3, (d['x'], d['y']), max(10, h//180)+2, (255, 255, 255), 2)
            label = d.get('anatomical_name', str(i+1))
            cv2.putText(step3, label, (d['x']+8, d['y']+5),
                        cv2.FONT_HERSHEY_SIMPLEX, max(0.35, h/4000.0),
                        (255, 255, 255), max(1, h//900))
    n_final = len(final_left) + len(final_right)
    _push(3, "Ordine anatomico finale",
          f"{n_final} punti | LC1→LA0→LA→LC→LB (sx) | RC1→RB→RC→RA→RA0 (dx)",
          step3)

    return steps


class WhiteDotsDebugRequest(BaseModel):
    image: str
    target_width:           int   = WHITE_DOTS_TARGET_WIDTH
    outer_px:               int   = WHITE_DOTS_OUTER_PX
    luma_min:               int   = WHITE_DOTS_LUMA_MIN
    luma_max:               int   = WHITE_DOTS_LUMA_MAX
    luma_lb:                int   = WHITE_DOTS_LUMA_LB
    luma_max_lb:            int   = WHITE_DOTS_LUMA_MAX_LB
    highlight_thresh_inner:       int   = WHITE_DOTS_HIGHLIGHT_THRESH_INNER
    highlight_strength_inner:     float = WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER
    highlight_thresh_outer:       int   = WHITE_DOTS_HIGHLIGHT_THRESH_OUTER
    highlight_strength_outer:     float = WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER
    min_circularity_inner:  float = WHITE_DOTS_MIN_CIRCULARITY_INNER
    max_circularity_inner:  float = WHITE_DOTS_MAX_CIRCULARITY_INNER
    min_perimeter_inner:    int   = WHITE_DOTS_MIN_PERIMETER_INNER
    max_perimeter_inner:    int   = WHITE_DOTS_MAX_PERIMETER_INNER
    min_circularity_outer:  float = WHITE_DOTS_MIN_CIRCULARITY_OUTER
    max_circularity_outer:  float = WHITE_DOTS_MAX_CIRCULARITY_OUTER
    min_perimeter_outer:    int   = WHITE_DOTS_MIN_PERIMETER_OUTER
    max_perimeter_outer:    int   = WHITE_DOTS_MAX_PERIMETER_OUTER
    min_distance:           int   = WHITE_DOTS_MIN_DISTANCE


@app.post("/api/debug/trova-differenze")
async def debug_trova_differenze(payload: WhiteDotsDebugRequest):
    """
    Esegue la pipeline step-by-step e restituisce 3 step di debug.
    Risposta: { success: true, steps: [...], total: 3 }
    """
    try:
        import base64 as _b64
        b64 = payload.image
        if ',' in b64:
            b64 = b64.split(',', 1)[1]
        img_bytes = _b64.b64decode(b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("Impossibile decodificare l'immagine")

        steps = _generate_debug_steps(
            img_bgr,
            target_width=payload.target_width,
            outer_px=payload.outer_px,
            luma_min=payload.luma_min,
            luma_max=payload.luma_max,
            luma_lb=payload.luma_lb,
            luma_max_lb=payload.luma_max_lb,
            highlight_thresh_inner=payload.highlight_thresh_inner,
            highlight_strength_inner=payload.highlight_strength_inner,
            highlight_thresh_outer=payload.highlight_thresh_outer,
            highlight_strength_outer=payload.highlight_strength_outer,
            min_circularity_inner=payload.min_circularity_inner,
            max_circularity_inner=payload.max_circularity_inner,
            min_perimeter_inner=payload.min_perimeter_inner,
            max_perimeter_inner=payload.max_perimeter_inner,
            min_circularity_outer=payload.min_circularity_outer,
            max_circularity_outer=payload.max_circularity_outer,
            min_perimeter_outer=payload.min_perimeter_outer,
            max_perimeter_outer=payload.max_perimeter_outer,
            min_distance=payload.min_distance,
        )
        return {"success": True, "steps": steps, "total": len(steps)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore debug trova-differenze: {e}")


@app.get("/api/debug/params")
async def get_debug_params():
    """Restituisce i parametri attuali della pipeline white-dots."""
    return {"success": True, "params": _load_white_dots_params()}


@app.put("/api/debug/params/approve")
async def approve_debug_params(payload: WhiteDotsDebugRequest):
    """Approva i parametri: salva su JSON e aggiorna le costanti globali in memoria."""
    global WHITE_DOTS_TARGET_WIDTH, WHITE_DOTS_OUTER_PX
    global WHITE_DOTS_LUMA_MIN, WHITE_DOTS_LUMA_MAX
    global WHITE_DOTS_LUMA_LB, WHITE_DOTS_LUMA_MAX_LB
    global WHITE_DOTS_HIGHLIGHT_THRESH_INNER, WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER
    global WHITE_DOTS_HIGHLIGHT_THRESH_OUTER, WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER
    global WHITE_DOTS_MIN_CIRCULARITY_INNER, WHITE_DOTS_MAX_CIRCULARITY_INNER
    global WHITE_DOTS_MIN_PERIMETER_INNER, WHITE_DOTS_MAX_PERIMETER_INNER
    global WHITE_DOTS_MIN_CIRCULARITY_OUTER, WHITE_DOTS_MAX_CIRCULARITY_OUTER
    global WHITE_DOTS_MIN_PERIMETER_OUTER, WHITE_DOTS_MAX_PERIMETER_OUTER
    global WHITE_DOTS_MIN_DISTANCE
    params = {
        "target_width":           payload.target_width,
        "outer_px":               payload.outer_px,
        "luma_min":               payload.luma_min,
        "luma_max":               payload.luma_max,
        "luma_lb":                payload.luma_lb,
        "luma_max_lb":            payload.luma_max_lb,
        "highlight_thresh_inner":       payload.highlight_thresh_inner,
        "highlight_strength_inner":     payload.highlight_strength_inner,
        "highlight_thresh_outer":       payload.highlight_thresh_outer,
        "highlight_strength_outer":     payload.highlight_strength_outer,
        "min_circularity_inner":  payload.min_circularity_inner,
        "max_circularity_inner":  payload.max_circularity_inner,
        "min_perimeter_inner":    payload.min_perimeter_inner,
        "max_perimeter_inner":    payload.max_perimeter_inner,
        "min_circularity_outer":  payload.min_circularity_outer,
        "max_circularity_outer":  payload.max_circularity_outer,
        "min_perimeter_outer":    payload.min_perimeter_outer,
        "max_perimeter_outer":    payload.max_perimeter_outer,
        "min_distance":           payload.min_distance,
    }
    _save_white_dots_params(params)
    WHITE_DOTS_TARGET_WIDTH          = payload.target_width
    WHITE_DOTS_OUTER_PX              = payload.outer_px
    WHITE_DOTS_LUMA_MIN              = payload.luma_min
    WHITE_DOTS_LUMA_MAX              = payload.luma_max
    WHITE_DOTS_LUMA_LB               = payload.luma_lb
    WHITE_DOTS_LUMA_MAX_LB           = payload.luma_max_lb
    WHITE_DOTS_HIGHLIGHT_THRESH_INNER    = payload.highlight_thresh_inner
    WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER  = payload.highlight_strength_inner
    WHITE_DOTS_HIGHLIGHT_THRESH_OUTER    = payload.highlight_thresh_outer
    WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER  = payload.highlight_strength_outer
    WHITE_DOTS_MIN_CIRCULARITY_INNER = payload.min_circularity_inner
    WHITE_DOTS_MAX_CIRCULARITY_INNER = payload.max_circularity_inner
    WHITE_DOTS_MIN_PERIMETER_INNER   = payload.min_perimeter_inner
    WHITE_DOTS_MAX_PERIMETER_INNER   = payload.max_perimeter_inner
    WHITE_DOTS_MIN_CIRCULARITY_OUTER = payload.min_circularity_outer
    WHITE_DOTS_MAX_CIRCULARITY_OUTER = payload.max_circularity_outer
    WHITE_DOTS_MIN_PERIMETER_OUTER   = payload.min_perimeter_outer
    WHITE_DOTS_MAX_PERIMETER_OUTER   = payload.max_perimeter_outer
    WHITE_DOTS_MIN_DISTANCE          = payload.min_distance
    return {"success": True, "message": "Parametri approvati e applicati", "params": params}


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
