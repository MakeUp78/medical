#!/usr/bin/env python3
"""
Script di test per l'algoritmo di riconoscimento green dots.
Testa l'efficacia del rilevamento su immagini con gli stessi 10 green dots.

Utilizzo:
    python test_green_dots.py
"""

from src.green_dots_processor import GreenDotsProcessor
from PIL import Image
import os
import sys

def test_green_dots_detection():
    """
    Testa il rilevamento green dots su due immagini di test
    """
    # Path delle immagini di test
    image_paths = [
        'src/green.png',
        'src/best_frontal_frame1.png'
    ]
    
    # Verifica che le immagini esistano
    for img_path in image_paths:
        if not os.path.exists(img_path):
            print(f"❌ ERRORE: Immagine non trovata: {img_path}")
            return False
    
    print("=" * 80)
    print("🧪 TEST RICONOSCIMENTO GREEN DOTS")
    print("=" * 80)
    print(f"\nImmagini di test:")
    for i, path in enumerate(image_paths, 1):
        print(f"  {i}. {path}")
    print(f"\n{'=' * 80}\n")
    
    # Crea il processore con i parametri di default
    processor = GreenDotsProcessor()
    
    print("📋 PARAMETRI ALGORITMO:")
    print(f"  • Hue range: {processor.hue_min}° - {processor.hue_max}°")
    print(f"  • Saturation min: {processor.saturation_min}%")
    print(f"  • Value range: {processor.value_min}% - {processor.value_max}%")
    print(f"  • Cluster size range: {processor.cluster_min} - {processor.cluster_max} pixels")
    print(f"  • Clustering radius: {processor.clustering_radius} pixels")
    print(f"\n{'=' * 80}\n")
    
    # Processa entrambe le immagini
    results = []
    
    for i, img_path in enumerate(image_paths, 1):
        print(f"🔍 ANALISI IMMAGINE {i}: {os.path.basename(img_path)}")
        print("-" * 80)
        
        try:
            # Carica immagine
            image = Image.open(img_path)
            img_width, img_height = image.size
            print(f"  📐 Dimensioni: {img_width}×{img_height} pixels")
            
            # Rileva green dots
            detection_result = processor.detect_green_dots(image)
            
            # Salva risultati
            results.append({
                'path': img_path,
                'name': os.path.basename(img_path),
                'size': (img_width, img_height),
                'result': detection_result
            })
            
            # Mostra statistiche
            print(f"  🟢 Pixel verdi rilevati: {detection_result['total_green_pixels']}")
            print(f"  🎯 Clusters trovati: {detection_result['total_dots']}")
            
            # Dettagli dei clusters
            if detection_result['total_dots'] > 0:
                print(f"\n  📊 Dettaglio clusters:")
                for j, dot in enumerate(detection_result['dots'], 1):
                    print(f"     {j:2d}. Posizione: ({dot['x']:4d}, {dot['y']:4d}) - Dimensione: {dot['size']:3d} px")
            else:
                print("  ⚠️  Nessun cluster rilevato!")
            
            # Prova la divisione in gruppi Sx/Dx
            if detection_result['total_dots'] >= 2:
                left_dots, right_dots = processor.divide_dots_by_vertical_center(
                    detection_result['dots'], 
                    img_width
                )
                print(f"\n  ↔️  Divisione Sx/Dx:")
                print(f"     Sinistra: {len(left_dots)} dots")
                print(f"     Destra: {len(right_dots)} dots")
                
                # Genera overlay per visualizzazione
                overlay = processor.generate_overlay(
                    (img_width, img_height),
                    left_dots,
                    right_dots
                )
                
                # Salva overlay
                overlay_path = img_path.replace('.png', '_overlay.png')
                overlay.save(overlay_path)
                print(f"  💾 Overlay salvato: {overlay_path}")
                
                # Composita immagine con overlay
                composite = image.copy().convert('RGBA')
                composite = Image.alpha_composite(composite, overlay)
                composite_path = img_path.replace('.png', '_result.png')
                composite.save(composite_path)
                print(f"  💾 Risultato salvato: {composite_path}")
            
            print(f"\n{'=' * 80}\n")
            
        except Exception as e:
            print(f"  ❌ ERRORE durante l'elaborazione: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n{'=' * 80}\n")
            results.append({
                'path': img_path,
                'name': os.path.basename(img_path),
                'error': str(e)
            })
    
    # Confronto risultati
    print("📊 CONFRONTO RISULTATI")
    print("=" * 80)
    
    if len(results) == 2 and 'error' not in results[0] and 'error' not in results[1]:
        r1 = results[0]['result']
        r2 = results[1]['result']
        
        print(f"\n{'Metrica':<30} | {'Immagine 1':<15} | {'Immagine 2':<15} | {'Differenza'}")
        print("-" * 80)
        print(f"{'Pixel verdi rilevati':<30} | {r1['total_green_pixels']:>15} | {r2['total_green_pixels']:>15} | {abs(r1['total_green_pixels'] - r2['total_green_pixels']):>10}")
        print(f"{'Clusters trovati':<30} | {r1['total_dots']:>15} | {r2['total_dots']:>15} | {abs(r1['total_dots'] - r2['total_dots']):>10}")
        
        # Confronto aspettato vs trovato
        expected_dots = 10
        print(f"\n{'Immagine':<30} | {'Attesi':<10} | {'Trovati':<10} | {'Accuratezza'}")
        print("-" * 80)
        
        for i, res in enumerate(results, 1):
            r = res['result']
            accuracy = (r['total_dots'] / expected_dots * 100) if expected_dots > 0 else 0
            accuracy_str = f"{accuracy:.1f}%"
            status = "✅" if r['total_dots'] == expected_dots else "⚠️" if r['total_dots'] > 0 else "❌"
            print(f"{status} {res['name']:<26} | {expected_dots:<10} | {r['total_dots']:<10} | {accuracy_str}")
        
        # Valutazione finale
        print(f"\n{'=' * 80}")
        print("🎯 VALUTAZIONE FINALE:")
        print("-" * 80)
        
        if r1['total_dots'] == expected_dots and r2['total_dots'] == expected_dots:
            print("✅ ECCELLENTE: Rilevati esattamente 10 dots in entrambe le immagini")
        elif r1['total_dots'] == r2['total_dots']:
            print(f"⚠️  COERENTE: Rilevati {r1['total_dots']} dots in entrambe (attesi: {expected_dots})")
            if r1['total_dots'] < expected_dots:
                print("   → L'algoritmo potrebbe essere troppo restrittivo")
                print("   → Considera di allargare i parametri HSV")
            else:
                print("   → L'algoritmo potrebbe rilevare falsi positivi")
                print("   → Considera di restringere i parametri HSV")
        else:
            print(f"❌ INCOERENTE: Rilevati {r1['total_dots']} dots nell'immagine 1 e {r2['total_dots']} nell'immagine 2")
            print("   → L'algoritmo non è stabile tra diverse condizioni di luce/qualità")
        
        print("=" * 80)
        
        # Suggerimenti
        print("\n💡 SUGGERIMENTI:")
        print("-" * 80)
        avg_found = (r1['total_dots'] + r2['total_dots']) / 2
        
        if avg_found < expected_dots * 0.5:
            print("📉 Troppi pochi dots rilevati - Parametri troppo restrittivi:")
            print("   • Aumenta hue_range (es. 45-165)")
            print("   • Diminuisci saturation_min (es. 5)")
            print("   • Aumenta value_range (es. 5-100)")
            print("   • Diminuisci cluster_min (es. 1)")
        elif avg_found > expected_dots * 1.5:
            print("📈 Troppi dots rilevati - Parametri troppo permissivi:")
            print("   • Riduci hue_range (es. 60-140)")
            print("   • Aumenta saturation_min (es. 20)")
            print("   • Riduci value_range (es. 20-90)")
            print("   • Aumenta cluster_min (es. 3)")
        else:
            print("✅ Parametri in range accettabile")
            print("   Per ottimizzare ulteriormente:")
            print("   • Analizza visivamente gli overlay generati")
            print("   • Verifica quali dots mancano o sono in eccesso")
            print("   • Regola i parametri in base all'analisi visiva")
        
        print(f"\n{'=' * 80}\n")
        
        return True
    else:
        print("❌ Non è possibile effettuare il confronto a causa di errori")
        return False

if __name__ == '__main__':
    success = test_green_dots_detection()
    sys.exit(0 if success else 1)
