"""
Replica ESATTA del flusso JavaScript della webapp per processare IMG_4675.JPEG
Segue passo-passo il codice reale di measurements.js
"""
import cv2
import numpy as np
import mediapipe as mp
import matplotlib.pyplot as plt
from pathlib import Path

def calculate_distance(p1, p2):
    """Calcola distanza euclidea tra due punti"""
    return np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def point_in_polygon(point, polygon):
    """Ray casting algorithm - ESATTO come nel JS"""
    x, y = point
    inside = False
    n = len(polygon)
    
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
    """Campiona pattern 3x3 - ESATTO come nel JS"""
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
    """Calcola similarità - ESATTO come nel JS (70% lum + 30% color)"""
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
print("REPLICA ESATTA DEL FLUSSO WEBAPP - IMG_4675.JPEG")
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
output_dir = Path("debug_exact_webapp_IMG_4675")
output_dir.mkdir(exist_ok=True)

# FASE 0: Originale
plt.figure(figsize=(12, 16))
plt.imshow(img)
plt.title("FASE 0: Immagine Originale", fontsize=14, fontweight='bold')
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

# GENERA MASCHERE ESPANSE - ESATTAMENTE COME NEL JS

# LEFT EYEBROW
print(f"\n{'='*60}")
print("GENERATING LEFT EYEBROW EXPANDED MASK")
print(f"{'='*60}")

lm107 = landmarks[107]
lm55 = landmarks[55]
lm52 = landmarks[52]
lm70 = landmarks[70]
lm105 = landmarks[105]

# Calcola ALPHA = metà distanza tra 107 e 55
distance_107_55 = calculate_distance(lm107, lm55)
ALPHA = distance_107_55 / 2

print(f"📐 SOPRACCIGLIO SINISTRO - ALPHA: {ALPHA:.2f}px")

# Genera i 5 punti EXT con offset ESATTI dal JS
lm107EXT = {
    'name': '107EXT',
    'x': lm107[0] + ALPHA,
    'y': lm107[1] - ALPHA
}
print(f"  ✓ 107EXT: origine({lm107[0]:.1f}, {lm107[1]:.1f}) + offset(+{ALPHA:.1f}, -{ALPHA:.1f}) = ({lm107EXT['x']:.1f}, {lm107EXT['y']:.1f})")

lm55EXT = {
    'name': '55EXT',
    'x': lm55[0] + ALPHA,
    'y': lm55[1] + ALPHA
}
print(f"  ✓ 55EXT: origine({lm55[0]:.1f}, {lm55[1]:.1f}) + offset(+{ALPHA:.1f}, +{ALPHA:.1f}) = ({lm55EXT['x']:.1f}, {lm55EXT['y']:.1f})")

lm52EXT = {
    'name': '52EXT',
    'x': lm52[0],
    'y': lm52[1] + ALPHA
}
print(f"  ✓ 52EXT: origine({lm52[0]:.1f}, {lm52[1]:.1f}) + offset(0, +{ALPHA:.1f}) = ({lm52EXT['x']:.1f}, {lm52EXT['y']:.1f})")

lm70EXT = {
    'name': '70EXT',
    'x': lm70[0] - ALPHA,
    'y': lm70[1] + ALPHA
}
print(f"  ✓ 70EXT: origine({lm70[0]:.1f}, {lm70[1]:.1f}) + offset(-{ALPHA:.1f}, +{ALPHA:.1f}) = ({lm70EXT['x']:.1f}, {lm70EXT['y']:.1f})")

lm105EXT = {
    'name': '105EXT',
    'x': lm105[0] - ALPHA,
    'y': lm105[1] - ALPHA
}
print(f"  ✓ 105EXT: origine({lm105[0]:.1f}, {lm105[1]:.1f}) + offset(-{ALPHA:.1f}, -{ALPHA:.1f}) = ({lm105EXT['x']:.1f}, {lm105EXT['y']:.1f})")

