# `world-builder`

Take one reference image. Get a full interactive 3D scene assembled in Blender. Claude Code drives the build, takes its own screenshots, judges the result against the reference, and iterates until the scene matches.

Spiritual sibling to [`image-blaster`](https://github.com/neilsonnn/image-blaster) — but instead of meshing a single image into objects, `world-builder` composes a **complete stylised scene**: procedural terrain, generated assets, scattered placement, sky / lighting — all inside a live Blender session via MCP.

## What you give it

A single reference image. Examples that work well:

- A stylised game-art screenshot (Wind Waker / Banjo-Kazooie / Mario Sunshine / Pokémon)
- An AI-generated concept of a location ("tropical island, low-poly palms, cartoon sand, lagoon")
- A photo of a real place you want to stylise

## What you get back

A `.blend` file with:

1. **Procedural surfaces** — Blender primitives (ground, water, grass) with tiled PBR materials generated via fal PATINA ($0.08 each at 1024px).
2. **Generated 3D objects** — typically 7-10 distinct ids re-instanced to 20-25 total objects per scene, generated via Tripo P1 textured (with PBR maps automatically included in `pbr_model` output URL). Polycount tuned per object class — 5,000-15,000 faces, never higher. Free procedural alternatives (Stylized Fantasy Tree Generator, Rock Generator) used for matching filler classes when available.
3. **Sky & lighting** — Poly Haven HDRI on a hemisphere, sun rotated to match the reference's shadow direction.
4. **A render** matching the reference framing — Eevee Next, 1920×1080.

### Cost per world

One world ≈ **$4-6 in fal spend** at the 20-25 instance working range. Breakdown:

- Tripo P1 textured × 7-10 distinct gens (re-instanced) = ~$3.50-$5.00
- PATINA materials × 3 (sand + water + grass) @ 1024 = ~$0.24
- Nano-banana reference plates × 7-10 = ~$0.27-$0.39

Plus ~$2-4 in Claude tokens for the loop (composite-screenshot optimisation keeps it tight).

**Total typical: ~$6-10 per built world.**

## How it works (the loop)

```
reference.png
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Step 0 — analyse                                       │
│  Claude Code reads the reference (multimodal native).   │
│  Produces a scene plan: terrain shape, object list,     │
│  rough positions, style notes, palette, lighting.       │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Step 1 — ground                                        │
│  Generate procedural terrain in Blender via             │
│  execute_blender_code (geometry nodes + displacement).  │
│  Apply stylised ground texture (Poly Haven CC0 or       │
│  generated via fal).                                    │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Step 2 — assets (parallel)                             │
│  For each object in the plan, call Tripo P1 image-to-3d │
│  via fal ($0.50/asset textured). Download .glb.         │
│  Fallback to Poly Haven / Sketchfab via blender-mcp     │
│  for objects that already exist as CC0.                 │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Step 3 — sky                                           │
│  Poly Haven HDRI via blender-mcp (existing tool).       │
│  Sun-direction tuned to match the reference shadow.     │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Step 4 — place & iterate  (the autonomous loop)        │
│  Import every asset. Place at plan position.            │
│  call get_viewport_screenshot() — Claude SEES the       │
│  scene as multimodal input.                             │
│  Compare to reference. Adjust scale / rotation /        │
│  position / swap assets. Iterate until convergence.     │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  Step 5 — render                                        │
│  Camera framed to match reference. Eevee render.        │
└─────────────────────────────────────────────────────────┘
```

The whole loop is documented in `docs/ARCHITECTURE.md` and `docs/PIPELINE.md`.

## Quickstart

1. Clone this repo.
2. Install [Claude Code](https://claude.com/claude-code): `curl -fsSL https://claude.ai/install.sh | bash`
3. Install [Blender 5.1 LTS](https://www.blender.org/download/lts/) and drag the [MCP add-on](https://www.blender.org/lab/mcp-server/) into it (twice — once for the repo, once for the add-on).
4. Wire blender-mcp into Claude Code:
   ```bash
   claude mcp add blender uvx blender-mcp
   ```
5. Copy `.env.example` to `.env` and fill in `FAL_KEY` (get from [fal.ai/dashboard](https://fal.ai/dashboard)).
6. Drop a reference image in `input/` (PNG, JPG — anything Claude can see).
7. Open Claude Code in this directory:
   ```bash
   claude --dangerously-skip-permissions
   ```
   (The `--dangerously-skip-permissions` flag lets the agent run Blender writes during the loop without per-tool prompts. Don't use it for untrusted work.)
8. Say: `Build me a world from input/<your-file>.png and call it <world-slug>.`

Claude will create `worlds/<world-slug>/` with the source image, the scene plan, all generated assets, screenshots from each loop iteration, and the final `.blend`.

## Style direction (the seed brief)

This scaffold is tuned for **stylised Nintendo-grade locations**, not photoreal scenes. Tripo P1 textured handles stylised art well; Trellis 2 is the fallback when P1 misses.

Anchor references in `docs/style-references.md`:
- Wind Waker (cel-shaded ocean + island silhouettes)
- Banjo-Kazooie / Banjo-Tooie (Treasure Trove Cove)
- Mario Sunshine (Isle Delfino plaza, Bianco Hills)
- Pokémon Scarlet/Violet (open-zone islands)
- Recent: Bananza beach zones (Donkey Kong Bananza, 2025)

## Differences from image-blaster

|  | image-blaster | world-builder |
|---|---|---|
| Output | individual `.glb` objects + WL splat env | full Blender scene (`.blend`) |
| 3D provider | Hunyuan (default) / Meshy | **Tripo P1 textured** (sole provider, no fallback) |
| Surfaces | n/a | **PATINA-generated PBR materials on Blender primitives** |
| Environment | World Labs Marble (splats) | Procedural terrain + Poly Haven HDRI |
| Sound | ElevenLabs SFX | none |
| Live session | no — generators only | **yes — Blender MCP, autonomous vision loop with composite-screenshot judge** |
| Image input | one image → N objects | one image → composed scene |

## Status

Scaffold-stage. The folder layout, design docs, fal client, and SKILL.md stubs are in place. Actual implementation of the loop happens after the scaffold ships to its own repo and gets iterated in a fresh Claude Code session.

## Credits

- Inspired by [`image-blaster`](https://github.com/neilsonnn/image-blaster) by Neilson (skill structure + fal client patterns)
- Vision-loop mechanism verified via [`ahujasid/blender-mcp`](https://github.com/ahujasid/blender-mcp) source (`get_viewport_screenshot` returns MCP `Image` block natively)
- Tripo 3D models via [fal.ai](https://fal.ai)

## License

MIT (TBD on push)
