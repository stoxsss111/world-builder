---
name: "build-world"
description: "Top-level orchestrator. Take a reference image from input/ and assemble a full stylised 3D scene in Blender via the autonomous vision loop. Use when the user says \"build me a world\" / \"make a scene\" / \"blast this into Blender\"."
---

## Codex adaptation

Use this as the top-level world-building skill. In this migrated skill, `$1` means the world slug. Use the Codex tools available in the current session; old source tool metadata is guidance, not a Codex permission boundary.

You are building one stylised 3D scene in Blender from one reference image.

## Required state

- Blender 5.1 LTS is open by the user (Codex must not launch Blender for this workflow — ask the user to open it if it isn't running) and the BlenderMCP add-on is connected on port 9876.
- The current Codex session exposes the `blender` MCP tools. If not, stop before live Blender work and ask the user to reload/connect MCP.
- `MAX_MCP_OUTPUT_TOKENS=50000` is set in the shell that launched the agent when applicable.
- `FAL_KEY` is set in `.env`.

If any of these are missing, run `.claude/hooks/setup-check.sh` and ask the user to fix what it reports.

## Steps

1. **Resolve the reference and the slug.**
   - The user says: `build me a world from input/banjo-beach.png called banjo-beach`.
   - If the slug is missing, derive from the filename.
   - Copy `input/<file>.png` → `worlds/<slug>/source/reference.png`.

2. **Pin the working Blender file to the world folder — FIRST thing in Blender.** Before any other `execute_blender_code` call, save-as the currently-open scene to `worlds/<slug>/world.blend` using an **absolute** path. From this moment on, `bpy.data.filepath` points here; every `save_mainfile()` writes here; nothing of the user's session escapes to a temp file.

   ```python
   execute_blender_code("""
   import bpy, os
   project_root = r"<absolute path to world-builder>"   # filled in by build-world
   world_slug   = r"<slug>"
   target = os.path.join(project_root, "worlds", world_slug, "world.blend")
   os.makedirs(os.path.dirname(target), exist_ok=True)
   bpy.ops.wm.save_as_mainfile(filepath=target)
   assert bpy.data.filepath == target, f"save_as failed: {bpy.data.filepath}"
   print(f"world.blend pinned at {target}")
   """)
   ```

   From here on, ONLY use:
   - `bpy.ops.wm.save_mainfile()` — overwrites `world.blend` (the live file).
   - `bpy.ops.wm.save_as_mainfile(filepath=..., copy=True)` — snapshot to a different path (the `copy=True` keeps `bpy.data.filepath` intact). This is what `place-and-iterate` uses for every-5th-iter `iterations/NNN.blend.bak`.
   - Never call `save_as_mainfile` without `copy=True` again until the final save in Step 9 — otherwise you hijack the active filepath and subsequent `save_mainfile()` calls go to the wrong file.

3. **Reset the Blender viewport** for a clean look: perspective camera, material-preview shading, render engine Eevee Next, overlays off (no grid clutter, no gizmos, no statistics). The viewport must look presentable from frame 1 (recording-ready).

   ```python
   execute_blender_code("""
   import bpy
   bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
   for area in bpy.context.screen.areas:
       if area.type != 'VIEW_3D':
           continue
       for space in area.spaces:
           if space.type != 'VIEW_3D':
               continue
           space.shading.type = 'MATERIAL'
           if space.region_3d.view_perspective == 'ORTHO':
               space.region_3d.view_perspective = 'PERSP'
           # clean overlays for recording
           space.overlay.show_overlays    = True   # keep on, but tame what's drawn
           space.overlay.show_floor       = False
           space.overlay.show_axis_x      = False
           space.overlay.show_axis_y      = False
           space.overlay.show_cursor      = False
           space.overlay.show_extras      = False
           space.overlay.show_relationship_lines = False
           space.overlay.show_object_origins     = False
           space.overlay.show_text        = False
           space.show_gizmo               = False
   bpy.ops.wm.save_mainfile()   # persist the recording-ready viewport
   """)
   ```

4. **Phase 0 — Analyse the reference.** Invoke the `analyze-reference` skill. It reads the image and writes `worlds/<slug>/plan.json`. Confirm:
   - Total instances (sum of `object.count`) ≤ 25 by default. If the analyzer needs more, it will stop and ask you — relay the question to the user before proceeding.
   - Every object has a `face_limit` in `[5000, 15000]`.
   - Every `priority: hero` object has a clear `name`.
   - `terrain.size_meters` and a `terrain.bbox` (xmin, ymin, zmin, xmax, ymax, zmax) covering the full intended scene. The bbox feeds every subsequent render — get it right.

5. **Phase 0.5 — Make control views.** Run `node .claude/scripts/asset-pipeline/make-control-views.mjs --reference worlds/<slug>/source/reference.png --output-dir worlds/<slug>/controls --style-anchor "<plan.style.anchor>"`. This generates three nano-banana views from the reference:
   - `controls/top.png` — strictly top-down ortho of the same scene
   - `controls/fl45.png` — front-left 45° elevation
   - `controls/fr45.png` — front-right 45° elevation
   Optional but recommended: also run `annotate-top-down.mjs --top controls/top.png --output-dir controls` to produce `controls/zones.png` — a flat zoned map with colour-coded sand/water/grass and per-class colored dots at each object position. Read `zones.png` back; use the dot positions to refine `plan.objects[].approx_positions` BEFORE moving on. The control views are the ground truth for every iteration that follows.

6. **Phase 1 — Generate the WHOLE LANDSCAPE via Tripo H3.1 from a JUICY 3/4 painted reference.** The base is the landscape — main island + satellite spit together — generated as ONE Tripo H3.1 textured mesh, face_limit 20 000.

   **Critical: the input image to Tripo must be a VOLUMETRIC PAINTED 3/4 VIEW, not a flat top-down silhouette.** Tripo extrudes depth from depth cues (lighting, shading, surface gradient, occlusion). A flat top-down silhouette has zero depth cues, so H3.1 returns garbage shapes (we observed: 75 fragmented components, sliver geometry, missing spit). A 3/4 painted view shows the slab edge thickness, the curvature of grass mounds on top, and the warm side-lit shading — all of which H3.1 needs to reconstruct the volume.

   **Source image:** the **original `source/reference.png`** — it IS a 3/4 painted view by definition. Do NOT use `top.png` (flat, no depth cues) and do NOT use `fl45.png`/`fr45.png` (nano-banana's interpretations — they drift). Original is the ground truth that has both the right silhouette and the right depth.

   **nano-banana edit prompt:** "Show only the sandy island landscape from this Banjo-Kazooie cove illustration — the sand slab and grass patches sitting on it — in the EXACT SAME 3/4 angle, EXACT SAME painted style, EXACT SAME lighting, EXACT SAME warm sand-edge gradient and shading. Remove EVERY palm tree, EVERY rock and boulder, EVERY hut, EVERY torch, EVERY chest, EVERY campfire and log, EVERY shell, EVERY flower. Keep the small satellite spit attached. Keep the painted volume cues — slab edge thickness, side lighting, surface relief on the grass patches. White background outside the islands, no water visible, no shadows from removed objects. The result must look like a juicy painted chunk of island carved cleanly out of the original."

   **Tripo H3.1 params:** `texture=True`, `face_limit=20000`. The painted grass patches and side gradient come baked into the mesh.

   Import, run a **connected-components clean-up by XY footprint area** (H3.1 sometimes returns multi-island fragments — keep components ≥1% of the largest by footprint area; tighten to 0.5% if interior holes appear). Scale so the longest XY axis matches `plan.terrain.size_meters`, flatten Z to a slab thickness (~0.7 m), rest the top at z=0.

   **The water is the ONLY base primitive:** flat `bpy.ops.mesh.primitive_plane_add` at z = -(slab_thickness × 0.7) so the water cuts into the slab edge for a beach effect.

   **Fallback if the Tripo gen still produces fragmented garbage after one retry:** use `.claude/scripts/blender/extrude-landscape-from-mask.py` to extrude directly from the top.png mask — geometrically deterministic, no Tripo needed, but the silhouette is "cookie-cutter" without painted side relief. Acceptable as a backup, not as a default.

7. **Phase 1.5 — PATINA on water only, with tile calibration.** Generate the water PBR set via `generate-material`. Build a planar-projected material on the water plane (Geometry.Position → CombineXYZ(X,Y,0) → Mapping → image textures, extension=REPEAT). **Calibrate the tile scale**: render the water plane at scales 0.5 / 1 / 2 / 4 / 8 via `render-3-views.py` and pick the one whose wave/foam density matches the reference. Bake that scale into the Mapping node. No tile calibration = no progress past this step. Sand and grass do NOT need PATINA — Tripo already painted them into the base mesh.

7.5 **Phase 1.75 — Landscape verification loop (up to 5 attempts).** Render the landscape mesh top-down ortho via `.claude/scripts/blender/verify-landscape.py` framed to `plan.terrain.bbox`. Save to `iterations/landscape-NN.png`. Compare to `controls/top.png`: silhouette, scale, rotation, grass-patch positions. If misaligned, adjust the `WB_Landscape` object's `rotation_euler.z`, uniform scale, and `location.xy`, then re-render. STOP when aligned, or after 5 attempts (escalate to user with the side-by-side). The verified state means the pixel rect of `controls/top.png` maps directly to `plan.terrain.bbox` in world XY — that mapping is the contract for Phase 4's placement.

8. **Phase 2 — Generate the 3D objects.** For each object in `plan.objects`:
   - nano-banana edit to extract the object on white from the reference (or from a tighter crop). Save the fal CDN URL — that's what Tripo wants as input.
   - Invoke `generate-3d` → `tripo3d/p1/image-to-3d` with `texture=True` (~$0.50). No Trellis fallback — retry P1 with a tighter plate if it fails (cap 2 retries).
   - Fire all gens in parallel via a driver script.
   - Save `.glb` to `worlds/<slug>/assets/<id>/<id>.glb`.
   - Track running cost in `worlds/<slug>/cost.json`.

9. **Phase 3 — Sky & lighting.** No Poly Haven in the official Blender Lab MCP. Use a procedural world shader (Sky Texture node) tinted to match `plan.style.lighting` (warm peach for golden-hour). Add a sun light, rotate to match the reference shadow direction. Roughly 30-45° elevation for golden-hour.

9.5 **Phase 3.5 — Detect per-class instance pixel positions on `controls/top.png`.** Call `.claude/scripts/asset-pipeline/detect-instances.mjs` which fires `fal-ai/moondream3-preview/detect` once per object class with `prompt: "<class label>"` (Moondream-3 outperforms Florence-2 / SAM-3 on dense top-down scenes — verified to return 5 palms vs 1 from the others). Each call returns N normalized bounding boxes scaled to pixel coords. Write `controls/detections.json` with the per-class list of pixel centroids `[{x_px, y_px, w_px, h_px}]`. Cost: ~$0.005 × N classes ≈ $0.05 total.

9.6 **Phase 3.6 — Set-of-Mark review by Codex.** Auto-detection is noisy: Moondream over-detects rocky shapes, sometimes classifies the same blob as multiple classes (palm AND boulder AND flower at one XY = visual chimera in the scene). Run:

   ```bash
   python .claude/scripts/asset-pipeline/annotate-detections.py worlds/<slug>
   ```

   This draws colored numbered dots + bbox outlines on `controls/top.png` per detected instance and writes `controls/top-marked.png` (+ `top-marked-legend.json` mapping mark → class). Then Codex reads `top-marked.png` alongside `top.png` and emits **`controls/detections-reviewed.json`** with these corrections:
   - **drop** marks that are misclassified (e.g. a "boulder" dot sitting on the tiki hut)
   - **drop** duplicates across classes (the placer's geometric dedup at 30px catches most of these but Codex catches semantic dupes the geometric pass misses)
   - **add** instances the detector missed (rare, but happens when a hero is partially occluded)
   - **keep the class label** of each remaining mark

   The placer prefers `detections-reviewed.json` if present, falls back to `detections.json`. Set-of-Mark prompting (Yang et al., 2023) is the published technique here — vision LLMs are unreliable at outputting raw coordinates but very reliable at *picking* among labelled candidates.

10. **Phase 4 — Place + iterate (BACK-PROJECTED placement).** Invoke `place-and-iterate`. It runs `.claude/scripts/blender/place-from-detections.py`, which reads `controls/detections-reviewed.json` (or `detections.json`) + `plan.terrain.bbox`, runs a geometric **30-pixel cross-class dedup** pass, then back-projects every remaining centroid to world XY. One instance per centroid per class. Then renders the six-up via `render-3-views.py`, compares against `controls/{top,fl45,fr45}.png`, micro-adjusts any obviously-misplaced instance, and re-renders. Batched 5-at-a-time biggest-to-smallest still applies for the *order* of placement.

10.5 **Phase 4.5 — Iterative refinement rounds (mandatory, 5–6 rounds).** Placement is NEVER one-shot. After back-projection, walk through these rounds before the toon pass. Each round = render → look class-by-class → apply fixes in Blender (no fal cost) → re-render to confirm. Don't advance to the next round until the current class group reads right.

  **Round 1 — Hero anchors** (`stone-arch`, `tiki-hut`, `hut-stairs`, `tiki-torch`, `campfire`, `treasure-chest`).
  Render bird-view 1280×720. Check each hero for: scale (Banjo-correct, see defaults), Z-rotation (does the arch's opening face the camera? does the hut's door face front? does the chest face the camera?), XY position relative to the controls. Fix via direct `obj.scale`, `obj.rotation_euler`, `obj.location` edits. Re-render.

  **Round 2 — Tree framing** (`palm-tall`, `palm-small`).
  Optionally `hide_render=True` on non-tree objects so you can see the tree silhouette cleanly. Check: do tall palms frame the scene corners? are small palms close enough to the hut to read as "around the hut"? are positions matching control top.png? Fix. Un-hide.

  **Round 3 — Boulder mass** (`boulder-mossy-large`, `boulder-mossy-small`).
  Boulders are the most-broken class historically (used to dominate the scene). Check: are boulders smaller than the hut? are large boulders clustered on the right side per reference? are small boulders scattered as accents, not stacked? Fix scale defaults via `plan.scale_per_class` if a global multiplier is needed, OR per-instance via direct `obj.scale` for the few outliers.

  **Round 4 — Filler scatter** (`flower-pink`, `conch-shell`, `log-stump`).
  These add life but shouldn't dominate. Check: flowers near campfire + edge of spit, shells on the spit, log-stumps near the campfire. Z-rest properly so they're not floating or buried.

  **Round 5 — Full scene polish.**
  Everything visible. Six-up render against `controls/{top,fl45,fr45}.png`. Identify any remaining clash (overlapping props, hero occluded by palm, etc.) and fix. This is also where you do per-class Z-rotation passes for objects that should face the camera (arch, chest, hut door).

  **Round 6 — Hide-and-iterate (only if rounds 1-5 didn't converge).**
  If something is fundamentally off (a hero in the wrong half of the island), use `hide_render` to work on subsets in isolation. This is a tool, not a default — `hide_render` makes objects invisible to the renderer but they're still in the scene; un-hide before the toon pass or they'll vanish from the final.

  Hard cap: 6 rounds. After that the toon pass runs even if convergence isn't perfect — escalate the remaining issues to the user.

10.6 **Phase 5 — Toon shader pass.** Apply `.claude/scripts/blender/apply-toon-shader.py` (passing `PROJECT_ROOT` + `WORLD_SLUG`). It walks every USED material in the scene, wraps Base Color through a 3-stop ColorRamp + Shader-to-RGB chain so Eevee renders hard cel-shaded bands, then enables Freestyle with black 2.5 px outlines on silhouette + border + crease edges (140°). This is what makes the render feel like a Banjo screenshot instead of a PBR demo. Run AFTER placement is final — the toon wrap doesn't survive re-applying base materials.

11. **Phase 5.1 — Render & freeze the final.** Eevee at 1920×1080, camera framed per `plan.camera`. Output to `worlds/<slug>/final.render.png`. Snapshot the world to `worlds/<slug>/final.blend` via `save_as_mainfile(filepath=..., copy=True)` so the user can still re-open `world.blend` to keep iterating. Do one last `save_mainfile()` after to make sure the live file matches.

12. **Summarise.** Read `cost.json`, count iterations, write a one-screen recap to the terminal with: total wall-clock, total fal cost (Tripo textured + Tripo textureless + PATINA + nano-banana), iterations used, path to final render.

## Output layout

```
worlds/<slug>/
├── source/reference.png
├── plan.json
├── controls/
│   ├── top.png                       (nano-banana top-down ortho of the reference)
│   ├── fl45.png                      (nano-banana front-left 45°)
│   ├── fr45.png                      (nano-banana front-right 45°)
│   ├── zones.png                     (nano-banana zone-coded planning map; optional)
│   └── index.json                    (request ids + URLs)
├── materials/
│   ├── sand/{basecolor,normal,roughness,metalness,height}.png
│   ├── water/...
│   └── grass/...
├── assets/
│   ├── base-island.glb               (Tripo H3.1 textureless, planar-projected PATINA sand)
│   ├── base-spit.glb                 (Tripo H3.1 textureless)
│   ├── <object-id>/<object-id>.glb   (Tripo H3.1 textured)
│   └── <object-id>/preview.png
├── iterations/
│   ├── 000-base.png                  (3-angle composite of just the base + materials)
│   ├── 001.png                       (3-angle composite — same cameras every iter)
│   ├── 001-vs-controls.png           (six-up: controls top row, current bottom row)
│   ├── 001.note.md                   (the agent's delta-list for this iter)
│   ├── 005.blend.bak                 (.blend backup, every 5th iter)
│   └── ...
├── world.blend                       (LIVE working file)
├── final.blend
├── final.render.png                  (1920×1080 Eevee bird-view)
└── cost.json                         (itemised Tripo + PATINA + nano-banana spend)
```

## Stop conditions

- Convergence reached (Codex judges 90% match) — happy path
- 25 iterations — hard cap. Save what we have, escalate with the last screenshot + the agent's read of what's wrong.
- Hard error (Blender crash, fal 5xx repeat, MCP connection lost) — escalate immediately, do NOT keep burning tokens.

## Do not

- Do not skip the terrain-cleanup phase (named groups, frames, exposed parameters) — the named groups are what make the GN setup legible.
- Do not request `max_size > 800` for screenshots — 4× cost without quality gain.
- Do not generate character assets — out of scope for v1.
- Do not exceed 25 instance generations per scene without explicit user confirmation. Default cap = 25 (≈ $12.50 fal at all-P1 / ≈ $7.50 mixed P1+Trellis).
- Do not exceed $20 fal spend per scene without user confirmation.
- Do not request `face_limit > 15_000` — the wrapper clamps to [5000, 15000] anyway; build prompts that match the budget.
