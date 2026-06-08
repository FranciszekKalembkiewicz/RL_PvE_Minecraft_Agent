"""PPO training for Minecraft Wave Arena."""

import os
from pathlib import Path

import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import (
    BaseCallback,
    CallbackList,
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.monitor import Monitor

from env.arena_mc_env import ArenaMcEnv
from env.bridge_client import load_config


def load_training_config() -> dict:
    root = Path(__file__).resolve().parent
    with open(root / "configs" / "waves.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class MaxWaveCurriculumCallback(BaseCallback):
    """Podnosi max_wave_train gdy średnia max_wave na eval rośnie."""

    def __init__(self, eval_callback: EvalCallback, threshold: float = 0.8, verbose: int = 1):
        super().__init__(verbose)
        self.eval_callback = eval_callback
        self.threshold = threshold
        self._last_promotion_step = 0

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        if self.eval_callback.last_mean_reward is None:
            return
        infos = getattr(self.eval_callback, "eval_episode_rewards", None)
        if self.num_timesteps - self._last_promotion_step < 50_000:
            return
        train_env = self.training_env
        if hasattr(train_env, "envs"):
            for wrapped in train_env.envs:
                env = wrapped
                while hasattr(env, "env"):
                    env = env.env
                if isinstance(env, ArenaMcEnv) and env.max_wave_train < 10:
                    env.max_wave_train += 1
                    self._last_promotion_step = self.num_timesteps
                    if self.verbose:
                        print(f"[Curriculum] max_wave_train -> {env.max_wave_train}")
                    break


def make_env(cfg: dict, mock: bool) -> callable:
    max_wave = int(cfg["training"].get("max_wave_train", 1))

    def _init():
        env = ArenaMcEnv(mock=mock, max_wave_train=max_wave)
        return Monitor(env)

    return _init


def train():
    cfg = load_training_config()
    train_cfg = cfg["training"]
    mock = os.environ.get("ARENA_MOCK", "0") == "1"

    save_dir = Path("checkpoints")
    log_dir = Path("logs")
    save_dir.mkdir(exist_ok=True)
    log_dir.mkdir(exist_ok=True)

    max_wave = int(train_cfg.get("max_wave_train", 1))
    print(f"\n{'='*50}")
    print(f"  Trening Wave Arena | max_wave_train={max_wave}")
    print(f"  Mock: {mock} | timesteps: {train_cfg['total_timesteps']:,}")
    print(f"{'='*50}\n")

    env = Monitor(ArenaMcEnv(mock=mock, max_wave_train=max_wave))
    eval_env = Monitor(ArenaMcEnv(mock=mock, max_wave_train=max_wave))

    checkpoint_callback = CheckpointCallback(
        save_freq=max(int(train_cfg.get("checkpoint_freq", 25000)), 1),
        save_path=str(save_dir / "snapshots"),
        name_prefix="ppo_wave",
        verbose=1,
    )

    if mock:
        eval_callback = EvalCallback(
            eval_env,
            best_model_save_path=str(save_dir / "best"),
            log_path=str(log_dir / "eval"),
            eval_freq=max(int(train_cfg.get("eval_freq", 5000)), 1),
            n_eval_episodes=3,
            deterministic=True,
            render=False,
            verbose=1,
        )
        callbacks = CallbackList([eval_callback, checkpoint_callback])
    else:
        print(
            "EvalCallback wyłączony dla Minecraft (jeden most TCP na raz).\n"
            "Ewaluacja: python evaluate.py po treningu.\n"
        )
        callbacks = CallbackList([checkpoint_callback])
        eval_env.close()
        eval_env = None

    resume_path = save_dir / "best" / "best_model.zip"
    force_new = os.environ.get("FORCE_NEW_MODEL", "0") == "1"
    ppo_params = {
        "n_steps": 512 if mock else 256,
        "batch_size": int(os.environ.get("PPO_BATCH_SIZE", "64")),
        "n_epochs": 10,
        "learning_rate": 3e-4,
        "clip_range": 0.2,
        "ent_coef": 0.02,
        "gamma": float(os.environ.get("PPO_GAMMA", "0.99")),
        "gae_lambda": 0.95,
        "tensorboard_log": str(log_dir),
        "verbose": 1,
    }
    print(
        f"PPO params: gamma={ppo_params['gamma']} "
        f"batch_size={ppo_params['batch_size']} n_steps={ppo_params['n_steps']}"
    )

    if resume_path.exists() and not force_new:
        print(f"Wznawianie: {resume_path}\n")
        try:
            model = PPO.load(str(resume_path), env=env, **ppo_params)
        except ValueError as e:
            msg = str(e)
            if "Observation spaces do not match" in msg or "Action spaces do not match" in msg:
                print(
                    "Checkpoint niepasujący do aktualnego env (inna obserwacja/akcje). "
                    "Start nowego modelu PPO.\n"
                )
                model = PPO(policy="MlpPolicy", env=env, **ppo_params)
            else:
                raise
    else:
        if force_new:
            print("FORCE_NEW_MODEL=1 -> pomijam wznawianie checkpointu.\n")
        print("Nowy model PPO...\n")
        model = PPO(policy="MlpPolicy", env=env, **ppo_params)

    print("TensorBoard: tensorboard --logdir logs\n")

    total_ts = int(os.environ.get("TRAIN_TIMESTEPS", train_cfg["total_timesteps"]))
    model.learn(
        total_timesteps=total_ts,
        callback=callbacks,
        reset_num_timesteps=False,
        progress_bar=True,
    )

    final_path = save_dir / "final_wave"
    model.save(str(final_path))
    print(f"\nModel zapisany: {final_path}.zip")

    env.close()
    if eval_env is not None:
        eval_env.close()


if __name__ == "__main__":
    train()
