"""Jedno epizod na żywo — pokaz dla prowadzącego (model już wytrenowany, bez uczenia).

Użycie:
  unset ARENA_MOCK
  python demo.py

Dwa modele (melee + szkielet):
  DUAL_MODEL=1 DEMO_SLEEP=0.03 python demo.py

Opcjonalnie wolniej (łatwiej oglądać w grze):
  DEMO_SLEEP=0.05 python demo.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from stable_baselines3 import PPO

from env.arena_mc_env import ArenaMcEnv
from env.dual_policy import DualModelPolicy, use_dual_models

ROOT = Path(__file__).resolve().parent

MODEL_PATH = Path("checkpoints/final_wave.zip")
FALLBACK = Path("checkpoints/best/best_model.zip")
SLEEP = float(os.environ.get("DEMO_SLEEP", "0.0"))


def _resolve_model() -> Path:
    env_path = os.environ.get("EVAL_MODEL", "").strip()
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"EVAL_MODEL nie istnieje: {p}")
    if MODEL_PATH.exists():
        return MODEL_PATH
    if FALLBACK.exists():
        return FALLBACK
    raise FileNotFoundError(
        f"Brak modelu: {MODEL_PATH} ani {FALLBACK}. "
        "Ustaw EVAL_MODEL=checkpoints/snapshots/ppo_wave_500000_steps.zip"
    )


def _apply_demo_wave_sequence() -> list[str] | None:
    """Ustaw kolejność mobów na falach z DEMO_WAVE_MOBS lub presetu."""
    if os.environ.get("ARENA_MOCK", "0") == "1":
        return None
    script = ROOT / "scripts/apply_wave_sequence.py"
    if not script.exists():
        return None
    preset = os.environ.get("DEMO_WAVE_PRESET", "").strip()
    raw = os.environ.get("DEMO_WAVE_MOBS", "").strip()
    cmd = [sys.executable, str(script)]
    if preset:
        cmd += ["--preset", preset]
    elif raw:
        cmd += [raw]
    elif os.environ.get("DEMO_RANDOM_MOBS", "0") == "1":
        cmd += ["--clear"]
        subprocess.run(cmd, cwd=ROOT, check=False)
        return None
    else:
        default = ROOT / "configs/demo_wave_sequence.yaml"
        if not default.exists():
            return None
        cmd += ["--preset", str(default)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    # parse printed sequence from preset file for display
    import yaml

    if preset:
        data = yaml.safe_load(Path(preset).read_text(encoding="utf-8"))
    elif raw:
        return [t.strip().upper() for t in raw.split(",") if t.strip()]
    else:
        data = yaml.safe_load((ROOT / "configs/demo_wave_sequence.yaml").read_text())
    return [str(x).upper() for x in data.get("wave_mob_sequence", [])]


def main() -> int:
    mock = os.environ.get("ARENA_MOCK", "0") == "1"
    dual = use_dual_models()

    if dual:
        policy = DualModelPolicy()
        print(
            f"Demo 1 epizod | DUAL_MODEL=1\n"
            f"  melee:  {policy.melee_path}\n"
            f"  ranged: {policy.ranged_path}\n"
            f"  mock={mock}\n"
        )
        if not mock:
            print(
                "  UWAGA: na falach SKELETON plugin musi mieć skeleton-combat ON\n"
                "  (face-target + move-toward). Po zmianie config.yml: /wavearena reload\n"
            )
    else:
        try:
            path = _resolve_model()
        except FileNotFoundError as e:
            print(e)
            return 1
        policy = PPO.load(str(path))
        print(f"Demo 1 epizod | model={path} | mock={mock}")

    print("Patrz na gracza Franq__ w Minecraft — agent sterowany siecią PPO.\n")

    seq = _apply_demo_wave_sequence()
    if seq:
        print("  Kolejność fal (wave-mob-sequence):")
        for i, m in enumerate(seq, start=1):
            print(f"    fala {i}: {m}")
        print()

    env = ArenaMcEnv(mock=mock)
    obs, info = env.reset()
    done = False
    step = 0
    total_reward = 0.0

    while not done:
        if dual:
            action, _ = policy.predict(
                obs, info.get("wave_mob_type", ""), deterministic=True
            )
        else:
            action, _ = policy.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(int(action))
        total_reward += reward
        done = terminated or truncated
        step += 1
        if SLEEP > 0:
            time.sleep(SLEEP)

    env.close()
    print(f"\nKoniec demo | kroki={step} | reward={total_reward:.1f}")
    print(
        f"max_wave={info.get('episode_max_wave', info.get('max_wave', 0))} | "
        f"hp={info.get('agent_hp', 0):.1f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
