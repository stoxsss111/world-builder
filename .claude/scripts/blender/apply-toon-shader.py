"""
Final-pass toon shader: walks every material that's actually USED on a mesh in
the scene, rebuilds its node graph as:

    <existing Base Color source> → Diffuse BSDF
                                          ↓
                                  Shader-to-RGB → ColorRamp (3 hard steps)
                                                              ↓
                                                         Emission → Material Output

This gives the Banjo-Kazooie cel-shaded look: hard light/mid/shadow bands per
material, no smooth gradient. The existing texture (Tripo's painted base
color) is preserved underneath — just quantised.

Plus enables Freestyle line rendering with black outlines on silhouette +
border + crease edges, ~2.5 px thick — the painterly outline you see in
Banjo / Wind Waker reference art.

Caller provides:

    PROJECT_ROOT = Path(...)
    WORLD_SLUG   = "<slug>"

Result: every WB_* material in the scene is now cel-shaded, render engine is
EEVEE with Freestyle on. Save and re-render via the standard final-render
camera and the look should jump from "PBR" to "Banjo-Kazooie screenshot".
"""
import bpy
from pathlib import Path

PROJECT_ROOT = Path(globals().get("PROJECT_ROOT", r"C:\GIT\world-builder"))
WORLD_SLUG = globals().get("WORLD_SLUG", "")

scene = bpy.context.scene

# ---------- 1. Wrap every used material in toon shading ----------------------
def find_principled(node_tree):
    for n in node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            return n
    return None

def find_output(node_tree):
    for n in node_tree.nodes:
        if n.type == 'OUTPUT_MATERIAL' and n.is_active_output:
            return n
    for n in node_tree.nodes:
        if n.type == 'OUTPUT_MATERIAL':
            return n
    return None

def already_toon(node_tree):
    return any(n.name == "WB_ToonColorRamp" for n in node_tree.nodes)

# Collect materials USED by any mesh in the scene
used_mats = set()
for obj in scene.objects:
    if obj.type == 'MESH':
        for slot in obj.material_slots:
            if slot.material is not None:
                used_mats.add(slot.material)

wrapped = []
skipped = []
for mat in used_mats:
    if not mat.use_nodes or mat.node_tree is None:
        skipped.append((mat.name, "no node tree")); continue
    if already_toon(mat.node_tree):
        skipped.append((mat.name, "already toon")); continue
    nt = mat.node_tree

    bsdf = find_principled(nt)
    out  = find_output(nt)
    if out is None:
        out = nt.nodes.new("ShaderNodeOutputMaterial")

    # Figure out what feeds Base Color
    base_color_input = None
    base_color_socket = None
    if bsdf is not None and "Base Color" in bsdf.inputs:
        bc = bsdf.inputs["Base Color"]
        if bc.is_linked:
            link = bc.links[0]
            base_color_input = link.from_node
            base_color_socket = link.from_socket
        else:
            # Use the literal colour
            base_color_socket = None
            literal_color = tuple(bc.default_value)
    else:
        literal_color = (0.8, 0.8, 0.8, 1.0)

    # Build the toon chain
    diffuse = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.name = "WB_ToonDiffuse"
    diffuse.location = (200, 200)
    if base_color_socket is not None:
        nt.links.new(base_color_socket, diffuse.inputs["Color"])
    else:
        diffuse.inputs["Color"].default_value = literal_color

    to_rgb = nt.nodes.new("ShaderNodeShaderToRGB")
    to_rgb.name = "WB_ToonShaderToRGB"
    to_rgb.location = (400, 200)
    nt.links.new(diffuse.outputs["BSDF"], to_rgb.inputs["Shader"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")    # ColorRamp
    ramp.name = "WB_ToonColorRamp"
    ramp.location = (600, 200)
    # 3-stop hard cell ramp: shadow / mid / light
    elements = ramp.color_ramp.elements
    while len(elements) > 1:
        elements.remove(elements[-1])
    elements[0].position = 0.0
    elements[0].color = (0.30, 0.30, 0.30, 1.0)         # shadow multiplier
    e_mid = elements.new(0.50);   e_mid.color = (0.75, 0.75, 0.75, 1.0)  # mid
    e_hi  = elements.new(0.80);   e_hi.color  = (1.00, 1.00, 1.00, 1.0)  # highlight
    ramp.color_ramp.interpolation = 'CONSTANT'

    # Multiply quantised tone × original base color → emission (so it ignores world lighting variance)
    mix_mul = nt.nodes.new("ShaderNodeMixRGB")
    mix_mul.blend_type = 'MULTIPLY'
    mix_mul.inputs["Fac"].default_value = 1.0
    mix_mul.location = (800, 200)
    nt.links.new(ramp.outputs["Color"], mix_mul.inputs["Color1"])
    if base_color_socket is not None:
        nt.links.new(base_color_socket, mix_mul.inputs["Color2"])
    else:
        mix_mul.inputs["Color2"].default_value = literal_color

    emi = nt.nodes.new("ShaderNodeEmission")
    emi.name = "WB_ToonEmission"
    emi.location = (1000, 200)
    nt.links.new(mix_mul.outputs["Color"], emi.inputs["Color"])

    # Disconnect existing Surface input on output and link emission instead
    if out.inputs["Surface"].is_linked:
        for link in list(out.inputs["Surface"].links):
            nt.links.remove(link)
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])

    wrapped.append(mat.name)

# ---------- 2. Freestyle outlines -------------------------------------------
scene.render.use_freestyle = True

# Configure the active view layer's freestyle settings
vl = scene.view_layers[0]
vl.use_freestyle = True

fs = vl.freestyle_settings
# Use the existing first line set, configure it
if len(fs.linesets) == 0:
    fs.linesets.new(name="WB_OutlineSet")
ls = fs.linesets[0]
ls.name = "WB_OutlineSet"
ls.select_silhouette  = True
ls.select_border      = True
ls.select_contour     = True
ls.select_crease      = True
ls.select_edge_mark   = False
ls.select_external_contour = True

ls.linestyle.color = (0.0, 0.0, 0.0)
ls.linestyle.thickness = 2.5
ls.linestyle.alpha = 1.0
# Pure flat line
for mod in list(ls.linestyle.color_modifiers):
    ls.linestyle.color_modifiers.remove(mod)

# Crease angle: 140° matches the soft Banjo edge style
fs.crease_angle = 2.443   # ~140 degrees in radians

# Engine must stay Eevee (Freestyle is supported)
available = bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items.keys()
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in available else 'BLENDER_EEVEE'

bpy.ops.wm.save_mainfile()
result = {
    "wrapped_materials": wrapped,
    "skipped_materials": skipped,
    "freestyle_enabled": scene.render.use_freestyle,
    "crease_angle_deg": 140
}
