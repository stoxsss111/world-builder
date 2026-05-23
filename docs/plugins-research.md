# Useful plugins / skills / MCPs — research notes

What else can we plug into `world-builder` to help the agent? Surveyed 2026-05-22.

## Tier 1 — strongly recommended for integration

### Blender MCP Pro (y1uda)

The single most-relevant find. A drop-in alternative / complement to `ahujasid/blender-mcp` with built-in commands for exactly the operations world-builder needs:

- **`create_pbr_material`** — 16 presets (glass, metal, gold, copper, wood, plastic, rubber, ceramic, fabric, skin, water, neon, concrete, mirror, brushed_metal, colored_glass). One-line call to slap a stylised material on an object.
- **`create_scatter_setup`** — full Geometry Nodes scatter system in one command. Crucial for grass-scatter, flower-scatter, small-rock-scatter on the procedural ground.
- **`create_array_along_curve`** — instance array along a curve. Useful for path / shore-line decoration.

Why this matters: the autonomous loop needs to issue compact, deterministic commands. A one-liner `create_scatter_setup(target_object="ground", instance_object="grass-blade", density=...)` is FAR more loop-friendly than asking Claude to write the GN tree by hand each iteration.

- Source: [y1uda.itch.io/blender-mcp-pro](https://y1uda.itch.io/blender-mcp-pro) (commercial — check pricing)
- Status: **evaluate before first build.** If pricing is reasonable, add as a second MCP server alongside `ahujasid/blender-mcp`.

### Stylized Fantasy Tree Generator (geometry-nodes-based)

Free geometry-nodes tool that produces stylised cartoon trees with endless variation. Fits the Banjo/Wind Waker aesthetic. For an island scene needing 3-5 palm variations, this could replace 3-5 Tripo P1 generations = **~$2.50 saved per scene**.

- Status: **add to docs/style-references.md as the recommended palm-variation source.** Use when you want palette variety without burning Tripo budget.

### Blender Studio Rock Generator + 3DT Stylized Rock Generator

Two free procedural rock generators (one from official Blender Studio, one from 3DT). Both produce stylised rocks at game-asset quality. For an island scene with 6-10 round boulders, these could replace **all the Tripo rock gens** = $5-6 saved per scene.

- Status: **add to docs/style-references.md.** Default boulder source for filler rocks.

## Tier 2 — worth evaluating if Tier 1 covers the basics well

### Geo-Scatter (free version)

Full-featured scatter add-on with brush painting, density control, biome management. More powerful than Blender's built-in particle / GN scatter for natural distribution.

- Use case: replace the agent's hand-built scatter logic with calls to Geo-Scatter's API. Cleaner output.
- Status: **add to docs/blender-mcp-setup.md as an optional install.** Not required, but improves quality.

### BagaPie

Pre-built geometry-node modifiers — drop-in array, scatter, arrange-on-curve, etc. Reduces the "build the GN tree from scratch" risk that comes with model-generated GN node code.

- Status: **add to docs/blender-mcp-setup.md as an optional install.** Especially useful for the agent in early iterations.

### Falling Leaves

For stylised foliage scatter on the ground (cherry petals, autumn leaves, pink frangipani flowers for a tropical island). Adds the "lived-in" detail that pushes a scene from "AI-built" to "designed".

- Status: **optional.** Add as a polish step in Phase 4 if the result feels sterile.

## Tier 3 — useful for specific niches, not core

| Tool | Use case | Status |
|---|---|---|
| **Auto-Terrainer** | Realistic terrain from low-poly mesh. Overkill for stylised flat islands. | Skip for v1. |
| **Terrain Mixer** (Boonar) | GPU-erosion + 9-height-mix terrain. Powerful but heavy. | Skip for v1. |
| **Terrain Nodes Addon** | CUDA-accelerated erosion at 4096×4096. | Skip — overkill. |
| **Blender Kit** | Full asset library, mostly photoreal. Doesn't fit stylised aesthetic. | Skip. |
| **Botaniq** | Realistic vegetation. Wrong style. | Skip. |
| **True-Terrain** | Procedural realistic terrain. Same — wrong style. | Skip. |

## Tier 4 — Claude Code / MCP ecosystem (worth referencing, not bundling)

| Skill / MCP | What it offers | Recommendation |
|---|---|---|
| **`ProfRino/Blender-MCP-Assemply-Skill`** | Plan-connections-first assembly methodology with `verify_bounds`, `verify_overlap`, `audit_all`, `finalize` helpers. | **Adopt the methodology pattern.** Mirror the verify-bounds approach in `place-and-iterate` to prevent floating / clipping. |
| **`elithril/blender-kiln`** | Full Claude Code skill for asset production: configure → brief → source → import → cleanup → texture → optimise → export. Integrates Hunyuan / PolyHaven / Sketchfab. | **Reference, don't bundle.** Their `/kiln:optimize` and `/kiln:texture` patterns are worth borrowing the prompt structures from. |
| **`anthropics/skills`** | Official skills repo. No Blender skill yet. | First-mover slot still open. |
| **Blender Toolkit (mcpmarket)** | Claude Code skill for primitive gen + PBR + modifiers. | Lightweight — overlaps with Blender MCP Pro. Skip. |
| **fal-mcp (official)** | HTTP MCP exposing all 1000+ fal models. | **Add as a second MCP server.** Lets the agent call PATINA / Tripo / nano-banana through MCP instead of shell scripts when convenient. `claude mcp add --transport http fal-ai https://mcp.fal.ai/mcp --header "Authorization: Bearer $FAL_KEY"`. |

## Recommended additions to world-builder v1

In order of impact for the first build:

1. **Stylized Fantasy Tree Generator** — add to `docs/style-references.md` as palm source. Saves ~$2.50/scene.
2. **3DT Stylized Rock Generator** or Blender Studio Rock Generator — add to `docs/style-references.md` as boulder source. Saves ~$5/scene.
3. **fal-mcp** — register as second MCP server in `.claude/settings.json`. Cleaner integration than shell scripts when the agent wants to call fal in-loop.
4. **Blender MCP Pro** — evaluate cost. If reasonable, add as third MCP server for `create_scatter_setup`, `create_array_along_curve`, `create_pbr_material`.
5. **Borrow ProfRino's verify-bounds methodology** — incorporate into `place-and-iterate` so we don't accept floating-above-the-ground placements.

These five additions could:
- Drop typical per-scene fal spend from ~$8-10 to **~$3-5**
- Improve placement quality (verify-bounds)
- Make scatter-heavy details (grass blades, flowers, debris) actually feasible in the agent loop

## Out of scope for v1, kept on list for later

- Animation / rigging plugins — character animation is explicitly out of scope.
- Realistic terrain plugins — wrong style.
- Photoreal asset libraries — wrong style.
- Real-time game-engine exports — `.blend` output is the contract.

## Sources

- [agmmnn/awesome-blender](https://github.com/agmmnn/awesome-blender) — curated list, kept current
- [Top 35 Geometry Node Addons in Blender 2026 (Blender Hub)](https://blenderhub.net/geometry-node-addons/)
- [y1uda Blender MCP Pro on itch.io](https://y1uda.itch.io/blender-mcp-pro)
- [ProfRino/Blender-MCP-Assemply-Skill on GitHub](https://github.com/ProfRino/Blender-MCP-Assemply-Skill)
- [elithril/blender-kiln on GitHub](https://github.com/elithril/blender-kiln)
- [Blender Toolkit on mcpmarket.com](https://mcpmarket.com/tools/skills/blender-toolkit)
- [fal MCP server announcement](https://blog.fal.ai/connect-your-ai-to-1-000-models-with-the-fal-mcp-server/)
