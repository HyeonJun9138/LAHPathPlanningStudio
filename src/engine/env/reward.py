"""Reward calculation for the terrain path-planning environment.

Implements a multi-component reward function with configurable weights,
potential-based reward shaping, and reward clipping.  Each component
is computed independently and the weighted sum is returned.

Improvements over v1:
- Added fuel_efficiency, threat_proximity, and smoothness components
- Potential-based shaping uses a configurable weight
- Wider clip range for terminal rewards so collision/fail signals
  are not suppressed
- Fuel-aware potential term encourages fuel conservation
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
    """Composite potential for reward shaping.

    Combines distance-to-goal progress (weight 0.7) with a fuel-conservation
    term (weight 0.3).  Returns a value in [0, 1].
    """
    d = mission_goal_dist
    max_d = state.get("initial_goal_distance", d + 1.0)
    if max_d < 1.0:
        dist_potential = 1.0
    else:
        dist_potential = max(0.0, 1.0 - d / max_d)

    fuel = float(state.get("fuel", 1.0))
    fuel_potential = max(0.0, min(1.0, fuel))

    return 0.7 * dist_potential + 0.3 * fuel_potential


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


def _reward_collision(collision: bool) -> float:
    """Large penalty for terrain collision."""
    return -1.0 if collision else 0.0


def _reward_fail_terminal(done: bool, success: bool) -> float:
    """Large penalty for failing the mission."""
    return -1.0 if (done and not success) else 0.0


def _reward_fuel_efficiency(prev_fuel: float, curr_fuel: float, dt: float) -> float:
    """Penalty for excessive fuel burn relative to time elapsed.

    Encourages the agent to find fuel-efficient trajectories.
    Returns a value in [-1, 0].
    """
    fuel_burn = prev_fuel - curr_fuel
    if dt < 0.01:
        return 0.0
    burn_rate = fuel_burn / dt
    # Penalise burn rates above the nominal 0.0001/s baseline
    excess = max(0.0, burn_rate - 0.0001)
    return -min(excess * 5000.0, 1.0)


def _reward_threat_proximity(min_clearance: float) -> float:
    """Penalty for flying dangerously close to terrain/threats.

    Encourages maintaining safe clearance. Smooth penalty that
    increases as clearance drops below 30 m.
    Returns a value in [-1, 0].
    """
    if min_clearance >= 30.0:
        return 0.0
    return -((30.0 - min_clearance) / 30.0)


def _reward_mode_switch(prev_mode: MissionMode, curr_mode: MissionMode) -> float:
    """Penalty for unnecessary mode switches.

    Frequent mode switches indicate indecision and waste time.
    Returns -1.0 if the mode changed, 0.0 otherwise.
    """
    return -1.0 if prev_mode != curr_mode else 0.0


def _reward_smoothness(
    prev_heading: float, curr_heading: float,
    prev_alt_agl: float, curr_alt_agl: float,
) -> float:
    """Penalty for jerky manoeuvres (large heading or altitude changes).

    Encourages smooth trajectories that are more realistic for
    rotorcraft flight.  Returns a value in [-1, 0].
    """
    # Heading change penalty (normalised by pi)
    dh = abs(curr_heading - prev_heading)
    if dh > math.pi:
        dh = 2.0 * math.pi - dh
    heading_pen = (dh / math.pi) ** 2  # quadratic: small turns are cheap

    # Altitude change penalty
    da = abs(curr_alt_agl - prev_alt_agl)
    alt_pen = min(da / 100.0, 1.0)

    return -0.5 * (heading_pen + alt_pen)


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
        Default widened to (-50, 50) so terminal signals for
        collision (weight 200) and fail (weight 150) are not
        excessively suppressed.
    gamma : float
        Discount factor used for potential-based shaping.
    shaping_weight : float
        Multiplier applied to the potential-based shaping term.
        Allows tuning the strength of the shaping signal independently
        of reward component weights.
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
        "fuel_efficiency",
        "threat_proximity",
        "smoothness",
    ]

    def __init__(
        self,
        weights: dict[str, float],
        clip_range: tuple[float, float] = (-50.0, 50.0),
        gamma: float = 0.99,
        shaping_weight: float = 1.0,
    ) -> None:
        self.weights = {k: weights.get(k, 0.0) for k in self.COMPONENT_NAMES}
        self.clip_min, self.clip_max = clip_range
        self.gamma = gamma
        self.shaping_weight = shaping_weight

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
            ``altitude_agl``, ``fuel``, ``heading``.
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
        prev_alt_agl = float(prev_state.get("altitude_agl", 30.0))
        target_agl = float(curr_state.get("target_agl", 20.0))
        zone_pen = float(curr_state.get("zone_penalty", 0.0))
        prev_fuel = float(prev_state.get("fuel", 1.0))
        curr_fuel = float(curr_state.get("fuel", 1.0))
        prev_heading = float(prev_state.get("heading", 0.0))
        curr_heading = float(curr_state.get("heading", 0.0))

        step_dist = float(action_result.get("distance", 0.0))
        dt = float(action_result.get("time_estimate", 0.0))
        alt_change = float(action_result.get("altitude_change", 0.0))
        int_risk = float(action_result.get("integrated_risk", 0.0))
        vis_ratio = float(action_result.get("visible_ratio", 0.0))
        min_clearance = float(action_result.get("min_clearance", 999.0))
        collision = min_clearance < 0.5

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
            "fuel_efficiency": _reward_fuel_efficiency(prev_fuel, curr_fuel, dt),
            "threat_proximity": _reward_threat_proximity(min_clearance),
            "smoothness": _reward_smoothness(
                prev_heading, curr_heading, prev_alt_agl, altitude_agl
            ),
        }

        # Weighted sum
        total = sum(
            self.weights[name] * value for name, value in components.items()
        )

        # Potential-based shaping: shaping_weight * (gamma * phi(s') - phi(s))
        phi_prev = _potential(prev_state, prev_gd)
        phi_curr = _potential(curr_state, curr_gd)
        shaping = self.gamma * phi_curr - phi_prev
        total += self.shaping_weight * shaping

        # Clip — wider range than v1 so terminal signals are preserved
        total = max(self.clip_min, min(self.clip_max, total))

        return total, components
