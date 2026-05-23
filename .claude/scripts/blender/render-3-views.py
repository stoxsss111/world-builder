"""
The ONLY renderer the place-and-iterate loop uses.

Takes a scene bounding box (xmin, ymin, zmin, xmax, ymax, zmax) and an iteration
number, then renders three camera angles that exactly mirror the three nano-banana
control views (top, front-left-45, front-right-45). The three panels are stitched
into one labeled composite PNG.

Caller invokes via execute_blender_code, after setting these globals in the
exec namespace:

    BBOX = (xmin, ymin, zmin, xmax, ymax, zmax)   # tuple of 6 floats
    ITER = 7                                       # int
    OUT_DIR = Path("worlds/<slug>/iterations")     # pathlib.Path
    CONTROLS_DIR = Path("worlds/<slug>/controls")  # for six-up overlay; optional
    PANEL_W = 640                                  # per-panel width (default 640)
    PANEL_H = 480                                  # per-panel height (default 480)

The composite is saved to OUT_DIR / f"{ITER:03d}.png" and (if CONTROLS_DIR is
provided and has top.png/fl45.png/fr45.png) a six-up image is also saved as
OUT_DIR / f"{ITER:03d}-vs-controls.png".
"""
import bpy
import math
import mathutils
import os
from pathlib import Path

# ---- inputs (overridable from caller scope) -------------------------------
try:
    BBOX
except NameError:
    BBOX = (-7.0, -6.0, 0.0, 7.0, 4.0, 5.0)
try:
    ITER
except NameError:
    ITER = 1
try:
    OUT_DIR
except NameError:
    OUT_DIR = Path(".")
try:
    CONTROLS_DIR
except NameError:
    CONTROLS_DIR = None
try:
    PANEL_W
except NameError:
    PANEL_W = 640
try:
    PANEL_H
except NameError:
    PANEL_H = 480

OUT_DIR = Path(OUT_DIR)
OUT_DIR.mkdir(parents=True, exist_ok=True)

xmin, ymin, zmin, xmax, ymax, zmax = BBOX
cx = (xmin + xmax) / 2.0
cy = (ymin + ymax) / 2.0
cz = (zmin + zmax) / 2.0
sx = xmax - xmin
sy = ymax - ymin
sz = zmax - zmin
diag = math.sqrt(sx * sx + sy * sy + sz * sz)

# Engine / render settings — Eevee Next, fast samples
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
try:
    scene.eevee.taa_render_samples = 16
except AttributeError:
    pass
scene.render.resolution_x = PANEL_W
scene.render.resolution_y = PANEL_H
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'


def add_or_get_camera(name, location, target, lens=35, ortho=False, ortho_scale=10):
    cam_obj = bpy.data.objects.get(name)
    if cam_obj is None:
        cam_data = bpy.data.cameras.new(name)
        cam_obj = bpy.data.objects.new(name, cam_data)
        scene.collection.objects.link(cam_obj)
    if ortho:
        cam_obj.data.type = 'ORTHO'
        cam_obj.data.ortho_scale = ortho_scale
    else:
        cam_obj.data.type = 'PERSP'
        cam_obj.data.lens = lens
    cam_obj.location = location
    direction = mathutils.Vector(target) - mathutils.Vector(location)
    cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return cam_obj


def render_view(cam, out_path):
    scene.camera = cam
    scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)
    return out_path


# Panel margin so the bbox sits comfortably inside the frame
PAD = 1.15
ortho_scale = max(sx, sy) * PAD

# TOP-DOWN ortho — camera straight above bbox centre
top_cam = add_or_get_camera(
    "WB_RENDER3_TOP",
    location=(cx, cy, max(cz + diag, zmax + 2.0)),
    target=(cx, cy, cz),
    ortho=True,
    ortho_scale=ortho_scale,
)

# FRONT-LEFT-45° — perspective from -X, -Y, +Z
# Use diag to back the camera off so the whole bbox fits at lens=35
fl_dist = diag * 1.05
fl_elev = math.radians(40)
fl_az = math.radians(225)  # front-left in scene-XY (back from camera POV)
fl_loc = (
    cx + fl_dist * math.cos(fl_elev) * math.cos(fl_az),
    cy + fl_dist * math.cos(fl_elev) * math.sin(fl_az),
    cz + fl_dist * math.sin(fl_elev),
)
fl_cam = add_or_get_camera(
    "WB_RENDER3_FL45",
    location=fl_loc,
    target=(cx, cy, cz),
    lens=35,
)