leftExpandedMask = [lm107EXT, lm55EXT, lm52EXT, lm70EXT, lm105EXT]

# RIGHT EYEBROW
print(f"\n{'='*60}")
print("GENERATING RIGHT EYEBROW EXPANDED MASK")
print(f"{'='*60}")

lm336 = landmarks[336]
lm285 = landmarks[285]
lm282 = landmarks[282]
lm300 = landmarks[300]
lm334 = landmarks[334]

# Calcola BETA = metà distanza tra 336 e 285
distance_336_285 = calculate_distance(lm336, lm285)
BETA = distance_336_285 / 2

print(f"📐 SOPRACCIGLIO DESTRO - BETA: {BETA:.2f}px")

# Genera i 5 punti EXT con offset ESATTI dal JS (speculari)
lm336EXT = {
    'name': '336EXT',
    'x': lm336[0] - BETA,
    'y': lm336[1] - BETA
}
print(f"  ✓ 336EXT: origine({lm336[0]:.1f}, {lm336[1]:.1f}) + offset(-{BETA:.1f}, -{BETA:.1f}) = ({lm336EXT['x']:.1f}, {lm336EXT['y']:.1f})")

lm285EXT = {
    'name': '285EXT',
    'x': lm285[0] - BETA,
    'y': lm285[1] + BETA
}
print(f"  ✓ 285EXT: origine({lm285[0]:.1f}, {lm285[1]:.1f}) + offset(-{BETA:.1f}, +{BETA:.1f}) = ({lm285EXT['x']:.1f}, {lm285EXT['y']:.1f})")

lm282EXT = {
    'name': '282EXT',
    'x': lm282[0],
    'y': lm282[1] + BETA
}
print(f"  ✓ 282EXT: origine({lm282[0]:.1f}, {lm282[1]:.1f}) + offset(0, +{BETA:.1f}) = ({lm282EXT['x']:.1f}, {lm282EXT['y']:.1f})")

lm300EXT = {
    'name': '300EXT',
    'x': lm300[0] + BETA,
    'y': lm300[1] + BETA
}
print(f"  ✓ 300EXT: origine({lm300[0]:.1f}, {lm300[1]:.1f}) + offset(+{BETA:.1f}, +{BETA:.1f}) = ({lm300EXT['x']:.1f}, {lm300EXT['y']:.1f})")

lm334EXT = {
    'name': '334EXT',
    'x': lm334[0] + BETA,
    'y': lm334[1] - BETA
}
print(f"  ✓ 334EXT: origine({lm334[0]:.1f}, {lm334[1]:.1f}) + offset(+{BETA:.1f}, -{BETA:.1f}) = ({lm334EXT['x']:.1f}, {lm334EXT['y']:.1f})")

rightExpandedMask = [lm336EXT, lm285EXT, lm282EXT, lm300EXT, lm334EXT]

# PROCESSA ENTRAMBI I SOPRACCIGLIA
eyebrow_configs = [
    {
        'side': 'left',
        'label': 'LEFT EYEBROW',
        'mask': leftExpandedMask,
        'lm52': lm52,
        'lm105': lm105,
        'lm107': lm107,
        'lm107ext': (lm107EXT['x'], lm107EXT['y'])
    },
    {
        'side': 'right',
        'label': 'RIGHT EYEBROW',
        'mask': rightExpandedMask,
        'lm52': lm282,  # Speculare di 52
        'lm105': lm334,  # Speculare di 105
        'lm107': lm336,  # Speculare di 107
        'lm107ext': (lm336EXT['x'], lm336EXT['y'])
    }
]

