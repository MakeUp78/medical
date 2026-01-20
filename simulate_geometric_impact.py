#!/usr/bin/env python3
"""
Simula cosa succederebbe agli SCORE se usassimo il metodo geometrico
Verifica se il frame 01 rimarrebbe il migliore
"""

import json
import cv2
import mediapipe as mp
import numpy as np
import os

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def calculate_geometric_yaw(image_path):
    """Calcola Yaw con metodo geometrico"""
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
    all_landmarks = np.zeros((len(landmarks), 2))
    for i in range(len(landmarks)):
        all_landmarks[i, 0] = landmarks[i].x * w
        all_landmarks[i, 1] = landmarks[i].y * h
    
    NOSE_TIP = 4
    LEFT_EYE = 33
    RIGHT_EYE = 263
    
    nose_tip = all_landmarks[NOSE_TIP]
    left_eye = all_landmarks[LEFT_EYE]
    right_eye = all_landmarks[RIGHT_EYE]
    
    # Calcolo geometrico
    eye_center_x = (left_eye[0] + right_eye[0]) / 2
    eye_distance = abs(right_eye[0] - left_eye[0])
    
    if eye_distance > 0:
        nose_relative = (nose_tip[0] - eye_center_x) / (eye_distance / 2)
        yaw_geometric = nose_relative * 30
        return yaw_geometric
    
    return None

def calculate_score_with_yaw(pitch, yaw, roll):
    """Calcola score come nel codice originale"""
    # Normalizza Roll
    normalized_roll = roll
    while normalized_roll > 180:
        normalized_roll -= 360
    while normalized_roll < -180:
        normalized_roll += 360
    if abs(normalized_roll) > 150:
        normalized_roll = 180 - abs(normalized_roll)
        if roll < 0:
            normalized_roll = -normalized_roll
    while normalized_roll > 90:
        normalized_roll -= 180
    while normalized_roll < -90:
        normalized_roll += 180
    
    roll_weighted = abs(normalized_roll) * 0.3
    yaw_weighted = abs(yaw) * 2.5
    pitch_weighted = abs(pitch) * 1.0
    
    pose_deviation = yaw_weighted + pitch_weighted + roll_weighted
    pose_score = max(0, 100 - pose_deviation * 0.8)
    
    return pose_score, {
        'yaw_weighted': yaw_weighted,
        'pitch_weighted': pitch_weighted,
        'roll_weighted': roll_weighted,
        'pose_deviation': pose_deviation
    }

