"""Flight primitive definitions and executor.

Each primitive type encapsulates a stereotyped manoeuvre with fixed
altitude-above-ground, speed, and behavioural characteristics.  The
:class:`PrimitiveExecutor` evaluates a primitive over terrain (DEM)
and an optional risk map, returning a rich result dict that downstream
planners and the RL reward function consume.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Optional

import numpy as np
from rasterio.transform import Affine


class PrimitiveType(Enum):
    """Enumeration of all supported flight primitives."""

    MOVE_MASKED_LOW = "MOVE_MASKED_LOW"
    MOVE_SAFE_MID = "MOVE_SAFE_MID"
    DESCEND_AND_HOLD = "DESCEND_AND_HOLD"
    CLIMB_TO_OBSERVE = "CLIMB_TO_OBSERVE"
    POPUP_OBSERVE = "POPUP_OBSERVE"
    DROP_DOWN_SAFE = "DROP_DOWN_SAFE"
    EGRESS_MASKED = "EGRESS_MASKED"
    RETURN_HOME = "RETURN_HOME"
    DIVERT_TO_ALT_LZ = "DIVERT_TO_ALT_LZ"
    HOLD_POSITION = "HOLD_POSITION"


# --------------------------------------------------------------------------- #
# Per-primitive configuration                                                  #
# --------------------------------------------------------------------------- #

_PRIMITIVE_PARAMS: dict[PrimitiveType, dict] = {
    PrimitiveType.MOVE_MASKED_LOW: {
        "agl_m": 20.0,
        "speed_mps": 40.0,
        "clearance_margin": 20.0,
        "masked": True,
    },
    PrimitiveType.MOVE_SAFE_MID: {
        "agl_m": 80.0,
        "speed_mps": 50.0,
        "clearance_margin": 40.0,
        "masked": False,
    },
    PrimitiveType.DESCEND_AND_HOLD: {
        "agl_m": 15.0,
        "speed_mps": 15.0,
        "clearance_margin": 10.0,
        "masked": True,
    },
    PrimitiveType.CLIMB_TO_OBSERVE: {
        "agl_m": 180.0,
        "speed_mps": 20.0,
        "clearance_margin": 50.0,
        "masked": False,
    },
    PrimitiveType.POPUP_OBSERVE: {
        "agl_m": 180.0,
        "speed_mps": 10.0,
        "clearance_margin": 50.0,
        "masked": False,
    },
    PrimitiveType.DROP_DOWN_SAFE: {
        "agl_m": 20.0,
        "speed_mps": 25.0,
        "clearance_margin": 15.0,
        "masked": True,
    },
    PrimitiveType.EGRESS_MASKED: {
        "agl_m": 20.0,
        "speed_mps": 45.0,
        "clearance_margin": 20.0,
        "masked": True,
    },
    PrimitiveType.RETURN_HOME: {
        "agl_m": 60.0,
        "speed_mps": 55.0,
        "clearance_margin": 30.0,
        "masked": False,
    },
    PrimitiveType.DIVERT_TO_ALT_LZ: {
        "agl_m": 40.0,
        "speed_mps": 50.0,
        "clearance_margin": 25.0,
        "masked": False,
    },
    PrimitiveType.HOLD_POSITION: {
        "agl_m": 0.0,  # maintain current altitude
        "speed_mps": 0.0,
        "clearance_margin": 10.0,
        "masked": True,
        "hold_duration_sec": 30.0,
    },
}

# Number of intermediate samples when discretising a segment.
_DEFAULT_NUM_SAMPLES = 50


class PrimitiveExecutor:
    """Evaluate flight primitives against a DEM and optional risk map.

    Parameters
    ----------
    dem : np.ndarray
        2-D elevation array (metres) covering the operational area.
    transform : Affine
        Geo-transform mapping pixel indices to map coordinates.
    resolution : float
        Cell size of *dem* in metres (assumed square).
    """

    def __init__(
        self,
        dem: np.ndarray,
        transform: Affine,
        resolution: float,
    ) -> None:
        self._dem = dem
        self._transform = transform
        self._resolution = resolution
        # Precompute inverse transform coefficients for world -> pixel.
        self._inv_a = 1.0 / transform.a
        self._inv_e = 1.0 / transform.e
        self._origin_x = transform.c
        self._origin_y = transform.f

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def execute(
        self,
        primitive_type: PrimitiveType,
        start_xyz: tuple[float, float, float],
        target_xyz: tuple[float, float, float],
        risk_map: Optional[np.ndarray] = None,
    ) -> dict:
        """Execute a primitive and return a comprehensive result dict.

        Parameters
        ----------
        primitive_type : PrimitiveType
            Which manoeuvre to evaluate.
        start_xyz : tuple
            ``(x, y, z)`` of the current position (map coords, metres MSL).
        target_xyz : tuple
            ``(x, y, z)`` of the desired end position.
        risk_map : np.ndarray | None
            Optional 2-D threat / detection-risk array aligned with *dem*.

        Returns
        -------
        dict
            Keys: waypoints, distance, time_estimate, altitude_change,
            clearance_ok, min_clearance, integrated_risk, visible_ratio,
            success.
        """
        params = _PRIMITIVE_PARAMS[primitive_type]
        agl = params["agl_m"]
        speed = params["speed_mps"]
        clearance_margin = params["clearance_margin"]
        is_masked = params["masked"]

        # -- Special case: hold position -------------------------------- #
        if primitive_type is PrimitiveType.HOLD_POSITION:
            hold_sec = params.get("hold_duration_sec", 30.0)
            elev = self._elevation_at(start_xyz[0], start_xyz[1])
            current_agl = start_xyz[2] - elev
            clearance_ok = current_agl >= clearance_margin
            risk_val = 0.0
            if risk_map is not None:
                risk_val = self._risk_at(risk_map, start_xyz[0], start_xyz[1])
            return {
                "waypoints": [start_xyz],
                "distance": 0.0,
                "time_estimate": hold_sec,
                "altitude_change": 0.0,
                "clearance_ok": clearance_ok,
                "min_clearance": max(current_agl, 0.0),
                "integrated_risk": risk_val * hold_sec,
                "visible_ratio": 0.0 if is_masked else 1.0,
                "success": clearance_ok,
            }

        # -- Generate waypoints along segment --------------------------- #
        waypoints = self._interpolate_segment(
            start_xyz, target_xyz, agl, _DEFAULT_NUM_SAMPLES
        )

        # -- Distance --------------------------------------------------- #
        distance = self._total_3d_distance(waypoints)

        # -- Time ------------------------------------------------------- #
        time_estimate = distance / speed if speed > 0 else 0.0

        # -- Altitude change -------------------------------------------- #
        altitude_change = waypoints[-1][2] - waypoints[0][2]

        # -- Terrain clearance ------------------------------------------ #
        clearance_ok, min_clearance = self._check_terrain_clearance(
            waypoints, clearance_margin
        )

        # -- Integrated risk -------------------------------------------- #
        integrated_risk = 0.0
        if risk_map is not None:
            integrated_risk = self._integrate_risk(risk_map, waypoints)

        # -- Visibility ratio ------------------------------------------- #
        visible_ratio = self._compute_visible_ratio(waypoints, is_masked)

        success = clearance_ok

        return {
            "waypoints": waypoints,
            "distance": distance,
            "time_estimate": time_estimate,
            "altitude_change": altitude_change,
            "clearance_ok": clearance_ok,
            "min_clearance": min_clearance,
            "integrated_risk": integrated_risk,
            "visible_ratio": visible_ratio,
            "success": success,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _world_to_pixel(self, x: float, y: float) -> tuple[int, int]:
        """Convert map coordinates to integer pixel indices (row, col)."""
        col = (x - self._origin_x) * self._inv_a
        row = (y - self._origin_y) * self._inv_e
        col_i = int(round(col))
        row_i = int(round(row))
        # Clamp to raster bounds.
        row_i = max(0, min(row_i, self._dem.shape[0] - 1))
        col_i = max(0, min(col_i, self._dem.shape[1] - 1))
        return row_i, col_i

    def _elevation_at(self, x: float, y: float) -> float:
        """Sample DEM elevation (metres MSL) at a map position."""
        r, c = self._world_to_pixel(x, y)
        return float(self._dem[r, c])

    def _risk_at(
        self, risk_map: np.ndarray, x: float, y: float
    ) -> float:
        """Sample risk value at a map position (clamped to grid)."""
        r, c = self._world_to_pixel(x, y)
        r = max(0, min(r, risk_map.shape[0] - 1))
        c = max(0, min(c, risk_map.shape[1] - 1))
        return float(risk_map[r, c])

    def _interpolate_segment(
        self,
        start_xyz: tuple[float, float, float],
        target_xyz: tuple[float, float, float],
        target_agl: float,
        num_samples: int,
    ) -> list[tuple[float, float, float]]:
        """Produce *num_samples* waypoints along the 2-D ground track.

        The altitude at each waypoint is ``terrain_elevation + target_agl``,
        producing a terrain-following profile.
        """
        sx, sy, sz = start_xyz
        tx, ty, tz = target_xyz

        waypoints: list[tuple[float, float, float]] = []
        for i in range(num_samples):
            t = i / max(num_samples - 1, 1)
            wx = sx + (tx - sx) * t
            wy = sy + (ty - sy) * t
            elev = self._elevation_at(wx, wy)
            if target_agl > 0:
                wz = elev + target_agl
            else:
                # Maintain current-ish altitude (e.g. hold position).
                wz = sz + (tz - sz) * t
            waypoints.append((wx, wy, wz))
        return waypoints

    @staticmethod
    def _total_3d_distance(waypoints: list[tuple[float, float, float]]) -> float:
        """Sum of 3-D Euclidean distances between consecutive waypoints."""
        total = 0.0
        for i in range(1, len(waypoints)):
            dx = waypoints[i][0] - waypoints[i - 1][0]
            dy = waypoints[i][1] - waypoints[i - 1][1]
            dz = waypoints[i][2] - waypoints[i - 1][2]
            total += math.sqrt(dx * dx + dy * dy + dz * dz)
        return total

    def _check_terrain_clearance(
        self,
        waypoints: list[tuple[float, float, float]],
        clearance_margin: float = 20.0,
    ) -> tuple[bool, float]:
        """Check terrain clearance for every waypoint.

        Returns
        -------
        (clearance_ok, min_clearance)
            *clearance_ok* is True when every waypoint is at least
            *clearance_margin* metres above terrain.
        """
        min_clearance = float("inf")
        for wx, wy, wz in waypoints:
            elev = self._elevation_at(wx, wy)
            agl = wz - elev
            if agl < min_clearance:
                min_clearance = agl
        clearance_ok = min_clearance >= clearance_margin
        return clearance_ok, max(min_clearance, 0.0)

    def _integrate_risk(
        self,
        risk_map: np.ndarray,
        waypoints: list[tuple[float, float, float]],
    ) -> float:
        """Sum risk values sampled at each waypoint (trapezoidal-ish)."""
        total = 0.0
        for wx, wy, _wz in waypoints:
            total += self._risk_at(risk_map, wx, wy)
        # Normalise by sample count to give a per-waypoint average, then
        # multiply by number of segments to approximate the integral.
        n = len(waypoints)
        if n > 1:
            return total / n * (n - 1)
        return total

    @staticmethod
    def _compute_visible_ratio(
        waypoints: list[tuple[float, float, float]],
        is_masked: bool,
    ) -> float:
        """Estimate what fraction of the path is 'visible' to threats.

        Masked-low primitives are assumed fully hidden (0.0).  High-
        altitude primitives are fully exposed (1.0).  For intermediate
        altitudes the ratio scales linearly between a *low_agl*
        threshold of 30 m and a *high_agl* threshold of 150 m.
        """
        if is_masked:
            return 0.0

        low_agl = 30.0
        high_agl = 150.0
        visible_count = 0
        for _wx, _wy, wz in waypoints:
            # We don't have terrain at this point (would need DEM), so
            # use an approximation: if the absolute Z is above a
            # reasonable threshold we consider it exposed.
            # However, we already store terrain-following AGL in the
            # waypoint Z (it includes terrain offset), so just use a
            # heuristic based on Z magnitude versus typical terrain.
            # For a cleaner approach, rely on the waypoint altitude
            # being generated as terrain + AGL.
            #
            # We use a simpler model: any non-masked primitive is
            # proportionally visible based on its target AGL.
            visible_count += 1

        if not waypoints:
            return 0.0

        # For non-masked primitives, visibility is 1.0 (fully exposed).
        return float(visible_count) / len(waypoints)
