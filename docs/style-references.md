# Style References — the seed brief

world-builder is tuned for **stylised Nintendo-grade locations**, not photoreal scenes. This file documents the visual anchors we're aiming for, so the `analyze-reference` skill and the asset-generation prompts stay consistent.

## Anchor titles

| Game | Year | What we borrow from it |
|---|---|---|
| **Banjo-Kazooie** (Treasure Trove Cove) | 1998 | Cartoon palms with thick trunks, pastel sand, exaggerated rock proportions, googly-eyed props |
| **Banjo-Tooie** | 2000 | Slightly higher detail than BK, same proportion language, more saturated palette |
| **Mario Sunshine** (Isle Delfino, Bianco Hills) | 2002 | Tropical island silhouettes, terraced terrain, plaza tiles, statue motifs |
| **Wind Waker** (Outset, Windfall, archipelago) | 2002 | Cel-shaded ocean, distinct island silhouettes from afar, sky-toned shadows |
| **Pokémon Scarlet/Violet** (open-zone islands) | 2022 | Open island layout, mid-stylisation, modern-shader cartoon |
| **Donkey Kong Bananza** (beach zones) | 2025 | Vibrant cartoon palette, exaggerated foliage, dense scatter, recent reference |
| **Animal Crossing: New Horizons** | 2020 | Tight stylisation, small-scale island composition, prop-heavy scenes |

## Visual rules to encode in prompts

These are the patterns the model should produce by default. Encode in `.claude/skills/generate-3d/SKILL.md` prompt template and in `analyze-reference`'s style detection.

### Geometry
- Thick, exaggerated proportions (palms have wide trunks; rocks are rounder than reality)
- Low-to-medium polycount silhouettes, NOT photoreal microdetail
- Visible bevels rather than crisp edges (more readable, more cartoon)
- Topology designed to read at distance — silhouette > microdetail

### Shading
- Toon / cel-shading preferred for hero objects
- Single saturated base colour + 1-2 highlight tones, NOT smooth PBR gradients
- Black or dark-purple rim shadows for the cartoon look (when toon)
- Optional: outline shader on hero props (heavy on cost, save for the flagship demo render)

### Palette (typical "banjo-beach" scene)
- Sand: `#f2d790` warm, slightly orange (not grey)
- Water: `#3aa6b8` saturated turquoise (not muted blue)
- Foliage: `#1f6f4b` saturated mid-green (not olive)
- Wood: `#9c6a3c` warm tan (not desaturated)
- Sky: tropical sunset palette — `#fcd9a3` → `#f08e7e` → `#7b6bb7`

These four-to-five hex codes get written into `plan.style.palette` and reused by `procedural-terrain` for the ground material + `generate-3d` for prompt biasing.

### Lighting
- Single warm key light (sun) — golden hour by default
- Saturated rim from opposite side
- Sky HDRI for fill, but rotated so the sun direction matches the reference shadows
- No global ambient occlusion turned to max — kills the cartoon look

### Composition
- Hero asset in centre or slight off-centre per rule-of-thirds
- Filler scatter along edges and around hero
- Foreground / midground / background separation (palms framing the lagoon, hut in middle, distant island silhouette)
- Camera ~35mm focal length (matches Nintendo aerial-three-quarter common framing)

## The first reference image to test on

A starter brief distilled into a prompt for nano-banana / Imagen / Stable Diffusion:

> "Stylised tropical beach island, Nintendo-style cartoon art, Banjo-Kazooie meets Wind Waker. Small round sandy island in turquoise ocean, three tall cartoon palm trees clustered on the right, one small thatched-roof wooden hut in centre, scattered mossy round rocks on the left shore, golden-hour lighting. Saturated warm palette: warm sand, saturated turquoise water, mid-green foliage. Three-quarter aerial view, ~35mm focal length feel. Highly stylised, toon shading, NOT photoreal, NOT realistic."

Generate this in your image tool of choice and drop the result into `input/banjo-beach.png` to kick off the first world build.

## Anti-patterns (what we DON'T want)

- Photoreal sand (looks weird next to cartoon palms)
- Generic Unity/Unreal asset-store realism
- Muted "AAA grim" palettes
- Crisp 90-degree edges everywhere — they make the scene feel CAD-modelled
- Overly-symmetric layouts (kills stylisation; Nintendo deliberately offsets things)
- "Slop"-tier AI-render symmetry — the model will tend toward this; the prompt + style anchor must push against it

## How the analyzer should detect the style

When `analyze-reference` reads `input/<file>.png`, it should:

1. Identify the closest anchor from the list above (or "custom" if no clear match).
2. Estimate the level of stylisation: `high` (Wind Waker / Banjo), `mid` (Scarlet/Violet), `low` (Horizon FW / photoreal stylised). This drives all downstream prompts.
3. Sample the dominant 4-5 colours from the reference into `plan.style.palette`.
4. Note the lighting direction + colour temperature (warm/cool, harsh/diffuse).
5. Note the camera framing.

That structured detection makes the rest of the pipeline (asset gen prompts, terrain shader, sky HDRI selection) deterministic.
