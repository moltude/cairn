#!/usr/bin/env bash
set -euo pipefail

# Watch-mode "chaos monkey" demo for the hardest CalTopo → OnX migration flow.
# Runs the normal workflow (`cairn migrate onx`) but feeds a pre-recorded input script
# so you can watch without typing.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT_DIR="${1:-demo/bitterroots/onx_ready_chaos_watch}"

mkdir -p "$OUT_DIR"

echo "Output: $OUT_DIR"
echo "Replay script: demo/chaos_inputs/bitterroots_chaos_watch.txt"
echo

uv run cairn migrate onx "$ROOT/demo/bitterroots" \
  -o "$OUT_DIR" \
  --interactive < "$ROOT/demo/chaos_inputs/bitterroots_chaos_watch.txt"
