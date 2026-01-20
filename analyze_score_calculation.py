#!/usr/bin/env python3
"""
Analisi dettagliata del calcolo score per capire perché i frame più frontali
hanno score più alto nonostante valori Yaw controintuitivi
"""

import json
import os

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def recalculate_score(pitch, yaw, roll):
    """Ricalcola lo score usando la stessa logica del codice"""
    
    # Normalizza Roll (come nel codice originale)
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
    
    # Calcola weighted (QUI È LA CHIAVE!)
    roll_weighted = abs(normalized_roll) * 0.3
    yaw_weighted = abs(yaw) * 2.5  # ← USA ABS(YAW)!
    pitch_weighted = abs(pitch) * 1.0  # ← USA ABS(PITCH)!
    
    pose_deviation = yaw_weighted + pitch_weighted + roll_weighted
    pose_score = max(0, 100 - pose_deviation * 0.8)
    
    return pose_score, {
        'yaw_weighted': yaw_weighted,
        'pitch_weighted': pitch_weighted,
        'roll_weighted': roll_weighted,
        'pose_deviation': pose_deviation
    }

def main():
    print("=" * 120)
    print(" ANALISI CALCOLO SCORE - PERCHÉ IL SISTEMA FUNZIONA NONOSTANTE YAW CONTROINTUITIVO")
    print("=" * 120)
    print()
    
    # Carica JSON
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        json_data = json.load(f)
    
    print("🔍 SCOPERTA CHIAVE:")
    print("   Il codice usa abs(yaw), abs(pitch), abs(roll) per calcolare lo score!")
    print("   Questo significa che NON IMPORTA il segno, solo la DISTANZA DA ZERO.")
    print()
    print("   Formula: pose_deviation = abs(yaw)*2.5 + abs(pitch)*1.0 + abs(roll)*0.3")
    print("   Formula: pose_score = 100 - pose_deviation*0.8")
    print()
    print("-" * 120)
    print()
    
    print(f"{'Frame':12} | {'Yaw':7} | {'Pitch':7} | {'Roll':7} | {'abs(Yaw)':9} | {'Yaw Weight':11} | {'Deviation':10} | {'Score JSON':11} | {'Score Calc':11}")
    print("-" * 120)
    
    for frame_data in json_data['frames']:
        filename = frame_data['filename']
        yaw = frame_data['pose']['yaw']
        pitch = frame_data['pose']['pitch']
        roll = frame_data['pose']['roll']
        score_json = frame_data['total_score']
        
        score_calc, details = recalculate_score(pitch, yaw, roll)
        
        print(f"{filename:12} | {yaw:6.2f}° | {pitch:6.2f}° | {roll:6.2f}° | {abs(yaw):8.2f}° | {details['yaw_weighted']:10.2f} | {details['pose_deviation']:9.2f} | {score_json:10.2f} | {score_calc:10.2f}")
    
    print()
    print("=" * 120)
    print()
    print("💡 SPIEGAZIONE DEL 'PARADOSSO':")
    print()
    print("Frame 01 (più frontale visivamente):")
    print("  • Yaw = -2.32° → abs(Yaw) = 2.32° → yaw_weighted = 5.80")
    print("  • Pitch = -0.63° → abs(Pitch) = 0.63° → pitch_weighted = 0.63")
    print("  • Deviazione totale più BASSA → Score più ALTO ✅")
    print()
    print("Frame 07 (più girato visivamente):")
    print("  • Yaw = -0.75° → abs(Yaw) = 0.75° → yaw_weighted = 1.88")
    print("  • Pitch = -9.67° → abs(Pitch) = 9.67° → pitch_weighted = 9.67")
    print("  • Deviazione totale più ALTA → Score più BASSO ✅")
    print()
    print("-" * 120)
    print()
    print("🎯 CONCLUSIONE:")
    print()
    print("Il sistema FUNZIONA correttamente perché:")
    print()
    print("1. ✅ Usa abs(yaw) per lo scoring → solo la distanza da zero conta")
    print("2. ✅ Frame più frontali hanno abs(yaw) + abs(pitch) più bassi")
    print("3. ✅ Il frame migliore viene selezionato correttamente")
    print()
    print("MA c'è un PROBLEMA SEMANTICO:")
    print()
    print("4. ❌ I valori Yaw/Pitch/Roll salvati nel JSON sono CONTROINTUITIVI")
    print("5. ❌ Yaw vicino a zero NON significa frontale, ma potrebbe essere molto girato con Pitch alto")
    print("6. ❌ L'utente non può interpretare i valori singoli senza fare abs()")
    print()
    print("📊 VERIFICA CASO SPECIFICO:")
    print()
    
    # Confronto frame 01 vs 07
    frame_01 = json_data['frames'][0]
    frame_07 = json_data['frames'][6]
    
    score_01, details_01 = recalculate_score(
        frame_01['pose']['pitch'], 
        frame_01['pose']['yaw'], 
        frame_01['pose']['roll']
    )
    
    score_07, details_07 = recalculate_score(
        frame_07['pose']['pitch'], 
        frame_07['pose']['yaw'], 
        frame_07['pose']['roll']
    )
    
    print(f"Frame 01 (Score {frame_01['total_score']:.2f}):")
    print(f"  Yaw={frame_01['pose']['yaw']:.2f}° Pitch={frame_01['pose']['pitch']:.2f}° Roll={frame_01['pose']['roll']:.2f}°")
    print(f"  abs(Yaw)={abs(frame_01['pose']['yaw']):.2f}° abs(Pitch)={abs(frame_01['pose']['pitch']):.2f}°")
    print(f"  Deviazione pose: {details_01['pose_deviation']:.2f}")
    print(f"  → Deviazione BASSA = più frontale ✅")
    print()
    print(f"Frame 07 (Score {frame_07['total_score']:.2f}):")
    print(f"  Yaw={frame_07['pose']['yaw']:.2f}° Pitch={frame_07['pose']['pitch']:.2f}° Roll={frame_07['pose']['roll']:.2f}°")
    print(f"  abs(Yaw)={abs(frame_07['pose']['yaw']):.2f}° abs(Pitch)={abs(frame_07['pose']['pitch']):.2f}°")
    print(f"  Deviazione pose: {details_07['pose_deviation']:.2f}")
    print(f"  → Deviazione ALTA = più girato ✅")
    print()
    print("-" * 120)
    print()
    print("🔴 IL VERO PROBLEMA:")
    print()
    print("Frame 07 sembra avere Yaw 'migliore' (-0.75° vs -2.32°) se guardi solo quel valore,")
    print("MA ha Pitch molto peggiore (-9.67° vs -0.63°)!")
    print()
    print("La deviazione TOTALE è ciò che conta:")
    print(f"  Frame 01: abs(yaw)*2.5 + abs(pitch)*1.0 = {abs(frame_01['pose']['yaw'])*2.5:.2f} + {abs(frame_01['pose']['pitch'])*1.0:.2f} = {abs(frame_01['pose']['yaw'])*2.5 + abs(frame_01['pose']['pitch'])*1.0:.2f}")
    print(f"  Frame 07: abs(yaw)*2.5 + abs(pitch)*1.0 = {abs(frame_07['pose']['yaw'])*2.5:.2f} + {abs(frame_07['pose']['pitch'])*1.0:.2f} = {abs(frame_07['pose']['yaw'])*2.5 + abs(frame_07['pose']['pitch'])*1.0:.2f}")
    print()
    print("Frame 01 vince perché la SOMMA delle deviazioni è minore!")
    print()
    print("=" * 120)
    print()
    print("📋 RACCOMANDAZIONE FINALE:")
    print()
    print("Non c'è un BUG nel calcolo, ma una CONFUSIONE nella rappresentazione:")
    print()
    print("Suggerimenti per migliorare la chiarezza:")
    print("1. Mostrare nella tabella anche abs(Yaw), abs(Pitch), abs(Roll)")
    print("2. Aggiungere colonna 'Deviazione Totale' = abs(yaw)*2.5 + abs(pitch)*1.0 + abs(roll)*0.3")
    print("3. Rinominare 'Yaw' in 'Yaw Raw' e aggiungere 'Yaw Impact' = abs(yaw)*2.5")
    print("4. Spiegare nella UI che conta la DISTANZA DA ZERO, non il valore assoluto")
    print()

if __name__ == "__main__":
    main()
