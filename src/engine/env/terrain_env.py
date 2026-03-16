"""Gymnasium environment for terrain-aware path planning.

Implements a discrete-action RL environment where the agent selects
from K=32 candidate waypoints at each step.  The environment wraps
the mission state machine, candidate generator, primitive executor,
reward calculator, and observation builder into a standard Gymnasium
``Dict``-observation environment compatible with SB3's MaskablePPO.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import gymnasium as gym
import numpy as np

from engine.mission.schema import Mission
from engine.mission.state_machine import MissionMode, MissionStateMachine
from engine.mission.candidate_generator import CandidateGenerator
from engine.mission.primitives import PrimitiveType, PrimitiveExecutor, _PRIMITIVE_PARAMS
from engine.env.reward import RewardCalculator
from engine.env.observation import ObservationBuilder, make_observation_space
from engine.terrain.patch_sampler import PatchSampler


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_K = 32  # number of candidate actions
_MAX_STEPS = 500
_GOAL_ARRIVAL_DIST = 100.0  # metres


class TerrainPathEnv(gym.Env):
    """Terrain path-planning Gymnasium environment.

    Parameters
    ----------
    mission : Mission
        Mission specification.
    terrain_data : dict[str, np.ndarray]
        Named terrain channel arrays (elevation, slope, ...).
    terrain_metadata : dict
        Metadata with transform, resolution, bounds, width, height, crs.
    risk_map : np.ndarray | None
        Optional 2-D risk/threat array aligned with the DEM.
    reward_weights : dict[str, float]
        Per-component reward weights.
    candidate_config : dict | None
        Configuration for the candidate generator.
    max_steps : int
        Maximum steps per episode.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        mission: Mission,
        terrain_data: dict[str, np.ndarray],
        terrain_metadata: dict,
        risk_map: Optional[np.ndarray] = None,
        reward_weights: Optional[dict[str, float]] = None,
        candidate_config: Optional[dict] = None,
        max_steps: int = _MAX_STEPS,
    ) -> None:
        super().__init__()

        self.mission = mission
        self.terrain_data = terrain_data
        self.terrain_metadata = terrain_metadata
        self.risk_map = risk_map
        self.max_steps = max_steps

        # DEM is the elevation channel
        self.dem = terrain_data.get("elevation", next(iter(terrain_data.values())))
        self.transform = terrain_metadata["transform"]
        res = terrain_metadata["resolution"]
        self.resolution = float(res[0]) if isinstance(res, (list, tuple)) else float(res)

        # Sub-components
        self.state_machine = MissionStateMachine(mission)
        self.candidate_gen = CandidateGenerator(candidate_config or {})
        self.primitive_exec = PrimitiveExecutor(self.dem, self.transform, self.resolution)
        self.patch_sampler = PatchSampler(terrain_data, terrain_metadata)
        self.obs_builder = ObservationBuilder(
            self.patch_sampler, self.patch_sampler.num_channels
        )

        default_weights = {
            "progress": 2.0,
            "mission_complete": 100.0,
            "observation_complete": 30.0,
            "integrated_risk": 2.5,
            "visible_time": 1.2,
            "path_length": 0.003,
            "time_cost": 0.01,
            "altitude_violation": 3.0,
            "zone_violation": 5.0,
            "excessive_climb": 0.5,
            "invalid_action": 10.0,
            "mode_switch": 0.2,
            "collision": 200.0,
            "fail_terminal": 150.0,
        }
        if reward_weights:
            default_weights.update(reward_weights)
        self.reward_calc = RewardCalculator(default_weights)

        # Spaces
        self.observation_space = make_observation_space(self.patch_sampler.num_channels)
        self.action_space = gym.spaces.Discrete(_K)

        # Pre-compute mission info (static for the episode)
        self._mission_info = self._build_mission_info()

        # Episode state (set in reset)
        self._state: dict = {}
        self._candidates: np.ndarray = np.zeros((_K, 24), dtype=np.float32)
        self._mask: np.ndarray = np.zeros(_K, dtype=bool)
        self._step_count: int = 0
        self._done: bool = False

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Reset the environment to the start of a new episode."""
        super().reset(seed=seed)

        self.state_machine.reset()
        self._step_count = 0
        self._done = False

        start = self.mission.start
        start_elev = self._elevation_at(start.x, start.y)
        start_z = start_elev + start.agl_m

        init_goal_dist = self.mission.goal_distance(start.x, start.y)

        self._state = {
            "x": start.x,
            "y": start.y,
            "z": start_z,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "heading": math.atan2(
                self.mission.goal.y - start.y,
                self.mission.goal.x - start.x,
            ),
            "altitude_agl": start.agl_m,
            "fuel": 1.0,
            "time_elapsed": 0.0,
            "mode": MissionMode.TRANSIT,
            "goal_distance": init_goal_dist,
            "observe_done": False,
            "observe_time": 0.0,
            "initial_goal_distance": init_goal_dist,
            "step_count": 0,
            "total_risk": 0.0,
            "min_clearance": 200.0,
            "num_mode_switches": 0,
            "in_observe_box": False,
            "zone_penalty": 0.0,
            "target_agl": start.agl_m,
            "max_time": self.mission.max_episode_time_sec,
            "max_steps": float(self.max_steps),
            "required_observe_time": (
                self.mission.observe_box.required_duration_sec
                if self.mission.observe_box else 10.0
            ),
            "prev_mode": MissionMode.TRANSIT,
            "dist_safe_hold": self._dist_to_nearest(
                start.x, start.y, self.mission.safe_hold_points
            ),
            "dist_alt_lz": self._dist_to_nearest(
                start.x, start.y, self.mission.alternate_lz
            ),
            "dist_observe_box": (
                self.mission.observe_box.distance_to_center(start.x, start.y)
                if self.mission.observe_box else 0.0
            ),
        }

        # Generate initial candidates
        self._update_candidates()

        obs = self.obs_builder.build(
            self._state, self._candidates, self._mask, self._mission_info
        )

        info: dict[str, Any] = {"action_mask": self._mask.copy()}
        return obs, info

    def step(
        self, action: int
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Execute one step: select candidate, execute primitive, update state."""
        assert not self._done, "Environment is done; call reset()."
        self._step_count += 1

        prev_state = dict(self._state)

        # Check if the action is valid
        action_was_invalid = False
        if action < 0 or action >= _K or not self._mask[action]:
            action_was_invalid = True
            # Fall back to first valid action
            valid_indices = np.flatnonzero(self._mask)
            if len(valid_indices) > 0:
                action = int(valid_indices[0])
            else:
                # No valid actions — force hold
                action = 0

        # Decode candidate
        cand_feat = self._candidates[action]
        ptype = self._decode_primitive_type(cand_feat)
        dx = cand_feat[10] * 5000.0
        dy = cand_feat[11] * 5000.0
        target_agl = cand_feat[12] * 200.0

        sx = self._state["x"]
        sy = self._state["y"]
        sz = self._state["z"]
        tx = sx + dx
        ty = sy + dy
        target_elev = self._elevation_at(tx, ty)
        tz = target_elev + target_agl

        # Execute primitive
        result = self.primitive_exec.execute(
            ptype,
            (sx, sy, sz),
            (tx, ty, tz),
            risk_map=self.risk_map,
        )

        # Update agent state
        self._update_agent_state(tx, ty, tz, result, ptype, target_agl)

        # Check termination conditions
        done, success, truncated = self._check_termination()
        self._done = done or truncated

        # Compute reward
        reward, reward_components = self.reward_calc.compute(
            prev_state=prev_state,
            curr_state=self._state,
            action_result=result,
            done=done,
            success=success,
            action_was_invalid=action_was_invalid,
        )

        # Generate new candidates for the next step
        if not self._done:
            self._update_candidates()

        obs = self.obs_builder.build(
            self._state, self._candidates, self._mask, self._mission_info
        )

        info: dict[str, Any] = {
            "action_mask": self._mask.copy(),
            "reward_components": reward_components,
            "primitive_type": ptype.value,
            "action_result": result,
            "success": success,
            "action_was_invalid": action_was_invalid,
        }

        return obs, reward, done, truncated, info

    def action_masks(self) -> np.ndarray:
        """Return the current action validity mask (for MaskablePPO)."""
        return self._mask.copy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_candidates(self) -> None:
        """Regenerate the candidate table and mask."""
        agent_state = {
            "x": self._state["x"],
            "y": self._state["y"],
            "z": self._state["z"],
            "heading": self._state["heading"],
            "mode": self._state["mode"],
            "time_elapsed": self._state["time_elapsed"],
            "goal_distance": self._state["goal_distance"],
            "observe_done": self._state["observe_done"],
        }
        terrain_info = {
            "data": self.dem,
            "transform": self.transform,
            "resolution": self.resolution,
        }
        self._candidates, self._mask = self.candidate_gen.generate_candidates(
            agent_state, self.mission, terrain_info, self.risk_map
        )

    def _update_agent_state(
        self,
        tx: float, ty: float, tz: float,
        result: dict,
        ptype: PrimitiveType,
        target_agl: float,
    ) -> None:
        """Update the internal agent state after executing a primitive."""
        sx = self._state["x"]
        sy = self._state["y"]

        # Position
        self._state["x"] = tx
        self._state["y"] = ty
        self._state["z"] = tz

        # Velocity approximation
        dt = max(result["time_estimate"], 0.01)
        self._state["vx"] = (tx - sx) / dt
        self._state["vy"] = (ty - sy) / dt
        self._state["vz"] = result["altitude_change"] / dt

        # Heading
        dx = tx - sx
        dy = ty - sy
        if dx * dx + dy * dy > 1.0:
            self._state["heading"] = math.atan2(dy, dx)

        # Altitude
        elev = self._elevation_at(tx, ty)
        self._state["altitude_agl"] = tz - elev
        self._state["target_agl"] = target_agl

        # Time and fuel
        self._state["time_elapsed"] += dt
        fuel_burn = dt * 0.0001  # simple linear fuel model
        self._state["fuel"] = max(0.0, self._state["fuel"] - fuel_burn)

        # Risk accumulation
        self._state["total_risk"] += result["integrated_risk"]

        # Clearance tracking
        self._state["min_clearance"] = min(
            self._state["min_clearance"],
            result["min_clearance"],
        )

        # Goal distance
        self._state["goal_distance"] = self.mission.goal_distance(tx, ty)

        # Step count
        self._state["step_count"] = self._step_count

        # Mode transitions
        prev_mode = self._state["mode"]
        new_mode = self._determine_mode_transition(ptype, result)
        if new_mode != prev_mode:
            self._state["num_mode_switches"] += 1
        self._state["prev_mode"] = prev_mode
        self._state["mode"] = new_mode

        # Observation box tracking
        if self.mission.observe_box is not None:
            box = self.mission.observe_box
            in_box = box.contains(tx, ty, tz)
            self._state["in_observe_box"] = in_box
            self._state["dist_observe_box"] = box.distance_to_center(tx, ty)
            if in_box and new_mode in (MissionMode.POPUP_OBSERVE, MissionMode.OBSERVE_SETUP):
                self._state["observe_time"] += dt
                req = box.required_duration_sec
                if self._state["observe_time"] >= req:
                    self._state["observe_done"] = True

        # Zone penalty
        self._state["zone_penalty"] = self._compute_zone_penalty(tx, ty)

        # Safe hold / alt LZ distances
        self._state["dist_safe_hold"] = self._dist_to_nearest(
            tx, ty, self.mission.safe_hold_points
        )
        self._state["dist_alt_lz"] = self._dist_to_nearest(
            tx, ty, self.mission.alternate_lz
        )

    def _determine_mode_transition(
        self, ptype: PrimitiveType, result: dict
    ) -> MissionMode:
        """Attempt a state-machine transition based on the executed primitive."""
        mode = self._state["mode"]
        sm = self.state_machine

        trigger: Optional[str] = None

        # Map primitive types to potential triggers
        if ptype == PrimitiveType.HOLD_POSITION:
            if mode == MissionMode.TRANSIT:
                trigger = "near_safe_hold"
        elif ptype == PrimitiveType.CLIMB_TO_OBSERVE:
            if mode == MissionMode.TRANSIT:
                trigger = "near_observe_box"
            elif mode == MissionMode.OBSERVE_SETUP:
                trigger = "ready"
        elif ptype == PrimitiveType.POPUP_OBSERVE:
            if self._state.get("observe_done", False):
                trigger = "observation_done"
        elif ptype == PrimitiveType.DROP_DOWN_SAFE:
            if mode == MissionMode.DROP_DOWN:
                trigger = "safely_descended"
        elif ptype == PrimitiveType.EGRESS_MASKED:
            if mode == MissionMode.EGRESS:
                trigger = "back_to_transit"
        elif ptype == PrimitiveType.RETURN_HOME:
            gd = self._state["goal_distance"]
            if gd < _GOAL_ARRIVAL_DIST:
                trigger = "at_goal"
            elif mode == MissionMode.EGRESS:
                trigger = "mission_done"
        elif ptype == PrimitiveType.DIVERT_TO_ALT_LZ:
            if mode != MissionMode.DIVERT:
                trigger = "risk_too_high"
            else:
                alt_dist = self._state.get("dist_alt_lz", 9999.0)
                if alt_dist < _GOAL_ARRIVAL_DIST:
                    trigger = "at_alt_lz"

        # Check goal arrival in TRANSIT/RETURN modes
        if trigger is None and mode in (MissionMode.TRANSIT, MissionMode.RETURN_HOME):
            if self._state["goal_distance"] < _GOAL_ARRIVAL_DIST:
                trigger = "at_goal"

        # Attempt transition if we have a valid trigger
        if trigger is not None:
            try:
                new_mode = sm.transition(trigger)
                return new_mode
            except ValueError:
                pass  # Invalid transition — stay in current mode

        return mode

    def _check_termination(self) -> tuple[bool, bool, bool]:
        """Check if the episode should terminate.

        Returns (done, success, truncated).
        """
        mode = self._state["mode"]

        # Terminal state machine modes
        if mode == MissionMode.SUCCESS:
            return True, True, False
        if mode == MissionMode.FAIL:
            return True, False, False

        # Collision check
        if self._state["altitude_agl"] < 0.5:
            return True, False, False

        # Time limit
        if self._state["time_elapsed"] >= self.mission.max_episode_time_sec:
            return True, False, True

        # Step limit
        if self._step_count >= self.max_steps:
            return False, False, True

        # Fuel exhaustion
        if self._state["fuel"] <= 0.0:
            return True, False, False

        return False, False, False

    def _elevation_at(self, x: float, y: float) -> float:
        """Sample DEM elevation at world coordinates."""
        inv = ~self.transform
        col_f, row_f = inv * (x, y)
        r = max(0, min(int(round(row_f)), self.dem.shape[0] - 1))
        c = max(0, min(int(round(col_f)), self.dem.shape[1] - 1))
        return float(self.dem[r, c])

    def _compute_zone_penalty(self, x: float, y: float) -> float:
        """Penalty for being near or outside the DEM boundary."""
        inv = ~self.transform
        col_f, row_f = inv * (x, y)
        h, w = self.dem.shape
        margin = 5.0
        x_pen = max(0.0, margin - col_f, col_f - (w - margin))
        y_pen = max(0.0, margin - row_f, row_f - (h - margin))
        return min(1.0, (x_pen + y_pen) / (2.0 * margin))

    @staticmethod
    def _dist_to_nearest(x: float, y: float, points: list) -> float:
        """Distance to the nearest point in a list of WaypointXYZ."""
        if not points:
            return 0.0
        return min(
            math.sqrt((x - p.x) ** 2 + (y - p.y) ** 2) for p in points
        )

    @staticmethod
    def _decode_primitive_type(cand_feat: np.ndarray) -> PrimitiveType:
        """Decode PrimitiveType from the one-hot encoding in features[0:10]."""
        one_hot = cand_feat[:10]
        idx = int(np.argmax(one_hot))
        ptype_list = list(PrimitiveType)
        if idx < len(ptype_list):
            return ptype_list[idx]
        return PrimitiveType.HOLD_POSITION

    def _build_mission_info(self) -> dict:
        """Build the static mission info dict for observations."""
        start = self.mission.start
        goal = self.mission.goal
        terrain_flat = self.dem.ravel()
        return {
            "goal_x": goal.x,
            "goal_y": goal.y,
            "start_x": start.x,
            "start_y": start.y,
            "max_time": self.mission.max_episode_time_sec,
            "has_observe_box": self.mission.observe_box is not None,
            "observe_box_dist": (
                self.mission.observe_box.distance_to_center(start.x, start.y)
                if self.mission.observe_box else 0.0
            ),
            "num_safe_holds": len(self.mission.safe_hold_points),
            "num_alternate_lz": len(self.mission.alternate_lz),
            "terrain_mean_elev": float(terrain_flat.mean()),
            "terrain_std_elev": float(terrain_flat.std()),
        }
