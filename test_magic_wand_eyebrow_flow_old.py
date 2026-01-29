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

print("="*80)
print("FLUSSO ALTERNATIVO: MAGIC WAND EYEBROW SELECTION")
print("="*80)

# Carica immagine
img_path = "webapp/IMG_4675.JPEG"
img = cv2.imread(img_path)
if img is None:
    raise ValueError(f"Impossibile caricare l'immagine: {img_path}")

img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
h, w = img.shape[:2]

print(f"✅ Immagine caricata: {w}x{h}px")

# Crea directory output
output_dir = Path("debug_magic_wand_eyebrow")
output_dir.mkdir(exist_ok=True)

# Rileva landmarks con MediaPipe
print("\n📍 Rilevamento landmarks con MediaPipe...")
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

print(f"✅ Rilevati {len(landmarks)} landmarks")

# ============================================================================
# CONFIGURAZIONE ENTRAMBI I SOPRACCIGLIA
# ============================================================================

eyebrow_configs = [
    {
        'side': 'right',
        'label': 'RIGHT EYEBROW',
        'lm_base': [336, 285, 282, 300, 334],
        'offsets': [
            (-1, -1),  # 336EXT
            (-1, +1),  # 285EXT
            (0, +1),   # 282EXT
            (+1, +1),  # 300EXT
            (+1, -1),  # 334EXT
        ]
    },
    {
        'side': 'left',
        'label': 'LEFT EYEBROW',
        'lm_base': [107, 55, 52, 70, 105],
        'offsets': [
            (+1, -1),  # 107EXT
            (+1, +1),  # 55EXT
            (0, +1),   # 52EXT
            (-1, +1),  # 70EXT
            (-1, -1),  # 105EXT
        ]
    }
]

