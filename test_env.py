"""Smoke test: random actions against mock or live bridge."""

import os
import sys

from env.arena_mc_env import ArenaMcEnv


def main() -> int:
    mock = os.environ.get("ARENA_MOCK", "1") == "1"
    if not mock:
        print("Łączenie z serwerem Minecraft (ARENA_MOCK=0)...")
    else:
        print("Tryb mock (ARENA_MOCK=1) — bez serwera.")

    try:
        env = ArenaMcEnv(mock=mock)
        obs, info = env.reset()
        print(f"reset OK | obs shape={obs.shape} | wave={info['wave']}")

        total_reward = 0.0
        for t in range(20):
            action = env.action_space.sample()
            obs, reward, term, trunc, info = env.step(action)
            total_reward += reward
            print(
                f"  step {t+1:2d} action={action} reward={reward:+.3f} "
                f"wave={info['wave']} alive={info['alive_mobs']} hp={info['agent_hp']:.1f}"
            )
            if term or trunc:
                print(f"  epizod zakończony | max_wave={info.get('episode_max_wave', info['max_wave'])}")
                break

        print(f"\nSuma nagród (20 kroków): {total_reward:.2f}")
        env.close()
        return 0
    except ConnectionError as e:
        print(f"Błąd połączenia: {e}")
        print("Uruchom serwer Paper + plugin WaveArena lub ustaw ARENA_MOCK=1")
        return 1
    except Exception as e:
        print(f"Błąd: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
