#!/usr/bin/env node
/**
 * Take the top-down control view of the scene and recompose it as a zoned
 * planning map: solid colour zones (sand / water / grass) + colored dots
 * indicating where each object class should sit.
 *
 * Output: worlds/<slug>/controls/zones.png  (used by build-world to read approx_positions)
 *
 * Usage:
 *   node .claude/scripts/asset-pipeline/annotate-top-down.mjs \
 *     --top worlds/<slug>/controls/top.png \
 *     --output-dir worlds/<slug>/controls \
 *     --object-classes "stone-arch,tiki-hut,palm-tall,palm-small,boulder,campfire,treasure-chest,flower,shell"
 */
import { mkdir, readdir, rename, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { runNanoBananaEdit } from "./nano-banana-edit.mjs";
import { one, parseArgs } from "./fal-queue.mjs";

const COLOR_KEY = `Zone colours:
  - SAND     = solid hex #F5C97A (warm yellow)
  - WATER    = solid hex #5BC9D4 (turquoise)
  - GRASS    = solid hex #7DC25A (emerald)
Object dot colours (4-8 px filled circles centred on each instance):
  - HERO_STRUCTURE (arch, hut, torch, chest)        = #E63946 (red)
  - LARGE_TREE / PALM-TALL                          = #2A7F2A (dark green)
  - SMALL_TREE / PALM-SMALL                         = #76C25A (light green)
  - LARGE_ROCK / BOULDER-MOSSY-LARGE                = #5A5A5A (dark gray)
  - SMALL_ROCK / BOULDER-MOSSY-SMALL                = #A8A8A8 (light gray)
  - CAMPFIRE / LOG / WOOD                           = #8B4A1A (warm brown)
  - FLOWER                                          = #E876B0 (magenta)
  - SHELL / SMALL_DEBRIS                            = #FFE0A0 (pale yellow)`;

export async function annotateTopDown({ topPath, outputDir, objectClasses }) {
  if (!topPath) throw new Error("topPath is required.");
  if (!outputDir) throw new Error("outputDir is required.");
  await mkdir(outputDir, { recursive: true });

  const classes = objectClasses && objectClasses.length ? `Classes: ${objectClasses}.` : "";

  const prompt = `Convert this top-down island scene into a flat zoned planning map. Replace every textured surface with SOLID FLAT COLOUR fills (no shading, no gradients, no detail). Replace every object with a SMALL FILLED CIRCLE in the colour from the key below, placed at the same XY position as the object in the source. No labels, no text — ONLY zones and dots. Use exactly these colours:\n${COLOR_KEY}\n${classes}\nKeep the same composition, same scene bounds, same orientation as the source. Output is a clean planning map — looks like an architectural / level-design diagram.`;

  const tmpDir = `${outputDir}/_zones-tmp`;
  await mkdir(tmpDir, { recursive: true });
  const summary = await runNanoBananaEdit({
    prompt,
    images: [topPath],
    outputDir: tmpDir,
    numImages: 1,
    aspectRatio: "1:1",
    resolution: "1K",
    outputFormat: "png",
    safetyTolerance: "4"
  });
  const files = (await readdir(tmpDir)).filter((f) => f.endsWith(".png"));
  let finalPath = null;
  if (files.length > 0) {
    finalPath = `${outputDir}/zones.png`;
    await rename(`${tmpDir}/${files[0]}`, finalPath);
  }
  await writeFile(`${outputDir}/zones.json`, JSON.stringify({
    generated_at: new Date().toISOString(),
    source_top: topPath,
    url: summary?.result?.images?.[0]?.url,
    request_id: summary?.request_id,
    path: finalPath
  }, null, 2));
  return { path: finalPath, request_id: summary?.request_id };
}

async function main() {
  const { flags } = parseArgs();
  const r = await annotateTopDown({
    topPath:       one(flags, "top"),
    outputDir:     one(flags, "output-dir"),
    objectClasses: one(flags, "object-classes")
  });
  console.log(`OK zones -> ${r.path}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => { console.error(e.message); process.exit(1); });
}
