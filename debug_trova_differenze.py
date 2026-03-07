"""
DEBUG VISUALE — FLUSSO "TROVA DIFFERENZE"
Replica ESATTA di _detect_white_dots_v3() + process_green_dots_analysis()
da webapp/api/main.py, con immagini di ogni trasformazione.

Immagine: face-landmark-localization-master/IMG_8116 - Copia.jpg
Output:
  debug_trova_differenze_output.png   griglia 3 colonne (input | output | legenda)
  debug_trova_differenze_final.png    overlay finale alta risoluzione

FLUSSO REALE (identico all'ordine di main.py):
  1. resize a TARGET_WIDTH=1200px          (prima di dlib)
  2. dlib → maschera binaria Sx/Dx        (sul frame ridimensionato)
  3. grayscale + highlight boost           (potenzia pixel sopra HIGHLIGHT_THRESH)
  4. dilate(OUTER_PX=35) → zona espansa   (intera, NON striscia)
     + lb_zone = strip estrema esterna   (colonne <= x_min+35 / >= x_max-35)
  5. soglia luma principale 200..255      white_mask nella zona espansa
     soglia luma LB/RB 120..255          lb_mask nella strip
  6. connectedComponents (8-conn)         su white_mask e lb_mask separati
     filtro circolarità+perimetro (inner/outer)
  7. rimappatura coordinate → orig        (scala inversa)
  8. sort_points_anatomical()             LC1,LA0,LA,LC,LB / RC1,RB,RC,RA,RA0
  9. generate_white_dots_overlay()        overlay PNG finale
"""

import sys, os, warnings, math
warnings.filterwarnings('ignore')
sys.path.insert(0, 'face-landmark-localization-master')

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe

from eyebrows import extract_eyebrows_from_array

# ─────────────────────────────────────────────────────────────────────────────
#  COSTANTI — copiate da webapp/api/main.py (WHITE_DOTS_*)
# ─────────────────────────────────────────────────────────────────────────────
TARGET_WIDTH          = 1200   # WHITE_DOTS_TARGET_WIDTH
OUTER_PX              = 35     # WHITE_DOTS_OUTER_PX
LUMA_MIN              = 200    # WHITE_DOTS_LUMA_MIN      (candidati principali)
LUMA_MAX              = 255    # WHITE_DOTS_LUMA_MAX
LUMA_LB               = 120    # WHITE_DOTS_LUMA_LB       (strip LB/RB)
LUMA_MAX_LB           = 255    # WHITE_DOTS_LUMA_MAX_LB
HIGHLIGHT_THRESH_INNER   = 160   # WHITE_DOTS_HIGHLIGHT_THRESH_INNER
HIGHLIGHT_STRENGTH_INNER = 0.8   # WHITE_DOTS_HIGHLIGHT_STRENGTH_INNER
HIGHLIGHT_THRESH_OUTER   = 140   # WHITE_DOTS_HIGHLIGHT_THRESH_OUTER
HIGHLIGHT_STRENGTH_OUTER = 0.6   # WHITE_DOTS_HIGHLIGHT_STRENGTH_OUTER
MIN_CIRC_INNER        = 0.5    # WHITE_DOTS_MIN_CIRCULARITY_INNER
MAX_CIRC_INNER        = 1.0    # WHITE_DOTS_MAX_CIRCULARITY_INNER
MIN_PERI_INNER        = 3      # WHITE_DOTS_MIN_PERIMETER_INNER
MAX_PERI_INNER        = 60     # WHITE_DOTS_MAX_PERIMETER_INNER
MIN_CIRC_OUTER        = 0.3    # WHITE_DOTS_MIN_CIRCULARITY_OUTER
MAX_CIRC_OUTER        = 1.0    # WHITE_DOTS_MAX_CIRCULARITY_OUTER
MIN_PERI_OUTER        = 2      # WHITE_DOTS_MIN_PERIMETER_OUTER
MAX_PERI_OUTER        = 40     # WHITE_DOTS_MAX_PERIMETER_OUTER
MIN_DISTANCE          = 12     # WHITE_DOTS_MIN_DISTANCE (NMS deduplicazione)

_DAT = 'face-landmark-localization-master/shape_predictor_68_face_landmarks.dat'
_IMG = 'face-landmark-localization-master/IMG_8116 - Copia.jpg'
OUT_GRID  = 'debug_trova_differenze_output.png'
OUT_FINAL = 'debug_trova_differenze_final.png'

ANAT_COLORS = {
    'LC1': '#00FF00', 'LA0': '#00CCFF', 'LA': '#0088FF',
    'LC':  '#FF8800', 'LB':  '#FF2222',
    'RC1': '#FFFF00', 'RB':  '#FF00FF', 'RC': '#FF6600',
    'RA':  '#00FFAA', 'RA0': '#AAFFFF',
}

# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY
# ─────────────────────────────────────────────────────────────────────────────
def bgr2rgb(img): return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
def gray2rgb(g):  return cv2.cvtColor(g,   cv2.COLOR_GRAY2RGB)
def hex2rgb(h):   return (int(h[1:3],16), int(h[3:5],16), int(h[5:7],16))

def annotate(ax, img_rgb, title, notes='', border=None):
    ax.imshow(img_rgb, aspect='auto')
    ax.set_title(title, fontsize=9, fontweight='bold', pad=3, color='white')
    if notes:
        ax.set_xlabel(notes, fontsize=6.5, color='#aaaaaa', labelpad=3)
    ax.axis('off')
    ax.set_facecolor('#090915')
    if border:
        for sp in ax.spines.values():
            sp.set_visible(True); sp.set_edgecolor(border); sp.set_linewidth(2)

def shrink(img, max_h=500):
    h, w = img.shape[:2]
    if h > max_h:
        s = max_h / h
        img = cv2.resize(img, (max(1,int(w*s)), max_h), interpolation=cv2.INTER_AREA)
    return img

def sort_anatomical(points, is_left):
    pts = [dict(p) for p in points]
    if len(pts) < 5:
        pref = 'L' if is_left else 'R'
        for i, pt in enumerate(sorted(pts, key=lambda p: p['y'])):
            pt['anatomical_name'] = f"{pref}{i+1}"
        return sorted(pts, key=lambda p: p['y'])
    if is_left:
        b  = min(pts, key=lambda p: p['x']);   b['anatomical_name']  = 'LB'
        sx = sorted(pts, key=lambda p: p['x'])
        c1 = min(sx[:3], key=lambda p: p['y']); c1['anatomical_name'] = 'LC1'
        sd = sorted(pts, key=lambda p: p['x'], reverse=True)
        a  = max(sd[:2], key=lambda p: p['y']); a['anatomical_name']  = 'LA'
        a0 = min(sd[:2], key=lambda p: p['y']); a0['anatomical_name'] = 'LA0'
        c  = [p for p in pts if p not in [b,c1,a,a0]][0]; c['anatomical_name'] = 'LC'
        return [c1, a0, a, c, b]
    else:
        b  = max(pts, key=lambda p: p['x']);   b['anatomical_name']  = 'RB'
        sx = sorted(pts, key=lambda p: p['x'], reverse=True)
        c1 = min(sx[:3], key=lambda p: p['y']); c1['anatomical_name'] = 'RC1'
        sa = sorted(pts, key=lambda p: p['x'])
        a  = max(sa[:2], key=lambda p: p['y']); a['anatomical_name']  = 'RA'
        a0 = min(sa[:2], key=lambda p: p['y']); a0['anatomical_name'] = 'RA0'
        c  = [p for p in pts if p not in [b,c1,a,a0]][0]; c['anatomical_name'] = 'RC'
        return [c1, b, c, a, a0]

