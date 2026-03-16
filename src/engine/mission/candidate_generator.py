"""Candidate action generator for the RL path-planning agent.

Produces a fixed-size batch of candidate next-actions (``K=32`` by
default).  Each candidate is a feature vector of length 24 describing
a proposed manoeuvre.  A companion boolean mask indicates which
candidates are valid given the current mission state, terrain, and
risk environment.
"""
from __future__ import annotations

import math
from typing import Optional, TYPE_CHECKING

import numpy as np

from .primitives import PrimitiveType, PrimitiveExecutor
from .state_machine import MissionMode

if TYPE_CHECKING:
    from .schema import Mission

# Number of primitive types (one-hot width).
_NUM_TYPES = len(PrimitiveType)  # 10
# Total feature width per candidate.
_FEATURE_DIM = 24

# Mapping from PrimitiveType to a zero-based index for one-hot encoding.
_TYPE_INDEX: dict[PrimitiveType, int] = {
    pt: i for i, pt in enumerate(PrimitiveType)
}

# Default speed (m/s) per primitive — mirrors primitives.py params.
_SPEED: dict[PrimitiveType, float] = {
    PrimitiveType.MOVE_MASKED_LOW: 40.0,
    PrimitiveType.MOVE_SAFE_MID: 50.0,
    PrimitiveType.DESCEND_AND_HOLD: 15.0,
    PrimitiveType.CLIMB_TO_OBSERVE: 20.0,
    PrimitiveType.POPUP_OBSERVE: 10.0,
    PrimitiveType.DROP_DOWN_SAFE: 25.0,
    PrimitiveType.EGRESS_MASKED: 45.0,
    PrimitiveType.RETURN_HOME: 55.0,
    PrimitiveType.DIVERT_TO_ALT_LZ: 50.0,
    PrimitiveType.HOLD_POSITION: 0.0,
}

# Target AGL per primitive.
_AGL: dict[PrimitiveType, float] = {
    PrimitiveType.MOVE_MASKED_LOW: 20.0,
    PrimitiveType.MOVE_SAFE_MID: 80.0,
    PrimitiveType.DESCEND_AND_HOLD: 15.0,
    PrimitiveType.CLIMB_TO_OBSERVE: 180.0,
    PrimitiveType.POPUP_OBSERVE: 180.0,
    PrimitiveType.DROP_DOWN_SAFE: 20.0,
    PrimitiveType.EGRESS_MASKED: 20.0,
    PrimitiveType.RETURN_HOME: 60.0,
    PrimitiveType.DIVERT_TO_ALT_LZ: 40.0,
    PrimitiveType.HOLD_POSITION: 0.0,
}

# Default configuration.
_DEFAULT_CONFIG: dict = {
    "max_candidates": 32,
    "distance_bands": [200.0, 500.0, 1000.0, 2000.0],
    "heading_samples": 8,
    "agl_bands": [20.0, 80.0, 180.0],
    "counts": {
        "transit": 10,
        "hold": 2,
        "observe": 4,
        "popup": 3,
        "egress": 3,
        "return": 3,
        "divert": 2,
        "safe_mid": 2,
        "descend": 2,
        "dropdown": 1,
    },
}


