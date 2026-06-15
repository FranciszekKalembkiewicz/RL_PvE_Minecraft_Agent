#!/usr/bin/env python3
"""Ustaw wave-mob-sequence w pluginie i przeładuj config.

Użycie:
  python scripts/apply_wave_sequence.py SKELETON,CREEPER,ZOMBIE,...
  DEMO_WAVE_MOBS=SKELETON,CREEPER python scripts/apply_wave_sequence.py
  python scripts/apply_wave_sequence.py --preset configs/demo_wave_sequence.yaml
  python scripts/apply_wave_sequence.py --clear   # wróć do losowych mobów
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_CFG = ROOT / "server/plugins/WaveArena/config.yml"


def _write_sequence(mobs: list[str]) -> None:
    text = PLUGIN_CFG.read_text(encoding="utf-8")
    block = "wave-mob-sequence: []\n"
    if mobs:
        lines = ["wave-mob-sequence:"]
        for i, m in enumerate(mobs, start=1):
            lines.append(f"  - {m.upper()}  # fala {i}")
        block = "\n".join(lines) + "\n"

    if re.search(r"^wave-mob-sequence:\n", text, flags=re.M):
        text = re.sub(
            r"^wave-mob-sequence:(?:\n(?:  - .+\n?)+|\s*\[\]\n?)",
            block,
            text,
            count=1,
            flags=re.M,
        )
    else:
        text = text.replace(
            "mob-types:\n",
            block + "\nmob-types:\n",
            1,
        )
    PLUGIN_CFG.write_text(text, encoding="utf-8")


def _reload() -> dict:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from env.bridge_client import BridgeClient

    c = BridgeClient()
    c.connect()
    try:
        return c.reload_config()
    except OSError:
        return c.send_command({"cmd": "reload"})
    finally:
        c.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mobs", nargs="?", help="CSV: SKELETON,CREEPER,ZOMBIE")
    p.add_argument("--preset", type=Path, help="YAML z wave_mob_sequence")
    p.add_argument("--clear", action="store_true", help="Wyczyść sekwencję (losowe)")
    args = p.parse_args()

    mobs: list[str] = []
    if args.clear:
        mobs = []
    elif args.preset:
        data = yaml.safe_load(args.preset.read_text(encoding="utf-8"))
        mobs = [str(x).upper() for x in data.get("wave_mob_sequence", [])]
    else:
        raw = args.mobs or os.environ.get("DEMO_WAVE_MOBS", "").strip()
        if not raw:
            print("Podaj moby CSV, DEMO_WAVE_MOBS lub --preset")
            return 1
        mobs = [t.strip().upper() for t in raw.split(",") if t.strip()]

    _write_sequence(mobs)
    r = _reload()
    seq = r.get("wave_mob_sequence", mobs)
    print("wave-mob-sequence:", seq if seq else "(losowe z mob-types)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
