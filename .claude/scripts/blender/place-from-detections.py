"""
Back-project every per-class pixel centroid from controls/detections.json to
world XY using plan.terrain.bbox + the verified controls/top.png dimensions.
Place one instance per centroid by importing the matching Tripo GLB (proto +
linked-duplicate copies tagged wb_tag="<id>_<idx>").

Caller provides these globals before invoking:

    PROJECT_ROOT = Path(r"...")            # absolute
    WORLD_SLUG   = "beach-island"
    CLASS_TO_ID  = {                        # human-readable class -> plan.objects.id
        "palm tree": ["palm-tall", "palm-small"],   # ambiguous classes split later by size
        "stone arch": ["stone-arch"],
        "tiki hut":   ["tiki-hut"],
        ...
    }
    TARGET_HEIGHTS = {...}                  # optional, per-id

If a class maps to MULTIPLE ids (e.g. "palm tree" → palm-tall + palm-small),
the detections are sorted by bbox area descending; biggest N go to the
largest id, next M to the next, etc., where N/M come from plan.objects[*].count.
"""
import bpy
import json
import math
import mathutils
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(globals().get("PROJECT_ROOT", r"C:\GIT\world-builder"))
WORLD_SLUG = globals().get("WORLD_SLUG", "beach-island")
WORLD = PROJECT_ROOT / "worlds" / WORLD_SLUG

DEFAULT_TARGET_HEIGHTS = {
    # All values in metres. Tuned for Banjo-Kazooie scale: characters ~1.5-1.8 m,
    # huts walkable, palms towering, boulders chest-to-waist height. These defaults
    # should give "looks roughly right" on first placement — refinement rounds tweak
    # per scene from there.
    "stone-arch":           3.5,   # walkable trilithon portal
    "tiki-hut":             3.2,   # head-height door + thatched roof
    "hut-stairs":           0.5,   # three small steps
    "tiki-torch":           2.8,   # taller than character so flame reads above heads
    "campfire":             0.7,   # low fire pit
    "log-stump":            0.5,   # sittable
    "treasure-chest":       0.8,   # waist-high
    "palm-tall":            5.5,   # towering — gives the silhouette "tropical island" reads
    "palm-small":           2.6,   # waist-to-chest
    "boulder-mossy-large":  1.8,   # waist height; not bigger than the hut
    "boulder-mossy-small":  0.8,   # knee height
    "flower-pink":          0.3,   # ankle-height cluster
    "conch-shell":          0.2,   # palm-of-hand
}
# plan.json may include a scale_per_class overrides map. It wins over DEFAULT_TARGET_HEIGHTS.
plan_scale_overrides = (plan.get("scale_per_class") or {}) if "plan" in globals() else {}
TARGET_HEIGHTS = {**DEFAULT_TARGET_HEIGHTS, **plan_scale_overrides, **(globals().get("TARGET_HEIGHTS") or {})}

DEFAULT_CLASS_TO_ID = {
    "palm tree":      ["palm-tall", "palm-small"],
    "stone arch":     ["stone-arch"],
    "tiki hut":       ["tiki-hut"],
    "tiki torch":     ["tiki-torch"],
    "campfire":       ["campfire"],
    "log stump":      ["log-stump"],
    "treasure chest": ["treasure-chest"],
    "boulder":        ["boulder-mossy-large", "boulder-mossy-small"],
    "flower":         ["flower-pink"],
    "shell":          ["conch-shell"],
    "stairs":         ["hut-stairs"],
}
CLASS_TO_ID = globals().get("CLASS_TO_ID", DEFAULT_CLASS_TO_ID)

plan = json.loads((WORLD / "plan.json").read_text(encoding="utf-8"))
reviewed_detections = WORLD / "controls" / "detections-reviewed.json"
detections_path = reviewed_detections if reviewed_detections.exists() else (WORLD / "controls" / "detections.json")
detections = json.loads(detections_path.read_text(encoding="utf-8"))
assets_idx = json.loads((WORLD / "assets" / "index.json").read_text(encoding="utf-8"))

