"""
Test completo del pipeline di preprocessing delle sopracciglia con IMG_4675.JPEG
Genera immagini di debug per ogni fase per verificare il flusso reale
"""
import cv2
import numpy as np
import json
import matplotlib.pyplot as plt
from pathlib import Path

def load_image(path):
    """Carica immagine"""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Immagine non trovata: {path}")
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img_rgb

def point_in_polygon(point, polygon):
    """Ray casting algorithm per point-in-polygon"""
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside

def sample_pattern_3x3(img, cx, cy):
    """Campiona pattern 3x3 pixel"""
    h, w = img.shape[:2]
    total_r, total_g, total_b, total_lum, count = 0, 0, 0, 0, 0
    
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            px = int(cx + dx)
            py = int(cy + dy)
            
            if 0 <= px < w and 0 <= py < h:
                r, g, b = img[py, px]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                
                total_r += r
                total_g += g
                total_b += b
                total_lum += lum
                count += 1
    
    return {
        'avgLum': total_lum / count,
        'avgR': total_r / count,
        'avgG': total_g / count,
        'avgB': total_b / count
    }

def calculate_similarity(r, g, b, sample):
    """Calcola similarità (70% lum + 30% color)"""
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    
    lum_diff = abs(lum - sample['avgLum']) / 255
    color_diff = (
        abs(r - sample['avgR']) +
        abs(g - sample['avgG']) +
        abs(b - sample['avgB'])
    ) / (3 * 255)
    
    similarity = 1 - (lum_diff * 0.7 + color_diff * 0.3)
    return similarity

def remove_small_components(mask, min_size=50):
    """Rimuovi componenti piccole"""
    mask_uint8 = (mask * 255).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_uint8, connectivity=8)
    
    cleaned = np.zeros_like(mask)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= min_size:
            cleaned[labels == i] = 1
    
    return cleaned

def keep_largest_component(mask):
    """Mantieni solo il componente più grande"""
    mask_uint8 = (mask * 255).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_uint8, connectivity=8)
    
    if num_labels <= 1:
        return mask
    
    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    result = np.zeros_like(mask)
    result[labels == largest_label] = 1
    
    return result

def trace_moore_neighbor_contour(mask):
    """Traccia contorno con Moore-Neighbor"""
    # Trova primo pixel
    ys, xs = np.where(mask == 1)
    if len(xs) == 0:
        return []
    
    start_x, start_y = xs[0], ys[0]
    
    # Direzioni: N, NE, E, SE, S, SW, W, NW
    directions = [
        (0, -1), (1, -1), (1, 0), (1, 1),
        (0, 1), (-1, 1), (-1, 0), (-1, -1)
    ]
    
    contour = []
    current_x, current_y = start_x, start_y
    dir_idx = 7
    h, w = mask.shape
    
    max_iterations = h * w
    iterations = 0
    
    while iterations < max_iterations:
        contour.append((current_x, current_y))
        
        found = False
        for i in range(8):
            check_dir = (dir_idx + i) % 8
            dx, dy = directions[check_dir]
            next_x = current_x + dx
            next_y = current_y + dy
            
            if 0 <= next_x < w and 0 <= next_y < h:
                if mask[next_y, next_x] == 1:
                    current_x, current_y = next_x, next_y
                    dir_idx = (check_dir + 5) % 8
                    found = True
                    break
        
        if not found:
            break
        
        if current_x == start_x and current_y == start_y and len(contour) > 1:
            break
        
        iterations += 1
    
    return contour

