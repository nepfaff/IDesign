#!/usr/bin/env python3
"""
Run IDesign scene generation with multiple parallel workers.

Usage:
    python run_multiworker.py                          # 3 workers (default)
    python run_multiworker.py --num_workers 2          # 2 workers (safer for GPU memory)
    python run_multiworker.py --num_workers 4 --skip_existing
    python run_multiworker.py --start_id 100 --end_id 150 --num_workers 2
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Default paths
SCRIPT_DIR = Path(__file__).parent.resolve()
CSV_FILE = str(Path.home() / "SceneEval/input/annotations.csv")
RESULTS_DIR = str(Path.home() / "efs/nicholas/scene-agent-eval-scenes/IDesign")
LOG_DIR = SCRIPT_DIR / "logs"


def get_scene_ids(csv_file: str, start_id: int = None, end_id: int = None) -> list:
    """Get list of scene IDs from CSV file."""
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        ids = [int(row["ID"]) for row in reader]

    if start_id is not None:
        ids = [i for i in ids if i >= start_id]
    if end_id is not None:
        ids = [i for i in ids if i <= end_id]

    return sorted(ids)


def filter_incomplete_scenes(scene_ids: list, results_dir: str) -> list:
    """Filter to only scenes that don't have render.png."""
    results_path = Path(results_dir)
    incomplete = []
    for scene_id in scene_ids:
        render_file = results_path / f"scene_{scene_id:03d}" / "render.png"
        if not render_file.exists():
            incomplete.append(scene_id)
    return incomplete


def divide_work(scene_ids: list, num_workers: int) -> list:
    """Divide scene IDs among workers as contiguous ranges."""
    n = len(scene_ids)
    chunk_size = n // num_workers
    remainder = n % num_workers

    chunks = []
    start = 0
    for i in range(num_workers):
        # Distribute remainder across first few workers
        size = chunk_size + (1 if i < remainder else 0)
        chunks.append(scene_ids[start:start + size])
        start += size

    return chunks


def main():
    parser = argparse.ArgumentParser(
        description="Run IDesign with multiple parallel workers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--num_workers", "-n",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3, recommended: 2-4 to avoid CUDA OOM)"
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
        "--skip_existing",
        action="store_true",
        help="Skip scenes that already have render.png"
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
        "--timeout",
        type=int,
        default=3600,
        help="Timeout per scene attempt in seconds (default: 3600)"
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Show what would be run without executing"
    )

    args = parser.parse_args()

    # Get scene IDs to process
    all_scene_ids = get_scene_ids(args.csv_file, args.start_id, args.end_id)

    # Filter to only incomplete scenes if --skip_existing
    if args.skip_existing:
        scene_ids = filter_incomplete_scenes(all_scene_ids, args.results_dir)
        print(f"Found {len(scene_ids)} incomplete scenes out of {len(all_scene_ids)} total")
    else:
        scene_ids = all_scene_ids

    if not scene_ids:
        print("No scenes to process!")
        return

    # Divide work among workers
    work_chunks = divide_work(scene_ids, args.num_workers)

    # Create log directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_log_dir = LOG_DIR / f"run_{timestamp}_{os.getpid()}"
    run_log_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("IDesign Multi-Worker Runner")
    print("=" * 60)
    print(f"Total scenes: {len(scene_ids)}")
    print(f"Workers: {args.num_workers}")
    print(f"Results dir: {args.results_dir}")
    print(f"Log dir: {run_log_dir}")
    print(f"Skip existing: {args.skip_existing}")
    print(f"Timeout: {args.timeout}s")
    print("=" * 60)

    for i, chunk in enumerate(work_chunks):
        if chunk:
            print(f"Worker {i}: {len(chunk)} scenes (IDs: {chunk[0]}-{chunk[-1]})")
        else:
            print(f"Worker {i}: 0 scenes")

    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN] Would execute the following commands:\n")
        for i, chunk in enumerate(work_chunks):
            if not chunk:
                continue
            cmd = [
                sys.executable, str(SCRIPT_DIR / "run_from_csv.py"),
                "--csv_file", args.csv_file,
                "--results_dir", args.results_dir,
                "--start_id", str(min(chunk)),
                "--end_id", str(max(chunk)),
                "--timeout", str(args.timeout),
            ]
            if args.skip_existing:
                cmd.append("--skip_existing")
            if args.skip_retrieve:
                cmd.append("--skip_retrieve")
            if args.skip_render:
                cmd.append("--skip_render")
            print(f"Worker {i}: {' '.join(cmd)}")
        return

    # Launch workers
    processes = []
    log_files = []

    print(f"\nLaunching {args.num_workers} workers...\n")

    for i, chunk in enumerate(work_chunks):
        if not chunk:
            continue

        log_file = run_log_dir / f"worker_{i}.log"
        log_handle = open(log_file, "w")
        log_files.append(log_handle)

        cmd = [
            sys.executable, str(SCRIPT_DIR / "run_from_csv.py"),
            "--csv_file", args.csv_file,
            "--results_dir", args.results_dir,
            "--start_id", str(min(chunk)),
            "--end_id", str(max(chunk)),
            "--timeout", str(args.timeout),
        ]
        if args.skip_existing:
            cmd.append("--skip_existing")
        if args.skip_retrieve:
            cmd.append("--skip_retrieve")
        if args.skip_render:
            cmd.append("--skip_render")

        print(f"Starting worker {i}: scenes {min(chunk)}-{max(chunk)} ({len(chunk)} scenes)")
        print(f"  Log: {log_file}")

        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(SCRIPT_DIR),
        )
        processes.append((i, proc, chunk))

    print(f"\nAll {len(processes)} workers started. Monitoring progress...\n")
    print("Press Ctrl+C to cancel all workers.\n")

    # Monitor progress
    try:
        start_time = time.time()
        while True:
            all_done = True
            status_parts = []

            for worker_id, proc, chunk in processes:
                ret = proc.poll()
                if ret is None:
                    all_done = False
                    status_parts.append(f"W{worker_id}:running")
                elif ret == 0:
                    status_parts.append(f"W{worker_id}:done")
                else:
                    status_parts.append(f"W{worker_id}:failed({ret})")

            elapsed = time.time() - start_time
            elapsed_str = f"{int(elapsed // 3600)}h{int((elapsed % 3600) // 60)}m"
            print(f"\r[{elapsed_str}] {' | '.join(status_parts)}", end="", flush=True)

            if all_done:
                break

            time.sleep(10)

        print("\n")

    except KeyboardInterrupt:
        print("\n\nInterrupted! Terminating workers...")
        for worker_id, proc, chunk in processes:
            proc.terminate()
        for worker_id, proc, chunk in processes:
            proc.wait()
        print("All workers terminated.")
        return

    finally:
        for log_handle in log_files:
            log_handle.close()

    # Summary
    print("=" * 60)
    print("Run Complete!")
    print("=" * 60)

    for worker_id, proc, chunk in processes:
        ret = proc.returncode
        status = "SUCCESS" if ret == 0 else f"FAILED (exit code {ret})"
        print(f"Worker {worker_id}: {status} ({len(chunk)} scenes)")

    print(f"\nLogs saved to: {run_log_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
