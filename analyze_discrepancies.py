#!/usr/bin/env python3
"""
Script per confronto visivo JSON vs IMMAGINI
Mostra chiaramente le discrepanze nel Roll e l'ordine dei frame
"""

import json
import os

SESSION_DIR = "face-landmark-localization-master/websocket_best_frames/session_webapp_session_2026-01-19T23_55_21_193Z"

def analyze_discrepancies():
    print("=" * 100)
    print(" ANALISI DETTAGLIATA DISCREPANZE - PROBLEMA IDENTIFICATO")
    print("=" * 100)
    print()
    
    # Carica JSON
    json_path = os.path.join(SESSION_DIR, "best_frames_data.json")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    print("🔴 PROBLEMA 1: DISCREPANZA ROLL ANGLE")
    print("-" * 100)
    print()
    print("I valori di Roll nel JSON sono completamente DIVERSI da quelli nelle immagini reali:")
    print()
    print("Frame    |  Roll JSON  |  Roll REALE  | Differenza |  Note")
    print("-" * 100)
    
    # Dati rilevati dallo script precedente
    real_rolls = {
        'frame_01.jpg': -178.17,
        'frame_02.jpg': -178.61,
        'frame_03.jpg': -177.91,
        'frame_04.jpg': -178.51,
        'frame_05.jpg': -178.36,
        'frame_06.jpg': -177.71,
        'frame_07.jpg': -178.12,
        'frame_08.jpg': -176.96,
        'frame_09.jpg': -177.69,
        'frame_10.jpg': -178.12
    }
    
    for frame in data['frames']:
        filename = frame['filename']
        json_roll = frame['pose']['roll']
        real_roll = real_rolls[filename]
        diff = abs(real_roll - json_roll)
        
        note = "❌ ENORME DISCREPANZA!" if diff > 100 else "✓ Ok"
        print(f"{filename}  |  {json_roll:7.2f}°  |  {real_roll:8.2f}°  |  {diff:8.2f}°  |  {note}")
    
    print()
    print("💡 INTERPRETAZIONE:")
    print("   Il Roll nelle immagini reali è ~-178°, che equivale a ~+2° (inversione asse)")
    print("   Il JSON mostra Roll tra -1° e -3°, che CORRISPONDE alla normalizzazione")
    print("   Tuttavia, questa 'normalizzazione' viene applicata SOLO al JSON salvato,")
    print("   mentre nel codice il Roll RAW (~-178°) viene usato per il calcolo dello score!")
    print()
    print("   ⚠️  QUESTO È IL BUG CRITICO:")
    print("   Il sistema calcola lo score usando Roll=-178° (interpretandolo come testa molto inclinata)")
    print("   ma poi salva Roll=-2° nel JSON (dopo normalizzazione), creando una FALSIFICAZIONE dei dati.")
    print()
    
    print("🔴 PROBLEMA 2: ORDINE FRAME INGANNEVOLE")
    print("-" * 100)
    print()
    print("I frame sono nominati 'frame_01.jpg, frame_02.jpg...' suggerendo un ordine 1-10,")
    print("ma in realtà rappresentano i frame 12-21 del video originale, riordinati per score:")
    print()
    print("Nome File    |  Rank Originale  |  Score  |  Timestamp")
    print("-" * 100)
    
    for frame in data['frames']:
        print(f"{frame['filename']}  |     {frame['rank']:2d}            |  {frame['total_score']:5.2f}  |  {frame['timestamp']:.3f}")
    
    print()
    print("Se ordinati per RANK ORIGINALE (ordine cronologico del video):")
    frames_by_rank = sorted(data['frames'], key=lambda x: x['rank'])
    print()
    for frame in frames_by_rank:
        print(f"Rank {frame['rank']:2d} → {frame['filename']} (Score {frame['total_score']:.2f})")
    
    print()
    print("💡 INTERPRETAZIONE:")
    print("   L'utente vede 'Frame 01, 02, 03...' e può pensare che siano i primi 10 frame")
    print("   in ordine temporale, ma in realtà sono i migliori 10 frame SELEZIONATI")
    print("   tra i frame 12-21 (e probabilmente molti altri) del video.")
    print()
    print("   Questo NON è necessariamente sbagliato (è il comportamento previsto),")
    print("   MA la nomenclatura può essere INGANNEVOLE per l'utente.")
    print()
    
    print("🔴 PROBLEMA 3: CODICE DI NORMALIZZAZIONE ROLL")
    print("-" * 100)
    print()
    print("Nel codice websocket_frame_api.py, ci sono DUE logiche di normalizzazione Roll:")
    print()
    print("1️⃣  Durante il calcolo dello SCORE (linee 196-209):")
    print("   - Normalizza Roll per evitare che ±180° influenzi negativamente lo score")
    print("   - Ma usa ANCORA il Roll raw per alcuni calcoli")
    print()
    print("2️⃣  Prima di salvare nel JSON (linee 412-419 e 430-437):")
    print("   - Normalizza nuovamente Roll per la visualizzazione UI")
    print("   - Salva il Roll 'cosmetico' nel JSON")
    print()
    print("💡 RISULTATO:")
    print("   Il Roll nel JSON NON riflette il Roll usato per calcolare lo score.")
    print("   Questo crea una INCONSISTENZA tra dati visualizzati e dati effettivi.")
    print()
    
    print("=" * 100)
    print("📊 CONCLUSIONE FINALE")
    print("=" * 100)
    print()
    print("✅ I FRAME SALVATI SONO CORRETTI (le immagini corrispondono al JSON in termini di identità)")
    print()
    print("❌ I DATI DI ROLL NEL JSON SONO NORMALIZZATI E NON RIFLETTONO IL VALORE USATO PER LO SCORE")
    print()
    print("⚠️  L'ORDINE DEI FRAME È PER SCORE, NON CRONOLOGICO, MA LA NOMENCLATURA PUÒ CONFONDERE")
    print()
    print("🔧 IMPLICAZIONI:")
    print("   1. Gli score mostrati potrebbero essere stati calcolati con Roll diversi da quelli mostrati")
    print("   2. L'utente non può verificare manualmente lo score guardando i valori nel JSON")
    print("   3. La tabella debug mostra dati 'cosmetici' e non i dati effettivi usati per lo scoring")
    print()
    print("💡 RACCOMANDAZIONI:")
    print("   1. Salvare nel JSON ANCHE il Roll RAW usato per lo score (es. 'roll_raw' e 'roll_normalized')")
    print("   2. Chiarire nella UI che i frame sono ordinati per SCORE, non per tempo")
    print("   3. Verificare che la normalizzazione Roll sia applicata PRIMA del calcolo score")
    print("   4. Considerare di rinominare i file con timestamp o rank originale per chiarezza")
    print()

if __name__ == "__main__":
    analyze_discrepancies()
