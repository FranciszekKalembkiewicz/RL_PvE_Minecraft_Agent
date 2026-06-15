"""Przełączanie między modelem melee (zombie/creeper) a ranged (szkielet)."""

from __future__ import annotations

import os
from pathlib import Path

from stable_baselines3 import PPO

RANGED_WAVE_TYPES = frozenset({"SKELETON", "STRAY", "DROWNED"})
DEFAULT_MELEE = Path("checkpoints/final_wave_melee.zip")
DEFAULT_RANGED = Path("checkpoints/final_wave_ranged.zip")
FALLBACK_MELEE = Path("checkpoints/snapshots/ppo_wave_500000_steps.zip")
FALLBACK_RANGED = Path("checkpoints/final_wave_post_skeleton80k.zip")


def _resolve_path(env_key: str, default: Path, fallback: Path) -> Path:
    override = os.environ.get(env_key, "").strip()
    if override:
        p = Path(override)
        if not p.exists():
            raise FileNotFoundError(f"{env_key} nie istnieje: {p}")
        return p
    if default.exists():
        return default
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Brak modelu ({env_key}): {default} ani {fallback}")


class DualModelPolicy:
    """Wybiera PPO wg typu fali z mostu (wave_mob_type)."""

    def __init__(
        self,
        melee_path: Path | None = None,
        ranged_path: Path | None = None,
    ):
        melee = melee_path or _resolve_path("MELEE_MODEL", DEFAULT_MELEE, FALLBACK_MELEE)
        ranged = ranged_path or _resolve_path("RANGED_MODEL", DEFAULT_RANGED, FALLBACK_RANGED)
        self.melee_path = melee
        self.ranged_path = ranged
        self.melee = PPO.load(str(melee))
        self.ranged = PPO.load(str(ranged))
        self._last_wave_type = ""

    def model_for_wave(self, wave_mob_type: str) -> PPO:
        wt = str(wave_mob_type or "").upper()
        if wt in RANGED_WAVE_TYPES:
            return self.ranged
        return self.melee

    def predict(
        self,
        obs,
        wave_mob_type: str,
        *,
        deterministic: bool = True,
    ):
        wt = str(wave_mob_type or "").upper()
        model = self.model_for_wave(wt)
        if wt != self._last_wave_type and wt:
            label = "RANGED" if wt in RANGED_WAVE_TYPES else "MELEE"
            path = self.ranged_path if wt in RANGED_WAVE_TYPES else self.melee_path
            print(f"  [dual] fala {wt} → model {label} ({path.name})", flush=True)
            self._last_wave_type = wt
        return model.predict(obs, deterministic=deterministic)


def use_dual_models() -> bool:
    return os.environ.get("DUAL_MODEL", "0") == "1"
