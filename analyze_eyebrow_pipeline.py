#!/usr/bin/env python3
"""
Analisi completa del pipeline di elaborazione sopracciglia
Simula il flusso JavaScript reale con tutte le fasi intermedie
"""

import cv2
import numpy as np
import mediapipe as mp
import matplotlib.pyplot as plt
from pathlib import Path

def point_in_polygon(point, polygon):
    """Verifica se un punto è dentro un poligono (ray casting algorithm)"""
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(n + 1):
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

def generate_left_eyebrow_mask(landmarks, img_height, img_width):
    """Genera maschera espansa 5 punti per sopracciglio sinistro"""
    lm107 = landmarks[107]
    lm55 = landmarks[55]
    lm52 = landmarks[52]
    lm70 = landmarks[70]
    lm105 = landmarks[105]
    
    # Converti in coordinate pixel
    def to_pixel(lm):
        return (int(lm.x * img_width), int(lm.y * img_height))
    
    p107 = to_pixel(lm107)
    p55 = to_pixel(lm55)
    p52 = to_pixel(lm52)
    p70 = to_pixel(lm70)
    p105 = to_pixel(lm105)
    
    # Calcola ALPHA
    dist = np.sqrt((p107[0] - p55[0])**2 + (p107[1] - p55[1])**2)
    ALPHA = dist / 2
    
    # Genera 5 punti EXT con offset corretti
    p107_ext = (int(p107[0] + ALPHA), int(p107[1] - ALPHA))
    p55_ext = (int(p55[0] + ALPHA), int(p55[1] + ALPHA))
    p52_ext = (int(p52[0]), int(p52[1] + ALPHA))
    p70_ext = (int(p70[0] - ALPHA), int(p70[1] + ALPHA))
    p105_ext = (int(p105[0] - ALPHA), int(p105[1] - ALPHA))
    
    return [p107_ext, p55_ext, p52_ext, p70_ext, p105_ext], ALPHA

def generate_right_eyebrow_mask(landmarks, img_height, img_width):
    """Genera maschera espansa 5 punti per sopracciglio destro"""
    lm336 = landmarks[336]
    lm285 = landmarks[285]
    lm282 = landmarks[282]
    lm300 = landmarks[300]
    lm334 = landmarks[334]
    
    def to_pixel(lm):
        return (int(lm.x * img_width), int(lm.y * img_height))
    
    p336 = to_pixel(lm336)
    p285 = to_pixel(lm285)
    p282 = to_pixel(lm282)
    p300 = to_pixel(lm300)
    p334 = to_pixel(lm334)
    
    # Calcola BETA
    dist = np.sqrt((p336[0] - p285[0])**2 + (p336[1] - p285[1])**2)
    BETA = dist / 2
    
    # Genera 5 punti EXT speculari
    p336_ext = (int(p336[0] - BETA), int(p336[1] - BETA))
    p285_ext = (int(p285[0] - BETA), int(p285[1] + BETA))
    p282_ext = (int(p282[0]), int(p282[1] + BETA))
    p300_ext = (int(p300[0] + BETA), int(p300[1] + BETA))
    p334_ext = (int(p334[0] + BETA), int(p334[1] - BETA))
    
    return [p336_ext, p285_ext, p282_ext, p300_ext, p334_ext], BETA

def apply_preprocessing_adaptive(image, polygon):
    """
    Preprocessing adattivo come nel codice JavaScript corretto
    1. Calcola media luminosità SOLO dei pixel dentro il poligono
    2. Applica contrast stretch
    3. Applica tonal separation con threshold adattivo (non fisso 128!)
    """
    img_copy = image.copy()
    h, w = img_copy.shape[:2]
    
    # FASE 1: Calcola media luminosità solo pixel dentro poligono
    total_lum = 0
    pixel_count = 0
    
    # Calcola bounding box per efficienza
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    min_x, max_x = max(0, min(xs)), min(w, max(xs))
    min_y, max_y = max(0, min(ys)), min(h, max(ys))
    
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            if point_in_polygon((x, y), polygon):
                b, g, r = img_copy[y, x]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                total_lum += lum
                pixel_count += 1
    
    mean_luminance = total_lum / pixel_count if pixel_count > 0 else 128
    print(f"  📊 Media luminosità regione: {mean_luminance:.1f} ({pixel_count} pixel)")
    
    # FASE 2: Applica preprocessing con threshold ADATTIVO
    contrast_factor = 2.5
    
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            if point_in_polygon((x, y), polygon):
                b, g, r = img_copy[y, x].astype(float)
                
                # Contrast stretch
                r = np.clip(((r - 128) * contrast_factor) + 128, 0, 255)
                g = np.clip(((g - 128) * contrast_factor) + 128, 0, 255)
                b = np.clip(((b - 128) * contrast_factor) + 128, 0, 255)
                
                # Tonal separation con threshold ADATTIVO
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if lum < mean_luminance:  # Non più 128 fisso!
                    # Scurisce
                    r *= 0.7
                    g *= 0.7
                    b *= 0.7
                else:
                    # Schiarisce
                    r = min(255, r * 1.3)
                    g = min(255, g * 1.3)
                    b = min(255, b * 1.3)
                
                img_copy[y, x] = [int(b), int(g), int(r)]
    
    print(f"  🎨 Preprocessing adattivo: threshold={mean_luminance:.1f}, contrasto=2.5x")
    return img_copy, mean_luminance

