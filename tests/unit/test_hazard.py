"""Unit tests for hazard engine modules."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestLoS:
    """Test Line-of-Sight calculations."""

    def test_los_flat_terrain(self):
        """On flat terrain, LoS should always be clear."""
        from src.engine.hazard.los import compute_los
        from rasterio.transform import from_bounds

        dem = np.ones((100, 100), dtype=np.float32) * 100.0
        transform = from_bounds(0, 0, 3000, 3000, 100, 100)

        result = compute_los(
            source_xyz=(500, 500, 150),
            target_xyz=(2500, 2500, 150),
            dem=dem,
            transform=transform,
            clearance=10.0,
        )
        assert result["visible"] is True
        assert result["visible_ratio"] > 0.9

    def test_los_blocked_by_ridge(self):
        """A tall ridge between source and target should block LoS."""
        from src.engine.hazard.los import compute_los
        from rasterio.transform import from_bounds

        dem = np.ones((100, 100), dtype=np.float32) * 100.0
        # Add a ridge in the middle
        dem[48:52, :] = 500.0
        transform = from_bounds(0, 0, 3000, 3000, 100, 100)

        result = compute_los(
            source_xyz=(500, 500, 120),
            target_xyz=(2500, 2500, 120),
            dem=dem,
            transform=transform,
            clearance=10.0,
        )
        assert result["visible"] is False
        assert result["visible_ratio"] < 1.0


class TestRiskFusion:
    """Test risk map fusion."""

    def test_probabilistic_union(self):
        from src.engine.hazard.fusion import fuse_risks

        r1 = np.full((50, 50), 0.3, dtype=np.float32)
        r2 = np.full((50, 50), 0.4, dtype=np.float32)
        fused = fuse_risks([r1, r2], mode="probabilistic_union")

        # 1 - (1-0.3)*(1-0.4) = 1 - 0.42 = 0.58
        expected = 0.58
        np.testing.assert_allclose(fused[25, 25], expected, atol=0.01)

    def test_max_fusion(self):
        from src.engine.hazard.fusion import fuse_risks

        r1 = np.full((50, 50), 0.3, dtype=np.float32)
        r2 = np.full((50, 50), 0.7, dtype=np.float32)
        fused = fuse_risks([r1, r2], mode="max")
        np.testing.assert_allclose(fused[25, 25], 0.7, atol=0.01)

    def test_sum_clip(self):
        from src.engine.hazard.fusion import fuse_risks

        r1 = np.full((50, 50), 0.6, dtype=np.float32)
        r2 = np.full((50, 50), 0.7, dtype=np.float32)
        fused = fuse_risks([r1, r2], mode="sum_clip")
        # sum=1.3, clipped to 1.0
        assert fused[25, 25] <= 1.0


class TestRiskModels:
    """Test per-source risk calculation."""

    def test_single_source_shape(self):
        from src.engine.hazard.risk_models import compute_single_source_risk
        from src.engine.hazard.schema import HazardSource

        source = HazardSource(
            id="hz_test",
            name="test_hazard",
            type="visibility_sensitive_zone",
            x=1500.0,
            y=1500.0,
            z=100.0,
            influence_radius_m=2000.0,
        )
        grid_x = np.arange(0, 3000, 30).astype(np.float32)
        grid_y = np.arange(0, 3000, 30).astype(np.float32)
        dem = np.ones((100, 100), dtype=np.float32) * 100.0

        risk = compute_single_source_risk(
            source=source,
            grid_x=grid_x,
            grid_y=grid_y,
            altitude=100.0,
            dem=dem,
        )
        assert risk.shape == (len(grid_y), len(grid_x))
        assert np.nanmin(risk) >= 0
        assert np.nanmax(risk) <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
