"""Rule-based finite state machine (FSM) baseline policy.

Implements a hand-crafted decision tree that mimics a conservative pilot:
choose the lowest-risk candidate that makes the best progress toward the
goal, switch to observation setup when near the observe box, execute the
popup / drop-down sequence, then egress home.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple

import numpy as np


class RuleFSMPolicy:
    """Deterministic rule-based policy driven by mission phase.

    The policy inspects the observation dict for:

    - ``mode`` -- current mission phase string.
    - ``candidates`` -- array of shape ``(K, D)`` with per-candidate
      features.  The column layout is assumed to be::

          [x, y, z, heading, risk, goal_distance, ...]

    - ``action_mask`` -- boolean array of valid actions.
    - ``goal_distance`` -- scalar distance to the goal.
    - ``observe_box_distance`` -- distance to the observation box centre.
    - ``observation_completed`` -- whether the observe objective is done.

    Missing keys are handled gracefully with sensible defaults so the
    policy can work with partial observations.
    """

    # Column indices into the candidates array
    _COL_X = 0
    _COL_Y = 1
    _COL_Z = 2
    _COL_HEADING = 3
    _COL_RISK = 4
    _COL_GOAL_DIST = 5

    # Proximity threshold for switching to observe setup (metres)
    OBSERVE_PROXIMITY_M = 500.0

    def __init__(self) -> None:
        """Initialise the FSM policy (stateless -- no learnable params)."""

    def predict(
        self,
        obs: Any,
        deterministic: bool = True,
    ) -> Tuple[int, None]:
        """Select an action using hard-coded rules.

        Parameters
        ----------
        obs
            Observation dict from the environment.
        deterministic : bool
            Ignored (always deterministic).

        Returns
        -------
        (action, None)
        """
        if not isinstance(obs, dict):
            return 0, None

        mode = str(obs.get("mode", "TRANSIT"))
        candidates, mask = self._extract(obs)

        if candidates is None or candidates.size == 0:
            return 0, None

        n_candidates = candidates.shape[0] if candidates.ndim > 1 else 1
        if candidates.ndim == 1:
            return 0, None

        observe_box_dist = float(obs.get("observe_box_distance", float("inf")))
        observation_done = bool(obs.get("observation_completed", False))

        # ----- TRANSIT mode -----
        if mode == "TRANSIT":
            if (
                observe_box_dist < self.OBSERVE_PROXIMITY_M
                and not observation_done
            ):
                # Near the observe box -- pick the observe-setup candidate
                action = self._pick_observe_setup_candidate(candidates, mask)
            else:
                # Normal transit: lowest risk + best goal progress
                action = self._pick_transit_candidate(candidates, mask)

        # ----- OBSERVE_SETUP mode -----
        elif mode == "OBSERVE_SETUP":
            # Pick the popup-observe candidate (usually the one that
            # ascends to observation altitude)
            action = self._pick_popup_candidate(candidates, mask)

        # ----- POPUP_OBSERVE mode -----
        elif mode == "POPUP_OBSERVE":
            # After observing, drop down / descend
            action = self._pick_dropdown_candidate(candidates, mask)

        # ----- EGRESS / RETURN HOME -----
        elif mode in ("EGRESS", "RETURN_HOME"):
            action = self._pick_transit_candidate(candidates, mask)

        # ----- Observation done, default egress -----
        elif observation_done:
            action = self._pick_egress_candidate(candidates, mask)

        # ----- Fallback: lowest risk -----
        else:
            action = self._pick_lowest_risk(candidates, mask)

        return int(action), None

    # ------------------------------------------------------------------
    # Candidate selection strategies
    # ------------------------------------------------------------------

    def _pick_transit_candidate(
        self,
        candidates: np.ndarray,
        mask: Optional[np.ndarray],
    ) -> int:
        """Select the valid candidate with the best risk-adjusted
        goal progress.

        Score = -goal_distance - risk_weight * risk  (higher is better
        with the negative distance -- i.e., closer to goal is better).
        """
        n = candidates.shape[0]
        risk_weight = 200.0  # metres-equivalent penalty per unit risk

        scores = np.full(n, -np.inf)
        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            risk = self._get_col(candidates, i, self._COL_RISK, default=0.0)
            goal_dist = self._get_col(candidates, i, self._COL_GOAL_DIST, default=0.0)
            # Prefer shorter goal distance and lower risk
            scores[i] = -goal_dist - risk_weight * risk

        best = int(np.argmax(scores))
        if scores[best] == -np.inf:
            return self._first_valid(mask, n)
        return best

    def _pick_observe_setup_candidate(
        self,
        candidates: np.ndarray,
        mask: Optional[np.ndarray],
    ) -> int:
        """Pick the candidate that transitions into observe-setup mode.

        Heuristic: among valid candidates, prefer the one with the
        highest altitude (z) that has low risk -- this is typically the
        setup waypoint that positions the vehicle for a popup.
        """
        n = candidates.shape[0]
        scores = np.full(n, -np.inf)

        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            z = self._get_col(candidates, i, self._COL_Z, default=0.0)
            risk = self._get_col(candidates, i, self._COL_RISK, default=0.0)
            # Prefer moderate altitude with low risk
            scores[i] = z - 100.0 * risk

        best = int(np.argmax(scores))
        if scores[best] == -np.inf:
            return self._first_valid(mask, n)
        return best

    def _pick_popup_candidate(
        self,
        candidates: np.ndarray,
        mask: Optional[np.ndarray],
    ) -> int:
        """Pick the popup-observe candidate (ascend to observe altitude).

        Heuristic: the valid candidate with the highest ``z`` value.
        """
        n = candidates.shape[0]
        best_z = -np.inf
        best_idx = self._first_valid(mask, n)

        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            z = self._get_col(candidates, i, self._COL_Z, default=0.0)
            if z > best_z:
                best_z = z
                best_idx = i

        return best_idx

    def _pick_dropdown_candidate(
        self,
        candidates: np.ndarray,
        mask: Optional[np.ndarray],
    ) -> int:
        """After popup observe, pick the candidate that descends lowest
        (safest drop-down) while still being valid."""
        n = candidates.shape[0]
        best_z = np.inf
        best_idx = self._first_valid(mask, n)

        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            z = self._get_col(candidates, i, self._COL_Z, default=float("inf"))
            risk = self._get_col(candidates, i, self._COL_RISK, default=1.0)
            # Prefer low altitude and low risk
            combined = z + 100.0 * risk
            if combined < best_z:
                best_z = combined
                best_idx = i

        return best_idx

    def _pick_egress_candidate(
        self,
        candidates: np.ndarray,
        mask: Optional[np.ndarray],
    ) -> int:
        """Pick the candidate that is closest to the goal (return home)
        with low risk."""
        return self._pick_transit_candidate(candidates, mask)

    def _pick_lowest_risk(
        self,
        candidates: np.ndarray,
        mask: Optional[np.ndarray],
    ) -> int:
        """Fallback: pick the valid candidate with the lowest risk."""
        n = candidates.shape[0]
        best_risk = np.inf
        best_idx = self._first_valid(mask, n)

        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            risk = self._get_col(candidates, i, self._COL_RISK, default=1.0)
            if risk < best_risk:
                best_risk = risk
                best_idx = i

        return best_idx

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract(
        obs: dict,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Extract candidates and mask from the observation dict."""
        candidates = None
        mask = None
        raw_cands = obs.get("candidates")
        if raw_cands is not None:
            candidates = np.asarray(raw_cands, dtype=np.float64)
        raw_mask = obs.get("action_mask")
        if raw_mask is not None:
            mask = np.asarray(raw_mask, dtype=bool)
        return candidates, mask

    @staticmethod
    def _get_col(
        candidates: np.ndarray,
        row: int,
        col: int,
        default: float = 0.0,
    ) -> float:
        """Safely read a column from the candidates array."""
        if candidates.ndim < 2 or col >= candidates.shape[1]:
            return default
        return float(candidates[row, col])

    @staticmethod
    def _first_valid(mask: Optional[np.ndarray], n: int) -> int:
        """Return the index of the first valid action, or 0."""
        if mask is not None:
            valid = np.flatnonzero(mask)
            if valid.size > 0:
                return int(valid[0])
        return 0
