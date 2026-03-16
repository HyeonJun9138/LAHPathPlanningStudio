"""Gymnasium wrappers for the terrain path-planning environment.

Provides standard environment wrappers that modify the behaviour of
:class:`~engine.env.terrain_env.TerrainPathEnv` for training,
evaluation, or logging.
"""

from __future__ import annotations

from typing import Any, Optional

import gymnasium as gym
import numpy as np


class ActionMaskWrapper(gym.Wrapper):
    """Expose the action mask through the ``action_masks()`` method.

    SB3's MaskablePPO calls ``env.action_masks()`` at each step.  This
    wrapper delegates to the underlying environment's :meth:`action_masks`
    method and caches the mask from the ``info`` dict for convenience.
    """

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        self._last_mask: Optional[np.ndarray] = None

    def reset(self, **kwargs: Any) -> tuple[Any, dict]:
        obs, info = self.env.reset(**kwargs)
        self._last_mask = info.get("action_mask")
        return obs, info

    def step(self, action: int) -> tuple[Any, float, bool, bool, dict]:
        obs, reward, done, truncated, info = self.env.step(action)
        self._last_mask = info.get("action_mask")
        return obs, reward, done, truncated, info

    def action_masks(self) -> np.ndarray:
        if self._last_mask is not None:
            return self._last_mask
        if hasattr(self.env, "action_masks"):
            return self.env.action_masks()
        # Fallback: all actions valid
        return np.ones(self.env.action_space.n, dtype=bool)


class RewardScalingWrapper(gym.Wrapper):
    """Scale the reward by a constant factor.

    Useful for tuning the magnitude of rewards relative to the value
    function's output range without editing reward weights.

    Parameters
    ----------
    env : gym.Env
        Wrapped environment.
    scale : float
        Multiplicative factor applied to every reward.
    """

    def __init__(self, env: gym.Env, scale: float = 1.0) -> None:
        super().__init__(env)
        self.scale = float(scale)

    def step(self, action: int) -> tuple[Any, float, bool, bool, dict]:
        obs, reward, done, truncated, info = self.env.step(action)
        return obs, reward * self.scale, done, truncated, info


class EpisodeStatsWrapper(gym.Wrapper):
    """Track per-episode statistics and add them to the ``info`` dict.

    On episode termination (``done or truncated``), the info dict is
    augmented with:

    - ``episode_return`` — cumulative reward.
    - ``episode_length`` — number of steps.
    - ``episode_success`` — whether the episode was successful.
    """

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        self._ep_return: float = 0.0
        self._ep_length: int = 0

    def reset(self, **kwargs: Any) -> tuple[Any, dict]:
        self._ep_return = 0.0
        self._ep_length = 0
        return self.env.reset(**kwargs)

    def step(self, action: int) -> tuple[Any, float, bool, bool, dict]:
        obs, reward, done, truncated, info = self.env.step(action)
        self._ep_return += reward
        self._ep_length += 1

        if done or truncated:
            info["episode_return"] = self._ep_return
            info["episode_length"] = self._ep_length
            info["episode_success"] = info.get("success", False)

        return obs, reward, done, truncated, info
