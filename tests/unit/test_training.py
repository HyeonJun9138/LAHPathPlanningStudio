"""Unit tests for training engine modules."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestDeviceDetection:
    """Test CUDA/device detection."""

    def test_detect_returns_dict(self):
        from src.engine.training.device import detect_cuda
        info = detect_cuda()
        assert isinstance(info, dict)
        assert "available" in info
        assert "torch_version" in info

    def test_select_cpu(self):
        from src.engine.training.device import select_device
        import torch
        device = select_device("cpu")
        assert device == torch.device("cpu")


class TestTrainingConfig:
    """Test training configuration."""

    def test_default_config(self):
        from src.engine.training.config import TrainingConfig
        config = TrainingConfig()
        assert config.algorithm == "MaskablePPO"
        assert config.seed == 42
        assert config.total_timesteps == 100_000

    def test_yaml_roundtrip(self, tmp_path):
        from src.engine.training.config import TrainingConfig
        config = TrainingConfig(seed=123, total_timesteps=50_000)
        path = str(tmp_path / "test_config.yaml")
        config.to_yaml(path)
        loaded = TrainingConfig.from_yaml(path)
        assert loaded.seed == 123
        assert loaded.total_timesteps == 50_000


class TestFeatureExtractor:
    """Test custom feature extractor."""

    def test_forward_shape(self):
        import torch
        import gymnasium as gym
        import numpy as np
        from src.engine.training.feature_extractor import TerrainFeatureExtractor

        # Create a sample observation space matching the env
        obs_space = gym.spaces.Dict({
            "self_state": gym.spaces.Box(-np.inf, np.inf, (48,), np.float32),
            "local_hi_patch": gym.spaces.Box(0, 1, (4, 32, 32), np.float32),
            "local_mid_patch": gym.spaces.Box(0, 1, (4, 16, 16), np.float32),
            "global_context": gym.spaces.Box(-np.inf, np.inf, (16,), np.float32),
            "candidate_table": gym.spaces.Box(-np.inf, np.inf, (32, 24), np.float32),
            "action_mask": gym.spaces.Box(0, 1, (32,), np.float32),
        })

        extractor = TerrainFeatureExtractor(obs_space)

        # Create a batch of observations
        batch = {
            "self_state": torch.randn(2, 48),
            "local_hi_patch": torch.randn(2, 4, 32, 32),
            "local_mid_patch": torch.randn(2, 4, 16, 16),
            "global_context": torch.randn(2, 16),
            "candidate_table": torch.randn(2, 32, 24),
            "action_mask": torch.ones(2, 32),
        }

        features = extractor(batch)
        assert features.shape[0] == 2
        assert features.ndim == 2
        assert features.shape[1] == extractor.features_dim


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
