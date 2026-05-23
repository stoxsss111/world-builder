# Example world — `banjo-island`

The first reference scene to test world-builder on. Stylised tropical beach island, Banjo-Kazooie × Wind Waker × Mario Sunshine aesthetic.

## How to use this folder

1. Generate the reference image (see prompt below) — drop it as `reference.png` next to this file.
2. Copy `reference.png` → `input/banjo-island.png` (or symlink).
3. In Claude Code, say: `Build me a world from input/banjo-island.png called banjo-island`.
4. After the loop runs, the actual `worlds/banjo-island/` folder will contain the build artifacts.

## Reference image prompt (for nano-banana / Imagen / Midjourney / SD)

> Stylised tropical beach island, Nintendo-style cartoon art, Banjo-Kazooie meets Wind Waker. Small round sandy island in turquoise ocean, three tall cartoon palm trees clustered on the right with curved trunks and saturated green fronds, one small thatched-roof wooden tiki hut in centre, scattered mossy round rocks on the left shore, a couple of cartoon starfish and conch shells on the sand, golden-hour sunset lighting. Saturated warm palette: warm sand, saturated turquoise water, mid-green foliage, orange-pink sky. Three-quarter aerial view at roughly 35mm focal length. Highly stylised toon shading, NOT photoreal, NOT realistic. No characters, no text, no UI.

## Expected scene plan (rough — fits the 25-instance cap)

When `analyze-reference` reads this, the resulting `plan.json` should look approximately like (25 total instances, every object has `face_limit` in the 5-15k range):

```jsonc
{
  "world_slug": "banjo-island",
  "style": {
    "anchor": "Banjo-Kazooie · Treasure Trove Cove × Wind Waker",
    "palette": ["#f2d790", "#3aa6b8", "#1f6f4b", "#9c6a3c", "#f08e7e"],
    "level_of_stylization": "high",
    "shading": "toon",
    "lighting": "golden-hour"
  },
  "terrain": {
    "shape": "island",
    "ground": "sand",
    "water": { "present": true, "level": -0.05 },
    "size_meters": [12, 12],
    "feature_notes": "Slight rise centre-right, palm cluster on south-east, rocks lining west shore, flatter sand belt on south."
  },
  "objects": [
    { "id": "palm-tall",      "name": "Tall stylised cartoon palm tree, thick trunk, saturated green fronds",       "count": 3, "approx_positions": [[2, 1], [3, 0.5], [2.5, 2]],            "scale_hint": "tall",   "priority": "hero",   "face_limit": 12000 },
    { "id": "palm-bent",      "name": "Short bent palm tree, curving trunk, fewer fronds",                          "count": 2, "approx_positions": [[-1, 1], [0, 3]],                       "scale_hint": "medium", "priority": "hero",   "face_limit": 11000 },
    { "id": "tiki-hut",       "name": "Small wooden tiki beach hut, thatched palm-leaf roof, open front",           "count": 1, "approx_positions": [[0, 0]],                                "scale_hint": "large",  "priority": "hero",   "face_limit": 14000 },
    { "id": "treasure-chest", "name": "Small wooden treasure chest with iron bands and gold trim, partly buried",   "count": 1, "approx_positions": [[1.2, 0.3]],                            "scale_hint": "small",  "priority": "hero",   "face_limit": 12000 },
    { "id": "rock-mossy",     "name": "Round mossy beach rock, smooth top, cartoon proportions",                    "count": 4, "approx_positions": [[-2, 2], [-3, 1], [-2.5, 3], [-1.8, 2.5]], "scale_hint": "medium", "priority": "filler", "face_limit": 8000 },
    { "id": "rock-small",     "name": "Small cartoon pebble",                                                       "count": 6, "approx_positions": [[-1, 0], [-1.5, 0.5], [1, -1], [1.5, -0.5], [2, -1.5], [-0.5, -2]], "scale_hint": "small", "priority": "filler", "face_limit": 5500 },
    { "id": "starfish",       "name": "Orange cartoon starfish, flat lying on sand",                                "count": 3, "approx_positions": [[1, -2], [2, -2.5], [0.5, -1.8]],       "scale_hint": "small",  "priority": "filler", "face_limit": 6000 },
    { "id": "shell-conch",    "name": "Pink-interior conch shell sitting on sand",                                  "count": 3, "approx_positions": [[-0.5, 1], [1.5, 1], [-1.8, 0.5]],      "scale_hint": "small",  "priority": "filler", "face_limit": 7000 },
    { "id": "lantern-tiki",   "name": "Tiki bamboo lantern on a wooden post",                                       "count": 2, "approx_positions": [[-0.5, -0.5], [0.5, -0.8]],             "scale_hint": "medium", "priority": "hero",   "face_limit": 11000 }
  ],
  "camera": { "framing": "three-quarter aerial", "focal_length_mm": 35 }
}
```

**Instance count: 3+2+1+1+4+6+3+3+2 = 25** ✓ (fits the default cap exactly)
**Distinct generations: 9** (one per `id`, then re-instanced via `count`)

## Cost estimate

Routing per `docs/api-research.md`:
- 5 hero ids × Tripo P1 textured = 5 × $0.50 = **$2.50**
- 4 filler ids × Trellis 2 1024p = 4 × $0.30 = **$1.20**
- 9 nano-banana reference plates × $0.039 = **$0.35**
- **Total fal spend ≈ $4.05** for the 9 distinct generations
- Plus ~$3-6 in Claude tokens for the loop

**Total per build ≈ $7-10.**
