"""Mission validation utilities."""
from __future__ import annotations

from typing import List, Tuple
from .schema import MissionConfig


def validate_mission(mission: MissionConfig) -> Tuple[bool, List[str]]:
    """Validate a mission configuration.
    
    Returns (is_valid, list_of_issues).
    """
    issues: List[str] = []

    # Check start != goal
    if (mission.start.x == mission.goal.x and
            mission.start.y == mission.goal.y):
        issues.append("Start and goal positions are identical.")

    # Check time limit
    if mission.max_episode_time_sec <= 0:
        issues.append("max_episode_time_sec must be positive.")

    # Check altitude values
    if mission.start.agl_m < 0:
        issues.append("Start AGL must be >= 0.")
    if mission.goal.agl_m < 0:
        issues.append("Goal AGL must be >= 0.")

    # Check observe box if present
    if mission.observe_box is not None:
        ob = mission.observe_box
        if ob.size_x <= 0 or ob.size_y <= 0 or ob.size_z <= 0:
            issues.append("Observe box dimensions must be positive.")
        if ob.required_duration_sec <= 0:
            issues.append("Observe box required_duration_sec must be positive.")

    # Check safe hold points
    for i, pt in enumerate(mission.safe_hold_points):
        if pt.agl_m < 0:
            issues.append(f"Safe hold point {i} AGL must be >= 0.")

    # Check alternate LZ
    for i, lz in enumerate(mission.alternate_lz):
        if lz.agl_m < 0:
            issues.append(f"Alternate LZ {i} AGL must be >= 0.")

    return (len(issues) == 0, issues)
