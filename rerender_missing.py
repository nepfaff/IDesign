#!/usr/bin/env python3
"""
Re-render IDesign scenes that have scene_graph.json and Assets but are missing render.png.

Usage:
    python rerender_missing.py --results_dir ~/efs/nicholas/scene-agent-eval-scenes/IDesign
"""

import argparse
import subprocess
import sys
from pathlib import Path

BLENDER_PATH = "/snap/bin/blender"  # Use snap blender


def run_blender(scene_dir: Path, script_dir: Path) -> bool:
    """Run Blender rendering for a scene."""
    blender_script = script_dir / "place_in_blender.py"
    if not blender_script.exists():
        print(f"  Error: place_in_blender.py not found at {blender_script}")
        return False

    print(f"  Running Blender rendering...")
    result = subprocess.run(
        [BLENDER_PATH, "--background", "--python", str(blender_script)],
        cwd=str(scene_dir),
        capture_output=True,
        text=True,
        timeout=1800,  # 30 minute timeout for complex scenes
    )

    if result.returncode != 0:
        print(f"  Blender failed: {result.stderr[-500:] if result.stderr else 'no stderr'}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Re-render IDesign scenes missing render.png")
    parser.add_argument("--results_dir", type=str, required=True, help="IDesign results directory")
    parser.add_argument("--dry_run", action="store_true", help="Just list scenes, don't render")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    script_dir = Path(__file__).parent.resolve()

    # Find scenes that need re-rendering
    to_render = []
    for scene_dir in sorted(results_dir.glob("scene_*")):
        has_graph = (scene_dir / "scene_graph.json").exists()
        has_assets = (scene_dir / "Assets").exists()
        has_render = (scene_dir / "render.png").exists()

        if has_graph and has_assets and not has_render:
            to_render.append(scene_dir)

    print(f"Found {len(to_render)} scenes needing re-render")

    if args.dry_run:
        for scene_dir in to_render:
            print(f"  {scene_dir.name}")
        return

    successful = 0
    failed = 0

    for i, scene_dir in enumerate(to_render):
        print(f"\n[{i+1}/{len(to_render)}] {scene_dir.name}")

        if run_blender(scene_dir, script_dir):
            if (scene_dir / "render.png").exists():
                print(f"  Success!")
                successful += 1
            else:
                print(f"  Failed: render.png not created")
                failed += 1
        else:
            failed += 1

    print(f"\n{'='*50}")
    print(f"Done! Successful: {successful}, Failed: {failed}")


if __name__ == "__main__":
    main()
