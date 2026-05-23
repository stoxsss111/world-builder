# Pipeline — phase by phase

Six phases, run in order by the `build-world` skill. Each phase corresponds to a focused skill in `.claude/skills/`.

## Phase 0 — Analyse the reference

**Skill:** `analyze-reference`

**Inputs:** `input/<file>.png`

**What happens:**

1. Claude reads the image directly (multimodal — no external vision API needed).
2. Produces a structured `plan.json` covering:

```jsonc
{
  "world_slug": "banjo-beach",
  "style": {
    "anchor": "Banjo-Kazooie · Treasure Trove Cove",
    "palette": ["#f2d790", "#3aa6b8", "#1f6f4b", "#9c6a3c"],
    "level_of_stylization": "high",     // "high" = cartoon, "mid" = stylized realism, "low" = photoreal
    "shading": "toon",                  // toon | flat | pbr-light
    "lighting": "golden-hour"
  },
  "terrain": {
    "shape": "small-island",            // island | hills | flat | crater | shoreline
    "ground": "sand",
    "water": { "present": true, "level": -0.05 },
    "size_meters": [12, 12],
    "feature_notes": "Slight rise in centre, palm cluster on south side, rocks lining north shore."
  },
  "objects": [
    { "id": "palm-tall", "name": "Tall stylised palm tree", "count": 3, "approx_positions": [[2,1],[3,0.5],[1.5,2]], "scale_hint": "tall" },
    { "id": "palm-short", "name": "Short bent palm tree", "count": 2, "approx_positions": [[-1,1],[0,3]], "scale_hint": "medium" },
    { "id": "beach-hut", "name": "Wooden tiki beach hut with thatched roof", "count": 1, "approx_positions": [[0,0]], "scale_hint": "large" },
    { "id": "rock-mossy", "name": "Mossy round rock", "count": 5, "approx_positions": [[-2,2],[-3,1],[-2.5,3],[-1.8,2.5],[-2.2,1.5]] },
    { "id": "starfish", "name": "Cartoon orange starfish", "count": 3, "approx_positions": [[1,-2],[2,-2.5],[0.5,-1.8]] },
    { "id": "shell", "name": "Conch shell, pink interior", "count": 4 },
    { "id": "barrel", "name": "Weathered wooden barrel", "count": 2 }
  ],
  "camera": {
    "framing": "three-quarter aerial",
    "focal_length_mm": 35
  }
}
```

3. Writes `worlds/<slug>/plan.json` and copies the reference to `worlds/<slug>/source/reference.png`.

**Hard rules:**
- Target the **20-25 instance working range** (sum of `count` across all objects). 25 is the soft cap before asking the user — NOT a goal. A sparser reference may justify 10-12; a denser one may justify raising to 30 with confirmation.
- If the plan needs more than 25 instances, the analyzer STOPS and asks the user.
- Every object MUST have a `face_limit` in `[5000, 15000]`. The Tripo wrapper clamps anyway.
- Group similar instances under one `id` with higher `count` — one .glb, N placements. Typical scene: 7-10 distinct `id`s re-instanced to fill 20-25 total objects.

## Phase 1 — Procedural terrain (primitives)

**Skill:** `procedural-terrain`

**Inputs:** `plan.terrain`, the Blender MCP session

**What happens:**

1. Claude calls `execute_blender_code` with a Python script that:
   - Adds a subdivided plane (default 100×100 verts over `plan.terrain.size_meters`)
   - Builds a geometry-nodes modifier `GN_Terrain` inside group `Terrain_Setup` with named frame `Displacement (noise + radial falloff)` and exposed inputs (`Hill Height`, `Noise Scale`, `Edge Falloff`) — non-negotiable so the GN setup stays legible to anyone opening the file
   - Applies vertex displacement via noise (for hills) or radial mask (for islands)
   - Adds **placeholder solid-colour materials** to each surface — these get replaced in Phase 1.5
   - If `plan.terrain.water.present`, adds an ocean plane at `plan.terrain.water.level`
   - If the plan has a secondary islet (twin-island composition), adds it as a smaller separate plane

