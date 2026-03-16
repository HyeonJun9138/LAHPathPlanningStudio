"""Unit tests for the Gymnasium environment."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestTerrainEnv:
    """Test the Gymnasium terrain path planning environment."""

    def _make_env(self):
        from src.engine.env.terrain_env import TerrainPathEnv
        env = TerrainPathEnv()
        return env

    def test_observation_space(self):
        env = self._make_env()
        obs_space = env.observation_space
        assert "self_state" in obs_space.spaces
        assert "candidate_table" in obs_space.spaces
        assert "action_mask" in obs_space.spaces
        env.close()

    def test_action_space(self):
        env = self._make_env()
        assert env.action_space.n == 32
        env.close()

    def test_reset(self):
        env = self._make_env()
        obs, info = env.reset(seed=42)
        assert isinstance(obs, dict)
        assert "self_state" in obs
        assert obs["self_state"].shape == env.observation_space["self_state"].shape
        assert obs["action_mask"].shape == (32,)
        env.close()

    def test_step(self):
        env = self._make_env()
        obs, info = env.reset(seed=42)
        mask = obs["action_mask"]
        # Pick a valid action
        valid_actions = np.where(mask > 0)[0]
        assert len(valid_actions) > 0
        action = valid_actions[0]
        obs2, reward, terminated, truncated, info2 = env.step(action)
        assert isinstance(reward, (float, int, np.floating))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info2, dict)
        env.close()

    def test_action_mask_consistency(self):
        env = self._make_env()
        obs, _ = env.reset(seed=42)
        mask = obs["action_mask"]
        # At least one action should be valid
        assert np.sum(mask) > 0
        # Mask values should be 0 or 1
        assert set(np.unique(mask)).issubset({0.0, 1.0})
        env.close()

    def test_multiple_steps(self):
        env = self._make_env()
        obs, _ = env.reset(seed=42)
        for _ in range(10):
            mask = obs["action_mask"]
            valid = np.where(mask > 0)[0]
            if len(valid) == 0:
                break
            action = np.random.choice(valid)
            obs, reward, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                obs, _ = env.reset()
        env.close()


class TestRewardCalculator:
    """Test reward decomposition."""

    def test_reward_components(self):
        from src.engine.env.reward import RewardCalculator
        calc = RewardCalculator()
        components = calc.compute(
            progress=0.1,
            risk=0.3,
            visible_time=2.0,
            path_length=500.0,
            time_elapsed=30.0,
            altitude_violation=False,
            zone_violation=False,
            collision=False,
            mission_complete=False,
            observe_complete=False,
            invalid_action=False,
            mode_switch=False,
        )
        assert "total" in components
        assert "breakdown" in components
        assert isinstance(components["total"], float)


class TestCandidateGenerator:
    """Test candidate waypoint generation."""

    def test_candidate_count(self):
        from src.engine.mission.candidate_generator import CandidateGenerator
        gen = CandidateGenerator(max_candidates=32)
        state = {
            "x": 1000.0,
            "y": 1000.0,
            "agl": 30.0,
            "heading": 0.0,
            "mode": "TRANSIT",
        }
        candidates, mask = gen.generate(state)
        assert candidates.shape[0] == 32
        assert mask.shape == (32,)
        assert candidates.shape[1] > 0  # Should have features

    def test_mask_valid(self):
        from src.engine.mission.candidate_generator import CandidateGenerator
        gen = CandidateGenerator(max_candidates=32)
        state = {
            "x": 1000.0,
            "y": 1000.0,
            "agl": 30.0,
            "heading": 0.0,
            "mode": "TRANSIT",
        }
        _, mask = gen.generate(state)
        # At least some candidates should be valid
        assert np.sum(mask) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
