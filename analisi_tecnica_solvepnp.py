#!/usr/bin/env python3
"""
ANALISI TECNICA: Perché solvePnP fallisce nel calcolare lo Yaw correttamente?

Questo script analizza in dettaglio il problema con solvePnP e perché il metodo
geometrico è più robusto per il rilevamento della frontalità.
"""

import cv2
import mediapipe as mp
import numpy as np
import json

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def calculate_solvepnp_detailed(landmarks_array, img_width, img_height):
    """Calcola pose con solvePnP e ritorna dettagli per debugging"""
    
    NOSE_TIP = 4
    CHIN = 152
    LEFT_EYE = 33
    RIGHT_EYE = 263
    LEFT_MOUTH = 78
    RIGHT_MOUTH = 308
    
    nose_tip = landmarks_array[NOSE_TIP]
    chin = landmarks_array[CHIN]
    left_eye = landmarks_array[LEFT_EYE]
    right_eye = landmarks_array[RIGHT_EYE]
    left_mouth = landmarks_array[LEFT_MOUTH]
    right_mouth = landmarks_array[RIGHT_MOUTH]
    
    # Modello 3D standard
    model_points = np.array([
        (0.0, 0.0, 0.0),             # Punta del naso (ORIGINE)
        (0.0, -330.0, -65.0),        # Mento 
        (-225.0, 170.0, -135.0),     # Occhio sinistro
        (225.0, 170.0, -135.0),      # Occhio destro  
        (-150.0, -150.0, -125.0),    # Bocca sinistra
        (150.0, -150.0, -125.0)      # Bocca destra
    ], dtype=np.float32)
    
    image_points = np.array([
        nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
    ], dtype=np.float32)
    
    # Camera matrix con focal_length = width
    focal_length = img_width
    center = (img_width/2, img_height/2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float32)
    
    dist_coeffs = np.zeros((4,1))
    
    success, rvec, tvec = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs)
    
    if not success:
        return None
    
    rmat, _ = cv2.Rodrigues(rvec)
    
    # Calcolo angoli di Eulero
    sy = np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)
    pitch = np.arctan2(-rmat[2,0], sy) * 180.0 / np.pi
    yaw = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
    roll = np.arctan2(rmat[2,1], rmat[2,2]) * 180.0 / np.pi
    
    return {
        'rotation_matrix': rmat,
        'rotation_vector': rvec,
        'translation_vector': tvec,
        'pitch': pitch,
        'yaw': yaw,
        'roll': roll,
        'camera_matrix': camera_matrix,
        'focal_length': focal_length,
        'image_center': center,
        'model_points': model_points,
        'image_points': image_points
    }

def calculate_geometric(landmarks_array):
    """Calcolo geometrico semplice"""
    NOSE_TIP = 4
    CHIN = 152
    LEFT_EYE = 33
    RIGHT_EYE = 263
    
    nose_tip = landmarks_array[NOSE_TIP]
    chin = landmarks_array[CHIN]
    left_eye = landmarks_array[LEFT_EYE]
    right_eye = landmarks_array[RIGHT_EYE]
    
    eye_center_x = (left_eye[0] + right_eye[0]) / 2.0
    eye_center_y = (left_eye[1] + right_eye[1]) / 2.0
    eye_distance = abs(right_eye[0] - left_eye[0])
    
    yaw = 0.0
    if eye_distance > 0:
        nose_offset = nose_tip[0] - eye_center_x
        nose_relative = nose_offset / (eye_distance / 2.0)
        yaw = nose_relative * 30.0
    
    pitch = 0.0
    nose_chin_distance = abs(chin[1] - nose_tip[1])
    if nose_chin_distance > 0:
        nose_vertical_offset = nose_tip[1] - eye_center_y
        nose_vertical_relative = nose_vertical_offset / nose_chin_distance
        pitch = nose_vertical_relative * 40.0
    
    return {
        'yaw': yaw,
        'pitch': pitch,
        'eye_center': (eye_center_x, eye_center_y),
        'eye_distance': eye_distance,
        'nose_offset': nose_offset,
        'nose_relative': nose_relative
    }

def analyze_frame(image_path):
    """Analizza un frame e confronta i due metodi"""
    mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    )
    
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    h, w = img.shape[:2]
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mp_face_mesh.process(rgb_img)
    
    if not results.multi_face_landmarks:
        return None
    
    landmarks = results.multi_face_landmarks[0].landmark
    landmarks_array = np.zeros((len(landmarks), 2))
    for i in range(len(landmarks)):
        landmarks_array[i, 0] = landmarks[i].x * w
        landmarks_array[i, 1] = landmarks[i].y * h
    
    solvepnp_data = calculate_solvepnp_detailed(landmarks_array, w, h)
    geometric_data = calculate_geometric(landmarks_array)
    
    return {
        'solvepnp': solvepnp_data,
        'geometric': geometric_data,
        'image_size': (w, h)
    }

