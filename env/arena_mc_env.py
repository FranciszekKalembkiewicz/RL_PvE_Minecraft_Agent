"""Gymnasium environment for Minecraft Wave Arena (TCP bridge or mock)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from env.bridge_client import BridgeClient, load_config

MAX_MOBS = 12
MOB_FEATURES = 6
AGENT_FEATURES = 3
OBS_SIZE = AGENT_FEATURES + MAX_MOBS * MOB_FEATURES


class ArenaMcEnv(gym.Env):
    """Connects to Paper WaveArena plugin via TCP JSON bridge."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        config_path: str | Path | None = None,
        mock: bool | None = None,
        max_wave_train: int | None = None,
    ):
        super().__init__()
        self.cfg = load_config(config_path)
        self.mock = mock if mock is not None else os.environ.get("ARENA_MOCK", "") == "1"
        self.max_mobs = int(self.cfg["arena"]["max_mobs"])
        self.radius = float(self.cfg["arena"]["radius"])
        self.agent_max_hp = float(self.cfg["agent"]["max_hp"])
        self.max_wave_train = max_wave_train or int(
            self.cfg["training"].get("max_wave_train", 10)
        )
        self.rewards_cfg = self.cfg.get("rewards", {})
        self._mob_counts = self.cfg["wave"]["mob_counts"]
        self._mob_type_to_idx = {
            name.upper(): idx + 1
            for idx, name in enumerate(self.cfg.get("wave", {}).get("mob_types", []))
        }

        self.action_space = spaces.Discrete(8)
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(OBS_SIZE,), dtype=np.float32
        )

        self._client: BridgeClient | _MockBridge | None = None
        self._prev_min_dist: float | None = None
        self._last_state: dict[str, Any] = {}
        self._episode_max_wave = 0

    def _ensure_client(self) -> BridgeClient | _MockBridge:
        if self._client is None:
            if self.mock:
                self._client = _MockBridge(self.cfg)
            else:
                self._client = BridgeClient.from_config(self.cfg)
        return self._client

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        client = self._ensure_client()
        state = client.reset()
        if not state.get("ok", False):
            raise RuntimeError(f"Bridge reset failed: {state.get('error', state)}")
        self._last_state = state
        self._prev_min_dist = self._min_dist_from_state(state)
        self._episode_max_wave = 0
        return self._build_obs(state), self._info_dict(state)

    def step(self, action: int):
        client = self._ensure_client()
        state = client.step(int(action))
        if not state.get("ok", False) and not state.get("episode_done", False):
            raise RuntimeError(f"Bridge step failed: {state.get('error', state)}")

        reward = self._compute_reward(state, self._last_state)
        self._last_state = state

        self._episode_max_wave = max(
            self._episode_max_wave, int(state.get("max_wave", 0))
        )

        terminated = bool(state.get("episode_done", False))
        truncated = False

        if terminated and not state.get("wave_failed") and state.get("agent_hp", 0) > 0:
            pass
        elif state.get("wave_failed") or state.get("agent_hp", 0) <= 0:
            terminated = True

        obs = self._build_obs(state)
        info = self._info_dict(state)
        info["episode_max_wave"] = self._episode_max_wave
        return obs, reward, terminated, truncated, info

    def close(self):
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()
        self._client = None

    def _info_dict(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "wave": int(state.get("wave", 0)),
            "max_wave": int(state.get("max_wave", 0)),
            "alive_mobs": int(state.get("alive_mobs", 0)),
            "agent_hp": float(state.get("agent_hp", 0)),
            "step": int(state.get("step", 0)),
            "wave_cleared": bool(state.get("wave_cleared", False)),
            "wave_failed": bool(state.get("wave_failed", False)),
        }

    def _compute_reward(
        self, state: dict[str, Any], prev: dict[str, Any]
    ) -> float:
        r = 0.0
        alive = int(state.get("alive_mobs", 0))
        r -= float(self.rewards_cfg.get("step_penalty_per_mob", 0.005)) * alive

        curr_dist = self._min_dist_from_state(state)
        if self._prev_min_dist is not None and curr_dist < self._prev_min_dist:
            r += float(self.rewards_cfg.get("approach_coef", 0.05)) * (
                self._prev_min_dist - curr_dist
            )
        self._prev_min_dist = curr_dist

        nearest = self._nearest_mob(state)
        if nearest is not None:
            nearest_dist, nearest_mob = nearest
            combat_min = float(self.rewards_cfg.get("combat_band_min", 2.0))
            combat_max = float(self.rewards_cfg.get("combat_band_max", 3.0))
            combat_bonus = float(self.rewards_cfg.get("combat_band_bonus", 0.03))
            if combat_min <= nearest_dist <= combat_max:
                r += combat_bonus

            threat_range = self._mob_threat_range(str(nearest_mob.get("type", "")))
            danger_buffer = float(self.rewards_cfg.get("danger_buffer", 0.2))
            danger_penalty_coef = float(self.rewards_cfg.get("danger_penalty_coef", 0.04))
            safe_dist = threat_range + danger_buffer
            if nearest_dist < safe_dist:
                r -= danger_penalty_coef * (safe_dist - nearest_dist)

        damage = float(state.get("damage_dealt", 0))
        if damage > 0:
            r += float(self.rewards_cfg.get("hit_reward", 1.0))

        kills = int(state.get("kills_this_step", 0))
        if kills > 0:
            r += float(self.rewards_cfg.get("kill_bonus", 3.0)) * kills

        if state.get("wave_cleared"):
            base = float(self.rewards_cfg.get("wave_clear_base", 10.0))
            r += base

        if state.get("wave_failed") or (
            state.get("episode_done") and state.get("agent_hp", 0) <= 0
        ):
            r += float(self.rewards_cfg.get("death_penalty", -10.0))

        return r

    def _min_dist_from_state(self, state: dict[str, Any]) -> float:
        nearest = self._nearest_mob(state)
        return nearest[0] if nearest is not None else 0.0

    def _nearest_mob(self, state: dict[str, Any]) -> tuple[float, dict[str, Any]] | None:
        agent = state.get("agent_pos") or {}
        ax, az = float(agent.get("x", 0)), float(agent.get("z", 0))
        best: tuple[float, dict[str, Any]] | None = None
        for mob in state.get("mobs", []):
            mx, mz = float(mob["x"]), float(mob["z"])
            d = float(np.hypot(mx - ax, mz - az))
            if best is None or d < best[0]:
                best = (d, mob)
        return best

    def _mob_threat_range(self, mob_type: str) -> float:
        mt = mob_type.upper()
        custom = self.rewards_cfg.get("threat_ranges", {})
        if isinstance(custom, dict) and mt in custom:
            try:
                return float(custom[mt])
            except (TypeError, ValueError):
                pass
        if mt in {"SKELETON", "STRAY", "DROWNED"}:
            return float(self.rewards_cfg.get("ranged_threat_range", 8.0))
        return float(self.rewards_cfg.get("melee_threat_range", 1.8))

    def _build_obs(self, state: dict[str, Any]) -> np.ndarray:
        agent = state.get("agent_pos") or {}
        center = state.get("arena_center") or self.cfg["arena"]["center"]
        radius = float(state.get("arena_radius", self.radius))

        cx, cz = float(center["x"]), float(center["z"])
        ax, az = float(agent.get("x", cx)), float(agent.get("z", cz))

        obs: list[float] = [
            float(state.get("agent_hp", 0)) / self.agent_max_hp,
            np.clip((ax - cx) / radius, -1, 1) * 0.5 + 0.5,
            np.clip((az - cz) / radius, -1, 1) * 0.5 + 0.5,
        ]

        mobs_sorted = []
        for mob in state.get("mobs", []):
            mx, mz = float(mob["x"]), float(mob["z"])
            dist = np.hypot(mx - ax, mz - az)
            mobs_sorted.append((dist, mob))
        mobs_sorted.sort(key=lambda t: t[0])

        for dist, mob in mobs_sorted[:MAX_MOBS]:
            max_hp = float(mob.get("max_hp", self.agent_max_hp))
            hp_n = float(mob["hp"]) / max(max_hp, 1e-6)
            dx = (float(mob["x"]) - ax) / radius
            dz = (float(mob["z"]) - az) / radius
            dist_n = min(dist / radius, 1.0)
            angle_sin = (dz / (dist + 1e-8) + 1.0) / 2.0
            mob_type_n = self._encode_mob_type(mob.get("type", ""))
            obs.extend(
                [
                    np.clip(hp_n, 0, 1),
                    np.clip(dx * 0.5 + 0.5, 0, 1),
                    np.clip(dz * 0.5 + 0.5, 0, 1),
                    dist_n,
                    angle_sin,
                    mob_type_n,
                ]
            )

        while len(obs) < OBS_SIZE:
            obs.extend([0.0] * MOB_FEATURES)

        return np.array(obs[:OBS_SIZE], dtype=np.float32)

    def _encode_mob_type(self, mob_type: Any) -> float:
        if not self._mob_type_to_idx:
            return 0.0
        idx = self._mob_type_to_idx.get(str(mob_type).upper(), 0)
        return idx / float(len(self._mob_type_to_idx))


