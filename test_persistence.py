#!/usr/bin/env python3
"""Test script per verificare la persistenza dei parametri di scoring."""

import json
import os
from src.scoring_config import ScoringConfig

def test_scoring_persistence():
    """Test della persistenza dei parametri di scoring."""
    
    print("🧪 TEST PERSISTENZA PARAMETRI SCORING\n")
    
    # 1. Leggi valori originali
    print("📋 1. Lettura valori originali...")
    with open("config.json", "r", encoding="utf-8") as f:
        original_config = json.load(f)
    
    original_nose = original_config["scoring"]["nose_weight"]
    original_mouth = original_config["scoring"]["mouth_weight"]
    print(f"   Peso naso originale: {original_nose}")
    print(f"   Peso bocca originale: {original_mouth}")
    
    # 2. Crea istanza ScoringConfig e verifica caricamento
    print("\n🔄 2. Creazione ScoringConfig e caricamento da file...")
    scoring = ScoringConfig()
    print(f"   Peso naso caricato: {scoring.nose_weight}")
    print(f"   Peso bocca caricato: {scoring.mouth_weight}")
    
    # 3. Modifica valori
    print("\n✏️ 3. Modifica dei parametri...")
    new_nose = 0.45
    new_mouth = 0.35
    scoring.set_nose_weight(new_nose)
    scoring.set_mouth_weight(new_mouth)
    print(f"   Nuovo peso naso: {scoring.nose_weight}")
    print(f"   Nuovo peso bocca: {scoring.mouth_weight}")
    
    # 4. Verifica salvataggio automatico
    print("\n💾 4. Verifica salvataggio automatico nel file...")
    with open("config.json", "r", encoding="utf-8") as f:
        updated_config = json.load(f)
    
    saved_nose = updated_config["scoring"]["nose_weight"]
    saved_mouth = updated_config["scoring"]["mouth_weight"]
    print(f"   Peso naso nel file: {saved_nose}")
    print(f"   Peso bocca nel file: {saved_mouth}")
    
    # 5. Verifica che i valori siano stati salvati
    if abs(saved_nose - new_nose) < 0.001 and abs(saved_mouth - new_mouth) < 0.001:
        print("   ✅ SALVATAGGIO AUTOMATICO FUNZIONA!")
    else:
        print("   ❌ ERRORE: I valori non sono stati salvati correttamente")
        return False
    
    # 6. Test nuovo caricamento
    print("\n🔄 5. Test caricamento da nuova istanza...")
    scoring2 = ScoringConfig()
    print(f"   Peso naso da nuova istanza: {scoring2.nose_weight}")
    print(f"   Peso bocca da nuova istanza: {scoring2.mouth_weight}")
    
    if abs(scoring2.nose_weight - new_nose) < 0.001 and abs(scoring2.mouth_weight - new_mouth) < 0.001:
        print("   ✅ CARICAMENTO AUTOMATICO FUNZIONA!")
    else:
        print("   ❌ ERRORE: I valori non sono stati caricati correttamente")
        return False
    
    # 7. Ripristina valori originali
    print("\n🔄 6. Ripristino valori originali...")
    scoring2.set_weights(nose=original_nose, mouth=original_mouth)
    print(f"   Peso naso ripristinato: {scoring2.nose_weight}")
    print(f"   Peso bocca ripristinato: {scoring2.mouth_weight}")
    
    print("\n🎉 TUTTI I TEST PASSATI! Sistema di persistenza funzionante.")
    return True

if __name__ == "__main__":
    test_scoring_persistence()