"""Jedno epizod na żywo — pokaz dla prowadzącego (model już wytrenowany, bez uczenia).

Użycie:
  unset ARENA_MOCK
  python demo.py

Opcjonalnie wolniej (łatwiej oglądać w grze):
  DEMO_SLEEP=0.05 python demo.py
"""

import os
import time
from pathlib import Path

from stable_baselines3 import PPO

from env.arena_mc_env import ArenaMcEnv

MODEL_PATH = Path("checkpoints/final_wave.zip")
FALLBACK = Path("checkpoints/best/best_model.zip")
SLEEP = float(os.environ.get("DEMO_SLEEP", "0.0"))


def main() -> int:
    mock = os.environ.get("ARENA_MOCK", "0") == "1"
    path = MODEL_PATH if MODEL_PATH.exists() else FALLBACK
    if not path.exists():
        print("Brak modelu. Najpierw: python train.py")
        return 1

    print(f"Demo 1 epizod | model={path} | mock={mock}")
    print("Patrz na gracza your Minecraft username w Minecraft — agent sterowany siecią PPO.\n")

    model = PPO.load(str(path))
    env = ArenaMcEnv(mock=mock)
    obs, _ = env.reset()
    done = False
    step = 0
    total_reward = 0.0

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(int(action))
        total_reward += reward
        done = terminated or truncated
        step += 1
        if SLEEP > 0:
            time.sleep(SLEEP)

    env.close()
    print(f"\nKoniec demo | kroki={step} | reward={total_reward:.1f}")
    print(f"max_wave={info.get('episode_max_wave', info.get('max_wave', 0))} | "
          f"hp={info.get('agent_hp', 0):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
