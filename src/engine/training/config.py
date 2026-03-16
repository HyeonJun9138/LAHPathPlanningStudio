"""Training configuration management."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import yaml
from pathlib import Path


@dataclass
class TrainingConfig:
    """Configuration for a training run."""
    algorithm: str = "MaskablePPO"
    device: str = "cpu"
    seed: int = 42
    total_timesteps: int = 100_000
    n_envs: int = 4
    n_steps: int = 1024
    batch_size: int = 256
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    checkpoint_interval: int = 50_000
    eval_interval: int = 25_000
    curriculum: str = "curriculum_a"
    project_id: str = "default"
    terrain_id: str = ""
    mission_preset: str = ""
    reward_preset: str = "reward_default"

    # Reward weights
    reward_weights: dict = field(default_factory=lambda: {
        "progress": 2.0,
        "mission_complete": 100.0,
        "observation_complete": 30.0,
        "integrated_risk": 2.5,
        "visible_time": 1.2,
        "path_length": 0.003,
        "time_cost": 0.01,
        "altitude_violation": 3.0,
        "zone_violation": 5.0,
        "excessive_climb": 0.5,
        "invalid_action": 10.0,
        "mode_switch": 0.2,
        "collision": 200.0,
        "fail_terminal": 150.0,
    })

    @classmethod
    def from_yaml(cls, path: str) -> "TrainingConfig":
        """Load config from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        training = data.get("training", data)
        return cls(**{k: v for k, v in training.items() if k in cls.__dataclass_fields__})

    def to_yaml(self, path: str) -> None:
        """Save config to YAML file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {"training": {k: v for k, v in self.__dict__.items()}}
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {k: v for k, v in self.__dict__.items()}
