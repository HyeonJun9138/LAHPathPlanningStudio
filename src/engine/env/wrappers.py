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
    - ``episode_min_reward`` — minimum single-step reward.
    - ``episode_max_reward`` — maximum single-step reward.
    """

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        self._ep_return: float = 0.0
        self._ep_length: int = 0
        self._ep_min_reward: float = float("inf")
        self._ep_max_reward: float = float("-inf")

    def reset(self, **kwargs: Any) -> tuple[Any, dict]:
        self._ep_return = 0.0
        self._ep_length = 0
        self._ep_min_reward = float("inf")
        self._ep_max_reward = float("-inf")
        return self.env.reset(**kwargs)

    def step(self, action: int) -> tuple[Any, float, bool, bool, dict]:
        obs, reward, done, truncated, info = self.env.step(action)
        self._ep_return += reward
        self._ep_length += 1
        self._ep_min_reward = min(self._ep_min_reward, reward)
        self._ep_max_reward = max(self._ep_max_reward, reward)

        if done or truncated:
            info["episode_return"] = self._ep_return
            info["episode_length"] = self._ep_length
            info["episode_success"] = info.get("success", False)
            info["episode_min_reward"] = self._ep_min_reward
            info["episode_max_reward"] = self._ep_max_reward

        return obs, reward, done, truncated, info


class ObservationClipWrapper(gym.ObservationWrapper):
    """Clip observation values to prevent NaN / Inf propagation.

    Replaces any NaN with 0.0 and clips all values to
    ``[-clip_value, clip_value]``.  Applied element-wise to every
    array in a Dict observation space.

    Parameters
    ----------
    env : gym.Env
        Wrapped environment.
    clip_value : float
        Symmetric clip bound (default 10.0).
    """

    def __init__(self, env: gym.Env, clip_value: float = 10.0) -> None:
        super().__init__(env)
        self.clip_value = float(clip_value)

    def observation(self, observation: Any) -> Any:
        if isinstance(observation, dict):
            return {
                k: self._clip_array(v) if isinstance(v, np.ndarray) else v
                for k, v in observation.items()
            }
        if isinstance(observation, np.ndarray):
            return self._clip_array(observation)
        return observation

    def _clip_array(self, arr: np.ndarray) -> np.ndarray:
        out = np.where(np.isfinite(arr), arr, 0.0)
        return np.clip(out, -self.clip_value, self.clip_value)
