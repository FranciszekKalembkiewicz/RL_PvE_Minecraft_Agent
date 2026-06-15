#!/usr/bin/env python3
"""Diagnostyka na żywo: reload pluginu, epizod dual-model, statystyki akcji per typ fali."""

from __future__ import annotations

import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from env.arena_mc_env import ArenaMcEnv
from env.bridge_client import BridgeClient
from env.dual_policy import DualModelPolicy

ACTIONS = ["fwd", "back", "left", "right", "attack", "noop", "jump", "turn"]


def wait_bridge(timeout_sec: float = 300.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            c = BridgeClient()
            c.connect()
            st = c.status()
            c.close()
            if st.get("ok"):
                return True
        except OSError:
            pass
        time.sleep(5)
    return False


def wait_agent(timeout_sec: float = 600.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            c = BridgeClient()
            c.connect()
            st = c.status()
            c.close()
            if st.get("ok") and float(st.get("agent_hp", 0)) > 0:
                return True
        except OSError:
            pass
        print("  czekam na gracza Franq__ online...", flush=True)
        time.sleep(10)
    return False


def reload_plugin() -> dict:
    c = BridgeClient()
    c.connect()
    try:
        return c.reload_config()
    except OSError:
        return c.send_command({"cmd": "reload"})
    finally:
        c.close()


def run_episode(max_steps: int = 2500) -> dict:
    policy = DualModelPolicy()
    env = ArenaMcEnv(mock=False)
    obs, info = env.reset()
    done = False
    step = 0
    total_reward = 0.0
    by_wave: dict[str, Counter] = defaultdict(Counter)
    movement_by_wave: dict[str, list[float]] = defaultdict(list)
    prev_pos = None

    while not done and step < max_steps:
        wave = str(info.get("wave_mob_type", "?"))
        action, _ = policy.predict(obs, wave, deterministic=True)
        a = int(action)
        by_wave[wave][a] += 1

        obs, reward, term, trunc, info = env.step(a)
        total_reward += reward
        done = term or trunc
        step += 1

        state = env._last_state
        pos = state.get("agent_pos")
        if pos and prev_pos:
            dx = float(pos["x"]) - float(prev_pos["x"])
            dz = float(pos["z"]) - float(prev_pos["z"])
            movement_by_wave[wave].append((dx * dx + dz * dz) ** 0.5)
        if pos:
            prev_pos = pos

    env.close()
    return {
        "steps": step,
        "reward": total_reward,
        "max_wave": info.get("episode_max_wave", info.get("max_wave", 0)),
        "hp": info.get("agent_hp", 0),
        "by_wave": dict(by_wave),
        "movement_by_wave": movement_by_wave,
        "melee": str(policy.melee_path),
        "ranged": str(policy.ranged_path),
    }


def print_report(rep: dict) -> None:
    print("\n=== LIVE DIAG ===")
    print(f"melee:  {rep['melee']}")
    print(f"ranged: {rep['ranged']}")
    print(f"steps={rep['steps']} reward={rep['reward']:.1f} max_wave={rep['max_wave']} hp={rep['hp']:.1f}")
    for wave, counts in sorted(rep["by_wave"].items()):
        total = sum(counts.values()) or 1
        moves = rep["movement_by_wave"].get(wave, [])
        avg_move = sum(moves) / len(moves) if moves else 0.0
        print(f"\n  fala {wave} ({total} kroków, avg_move={avg_move:.3f})")
        for i in range(8):
            if counts[i]:
                print(f"    {ACTIONS[i]:6s} {counts[i]:4d} ({100 * counts[i] / total:.1f}%)")


def main() -> int:
    print("1) bridge...")
    if not wait_bridge(60):
        print("FAIL: brak bridge :5555 — uruchom serwer (scripts/start_mc.sh)")
        return 1
    print("   bridge OK")

    print("2) reload config pluginu...")
    try:
        r = reload_plugin()
        if r.get("config_reloaded"):
            print(
                f"   reload OK | skeleton_face={r.get('skeleton_face_target')} "
                f"move_toward={r.get('skeleton_move_toward')}"
            )
        else:
            print("   reload: stary JAR bez cmd reload — zrestartuj serwer po build pluginu")
            st = BridgeClient().status()
    except OSError as e:
        print(f"   reload skip: {e}")

    print("3) gracz online...")
    if not wait_agent(120):
        print("WARN: Franq__ offline — epizod może się nie zacząć")
    else:
        print("   gracz OK")

    print("4) epizod dual-model...")
    rep = run_episode()
    print_report(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
