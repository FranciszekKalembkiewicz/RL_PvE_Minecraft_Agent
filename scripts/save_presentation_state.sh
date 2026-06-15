#!/usr/bin/env bash
# Zapisz stan prezentacyjny (modele + configi + raport).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/checkpoints/presentation_${STAMP}"
mkdir -p "$OUT"

cp "$ROOT/checkpoints/final_wave_melee.zip" "$OUT/"
cp "$ROOT/checkpoints/final_wave_ranged.zip" "$OUT/"
cp "$ROOT/configs/waves.yaml" "$OUT/"
cp "$ROOT/configs/demo_wave_sequence.yaml" "$OUT/"
cp "$ROOT/server/plugins/WaveArena/config.yml" "$OUT/plugin_config.yml"

if [ -d "$ROOT/reports/dual_validation_latest" ]; then
  cp -R "$ROOT/reports/dual_validation_latest" "$OUT/validation_report"
fi

cat >"$OUT/README.txt" <<EOF
Snapshot prezentacji — $STAMP

Modele:
  final_wave_melee.zip  — zombie/creeper (czyste RL)
  final_wave_ranged.zip — szkielet (RL + skill celowania)

Demo:
  DUAL_MODEL=1 DEMO_SLEEP=0.03 python demo.py

Kolejność fal: configs/demo_wave_sequence.yaml
Plugin: plugin_config.yml (skopiuj do server/plugins/WaveArena/config.yml)
EOF

ln -sfn "$OUT" "$ROOT/checkpoints/presentation_latest"
echo "Zapisano: $OUT"
echo "Link:     checkpoints/presentation_latest"
