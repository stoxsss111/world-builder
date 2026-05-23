---
name: "generate-3d"
description: "Generate one atomic 3D asset via fal Tripo P1 (textured, PBR auto-included, $0.50). Polycount tuned per object class \u2014 sweet spot 5,000-15,000 faces. No fallback (Trellis 2 quality is worse for stylised cases; retry P1 with a better reference plate instead)."
---

## Codex adaptation

Use the available Codex shell and file tools. In this migrated skill, `$1` means world slug and `$2` means object id.

Generate exactly one 3D asset for `worlds/$1/assets/$2.glb`.

## Inputs

- `$1` = world slug
- `$2` = object id (from `plan.objects[].id`)
- The object's `name`, `scale_hint`, `priority`, and (new) `face_limit` come from `worlds/$1/plan.json`.

## Procedure

1. **Pick the face_limit for this object.** Tripo P1 generates clean meshes in the 5,000-15,000 face range. Anything below = blocky, above = wasted detail you'll never see in a stylised scene. Match to the object class:

   | Object class | face_limit | Why |
   |---|---:|---|
   | Hero structural (tiki hut, treasure chest, beach hut, lantern post) | **12,000-15,000** | Visible silhouette, multiple read-at-distance parts |
   | Hero organic (tall palm, big rock, bent palm, statue) | **10,000-13,000** | Smooth curves need a bit more geometry to read cleanly |
   | Mid-detail (medium rock, barrel, conch shell, starfish) | **7,000-9,000** | Recognisable shape, no microdetail |
   | Filler (pebble, small shell, twig, debris) | **5,000-6,000** | Generic prop — won't be looked at closely |

   If the plan already specifies a `face_limit`, use that. Otherwise pick from the table by `scale_hint` + `priority`.

   **Never request face_limit > 15,000.** The wrapper clamps to [5,000, 15,000] regardless — but the prompt should match the budget so you don't waste a generation on detail the clamp will discard.

2. **Build the generation prompt.** Combine `object.name + plan.style.anchor + plan.style.level_of_stylization`:
   > "{name}, {anchor} cartoon art style, {level_of_stylization} stylisation, vibrant saturated palette ({palette[0]}, {palette[2]}), isolated on white background, centred, no shadows, single object only, simple readable silhouette, no microdetail."

   The "simple readable silhouette, no microdetail" tail is important — biases the reference image (and thus the Tripo output) toward shapes that fit the 5-15k face budget.

3. **Generate the reference plate** (image input to Tripo). Use nano-banana text-to-image at $0.039:
   ```bash
   node .claude/scripts/asset-pipeline/nano-banana-edit.mjs \
     --prompt "<the prompt above>" \
     --output-dir worlds/$1/assets \
     --output-slug $2-ref
   ```
   This produces `worlds/$1/assets/$2-ref.png` — a clean, white-bg reference of the object.

4. **Generate the 3D asset via Tripo P1 textured** ($0.50, includes PBR in the `pbr_model` output URL):
   ```bash
   node .claude/scripts/asset-pipeline/tripo-p1.mjs \
     --image worlds/$1/assets/$2-ref.png \
     --output-dir worlds/$1/assets \
     --output-slug $2 \
     --texture true \
     --face-limit <picked-from-table>
   ```

5. **If the result is poor — retry with a better reference plate.** Read the preview (Tripo includes one in the request metadata). If the mesh / texture clearly fails (mangled silhouette, wrong colours, broken topology), do NOT fall back to a different model. Instead:
   - Regenerate the reference plate with a tightened nano-banana prompt (add "single object, white background, no shadows, centred, no clipping, full object visible").
   - Re-run Tripo P1 with a different `--seed`.
   - Cap at **2 retries per object**. After that, escalate to the user with the failed preview attached.

   Why no Trellis 2 fallback: stylised scenes degrade visibly when half the assets are from a lower-quality model. The project default is to fail explicitly rather than silently swap in a mid-tier result.

6. **Update plan.json.** Add the asset path + cost + face_limit to the object entry:
   ```jsonc
   "objects": [
     {
       "id": "$2",
       ...
       "asset_path": "worlds/$1/assets/$2.glb",
       "pbr_asset_path": "worlds/$1/assets/$2-pbr.glb",   // optional — present when texture=true
       "cost_usd": 0.50,
       "face_limit": 10000,
       "provider": "tripo3d/p1"
     }
   ]
   ```

7. **Log cost.** Append to `worlds/$1/cost.json`. Reconciler runs once at end-of-Phase-2.

## Returns

- Path to the generated `.glb`
- (Optional) path to the PBR variant
- Cost in USD
- Face limit used
- Provider used (`tripo3d/p1` or `fal-ai/trellis-2`)
- If a fallback happened, the reason

## What you must NOT do

- Do NOT request `face_limit > 15_000` — wasted detail, wasted tokens explaining it.
- Do NOT use `quality: "high"` — that's not a real Tripo P1 param; the wrapper would silently drop it.
- Do NOT generate the same object id twice — check `worlds/$1/assets/$2.glb` exists before kicking the gen.

## Parallelisation note

Designed to be invoked N times in parallel from `build-world`. fal handles parallel queues; the only contention is the local `cost.json` file — read-modify-write with a small file lock, or rebuild from `request-metadata` records at the end of Phase 2.
