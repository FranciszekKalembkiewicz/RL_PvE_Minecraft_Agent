#!/usr/bin/env bash
# Trening modelu RANGED (szkielet) — czyste RL, bez skeleton-assist.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="$ROOT/logs/ranged_train_$(date +%Y%m%d_%H%M%S).log"
mkdir -p checkpoints/backups logs

echo "=== RANGED TRAIN (SKELETON, no assist) ===" | tee "$LOG"

# backup melee — nie nadpisujemy
cp checkpoints/final_wave_melee.zip "checkpoints/backups/melee_$(date +%Y%m%d_%H%M%S).zip"

# config: tylko SKELETON, assist OFF
python3 <<'PY'
from pathlib import Path
import re
root = Path(".")
waves = (root / "configs/waves.yaml").read_text(encoding="utf-8")
waves = re.sub(
    r"  mob_types:\n(?:    - .+\n)+",
    "  mob_types:\n    - SKELETON\n",
    waves,
    count=1,
)
(root / "configs/waves.yaml").write_text(waves, encoding="utf-8")
plugin = (root / "server/plugins/WaveArena/config.yml").read_text(encoding="utf-8")
plugin = re.sub(r"  face-target-each-step: false", "  face-target-each-step: true", plugin)
plugin = re.sub(r"  move-toward-target-on-forward: true", "  move-toward-target-on-forward: false", plugin)
plugin = re.sub(
    r"mob-types:\n(?:  - .+\n)+",
    "mob-types:\n  - SKELETON\n",
    plugin,
    count=1,
)
(root / "server/plugins/WaveArena/config.yml").write_text(plugin, encoding="utf-8")
print("Config: SKELETON only, assist OFF")
PY

# reload plugin
/opt/anaconda3/envs/minecraft_rl/bin/python -c "
from env.bridge_client import BridgeClient
c=BridgeClient(); c.connect()
r=c.reload_config()
print('reload', r.get('skeleton_face_target'), r.get('skeleton_move_toward'))
c.close()
" | tee -a "$LOG"

export TRAIN_RESUME="$ROOT/checkpoints/final_wave_ranged.zip"
export TRAIN_SAVE_AS=final_wave_ranged
export TRAIN_MOB_TYPES=SKELETON
export TRAIN_TIMESTEPS="${TRAIN_TIMESTEPS:-30000}"
export PPO_LR="${PPO_LR:-0.00008}"
export PPO_ENT_COEF="${PPO_ENT_COEF:-0.025}"

echo "Trening: resume=$TRAIN_RESUME save=$TRAIN_SAVE_AS steps=$TRAIN_TIMESTEPS" | tee -a "$LOG"
unset ARENA_MOCK
/opt/anaconda3/envs/minecraft_rl/bin/python train.py 2>&1 | tee -a "$LOG"

# przywróć pulę mobów pod dual demo
python3 <<'PY'
from pathlib import Path
import re
root = Path(".")
waves = (root / "configs/waves.yaml").read_text(encoding="utf-8")
waves = re.sub(
    r"  mob_types:\n(?:    - .+\n)+",
    "  mob_types:\n    - ZOMBIE\n    - CREEPER\n    - SKELETON\n",
    waves,
    count=1,
)
(root / "configs/waves.yaml").write_text(waves, encoding="utf-8")
plugin = (root / "server/plugins/WaveArena/config.yml").read_text(encoding="utf-8")
plugin = re.sub(
    r"mob-types:\n(?:  - .+\n)+",
    "mob-types:\n  - ZOMBIE\n  - CREEPER\n  - SKELETON\n",
    plugin,
    count=1,
)
(root / "server/plugins/WaveArena/config.yml").write_text(plugin, encoding="utf-8")
print("Config: ZOMBIE+CREEPER+SKELETON restored")
PY

/opt/anaconda3/envs/minecraft_rl/bin/python -c "
from env.bridge_client import BridgeClient
c=BridgeClient(); c.connect(); c.reload_config(); c.close()
print('reload OK')
" | tee -a "$LOG"

echo "DONE ranged: checkpoints/final_wave_ranged.zip" | tee -a "$LOG"
