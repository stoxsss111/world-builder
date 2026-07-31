#!/usr/bin/env python3
"""
3ds Max World Builder Pipeline (Local Models Only, Zero External APIs)
Drives 3D scene arrangement in 3ds Max via 3ds Max MCP and simready-scene-arranger skill.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add 3dsmax-mcp src to path
MCP_SRC_PATH = r'C:\Users\sapfi\Desktop\VibeScripts\3dsmax-mcp\src'
if MCP_SRC_PATH not in sys.path and os.path.exists(MCP_SRC_PATH):
    sys.path.append(MCP_SRC_PATH)

try:
    from max_client import MaxClient
except ImportError:
    MaxClient = None


class MaxWorldBuilder:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path).resolve()
        if not self.config_path.exists():
            self.config = {
                "models_directory": r"C:\Users\sapfi\Desktop\models",
                "mcp_pipe_name": r"\\.\pipe\3dsmax-mcp",
                "skill_path": r"C:\Users\sapfi\.gemini\config\skills\simready-scene-arranger",
                "allow_external_apis": False
            }
        else:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

        if MaxClient is None:
            raise RuntimeError("MaxClient module not found. Check 3dsmax-mcp installation.")
            
        self.client = MaxClient(pipe_name=self.config.get("mcp_pipe_name", r"\\.\pipe\3dsmax-mcp"))

    def analyze_scene(self) -> dict:
        """Step 1: Structural Analysis & Dynamic Floor Height Calculation."""
        print("[Step 1] Analyzing 3ds Max scene structure & calculating floor elevation...")
        ms_script = """
        (
            local maxFloorZ = 0.0
            local foundFloor = false
            local objectCount = 0
            
            for o in objects where not o.isHidden do (
                local n = toLower o.name
                if (matchPattern n pattern:"*floor*") or (matchPattern n pattern:"*wall*") or (matchPattern n pattern:"*ceiling*") or (matchPattern n pattern:"*shelf*") do (
                    objectCount += 1
                    local bb = nodeGetBoundingBox o o.transform
                    if (matchPattern n pattern:"*floor*") do (
                        if not foundFloor or bb[2].z > maxFloorZ do (
                            maxFloorZ = bb[2].z
                            foundFloor = true
                        )
                    )
                )
            )
            (maxFloorZ as string) + "|" + (foundFloor as string) + "|" + (objectCount as string)
        )
        """
        res = self.client.send_command(command=ms_script, cmd_type="maxscript")
        res_str = res.get("result", "0.0|false|0")
        parts = res_str.split("|") if isinstance(res_str, str) else ["0.0", "false", "0"]
        
        return {
            "floor_z": float(parts[0]) if len(parts) > 0 else 0.0,
            "floor_found": parts[1] == "true" if len(parts) > 1 else False,
            "structural_objects_count": int(parts[2]) if len(parts) > 2 else 0
        }

    def import_local_models(self, limit: int = None) -> dict:
        """Step 2: Headless Native Model Import from Local Folder (No External APIs)."""
        models_dir = Path(self.config["models_directory"]).resolve()
        print(f"[Step 2] Importing local models from: {models_dir} (NO GENERATION APIs)...")
        
        if not models_dir.exists():
            raise FileNotFoundError(f"Local models folder does not exist: {models_dir}")

        zip_files = [str(p) for p in models_dir.glob("*.zip")]
        if limit is not None and limit > 0:
            zip_files = zip_files[:limit]

        if not zip_files:
            print("No .zip model archives found in directory.")
            return {"imported": 0, "total": 0}

        zip_args = ", ".join([f'@"{z}"' for z in zip_files])
        loader_path = os.path.join(self.config["skill_path"], "scripts", "native_model_loader.ms")

        ms_script = f"""
        (
            filein @"{loader_path}"
            local zips = #({zip_args})
            local successCount = 0
            for z in zips do (
                if (SRT_LoadModelNative z) do successCount += 1
            )
            (successCount as string) + "/" + (zips.count as string)
        )
        """
        res = self.client.send_command(command=ms_script, cmd_type="maxscript")
        
        return {
            "imported_result": res.get("result"),
            "count": len(zip_files)
        }

    def arrange_models(self, floor_z: float) -> dict:
        """Step 3: Arrange ONLY Newly Imported Models by Point Helper on Dynamic Floor Z (Inside Room Boundaries with Physical Mesh Spacing)."""
        print(f"[Step 3] Arranging ONLY imported model helpers inside Room Boundaries on Floor Z = {floor_z}...")
        arranger_path = os.path.join(self.config["skill_path"], "scripts", "arrange_scene_native.ms")

        ms_script = f"""
        (
            filein @"{arranger_path}"
            SRT_ArrangeSceneNative {floor_z}
        )
        """
        res = self.client.send_command(command=ms_script, cmd_type="maxscript")
        return {"arranged_count": res.get("result")}

    def check_collisions(self, fix: bool = True) -> dict:
        """Step 4: Collision Verification & Auto-Fix (Only Moves Imported Assets)."""
        print("[Step 4] Checking & fixing object collisions & wall overlaps...")
        collision_path = os.path.join(self.config["skill_path"], "scripts", "check_collisions.ms")

        ms_script = f"""
        (
            filein @"{collision_path}"
            SRT_CheckCollisions fixCollisions:{"true" if fix else "false"}
        )
        """
        res = self.client.send_command(command=ms_script, cmd_type="maxscript")
        return {"collisions": res.get("result", []), "fixed": fix}

    def build_world(self, limit: int = None, output_file: str = "build_report.json"):
        """Runs full end-to-end 3ds Max World Building Pipeline."""
        print("==================================================")
        print("  3ds Max World Builder (No APIs, Local Models)   ")
        print("==================================================")
        
        analysis = self.analyze_scene()
        floor_z = analysis["floor_z"]
        print(f"-> Calculated Floor Elevation: Z = {floor_z}")

        import_res = self.import_local_models(limit=limit)
        print(f"-> Models Import Result: {import_res.get('imported_result')}")

        arrange_res = self.arrange_models(floor_z)
        print(f"-> Arranged ONLY Imported Models Count: {arrange_res.get('arranged_count')}")

        collision_res = self.check_collisions(fix=True)
        print(f"-> Collision Status: {collision_res.get('collisions')}")

        report = {
            "status": "success",
            "analysis": analysis,
            "import": import_res,
            "arrange": arrange_res,
            "collisions": collision_res
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        print("==================================================")
        print(f"World Build Complete! Report saved to: {output_file}")
        print("==================================================")
        return report


def main():
    parser = argparse.ArgumentParser(description="3ds Max World Builder Pipeline")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of local models to import")
    parser.add_argument("--output", default="build_report.json", help="Path to output build report JSON")

    args = parser.parse_args()

    builder = MaxWorldBuilder(config_path=args.config)
    builder.build_world(limit=args.limit, output_file=args.output)


if __name__ == "__main__":
    main()
