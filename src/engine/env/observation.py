"""Observation builder for the terrain path-planning environment.

Constructs the Dict observation consumed by the RL policy from raw
environment state.  The observation space has five components:

1. ``local_hi_patch``  — (C, 32, 32) high-res terrain patch
2. ``local_mid_patch`` — (C, 16, 16) mid-res terrain patch
3. ``self_state``      — (48,) agent kinematic / mission state
4. ``global_context``  — (16,) global mission summary
5. ``candidate_table`` — (32, 24) per-candidate feature rows
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import gymnasium as gym

from engine.mission.state_machine import MissionMode
from engine.terrain.patch_sampler import PatchSampler


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HI_PATCH_SIZE = 32
_MID_PATCH_SIZE = 16
_SELF_STATE_DIM = 48
_GLOBAL_DIM = 16
_K = 32
_CANDIDATE_FEAT_DIM = 24

# Mission-mode one-hot width
_NUM_MODES = len(MissionMode)  # 10


# ---------------------------------------------------------------------------
# Observation space factory
# ---------------------------------------------------------------------------

def make_observation_space(num_terrain_channels: int) -> gym.spaces.Dict:
    """Build and return the Dict observation space.

    Parameters
    ----------
    num_terrain_channels : int
        Number of channels in terrain patch data (e.g. 7 for elevation,
        slope, aspect, roughness, curvature, tpi, openness).

    Returns
    -------
    gym.spaces.Dict
    """
    C = num_terrain_channels
    return gym.spaces.Dict(
        {
            "local_hi_patch": gym.spaces.Box(
                low=-np.inf, high=np.inf,
                shape=(C, _HI_PATCH_SIZE, _HI_PATCH_SIZE),
                dtype=np.float32,
            ),
            "local_mid_patch": gym.spaces.Box(
                low=-np.inf, high=np.inf,
                shape=(C, _MID_PATCH_SIZE, _MID_PATCH_SIZE),
                dtype=np.float32,
            ),
            "self_state": gym.spaces.Box(
                low=-np.inf, high=np.inf,
                shape=(_SELF_STATE_DIM,),
                dtype=np.float32,
            ),
            "global_context": gym.spaces.Box(
                low=-np.inf, high=np.inf,
                shape=(_GLOBAL_DIM,),
                dtype=np.float32,
            ),
            "candidate_table": gym.spaces.Box(
                low=-np.inf, high=np.inf,
                shape=(_K, _CANDIDATE_FEAT_DIM),
                dtype=np.float32,
            ),
        }
    )


# ---------------------------------------------------------------------------
# Observation builder
# ---------------------------------------------------------------------------

class ObservationBuilder:
    """Build observations from raw environment state.

    Parameters
    ----------
    patch_sampler : PatchSampler
        Provides terrain patch extraction at high and mid resolution.
    num_terrain_channels : int
        Number of channels in terrain data.
    """

    def __init__(
        self,
        patch_sampler: PatchSampler,
        num_terrain_channels: int,
    ) -> None:
        self.patch_sampler = patch_sampler
        self.num_channels = num_terrain_channels

    def build(
        self,
        state: dict,
        candidates: np.ndarray,
        mask: np.ndarray,
        mission_info: dict,
    ) -> dict[str, np.ndarray]:
        """Construct the full observation dict.

        Parameters
        ----------
        state : dict
            Agent state with keys: x, y, z, vx, vy, vz, heading,
            altitude_agl, fuel, time_elapsed, mode, goal_distance,
            observe_done, observe_time, initial_goal_distance,
            prev_mode, step_count, total_risk.
        candidates : np.ndarray
            (K, 24) candidate feature matrix.
        mask : np.ndarray
            (K,) boolean validity mask.
        mission_info : dict
            Keys: goal_x, goal_y, start_x, start_y, max_time,
            has_observe_box, observe_box_dist, num_safe_holds,
            num_alternate_lz, terrain_mean_elev, terrain_std_elev.

        Returns
        -------
        dict[str, np.ndarray]
        """
        x = float(state.get("x", 0.0))
        y = float(state.get("y", 0.0))

        hi_patch = self._extract_hi_patch(x, y)
        mid_patch = self._extract_mid_patch(x, y)
        self_state = self._build_self_state(state)
        global_ctx = self._build_global_context(state, mission_info)
        cand_table = self._build_candidate_table(candidates, mask)

        return {
            "local_hi_patch": hi_patch,
            "local_mid_patch": mid_patch,
            "self_state": self_state,
            "global_context": global_ctx,
            "candidate_table": cand_table,
        }

    # ------------------------------------------------------------------
    # Terrain patches
    # ------------------------------------------------------------------

    def _extract_hi_patch(self, x: float, y: float) -> np.ndarray:
        """High-resolution patch (C, 32, 32) from native resolution."""
        raw = self.patch_sampler.extract_patch(x, y, _HI_PATCH_SIZE, resolution_level=1)
        return self._normalize_patch(raw)

    def _extract_mid_patch(self, x: float, y: float) -> np.ndarray:
        """Mid-resolution patch (C, 16, 16) from 2x-coarsened view."""
        raw = self.patch_sampler.extract_patch(x, y, _MID_PATCH_SIZE, resolution_level=2)
        return self._normalize_patch(raw)

    @staticmethod
    def _normalize_patch(patch: np.ndarray) -> np.ndarray:
        """Per-channel zero-mean unit-variance normalization."""
        out = np.empty_like(patch, dtype=np.float32)
        for c in range(patch.shape[0]):
            ch = patch[c]
            mu = ch.mean()
            std = ch.std()
            if std > 1e-8:
                out[c] = (ch - mu) / std
            else:
                out[c] = ch - mu
        return out

    # ------------------------------------------------------------------
    # Self-state vector (48 dims)
    # ------------------------------------------------------------------

    def _build_self_state(self, state: dict) -> np.ndarray:
        """Build the 48-dimensional self-state vector.

        Layout:
            [0]   x / 10000
            [1]   y / 10000
            [2]   z / 1000
            [3]   vx / 100
            [4]   vy / 100
            [5]   vz / 50
            [6]   heading / pi  (normalised to [-1, 1])
            [7]   sin(heading)
            [8]   cos(heading)
            [9]   altitude_agl / 200
            [10]  fuel (0..1 fraction remaining)
            [11]  time_elapsed / max_time
            [12..21]  one-hot mission mode (10 dims)
            [22]  goal_distance / initial_goal_distance (progress)
            [23]  observe_done (0 or 1)
            [24]  observe_time / required_observe_time
            [25]  step_count / max_steps
            [26]  total_accumulated_risk / 1000
            [27]  min_clearance_so_far / 200
            [28]  distance_to_nearest_safe_hold / 5000
            [29]  distance_to_nearest_alt_lz / 5000
            [30]  distance_to_observe_box / 5000
            [31]  num_mode_switches / 20
            [32]  is_in_observe_box (0 or 1)
            [33]  altitude_band (0=low, 0.5=mid, 1=high)
            [34]  velocity_magnitude / 100
            [35]  sin(velocity_direction)
            [36]  cos(velocity_direction)
            [37]  fuel_burn_rate * 1000
            [38]  time_pressure (elapsed / max_time)
            [39]  goal_progress_rate
            [40]  vertical_speed / 50
            [41]  zone_penalty
            [42]  target_agl / 200
            [43]  fuel_efficiency_estimate (fuel_remaining * 10000 / goal_dist)
            [44..47]  reserved (zeros)
        """
        s = np.zeros(_SELF_STATE_DIM, dtype=np.float32)

        heading = float(state.get("heading", 0.0))
        init_gd = float(state.get("initial_goal_distance", 1.0))
        goal_dist = float(state.get("goal_distance", 0.0))
        max_time = float(state.get("max_time", 1800.0))
        max_steps = float(state.get("max_steps", 500.0))

        s[0] = float(state.get("x", 0.0)) / 10000.0
        s[1] = float(state.get("y", 0.0)) / 10000.0
        s[2] = float(state.get("z", 0.0)) / 1000.0
        s[3] = float(state.get("vx", 0.0)) / 100.0
        s[4] = float(state.get("vy", 0.0)) / 100.0
        s[5] = float(state.get("vz", 0.0)) / 50.0
        s[6] = heading / math.pi
        s[7] = math.sin(heading)
        s[8] = math.cos(heading)
        s[9] = float(state.get("altitude_agl", 30.0)) / 200.0
        s[10] = float(state.get("fuel", 1.0))
        s[11] = float(state.get("time_elapsed", 0.0)) / max(max_time, 1.0)

        # One-hot mode (indices 12..21)
        mode: MissionMode = state.get("mode", MissionMode.TRANSIT)
        mode_list = list(MissionMode)
        mode_idx = mode_list.index(mode) if mode in mode_list else 0
        s[12 + mode_idx] = 1.0

        # Progress and mission state
        if init_gd > 1.0:
            s[22] = goal_dist / init_gd
        else:
            s[22] = 0.0
        s[23] = 1.0 if state.get("observe_done", False) else 0.0
        req_obs_time = float(state.get("required_observe_time", 10.0))
        s[24] = float(state.get("observe_time", 0.0)) / max(req_obs_time, 1.0)
        s[25] = float(state.get("step_count", 0)) / max(max_steps, 1.0)
        s[26] = float(state.get("total_risk", 0.0)) / 1000.0
        s[27] = float(state.get("min_clearance", 200.0)) / 200.0
        s[28] = float(state.get("dist_safe_hold", 0.0)) / 5000.0
        s[29] = float(state.get("dist_alt_lz", 0.0)) / 5000.0
        s[30] = float(state.get("dist_observe_box", 0.0)) / 5000.0
        s[31] = float(state.get("num_mode_switches", 0)) / 20.0
        s[32] = 1.0 if state.get("in_observe_box", False) else 0.0

        agl = float(state.get("altitude_agl", 30.0))
        if agl < 40.0:
            s[33] = 0.0
        elif agl < 120.0:
            s[33] = 0.5
        else:
            s[33] = 1.0

        # [34..43] additional features
        # Velocity magnitude and direction
        vx = float(state.get("vx", 0.0))
        vy = float(state.get("vy", 0.0))
        vz = float(state.get("vz", 0.0))
        speed = math.sqrt(vx * vx + vy * vy + vz * vz)
        s[34] = speed / 100.0  # velocity magnitude normalised

        vel_heading = math.atan2(vy, vx) if speed > 0.1 else heading
        s[35] = math.sin(vel_heading)  # velocity direction sin
        s[36] = math.cos(vel_heading)  # velocity direction cos

        # Fuel burn rate estimate (fuel consumed per time)
        fuel = float(state.get("fuel", 1.0))
        elapsed = float(state.get("time_elapsed", 0.0))
        if elapsed > 1.0:
            s[37] = (1.0 - fuel) / elapsed * 1000.0  # burn rate * 1000
        else:
            s[37] = 0.0

        # Time pressure: ratio of elapsed to max time
        if max_time > 1.0:
            s[38] = elapsed / max_time
        else:
            s[38] = 0.0

        # Goal distance change rate (progress velocity)
        prev_gd = float(state.get("prev_goal_distance", goal_dist))
        if elapsed > 1.0:
            s[39] = (prev_gd - goal_dist) / max(init_gd, 1.0)
        else:
            s[39] = 0.0

        # Vertical speed normalised
        s[40] = vz / 50.0

        # Zone penalty (proximity to boundary)
        s[41] = float(state.get("zone_penalty", 0.0))

        # Target AGL normalised
        s[42] = float(state.get("target_agl", 20.0)) / 200.0

        # Remaining fuel efficiency estimate
        if goal_dist > 1.0 and fuel > 0.01:
            s[43] = min(1.0, (fuel * 10000.0) / goal_dist)
        else:
            s[43] = 1.0

        # [44..47] reserved — already zero
        return s

    # ------------------------------------------------------------------
    # Global context (16 dims)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_global_context(
        state: dict,
        mission_info: dict,
    ) -> np.ndarray:
        """Build the 16-dimensional global context vector.

        Layout:
            [0]   goal_x / 10000
            [1]   goal_y / 10000
            [2]   start_x / 10000
            [3]   start_y / 10000
            [4]   max_time / 3600
            [5]   has_observe_box (0 or 1)
            [6]   observe_box_dist / 10000
            [7]   num_safe_holds / 10
            [8]   num_alternate_lz / 10
            [9]   terrain_mean_elev / 1000
            [10]  terrain_std_elev / 500
            [11]  goal_distance / 10000
            [12]  time_remaining_fraction
            [13]  fuel_remaining
            [14]  terrain_roughness (terrain_std_elev / 1000)
            [15]  mission_phase_progress (0..1)
        """
        g = np.zeros(_GLOBAL_DIM, dtype=np.float32)

        g[0] = float(mission_info.get("goal_x", 0.0)) / 10000.0
        g[1] = float(mission_info.get("goal_y", 0.0)) / 10000.0
        g[2] = float(mission_info.get("start_x", 0.0)) / 10000.0
        g[3] = float(mission_info.get("start_y", 0.0)) / 10000.0
        g[4] = float(mission_info.get("max_time", 1800.0)) / 3600.0
        g[5] = 1.0 if mission_info.get("has_observe_box", False) else 0.0
        g[6] = float(mission_info.get("observe_box_dist", 0.0)) / 10000.0
        g[7] = float(mission_info.get("num_safe_holds", 0)) / 10.0
        g[8] = float(mission_info.get("num_alternate_lz", 0)) / 10.0
        g[9] = float(mission_info.get("terrain_mean_elev", 0.0)) / 1000.0
        g[10] = float(mission_info.get("terrain_std_elev", 0.0)) / 500.0
        g[11] = float(state.get("goal_distance", 0.0)) / 10000.0

        max_time = float(mission_info.get("max_time", 1800.0))
        elapsed = float(state.get("time_elapsed", 0.0))
        g[12] = max(0.0, (max_time - elapsed) / max(max_time, 1.0))
        g[13] = float(state.get("fuel", 1.0))

        # Terrain roughness (std of elevation normalised)
        g[14] = float(mission_info.get("terrain_std_elev", 0.0)) / 1000.0

        # Mission phase progress: fraction of waypoints/objectives completed
        observe_done = 1.0 if state.get("observe_done", False) else 0.0
        goal_progress = 1.0 - min(
            float(state.get("goal_distance", 0.0))
            / max(float(state.get("initial_goal_distance", 1.0)), 1.0),
            1.0,
        )
        g[15] = 0.5 * observe_done + 0.5 * goal_progress

        return g

    # ------------------------------------------------------------------
    # Candidate table (K, 24)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_candidate_table(
        candidates: np.ndarray,
        mask: np.ndarray,
    ) -> np.ndarray:
        """Pack the candidate matrix, zeroing out invalid rows.

        Parameters
        ----------
        candidates : np.ndarray  (K, 24)
        mask : np.ndarray  (K,) bool

        Returns
        -------
        np.ndarray  (K, 24) float32
        """
        table = candidates.astype(np.float32).copy()
        # Zero-out invalid candidate rows so the network sees a clean signal
        invalid = ~mask
        table[invalid] = 0.0
        return table
