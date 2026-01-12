#!/usr/bin/env python3
"""
Test per confrontare prova3.jpg: diretto backend vs simulazione frontend
"""
import requests
import base64
from PIL import Image
import io

def test_direct_backend():
    """Test diretto con il file"""
    print("=" * 70)
    print("TEST 1: File diretto al backend")
    print("=" * 70)
    
    with open('/var/www/html/kimerika.cloud/src/prova3.jpg', 'rb') as f:
        img_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    img = Image.open('/var/www/html/kimerika.cloud/src/prova3.jpg')
    print(f"📊 Dimensioni originali: {img.size[0]}x{img.size[1]}")
    print(f"📊 Formato: {img.format}, Modo: {img.mode}")
    
    response = requests.post(
        'http://127.0.0.1:8001/api/green-dots/analyze',
        json={
            "image": img_base64,
            "hue_range": [42, 158],
            "saturation_min": 13,
            "value_range": [12, 98],
            "cluster_size_range": [2, 170],
            "clustering_radius": 3
        },
        timeout=120
    )
    
    result = response.json()
    if result['success']:
        print(f"✅ Punti rilevati: {result['detection_results']['total_dots']}")
        print(f"✅ Pixel verdi: {result['detection_results']['total_green_pixels']}")
    else:
        print(f"❌ Errore: {result.get('error', 'N/A')}")
    
    return result

def test_frontend_simulation():
    """Simula il processo frontend: carica -> resize -> PNG -> base64"""
    print("\n" + "=" * 70)
    print("TEST 2: Simulazione processo frontend (resize + PNG conversion)")
    print("=" * 70)
    
    # Carica immagine
    img = Image.open('/var/www/html/kimerika.cloud/src/prova3.jpg')
    orig_size = img.size
    print(f"📊 Dimensioni originali: {orig_size[0]}x{orig_size[1]}")
    
    # Simula resize frontend (max 1600px)
    max_dimension = 1600
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        print(f"📐 Resize applicato: {new_size[0]}x{new_size[1]} (ratio: {ratio:.2f})")
    
    # Converte in PNG (come fa canvas.toDataURL)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    png_data = buffer.getvalue()
    print(f"📊 Dimensione PNG: {len(png_data) / 1024:.1f} KB")
    
    # Codifica in base64
    img_base64 = base64.b64encode(png_data).decode('utf-8')
    
    response = requests.post(
        'http://127.0.0.1:8001/api/green-dots/analyze',
        json={
            "image": img_base64,
            "hue_range": [42, 158],
            "saturation_min": 13,
            "value_range": [12, 98],
            "cluster_size_range": [2, 170],
            "clustering_radius": 3
        },
        timeout=120
    )
    
    result = response.json()
    if result['success']:
        print(f"✅ Punti rilevati: {result['detection_results']['total_dots']}")
        print(f"✅ Pixel verdi: {result['detection_results']['total_green_pixels']}")
    else:
        print(f"❌ Errore: {result.get('error', 'N/A')}")
    
    return result

def test_jpeg_quality():
    """Test con JPEG invece di PNG"""
    print("\n" + "=" * 70)
    print("TEST 3: Simulazione con JPEG (invece di PNG)")
    print("=" * 70)
    
    img = Image.open('/var/www/html/kimerika.cloud/src/prova3.jpg')
    
    # Simula resize frontend
    max_dimension = 1600
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        print(f"📐 Resize: {new_size[0]}x{new_size[1]}")
    
    # Converte in JPEG con qualità alta
    buffer = io.BytesIO()
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(buffer, format='JPEG', quality=95)
    jpeg_data = buffer.getvalue()
    print(f"📊 Dimensione JPEG: {len(jpeg_data) / 1024:.1f} KB")
    
    img_base64 = base64.b64encode(jpeg_data).decode('utf-8')
    
    response = requests.post(
        'http://127.0.0.1:8001/api/green-dots/analyze',
        json={
            "image": img_base64,
            "hue_range": [42, 158],
            "saturation_min": 13,
            "value_range": [12, 98],
            "cluster_size_range": [2, 170],
            "clustering_radius": 3
        },
        timeout=120
    )
    
    result = response.json()
    if result['success']:
        print(f"✅ Punti rilevati: {result['detection_results']['total_dots']}")
        print(f"✅ Pixel verdi: {result['detection_results']['total_green_pixels']}")
    else:
        print(f"❌ Errore: {result.get('error', 'N/A')}")
    
    return result

if __name__ == "__main__":
    r1 = test_direct_backend()
    r2 = test_frontend_simulation()
    r3 = test_jpeg_quality()
    
    print("\n" + "=" * 70)
    print("RIEPILOGO")
    print("=" * 70)
    print(f"Test 1 (File diretto):     {r1['detection_results']['total_dots']} punti")
    print(f"Test 2 (Frontend PNG):     {r2['detection_results']['total_dots']} punti")
    print(f"Test 3 (Frontend JPEG):    {r3['detection_results']['total_dots']} punti")
    
    if r2['detection_results']['total_dots'] < r1['detection_results']['total_dots']:
        print("\n⚠️  PROBLEMA: Conversione PNG perde colori verdi!")
        print("💡 SOLUZIONE: Usare JPEG nel frontend invece di PNG")
