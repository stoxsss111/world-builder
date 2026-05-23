---
name: "procedural-terrain"
description: "Build the procedural ground in Blender \u2014 primitive surfaces (sand, water, grass), GN displacement for terrain shape, then tiled PBR materials via PATINA. Pastes a known-good template rather than composing GN nodes from scratch (sidesteps GN-API-drift)."
---

## Codex adaptation

Use the available Codex file and Blender MCP tools. In this migrated skill, `$1` means world slug.

Build the procedural terrain for `worlds/$1/` based on `worlds/$1/plan.json`.

## The procedural-vs-generated split

This skill handles **PROCEDURAL surfaces** — flat or displaced Blender primitives that get tiled PBR materials. Objects (palms, chests, lanterns, log-stumps, boulders, flowers) come from `generate-3d` via Tripo P1.

Procedural surface candidates for this skill:
- Main sand ground plane (always)
- Water plane around the island (if `plan.terrain.water.present`)
- Small grass patches (if the reference has grass)
- Secondary islet ground plane (if the plan has a second island)

For each procedural surface: create the primitive in Blender → call `generate-material` skill to produce PBR via PATINA → apply.

## Procedure

1. **Read `worlds/$1/plan.json`.** Extract:
   - `plan.terrain.shape` (`"island"` / `"hills"` / `"flat"` / `"shoreline"` / `"crater"`)
   - `plan.terrain.size_meters` (e.g. `[12, 12]`)
   - `plan.terrain.water.present` + `plan.terrain.water.level`
   - `plan.style.palette` (use index 0 for ground colour, index 1 for water colour)

2. **Read the template** at `.claude/scripts/blender/procedural-terrain.py`.

3. **Substitute parameters** at the top of the template:
   ```python
   SIZE_X = <plan.terrain.size_meters[0]>
   SIZE_Y = <plan.terrain.size_meters[1]>
   SHAPE = "<plan.terrain.shape>"
   WATER_LEVEL = <plan.terrain.water.level or None>
   SAND_HEX = "<plan.style.palette[0]>"
   WATER_HEX = "<plan.style.palette[1]>"
   ```

4. **Send to Blender via MCP** by calling the `execute_blender_code` tool (from the `blender` MCP server) with the full substituted script. This creates the primitives — ground plane, optional water plane, optional secondary islet — with placeholder solid-colour materials.

5. **Generate + apply PATINA materials.** For each procedural surface created in step 4, invoke the `generate-material` skill:

   - `sand` (main ground) — always
   - `water-shallow` (water plane) — if `plan.terrain.water.present`
   - `grass` (grass patches) — if grass is in the plan
   - `sand` (secondary islet, can reuse the main sand material) — if a second island exists

   Each PATINA call is `~$0.08` at 1024px. Total PATINA spend per typical world = **~$0.16-0.24** for 2-3 distinct materials.

   After the maps are generated, paste the `apply_patina_material(...)` Python snippet (see `generate-material/SKILL.md`) into `execute_blender_code` to wire each map set onto the right object.

6. **Take a baseline screenshot.** Call `get_viewport_screenshot(max_size=800)` from the `blender` MCP server. Save the returned PNG to `worlds/$1/iterations/000-terrain.png`.

7. **Inspect the screenshot.** Read it back (it's a multimodal Image block). Confirm:
   - Ground is visible and oriented correctly
   - PATINA material applied — palette matches the reference (not pink/missing-texture default, not the placeholder solid colour)
   - Water plane is present if expected
   - Camera is looking at the scene (not into the void)

   If any check fails, run `execute_blender_code` with corrective Python and re-screenshot. If the PATINA material itself looks off (wrong palette, broken tile), call `generate-material` again with a tighter prompt or different seed (cap at 2 PATINA retries per surface).

   Hard cap: 3 corrective tries total before escalating to the user.

## Hard rules — these are non-negotiable

- The GN terrain modifier MUST be named `GN_Terrain` and live in a group named `Terrain_Setup` with exposed inputs (`Hill Height`, `Noise Scale`, `Edge Falloff`).
- The displacement chain MUST be wrapped in a `NodeFrame` labelled `"Displacement (noise + radial falloff)"` — visible in the node editor for the on-camera reveal.
- These naming choices keep the GN setup legible — anyone opening the node editor can see the displacement chain and tweak the exposed parameters without spelunking.

## Returns

- Path to the baseline screenshot
- A one-line summary of what was built (e.g. `"island terrain 12×12, water at z=-0.05, sand #f2d790"`)