for config in eyebrow_configs:
for config in eyebrow_configs:
    
    print(f"\n{'='*80}")
    print(f"PROCESSING: {config['label']} - MAGIC WAND FLOW")
    print(f"{'='*80}")
    
    side = config['side']
    lm_indices = config['lm_base']
    offsets = config['offsets']
    
    # Ottieni landmarks base
    lm_points = [landmarks[i] for i in lm_indices]
    
    # Calcola BETA (metà distanza tra primi due punti)
    distance = calculate_distance(lm_points[0], lm_points[1])
    BETA = distance / 2
    
    print(f"📐 BETA: {BETA:.2f}px")
    
    # Genera punti EXT
    expandedMask = []
    for i, (lm, (ox, oy)) in enumerate(zip(lm_points, offsets)):
        ext_point = {
            'name': f'{lm_indices[i]}EXT',
            'x': lm[0] + (ox * BETA),
            'y': lm[1] + (oy * BETA)
        }
        expandedMask.append(ext_point)
    
    polygon_points = [(int(p['x']), int(p['y'])) for p in expandedMask]
    polygon_array = np.array(polygon_points, dtype=np.int32)
    
    # Visualizza maschera espansa
    img_mask = img.copy()
    cv2.polylines(img_mask, [polygon_array], True, (0, 255, 0), 3)
    
    for i, (x, y) in enumerate(polygon_points):
        cv2.circle(img_mask, (x, y), 8, (255, 0, 0), -1)
        cv2.putText(img_mask, expandedMask[i]['name'], (x+10, y-10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_mask)
    plt.title(f"FASE MW-1: Maschera Espansa {config['label']} (5 punti EXT)", fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"MW01_{side}_expanded_mask.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: MW01_{side}_expanded_mask.png")
    
    # ========================================================================
    # FASE MW-2: CALCOLA PUNTO SEED (centro tra LM base e EXT)
    # ========================================================================
    
    print(f"\n{'='*80}")
    print(f"FASE MW-2: CALCOLO SEED POINT (ZONA PELLE) - {side.upper()}")
    print(f"{'='*80}")
    
    # Centro tra primo landmark base e primo EXT (zona pelle)
    seed_x = (lm_points[0][0] + expandedMask[0]['x']) / 2
    seed_y = (lm_points[0][1] + expandedMask[0]['y']) / 2
    
    print(f"📍 LM{lm_indices[0]}: ({lm_points[0][0]:.1f}, {lm_points[0][1]:.1f})")
    print(f"📍 {lm_indices[0]}EXT: ({expandedMask[0]['x']:.1f}, {expandedMask[0]['y']:.1f})")
    print(f"📍 SEED POINT (centro - PELLE): ({seed_x:.1f}, {seed_y:.1f})")
    
    # Campiona colore 2x2 nel punto seed
    seed_color = sample_color_2x2(img, seed_x - 1, seed_y - 1)
    if seed_color is None:
        print(f"⚠️  Impossibile campionare colore nel punto seed per {side}, skip")
        continue
    
    print(f"🎨 Colore PELLE seed (2x2): BGR=({seed_color[0]}, {seed_color[1]}, {seed_color[2]})")
    
    # Visualizza seed point
    img_seed = img.copy()
    cv2.polylines(img_seed, [polygon_array], True, (0, 255, 0), 2)
    cv2.circle(img_seed, (int(seed_x), int(seed_y)), 10, (255, 0, 0), -1)
    cv2.rectangle(img_seed, 
                  (int(seed_x-1), int(seed_y-1)),
                  (int(seed_x+1), int(seed_y+1)),
                  (255, 0, 0), 3)
    
    # Aggiungi landmarks di riferimento
    cv2.circle(img_seed, (int(lm_points[0][0]), int(lm_points[0][1])), 6, (0, 255, 255), -1)
    cv2.circle(img_seed, (int(expandedMask[0]['x']), int(expandedMask[0]['y'])), 6, (0, 255, 255), -1)
    cv2.putText(img_seed, f"LM{lm_indices[0]}", (int(lm_points[0][0])+10, int(lm_points[0][1])), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(img_seed, f"{lm_indices[0]}EXT", (int(expandedMask[0]['x'])+10, int(expandedMask[0]['y'])), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(img_seed, "SEED", (int(seed_x)+10, int(seed_y)+10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_seed)
    plt.title(f"FASE MW-2: Seed Point {config['label']} (centro LM{lm_indices[0]}-{lm_indices[0]}EXT)\nBGR=({seed_color[0]}, {seed_color[1]}, {seed_color[2]})", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"MW02_{side}_seed_point.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: MW02_{side}_seed_point.png")
    
    # ========================================================================
    # FASE MW-3: APPLICA MAGIC WAND
    # ========================================================================
    
    print(f"\n{'='*80}")
    print(f"FASE MW-3: MAGIC WAND SELECTION (selezione PELLE) - {side.upper()}")
    print(f"{'='*80}")
    
    # Converti immagine in BGR per OpenCV
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    # Usa tolleranza appropriata per la pelle
    tolerance = 50
    print(f"⚙️  Tolleranza: {tolerance}")
    print(f"   (Distanza euclidea massima nel spazio BGR)")
    
    background_mask = magic_wand_selection_color_distance(
        img_bgr, 
        polygon_array, 
        (seed_x, seed_y), 
        tolerance
    )
    
    # Visualizza maschera sfondo
    plt.figure(figsize=(12, 16))
    plt.imshow(background_mask, cmap='gray')
    plt.title(f"FASE MW-3: PELLE Selezionata {config['label']}\nBIANCO=Pelle/Sfondo ({np.sum(background_mask)} px, tol={tolerance})", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / f"MW03_{side}_background_mask.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: MW03_{side}_background_mask.png")
# ============================================================================

print(f"\n{'='*80}")
print("FASE MW-4: INVERSIONE SELEZIONE (estrai sopracciglio)")
print(f"{'='*80}")

# Crea maschera del poligono
polygon_mask = np.zeros((h, w), dtype=np.uint8)
cv2.fillPoly(polygon_mask, [polygon_array], 1)

# Inverti: sopracciglio = pixel dentro poligono che NON sono pelle
eyebrow_mask = polygon_mask.copy()
eyebrow_mask[background_mask == 1] = 0

pixels_eyebrow = np.sum(eyebrow_mask)
pixels_total = np.sum(polygon_mask)
percentage = (pixels_eyebrow / pixels_total * 100) if pixels_total > 0 else 0

print(f"   ✓ Pixel totali poligono: {pixels_total}")
print(f"   ✓ Pixel pelle (sfondo): {np.sum(background_mask)}")
print(f"   ✓ Pixel sopracciglio (dopo inversione): {pixels_eyebrow}")
print(f"   ✓ Percentuale sopracciglio: {percentage:.1f}%")

plt.figure(figsize=(12, 16))
plt.imshow(eyebrow_mask, cmap='gray')
plt.title(f"FASE MW-4: Sopracciglio (inversione pelle)\nBIANCO=Sopracciglio ({pixels_eyebrow} px, {percentage:.1f}%)", 
         fontsize=14, fontweight='bold')
plt.axis('off')
plt.savefig(output_dir / "MW04_objects_mask.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Salvata: MW04_objects_mask.png")

# ============================================================================
# FASE MW-5: MANTIENI SOLO COMPONENTE CENTRALE
# ============================================================================

print(f"\n{'='*80}")
print("FASE MW-5: SELEZIONE COMPONENTE CENTRALE")
print(f"{'='*80}")

# Calcola centro del poligono
center_x = np.mean([p[0] for p in polygon_points])
center_y = np.mean([p[1] for p in polygon_points])
print(f"📍 Centro poligono: ({center_x:.1f}, {center_y:.1f})")

# Mantieni solo il componente centrale
central_mask = get_largest_central_component(eyebrow_mask, (center_x, center_y))

plt.figure(figsize=(12, 16))
plt.imshow(central_mask, cmap='gray')
plt.title(f"FASE MW-5: Solo Componente Centrale\n({np.sum(central_mask)} px)", 
         fontsize=14, fontweight='bold')
plt.axis('off')
plt.savefig(output_dir / "MW05_central_component.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Salvata: MW05_central_component.png")

# ============================================================================
# FASE MW-6: OPERAZIONI MORFOLOGICHE (opzionale, per pulizia)
# ============================================================================

print(f"\n{'='*80}")
print("FASE MW-6: MORFOLOGIA (opzionale)")
print(f"{'='*80}")

# Closing per riempire piccoli buchi
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
morphed_mask = cv2.morphologyEx(
    (central_mask * 255).astype(np.uint8), 
    cv2.MORPH_CLOSE, 
    kernel
)
morphed_mask = (morphed_mask > 0).astype(np.uint8)

print(f"   ✓ Dopo morfologia: {np.sum(morphed_mask)} pixel")

plt.figure(figsize=(12, 16))
plt.imshow(morphed_mask, cmap='gray')
plt.title(f"FASE MW-6: Dopo Morfologia (closing)\n({np.sum(morphed_mask)} px)", 
         fontsize=14, fontweight='bold')
plt.axis('off')
plt.savefig(output_dir / "MW06_morphology.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"✅ Salvata: MW06_morphology.png")

# ============================================================================
# FASE MW-7: ESTRAI CONTORNO
# ============================================================================

print(f"\n{'='*80}")
print("FASE MW-7: ESTRAZIONE CONTORNO")
print(f"{'='*80}")

# Trova contorno
contours, _ = cv2.findContours(
    (morphed_mask * 255).astype(np.uint8),
    cv2.RETR_EXTERNAL,
    cv2.CHAIN_APPROX_SIMPLE
)

if len(contours) == 0:
    print("⚠️  Nessun contorno trovato!")
else:
    # Prendi il contorno più grande
    largest_contour = max(contours, key=cv2.contourArea)
    contour_points = largest_contour.squeeze()
    
    if len(contour_points.shape) == 1:
        contour_points = contour_points.reshape(-1, 2)
    
    print(f"   ✓ Punti contorno: {len(contour_points)}")
    
    # Semplifica contorno (opzionale)
    epsilon = 0.005 * cv2.arcLength(largest_contour, True)
    simplified_contour = cv2.approxPolyDP(largest_contour, epsilon, True)
    simplified_points = simplified_contour.squeeze()
    
    if len(simplified_points.shape) == 1:
        simplified_points = simplified_points.reshape(-1, 2)
    
    print(f"   ✓ Contorno semplificato: {len(simplified_points)} punti")
    
    # Visualizza contorno
    img_contour = img.copy()
    cv2.drawContours(img_contour, [largest_contour], -1, (0, 255, 0), 3)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_contour)
    plt.title(f"FASE MW-7: Contorno Estratto\n({len(contour_points)} punti, semplificato: {len(simplified_points)})", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / "MW07_contour.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: MW07_contour.png")
    
    # ========================================================================
    # FASE MW-8: OVERLAY FINALE SUL CANVAS
    # ========================================================================
    
    print(f"\n{'='*80}")
    print("FASE MW-8: OVERLAY FINALE")
    print(f"{'='*80}")
    
    # Overlay con riempimento semi-trasparente
    img_overlay = img.copy()
    overlay = img.copy()
    
    # Disegna contorno e riempi
    cv2.drawContours(overlay, [largest_contour], -1, (0, 255, 0), -1)
    cv2.drawContours(overlay, [largest_contour], -1, (255, 255, 0), 3)
    
    # Blend
    img_overlay = cv2.addWeighted(img_overlay, 0.7, overlay, 0.3, 0)
    
    # Aggiungi anche la maschera EXT originale per confronto
    cv2.polylines(img_overlay, [polygon_array], True, (255, 0, 0), 2)
    
    plt.figure(figsize=(12, 16))
    plt.imshow(img_overlay)
    plt.title("FASE MW-8: Overlay Finale Canvas\nVERDE=Contorno Magic Wand | ROSSO=Maschera EXT originale", 
             fontsize=14, fontweight='bold')
    plt.axis('off')
    plt.savefig(output_dir / "MW08_final_overlay.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Salvata: MW08_final_overlay.png")
    
    # ========================================================================
    # FASE MW-9: CONFRONTO CON FLUSSO ORIGINALE
    # ========================================================================
    
    print(f"\n{'='*80}")
    print("FASE MW-9: CONFRONTO FLUSSI")
    print(f"{'='*80}")
    
    # Leggi immagine del flusso originale se esiste
    original_flow_path = Path("debug_exact_webapp_IMG_4675/05_right_contour_final.png")
    
    if original_flow_path.exists():
        img_comparison = img.copy()
        
        # ROSSO = maschera EXT
        cv2.polylines(img_comparison, [polygon_array], True, (255, 0, 0), 2)
        
        # VERDE = contorno Magic Wand
        cv2.drawContours(img_comparison, [largest_contour], -1, (0, 255, 0), 3)
        
        plt.figure(figsize=(12, 16))
        plt.imshow(img_comparison)
        plt.title("⚡ CONFRONTO: Magic Wand vs Flusso Originale\nROSSO=Maschera EXT | VERDE=Magic Wand", 
                 fontsize=14, fontweight='bold')
        plt.axis('off')
        plt.savefig(output_dir / "MW09_comparison.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Salvata: MW09_comparison.png")
    else:
        print(f"⚠️  File flusso originale non trovato: {original_flow_path}")

print("\n" + "=" * 80)
print(f"✅ FLUSSO MAGIC WAND COMPLETATO!")
print(f"📂 Tutte le immagini salvate in: {output_dir}/")
print("=" * 80)
print("\n🔍 RIEPILOGO FLUSSO:")
print("   MW01: Maschera espansa 5 punti EXT")
print("   MW02: Seed point (centro LM336-336EXT)")
print("   MW03: Sfondo selezionato con Magic Wand")
print("   MW04: Inversione → oggetti")
print("   MW05: Solo componente centrale")
print("   MW06: Morfologia (pulizia)")
print("   MW07: Contorno estratto")
print("   MW08: Overlay finale sul canvas")
print("   MW09: Confronto con flusso originale")