2. Sets up the camera framing per `plan.camera`.

**Template:** `.claude/scripts/blender/procedural-terrain.py` provides a known-good starting point with the GN node tree pre-built. Claude edits it for the specific terrain — it doesn't compose nodes from scratch.

## Phase 1.5 — Surface materials (PATINA)

**Skill:** `generate-material` (×3 in parallel)

**Inputs:** the procedural surfaces from Phase 1, `plan.style`

**What happens:**

1. For each surface (sand, water, grass), build a tile-prompt biased by `plan.style.anchor` + `plan.style.palette` + the magic phrase `"seamlessly tiling, no border artefacts"`.

2. Fire the PATINA gens in parallel via `fal-ai/patina/material` (text-to-PBR-set). Each returns BaseColor + Normal + Roughness + Metalness + Height PNGs. ~$0.08 at 1024px.

3. Apply each PBR set to the matching Blender primitive via the `apply_patina_material(...)` snippet (see `generate-material/SKILL.md`).

4. Take the **baseline screenshot** now — surfaces are textured. Save to `worlds/<slug>/iterations/000-terrain.png`.

5. Visual check: if a surface looks wrong (palette mismatch, broken tile), regenerate that one material with a tighter prompt or different seed. Cap at 2 PATINA retries per surface.

**Typical material spend per world:** 3 surfaces × $0.08 = **~$0.24**. Cheap enough to iterate.

## Phase 2 — Generate the objects

**Skill:** `generate-3d` (run ×N in parallel)

**Inputs:** each distinct `plan.objects[i].id` (NOT each instance — re-instancing happens in Phase 4)

**What happens for each distinct object class:**

1. **Check for a procedural alternative first.** If the object class matches a free Blender plugin (Stylized Fantasy Tree for palms, Blender Studio Rock Generator for boulders — see `docs/plugins-research.md`), invoke the plugin and skip the Tripo call. Saves ~$0.50 per matched class.

2. Build the generation prompt from `name + style.anchor + style.level_of_stylization`. Example:
   > "Tall stylised palm tree, Banjo-Kazooie / Wind Waker cartoon art style, vibrant saturated green fronds, thick textured trunk, slight curve, isolated on white background, centred, no shadows, single object only, simple readable silhouette, no microdetail."

   The "simple readable silhouette, no microdetail" tail is important — biases the reference image (and thus the Tripo output) toward shapes that fit the 5-15k face budget.

3. Generate a clean reference plate via `nano-banana-edit` ($0.039), saved as `<id>-ref.png`.

4. Call `tripo3d/p1/image-to-3d` via fal with:
   - `image_url`: the reference plate URL
   - `texture: true` (default — PBR maps auto-included in `pbr_model` output, $0.50)
   - `face_limit`: picked from the polycount routing table per object class (5-15k clamp enforced by wrapper)

5. **If the result is poor** — do NOT fall back to Trellis 2. Instead retry P1 with a tightened reference-plate prompt or a different `model_seed`. Cap at 2 retries per object. After that, escalate.

6. Download the `.glb` to `worlds/<slug>/assets/<id>.glb`. The `pbr_model` URL (when texture=true) is the PBR-textured variant — save as `worlds/<slug>/assets/<id>-pbr.glb`.

7. Update `worlds/<slug>/plan.json` with the generated paths, cost, and `face_limit`.

8. Log the cost.

**Re-instancing.** Phase 4 imports each `.glb` once per `count` value in `plan.objects`. So one Tripo gen of `palm-tall` can be placed 3-4 times across the island. Typical scene: 7-10 distinct gens, re-instanced to fill 20-25 total objects.

**Parallelism:** fal handles parallel requests. For 20-30 assets, fire them all at once and `Promise.all` — total wall-clock ~2-3 min.

**Fallback to free libraries:** for very generic items (rocks, basic plants, props), check `download_polyhaven_asset` first. Saves money on items that aren't visually distinctive. The Banjo-style stylised aesthetic mostly won't match what's on Poly Haven, but for some items (basic foliage, rocks) it's fine.

