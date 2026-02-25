#!/usr/bin/env python3
"""
Script per analizzare le differenze tra successo.jpg e fallisce.JPG
nel rilevamento dei puntini bianchi.
"""

import sys
import os
from PIL import Image, ImageDraw, ImageStat
import json
import numpy as np

# Aggiungi il percorso src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from green_dots_processor import GreenDotsProcessor


def analyze_image_properties(image_path):
    """Analizza proprietà dell'immagine."""
    print(f"\n{'='*80}")
    print(f"ANALISI: {os.path.basename(image_path)}")
    print(f"{'='*80}")
    
    try:
        image = Image.open(image_path)
        
        # Info base
        print(f"\n📐 DIMENSIONI E FORMATO:")
        print(f"   - Dimensioni: {image.size[0]} x {image.size[1]} pixels")
        print(f"   - Formato: {image.format}")
        print(f"   - Modalità: {image.mode}")
        
        # Statistiche colore
        stat = ImageStat.Stat(image)
        print(f"\n🎨 STATISTICHE COLORE (RGB):")
        print(f"   - Media RGB: {[round(x, 2) for x in stat.mean]}")
        print(f"   - Deviazione std RGB: {[round(x, 2) for x in stat.stddev]}")
        print(f"   - Min/Max RGB: {stat.extrema}")
        
        # Analizza luminosità generale
        grayscale = image.convert('L')
        hist = grayscale.histogram()
        avg_brightness = sum(i * hist[i] for i in range(256)) / sum(hist)
        print(f"   - Luminosità media: {round(avg_brightness, 2)}/255")
        
        # EXIF orientation
        try:
            exif = image._getexif()
            if exif:
                orientation = exif.get(274)  # 274 è il tag orientation
                print(f"   - EXIF Orientation: {orientation}")
        except:
            print(f"   - EXIF Orientation: N/A")
        
        # Test preprocessing
        print(f"\n🔬 TEST PREPROCESSING:")
        processor = GreenDotsProcessor()
        
        # Test con preprocessing
        preprocessed, original, scale = processor.preprocess_for_detection(image, target_width=1400)
        print(f"   - Scala applicata: {scale:.4f}")
        print(f"   - Dimensioni preprocessata: {preprocessed.size}")
        print(f"   - MediaPipe disponibile: {hasattr(processor, '_get_eyebrow_masks')}")
        
        # Test rilevamento con preprocessing
        print(f"\n🎯 RILEVAMENTO CON PREPROCESSING:")
        results_with_prep = processor.detect_green_dots(preprocessed)
        print(f"   - Puntini rilevati: {results_with_prep['total_dots']}")
        print(f"   - Pixel bianchi/verdi totali: {results_with_prep['total_green_pixels']}")
        
        if results_with_prep['total_dots'] > 0:
            print(f"\n   📍 Dettagli puntini:")
            for i, dot in enumerate(results_with_prep['dots'][:15], 1):  # Max 15
                # Calcola saturazione media del cluster
                avg_sat = sum(p['s'] for p in dot['pixels']) / len(dot['pixels'])
                avg_val = sum(p['v'] for p in dot['pixels']) / len(dot['pixels'])
                print(f"      {i}. Pos: ({dot['x']:4d}, {dot['y']:4d}), "
                      f"Size: {dot['size']:3d}px, "
                      f"Sat: {avg_sat:5.1f}%, Val: {avg_val:5.1f}%")
        
        # Test rilevamento SENZA preprocessing (immagine originale ridimensionata)
        print(f"\n🎯 RILEVAMENTO SENZA PREPROCESSING (immagine diretta):")
        
        # Ridimensiona se necessario
        max_dim = 1600
        if max(image.size) > max_dim:
            ratio = max_dim / max(image.size)
            test_img = image.resize((int(image.size[0]*ratio), int(image.size[1]*ratio)), Image.Resampling.LANCZOS)
            print(f"   - Ridimensionata a: {test_img.size}")
        else:
            test_img = image.copy()
        
        results_no_prep = processor.detect_green_dots(test_img)
        print(f"   - Puntini rilevati: {results_no_prep['total_dots']}")
        print(f"   - Pixel bianchi/verdi totali: {results_no_prep['total_green_pixels']}")
        
        if results_no_prep['total_dots'] > 0:
            print(f"\n   📍 Dettagli puntini:")
            for i, dot in enumerate(results_no_prep['dots'][:15], 1):
                avg_sat = sum(p['s'] for p in dot['pixels']) / len(dot['pixels'])
                avg_val = sum(p['v'] for p in dot['pixels']) / len(dot['pixels'])
                print(f"      {i}. Pos: ({dot['x']:4d}, {dot['y']:4d}), "
                      f"Size: {dot['size']:3d}px, "
                      f"Sat: {avg_sat:5.1f}%, Val: {avg_val:5.1f}%")
        
        # Salva immagine di debug
        debug_path = image_path.replace('.jpg', '_debug_analysis.jpg').replace('.JPG', '_debug_analysis.jpg')
        
        # Disegna heatmap pixel bianchi rilevati
        heatmap = Image.new('RGB', test_img.size, 'black')
        draw = ImageDraw.Draw(heatmap)
        
        for dot in results_no_prep['dots']:
            for pixel in dot['pixels']:
                x, y = pixel['x'], pixel['y']
                draw.point((x, y), fill='white')
        
        # Disegna centroidi con cerchi colorati
        for dot in results_no_prep['dots']:
            x, y = dot['x'], dot['y']
            r = 5
            draw.ellipse([x-r, y-r, x+r, y+r], outline='red', width=2)
        
        heatmap.save(debug_path)
        print(f"\n💾 Salvata heatmap debug: {debug_path}")
        
        return {
            'size': image.size,
            'format': image.format,
            'mode': image.mode,
            'brightness': avg_brightness,
            'scale_factor': scale,
            'dots_with_prep': results_with_prep['total_dots'],
            'dots_no_prep': results_no_prep['total_dots'],
            'pixels_detected': results_no_prep['total_green_pixels']
        }
        
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_images():
    """Confronta le due immagini."""
    
    print("\n" + "="*80)
    print("CONFRONTO IMMAGINI: successo.jpg vs fallisce.JPG")
    print("="*80)
    
    success_props = analyze_image_properties('successo.jpg')
    fail_props = analyze_image_properties('fallisce.JPG')
    
    if success_props and fail_props:
        print(f"\n{'='*80}")
        print("CONFRONTO FINALE")
        print(f"{'='*80}")
        
        print(f"\nDIMENSIONI:")
        print(f"   successo.jpg: {success_props['size']}")
        print(f"   fallisce.JPG: {fail_props['size']}")
        
        print(f"\nLUMINOSITÀ MEDIA:")
        print(f"   successo.jpg: {success_props['brightness']:.2f}")
        print(f"   fallisce.JPG: {fail_props['brightness']:.2f}")
        
        print(f"\nRISULTATI RILEVAMENTO (senza preprocessing):")
        print(f"   successo.jpg: {success_props['dots_no_prep']} puntini")
        print(f"   fallisce.JPG: {fail_props['dots_no_prep']} puntini")
        
        print(f"\nRISULTATI RILEVAMENTO (con preprocessing):")
        print(f"   successo.jpg: {success_props['dots_with_prep']} puntini")
        print(f"   fallisce.JPG: {fail_props['dots_with_prep']} puntini")
        
        print(f"\n{'='*80}")
        print("CONCLUSIONI:")
        print(f"{'='*80}")
        
        if fail_props['dots_no_prep'] == 0 and success_props['dots_no_prep'] > 0:
            print("\n❌ PROBLEMA IDENTIFICATO:")
            print("   fallisce.JPG non rileva NESSUN puntino mentre successo.jpg sì.")
            print("\n   Possibili cause:")
            print("   1. Parametri HSV non adatti per il colore dei puntini in fallisce.JPG")
            print("   2. Dimensione dei cluster troppo restrittiva")
            print("   3. Compattezza (compactness) troppo stringente")
            print("   4. Preprocessing MediaPipe non rileva correttamente le sopracciglia")
            print("   5. Qualità/compressione JPG diversa che altera i valori HSV")


if __name__ == "__main__":
    compare_images()
