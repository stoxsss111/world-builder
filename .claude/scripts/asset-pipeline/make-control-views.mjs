#!/usr/bin/env node
/**
 * Generate 3 nano-banana "control views" from a single reference image.
 * These are the ground truth that every iteration of place-and-iterate compares against.
 *
 *   top.png  — strictly top-down orthographic of the same scene
 *   fl45.png — same scene viewed from front-left at ~40° elevation
 *   fr45.png — same scene viewed from front-right at ~40° elevation
 *
 * All three contain the full bounding box of the location. No new objects.
 *
 * Usage:
 *   node .claude/scripts/asset-pipeline/make-control-views.mjs \
 *     --reference worlds/<slug>/source/reference.png \
 *     --output-dir worlds/<slug>/controls \
 *     --style-anchor "Banjo-Kazooie Treasure Trove Cove cartoon stylisation"
 *
 * Writes:
 *   worlds/<slug>/controls/{top,fl45,fr45}.png  — downloaded files
 *   worlds/<slug>/controls/index.json           — request ids + fal CDN URLs
 */
import { mkdir, writeFile, readdir, rename } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { runNanoBananaEdit } from "./nano-banana-edit.mjs";
import { one, parseArgs } from "./fal-queue.mjs";

const VIEW_PROMPTS = {
  top:  "Recompose this exact scene as a STRICTLY TOP-DOWN ORTHOGRAPHIC view from directly above, no perspective distortion, all elements of the original visible from above, same %ANCHOR%, same vibrant palette, same level of stylisation. Keep every object the same — do NOT add, remove, or invent objects. The full bounding box of the scene must be in frame. Plain background outside the island.",
  fl45: "Recompose this exact scene as if photographed from the FRONT-LEFT at ~40 degrees elevation: camera in front-left of the location looking back-right and slightly down. Same %ANCHOR%, same vibrant palette, same level of stylisation. Keep every object the same — do NOT add, remove, or invent objects. The full bounding box of the location must be in frame. Plain background outside the island.",
  fr45: "Recompose this exact scene as if photographed from the FRONT-RIGHT at ~40 degrees elevation: camera in front-right of the location looking back-left and slightly down. Same %ANCHOR%, same vibrant palette, same level of stylisation. Keep every object the same — do NOT add, remove, or invent objects. The full bounding box of the location must be in frame. Plain background outside the island."
};

export async function makeControlViews({ referencePath, outputDir, styleAnchor }) {
  if (!referencePath) throw new Error("referencePath is required.");
  if (!outputDir) throw new Error("outputDir is required.");
  await mkdir(outputDir, { recursive: true });
  const anchor = styleAnchor || "the original cartoon stylisation";

  const views = ["top", "fl45", "fr45"];
  const tasks = views.map(async (view) => {
    const viewDir = `${outputDir}/_${view}`;
    await mkdir(viewDir, { recursive: true });
    const prompt = VIEW_PROMPTS[view].replace(/%ANCHOR%/g, anchor);
    const t0 = Date.now();
    const summary = await runNanoBananaEdit({
      prompt,
      images: [referencePath],
      outputDir: viewDir,
      numImages: 1,
      aspectRatio: "1:1",
      resolution: "1K",
      outputFormat: "png",
      safetyTolerance: "4"
    });
    const url = summary?.result?.images?.[0]?.url;
    // Find the actual downloaded PNG (random hash filename) and rename it to <view>.png
    const files = (await readdir(viewDir)).filter((f) => f.endsWith(".png"));
    let renamed = null;
    if (files.length > 0) {
      const finalPath = `${outputDir}/${view}.png`;
      await rename(`${viewDir}/${files[0]}`, finalPath);
      renamed = finalPath;
    }
    return { view, url, path: renamed, request_id: summary?.request_id, ms: Date.now() - t0 };
  });

  const results = await Promise.allSettled(tasks);
  const index = { generated_at: new Date().toISOString(), reference: referencePath, items: [] };
  for (const r of results) {
    if (r.status === "fulfilled") {
      index.items.push({ status: "ok", ...r.value });
      console.log(`OK  ${r.value.view.padEnd(5)}  ${r.value.path}  (${r.value.ms} ms)`);
    } else {
      index.items.push({ status: "error", error: String(r.reason?.message || r.reason) });
      console.log(`ERR ${r.reason?.message || r.reason}`);
    }
  }
  await writeFile(`${outputDir}/index.json`, JSON.stringify(index, null, 2));
  return index;
}

async function main() {
  const { flags } = parseArgs();
  await makeControlViews({
    referencePath: one(flags, "reference"),
    outputDir:     one(flags, "output-dir"),
    styleAnchor:   one(flags, "style-anchor")
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => { console.error(e.message); process.exit(1); });
}
