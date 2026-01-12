#!/usr/bin/env python3
"""
Script di test per verificare il rilevamento di puntini bianchi.
Testa l'algoritmo modificato su un'immagine con puntini bianchi.

Usage:
    python test_white_dots.py white.jpg
"""

import sys
import os
from PIL import Image, ImageDraw
import json
import numpy as np

# Aggiungi il percorso src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from green_dots_processor import GreenDotsProcessor


def test_white_dots_detection(image_path: str):
    """
    Testa il rilevamento di puntini bianchi su un'immagine.
    
    Args:
        image_path: Percorso dell'immagine da testare
    """
    print(f"\n{'='*70}")
    print(f"TEST RILEVAMENTO PUNTINI BIANCHI")
    print(f"{'='*70}\n")
    
    # Verifica che l'immagine esista
    if not os.path.exists(image_path):
        print(f"❌ ERRORE: Immagine '{image_path}' non trovata!")
        return False
    
    print(f"📂 Caricamento immagine: {image_path}")
    
    try:
        # Carica l'immagine
        image = Image.open(image_path)
        original_size = image.size
        print(f"✅ Immagine caricata: {image.size[0]}x{image.size[1]} pixels")
        
        # Ridimensiona immagini troppo grandi per velocizzare il test
        max_dimension = 1600
        if max(image.size) > max_dimension:
            ratio = max_dimension / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            print(f"⚡ Ridimensionata a: {image.size[0]}x{image.size[1]} pixels (per velocità)")
        else:
            print(f"✓ Dimensione ottimale, nessun ridimensionamento necessario")
        
        # Crea il processore con parametri per rilevare bianco
        print("\n🔧 Configurazione processore:")
        print("   - Hue range: 0-360 (irrilevante per bianco)")
        print("   - Saturation: 0-30 (bassa saturazione = colori desaturati/bianchi)")
        print("   - Value: 70-100 (alta luminosità)")
        print("   - Cluster size: 2-170 pixels")
        print("   - Clustering radius: 3 pixels")
        
        processor = GreenDotsProcessor(
            hue_range=(0, 360),
            saturation_min=0,
            saturation_max=30,
            value_range=(70, 100),
            cluster_size_range=(2, 170),
            clustering_radius=3
        )
        
        # Rileva i puntini
        print("\n🔍 Rilevamento puntini bianchi in corso...")
        results = processor.detect_green_dots(image)
        
        # Stampa risultati
        print(f"\n📊 RISULTATI RILEVAMENTO:")
        print(f"   - Puntini rilevati: {results['total_dots']}")
        print(f"   - Pixel bianchi totali: {results['total_white_pixels']}")
        print(f"   - Dimensioni immagine: {results['image_size']}")
        
        # Dividi i puntini in sinistro e destro
        left_dots, right_dots = processor.divide_dots_by_vertical_center(
            results['dots'], 
            results['image_size'][0]
        )
        
        print(f"\n📍 DIVISIONE PUNTINI:")
        print(f"   - Puntini sinistri (Sx): {len(left_dots)}")
        print(f"   - Puntini destri (Dx): {len(right_dots)}")
        
        # Stampa dettagli di ogni puntino
        print(f"\n🔎 DETTAGLI PUNTINI SINISTRI (Sx):")
        for i, dot in enumerate(left_dots, 1):
            print(f"   {i}. Posizione: ({dot['x']}, {dot['y']}), Dimensione: {dot['size']} px")
        
        print(f"\n🔎 DETTAGLI PUNTINI DESTRI (Dx):")
        for i, dot in enumerate(right_dots, 1):
            print(f"   {i}. Posizione: ({dot['x']}, {dot['y']}), Dimensione: {dot['size']} px")
        
        # Crea immagine di output con i puntini evidenziati
        output_image = image.copy()
        draw = ImageDraw.Draw(output_image)
        
        # Disegna i puntini sinistri in blu
        for dot in left_dots:
            x, y = dot['x'], dot['y']
            radius = 8
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], 
                        outline='blue', width=3)
            draw.text((x+10, y), f"Sx{left_dots.index(dot)+1}", fill='blue')
        
        # Disegna i puntini destri in rosso
        for dot in right_dots:
            x, y = dot['x'], dot['y']
            radius = 8
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], 
                        outline='red', width=3)
            draw.text((x+10, y), f"Dx{right_dots.index(dot)+1}", fill='red')
        
        # Disegna la linea centrale
        img_width = results['image_size'][0]
        img_height = results['image_size'][1]
        center_x = img_width // 2
        draw.line([(center_x, 0), (center_x, img_height)], 
                 fill='green', width=2)
        
        # Salva l'immagine di output
        output_path = image_path.replace('.jpg', '_detected.jpg').replace('.png', '_detected.png')
        output_image.save(output_path)
        print(f"\n💾 Immagine con rilevamento salvata: {output_path}")
        
        # ========== GENERA IMMAGINI DI DEBUG ==========
        print(f"\n🎨 Generazione immagini di debug...")
        
        # 1. Immagine con poligoni delle sopracciglia
        debug_polygons = image.copy()
        draw_poly = ImageDraw.Draw(debug_polygons, 'RGBA')
        
        if len(left_dots) >= 3:
            # Crea poligono sinistro (blu trasparente)
            left_points = [(d['x'], d['y']) for d in left_dots]
            draw_poly.polygon(left_points, fill=(0, 0, 255, 80), outline='blue')
            for i, p in enumerate(left_points, 1):
                draw_poly.ellipse([p[0]-5, p[1]-5, p[0]+5, p[1]+5], fill='blue')
                draw_poly.text((p[0]+8, p[1]-8), str(i), fill='blue')
        
        if len(right_dots) >= 3:
            # Crea poligono destro (rosso trasparente)
            right_points = [(d['x'], d['y']) for d in right_dots]
            draw_poly.polygon(right_points, fill=(255, 0, 0, 80), outline='red')
            for i, p in enumerate(right_points, 1):
                draw_poly.ellipse([p[0]-5, p[1]-5, p[0]+5, p[1]+5], fill='red')
                draw_poly.text((p[0]+8, p[1]-8), str(i), fill='red')
        
        # Linea centrale
        draw_poly.line([(center_x, 0), (center_x, img_height)], fill='green', width=2)
        
        polygons_path = image_path.replace('.jpg', '_polygons.jpg').replace('.png', '_polygons.png')
        debug_polygons.save(polygons_path)
        print(f"   ✅ Poligoni sopracciglia: {polygons_path}")
        
        # 2. Immagine con maschere MediaPipe (se disponibile)
        print(f"   ⏳ Tentativo generazione maschere MediaPipe...")
        try:
            import cv2
            
            # Converti PIL a numpy/OpenCV
            img_np = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Rileva maschere sopracciglia (solo se MediaPipe è disponibile)
            if hasattr(processor, '_get_eyebrow_masks'):
                left_poly, right_poly, left_bbox, right_bbox = processor._get_eyebrow_masks(img_np)
            
                debug_masks = image.copy()
                draw_masks = ImageDraw.Draw(debug_masks, 'RGBA')
                
                # Disegna bounding boxes
                if left_bbox:
                    draw_masks.rectangle(left_bbox, outline='cyan', width=3)
                    draw_masks.text((left_bbox[0]+5, left_bbox[1]+5), 'Sx Area', fill='cyan')
                
                if right_bbox:
                    draw_masks.rectangle(right_bbox, outline='magenta', width=3)
                    draw_masks.text((right_bbox[0]+5, right_bbox[1]+5), 'Dx Area', fill='magenta')
                
                # Disegna poligoni MediaPipe
                if left_poly is not None and len(left_poly) > 0:
                    left_poly_points = [(int(p[0]), int(p[1])) for p in left_poly]
                    draw_masks.polygon(left_poly_points, fill=(0, 255, 255, 60), outline='cyan')
                
                if right_poly is not None and len(right_poly) > 0:
                    right_poly_points = [(int(p[0]), int(p[1])) for p in right_poly]
                    draw_masks.polygon(right_poly_points, fill=(255, 0, 255, 60), outline='magenta')
                
                masks_path = image_path.replace('.jpg', '_masks.jpg').replace('.png', '_masks.png')
                debug_masks.save(masks_path)
                print(f"   ✅ Maschere MediaPipe: {masks_path}")
            else:
                print(f"   ⚠️  MediaPipe non disponibile in questo processore")
            
        except Exception as e:
            print(f"   ⚠️  Maschere MediaPipe non disponibili: {str(e)}")
        
        # 3. Mappa di calore dei pixel bianchi rilevati
        heatmap = Image.new('RGB', image.size, 'black')
        draw_heat = ImageDraw.Draw(heatmap)
        
        for dot in results['dots']:
            for pixel in dot['pixels']:
                x, y = pixel['x'], pixel['y']
                # Disegna pixel in bianco
                draw_heat.point((x, y), fill='white')
        
        heatmap_path = image_path.replace('.jpg', '_heatmap.jpg').replace('.png', '_heatmap.png')
        heatmap.save(heatmap_path)
        print(f"   ✅ Mappa pixel bianchi: {heatmap_path}")
        
        # 4. Immagine con overlay preprocessing (se disponibile)
        try:
            preprocessed_img, left_mask_poly, right_mask_poly, left_crop_bbox, right_crop_bbox = processor.preprocess_for_detection(image)
            
            prep_debug = preprocessed_img.copy()
            draw_prep = ImageDraw.Draw(prep_debug, 'RGBA')
            
            if left_crop_bbox:
                draw_prep.rectangle(left_crop_bbox, outline='yellow', width=4)
                draw_prep.text((left_crop_bbox[0]+5, left_crop_bbox[1]+5), 'Sx Crop', fill='yellow')
            
            if right_crop_bbox:
                draw_prep.rectangle(right_crop_bbox, outline='orange', width=4)
                draw_prep.text((right_crop_bbox[0]+5, right_crop_bbox[1]+5), 'Dx Crop', fill='orange')
            
            prep_path = image_path.replace('.jpg', '_preprocessing.jpg').replace('.png', '_preprocessing.png')
            prep_debug.save(prep_path)
            print(f"   ✅ Preprocessing areas: {prep_path}")
            
        except Exception as e:
            print(f"   ⚠️  Preprocessing debug non disponibile: {str(e)}")
        
        # Salva i risultati in JSON
        json_path = image_path.replace('.jpg', '_results.json').replace('.png', '_results.json')
        results_to_save = {
            'total_dots': results['total_dots'],
            'total_white_pixels': results['total_white_pixels'],
            'image_size': results['image_size'],
            'left_dots': len(left_dots),
            'right_dots': len(right_dots),
            'dots_sx': [{'x': d['x'], 'y': d['y'], 'size': d['size']} for d in left_dots],
            'dots_dx': [{'x': d['x'], 'y': d['y'], 'size': d['size']} for d in right_dots],
            'parameters': results['parameters']
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results_to_save, f, indent=2, ensure_ascii=False)
        print(f"💾 Risultati JSON salvati: {json_path}")
        
        # Verifica se abbiamo rilevato circa 10 punti divisi in due gruppi
        print(f"\n🎯 VERIFICA TEST:")
        if results['total_dots'] >= 8 and results['total_dots'] <= 12:
            print(f"   ✅ Numero puntini OK: {results['total_dots']} (target: ~10)")
        else:
            print(f"   ⚠️  Numero puntini: {results['total_dots']} (target: ~10)")
        
        if len(left_dots) > 0 and len(right_dots) > 0:
            print(f"   ✅ Puntini divisi correttamente in Sx e Dx")
        else:
            print(f"   ⚠️  Problemi nella divisione: Sx={len(left_dots)}, Dx={len(right_dots)}")
        
        print(f"\n{'='*70}")
        print("✅ TEST COMPLETATO CON SUCCESSO!")
        print(f"{'='*70}\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRORE durante il test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_white_dots.py <image_path>")
        print("Example: python test_white_dots.py white.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    success = test_white_dots_detection(image_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
