"""Publication-quality training plot generators.

Each function accepts raw metric sequences, applies optional rolling-window
smoothing, and saves a self-contained PNG to *output_path*.
Matplotlib is configured with the ``Agg`` backend so the functions work in
headless / CI environments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")  # noqa: E402 -- must be set before pyplot import
import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rolling_mean(values: Sequence[float], window: int) -> np.ndarray:
    """Compute a causal rolling mean with minimum 1-sample window at the edges."""
    arr = np.asarray(values, dtype=np.float64)
    if len(arr) == 0:
        return arr
    cumsum = np.cumsum(arr)
    rolling = np.empty_like(arr)
    for i in range(len(arr)):
        start = max(0, i - window + 1)
        rolling[i] = (cumsum[i] - (cumsum[start - 1] if start > 0 else 0.0)) / (i - start + 1)
    return rolling


def _setup_axes(title: str, xlabel: str, ylabel: str) -> tuple:
    """Create a clean figure with consistent styling."""
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, alpha=0.3, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig, ax


def _save(fig, output_path: str) -> None:
    """Save figure and close to free memory."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plot_reward_curve(
    rewards: Sequence[float],
    output_path: str,
    window: int = 100,
) -> None:
    """Plot smoothed episode reward over training episodes.

    Parameters
    ----------
    rewards:
        Per-episode cumulative rewards.
    output_path:
        Destination PNG path.
    window:
        Rolling-average window size.
    """
    if len(rewards) == 0:
        return
    fig, ax = _setup_axes("Episode Reward", "Episode", "Reward")
    episodes = np.arange(1, len(rewards) + 1)
    ax.plot(episodes, rewards, alpha=0.25, linewidth=0.5, color="#93c5fd", label="Raw")
    smoothed = _rolling_mean(rewards, window)
    ax.plot(episodes, smoothed, linewidth=2.0, color="#2563eb", label=f"Mean ({window})")
    ax.legend(loc="lower right", fontsize=9, framealpha=0.8)
    _save(fig, output_path)


def plot_success_rate(
    successes: Sequence[float],
    output_path: str,
    window: int = 100,
) -> None:
    """Plot rolling success rate over training episodes.

    Parameters
    ----------
    successes:
        Per-episode binary success indicator (0.0 or 1.0).
    output_path:
        Destination PNG path.
    window:
        Rolling-average window size.
    """
    if len(successes) == 0:
        return
    fig, ax = _setup_axes("Success Rate", "Episode", "Success Rate")
    episodes = np.arange(1, len(successes) + 1)
    smoothed = _rolling_mean(successes, window)
    ax.fill_between(episodes, 0, smoothed, alpha=0.15, color="#22c55e")
    ax.plot(episodes, smoothed, linewidth=2.0, color="#16a34a", label=f"Rolling ({window})")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.8)
    _save(fig, output_path)


def plot_loss_curve(
    losses: Sequence[float],
    output_path: str,
) -> None:
    """Plot training loss (policy or value) over optimisation steps.

    Parameters
    ----------
    losses:
        Per-update loss values.
    output_path:
        Destination PNG path.
    """
    if len(losses) == 0:
        return
    fig, ax = _setup_axes("Training Loss", "Update Step", "Loss")
    steps = np.arange(1, len(losses) + 1)
    ax.plot(steps, losses, linewidth=1.0, color="#ef4444", alpha=0.6, label="Loss")
    # Add smoothed overlay when enough data
    if len(losses) > 20:
        smoothed = _rolling_mean(losses, min(50, len(losses) // 4))
        ax.plot(steps, smoothed, linewidth=2.0, color="#991b1b", label="Smoothed")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
    _save(fig, output_path)


def plot_episode_length(
    lengths: Sequence[float],
    output_path: str,
    window: int = 100,
) -> None:
    """Plot episode length (timesteps) over training episodes.

    Parameters
    ----------
    lengths:
        Per-episode step counts.
    output_path:
        Destination PNG path.
    window:
        Rolling-average window size.
    """
    if len(lengths) == 0:
        return
    fig, ax = _setup_axes("Episode Length", "Episode", "Steps")
    episodes = np.arange(1, len(lengths) + 1)
    ax.plot(episodes, lengths, alpha=0.25, linewidth=0.5, color="#fdba74", label="Raw")
    smoothed = _rolling_mean(lengths, window)
    ax.plot(episodes, smoothed, linewidth=2.0, color="#ea580c", label=f"Mean ({window})")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.8)
    _save(fig, output_path)
