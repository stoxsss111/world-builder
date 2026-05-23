---
name: "place-and-iterate"
description: "The autonomous vision loop. Sort objects by size descending, place in batches of 5, render the same 3 angles as the nano-banana control views, compare six-up, micro-adjust, then continue. Eevee renders \u2014 fast."
---

## Codex adaptation

Use the available Codex image, file, shell, and Blender MCP tools. In this migrated skill, `$1` means world slug.

Run the batched placement loop on `worlds/$1/`.

## Two protocols, used in sequence

### **Gotcha: `rotation_mode = 'XYZ'` is REQUIRED on every imported Tripo object.**

Tripo's GLB import sets `rotation_mode='QUATERNION'` by default. Setting `rotation_euler` on such an object is a silent no-op — the value gets stored but ignored. Every script that touches a Tripo-imported mesh MUST set `obj.rotation_mode = 'XYZ'` first, otherwise rotation appears not to apply (no error, just no effect). This bit us once when landscape rotation looked like it changed but the rendered top-down showed the same orientation for all 4 angles. `place-from-detections.py` sets this on both the proto AND on each linked-duplicate instance.

### Protocol A — back-projected placement (one-shot, Phase 4)

1. Read `controls/detections-reviewed.json` (or `detections.json`) + `plan.terrain.bbox`.
2. Run cross-class 30-pixel dedup.
3. Back-project every centroid: `world_x = xmin + (px/img_w)*(xmax-xmin)`, `world_y = ymax - (py/img_h)*(ymax-ymin)`.
4. Per-class assignment (e.g. "palm tree" → palm-tall + palm-small) by bbox-area-descending.
5. Spawn instances at world XY with default heights from `DEFAULT_TARGET_HEIGHTS` (Banjo-tuned).

### Protocol B — iterative refinement rounds (Phase 4.5, MANDATORY 5-6 rounds)

Placement is **never one-shot**. After Protocol A, run these rounds:

| Round | Focus | What to check | Tools |
|---|---|---|---|
| 1 | Hero anchors | arch / hut / torch / chest / campfire — scale, Z-rotation, XY vs controls | `obj.scale`, `obj.rotation_euler`, `obj.location` |
| 2 | Tree framing | palm-tall, palm-small — corners + near-hut framing | same |
| 3 | Boulder mass | large + small boulders — clustered right per reference, NOT bigger than hut | `plan.scale_per_class` for global, per-instance for outliers |
| 4 | Filler scatter | flowers, shells, log-stumps — near campfire / on spit, sitting flat on z=0 | same |
| 5 | Full-scene polish | overlaps, occlusion, camera-facing rotation | same |
| 6 | Hide-and-iterate | only if 1-5 didn't converge — work on subsets via `hide_render=True`, ALWAYS un-hide before toon | `hide_render` toggle |

Each round = render → look class-by-class → fix in Blender → re-render to confirm. Don't advance until the current class reads right.

### The batched protocol (legacy, kept for cases without detections)

If detections are unavailable, fall back to size-descending batches of 5. Each batch ends only when its 3-angle render visibly matches the controls.

```
batch_index = 0
sorted_objects = sorted(plan.objects, key=lambda o: -o.face_limit)   # biggest first
batches = [sorted_objects[i:i+5] for i in range(0, len(sorted_objects), 5)]

for batch in batches:
    # Place every instance of every object in this batch at plan.approx_positions[*]
    place_batch(batch)

    micro = 0
    while micro < 3:
        micro += 1
        # Render the SAME 3 angles as the controls
        render_3_views(BBOX=plan.terrain.bbox, ITER=f"{batch_index:02d}-{micro}", CONTROLS_DIR="worlds/$1/controls")
        # Judge against the six-up
        deltas = judge_six_up()        # list of {tag, action, params}
        if not deltas: break
        apply_deltas(deltas)
        bpy.ops.wm.save_mainfile()      # live save every micro-iter

    batch_index += 1

# Final 2-3 polish passes on the FULL scene
for polish in range(3):
    render_3_views(...)
    deltas = judge_six_up()
    if not deltas: break
    apply_deltas(deltas)
    bpy.ops.wm.save_mainfile()
```

Hard rule: **only adjust objects from the current batch (or already-placed batches if a later batch reveals a fix is needed).** Don't add objects ahead of their batch.

## Pre-flight

- `worlds/$1/plan.json` exists; every object has `asset_path` and the plan has `terrain.bbox`.
- `worlds/$1/controls/{top,fl45,fr45}.png` exist (from Phase 0.5 of `build-world`).
- Base shapes are placed and PATINA-projected. Phase 1.5 done.
- Sky / sun is set. Phase 3 done.
- Render engine: **Eevee** (5.1 calls it `BLENDER_EEVEE` — the legacy enum name is gone, this IS Eevee Next). Confirm via `execute_blender_code`:
  ```python
  bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
  bpy.context.scene.eevee.taa_render_samples = 16  # fast; viewport quality
  ```
  Cycles is too slow for a 25-iteration loop. Eevee Next renders the composite in 1-3 seconds.