class CandidateGenerator:
    """Generate a fixed-size array of candidate next-actions.

    Parameters
    ----------
    config : dict
        Configuration dictionary.  Recognised keys:

        - ``max_candidates`` (int): K, number of slots (default 32).
        - ``distance_bands`` (list[float]): radii in metres to sample.
        - ``heading_samples`` (int): angular resolution for transit.
        - ``agl_bands`` (list[float]): altitude bands for variety.
        - ``counts`` (dict): per-type allocation budget.
    """

    def __init__(self, config: dict) -> None:
        merged = {**_DEFAULT_CONFIG, **config}
        self.max_candidates: int = int(merged["max_candidates"])
        self.distance_bands: list[float] = list(merged["distance_bands"])
        self.heading_samples: int = int(merged["heading_samples"])
        self.agl_bands: list[float] = list(merged["agl_bands"])
        self.counts: dict[str, int] = dict(merged["counts"])

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def generate_candidates(
        self,
        state: dict,
        mission: "Mission",
        terrain_data: dict,
        risk_data: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build candidate feature matrix and validity mask.

        Parameters
        ----------
        state : dict
            Current agent state with keys: ``x``, ``y``, ``z``,
            ``heading`` (radians), ``mode`` (:class:`MissionMode`),
            ``time_elapsed``, ``goal_distance``, ``observe_done``.
        mission : Mission
            Active mission specification.
        terrain_data : dict
            Must contain ``"data"`` (2-D DEM ndarray), ``"transform"``
            (Affine), and ``"resolution"`` (float or tuple).
        risk_data : np.ndarray | None
            Optional 2-D risk/threat array aligned with the DEM.

        Returns
        -------
        (candidates, mask)
            ``candidates`` is ``(K, 24)`` float32; ``mask`` is ``(K,)``
            bool where ``True`` means the slot contains a valid action.
        """
        K = self.max_candidates
        candidates = np.zeros((K, _FEATURE_DIM), dtype=np.float32)
        mask = np.zeros(K, dtype=bool)

        dem = terrain_data["data"]
        transform = terrain_data["transform"]
        res = terrain_data["resolution"]
        if isinstance(res, (list, tuple)):
            resolution = float(res[0])
        else:
            resolution = float(res)

        sx = float(state["x"])
        sy = float(state["y"])
        sz = float(state["z"])
        heading = float(state["heading"])
        mode: MissionMode = state["mode"]
        time_elapsed = float(state["time_elapsed"])
        goal_dist = float(state["goal_distance"])
        observe_done = bool(state["observe_done"])

        executor = PrimitiveExecutor(dem, transform, resolution)

        # Collect raw candidate descriptors: (PrimitiveType, target_x, target_y, target_agl).
        raw: list[tuple[PrimitiveType, float, float, float]] = []

        # ---- Transit candidates ---------------------------------------- #
        raw.extend(
            self._transit_candidates(sx, sy, heading, mission, goal_dist)
        )

        # ---- Safe-mid transit ------------------------------------------ #
        raw.extend(
            self._safe_mid_candidates(sx, sy, heading, mission, goal_dist)
        )

        # ---- Hold candidates ------------------------------------------- #
        raw.extend(self._hold_candidates(sx, sy, sz))

        # ---- Observe candidates ---------------------------------------- #
        raw.extend(
            self._observe_candidates(sx, sy, mission, mode, observe_done)
        )

        # ---- Popup candidates ------------------------------------------ #
        raw.extend(
            self._popup_candidates(sx, sy, mission, mode, observe_done)
        )

        # ---- Egress candidates ----------------------------------------- #
        raw.extend(self._egress_candidates(sx, sy, heading, mission, mode))

        # ---- Return-home candidates ------------------------------------ #
        raw.extend(self._return_candidates(sx, sy, mission, mode))

        # ---- Descend-and-hold candidates --------------------------------- #
        raw.extend(
            self._descend_candidates(sx, sy, sz, mission, mode)
        )

        # ---- Drop-down-safe candidates ----------------------------------- #
        raw.extend(
            self._dropdown_candidates(sx, sy, mission, mode)
        )

        # ---- Divert candidates ----------------------------------------- #
        raw.extend(self._divert_candidates(sx, sy, mission))

        # Trim / pad to K slots.
        if len(raw) > K:
            raw = raw[:K]

        # Fill feature vectors.
        for idx, (ptype, tx, ty, target_agl) in enumerate(raw):
            features = self._compute_features(
                ptype,
                sx, sy, sz,
                tx, ty, target_agl,
                heading,
                goal_dist,
                time_elapsed,
                observe_done,
                mission,
                executor,
                dem,
                transform,
                resolution,
                risk_data,
            )
            candidates[idx, :] = features
            mask[idx] = True

        return candidates, mask

    # ------------------------------------------------------------------ #
    # Candidate generators (per type)                                     #
    # ------------------------------------------------------------------ #

    def _transit_candidates(
        self,
        sx: float, sy: float,
        heading: float,
        mission: "Mission",
        goal_dist: float,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Low-altitude masked transit candidates towards goal with noise."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("transit", 12)
        goal_heading = math.atan2(
            mission.goal.y - sy, mission.goal.x - sx
        )

        idx = 0
        for dist in self.distance_bands:
            # Don't propose distances longer than remaining goal distance.
            d = min(dist, goal_dist) if goal_dist > 0 else dist
            # Sample headings centred on goal heading.
            num_h = max(1, n // len(self.distance_bands))
            for hi in range(num_h):
                if idx >= n:
                    break
                angle_offset = (
                    (hi - num_h / 2.0) * (2.0 * math.pi / self.heading_samples)
                )
                h = goal_heading + angle_offset
                tx = sx + d * math.cos(h)
                ty = sy + d * math.sin(h)
                results.append(
                    (PrimitiveType.MOVE_MASKED_LOW, tx, ty, _AGL[PrimitiveType.MOVE_MASKED_LOW])
                )
                idx += 1
            if idx >= n:
                break
        return results[:n]

    def _safe_mid_candidates(
        self,
        sx: float, sy: float,
        heading: float,
        mission: "Mission",
        goal_dist: float,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Mid-altitude safe-transit candidates."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("safe_mid", 2)
        goal_heading = math.atan2(
            mission.goal.y - sy, mission.goal.x - sx
        )
        for i in range(n):
            dist = self.distance_bands[min(i, len(self.distance_bands) - 1)]
            d = min(dist, goal_dist) if goal_dist > 0 else dist
            offset = (i - n / 2.0) * 0.3
            h = goal_heading + offset
            tx = sx + d * math.cos(h)
            ty = sy + d * math.sin(h)
            results.append(
                (PrimitiveType.MOVE_SAFE_MID, tx, ty, _AGL[PrimitiveType.MOVE_SAFE_MID])
            )
        return results

    def _hold_candidates(
        self, sx: float, sy: float, sz: float
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Hold-position candidates (stay in place)."""
        n = self.counts.get("hold", 3)
        results: list[tuple[PrimitiveType, float, float, float]] = []
        for i in range(n):
            # Slight altitude variations.
            agl_offset = (i - 1) * 10.0
            results.append(
                (PrimitiveType.HOLD_POSITION, sx, sy, max(15.0, 20.0 + agl_offset))
            )
        return results

    def _observe_candidates(
        self,
        sx: float, sy: float,
        mission: "Mission",
        mode: MissionMode,
        observe_done: bool,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Climb-to-observe candidates — only valid near the observe box."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("observe", 4)
        if observe_done:
            return results
        if mission.observe_box is None:
            return results
        box = mission.observe_box
        dist_to_box = box.distance_to_center(sx, sy)
        # Only generate if within 3 km of the observation box.
        if dist_to_box > 3000.0:
            return results
        # Candidates: approach the box centre from different offsets.
        for i in range(n):
            angle = 2.0 * math.pi * i / n
            offset = min(box.size_x, box.size_y) * 0.3
            tx = box.center_x + offset * math.cos(angle)
            ty = box.center_y + offset * math.sin(angle)
            results.append(
                (PrimitiveType.CLIMB_TO_OBSERVE, tx, ty, _AGL[PrimitiveType.CLIMB_TO_OBSERVE])
            )
        return results

    def _popup_candidates(
        self,
        sx: float, sy: float,
        mission: "Mission",
        mode: MissionMode,
        observe_done: bool,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Pop-up observe candidates — only valid in OBSERVE_SETUP or POPUP."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("popup", 3)
        if observe_done:
            return results
        if mission.observe_box is None:
            return results
        if mode not in (MissionMode.OBSERVE_SETUP, MissionMode.POPUP_OBSERVE):
            return results
        box = mission.observe_box
        for i in range(n):
            angle = 2.0 * math.pi * i / n
            r = min(box.size_x, box.size_y) * 0.2
            tx = box.center_x + r * math.cos(angle)
            ty = box.center_y + r * math.sin(angle)
            results.append(
                (PrimitiveType.POPUP_OBSERVE, tx, ty, _AGL[PrimitiveType.POPUP_OBSERVE])
            )
        return results

    def _egress_candidates(
        self,
        sx: float, sy: float,
        heading: float,
        mission: "Mission",
        mode: MissionMode,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Egress candidates — masked retreat after observation."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("egress", 3)
        if mode not in (
            MissionMode.DROP_DOWN,
            MissionMode.EGRESS,
            MissionMode.POPUP_OBSERVE,
            MissionMode.OBSERVE_SETUP,
        ):
            return results
        # Head generally away from the observe box and towards the goal.
        goal_heading = math.atan2(
            mission.goal.y - sy, mission.goal.x - sx
        )
        for i in range(n):
            dist = self.distance_bands[min(i, len(self.distance_bands) - 1)]
            offset = (i - n / 2.0) * 0.4
            h = goal_heading + offset
            tx = sx + dist * math.cos(h)
            ty = sy + dist * math.sin(h)
            results.append(
                (PrimitiveType.EGRESS_MASKED, tx, ty, _AGL[PrimitiveType.EGRESS_MASKED])
            )
        return results

    def _return_candidates(
        self,
        sx: float, sy: float,
        mission: "Mission",
        mode: MissionMode,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Return-home candidates — head to goal/start."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("return", 3)
        if mode not in (
            MissionMode.EGRESS,
            MissionMode.TRANSIT,
            MissionMode.RETURN_HOME,
        ):
            return results
        # Primary: go straight to goal.
        results.append(
            (PrimitiveType.RETURN_HOME, mission.goal.x, mission.goal.y,
             _AGL[PrimitiveType.RETURN_HOME])
        )
        # Intermediate waypoints towards goal.
        goal_heading = math.atan2(
            mission.goal.y - sy, mission.goal.x - sx
        )
        goal_dist = mission.goal_distance(sx, sy)
        for i in range(1, n):
            frac = min(1.0, (i * 0.33))
            d = goal_dist * frac
            offset = (i - 1) * 0.15
            h = goal_heading + offset
            tx = sx + d * math.cos(h)
            ty = sy + d * math.sin(h)
            results.append(
                (PrimitiveType.RETURN_HOME, tx, ty, _AGL[PrimitiveType.RETURN_HOME])
            )
        return results[:n]

    def _descend_candidates(
        self,
        sx: float, sy: float, sz: float,
        mission: "Mission",
        mode: MissionMode,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Descend-and-hold candidates — descend to low altitude and loiter."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("descend", 2)
        # Only useful when at mid/high altitude or approaching safe holds
        if mode not in (
            MissionMode.TRANSIT,
            MissionMode.OBSERVE_SETUP,
            MissionMode.SAFE_HOLD,
        ):
            return results
        # Near safe-hold points or current position with low AGL
        targets: list[tuple[float, float]] = [(sx, sy)]
        for sp in mission.safe_hold_points[:n - 1]:
            targets.append((sp.x, sp.y))
        for tx, ty in targets[:n]:
            results.append(
                (PrimitiveType.DESCEND_AND_HOLD, tx, ty,
                 _AGL[PrimitiveType.DESCEND_AND_HOLD])
            )
        return results[:n]

    def _dropdown_candidates(
        self,
        sx: float, sy: float,
        mission: "Mission",
        mode: MissionMode,
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Drop-down-safe candidates — rapid descent after observation."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("dropdown", 1)
        if mode not in (
            MissionMode.POPUP_OBSERVE,
            MissionMode.DROP_DOWN,
            MissionMode.OBSERVE_SETUP,
        ):
            return results
        # Drop down towards goal direction at low altitude
        goal_heading = math.atan2(
            mission.goal.y - sy, mission.goal.x - sx
        )
        for i in range(n):
            dist = self.distance_bands[0] * 0.5  # short distance
            offset = (i - n / 2.0) * 0.3
            h = goal_heading + offset
            tx = sx + dist * math.cos(h)
            ty = sy + dist * math.sin(h)
            results.append(
                (PrimitiveType.DROP_DOWN_SAFE, tx, ty,
                 _AGL[PrimitiveType.DROP_DOWN_SAFE])
            )
        return results[:n]

    def _divert_candidates(
        self,
        sx: float, sy: float,
        mission: "Mission",
    ) -> list[tuple[PrimitiveType, float, float, float]]:
        """Divert candidates — head to alternate LZs."""
        results: list[tuple[PrimitiveType, float, float, float]] = []
        n = self.counts.get("divert", 2)
        if not mission.alternate_lz:
            # If no alternate LZs, create a divert towards start.
            results.append(
                (PrimitiveType.DIVERT_TO_ALT_LZ,
                 mission.start.x, mission.start.y,
                 _AGL[PrimitiveType.DIVERT_TO_ALT_LZ])
            )
            return results[:n]
        # One candidate per alternate LZ (up to budget).
        for alt in mission.alternate_lz[:n]:
            results.append(
                (PrimitiveType.DIVERT_TO_ALT_LZ, alt.x, alt.y,
                 _AGL[PrimitiveType.DIVERT_TO_ALT_LZ])
            )
        return results[:n]

    # ------------------------------------------------------------------ #
    # Feature computation                                                 #
    # ------------------------------------------------------------------ #

    def _compute_features(
        self,
        ptype: PrimitiveType,
        sx: float, sy: float, sz: float,
        tx: float, ty: float, target_agl: float,
        heading: float,
        goal_dist: float,
        time_elapsed: float,
        observe_done: bool,
        mission: "Mission",
        executor: PrimitiveExecutor,
        dem: np.ndarray,
        transform,
        resolution: float,
        risk_data: Optional[np.ndarray],
    ) -> np.ndarray:
        """Build a 24-element feature vector for one candidate.

        Layout (indices):
            [0..9]  : one-hot primitive type  (10 features)
            [10]    : rel_dx  (target_x - sx, normalised)
            [11]    : rel_dy  (target_y - sy, normalised)
            [12]    : target_agl (metres, normalised by 200)
            [13]    : distance (3-D metres, normalised by 5000)
            [14]    : time_est (seconds, normalised by 300)
            [15]    : goal_progress  (fraction 0..1 of remaining goal_dist saved)
            [16]    : integrated_risk  (normalised by 100)
            [17]    : visible_ratio   (0..1)
            [18]    : clearance_margin (min AGL, normalised by 200)
            [19]    : turn_cost  (absolute heading change, normalised by pi)
            [20]    : observe_feasible (0 or 1)
            [21]    : hold_quality  (0..1, how good the hold spot is)
            [22]    : zone_penalty  (0..1, proximity to boundary)
            [23]    : (padding / reserved)
        """
        feat = np.zeros(_FEATURE_DIM, dtype=np.float32)

        # -- One-hot type encoding ---------------------------------------- #
        feat[_TYPE_INDEX[ptype]] = 1.0

        # -- Relative displacement ---------------------------------------- #
        dx = tx - sx
        dy = ty - sy
        horiz_dist = math.sqrt(dx * dx + dy * dy)
        feat[10] = dx / 5000.0
        feat[11] = dy / 5000.0

        # -- Target AGL --------------------------------------------------- #
        feat[12] = target_agl / 200.0

        # -- Execute primitive to get enriched metrics -------------------- #
        # Sample terrain elevation at target for the target Z.
        target_elev = self._sample_elevation(dem, transform, resolution, tx, ty)
        target_z = target_elev + target_agl

        result = executor.execute(
            ptype,
            (sx, sy, sz),
            (tx, ty, target_z),
            risk_map=risk_data,
        )

        distance_3d = result["distance"]
        feat[13] = distance_3d / 5000.0

        feat[14] = result["time_estimate"] / 300.0

        # -- Goal progress ------------------------------------------------ #
        if goal_dist > 1.0:
            new_goal_dist = mission.goal_distance(tx, ty)
            progress = (goal_dist - new_goal_dist) / goal_dist
            feat[15] = max(-1.0, min(1.0, progress))
        else:
            feat[15] = 1.0

        # -- Risk --------------------------------------------------------- #
        feat[16] = result["integrated_risk"] / 100.0

        # -- Visibility --------------------------------------------------- #
        feat[17] = result["visible_ratio"]

        # -- Clearance ---------------------------------------------------- #
        feat[18] = result["min_clearance"] / 200.0

        # -- Turn cost ---------------------------------------------------- #
        candidate_heading = math.atan2(dy, dx) if horiz_dist > 1.0 else heading
        turn = abs(self._wrap_angle(candidate_heading - heading))
        feat[19] = turn / math.pi

        # -- Observe feasibility ------------------------------------------ #
        if mission.observe_box is not None and not observe_done:
            box = mission.observe_box
            dist_to_box = box.distance_to_center(tx, ty)
            # Feasible if the candidate lands inside or very close to the box.
            feasible_threshold = max(box.size_x, box.size_y) * 0.6
            feat[20] = 1.0 if dist_to_box <= feasible_threshold else 0.0
        else:
            feat[20] = 0.0

        # -- Hold quality ------------------------------------------------- #
        if ptype == PrimitiveType.HOLD_POSITION:
            # Higher quality if clearance is good and risk is low.
            clr_score = min(result["min_clearance"] / 50.0, 1.0)
            risk_score = max(0.0, 1.0 - result["integrated_risk"] / 50.0)
            feat[21] = 0.5 * clr_score + 0.5 * risk_score
        else:
            feat[21] = 0.0

        # -- Zone penalty ------------------------------------------------- #
        # Penalise candidates that go outside the DEM coverage.
        dem_h, dem_w = dem.shape
        inv_a = 1.0 / transform.a
        inv_e = 1.0 / transform.e
        col = (tx - transform.c) * inv_a
        row = (ty - transform.f) * inv_e
        margin_cells = 5.0
        x_penalty = max(0.0, margin_cells - col, col - (dem_w - margin_cells))
        y_penalty = max(0.0, margin_cells - row, row - (dem_h - margin_cells))
        raw_penalty = (x_penalty + y_penalty) / (2.0 * margin_cells)
        feat[22] = min(1.0, raw_penalty)

        # feat[23] reserved / zero-padded.
        return feat

    # ------------------------------------------------------------------ #
    # Utility helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sample_elevation(
        dem: np.ndarray,
        transform,
        resolution: float,
        x: float,
        y: float,
    ) -> float:
        """Sample DEM elevation at world coordinates *(x, y)*."""
        col = (x - transform.c) / transform.a
        row = (y - transform.f) / transform.e
        r = int(round(row))
        c = int(round(col))
        r = max(0, min(r, dem.shape[0] - 1))
        c = max(0, min(c, dem.shape[1] - 1))
        return float(dem[r, c])

    @staticmethod
    def _wrap_angle(angle: float) -> float:
        """Wrap an angle to the range ``[-pi, pi]``."""
        return ((angle + math.pi) % (2.0 * math.pi)) - math.pi
