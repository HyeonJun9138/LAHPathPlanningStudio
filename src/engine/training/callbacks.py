"""Stable-Baselines3 training callbacks for the terrain path-planning loop.

Provides:

* :class:`CheckpointCallback` -- periodic model snapshots.
* :class:`BestModelCallback` -- saves the model when mean reward improves.
* :class:`MetricsLogger` -- writes custom per-episode metrics to a CSV.
* :class:`PlotCallback` -- renders reward / success / length curves as PNG.
* :class:`NaNDetector` -- halts training when NaN appears in the loss.
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path
from typing import Optional

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback


# ---------------------------------------------------------------------------
# 1. CheckpointCallback
# ---------------------------------------------------------------------------

class CheckpointCallback(BaseCallback):
    """Save the model every *save_freq* timesteps into *checkpoint_dir*.

    File names follow the pattern ``model_<step>.zip``.
    """

    def __init__(
        self,
        save_freq: int = 10_000,
        checkpoint_dir: str = "checkpoints",
        name_prefix: str = "model",
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self.save_freq = save_freq
        self.checkpoint_dir = Path(checkpoint_dir)
        self.name_prefix = name_prefix

    def _init_callback(self) -> None:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        if self.n_calls % self.save_freq == 0:
            path = self.checkpoint_dir / f"{self.name_prefix}_{self.num_timesteps}.zip"
            self.model.save(str(path))
            if self.verbose >= 1:
                print(f"[CheckpointCallback] Saved checkpoint -> {path}")
        return True


# ---------------------------------------------------------------------------
# 2. BestModelCallback
# ---------------------------------------------------------------------------

class BestModelCallback(BaseCallback):
    """Track the rolling mean episode reward and save the model when it improves.

    The monitor wrapper populates ``self.locals["infos"]`` with
    ``episode`` dicts that carry ``"r"`` (episode reward).
    """

    def __init__(
        self,
        save_dir: str = "best_model",
        window: int = 100,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self.save_dir = Path(save_dir)
        self.window = window
        self.episode_rewards: list[float] = []
        self.best_mean_reward: float = -float("inf")

    def _init_callback(self) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        for info in infos:
            ep_info = info.get("episode")
            if ep_info is not None:
                self.episode_rewards.append(float(ep_info["r"]))

        # Only evaluate when we have enough data
        if len(self.episode_rewards) >= self.window:
            recent = self.episode_rewards[-self.window:]
            mean_reward = float(np.mean(recent))
            if mean_reward > self.best_mean_reward:
                self.best_mean_reward = mean_reward
                path = self.save_dir / "best_model.zip"
                self.model.save(str(path))
                if self.verbose >= 1:
                    print(
                        f"[BestModelCallback] New best mean reward "
                        f"{mean_reward:.4f} -> {path}"
                    )
        return True


# ---------------------------------------------------------------------------
# 3. MetricsLogger
# ---------------------------------------------------------------------------

class MetricsLogger(BaseCallback):
    """Log custom per-episode metrics to a CSV file.

    Expected info keys (populated by the environment):
    ``integrated_risk``, ``visible_time``, ``path_length``,
    ``success``.  Missing keys are recorded as empty strings.
    """

    METRIC_KEYS = [
        "integrated_risk",
        "visible_time",
        "path_length",
        "success",
    ]

    def __init__(
        self,
        log_path: str = "metrics.csv",
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self.log_path = Path(log_path)
        self._csv_file = None
        self._writer: Optional[csv.writer] = None
        self._episode_count: int = 0

    def _init_callback(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_file = open(self.log_path, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._csv_file)
        header = ["episode", "timestep", "reward"] + self.METRIC_KEYS
        self._writer.writerow(header)
        self._csv_file.flush()

    def _on_step(self) -> bool:
        infos = self.locals.get("infos", [])
        for info in infos:
            ep_info = info.get("episode")
            if ep_info is not None:
                self._episode_count += 1
                reward = float(ep_info["r"])
                row = [
                    self._episode_count,
                    self.num_timesteps,
                    reward,
                ]
                for key in self.METRIC_KEYS:
                    row.append(info.get(key, ""))
                self._writer.writerow(row)
                self._csv_file.flush()
        return True

    def _on_training_end(self) -> None:
        if self._csv_file is not None:
            self._csv_file.close()
            self._csv_file = None


# ---------------------------------------------------------------------------
# 4. PlotCallback
# ---------------------------------------------------------------------------

class PlotCallback(BaseCallback):
    """Generate reward / success-rate / episode-length plots every *plot_freq* steps.

    Plots are saved as PNG files in *output_dir*.
    """

    def __init__(
        self,
        output_dir: str = "plots",
        plot_freq: int = 10_000,
        window: int = 100,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self.output_dir = Path(output_dir)
        self.plot_freq = plot_freq
        self.window = window
        self.episode_rewards: list[float] = []
        self.episode_lengths: list[int] = []
        self.episode_successes: list[float] = []

    def _init_callback(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        # Collect data from Monitor-wrapped info dicts
        infos = self.locals.get("infos", [])
        for info in infos:
            ep_info = info.get("episode")
            if ep_info is not None:
                self.episode_rewards.append(float(ep_info["r"]))
                self.episode_lengths.append(int(ep_info["l"]))
                # success may come from the environment directly
                self.episode_successes.append(float(info.get("success", 0.0)))

        if self.n_calls % self.plot_freq == 0 and len(self.episode_rewards) > 0:
            self._generate_plots()

        return True

    def _on_training_end(self) -> None:
        if len(self.episode_rewards) > 0:
            self._generate_plots()

    def _generate_plots(self) -> None:
        # Import lazily so matplotlib backend issues don't block import
        from .plots import plot_episode_length, plot_reward_curve, plot_success_rate

        step_tag = self.num_timesteps

        plot_reward_curve(
            self.episode_rewards,
            str(self.output_dir / f"reward_curve_{step_tag}.png"),
            window=self.window,
        )
        plot_success_rate(
            self.episode_successes,
            str(self.output_dir / f"success_rate_{step_tag}.png"),
            window=self.window,
        )
        plot_episode_length(
            self.episode_lengths,
            str(self.output_dir / f"episode_length_{step_tag}.png"),
            window=self.window,
        )
        if self.verbose >= 1:
            print(f"[PlotCallback] Plots saved at step {step_tag}")


# ---------------------------------------------------------------------------
# 5. NaNDetector
# ---------------------------------------------------------------------------

class NaNDetector(BaseCallback):
    """Check for NaN values in losses and stop training if detected.

    Inspects the ``self.locals`` dict for known SB3 loss keys
    (``loss``, ``pg_loss``, ``value_loss``, ``entropy_loss``).  Also
    scans model parameters for NaN / Inf.
    """

    LOSS_KEYS = ["loss", "pg_loss", "value_loss", "entropy_loss"]

    def __init__(self, verbose: int = 0, check_params_every: int = 500) -> None:
        super().__init__(verbose)
        self.check_params_every = check_params_every

    def _on_step(self) -> bool:
        # --- Check loss scalars in locals ---------------------------------
        for key in self.LOSS_KEYS:
            val = self.locals.get(key)
            if val is not None:
                if isinstance(val, (float, int)):
                    if math.isnan(val) or math.isinf(val):
                        print(
                            f"[NaNDetector] {key}={val} detected at "
                            f"step {self.num_timesteps}. Stopping training."
                        )
                        return False
                else:
                    # Could be a tensor
                    try:
                        import torch
                        if isinstance(val, torch.Tensor):
                            if torch.isnan(val).any() or torch.isinf(val).any():
                                print(
                                    f"[NaNDetector] {key} contains NaN/Inf at "
                                    f"step {self.num_timesteps}. Stopping training."
                                )
                                return False
                    except Exception:
                        pass

        # --- Periodically scan model parameters ---------------------------
        if self.n_calls % self.check_params_every == 0:
            import torch
            for name, param in self.model.policy.named_parameters():
                if param.data is not None and (
                    torch.isnan(param.data).any() or torch.isinf(param.data).any()
                ):
                    print(
                        f"[NaNDetector] Parameter '{name}' contains NaN/Inf "
                        f"at step {self.num_timesteps}. Stopping training."
                    )
                    return False

        return True
