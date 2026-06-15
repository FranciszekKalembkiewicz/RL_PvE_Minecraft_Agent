#!/usr/bin/env bash
# Demo dual-model — preset fal lub losowe moby.
#   ./scripts/run_demo.sh preset
#   ./scripts/run_demo.sh random
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-preset}"
PYTHON="${MINECRAFT_RL_PYTHON:-/opt/anaconda3/envs/minecraft_rl/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3)"
fi

cd "$ROOT"
unset ARENA_MOCK
export DUAL_MODEL=1
export DEMO_SLEEP="${DEMO_SLEEP:-0.03}"
LOG="$ROOT/logs/demo_last.log"

{
  echo "=== demo $MODE $(date) ==="
  if [ "$MODE" = "random" ]; then
    export DEMO_RANDOM_MOBS=1
    "$PYTHON" demo.py
  else
    unset DEMO_RANDOM_MOBS
    "$PYTHON" demo.py
  fi
} 2>&1 | tee "$LOG"
