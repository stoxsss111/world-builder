# world-builder · Agent Context

You are the agent inside the `world-builder` project. Your job: take a reference image from `input/` and assemble a full 3D scene in Blender that matches it.

## Required Blender state — the `world.blend` rule

- **The user opens Blender.** You can't launch Blender from Claude (no `Bash(blender ...)` permission, and even with it the MCP add-on wouldn't auto-attach to the new instance). If Blender isn't open when you start, **stop and ask** — don't try to work around it.
- **The first thing `build-world` does in Blender is save-as `worlds/<slug>/world.blend`** (absolute path). From that moment on, `bpy.data.filepath` points there; every `bpy.ops.wm.save_mainfile()` overwrites it; nothing of the user's session escapes to a temp `Untitled.blend`. See `build-world` SKILL.md Step 2 for the exact snippet.
- **After Step 2, never call `save_as_mainfile` without `copy=True` until the final save.** Otherwise you hijack the live filepath and subsequent `save_mainfile()` calls go to the wrong file. Pattern:
  - Live save → `bpy.ops.wm.save_mainfile()` (writes to `world.blend`)
  - Iteration snapshot → `bpy.ops.wm.save_as_mainfile(filepath='<abs>/worlds/<slug>/iterations/NNN.blend.bak', copy=True)`
  - Final freeze → `bpy.ops.wm.save_as_mainfile(filepath='<abs>/worlds/<slug>/final.blend', copy=True)` then `save_mainfile()` to flush
- **Clean viewport for recording or sharing.** After save-as in Step 2, immediately apply the viewport-beautify snippet (`build-world` Step 3): perspective camera, material-preview shading, Eevee Next render engine, overlays trimmed (no grid floor, no axis lines, no gizmos, no statistics, no cursor). Looks clean from frame 1.

## Operating mode

- **Vision-loop is your superpower.** Use the `blender` MCP server's `get_screenshot_of_window_as_image` (or `render_viewport_to_path` for a clean render-buffer capture) to SEE what you've built. Compare it visually against the reference image. Iterate.
- **Don't ask between iterations.** When the user runs `claude --dangerously-skip-permissions` and asks for a world build, run the full loop unattended. Show progress as you go. Stop only when (a) the visual match is good, or (b) you hit a hard error, or (c) iteration count exceeds 25.
- **Show the cost.** Track every `fal` call (each Tripo H3.1 textured generation is ~$0.50). At the end, summarise total spend.

## `controls/top.png` is the source of placement coordinates

Object positions are NOT eyeballed into `plan.json.approx_positions` anymore. They are mechanically back-projected from `controls/top.png` via this protocol:

1. **Landscape verification loop (up to 5 attempts).** After the landscape Tripo mesh is imported, render a top-down ortho view from a Blender camera framed to `plan.terrain.bbox`. Diff against `controls/top.png`. If silhouette / scale / rotation / grass-patch positions don't match, adjust the landscape transform (scale, rotate Z, translate XY) and re-render. Up to 5 attempts before escalating. The verified mapping = pixel rect of `controls/top.png` ↔ `plan.terrain.bbox` in world XY.
2. **Per-class detection on `controls/top.png`.** Call `fal-ai/moondream3-preview/detect` once per object class (`prompt: "palm tree"` / `"stone arch"` / ...). Returns normalized bboxes that we scale to pixels. ~$0.005 / call. (Florence-2 only returned 1 instance per class on dense top-down scenes; Moondream-3 returns the multi-instance result we need.)
2.5. **Set-of-Mark review by Claude.** Auto-detection is noisy. Run `annotate-detections.py` to draw colored numbered dots per detected instance on `top.png` → `top-marked.png`. Claude reads it and emits `detections-reviewed.json` (drop misclassified marks, drop semantic dupes, optionally add missed instances). See `build-world` Phase 3.6.
3. **Centroid of each bbox = (x + w/2, y + h/2)** in pixel space.
4. **Back-project** every centroid through the verified ortho mapping:
   - `world_x = bbox.xmin + (px / image_w) × (bbox.xmax − bbox.xmin)`
   - `world_y = bbox.ymax − (py / image_h) × (bbox.ymax − bbox.ymin)` (Y flips because image y-axis points down)
