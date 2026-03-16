"""Playback data adapter for the Simulation Player UI.

Wraps raw episode data (as produced by :func:`run_rollout`) into a
convenient API that the front-end can query frame-by-frame for
top-down map rendering, altitude profiles, risk timelines, and event
markers.
"""

from __future__ import annotations

from typing import Any


class PlayerData:
    """Read-only view over a single episode for frame-based playback.

    Parameters
    ----------
    episode_data : dict
        An episode dict as returned by :func:`~engine.simulation.rollout.run_rollout`.
        Must contain a ``steps`` list.
    """

    def __init__(self, episode_data: dict) -> None:
        self._data = episode_data
        self._steps: list[dict] = episode_data.get("steps", [])

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_frames(self) -> int:
        """Number of decision steps (frames) in the episode."""
        return len(self._steps)

    @property
    def duration(self) -> float:
        """Total simulation time in seconds.

        Uses the ``sim_time`` key when available, else sums step ``dt``
        values, else falls back to frame count.
        """
        if "sim_time" in self._data:
            return float(self._data["sim_time"])
        if self._steps:
            last_time = self._steps[-1].get("time")
            if last_time is not None:
                return float(last_time)
        return float(self.total_frames)

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame(self, index: int) -> dict:
        """Return the full state dict at frame *index*.

        Parameters
        ----------
        index : int
            Zero-based frame index.  Negative indices are supported
            (Python-style).

        Returns
        -------
        dict
            Step record containing ``x``, ``y``, ``z``, ``heading``,
            ``action``, ``reward``, ``risk``, ``clearance``, ``mode``,
            ``primitive``, ``time``, and any extra keys from the
            original step data.

        Raises
        ------
        IndexError
            If *index* is out of range.
        """
        n = self.total_frames
        if n == 0:
            raise IndexError("Episode has no frames")

        # Support negative indexing
        if index < 0:
            index = n + index
        if index < 0 or index >= n:
            raise IndexError(
                f"Frame index {index} out of range [0, {n - 1}]"
            )

        step = self._steps[index]
        frame: dict[str, Any] = {
            "frame_index": index,
            "x": float(step.get("x", 0.0)),
            "y": float(step.get("y", 0.0)),
            "z": float(step.get("z", 0.0)),
            "heading": float(step.get("heading", 0.0)),
            "action": int(step.get("action", -1)),
            "reward": float(step.get("reward", 0.0)),
            "risk": float(step.get("risk", 0.0)),
            "clearance": float(step.get("clearance", 0.0)),
            "mode": str(step.get("mode", "UNKNOWN")),
            "primitive": str(step.get("primitive", "UNKNOWN")),
            "time": float(step.get("time", float(index))),
        }
        return frame

    # ------------------------------------------------------------------
    # Aggregated views
    # ------------------------------------------------------------------

    def get_path_polyline(self) -> list[tuple[float, float, float]]:
        """Extract the 3-D path as a list of ``(x, y, z)`` tuples.

        Used for rendering the flight path on the top-down map.
        """
        polyline: list[tuple[float, float, float]] = []
        for s in self._steps:
            polyline.append((
                float(s.get("x", 0.0)),
                float(s.get("y", 0.0)),
                float(s.get("z", 0.0)),
            ))
        return polyline

    def get_altitude_profile(self) -> list[tuple[float, float]]:
        """Return ``(time, altitude)`` pairs for the altitude chart.

        Altitude is taken from the ``z`` field of each step.  Time is
        either the ``time`` field or the frame index.
        """
        profile: list[tuple[float, float]] = []
        for i, s in enumerate(self._steps):
            t = float(s.get("time", float(i)))
            alt = float(s.get("z", 0.0))
            profile.append((t, alt))
        return profile

    def get_risk_timeline(self) -> list[tuple[float, float]]:
        """Return ``(time, risk)`` pairs for the risk chart."""
        timeline: list[tuple[float, float]] = []
        for i, s in enumerate(self._steps):
            t = float(s.get("time", float(i)))
            risk = float(s.get("risk", 0.0))
            timeline.append((t, risk))
        return timeline

    def get_event_markers(self) -> list[tuple[float, str, str]]:
        """Identify notable events and return ``(time, type, description)``.

        Events include mode transitions, collisions, diversions, and
        observation completions.
        """
        markers: list[tuple[float, str, str]] = []
        prev_mode: str | None = None

        for i, s in enumerate(self._steps):
            t = float(s.get("time", float(i)))
            mode = str(s.get("mode", "UNKNOWN"))

            # Mode transition
            if mode != prev_mode and prev_mode is not None:
                markers.append((
                    t,
                    "mode_change",
                    f"Mode: {prev_mode} -> {mode}",
                ))
            prev_mode = mode

        # Terminal events from the episode-level data
        ep_time = self.duration
        if self._data.get("success"):
            markers.append((ep_time, "success", "Goal reached"))
        if self._data.get("collision"):
            markers.append((ep_time, "collision", "Collision detected"))
        if self._data.get("diverted"):
            markers.append((ep_time, "divert", "Diverted to alternate LZ"))
        if self._data.get("observation_completed"):
            markers.append((ep_time, "observation", "Observation objective completed"))

        # Sort by time
        markers.sort(key=lambda m: m[0])
        return markers
