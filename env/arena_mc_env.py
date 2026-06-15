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
AGENT_FEATURES = 5
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
        mob_override = os.environ.get("TRAIN_MOB_TYPES", "").strip()
        if mob_override:
            self.cfg.setdefault("wave", {})["mob_types"] = [
                t.strip().upper() for t in mob_override.split(",") if t.strip()
            ]
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
        self._prev_agent_hp: float | None = None
        self._prev_agent_x: float | None = None
        self._prev_agent_z: float | None = None
        self._last_state: dict[str, Any] = {}
        self._episode_max_wave = 0
        self._wave_start_step = 0
        self._last_wave_num = 0
        self._last_action = 5

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
        self._prev_agent_hp = float(state.get("agent_hp", self.agent_max_hp))
        agent_pos = state.get("agent_pos") or {}
        self._prev_agent_x = float(agent_pos.get("x", 0))
        self._prev_agent_z = float(agent_pos.get("z", 0))
        self._episode_max_wave = 0
        self._wave_start_step = int(state.get("step", 0))
        self._last_wave_num = int(state.get("wave", 0))
        self._last_action = 5
        return self._build_obs(state), self._info_dict(state)

    def step(self, action: int):
        self._last_action = int(action)
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

        wave_num = int(state.get("wave", 0))
        if wave_num != self._last_wave_num:
            self._wave_start_step = int(state.get("step", 0))
            self._last_wave_num = wave_num

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
            "wave_mob_type": str(state.get("wave_mob_type", "")),
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
        nearest = self._nearest_mob(state)
        wave_type = str(state.get("wave_mob_type", "")).upper()
        if not wave_type and nearest is not None:
            wave_type = str(nearest[1].get("type", "")).upper()

        attack_range = float(self.rewards_cfg.get("attack_range", 3.0))
        agent = state.get("agent_pos") or {}
        center = state.get("arena_center") or self.cfg["arena"]["center"]
        ax, az = float(agent.get("x", center["x"])), float(agent.get("z", center["z"]))
        movement = 0.0
        if self._prev_agent_x is not None and self._prev_agent_z is not None:
            movement = float(np.hypot(ax - self._prev_agent_x, az - self._prev_agent_z))
        self._prev_agent_x = ax
        self._prev_agent_z = az
        prev_dist = self._prev_min_dist

        if nearest is not None:
            nearest_dist, nearest_mob = nearest
            mob_type = str(nearest_mob.get("type", wave_type)).upper()
            opt_min, opt_max = self._optimal_range(mob_type)
            is_skeleton = mob_type == "SKELETON" or wave_type == "SKELETON"

            delta = (prev_dist - nearest_dist) if prev_dist is not None else 0.0
            approach_coef = float(self.rewards_cfg.get("approach_coef", 0.05))
            retreat_coef = float(self.rewards_cfg.get("retreat_coef", 0.06))

            if is_skeleton:
                yaw = float(state.get("agent_yaw", 0.0))
                radius = float(state.get("arena_radius", self.radius))
                cx, cz = float(center["x"]), float(center["z"])
                edge = max(abs(ax - cx), abs(az - cz)) / max(radius, 1e-6)
                r += self._skeleton_reward(
                    state,
                    nearest_mob=nearest_mob,
                    ax=ax,
                    az=az,
                    yaw=yaw,
                    nearest_dist=nearest_dist,
                    delta=delta,
                    movement=movement,
                    attack_range=attack_range,
                    alive=alive,
                    edge=edge,
                    last_action=self._last_action,
                )
            else:
                crowd_min = int(self.rewards_cfg.get("crowd_min_mobs", 6))
                if prev_dist is not None:
                    if nearest_dist > attack_range and delta > 0:
                        r += approach_coef * delta
                    elif nearest_dist < opt_min and delta < 0:
                        r += retreat_coef * (-delta)
                    elif alive >= crowd_min and delta < 0:
                        r -= float(
                            self.rewards_cfg.get("crowd_retreat_penalty", 0.25)
                        ) * (-delta)
                    else:
                        threat = self._mob_threat_range(mob_type)
                        if nearest_dist < threat and delta < 0:
                            r += retreat_coef * (-delta)

                if opt_min <= nearest_dist <= opt_max:
                    r += float(self.rewards_cfg.get("combat_band_bonus", 0.05))

                if nearest_dist <= attack_range:
                    r += float(self.rewards_cfg.get("strike_range_bonus", 0.08))
                    if float(state.get("damage_dealt", 0)) <= 0:
                        r -= float(
                            self.rewards_cfg.get("in_range_no_hit_penalty", 0.03)
                        )

                too_far = float(self.rewards_cfg.get("too_far_threshold", 3.2))
                if nearest_dist > too_far:
                    r -= float(self.rewards_cfg.get("too_far_penalty", 0.04))
                elif nearest_dist > attack_range:
                    r -= float(self.rewards_cfg.get("too_far_penalty", 0.04)) * 0.5

                threat_range = self._mob_threat_range(mob_type)
                danger_buffer = float(self.rewards_cfg.get("danger_buffer", 0.2))
                danger_penalty_coef = float(
                    self.rewards_cfg.get("danger_penalty_coef", 0.06)
                )
                safe_dist = threat_range + danger_buffer
                if nearest_dist < safe_dist:
                    r -= danger_penalty_coef * (safe_dist - nearest_dist)

        self._prev_min_dist = curr_dist

        edge_penalty = float(self.rewards_cfg.get("corner_penalty", 0.02))
        radius = float(state.get("arena_radius", self.radius))
        cx, cz = float(center["x"]), float(center["z"])
        edge = max(abs(ax - cx), abs(az - cz)) / max(radius, 1e-6)
        edge_thr = float(self.rewards_cfg.get("corner_edge_threshold", 0.82))
        if edge > edge_thr:
            r -= edge_penalty

        damage_taken = float(state.get("damage_taken", 0.0))
        if damage_taken <= 0 and self._prev_agent_hp is not None:
            damage_taken = max(0.0, self._prev_agent_hp - float(state.get("agent_hp", 0)))
        if damage_taken > 0:
            dmg_pen = float(self.rewards_cfg.get("damage_taken_penalty", 0.35))
            if nearest is not None:
                mt = str(nearest[1].get("type", wave_type)).upper()
                if (mt == "SKELETON" or wave_type == "SKELETON") and (
                    prev_dist is not None and curr_dist < prev_dist
                ):
                    dmg_pen *= float(
                        self.rewards_cfg.get("skeleton_approach_damage_factor", 0.35)
                    )
            r -= dmg_pen * damage_taken
        self._prev_agent_hp = float(state.get("agent_hp", 0))

        damage = float(state.get("damage_dealt", 0))
        if damage > 0:
            hit_r = float(self.rewards_cfg.get("hit_reward", 1.0))
            if wave_type == "SKELETON" or (
                nearest is not None
                and str(nearest[1].get("type", wave_type)).upper() == "SKELETON"
            ):
                hit_r += float(self.rewards_cfg.get("skeleton_hit_bonus", 4.0))
            r += hit_r

        kills = int(state.get("kills_this_step", 0))
        if kills > 0:
            kill_r = float(self.rewards_cfg.get("kill_bonus", 3.0)) * kills
            crowd_min = int(self.rewards_cfg.get("crowd_min_mobs", 6))
            if alive + kills >= crowd_min:
                kill_r += float(self.rewards_cfg.get("crowd_kill_bonus", 0.0)) * kills
            if wave_type == "SKELETON" or (
                nearest is not None
                and str(nearest[1].get("type", wave_type)).upper() == "SKELETON"
            ):
                kill_r += float(self.rewards_cfg.get("skeleton_kill_bonus", 8.0)) * kills
            r += kill_r

        if state.get("wave_cleared"):
            r += float(self.rewards_cfg.get("wave_clear_base", 10.0))
            sk_clear = wave_type == "SKELETON" or (
                nearest is not None
                and str(nearest[1].get("type", wave_type)).upper() == "SKELETON"
            )
            if sk_clear:
                steps_in_wave = max(
                    1, int(state.get("step", 0)) - self._wave_start_step
                )
                target = float(
                    self.rewards_cfg.get("skeleton_fast_clear_steps", 80)
                )
                if steps_in_wave < target:
                    r += (target - steps_in_wave) * float(
                        self.rewards_cfg.get("skeleton_fast_clear_coef", 0.2)
                    )

        if state.get("wave_failed") or (
            state.get("episode_done") and state.get("agent_hp", 0) <= 0
        ):
            r += float(self.rewards_cfg.get("death_penalty", -10.0))

        return r

    def _skeleton_reward(
        self,
        state: dict[str, Any],
        *,
        nearest_mob: dict[str, Any],
        ax: float,
        az: float,
        yaw: float,
        nearest_dist: float,
        delta: float,
        movement: float,
        attack_range: float,
        alive: int,
        edge: float,
        last_action: int = 5,
    ) -> float:
        """Podejdź na ~1 kratkę (nie ta sama pozycja), potem bij."""
        r = 0.0
        r -= float(self.rewards_cfg.get("skeleton_time_penalty", 0.12)) * alive

        ideal_min = float(self.rewards_cfg.get("skeleton_ideal_min", 0.95))
        ideal_max = float(self.rewards_cfg.get("skeleton_ideal_max", 2.0))
        must_close = float(self.rewards_cfg.get("skeleton_must_close_dist", 2.8))

        bearing_n = self._relative_bearing_norm(
            ax, az, float(nearest_mob["x"]), float(nearest_mob["z"]), yaw
        )
        facing_align = 1.0 - min(abs(bearing_n - 0.5) * 2.0, 1.0)
        face_min = float(self.rewards_cfg.get("skeleton_approach_facing_min", 0.35))
        idle_thr = float(self.rewards_cfg.get("skeleton_idle_move_threshold", 0.06))
        damage_dealt = float(state.get("damage_dealt", 0))
        damage_taken = float(state.get("damage_taken", 0))

        if last_action == 6:
            if damage_taken > 0:
                r += float(self.rewards_cfg.get("skeleton_dodge_jump_bonus", 0.08))
            else:
                r -= float(self.rewards_cfg.get("skeleton_jump_penalty", 0.55))

        if last_action == 7 and facing_align < 0.55:
            r += float(self.rewards_cfg.get("skeleton_turn_bonus", 0.12)) * (
                1.0 - facing_align
            )

        # Forward — gdy za daleko od strefy ~1 kratki
        if last_action == 0 and nearest_dist > ideal_max and facing_align >= face_min:
            r += float(self.rewards_cfg.get("skeleton_forward_bonus", 0.35)) * (
                0.5 + 0.5 * facing_align
            )

        if last_action in (2, 3) and nearest_dist > ideal_max and delta <= 0:
            r -= float(self.rewards_cfg.get("skeleton_strafe_penalty", 0.45))

        approach_coef = float(self.rewards_cfg.get("skeleton_approach_coef", 2.5))
        if delta > 0 and facing_align >= face_min and nearest_dist > ideal_min:
            r += approach_coef * delta * (0.4 + 0.6 * facing_align)

        # Strefa docelowa: ~1 kratka (nie ta sama pozycja co mob)
        if nearest_dist < ideal_min:
            r -= float(self.rewards_cfg.get("skeleton_too_close_penalty", 0.65))
            if delta > 0:
                r -= float(self.rewards_cfg.get("skeleton_too_close_penalty", 0.65)) * 0.5
        elif ideal_min <= nearest_dist <= ideal_max:
            r += float(self.rewards_cfg.get("skeleton_ideal_range_bonus", 0.55))
            if damage_dealt > 0:
                r += float(self.rewards_cfg.get("skeleton_ideal_hit_bonus", 0.4))
            if damage_dealt <= 0:
                r -= float(
                    self.rewards_cfg.get("skeleton_in_range_no_hit_penalty", 0.7)
                )
        elif nearest_dist <= attack_range:
            r += float(self.rewards_cfg.get("skeleton_close_bonus", 0.25))
            if delta > 0:
                r += float(self.rewards_cfg.get("skeleton_facing_approach_bonus", 0.2))
            if damage_dealt <= 0:
                r -= float(
                    self.rewards_cfg.get("skeleton_in_range_no_hit_penalty", 0.85)
                )
        else:
            r -= float(self.rewards_cfg.get("skeleton_far_penalty", 0.7))
            far_coef = float(self.rewards_cfg.get("skeleton_far_dist_coef", 0.5))
            r -= far_coef * max(0.0, nearest_dist - attack_range)
            if facing_align < 0.35:
                r -= float(self.rewards_cfg.get("skeleton_back_to_mob_penalty", 1.0))

        # Stoi w miejscu gdy szkielet daleko — główny problem
        if nearest_dist > must_close:
            if movement < idle_thr:
                r -= float(self.rewards_cfg.get("skeleton_stand_still_penalty", 0.9))
            elif delta <= 0:
                r -= float(self.rewards_cfg.get("skeleton_orbit_penalty", 0.75))
        elif nearest_dist > ideal_max and movement < idle_thr:
            r -= float(self.rewards_cfg.get("skeleton_idle_penalty", 0.6))

        edge_thr = float(self.rewards_cfg.get("skeleton_wall_edge_threshold", 0.65))
        if edge > edge_thr and movement >= idle_thr:
            r -= float(self.rewards_cfg.get("skeleton_wall_penalty", 0.55))

        return r

    def _optimal_range(self, mob_type: str) -> tuple[float, float]:
        ranges = self.rewards_cfg.get("optimal_ranges", {})
        if isinstance(ranges, dict) and mob_type in ranges:
            entry = ranges[mob_type]
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                return float(entry[0]), float(entry[1])
        if mob_type == "SKELETON":
            return 0.5, float(self.rewards_cfg.get("attack_range", 3.0))
        if mob_type == "CREEPER":
            return 2.5, 3.0
        return (
            float(self.rewards_cfg.get("combat_band_min", 2.0)),
            float(self.rewards_cfg.get("combat_band_max", 3.0)),
        )

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

    @staticmethod
    def _relative_bearing_norm(
        ax: float, az: float, mx: float, mz: float, yaw_deg: float
    ) -> float:
        dx = mx - ax
        dz = mz - az
        if dx * dx + dz * dz < 1e-12:
            return 0.5
        bearing = float(np.degrees(np.arctan2(-dx, dz)))
        rel = (bearing - yaw_deg + 180.0) % 360.0 - 180.0
        return float(np.clip((rel + 180.0) / 360.0, 0.0, 1.0))

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

        yaw = float(state.get("agent_yaw", 0.0))
        yaw_n = (yaw % 360.0) / 360.0
        wave_type_n = self._encode_mob_type(state.get("wave_mob_type", ""))

        obs: list[float] = [
            float(state.get("agent_hp", 0)) / self.agent_max_hp,
            np.clip((ax - cx) / radius, -1, 1) * 0.5 + 0.5,
            np.clip((az - cz) / radius, -1, 1) * 0.5 + 0.5,
            yaw_n,
            wave_type_n,
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
            bearing_n = self._relative_bearing_norm(
                ax, az, float(mob["x"]), float(mob["z"]), yaw
            )
            mob_type_n = self._encode_mob_type(mob.get("type", ""))
            obs.extend(
                [
                    np.clip(hp_n, 0, 1),
                    np.clip(dx * 0.5 + 0.5, 0, 1),
                    np.clip(dz * 0.5 + 0.5, 0, 1),
                    dist_n,
                    bearing_n,
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
        self._prev_hp_mock = self.agent_hp

    def close(self) -> None:
        pass

    def reset(self) -> dict[str, Any]:
        self.wave = 0
        self.max_wave = 0
        self.step_num = 0
        self.agent_hp = float(self.cfg["agent"]["max_hp"])
        self.episode_done = False
        self.current_type = "ZOMBIE"
        self._prev_hp_mock = self.agent_hp
        self._spawn_wave()
        return self._state(ok=True, wave_cleared=False, kills=0, damage=0.0)

    def step(self, action: int) -> dict[str, Any]:
        if self.episode_done:
            return self._state(ok=False, error="episode_not_active")

        hp_before = self.agent_hp
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

        self._prev_hp_mock = hp_before
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
            "agent_yaw": 0.0,
            "wave_mob_type": self.current_type,
            "damage_taken": max(0.0, self._prev_hp_mock - self.agent_hp),
            "mobs": [dict(m) for m in self.mobs],
        }
        if error:
            s["error"] = error
        return s