def _abs(p):
    pp = Path(p)
    return str(pp if pp.is_absolute() else (PROJECT_ROOT / pp).resolve())

asset_path_by_id = {it["id"]: _abs(it["glb_path"]) for it in assets_idx["items"] if it.get("glb_path")}
plan_obj_by_id   = {o["id"]: o for o in plan["objects"]}

bbox = plan["terrain"]["bbox"]
xmin, ymin, _, xmax, ymax, _ = bbox

# Image dimensions: assume controls/top.png is square (nano-banana default) but
# read actual dims for accuracy.
from PIL import Image as PIL_Image
img_w, img_h = PIL_Image.open(WORLD / "controls" / "top.png").size

def pixel_to_world(px, py):
    wx = xmin + (px / img_w) * (xmax - xmin)
    wy = ymax - (py / img_h) * (ymax - ymin)
    return wx, wy

# Collection
coll = bpy.data.collections.get("Assets") or bpy.data.collections.new("Assets")
if coll.name not in [c.name for c in bpy.context.scene.collection.children]:
    bpy.context.scene.collection.children.link(coll)

def link_to(obj, c):
    for x in list(obj.users_collection):
        x.objects.unlink(obj)
    c.objects.link(obj)

def bbox_world(obj):
    coords = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    zs = [c.z for c in coords]
    return min(zs), max(zs)

def import_proto(obj_id):
    name = f"WB_proto_{obj_id}"
    existing = bpy.data.objects.get(name)
    if existing: return existing
    path = asset_path_by_id.get(obj_id)
    if not path: return None
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.gltf(filepath=str(path))
    added = [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]
    meshes = [o for o in added if o.type == 'MESH']
    if not meshes: return None
    bpy.ops.object.select_all(action='DESELECT')
    for m in meshes: m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1: bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    # IMPORTANT: Tripo's GLB import sets rotation_mode='QUATERNION'.
    # Setting rotation_euler on a QUATERNION object is a silent no-op.
    # Force XYZ so subsequent rotation_euler assignments actually apply.
    obj.rotation_mode = 'XYZ'
    for o in added:
        if o.type != 'MESH' and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    # Scale to target height FIRST so the bbox math below is in target metres
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    mnz, mxz = bbox_world(obj)
    h = mxz - mnz
    if h < 1e-4: h = 1.0
    s = TARGET_HEIGHTS.get(obj_id, 1.5) / h
    obj.scale = (s, s, s)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # Set origin to bbox CENTER-BOTTOM: cursor.location = (cx, cy, z_min), then ORIGIN_CURSOR.
    # After this, the object's origin (and thus its inst.location after copy) sits exactly
    # at the bbox bottom-centre, so `inst.location = (wx, wy, 0)` puts the object's footprint
    # right at world (wx, wy) on the ground at z=0. Pixel-precise placement.
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]; ys = [c.y for c in corners]; zs = [c.z for c in corners]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    z_min = min(zs)
    bpy.context.scene.cursor.location = (cx, cy, z_min)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    # After ORIGIN_CURSOR, obj.location == cursor. Move object so origin sits at world (0,0,0).
    obj.location = (0, 0, 0)
    obj.hide_viewport = True
    obj.hide_render = True
    link_to(obj, coll)
    return obj

# Clear stale instances
for o in list(bpy.data.objects):
    if o.name.startswith("WB_asset_"):
        bpy.data.objects.remove(o, do_unlink=True)

placed = []

# detections.classes is a list of {class, instances: [{cx_px, cy_px, w_px, h_px}, ...]}
det_by_class = {entry["class"]: entry.get("instances", []) for entry in detections["classes"] if "class" in entry}

# Cross-class centroid dedup: if two centroids from DIFFERENT classes land within DEDUP_PX of each
# other, keep only the one whose bbox area is larger (assume that's the more confident detection).
# This kills stacked-chimera artifacts (e.g. palm + boulder + flower all placed at the same XY
# because Moondream classified the same blob into multiple classes).
DEDUP_PX = 30
def _area(d): return d["w_px"] * d["h_px"]
flat = []
for cls, insts in det_by_class.items():
    for d in insts:
        flat.append({"class": cls, **d})