5. **Place** one instance per centroid per class. No more `approx_positions` block in `plan.json` — `plan.objects[*]` lists the class metadata (face_limit, scale_hint, prompt) only.

`controls/fl45.png` and `controls/fr45.png` stay as additional comparison anchors for the six-up after placement, but they don't drive XY positions.

## Control views are the ground truth

Before any Blender work that follows the reference, generate **three control views** from the reference via nano-banana edit and save them to `worlds/<slug>/controls/`:

1. `controls/top.png` — strictly top-down orthographic of the same scene, no perspective.
2. `controls/fl45.png` — same scene rendered from front-left at 35-45° elevation, full bbox in frame.
3. `controls/fr45.png` — same scene rendered from front-right at 35-45° elevation, full bbox in frame.

Use the `make-control-views` skill (see `.claude/scripts/asset-pipeline/make-control-views.mjs`). Prompts must be strict: "exact same scene, no new objects, full bounding box in frame, same stylisation."

Every iteration of the placement loop renders the **same three camera angles** (top-down ortho, front-left-45°, front-right-45°) at fixed positions derived from the scene bounding box. The three rendered panels go side-by-side with the three control panels for a six-up comparison. This is the only comparison protocol that gives Claude unambiguous spatial feedback — a single bird-view leaves too much ambiguity about depth.

Use `.claude/scripts/blender/render-3-views.py` as the **only** loop renderer. It takes a bbox and an iter index, nothing else varies.

## Tripo textured for everything 3D, PATINA only on flat planes

Every 3D mesh in the scene — **including the big base shapes** (island floor, satellite spit, large terraced platforms) — is generated with **Tripo H3.1 `texture=True`** ($0.50 each). The base inherits the cartoon silhouette AND the painted texture (sand grain, grass patches, edge gradient) from the nano-banana extract, so it reads as part of the scene immediately, with no UV-projection step.

**Extract the base from `source/reference.png` (the original 3/4 painted view), NEVER from `top.png`.** A flat top-down silhouette has no depth cues, so Tripo returns fragmented garbage shapes. The original reference has volume, lighting, slab-edge thickness, and surface relief on the grass patches — all the depth cues Tripo needs to reconstruct a clean slab. The nano-banana edit prompt removes every placed object and keeps the SAME 3/4 painted view with all its volume cues intact ("juicy painted chunk of island"). A single Tripo H3.1 gen at 20k polycount covers the whole base.

`top.png` stays as the placement coordinate reference only — it drives Phase 3.5 detection and Phase 4 back-projection, not Phase 1 geometry.

**PATINA materials are reserved for flat primitive planes only.** In practice that means:
- the water surface (always),
- optional flat grass disks that sit on top of the base,
- nothing else.

Whenever PATINA is applied to a plane, **tile scale must be calibrated visually**: render the textured plane at multiple `Mapping.Scale` values (e.g. 0.5, 1, 2, 4) and pick the one whose wave/grain pattern density matches the reference. Bake the chosen scale into the material before continuing — never ship a plane with a default-scale PATINA tile.

Why this rule: planar-projecting a PATINA map onto a curved Tripo base flattens the lighting cues Tripo painted into the geometry, so the slab loses its 3D read. Trusting Tripo's textured output keeps the painted highlights/shadows aligned with the silhouette.

Why primitives are still wrong for the base: they look like fan-out CAD blocks from any angle that isn't perfectly axis-aligned. A Tripo-gen base inherits the cartoon silhouette of the reference and reads as part of the scene.

## The procedural-vs-generated split