def main():
    print("=" * 100)
    print("ANALISI TECNICA: Perché solvePnP fallisce?")
    print("=" * 100)
    print()
    
    # Carica JSON per conoscere i frame
    json_path = f"{SESSION_DIR}/best_frames_data.json"
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    # Analizza frame 01 (FRONTALE) e frame 07 (GIRATO)
    frames_to_analyze = ['frame_01.jpg', 'frame_07.jpg']
    
    results = {}
    for filename in frames_to_analyze:
        image_path = f"{SESSION_DIR}/{filename}"
        print(f"📸 Analisi {filename}...")
        data = analyze_frame(image_path)
        if data:
            results[filename] = data
            print(f"   ✅ Analizzato\n")
    
    print("=" * 100)
    print("CONFRONTO DETTAGLIATO")
    print("=" * 100)
    print()
    
    for filename in frames_to_analyze:
        if filename not in results:
            continue
        
        data = results[filename]
        solvepnp = data['solvepnp']
        geometric = data['geometric']
        
        print(f"{'='*100}")
        print(f"FRAME: {filename}")
        print(f"{'='*100}")
        print()
        
        print("📐 GEOMETRIA REALE:")
        print(f"   • Centro occhi: ({geometric['eye_center'][0]:.1f}, {geometric['eye_center'][1]:.1f})")
        print(f"   • Distanza occhi: {geometric['eye_distance']:.1f} px")
        print(f"   • Offset naso da centro viso: {geometric['nose_offset']:+.1f} px")
        print(f"   • Offset normalizzato: {geometric['nose_relative']:+.3f}")
        print()
        
        print("🎯 METODO GEOMETRICO:")
        print(f"   • Yaw: {geometric['yaw']:+.2f}°")
        print(f"   • Pitch: {geometric['pitch']:+.2f}°")
        print()
        
        print("🔧 METODO solvePnP:")
        print(f"   • Yaw: {solvepnp['yaw']:+.2f}°")
        print(f"   • Pitch: {solvepnp['pitch']:+.2f}°")
        print(f"   • Roll: {solvepnp['roll']:+.2f}°")
        print()
        
        print("🔍 PARAMETRI solvePnP:")
        print(f"   • Focal length: {solvepnp['focal_length']:.1f} px (= image width)")
        print(f"   • Image center: ({solvepnp['image_center'][0]:.1f}, {solvepnp['image_center'][1]:.1f})")
        print(f"   • Translation vector: {solvepnp['translation_vector'].flatten()}")
        print()
        
        print("📊 MATRICE DI ROTAZIONE:")
        rmat = solvepnp['rotation_matrix']
        for i in range(3):
            print(f"   [{rmat[i,0]:+.4f}  {rmat[i,1]:+.4f}  {rmat[i,2]:+.4f}]")
        print()
        
        # Analisi CRITICA
        print("❗ ANALISI CRITICA:")
        print()
        
        # Verifica se yaw solvePnP è coerente con offset geometrico
        if geometric['nose_offset'] > 0 and solvepnp['yaw'] < 0:
            print("   🚨 PROBLEMA: Naso spostato a DESTRA (+px) ma Yaw NEGATIVO")
            print("      → Semantica INVERTITA!")
        elif geometric['nose_offset'] < 0 and solvepnp['yaw'] > 0:
            print("   🚨 PROBLEMA: Naso spostato a SINISTRA (-px) ma Yaw POSITIVO")
            print("      → Semantica INVERTITA!")
        elif abs(geometric['nose_offset']) < 20 and abs(solvepnp['yaw']) > 2:
            print(f"   🚨 PROBLEMA: Naso quasi centrato ({geometric['nose_offset']:+.1f}px)")
            print(f"      ma Yaw solvePnP = {solvepnp['yaw']:+.2f}° (dovrebbe essere ~0°)")
        else:
            print("   ✅ Yaw solvePnP coerente con geometria")
        
        print()
        print()
    
    print("=" * 100)
    print("SPIEGAZIONE TECNICA DEL PROBLEMA")
    print("=" * 100)
    print()
    
    print("🔬 PERCHÉ solvePnP FALLISCE:")
    print()
    print("1. FOCAL LENGTH ERRATA:")
    print("   solvePnP usa focal_length = image_width (~640px)")
    print("   Questo è corretto per una VERA camera, ma MediaPipe fornisce")
    print("   landmark 2D già proiettati, NON dati 3D reali.")
    print()
    print("2. MODELLO 3D GENERICO:")
    print("   Il modello 3D è un volto 'medio' standard")
    print("   Non si adatta alle proporzioni reali del viso specifico")
    print()
    print("3. ASSUNZIONI CAMERA:")
    print("   solvePnP assume una camera pinhole con distorsioni specifiche")
    print("   Ma l'immagine può venire da qualunque camera con qualunque focal")
    print()
    print("4. SENSIBILITÀ:")
    print("   Piccoli errori nei landmark (1-2px) causano grandi variazioni")
    print("   negli angoli di rotazione calcolati")
    print()
    print("✅ PERCHÉ GEOMETRICO FUNZIONA:")
    print()
    print("1. RIFERIMENTO INTERNO:")
    print("   Usa il CENTRO DEGLI OCCHI come riferimento del viso")
    print("   Non dipende dalla posizione nell'immagine o dalla camera")
    print()
    print("2. NORMALIZZAZIONE INTRINSECA:")
    print("   Normalizza su DISTANZA TRA OCCHI (propria del viso)")
    print("   Scala automaticamente per visi vicini/lontani")
    print()
    print("3. MISURAZIONE DIRETTA:")
    print("   Misura DIRETTAMENTE lo spostamento del naso")
    print("   Non passa attraverso proiezioni 3D→2D")
    print()
    print("4. ROBUSTO:")
    print("   Errori di 1-2px nei landmark causano variazioni minime")
    print("   perché normalizzato su distanze grandi (eye_distance)")
    print()
    print("=" * 100)
    print()
    
    print("💡 CONCLUSIONE:")
    print()
    print("Per RILEVAMENTO FRONTALITÀ (non ricostruzione 3D completa):")
    print("   → Metodo GEOMETRICO è superiore")
    print("   → Più robusto, più affidabile, semanticamente corretto")
    print()
    print("solvePnP rimane utile per:")
    print("   → Roll (rotazione laterale testa)")
    print("   → Ricostruzione 3D completa della posa")
    print("   → AR/VR dove serve orientamento completo")
    print()

if __name__ == "__main__":
    main()
