#!/usr/bin/env python3
"""
Script per visualizzare il preprocessing step-by-step dell'immagine
Applica le stesse trasformazioni del codice JavaScript measurements.js
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def apply_contrast_stretch(image, factor=2.5):
    """
    Applica contrast stretch: newValue = ((oldValue - 128) * factor) + 128
    """
    result = image.astype(np.float32)
    result = ((result - 128) * factor) + 128
    result = np.clip(result, 0, 255).astype(np.uint8)
    return result

def apply_tonal_separation(image):
    """
    Intensifica la separazione tonale:
    - Pixel scuri (< 128): scurisce al 70%
    - Pixel chiari (>= 128): schiarisce al 130%
    """
    result = image.astype(np.float32)
    
    # Calcola luminosità (grayscale)
    luminance = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Maschera pixel scuri e chiari
    dark_mask = luminance < 128
    light_mask = luminance >= 128
    
    # Applica fattori
    for c in range(3):  # Per ogni canale BGR
        result[:, :, c] = np.where(dark_mask, result[:, :, c] * 0.7, result[:, :, c])
        result[:, :, c] = np.where(light_mask, np.minimum(result[:, :, c] * 1.3, 255), result[:, :, c])
    
    return result.astype(np.uint8)

def calculate_adaptive_threshold(image):
    """
    Calcola threshold adattivo: meanLuminance - 8
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mean_luminance = np.mean(gray)
    threshold = mean_luminance - 8
    return threshold, mean_luminance

def apply_binarization(image, threshold):
    """
    Binarizza: pixel < threshold = nero (255), pixel >= threshold = bianco (0)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = np.where(gray < threshold, 255, 0).astype(np.uint8)
    return binary

def main():
    # Carica l'immagine
    input_path = Path('/var/www/html/kimerika.cloud/best_frontal_frame1.png')
    if not input_path.exists():
        print(f"❌ File non trovato: {input_path}")
        return
    
    img_original = cv2.imread(str(input_path))
    if img_original is None:
        print(f"❌ Impossibile leggere l'immagine: {input_path}")
        return
    
    print(f"✅ Immagine caricata: {img_original.shape}")
    
    # === STEP 1: CONTRAST STRETCH (2.5x) ===
    print("\n📊 STEP 1: Applicazione contrast stretch (fattore 2.5x)...")
    img_contrast = apply_contrast_stretch(img_original, factor=2.5)
    
    # === STEP 2: TONAL SEPARATION ===
    print("📊 STEP 2: Intensificazione tonale (scuri->70%, chiari->130%)...")
    img_tonal = apply_tonal_separation(img_contrast)
    
    # === STEP 3: CALCOLO THRESHOLD ===
    print("📊 STEP 3: Calcolo threshold adattivo...")
    threshold, mean_lum = calculate_adaptive_threshold(img_tonal)
    print(f"   Media luminosità: {mean_lum:.1f}")
    print(f"   Threshold adattivo: {threshold:.1f}")
    
    # === STEP 4: BINARIZZAZIONE ===
    print("📊 STEP 4: Binarizzazione con threshold adattivo...")
    img_binary = apply_binarization(img_tonal, threshold)
    
    # === SALVA I RISULTATI ===
    output_dir = Path('/var/www/html/kimerika.cloud/preprocessing_steps')
    output_dir.mkdir(exist_ok=True)
    
    cv2.imwrite(str(output_dir / 'step0_original.png'), img_original)
    cv2.imwrite(str(output_dir / 'step1_contrast.png'), img_contrast)
    cv2.imwrite(str(output_dir / 'step2_tonal_separation.png'), img_tonal)
    cv2.imwrite(str(output_dir / 'step3_binary.png'), img_binary)
    
    print(f"\n✅ Immagini salvate in: {output_dir}/")
    
    # === CREA VISUALIZZAZIONE COMPARATIVA ===
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Preprocessing Pipeline - Step by Step', fontsize=16, fontweight='bold')
    
    # Step 0: Originale
    axes[0, 0].imshow(cv2.cvtColor(img_original, cv2.COLOR_BGR2RGB))
    axes[0, 0].set_title('STEP 0: Originale', fontsize=14, fontweight='bold')
    axes[0, 0].axis('off')
    
    # Step 1: Contrast stretch
    axes[0, 1].imshow(cv2.cvtColor(img_contrast, cv2.COLOR_BGR2RGB))
    axes[0, 1].set_title('STEP 1: Contrast Stretch (2.5x)', fontsize=14, fontweight='bold')
    axes[0, 1].axis('off')
    
    # Step 2: Tonal separation
    axes[1, 0].imshow(cv2.cvtColor(img_tonal, cv2.COLOR_BGR2RGB))
    axes[1, 0].set_title('STEP 2: Tonal Separation\n(scuri->70%, chiari->130%)', 
                         fontsize=14, fontweight='bold')
    axes[1, 0].axis('off')
    
    # Step 3: Binary
    axes[1, 1].imshow(img_binary, cmap='gray')
    axes[1, 1].set_title(f'STEP 3: Binarizzazione\n(threshold={threshold:.1f}, media={mean_lum:.1f})', 
                         fontsize=14, fontweight='bold')
    axes[1, 1].axis('off')
    
    plt.tight_layout()
    comparison_path = output_dir / 'preprocessing_comparison.png'
    plt.savefig(str(comparison_path), dpi=150, bbox_inches='tight')
    print(f"✅ Comparazione salvata in: {comparison_path}")
    
    # === ISTOGRAMMI LUMINOSITÀ ===
    fig2, axes2 = plt.subplots(2, 2, figsize=(16, 10))
    fig2.suptitle('Istogrammi Luminosità - Evoluzione', fontsize=16, fontweight='bold')
    
    images_gray = [
        cv2.cvtColor(img_original, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(img_contrast, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(img_tonal, cv2.COLOR_BGR2GRAY),
        img_binary
    ]
    titles = [
        'Originale',
        'Dopo Contrast Stretch',
        'Dopo Tonal Separation',
        'Binaria'
    ]
    
    for idx, (img_gray, title) in enumerate(zip(images_gray, titles)):
        ax = axes2.flat[idx]
        hist = cv2.calcHist([img_gray], [0], None, [256], [0, 256])
        ax.plot(hist, color='blue')
        ax.set_xlim([0, 256])
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xlabel('Luminosità')
        ax.set_ylabel('Frequenza')
        ax.grid(True, alpha=0.3)
        
        # Aggiungi linea threshold per l'ultimo
        if idx == 2:  # Tonal separation
            ax.axvline(x=threshold, color='red', linestyle='--', linewidth=2, 
                      label=f'Threshold={threshold:.1f}')
            ax.legend()
    
    plt.tight_layout()
    histogram_path = output_dir / 'luminosity_histograms.png'
    plt.savefig(str(histogram_path), dpi=150, bbox_inches='tight')
    print(f"✅ Istogrammi salvati in: {histogram_path}")
    
    print("\n" + "="*60)
    print("✨ PREPROCESSING COMPLETATO!")
    print("="*60)
    print(f"📁 Tutti i file sono in: {output_dir}/")
    print("\nFile generati:")
    print("  - step0_original.png")
    print("  - step1_contrast.png")
    print("  - step2_tonal_separation.png")
    print("  - step3_binary.png")
    print("  - preprocessing_comparison.png")
    print("  - luminosity_histograms.png")

if __name__ == '__main__':
    main()
