# Architecture

`world-builder` is a Claude Code agent project that wires three things together:

1. **Claude Code's vision-loop** — the model sees image content returned by MCP tools as multimodal input, reasons about it, and decides the next action.
2. **Blender MCP server** (`ahujasid/blender-mcp` v1.5.5) — exposes Blender's Python API + a `get_viewport_screenshot` tool that returns PNG bytes inline.
3. **fal.ai** — for asset generation (Tripo P1 textured for stylised 3D, Trellis 2 fallback, nano-banana for image cleanup if needed).

The agent doesn't render anything itself — it composes calls between these three.

## The whole picture

```
┌────────────────────────────────────────────────────────────────────────┐
│  USER                                                                  │
│  drops reference.png into input/ and says                              │
│  "build me a world from input/banjo-beach.png, call it banjo-beach"    │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│  CLAUDE CODE  (terminal, --dangerously-skip-permissions)               │
│  loads `.claude/skills/build-world/SKILL.md`                           │
│  reads input/banjo-beach.png as multimodal input                       │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                ┌─────────────────┴─────────────────┐
                ▼                                   ▼
┌──────────────────────────┐         ┌─────────────────────────────────┐
│  FAL.AI                  │         │  BLENDER MCP SERVER             │
│  asset generation        │         │  (Python, port 9876)            │
│                          │         │                                 │
│  • tripo3d/p1/image-to-3d│         │  • get_viewport_screenshot      │
│    ($0.50 textured)      │         │  • execute_blender_code         │
│  • fal-ai/trellis-2      │         │  • get_scene_info               │
│    ($0.25-0.35)          │         │  • download_polyhaven_asset     │
│  • nano-banana (edit)    │         │  • search_sketchfab_models      │
│                          │         │  • set_texture                  │
│  scripts:                │         │                                 │
│  .claude/scripts/        │         │  Talks to live Blender on       │
│  asset-pipeline/         │         │  localhost:9876 via socket      │
└──────────────────────────┘         └─────────────────────────────────┘
                │                                   │
                ▼                                   ▼
        worlds/<slug>/assets/                 BLENDER 5.1 LTS
        ├── palm-tree.glb                     (the actual app)
        ├── beach-hut.glb                     scene gets built here
        └── ...
```

## Why these three pieces

| Piece | Why it's here | What it can't do |
|---|---|---|
| Claude Code | Multimodal model, native image understanding, runs loops via `/loop`, MCP-native, can write its own skills mid-flight, shows `/cost` | Doesn't render. Doesn't know Blender Python API perfectly — needs `CLAUDE.md` hints to stay on rails. |
| Blender MCP | Live Blender session, screenshot-as-Image-block, arbitrary Python via `execute_blender_code`, free CC0 asset access (Poly Haven, Sketchfab) built in | Can't generate 3D from images on its own — needs an external API for that. |
| fal.ai | Best-in-class hosted access to Tripo P1 textured ($0.50/asset, PBR included), PATINA PBR-material gen (~$0.08 per surface), nano-banana for reference plates. Pay-as-you-go. | Not free. Doesn't run inside Blender — outputs URLs that we download and import. |

## The autonomous loop, drawn out

This is the bit that makes the demo land. The mechanism is verified end-to-end against the `ahujasid/blender-mcp` v1.5.5 server source.

```
┌──────────────────────────────────────────────────────────┐
│  ITERATION N                                             │
│                                                          │
│  1.  tool_call:  get_viewport_screenshot(max_size=800)   │
│      ─────────────────────────────────────────────►      │
│                                                          │
│  2.  tool_result: ImageContent(png, inline)              │
│      ◄─────────────────────────────────────────          │
│                                                          │
│  3.  CLAUDE SEES the image as multimodal input.          │
│      Compares to reference.png (also multimodal).        │
│      Decides what's off:                                 │
│        "palm trees too tall, sand looks grey, missing    │
│         the lagoon edge on the left."                    │
│                                                          │
│  4.  tool_call:  execute_blender_code(...)               │
│      ─────────────────────────────────────────►          │
│      (scale palms 0.6, swap ground texture for warmer    │
│       sand HDRI, add ocean plane at z=-0.05)             │
│                                                          │
│  5.  tool_result: "OK"                                   │
│      ◄─────────────────────────────────────────          │
│                                                          │
│  GOTO 1 — until visual match or 25 iter cap              │
└──────────────────────────────────────────────────────────┘
```

The key insight: Claude Code's MCP client feeds `Image` content blocks from MCP tools to the model as **first-class multimodal input**, the same way `Read` on a PNG does. There's no "save screenshot to disk then read it" workaround — the round-trip is native.

Source: `ahujasid/blender-mcp` v1.5.5 `src/blender_mcp/server.py`:
```python
@mcp.tool()
def get_viewport_screenshot(ctx, max_size: int = 800):
    # …RPC to Blender, render, read bytes, delete tmp…
    return Image(data=image_bytes, format="png")
```