def create_binary_mask(image, polygon, adaptive_threshold):
    """Crea maschera binaria con threshold adattivo"""
    h, w = image.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    min_x, max_x = max(0, min(xs)), min(w, max(xs))
    min_y, max_y = max(0, min(ys)), min(h, max(ys))
    
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            if point_in_polygon((x, y), polygon):
                b, g, r = image[y, x]
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if lum < adaptive_threshold:
                    mask[y, x] = 255
    
    return mask

def apply_morphology(mask):
    """Applica operazioni morfologiche conservative (opening 2x2)"""
    kernel = np.ones((2, 2), np.uint8)
    # Opening = erosion + dilation
    eroded = cv2.erode(mask, kernel, iterations=2)
    opened = cv2.dilate(eroded, kernel, iterations=2)
    return opened

def smooth_contour(contour, window=3):
    """Smoothing con moving average"""
    if len(contour) < window:
        return contour
    
    smoothed = []
    for i in range(len(contour)):
        points = []
        for j in range(-window//2 + 1, window//2 + 2):
            idx = (i + j) % len(contour)
            points.append(contour[idx][0])
        
        avg_x = sum(p[0] for p in points) / len(points)
        avg_y = sum(p[1] for p in points) / len(points)
        smoothed.append([[int(avg_x), int(avg_y)]])
    
    return np.array(smoothed)

# Carica immagine
image_path = '/var/www/html/kimerika.cloud/IMG_7655.JPG'
image = cv2.imread(image_path)
h, w = image.shape[:2]

print(f"📷 Immagine caricata: {w}x{h}px")

# Inizializza MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=True,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5
)

# Rileva landmarks
image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
results = face_mesh.process(image_rgb)

if not results.multi_face_landmarks:
    print("❌ Nessun volto rilevato")
    exit(1)

landmarks = results.multi_face_landmarks[0].landmark
print("✅ Landmarks rilevati")

# FASE 0: Immagine originale
img_original = image.copy()

# FASE 1: Genera maschere a 5 punti
left_polygon, alpha = generate_left_eyebrow_mask(landmarks, h, w)
right_polygon, beta = generate_right_eyebrow_mask(landmarks, h, w)

print(f"\n📐 ALPHA={alpha:.1f}px, BETA={beta:.1f}px")

img_polygons = image.copy()
cv2.polylines(img_polygons, [np.array(left_polygon)], True, (255, 107, 53), 2)
cv2.polylines(img_polygons, [np.array(right_polygon)], True, (107, 115, 255), 2)

# FASE 2: Preprocessing adattivo (sopracciglio sinistro)
print("\n🔬 SOPRACCIGLIO SINISTRO:")
img_preproc_left, mean_lum_left = apply_preprocessing_adaptive(image, left_polygon)

print("\n🔬 SOPRACCIGLIO DESTRO:")
img_preproc_right, mean_lum_right = apply_preprocessing_adaptive(img_preproc_left, right_polygon)

# FASE 3: Binarizzazione con threshold adattivo
threshold_left = mean_lum_left - 8
threshold_right = mean_lum_right - 8

print(f"\n🎯 Threshold binarizzazione: left={threshold_left:.1f}, right={threshold_right:.1f}")

mask_left = create_binary_mask(img_preproc_right, left_polygon, threshold_left)
mask_right = create_binary_mask(img_preproc_right, right_polygon, threshold_right)

mask_combined = cv2.bitwise_or(mask_left, mask_right)