# ═════════════════════════════════════════════════════════════════════════════
#  PIPELINE — replica ESATTA di _detect_white_dots_v3()
#  Le variabili snap_* catturano lo stato interno ad ogni trasformazione.
# ═════════════════════════════════════════════════════════════════════════════
print("="*72)
print("  DEBUG FLUSSO «TROVA DIFFERENZE»  — pipeline reale _detect_white_dots_v3")
print(f"  Immagine: {_IMG}")
print("="*72)

# ── Carica originale ──────────────────────────────────────────────────────────
img_orig_bgr = cv2.imread(_IMG)
assert img_orig_bgr is not None, f"Immagine non trovata: {_IMG}"
_orig_h, _orig_w = img_orig_bgr.shape[:2]
print(f"\n  Originale: {_orig_w}x{_orig_h} px")
snap_orig = bgr2rgb(img_orig_bgr)

# ── PASSO 1: resize (PRIMA di dlib) ──────────────────────────────────────────
print(f"\n[1] resize → TARGET_WIDTH={TARGET_WIDTH}px")
_scale = TARGET_WIDTH / _orig_w
img_bgr = cv2.resize(img_orig_bgr,
                     (TARGET_WIDTH, max(1, round(_orig_h * _scale))),
                     interpolation=cv2.INTER_AREA)
h, w = img_bgr.shape[:2]
print(f"    {_orig_w}x{_orig_h} → {w}x{h}  (scala={_scale:.4f})")
snap_resized = bgr2rgb(img_bgr)

# ── PASSO 2: dlib (sul frame ridimensionato) ──────────────────────────────────
print(f"\n[2] extract_eyebrows_from_array() su immagine {w}x{h}")
res_dlib = extract_eyebrows_from_array(img_bgr, predictor_path=_DAT)
assert res_dlib['face_detected'], "Volto non rilevato!"
left_mask  = res_dlib['left_mask']
right_mask = res_dlib['right_mask']
print(f"    maschera Sx: {int(np.sum(left_mask>0))} px")
print(f"    maschera Dx: {int(np.sum(right_mask>0))} px")

# Output reale di dlib: maschere binarie (bianco=sopracciglio, nero=fuori)
# Le due maschere affiancate con tinta Sx=verde, Dx=giallo su sfondo nero
snap_dlib = np.zeros((h, w, 3), dtype=np.uint8)
snap_dlib[left_mask  > 0] = [0, 220, 80]    # verde = Sx
snap_dlib[right_mask > 0] = [220, 180, 0]   # giallo = Dx

# ── PASSO 3: grayscale + highlight boost (separato inner/outer) ───────────────
print(f"\n[3] grayscale + highlight boost inner(thresh={HIGHLIGHT_THRESH_INNER}, str={HIGHLIGHT_STRENGTH_INNER}) "
      f"outer(thresh={HIGHLIGHT_THRESH_OUTER}, str={HIGHLIGHT_STRENGTH_OUTER})")
gray_raw = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
# boost inner
gray_f_inner = gray_raw.astype(np.float32)
mask_hi_inner = gray_f_inner >= HIGHLIGHT_THRESH_INNER
gray_f_inner[mask_hi_inner] = np.clip(
    gray_f_inner[mask_hi_inner] + HIGHLIGHT_STRENGTH_INNER * (255.0 - gray_f_inner[mask_hi_inner]), 0, 255)
gray_inner = gray_f_inner.astype(np.uint8)
# boost outer
gray_f_outer = gray_raw.astype(np.float32)
mask_hi_outer = gray_f_outer >= HIGHLIGHT_THRESH_OUTER
gray_f_outer[mask_hi_outer] = np.clip(
    gray_f_outer[mask_hi_outer] + HIGHLIGHT_STRENGTH_OUTER * (255.0 - gray_f_outer[mask_hi_outer]), 0, 255)
gray_outer = gray_f_outer.astype(np.uint8)
print(f"    inner: {int(np.sum(mask_hi_inner))} px potenziati  luma medio raw={gray_raw.mean():.1f} → {gray_inner.mean():.1f}")
print(f"    outer: {int(np.sum(mask_hi_outer))} px potenziati  luma medio raw={gray_raw.mean():.1f} → {gray_outer.mean():.1f}")
# usa gray_inner come riferimento per la visualizzazione
snap_gray_raw    = gray2rgb(gray_raw)
snap_gray_clahe  = gray2rgb(gray_inner)  # snap step 3 = boost inner (principale)

# ── PASSO 4: dilate + lb_zone  (per ogni lato) ────────────────────────────────
print(f"\n[4] dilate(OUTER_PX={OUTER_PX}) → zona espansa intera  +  strip LB/RB")
k_outer  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OUTER_PX*2+1, OUTER_PX*2+1))
col_idx  = np.indices((h, w))[1]

