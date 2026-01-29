"""
Test REALE del pipeline di preprocessing delle sopracciglia con IMG_4675.JPEG
Usa MediaPipe per ottenere landmarks reali e replica il processo JavaScript
"""
import cv2
import numpy as np
import mediapipe as mp
import matplotlib.pyplot as plt
from pathlib import Path

def point_in_polygon(point, polygon):
    """Ray casting algorithm"""
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
    ys, xs = np.where(mask == 1)
    if len(xs) == 0:
        return []
    
    start_x, start_y = xs[0], ys[0]
    
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

print("=" * 80)
print("ANALISI REALE PIPELINE - IMG_4675.JPEG CON MEDIAPIPE")
print("=" * 80)

# Carica immagine
img_path = "webapp/IMG_4675.JPEG"
img_bgr = cv2.imread(img_path)
if img_bgr is None:
    raise FileNotFoundError(f"Immagine non trovata: {img_path}")

img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
h, w = img.shape[:2]
print(f"\n✅ Immagine caricata: {w}x{h} pixels")

# Output directory
output_dir = Path("debug_real_pipeline_IMG_4675")
output_dir.mkdir(exist_ok=True)

# FASE 0: Originale
plt.figure(figsize=(12, 16))
plt.imshow(img)
plt.title("FASE 0: Immagine Originale")
plt.axis('off')
plt.savefig(output_dir / "00_originale.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Salvata: 00_originale.png")

# MediaPipe Face Mesh
print("\n🔍 Esecuzione MediaPipe Face Mesh...")
mp_face_mesh = mp.solutions.face_mesh
with mp_face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5
) as face_mesh:
    results = face_mesh.process(img)
    
    if not results.multi_face_landmarks:
        print("❌ Nessun volto rilevato!")
        exit(1)
    
    face_landmarks = results.multi_face_landmarks[0]
    print(f"✅ Rilevati {len(face_landmarks.landmark)} landmarks")

# Converti landmarks in coordinate pixel
landmarks = []
for lm in face_landmarks.landmark:
    x = int(lm.x * w)
    y = int(lm.y * h)
    landmarks.append((x, y))

# Visualizza tutti landmarks
img_all_lm = img.copy()
for i, (x, y) in enumerate(landmarks):
    cv2.circle(img_all_lm, (x, y), 2, (0, 255, 0), -1)

plt.figure(figsize=(12, 16))
plt.imshow(img_all_lm)
plt.title(f"FASE 1: MediaPipe Face Mesh - {len(landmarks)} Landmarks")
plt.axis('off')
plt.savefig(output_dir / "01_all_landmarks.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Salvata: 01_all_landmarks.png")

# LANDMARKS SPECIFICI SOPRACCIGLIA (come nel codice JS)
# LEFT: 107, 55, 52, 70, 105
# RIGHT: 336, 285, 282, 300, 334

eyebrow_config = {
    'left': {
        'base': [107, 55, 52, 70, 105],
        'label': 'LEFT EYEBROW'
    },
    'right': {
        'base': [336, 285, 282, 300, 334],
        'label': 'RIGHT EYEBROW'
    }
}

# Calcolo ALPHA/BETA per offset EXT come nel codice JS
ALPHA = 0.5  # metà distanza tra coppie
BETA = 0.5

