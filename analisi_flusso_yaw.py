#!/usr/bin/env python3
"""
ANALISI FLUSSO CALCOLO YAW con solvePnP

Analizza passo per passo:
1. Input: landmark 2D MediaPipe
2. Modello 3D usato
3. Camera matrix e parametri
4. Output solvePnP: rotation_vector, translation_vector
5. Conversione Rodrigues: rotation_vector → rotation_matrix
6. Estrazione angoli di Eulero: rotation_matrix → pitch/yaw/roll
7. Sistema di coordinate e convenzioni

Identifica TUTTI i bias e le assunzioni nascoste
"""

import cv2
import mediapipe as mp
import numpy as np
import json

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def analyze_complete_flow(image_path):
    """Analisi completa del flusso solvePnP"""
    
    # STEP 1: Carica immagine e estrai landmark
    mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5
    )
    
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = mp_face_mesh.process(rgb_img)
    
    landmarks = results.multi_face_landmarks[0].landmark
    landmarks_array = np.zeros((len(landmarks), 2))
    for i in range(len(landmarks)):
        landmarks_array[i, 0] = landmarks[i].x * w
        landmarks_array[i, 1] = landmarks[i].y * h
    
    # STEP 2: Estrai punti chiave
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
    
    print("STEP 1: LANDMARK 2D (pixel coordinates)")
    print("=" * 80)
    print(f"Nose tip:    ({nose_tip[0]:.1f}, {nose_tip[1]:.1f})")
    print(f"Chin:        ({chin[0]:.1f}, {chin[1]:.1f})")
    print(f"Left eye:    ({left_eye[0]:.1f}, {left_eye[1]:.1f})")
    print(f"Right eye:   ({right_eye[0]:.1f}, {right_eye[1]:.1f})")
    print(f"Left mouth:  ({left_mouth[0]:.1f}, {left_mouth[1]:.1f})")
    print(f"Right mouth: ({right_mouth[0]:.1f}, {right_mouth[1]:.1f})")
    print()
    
    # STEP 3: Modello 3D
    model_points = np.array([
        (0.0, 0.0, 0.0),             # Punta del naso (ORIGINE)
        (0.0, -330.0, -65.0),        # Mento 
        (-225.0, 170.0, -135.0),     # Occhio sinistro
        (225.0, 170.0, -135.0),      # Occhio destro  
        (-150.0, -150.0, -125.0),    # Bocca sinistra
        (150.0, -150.0, -125.0)      # Bocca destra
    ], dtype=np.float32)
    
    print("STEP 2: MODELLO 3D (coordinate modello)")
    print("=" * 80)
    print("Sistema di coordinate del modello:")
    print("  X: positivo = DESTRA del viso (dal punto di vista del viso)")
    print("  Y: positivo = SU")
    print("  Z: positivo = FUORI (verso la camera)")
    print()
    print("Punti del modello:")
    for i, name in enumerate(['Nose', 'Chin', 'L.Eye', 'R.Eye', 'L.Mouth', 'R.Mouth']):
        print(f"  {name:8s}: ({model_points[i,0]:+7.1f}, {model_points[i,1]:+7.1f}, {model_points[i,2]:+7.1f})")
    print()
    
    # STEP 4: Camera matrix
    focal_length = w
    center = (w/2, h/2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float32)
    
    print("STEP 3: CAMERA MATRIX")
    print("=" * 80)
    print(f"Focal length: {focal_length:.1f} px (= image width)")
    print(f"Principal point: ({center[0]:.1f}, {center[1]:.1f})")
    print("Camera matrix:")
    for i in range(3):
        print(f"  [{camera_matrix[i,0]:8.1f} {camera_matrix[i,1]:8.1f} {camera_matrix[i,2]:8.1f}]")
    print()
    print("⚠️ ASSUNZIONE: focal_length = image_width")
    print("   Questo assume una FOV (field of view) specifica")
    print("   Se la camera reale ha FOV diverso, gli angoli saranno sbagliati!")
    print()
    
    # STEP 5: solvePnP
    image_points = np.array([
        nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
    ], dtype=np.float32)
    
    dist_coeffs = np.zeros((4,1))
    
    success, rvec, tvec = cv2.solvePnP(model_points, image_points, camera_matrix, dist_coeffs)
    
    print("STEP 4: solvePnP OUTPUT")
    print("=" * 80)
    print("Rotation vector (Rodrigues):")
    print(f"  [{rvec[0,0]:+.4f}, {rvec[1,0]:+.4f}, {rvec[2,0]:+.4f}]")
    print()
    print("Translation vector:")
    print(f"  [{tvec[0,0]:+.2f}, {tvec[1,0]:+.2f}, {tvec[2,0]:+.2f}]")
    print()
    print("💡 Rotation vector è una rappresentazione compatta (axis-angle)")
    print("   Deve essere convertito in matrice 3x3 per estrarre gli angoli")
    print()
    
    # STEP 6: Rodrigues
    rmat, _ = cv2.Rodrigues(rvec)
    
    print("STEP 5: ROTATION MATRIX (da Rodrigues)")
    print("=" * 80)
    print("Rotation matrix 3x3:")
    for i in range(3):
        print(f"  [{rmat[i,0]:+.4f} {rmat[i,1]:+.4f} {rmat[i,2]:+.4f}]")
    print()
    print("💡 Questa matrice rappresenta la rotazione del viso rispetto alla camera")
    print()
    
    # STEP 7: Estrazione angoli
    sy = np.sqrt(rmat[0,0]**2 + rmat[1,0]**2)
    
    print("STEP 6: ESTRAZIONE ANGOLI DI EULERO")
    print("=" * 80)
    print("Convenzione usata: ROTAZIONE INTRINSECA Y-X-Z")
    print("  1. Yaw (Y-axis rotation) - rotazione orizzontale")
    print("  2. Pitch (X-axis rotation) - rotazione verticale")
    print("  3. Roll (Z-axis rotation) - rotazione laterale")
    print()
    
    # Formula ORIGINALE (senza correzione)
    yaw_original = np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
    pitch = np.arctan2(-rmat[2,0], sy) * 180.0 / np.pi
    roll = np.arctan2(rmat[2,1], rmat[2,2]) * 180.0 / np.pi
    
    # Formula CORRETTA (negata)
    yaw_corrected = -np.arctan2(rmat[1,0], rmat[0,0]) * 180.0 / np.pi
    
    print("Formula Yaw ORIGINALE:")
    print("  yaw = arctan2(R[1,0], R[0,0]) * 180/π")
    print(f"  yaw = arctan2({rmat[1,0]:+.4f}, {rmat[0,0]:+.4f}) * 180/π")
    print(f"  yaw = {yaw_original:+.2f}°")
    print()
    print("Formula Yaw CORRETTA (negata):")
    print("  yaw = -arctan2(R[1,0], R[0,0]) * 180/π")
    print(f"  yaw = {yaw_corrected:+.2f}°")
    print()
    
    print("Formula Pitch:")
    print("  pitch = arctan2(-R[2,0], sqrt(R[0,0]² + R[1,0]²)) * 180/π")
    print(f"  pitch = {pitch:+.2f}°")
    print()
    
    print("Formula Roll:")
    print("  roll = arctan2(R[2,1], R[2,2]) * 180/π")
    print(f"  roll = {roll:+.2f}°")
    print()
    
    # STEP 8: Verifica geometrica
    eye_center_x = (left_eye[0] + right_eye[0]) / 2.0
    eye_distance = abs(right_eye[0] - left_eye[0])
    nose_offset = nose_tip[0] - eye_center_x
    yaw_geometric = (nose_offset / (eye_distance / 2.0)) * 30.0
    
    print("STEP 7: VERIFICA GEOMETRICA")
    print("=" * 80)
    print(f"Centro occhi X: {eye_center_x:.1f} px")
    print(f"Distanza occhi: {eye_distance:.1f} px")
    print(f"Offset naso: {nose_offset:+.1f} px")
    print(f"Yaw geometrico: {yaw_geometric:+.2f}°")
    print()
    
    print("CONFRONTO FINALE:")
    print("=" * 80)
    print(f"Yaw geometrico (ground truth): {yaw_geometric:+7.2f}°")
    print(f"Yaw solvePnP ORIGINALE:        {yaw_original:+7.2f}° (err: {abs(yaw_geometric-yaw_original):.2f}°)")
    print(f"Yaw solvePnP CORRETTA:         {yaw_corrected:+7.2f}° (err: {abs(yaw_geometric-yaw_corrected):.2f}°)")
    print()
    
    # ANALISI BIAS
    print("ANALISI BIAS:")
    print("=" * 80)
    
    bias_original = yaw_original - yaw_geometric
    bias_corrected = yaw_corrected - yaw_geometric
    
    print(f"Bias formula ORIGINALE: {bias_original:+.2f}°")
    print(f"Bias formula CORRETTA:  {bias_corrected:+.2f}°")
    print()
    
    if abs(bias_corrected) > 2:
        print("⚠️ BIAS RESIDUO SIGNIFICATIVO!")
        print()
        print("Possibili cause:")
        print("1. Focal length errata (assume FOV specifica)")
        print("2. Modello 3D non rappresenta proporzioni reali del viso")
        print("3. Landmark MediaPipe hanno piccoli errori")
        print("4. Sistema di coordinate non allineato")
        print()
        
        # Test con focal length diversa
        print("TEST: Focal length alternativa")
        for mult in [0.5, 0.75, 1.5, 2.0]:
            focal_test = w * mult
            camera_test = np.array([
                [focal_test, 0, center[0]],
                [0, focal_test, center[1]],
                [0, 0, 1]
            ], dtype=np.float32)
            
            _, rvec_test, _ = cv2.solvePnP(model_points, image_points, camera_test, dist_coeffs)
            rmat_test, _ = cv2.Rodrigues(rvec_test)
            yaw_test = -np.arctan2(rmat_test[1,0], rmat_test[0,0]) * 180.0 / np.pi
            error_test = abs(yaw_test - yaw_geometric)
            
            marker = "✅" if error_test < abs(bias_corrected) else "  "
            print(f"  {marker} focal = {mult:3.1f}x width → yaw = {yaw_test:+6.2f}° (err: {error_test:5.2f}°)")
    
    print()
    return {
        'yaw_geometric': yaw_geometric,
        'yaw_original': yaw_original,
        'yaw_corrected': yaw_corrected,
        'nose_offset': nose_offset,
        'rotation_matrix': rmat
    }

def main():
    print("=" * 100)
    print("ANALISI COMPLETA FLUSSO CALCOLO YAW con solvePnP")
    print("=" * 100)
    print()
    
    # Test su frame frontale
    print("FRAME FRONTALE (frame_01.jpg)")
    print("=" * 100)
    print()
    analyze_complete_flow(f"{SESSION_DIR}/frame_01.jpg")
    
    print("\n\n")
    print("=" * 100)
    print("FRAME GIRATO (frame_07.jpg)")
    print("=" * 100)
    print()
    analyze_complete_flow(f"{SESSION_DIR}/frame_07.jpg")

if __name__ == "__main__":
    main()