expanded  = {}
lb_zones  = {}
polygons  = {}
for side, mask in [('left', left_mask), ('right', right_mask)]:
    exp = cv2.dilate(mask, k_outer, iterations=1)
    expanded[side] = exp

    # contorno per overlay finale
    cnts, _ = cv2.findContours(exp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        polygons[side] = max(cnts, key=cv2.contourArea).squeeze()

    # lb_zone: strip estrema basata su x_min/x_max della maschera dlib (NON expanded)
    ys_m, xs_m = np.where(mask > 0)
    x_min_mask, x_max_mask = int(xs_m.min()), int(xs_m.max())
    if side == 'left':
        lb_zones[side] = (exp > 0) & (col_idx <= x_min_mask + OUTER_PX)
    else:
        lb_zones[side] = (exp > 0) & (col_idx >= x_max_mask - OUTER_PX)
    print(f"    [{side}] zona espansa: {int(np.sum(exp>0))} px  "
          f"strip LB/RB: {int(np.sum(lb_zones[side]))} px  "
          f"(x_min={x_min_mask} x_max={x_max_mask})")

# visualizzazione step 4 — sfondo = gray CLAHE (quello che usano davvero gli step successivi)
snap_zones = gray2rgb(gray_inner).copy()
for side in ['left','right']:
    mask = left_mask if side=='left' else right_mask
    exp  = expanded[side]
    # zona espansa pura (escl. maschera e strip)
    zone_only = (exp > 0) & (mask == 0) & (~lb_zones[side])
    # maschera dlib interna = tinta blu scura
    snap_zones[mask > 0]       = (snap_zones[mask > 0]       * 0.3 + np.array([60,60,80])  * 0.7).astype(np.uint8)
    # zona espansa = ciano (sx) o verde (dx)
    col_exp = np.array([0,180,255]) if side=='left' else np.array([0,255,120])
    snap_zones[zone_only]      = (snap_zones[zone_only]      * 0.15 + col_exp * 0.85).astype(np.uint8)
    # strip LB/RB = arancio vivace
    snap_zones[lb_zones[side]] = (snap_zones[lb_zones[side]] * 0.1 + np.array([255,140,0]) * 0.9).astype(np.uint8)
# Contorno zona espansa
for side in ['left','right']:
    cnts, _ = cv2.findContours(expanded[side], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    col = (0,180,255) if side=='left' else (0,255,120)
    cv2.drawContours(snap_zones, cnts, -1, col, 2, cv2.LINE_AA)

# ── PASSO 5: soglia luma ──────────────────────────────────────────────────────
print(f"\n[5] soglia luma principale {LUMA_MIN}..{LUMA_MAX}  +  LB/RB {LUMA_LB}..{LUMA_MAX_LB}")
white_masks = {}
lb_masks    = {}
for side in ['left','right']:
    wm = np.zeros((h, w), dtype=np.uint8)
    wm[(gray_inner >= LUMA_MIN) & (gray_inner <= LUMA_MAX) & (expanded[side] > 0)] = 255
    white_masks[side] = wm

    lm = np.zeros((h, w), dtype=np.uint8)
    lm[(gray_outer >= LUMA_LB) & (gray_outer <= LUMA_MAX_LB) & lb_zones[side]] = 255
    lb_masks[side] = lm
    print(f"    [{side}] pixel bianchi principali: {int(np.sum(wm>0))}  "
          f"strip LB/RB: {int(np.sum(lm>0))}")

snap_thresh = gray2rgb(gray_inner).copy()  # sfondo = gray_inner (input reale della soglia)
snap_thresh[white_masks['left']  > 0] = [0, 255, 120]    # verde chiaro = Sx principale
snap_thresh[white_masks['right'] > 0] = [255, 240, 0]    # giallo = Dx principale
snap_thresh[lb_masks['left']     > 0] = [0, 180, 255]    # ciano = strip Sx
snap_thresh[lb_masks['right']    > 0] = [255, 80, 255]   # magenta = strip Dx

# ── PASSO 6: connected components + filtro circolarità+perimetro ──────────────
print(f"\n[6] connectedComponents (8-conn)  "
      f"inner circ[{MIN_CIRC_INNER:.1f}-{MAX_CIRC_INNER:.1f}] peri[{MIN_PERI_INNER}-{MAX_PERI_INNER}px]  "
      f"outer circ[{MIN_CIRC_OUTER:.1f}-{MAX_CIRC_OUTER:.1f}] peri[{MIN_PERI_OUTER}-{MAX_PERI_OUTER}px]")
candidates    = {}
lb_candidates = {}
snap_cc = gray2rgb(gray_inner).copy()
R  = max(5, h // 220)

# ── _filter_circ: restituisce info complete per ogni blob ─────────────────────
# discarded: (cx, cy, area, perim, circ, luma, reason_short, reason_verbose)
# accepted:  dict con chiavi aggiuntive perim, circ, luma
def _filter_circ(cc_mask, lmap, stats, cents, n_lbl, g, min_c, max_c, min_p, max_p, forced=False):
    result, discarded = [], []
    for lbl in range(1, n_lbl):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        cx   = int(round(float(cents[lbl, 0])))
        cy   = int(round(float(cents[lbl, 1])))
        blob_m = (lmap == lbl).astype(np.uint8)
        cnts_b, _ = cv2.findContours(blob_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts_b:
            discarded.append((cx, cy, area, 0, 0.0, 0.0, "no-cnt",
                              "nessun contorno rilevabile\n→ blob degenerato (1px?)"))
            continue
        perim = cv2.arcLength(cnts_b[0], True)
        circ  = (4.0 * math.pi * area / (perim ** 2)) if perim > 0 else 0.0
        mluma = float(np.mean(g[lmap == lbl]))
        if perim < min_p:
            discarded.append((cx, cy, area, perim, circ, mluma,
                              f"P={perim:.0f}<{min_p}",
                              f"perim {perim:.0f}px < min {min_p}\n→ blob troppo piccolo\n→ probabilmente rumore"))
            continue
        if perim > max_p:
            discarded.append((cx, cy, area, perim, circ, mluma,
                              f"P={perim:.0f}>{max_p}",
                              f"perim {perim:.0f}px > max {max_p}\n→ blob troppo grande\n→ riflesso o capello"))
            continue
        if circ < min_c:
            discarded.append((cx, cy, area, perim, circ, mluma,
                              f"C={circ:.2f}<{min_c:.1f}",
                              f"circ {circ:.3f} < min {min_c:.1f}\n→ forma troppo allungata\n→ riflesso lineare"))
            continue
        if circ > max_c:
            discarded.append((cx, cy, area, perim, circ, mluma,
                              f"C={circ:.2f}>{max_c:.1f}",
                              f"circ {circ:.3f} > max {max_c:.1f}\n→ forma anomala\n(quasi mai accade)"))
            continue
        d = {'x': cx, 'y': cy, 'size': area, 'score': round(mluma/255*100, 2),
             'perim': perim, 'circ': circ, 'luma': mluma}
        if forced: d['forced'] = True
        result.append(d)
    return result, discarded

# ── funzione etichette blob grandi con leader line e anti-overlap ──────────────
_LBL_FONT      = cv2.FONT_HERSHEY_DUPLEX
_LBL_FS        = max(0.38, h / 3200.0)   # font scale proporzionale all'immagine
_LBL_THICK     = 1
_LBL_PAD       = 5                        # padding interno box
_LBL_OFFSET    = max(55, h // 18)         # distanza minima blob→box
_LBL_LINE_GAP  = max(14, int(h / 55))     # interlinea pixel

_placed_boxes = []  # [(x1,y1,x2,y2)] per anti-overlap globale

def _box_overlaps(x1, y1, x2, y2, margin=6):
    for bx1, by1, bx2, by2 in _placed_boxes:
        if x1-margin < bx2 and x2+margin > bx1 and y1-margin < by2 and y2+margin > by1:
            return True
    return False

def _find_free_pos(cx, cy, bw, bh, img_h, img_w):
    """Prova posizioni candidate: sopra/sotto/laterale; shifta ortogonalmente se occupato."""
    # (base_x, base_y, shift_axis): 'h'=shifta orizzontalmente, 'v'=verticalmente
    candidate_bases = [
        (cx - bw//2,        cy - _LBL_OFFSET - bh, 'h'),  # sopra
        (cx - bw//2,        cy + _LBL_OFFSET,       'h'),  # sotto
        (cx + _LBL_OFFSET,  cy - bh//2,             'v'),  # destra
        (cx - _LBL_OFFSET - bw, cy - bh//2,         'v'),  # sinistra
    ]
    step = _LBL_LINE_GAP * 2
    max_shift = max(img_h, img_w)
    for bx0, by0, axis in candidate_bases:
        for shift in range(0, max_shift, step):
            signs = (0,) if shift == 0 else (1, -1)
            for sign in signs:
                if axis == 'h':
                    sx, sy = bx0 + sign * shift, by0
                else:
                    sx, sy = bx0, by0 + sign * shift
                sx = max(2, min(sx, img_w - bw - 2))
                sy = max(2, min(sy, img_h - bh - 2))
                if not _box_overlaps(sx, sy, sx+bw, sy+bh):
                    return sx, sy
    # fallback senza check
    bx0 = max(2, min(cx - bw//2,         img_w - bw - 2))
    by0 = max(2, min(cy - _LBL_OFFSET - bh, img_h - bh - 2))
    return bx0, by0

def _draw_blob_label(img, cx, cy, lines, dot_color, rejected=False):
    """Disegna etichetta grande con box scuro e leader line sottile."""
    ih, iw = img.shape[:2]
    # calcola dimensioni box
    line_sizes = [cv2.getTextSize(ln, _LBL_FONT, _LBL_FS, _LBL_THICK)[0] for ln in lines if ln]
    if not line_sizes:
        return
    bw = max(s[0] for s in line_sizes) + _LBL_PAD * 2
    bh = _LBL_LINE_GAP * len(lines) + _LBL_PAD * 2

    lx, ly = _find_free_pos(cx, cy, bw, bh, ih, iw)
    _placed_boxes.append((lx, ly, lx+bw, ly+bh))

    # punto di aggancio leader line = bordo box più vicino al blob
    anchor_x = lx + bw//2
    anchor_y = ly + bh if cy > ly + bh else ly   # attacca al lato superiore o inferiore
    if abs(cx - lx) < abs(cx - (lx+bw)):
        anchor_x = lx  # bordo sinistro
    elif abs(cx - (lx+bw)) < bw * 0.4:
        anchor_x = lx + bw  # bordo destro

    # leader line: piccolo cerchio sul blob → line → box
    line_col = (110, 110, 110) if rejected else tuple(int(c) for c in dot_color[::-1][:3] if True)
    if isinstance(dot_color, (list, tuple)) and len(dot_color) >= 3:
        line_col = (int(dot_color[0]*0.6), int(dot_color[1]*0.6), int(dot_color[2]*0.6))
    cv2.line(img, (cx, cy), (anchor_x, anchor_y), line_col, 1, cv2.LINE_AA)

    # box sfondo
    bg_col = (30, 20, 20) if rejected else (15, 30, 20)
    border_col = (100, 60, 60) if rejected else (40, 120, 60)
    cv2.rectangle(img, (lx, ly), (lx+bw, ly+bh), bg_col, -1)
    cv2.rectangle(img, (lx, ly), (lx+bw, ly+bh), border_col, 1)

    # testo riga per riga
    txt_col_header = (200, 120, 120) if rejected else (120, 255, 160)
    txt_col_data   = (180, 180, 180) if rejected else (200, 230, 200)
    y_text = ly + _LBL_PAD + _LBL_LINE_GAP
    for i, ln in enumerate(lines):
        col = txt_col_header if i == 0 else txt_col_data
        cv2.putText(img, ln, (lx + _LBL_PAD, y_text),
                    _LBL_FONT, _LBL_FS, col, _LBL_THICK, cv2.LINE_AA)
        y_text += _LBL_LINE_GAP

# ── connectedComponents + filtro + raccolta blob ───────────────────────────────
_all_blobs = []   # (cx, cy, area, perim, circ, luma, short, verbose, dot_color, rejected, side, kind)

for side in ['left','right']:
    n, lmap, stats, cents = cv2.connectedComponentsWithStats(white_masks[side], 8)
    cands, discarded_inner = _filter_circ(
        white_masks[side], lmap, stats, cents, n, gray_inner,
        MIN_CIRC_INNER, MAX_CIRC_INNER, MIN_PERI_INNER, MAX_PERI_INNER, forced=False)
    candidates[side] = cands

    n_lb, lmap_lb, stats_lb, cents_lb = cv2.connectedComponentsWithStats(lb_masks[side], 8)
    lb_cands, discarded_outer = _filter_circ(
        lb_masks[side], lmap_lb, stats_lb, cents_lb, n_lb, gray_outer,
        MIN_CIRC_OUTER, MAX_CIRC_OUTER, MIN_PERI_OUTER, MAX_PERI_OUTER, forced=True)
    lb_candidates[side] = lb_cands
    print(f"    [{side}] inner validi: {len(cands)}  scartati: {len(discarded_inner)}  "
          f"outer LB/RB: {len(lb_cands)}  scartati outer: {len(discarded_outer)}")

    col_main = [0, 255, 120] if side=='left' else [255, 240, 0]
    col_lb_c = [0, 180, 255] if side=='left' else [255, 80, 255]

    # disegna cerchi sul canvas
    for item in discarded_inner:
        cx2, cy2 = item[0], item[1]
        cv2.circle(snap_cc, (cx2, cy2), R, (70, 70, 70), -1)
        cv2.circle(snap_cc, (cx2, cy2), R+1, (120, 60, 60), 1)
        _all_blobs.append(item + ([70, 70, 70], True, side, 'inner'))
    for item in discarded_outer:
        cx2, cy2 = item[0], item[1]
        cv2.circle(snap_cc, (cx2, cy2), R, (60, 50, 70), -1)
        cv2.circle(snap_cc, (cx2, cy2), R+1, (100, 60, 120), 1)
        _all_blobs.append(item + ([60, 50, 70], True, side, 'outer'))
    for d in cands:
        cv2.circle(snap_cc, (d['x'],d['y']), R, col_main, -1)
        cv2.circle(snap_cc, (d['x'],d['y']), R+2, (200,200,200), 1)
        _all_blobs.append((d['x'], d['y'], d['size'], d['perim'], d['circ'], d['luma'],
                           'OK-inner', 'accettato (inner)', col_main, False, side, 'inner'))
    for d in lb_cands:
        cv2.circle(snap_cc, (d['x'],d['y']), R+2, col_lb_c, -1)
        cv2.circle(snap_cc, (d['x'],d['y']), R+4, (255,255,255), 2)
        _all_blobs.append((d['x'], d['y'], d['size'], d['perim'], d['circ'], d['luma'],
                           'OK-outer', 'accettato (outer/LB)', col_lb_c, False, side, 'outer'))

# ── disegna etichette in ordine y (alto→basso) per migliore anti-overlap ──────
_all_blobs_sorted = sorted(_all_blobs, key=lambda b: b[1])  # ordina per cy
for blob in _all_blobs_sorted:
    cx2, cy2, area, perim, circ, luma, short, verbose, dot_col, rejected, side2, kind = blob
    if rejected:
        lines = [
            f"SCARTATO [{kind}]",
            f"motivo: {short}",
            *verbose.split('\n'),
            f"area={area}px  P={perim:.0f}px",
            f"circ={circ:.3f}  luma={luma:.0f}",
        ]
    else:
        lines = [
            f"OK [{kind}] {side2}",
            f"area={area}px",
            f"perim={perim:.0f}px",
            f"circ={circ:.3f}",
            f"luma={luma:.0f} ({luma/255*100:.0f}%)",
        ]
    _draw_blob_label(snap_cc, cx2, cy2, lines, dot_col, rejected=rejected)

# Tutti i candidati selezionati (inner + outer)
selected_all = {side: candidates[side] + lb_candidates[side] for side in ['left','right']}

# Aggiungi campo 'eyebrow' a tutti i blob prima di NMS
for side in ['left','right']:
    for d in selected_all[side]:
        d['eyebrow'] = side

# ── NMS: rimuove blob duplicati troppo vicini GLOBALMENTE ─────────────────────
def _nms_by_distance(pts, min_dist):
    """NMS per distanza: rimuove punti troppo vicini, tenendo quello con score più alto.
    I punti forzati (flag 'forced'=True) vengono sempre mantenuti.
    Criterio: score più alto, poi circolarità più alta."""
    if min_dist <= 0:
        return pts
    ordered = sorted(pts, key=lambda d: (0 if d.get('forced') else 1, -d.get('score', 0), -d.get('circ', 0)))
    kept = []
    rejected = []
    for p in ordered:
        too_close = False
        closest_dist = float('inf')
        closest_blob = None
        for k in kept:
            dist = math.hypot(p['x'] - k['x'], p['y'] - k['y'])
            if dist <= min_dist:  # <= per includere anche distanza esatta
                too_close = True
                if dist < closest_dist:
                    closest_dist = dist
                    closest_blob = k
        if not too_close:
            kept.append(p)
        else:
            rejected.append((p, closest_blob, closest_dist))
    
    if rejected:
        print(f"    [NMS DEBUG] Eliminati {len(rejected)} blob:")
        for p, k, dist in rejected[:10]:  # Mostra primi 10 eliminati
            print(f"      • ({p['x']},{p['y']}) score={p.get('score',0):.0f} eliminato: troppo vicino a ({k['x']},{k['y']}) dist={dist:.1f}px")
    
    return kept

print(f"\n[6b] NMS deduplicazione blob vicini GLOBALE (distanza minima {MIN_DISTANCE} px)")
# Combina tutti i blob di entrambi i lati
all_blobs_combined = selected_all['left'] + selected_all['right']
before = len(all_blobs_combined)
# Applica NMS globalmente
all_blobs_post_nms = _nms_by_distance(all_blobs_combined, MIN_DISTANCE)
after = len(all_blobs_post_nms)
print(f"    Totale: {before} → {after} blob (NMS globale su entrambi i lati)")
# Ri-separa per lato
selected_all = {
    'left': [d for d in all_blobs_post_nms if d.get('eyebrow') == 'left'],
    'right': [d for d in all_blobs_post_nms if d.get('eyebrow') == 'right']
}
print(f"    [left] {len(selected_all['left'])} blob finali | [right] {len(selected_all['right'])} blob finali")

# ── PASSO 7: rimappatura coordinate → spazio originale ────────────────────────
print(f"\n[7] rimappatura coordinate → spazio originale (scala_inv={1/_scale:.4f})")
_inv = _orig_w / TARGET_WIDTH
all_dots_orig = []
for side in ['left','right']:
    for d in selected_all[side]:
        dd = dict(d)
        dd['x'] = int(round(d['x'] * _inv))
        dd['y'] = int(round(d['y'] * _inv))
        dd['eyebrow'] = side
        all_dots_orig.append(dd)
print(f"    punti totali rimappati: {len(all_dots_orig)}")

# ── PASSO 8: sort_points_anatomical() ────────────────────────────────────────
print(f"\n[8] sort_points_anatomical()  →  LC1,LA0,LA,LC,LB / RC1,RB,RC,RA,RA0")
left_pts  = sort_anatomical([d for d in all_dots_orig if d['eyebrow']=='left'],  is_left=True)
right_pts = sort_anatomical([d for d in all_dots_orig if d['eyebrow']=='right'], is_left=False)
for lbl, pts in [('Sx', left_pts), ('Dx', right_pts)]:
    names = " → ".join(f"{d.get('anatomical_name','?')}({d['x']},{d['y']})" for d in pts)
    print(f"    [{lbl}]: {names}")

snap_anat = bgr2rgb(img_orig_bgr).copy()
for pts, col_line in [(left_pts,(0,255,120)), (right_pts,(255,240,0))]:
    xy = [(d['x'],d['y']) for d in pts]
    for i in range(len(xy)-1):
        cv2.line(snap_anat, xy[i], xy[i+1], col_line, 2, cv2.LINE_AA)
    for d in pts:
        aname = d.get('anatomical_name','?')
        rgb_c = hex2rgb(ANAT_COLORS.get(aname,'#FFFFFF'))
        r = max(10, int(d['size']**0.5)+4)
        cv2.circle(snap_anat, (d['x'],d['y']), r+3, (0,0,0), -1)
        cv2.circle(snap_anat, (d['x'],d['y']), r, rgb_c, -1)
        cv2.putText(snap_anat, aname, (d['x']+r+4,d['y']-2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1, cv2.LINE_AA)

# ── PASSO 9: overlay finale ───────────────────────────────────────────────────
print(f"\n[9] generate_white_dots_overlay() → overlay PNG finale")
snap_final = bgr2rgb(img_orig_bgr).copy()

# Contorno maschere espanse (riscalato all'originale)
k_orig = cv2.getStructuringElement(
    cv2.MORPH_ELLIPSE,
    (int(OUTER_PX/_scale)*2+1,)*2)
for side, mask_o in [('left', res_dlib['left_mask']),
                     ('right', res_dlib['right_mask'])]:
    # Le maschere dlib sono state calcolate sul frame 1200px: riscaliamo
    mask_orig_size = cv2.resize(mask_o, (_orig_w, _orig_h),
                                interpolation=cv2.INTER_NEAREST)
    exp_o = cv2.dilate(mask_orig_size, k_orig, iterations=1)
    cnts, _ = cv2.findContours(exp_o, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        col = (0,200,80) if side=='left' else (200,200,0)
        cv2.drawContours(snap_final, [max(cnts,key=cv2.contourArea)], -1, col, 2, cv2.LINE_AA)

for pts, col_line in [(left_pts,(0,255,120)), (right_pts,(255,240,0))]:
    xy = [(d['x'],d['y']) for d in pts]
    for i in range(len(xy)-1):
        cv2.line(snap_final, xy[i], xy[i+1], col_line, 2, cv2.LINE_AA)
    for d in pts:
        aname = d.get('anatomical_name','?')
        rgb_c = hex2rgb(ANAT_COLORS.get(aname,'#FFFFFF'))
        r = max(11, int(d['size']**0.5)+5)
        cv2.circle(snap_final, (d['x'],d['y']), r+3, (0,0,0), -1)
        cv2.circle(snap_final, (d['x'],d['y']), r, rgb_c, -1)
        cv2.circle(snap_final, (d['x'],d['y']), r, (255,255,255), 1)
        label = f"{aname}  sc={d.get('score',0):.0f}"
        pos = (d['x']+r+5, d['y']+5)
        cv2.putText(snap_final, label, pos, cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (0,0,0), 3, cv2.LINE_AA)
        cv2.putText(snap_final, label, pos, cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (255,255,255), 1, cv2.LINE_AA)

# ═════════════════════════════════════════════════════════════════════════════
#  GRIGLIA MATPLOTLIB
#  Layout 3 colonne: [passo | ingresso] [uscita / risultato] [info testuale]
# ═════════════════════════════════════════════════════════════════════════════

def make_info_panel(ax, lines, title=''):
    ax.set_facecolor('#090915')
    ax.axis('off')
    if title:
        ax.set_title(title, fontsize=9, fontweight='bold', color='white', pad=3)
    y = 0.97
    for txt, color, size in lines:
        ax.text(0.03, y, txt, transform=ax.transAxes, fontsize=size,
                color=color, va='top', ha='left', fontfamily='monospace',
                wrap=True)
        y -= 0.065
        if y < 0.02:
            break

rows = [
    # (titolo_sx, img_sx, border_sx,
    #  titolo_dx, img_dx, border_dx,
    #  info_lines, info_title)
    (
        f"STEP 1 — INPUT\nOriginale  {_orig_w}×{_orig_h}px",
        snap_orig, '#446688',
        f"STEP 1 — OUTPUT\nresize → {TARGET_WIDTH}px",
        snap_resized, '#44aa88',
        [
            ("process_green_dots_analysis()", '#88ccff', 8),
            ("  ↓", '#888888', 7),
            ("_detect_white_dots_v3(img_bgr)", '#88ccff', 8),
            ("", '#888888', 7),
            (f"PRIMA OPERAZIONE:", '#ffdd88', 7.5),
            (f"cv2.resize(img,", '#cccccc', 7),
            (f"  ({TARGET_WIDTH}, h*scale),", '#cccccc', 7),
            (f"  INTER_AREA)", '#cccccc', 7),
            (f"scala = {_scale:.4f}", '#aaffaa', 7),
            (f"output: {w}×{h} px", '#aaffaa', 7),
            ("", '#888888', 7),
            ("Perché: normalizza risoluzione", '#888888', 7),
            ("tra webcam/foto/video.", '#888888', 7),
        ],
        "Funzione chiamante + resize"
    ),
    (
        f"STEP 2 — INPUT\nFrame {w}×{h}px (dopo resize)",
        snap_resized, '#446688',
        "STEP 2 — OUTPUT\ndlib 68 landmark → maschera Sx/Dx",
        snap_dlib, '#44aa88',
        [
            ("extract_eyebrows_from_array(", '#88ccff', 8),
            ("  img_bgr,", '#cccccc', 7),
            ("  predictor_path=_dat)", '#cccccc', 7),
            ("", '#888888', 7),
            ("Richiede: dlib + shape_predictor", '#ffdd88', 7.5),
            ("_68_face_landmarks.dat", '#ffdd88', 7),
            ("", '#888888', 7),
            (f"maschera Sx: {int(np.sum(left_mask>0))} px", '#aaffaa', 7),
            (f"maschera Dx: {int(np.sum(right_mask>0))} px", '#aaffaa', 7),
            ("", '#888888', 7),
            ("Verde = sopracciglio sinistro", '#00ff80', 7),
            ("Giallo = sopracciglio destro", '#ffee00', 7),
        ],
        "extract_eyebrows_from_array()"
    ),
    (
        "STEP 3 — INPUT\nGrayscale raw",
        snap_gray_raw, '#446688',
        "STEP 3 — OUTPUT\nGrayscale + highlight boost",
        snap_gray_clahe, '#44aa88',
        [
            ("HIGHLIGHT BOOST", '#ffdd88', 8),
            ("Sostituisce CLAHE: invece di", '#888888', 7),
            ("equalizzare tutto, spinge solo i", '#888888', 7),
            ("toni già chiari verso il bianco.", '#888888', 7),
            ("", '#888888', 6),
            ("Formula per ogni zona:", '#ffdd88', 7.5),
            ("  g_out = g + S*(255-g)  se g >= T", '#88ccff', 7),
            ("  g_out = g              altrimenti", '#888888', 7),
            ("", '#888888', 6),
            ("── INNER (zona principale) ─────", '#44aaff', 7.5),
            (f"  thresh  T={HIGHLIGHT_THRESH_INNER}  → pixel >= T potenziati", '#cccccc', 7),
            (f"  strength S={HIGHLIGHT_STRENGTH_INNER}  → boost {int(HIGHLIGHT_STRENGTH_INNER*100)}%", '#cccccc', 7),
            (f"  ↑T = meno pixel mossi (solo brillanti)", '#888888', 6.5),
            (f"  ↑S = boost più aggressivo", '#888888', 6.5),
            (f"  px potenziati: {int(np.sum(mask_hi_inner))}", '#aaffaa', 7),
            (f"  luma raw→inner: {gray_raw.mean():.1f}→{gray_inner.mean():.1f}", '#aaffaa', 7),
            ("── OUTER (strip LB/RB) ─────────", '#ffaa44', 7.5),
            (f"  thresh  T={HIGHLIGHT_THRESH_OUTER}  (più basso = più sensibile)", '#cccccc', 7),
            (f"  strength S={HIGHLIGHT_STRENGTH_OUTER}  (più lieve per evitare falsi)", '#cccccc', 7),
            (f"  px potenziati: {int(np.sum(mask_hi_outer))}", '#ffcc88', 7),
            (f"  luma raw→outer: {gray_raw.mean():.1f}→{gray_outer.mean():.1f}", '#ffcc88', 7),
        ],
        "Grayscale + highlight boost"
    ),
    (
        "STEP 4 — INPUT\ngray boosted + maschere dlib",
        snap_gray_clahe, '#446688',
        f"STEP 4 — OUTPUT\ndilate({OUTER_PX}px) + strip LB/RB (su gray boosted)",
        snap_zones, '#44aa88',
        [
            (f"k = MORPH_ELLIPSE({OUTER_PX*2+1}×{OUTER_PX*2+1}px)", '#88ccff', 7.5),
            ("expanded = cv2.dilate(mask, k)", '#88ccff', 7.5),
            ("", '#888888', 7),
            ("strip LB/RB (per ogni lato):", '#ffdd88', 7.5),
            ("  xs = np.where(mask>0)", '#cccccc', 7),
            ("  x_min, x_max = xs.min,max", '#cccccc', 7),
            ("  Sx: col <= x_min + OUTER_PX", '#cccccc', 7),
            ("  Dx: col >= x_max - OUTER_PX", '#cccccc', 7),
            ("", '#888888', 7),
            ("Ciano/Verde = zona espansa", '#aaffaa', 7),
            ("Arancio = strip LB/RB", '#ffaa44', 7),
            ("Grigio = interno maschera dlib", '#888888', 7),
            ("Contorno = bordo zona espansa", '#aaaaaa', 7),
        ],
        f"dilate(OUTER_PX={OUTER_PX})"
    ),
    (
        "STEP 5 — INPUT\nZona espansa (gray CLAHE)",
        snap_zones, '#446688',
        f"STEP 5 — OUTPUT\nSoglia luma → pixel candidati",
        snap_thresh, '#44aa88',
        [
            ("SOGLIA LUMA — due range separati", '#ffdd88', 8),
            ("Seleziona pixel abbastanza chiari", '#888888', 7),
            ("nella zona di interesse.", '#888888', 7),
            ("", '#888888', 6),
            ("── INNER (zona espansa intera) ──", '#44aaff', 7.5),
            (f"  {LUMA_MIN} ≤ gray_inner ≤ {LUMA_MAX}", '#88ccff', 7),
            ("  AND pixel dentro expanded mask", '#cccccc', 7),
            (f"  ↑LUMA_MIN = meno falsi positivi", '#888888', 6.5),
            (f"  ↓LUMA_MIN = più candidati (rischio rumore)", '#888888', 6.5),
            (f"  Sx: {int(np.sum(white_masks['left']>0))} px   Dx: {int(np.sum(white_masks['right']>0))} px", '#aaffaa', 7),
            ("── OUTER / strip LB/RB ──────────", '#ffaa44', 7.5),
            (f"  {LUMA_LB} ≤ gray_outer ≤ {LUMA_MAX_LB}", '#ffaa88', 7),
            ("  AND pixel nella strip estrema", '#cccccc', 7),
            ("  Soglia più bassa: catch peli/",  '#888888', 6.5),
            ("  sopracciglia esterne (più scure)", '#888888', 6.5),
            (f"  Sx: {int(np.sum(lb_masks['left']>0))} px   Dx: {int(np.sum(lb_masks['right']>0))} px", '#ffcc88', 7),
            ("Verde/Giallo=inner  Ciano/Magenta=outer", '#888888', 6.5),
        ],
        "Soglia luma"
    ),
    (
        "STEP 6 — INPUT\nPixel sogliati",
        snap_thresh, '#446688',
        f"STEP 6 — OUTPUT\nCC + filtro circ+peri inner/outer",
        snap_cc, '#44aa88',
        [
            ("CC + FILTRO CIRCOLARITÀ+PERIMETRO", '#ffdd88', 8),
            ("connectedComponents(mask, 8conn)", '#88ccff', 7),
            ("→ individua blob contigui", '#888888', 6.5),
            ("", '#888888', 6),
            ("circ = 4π·area / perimeter²", '#ffdd88', 7.5),
            ("  1.0 = cerchio perfetto", '#888888', 6.5),
            ("  0.785 = quadrato", '#888888', 6.5),
            ("  <0.4 = molto allungato (capello)", '#888888', 6.5),
            ("", '#888888', 6),
            ("── INNER ────────────────────────", '#44aaff', 7.5),
            (f"  circ  [{MIN_CIRC_INNER:.1f} – {MAX_CIRC_INNER:.1f}]", '#88ccff', 7),
            (f"  peri  [{MIN_PERI_INNER} – {MAX_PERI_INNER}px]", '#88ccff', 7),
            (f"  ↑min_circ = solo blob rotondi", '#888888', 6.5),
            (f"  ↑max_peri = cattura blob più grandi", '#888888', 6.5),
            (f"  Sx: {len(candidates['left'])} OK  Dx: {len(candidates['right'])} OK", '#aaffaa', 7),
            ("── OUTER (strip LB/RB) ──────────", '#ffaa44', 7.5),
            (f"  circ  [{MIN_CIRC_OUTER:.1f} – {MAX_CIRC_OUTER:.1f}]  (più permissivo)", '#ffaa88', 7),
            (f"  peri  [{MIN_PERI_OUTER} – {MAX_PERI_OUTER}px]  (dimensioni minori)", '#ffaa88', 7),
            (f"  Sx: {len(lb_candidates['left'])} OK  Dx: {len(lb_candidates['right'])} OK", '#ffcc88', 7),
            ("Etichette su ogni blob: area,", '#888888', 6.5),
            ("perim, circ, luma, motivo scarto", '#888888', 6.5),
        ],
        "CC + filtro circolarità+perimetro"
    ),
    (
        f"STEP 7 — INPUT\nCoordinate a 1200px",
        snap_cc, '#446688',
        "STEP 7 — OUTPUT\nCoordinate → spazio originale",
        snap_cc, '#44aa88',
        [
            ("Rimappatura coordinate:", '#ffdd88', 7.5),
            ("inv_scale = orig_w / TARGET_WIDTH", '#cccccc', 7),
            (f"inv_scale = {_orig_w} / {TARGET_WIDTH}", '#cccccc', 7),
            (f"         = {_inv:.4f}", '#aaffaa', 7),
            ("d['x'] = round(d['x'] * inv)", '#cccccc', 7),
            ("d['y'] = round(d['y'] * inv)", '#cccccc', 7),
            ("", '#888888', 7),
            (f"Tutti i {len(all_dots_orig)} punti rimappati", '#aaffaa', 7),
            (f"verso spazio {_orig_w}×{_orig_h}px", '#aaffaa', 7),
        ],
        f"Rimappatura inv_scale={_inv:.4f}"
    ),
    (
        "STEP 8 — INPUT\nPunti rimappati (spazio orig)",
        snap_cc, '#446688',
        "STEP 8 — OUTPUT\nOrdine anatomico",
        snap_anat, '#44aa88',
        [
            ("sort_points_anatomical(pts,", '#88ccff', 7.5),
            ("  is_left=True/False)", '#cccccc', 7),
            ("", '#888888', 7),
            ("Ordine sinistro:", '#ffdd88', 7.5),
            ("  LC1 → LA0 → LA → LC → LB", '#cccccc', 7),
            ("Ordine destro:", '#ffdd88', 7.5),
            ("  RC1 → RB → RC → RA → RA0", '#cccccc', 7),
            ("", '#888888', 7),
            (f"Sx: {len(left_pts)} punti   Dx: {len(right_pts)} punti", '#aaffaa', 7),
            ("", '#888888', 7),
        ] + [(f"{d.get('anatomical_name','?')}: ({d['x']},{d['y']}) sc={d.get('score',0):.0f}",
              '#'+ANAT_COLORS.get(d.get('anatomical_name','?'),'#888888')[1:], 7)
             for d in left_pts+right_pts],
        "sort_points_anatomical()"
    ),
    (
        "STEP 9 — INPUT\nPunti anatomici",
        snap_anat, '#446688',
        "STEP 9 — OUTPUT FINALE\ngenerate_white_dots_overlay()",
        snap_final, '#4488ff',
        [
            ("generate_white_dots_overlay(", '#88ccff', 7.5),
            ("  pil_image.size, formatted_dots,", '#cccccc', 7),
            ("  left_polygon, right_polygon)", '#cccccc', 7),
            ("", '#888888', 7),
            ("Overlay PNG trasparente inviato", '#ffdd88', 7.5),
            ("al frontend (canvas Fabric.js).", '#cccccc', 7),
            ("", '#888888', 7),
            ("Contorno = maschera espansa", '#888888', 7),
            ("Linee = ordine anatomico", '#888888', 7),
            ("Pallini = etichette colorate", '#888888', 7),
            ("", '#888888', 7),
            (f"Totale punti: {len(left_pts)+len(right_pts)}", '#aaffaa', 7.5),
            (f"Sx={len(left_pts)}  Dx={len(right_pts)}", '#aaffaa', 7),
        ],
        "Overlay finale (frontend)"
    ),
]

NROWS = len(rows)
NCOLS = 3
fig, axes = plt.subplots(NROWS, NCOLS, figsize=(22, NROWS * 4.8))
fig.patch.set_facecolor('#090915')
fig.suptitle(
    'DEBUG «TROVA DIFFERENZE»  —  _detect_white_dots_v3()  '
    '|  webapp/api/main.py\n'
    f'IMG_8116 - Copia.jpg   TARGET={TARGET_WIDTH}px  OUTER={OUTER_PX}  '
    f'LUMA={LUMA_MIN}-{LUMA_MAX}  LB={LUMA_LB}-{LUMA_MAX_LB}  '
    f'hiboost inner(t={HIGHLIGHT_THRESH_INNER} s={HIGHLIGHT_STRENGTH_INNER}) '
    f'outer(t={HIGHLIGHT_THRESH_OUTER} s={HIGHLIGHT_STRENGTH_OUTER})  '
    f'inner circ[{MIN_CIRC_INNER:.1f}-{MAX_CIRC_INNER:.1f}] peri[{MIN_PERI_INNER}-{MAX_PERI_INNER}]  '
    f'outer circ[{MIN_CIRC_OUTER:.1f}-{MAX_CIRC_OUTER:.1f}] peri[{MIN_PERI_OUTER}-{MAX_PERI_OUTER}]',
    fontsize=10, fontweight='bold', color='white', y=0.999)

for row_idx, (t0, img0, b0, t1, img1, b1, info_lines, info_title) in enumerate(rows):
    ax0 = axes[row_idx][0]
    ax1 = axes[row_idx][1]
    ax2 = axes[row_idx][2]
    annotate(ax0, shrink(img0), t0, border=b0)
    annotate(ax1, shrink(img1), t1, border=b1)
    make_info_panel(ax2, info_lines, info_title)

plt.tight_layout(rect=[0, 0, 1, 0.998])
plt.savefig(OUT_GRID, dpi=115, bbox_inches='tight',
            facecolor='#090915', edgecolor='none')
plt.close()
print(f"\n[OUTPUT] Griglia debug → {OUT_GRID}")

# ─────────────────────────────────────────────────────────────────────────────
#  OVERLAY FINALE ALTA RISOLUZIONE
# ─────────────────────────────────────────────────────────────────────────────
fig2, ax2 = plt.subplots(figsize=(_orig_w/120, _orig_h/120))
fig2.patch.set_facecolor('black')
ax2.imshow(snap_final)
ax2.set_title(
    'RISULTATO FINALE — TROVA DIFFERENZE  |  _detect_white_dots_v3()\n'
    f'IMG_8116 - Copia.jpg   '
    f'LUMA={LUMA_MIN}-{LUMA_MAX}  LB={LUMA_LB}-{LUMA_MAX_LB}  '
    f'hiboost inner(t={HIGHLIGHT_THRESH_INNER} s={HIGHLIGHT_STRENGTH_INNER}) '
    f'outer(t={HIGHLIGHT_THRESH_OUTER} s={HIGHLIGHT_STRENGTH_OUTER})  →  {len(left_pts)+len(right_pts)} punti',
    fontsize=12, fontweight='bold', color='white', pad=10)
ax2.axis('off')
patches = [mpatches.Patch(color=c, label=n) for n,c in ANAT_COLORS.items()]
ax2.legend(handles=patches, loc='lower left', ncol=5, fontsize=8,
           framealpha=0.85, facecolor='#111111', labelcolor='white',
           title='Etichette anatomiche', title_fontsize=9)
plt.tight_layout()
plt.savefig(OUT_FINAL, dpi=200, bbox_inches='tight',
            facecolor='black', edgecolor='none')
plt.close()
print(f"[OUTPUT] Overlay finale    → {OUT_FINAL}")

# ─────────────────────────────────────────────────────────────────────────────
#  RIEPILOGO
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("  RIEPILOGO PUNTI ANATOMICI")
print("="*72)
print(f"  {'Nome':<5} {'x':>6} {'y':>6}  {'score':>7}  {'size':>5}  Lato")
print("  "+"-"*42)
for d in left_pts:
    print(f"  {d.get('anatomical_name','?'):<5} {d['x']:>6} {d['y']:>6}  "
          f"{d.get('score',0):>6.1f}%  {d['size']:>5}  <- Sx")
print("  "+"-"*42)
for d in right_pts:
    print(f"  {d.get('anatomical_name','?'):<5} {d['x']:>6} {d['y']:>6}  "
          f"{d.get('score',0):>6.1f}%  {d['size']:>5}  Dx ->")
print("="*72)
print(f"\n  PARAMETRI USATI:")
print(f"    TARGET_WIDTH       = {TARGET_WIDTH}px")
print(f"    OUTER_PX           = {OUTER_PX}  (dilate zona intera)")
print(f"    HIGHLIGHT_THRESH_INNER   = {HIGHLIGHT_THRESH_INNER}")
print(f"    HIGHLIGHT_STRENGTH_INNER = {HIGHLIGHT_STRENGTH_INNER}")
print(f"    HIGHLIGHT_THRESH_OUTER   = {HIGHLIGHT_THRESH_OUTER}")
print(f"    HIGHLIGHT_STRENGTH_OUTER = {HIGHLIGHT_STRENGTH_OUTER}")
print(f"    LUMA_MIN/MAX       = {LUMA_MIN}..{LUMA_MAX}  (candidati principali)")
print(f"    LUMA_LB/MAX        = {LUMA_LB}..{LUMA_MAX_LB}  (strip LB/RB)")
print(f"    CIRC inner         = {MIN_CIRC_INNER:.1f}..{MAX_CIRC_INNER:.1f}  (zona principale)")
print(f"    PERI inner         = {MIN_PERI_INNER}..{MAX_PERI_INNER} px")
print(f"    CIRC outer         = {MIN_CIRC_OUTER:.1f}..{MAX_CIRC_OUTER:.1f}  (strip LB/RB)")
print(f"    PERI outer         = {MIN_PERI_OUTER}..{MAX_PERI_OUTER} px")
print()
