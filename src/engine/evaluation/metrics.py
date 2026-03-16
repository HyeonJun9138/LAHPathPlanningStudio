"""Metric computation functions for evaluation episodes.

Each function accepts a list of episode dicts (as produced by
:class:`~engine.evaluation.evaluator.Evaluator` or
:func:`~engine.simulation.rollout.run_rollout`) and returns a scalar
metric value.  :func:`aggregate_metrics` bundles them all into a single
dict.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np


def compute_success_rate(episodes: list[dict]) -> float:
    """Fraction of episodes where the agent reached the goal.

    Looks for the ``success`` key (bool) in each episode dict.
    """
    if not episodes:
        return 0.0
    successes = [bool(ep.get("success", False)) for ep in episodes]
    return float(np.mean(successes))


def compute_mean_return(episodes: list[dict]) -> float:
    """Average cumulative reward across episodes."""
    if not episodes:
        return 0.0
    returns = [float(ep.get("total_reward", 0.0)) for ep in episodes]
    return float(np.mean(returns))


def compute_mean_path_length(episodes: list[dict]) -> float:
    """Average 3-D path length (metres) across episodes.

    Falls back to computing from step (x, y, z) data when the
    ``path_length`` key is missing from an episode dict.
    """
    if not episodes:
        return 0.0
    lengths: list[float] = []
    for ep in episodes:
        if "path_length" in ep:
            lengths.append(float(ep["path_length"]))
        else:
            lengths.append(_path_length_from_steps(ep.get("steps", [])))
    return float(np.mean(lengths))


def _path_length_from_steps(steps: list[dict]) -> float:
    """Compute cumulative Euclidean path length from step records."""
    total = 0.0
    prev_x, prev_y, prev_z = None, None, None
    for s in steps:
        x = s.get("x")
        y = s.get("y")
        z = s.get("z", 0.0)
        if x is not None and y is not None:
            if prev_x is not None:
                dx = float(x) - prev_x
                dy = float(y) - prev_y
                dz = float(z) - prev_z
                total += (dx * dx + dy * dy + dz * dz) ** 0.5
            prev_x, prev_y, prev_z = float(x), float(y), float(z)
    return total


def compute_mean_episode_time(episodes: list[dict]) -> float:
    """Average wall-clock episode duration (seconds).

    Uses the ``episode_time`` key when available, else counts steps.
    """
    if not episodes:
        return 0.0
    times: list[float] = []
    for ep in episodes:
        if "episode_time" in ep:
            times.append(float(ep["episode_time"]))
        else:
            # Fallback: count the number of steps as a proxy
            times.append(float(len(ep.get("steps", []))))
    return float(np.mean(times))


def compute_mean_risk(episodes: list[dict]) -> float:
    """Average per-step risk value pooled across all episodes.

    Collects all ``risk`` values from every step and returns their mean.
    If no risk data is present, returns 0.0.
    """
    all_risks: list[float] = []
    for ep in episodes:
        if "mean_risk" in ep:
            all_risks.append(float(ep["mean_risk"]))
        else:
            for s in ep.get("steps", []):
                if "risk" in s:
                    all_risks.append(float(s["risk"]))
    if not all_risks:
        return 0.0
    return float(np.mean(all_risks))


def compute_divert_rate(episodes: list[dict]) -> float:
    """Fraction of episodes that ended with a divert."""
    if not episodes:
        return 0.0
    diverts = [bool(ep.get("diverted", False)) for ep in episodes]
    return float(np.mean(diverts))


def compute_collision_rate(episodes: list[dict]) -> float:
    """Fraction of episodes that ended in a collision."""
    if not episodes:
        return 0.0
    collisions = [bool(ep.get("collision", False)) for ep in episodes]
    return float(np.mean(collisions))


def compute_observation_rate(episodes: list[dict]) -> float:
    """Fraction of episodes that completed the observation objective."""
    if not episodes:
        return 0.0
    completions = [
        bool(ep.get("observation_completed", False)) for ep in episodes
    ]
    return float(np.mean(completions))


def compute_mean_integrated_risk(episodes: list[dict]) -> float:
    """Average total integrated risk accumulated over each episode.

    Uses the ``total_risk`` key from the final state of each episode.
    Falls back to summing per-step ``integrated_risk`` values.
    """
    if not episodes:
        return 0.0
    risks: list[float] = []
    for ep in episodes:
        if "total_risk" in ep:
            risks.append(float(ep["total_risk"]))
        else:
            step_risk = sum(
                float(s.get("integrated_risk", 0.0))
                for s in ep.get("steps", [])
            )
            risks.append(step_risk)
    return float(np.mean(risks)) if risks else 0.0


def compute_mean_visible_time(episodes: list[dict]) -> float:
    """Average time (seconds) the agent spent inside the observation box.

    Uses the ``observe_time`` key from the final state.  Falls back to
    counting steps where ``in_observe_box`` is true, multiplied by the
    average step duration.
    """
    if not episodes:
        return 0.0
    times: list[float] = []
    for ep in episodes:
        if "observe_time" in ep:
            times.append(float(ep["observe_time"]))
        else:
            steps = ep.get("steps", [])
            in_box_count = sum(
                1 for s in steps if s.get("in_observe_box", False)
            )
            # Estimate per-step duration from episode time
            ep_time = float(ep.get("episode_time", len(steps)))
            n_steps = max(len(steps), 1)
            times.append(in_box_count * (ep_time / n_steps))
    return float(np.mean(times)) if times else 0.0


def compute_altitude_violation_count(episodes: list[dict]) -> float:
    """Total number of altitude-AGL violations across all episodes.

    A violation is counted when the agent's AGL drops below a minimum
    safe threshold (``altitude_agl < 5.0`` metres).  Uses the
    ``altitude_violations`` key if present; otherwise scans step data.
    """
    total = 0
    for ep in episodes:
        if "altitude_violations" in ep:
            total += int(ep["altitude_violations"])
        else:
            for s in ep.get("steps", []):
                agl = s.get("altitude_agl")
                if agl is not None and float(agl) < 5.0:
                    total += 1
    return float(total)


def compute_zone_violation_count(episodes: list[dict]) -> float:
    """Total number of zone/boundary violations across all episodes.

    A violation is any step where ``zone_penalty > 0``.  Uses the
    ``zone_violations`` key if present; otherwise scans step data.
    """
    total = 0
    for ep in episodes:
        if "zone_violations" in ep:
            total += int(ep["zone_violations"])
        else:
            for s in ep.get("steps", []):
                zp = s.get("zone_penalty", 0.0)
                if float(zp) > 0.0:
                    total += 1
    return float(total)


def aggregate_metrics(episodes: list[dict]) -> dict[str, float]:
    """Compute all standard metrics and return them as a flat dict.

    Returns
    -------
    dict[str, float]
        Keys: ``success_rate``, ``mean_return``, ``mean_path_length``,
        ``mean_episode_time``, ``mean_risk``, ``mean_integrated_risk``,
        ``mean_visible_time``, ``altitude_violation_count``,
        ``zone_violation_count``, ``divert_rate``, ``collision_rate``,
        ``observation_completion_rate``, ``num_episodes``.
    """
    return {
        "success_rate": compute_success_rate(episodes),
        "mean_return": compute_mean_return(episodes),
        "mean_path_length": compute_mean_path_length(episodes),
        "mean_episode_time": compute_mean_episode_time(episodes),
        "mean_risk": compute_mean_risk(episodes),
        "mean_integrated_risk": compute_mean_integrated_risk(episodes),
        "mean_visible_time": compute_mean_visible_time(episodes),
        "altitude_violation_count": compute_altitude_violation_count(episodes),
        "zone_violation_count": compute_zone_violation_count(episodes),
        "divert_rate": compute_divert_rate(episodes),
        "collision_rate": compute_collision_rate(episodes),
        "observation_completion_rate": compute_observation_rate(episodes),
        "num_episodes": float(len(episodes)),
    }


def compute_inference_latency(
    model: Any,
    obs: Any,
    n_samples: int = 100,
) -> dict[str, float]:
    """Measure prediction latency of *model*.

    Calls ``model.predict(obs, deterministic=True)`` *n_samples* times and
    returns timing statistics.

    Parameters
    ----------
    model
        Object with a ``predict(obs, deterministic)`` method (e.g. an
        SB3 model).
    obs
        A single observation compatible with the model's observation space.
    n_samples : int
        Number of prediction calls to time.

    Returns
    -------
    dict[str, float]
        ``mean`` -- mean latency in seconds.
        ``p95`` -- 95th percentile latency.
        ``p99`` -- 99th percentile latency.
    """
    latencies: list[float] = []

    # Warm-up call (exclude from statistics)
    model.predict(obs, deterministic=True)

    for _ in range(n_samples):
        t0 = time.perf_counter()
        model.predict(obs, deterministic=True)
        t1 = time.perf_counter()
        latencies.append(t1 - t0)

    arr = np.array(latencies)
    return {
        "mean": float(np.mean(arr)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
    }
