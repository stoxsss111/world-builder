#!/usr/bin/env node
/**
 * Tripo P1 image-to-3d provider for world-builder.
 *
 * Sole 3D-asset provider. No fallback to Trellis 2 — Trellis 2 results are
 * noticeably worse in stylised cases, so we'd rather retry P1 with a better
 * reference plate than fall back to a model that hurts the scene.
 *
 * Endpoint: tripo3d/p1/image-to-3d
 * Cost: $0.40 untextured / $0.50 textured (default: textured)
 * Output: .glb file + (when textured) a separate pbr_model URL with PBR maps baked in
 *
 * The Tripo P1 API on fal:
 *   - image_url       (required)  URL of the reference image
 *   - texture         (bool=true) Generate textures? When true, output includes a pbr_model variant.
 *   - face_limit      (int)       Target face count for the generated mesh. Optional.
 *                                 world-builder clamps to [5_000, 15_000] (project sweet spot).
 *                                 Default in this wrapper: 10_000.
 *   - model_seed      (int)       Optional seed for geometry reproducibility.
 *
 * There is NO separate PBR flag — PBR maps are produced automatically when texture=true
 * and surface as `pbr_model` in the output. Use the pbr_model URL when you need the
 * PBR-textured variant; use the regular `model_mesh` URL for the simpler textured GLB.
 *
 * Usage:
 *   node .claude/scripts/asset-pipeline/tripo-p1.mjs \
 *     --image "<path-or-url>" \
 *     --output-dir worlds/<slug>/assets \
 *     --output-slug <object-id> \
 *     [--texture true|false] \
 *     [--face-limit <5000..15000>] \
 *     [--seed <int>]
 *
 * Returns JSON: { path, cost_usd, face_limit, textured, request_metadata, provider }
 */
import { pathToFileURL } from "node:url";
import { runFalWildcard } from "../fal/run-fal.mjs";
import { one, parseArgs, toModelInputUrl } from "./fal-queue.mjs";

// Switched from tripo3d/p1 → tripo3d/h3.1 on 2026-05-23. H3.1 gives cleaner topology
// on dense / clustered scenes (P1 tended to fuse adjacent objects).
// API contract (image_url / texture / face_limit / model_seed) is the same, output
// shape (model_mesh / model_urls / rendered_image) is the same — drop-in.
const ENDPOINT = "tripo3d/h3.1/image-to-3d";

// Polycount range — H3.1 handles up to 20k cleanly, sweet spot shifted up.
const FACE_MIN = 5_000;
const FACE_MAX = 20_000;
const FACE_DEFAULT = 12_000;

function parseBool(value, fallback) {
  if (value === undefined) return fallback;
  if (value === true || value === false) return value;
  return !["false", "0", "no", "off"].includes(String(value).toLowerCase());
}

function clampFaceLimit(n) {
  const v = Math.round(Number(n));
  if (!Number.isFinite(v)) return FACE_DEFAULT;
  return Math.max(FACE_MIN, Math.min(FACE_MAX, v));
}

export async function generateAssetWithTripoP1(options) {
  const {
    imageInput,                     // path or URL
    outputDir,
    outputSlug,
    texture = true,
    faceLimit = FACE_DEFAULT,
    seed
  } = options;

  if (!imageInput) throw new Error("imageInput is required.");
  if (!outputDir) throw new Error("outputDir is required.");

  const clampedFace = clampFaceLimit(faceLimit);
  const image_url = await toModelInputUrl(imageInput);

  const input = {
    image_url,
    texture,
    face_limit: clampedFace,
    ...(seed !== undefined ? { model_seed: Number(seed) } : {})
  };

  const result = await runFalWildcard({
    endpoint: ENDPOINT,
    input,
    outputDir,
    outputSlug: outputSlug || "tripo-p1-asset",
    kind: "world-builder-3d-h31",
    mode: "queue",
    downloadOutputs: true,
    userPrompt: options.userPrompt
  });

  // Cost: $0.50 textured (incl. PBR variant), $0.40 untextured
  const cost_usd = texture ? 0.50 : 0.40;

  return {
    ...result,
    cost_usd,
    face_limit: clampedFace,
    textured: texture,
    pbr_included: texture,        // pbr_model is auto-generated when texture=true
    provider: "tripo3d/h3.1"
  };
}

async function main() {
  const { flags } = parseArgs();
  const result = await generateAssetWithTripoP1({
    imageInput: one(flags, "image"),
    outputDir: one(flags, "output-dir"),
    outputSlug: one(flags, "output-slug") || one(flags, "slug"),
    texture: parseBool(one(flags, "texture"), true),
    faceLimit: one(flags, "face-limit") || FACE_DEFAULT,
    seed: one(flags, "seed"),
    userPrompt: one(flags, "user-prompt")
  });
  console.log(JSON.stringify(result, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