# FRONT-RIGHT-45°
fr_az = math.radians(315)
fr_loc = (
    cx + fl_dist * math.cos(fl_elev) * math.cos(fr_az),
    cy + fl_dist * math.cos(fl_elev) * math.sin(fr_az),
    cz + fl_dist * math.sin(fl_elev),
)
fr_cam = add_or_get_camera(
    "WB_RENDER3_FR45",
    location=fr_loc,
    target=(cx, cy, cz),
    lens=35,
)

top_path = OUT_DIR / f"{ITER:03d}-top.png"
fl_path  = OUT_DIR / f"{ITER:03d}-fl45.png"
fr_path  = OUT_DIR / f"{ITER:03d}-fr45.png"
render_view(top_cam, top_path)
render_view(fl_cam, fl_path)
render_view(fr_cam, fr_path)

# Composite three panels in a labeled row
from PIL import Image, ImageDraw
top  = Image.open(top_path)
fl   = Image.open(fl_path)
fr   = Image.open(fr_path)
w, h = top.size
gap = 8
label_h = 28
canvas = Image.new("RGB", (w * 3 + gap * 2, h + label_h), (10, 10, 12))
canvas.paste(top, (0, label_h))
canvas.paste(fl,  (w + gap, label_h))
canvas.paste(fr,  (w * 2 + gap * 2, label_h))
draw = ImageDraw.Draw(canvas)
draw.text((8, 6),                       "TOP (ortho)",         fill=(240, 240, 240))
draw.text((w + gap + 8, 6),             "FRONT-LEFT 45",       fill=(240, 240, 240))
draw.text((w * 2 + gap * 2 + 8, 6),     "FRONT-RIGHT 45",      fill=(240, 240, 240))
composite_path = OUT_DIR / f"{ITER:03d}.png"
canvas.save(composite_path)

# Optional six-up: control views on top row, current renders on bottom row
sixup_path = None
if CONTROLS_DIR is not None:
    CONTROLS_DIR = Path(CONTROLS_DIR)
    ctop = CONTROLS_DIR / "top.png"
    cfl  = CONTROLS_DIR / "fl45.png"
    cfr  = CONTROLS_DIR / "fr45.png"
    if ctop.exists() and cfl.exists() and cfr.exists():
        c_top = Image.open(ctop).resize((w, h))
        c_fl  = Image.open(cfl).resize((w, h))
        c_fr  = Image.open(cfr).resize((w, h))
        six = Image.new("RGB", (w * 3 + gap * 2, h * 2 + label_h * 2 + gap), (10, 10, 12))
        # row 1 — controls
        six.paste(c_top, (0, label_h))
        six.paste(c_fl,  (w + gap, label_h))
        six.paste(c_fr,  (w * 2 + gap * 2, label_h))
        # row 2 — current renders
        y2 = label_h + h + gap + label_h
        six.paste(top, (0, y2))
        six.paste(fl,  (w + gap, y2))
        six.paste(fr,  (w * 2 + gap * 2, y2))
        d2 = ImageDraw.Draw(six)
        d2.text((8, 6),                   "CONTROL  top",       fill=(180, 220, 180))
        d2.text((w + gap + 8, 6),         "CONTROL  fl-45",     fill=(180, 220, 180))
        d2.text((w * 2 + gap * 2 + 8, 6), "CONTROL  fr-45",     fill=(180, 220, 180))
        d2.text((8, label_h + h + gap + 6),                   f"ITER {ITER:03d}  top",   fill=(220, 220, 180))
        d2.text((w + gap + 8, label_h + h + gap + 6),         f"ITER {ITER:03d}  fl-45", fill=(220, 220, 180))
        d2.text((w * 2 + gap * 2 + 8, label_h + h + gap + 6), f"ITER {ITER:03d}  fr-45", fill=(220, 220, 180))
        sixup_path = OUT_DIR / f"{ITER:03d}-vs-controls.png"
        six.save(sixup_path)

# Clean per-angle PNGs
for p in (top_path, fl_path, fr_path):
    try:
        p.unlink()
    except FileNotFoundError:
        pass

result = {
    "composite": str(composite_path),
    "sixup": str(sixup_path) if sixup_path else None,
    "bbox": list(BBOX),
}
