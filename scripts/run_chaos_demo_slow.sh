#!/usr/bin/env bash
set -euo pipefail

# Slow "watch-mode" replay for the chaos-monkey demo.
#
# Usage:
#   ./scripts/run_chaos_demo_slow.sh [OUT_DIR] [DELAY_SECONDS]
#
# Example:
#   ./scripts/run_chaos_demo_slow.sh demo/bitterroots/onx_ready_chaos_watch 0.25
#
# Notes:
# - This still runs the normal interactive CLI, but feeds answers from a file.
# - DELAY_SECONDS throttles each line of input so you can watch the prompts.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT_DIR="${1:-demo/bitterroots/onx_ready_chaos_watch}"
DELAY_SECONDS="${2:-0.20}"

INPUT_FILE="${INPUT_FILE:-$ROOT/demo/chaos_inputs/bitterroots_chaos_watch.txt}"

mkdir -p "$OUT_DIR"

echo "Output: $OUT_DIR"
echo "Replay script: $INPUT_FILE"
echo "Delay per input line: ${DELAY_SECONDS}s"
echo

(
  # Feed inputs slowly, preserving blank lines.
  while IFS= read -r line || [[ -n "${line:-}" ]]; do
    printf '%s\n' "$line"
    sleep "$DELAY_SECONDS"
  done < "$INPUT_FILE"
) | uv run cairn migrate onx "$ROOT/demo/bitterroots" \
  -o "$OUT_DIR" \
  --interactive