## Phase 3 — Sky & lighting

Inline in `build-world`. No dedicated skill.

**What happens:**

1. Pick a Poly Haven HDRI matching `plan.style.lighting`:
   - `golden-hour` → `kloofendal_43d_clear_puresky` or `qwantani_puresky`
   - `noon` → `kiara_5_noon` or `peppermint_powerplant`
   - `dusk` → `belfast_sunset`
2. `download_polyhaven_asset(asset_id, asset_type="hdris", resolution="2k")` via blender-mcp.
3. Set as world background via `execute_blender_code`.
4. Place a sun light, rotated to match the shadow direction Claude observed in the reference.

**v2 stretch goal:** generate a custom skydome via fal image gen + project onto a hemisphere. Not in v1 — Poly Haven covers the typical golden-hour / noon / dusk cases and is the most reliable path. Switch to generated skydome if a specific scene needs a palette not in the Poly Haven library.

## Phase 4 — Place and iterate (the autonomous loop)

**Skill:** `place-and-iterate`

**Inputs:** `plan.json` (now with all asset paths), the live Blender scene with terrain + sky

**What happens — the loop:**

```
iteration_n = 0
while iteration_n < 25:
    iteration_n += 1

    # 1. Import any not-yet-imported assets, place at their plan position
    for obj in plan.objects:
        for instance_idx in range(obj.count):
            if not_imported(obj.id, instance_idx):
                execute_blender_code(import_glb(obj.path, position=obj.approx_positions[instance_idx]))

    # 2. SEE the scene
    screenshot = get_viewport_screenshot(max_size=800)   # Image block
    save_to(f"worlds/{slug}/iterations/{iteration_n:03d}.png")

    # 3. JUDGE — Claude reads both screenshot + reference as multimodal
    # The model produces a delta-list:
    #   "palm-tall instance 2 is at (3, 0.5) but should be closer to the hut at (2, 1).
    #    The hut scale is wrong — too small. The rocks on the north shore look out of place
    #    because they're floating above the sand by ~0.3m."

    # 4. ADJUST
    for change in deltas:
        execute_blender_code(change.to_python())

    # 5. Save backup
    execute_blender_code("bpy.ops.wm.save_as_mainfile(filepath=f'worlds/{slug}/iterations/{n:03d}.blend.bak')")

    # 6. Convergence check
    if claude_judges("good enough — within 90% of reference") or no_changes_made_this_iteration:
        break

return final_blend
```

**The judge prompt structure** (this lives inside the skill):
> "Here are two images side by side: the reference and the current viewport. List concrete, actionable differences. For each, give: (a) what's wrong, (b) which object id and instance index, (c) the Blender Python you'd run to fix it. Return as a JSON array. If the scene is within 90% of the reference, return an empty array."

**Hard caps:** 25 iterations max. ~3 seconds per `get_viewport_screenshot` (Blender re-renders the viewport). ~10-20 sec per `execute_blender_code` round-trip. Realistic loop time: 15-30 minutes per scene.

## Phase 5 — Render

Inline in `build-world`.

1. Set Eevee Next as render engine (Blender 5.1+) for speed.
2. Set camera to match `plan.camera.framing` + `plan.camera.focal_length_mm`.
3. Render at 1920×1080, save to `worlds/<slug>/final.render.png`.
4. Save the final `.blend` to `worlds/<slug>/final.blend`.
5. Write `worlds/<slug>/cost.json` with the itemised fal spend.

## Success criteria

- `final.render.png` is recognisably the same location as `source/reference.png` (palette, silhouette, key objects roughly placed, terrain shape matches).
- `final.blend` opens cleanly in Blender 5.1.
- Total `fal` cost under **$10** for a 20-25-instance scene (Tripo + PATINA + nano-banana).
- Wall-clock under **25 min** from "build me a world" to `final.render.png` (composite-screenshot + Eevee Next + every-5th-iter backup).

If those four hit, the scaffold has done its job — you have a reproducible end-to-end build.
