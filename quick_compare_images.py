#!/usr/bin/env python3
"""
Analisi rapida delle differenze tra successo.jpg e fallisce.JPG
"""

import sys
import os
from PIL import Image, ImageStat
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from green_dots_processor import GreenDotsProcessor


def quick_test(image_path):
    """Test rapido con preprocessing."""
    print(f"\n{'='*80}")
    print(f"TEST: {os.path.basename(image_path)}")
    print(f"{'='*80}")
    
    try:
        image = Image.open(image_path)
        print(f"📐 Dimensioni: {image.size[0]} x {image.size[1]}")
        print(f"📄 Formato: {image.format}")
        
        # Statistiche base
        stat = ImageStat.Stat(image)
        print(f"🎨 Media RGB: {[round(x, 1) for x in stat.mean]}")
        
        # EXIF
        try:
            exif = image._getexif()
            orientation = exif.get(274) if exif else None
            print(f"📸 EXIF Orientation: {orientation}")
        except:
            print(f"📸 EXIF Orientation: N/A")
        
        # Test con GreenDotsProcessor usando process_pil_image (come fa l'API)
        print(f"\n🔬 Test come fa l'API (use_preprocessing=True):")
        processor = GreenDotsProcessor()
        
        # Simula esattamente quello che fa l'API
        results = processor.process_pil_image(image, use_preprocessing=True)
        
        print(f"   ✅ success: {results['success']}")
        if 'warning' in results:
            print(f"   ⚠️  warning: {results['warning']}")
        if 'error' in results:
            print(f"   ❌ error: {results['error']}")
        
        print(f"   📊 Puntini rilevati: {results['detection_results']['total_dots']}")
        print(f"   📊 Pixel verdi/bianchi: {results['detection_results']['total_green_pixels']}")
        print(f"   📊 Dimensione immagine: {results['detection_results']['image_size']}")
        
        # Mostra dettagli puntini
        if results['detection_results']['total_dots'] > 0:
            print(f"\n   📍 Puntini rilevati:")
            for i, dot in enumerate(results['detection_results']['dots'][:15], 1):
                avg_sat = sum(p['s'] for p in dot['pixels']) / len(dot['pixels'])
                avg_val = sum(p['v'] for p in dot['pixels']) / len(dot['pixels'])
                avg_hue = sum(p['h'] for p in dot['pixels']) / len(dot['pixels'])
                print(f"      {i:2d}. Pos=({dot['x']:4d},{dot['y']:4d}) "
                      f"Size={dot['size']:3d}px "
                      f"H={avg_hue:5.1f}° S={avg_sat:4.1f}% V={avg_val:4.1f}%")
        
        # Gruppi
        if results['groups']:
            print(f"\n   📦 Gruppi: Sx={len(results['groups']['Sx'])} Dx={len(results['groups']['Dx'])}")
        else:
            print(f"\n   📦 Gruppi: Non creati (serve esattamente 10 puntini)")
        
        # Parametri usati
        params = results['detection_results']['parameters']
        print(f"\n   ⚙️  Parametri HSV utilizzati:")
        print(f"      - Hue: {params['hue_range']}")
        print(f"      - Saturation min: {params['saturation_min']}")
        print(f"      - Value: {params['value_range']}")
        
        return results
        
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("\n" + "="*80)
    print("CONFRONTO RAPIDO: successo.jpg vs fallisce.JPG")
    print("Simula il comportamento dell'API /api/green-dots/analyze")
    print("="*80)
    
    result_success = quick_test('successo.jpg')
    result_fail = quick_test('fallisce.JPG')
    
    print(f"\n{'='*80}")
    print("RIEPILOGO CONFRONTO")
    print(f"{'='*80}")
    
    if result_success and result_fail:
        s_dots = result_success['detection_results']['total_dots']
        f_dots = result_fail['detection_results']['total_dots']
        
        print(f"\n📊 RISULTATI:")
        print(f"   successo.jpg: {s_dots} puntini rilevati")
        print(f"   fallisce.JPG: {f_dots} puntini rilevati")
        
        if s_dots >= 10 and f_dots < 10:
            print(f"\n❌ PROBLEMA CONFERMATO:")
            print(f"   successo.jpg funziona ({s_dots} puntini)")
            print(f"   fallisce.JPG non funziona ({f_dots} puntini)")
        elif s_dots < 10 and f_dots < 10:
            print(f"\n⚠️  ENTRAMBE LE IMMAGINI NON RILEVANO 10 PUNTINI:")
            print(f"   successo.jpg: {s_dots} puntini (serve 10)")
            print(f"   fallisce.JPG: {f_dots} puntini (serve 10)")
        elif s_dots >= 10 and f_dots >= 10:
            print(f"\n✅ ENTRAMBE FUNZIONANO:")
            print(f"   successo.jpg: {s_dots} puntini")
            print(f"   fallisce.JPG: {f_dots} puntini")
        
        print(f"\n💡 SUGGERIMENTI PER L'ANALISI:")
        print(f"   1. Confrontare i valori HSV dei puntini rilevati")
        print(f"   2. Verificare se MediaPipe rileva correttamente le sopracciglia")
        print(f"   3. Controllare la qualità/compressione JPG")
        print(f"   4. Verificare se i parametri HSV sono troppo ristretti")


if __name__ == "__main__":
    main()
