"""
FLUSSO ALTERNATIVO: Magic Wand per Aree Sopracciglio
Parte dalla fase 02c_right_pixels_inside_polygon.png e applica la bacchetta magica
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
    """Ray casting algorithm"""
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

def sample_color_2x2(img, cx, cy):
    """Campiona colore da pattern 2x2"""
    h, w = img.shape[:2]
    total_r, total_g, total_b = 0, 0, 0
    count = 0
    
    for dy in range(2):
        for dx in range(2):
            px = int(cx + dx)
            py = int(cy + dy)
            
            if 0 <= px < w and 0 <= py < h:
                b, g, r = img[py, px]
                total_r += r
                total_g += g
                total_b += b
                count += 1
    
    if count == 0:
        return None
    
    return (int(total_b / count), int(total_g / count), int(total_r / count))

def magic_wand_selection_color_distance(img, mask_polygon, seed_point, tolerance=30):
    """
    Applica selezione basata su distanza colore dal seed (non flood fill)
    SOLO sui pixel dentro il poligono
    
    Args:
        img: Immagine BGR
        mask_polygon: Array numpy di punti del poligono [(x,y), ...]
        seed_point: Punto (x, y) per il colore seed
        tolerance: Tolleranza di selezione (differenza colore massima)
    
    Returns:
        background_mask: Maschera binaria dello sfondo selezionato
    """
    h, w = img.shape[:2]
    
    # Crea maschera del poligono
    polygon_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(polygon_mask, [mask_polygon], 1)
    
    # Ottieni colore seed (BGR)
    seed_color = img[int(seed_point[1]), int(seed_point[0])].astype(np.float32)
    print(f"   🎨 Colore seed @ ({seed_point[0]:.1f}, {seed_point[1]:.1f}): BGR=({seed_color[0]:.0f}, {seed_color[1]:.0f}, {seed_color[2]:.0f})")
    
    # Crea maschera basata sulla distanza euclidea dal colore seed
    background_mask = np.zeros((h, w), dtype=np.uint8)
    
    # Calcola distanza colore per ogni pixel dentro il poligono
    for y in range(h):
        for x in range(w):
            if polygon_mask[y, x] == 1:
                pixel_color = img[y, x].astype(np.float32)
                
                # Distanza euclidea nel spazio RGB
                diff = pixel_color - seed_color
                distance = np.sqrt(np.sum(diff ** 2))
                
                # Se la distanza è sotto la tolleranza, è parte dello sfondo
                if distance <= tolerance:
                    background_mask[y, x] = 1
    
    print(f"   ✓ Pixel selezionati (distanza <= {tolerance}): {np.sum(background_mask)}")
    
    return background_mask

def get_largest_central_component(mask, center_point):
    """
    Trova il componente più grande che contiene il punto centrale
    Se nessun componente contiene il centro, prende il più vicino
    """
    mask_uint8 = (mask * 255).astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_uint8, connectivity=8)
    
    if num_labels <= 1:
        return mask
    
    cx, cy = int(center_point[0]), int(center_point[1])
    h, w = mask.shape
    
    # Cerca il componente che contiene il punto centrale
    if 0 <= cy < h and 0 <= cx < w:
        center_label = labels[cy, cx]
        if center_label > 0:
            result = np.zeros_like(mask)
            result[labels == center_label] = 1
            print(f"   ✓ Componente centrale trovato: {np.sum(result)} pixel")
            return result
    
    # Se il punto centrale non è in nessun componente, trova il più vicino
    min_dist = float('inf')
    closest_label = 1
    
    for i in range(1, num_labels):
        centroid = centroids[i]
        dist = np.sqrt((centroid[0] - cx)**2 + (centroid[1] - cy)**2)
        if dist < min_dist:
            min_dist = dist
            closest_label = i
    
    result = np.zeros_like(mask)
    result[labels == closest_label] = 1
    print(f"   ✓ Componente più vicino al centro: {np.sum(result)} pixel (distanza: {min_dist:.1f}px)")
    return result

def trace_moore_neighbor_contour(binary_mask):
    """Traccia il contorno usando algoritmo Moore-Neighbor"""
    contours, _ = cv2.findContours(
        (binary_mask * 255).astype(np.uint8),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_NONE
    )
    
    if len(contours) == 0:
        return []
    
    # Prendi il contorno più lungo
    largest_contour = max(contours, key=cv2.contourArea)
    return largest_contour.squeeze().tolist()

# ============================================================================
# MAIN EXECUTION
# ============================================================================


def process_eyebrow_magic_wand(img, img_bgr, landmarks, config, output_dir, h, w):
    """Processa un sopracciglio con il metodo Magic Wand"""
    
    side = config['side']
    lm_indices = config['lm_base']
    offsets = config['offsets']
    
    print(f"\n{'='*80}")
    print(f"PROCESSING: {config['label']} - MAGIC WAND FLOW")
    print(f"{'='*80}")
    
    # Ottieni landmarks base
    lm_points = [landmarks[i] for i in lm_indices]
    
    # Calcola BETA
    distance = calculate_distance(lm_points[0], lm_points[1])
    BETA = distance / 2
    print(f"📐 BETA: {BETA:.2f}px")
    
    # Genera punti EXT (primi 5 punti)
    expandedMask = []
    for i, (lm, (ox, oy)) in enumerate(zip(lm_points, offsets)):
        ext_point = {
            'name': f'{lm_indices[i]}EXT',
            'x': lm[0] + (ox * BETA),
            'y': lm[1] + (oy * BETA)
        }
        expandedMask.append(ext_point)
    
    # Aggiungi il 6° punto calcolato dal punto con indice extra_vertex_idx
    extra_vertex_idx = config['extra_vertex_idx']
    extra_offset = config['extra_offset']
    base_point = expandedMask[extra_vertex_idx]
    
    extra_point = {
        'name': f"{lm_indices[extra_vertex_idx]}EXT2",
        'x': base_point['x'] + (extra_offset[0] * BETA),
        'y': base_point['y'] + (extra_offset[1] * BETA)
    }
    
    # Inserisci il 6° punto nella posizione corretta
    insert_position = config['insert_position']
    expandedMask.insert(insert_position, extra_point)
    
    polygon_points = [(int(p['x']), int(p['y'])) for p in expandedMask]
    polygon_array = np.array(polygon_points, dtype=np.int32)
    
    print(f"   ✓ Poligono a {len(expandedMask)} vertici:")
    for i, p in enumerate(expandedMask):
        print(f"      {i+1}. {p['name']}: ({p['x']:.1f}, {p['y']:.1f})")
    
    # Seed point
    seed_x = (lm_points[0][0] + expandedMask[0]['x']) / 2
    seed_y = (lm_points[0][1] + expandedMask[0]['y']) / 2
    
    seed_color = sample_color_2x2(img, seed_x - 1, seed_y - 1)
    if seed_color is None:
        print(f"⚠️  Skip {side}")
        return None
    
    print(f"🎨 Seed BGR=({seed_color[0]}, {seed_color[1]}, {seed_color[2]})")
    
    # Magic Wand - usa la tolleranza dalla configurazione
    tolerance = config.get('tolerance', 90)  # Default 50 se non specificato
    print(f"⚙️  Tolleranza: {tolerance}")
    background_mask = magic_wand_selection_color_distance(
        img_bgr, polygon_array, (seed_x, seed_y), tolerance
    )
    
    # Inversione
    polygon_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(polygon_mask, [polygon_array], 1)
    
    eyebrow_mask = polygon_mask.copy()
    eyebrow_mask[background_mask == 1] = 0
    
    pixels_eyebrow = np.sum(eyebrow_mask)
    pixels_total = np.sum(polygon_mask)
    percentage = (pixels_eyebrow / pixels_total * 100) if pixels_total > 0 else 0
    
    print(f"   ✓ Sopracciglio: {pixels_eyebrow} px ({percentage:.1f}%)")
    
    # Salva maschera sopracciglio (DEBUG)
    plt.figure(figsize=(12, 16))
    plt.imshow(eyebrow_mask, cmap='gray')
    plt.title(f"DEBUG: Maschera Sopracciglio {config['label']}\n{pixels_eyebrow} px ({percentage:.1f}%)", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"MW_debug_{side}_01_eyebrow_mask.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Componente centrale
    center_x = np.mean([p[0] for p in polygon_points])
    center_y = np.mean([p[1] for p in polygon_points])
    print(f"   📍 Centro poligono: ({center_x:.1f}, {center_y:.1f})")
    central_mask = get_largest_central_component(eyebrow_mask, (center_x, center_y))
    
    # Salva componente centrale (DEBUG)
    plt.figure(figsize=(12, 16))
    plt.imshow(central_mask, cmap='gray')
    plt.title(f"DEBUG: Componente Centrale {config['label']}\n{np.sum(central_mask)} px", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"MW_debug_{side}_02_central_mask.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Morfologia (COMMENTATO)
    # kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    # morphed_mask = cv2.morphologyEx(
    #     (central_mask * 255).astype(np.uint8), 
    #     cv2.MORPH_CLOSE, 
    #     kernel
    # )
    # morphed_mask = (morphed_mask > 0).astype(np.uint8)
    morphed_mask = central_mask  # Usa direttamente la maschera senza morfologia
    
    # Salva morfologia (DEBUG)
    plt.figure(figsize=(12, 16))
    plt.imshow(morphed_mask, cmap='gray')
    plt.title(f"DEBUG: Dopo Morfologia {config['label']}\n{np.sum(morphed_mask)} px", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"MW_debug_{side}_03_morphed_mask.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # Contorno
    contours, _ = cv2.findContours(
        (morphed_mask * 255).astype(np.uint8),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )
    
    if len(contours) == 0:
        print(f"⚠️  Nessun contorno trovato per {side}")
        return None
    
    largest_contour = max(contours, key=cv2.contourArea)
    contour_points = largest_contour.squeeze()
    
    if len(contour_points.shape) == 1:
        contour_points = contour_points.reshape(-1, 2)
    
    print(f"   ✓ Contorno: {len(contour_points)} punti")
    
    # Visualizza overlay finale
    img_overlay = img.copy()
    overlay = img.copy()
    
    cv2.drawContours(overlay, [largest_contour], -1, (0, 255, 0), -1)
    cv2.drawContours(overlay, [largest_contour], -1, (255, 255, 0), 3)
    img_overlay = cv2.addWeighted(img_overlay, 0.7, overlay, 0.3, 0)
    
    # Aggiungi maschera EXT per confronto
    cv2.polylines(img_overlay, [polygon_array], True, (255, 0, 0), 2)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_overlay)
    plt.title(f"Magic Wand {config['label']}\nVERDE=Contorno Magic Wand | ROSSO=Maschera EXT", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"MW_final_{side}.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: MW_final_{side}.png")
    
    return largest_contour


# MAIN
print("="*80)
print("FLUSSO ALTERNATIVO: MAGIC WAND EYEBROW SELECTION")
print("="*80)

img_path = "webapp/IMG_4675.JPEG"
img = cv2.imread(img_path)
if img is None:
    raise ValueError(f"Impossibile caricare: {img_path}")

img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
h, w = img.shape[:2]
img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

print(f"✅ Immagine: {w}x{h}px")

output_dir = Path("debug_magic_wand_eyebrow")
output_dir.mkdir(exist_ok=True)

# MediaPipe
print("📍 Rilevamento landmarks...")
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5
)

results = face_mesh.process(img)
if not results.multi_face_landmarks:
    raise ValueError("Nessun volto rilevato!")

face_landmarks = results.multi_face_landmarks[0]
landmarks = {}
for idx, landmark in enumerate(face_landmarks.landmark):
    landmarks[idx] = (landmark.x * w, landmark.y * h)

print(f"✅ {len(landmarks)} landmarks")

# Configurazione sopracciglia
eyebrow_configs = [
    {
        'side': 'right',
        'label': 'RIGHT EYEBROW',
        'lm_base': [336, 285, 282, 300, 334],
        'offsets': [(-1, -1), (-1, +1), (0, +1), (+1, +1), (+1, -1)],
        'extra_vertex_idx': 3,  # 300EXT
        'extra_offset': (-1, +1),  # -BETA a x, +BETA a y (speculare)
        'insert_position': 3,  # Inserisci 300EXT2 alla posizione 3 (prima di 300EXT)
        'tolerance': 90  # Tolleranza bacchetta magica (20-80)
    },
    {
        'side': 'left',
        'label': 'LEFT EYEBROW',
        'lm_base': [107, 55, 52, 70, 105],
        'offsets': [(+1, -1), (+1, +1), (0, +1), (-1, +1), (-1, -1)],
        'extra_vertex_idx': 3,  # 70EXT
        'extra_offset': (+1, +1),  # +ALPHA a x, +ALPHA a y
        'insert_position': 3,  # Inserisci 70EXT2 alla posizione 3 (prima di 70EXT)
        'tolerance': 90  # Tolleranza bacchetta magica (20-80)
    }
]

# Processa entrambi
contours_results = {}
for config in eyebrow_configs:
    contour = process_eyebrow_magic_wand(img, img_bgr, landmarks, config, output_dir, h, w)
    if contour is not None:
        contours_results[config['side']] = contour

# Confronto finale
if len(contours_results) > 0:
    img_final = img.copy()
    
    for side, contour in contours_results.items():
        color = (0, 255, 0) if side == 'right' else (255, 0, 255)
        cv2.drawContours(img_final, [contour], -1, color, 3)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_final)
    plt.title("CONFRONTO FINALE: Magic Wand\nVERDE=Right | MAGENTA=Left", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / "MW_comparison_both.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n✅ Salvata: MW_comparison_both.png")

print("\n" + "=" * 80)
print(f"✅ FLUSSO MAGIC WAND COMPLETATO!")
print(f"📂 Output in: {output_dir}/")
print("=" * 80)
