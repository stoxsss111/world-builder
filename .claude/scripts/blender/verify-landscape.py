"""
Render the current Blender landscape mesh as a TOP-DOWN ORTHO view framed
exactly to plan.terrain.bbox in world XY. The output PNG is meant to be diffed
against controls/top.png — if the two silhouettes line up, the world-XY ↔ pixel
mapping is the contract for back-projection in `place-from-detections.py`.

Caller provides these globals in the exec namespace before invoking:

    BBOX = (xmin, ymin, zmin, xmax, ymax, zmax)
    OUT_PATH = "worlds/<slug>/iterations/landscape-NN.png"
    IMAGE_SIZE = 1024            # default 1024; match controls/top.png if different
    LANDSCAPE_NAME = "WB_Landscape"   # optional override

The script:
  - hides everything except WB_Landscape and its grass children
  - sets up an ortho camera straight above the bbox centre
  - renders at IMAGE_SIZE × IMAGE_SIZE (or aspect-matched if bbox is non-square)
  - un-hides what it hid
  - returns {out: ..., image_size: [W, H]}
"""
import bpy
import math
import mathutils
import os
from pathlib import Path

try:
    BBOX
except NameError:
    BBOX = (-7.0, -6.0, -0.5, 7.0, 6.0, 4.5)
try:
    OUT_PATH
except NameError:
    OUT_PATH = "landscape-verify.png"
try:
    IMAGE_SIZE
except NameError:
    IMAGE_SIZE = 1024
try:
    LANDSCAPE_NAME
except NameError:
    LANDSCAPE_NAME = "WB_Landscape"

xmin, ymin, zmin, xmax, ymax, zmax = BBOX
cx = (xmin + xmax) / 2.0
cy = (ymin + ymax) / 2.0
sx = xmax - xmin
sy = ymax - ymin
# Aspect-correct ortho: longest axis = ortho_scale, render res scales by aspect
longest = max(sx, sy)
aspect_x = sx / longest
aspect_y = sy / longest
res_x = int(IMAGE_SIZE * aspect_x) if sx <= sy else IMAGE_SIZE
res_y = int(IMAGE_SIZE * aspect_y) if sy <= sx else IMAGE_SIZE
if sx == sy:
    res_x = res_y = IMAGE_SIZE

# Hide everything except landscape + grass children + (optional) water
visible_before = {}
keep_visible = {LANDSCAPE_NAME, "WB_Water"}
for o in bpy.data.objects:
    visible_before[o.name] = (o.hide_viewport, o.hide_render)
    if o.type == 'MESH' and o.name not in keep_visible:
        o.hide_viewport = True
        o.hide_render = True

# Top-down ortho camera
cam_name = "WB_VerifyTopCam"
cam = bpy.data.objects.get(cam_name)
if cam is None:
    cam_data = bpy.data.cameras.new(cam_name)
    cam = bpy.data.objects.new(cam_name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = longest
cam.location = (cx, cy, max(zmax, 0) + 20.0)
cam.rotation_euler = (0.0, 0.0, 0.0)             # +Z up, looking straight down (-Z)

scene = bpy.context.scene
scene.camera = cam
scene.render.engine = 'BLENDER_EEVEE'
try:
    scene.eevee.taa_render_samples = 16
except AttributeError:
    pass
scene.render.resolution_x = res_x
scene.render.resolution_y = res_y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'

out_path_abs = str(Path(OUT_PATH))
os.makedirs(os.path.dirname(out_path_abs), exist_ok=True)
scene.render.filepath = out_path_abs
bpy.ops.render.render(write_still=True)

# Restore visibility
for name, (hv, hr) in visible_before.items():
    o = bpy.data.objects.get(name)
    if o is not None:
        o.hide_viewport = hv
        o.hide_render = hr

result = {
    "out": out_path_abs,
    "image_size": [res_x, res_y],
    "bbox": list(BBOX),
    "ortho_scale": longest,
    "pixel_to_world": {
        "x_px_per_world": res_x / sx,
        "y_px_per_world": res_y / sy,
        "world_xmin": xmin,
        "world_ymin": ymin,
        "world_xmax": xmax,
        "world_ymax": ymax,
        "image_w": res_x,
        "image_h": res_y,
    }
}
