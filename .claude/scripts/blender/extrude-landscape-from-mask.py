"""
Build the landscape mesh by extruding it directly from a top-down mask image.
No Tripo for the landscape anymore — we have the silhouette, just turn it into
a slab in Blender. Result: 1:1 silhouette match with `controls/top.png` because
the same image drives the geometry.

Caller provides globals before invoking:

    PROJECT_ROOT  = Path(...)
    WORLD_SLUG    = "<slug>"
    MASK_IMAGE    = Path("worlds/<slug>/controls/_landscape.png")   # source of silhouette
    BBOX_XY       = (xmin, ymin, xmax, ymax)                        # world XY extent the mask spans
    SLAB_THICK    = 0.7                                             # metres
    GRID_RES      = 256                                             # per-axis grid sample density
    SAND_MATERIAL = "WB_PlanarSand"                                 # material name to apply

Reads the image alpha (or sand-tone via colour heuristic when alpha is opaque
everywhere), thresholds it to a binary land mask, downsamples to GRID_RES,
constructs a 2D quad mesh for the land pixels, dissolves interior edges,
extrudes downward by SLAB_THICK, bevels the silhouette edges, and applies the
sand material via planar projection.

The grid spacing is auto-computed so the mesh fills BBOX_XY exactly. The result
sits with its TOP face at z=0 (objects placed at z=0 sit on the slab).
"""
import bpy
import bmesh
import numpy as np
import math
import mathutils
from PIL import Image
from pathlib import Path

PROJECT_ROOT  = Path(globals().get("PROJECT_ROOT", r"C:\GIT\world-builder"))
WORLD_SLUG    = globals().get("WORLD_SLUG", "new-island")
WORLD         = PROJECT_ROOT / "worlds" / WORLD_SLUG
MASK_IMAGE    = Path(globals().get("MASK_IMAGE", WORLD / "controls" / "_landscape.png"))
BBOX_XY       = globals().get("BBOX_XY", (-7.0, -6.0, 7.0, 6.0))
SLAB_THICK    = float(globals().get("SLAB_THICK", 0.7))
GRID_RES      = int(globals().get("GRID_RES", 256))
SAND_MATERIAL = globals().get("SAND_MATERIAL", "WB_PlanarSand")

xmin_w, ymin_w, xmax_w, ymax_w = BBOX_XY

# --- 1. Read mask image -----------------------------------------------------
img = Image.open(MASK_IMAGE).convert("RGBA")
arr = np.array(img)
H, W = arr.shape[:2]
r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
# Land heuristic: pixel is land if alpha > 200 AND it's NOT mostly blue (water).
# The PATINA water is bluish (B > R, B > G). Land is sandy / grassy (R+G > B).
is_opaque = a > 200
is_blue   = (b.astype(int) > r.astype(int) + 15) & (b.astype(int) > g.astype(int))
mask_full = is_opaque & ~is_blue

# --- 2. Downsample mask to GRID_RES × (aspect-matched H) -------------------
aspect = H / W
grid_w = GRID_RES
grid_h = max(1, int(round(GRID_RES * aspect)))
# Convert mask to PIL, resize with average / nearest, threshold again
mask_img = Image.fromarray((mask_full.astype(np.uint8) * 255), mode='L')
mask_small = mask_img.resize((grid_w, grid_h), resample=Image.BILINEAR)
mask = np.array(mask_small) > 128

# --- 3. Build a quad grid mesh for the land cells ---------------------------
bbox_w = xmax_w - xmin_w
bbox_h = ymax_w - ymin_w
dx = bbox_w / grid_w
dy = bbox_h / grid_h

# Remove any existing WB_Landscape
old = bpy.data.objects.get("WB_Landscape")
if old:
    bpy.data.objects.remove(old, do_unlink=True)
for m in list(bpy.data.meshes):
    if m.users == 0: bpy.data.meshes.remove(m)

bm = bmesh.new()
verts = {}
def vert_at(i, j):
    key = (i, j)
    if key in verts: return verts[key]
    x = xmin_w + i * dx
    y = ymax_w - j * dy            # image-Y points DOWN, world-Y points UP → flip
    v = bm.verts.new((x, y, 0.0))
    verts[key] = v
    return v

face_count = 0
for j in range(grid_h):
    for i in range(grid_w):
        if not mask[j, i]: continue
        v0 = vert_at(i,   j)
        v1 = vert_at(i+1, j)
        v2 = vert_at(i+1, j+1)
        v3 = vert_at(i,   j+1)
        bm.faces.new((v0, v1, v2, v3))
        face_count += 1

