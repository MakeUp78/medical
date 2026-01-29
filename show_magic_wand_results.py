import matplotlib.pyplot as plt
from pathlib import Path
import cv2

output_dir = Path("debug_magic_wand_eyebrow")

# Lista di immagini da mostrare
images = [
    ("MW_final_right.png", "Right Eyebrow - Finale"),
    ("MW_final_left.png", "Left Eyebrow - Finale"),
    ("MW_comparison_both.png", "Confronto Entrambi"),
    ("MW_debug_right_01_eyebrow_mask.png", "Right - Maschera Sopracciglio"),
    ("MW_debug_right_02_central_mask.png", "Right - Componente Centrale"),
    ("MW_debug_right_03_morphed_mask.png", "Right - Dopo Morfologia"),
    ("MW_debug_left_01_eyebrow_mask.png", "Left - Maschera Sopracciglio"),
    ("MW_debug_left_02_central_mask.png", "Left - Componente Centrale"),
    ("MW_debug_left_03_morphed_mask.png", "Left - Dopo Morfologia"),
]

print("\n" + "="*80)
print("RIEPILOGO IMMAGINI GENERATE - Magic Wand Eyebrow Flow")
print("="*80 + "\n")

for img_name, desc in images:
    img_path = output_dir / img_name
    if img_path.exists():
        img = cv2.imread(str(img_path))
        if img is not None:
            h, w = img.shape[:2]
            size_kb = img_path.stat().st_size / 1024
            print(f"✅ {img_name:50s} {desc:35s} ({w}x{h}px, {size_kb:.1f}KB)")
        else:
            print(f"⚠️  {img_name:50s} {desc:35s} (errore lettura)")
    else:
        print(f"❌ {img_name:50s} {desc:35s} (non trovato)")

print("\n" + "="*80)
print(f"📂 Directory: {output_dir.absolute()}")
print("="*80)
