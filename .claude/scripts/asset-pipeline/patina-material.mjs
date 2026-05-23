#!/usr/bin/env node
/**
 * PATINA PBR material generator.
 *
 * Endpoint: fal-ai/patina/material  (text-to-PBR-set)
 * Cost: ~$0.01 base + $0.02/MP + $0.01/MP per map = ~$0.06-0.10 for 1024px 5-map set
 * Output: { basecolor, normal, roughness, metalness, height } URLs
 *
 * Used by world-builder for PROCEDURAL surfaces (sand, water, grass, dirt)
 * — i.e. flat Blender primitives that get tiled PBR materials applied.
 * Not for objects (those come from Tripo P1, which embeds PBR in the GLB).
 *
 * Usage:
 *   node .claude/scripts/asset-pipeline/patina-material.mjs \
 *     --prompt "stylised cartoon warm sandy beach, Donkey Kong Bananza palette, saturated warm yellow, seamlessly tiling" \
 *     --output-dir worlds/<slug>/materials/sand \
 *     --output-slug sand \
 *     [--resolution 1024|2048|4096|8192] \
 *     [--seed <int>]
 *
 * Returns JSON: { paths: { basecolor, normal, roughness, metalness, height }, cost_usd, request_metadata }
 */
import { pathToFileURL } from "node:url";
import { runFalWildcard } from "../fal/run-fal.mjs";
import { one, parseArgs } from "./fal-queue.mjs";

const ENDPOINT = "fal-ai/patina/material";

// Cost model from fal.ai (2026-05):
//   $0.01 base + $0.02 / MP + $0.01 / MP per output map
//   PATINA emits 5 maps (basecolor, normal, roughness, metalness, height)
//   So total = 0.01 + (0.02 * MP) + (0.01 * MP * 5)  =  0.01 + 0.07 * MP
function estimateCost(resolution) {
  const px = Number(resolution) || 1024;
  const mp = (px * px) / 1_000_000;
  return Number((0.01 + 0.07 * mp).toFixed(3));
}

export async function generateMaterialWithPatina(options) {
  const {
    prompt,
    outputDir,
    outputSlug,
    resolution = 1024,
    seed
  } = options;

  if (!prompt) throw new Error("prompt is required.");
  if (!outputDir) throw new Error("outputDir is required.");

  const input = {
    prompt,
    resolution: Number(resolution),
    ...(seed !== undefined ? { seed: Number(seed) } : {})
  };

  const result = await runFalWildcard({
    endpoint: ENDPOINT,
    input,
    outputDir,
    outputSlug: outputSlug || "patina-material",
    kind: "world-builder-material",
    mode: "queue",
    downloadOutputs: true,
    userPrompt: prompt
  });

  // PATINA's response surfaces five image URLs — basecolor / normal / roughness / metalness / height.
  // The fal-queue downloader saves each as a labelled file; the caller can find them in
  // `result.output_files` and `result.request_metadata` under the slug.

  return {
    ...result,
    cost_usd: estimateCost(resolution),
    resolution,
    map_set: ["basecolor", "normal", "roughness", "metalness", "height"],
    provider: "fal-ai/patina/material"
  };
}

async function main() {
  const { flags } = parseArgs();
  const result = await generateMaterialWithPatina({
    prompt: one(flags, "prompt"),
    outputDir: one(flags, "output-dir"),
    outputSlug: one(flags, "output-slug") || one(flags, "slug"),
    resolution: Number(one(flags, "resolution") || 1024),
    seed: one(flags, "seed")
  });
  console.log(JSON.stringify(result, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
