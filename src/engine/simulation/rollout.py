"""Episode rollout execution for simulation and replay.

Runs one or more episodes through a Gymnasium environment using the
provided policy object, and collects detailed per-step telemetry for
downstream visualisation, export, and metric computation.
"""

from __future__ import annotations

import math
import time
from typing import Any


def run_rollout(
    env,
    policy,
    num_episodes: int = 1,
    deterministic: bool = True,
) -> list[dict]:
    """Execute *num_episodes* rollouts and return detailed episode data.

    Parameters
    ----------
    env
        A Gymnasium-compatible environment.  ``reset()`` must return
        ``(obs, info)`` and ``step(action)`` must return
        ``(obs, reward, terminated, truncated, info)``.
    policy
        An object with a ``predict(obs, deterministic=...)`` method that
        returns ``(action, state)``.  Compatible with SB3 models and the
        baseline policies defined in this project.
    num_episodes : int
        How many episodes to run.
    deterministic : bool
        Forwarded to ``policy.predict``.

    Returns
    -------
    list[dict]
        One dict per episode with keys:

        ``steps`` -- list of per-step dicts (see below).
        ``total_reward`` -- cumulative reward for the episode.
        ``success`` -- whether the agent reached the goal.
        ``collision`` -- whether the agent collided.
        ``diverted`` -- whether the agent diverted to alternate LZ.
        ``observation_completed`` -- whether observation objective was met.
        ``path_length`` -- 3-D path length in metres.
        ``episode_time`` -- wall-clock duration in seconds.
        ``num_steps`` -- number of decision steps.

    Each step dict contains:
        ``x``, ``y``, ``z`` -- position (metres).
        ``heading`` -- heading in degrees.
        ``action`` -- integer action selected by the policy.
        ``reward`` -- immediate scalar reward.
        ``risk`` -- local risk value.
        ``clearance`` -- terrain clearance (metres AGL).
        ``mode`` -- mission-phase string (e.g. TRANSIT, OBSERVE_SETUP).
        ``primitive`` -- motion-primitive name.
        ``time`` -- simulation time (seconds).
    """
    all_episodes: list[dict] = []

    for ep_idx in range(num_episodes):
        obs, reset_info = env.reset()
        episode_steps: list[dict] = []
        total_reward = 0.0
        done = False
        truncated = False
        wall_start = time.perf_counter()
        sim_time = 0.0

        while not done and not truncated:
            action, _state = policy.predict(obs, deterministic=deterministic)
            action_int = int(action)

            next_obs, reward, done, truncated, step_info = env.step(action_int)
            total_reward += float(reward)

            # Build the step record from step_info and obs
            step_record = _build_step_record(
                action=action_int,
                reward=float(reward),
                step_info=step_info,
                obs=next_obs,
                sim_time=sim_time,
            )
            episode_steps.append(step_record)

            # Advance simulation clock
            dt = step_info.get("dt", 1.0)
            sim_time += float(dt)
            obs = next_obs

        wall_end = time.perf_counter()

        # Terminal flags
        last_info = step_info if episode_steps else {}
        success = bool(last_info.get("success", last_info.get("is_success", False)))
        collision = bool(last_info.get("collision", False))
        diverted = bool(last_info.get("diverted", False))
        observation_completed = bool(last_info.get("observation_completed", False))

        path_length = _compute_path_length(episode_steps)

        all_episodes.append({
            "episode_index": ep_idx,
            "steps": episode_steps,
            "total_reward": total_reward,
            "success": success,
            "collision": collision,
            "diverted": diverted,
            "observation_completed": observation_completed,
            "path_length": path_length,
            "episode_time": wall_end - wall_start,
            "sim_time": sim_time,
            "num_steps": len(episode_steps),
        })

    return all_episodes


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_step_record(
    action: int,
    reward: float,
    step_info: dict,
    obs: Any,
    sim_time: float,
) -> dict:
    """Assemble a per-step telemetry dict from available sources."""
    record: dict[str, Any] = {
        "action": action,
        "reward": reward,
        "time": sim_time,
    }

    # Keys we want to capture from step_info or obs
    desired_keys = ("x", "y", "z", "heading", "risk", "clearance", "mode", "primitive")

    for key in desired_keys:
        if key in step_info:
            record[key] = step_info[key]
        elif isinstance(obs, dict) and key in obs:
            record[key] = obs[key]

    # Ensure numeric defaults for critical fields
    record.setdefault("x", 0.0)
    record.setdefault("y", 0.0)
    record.setdefault("z", 0.0)
    record.setdefault("heading", 0.0)
    record.setdefault("risk", 0.0)
    record.setdefault("clearance", 0.0)
    record.setdefault("mode", "UNKNOWN")
    record.setdefault("primitive", "UNKNOWN")

    return record


def _compute_path_length(steps: list[dict]) -> float:
    """Sum of 3-D segment lengths from consecutive step positions."""
    total = 0.0
    if len(steps) < 2:
        return total

    prev_x = float(steps[0].get("x", 0.0))
    prev_y = float(steps[0].get("y", 0.0))
    prev_z = float(steps[0].get("z", 0.0))

    for s in steps[1:]:
        cx = float(s.get("x", 0.0))
        cy = float(s.get("y", 0.0))
        cz = float(s.get("z", 0.0))
        dx = cx - prev_x
        dy = cy - prev_y
        dz = cz - prev_z
        total += math.sqrt(dx * dx + dy * dy + dz * dz)
        prev_x, prev_y, prev_z = cx, cy, cz

    return total
