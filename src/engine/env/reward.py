"""Reward calculation for the terrain path-planning environment.

Implements a 14-component reward function with configurable weights,
potential-based reward shaping, and reward clipping.  Each component
is computed independently and the weighted sum is returned.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from engine.mission.state_machine import MissionMode


# ---------------------------------------------------------------------------
# Potential function for reward shaping
# ---------------------------------------------------------------------------

def _potential(state: dict, mission_goal_dist: float) -> float:
    """Distance-based potential for reward shaping (closer = higher).

    Returns a value in [0, 1] that increases as the agent approaches
    the goal.
    """
    d = mission_goal_dist
    max_d = state.get("initial_goal_distance", d + 1.0)
    if max_d < 1.0:
        return 1.0
    return max(0.0, 1.0 - d / max_d)


# ---------------------------------------------------------------------------
# Individual reward components
# ---------------------------------------------------------------------------

def _reward_progress(
    prev_goal_dist: float,
    curr_goal_dist: float,
    initial_goal_dist: float,
) -> float:
    """Reward for reducing distance to goal (normalised by initial)."""
    if initial_goal_dist < 1.0:
        return 0.0
    return (prev_goal_dist - curr_goal_dist) / initial_goal_dist


def _reward_mission_complete(done: bool, success: bool) -> float:
    """Binary reward for successful mission completion."""
    return 1.0 if (done and success) else 0.0


def _reward_observation_complete(
    observe_done: bool,
    prev_observe_done: bool,
) -> float:
    """One-time reward when the observation objective is first completed."""
    return 1.0 if (observe_done and not prev_observe_done) else 0.0


def _reward_integrated_risk(integrated_risk: float) -> float:
    """Penalty proportional to risk accumulated on this step.

    Returns a negative value (penalty).  Normalised by 100 so
    that typical risk values produce small penalties.
    """
    return -min(integrated_risk / 100.0, 1.0)


def _reward_visible_time(visible_ratio: float) -> float:
    """Penalty for time spent visible to threats."""
    return -visible_ratio


def _reward_path_length(step_distance: float) -> float:
    """Small penalty per metre of path length to encourage efficiency."""
    return -step_distance


def _reward_time_cost(dt: float) -> float:
    """Small penalty per second elapsed to discourage dawdling."""
    return -dt


def _reward_altitude_violation(
    altitude_agl: float,
    mode: MissionMode,
    target_agl: float,
) -> float:
    """Penalty when the agent violates altitude band constraints.

    Low-altitude modes should stay below ~40 m AGL; high modes should
    be above the target AGL minus a tolerance.
    """
    if mode in (
        MissionMode.TRANSIT,
        MissionMode.EGRESS,
        MissionMode.SAFE_HOLD,
    ):
        # Should be low-altitude masked
        if altitude_agl > 50.0:
            return -((altitude_agl - 50.0) / 100.0)
    elif mode in (MissionMode.POPUP_OBSERVE, MissionMode.OBSERVE_SETUP):
        # Should be high
        if altitude_agl < target_agl * 0.5:
            return -(1.0 - altitude_agl / (target_agl * 0.5 + 1.0))
    return 0.0


def _reward_zone_violation(zone_penalty: float) -> float:
    """Penalty for leaving the operational zone (DEM boundary)."""
    return -zone_penalty


def _reward_excessive_climb(altitude_change: float) -> float:
    """Penalty for rapid altitude changes that waste energy."""
    abs_change = abs(altitude_change)
    if abs_change > 80.0:
        return -((abs_change - 80.0) / 100.0)
    return 0.0


def _reward_invalid_action(action_was_invalid: bool) -> float:
    """Large penalty for selecting an invalid (masked) action."""
    return -1.0 if action_was_invalid else 0.0


def _reward_mode_switch(prev_mode: MissionMode, curr_mode: MissionMode) -> float:
    """Small penalty for every mode switch to discourage oscillation."""
    return -1.0 if prev_mode != curr_mode else 0.0


def _reward_collision(collision: bool) -> float:
    """Large penalty for terrain collision."""
    return -1.0 if collision else 0.0


def _reward_fail_terminal(done: bool, success: bool) -> float:
    """Large penalty for failing the mission."""
    return -1.0 if (done and not success) else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RewardCalculator:
    """Compute the composite reward for a single environment step.

    Parameters
    ----------
    weights : dict[str, float]
        Mapping from component name to weight.  Missing keys default
        to zero.  Expected keys match those in
        :attr:`TrainingConfig.reward_weights`.
    clip_range : tuple[float, float]
        ``(min_reward, max_reward)`` applied after weighting.
    gamma : float
        Discount factor used for potential-based shaping.
    """

    COMPONENT_NAMES = [
        "progress",
        "mission_complete",
        "observation_complete",
        "integrated_risk",
        "visible_time",
        "path_length",
        "time_cost",
        "altitude_violation",
        "zone_violation",
        "excessive_climb",
        "invalid_action",
        "mode_switch",
        "collision",
        "fail_terminal",
    ]

    def __init__(
        self,
        weights: dict[str, float],
        clip_range: tuple[float, float] = (-10.0, 10.0),
        gamma: float = 0.99,
    ) -> None:
        self.weights = {k: weights.get(k, 0.0) for k in self.COMPONENT_NAMES}
        self.clip_min, self.clip_max = clip_range
        self.gamma = gamma

    def compute(
        self,
        *,
        prev_state: dict,
        curr_state: dict,
        action_result: dict,
        done: bool,
        success: bool,
        action_was_invalid: bool = False,
    ) -> tuple[float, dict[str, float]]:
        """Compute the total reward and per-component breakdown.

        Parameters
        ----------
        prev_state : dict
            Agent state *before* the step.  Keys: ``goal_distance``,
            ``mode``, ``observe_done``, ``initial_goal_distance``,
            ``altitude_agl``.
        curr_state : dict
            Agent state *after* the step.  Same keys as above plus
            ``zone_penalty``.
        action_result : dict
            Result from :meth:`PrimitiveExecutor.execute`.  Keys:
            ``distance``, ``time_estimate``, ``altitude_change``,
            ``integrated_risk``, ``visible_ratio``, ``min_clearance``.
        done : bool
            Whether the episode terminated on this step.
        success : bool
            Whether the termination (if any) was successful.
        action_was_invalid : bool
            Whether the selected action was masked (invalid).

        Returns
        -------
        (total_reward, components)
            ``total_reward`` is the clipped weighted sum.
            ``components`` is a dict mapping each component name to
            its *unweighted* raw value.
        """
        prev_gd = float(prev_state.get("goal_distance", 0.0))
        curr_gd = float(curr_state.get("goal_distance", 0.0))
        init_gd = float(prev_state.get("initial_goal_distance", prev_gd + 1.0))
        prev_mode: MissionMode = prev_state.get("mode", MissionMode.TRANSIT)
        curr_mode: MissionMode = curr_state.get("mode", MissionMode.TRANSIT)
        observe_done = bool(curr_state.get("observe_done", False))
        prev_observe_done = bool(prev_state.get("observe_done", False))
        altitude_agl = float(curr_state.get("altitude_agl", 30.0))
        target_agl = float(curr_state.get("target_agl", 20.0))
        zone_pen = float(curr_state.get("zone_penalty", 0.0))

        step_dist = float(action_result.get("distance", 0.0))
        dt = float(action_result.get("time_estimate", 0.0))
        alt_change = float(action_result.get("altitude_change", 0.0))
        int_risk = float(action_result.get("integrated_risk", 0.0))
        vis_ratio = float(action_result.get("visible_ratio", 0.0))
        collision = float(action_result.get("min_clearance", 999.0)) < 0.5

        components: dict[str, float] = {
            "progress": _reward_progress(prev_gd, curr_gd, init_gd),
            "mission_complete": _reward_mission_complete(done, success),
            "observation_complete": _reward_observation_complete(
                observe_done, prev_observe_done
            ),
            "integrated_risk": _reward_integrated_risk(int_risk),
            "visible_time": _reward_visible_time(vis_ratio),
            "path_length": _reward_path_length(step_dist),
            "time_cost": _reward_time_cost(dt),
            "altitude_violation": _reward_altitude_violation(
                altitude_agl, curr_mode, target_agl
            ),
            "zone_violation": _reward_zone_violation(zone_pen),
            "excessive_climb": _reward_excessive_climb(alt_change),
            "invalid_action": _reward_invalid_action(action_was_invalid),
            "mode_switch": _reward_mode_switch(prev_mode, curr_mode),
            "collision": _reward_collision(collision),
            "fail_terminal": _reward_fail_terminal(done, success),
        }

        # Weighted sum
        total = sum(
            self.weights[name] * value for name, value in components.items()
        )

        # Potential-based shaping: gamma * phi(s') - phi(s)
        phi_prev = _potential(prev_state, prev_gd)
        phi_curr = _potential(curr_state, curr_gd)
        shaping = self.gamma * phi_curr - phi_prev
        total += shaping

        # Clip
        total = max(self.clip_min, min(self.clip_max, total))

        return total, components
