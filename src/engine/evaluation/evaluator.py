"""Episode-level evaluator for RL models and baseline policies.

Runs a configurable number of evaluation episodes, collects per-step and
per-episode data, and returns aggregated performance metrics.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np


class Evaluator:
    """Run evaluation episodes and aggregate metrics.

    Parameters
    ----------
    env
        A Gymnasium-compatible environment with ``reset()`` and ``step()``.
        The observation returned by the environment may include an
        ``action_mask`` key used by masked policies.
    model
        An RL model (e.g. from Stable-Baselines3) with a ``predict(obs,
        deterministic)`` method.  When *None*, a random (uniform over valid
        actions) policy is used as the fallback.
    num_episodes : int
        Number of rollout episodes.
    deterministic : bool
        Whether to use the deterministic prediction mode.
    """

    def __init__(
        self,
        env,
        model=None,
        num_episodes: int = 10,
        deterministic: bool = True,
    ) -> None:
        self.env = env
        self.model = model
        self.num_episodes = num_episodes
        self.deterministic = deterministic

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _predict_action(self, obs: Any) -> int:
        """Choose an action using the model or a random masked fallback."""
        if self.model is not None:
            action, _ = self.model.predict(obs, deterministic=self.deterministic)
            return int(action)

        # Fallback: uniform random over valid actions (action-mask aware)
        if isinstance(obs, dict) and "action_mask" in obs:
            mask = np.asarray(obs["action_mask"], dtype=bool)
            valid_indices = np.flatnonzero(mask)
            if valid_indices.size > 0:
                return int(np.random.choice(valid_indices))
        # No mask information -- sample uniformly over the full space
        return int(self.env.action_space.sample())

    def _run_single_episode(self) -> dict:
        """Execute one episode and return collected data."""
        obs, info = self.env.reset()

        steps: list[dict] = []
        total_reward = 0.0
        done = False
        truncated = False
        t_start = time.perf_counter()

        while not done and not truncated:
            action = self._predict_action(obs)
            next_obs, reward, done, truncated, step_info = self.env.step(action)

            step_record: dict[str, Any] = {
                "action": int(action),
                "reward": float(reward),
                "done": bool(done),
                "truncated": bool(truncated),
            }

            # Harvest optional fields from info / obs
            for key in (
                "x", "y", "z", "heading", "risk", "clearance",
                "mode", "primitive", "time",
            ):
                if key in step_info:
                    step_record[key] = step_info[key]
                elif isinstance(next_obs, dict) and key in next_obs:
                    step_record[key] = next_obs[key]

            steps.append(step_record)
            total_reward += float(reward)
            obs = next_obs

        t_end = time.perf_counter()

        # Derive path length from (x, y, z) if available
        path_length = self._compute_path_length(steps)

        # Determine success, collision, divert from terminal info
        success = bool(step_info.get("success", step_info.get("is_success", False))) if steps else False
        collision = bool(step_info.get("collision", False)) if steps else False
        diverted = bool(step_info.get("diverted", False)) if steps else False
        observation_completed = bool(step_info.get("observation_completed", False)) if steps else False

        # Collect risk values across the episode
        risk_values = [s["risk"] for s in steps if "risk" in s]
        mean_risk = float(np.mean(risk_values)) if risk_values else 0.0

        # Visible time: steps where the agent was in a visible/exposed state
        visible_steps = [s for s in steps if s.get("mode") == "POPUP_OBSERVE"]
        visible_time = len(visible_steps) * (step_info.get("dt", 1.0) if steps else 1.0)

        return {
            "steps": steps,
            "total_reward": total_reward,
            "success": success,
            "collision": collision,
            "diverted": diverted,
            "observation_completed": observation_completed,
            "path_length": path_length,
            "episode_time": t_end - t_start,
            "mean_risk": mean_risk,
            "visible_time": visible_time,
            "num_steps": len(steps),
        }

    @staticmethod
    def _compute_path_length(steps: list[dict]) -> float:
        """Sum of Euclidean segment lengths from step positions."""
        total = 0.0
        prev: Optional[tuple[float, float, float]] = None
        for s in steps:
            if "x" in s and "y" in s:
                z = s.get("z", 0.0)
                cur = (float(s["x"]), float(s["y"]), float(z))
                if prev is not None:
                    dx = cur[0] - prev[0]
                    dy = cur[1] - prev[1]
                    dz = cur[2] - prev[2]
                    total += (dx * dx + dy * dy + dz * dz) ** 0.5
                prev = cur
        return total

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self) -> dict:
        """Run all evaluation episodes and return aggregated metrics.

        Returns
        -------
        dict
            Aggregated metrics across all episodes:

            - ``success_rate`` -- fraction of episodes that reached the goal.
            - ``mean_return`` -- average cumulative reward.
            - ``mean_path_length`` -- average 3-D path length (metres).
            - ``mean_episode_time`` -- average wall-clock time (seconds).
            - ``mean_risk`` -- average per-step risk across episodes.
            - ``mean_visible_time`` -- average time exposed in observe mode.
            - ``divert_rate`` -- fraction of episodes that diverted.
            - ``collision_rate`` -- fraction that ended in collision.
            - ``observation_completion_rate`` -- fraction that finished observation.
            - ``episodes`` -- raw per-episode data list.
        """
        episodes: list[dict] = []
        for _ in range(self.num_episodes):
            ep = self._run_single_episode()
            episodes.append(ep)

        successes = [e["success"] for e in episodes]
        returns = [e["total_reward"] for e in episodes]
        path_lengths = [e["path_length"] for e in episodes]
        times = [e["episode_time"] for e in episodes]
        risks = [e["mean_risk"] for e in episodes]
        visible_times = [e["visible_time"] for e in episodes]
        diverts = [e["diverted"] for e in episodes]
        collisions = [e["collision"] for e in episodes]
        obs_completions = [e["observation_completed"] for e in episodes]

        n = max(len(episodes), 1)
        return {
            "success_rate": float(np.mean(successes)),
            "mean_return": float(np.mean(returns)),
            "mean_path_length": float(np.mean(path_lengths)),
            "mean_episode_time": float(np.mean(times)),
            "mean_risk": float(np.mean(risks)),
            "mean_visible_time": float(np.mean(visible_times)),
            "divert_rate": float(np.sum(diverts)) / n,
            "collision_rate": float(np.sum(collisions)) / n,
            "observation_completion_rate": float(np.sum(obs_completions)) / n,
            "num_episodes": len(episodes),
            "episodes": episodes,
        }
