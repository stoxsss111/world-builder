# Blender MCP setup — verified mechanism

This doc captures **exactly** how Claude Code talks to Blender. Verified against primary sources (the `ahujasid/blender-mcp` v1.5.5 server source).

## The two pieces

```
┌─────────────────────────────────────────────┐
│  Claude Code (terminal)                     │
│  loads .claude/settings.json with mcp entry │
└─────────────────────────────────────────────┘
                  ▲
                  │ MCP protocol (stdio)
                  ▼
┌─────────────────────────────────────────────┐
│  blender-mcp (Python, ahujasid v1.5.5)      │
│  launched by `uvx blender-mcp`              │
│  exposes 22 tools (see tool list below)     │
└─────────────────────────────────────────────┘
                  ▲
                  │ socket on localhost:9876
                  ▼
┌─────────────────────────────────────────────┐
│  Blender 5.1 LTS (the GUI app)              │
│  with the "BlenderMCP" add-on enabled       │
│  (drag-install from blender.org/lab/mcp)    │
└─────────────────────────────────────────────┘
```

## One-time installation

```bash
# 1) Install Blender 5.1 LTS from blender.org/download/lts/

# 2) Install the Blender MCP add-on
#    Open Blender → drag the link from blender.org/lab/mcp-server into the viewport
#    Drag TWICE: first drag adds the Lab extension repo, second drag installs the add-on
#    Press N → BlenderMCP tab → click "Connect to Claude"
#    The add-on now listens on localhost:9876

# 3) Add the MCP server to Claude Code
claude mcp add blender uvx blender-mcp

# 4) Verify
claude mcp list                       # expect: blender ✓
```

The world-builder repo ships `.claude/settings.json` with this server pre-registered, so step 3 is automatic when you `cd world-builder && claude` in a fresh terminal.

## Per-session setup

Before kicking the autonomous loop:

```bash
# Raise the image-token cap for long loops (default 25k truncates screenshots silently)
export MAX_MCP_OUTPUT_TOKENS=50000

# Launch Claude Code with permissions bypassed for the demo
claude --dangerously-skip-permissions
```

Then inside the Claude Code session, before running any build:

```python
# Reset Blender viewport to known-good state — material-preview shading, perspective camera
# (otherwise the first screenshot will be whatever wireframe was left over)
execute_blender_code("""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'
                space.region_3d.view_perspective = 'PERSP'
""")
```

## The tools we use (subset of the 22)

Source: `ahujasid/blender-mcp` v1.5.5 `src/blender_mcp/server.py`.

| Tool | Returns | What we use it for |
|---|---|---|
| `get_viewport_screenshot(max_size=800)` | **`Image(png)` — MCP image block** | Eyes of the loop. After every change. Always `max_size=800` (bigger 4× the cost without helping). |
| `execute_blender_code(code)` | `str` | Hands. Procedural terrain, GLB import, transform, materials, render. |
| `get_scene_info()` | `str (JSON)` | Quick scene-state read between iterations. |
| `get_object_info(name)` | `str (JSON)` | Drill into one object before adjusting it. |
| `download_polyhaven_asset(asset_id, asset_type, resolution)` | `str` | Free CC0 HDRIs, textures, some models. |
| `set_texture(object_name, texture_id)` | `str` | Apply a Poly Haven texture to an object. |
| `get_polyhaven_status()` | `str` | Verify Poly Haven access before the run. |
| `search_sketchfab_models(query, count, downloadable)` | `str` | CC-licensed model search (use sparingly — most are CC-BY not CC0). |
| `download_sketchfab_model(uid, target_size)` | `str` | If a Sketchfab model would save a Tripo call. |
| `get_sketchfab_model_preview(uid)` | **`Image`** | Visual preview before deciding to download. |

**Not used (but available):**
- All Hyper3D Rodin tools — use Tripo P1 instead
- All Hunyuan3D tools — same
- Sketchfab `get_sketchfab_status` — handled by error from search

## How the vision loop actually works

The KEY mechanism: `get_viewport_screenshot` returns an MCP `Image` content block (PNG bytes inline). Claude Code's MCP client feeds image content from tool results to the model as **first-class multimodal input** — exactly like `Read` on a PNG. There is no "save screenshot to disk then re-read" workaround.

Source-level proof from `server.py`:
```python
@mcp.tool()
def get_viewport_screenshot(ctx, max_size: int = 800):
    # RPC to Blender add-on, render viewport, read bytes, delete tmp
    return Image(data=image_bytes, format="png")
```

And Claude Code's MCP docs explicitly call out image-content support (with the caveat that image tools count against `MAX_MCP_OUTPUT_TOKENS`, hence why we raise it to 50k).

## Gotchas to handle in code

1. **GitHub issue #148** — Linux: temp screenshot file not created. Affects some distros where Blender can't write to `/tmp`. Non-issue on Windows. The `setup-check.sh` hook detects Linux and warns.
2. **GN API drift** — Geometry Nodes API changes between Blender versions. Claude's training data may not match the installed Blender's GN node names. Mitigation: lock to **Blender 5.1 LTS**, pre-seed `.claude/scripts/blender/procedural-terrain.py` with known-good node names (`GeometryNodeDistributePointsOnFaces`, `GeometryNodeRaycast`, etc.).
3. **Headless mode is not supported** — Blender MCP requires the GUI app running with the add-on active. Cannot run in pure CI.
4. **Image content tokens** — without `MAX_MCP_OUTPUT_TOKENS=50000`, screenshots truncate silently around the ~25k default and vision degrades mid-loop with no error.
5. **Always save .blend after each iteration** to `iterations/NNN.blend.bak` so a stall doesn't lose work. Use `bpy.ops.wm.save_as_mainfile(filepath=..., copy=True)` — `copy=True` keeps the current session's filepath intact.

## When something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `claude mcp list` doesn't show `blender` | Server name conflict or add failed | Re-run `claude mcp add blender uvx blender-mcp` |
| Screenshots are black | Viewport in wireframe shading | Run the viewport-reset snippet above |
| Screenshots are blank/empty | Camera not in scene or pointing at nothing | Set camera + Lock Camera to View |
| `get_viewport_screenshot` errors | Blender add-on not connected | Press N in Blender → BlenderMCP tab → "Connect to Claude" |
| GN nodes not found (e.g. `GeometryNodePointDistribute`) | Blender version mismatch | Confirm Blender 5.1 LTS, check `bpy.app.version` |
| Long loops degrade visually | Image-token cap hit | `export MAX_MCP_OUTPUT_TOKENS=50000` before launching |
| Tripo P1 returns 400 | Image too large or wrong format | Run `nano-banana-edit` clean-plate first, ≤2048px square |

## References

- [`ahujasid/blender-mcp`](https://github.com/ahujasid/blender-mcp) — source of truth
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) — confirms image-content support and `MAX_MCP_OUTPUT_TOKENS`
- [Blender Lab MCP add-on](https://www.blender.org/lab/mcp-server/) — install path
