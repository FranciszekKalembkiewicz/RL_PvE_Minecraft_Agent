#!/usr/bin/env bash
# Nocny pipeline: model RANGED (szkielet) + przygotowanie DUAL_MODEL
# Wymaga: serwer MC działa, gracz Franq__ online (AFK OK), conda env minecraft_rl

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/overnight_${STAMP}.log"
STATUS="$LOG_DIR/overnight_STATUS.txt"

exec > >(tee -a "$LOG") 2>&1

echo "=== OVERNIGHT DUAL-MODEL PIPELINE ==="
echo "Start: $(date)"
echo "ROOT: $ROOT"

write_status() {
  echo "$1" | tee "$STATUS"
}

# --- conda ---
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "$(conda info --base)/etc/profile.d/conda.sh"
else
  write_status "FAIL: nie znaleziono conda.sh"
  exit 1
fi

conda activate minecraft_rl
unset ARENA_MOCK

write_status "RUNNING: przygotowanie..."

# --- backup configów ---
BACKUP="$ROOT/configs/backups/overnight_${STAMP}"
mkdir -p "$BACKUP"
cp "$ROOT/configs/waves.yaml" "$BACKUP/waves.yaml"
cp "$ROOT/server/plugins/WaveArena/config.yml" "$BACKUP/plugin_config.yml"
echo "Backup configów: $BACKUP"

# --- melee model (już wytrenowany 500k) ---
MELEE_SRC="$ROOT/checkpoints/snapshots/ppo_wave_500000_steps.zip"
MELEE_DST="$ROOT/checkpoints/final_wave_melee.zip"
if [ ! -f "$MELEE_SRC" ]; then
  write_status "FAIL: brak $MELEE_SRC"
  exit 1
fi
cp "$MELEE_SRC" "$MELEE_DST"
echo "Melee model OK: $MELEE_DST"

# --- konfiguracja treningu RANGED (tylko SKELETON + assist) ---
python3 <<'PY'
from pathlib import Path
import re

root = Path(".")

# waves.yaml — tylko SKELETON
waves = (root / "configs/waves.yaml").read_text(encoding="utf-8")
waves = re.sub(
    r"  mob_types:\n(?:    - .+\n)+",
    "  mob_types:\n    - SKELETON\n",
    waves,
    count=1,
)
(root / "configs/waves.yaml").write_text(waves, encoding="utf-8")

# plugin config — mob-types + skeleton-combat ON
plugin = (root / "server/plugins/WaveArena/config.yml").read_text(encoding="utf-8")
plugin = re.sub(
    r"  face-target-each-step: false",
    "  face-target-each-step: true",
    plugin,
)
plugin = re.sub(
    r"  move-toward-target-on-forward: false",
    "  move-toward-target-on-forward: true",
    plugin,
)
plugin = re.sub(
    r"mob-types:\n(?:  - .+\n)+",
    "mob-types:\n  - SKELETON\n",
    plugin,
    count=1,
)
(root / "server/plugins/WaveArena/config.yml").write_text(plugin, encoding="utf-8")
print("Config: SKELETON only + skeleton-combat ON")
PY

echo ""
echo "============================================================"
echo " WAŻNE: zrestartuj serwer Minecraft LUB w grze:"
echo "   /wavearena reload"
echo "   /wavearena reset"
echo " Gracz Franq__ musi być ONLINE (może stać AFK)."
echo "============================================================"
echo ""

# --- czekaj na bridge (max ~30 min) ---
write_status "WAITING: czekam na bridge :5555 (serwer + gracz)..."
python3 <<'PY'
import socket, time, sys
host, port = "127.0.0.1", 5555
for i in range(60):
    try:
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        print(f"Bridge OK po {i * 30}s")
        sys.exit(0)
    except OSError:
        print(f"  [{i+1}/60] brak bridge — czekam 30s...")
        time.sleep(30)
print("TIMEOUT: bridge :5555 niedostępny po 30 min")
sys.exit(1)
PY

write_status "RUNNING: trening RANGED 80k (od 500k)..."

export TRAIN_RESUME="$ROOT/checkpoints/snapshots/ppo_wave_500000_steps.zip"
export TRAIN_MOB_TYPES=SKELETON
export TRAIN_TIMESTEPS=80000

python train.py

# --- zapis ranged ---
cp "$ROOT/checkpoints/final_wave.zip" "$ROOT/checkpoints/final_wave_ranged.zip"
echo "Ranged model: checkpoints/final_wave_ranged.zip"

# Przywróć config prezentacyjny (mixed moby; assist ZOSTAJE ON dla szkieletów w demo)
cp "$BACKUP/waves.yaml" "$ROOT/configs/waves.yaml"
python3 <<'PY'
from pathlib import Path
import re
plugin_path = Path("server/plugins/WaveArena/config.yml")
text = plugin_path.read_text(encoding="utf-8")
# assist ON na szkieletach — model ranged trenowany z assistem
text = re.sub(r"  face-target-each-step: false", "  face-target-each-step: true", text)
text = re.sub(r"  move-toward-target-on-forward: false", "  move-toward-target-on-forward: true", text)
text = re.sub(
    r"mob-types:\n(?:  - .+\n)+",
    "mob-types:\n  - ZOMBIE\n  - CREEPER\n  - SKELETON\n",
    text,
    count=1,
)
plugin_path.write_text(text, encoding="utf-8")
print("Config przywrócony: mixed moby, skeleton-combat ON (demo)")
PY

echo ""
echo "Po przebudzeniu: /wavearena reload + restart serwera (zalecane)"
echo ""

write_status "DONE $(date)
Melee:  checkpoints/final_wave_melee.zip
Ranged: checkpoints/final_wave_ranged.zip
Demo:   DUAL_MODEL=1 DEMO_SLEEP=0.03 python demo.py
Eval:   DUAL_MODEL=1 EVAL_EPISODES=20 python evaluate.py
Log:    $LOG"

echo "=== KONIEC $(date) ==="
