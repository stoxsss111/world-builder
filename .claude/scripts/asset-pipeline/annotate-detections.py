"""
Draw Set-of-Mark style numbered colored dots on controls/top.png from
controls/detections.json. Output: controls/top-marked.png — a visualisation
the agent (Claude) reviews to spot misclassifications + missing instances
before placement.

Usage:
    python annotate-detections.py worlds/<slug>

Reads:
    worlds/<slug>/controls/top.png
    worlds/<slug>/controls/detections.json
Writes:
    worlds/<slug>/controls/top-marked.png
    worlds/<slug>/controls/top-marked-legend.json
"""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if len(sys.argv) < 2:
    print("usage: annotate-detections.py <world-folder>")
    sys.exit(1)
WORLD = Path(sys.argv[1])
top_path = WORLD / "controls" / "top.png"
det_path = WORLD / "controls" / "detections.json"
out_path = WORLD / "controls" / "top-marked.png"
legend_path = WORLD / "controls" / "top-marked-legend.json"

img = Image.open(top_path).convert("RGB")
W, H = img.size
draw = ImageDraw.Draw(img, "RGBA")

# Per-class colors (consistent palette so the legend is readable)
CLASS_COLORS = {
    "palm tree":       (51, 204, 51),    # green
    "stone arch":      (220, 90, 220),   # magenta
    "tiki hut":        (255, 165, 0),    # orange
    "tiki torch":      (255, 80, 80),    # red
    "campfire":        (255, 60, 60),    # warm red
    "log stump":       (139, 95, 50),    # brown
    "treasure chest":  (255, 215, 0),    # gold
    "boulder":         (130, 130, 130),  # gray
    "flower":          (255, 100, 200),  # pink
    "shell":           (255, 230, 180),  # cream
    "stairs":          (95, 50, 30),     # dark brown
}
DEFAULT_COLOR = (0, 200, 255)

try:
    font = ImageFont.truetype("arial.ttf", 16)
except IOError:
    font = ImageFont.load_default()

det = json.load(open(det_path, "r", encoding="utf-8"))
legend = []
mark_idx = 0
for entry in det.get("classes", []):
    cls = entry.get("class")
    if not cls: continue
    color = CLASS_COLORS.get(cls, DEFAULT_COLOR)
    for inst in entry.get("instances", []):
        cx = int(inst["cx_px"]); cy = int(inst["cy_px"])
        w = int(inst.get("w_px", 0)); h = int(inst.get("h_px", 0))
        mark_idx += 1
        # bbox outline
        if w and h:
            x0 = cx - w//2; y0 = cy - h//2
            draw.rectangle([x0, y0, x0+w, y0+h], outline=color + (255,), width=2)
        # filled dot
        r = 10
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color + (255,), outline=(0,0,0,255), width=2)
        # number label
        label = str(mark_idx)
        # text shadow / fill
        try:
            tw, th = draw.textbbox((0,0), label, font=font)[2:]
        except Exception:
            tw, th = (10, 14)
        draw.text((cx-tw//2, cy-th//2), label, fill=(0,0,0,255), font=font)
        legend.append({
            "mark": mark_idx, "class": cls, "cx_px": cx, "cy_px": cy, "w_px": w, "h_px": h,
            "color_rgb": list(color)
        })

img.save(out_path)
with open(legend_path, "w", encoding="utf-8") as f:
    json.dump({"image": str(out_path), "image_size": [W, H], "marks": legend}, f, indent=2)
print(f"wrote {out_path}  ({mark_idx} marks)")