## The composite screenshot — the key optimisation

Instead of taking three separate `get_viewport_screenshot` calls (three Image blocks, 3× the token cost), the loop builds **one composite PNG** per iteration with three angles side-by-side and feeds it as a single multimodal input.

```
┌───────────────────────────────────────────────────┐
│ ┌───────────┐ ┌───────────┐ ┌───────────┐         │
│ │ TOP-DOWN  │ │ BIRD-VIEW │ │ SIDE-3/4  │         │
│ │ (ortho)   │ │ (matches  │ │ (rotated  │         │
│ │           │ │  reference│ │  +45 deg) │         │
│ └───────────┘ └───────────┘ └───────────┘         │
│                                                   │
│ iter NN | tag-count: 22 / 22 placed               │
└───────────────────────────────────────────────────┘
```

### How to render the composite

Pass this Python to `execute_blender_code` once per iteration. It uses Eevee Next to render three angles fast, then composites them with PIL.

```python
import bpy, os, math
from pathlib import Path

WORLD_SLUG = "$1"
ITER = ITERATION_NUMBER  # filled in by caller, e.g. 7
SCENE_SIZE = max(*plan.terrain.size_meters)  # e.g. 12
OUT_DIR = Path(f"worlds/{WORLD_SLUG}/iterations")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def setup_eevee_fast():
    s = bpy.context.scene
    s.render.engine = 'BLENDER_EEVEE_NEXT'
    s.eevee.taa_render_samples = 16
    s.render.resolution_x = 512
    s.render.resolution_y = 384
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'

def place_cam(name, location, rotation_deg, lens=35, ortho=False, ortho_scale=20):
    cam_data = bpy.data.cameras.new(name)
    if ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.lens = lens
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = location
    cam_obj.rotation_euler = tuple(math.radians(d) for d in rotation_deg)
    return cam_obj

def render_view(cam, out_path):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)

setup_eevee_fast()

# 1. Top-down orthographic — sees the floor plan
cam_top = place_cam("WB_TopCam",
    location=(0, 0, SCENE_SIZE * 1.5),
    rotation_deg=(0, 0, 0),
    ortho=True, ortho_scale=SCENE_SIZE * 1.4)
render_view(cam_top, OUT_DIR / f"{ITER:03d}-top.png")

# 2. Bird-view — matches the reference framing
cam_bird = place_cam("WB_BirdCam",
    location=(SCENE_SIZE * 0.7, -SCENE_SIZE * 0.7, SCENE_SIZE * 0.6),
    rotation_deg=(60, 0, 45),
    lens=35)
render_view(cam_bird, OUT_DIR / f"{ITER:03d}-bird.png")

# 3. Side three-quarter — sanity check on object scale
cam_side = place_cam("WB_SideCam",
    location=(-SCENE_SIZE * 0.6, -SCENE_SIZE * 0.9, SCENE_SIZE * 0.3),
    rotation_deg=(75, 0, -30),
    lens=35)
render_view(cam_side, OUT_DIR / f"{ITER:03d}-side.png")

# Composite via PIL
from PIL import Image, ImageDraw, ImageFont
top  = Image.open(OUT_DIR / f"{ITER:03d}-top.png")
bird = Image.open(OUT_DIR / f"{ITER:03d}-bird.png")
side = Image.open(OUT_DIR / f"{ITER:03d}-side.png")
w, h = top.size  # all three same dims
gap = 8
canvas = Image.new("RGB", (w*3 + gap*2, h + 28), (10, 10, 12))
canvas.paste(top,  (0,         28))
canvas.paste(bird, (w + gap,   28))
canvas.paste(side, (w*2 + gap*2, 28))
draw = ImageDraw.Draw(canvas)
labels = [("TOP-DOWN", 0), ("BIRD-VIEW", w + gap), ("SIDE 3/4", w*2 + gap*2)]
for label, x in labels:
    draw.text((x + 8, 6), label, fill=(240, 240, 240))
composite_path = OUT_DIR / f"{ITER:03d}.png"
canvas.save(composite_path)

# Cleanup the temp cameras so we don't pollute the scene
for cam_name in ("WB_TopCam", "WB_BirdCam", "WB_SideCam"):
    if cam_name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[cam_name], do_unlink=True)
        if cam_name in bpy.data.cameras:
            bpy.data.cameras.remove(bpy.data.cameras[cam_name])

# Clean per-angle PNGs (we only need the composite from here on)
for angle in ("top", "bird", "side"):
    (OUT_DIR / f"{ITER:03d}-{angle}.png").unlink(missing_ok=True)

print(f"Rendered composite: {composite_path}")
```

Then `Read` the composite PNG (`worlds/$1/iterations/{N:03d}.png`) — Codex sees all three angles as one multimodal input.

## The loop