# Sort by area desc — bigger wins ties
flat.sort(key=lambda d: -_area(d))
kept = []
for d in flat:
    is_dupe = False
    for k in kept:
        if k["class"] == d["class"]:
            continue
        dx = k["cx_px"] - d["cx_px"]; dy = k["cy_px"] - d["cy_px"]
        if dx*dx + dy*dy < DEDUP_PX*DEDUP_PX:
            is_dupe = True
            break
    if not is_dupe:
        kept.append(d)
# Rebuild det_by_class from kept
det_by_class = {cls: [] for cls in det_by_class}
for d in kept:
    det_by_class.setdefault(d["class"], []).append({k: d[k] for k in ("index", "x_px","y_px","w_px","h_px","cx_px","cy_px") if k in d})
dedup_dropped = len(flat) - len(kept)

for cls, ids in CLASS_TO_ID.items():
    insts = det_by_class.get(cls, [])
    if not insts: continue
    # Sort instances by bbox area descending
    insts_sorted = sorted(insts, key=lambda d: -(d["w_px"] * d["h_px"]))
    # Split across IDs by plan counts (greedy)
    id_caps = []
    for obj_id in ids:
        cap = plan_obj_by_id.get(obj_id, {}).get("count", 0)
        id_caps.append([obj_id, cap])
    # If detections > capacity, drop the smallest extras
    total_cap = sum(c for _, c in id_caps)
    if total_cap and len(insts_sorted) > total_cap:
        insts_sorted = insts_sorted[:total_cap]
    # Per-instance scale based on Moondream's bbox area: each instance is scaled relative to
    # the median area of its class. Big detection → big object. Clamp ±40 % so a noisy
    # detection can't blow up a flower to palm-tall size.
    areas = [max(1.0, d.get("w_px", 1) * d.get("h_px", 1)) for d in insts_sorted]
    median_area = sorted(areas)[len(areas) // 2] if areas else 1.0
    cursor = 0
    for obj_id, cap in id_caps:
        if not cap: continue
        proto = import_proto(obj_id)
        if proto is None: continue
        chunk = insts_sorted[cursor:cursor + cap]
        cursor += cap
        for idx, det in enumerate(chunk):
            wx, wy = pixel_to_world(det["cx_px"], det["cy_px"])
            inst = proto.copy()
            inst.hide_viewport = False
            inst.hide_render = False
            tag = f"{obj_id}_{idx}"
            inst.name = f"WB_asset_{tag}"
            inst["wb_tag"] = tag
            inst["wb_id"] = obj_id
            inst["wb_idx"] = idx
            inst.rotation_mode = 'XYZ'                                    # ensure Euler — Blender copy() inherits QUATERNION from the proto
            # bbox center-bottom origin means `inst.location = (wx, wy, 0)` plants the
            # object's footprint exactly at (wx, wy) on the z=0 ground.
            inst.location = (wx, wy, 0.0)
            # Per-instance scale from detection bbox area (clamped ±40 %)
            instance_area = max(1.0, det.get("w_px", 1) * det.get("h_px", 1))
            scale_ratio = (instance_area / median_area) ** 0.5
            scale_ratio = max(0.6, min(1.6, scale_ratio))
            inst.scale = (proto.scale.x * scale_ratio, proto.scale.y * scale_ratio, proto.scale.z * scale_ratio)
            inst.rotation_euler = (0, 0, math.radians((idx * 37 + hash(obj_id) % 360)))
            coll.objects.link(inst)
            placed.append({"tag": tag, "world_xy": [round(wx,2), round(wy,2)], "from_px": [det["cx_px"], det["cy_px"]], "scale_ratio": round(scale_ratio,2)})

bpy.ops.wm.save_mainfile()

result = {
    "placed_count": len(placed),
    "first_five": placed[:5],
    "bbox": bbox,
    "image_size": [img_w, img_h],
    "dedup_dropped": dedup_dropped,
}
