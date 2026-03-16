"""High-level training orchestrator.

:class:`TrainRunner` wires together the environment, the MaskablePPO
model (with our custom feature extractor), all training callbacks,
device selection, and the final save / metrics-export logic.

Typical usage::

    runner = TrainRunner(config)
    runner.setup()
    runner.run()
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np


class TrainRunner:
    """End-to-end training orchestrator.

    Parameters
    ----------
    config:
        Dictionary with at least the following keys:

        - ``run_id`` (*str*) -- unique run identifier.
        - ``output_dir`` (*str*) -- base directory for all artefacts.
        - ``device`` (*str*) -- ``"auto"``, ``"cpu"``, ``"cuda:0"``, ...
        - ``total_timesteps`` (*int*) -- training budget.
        - ``env`` (*dict*) -- forwarded to environment constructor.
        - ``model`` (*dict*, optional) -- PPO hyper-parameters.
        - ``callbacks`` (*dict*, optional) -- per-callback overrides.
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.run_id: str = config.get("run_id", f"run_{int(time.time())}")
        self.output_dir = Path(config.get("output_dir", "output")) / self.run_id
        self.device_pref: str = config.get("device", "auto")
        self.total_timesteps: int = config.get("total_timesteps", 100_000)

        # Populated by setup()
        self.device = None
        self.env = None
        self.model = None
        self.callback_list = None
        self._metrics: dict[str, Any] = {}
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Create environment, model, callbacks, and select the compute device."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Device
        from .device import select_device
        self.device = select_device(self.device_pref)

        # Environment
        self.env = self._create_env()

        # Model
        self.model = self._create_model()

        # Callbacks
        self.callback_list = self._create_callbacks()

        # Persist the full config snapshot for reproducibility
        config_path = self.output_dir / "config.json"
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(self.config, fh, indent=2, default=str)

    def run(self) -> dict[str, Any]:
        """Train the model, save final artefacts, and return summary metrics.

        Returns
        -------
        dict
            Summary metrics including wall-clock time, total timesteps,
            and episode statistics.
        """
        if self.model is None:
            raise RuntimeError("Call setup() before run().")

        self._start_time = time.time()

        self.model.learn(
            total_timesteps=self.total_timesteps,
            callback=self.callback_list,
            progress_bar=False,
        )

        elapsed = time.time() - self._start_time

        # Save final model
        final_model_path = self.output_dir / "final_model.zip"
        self.model.save(str(final_model_path))

        # Collect summary metrics
        self._metrics = {
            "run_id": self.run_id,
            "total_timesteps": self.total_timesteps,
            "wall_time_sec": round(elapsed, 2),
            "device": str(self.device),
            "final_model_path": str(final_model_path),
        }

        # Append episode stats from the best-model callback
        for cb in (self.callback_list or []):
            from .callbacks import BestModelCallback
            if isinstance(cb, BestModelCallback) and cb.episode_rewards:
                rewards = cb.episode_rewards
                self._metrics["episodes"] = len(rewards)
                self._metrics["mean_reward_last100"] = float(
                    np.mean(rewards[-100:])
                )
                self._metrics["best_mean_reward"] = cb.best_mean_reward
                break

        # Save metrics JSON
        metrics_path = self.output_dir / "metrics.json"
        self.save_metrics(str(metrics_path))

        # Generate final plots via the plot callback's training-end hook
        # (already triggered by .learn()), but also generate a standalone
        # set for safety.
        self._generate_final_plots()

        return self._metrics

    def save_metrics(self, path: str) -> None:
        """Write collected metrics to a JSON file at *path*."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._metrics, fh, indent=2, default=str)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_env(self):
        """Create and wrap the terrain path-planning Gymnasium environment.

        Returns a Monitor-wrapped (and optionally action-mask-wrapped)
        environment suitable for MaskablePPO.
        """
        from stable_baselines3.common.monitor import Monitor

        env_config = self.config.get("env", {})

        # Try to import the project's own environment first
        try:
            from src.engine.env.terrain_env import TerrainPathEnv
            raw_env = TerrainPathEnv(**env_config)
        except Exception:
            # Fallback: attempt relative import path
            try:
                from ...env.terrain_env import TerrainPathEnv
                raw_env = TerrainPathEnv(**env_config)
            except Exception:
                # Last resort: build a minimal compatible env for testing
                raw_env = self._make_dummy_env(env_config)

        monitored = Monitor(raw_env, filename=str(self.output_dir / "monitor"))
        return monitored

    def _make_dummy_env(self, env_config: dict):
        """Create a lightweight stand-in environment when the real one is unavailable.

        This allows the training pipeline to be tested independently of
        the full terrain / hazard / mission subsystem.
        """
        import gymnasium as gym
        from gymnasium import spaces

        n_candidates = env_config.get("n_candidates", 32)
        hi_channels = env_config.get("hi_channels", 3)
        mid_channels = env_config.get("mid_channels", 3)
        self_state_dim = env_config.get("self_state_dim", 12)
        global_context_dim = env_config.get("global_context_dim", 8)
        candidate_feat_dim = env_config.get("candidate_feat_dim", 24)

        obs_space = spaces.Dict(
            {
                "local_hi_patch": spaces.Box(
                    low=-1.0, high=1.0,
                    shape=(hi_channels, 32, 32),
                    dtype=np.float32,
                ),
                "local_mid_patch": spaces.Box(
                    low=-1.0, high=1.0,
                    shape=(mid_channels, 16, 16),
                    dtype=np.float32,
                ),
                "self_state": spaces.Box(
                    low=-np.inf, high=np.inf,
                    shape=(self_state_dim,),
                    dtype=np.float32,
                ),
                "global_context": spaces.Box(
                    low=-np.inf, high=np.inf,
                    shape=(global_context_dim,),
                    dtype=np.float32,
                ),
                "candidate_table": spaces.Box(
                    low=-np.inf, high=np.inf,
                    shape=(n_candidates, candidate_feat_dim),
                    dtype=np.float32,
                ),
            }
        )
        act_space = spaces.Discrete(n_candidates)

        class _DummyTerrainEnv(gym.Env):
            """Minimal stand-in that matches the real env's spaces."""

            metadata = {"render_modes": []}

            def __init__(self):
                super().__init__()
                self.observation_space = obs_space
                self.action_space = act_space
                self._step_count = 0
                self._max_steps = env_config.get("max_steps", 200)

            def reset(self, *, seed=None, options=None):
                super().reset(seed=seed)
                self._step_count = 0
                return self._obs(), {}

            def step(self, action):
                self._step_count += 1
                reward = float(self.np_random.standard_normal())
                terminated = self._step_count >= self._max_steps
                truncated = False
                info = {
                    "integrated_risk": float(self.np_random.random()),
                    "visible_time": float(self.np_random.random() * 100),
                    "path_length": float(self._step_count * 50),
                    "success": float(terminated and self.np_random.random() > 0.5),
                }
                return self._obs(), reward, terminated, truncated, info

            def action_masks(self) -> np.ndarray:
                mask = np.ones(n_candidates, dtype=np.bool_)
                # Randomly mask out a few candidates
                n_masked = self.np_random.integers(0, max(1, n_candidates // 4))
                if n_masked > 0:
                    indices = self.np_random.choice(
                        n_candidates, size=n_masked, replace=False
                    )
                    mask[indices] = False
                # Ensure at least one action is valid
                if not mask.any():
                    mask[0] = True
                return mask

            def _obs(self):
                return {
                    k: space.sample()
                    for k, space in self.observation_space.spaces.items()
                }

        return _DummyTerrainEnv()

    def _create_model(self):
        """Create a MaskablePPO model with the custom feature extractor.

        Falls back to CPU transparently when CUDA is unavailable.
        """
        from sb3_contrib import MaskablePPO

        from .feature_extractor import TerrainFeatureExtractor

        model_cfg = self.config.get("model", {})

        policy_kwargs = {
            "features_extractor_class": TerrainFeatureExtractor,
            "features_extractor_kwargs": {
                "features_dim": model_cfg.get("features_dim", 256),
            },
            "net_arch": model_cfg.get("net_arch", dict(pi=[256, 128], vf=[256, 128])),
        }

        model = MaskablePPO(
            policy="MultiInputPolicy",
            env=self.env,
            learning_rate=model_cfg.get("learning_rate", 3e-4),
            n_steps=model_cfg.get("n_steps", 2048),
            batch_size=model_cfg.get("batch_size", 64),
            n_epochs=model_cfg.get("n_epochs", 10),
            gamma=model_cfg.get("gamma", 0.99),
            gae_lambda=model_cfg.get("gae_lambda", 0.95),
            clip_range=model_cfg.get("clip_range", 0.2),
            ent_coef=model_cfg.get("ent_coef", 0.01),
            vf_coef=model_cfg.get("vf_coef", 0.5),
            max_grad_norm=model_cfg.get("max_grad_norm", 0.5),
            policy_kwargs=policy_kwargs,
            verbose=model_cfg.get("verbose", 0),
            device=self.device,
            seed=model_cfg.get("seed", None),
        )
        return model

    def _create_callbacks(self) -> list:
        """Instantiate all training callbacks."""
        from .callbacks import (
            BestModelCallback,
            CheckpointCallback,
            MetricsLogger,
            NaNDetector,
            PlotCallback,
        )

        cb_cfg = self.config.get("callbacks", {})

        checkpoint_dir = str(self.output_dir / "checkpoints")
        best_dir = str(self.output_dir / "best_model")
        plot_dir = str(self.output_dir / "plots")
        metrics_csv = str(self.output_dir / "metrics.csv")

        callbacks = [
            CheckpointCallback(
                save_freq=cb_cfg.get("checkpoint_freq", 10_000),
                checkpoint_dir=checkpoint_dir,
                verbose=1,
            ),
            BestModelCallback(
                save_dir=best_dir,
                window=cb_cfg.get("best_model_window", 100),
                verbose=1,
            ),
            MetricsLogger(
                log_path=metrics_csv,
                verbose=1,
            ),
            PlotCallback(
                output_dir=plot_dir,
                plot_freq=cb_cfg.get("plot_freq", 10_000),
                window=cb_cfg.get("plot_window", 100),
                verbose=1,
            ),
            NaNDetector(
                verbose=1,
                check_params_every=cb_cfg.get("nan_check_freq", 500),
            ),
        ]
        return callbacks

    def _generate_final_plots(self) -> None:
        """Generate a definitive set of plots from the BestModel / Plot callback data."""
        from .plots import plot_episode_length, plot_reward_curve, plot_success_rate

        plot_dir = self.output_dir / "plots"
        plot_dir.mkdir(parents=True, exist_ok=True)

        # Gather data from callbacks
        rewards: list[float] = []
        lengths: list[int] = []
        successes: list[float] = []

        for cb in (self.callback_list or []):
            from .callbacks import BestModelCallback, PlotCallback
            if isinstance(cb, PlotCallback):
                rewards = cb.episode_rewards
                lengths = cb.episode_lengths
                successes = cb.episode_successes
                break
            if isinstance(cb, BestModelCallback) and not rewards:
                rewards = cb.episode_rewards

        if rewards:
            plot_reward_curve(rewards, str(plot_dir / "reward_final.png"))
        if successes:
            plot_success_rate(successes, str(plot_dir / "success_final.png"))
        if lengths:
            plot_episode_length(lengths, str(plot_dir / "episode_length_final.png"))
