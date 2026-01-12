#!/usr/bin/env python3
"""
Test dell'API green-dots con l'immagine reale src/green.png
"""
import requests
import base64
from PIL import Image
import io
import time

def image_file_to_base64(image_path):
    """Legge un'immagine da file e la converte in base64"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def test_with_real_image():
    """Testa l'API con src/green.png"""
    print("🧪 Test API Green Dots con src/green.png")
    print("=" * 70)
    
    image_path = '/var/www/html/kimerika.cloud/src/green.png'
    
    # 1. Carica immagine
    print(f"\n1. Caricamento immagine: {image_path}")
    try:
        # Verifica dimensioni
        img = Image.open(image_path)
        print(f"   ✅ Immagine caricata: {img.size[0]}x{img.size[1]} px")
        print(f"   📏 Formato: {img.format}, Modalità: {img.mode}")
        
        # Converti in base64
        img_base64 = image_file_to_base64(image_path)
        print(f"   📊 Dimensione base64: {len(img_base64)} caratteri ({len(img_base64)/1024:.1f} KB)")
    except Exception as e:
        print(f"   ❌ Errore caricamento: {e}")
        return False
    
    # 2. Testa endpoint analyze
    print("\n2. Invio richiesta a /api/green-dots/analyze...")
    payload = {
        "image": img_base64,
        "hue_range": [42, 158],
        "saturation_min": 13,
        "value_range": [12, 98],
        "cluster_size_range": [2, 170],
        "clustering_radius": 3
    }
    
    try:
        print("   ⏳ Elaborazione in corso...")
        start_time = time.time()
        
        response = requests.post(
            'http://127.0.0.1:8001/api/green-dots/analyze',
            json=payload,
            timeout=180
        )
        
        elapsed_time = time.time() - start_time
        print(f"   ⏱️  Tempo elaborazione: {elapsed_time:.2f} secondi")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n   ✅ RISPOSTA API RICEVUTA!")
            print(f"   {'=' * 66}")
            print(f"   📊 Successo: {result['success']}")
            print(f"   📊 Session ID: {result.get('session_id', 'N/A')}")
            
            if result['success']:
                detection = result['detection_results']
                print(f"\n   🎯 RISULTATI RILEVAMENTO:")
                print(f"   {'─' * 66}")
                print(f"   • Punti rilevati: {detection['total_dots']}")
                print(f"   • Pixel verdi totali: {detection['total_green_pixels']}")
                print(f"   • Dimensioni immagine: {detection['image_size']}")
                
                if detection['dots']:
                    print(f"\n   📍 PRIMI 5 PUNTI RILEVATI:")
                    for i, dot in enumerate(detection['dots'][:5], 1):
                        print(f"      {i}. Posizione: ({dot['x']}, {dot['y']}) - Dimensione cluster: {dot['size']} px")
                
                if result.get('groups'):
                    print(f"\n   🔄 GRUPPI:")
                    print(f"   {'─' * 66}")
                    print(f"   • Gruppo Sinistro (Sx): {len(result['groups']['Sx'])} punti")
                    print(f"   • Gruppo Destro (Dx): {len(result['groups']['Dx'])} punti")
                    
                    if result['groups']['Sx']:
                        print(f"\n   📍 Punti Sinistri:")
                        for i, p in enumerate(result['groups']['Sx'], 1):
                            print(f"      {i}. ({p['x']}, {p['y']})")
                    
                    if result['groups']['Dx']:
                        print(f"\n   📍 Punti Destri:")
                        for i, p in enumerate(result['groups']['Dx'], 1):
                            print(f"      {i}. ({p['x']}, {p['y']})")
                
                if result.get('statistics'):
                    stats = result['statistics']
                    print(f"\n   📊 STATISTICHE:")
                    print(f"   {'─' * 66}")
                    if stats.get('left'):
                        print(f"   • Area Sinistra: {stats['left']['area']:.1f} px²")
                        print(f"   • Perimetro Sinistro: {stats['left']['perimeter']:.1f} px")
                    if stats.get('right'):
                        print(f"   • Area Destra: {stats['right']['area']:.1f} px²")
                        print(f"   • Perimetro Destro: {stats['right']['perimeter']:.1f} px")
                    if stats.get('combined'):
                        print(f"   • Area Totale: {stats['combined']['total_area']:.1f} px²")
                
                if result.get('overlay_base64'):
                    overlay_size = len(result['overlay_base64'])
                    print(f"\n   🎨 OVERLAY:")
                    print(f"   {'─' * 66}")
                    print(f"   • Overlay generato: {overlay_size} caratteri ({overlay_size/1024:.1f} KB)")
                
                if result.get('warning'):
                    print(f"\n   ⚠️  WARNING: {result['warning']}")
                
                print(f"\n   {'=' * 66}")
                return True
            else:
                print(f"   ⚠️ Analisi non riuscita: {result.get('error', 'Errore sconosciuto')}")
                return False
        else:
            print(f"\n   ❌ ERRORE HTTP {response.status_code}")
            print(f"   Dettagli: {response.text[:1000]}")
            return False
            
    except requests.Timeout:
        print(f"\n   ❌ TIMEOUT dopo 180 secondi")
        return False
    except Exception as e:
        print(f"\n   ❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_with_real_image()
    print("\n" + "=" * 70)
    if success:
        print("✅ TEST COMPLETATO CON SUCCESSO!")
        print("   L'API green-dots funziona correttamente con src/green.png")
    else:
        print("❌ TEST FALLITO")
        print("   Controllare i log per maggiori dettagli")
    print("=" * 70)
