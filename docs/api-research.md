# API Research — verified provider choices

All endpoints verified via fal.ai search results 2026-05-22. Prices in USD. Speeds are fal's published estimates — actual varies under load.

## 3D model generation

| Endpoint | Cost / generation | Speed | Quality | Use in world-builder |
|---|---|---|---|---|
| `tripo3d/p1/image-to-3d` | **$0.40 untextured / $0.50 textured (PBR auto-included)** | ~60-90s | Best for stylised game-ready meshes. Optimised topology. | **Sole 3D-asset provider.** |
| `tripo3d/p1/text-to-3d` | $0.40 / $0.50 textured | ~60-90s | Same model, text input instead of image. | When no reference image is needed for an asset. |
| `fal-ai/trellis-2` | $0.25 (512p) / $0.30 (1024p) / $0.35 (1536p) | ~30-60s | Native 3D generative model. | **Not used.** Quality drop noticeable in stylised cases. Retry P1 with a better reference plate instead. |
| `tripo3d/tripo/v2.5/image-to-3d` | $0.20 / $0.30 std-tex / $0.40 HD-tex | ~60-90s | Older Tripo. Cheaper, more variance. | Not used in v1. |
| `fal-ai/hunyuan3d/v2` | ~$0.30 | ~60s | Used in image-blaster. Mid stylisation. | Not used. |

### Tripo P1 input parameters (verified against fal.ai/models/tripo3d/p1/image-to-3d/api)

| Param | Type | Default | Range | Notes |
|---|---|---|---|---|
| `image_url` | string | — | URL or fal-uploaded path | Required. Reference image for the gen. |
| `texture` | bool | `true` | true/false | When `true`, output includes a `pbr_model` variant with PBR maps baked in. There is no separate PBR input flag. |
| `face_limit` | int | model-decided | world-builder clamps to **5,000-15,000** | Project sweet spot. Below 5k = blocky; above 15k = wasted detail you can't see in a stylised scene. |
| `model_seed` | int | unset | any | Seed for geometry reproducibility on retries. |

No `quality`, `style`, or explicit `pbr` flag exist. The `pbr_model` URL is in the OUTPUT, not the input.

### Polycount routing by object class

The `generate-3d` skill picks `face_limit` per object based on its role:

| Object class | face_limit | Examples |
|---|---:|---|
| Hero structural | **12,000-15,000** | tiki hut, treasure chest, beach hut, lantern post |
| Hero organic | **10,000-13,000** | tall palm, big rock, bent palm, statue |
| Mid-detail | **7,000-9,000** | medium rock, barrel, conch shell, starfish |
| Filler | **5,000-6,000** | pebble, small shell, twig, debris |

### Per-scene budget — the 20-25 working range

**Target 20-25 total instances** for a Banjo-style island. That's the realistic density — fewer and the scene feels empty, more and you're burning budget without visual gain.

**25 is the SOFT CAP before asking the user**, not a goal. A sparser reference may justify 10-12 instances; a denser one may justify raising to 30 with confirmation. The `analyze-reference` skill enforces this — if the plan needs >25 instances, it stops and asks.

Cost at 20-25 instances, single-provider (Tripo P1):
- Distinct generations: typically 7-10 (re-instanced via `count` to fill 20-25)
- Tripo P1 spend: **~$3.50 - $5.00**
- nano-banana reference plates: ~$0.27 - $0.39
- **Total 3D-asset spend: ~$4 - $6**

If 1-2 classes are covered by procedural alternatives (palms, rocks): cut another ~$1-2.

**Cost per scene at the 20-25-instance working range (single provider):**
- Tripo P1 textured × 25 instances = **$12.50** worst case
- Tripo P1 textured × ~8 distinct generations (re-instanced 20-25 times) = **~$4** typical
- Procedural alternatives (Stylized Fantasy Tree, Rock Generator) replace ~5 gens = **~$2 saved**

**Default policy:** Tripo P1 textured for every object class that doesn't have a procedural alternative. Re-instance via `count` to cover the 20-25 working range without burning multiple generations on the same mesh. See `docs/plugins-research.md` for the free procedural generators that can replace specific classes (palms, rocks).

## Image generation / editing

Used for: cleaning up the reference, isolating individual objects, generating any synthetic concept the user didn't provide.

| Endpoint | Cost | Use |
|---|---|---|
| `fal-ai/nano-banana/edit` | $0.039/image | Clean-plate edits, isolate one object on white bg (for Tripo input). Same as image-blaster. |
| `fal-ai/nano-banana-pro/text-to-image` | $0.039/image (2K) | Generate reference plates for object gen. Higher resolution than banana 2. |
| `fal-ai/gpt-image-2/edit` | $0.04+ | Alt edit model. Used if banana misses. |

## PBR materials — fal PATINA

For PROCEDURAL surfaces (sand, water, grass). Generates a full PBR set (BaseColor + Normal + Roughness + Metalness + Height) from a text prompt, optimised for seamless tiling.

| Endpoint | Pricing model | Total at common res | Use in world-builder |
|---|---|---|---|
| `fal-ai/patina/material` (text-to-PBR) | $0.01 base + $0.02/MP + $0.01/MP per map (5 maps) | ~$0.08 @ 1024 / ~$0.30 @ 2048 / ~$1.18 @ 4096 | **Primary** for all procedural surfaces. |
| `fal-ai/patina` (image-to-PBR) | $0.01 base + $0.01/MP per map | ~$0.06 @ 1024 | When you already have a reference texture and want PBR maps from it. |