def smooth_contour(contour, window=3):
    """Smooth con moving average"""
    if len(contour) < window:
        return contour
    
    smoothed = []
    for i in range(len(contour)):
        sum_x, sum_y = 0, 0
        for j in range(window):
            idx = (i - window // 2 + j) % len(contour)
            sum_x += contour[idx][0]
            sum_y += contour[idx][1]
        smoothed.append((sum_x // window, sum_y // window))
    
    return smoothed

# Landmarks simulati (devi sostituire con quelli reali da MediaPipe)
# Per questo test uso posizioni approssimative
landmarks = {
    'left': {
        'lm52': (350, 280),
        'lm105': (450, 280),
        'lm107': (320, 290),
        'lm55': (360, 260),
        'lm70': (440, 260),
        # Calcolo EXT points (offset verso esterno)
    },
    'right': {
        'lm282': (650, 280),  # speculare 52
        'lm334': (750, 280),  # speculare 105
        'lm336': (780, 290),  # speculare 107
        'lm285': (640, 260),  # speculare 55
        'lm300': (740, 260),  # speculare 70
    }
}

# Crea poligoni allargati (5 punti + 5 EXT)
def create_expanded_polygon(side_landmarks, side_name):
    """Crea poligono 5+5 punti EXT"""
    polygon = []
    
    if side_name == 'left':
        base_points = ['lm107', 'lm55', 'lm52', 'lm70', 'lm105']
        # Aggiungi offset per EXT points (simulati)
        offsets = [
            (-30, 5),   # 107 EXT
            (-10, -20), # 55 EXT
            (0, -25),   # 52 EXT
            (0, -25),   # 70 EXT
            (10, -20)   # 105 EXT
        ]
    else:
        base_points = ['lm336', 'lm285', 'lm282', 'lm300', 'lm334']
        offsets = [
            (30, 5),    # 336 EXT
            (10, -20),  # 285 EXT
            (0, -25),   # 282 EXT
            (0, -25),   # 300 EXT
            (-10, -20)  # 334 EXT
        ]
    
    for point_name in base_points:
        if point_name in side_landmarks:
            polygon.append(side_landmarks[point_name])
    
    # Aggiungi EXT points
    for i, offset in enumerate(offsets):
        base_point = polygon[i]
        ext_point = (base_point[0] + offset[0], base_point[1] + offset[1])
        polygon.append(ext_point)
    
    return polygon

print("=" * 80)
print("ANALISI COMPLETA PIPELINE PREPROCESSING - IMG_4675.JPEG")
print("=" * 80)

# Carica immagine
img_path = "webapp/IMG_4675.JPEG"
img = load_image(img_path)
h, w = img.shape[:2]
print(f"\n✅ Immagine caricata: {w}x{h} pixels")

# Output directory
output_dir = Path("debug_pipeline_IMG_4675")
output_dir.mkdir(exist_ok=True)

# FASE 0: Immagine originale
plt.figure(figsize=(12, 8))
plt.imshow(img)
plt.title("FASE 0: Immagine Originale")
plt.axis('off')
plt.savefig(output_dir / "00_originale.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Salvata: 00_originale.png")

# FASE 1: Poligoni allargati
for side_name in ['left', 'right']:
    side_landmarks = landmarks[side_name]
    polygon = create_expanded_polygon(side_landmarks, side_name)
    
    print(f"\n{'='*60}")
    print(f"PROCESSING: {side_name.upper()} EYEBROW")
    print(f"{'='*60}")
    
    # Visualizza poligono
    img_polygon = img.copy()
    polygon_array = np.array(polygon, dtype=np.int32)
    cv2.polylines(img_polygon, [polygon_array], True, (255, 0, 0), 2)
    for i, (x, y) in enumerate(polygon):
        cv2.circle(img_polygon, (x, y), 3, (0, 255, 0), -1)
        cv2.putText(img_polygon, str(i), (x+5, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
    
    plt.figure(figsize=(12, 8))
    plt.imshow(img_polygon)
    plt.title(f"FASE 1: Poligono Allargato {side_name.upper()} (5+5 EXT)")
    plt.axis('off')
    plt.savefig(output_dir / f"01_{side_name}_poligono.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 01_{side_name}_poligono.png")
    
    # FASE 2: Campionamento pattern 3x3
    lm_keys = list(side_landmarks.keys())
    cx_eyebrow = (side_landmarks[lm_keys[2]][0] + side_landmarks[lm_keys[4]][0]) / 2
    cy_eyebrow = (side_landmarks[lm_keys[2]][1] + side_landmarks[lm_keys[4]][1]) / 2
    
    cx_skin = (side_landmarks[lm_keys[0]][0] + polygon[5][0]) / 2
    cy_skin = (side_landmarks[lm_keys[0]][1] + polygon[5][1]) / 2
    
    eyebrow_sample = sample_pattern_3x3(img, cx_eyebrow, cy_eyebrow)
    skin_sample = sample_pattern_3x3(img, cx_skin, cy_skin)
    
    print(f"\n🔬 Campione SOPRACCIGLIO @ ({cx_eyebrow:.1f}, {cy_eyebrow:.1f}):")
    print(f"   Lum={eyebrow_sample['avgLum']:.1f}, RGB=({eyebrow_sample['avgR']:.0f},{eyebrow_sample['avgG']:.0f},{eyebrow_sample['avgB']:.0f})")
    
    print(f"🔬 Campione PELLE @ ({cx_skin:.1f}, {cy_skin:.1f}):")
    print(f"   Lum={skin_sample['avgLum']:.1f}, RGB=({skin_sample['avgR']:.0f},{skin_sample['avgG']:.0f},{skin_sample['avgB']:.0f})")
    
    img_samples = img.copy()
    cv2.circle(img_samples, (int(cx_eyebrow), int(cy_eyebrow)), 5, (255, 0, 0), -1)
    cv2.circle(img_samples, (int(cx_skin), int(cy_skin)), 5, (0, 255, 0), -1)
    cv2.rectangle(img_samples, 
                  (int(cx_eyebrow)-5, int(cy_eyebrow)-5),
                  (int(cx_eyebrow)+5, int(cy_eyebrow)+5),
                  (255, 0, 0), 2)
    cv2.rectangle(img_samples,
                  (int(cx_skin)-5, int(cy_skin)-5),
                  (int(cx_skin)+5, int(cy_skin)+5),
                  (0, 255, 0), 2)
    
    plt.figure(figsize=(12, 8))
    plt.imshow(img_samples)
    plt.title(f"FASE 2: Campionamento Pattern 3x3 {side_name.upper()}\nROSSO=Sopracciglio, VERDE=Pelle")
    plt.axis('off')
    plt.savefig(output_dir / f"02_{side_name}_samples.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 02_{side_name}_samples.png")
    
    # FASE 3: Binarizzazione con confronto similarità
    print(f"\n🔍 Binarizzazione (solo pixel dentro poligono)...")
    
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    min_x = max(0, int(min(xs)))
    max_x = min(w - 1, int(max(xs)))
    min_y = max(0, int(min(ys)))
    max_y = min(h - 1, int(max(ys)))
    
    binary_mask = np.zeros((h, w), dtype=np.uint8)
    
    pixels_checked = 0
    pixels_inside = 0
    pixels_eyebrow = 0
    
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            pixels_checked += 1
            
            if point_in_polygon((x, y), polygon):
                pixels_inside += 1
                r, g, b = img[y, x]
                
                eyebrow_sim = calculate_similarity(r, g, b, eyebrow_sample)
                skin_sim = calculate_similarity(r, g, b, skin_sample)
                
                # BIAS +0.15 per favorire sopracciglio (come nel codice)
                if eyebrow_sim > skin_sim:
                    binary_mask[y, x] = 1
                    pixels_eyebrow += 1
    
    print(f"   Pixel controllati: {pixels_checked}")
    print(f"   Pixel dentro poligono: {pixels_inside}")
    print(f"   Pixel classificati come sopracciglio: {pixels_eyebrow}")
    print(f"   Percentuale sopracciglio: {(pixels_eyebrow/pixels_inside*100):.1f}%")
    
    plt.figure(figsize=(12, 8))
    plt.imshow(binary_mask, cmap='gray')
    plt.title(f"FASE 3: Maschera Binaria {side_name.upper()}\nBIANCO=Sopracciglio, NERO=Pelle")
    plt.axis('off')
    plt.savefig(output_dir / f"03_{side_name}_binary_raw.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 03_{side_name}_binary_raw.png")
    
    # FASE 4: Morfologia - Remove small components
    print(f"\n🔧 Morfologia: Remove small components...")
    cleaned_mask = remove_small_components(binary_mask, min_size=50)
    cleaned_pixels = np.sum(cleaned_mask)
    print(f"   Pixel dopo pulizia: {cleaned_pixels}")
    
    plt.figure(figsize=(12, 8))
    plt.imshow(cleaned_mask, cmap='gray')
    plt.title(f"FASE 4: Dopo Remove Small Components {side_name.upper()}")
    plt.axis('off')
    plt.savefig(output_dir / f"04_{side_name}_cleaned.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 04_{side_name}_cleaned.png")
    
    # FASE 5: Keep largest component
    print(f"\n🔧 Morfologia: Keep largest component...")
    largest_mask = keep_largest_component(cleaned_mask)
    largest_pixels = np.sum(largest_mask)
    print(f"   Pixel componente più grande: {largest_pixels}")
    
    plt.figure(figsize=(12, 8))
    plt.imshow(largest_mask, cmap='gray')
    plt.title(f"FASE 5: Solo Componente Più Grande {side_name.upper()}")
    plt.axis('off')
    plt.savefig(output_dir / f"05_{side_name}_largest.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 05_{side_name}_largest.png")
    
    # FASE 6: Trace contour
    print(f"\n📐 Tracciamento contorno (Moore-Neighbor)...")
    contour = trace_moore_neighbor_contour(largest_mask)
    print(f"   Punti contorno: {len(contour)}")
    
    img_contour = img.copy()
    if len(contour) > 0:
        contour_array = np.array(contour, dtype=np.int32)
        cv2.polylines(img_contour, [contour_array], True, (255, 0, 255), 2)
    
    plt.figure(figsize=(12, 8))
    plt.imshow(img_contour)
    plt.title(f"FASE 6: Contorno Tracciato {side_name.upper()} ({len(contour)} punti)")
    plt.axis('off')
    plt.savefig(output_dir / f"06_{side_name}_contour_raw.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 06_{side_name}_contour_raw.png")
    
    # FASE 7: Smooth contour
    if len(contour) > 3:
        print(f"\n🔄 Smoothing contorno (window=3)...")
        smoothed = smooth_contour(contour, window=3)
        
        # Simplification
        simplification_factor = max(1, len(smoothed) // 200)
        simplified = smoothed[::simplification_factor]
        print(f"   Contorno smoothato: {len(smoothed)} punti")
        print(f"   Contorno semplificato: {len(simplified)} punti (factor={simplification_factor})")
        
        img_final = img.copy()
        simplified_array = np.array(simplified, dtype=np.int32)
        cv2.polylines(img_final, [simplified_array], True, (0, 255, 255), 2)
        cv2.fillPoly(img_final, [simplified_array], (255, 255, 0), lineType=cv2.LINE_AA)
        img_final = cv2.addWeighted(img, 0.7, img_final, 0.3, 0)
        
        plt.figure(figsize=(12, 8))
        plt.imshow(img_final)
        plt.title(f"FASE 7: Contorno FINALE Smoothato+Semplificato {side_name.upper()}\n({len(simplified)} punti)")
        plt.axis('off')
        plt.savefig(output_dir / f"07_{side_name}_contour_final.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Salvata: 07_{side_name}_contour_final.png")
        
        # CONFRONTO: Poligono vs Contorno
        img_comparison = img.copy()
        polygon_array = np.array(polygon, dtype=np.int32)
        cv2.polylines(img_comparison, [polygon_array], True, (255, 0, 0), 2)  # Rosso = poligono
        cv2.polylines(img_comparison, [simplified_array], True, (0, 255, 0), 3)  # Verde = contorno
        
        plt.figure(figsize=(12, 8))
        plt.imshow(img_comparison)
        plt.title(f"CONFRONTO {side_name.upper()}: ROSSO=Poligono Landmarks | VERDE=Contorno Binarizzato")
        plt.axis('off')
        plt.savefig(output_dir / f"08_{side_name}_CONFRONTO.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Salvata: 08_{side_name}_CONFRONTO.png")

print("\n" + "=" * 80)
print(f"✅ ANALISI COMPLETATA!")
print(f"📂 Tutte le immagini salvate in: {output_dir}/")
print("=" * 80)
print("\n🔍 VERIFICA:")
print("   - Le immagini 08_*_CONFRONTO.png mostrano se il contorno segue")
print("     la binarizzazione (VERDE) o il poligono landmarks (ROSSO)")
print("   - Se VERDE è molto diverso da ROSSO → contorno segue binarizzazione ✓")
print("   - Se VERDE coincide con ROSSO → bug, contorno segue landmarks ✗")
