"""Standard report visualisation functions.

All functions produce PNG files via matplotlib and save them to the
specified ``output_path``.  They are designed to be called from the
report generation pipeline or interactively during experiment analysis.

Each function returns the *output_path* it wrote so callers can chain
the result into an artifact record.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # non-interactive backend — safe for headless servers

import matplotlib.pyplot as plt
import numpy as np

# -- shared styling --------------------------------------------------------

_STYLE: dict[str, Any] = {
    "figure.facecolor": "#fafafa",
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#d2d2d7",
    "axes.grid": True,
    "grid.color": "#e5e5ea",
    "grid.linewidth": 0.6,
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
}

# Colour palette — Apple-inspired blues / teals
_COLORS = [
    "#0071e3",  # blue
    "#34c759",  # green
    "#ff9500",  # orange
    "#af52de",  # purple
    "#ff3b30",  # red
    "#5ac8fa",  # teal
    "#ff2d55",  # pink
    "#ffcc00",  # yellow
]


def _ensure_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# 1. Bar chart comparing a metric across runs
# ------------------------------------------------------------------

def plot_run_comparison_bar(
    run_results: list[dict],
    metric: str,
    output_path: str,
) -> str:
    """Horizontal bar chart comparing *metric* across multiple runs.

    Parameters
    ----------
    run_results : list[dict]
        Each dict must contain at least ``"run_id"`` (str) and a key
        matching *metric* (float).  Optional ``"label"`` overrides the
        bar label.
    metric : str
        The key to read from each result dict.
    output_path : str
        Destination PNG file path.

    Returns
    -------
    str
        The written *output_path*.
    """
    _ensure_dir(output_path)

    labels: list[str] = []
    values: list[float] = []
    for r in run_results:
        lbl = r.get("label", r.get("run_id", "?"))
        if len(lbl) > 16:
            lbl = lbl[:14] + ".."
        labels.append(lbl)
        values.append(float(r.get(metric, 0.0)))

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(7, max(2.5, 0.5 * len(labels))))
        y_pos = np.arange(len(labels))
        colors = [_COLORS[i % len(_COLORS)] for i in range(len(labels))]
        bars = ax.barh(y_pos, values, color=colors, height=0.55, edgecolor="white", linewidth=0.5)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel(metric)
        ax.set_title(f"Run Comparison — {metric}")

        # Value labels on bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + 0.01 * max(abs(v) for v in values) if values else 0,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.4g}",
                va="center",
                fontsize=8,
                color="#1d1d1f",
            )

        fig.savefig(output_path)
        plt.close(fig)

    return output_path


# ------------------------------------------------------------------
# 2. Time-series / step-series line plot for a single metric
# ------------------------------------------------------------------

def plot_metric_timeline(
    metrics: list[dict],
    metric_name: str,
    output_path: str,
) -> str:
    """Line chart of *metric_name* over steps (or recording order).

    Parameters
    ----------
    metrics : list[dict]
        Metric records, each with ``"name"``, ``"value"``, and
        optionally ``"step"`` and ``"run_id"``.  Only rows whose
        ``"name"`` matches *metric_name* are plotted.
    metric_name : str
        The metric to filter and plot.
    output_path : str
        Destination PNG path.

    Returns
    -------
    str
        The written *output_path*.
    """
    _ensure_dir(output_path)

    # Group by run_id (or lump into a single series)
    series: dict[str, tuple[list[float], list[float]]] = {}
    idx_counter: dict[str, int] = {}
    for m in metrics:
        if m.get("name") != metric_name:
            continue
        rid = m.get("run_id", "default")
        if rid not in series:
            series[rid] = ([], [])
            idx_counter[rid] = 0
        step = m.get("step")
        if step is None:
            step = idx_counter[rid]
            idx_counter[rid] += 1
        series[rid][0].append(float(step))
        series[rid][1].append(float(m["value"]))

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(8, 4))
        for i, (rid, (steps, vals)) in enumerate(series.items()):
            label = rid[:12] if len(rid) > 12 else rid
            color = _COLORS[i % len(_COLORS)]
            ax.plot(steps, vals, color=color, linewidth=1.4, label=label, marker="o", markersize=3)
        ax.set_xlabel("Step")
        ax.set_ylabel(metric_name)
        ax.set_title(f"{metric_name} over Steps")
        if len(series) > 1:
            ax.legend(loc="best", framealpha=0.9)
        fig.savefig(output_path)
        plt.close(fig)

    return output_path


# ------------------------------------------------------------------
# 3. Config impact scatter / box plot
# ------------------------------------------------------------------

def plot_config_impact(
    runs: list[dict],
    param_name: str,
    metric_name: str,
    output_path: str,
) -> str:
    """Scatter plot showing the effect of *param_name* on *metric_name*.

    Parameters
    ----------
    runs : list[dict]
        Each dict must contain a ``"config"`` sub-dict and a ``"metrics"``
        sub-dict (or top-level keys).  The function extracts the value
        of *param_name* from the config and *metric_name* from the
        metrics.
    param_name : str
        Configuration parameter key (looked up in ``run["config"]``).
    metric_name : str
        Metric key (looked up in ``run["metrics"]`` first, then
        top-level ``run``).
    output_path : str
        Destination PNG path.

    Returns
    -------
    str
        The written *output_path*.
    """
    _ensure_dir(output_path)

    xs: list[float] = []
    ys: list[float] = []
    labels: list[str] = []

    for r in runs:
        cfg = r.get("config", r)
        met = r.get("metrics", r)

        param_val = _deep_get(cfg, param_name)
        metric_val = _deep_get(met, metric_name)
        if param_val is None or metric_val is None:
            continue
        try:
            xs.append(float(param_val))
            ys.append(float(metric_val))
            labels.append(str(r.get("run_id", "?"))[:10])
        except (ValueError, TypeError):
            continue

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(7, 5))
        if xs:
            ax.scatter(xs, ys, c=_COLORS[0], s=60, edgecolors="white", linewidth=0.6, zorder=3)
            # Annotate points
            for x, y, lbl in zip(xs, ys, labels):
                ax.annotate(lbl, (x, y), fontsize=7, textcoords="offset points",
                            xytext=(4, 4), color="#86868b")
            # Trend line
            if len(xs) >= 2:
                coeffs = np.polyfit(xs, ys, 1)
                poly = np.poly1d(coeffs)
                x_line = np.linspace(min(xs), max(xs), 50)
                ax.plot(x_line, poly(x_line), "--", color=_COLORS[2], linewidth=1, alpha=0.7, label="trend")
                ax.legend(loc="best")
        else:
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

        ax.set_xlabel(param_name)
        ax.set_ylabel(metric_name)
        ax.set_title(f"Impact of {param_name} on {metric_name}")
        fig.savefig(output_path)
        plt.close(fig)

    return output_path


# ------------------------------------------------------------------
# 4. Visual summary card
# ------------------------------------------------------------------

def plot_summary_card(
    run_data: dict,
    output_path: str,
) -> str:
    """Render a single-run visual summary card as a PNG.

    The card displays key information: run id, status, type, top
    metrics, and creation timestamp, laid out as a compact dashboard
    tile.

    Parameters
    ----------
    run_data : dict
        Must contain ``"run_id"``.  Optional keys: ``"status"``,
        ``"run_type"``, ``"created_at"``, ``"metrics"`` (dict of name->value
        or list of metric dicts).
    output_path : str
        Destination PNG path.

    Returns
    -------
    str
        The written *output_path*.
    """
    _ensure_dir(output_path)

    run_id = str(run_data.get("run_id", "unknown"))[:16]
    status = str(run_data.get("status", "—"))
    run_type = str(run_data.get("run_type", "—"))
    created = str(run_data.get("created_at", "—"))

    # Normalise metrics into a simple dict
    raw_metrics = run_data.get("metrics", {})
    if isinstance(raw_metrics, list):
        metrics_dict: dict[str, float] = {}
        for m in raw_metrics:
            name = m.get("name", "")
            val = m.get("value", 0)
            metrics_dict[name] = float(val)
    elif isinstance(raw_metrics, dict):
        metrics_dict = {k: float(v) for k, v in raw_metrics.items()}
    else:
        metrics_dict = {}

    # Pick up to 6 metrics to display
    top_metrics = dict(list(metrics_dict.items())[:6])

    status_colors = {
        "completed": "#34c759",
        "running": "#0071e3",
        "pending": "#ff9500",
        "failed": "#ff3b30",
    }
    status_color = status_colors.get(status.lower(), "#86868b")

    with plt.rc_context(_STYLE):
        fig_h = 2.2 + 0.28 * max(len(top_metrics), 1)
        fig, ax = plt.subplots(figsize=(5.5, fig_h))
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis("off")
        fig.patch.set_facecolor("#ffffff")

        # Card border
        from matplotlib.patches import FancyBboxPatch

        card = FancyBboxPatch(
            (0.3, 0.3), 9.4, 9.4,
            boxstyle="round,pad=0.2",
            facecolor="#fafafa",
            edgecolor="#d2d2d7",
            linewidth=1.2,
        )
        ax.add_patch(card)

        # Header
        ax.text(0.8, 9.0, f"Run: {run_id}", fontsize=13, fontweight="bold", color="#1d1d1f")
        ax.text(0.8, 8.3, f"Type: {run_type}   |   Created: {created}",
                fontsize=8, color="#86868b")

        # Status pill
        ax.text(8.5, 9.0, status.upper(), fontsize=9, fontweight="bold",
                color="white", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=status_color, edgecolor="none"))

        # Divider line
        ax.plot([0.8, 9.2], [7.8, 7.8], color="#d2d2d7", linewidth=0.8)

        # Metrics
        if top_metrics:
            y_cursor = 7.2
            for name, val in top_metrics.items():
                ax.text(1.0, y_cursor, name, fontsize=9, color="#1d1d1f")
                ax.text(8.0, y_cursor, f"{val:.4g}", fontsize=9, fontweight="bold",
                        color=_COLORS[0], ha="right")
                y_cursor -= 0.9
        else:
            ax.text(5.0, 5.0, "No metrics recorded", fontsize=10,
                    ha="center", va="center", color="#86868b")

        fig.savefig(output_path)
        plt.close(fig)

    return output_path


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _deep_get(d: dict, key: str, default: Any = None) -> Any:
    """Retrieve a value from a dict, supporting dotted keys.

    ``_deep_get({"a": {"b": 3}}, "a.b")`` returns ``3``.
    """
    keys = key.split(".")
    current: Any = d
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default
        if current is None:
            return default
    return current