for side_name, config in eyebrow_config.items():
    print(f"\n{'='*60}")
    print(f"PROCESSING: {config['label']}")
    print(f"{'='*60}")
    
    base_indices = config['base']
    base_points = [landmarks[i] for i in base_indices]
    
    # Visualizza landmarks base
    img_base = img.copy()
    for i, idx in enumerate(base_indices):
        x, y = landmarks[idx]
        cv2.circle(img_base, (x, y), 5, (255, 0, 0), -1)
        cv2.putText(img_base, f"LM{idx}", (x+5, y-5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
    
    # Crea poligono con punti base
    base_array = np.array(base_points, dtype=np.int32)
    cv2.polylines(img_base, [base_array], True, (255, 0, 0), 2)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_base)
    plt.title(f"FASE 2: Landmarks Base {config['label']}")
    plt.axis('off')
    plt.savefig(output_dir / f"02_{side_name}_base_landmarks.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 02_{side_name}_base_landmarks.png")
    
    # Calcola punti EXT con offset (come nel codice JS)
    # OFFSET: verso esterno, metà distanza tra coppie consecutive
    ext_points = []
    n = len(base_points)
    for i in range(n):
        curr = base_points[i]
        prev_idx = (i - 1) % n
        next_idx = (i + 1) % n
        prev_point = base_points[prev_idx]
        next_point = base_points[next_idx]
        
        # Vettore normale (outward)
        dx = next_point[0] - prev_point[0]
        dy = next_point[1] - prev_point[1]
        length = np.sqrt(dx*dx + dy*dy)
        if length > 0:
            # Normal (perpendicular outward)
            nx = -dy / length
            ny = dx / length
            
            # Offset ALPHA * distanza media
            offset_dist = ALPHA * length / 2
            ext_x = int(curr[0] + nx * offset_dist)
            ext_y = int(curr[1] + ny * offset_dist)
            ext_points.append((ext_x, ext_y))
        else:
            ext_points.append(curr)
    
    # Poligono allargato: base + ext
    expanded_polygon = base_points + ext_points
    
    # Visualizza poligono allargato
    img_expanded = img.copy()
    expanded_array = np.array(expanded_polygon, dtype=np.int32)
    cv2.polylines(img_expanded, [expanded_array], True, (255, 0, 0), 2)
    
    for i, (x, y) in enumerate(base_points):
        cv2.circle(img_expanded, (x, y), 5, (255, 0, 0), -1)
        cv2.putText(img_expanded, str(i), (x+5, y-5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
    
    for i, (x, y) in enumerate(ext_points):
        cv2.circle(img_expanded, (x, y), 5, (0, 255, 255), -1)
        cv2.putText(img_expanded, f"E{i}", (x+5, y-5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_expanded)
    plt.title(f"FASE 3: Poligono Allargato {config['label']} (5+5 EXT)\nROSSO=Base, CYAN=EXT")
    plt.axis('off')
    plt.savefig(output_dir / f"03_{side_name}_expanded_polygon.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 03_{side_name}_expanded_polygon.png")
    
    # CAMPIONAMENTO PATTERN 3x3
    # Sopracciglio: centro tra LM52-LM105 (left) o LM282-LM334 (right)
    # Pelle: centro tra LM107-LM107EXT (left) o LM336-LM336EXT (right)
    
    if side_name == 'left':
        lm52 = landmarks[52]
        lm105 = landmarks[105]
        lm107 = landmarks[107]
        lm107ext = ext_points[0]  # primo EXT point
    else:
        lm52 = landmarks[282]  # speculare di 52
        lm105 = landmarks[334]  # speculare di 105
        lm107 = landmarks[336]  # speculare di 107
        lm107ext = ext_points[0]
    
    cx_eyebrow = (lm52[0] + lm105[0]) / 2
    cy_eyebrow = (lm52[1] + lm105[1]) / 2
    
    cx_skin = (lm107[0] + lm107ext[0]) / 2
    cy_skin = (lm107[1] + lm107ext[1]) / 2
    
    eyebrow_sample = sample_pattern_3x3(img, cx_eyebrow, cy_eyebrow)
    skin_sample = sample_pattern_3x3(img, cx_skin, cy_skin)
    
    print(f"\n🔬 Campione SOPRACCIGLIO @ ({cx_eyebrow:.1f}, {cy_eyebrow:.1f}):")
    print(f"   Lum={eyebrow_sample['avgLum']:.1f}, RGB=({eyebrow_sample['avgR']:.0f},{eyebrow_sample['avgG']:.0f},{eyebrow_sample['avgB']:.0f})")
    
    print(f"🔬 Campione PELLE @ ({cx_skin:.1f}, {cy_skin:.1f}):")
    print(f"   Lum={skin_sample['avgLum']:.1f}, RGB=({skin_sample['avgR']:.0f},{skin_sample['avgG']:.0f},{skin_sample['avgB']:.0f})")
    
    img_samples = img.copy()
    cv2.polylines(img_samples, [expanded_array], True, (255, 0, 0), 2)
    cv2.circle(img_samples, (int(cx_eyebrow), int(cy_eyebrow)), 8, (255, 0, 0), -1)
    cv2.circle(img_samples, (int(cx_skin), int(cy_skin)), 8, (0, 255, 0), -1)
    cv2.rectangle(img_samples, 
                  (int(cx_eyebrow)-8, int(cy_eyebrow)-8),
                  (int(cx_eyebrow)+8, int(cy_eyebrow)+8),
                  (255, 0, 0), 2)
    cv2.rectangle(img_samples,
                  (int(cx_skin)-8, int(cy_skin)-8),
                  (int(cx_skin)+8, int(cy_skin)+8),
                  (0, 255, 0), 2)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_samples)
    plt.title(f"FASE 4: Campionamento Pattern 3x3 {config['label']}\nROSSO=Sopracciglio, VERDE=Pelle")
    plt.axis('off')
    plt.savefig(output_dir / f"04_{side_name}_samples.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 04_{side_name}_samples.png")
    
    # BINARIZZAZIONE
    print(f"\n🔍 Binarizzazione (solo pixel dentro poligono)...")
    
    xs = [p[0] for p in expanded_polygon]
    ys = [p[1] for p in expanded_polygon]
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
            
            if point_in_polygon((x, y), expanded_polygon):
                pixels_inside += 1
                r, g, b = img[y, x]
                
                eyebrow_sim = calculate_similarity(r, g, b, eyebrow_sample)
                skin_sim = calculate_similarity(r, g, b, skin_sample)
                
                # NESSUN BIAS (come nel codice attuale)
                if eyebrow_sim > skin_sim:
                    binary_mask[y, x] = 1
                    pixels_eyebrow += 1
    
    print(f"   Pixel controllati: {pixels_checked}")
    print(f"   Pixel dentro poligono: {pixels_inside}")
    print(f"   Pixel classificati come sopracciglio: {pixels_eyebrow}")
    if pixels_inside > 0:
        print(f"   Percentuale sopracciglio: {(pixels_eyebrow/pixels_inside*100):.1f}%")
    
    # Visualizza maschera binaria full size
    plt.figure(figsize=(12, 16))
    plt.imshow(binary_mask, cmap='gray')
    plt.title(f"FASE 5: Maschera Binaria {config['label']}\nBIANCO=Sopracciglio, NERO=Pelle")
    plt.axis('off')
    plt.savefig(output_dir / f"05_{side_name}_binary_raw.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 05_{side_name}_binary_raw.png")
    
    # Overlay maschera su immagine
    img_overlay = img.copy()
    mask_colored = np.zeros_like(img)
    mask_colored[binary_mask == 1] = [255, 0, 0]  # Rosso
    img_overlay = cv2.addWeighted(img_overlay, 0.7, mask_colored, 0.3, 0)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_overlay)
    plt.title(f"FASE 5b: Overlay Maschera Binaria {config['label']}")
    plt.axis('off')
    plt.savefig(output_dir / f"05b_{side_name}_binary_overlay.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 05b_{side_name}_binary_overlay.png")
    
    # MORFOLOGIA
    print(f"\n🔧 Morfologia: Remove small components...")
    cleaned_mask = remove_small_components(binary_mask, min_size=50)
    cleaned_pixels = np.sum(cleaned_mask)
    print(f"   Pixel dopo pulizia: {cleaned_pixels}")
    
    plt.figure(figsize=(12, 16))
    plt.imshow(cleaned_mask, cmap='gray')
    plt.title(f"FASE 6: Dopo Remove Small Components {config['label']}")
    plt.axis('off')
    plt.savefig(output_dir / f"06_{side_name}_cleaned.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 06_{side_name}_cleaned.png")
    
    print(f"\n🔧 Morfologia: Keep largest component...")
    largest_mask = keep_largest_component(cleaned_mask)
    largest_pixels = np.sum(largest_mask)
    print(f"   Pixel componente più grande: {largest_pixels}")
    
    plt.figure(figsize=(12, 16))
    plt.imshow(largest_mask, cmap='gray')
    plt.title(f"FASE 7: Solo Componente Più Grande {config['label']}")
    plt.axis('off')
    plt.savefig(output_dir / f"07_{side_name}_largest.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 07_{side_name}_largest.png")
    
    # TRACE CONTOUR
    print(f"\n📐 Tracciamento contorno (Moore-Neighbor)...")
    contour = trace_moore_neighbor_contour(largest_mask)
    print(f"   Punti contorno: {len(contour)}")
    
    if len(contour) > 0:
        img_contour = img.copy()
        contour_array = np.array(contour, dtype=np.int32)
        cv2.polylines(img_contour, [contour_array], True, (255, 0, 255), 3)
        
        plt.figure(figsize=(12, 16))
        plt.imshow(img_contour)
        plt.title(f"FASE 8: Contorno Tracciato {config['label']} ({len(contour)} punti)")
        plt.axis('off')
        plt.savefig(output_dir / f"08_{side_name}_contour_raw.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Salvata: 08_{side_name}_contour_raw.png")
        
        # SMOOTH
        if len(contour) > 3:
            print(f"\n🔄 Smoothing contorno (window=3)...")
            smoothed = smooth_contour(contour, window=3)
            
            simplification_factor = max(1, len(smoothed) // 200)
            simplified = smoothed[::simplification_factor]
            print(f"   Contorno smoothato: {len(smoothed)} punti")
            print(f"   Contorno semplificato: {len(simplified)} punti (factor={simplification_factor})")
            
            img_final = img.copy()
            simplified_array = np.array(simplified, dtype=np.int32)
            cv2.polylines(img_final, [simplified_array], True, (0, 255, 0), 3)
            cv2.fillPoly(img_final, [simplified_array], (255, 255, 0), lineType=cv2.LINE_AA)
            img_final = cv2.addWeighted(img, 0.7, img_final, 0.3, 0)
            
            plt.figure(figsize=(12, 16))
            plt.imshow(img_final)
            plt.title(f"FASE 9: Contorno FINALE {config['label']}\n({len(simplified)} punti)")
            plt.axis('off')
            plt.savefig(output_dir / f"09_{side_name}_contour_final.png", dpi=150, bbox_inches='tight')
            plt.close()
            print(f"✅ Salvata: 09_{side_name}_contour_final.png")
            
            # CONFRONTO CRITICO
            img_comparison = img.copy()
            cv2.polylines(img_comparison, [expanded_array], True, (255, 0, 0), 3)  # ROSSO = poligono
            cv2.polylines(img_comparison, [simplified_array], True, (0, 255, 0), 3)  # VERDE = contorno
            
            plt.figure(figsize=(12, 16))
            plt.imshow(img_comparison)
            plt.title(f"⚠️ CONFRONTO CRITICO {config['label']} ⚠️\nROSSO=Poligono Landmarks | VERDE=Contorno Binarizzato\nSe coincidono → BUG!")
            plt.axis('off')
            plt.savefig(output_dir / f"10_{side_name}_CONFRONTO_CRITICO.png", dpi=150, bbox_inches='tight')
            plt.close()
            print(f"✅ Salvata: 10_{side_name}_CONFRONTO_CRITICO.png")

print("\n" + "=" * 80)
print(f"✅ ANALISI REALE COMPLETATA!")
print(f"📂 Tutte le immagini salvate in: {output_dir}/")
print("=" * 80)
print("\n🔍 VERIFICA CRITICA:")
print("   Controlla le immagini: 10_*_CONFRONTO_CRITICO.png")
print("")
print("   Se VERDE (contorno) è DIVERSO da ROSSO (poligono):")
print("   → ✅ CORRETTO: Il contorno segue la binarizzazione reale")
print("")
print("   Se VERDE coincide esattamente con ROSSO:")
print("   → ❌ BUG: Il contorno ignora la binarizzazione e segue i landmarks")
