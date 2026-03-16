"""Cross-run comparison utilities.

Compares evaluation results from multiple runs (policies, checkpoints, or
hyperparameter sweeps) by tabulating metrics, ranking, and computing
deltas against a reference baseline.
"""

from __future__ import annotations

from typing import Any


def compare_runs(run_results: list[dict]) -> dict:
    """Build a comparison report across multiple evaluation runs.

    Parameters
    ----------
    run_results : list[dict]
        Each dict must have at least a ``run_id`` (or ``name``) key and
        one or more metric keys (e.g. ``success_rate``, ``mean_return``).

    Returns
    -------
    dict
        ``table`` -- A list of row-dicts suitable for tabular display,
        one per run, with all shared metric columns.

        ``rankings`` -- A dict mapping each metric name to the list of
        run identifiers sorted from best to worst.  Lower is better for
        ``mean_risk``, ``collision_rate``, ``divert_rate``,
        ``mean_episode_time``; higher is better for the rest.

        ``best`` -- Dict mapping each metric to the run identifier of the
        best performer.

        ``metric_names`` -- Sorted list of all metric names found.
    """
    if not run_results:
        return {"table": [], "rankings": {}, "best": {}, "metric_names": []}

    # Discover all metric names (exclude meta keys)
    meta_keys = {"run_id", "name", "episodes", "config", "label"}
    metric_names: set[str] = set()
    for rr in run_results:
        for k in rr:
            if k not in meta_keys and isinstance(rr[k], (int, float)):
                metric_names.add(k)
    metric_names_sorted = sorted(metric_names)

    # Build the comparison table
    table = generate_comparison_table(run_results, metric_names_sorted)

    # Lower-is-better metrics
    lower_is_better = {
        "mean_risk",
        "collision_rate",
        "divert_rate",
        "mean_episode_time",
        "mean_path_length",
    }

    rankings: dict[str, list[str]] = {}
    best: dict[str, str] = {}

    for metric in metric_names_sorted:
        ascending = metric in lower_is_better
        ranked = rank_runs(run_results, metric, ascending=ascending)
        rankings[metric] = [_run_label(r) for r in ranked]
        if ranked:
            best[metric] = _run_label(ranked[0])

    return {
        "table": table,
        "rankings": rankings,
        "best": best,
        "metric_names": metric_names_sorted,
    }


def generate_comparison_table(
    results: list[dict],
    metric_names: list[str],
) -> list[dict]:
    """Produce a list of row-dicts with ``run_id`` and requested metrics.

    Parameters
    ----------
    results : list[dict]
        Raw run results.
    metric_names : list[str]
        Metric columns to include.

    Returns
    -------
    list[dict]
        One dict per run containing ``run_id`` plus each metric value
        (``None`` when a metric is missing for that run).
    """
    table: list[dict] = []
    for rr in results:
        row: dict[str, Any] = {"run_id": _run_label(rr)}
        for m in metric_names:
            value = rr.get(m)
            if value is not None:
                row[m] = float(value)
            else:
                row[m] = None
        table.append(row)
    return table


def rank_runs(
    results: list[dict],
    metric: str,
    ascending: bool = True,
) -> list[dict]:
    """Return *results* sorted by *metric*.

    Parameters
    ----------
    results : list[dict]
        Run result dicts.
    metric : str
        The metric key to sort on.
    ascending : bool
        ``True`` puts the smallest value first (best for cost-like
        metrics).  ``False`` puts the largest first (best for
        reward-like metrics).

    Returns
    -------
    list[dict]
        Sorted copy of *results*.  Runs missing the metric are placed
        at the end.
    """
    present = [r for r in results if metric in r and r[metric] is not None]
    missing = [r for r in results if metric not in r or r[metric] is None]

    sorted_present = sorted(
        present,
        key=lambda r: float(r[metric]),
        reverse=not ascending,
    )
    return sorted_present + missing


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _run_label(run: dict) -> str:
    """Extract a human-readable identifier from a run dict."""
    return str(run.get("run_id", run.get("name", run.get("label", "unknown"))))
