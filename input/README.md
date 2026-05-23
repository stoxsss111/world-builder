# `input/` — drop reference images here

Drop your reference image into this folder, then ask Claude:

> Build me a world from `input/<your-file>.png` called `<world-slug>`.

The orchestrator copies the file to `worlds/<world-slug>/source/reference.png` and starts the pipeline.

## What works as a reference

- A stylised game-art screenshot (Wind Waker / Banjo-Kazooie / Mario Sunshine / Pokémon SV / Bananza)
- An AI-generated concept (use nano-banana / Imagen / Midjourney — see `worlds/_examples/banjo-island/prompts.md` for an example prompt)
- A photo of a real place you want to stylise (the analyzer will detect this and downgrade `level_of_stylization` accordingly)

## What doesn't work well

- Character portraits (out of scope for v1)
- Photos with heavy depth-of-field (the analyzer reads them as "fewer objects than really exist")
- Wireframe sketches or pencil drawings (need full colour for palette + lighting detection)
- Vertical-format images (the analyzer expects landscape / square framing for the aerial view)

Stick to landscape, well-lit, painterly/stylised images for best results.