And Claude Code's MCP docs explicitly document image-content support (with the caveat that image tools count against `MAX_MCP_OUTPUT_TOKENS`).

## Pipeline phases

The pipeline lives in `docs/PIPELINE.md` — each phase has a corresponding skill in `.claude/skills/`:

| Phase | Skill | Output |
|---|---|---|
| 0. Analyse | `analyze-reference` | `worlds/<slug>/plan.json` |
| 1. Terrain (primitives) | `procedural-terrain` | ground / water / grass primitives in Blender |
| 1.5. Surface materials | `generate-material` (×3 in parallel) | `worlds/<slug>/materials/<id>/*.png` PATINA PBR sets applied |
| 2. Objects | `generate-3d` (×N, parallel) | `worlds/<slug>/assets/*.glb` |
| 3. Sky | (inline via blender-mcp Poly Haven) | HDRI on world background |
| 4. Place + iterate | `place-and-iterate` | imported, positioned, refined scene (composite-screenshot loop) |
| 5. Render | (inline) | `worlds/<slug>/final.render.png` |

`build-world` is the conductor — it calls the others in order, manages state in `worlds/<slug>/plan.json`, and writes the final summary.

## The procedural-vs-generated split

A core design choice. SURFACES (the "ground" of the scene) and OBJECTS (the "things on" the scene) take completely different paths:

| Category | Examples | Production path | Cost |
|---|---|---|---|
| **Procedural surface** | Sand ground, water plane, grass patches, dirt | Blender primitive → PATINA-generated PBR maps applied | ~$0.08 per surface |
| **Generated object** | Palms, chests, lanterns, log-stumps, boulders, flowers, huts | Tripo P1 image-to-3d (textured, PBR baked in) | $0.50 per distinct ID |
| **Procedural object** (optional) | Stylised trees, generic rocks, grass blades for scatter | Free Blender plugins (Stylized Fantasy Tree, Rock Generator) | $0 |

The procedural path keeps tile-able materials looking right at any zoom level. The generated path keeps objects looking like the reference image. Mixing the two means a 20-25-object scene total cost stays around $4-6 in fal spend.

## What lives where

```
world-builder/
├── README.md                    # user-facing pitch + quickstart
├── CLAUDE.md                    # high-level agent context (this is what Claude loads on start)
├── docs/
│   ├── ARCHITECTURE.md          # ← you are here
│   ├── PIPELINE.md              # step-by-step phase walkthrough
│   ├── api-research.md          # provider choices: Tripo P1, Trellis 2, vision, free assets
│   ├── style-references.md      # Banjo / Wind Waker / Mario Sunshine stylistic anchors
│   └── blender-mcp-setup.md     # how to wire blender-mcp and what tools it exposes
├── .claude/
│   ├── settings.json            # mcp servers, permissions, env
│   ├── skills/                  # the 5 skills (build-world, analyze-reference, generate-3d, …)
│   ├── agents/                  # forked agent personas if a skill needs context: fork
│   ├── scripts/
│   │   ├── fal/run-fal.mjs              # general fal endpoint runner (from image-blaster)
│   │   ├── asset-pipeline/
│   │   │   ├── fal-queue.mjs            # shared fal client helpers
│   │   │   ├── tripo-p1.mjs             # NEW — Tripo P1 image-to-3d provider
│   │   │   ├── trellis-2.mjs            # NEW — Trellis 2 fallback
│   │   │   ├── nano-banana-edit.mjs     # image edit (clean plate / extraction)
│   │   │   └── generate-single-asset.mjs# the per-asset orchestrator
│   │   ├── blender/
│   │   │   ├── procedural-terrain.py    # GN terrain template (Claude tweaks it)
│   │   │   ├── place-asset.py           # GLB import + transform helpers
│   │   │   └── README.md
│   │   └── project/project-state.mjs    # worlds/<slug> state I/O
│   └── hooks/setup-check.sh             # validates FAL_KEY + blender-mcp + Blender version
├── input/                       # user drops reference images here
└── worlds/
    └── <slug>/                  # one folder per built world (see CLAUDE.md output layout)
```

## What we deliberately did NOT include

- **No Hunyuan3D** — too expensive at scale, stylisation is mid for cartoon aesthetics.
- **No Trellis 2 fallback** — quality drop noticeable in stylised cases; better to retry Tripo P1 with a fixed reference plate than swap to a worse model mid-scene.
- **No World Labs Marble** — pure 3D only, not Gaussian splats.
- **No sound** — image-blaster has SFX via ElevenLabs; world-builder is silent. (Could add later as an optional skill.)
- **No game engine export** — output is `.blend`. Hand-off to UE / Unity / Three.js separately.
- **No character animation** — known weak spot in current image-to-3D models. Out of scope.
- **No physics simulation** — out of scope.
- **No custom skybox generation in v1** — Poly Haven HDRIs cover the cases. Generated skydome via fal image gen + hemisphere projection is a stretch goal for v2 if Poly Haven coverage feels stale.

These are deferred so the scaffold stays focused. Each could be a follow-up skill.