- **Tripo H3.1 textured (~$0.50)** = every 3D mesh — base shapes (island floor, spit) AND every object (palms, chests, lanterns, log-stumps, boulders, flowers). face_limit cap raised from 15k → 20k (H3.1 handles the extra detail cleanly). **The input image to Tripo must be a 3/4 painted view with volume cues — never a flat top-down silhouette.** For the base, extract from `source/reference.png` (NOT `top.png`).
- **Toon shader as a final pass.** After placement is final, run `.claude/scripts/blender/apply-toon-shader.py` to wrap every used material with a Shader-to-RGB → 3-stop ColorRamp chain + enable Freestyle outlines (black, 2.5 px, silhouette + crease). This is what turns the render from "PBR demo" into "Banjo screenshot".
- **`plan.scale_per_class` override map** lets you correct over-scaled objects per-scene without editing scripts. The placer reads `{"boulder-mossy-large": 1.6, "palm-tall": 5.5, ...}` and overrides the defaults.
- **Iterative refinement is MANDATORY after back-projection** — 5–6 rounds before the toon pass: (1) heroes, (2) trees, (3) boulders, (4) fillers, (5) full-scene polish, (6) optional hide-and-iterate for stuck cases. Each round = render → look class-by-class → fix scale/rotation/position in Blender → re-render. Placement is never one-shot. See `build-world` Phase 4.5.
- **Default heights are Banjo-tuned.** Palm-tall is 5.5 m (towering), stone-arch 3.5 m (walkable portal), tiki-hut 3.2 m, boulder-large 1.8 m (smaller than the hut). These are real-world-ish proportions for the Banjo aesthetic — first placement should look roughly right.
- **`rotation_mode = 'XYZ'` is required on every Tripo-imported mesh.** Tripo's GLB import sets `rotation_mode='QUATERNION'`, which makes `rotation_euler` assignments silent no-ops. Set `obj.rotation_mode='XYZ'` immediately after import and before any rotation work. `place-from-detections.py` does this on both protos and instances. If you ever see "rotation didn't apply visually," check this first.
- **Landscape rotation must be auto-derived, not chosen by sweep.** Compute the spit's centroid in mesh-local coords, calculate its angle from main-island centroid, and set Z rotation to target spit at world (+X, −Y) so back-projection from `top.png` aligns. `(target_angle_deg=-45) - (spit_local_angle_deg)` = the rotation to apply.
- **Object origin = bbox CENTER-BOTTOM.** After scaling each proto to its target height, set its origin via `bpy.context.scene.cursor.location = (cx, cy, z_min)` + `bpy.ops.object.origin_set(type='ORIGIN_CURSOR')`. Then `inst.location = (wx, wy, 0)` plants the object's footprint EXACTLY at the back-projected pixel position on the z=0 ground — no more drift between the dot in `top.png` and where the mesh actually sits.
- **Per-instance scale from detection bbox.** For multi-instance classes, scale each instance by `sqrt(instance_bbox_area / median_class_bbox_area)` clamped to ±40 %. Big palm in detection → big palm in scene. Encoded in `place-from-detections.py`.
- **Annotated top renders for Claude-vision review.** `.claude/scripts/blender/annotate-scene-top.py` renders the full scene top-down ortho framed to `plan.terrain.bbox`, then PIL-overlays each `WB_asset_*` with a colored dot + its `wb_tag` label at the pixel-projected position. Claude reads the labeled image side-by-side with `controls/top.png` and emits per-object fixes (move XY, rescale, rotate). **No iteration cap on this loop** — keep refining until the annotated render matches `top.png`. This is the Claude-in-the-loop refinement pass.
- **PATINA materials ($0.06-0.10 each)** = flat primitive planes only (water; optional flat grass).
- **Primitive Blender plane** = the geometric carrier for PATINA.
- **Tripo H3.1 textureless ($0.40)** = NOT USED for base shapes anymore (legacy from the v2 iteration; left in `generate-base-shape` as an opt-out only, default is textured).

## Iterative placement, biggest → smallest, in batches of ~5

