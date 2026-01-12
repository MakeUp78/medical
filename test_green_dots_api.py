#!/usr/bin/env python3
"""
Test rapido per verificare che l'API green-dots funzioni correttamente
"""
import requests
import base64
from PIL import Image, ImageDraw
import io
import json

def create_test_image_with_green_dots():
    """Crea un'immagine di test con 10 puntini verdi"""
    # Crea immagine 800x600 bianca
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Aggiungi 10 puntini verdi (5 a sinistra, 5 a destra)
    green_color = (0, 255, 0)
    
    # Puntini sinistri (x < 400)
    left_dots = [
        (200, 150), (180, 200), (220, 250), (190, 300), (210, 350)
    ]
    
    # Puntini destri (x >= 400)
    right_dots = [
        (600, 150), (620, 200), (580, 250), (610, 300), (590, 350)
    ]
    
    all_dots = left_dots + right_dots
    
    # Disegna ogni punto come un cerchio verde di raggio 5px
    for x, y in all_dots:
        draw.ellipse([x-5, y-5, x+5, y+5], fill=green_color)
    
    return img

def image_to_base64(image):
    """Converte un'immagine PIL in base64"""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def test_green_dots_api():
    """Testa l'API green-dots"""
    print("🧪 Test API Green Dots")
    print("=" * 50)
    
    # 1. Crea immagine di test
    print("\n1. Creazione immagine di test con 10 puntini verdi...")
    test_img = create_test_image_with_green_dots()
    img_base64 = image_to_base64(test_img)
    print(f"   ✅ Immagine creata (dimensione base64: {len(img_base64)} caratteri)")
    
    # 2. Testa endpoint info
    print("\n2. Test endpoint /api/green-dots/info...")
    try:
        response = requests.get('http://127.0.0.1:8001/api/green-dots/info', timeout=10)
        if response.status_code == 200:
            info = response.json()
            print(f"   ✅ Endpoint info OK - Modulo disponibile: {info['available']}")
        else:
            print(f"   ❌ Errore {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Errore connessione: {e}")
        return False
    
    # 3. Testa endpoint analyze
    print("\n3. Test endpoint /api/green-dots/analyze...")
    payload = {
        "image": img_base64,
        "hue_range": [60, 150],
        "saturation_min": 15,
        "value_range": [15, 95],
        "cluster_size_range": [2, 150],
        "clustering_radius": 2
    }
    
    try:
        print("   ⏳ Invio richiesta...")
        response = requests.post(
            'http://127.0.0.1:8001/api/green-dots/analyze',
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Analisi completata!")
            print(f"   📊 Successo: {result['success']}")
            
            if result['success']:
                detection = result['detection_results']
                print(f"   📊 Punti rilevati: {detection['total_dots']}")
                print(f"   📊 Pixel verdi: {detection['total_green_pixels']}")
                print(f"   📊 Dimensioni immagine: {detection['image_size']}")
                
                if result.get('groups'):
                    print(f"   📊 Gruppo Sinistro: {len(result['groups']['Sx'])} punti")
                    print(f"   📊 Gruppo Destro: {len(result['groups']['Dx'])} punti")
                
                if result.get('statistics'):
                    stats = result['statistics']
                    print(f"   📊 Area sinistra: {stats['left']['area']:.1f} px²")
                    print(f"   📊 Area destra: {stats['right']['area']:.1f} px²")
                
                if result.get('overlay_base64'):
                    print(f"   📊 Overlay generato: {len(result['overlay_base64'])} caratteri")
                
                return True
            else:
                print(f"   ⚠️ Analisi non riuscita: {result.get('error', 'Errore sconosciuto')}")
                return False
        else:
            print(f"   ❌ Errore {response.status_code}")
            print(f"   Dettagli: {response.text[:500]}")
            return False
            
    except requests.Timeout:
        print(f"   ❌ Timeout dopo 120 secondi")
        return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False

if __name__ == "__main__":
    success = test_green_dots_api()
    print("\n" + "=" * 50)
    if success:
        print("✅ TUTTI I TEST PASSATI")
    else:
        print("❌ TEST FALLITI")
    print("=" * 50)
