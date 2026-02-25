#!/usr/bin/env python3
"""
Test con parametri ottimizzati per puntini BIANCHI
"""

import sys
import os
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from green_dots_processor import GreenDotsProcessor


def test_with_params(image_path, params_desc, **params):
    """Test con parametri specifici."""
    print(f"\n{'='*80}")
    print(f"TEST: {os.path.basename(image_path)} - {params_desc}")
    print(f"{'='*80}")
    
    try:
        image = Image.open(image_path)
        print(f"📐 {image.size[0]} x {image.size[1]}, Formato: {image.format}")
        
        processor = GreenDotsProcessor(**params)
        results = processor.process_pil_image(image, use_preprocessing=True)
        
        dots = results['detection_results']['total_dots']
        pixels = results['detection_results']['total_green_pixels']
        
        print(f"📊 Puntini: {dots}, Pixel: {pixels}")
        
        if dots > 0:
            print(f"📍 Dettagli (primi 10):")
            for i, dot in enumerate(results['detection_results']['dots'][:10], 1):
                avg_s = sum(p['s'] for p in dot['pixels']) / len(dot['pixels'])
                avg_v = sum(p['v'] for p in dot['pixels']) / len(dot['pixels'])
                avg_h = sum(p['h'] for p in dot['pixels']) / len(dot['pixels'])
                print(f"   {i:2d}. ({dot['x']:4d},{dot['y']:4d}) "
                      f"sz={dot['size']:3d} H={avg_h:5.1f}° S={avg_s:4.1f}% V={avg_v:4.1f}%")
        
        return dots
        
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        return 0


def main():
    print("\n" + "="*80)
    print("TEST PARAMETRI OTTIMIZZATI PER PUNTINI BIANCHI")
    print("="*80)
    
    # Parametri DEFAULT (per puntini verdi)
    print(f"\n{'*'*80}")
    print("PARAMETRI DEFAULT (per puntini VERDI)")
    print(f"{'*'*80}")
    print("Hue: 125-185°, Saturation: ≥50%, Value: 15-55%")
    
    s1 = test_with_params('successo.jpg', 'Default (verdi)',
                          hue_range=(125, 185),
                          saturation_min=50,
                          value_range=(15, 55))
    
    f1 = test_with_params('fallisce.JPG', 'Default (verdi)',
                          hue_range=(125, 185),
                          saturation_min=50,
                          value_range=(15, 55))
    
    # OSSERVAZIONI dai risultati precedenti:
    # I puntini BIANCHI hanno:
    # - Hue: 15-31° (arancione/rosso chiaro, NON verde!)
    # - Saturation: 8-20% (MOLTO BASSA, sotto il min 50!)
    # - Value: 79-92% (alta luminosità)
    
    print(f"\n{'*'*80}")
    print("PARAMETRI OTTIMIZZATI (per puntini BIANCHI)")
    print(f"{'*'*80}")
    print("Hue: 0-360° (qualsiasi - irrilevante per bianco)")
    print("Saturation: ≥0% min (eliminato filtro)")
    print("Value: 78-95% (alta luminosità)")
    
    # Test 1: Parametri come in main.js (frontend)
    print(f"\n--- TEST 1: Come in main.js (frontend) ---")
    s2 = test_with_params('successo.jpg', 'Frontend params',
                          hue_range=(60, 150),
                          saturation_min=15,
                          value_range=(15, 95))
    
    f2 = test_with_params('fallisce.JPG', 'Frontend params',
                          hue_range=(60, 150),
                          saturation_min=15,
                          value_range=(15, 95))
    
    # Test 2: Parametri ancora più permissivi per bianchi
    print(f"\n--- TEST 2: Parametri ottimizzati per bianchi ---")
    s3 = test_with_params('successo.jpg', 'Ottimizzati bianchi',
                          hue_range=(0, 360),      # Qualsiasi hue
                          saturation_min=0,         # NESSUN filtro saturazione
                          value_range=(78, 95),     # Solo luminosità alta
                          cluster_size_range=(3, 150),  # Min 3 pixel
                          clustering_radius=3)
    
    f3 = test_with_params('fallisce.JPG', 'Ottimizzati bianchi',
                          hue_range=(0, 360),
                          saturation_min=0,
                          value_range=(78, 95),
                          cluster_size_range=(3, 150),
                          clustering_radius=3)
    
    # Test 3: Parametri ULTRA permissivi
    print(f"\n--- TEST 3: ULTRA permissivi ---")
    s4 = test_with_params('successo.jpg', 'Ultra permissivi',
                          hue_range=(0, 360),
                          saturation_min=0,
                          value_range=(70, 100),    # Ancora più ampio
                          cluster_size_range=(2, 200),  # Più permissivo
                          clustering_radius=4)      # Radius più ampio
    
    f4 = test_with_params('fallisce.JPG', 'Ultra permissivi',
                          hue_range=(0, 360),
                          saturation_min=0,
                          value_range=(70, 100),
                          cluster_size_range=(2, 200),
                          clustering_radius=4)
    
    # RIEPILOGO
    print(f"\n{'='*80}")
    print("RIEPILOGO RISULTATI")
    print(f"{'='*80}")
    print(f"\n{'Test':<30} | {'successo.jpg':>15} | {'fallisce.JPG':>15}")
    print(f"{'-'*30}-|-{'-'*15}-|-{'-'*15}")
    print(f"{'Default (verdi)':<30} | {s1:>15} | {f1:>15}")
    print(f"{'Frontend params':<30} | {s2:>15} | {f2:>15}")
    print(f"{'Ottimizzati bianchi':<30} | {s3:>15} | {f3:>15}")
    print(f"{'Ultra permissivi':<30} | {s4:>15} | {f4:>15}")
    
    print(f"\n{'='*80}")
    print("CONCLUSIONI")
    print(f"{'='*80}")
    
    print("\n🔍 PROBLEMA IDENTIFICATO:")
    print("\n1. I parametri DEFAULT sono per PUNTINI VERDI:")
    print("   - Hue: 125-185° (verde)")
    print("   - Saturation: ≥50% (colori saturi)")
    print("   - Value: 15-55% (luminosità medio-bassa)")
    
    print("\n2. I puntini nelle immagini sono BIANCHI/BIANCASTRI:")
    print("   - Hue: 15-31° (non verde!)")
    print("   - Saturation: 8-20% (MOLTO SOTTO il minimo 50%)")
    print("   - Value: 79-92% (luminosità alta)")
    
    print("\n3. Il codice in is_green_pixel() ha un check per bianchi:")
    print("   - is_white = (s <= 20 and 78 <= v <= 95)")
    print("   - Ma i parametri del costruttore NON VENGONO USATI per questo check!")
    
    print("\n4. Il problema è che detect_green_dots chiama is_green_pixel")
    print("   che controlla PRIMA i parametri del costruttore (verdi)")
    print("   e POI controlla il bianco. Ma con saturation_min=50,")
    print("   i pixel con sat=8-20% vengono esclusi PRIMA di verificare il bianco!")
    
    print("\n💡 SOLUZIONE:")
    print("   Modificare is_green_pixel per dare priorità al check del bianco")
    print("   PRIMA di applicare i filtri di saturazione per il verde.")


if __name__ == "__main__":
    main()
