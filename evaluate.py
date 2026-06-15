"""Evaluate trained PPO agent — reports max_wave distribution."""

import os
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO

from env.arena_mc_env import ArenaMcEnv
from env.dual_policy import DualModelPolicy, use_dual_models


def _log(msg: str) -> None:
    print(msg, flush=True)


DEFAULT_MODEL = Path("checkpoints/final_wave.zip")
FALLBACK_MODEL = Path("checkpoints/best/best_model.zip")


def _resolve_model() -> Path:
    env_path = os.environ.get("EVAL_MODEL", "").strip()
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"EVAL_MODEL nie istnieje: {p}")
    if DEFAULT_MODEL.exists():
        return DEFAULT_MODEL
    if FALLBACK_MODEL.exists():
        return FALLBACK_MODEL
    raise FileNotFoundError(
        f"Brak modelu: {DEFAULT_MODEL} ani {FALLBACK_MODEL}. "
        "Ustaw EVAL_MODEL=checkpoints/Personal/200000stepstreningsnapszot.zip"
    )


def main():
    # Bez ARENA_MOCK = prawdziwy Minecraft (wolniej). Z ARENA_MOCK=1 = mock, szybko.
    mock = os.environ.get("ARENA_MOCK", "0") == "1"
    n_episodes = int(os.environ.get("EVAL_EPISODES", "20"))
    progress_every = int(os.environ.get("EVAL_PROGRESS_EVERY", "50"))

    dual = use_dual_models()

    if dual:
        policy = DualModelPolicy()
        _log(f"DUAL_MODEL=1 | melee={policy.melee_path} | ranged={policy.ranged_path}")
    else:
        try:
            model_path = _resolve_model()
        except FileNotFoundError as e:
            _log(str(e))
            _log("Uruchom najpierw train.py lub podaj EVAL_MODEL=ścieżka/do/modelu.zip")
            return 1
        _log(f"Model: {model_path}")
        policy = PPO.load(str(model_path))

    _log(f"mock={mock} | epizody={n_episodes} | postęp co {progress_every} kroków")
    if not mock:
        _log(
            "LIVE: serwer ./start.sh + gracz your Minecraft username online. "
            "Pierwszy wiersz wyniku pojawi się po ~3–8 min (koniec ep. 1)."
        )
    _log("Ładowanie sieci PPO...")
    if not dual:
        _log("Tworzenie środowiska...")
    else:
        _log("Dual policy załadowana. Tworzenie środowiska...")
    env = ArenaMcEnv(mock=mock)

    max_waves = []
    deaths = 0
    clears = 0

    for ep in range(n_episodes):
        _log(f"\n--- Epizod {ep + 1}/{n_episodes} (reset mostu...) ---")
        obs, info = env.reset()
        done = False
        total_reward = 0.0
        step = 0
        last_wave = -1

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

            wave = int(info.get("wave", 0))
            if wave != last_wave:
                _log(
                    f"  ep {ep + 1} | fala {wave} | hp={info.get('agent_hp', 0):.1f} | "
                    f"moby={info.get('alive_mobs', 0)} | krok {step}"
                )
                last_wave = wave
            elif progress_every > 0 and step % progress_every == 0:
                _log(
                    f"  ep {ep + 1} | fala {wave} | krok {step} | "
                    f"hp={info.get('agent_hp', 0):.1f} | moby={info.get('alive_mobs', 0)}"
                )

        ep_max = info.get("episode_max_wave", info.get("max_wave", 0))
        max_waves.append(ep_max)

        if info.get("wave_failed") or info.get("agent_hp", 0) <= 0:
            deaths += 1
            result = "ŚMIERĆ"
        elif info.get("episode_done") and ep_max >= 1:
            clears += 1
            result = f"KONIEC (max_wave={ep_max})"
        else:
            result = f"STOP (max_wave={ep_max})"

        _log(
            f"Ep {ep + 1:2d}: {result:28s} | reward={total_reward:8.2f} | "
            f"kroki={step} | wave={info['wave']} hp={info['agent_hp']:.1f}"
        )

    env.close()
    arr = np.array(max_waves)
    _log(f"\n{'=' * 50}")
    _log(f"Średnia max_wave: {arr.mean():.2f} ± {arr.std():.2f}")
    _log(f"Mediana max_wave: {np.median(arr):.0f}")
    _log(f"Max max_wave:     {arr.max():.0f}")
    _log(f"Śmierci: {deaths}/{n_episodes} | Ukończone epizody: {clears}/{n_episodes}")

    out_dir = Path("logs")
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / "eval_max_wave.csv"
    np.savetxt(csv_path, arr, fmt="%d", header="max_wave", comments="")
    _log(f"\nZapisano: {csv_path}")
    _log("Wykres: python report/plot_results.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
