---
name: analyze-reference
description: Read one reference image and produce a structured scene plan (terrain, objects, palette, lighting, camera). Use when build-world calls into Phase 0.
argument-hint: [reference-image-path] [world-slug]
allowed-tools: Read Write Edit Bash(mkdir *)
---

You are analysing one reference image and writing a scene plan to `worlds/$1/plan.json`.

## Procedure

1. **Read the reference image.** Use the `Read` tool on `worlds/$1/source/reference.png` — Claude's multimodal vision handles this natively. No external vision API.

2. **Identify the style anchor.** Match against `docs/style-references.md` anchors:
   - Banjo-Kazooie · Treasure Trove Cove (high-stylisation cartoon)
   - Wind Waker (cel-shaded)
   - Mario Sunshine · Isle Delfino (mid-high stylisation, tropical)
   - Pokémon Scarlet/Violet (mid-stylisation, modern toon)
   - Donkey Kong Bananza (vibrant cartoon, dense scatter)
   - Animal Crossing: New Horizons (tight stylisation)
   - Or `"custom"` if no clear match.

3. **Extract style metadata:**
   - `palette`: dominant 4-5 hex colours (sand, water, foliage, wood, sky)
   - `level_of_stylization`: `"high"` (Banjo) / `"mid"` (Pokémon SV) / `"low"` (Horizon FW)
   - `shading`: `"toon"` / `"flat"` / `"pbr-light"`
   - `lighting`: `"golden-hour"` / `"noon"` / `"dusk"` / `"overcast"`

4. **Identify the terrain shape.** Read the image and decide:
   - `"island"` (round, surrounded by water)
   - `"shoreline"` (water on one side)
   - `"hills"` (no water, vertical relief)
   - `"flat"` (no relief)
   - `"crater"` (recessed centre)
   Plus: ground type (sand/grass/dirt/rock/snow), water level if applicable, approx size in metres (default 12×12 for an island).

5. **Enumerate the objects.** Look at the image and list every distinct object class you can identify. For each:
   - `id`: lowercase-slug (e.g. `palm-tall`, `beach-hut`, `rock-mossy`)
   - `name`: human-readable description suitable for a Tripo gen prompt (e.g. "Tall stylised palm tree with curved trunk")
   - `count`: how many instances are in the reference (or how many you'd add to look right)
   - `approx_positions`: list of [x, y] in metres, anchored at scene origin
   - `scale_hint`: `"large"` / `"medium"` / `"small"` / `"tiny"`
   - `priority`: `"hero"` (visually critical, use Tripo P1 textured) / `"filler"` (generic, use Trellis 2 or re-instance)
   - `face_limit`: integer in `[5000, 15000]`. Pick from the table in `generate-3d/SKILL.md` (hero structural 12-15k, hero organic 10-13k, mid-detail 7-9k, filler 5-6k).

   ### The 25-object default cap

   **Total instance count across all objects MUST be ≤ 25 by default.** Each instance = $0.30-0.50 in fal spend. The cap keeps a single scene under $15 of asset generation.

   How to fit:
   - Identify ~6-10 distinct `id`s (object classes).
   - Re-instance via `count` for repeating items (palms, rocks, shells). Same .glb, different positions — costs $0.50 once.
   - Sum of `count` across all objects = total instances. Keep this ≤ 25.

   If the reference clearly NEEDS more than 25 instances to read correctly:
   - Stop and ask the user: `Reference suggests ~N instances. Default cap is 25 (≈$<estimated cost> in fal spend). Raise the cap?`
   - Only proceed past 25 after explicit user confirmation.

6. **Camera framing.** Estimate the reference's camera:
   - `framing`: `"three-quarter aerial"` / `"side"` / `"top-down"` / `"hero-low-angle"`
   - `focal_length_mm`: usually `35` for the Nintendo aerial-three-quarter look, `50` for closer, `24` for wider

7. **Write `worlds/$1/plan.json`** with the structure shown in `docs/PIPELINE.md`:

```jsonc
{
  "world_slug": "$1",
  "style": { "anchor": "...", "palette": ["#..."], "level_of_stylization": "...", "shading": "...", "lighting": "..." },
  "terrain": { "shape": "...", "ground": "...", "water": { "present": true, "level": -0.05 }, "size_meters": [12, 12], "feature_notes": "..." },
  "objects": [
    { "id": "palm-tall", "name": "...", "count": 3, "approx_positions": [[2,1], [3,0.5], [1.5,2]], "scale_hint": "tall", "priority": "hero", "face_limit": 12000 },
    ...
  ],
  "camera": { "framing": "three-quarter aerial", "focal_length_mm": 35 }
}
```

8. **Sanity-check the plan**: read it back, confirm total instances (sum of `count`) ≤ 25, confirm all `priority: hero` objects have a clear `name` suitable for asset generation, confirm every object has a `face_limit` in [5000, 15000]. Fix in-place if needed.

## Output

Returns the plan path: `worlds/$1/plan.json`. Logs a one-line summary of the analysis (anchor, terrain, object count) for the orchestrator.