bm.faces.ensure_lookup_table()
# Dissolve interior edges (any edge whose two adjacent faces are both land)
to_dissolve = [e for e in bm.edges if len(e.link_faces) == 2]
bmesh.ops.dissolve_edges(bm, edges=to_dissolve, use_verts=False, use_face_split=False)

# Top face now is a single big n-gon (or several, one per connected island/spit).
# Extrude downward to make a slab.
top_faces = list(bm.faces)
ret = bmesh.ops.extrude_face_region(bm, geom=top_faces)
extruded_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
bmesh.ops.translate(bm, vec=(0, 0, -SLAB_THICK), verts=extruded_verts)

# Push down so the TOP sits at z = 0
for v in bm.verts:
    v.co.z -= 0  # top is already at z=0; the bottom is at -SLAB_THICK. OK.

# Convert bmesh → mesh data
me = bpy.data.meshes.new("WB_LandscapeMesh")
bm.to_mesh(me); bm.free()
land = bpy.data.objects.new("WB_Landscape", me)
bpy.context.scene.collection.objects.link(land)

# Bevel modifier for soft Banjo edges
bev = land.modifiers.new("Bevel", 'BEVEL')
bev.width = 0.06
bev.segments = 3
bev.profile = 0.7
bev.angle_limit = math.radians(35)

# Smooth shading
bpy.ops.object.select_all(action='DESELECT')
land.select_set(True); bpy.context.view_layer.objects.active = land
bpy.ops.object.shade_smooth()

# --- 4. PATINA sand material applied via planar (Generated -> Mapping) ----
def patina_sand_material(name=SAND_MATERIAL, tile=2.0):
    sand_dir = WORLD / "materials" / "sand"
    paths = {
        "basecolor": str(sand_dir / "0-sand-2-images-2.png"),
        "normal":    str(sand_dir / "0-sand-3-images-3.png"),
        "roughness": str(sand_dir / "0-sand-4-images-4.png"),
    }
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True; nt = mat.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    geom = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geom.outputs["Position"], sep.inputs["Vector"])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value=(tile,tile,1.0)
    nt.links.new(comb.outputs["Vector"], mp.inputs["Vector"])
    def ld(p, cs):
        try:
            img = bpy.data.images.load(p, check_existing=True)
            img.colorspace_settings.name = cs
            t = nt.nodes.new("ShaderNodeTexImage"); t.image=img; t.extension='REPEAT'
            nt.links.new(mp.outputs["Vector"], t.inputs["Vector"]); return t
        except Exception:
            return None
    basecolor = ld(paths["basecolor"], "sRGB")
    normal_t  = ld(paths["normal"],    "Non-Color")
    rough_t   = ld(paths["roughness"], "Non-Color")
    if basecolor: nt.links.new(basecolor.outputs["Color"], bsdf.inputs["Base Color"])
    if rough_t:   nt.links.new(rough_t.outputs["Color"],   bsdf.inputs["Roughness"])
    if normal_t:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(normal_t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat

# Apply sand material if the sand maps exist in this world; else leave default
if (WORLD / "materials" / "sand" / "0-sand-2-images-2.png").exists():
    mat = patina_sand_material(SAND_MATERIAL, tile=2.0)
    land.data.materials.clear()
    land.data.materials.append(mat)
else:
    # Fallback: a flat warm-yellow material
    mat = bpy.data.materials.get("WB_SandFallback") or bpy.data.materials.new("WB_SandFallback")
    mat.use_nodes = True
    for n in list(mat.node_tree.nodes):
        if n.type == 'BSDF_PRINCIPLED':
            n.inputs["Base Color"].default_value = (0.96, 0.79, 0.48, 1.0)
            n.inputs["Roughness"].default_value = 0.85
    land.data.materials.clear()
    land.data.materials.append(mat)

# Put in Terrain collection
coll = bpy.data.collections.get("Terrain") or bpy.data.collections.new("Terrain")
if coll.name not in [c.name for c in bpy.context.scene.collection.children]:
    bpy.context.scene.collection.children.link(coll)
for c in list(land.users_collection): c.objects.unlink(land)
coll.objects.link(land)

bpy.ops.wm.save_mainfile()

result = {
    "land_pixels": int(mask.sum()),
    "grid_size": [grid_w, grid_h],
    "world_bbox": list(BBOX_XY),
    "slab_thickness_m": SLAB_THICK,
    "dimensions_m": [round(d, 2) for d in land.dimensions],
}