for config in eyebrow_configs:
    print(f"\n{'='*80}")
    print(f"PROCESSING: {config['label']}")
    print(f"{'='*80}")
    
    side = config['side']
    maskPolygon = config['mask']
    
    # Converti polygon in formato (x, y)
    polygon_points = [(int(p['x']), int(p['y'])) for p in maskPolygon]
    
    # Visualizza maschera espansa (5 punti EXT)
    img_mask = img.copy()
    polygon_array = np.array(polygon_points, dtype=np.int32)
    cv2.polylines(img_mask, [polygon_array], True, (0, 255, 0), 3)
    
    for i, (x, y) in enumerate(polygon_points):
        cv2.circle(img_mask, (x, y), 8, (255, 0, 0), -1)
        cv2.putText(img_mask, maskPolygon[i]['name'], (x+10, y-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_mask)
    plt.title(f"FASE 1: Maschera Espansa {config['label']} (5 punti EXT)", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"01_{side}_expanded_mask.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 01_{side}_expanded_mask.png")
    
    # CAMPIONAMENTO PATTERN 3x3 - ESATTAMENTE COME NEL JS
    cx_eyebrow = (config['lm52'][0] + config['lm105'][0]) / 2
    cy_eyebrow = (config['lm52'][1] + config['lm105'][1]) / 2
    
    cx_skin = (config['lm107'][0] + config['lm107ext'][0]) / 2
    cy_skin = (config['lm107'][1] + config['lm107ext'][1]) / 2
    
    eyebrow_sample = sample_pattern_3x3(img, cx_eyebrow, cy_eyebrow)
    skin_sample = sample_pattern_3x3(img, cx_skin, cy_skin)
    
    print(f"\n🔬 Campione SOPRACCIGLIO @ ({cx_eyebrow:.1f}, {cy_eyebrow:.1f}):")
    print(f"   Lum={eyebrow_sample['avgLum']:.1f}, RGB=({eyebrow_sample['avgR']:.0f},{eyebrow_sample['avgG']:.0f},{eyebrow_sample['avgB']:.0f})")
    
    print(f"🔬 Campione PELLE @ ({cx_skin:.1f}, {cy_skin:.1f}):")
    print(f"   Lum={skin_sample['avgLum']:.1f}, RGB=({skin_sample['avgR']:.0f},{skin_sample['avgG']:.0f},{skin_sample['avgB']:.0f})")
    
    # Visualizza campioni
    img_samples = img.copy()
    cv2.polylines(img_samples, [polygon_array], True, (0, 255, 0), 2)
    cv2.circle(img_samples, (int(cx_eyebrow), int(cy_eyebrow)), 10, (255, 0, 0), -1)
    cv2.circle(img_samples, (int(cx_skin), int(cy_skin)), 10, (0, 255, 0), -1)
    cv2.rectangle(img_samples,
                  (int(cx_eyebrow)-10, int(cy_eyebrow)-10),
                  (int(cx_eyebrow)+10, int(cy_eyebrow)+10),
                  (255, 0, 0), 3)
    cv2.rectangle(img_samples,
                  (int(cx_skin)-10, int(cy_skin)-10),
                  (int(cx_skin)+10, int(cy_skin)+10),
                  (0, 255, 0), 3)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_samples)
    plt.title(f"FASE 2: Campionamento Pattern 3x3 {config['label']}\nROSSO=Sopracciglio, VERDE=Pelle", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"02_{side}_samples.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 02_{side}_samples.png")
    
    # ESTRAI LA PORZIONE ORIGINALE CHE VIENE PROCESSATA
    # Nel codice JS viene passata l'IMMAGINE COMPLETA, ma mostriamo solo l'area rilevante
    xs = [p[0] for p in polygon_points]
    ys = [p[1] for p in polygon_points]
    min_x = max(0, int(min(xs)))
    max_x = min(w - 1, int(max(xs)))
    min_y = max(0, int(min(ys)))
    max_y = min(h - 1, int(max(ys)))
    
    # IMMAGINE 1: Porzione originale (senza overlay) - QUESTO È CIÒ CHE VIENE LETTO
    img_original_crop = img[min_y:max_y+1, min_x:max_x+1].copy()
    
    plt.figure(figsize=(12, 8))
    plt.imshow(img_original_crop)
    plt.title(f"PIXEL ORIGINALI NELL'AREA {config['label']}\n(Questi sono i pixel RGB reali che vengono letti dalla funzione)", fontsize=12, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"02b_{side}_original_pixels_area.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 02b_{side}_original_pixels_area.png - PIXEL RGB ORIGINALI dell'area")
    
    # IMMAGINE 2: Mostra quali pixel DENTRO il poligono verranno analizzati
    img_polygon_only = img.copy()
    
    # Crea maschera: nero tutto, tranne area poligono
    mask_polygon = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask_polygon, [polygon_array], 1)
    
    # Applica maschera: nero fuori poligono, originale dentro
    img_polygon_only[mask_polygon == 0] = 0
    
    # Crop all'area
    img_polygon_crop = img_polygon_only[min_y:max_y+1, min_x:max_x+1].copy()
    
    plt.figure(figsize=(12, 8))
    plt.imshow(img_polygon_crop)
    plt.title(f"PIXEL DENTRO IL POLIGONO {config['label']}\n(NERO=fuori poligono, ORIGINALE=dentro poligono - questi vengono binarizzati)", fontsize=12, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"02c_{side}_pixels_inside_polygon.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 02c_{side}_pixels_inside_polygon.png - SOLO pixel dentro poligono")
    
    # FASE 2D: APPLICA CONTRASTO AI PIXEL DENTRO IL POLIGONO
    print(f"\n🎨 Applicazione contrasto ai pixel del poligono...")
    
    # Fattore di contrasto (1.0 = nessun cambio, 2.0 = contrasto doppio)
    contrast_factor = 2.0
    
    # Crea una copia dell'immagine per applicare il contrasto
    img_contrasted = img.copy()
    
    # Per ogni pixel dentro il poligono, aumenta il contrasto
    for y in range(h):
        for x in range(w):
            if mask_polygon[y, x] == 1:  # Solo pixel dentro poligono
                # Pixel originale
                r, g, b = img[y, x]
                
                # Converti in float per calcoli
                r_f = r / 255.0
                g_f = g / 255.0
                b_f = b / 255.0
                
                # Applica contrasto: new = (old - 0.5) * factor + 0.5
                r_new = ((r_f - 0.5) * contrast_factor + 0.5) * 255
                g_new = ((g_f - 0.5) * contrast_factor + 0.5) * 255
                b_new = ((b_f - 0.5) * contrast_factor + 0.5) * 255
                
                # Clamp ai valori 0-255
                r_new = max(0, min(255, r_new))
                g_new = max(0, min(255, g_new))
                b_new = max(0, min(255, b_new))
                
                img_contrasted[y, x] = [r_new, g_new, b_new]
    
    # Visualizza risultato contrasto
    img_contrasted_crop = img_contrasted[min_y:max_y+1, min_x:max_x+1].copy()
    
    # Mostra solo area poligono con contrasto
    img_contrasted_polygon = img_contrasted.copy()
    img_contrasted_polygon[mask_polygon == 0] = 0
    img_contrasted_polygon_crop = img_contrasted_polygon[min_y:max_y+1, min_x:max_x+1].copy()
    
    plt.figure(figsize=(12, 8))
    plt.imshow(img_contrasted_polygon_crop)
    plt.title(f"PIXEL CON CONTRASTO x{contrast_factor} {config['label']}\n(Questi pixel verranno usati per la binarizzazione)", fontsize=12, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"02d_{side}_pixels_contrasted.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 02d_{side}_pixels_contrasted.png - Pixel con contrasto aumentato (factor={contrast_factor})")
    
    # USA L'IMMAGINE CON CONTRASTO PER LA BINARIZZAZIONE
    img_for_binarization = img_contrasted
    
    # BINARIZZAZIONE CON SOGLIA FISSA
    print(f"\n🔍 Binarizzazione con soglia fissa (threshold=160)...")
    
    print(f"🔍 Area ricerca ottimizzata: x[{min_x}-{max_x}] y[{min_y}-{max_y}]")
    
    binary_mask = np.zeros((h, w), dtype=np.uint8)
    
    pixels_checked = 0
    pixels_inside = 0
    pixels_eyebrow = 0
    
    # SOGLIA FISSA DI LUMINOSITÀ
    threshold = 160
    
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            pixels_checked += 1
            
            if point_in_polygon((x, y), polygon_points):
                pixels_inside += 1
                r, g, b = img_for_binarization[y, x]  # USA PIXEL CON CONTRASTO
                
                # Calcola luminosità
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                
                # SOGLIA FISSA: se luminosità < threshold → pixel sopracciglio (scuro)
                if lum < threshold:
                    binary_mask[y, x] = 1
                    pixels_eyebrow += 1
    
    print(f"   Pixel controllati: {pixels_checked}")
    print(f"   Pixel dentro poligono: {pixels_inside}")
    print(f"   Pixel classificati come sopracciglio: {pixels_eyebrow}")
    if pixels_inside > 0:
        print(f"   Percentuale sopracciglio: {(pixels_eyebrow/pixels_inside*100):.1f}%")
    
    # Visualizza maschera binaria
    plt.figure(figsize=(12, 16))
    plt.imshow(binary_mask, cmap='gray')
    plt.title(f"FASE 3: Maschera Binaria {config['label']}\nBIANCO=Sopracciglio ({pixels_eyebrow} px), NERO=Pelle", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"03_{side}_binary_raw.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 03_{side}_binary_raw.png")
    
    # TRASFORMAZIONI MORFOLOGICHE
    print(f"\n🔧 Morfologia: Espansione (5 iterazioni)...")
    for i in range(5):
        dilated = np.zeros_like(binary_mask)
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if binary_mask[y, x] == 1 or \
                   binary_mask[y-1, x] == 1 or binary_mask[y+1, x] == 1 or \
                   binary_mask[y, x-1] == 1 or binary_mask[y, x+1] == 1 or \
                   binary_mask[y-1, x-1] == 1 or binary_mask[y-1, x+1] == 1 or \
                   binary_mask[y+1, x-1] == 1 or binary_mask[y+1, x+1] == 1:
                    dilated[y, x] = 1
        binary_mask = dilated
        pixel_count = np.sum(binary_mask)
        print(f"   Dopo espansione {i+1}: {pixel_count} pixel")
    
    plt.figure(figsize=(12, 16))
    plt.imshow(binary_mask, cmap='gray')
    plt.title(f"FASE 3c: Dopo Espansione (5x) {config['label']}", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"03c_{side}_after_dilation.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 03c_{side}_after_dilation.png")
    
    print(f"\n🔧 Morfologia: Erosione (2 iterazioni)...")
    for i in range(2):
        eroded = np.zeros_like(binary_mask)
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if binary_mask[y, x] == 1 and \
                   binary_mask[y-1, x] == 1 and binary_mask[y+1, x] == 1 and \
                   binary_mask[y, x-1] == 1 and binary_mask[y, x+1] == 1 and \
                   binary_mask[y-1, x-1] == 1 and binary_mask[y-1, x+1] == 1 and \
                   binary_mask[y+1, x-1] == 1 and binary_mask[y+1, x+1] == 1:
                    eroded[y, x] = 1
        binary_mask = eroded
        pixel_count = np.sum(binary_mask)
        print(f"   Dopo erosione {i+1}: {pixel_count} pixel")
    
    plt.figure(figsize=(12, 16))
    plt.imshow(binary_mask, cmap='gray')
    plt.title(f"FASE 3d: Dopo Erosione (2x) {config['label']}", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"03d_{side}_after_erosion.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 03d_{side}_after_erosion.png")
    
    # MORFOLOGIA
    print(f"\n🔧 Morfologia: Remove small components...")
    cleaned_mask = remove_small_components(binary_mask, min_size=50)
    cleaned_pixels = np.sum(cleaned_mask)
    print(f"   Pixel dopo pulizia: {cleaned_pixels}")
    
    print(f"\n🔧 Morfologia: Keep largest component...")
    largest_mask = keep_largest_component(cleaned_mask)
    largest_pixels = np.sum(largest_mask)
    print(f"   Pixel componente più grande: {largest_pixels}")
    
    plt.figure(figsize=(12, 16))
    plt.imshow(largest_mask, cmap='gray')
    plt.title(f"FASE 4: Dopo Morfologia {config['label']}\n({largest_pixels} pixel)", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"04_{side}_morphology.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 04_{side}_morphology.png")
    
    # Overlay dopo morfologia
    img_overlay = img.copy()
    mask_colored = np.zeros_like(img)
    mask_colored[largest_mask == 1] = [0, 255, 0]
    img_overlay = cv2.addWeighted(img_overlay, 0.7, mask_colored, 0.3, 0)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_overlay)
    plt.title(f"FASE 4b: Overlay Area Finale {config['label']}", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"04b_{side}_final_overlay.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: 04b_{side}_final_overlay.png")
    
    # TRACE CONTOUR SEMPLIFICATO
    print(f"\n📐 Tracciamento contorno...")
    contour = trace_moore_neighbor_contour(largest_mask)
    print(f"   Punti contorno: {len(contour)}")
    
    if len(contour) > 0:
        # Semplificazione più aggressiva
        simplification_factor = max(2, len(contour) // 100)
        simplified = contour[::simplification_factor]
        print(f"   Contorno semplificato: {len(simplified)} punti")
        
        # Visualizza contorno finale
        img_final = img.copy()
        simplified_array = np.array(simplified, dtype=np.int32)
        cv2.polylines(img_final, [simplified_array], True, (0, 255, 0), 4)
        cv2.fillPoly(img_final, [simplified_array], (255, 255, 0), lineType=cv2.LINE_AA)
        img_final = cv2.addWeighted(img, 0.7, img_final, 0.3, 0)
        
        plt.figure(figsize=(12, 16))
        plt.imshow(img_final)
        plt.title(f"FASE 5: Contorno FINALE {config['label']}\n({len(simplified)} punti)", fontsize=14, fontweight='bold')
        plt.axis('off')
        plt.savefig(output_dir / f"05_{side}_contour_final.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Salvata: 05_{side}_contour_final.png")
        
        # CONFRONTO CRITICO: Maschera EXT vs Contorno Binarizzato
        img_comparison = img.copy()
        cv2.polylines(img_comparison, [polygon_array], True, (255, 0, 0), 4)  # ROSSO = maschera 5 punti EXT
        cv2.polylines(img_comparison, [simplified_array], True, (0, 255, 0), 4)  # VERDE = contorno binarizzato
        
        plt.figure(figsize=(12, 16))
        plt.imshow(img_comparison)
        plt.title(f"⚠️ CONFRONTO CRITICO {config['label']} ⚠️\nROSSO=Maschera 5 punti EXT | VERDE=Contorno Binarizzato\nSe coincidono esattamente → Il contorno NON segue la binarizzazione!", fontsize=12, fontweight='bold')
        plt.axis('off')
        plt.savefig(output_dir / f"06_{side}_CONFRONTO_CRITICO.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Salvata: 06_{side}_CONFRONTO_CRITICO.png")

print("\n" + "=" * 80)
print(f"✅ ANALISI ESATTA COMPLETATA!")
print(f"📂 Tutte le immagini salvate in: {output_dir}/")
print("=" * 80)
print("\n🔍 VERIFICA CRITICA:")
print("   Controlla: 06_*_CONFRONTO_CRITICO.png")
print("")
print("   Se VERDE (contorno) è DIVERSO da ROSSO (maschera 5 EXT):")
print("   → ✅ CORRETTO: Il contorno segue la binarizzazione reale dei pixel")
print("")
print("   Se VERDE coincide con ROSSO:")
print("   → ❌ BUG: Il contorno ignora i pixel e segue la maschera EXT")