Don't dump 25 objects in one shot — the scene gets unreadable and the loop has nothing to grip on. Sort the plan's objects by `face_limit` descending (which is also size descending), take **5 at a time**, place that batch, render the 3 angles, compare against the 3 control views, adjust the batch in place, then continue with the next 5.

Hard rule: **no batch is "done" until its 3-angle render visibly matches the control views.** Typical: 1-3 micro-adjustments per batch. After all batches placed, do 2-3 polish iterations on the full scene.

This caps the loop at ~5-7 batches × ~3 micro-iters = ~15-20 total renders, well under the 25-iter ceiling, and each render has a clear scoped question ("are these 5 in the right place?") instead of "is everything correct?".

## Zone annotation (optional, recommended)

Before placement, generate a planning map from `controls/top.png` via nano-banana edit: redraw it with **solid-color zones** (yellow=sand, blue=water, green=grass) and **colored dots** marking where each object class goes (red=hero structures, orange=tall palms, pink=small palms, gray=boulders, brown=wood). Save as `controls/zones.png`. Use it as the source of truth for the `approx_positions` in `plan.json`.

If fal SAM-3 (`fal-ai/sam-3/image`) is more useful, segment the top-down with it instead. The deliverable is the same: a colored map that Claude reads alongside the geometry.

## The skills

Located in `.claude/skills/`. Use the right tool for the task:

| Skill | When to use |
|---|---|
| `build-world` | Top-level orchestrator. The user says "build a world from X" — start here. |
| `analyze-reference` | Read the reference image, produce a scene plan: terrain shape, object list, positions, style, palette, lighting. |
| `make-control-views` | Generate the 3 nano-banana control views (top, fl45, fr45) + the zone annotation map. Runs after `analyze-reference`, before any Blender work. |
| `generate-base-shape` | Tripo H3.1 textureless gen for the island floor + satellite spit + large platforms. Planar-projects the PATINA sand on top. |
| `generate-material` | Generate one tiled PBR material set (BaseColor/Normal/Roughness/Metalness/Height) via fal PATINA. Used by `generate-base-shape` for the planar-projected surface texture. |
| `generate-3d` | Generate one atomic 3D object via Tripo H3.1 textured ($0.50). No fallback — retry P1 with a better reference plate if it fails (cap 2 retries). |
| `place-and-iterate` | The autonomous loop: SORT by size descending, place in batches of 5, render the same 3 angles as the control views via `render-3-views.py`, compare six-up, adjust the batch, then next 5. |

## The MCP tools you have

We use the **official Blender Lab MCP server** (installed per `MCP_SETUP.md`, not the ahujasid PyPI package). After `.mcp.json` connects it, the `blender` server exposes:

- `mcp__blender__execute_blender_code(code)` — your hands. Run arbitrary Python in the live Blender session. This is how you save-as, set viewport, build terrain, import GLBs, position objects, set up materials, render.
- `mcp__blender__get_screenshot_of_window_as_image()` / `get_screenshot_of_area_as_image()` — **your eyes.** Returns an MCP Image block (PNG, multimodal). Use after every change to assess.
- `mcp__blender__get_screenshot_of_window_as_json()` — text-only JSON of window layout, active object, selection. Cheaper than a screenshot when you only need state, not pixels.
- `mcp__blender__get_objects_summary()` / `get_object_detail_summary(name)` — query the scene's collections and one object as JSON.
- `mcp__blender__get_blendfile_summary_*()` — file analysis (datablocks, missing files, linked libraries, path info, usage guess).
- `mcp__blender__get_python_api_docs(identifier)` / `search_api_docs(query)` / `search_manual_docs(query)` — Blender API and manual lookup bundled with the server. Use when you're about to call a `bpy.ops.*` you're not 100% sure of, instead of guessing.
- `mcp__blender__render_viewport_to_path(path)` / `render_thumbnail_to_path(path)` — render to a file path (useful for the 3-angle composite and the final 1920×1080 shot).
- `mcp__blender__jump_to_view3d_object_by_name(name)` / `jump_to_tab_by_name(name)` — viewport navigation.

