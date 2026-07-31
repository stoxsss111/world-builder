# `3dsmax-world-builder`

A standalone 3ds Max pipeline sub-project adapted from `world-builder` for **3ds Max MCP**.

Unlike the original `world-builder` which generated assets via external paid APIs (Tripo P1, fal.ai, etc.), **`3dsmax-world-builder` operates 100% locally with ZERO third-party generation APIs**. It imports local models, calculates dynamic scene geometry, positions models via Point Helpers, and runs collision verification powered by the **`simready-scene-arranger`** skill.

---

## 🚀 Key Differences from Original `world-builder`

| Feature | Original `world-builder` | `3dsmax-world-builder` |
| :--- | :--- | :--- |
| **DCC Host** | Blender 5.1 | **3ds Max 2023+ (via MCP)** |
| **Asset Source** | Tripo P1 AI generation / fal.ai | **Local Model Archives (`C:\Users\sapfi\Desktop\models`)** |
| **External APIs** | ~$6-10 per world (fal / Tripo) | **$0.00 (Zero External APIs)** |
| **Import Pipeline** | `.glb` import via blender-mcp | **Viser Headless API (`native_model_loader.ms`)** |
| **Transform Rules** | Scales and places meshes | **Helper-Only (Scale 100% fixed, moves Point Helper)** |
| **Floor Surface** | Procedural terrain node | **Dynamic Surface Calculation from `Floor` geometry** |
| **Collisions** | Visual comparison loop | **Automated Mesh/AABB Collision Check (`check_collisions.ms`)** |

---

## 🛠️ Folder Structure

```
world-builder/3dsmax-world-builder/
├── config.json             # Pipe settings, local models path, skill script paths
├── pipeline.py             # Main CLI orchestrator (Steps 1-4)
├── README.md               # Documentation & setup guide
└── build_report.json       # Generated build logs and status reports
```

---

## ⚡ Quickstart

### 1. Requirements
- Running 3ds Max 2023+ with 3ds Max MCP named pipe (`\\.\pipe\3dsmax-mcp`).
- Installed `simready-scene-arranger` skill (`C:\Users\sapfi\.gemini\config\skills\simready-scene-arranger`).
- Local ZIP models in `C:\Users\sapfi\Desktop\models`.

### 2. Running the Pipeline
To run an automated build using local models:

```bash
python pipeline.py --limit 10 --output build_report.json
```

Or run all available local models:

```bash
python pipeline.py --output build_report.json
```

---

## 📑 Pipeline Workflow

1. **Step 1: Structural Analysis & Dynamic Floor Calculation:**
   Scans the 3ds Max scene for room architecture (`Floor`, `Wall`, `Ceiling`). Dynamically calculates floor surface elevation ($Z_{\text{max}}$). Keeps scene structure 100% immutable.
2. **Step 2: Headless Native Viser Import:**
   Imports model `.zip` archives headlessly via `native_model_loader.ms` and Viser C# core API (`Viser.dll`), avoiding UI popups.
3. **Step 3: Helper-Only Grid Placement:**
   Arranges models on calculated floor elevation by transforming top-level **Point Helpers** only (no scaling allowed).
4. **Step 4: Collision Verification & Auto-Fix:**
   Executes `check_collisions.ms` to verify geometry overlaps and auto-adjust Z positions.