class _MockBridge:
    """Offline simulator for tests when Minecraft server is not running."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.wave = 0
        self.max_wave = 0
        self.step_num = 0
        self.agent_hp = float(cfg["agent"]["max_hp"])
        self.center = cfg["arena"]["center"]
        self.radius = float(cfg["arena"]["radius"])
        self.mob_counts = cfg["wave"]["mob_counts"]
        self.mob_types = [str(t).upper() for t in cfg.get("wave", {}).get("mob_types", ["ZOMBIE"])]
        self.mobs: list[dict[str, float | str]] = []
        self.episode_done = False
        self.current_type = "ZOMBIE"

    def close(self) -> None:
        pass

    def reset(self) -> dict[str, Any]:
        self.wave = 0
        self.max_wave = 0
        self.step_num = 0
        self.agent_hp = float(self.cfg["agent"]["max_hp"])
        self.episode_done = False
        self.current_type = "ZOMBIE"
        self._spawn_wave()
        return self._state(ok=True, wave_cleared=False, kills=0, damage=0.0)

    def step(self, action: int) -> dict[str, Any]:
        if self.episode_done:
            return self._state(ok=False, error="episode_not_active")

        self.step_num += 1
        kills = 0
        damage = 0.0
        wave_cleared = False

        if action == 4 and self.mobs:
            target = min(self.mobs, key=lambda m: m["hp"])
            dmg = 4.5
            target["hp"] = float(target["hp"]) - dmg
            damage = dmg
            if target["hp"] <= 0:
                kills = 1
                self.mobs.remove(target)

        if action in (0, 1, 2, 3):
            for m in self.mobs:
                m["x"] = float(m["x"]) - 0.1
                m["z"] = float(m["z"]) - 0.05

        for m in list(self.mobs):
            dist = np.hypot(
                float(m["x"]) - float(self.center["x"]),
                float(m["z"]) - float(self.center["z"]),
            )
            if dist < 2.0:
                self.agent_hp -= 0.5

        if not self.mobs and self.wave > 0:
            wave_cleared = True
            self.max_wave = max(self.max_wave, self.wave)
            if self.wave >= len(self.mob_counts):
                self.episode_done = True
            else:
                self._spawn_wave()

        if self.agent_hp <= 0:
            self.episode_done = True

        return self._state(
            ok=True,
            wave_cleared=wave_cleared,
            kills=kills,
            damage=damage,
        )

    def _spawn_wave(self) -> None:
        self.wave += 1
        idx = min(self.wave - 1, len(self.mob_counts) - 1)
        count = self.mob_counts[idx]
        if self.mob_types:
            self.current_type = self.mob_types[(self.wave - 1) % len(self.mob_types)]
        self.mobs = []
        slots = self.cfg["spawn_slots"][:count]
        for slot in slots:
            self.mobs.append(
                {
                    "hp": 20.0,
                    "max_hp": 20.0,
                    "x": slot["x"],
                    "y": slot["y"],
                    "z": slot["z"],
                    "type": self.current_type,
                }
            )

    def _state(
        self,
        ok: bool,
        wave_cleared: bool = False,
        kills: int = 0,
        damage: float = 0.0,
        error: str | None = None,
    ) -> dict[str, Any]:
        s: dict[str, Any] = {
            "ok": ok,
            "wave": self.wave,
            "max_wave": self.max_wave,
            "alive_mobs": len(self.mobs),
            "episode_done": self.episode_done,
            "wave_cleared": wave_cleared,
            "wave_failed": self.agent_hp <= 0,
            "step": self.step_num,
            "kills_this_step": kills,
            "damage_dealt": damage,
            "arena_radius": self.radius,
            "arena_center": self.center,
            "agent_hp": self.agent_hp,
            "agent_max_hp": float(self.cfg["agent"]["max_hp"]),
            "agent_pos": {
                "x": float(self.center["x"]),
                "y": float(self.center["y"]),
                "z": float(self.center["z"]),
            },
            "mobs": [dict(m) for m in self.mobs],
        }
        if error:
            s["error"] = error
        return s
