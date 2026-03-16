"""Episode data export to CSV, JSON, and PNG visualisations.

All functions operate on a single episode dict as produced by
:func:`~engine.simulation.rollout.run_rollout`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray


# ------------------------------------------------------------------
# Tabular / structured exports
# ------------------------------------------------------------------

def export_episode_csv(episode: dict, output_path: str | Path) -> None:
    """Write per-step telemetry to a CSV file.

    Parameters
    ----------
    episode : dict
        Episode dict with a ``steps`` list.
    output_path : str | Path
        Destination CSV file.  Parent directories are created
        automatically.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    steps = episode.get("steps", [])
    if not steps:
        # Write an empty file with headers
        fieldnames = [
            "step", "x", "y", "z", "heading", "action", "reward",
            "risk", "clearance", "mode", "primitive", "time",
        ]
    else:
        # Use the union of all keys across steps, with a stable ordering
        ordered_base = [
            "step", "x", "y", "z", "heading", "action", "reward",
            "risk", "clearance", "mode", "primitive", "time",
        ]
        extra_keys: set[str] = set()
        for s in steps:
            extra_keys.update(s.keys())
        extra_keys -= set(ordered_base)
        fieldnames = ordered_base + sorted(extra_keys)

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for idx, step in enumerate(steps):
            row = {"step": idx}
            row.update(step)
            writer.writerow(row)


def export_episode_json(episode: dict, output_path: str | Path) -> None:
    """Write the full episode dict to a JSON file.

    Parameters
    ----------
    episode : dict
        Episode dict (steps, total_reward, success, etc.).
    output_path : str | Path
        Destination JSON file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Make a JSON-safe copy (convert numpy types, etc.)
    safe = _make_json_safe(episode)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(safe, fh, indent=2, default=str)


# ------------------------------------------------------------------
# Visual exports
# ------------------------------------------------------------------

def export_topdown_png(
    episode: dict,
    dem: NDArray[np.floating],
    transform: Any,
    output_path: str | Path,
) -> None:
    """Render the flight path overlaid on a terrain elevation map.

    Parameters
    ----------
    episode : dict
        Episode dict with a ``steps`` list containing ``x``, ``y`` keys.
    dem : NDArray
        2-D terrain elevation array (rows x cols).
    transform
        Rasterio affine transform mapping pixel (col, row) to map (x, y).
        Used to compute the map extent for ``imshow``.
    output_path : str | Path
        Destination PNG file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    steps = episode.get("steps", [])

    # Compute the map extent from the affine transform
    nrows, ncols = dem.shape
    # transform: (a, b, c, d, e, f) where x = a*col + b*row + c, y = d*col + e*row + f
    left = transform.c
    top = transform.f
    right = left + transform.a * ncols
    bottom = top + transform.e * nrows
    extent = [left, right, bottom, top]

    fig, ax = plt.subplots(figsize=(10, 8))

    # Terrain background
    ax.imshow(
        dem,
        cmap="terrain",
        extent=extent,
        origin="upper",
        alpha=0.8,
    )

    # Flight path
    if steps:
        xs = [float(s.get("x", 0.0)) for s in steps]
        ys = [float(s.get("y", 0.0)) for s in steps]
        risks = [float(s.get("risk", 0.0)) for s in steps]

        # Colour the path by risk level
        points = np.array([xs, ys]).T.reshape(-1, 1, 2)
        if len(points) > 1:
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            from matplotlib.collections import LineCollection

            norm = plt.Normalize(vmin=0, vmax=max(max(risks), 0.01))
            lc = LineCollection(segments, cmap="RdYlGn_r", norm=norm)
            lc.set_array(np.array(risks[:-1]))
            lc.set_linewidth(2)
            ax.add_collection(lc)
            fig.colorbar(lc, ax=ax, label="Risk", shrink=0.7)

        # Start and end markers
        ax.plot(xs[0], ys[0], "go", markersize=10, label="Start", zorder=5)
        ax.plot(xs[-1], ys[-1], "rs", markersize=10, label="End", zorder=5)

    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.set_title("Top-Down Flight Path")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def export_altitude_profile_png(episode: dict, output_path: str | Path) -> None:
    """Plot altitude vs. simulation time and save as PNG.

    Parameters
    ----------
    episode : dict
        Episode dict with ``steps`` containing ``time`` and ``z``.
    output_path : str | Path
        Destination PNG file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    steps = episode.get("steps", [])
    times = [float(s.get("time", float(i))) for i, s in enumerate(steps)]
    altitudes = [float(s.get("z", 0.0)) for s in steps]
    clearances = [float(s.get("clearance", 0.0)) for s in steps]

    fig, ax1 = plt.subplots(figsize=(10, 5))

    ax1.plot(times, altitudes, "b-", linewidth=1.5, label="Altitude (m)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Altitude (m)", color="b")
    ax1.tick_params(axis="y", labelcolor="b")
    ax1.grid(alpha=0.3)

    # Overlay clearance on secondary axis
    if any(c != 0.0 for c in clearances):
        ax2 = ax1.twinx()
        ax2.plot(times, clearances, "g--", linewidth=1.0, alpha=0.7, label="Clearance (m)")
        ax2.set_ylabel("Terrain Clearance (m)", color="g")
        ax2.tick_params(axis="y", labelcolor="g")

    # Mark mode transitions
    prev_mode = None
    for i, s in enumerate(steps):
        mode = s.get("mode", "UNKNOWN")
        if mode != prev_mode and prev_mode is not None:
            ax1.axvline(x=times[i], color="orange", linestyle=":", alpha=0.5)
            ax1.text(
                times[i], ax1.get_ylim()[1] * 0.95, mode,
                fontsize=7, rotation=90, va="top", ha="right", alpha=0.7,
            )
        prev_mode = mode

    ax1.set_title("Altitude Profile")
    ax1.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def export_risk_timeline_png(episode: dict, output_path: str | Path) -> None:
    """Plot risk vs. simulation time and save as PNG.

    Parameters
    ----------
    episode : dict
        Episode dict with ``steps`` containing ``time`` and ``risk``.
    output_path : str | Path
        Destination PNG file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    steps = episode.get("steps", [])
    times = [float(s.get("time", float(i))) for i, s in enumerate(steps)]
    risks = [float(s.get("risk", 0.0)) for s in steps]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(times, risks, alpha=0.3, color="red")
    ax.plot(times, risks, "r-", linewidth=1.2)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Risk")
    ax.set_ylim(bottom=0)
    ax.set_title("Risk Timeline")
    ax.grid(alpha=0.3)

    # Highlight modes with background colour
    mode_colors = {
        "TRANSIT": "#4A90D9",
        "OBSERVE_SETUP": "#F5A623",
        "POPUP_OBSERVE": "#D0021B",
        "EGRESS": "#7ED321",
    }
    prev_mode = None
    span_start = 0.0
    for i, s in enumerate(steps):
        mode = str(s.get("mode", "UNKNOWN"))
        t = times[i]
        if mode != prev_mode:
            if prev_mode is not None and prev_mode in mode_colors:
                ax.axvspan(span_start, t, alpha=0.08,
                           color=mode_colors[prev_mode])
            span_start = t
        prev_mode = mode

    # Final span
    if prev_mode is not None and prev_mode in mode_colors and times:
        ax.axvspan(span_start, times[-1], alpha=0.08,
                   color=mode_colors[prev_mode])

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_json_safe(obj: Any) -> Any:
    """Recursively convert numpy types to native Python types."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj
