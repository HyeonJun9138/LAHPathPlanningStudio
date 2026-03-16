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

from engine.mission.state_machine import MissionMode


class RuleFSMPolicy:
    """Deterministic rule-based policy driven by mission phase.

    The policy inspects the observation dict and extracts mission mode from
    the self_state one-hot encoding (indices 12..21), candidates from the
    ``candidate_table`` key, and the action mask.

    Candidate feature layout (24 columns)::

        [0..9]   one-hot primitive type
        [10]     rel_dx / 5000
        [11]     rel_dy / 5000
        [12]     target_agl / 200
        [13]     distance / 5000
        [14]     time_estimate / 300
        [15]     goal_progress
        [16]     risk / 100
        [17]     visibility
        [18]     clearance / 200
        [19]     turn_cost / pi
        [20]     observe_feasible
        [21]     hold_quality
        [22]     zone_penalty
        [23]     reserved (terrain slope)
    """

    # Correct column indices into the candidate feature vector
    _COL_REL_DX = 10
    _COL_REL_DY = 11
    _COL_TARGET_AGL = 12
    _COL_DISTANCE = 13
    _COL_TIME_EST = 14
    _COL_GOAL_PROGRESS = 15
    _COL_RISK = 16
    _COL_VISIBILITY = 17
    _COL_CLEARANCE = 18
    _COL_TURN_COST = 19
    _COL_OBSERVE_FEASIBLE = 20
    _COL_HOLD_QUALITY = 21
    _COL_ZONE_PENALTY = 22

    # Proximity threshold for switching to observe setup (metres)
    OBSERVE_PROXIMITY_M = 500.0

    # Mission mode ordering (must match MissionMode enum order)
    _MODE_LIST = list(MissionMode)

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

        mode = self._detect_mode(obs)
        candidates, mask = self._extract(obs)

        if candidates is None or candidates.size == 0:
            return 0, None

        if candidates.ndim == 1:
            return 0, None

        # Extract observe box distance and observation status from self_state
        self_state = obs.get("self_state")
        observe_box_dist = float("inf")
        observation_done = False
        if self_state is not None:
            ss = np.asarray(self_state, dtype=np.float64)
            if ss.shape[0] > 30:
                observe_box_dist = float(ss[30]) * 5000.0  # dist_observe_box
            if ss.shape[0] > 23:
                observation_done = float(ss[23]) > 0.5  # observe_done flag

        # ----- TRANSIT mode -----
        if mode == MissionMode.TRANSIT:
            if (
                observe_box_dist < self.OBSERVE_PROXIMITY_M
                and not observation_done
            ):
                action = self._pick_observe_setup_candidate(candidates, mask)
            else:
                action = self._pick_transit_candidate(candidates, mask)

        # ----- OBSERVE_SETUP mode -----
        elif mode == MissionMode.OBSERVE_SETUP:
            action = self._pick_popup_candidate(candidates, mask)

        # ----- POPUP_OBSERVE mode -----
        elif mode == MissionMode.POPUP_OBSERVE:
            action = self._pick_dropdown_candidate(candidates, mask)

        # ----- DROP_DOWN mode -----
        elif mode == MissionMode.DROP_DOWN:
            action = self._pick_dropdown_candidate(candidates, mask)

        # ----- EGRESS / RETURN HOME -----
        elif mode in (MissionMode.EGRESS, MissionMode.RETURN_HOME):
            action = self._pick_transit_candidate(candidates, mask)

        # ----- SAFE_HOLD -----
        elif mode == MissionMode.SAFE_HOLD:
            action = self._pick_lowest_risk(candidates, mask)

        # ----- DIVERT -----
        elif mode == MissionMode.DIVERT:
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

        Score = goal_progress - risk_weight * risk  (higher is better).
        """
        n = candidates.shape[0]
        risk_weight = 2.0

        scores = np.full(n, -np.inf)
        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            risk = self._get_col(candidates, i, self._COL_RISK, default=0.0)
            goal_progress = self._get_col(
                candidates, i, self._COL_GOAL_PROGRESS, default=0.0
            )
            clearance = self._get_col(
                candidates, i, self._COL_CLEARANCE, default=0.5
            )
            zone_pen = self._get_col(
                candidates, i, self._COL_ZONE_PENALTY, default=0.0
            )
            scores[i] = (
                goal_progress
                - risk_weight * risk
                + 0.5 * clearance
                - 3.0 * zone_pen
            )

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

        Prefers candidates with high target AGL and observe_feasible flag,
        low risk.
        """
        n = candidates.shape[0]
        scores = np.full(n, -np.inf)

        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            target_agl = self._get_col(
                candidates, i, self._COL_TARGET_AGL, default=0.0
            )
            risk = self._get_col(candidates, i, self._COL_RISK, default=0.0)
            obs_feasible = self._get_col(
                candidates, i, self._COL_OBSERVE_FEASIBLE, default=0.0
            )
            scores[i] = (
                2.0 * obs_feasible
                + target_agl
                - 1.0 * risk
            )

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

        Prefers candidates with highest target AGL and observe_feasible.
        """
        n = candidates.shape[0]
        best_score = -np.inf
        best_idx = self._first_valid(mask, n)

        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            target_agl = self._get_col(
                candidates, i, self._COL_TARGET_AGL, default=0.0
            )
            obs_feasible = self._get_col(
                candidates, i, self._COL_OBSERVE_FEASIBLE, default=0.0
            )
            score = target_agl + 5.0 * obs_feasible
            if score > best_score:
                best_score = score
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
        best_score = np.inf
        best_idx = self._first_valid(mask, n)

        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            target_agl = self._get_col(
                candidates, i, self._COL_TARGET_AGL, default=1.0
            )
            risk = self._get_col(candidates, i, self._COL_RISK, default=1.0)
            clearance = self._get_col(
                candidates, i, self._COL_CLEARANCE, default=0.5
            )
            # Prefer low altitude, low risk, reasonable clearance
            combined = target_agl + 2.0 * risk - 0.5 * clearance
            if combined < best_score:
                best_score = combined
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
    def _detect_mode(obs: dict) -> MissionMode:
        """Detect mission mode from self_state one-hot encoding.

        The self_state vector has a one-hot mode encoding at indices [12..21].
        """
        self_state = obs.get("self_state")
        if self_state is None:
            return MissionMode.TRANSIT

        ss = np.asarray(self_state, dtype=np.float64)
        if ss.shape[0] < 22:
            return MissionMode.TRANSIT

        mode_one_hot = ss[12:22]
        mode_idx = int(np.argmax(mode_one_hot))
        mode_list = list(MissionMode)
        if mode_idx < len(mode_list):
            return mode_list[mode_idx]
        return MissionMode.TRANSIT

    @staticmethod
    def _extract(
        obs: dict,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Extract candidates and mask from the observation dict."""
        candidates = None
        mask = None
        # Environment uses "candidate_table" as the observation key
        raw_cands = obs.get("candidate_table")
        if raw_cands is None:
            raw_cands = obs.get("candidates")  # legacy fallback
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
