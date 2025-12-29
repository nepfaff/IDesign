#!/bin/bash
# Run IDesign scene generation in parallel by splitting scene ranges across workers
#
# Usage: ./scripts/run_parallel.sh <start_id> <end_id> <num_workers> [extra_args...]
#
# Examples:
#   # Generate scenes 1-100 with 4 workers
#   ./scripts/run_parallel.sh 1 100 4
#
#   # Generate scenes 1-50 with 2 workers, skipping render
#   ./scripts/run_parallel.sh 1 50 2 --skip_render
#
#   # Full example with custom CSV
#   ./scripts/run_parallel.sh 1 100 4 --csv_file /path/to/prompts.csv --skip_retrieve
#
# Output:
#   - Each scene creates its own output directory in data/sceneval_results/
#   - Worker stdout/stderr is captured in logs/worker_*.log

set -e

# Parse arguments
START_ID=${1:-1}
END_ID=${2:-100}
NUM_WORKERS=${3:-4}

if [ $# -lt 3 ]; then
    echo "Usage: $0 <start_id> <end_id> <num_workers> [extra_args...]"
    echo "Example: $0 1 100 4 --skip_render"
    exit 1
fi

shift 3  # Remove first three args, rest are passed to run_from_csv.py

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Create unique run ID and log directory
RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
LOG_DIR="logs/run_${RUN_ID}"
mkdir -p "$LOG_DIR"

# Calculate scenes per worker
TOTAL_SCENES=$((END_ID - START_ID + 1))
SCENES_PER_WORKER=$(( (TOTAL_SCENES + NUM_WORKERS - 1) / NUM_WORKERS ))  # Ceiling division
PIDS=()

# Cleanup function to kill all workers
cleanup() {
    echo ""
    echo "Caught signal, terminating workers..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
        fi
    done
    # Wait briefly for graceful shutdown, then force kill
    sleep 2
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
    done
    echo "Workers terminated."
    exit 130
}

# Trap signals to ensure cleanup
trap cleanup INT TERM EXIT

echo "========================================"
echo "IDesign Parallel Scene Generation"
echo "========================================"
echo "Run ID: $RUN_ID"
echo "Scene range: $START_ID - $END_ID"
echo "Total scenes: $TOTAL_SCENES"
echo "Workers: $NUM_WORKERS"
echo "Scenes per worker: ~$SCENES_PER_WORKER"
echo "Extra args: $@"
echo "Log directory: $LOG_DIR"
echo "========================================"
echo ""

# Launch workers
for ((i=0; i<NUM_WORKERS; i++)); do
    WORKER_START=$((START_ID + i * SCENES_PER_WORKER))
    WORKER_END=$((WORKER_START + SCENES_PER_WORKER - 1))

    # Last worker gets remainder
    if [ $i -eq $((NUM_WORKERS - 1)) ]; then
        WORKER_END=$END_ID
    fi

    # Skip if this worker's range is beyond end
    if [ $WORKER_START -gt $END_ID ]; then
        continue
    fi

    # Cap worker end at END_ID
    if [ $WORKER_END -gt $END_ID ]; then
        WORKER_END=$END_ID
    fi

    echo "Starting worker $i: scenes [$WORKER_START - $WORKER_END]"

    python run_from_csv.py \
        --start_id "$WORKER_START" \
        --end_id "$WORKER_END" \
        "$@" \
        > "${LOG_DIR}/worker_${i}.log" 2>&1 &

    PIDS+=($!)
done

echo ""
echo "All workers launched. PIDs: ${PIDS[*]}"
echo "Logs: ${LOG_DIR}/worker_*.log"
echo ""
echo "Monitor with: tail -f ${LOG_DIR}/worker_*.log"
echo "Waiting for completion..."
echo ""

# Wait for all workers and track failures
FAILED=0
FAILED_WORKERS=()

for i in "${!PIDS[@]}"; do
    PID=${PIDS[$i]}
    if ! wait $PID; then
        echo "Worker $i (PID $PID) FAILED"
        FAILED=1
        FAILED_WORKERS+=($i)
    else
        echo "Worker $i (PID $PID) completed"
    fi
done

echo ""
echo "========================================"

# Disable EXIT trap for normal completion
trap - EXIT

if [ $FAILED -eq 1 ]; then
    echo "SOME WORKERS FAILED: ${FAILED_WORKERS[*]}"
    echo "Check ${LOG_DIR}/worker_*.log for details"
    exit 1
else
    echo "ALL WORKERS COMPLETED SUCCESSFULLY"
fi
echo "Logs: ${LOG_DIR}/"
echo "========================================"
