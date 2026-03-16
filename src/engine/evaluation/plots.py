"""Matplotlib-based comparison plots for evaluation results.

All functions accept a list of run-result dicts and write a PNG file
to the specified output path.  Each run dict should contain at least a
``run_id`` (or ``name``) key and the relevant metric values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for headless rendering
import matplotlib.pyplot as plt
import numpy as np


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _labels(results: list[dict]) -> list[str]:
    """Extract display labels from run dicts."""
    return [
        str(r.get("run_id", r.get("name", r.get("label", f"run_{i}"))))
        for i, r in enumerate(results)
    ]


def _ensure_dir(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _save_and_close(fig: plt.Figure, output_path: str | Path) -> None:
    _ensure_dir(output_path)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------
# Public plot functions
# ------------------------------------------------------------------

def plot_success_rate_bar(results: list[dict], output_path: str | Path) -> None:
    """Bar chart comparing success rates across runs.

    Parameters
    ----------
    results : list[dict]
        Each dict should have ``success_rate`` (0-1).
    output_path : str | Path
        Destination PNG file.
    """
    labels = _labels(results)
    values = [float(r.get("success_rate", 0.0)) for r in results]

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color="#4A90D9", edgecolor="white", linewidth=0.5)

    # Annotate bars with percentage
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + 0.01,
            f"{val:.1%}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Success Rate")
    ax.set_ylim(0, 1.1)
    ax.set_title("Success Rate Comparison")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _save_and_close(fig, output_path)


def plot_risk_boxplot(results: list[dict], output_path: str | Path) -> None:
    """Box plot of per-episode risk distributions for each run.

    Parameters
    ----------
    results : list[dict]
        Each dict should contain an ``episodes`` list where each episode
        has a ``mean_risk`` key.  If episodes are missing, uses the
        top-level ``mean_risk`` as a single data point.
    output_path : str | Path
        Destination PNG file.
    """
    labels = _labels(results)
    data: list[list[float]] = []

    for r in results:
        episodes = r.get("episodes", [])
        if episodes:
            risks = [float(ep.get("mean_risk", 0.0)) for ep in episodes]
        else:
            risks = [float(r.get("mean_risk", 0.0))]
        data.append(risks)

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 5))
    bp = ax.boxplot(data, labels=labels, patch_artist=True)

    for patch in bp["boxes"]:
        patch.set_facecolor("#F5A623")
        patch.set_alpha(0.7)

    ax.set_ylabel("Mean Risk per Episode")
    ax.set_title("Risk Distribution Comparison")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=30, ha="right", fontsize=9)
    fig.tight_layout()
    _save_and_close(fig, output_path)


def plot_path_length_boxplot(results: list[dict], output_path: str | Path) -> None:
    """Box plot of per-episode path lengths for each run.

    Parameters
    ----------
    results : list[dict]
        Each dict should contain ``episodes`` with ``path_length``.
    output_path : str | Path
        Destination PNG file.
    """
    labels = _labels(results)
    data: list[list[float]] = []

    for r in results:
        episodes = r.get("episodes", [])
        if episodes:
            lengths = [float(ep.get("path_length", 0.0)) for ep in episodes]
        else:
            lengths = [float(r.get("mean_path_length", 0.0))]
        data.append(lengths)

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.2), 5))
    bp = ax.boxplot(data, labels=labels, patch_artist=True)

    for patch in bp["boxes"]:
        patch.set_facecolor("#7ED321")
        patch.set_alpha(0.7)

    ax.set_ylabel("Path Length (m)")
    ax.set_title("Path Length Distribution Comparison")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=30, ha="right", fontsize=9)
    fig.tight_layout()
    _save_and_close(fig, output_path)


def plot_risk_vs_path_scatter(results: list[dict], output_path: str | Path) -> None:
    """Scatter plot of mean risk vs. mean path length for each run.

    Each run is plotted as a single point.  Good policies appear in the
    lower-left (low risk, short path).

    Parameters
    ----------
    results : list[dict]
        Each dict should have ``mean_risk`` and ``mean_path_length``.
    output_path : str | Path
        Destination PNG file.
    """
    labels = _labels(results)
    risks = [float(r.get("mean_risk", 0.0)) for r in results]
    lengths = [float(r.get("mean_path_length", 0.0)) for r in results]

    fig, ax = plt.subplots(figsize=(7, 6))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(labels), 1)))

    for i, (lbl, risk, length) in enumerate(zip(labels, risks, lengths)):
        ax.scatter(length, risk, color=colors[i % len(colors)], s=80, zorder=3)
        ax.annotate(
            lbl,
            (length, risk),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=8,
        )

    ax.set_xlabel("Mean Path Length (m)")
    ax.set_ylabel("Mean Risk")
    ax.set_title("Risk vs. Path Length")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    _save_and_close(fig, output_path)


def plot_latency_bar(results: list[dict], output_path: str | Path) -> None:
    """Grouped bar chart of inference latency (mean, p95, p99).

    Parameters
    ----------
    results : list[dict]
        Each dict should have a ``latency`` sub-dict with keys ``mean``,
        ``p95``, ``p99`` (seconds).  Runs without latency data are
        silently skipped.
    output_path : str | Path
        Destination PNG file.
    """
    labels: list[str] = []
    means: list[float] = []
    p95s: list[float] = []
    p99s: list[float] = []

    for i, r in enumerate(results):
        lat = r.get("latency")
        if lat is None:
            continue
        labels.append(str(r.get("run_id", r.get("name", f"run_{i}"))))
        # Convert to milliseconds for readability
        means.append(float(lat.get("mean", 0.0)) * 1000.0)
        p95s.append(float(lat.get("p95", 0.0)) * 1000.0)
        p99s.append(float(lat.get("p99", 0.0)) * 1000.0)

    if not labels:
        # Nothing to plot -- write a placeholder
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No latency data available",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        ax.set_axis_off()
        _save_and_close(fig, output_path)
        return

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.5), 5))
    ax.bar(x - width, means, width, label="Mean", color="#4A90D9")
    ax.bar(x, p95s, width, label="p95", color="#F5A623")
    ax.bar(x + width, p99s, width, label="p99", color="#D0021B")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Inference Latency Comparison")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    _save_and_close(fig, output_path)


def plot_terrain_split_heatmap(results: list[dict], output_path: str | Path) -> None:
    """Heatmap of metric performance split by terrain type.

    Parameters
    ----------
    results : list[dict]
        Each dict should have ``terrain_splits``, a dict mapping
        terrain names to metric sub-dicts (e.g.
        ``{"Hongik": {"success_rate": 0.8, ...}, ...}``).
        Alternatively, if each run has a ``terrain_id`` and a
        flat metric set, the function will group runs by terrain.
    output_path : str | Path
        Destination PNG file.
    """
    # Strategy 1: runs with explicit terrain_splits
    has_splits = any("terrain_splits" in r for r in results)

    if has_splits:
        _plot_terrain_split_from_splits(results, output_path)
    else:
        # Strategy 2: group runs by terrain_id
        _plot_terrain_split_from_groups(results, output_path)


def _plot_terrain_split_from_splits(
    results: list[dict], output_path: str | Path
) -> None:
    """Build heatmap when each run carries a ``terrain_splits`` dict."""
    labels = _labels(results)

    # Collect all terrain names and metrics
    terrains: set[str] = set()
    metrics: set[str] = set()
    for r in results:
        splits = r.get("terrain_splits", {})
        for terrain, mdict in splits.items():
            terrains.add(terrain)
            for k, v in mdict.items():
                if isinstance(v, (int, float)):
                    metrics.add(k)

    terrain_list = sorted(terrains)
    metric_list = sorted(metrics)

    if not terrain_list or not metric_list:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No terrain split data",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        ax.set_axis_off()
        _save_and_close(fig, output_path)
        return

    # Use success_rate as the primary metric for the heatmap
    primary_metric = "success_rate" if "success_rate" in metric_list else metric_list[0]

    # Build matrix: rows = runs, cols = terrains
    matrix = np.zeros((len(labels), len(terrain_list)))
    for i, r in enumerate(results):
        splits = r.get("terrain_splits", {})
        for j, t in enumerate(terrain_list):
            matrix[i, j] = float(splits.get(t, {}).get(primary_metric, 0.0))

    fig, ax = plt.subplots(figsize=(max(6, len(terrain_list) * 1.5),
                                     max(4, len(labels) * 0.8)))
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(np.arange(len(terrain_list)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(terrain_list, fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)

    # Annotate cells
    for i in range(len(labels)):
        for j in range(len(terrain_list)):
            ax.text(j, i, f"{matrix[i, j]:.2f}",
                    ha="center", va="center", fontsize=8,
                    color="white" if matrix[i, j] < 0.5 else "black")

    ax.set_title(f"Terrain Split: {primary_metric}")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    _save_and_close(fig, output_path)


def _plot_terrain_split_from_groups(
    results: list[dict], output_path: str | Path
) -> None:
    """Build heatmap by grouping runs that share the same run label but
    have different ``terrain_id`` values.  Falls back to a single-row
    heatmap if no grouping is possible."""
    from collections import defaultdict

    groups: dict[str, dict[str, float]] = defaultdict(dict)
    run_ids: set[str] = set()
    terrain_ids: set[str] = set()

    for r in results:
        rid = str(r.get("run_id", r.get("name", "unknown")))
        tid = str(r.get("terrain_id", "default"))
        run_ids.add(rid)
        terrain_ids.add(tid)
        groups[(rid, tid)] = float(r.get("success_rate", 0.0))

    run_list = sorted(run_ids)
    terrain_list = sorted(terrain_ids)

    matrix = np.zeros((len(run_list), len(terrain_list)))
    for i, rid in enumerate(run_list):
        for j, tid in enumerate(terrain_list):
            matrix[i, j] = groups.get((rid, tid), 0.0)

    fig, ax = plt.subplots(figsize=(max(6, len(terrain_list) * 1.5),
                                     max(4, len(run_list) * 0.8)))
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(np.arange(len(terrain_list)))
    ax.set_yticks(np.arange(len(run_list)))
    ax.set_xticklabels(terrain_list, fontsize=9)
    ax.set_yticklabels(run_list, fontsize=9)

    for i in range(len(run_list)):
        for j in range(len(terrain_list)):
            ax.text(j, i, f"{matrix[i, j]:.2f}",
                    ha="center", va="center", fontsize=8,
                    color="white" if matrix[i, j] < 0.5 else "black")

    ax.set_title("Terrain Split: success_rate")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    _save_and_close(fig, output_path)
