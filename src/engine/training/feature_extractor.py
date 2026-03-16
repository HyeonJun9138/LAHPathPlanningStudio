"""Custom SB3 feature extractor for the terrain path-planning environment.

The :class:`TerrainFeatureExtractor` consumes the Dict observation space
produced by :mod:`src.engine.env.terrain_env` and fuses five modalities:

1. **local_hi_patch** -- high-resolution terrain patch (CNN).
2. **local_mid_patch** -- medium-resolution terrain patch (CNN).
3. **self_state** -- agent kinematic / mission state vector (MLP).
4. **global_context** -- global mission summary features (MLP).
5. **candidate_table** -- per-candidate waypoint feature rows (shared MLP
   + max-pool aggregation).

All branches are concatenated and projected to a fixed-width feature
vector consumed by the policy / value heads.
"""

from __future__ import annotations

import gymnasium as gym
import torch
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


def _init_weights(module: nn.Module) -> None:
    """Apply proper weight initialisation to Conv2d and Linear layers.

    Uses Kaiming (He) init for layers followed by ReLU, which is the
    standard choice for networks with ReLU activations.
    """
    if isinstance(module, (nn.Conv2d, nn.Linear)):
        nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
        if module.bias is not None:
            nn.init.zeros_(module.bias)


class TerrainFeatureExtractor(BaseFeaturesExtractor):
    """Multi-modal feature extractor for :class:`TerrainPathEnv`.

    Parameters
    ----------
    observation_space:
        A :class:`gym.spaces.Dict` with the five keys listed above.
    features_dim:
        Width of the output feature vector (default 256).
    dropout:
        Dropout probability applied after fusion and within MLP branches
        for regularisation.  Default 0.1.
    """

    def __init__(
        self,
        observation_space: gym.spaces.Dict,
        features_dim: int = 256,
        dropout: float = 0.1,
    ) -> None:
        # Call super with the *final* features_dim; we will recompute
        # _features_dim after building the sub-networks.
        super().__init__(observation_space, features_dim)

        # ------------------------------------------------------------------
        # 1. CNN for local_hi_patch  (C, 32, 32)
        # ------------------------------------------------------------------
        hi_shape = observation_space["local_hi_patch"].shape
        self.hi_cnn = nn.Sequential(
            nn.Conv2d(hi_shape[0], 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            hi_out_dim = self.hi_cnn(torch.zeros(1, *hi_shape)).shape[1]

        # ------------------------------------------------------------------
        # 2. CNN for local_mid_patch  (C, 16, 16)
        # ------------------------------------------------------------------
        mid_shape = observation_space["local_mid_patch"].shape
        self.mid_cnn = nn.Sequential(
            nn.Conv2d(mid_shape[0], 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            mid_out_dim = self.mid_cnn(torch.zeros(1, *mid_shape)).shape[1]

        # ------------------------------------------------------------------
        # 3. MLP for self_state  (flat vector)
        # ------------------------------------------------------------------
        self_state_dim = observation_space["self_state"].shape[0]
        self.state_mlp = nn.Sequential(
            nn.Linear(self_state_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
        )
        state_out_dim = 64

        # ------------------------------------------------------------------
        # 4. MLP for global_context  (flat vector)
        # ------------------------------------------------------------------
        global_dim = observation_space["global_context"].shape[0]
        self.global_mlp = nn.Sequential(
            nn.Linear(global_dim, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
        )
        global_out_dim = 32

        # ------------------------------------------------------------------
        # 5. Shared MLP for candidate_table rows (K, D) -> max-pool -> (D')
        # ------------------------------------------------------------------
        cand_feat_dim = observation_space["candidate_table"].shape[1]
        self.candidate_mlp = nn.Sequential(
            nn.Linear(cand_feat_dim, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
        )
        cand_out_dim = 32  # after max-pool over K candidates

        # ------------------------------------------------------------------
        # 6. Final fusion MLP
        # ------------------------------------------------------------------
        total_dim = hi_out_dim + mid_out_dim + state_out_dim + global_out_dim + cand_out_dim
        self.fusion_dropout = nn.Dropout(dropout)
        self.final_mlp = nn.Sequential(
            nn.Linear(total_dim, features_dim),
            nn.BatchNorm1d(features_dim),
            nn.ReLU(),
        )

        # Store the authoritative features_dim
        self._features_dim = features_dim

        # Apply Kaiming (He) weight initialisation to all conv/linear layers
        self.apply(_init_weights)

    # ------------------------------------------------------------------
    # Forward
    # ------------------------------------------------------------------
    def forward(self, observations: dict[str, torch.Tensor]) -> torch.Tensor:
        """Fuse all observation modalities into a single feature vector.

        Parameters
        ----------
        observations:
            Dictionary of tensors keyed by observation-space name.
            Batch dimension is always the leading axis.

        Returns
        -------
        torch.Tensor
            Shape ``(batch, features_dim)``.
        """
        hi_features = self.hi_cnn(observations["local_hi_patch"])
        mid_features = self.mid_cnn(observations["local_mid_patch"])
        state_features = self.state_mlp(observations["self_state"])
        global_features = self.global_mlp(observations["global_context"])

        # Candidate table: (batch, K, D) -> shared MLP per row -> (batch, K, 32)
        cand = observations["candidate_table"]
        batch_size = cand.shape[0]
        cand_flat = cand.reshape(-1, cand.shape[-1])          # (batch*K, D)
        cand_encoded = self.candidate_mlp(cand_flat)           # (batch*K, 32)
        cand_encoded = cand_encoded.view(batch_size, -1, cand_encoded.shape[-1])  # (batch, K, 32)
        cand_pooled = cand_encoded.max(dim=1).values           # (batch, 32)

        combined = torch.cat(
            [hi_features, mid_features, state_features, global_features, cand_pooled],
            dim=-1,
        )
        combined = self.fusion_dropout(combined)
        return self.final_mlp(combined)
