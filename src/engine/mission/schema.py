"""Mission schema definitions using Pydantic v2.

Provides structured models for waypoints, observation boxes, and full
mission specifications.  Includes a YAML loader for deserialising
mission files stored on disk.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class WaypointXYZ(BaseModel):
    """A 3-D waypoint expressed in local (UTM-metres) coordinates.

    ``agl_m`` is the desired altitude above ground level; defaults to
    30 m which is a typical nap-of-earth flight altitude.
    """

    x: float
    y: float
    agl_m: float = 30.0


class ObserveBoxMission(BaseModel):
    """Axis-aligned observation volume the agent must loiter inside.

    The box is centred at ``(center_x, center_y, center_z)`` with
    half-extents ``size_x / 2`` etc.  ``required_duration_sec`` is
    the minimum contiguous time the agent must remain inside.
    """

    center_x: float
    center_y: float
    center_z: float
    size_x: float
    size_y: float
    size_z: float
    required_duration_sec: float = 10.0

    def contains(self, x: float, y: float, z: float) -> bool:
        """Return *True* if the point lies inside the box."""
        dx = abs(x - self.center_x)
        dy = abs(y - self.center_y)
        dz = abs(z - self.center_z)
        return (
            dx <= self.size_x / 2.0
            and dy <= self.size_y / 2.0
            and dz <= self.size_z / 2.0
        )

    def distance_to_center(self, x: float, y: float) -> float:
        """Horizontal distance from *(x, y)* to box centre."""
        return ((x - self.center_x) ** 2 + (y - self.center_y) ** 2) ** 0.5


class Mission(BaseModel):
    """Top-level mission specification.

    A mission describes the terrain reference, start / goal waypoints,
    an optional observation box, safe-hold points for emergency hover,
    and alternate landing zones for divert scenarios.
    """

    mission_id: str
    terrain_id: str
    max_episode_time_sec: float = 1800.0
    start: WaypointXYZ
    goal: WaypointXYZ
    observe_box: Optional[ObserveBoxMission] = None
    safe_hold_points: list[WaypointXYZ] = Field(default_factory=list)
    alternate_lz: list[WaypointXYZ] = Field(default_factory=list)

    def goal_distance(self, x: float, y: float) -> float:
        """Horizontal distance from *(x, y)* to the goal waypoint."""
        return ((x - self.goal.x) ** 2 + (y - self.goal.y) ** 2) ** 0.5

    def nearest_safe_hold(self, x: float, y: float) -> Optional[WaypointXYZ]:
        """Return the closest safe-hold point, or *None* if none defined."""
        if not self.safe_hold_points:
            return None
        best: Optional[WaypointXYZ] = None
        best_dist = float("inf")
        for pt in self.safe_hold_points:
            d = ((x - pt.x) ** 2 + (y - pt.y) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best = pt
        return best

    def nearest_alternate_lz(self, x: float, y: float) -> Optional[WaypointXYZ]:
        """Return the closest alternate landing zone, or *None*."""
        if not self.alternate_lz:
            return None
        best: Optional[WaypointXYZ] = None
        best_dist = float("inf")
        for pt in self.alternate_lz:
            d = ((x - pt.x) ** 2 + (y - pt.y) ** 2) ** 0.5
            if d < best_dist:
                best_dist = d
                best = pt
        return best


def load_mission(path: str) -> Mission:
    """Load a :class:`Mission` from a YAML file on disk.

    The YAML structure must map directly to the :class:`Mission` schema.
    Nested keys ``start``, ``goal``, ``observe_box``, etc. are parsed
    automatically by Pydantic.

    Parameters
    ----------
    path : str
        Filesystem path to the ``.yaml`` / ``.yml`` mission file.

    Returns
    -------
    Mission
        Validated mission instance.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    yaml.YAMLError
        If the file is not valid YAML.
    pydantic.ValidationError
        If the YAML content does not match the Mission schema.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Mission file not found: {path}")

    with open(file_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Expected a YAML mapping at the top level, got {type(raw).__name__}"
        )

    return Mission.model_validate(raw)