```
iteration = 0
last_deltas = None

while iteration < 25:
    iteration += 1

    # 1. Import any not-yet-placed assets (tag-based — see place-asset.py)
    for obj in plan.objects:
        for instance_idx in range(obj.count):
            tag = f"{obj.id}_{instance_idx}"
            if tag not in current_scene_tags:
                execute_blender_code(import_glb_call(obj.path, obj.approx_positions[instance_idx], tag))

    # 2. SEE — composite render (3-angle, Eevee Next, ~3 seconds total)
    execute_blender_code(composite_render_script with ITER=iteration)
    composite = Read(f"worlds/$1/iterations/{iteration:03d}.png")    # one multimodal Image

    # 3. JUDGE — Codex sees composite + reference together
    reference = Read("worlds/$1/source/reference.png")               # multimodal
    # Compose strict JSON delta:
    #   [{ "issue": "...", "tag": "palm-tall_1",
    #      "action": "rescale|reposition|rotate|swap|remove|add",
    #      "params": { ... } }]
    # If scene ~90% match → return []

    # 4. ADJUST
    for delta in deltas:
        execute_blender_code(delta.to_python())

    # 5. SAVE — overwrite the live worlds/$1/world.blend so a crash never loses work.
    #    save_mainfile() writes to bpy.data.filepath (set by build-world Step 2). <1s for our scenes.
    execute_blender_code("bpy.ops.wm.save_mainfile()")

    # 5b. SNAPSHOT (every 5th iteration only — keeps history without bloating wall-clock)
    if iteration % 5 == 0:
        execute_blender_code(f"""
import bpy, os
project_root = bpy.path.abspath('//')
snapshot = os.path.join(project_root, 'iterations', f'{iteration:03d}.blend.bak')
bpy.ops.wm.save_as_mainfile(filepath=snapshot, copy=True)   # copy=True keeps live filepath = world.blend
""")

    # 6. Save the note
    Write(f"worlds/$1/iterations/{iteration:03d}.note.md", deltas_summary)

    # 7. Convergence
    if len(deltas) == 0:
        log("Converged"); break
    if deltas == last_deltas:
        log("Stuck — same delta list twice; escalating"); break
    last_deltas = deltas
```

## Judge prompt structure

Strict JSON output keeps the loop deterministic:

> "Here are two images. The first is the target reference (a single bird-view). The second is the current Blender scene rendered from three angles side-by-side: top-down (left), bird-view (middle — compare directly to reference), side three-quarter (right — use to check object scale and grounding).
>
> List concrete actionable differences. For each: (a) one-sentence issue, (b) which object tag (`{object_id}_{instance_idx}`) is affected, (c) one action from `rescale | reposition | rotate | swap | remove | add`, (d) the parameters for that action.
>
> Return as a JSON array. If the bird-view matches the reference within 90% (palette + silhouette + key objects in roughly right places), return `[]`."

## Performance budget

| Step | Wall-clock per iteration |
|---|---|
| Import any new GLBs (only iter 1) | 2-10s |
| Composite render (3 angles, Eevee Next, 512×384) | 2-5s |
| Read composite + reference (multimodal) | <1s |
| Judge step (Codex reasoning) | 5-15s |
| Apply deltas (3-10 execute_blender_code calls) | 5-15s |
| **Total per iteration** | **15-45s** |

25 iterations × 30s average = **~12-13 min total loop time**. With Cycles instead of Eevee Next: 25 × 90s+ = 38+ min — unacceptable. Eevee Next is non-negotiable for the loop.

## Hard caps

- **25 iterations max.** Beyond that = not converging; escalate.
- **Same delta list twice in a row = stuck.** Break early.
- **3+ min per iteration** = something is wrong (Blender hang, MCP timeout). Escalate.
- **Backup every 5th iteration**, not every iteration — saves ~5-10s × 20 = 2-3 min wall-clock.

## Output on exit (converged, capped, or stuck)

1. Snapshot the final state to `worlds/$1/final.blend` via `bpy.ops.wm.save_as_mainfile(filepath='<abs>/worlds/$1/final.blend', copy=True)` — `copy=True` keeps the live filepath as `world.blend`, so reopening that file shows the same scene and the user can keep iterating.
2. Final `bpy.ops.wm.save_mainfile()` to flush `world.blend` to disk.
3. Render the bird-view camera at full resolution (1920×1080, Eevee Next) to `worlds/$1/final.render.png`.
4. Append loop stats to `worlds/$1/cost.json`.
5. Return a one-paragraph summary.

## What you must NOT do

- Do NOT use Cycles. Eevee Next or bust.
- Do NOT render at 1024+ per angle in the loop — 512×384 per angle is plenty for judging. Save fidelity for the FINAL render.
- Do NOT take separate `get_viewport_screenshot` calls in the loop — always composite the 3 angles first. Saves tokens + gives the judge more spatial information per round.
- Do NOT recompose GN trees inside the loop. Terrain is fixed after Phase 1.
- Do NOT add objects beyond `plan.json` unless the judge explicitly emits `"action": "add"`.
