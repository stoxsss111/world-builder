---
name: generate-material
description: Generate one tiled PBR material via fal PATINA. BaseColor + Normal + Roughness + Metalness + Height maps from a text prompt. ~$0.06-0.10 per material at 1024px. Use for procedural surfaces (sand, water, grass, dirt, rock) — NOT for objects (those come textured from Tripo P1).
argument-hint: [world-slug] [material-id] [--resolution 1024|2048] [--seed N]
allowed-tools: Read Write Edit Bash(node .claude/scripts/asset-pipeline/* *) Bash(ls *)
---

Generate one PBR material set for `worlds/$1/materials/$2/`.

## When to call this skill

For PROCEDURAL surfaces — primitives Claude builds in Blender (ground plane, water plane, grass patch) that need a tiled material. Examples:

- `sand` — for the main ground plane
- `water-shallow` — for the water plane around the island
- `grass` — for grass patch planes
- `wood-planks` — for a wooden walkway or hut floor
- `rock-cliff` — only if there's a procedural cliff surface (not a placed boulder)

For OBJECTS (palms, chests, lanterns, log-stumps, boulders, flowers) — do NOT use this skill. Tripo P1 emits textured GLBs with PBR maps baked in.

## Procedure

1. **Build the material prompt.** Combine the material type with `plan.style.anchor` + palette + the magic phrase `seamlessly tiling`:

   > "{material-type-description}, {style.anchor} cartoon art style, vibrant saturated palette ({relevant palette colours}), seamlessly tiling, no border artefacts, top-down view, no shadows."

   Examples:
   - Sand: `"warm stylised cartoon beach sand, Donkey Kong Bananza palette, saturated warm yellow with subtle highlights, seamlessly tiling, no border artefacts, top-down view, no shadows."`
   - Water: `"stylised cartoon turquoise tropical water surface, Wind Waker shading, saturated cyan, seamlessly tiling, no border artefacts, top-down view, no shadows."`
   - Grass: `"stylised cartoon emerald-mint grass with small pink flowers, Banjo-Kazooie palette, saturated mid-green, seamlessly tiling, no border artefacts, top-down view, no shadows."`

2. **Generate the PBR set.**
   ```bash
   node .claude/scripts/asset-pipeline/patina-material.mjs \
     --prompt "<the prompt above>" \
     --output-dir worlds/$1/materials/$2 \
     --output-slug $2 \
     --resolution 1024
   ```
   This produces five PNGs in the output dir: `{basecolor, normal, roughness, metalness, height}.png` and saves request metadata.

3. **Apply to Blender.** Build a Python snippet that creates a Principled BSDF material with the five maps loaded and connected:
   ```python
   import bpy
   def apply_patina_material(obj_name, material_id, world_slug):
       base = f"worlds/{world_slug}/materials/{material_id}"
       mat = bpy.data.materials.new(name=f"{material_id}_PATINA")
       mat.use_nodes = True
       nt = mat.node_tree
       # Clear default
       for n in nt.nodes: nt.nodes.remove(n)
       out = nt.nodes.new("ShaderNodeOutputMaterial")
       bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
       nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

       def load_tex(slug, colorspace="sRGB"):
           img = bpy.data.images.load(f"{base}/{material_id}-{slug}.png", check_existing=True)
           img.colorspace_settings.name = colorspace
           t = nt.nodes.new("ShaderNodeTexImage")
           t.image = img
           return t

       basecolor = load_tex("basecolor", "sRGB")
       normal_t  = load_tex("normal", "Non-Color")
       rough_t   = load_tex("roughness", "Non-Color")
       metal_t   = load_tex("metalness", "Non-Color")
       height_t  = load_tex("height", "Non-Color")

       normal_map = nt.nodes.new("ShaderNodeNormalMap")
       nt.links.new(normal_t.outputs["Color"], normal_map.inputs["Color"])

       nt.links.new(basecolor.outputs["Color"], bsdf.inputs["Base Color"])
       nt.links.new(rough_t.outputs["Color"], bsdf.inputs["Roughness"])
       nt.links.new(metal_t.outputs["Color"], bsdf.inputs["Metallic"])
       nt.links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
       # Height → optional displacement on output

       obj = bpy.data.objects[obj_name]
       if obj.data.materials: obj.data.materials[0] = mat
       else: obj.data.materials.append(mat)
       return mat
   ```
   Call via `execute_blender_code` after `patina-material.mjs` finishes.

4. **Visual check.** Screenshot the textured surface, read it back. If the tile looks acceptable, done. If it looks bad (wrong colour, wrong style, broken seams), regenerate with a tighter prompt or different seed.

5. **Hard cap: 2 retries per material.** If three attempts in a row miss, escalate — usually means the prompt needs human intervention or the material needs to be hand-authored.

6. **Update `worlds/$1/cost.json`** with the PATINA spend.

## Cost guide

| Resolution | ~Cost / generation | When to use |
|---|---|---|
| 1024 | $0.08 | Default. Fine for all procedural surfaces. |
| 2048 | $0.30 | Hero surface that fills the screen (rarely needed in stylised scenes). |
| 4096 | $1.18 | Avoid — overkill for our pipeline. |
| 8192 | $4.70 | Never use. |

Total PATINA spend for a typical world (sand + water + grass = 3 materials at 1024) = **~$0.24**.

## What you must NOT do

- Do NOT use PATINA for objects with topology (palms, chests, log-stumps). They come textured from Tripo P1.
- Do NOT request > 2048 resolution — the model doesn't need that much detail in a stylised scene.
- Do NOT skip the "seamlessly tiling, no border artefacts" tail in the prompt — without it you get a single-shot photo instead of a tile.
- Do NOT regenerate more than 2 times per material — escalate instead.
