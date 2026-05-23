# Blender scripts

These Python files are **not run directly** — they're templates that Claude pastes (with substitutions) into the `execute_blender_code(code)` MCP tool. The live Blender session executes them in-process.

| File | Purpose |
|---|---|
| `procedural-terrain.py` | Build the ground + water + GN terrain modifier with named groups and exposed parameters. |
| `place-asset.py` | Import a GLB, position/scale/tag it for the loop. Plus reposition / remove helpers used by the judge. |

## Pattern Claude follows

```python
# 1) Read this file
template = open(".claude/scripts/blender/procedural-terrain.py").read()

# 2) Substitute the parameter constants at the top
code = template.replace('SIZE_X = 12.0', f'SIZE_X = {plan.terrain.size_meters[0]}')\
               .replace('SHAPE = "island"', f'SHAPE = "{plan.terrain.shape}"')\
               # ... etc

# 3) Send to Blender via MCP
execute_blender_code(code)

# 4) Screenshot to confirm
screenshot = get_viewport_screenshot(max_size=800)
```

This pattern is documented in `docs/PIPELINE.md`. Claude doesn't compose Blender Python from scratch — it edits known-good templates. That's how we sidestep the GN-API-drift problem (the model's training data may not match the installed Blender's GN node names).
