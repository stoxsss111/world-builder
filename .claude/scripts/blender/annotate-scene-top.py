"""
Render a top-down ortho of the FULL scene framed to plan.terrain.bbox, then
overlay every WB_asset_*'s wb_tag at its XY pixel position. Claude reads the
labeled image side-by-side with controls/top.png and decides per-object fixes.

Caller globals:

    PROJECT_ROOT = Path(...)
    WORLD_SLUG   = "<slug>"
    BBOX         = (xmin, ymin, zmin, xmax, ymax, zmax)
    OUT_PATH     = "worlds/<slug>/iterations/topviewNN-labeled.png"
    IMAGE_SIZE   = 1024
    HIDE_WATER   = True       # hide the water plane so labels are readable
    LABEL_MODE   = "tag"      # "tag" (full wb_tag) | "short" (last digit) | "id" (wb_id only)

Side effects:
- Adds / replaces a top-down ortho camera (WB_AnnoTopCam) framed to BBOX
- Renders the scene WITHOUT freestyle (cleaner labels)
- Reads the rendered PNG, draws colored dots + tag labels per WB_asset_, writes labeled PNG
- Restores prior visibility and freestyle setting
"""
import bpy
import math
import mathutils
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(globals().get("PROJECT_ROOT", r"C:\GIT\world-builder"))
WORLD_SLUG   = globals().get("WORLD_SLUG", "")
BBOX         = tuple(globals().get("BBOX", (-7.5, -6.5, -0.6, 7.5, 6.0, 6.0)))
OUT_PATH     = str(globals().get("OUT_PATH", "annotated-top.png"))
IMAGE_SIZE   = int(globals().get("IMAGE_SIZE", 1024))
HIDE_WATER   = bool(globals().get("HIDE_WATER", True))
LABEL_MODE   = globals().get("LABEL_MODE", "tag")

xmin, ymin, zmin, xmax, ymax, zmax = BBOX
cx = (xmin + xmax) / 2.0
cy = (ymin + ymax) / 2.0
sx = xmax - xmin
sy = ymax - ymin
longest = max(sx, sy)
res_x = int(IMAGE_SIZE * sx / longest) if sy >= sx else IMAGE_SIZE
res_y = int(IMAGE_SIZE * sy / longest) if sx >= sy else IMAGE_SIZE
if sx == sy:
    res_x = res_y = IMAGE_SIZE

# Top-down ortho camera framed to bbox
cam_name = "WB_AnnoTopCam"
cam = bpy.data.objects.get(cam_name)
if cam is None:
    cd = bpy.data.cameras.new(cam_name)
    cam = bpy.data.objects.new(cam_name, cd)
    bpy.context.scene.collection.objects.link(cam)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = longest
cam.location = (cx, cy, max(zmax, 0) + 20.0)
cam.rotation_euler = (0.0, 0.0, 0.0)

# Hide water so labels are readable
saved_visibility = {}
for o in bpy.data.objects:
    saved_visibility[o.name] = (o.hide_viewport, o.hide_render)
if HIDE_WATER:
    w = bpy.data.objects.get("WB_Water")
    if w:
        w.hide_render = True
        w.hide_viewport = True

scene = bpy.context.scene
prev_engine = scene.render.engine
prev_freestyle = scene.render.use_freestyle
prev_res_x = scene.render.resolution_x
prev_res_y = scene.render.resolution_y
prev_cam = scene.camera

scene.render.engine = 'BLENDER_EEVEE'
try:
    scene.eevee.taa_render_samples = 16
except AttributeError:
    pass
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.use_freestyle = False
scene.camera = cam

# Render the base top-down
out_dir = os.path.dirname(OUT_PATH)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)
tmp_render = OUT_PATH.replace(".png", "_raw.png")
scene.render.filepath = tmp_render
bpy.ops.render.render(write_still=True)

# Restore
for n, (hv, hr) in saved_visibility.items():
    o = bpy.data.objects.get(n)
    if o is not None:
        o.hide_viewport = hv
        o.hide_render = hr
scene.render.engine = prev_engine
scene.render.use_freestyle = prev_freestyle
scene.render.resolution_x = prev_res_x
scene.render.resolution_y = prev_res_y
scene.camera = prev_cam

# Now overlay labels using PIL
img = Image.open(tmp_render).convert("RGB")
W, H = img.size
draw = ImageDraw.Draw(img, "RGBA")

try:
    font_label = ImageFont.truetype("arial.ttf", 14)
    font_id    = ImageFont.truetype("arial.ttf", 11)
except IOError:
    font_label = ImageFont.load_default()
    font_id    = ImageFont.load_default()

# Per-class colours so the labels are scannable
CLASS_COLORS = {
    "stone-arch":           (220, 90, 220),
    "tiki-hut":             (255, 165, 0),
    "tiki-torch":           (255, 80, 80),
    "campfire":             (255, 60, 60),
    "log-stump":            (139, 95, 50),
    "treasure-chest":       (255, 215, 0),
    "palm-tall":            (51, 204, 51),
    "palm-small":           (118, 194, 90),
    "boulder-mossy-large":  (90, 90, 90),
    "boulder-mossy-small":  (168, 168, 168),
    "flower-pink":          (255, 100, 200),
    "conch-shell":          (255, 230, 180),
    "hut-stairs":           (95, 50, 30),
}
DEFAULT_COLOR = (0, 200, 255)

def world_to_pixel(wx, wy):
    px = int((wx - xmin) / sx * W)
    py = int((ymax - wy) / sy * H)
    return px, py

label_records = []
for obj in bpy.data.objects:
    tag = obj.get("wb_tag")
    wid = obj.get("wb_id")
    if not tag: continue
    wx, wy = obj.location.x, obj.location.y
    px, py = world_to_pixel(wx, wy)
    color = CLASS_COLORS.get(wid, DEFAULT_COLOR)
    # dot
    r = 6
    draw.ellipse([px - r, py - r, px + r, py + r], fill=color + (255,), outline=(0, 0, 0, 255), width=1)
    # label text
    if LABEL_MODE == "tag":
        text = tag
    elif LABEL_MODE == "short":
        text = tag.split("_")[-1]
    else:
        text = wid or tag
    # text with light shadow so it's readable on any background
    tx = px + 10
    ty = py - 8
    # shadow
    draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0, 220), font=font_label)
    draw.text((tx, ty),         text, fill=(255, 255, 255, 255), font=font_label)
    label_records.append({"tag": tag, "wb_id": wid, "world_xy": [round(wx,2), round(wy,2)], "px": [px, py], "color": list(color)})

# Optional: draw the world bbox edge for orientation
bx_min, by_max = world_to_pixel(xmin, ymax)
bx_max, by_min = world_to_pixel(xmax, ymin)
draw.rectangle([bx_min, by_max, bx_max, by_min], outline=(120, 120, 120, 200), width=1)
# Compass: small "+X →" and "+Y ↑" markers in the corner
draw.text((10, H - 30), "x→  -y↓", fill=(220, 220, 220, 255), font=font_id)

img.save(OUT_PATH)

# Cleanup intermediate
try:
    os.remove(tmp_render)
except OSError:
    pass

result = {
    "labeled_image": OUT_PATH,
    "image_size": [W, H],
    "labels_drawn": len(label_records),
    "world_bbox": [xmin, ymin, xmax, ymax],
    "pixel_to_world_mapping": {
        "world_xmin": xmin, "world_ymin": ymin, "world_xmax": xmax, "world_ymax": ymax,
        "image_w": W, "image_h": H,
    }
}
