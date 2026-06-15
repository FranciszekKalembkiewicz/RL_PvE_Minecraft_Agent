#!/usr/bin/env python3
"""Walidacja DUAL_MODEL: epizody, statystyki per mob, wykresy → reports/."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from env.arena_mc_env import ArenaMcEnv
from env.bridge_client import BridgeClient
from env.dual_policy import DualModelPolicy

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


def reload_plugin() -> None:
    try:
        c = BridgeClient()
        c.connect()
        c.reload_config()
        c.close()
    except OSError:
        pass


def run_validation(n_episodes: int, out_dir: Path) -> dict:
    policy = DualModelPolicy()
    env = ArenaMcEnv(mock=False)

    episodes: list[dict] = []
    deaths_by_mob: Counter = Counter()
    clears_by_mob: Counter = Counter()
    death_wave_hist: Counter = Counter()

    for ep in range(n_episodes):
        obs, info = env.reset()
        done = False
        step = 0
        total_reward = 0.0
        last_wave = 0
        last_mob = ""
        wave_log: list[dict] = []

        while not done:
            wave = int(info.get("wave", 0))
            mob = str(info.get("wave_mob_type", "")).upper()
            if wave != last_wave and last_wave > 0 and last_mob:
                wave_log.append(
                    {
                        "wave": last_wave,
                        "mob_type": last_mob,
                        "cleared": True,
                        "end_step": step,
                    }
                )
                clears_by_mob[last_mob] += 1
            if wave != last_wave:
                last_wave = wave
                last_mob = mob

            action, _ = policy.predict(obs, mob, deterministic=True)
            obs, reward, term, trunc, info = env.step(int(action))
            total_reward += reward
            done = term or trunc
            step += 1

        ep_max = int(info.get("episode_max_wave", info.get("max_wave", 0)))
        died = bool(info.get("wave_failed")) or float(info.get("agent_hp", 0)) <= 0
        death_wave = int(info.get("wave", 0))
        death_mob = str(info.get("wave_mob_type", "")).upper()

        if died and death_mob:
            deaths_by_mob[death_mob] += 1
            death_wave_hist[death_wave] += 1
            wave_log.append(
                {
                    "wave": death_wave,
                    "mob_type": death_mob,
                    "cleared": False,
                    "end_step": step,
                }
            )
        elif last_mob and (not wave_log or wave_log[-1]["wave"] != last_wave):
            wave_log.append(
                {
                    "wave": last_wave,
                    "mob_type": last_mob,
                    "cleared": True,
                    "end_step": step,
                }
            )
            clears_by_mob[last_mob] += 1

        ep_rec = {
            "episode": ep + 1,
            "max_wave": ep_max,
            "death_wave": death_wave if died else None,
            "death_mob": death_mob if died else None,
            "died": died,
            "steps": step,
            "reward": round(total_reward, 2),
            "final_hp": float(info.get("agent_hp", 0)),
            "waves": wave_log,
        }
        episodes.append(ep_rec)
        print(
            f"Ep {ep+1}/{n_episodes}: max_wave={ep_max} "
            f"{'ŚMIERĆ@'+death_mob+' f'+str(death_wave) if died else 'OK'} "
            f"reward={total_reward:.1f} steps={step}",
            flush=True,
        )

    env.close()

    max_waves = np.array([e["max_wave"] for e in episodes])
    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "n_episodes": n_episodes,
        "melee_model": str(policy.melee_path),
        "ranged_model": str(policy.ranged_path),
        "mean_max_wave": float(max_waves.mean()),
        "std_max_wave": float(max_waves.std()),
        "median_max_wave": float(np.median(max_waves)),
        "max_max_wave": int(max_waves.max()),
        "deaths": sum(1 for e in episodes if e["died"]),
        "full_clear_10": sum(1 for e in episodes if e["max_wave"] >= 10),
        "deaths_by_mob": dict(deaths_by_mob),
        "clears_by_mob": dict(clears_by_mob),
        "death_wave_hist": dict(death_wave_hist),
        "episodes": episodes,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    with open(out_dir / "episodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "episode",
                "max_wave",
                "died",
                "death_wave",
                "death_mob",
                "steps",
                "reward",
                "final_hp",
            ]
        )
        for e in episodes:
            w.writerow(
                [
                    e["episode"],
                    e["max_wave"],
                    int(e["died"]),
                    e["death_wave"] or "",
                    e["death_mob"] or "",
                    e["steps"],
                    e["reward"],
                    e["final_hp"],
                ]
            )

    with open(out_dir / "wave_log.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["episode", "wave", "mob_type", "cleared", "end_step"])
        for e in episodes:
            for wl in e["waves"]:
                w.writerow(
                    [
                        e["episode"],
                        wl["wave"],
                        wl["mob_type"],
                        int(wl["cleared"]),
                        wl["end_step"],
                    ]
                )

    _write_report_txt(out_dir, summary)
    if plt is not None:
        _plot_all(out_dir, summary, max_waves)
    else:
        print("WARN: brak matplotlib — pomijam wykresy")

    return summary


def _write_report_txt(out_dir: Path, s: dict) -> None:
    lines = [
        "WALIDACJA DUAL MODEL",
        "=" * 50,
        f"Data: {s['timestamp']}",
        f"Epizody: {s['n_episodes']}",
        f"Melee:  {s['melee_model']}",
        f"Ranged: {s['ranged_model']}",
        "",
        f"Średnia max_wave: {s['mean_max_wave']:.2f} ± {s['std_max_wave']:.2f}",
        f"Mediana: {s['median_max_wave']:.0f} | Max: {s['max_max_wave']}",
        f"Śmierci: {s['deaths']}/{s['n_episodes']}",
        f"Pełne 10 fal: {s['full_clear_10']}/{s['n_episodes']}",
        "",
        "Pokonane fale (łącznie po typie moba):",
    ]
    for mob, n in sorted(s["clears_by_mob"].items(), key=lambda x: -x[1]):
        lines.append(f"  {mob}: {n}")
    lines.append("")
    lines.append("Śmierci po typie moba:")
    for mob, n in sorted(s["deaths_by_mob"].items(), key=lambda x: -x[1]):
        lines.append(f"  {mob}: {n}")
    lines.append("")
    lines.append("Śmierci po numerze fali:")
    for w, n in sorted(s["death_wave_hist"].items(), key=lambda x: int(x[0])):
        lines.append(f"  fala {w}: {n}")
    (out_dir / "REPORT.txt").write_text("\n".join(lines), encoding="utf-8")


def _plot_all(out_dir: Path, s: dict, max_waves: np.ndarray) -> None:
    # 1. histogram max_wave + survival
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    mx = max(int(max_waves.max()), 1)
    axes[0].hist(max_waves, bins=range(mx + 2), edgecolor="black", alpha=0.75, color="#4C72B0")
    axes[0].axvline(s["mean_max_wave"], color="red", linestyle="--", label=f"μ={s['mean_max_wave']:.1f}")
    axes[0].set_xlabel("max_wave")
    axes[0].set_ylabel("Epizody")
    axes[0].set_title("Rozkład max_wave (dual model)")
    axes[0].legend()

    waves = np.arange(1, mx + 1)
    survival = [np.mean(max_waves >= w) * 100 for w in waves]
    axes[1].plot(waves, survival, marker="o", color="#55A868")
    axes[1].set_xlabel("Fala")
    axes[1].set_ylabel("% epizodów")
    axes[1].set_title("Krzywa przeżycia")
    axes[1].set_ylim(0, 105)
    plt.tight_layout()
    fig.savefig(out_dir / "01_max_wave_survival.png", dpi=140)
    plt.close(fig)

    # 2. deaths by mob type
    if s["deaths_by_mob"]:
        fig, ax = plt.subplots(figsize=(6, 4))
        mobs = list(s["deaths_by_mob"].keys())
        counts = [s["deaths_by_mob"][m] for m in mobs]
        colors = {"ZOMBIE": "#8B4513", "CREEPER": "#2ECC40", "SKELETON": "#DDDDDD"}
        ax.bar(mobs, counts, color=[colors.get(m, "#888") for m in mobs], edgecolor="black")
        ax.set_title("Śmierci wg typu moba (fala śmierci)")
        ax.set_ylabel("Liczba")
        plt.tight_layout()
        fig.savefig(out_dir / "02_deaths_by_mob.png", dpi=140)
        plt.close(fig)

    # 3. clears by mob type
    if s["clears_by_mob"]:
        fig, ax = plt.subplots(figsize=(6, 4))
        mobs = list(s["clears_by_mob"].keys())
        counts = [s["clears_by_mob"][m] for m in mobs]
        colors = {"ZOMBIE": "#8B4513", "CREEPER": "#2ECC40", "SKELETON": "#AAAAAA"}
        ax.bar(mobs, counts, color=[colors.get(m, "#888") for m in mobs], edgecolor="black")
        ax.set_title("Pokonane fale wg typu moba")
        ax.set_ylabel("Liczba")
        plt.tight_layout()
        fig.savefig(out_dir / "03_clears_by_mob.png", dpi=140)
        plt.close(fig)

    # 4. death wave histogram
    if s["death_wave_hist"]:
        fig, ax = plt.subplots(figsize=(7, 4))
        ws = sorted(s["death_wave_hist"].keys(), key=int)
        cs = [s["death_wave_hist"][w] for w in ws]
        ax.bar([str(w) for w in ws], cs, color="#C44E52", edgecolor="black")
        ax.set_xlabel("Fala śmierci")
        ax.set_title("Na której fali najczęściej ginie")
        ax.set_ylabel("Liczba śmierci")
        plt.tight_layout()
        fig.savefig(out_dir / "04_deaths_by_wave.png", dpi=140)
        plt.close(fig)

    # 5. mob mix on path (stacked per episode) - simplified: mob appearance rate in cleared waves
    mob_ep_count: Counter = Counter()
    for e in s["episodes"]:
        seen = {wl["mob_type"] for wl in e["waves"] if wl["cleared"]}
        for m in seen:
            mob_ep_count[m] += 1
    if mob_ep_count:
        fig, ax = plt.subplots(figsize=(6, 4))
        mobs = list(mob_ep_count.keys())
        counts = [mob_ep_count[m] for m in mobs]
        ax.bar(mobs, counts, color="#8172B2", edgecolor="black")
        ax.set_title("W ilu epizodach pokonano dany typ moba")
        ax.set_ylabel("Epizody")
        plt.tight_layout()
        fig.savefig(out_dir / "05_mob_presence_episodes.png", dpi=140)
        plt.close(fig)

    print(f"Wykresy zapisane w {out_dir}")


def main() -> int:
    n = int(os.environ.get("VALIDATION_EPISODES", "10"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(os.environ.get("VALIDATION_OUT", f"reports/dual_validation_{stamp}"))

    print(f"Walidacja dual | epizody={n} | out={out_dir}")
    reload_plugin()
    summary = run_validation(n, out_dir)

    print("\n" + "=" * 50)
    print(f"Średnia max_wave: {summary['mean_max_wave']:.2f} ± {summary['std_max_wave']:.2f}")
    print(f"Śmierci: {summary['deaths']}/{n} | Pełne 10 fal: {summary['full_clear_10']}/{n}")
    print(f"Zapisano: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
