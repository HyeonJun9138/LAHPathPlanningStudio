"""Integration tests for the full pipeline."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestTerrainToEnvPipeline:
    """Test terrain preprocessing -> hazard -> env flow."""

    def test_derivatives_to_env(self):
        """Verify that terrain derivatives feed correctly into the env."""
        from src.engine.terrain.derivatives import (
            calc_slope, calc_roughness, calc_tpi
        )
        from src.engine.env.terrain_env import TerrainPathEnv

        # Create synthetic DEM
        dem = np.random.rand(200, 200).astype(np.float32) * 500 + 200
        res = 30.0

        # Compute derivatives
        slope = calc_slope(dem, res)
        roughness = calc_roughness(dem, window=5)
        tpi = calc_tpi(dem, window=11)

        assert slope.shape == dem.shape
        assert roughness.shape == dem.shape
        assert tpi.shape == dem.shape

        # Env should initialize and run
        env = TerrainPathEnv()
        obs, info = env.reset(seed=42)
        assert obs is not None
        env.close()

    def test_hazard_fusion_pipeline(self):
        """Test multiple risk sources fuse correctly."""
        from src.engine.hazard.fusion import fuse_risks

        r1 = np.random.rand(100, 100).astype(np.float32) * 0.5
        r2 = np.random.rand(100, 100).astype(np.float32) * 0.3
        r3 = np.random.rand(100, 100).astype(np.float32) * 0.2

        fused = fuse_risks([r1, r2, r3], mode="probabilistic_union")
        assert fused.shape == (100, 100)
        assert np.all(fused >= 0)
        assert np.all(fused <= 1)

    def test_env_episode_completion(self):
        """Run a full episode with random actions."""
        from src.engine.env.terrain_env import TerrainPathEnv

        env = TerrainPathEnv()
        obs, _ = env.reset(seed=42)

        total_reward = 0
        steps = 0
        max_steps = 200

        while steps < max_steps:
            mask = obs["action_mask"]
            valid = np.where(mask > 0)[0]
            if len(valid) == 0:
                break
            action = np.random.choice(valid)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            steps += 1
            if terminated or truncated:
                break

        assert steps > 0
        env.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
