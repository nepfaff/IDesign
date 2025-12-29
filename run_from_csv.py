#!/usr/bin/env python3
"""
Run IDesign scene generation for all prompts in a CSV file.

Usage:
    python run_from_csv.py
    python run_from_csv.py --csv_file prompts.csv --results_dir ./scenes
    python run_from_csv.py --start_id 5 --end_id 10
    python run_from_csv.py --skip_retrieve --skip_render  # Scene graph only
    python run_from_csv.py --skip_existing               # Skip scenes with render.png
"""

import argparse
import csv
import os
import subprocess
import sys
import traceback
from pathlib import Path

from generate_scene import generate_scene

# Default paths
CSV_FILE = str(Path.home() / "SceneEval/input/annotations.csv")
RESULTS_DIR = "./data/sceneval_results"
BLENDER_PATH = "/home/ubuntu/blender-4.2.0-linux-x64/blender"
MAX_RETRIES = 10


def run_retrieve(scene_dir: Path, script_dir: Path) -> bool:
    """
    Run asset retrieval for a scene.

    Args:
        scene_dir: Directory containing scene_graph.json
        script_dir: Directory containing retrieve.py

    Returns:
        True if successful, False otherwise
    """
    retrieve_script = script_dir / "retrieve.py"
    if not retrieve_script.exists():
        print(f"Warning: retrieve.py not found at {retrieve_script}")
        return False

    print("  Running asset retrieval...")
    result = subprocess.run(
        [sys.executable, str(retrieve_script)],
        cwd=str(scene_dir),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  Asset retrieval failed: {result.stderr}")
        return False

    print("  Asset retrieval complete")
    return True


def run_blender(scene_dir: Path, script_dir: Path) -> bool:
    """
    Run Blender rendering for a scene.

    Args:
        scene_dir: Directory containing scene_graph.json and Assets/
        script_dir: Directory containing place_in_blender.py

    Returns:
        True if successful, False otherwise
    """
    blender_script = script_dir / "place_in_blender.py"
    if not blender_script.exists():
        print(f"Warning: place_in_blender.py not found at {blender_script}")
        return False

    if not Path(BLENDER_PATH).exists():
        print(f"Warning: Blender not found at {BLENDER_PATH}")
        return False

    print("  Running Blender rendering...")
    result = subprocess.run(
        [BLENDER_PATH, "--background", "--python", str(blender_script)],
        cwd=str(scene_dir),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  Blender rendering failed: {result.stderr}")
        return False

    print("  Blender rendering complete")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Run IDesign scene generation from CSV prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Process all prompts with defaults
  %(prog)s --csv_file my_prompts.csv          # Use custom CSV file
  %(prog)s --start_id 5 --end_id 10           # Process only IDs 5-10
  %(prog)s --auto                             # Use GPT-4 for room parameters
  %(prog)s --skip_retrieve --skip_render      # Generate scene graphs only
  %(prog)s --skip_existing                    # Skip scenes with existing render.png
        """
    )

    parser.add_argument(
        "--csv_file",
        type=str,
        default=CSV_FILE,
        help=f"Path to CSV file with prompts (default: {CSV_FILE})"
    )
    parser.add_argument(
        "--results_dir",
        type=str,
        default=RESULTS_DIR,
        help=f"Output directory for results (default: {RESULTS_DIR})"
    )
    parser.add_argument(
        "--start_id",
        type=int,
        default=None,
        help="Start from this ID (inclusive)"
    )
    parser.add_argument(
        "--end_id",
        type=int,
        default=None,
        help="End at this ID (inclusive)"
    )
    parser.add_argument(
        "--auto",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use GPT-4 to determine room parameters for each prompt (default: True)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress information"
    )
    parser.add_argument(
        "--skip_retrieve",
        action="store_true",
        help="Skip asset retrieval step"
    )
    parser.add_argument(
        "--skip_render",
        action="store_true",
        help="Skip Blender rendering step"
    )
    parser.add_argument(
        "--skip_existing",
        action="store_true",
        help="Skip scenes that already have a render.png"
    )

    args = parser.parse_args()

    # Get script directory for locating retrieve.py and place_in_blender.py
    script_dir = Path(__file__).parent.resolve()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'='*60}")
    print(f"IDesign Batch Scene Generator")
    print(f"{'='*60}")
    print(f"CSV file: {args.csv_file}")
    print(f"Results dir: {results_dir}")
    print(f"Auto mode: {args.auto}")
    print(f"Skip retrieve: {args.skip_retrieve}")
    print(f"Skip render: {args.skip_render}")
    print(f"Skip existing: {args.skip_existing}")
    print(f"{'='*60}\n")

    # Read prompts from CSV
    with open(args.csv_file, "r") as f:
        prompts = list(csv.DictReader(f))

    total = len(prompts)
    print(f"Loaded {total} prompts from CSV\n")

    successful = 0
    failed = 0
    skipped = 0

    for i, row in enumerate(prompts):
        prompt_id = int(row["ID"])

        # Filter by ID range
        if args.start_id is not None and prompt_id < args.start_id:
            skipped += 1
            continue
        if args.end_id is not None and prompt_id > args.end_id:
            skipped += 1
            continue

        description = row["Description"]
        scene_dir = results_dir / f"scene_{prompt_id:03d}"
        render_file = scene_dir / "render.png"

        # Skip if render already exists
        if args.skip_existing and render_file.exists():
            print(f"Skipping scene {prompt_id} (render.png exists)")
            skipped += 1
            continue

        scene_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"Scene {prompt_id} ({i+1}/{total}): {description[:50]}...")
        print(f"Output: {scene_dir}")
        print(f"{'='*60}\n")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Stage 1: Generate scene graph
                output_file = scene_dir / "scene_graph.json"
                print(f"[Stage 1/3] Generating scene graph... (attempt {attempt}/{MAX_RETRIES})")
                generate_scene(
                    prompt=description,
                    output_file=str(output_file),
                    auto_mode=args.auto,
                    verbose=args.verbose,
                )
                print(f"  Scene graph saved to: {output_file}")

                # Stage 2: Retrieve assets
                if not args.skip_retrieve:
                    print("\n[Stage 2/3] Retrieving 3D assets...")
                    if not run_retrieve(scene_dir, script_dir):
                        raise RuntimeError("Asset retrieval failed")
                else:
                    print("\n[Stage 2/3] Skipping asset retrieval")

                # Stage 3: Render in Blender
                if not args.skip_render:
                    print("\n[Stage 3/3] Rendering in Blender...")
                    if not run_blender(scene_dir, script_dir):
                        raise RuntimeError("Blender rendering failed")

                    # Verify render.png was created
                    if not render_file.exists():
                        raise RuntimeError(f"render.png not found after Blender execution")
                else:
                    print("\n[Stage 3/3] Skipping Blender rendering")

                print(f"\nScene {prompt_id} completed successfully on attempt {attempt}!")
                successful += 1
                break  # Success - exit retry loop

            except Exception as e:
                print(f"\nAttempt {attempt}/{MAX_RETRIES} failed for scene {prompt_id}: {e}")
                traceback.print_exc()
                if attempt == MAX_RETRIES:
                    print(f"Scene {prompt_id} failed after {MAX_RETRIES} attempts")
                    failed += 1
                else:
                    print("Retrying...")

    print(f"\n{'='*60}")
    print(f"Batch complete!")
    print(f"{'='*60}")
    print(f"Results saved to: {results_dir}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