**Typical material spend per world:** sand + water + grass = 3 materials at 1024 = **~$0.24**. Cheap enough to iterate 1-2 times if the first attempt misses.

Default resolution: **1024px**. Stylised scenes don't need more — and 2048+ quadruples the per-material cost without visible benefit in the bird-view final render.

## Vision (analyse the reference)

**We don't use an external vision model.** Claude Code is multimodal — the agent reads PNGs from `input/` directly via the `Read` tool and reasons about them. Saves an API call per scene. Confirmed by ahujasid/blender-mcp's own pattern: it returns `Image` blocks that Claude reads natively.

If we needed an external vision pass for any reason (e.g., extreme cost optimisation where we want to use Haiku for the loop):

| Endpoint | Cost | Note |
|---|---|---|
| `fal-ai/qwen2-vl-7b` | ~$0.002/call | Cheap fallback for routine vision. |
| `google/gemini-2.5-pro` (via fal) | ~$0.005/image | Strong vision, good Blender-context understanding. |
| Anthropic API direct | varies by model | Claude Code's own model handles this natively — don't pay twice. |

## Free 3D / texture / HDRI libraries (CC0)

These come for free through the blender-mcp's existing tools (`download_polyhaven_asset`, `search_sketchfab_models`). Use them BEFORE paying fal for generation when an existing asset will do.

| Source | Coverage | Access method |
|---|---|---|
| **Poly Haven** | HDRIs (~700), Textures (~600), Models (~250) — all CC0. Mostly realistic. | `download_polyhaven_asset(asset_id, asset_type, resolution)` via blender-mcp |
| **Sketchfab** | Massive — but most assets are CC-BY (require attribution). Some CC0. | `search_sketchfab_models(query)` + `download_sketchfab_model(uid, target_size)` via blender-mcp |
| **Kenney.nl** | CC0 stylised low-poly assets — perfect match for Banjo/Wind Waker aesthetic. **No formal API** but predictable URL structure. | TBD — could ship a small fetcher script if needed. |
| **Quaternius** | CC0 stylised low-poly — great for cartoon-style scenes. **No API.** | Manual download for now. |

**Recommendation:** Tripo P1 is the primary path. CC0 libraries are the optional optimisation for cost-sensitive runs once the scaffold proves out.

## Cost ceiling for a single world build

Rough budget for a Banjo-style island scene at the 20-25 working range, single 3D provider (Tripo P1), procedural-PATINA surfaces:

| Item | Count | Unit cost | Total |
|---|---|---|---|
| Tripo P1 textured | 7-10 distinct (re-instanced to 20-25) | $0.50 | $3.50 - $5.00 |
| PATINA materials @ 1024 | 3 (sand + water + grass) | $0.08 | $0.24 |
| Nano-banana reference plates | 7-10 (one per distinct Tripo) | $0.039 | $0.27 - $0.39 |
| **Total fal spend per scene** | | | **$4.00 - $5.60** |

Plus Claude tokens for the loop. With the composite-screenshot optimisation (one image input per iteration instead of three), `MAX_MCP_OUTPUT_TOKENS=50000`, and ~15-20 average iterations: rough estimate **$2-4 in Claude tokens**.

**Total per scene: ~$6-10.**

If procedural alternatives (Stylized Fantasy Tree, Blender Studio Rock Generator) cover 1-2 classes: drop another ~$1-2.

This is the headline cost figure for the project.

## Performance / time budget

| Phase | Wall-clock (typical) |
|---|---|
| 0. Analyse reference | <30s (Claude reads + emits JSON plan) |
| 1. Procedural terrain (primitives) | 30-60s (one `execute_blender_code` round) |
| 1.5. PATINA materials | ~1-2 min (3 materials in parallel, applied) |
| 2. Object generation (parallel) | 2-3 min (fal parallel, 7-10 distinct fire at once) |
| 3. Sky & HDRI | 30s (Poly Haven download + set) |
| 4. **Place + iterate (the loop)** | **8-15 min** (15-20 iter × ~30s, composite-screenshot optimisation) |
| 5. Render | 30-60s (Eevee Next final at 1920×1080) |
| **Total** | **~15-25 min** |

Loop time dropped from ~15-30 min (in the previous estimate) to **~8-15 min** thanks to:
- Eevee Next instead of Cycles
- Composite-screenshot (one image input per iter instead of three)
- Backup every 5th iter instead of every iter
- 512×384 per-angle composite panel resolution

"20 minutes unattended" is the wall-clock target — and the actual figure typically comes in under that.

## Sources

- [Tripo P1 image-to-3d on fal](https://fal.ai/models/tripo3d/p1/image-to-3d) — $0.40/$0.50 confirmed
- [Trellis 2 on fal](https://fal.ai/models/fal-ai/trellis-2) — $0.25/$0.30/$0.35 confirmed
- [Tripo v2.5 image-to-3d on fal](https://fal.ai/models/tripo3d/tripo/v2.5/image-to-3d) — $0.20-$0.40 confirmed
- [fal pricing index](https://fal.ai/pricing)
- [ahujasid/blender-mcp v1.5.5 server.py](https://github.com/ahujasid/blender-mcp/blob/main/src/blender_mcp/server.py) — for the tool list and Image return type