The image-returning tools (`get_screenshot_of_window_as_image`, `get_screenshot_of_area_as_image`) come back as multimodal input you can reason about directly. Use them often.

**Not available** in the official MCP: Poly Haven / Sketchfab integrations were ahujasid-only. If you need CC0 assets, either (a) generate via fal (Tripo H3.1 / PATINA) or (b) the user can download manually and you import via `execute_blender_code` + `bpy.ops.import_scene.gltf`.

## Output layout

Every world goes into `worlds/<world-slug>/`:

```
worlds/<world-slug>/
├── source/
│   └── reference.png          # copied from input/
├── plan.json                  # the scene plan you produced in Step 0
├── assets/
│   ├── <object-1>.glb
│   ├── <object-1>.preview.png
│   └── ...                    # one .glb per generated asset
├── iterations/
│   ├── 001.png                # screenshot after iteration 1
│   ├── 001.note.md            # what you changed + why
│   ├── 005.blend.bak          # snapshot every 5th iter (copy=True, does not steal active filepath)
│   ├── 002.png
│   └── ...
├── world.blend                # the LIVE working file — pinned in build-world Step 2, overwritten each iter
├── final.blend                # snapshot of converged state (copy=True so world.blend stays live)
├── final.render.png           # rendered camera shot
└── cost.json                  # itemised fal spend
```

## Hard rules

- **Lock to Blender 5.1 LTS.** GN API drifts. Pin in errors if user is on a different version.
- **Render engine for the loop = Eevee Next.** NOT Cycles. Cycles is too slow for a 25-iteration loop. Confirm `bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'` before kicking the loop.
- **Composite 3 angles into one PNG per iteration** (top-down + bird-view + side), feed as a single multimodal input to the judge step. Do NOT take three separate `get_viewport_screenshot` calls — wasteful.
- **Cap `get_viewport_screenshot(max_size=800)` for the initial baseline.** For the loop, use the 3-angle composite at 512×384 per panel.
- **Set `MAX_MCP_OUTPUT_TOKENS=50000` in env before long loops** — image content shares the same cap as text and silently truncates otherwise.
- **Target 20-25 objects per world.** That's the working range for a Banjo-style island. 25 is the soft cap before asking the user, NOT a goal. A 10-12-object scene is also valid if the reference is sparse.
- **Pre-set viewport to perspective + material-preview shading** before kicking the loop. Otherwise your first screenshot will be whatever wireframe the user left.
- **Live save every iteration** with `bpy.ops.wm.save_mainfile()` (overwrites `world.blend`, <1s for our scenes). **Snapshot every 5th iteration** to `iterations/NNN.blend.bak` via `save_as_mainfile(..., copy=True)` so the snapshot doesn't steal the active filepath.
- **Hard-cap at 25 iterations.** If convergence isn't reached, escalate to the user with the last composite + your read of what's wrong.
- **No Trellis 2 fallback.** If Tripo H3.1 fails, retry with a better reference plate (max 2 retries), then escalate.

## When in doubt

- Read `docs/ARCHITECTURE.md` for the pipeline.
- Read `docs/PIPELINE.md` for the step-by-step.
- Read `docs/api-research.md` for provider choices and costs (Tripo H3.1, PATINA, nano-banana).
- Read `docs/style-references.md` for the stylistic anchors (Wind Waker, Banjo-Kazooie, Mario Sunshine, Bananza).
- Read `docs/blender-mcp-setup.md` for the MCP wiring details.
- Read `docs/plugins-research.md` for optional Blender plugins (Stylized Fantasy Tree Generator, Rock generators, Blender MCP Pro) that can replace specific Tripo gens with free procedural alternatives.

## Tone

The user prefers terse responses with no trailing summaries. Show progress as terminal output, not chat narration. All artifacts in English.