# FASE 4: Morphological operations
print("\n🔧 Operazioni morfologiche (opening 2x2)...")
mask_morph_left = apply_morphology(mask_left)
mask_morph_right = apply_morphology(mask_right)
mask_morph_combined = cv2.bitwise_or(mask_morph_left, mask_morph_right)

# FASE 5: Tracciamento contorni
print("\n🔍 Tracciamento contorni...")
contours_left, _ = cv2.findContours(mask_morph_left, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours_right, _ = cv2.findContours(mask_morph_right, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

img_contours = image.copy()
if contours_left:
    cv2.drawContours(img_contours, contours_left, -1, (255, 107, 53), 2)
if contours_right:
    cv2.drawContours(img_contours, contours_right, -1, (107, 115, 255), 2)

# FASE 6: Smoothing
print("✨ Smoothing contorni (window=3)...")
img_smoothed = image.copy()
if contours_left:
    smoothed_left = smooth_contour(max(contours_left, key=cv2.contourArea), window=3)
    cv2.drawContours(img_smoothed, [smoothed_left], -1, (255, 107, 53), 2)
if contours_right:
    smoothed_right = smooth_contour(max(contours_right, key=cv2.contourArea), window=3)
    cv2.drawContours(img_smoothed, [smoothed_right], -1, (107, 115, 255), 2)

# Salva tutte le immagini
output_dir = Path('/var/www/html/kimerika.cloud')

cv2.imwrite(str(output_dir / 'pipeline_0_original.jpg'), img_original)
cv2.imwrite(str(output_dir / 'pipeline_1_polygons_5points.jpg'), img_polygons)
cv2.imwrite(str(output_dir / 'pipeline_2_preprocessing_adaptive.jpg'), img_preproc_right)
cv2.imwrite(str(output_dir / 'pipeline_3_binary_mask.jpg'), mask_combined)
cv2.imwrite(str(output_dir / 'pipeline_4_morphology.jpg'), mask_morph_combined)
cv2.imwrite(str(output_dir / 'pipeline_5_contours.jpg'), img_contours)
cv2.imwrite(str(output_dir / 'pipeline_6_smoothed.jpg'), img_smoothed)

print("\n✅ Immagini salvate:")
print("  - pipeline_0_original.jpg")
print("  - pipeline_1_polygons_5points.jpg")
print("  - pipeline_2_preprocessing_adaptive.jpg")
print("  - pipeline_3_binary_mask.jpg")
print("  - pipeline_4_morphology.jpg")
print("  - pipeline_5_contours.jpg")
print("  - pipeline_6_smoothed.jpg")

# Crea visualizzazione comparativa
fig, axes = plt.subplots(2, 4, figsize=(20, 10))
fig.suptitle('Pipeline Completo Elaborazione Sopracciglia (Flusso Reale)', fontsize=16, fontweight='bold')

images = [
    (img_original, 'FASE 0: Originale'),
    (img_polygons, 'FASE 1: Poligoni 5 Punti EXT'),
    (img_preproc_right, 'FASE 2: Preprocessing Adattivo'),
    (mask_combined, 'FASE 3: Binarizzazione'),
    (mask_morph_combined, 'FASE 4: Morphology (Opening 2x2)'),
    (img_contours, 'FASE 5: Contorni'),
    (img_smoothed, 'FASE 6: Smoothing (window=3)'),
]

for idx, (img, title) in enumerate(images):
    row = idx // 4
    col = idx % 4
    ax = axes[row, col]
    
    if len(img.shape) == 3:
        img_display = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        img_display = img
    
    ax.imshow(img_display, cmap='gray' if len(img.shape) == 2 else None)
    ax.set_title(title, fontsize=10, fontweight='bold')
    ax.axis('off')

# Rimuovi ultimo subplot vuoto
axes[1, 3].axis('off')

plt.tight_layout()
plt.savefig(str(output_dir / 'pipeline_comparison.png'), dpi=150, bbox_inches='tight')
print("  - pipeline_comparison.png (visualizzazione comparativa)")

print("\n🎉 Analisi completa!")
print(f"📊 Parametri utilizzati:")
print(f"  - Threshold adattivo SX: {mean_lum_left:.1f} (binarizzazione: {threshold_left:.1f})")
print(f"  - Threshold adattivo DX: {mean_lum_right:.1f} (binarizzazione: {threshold_right:.1f})")
print(f"  - Contrasto: 2.5x")
print(f"  - Morphology: Opening 2x2 (erosion x2 + dilation x2)")
print(f"  - Smoothing: Moving average window=3")
