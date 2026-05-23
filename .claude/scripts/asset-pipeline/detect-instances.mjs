#!/usr/bin/env node
/**
 * Call fal-ai/florence-2-large/open-vocabulary-detection once per object class
 * on a top-down image. Each call returns N pixel bounding boxes — one per
 * detected instance. Output: per-class centroids in pixel coords, ready to be
 * back-projected to world XY by .claude/scripts/blender/place-from-detections.py.
 *
 * Usage:
 *   node .claude/scripts/asset-pipeline/detect-instances.mjs \
 *     --top worlds/<slug>/controls/top.png \
 *     --output worlds/<slug>/controls/detections.json \
 *     --classes "palm tree,stone arch,tiki hut,boulder,campfire,treasure chest,flower,shell,tiki torch,log stump"
 *
 * Cost: ~$0.003 per class on Florence-2 Large. 10-15 classes = <$0.05 total.
 */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { callFalQueue, one, parseArgs, requireEnv, toModelInputUrl } from "./fal-queue.mjs";

// moondream-3 returns multi-instance detections more reliably than florence-2 on dense top-down scenes.
// Output shape: { objects: [ { x_min, y_min, x_max, y_max } ] } in normalized [0,1] coords.
const ENDPOINT = "fal-ai/moondream3-preview/detect";

export async function detectInstances({ topPath, outputJson, classes }) {
  if (!topPath) throw new Error("topPath required");
  if (!outputJson) throw new Error("outputJson required");
  if (!classes?.length) throw new Error("classes (array of strings) required");

  await mkdir(path.dirname(outputJson), { recursive: true });
  const imageUrl = await toModelInputUrl(topPath);

  // Read image dims so we can convert normalized coords to pixels.
  const { default: imageSizeOf } = await import("image-size").catch(() => ({ default: null }));
  let img_w = 1024, img_h = 1024;
  if (imageSizeOf) {
    try { const { width, height } = imageSizeOf(topPath); img_w = width; img_h = height; } catch {}
  } else {
    // Fallback: spawn node -e to get dims via PNG header
    const buf = await readFile(topPath);
    if (buf[0] === 0x89 && buf[1] === 0x50) {
      img_w = buf.readUInt32BE(16);
      img_h = buf.readUInt32BE(20);
    }
  }

  const tasks = classes.map(async (cls) => {
    const t0 = Date.now();
    const result = await callFalQueue(ENDPOINT, {
      image_url: imageUrl,
      prompt: cls
    }, {
      metadataPath: outputJson.replace(/\.json$/i, `_${cls.replace(/\W+/g, "_")}_request.json`),
      metadata: { kind: "detection", provider: ENDPOINT, class: cls }
    });
    // moondream-3 returns normalized bboxes: [{x_min,y_min,x_max,y_max}, ...]
    const objs = result?.data?.objects ?? [];
    const bboxes = objs.map((o) => ({
      x: o.x_min * img_w,
      y: o.y_min * img_h,
      w: (o.x_max - o.x_min) * img_w,
      h: (o.y_max - o.y_min) * img_h,
      label: cls
    }));
    const ms = Date.now() - t0;
    return { class: cls, bboxes, ms };
  });

  const settled = await Promise.allSettled(tasks);
  const out = {
    generated_at: new Date().toISOString(),
    source_top: topPath,
    provider: ENDPOINT,
    classes: []
  };
  for (const r of settled) {
    if (r.status === "fulfilled") {
      const cls = r.value.class;
      const instances = r.value.bboxes.map((b, i) => ({
        index: i,
        x_px:  b.x,
        y_px:  b.y,
        w_px:  b.w,
        h_px:  b.h,
        cx_px: b.x + b.w / 2,
        cy_px: b.y + b.h / 2
      }));
      out.classes.push({ class: cls, count: instances.length, instances });
      console.log(`OK  ${cls.padEnd(22)}  ${instances.length} instances  (${r.value.ms} ms)`);
    } else {
      out.classes.push({ class: "?", error: String(r.reason?.message || r.reason) });
      console.log(`ERR ${r.reason?.message || r.reason}`);
    }
  }
  await writeFile(outputJson, JSON.stringify(out, null, 2));
  console.log(`\nwrote ${outputJson}`);
  return out;
}

async function main() {
  const { flags } = parseArgs();
  const classes = (one(flags, "classes") || "").split(",").map((s) => s.trim()).filter(Boolean);
  await detectInstances({
    topPath:    one(flags, "top"),
    outputJson: one(flags, "output"),
    classes
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => { console.error(e.message); process.exit(1); });
}
