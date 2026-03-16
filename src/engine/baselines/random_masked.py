"""Random masked baseline policy.

Samples uniformly at random from the set of valid (unmasked) actions.
Compatible with the SB3 ``predict(obs, deterministic)`` interface and
the action-masked Gymnasium environments used in this project.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

import numpy as np


class RandomMaskedPolicy:
    """Baseline that picks a random valid action each step.

    Parameters
    ----------
    seed : int | None
        Random seed for reproducibility.  When *None*, the default
        numpy RNG state is used.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)

    def predict(
        self,
        obs: Any,
        deterministic: bool = False,
    ) -> Tuple[int, None]:
        """Select a random action from the valid (masked) set.

        Parameters
        ----------
        obs
            Observation from the environment.  May be a dict containing
            an ``"action_mask"`` key (a boolean or 0/1 array indicating
            which actions are valid), or a flat array / other structure.
        deterministic : bool
            Ignored -- the random policy is always stochastic.  Accepted
            for API compatibility with SB3 models.

        Returns
        -------
        (action, None)
            An integer action uniformly sampled from the valid set, and
            ``None`` (no recurrent state).
        """
        mask = self._extract_mask(obs)

        if mask is not None:
            valid_indices = np.flatnonzero(mask)
            if valid_indices.size > 0:
                action = int(self._rng.choice(valid_indices))
                return action, None

        # Fallback: no mask found -- sample from [0, n_candidates)
        n_actions = self._infer_action_count(obs)
        action = int(self._rng.integers(0, n_actions))
        return action, None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_mask(obs: Any) -> Optional[np.ndarray]:
        """Try to pull an action mask from various observation formats."""
        if isinstance(obs, dict):
            raw = obs.get("action_mask")
            if raw is not None:
                return np.asarray(raw, dtype=bool)
        # Some wrappers store the mask as an attribute
        if hasattr(obs, "action_mask"):
            return np.asarray(obs.action_mask, dtype=bool)
        return None

    @staticmethod
    def _infer_action_count(obs: Any) -> int:
        """Heuristic to determine the number of candidate actions.

        Defaults to K=32 (the project's standard candidate count) when
        no mask is available.
        """
        if isinstance(obs, dict):
            # Try candidate_table first (standard key), then legacy fallback
            candidates = obs.get("candidate_table")
            if candidates is None:
                candidates = obs.get("candidates")
            if candidates is not None:
                arr = np.asarray(candidates)
                if arr.ndim >= 1:
                    return arr.shape[0]
        return 32  # project default K