def main():
    print("=" * 140)
    print(" SIMULAZIONE: Cosa succederebbe agli SCORE con metodo GEOMETRICO?")
    print("=" * 140)
    print()
    
    # Carica JSON
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    print("🎯 DOMANDA: Il frame 01 rimarrebbe il migliore con Yaw geometrico?")
    print()
    print("-" * 140)
    print()
    
    results = []
    
    for frame_data in json_data['frames']:
        filename = frame_data['filename']
        image_path = os.path.join(SESSION_DIR, filename)
        
        # Valori attuali
        yaw_current = frame_data['pose']['yaw']
        pitch = frame_data['pose']['pitch']
        roll = frame_data['pose']['roll']
        score_current = frame_data['total_score']
        
        # Calcola Yaw geometrico
        yaw_geometric = calculate_geometric_yaw(image_path)
        
        if yaw_geometric is not None:
            # Ricalcola score con Yaw geometrico
            score_geometric, details = calculate_score_with_yaw(pitch, yaw_geometric, roll)
            
            results.append({
                'filename': filename,
                'rank': frame_data['rank'],
                'yaw_current': yaw_current,
                'yaw_geometric': yaw_geometric,
                'pitch': pitch,
                'score_current': score_current,
                'score_geometric': score_geometric,
                'score_diff': score_geometric - score_current,
                'details': details
            })
    
    # Ordina per score attuale
    print("📊 CONFRONTO SCORE: ATTUALE vs CON YAW GEOMETRICO")
    print()
    print(f"{'Frame':12} | {'Rank':4} | {'Yaw OLD':9} | {'Yaw NEW':9} | {'Δ Yaw':8} | {'Score OLD':10} | {'Score NEW':10} | {'Δ Score':9} | Impatto")
    print("-" * 140)
    
    for res in results:
        yaw_diff = res['yaw_geometric'] - res['yaw_current']
        
        impact = ""
        if abs(res['score_diff']) < 0.5:
            impact = "≈ Nessun impatto"
        elif res['score_diff'] > 0:
            impact = f"↑ Migliora di {res['score_diff']:.2f}"
        else:
            impact = f"↓ Peggiora di {abs(res['score_diff']):.2f}"
        
        print(f"{res['filename']:12} | {res['rank']:4} | {res['yaw_current']:8.2f}° | {res['yaw_geometric']:8.2f}° | {yaw_diff:+7.2f}° | {res['score_current']:9.2f} | {res['score_geometric']:9.2f} | {res['score_diff']:+8.2f} | {impact}")
    
    print()
    print("-" * 140)
    print()
    
    # Riordina per score geometrico
    results_sorted_current = sorted(results, key=lambda x: x['score_current'], reverse=True)
    results_sorted_geometric = sorted(results, key=lambda x: x['score_geometric'], reverse=True)
    
    print("🏆 CLASSIFICA ATTUALE (con solvePnP):")
    print()
    for i, res in enumerate(results_sorted_current[:5], 1):
        marker = "👑" if i == 1 else f"{i}°"
        print(f"   {marker:3} {res['filename']:12} - Score {res['score_current']:.2f} (Yaw {res['yaw_current']:+.2f}°)")
    
    print()
    print("🏆 CLASSIFICA CON YAW GEOMETRICO:")
    print()
    for i, res in enumerate(results_sorted_geometric[:5], 1):
        marker = "👑" if i == 1 else f"{i}°"
        
        # Trova posizione attuale
        current_pos = results_sorted_current.index(res) + 1
        
        if i != current_pos:
            change = f" (era {current_pos}°)"
        else:
            change = ""
        
        print(f"   {marker:3} {res['filename']:12} - Score {res['score_geometric']:.2f} (Yaw {res['yaw_geometric']:+.2f}°){change}")
    
    print()
    print("=" * 140)
    print()
    
    # Verifica se il vincitore cambia
    winner_current = results_sorted_current[0]['filename']
    winner_geometric = results_sorted_geometric[0]['filename']
    
    print("💡 RISPOSTA ALLA DOMANDA:")
    print()
    
    if winner_current == winner_geometric:
        print(f"✅ Il frame {winner_current} RIMANE IL MIGLIORE anche con Yaw geometrico!")
        print()
        print("   La modifica NON cambierebbe il frame selezionato come più frontale.")
        print("   Cambierebbe SOLO i valori Yaw mostrati, rendendoli semanticamente corretti.")
    else:
        print(f"⚠️  ATTENZIONE: Il vincitore CAMBIEREBBE!")
        print(f"   • Attuale: {winner_current}")
        print(f"   • Con Yaw geometrico: {winner_geometric}")
        print()
        print("   Questo potrebbe indicare che il metodo geometrico è PIÙ preciso,")
        print("   oppure che i due metodi valutano la frontalità in modo diverso.")
    
    print()
    
    # Analisi top 3
    top3_current = [r['filename'] for r in results_sorted_current[:3]]
    top3_geometric = [r['filename'] for r in results_sorted_geometric[:3]]
    
    common_top3 = set(top3_current) & set(top3_geometric)
    
    print(f"📊 STABILITÀ TOP 3:")
    print(f"   Frame comuni nei top 3: {len(common_top3)}/3")
    print(f"   Top 3 attuale: {', '.join(top3_current)}")
    print(f"   Top 3 geometrico: {', '.join(top3_geometric)}")
    print()
    
    if len(common_top3) == 3:
        print("   ✅ I migliori 3 frame rimangono gli stessi, solo l'ordine potrebbe cambiare")
    elif len(common_top3) >= 2:
        print("   ⚠️  2 frame su 3 rimangono nei top, ma c'è una sostituzione")
    else:
        print("   ❌ Cambiano significativamente i frame selezionati")
    
    print()
    print("-" * 140)
    print()
    
    print("🔬 DETTAGLIO FRAME 01 (attuale vincitore):")
    print()
    frame_01 = next(r for r in results if r['filename'] == 'frame_01.jpg')
    
    print(f"   Yaw attuale (solvePnP): {frame_01['yaw_current']:+.2f}°")
    print(f"   Yaw geometrico:         {frame_01['yaw_geometric']:+.2f}°")
    print(f"   Pitch:                  {frame_01['pitch']:+.2f}°")
    print()
    print(f"   Score attuale:          {frame_01['score_current']:.2f}")
    print(f"   Score con Yaw geometrico: {frame_01['score_geometric']:.2f}")
    print(f"   Differenza:             {frame_01['score_diff']:+.2f}")
    print()
    
    if frame_01['score_diff'] > 0:
        print(f"   ✅ Lo score MIGLIORA di {frame_01['score_diff']:.2f} punti con Yaw geometrico")
    elif frame_01['score_diff'] < 0:
        print(f"   ⚠️  Lo score PEGGIORA di {abs(frame_01['score_diff']):.2f} punti con Yaw geometrico")
    else:
        print(f"   ≈ Lo score rimane praticamente invariato")
    
    print()
    print("=" * 140)

if __name__ == "__main__":
    main()
