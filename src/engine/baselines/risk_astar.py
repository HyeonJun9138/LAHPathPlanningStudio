"""Risk-aware A* planner baseline.

Uses A* search on a coarsened terrain grid where the cost of moving to
a cell is the Euclidean distance plus a weighted risk penalty.  The
resulting waypoint plan is then followed greedily at each environment
step by selecting the candidate waypoint closest to the next A*
waypoint.
"""

from __future__ import annotations

import heapq
import math
from typing import Any, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


class RiskAStarPlanner:
    """A* baseline with risk-penalised edge costs.

    Parameters
    ----------
    dem : NDArray
        2-D elevation array.
    risk_map : NDArray
        2-D risk array (values in [0, 1]), same shape as *dem*.
    transform
        Rasterio affine transform mapping pixel (col, row) to
        map coordinates (x, y).
    resolution : float
        Grid cell size in metres (used for coarsening and distance).
    goal_xy : tuple[float, float]
        Goal position in map coordinates ``(x, y)``.
    risk_weight : float
        Multiplier on the risk cost per cell.  Higher values make the
        planner more risk-averse.
    coarsen_factor : int
        Factor by which to down-sample the grid before running A*.
        ``1`` means native resolution.
    """

    def __init__(
        self,
        dem: NDArray[np.floating],
        risk_map: NDArray[np.floating],
        transform: Any,
        resolution: float,
        goal_xy: tuple[float, float],
        risk_weight: float = 50.0,
        coarsen_factor: int = 4,
    ) -> None:
        self.dem = np.asarray(dem, dtype=np.float64)
        self.risk_map = np.asarray(risk_map, dtype=np.float64)
        self.transform = transform
        self.resolution = float(resolution)
        self.goal_xy = (float(goal_xy[0]), float(goal_xy[1]))
        self.risk_weight = float(risk_weight)
        self.coarsen_factor = max(1, int(coarsen_factor))

        # Coarsen the risk map for faster search
        self._coarse_risk = self._coarsen(self.risk_map, self.coarsen_factor)
        self._coarse_rows, self._coarse_cols = self._coarse_risk.shape
        self._cell_size = self.resolution * self.coarsen_factor

        # Pre-compute the goal cell
        self._goal_cell = self._world_to_cell(*self.goal_xy)

        # Cache for the planned waypoint sequence
        self._waypoints: list[tuple[float, float]] = []
        self._current_wp_index: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def plan(self, start_xy: tuple[float, float]) -> list[tuple[float, float]]:
        """Run A* from *start_xy* to the goal and return waypoints.

        Parameters
        ----------
        start_xy : tuple[float, float]
            Start position in map coordinates ``(x, y)``.

        Returns
        -------
        list[tuple[float, float]]
            Ordered waypoints ``(x, y)`` from start to goal.  The list
            is empty if no path is found.
        """
        start_cell = self._world_to_cell(*start_xy)
        goal_cell = self._goal_cell

        path_cells = self._astar(start_cell, goal_cell)
        if not path_cells:
            return []

        # Convert grid cells back to world coordinates
        waypoints = [self._cell_to_world(r, c) for r, c in path_cells]

        self._waypoints = waypoints
        self._current_wp_index = 0

        return waypoints

    def predict(
        self,
        obs: Any,
        deterministic: bool = True,
    ) -> Tuple[int, None]:
        """Select the candidate action closest to the next A* waypoint.

        Parameters
        ----------
        obs
            Observation dict from the environment.  Expected keys:

            - ``"x"``, ``"y"`` -- current agent position.
            - ``"candidates"`` -- array of shape ``(K, ...)`` where each
              row's first two elements are ``(x, y)`` of the candidate.
            - ``"action_mask"`` -- boolean mask of valid actions.

        deterministic : bool
            Ignored (the planner is always deterministic).

        Returns
        -------
        (action, None)
        """
        # Extract current position
        if isinstance(obs, dict):
            cur_x = float(obs.get("x", 0.0))
            cur_y = float(obs.get("y", 0.0))
        else:
            cur_x, cur_y = 0.0, 0.0

        # Lazily compute a plan if we don't have one
        if not self._waypoints:
            self.plan((cur_x, cur_y))

        # Advance waypoint index if we are close to the current target
        target = self._get_next_target(cur_x, cur_y)

        # Extract candidates and mask
        candidates, mask = self._extract_candidates_and_mask(obs)

        if candidates is None or len(candidates) == 0:
            return 0, None

        # Find candidate closest to the target waypoint
        best_action = self._closest_candidate(candidates, mask, target)
        return best_action, None

    # ------------------------------------------------------------------
    # A* implementation
    # ------------------------------------------------------------------

    def _astar(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> list[tuple[int, int]]:
        """A* on the coarsened grid.  Returns list of (row, col) cells."""
        sr, sc = start
        gr, gc = goal

        # Clamp to valid range
        sr = max(0, min(sr, self._coarse_rows - 1))
        sc = max(0, min(sc, self._coarse_cols - 1))
        gr = max(0, min(gr, self._coarse_rows - 1))
        gc = max(0, min(gc, self._coarse_cols - 1))

        # Priority queue: (f_cost, g_cost, row, col)
        open_set: list[tuple[float, float, int, int]] = []
        heapq.heappush(open_set, (0.0, 0.0, sr, sc))
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {(sr, sc): None}
        g_score: dict[tuple[int, int], float] = {(sr, sc): 0.0}

        # 8-connected neighbours
        neighbours = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
        ]

        max_iterations = self._coarse_rows * self._coarse_cols * 2
        iteration = 0

        while open_set and iteration < max_iterations:
            iteration += 1
            f, g, cr, cc = heapq.heappop(open_set)

            if (cr, cc) == (gr, gc):
                return self._reconstruct_path(came_from, (gr, gc))

            for dr, dc in neighbours:
                nr, nc = cr + dr, cc + dc
                if nr < 0 or nr >= self._coarse_rows or nc < 0 or nc >= self._coarse_cols:
                    continue

                # Movement cost: Euclidean + risk penalty
                step_dist = self._cell_size * (1.414 if (dr != 0 and dc != 0) else 1.0)
                cell_risk = float(self._coarse_risk[nr, nc])
                move_cost = step_dist + self.risk_weight * cell_risk * self._cell_size

                tentative_g = g + move_cost

                if tentative_g < g_score.get((nr, nc), float("inf")):
                    g_score[(nr, nc)] = tentative_g
                    h = self._heuristic(nr, nc, gr, gc)
                    f_new = tentative_g + h
                    came_from[(nr, nc)] = (cr, cc)
                    heapq.heappush(open_set, (f_new, tentative_g, nr, nc))

        # No path found -- return empty
        return []

    def _heuristic(self, r1: int, c1: int, r2: int, c2: int) -> float:
        """Euclidean distance heuristic in world units."""
        dr = (r1 - r2) * self._cell_size
        dc = (c1 - c2) * self._cell_size
        return math.sqrt(dr * dr + dc * dc)

    @staticmethod
    def _reconstruct_path(
        came_from: dict[tuple[int, int], tuple[int, int] | None],
        current: tuple[int, int],
    ) -> list[tuple[int, int]]:
        """Trace back from goal to start and reverse."""
        path = [current]
        while came_from.get(current) is not None:
            current = came_from[current]  # type: ignore[assignment]
            path.append(current)
        path.reverse()
        return path

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        """Convert map coordinates to coarsened grid (row, col)."""
        inv = ~self.transform
        col_f, row_f = inv * (x, y)
        row = int(round(row_f / self.coarsen_factor))
        col = int(round(col_f / self.coarsen_factor))
        row = max(0, min(row, self._coarse_rows - 1))
        col = max(0, min(col, self._coarse_cols - 1))
        return row, col

    def _cell_to_world(self, row: int, col: int) -> tuple[float, float]:
        """Convert coarsened grid cell back to map coordinates."""
        pixel_col = col * self.coarsen_factor + self.coarsen_factor / 2.0
        pixel_row = row * self.coarsen_factor + self.coarsen_factor / 2.0
        x, y = self.transform * (pixel_col, pixel_row)
        return (float(x), float(y))

    @staticmethod
    def _coarsen(arr: NDArray, factor: int) -> NDArray:
        """Down-sample a 2-D array by block-averaging."""
        if factor <= 1:
            return arr.copy()
        rows, cols = arr.shape
        # Trim to be evenly divisible
        trim_r = (rows // factor) * factor
        trim_c = (cols // factor) * factor
        trimmed = arr[:trim_r, :trim_c]
        # Reshape and mean over blocks
        coarsened = trimmed.reshape(
            trim_r // factor, factor,
            trim_c // factor, factor,
        ).mean(axis=(1, 3))
        return coarsened

    # ------------------------------------------------------------------
    # Waypoint tracking
    # ------------------------------------------------------------------

    def _get_next_target(self, x: float, y: float) -> tuple[float, float]:
        """Return the next waypoint to steer toward, advancing the index
        when the agent is close to the current one."""
        if not self._waypoints:
            return self.goal_xy

        arrival_threshold = self._cell_size * 1.5

        # Advance past waypoints the agent has already reached
        while self._current_wp_index < len(self._waypoints) - 1:
            wp = self._waypoints[self._current_wp_index]
            dist = math.sqrt((x - wp[0]) ** 2 + (y - wp[1]) ** 2)
            if dist < arrival_threshold:
                self._current_wp_index += 1
            else:
                break

        return self._waypoints[self._current_wp_index]

    # ------------------------------------------------------------------
    # Candidate selection
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_candidates_and_mask(
        obs: Any,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Pull candidate positions and action mask from the observation."""
        candidates = None
        mask = None

        if isinstance(obs, dict):
            raw_cands = obs.get("candidates")
            if raw_cands is not None:
                candidates = np.asarray(raw_cands, dtype=np.float64)
            raw_mask = obs.get("action_mask")
            if raw_mask is not None:
                mask = np.asarray(raw_mask, dtype=bool)

        return candidates, mask

    @staticmethod
    def _closest_candidate(
        candidates: np.ndarray,
        mask: Optional[np.ndarray],
        target: tuple[float, float],
    ) -> int:
        """Return the index of the valid candidate nearest to *target*."""
        tx, ty = target

        # Candidate xy -- assume first two columns are (x, y)
        if candidates.ndim == 1:
            # Single candidate or flat vector -- return 0
            return 0

        cand_x = candidates[:, 0].astype(np.float64)
        cand_y = candidates[:, 1].astype(np.float64)

        dist = np.sqrt((cand_x - tx) ** 2 + (cand_y - ty) ** 2)

        if mask is not None:
            # Set invalid candidates to infinite distance
            dist = np.where(mask, dist, np.inf)

        best = int(np.argmin(dist))
        # If all were masked (inf), pick the first valid
        if np.isinf(dist[best]) and mask is not None:
            valid = np.flatnonzero(mask)
            if valid.size > 0:
                best = int(valid[0])
            else:
                best = 0

        return best
