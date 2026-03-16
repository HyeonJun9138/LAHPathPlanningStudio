"""Unit tests for terrain engine modules."""
import numpy as np
import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestDerivatives:
    """Test terrain derivative calculations."""

    def _make_dem(self, rows=100, cols=100, res=30.0):
        """Create synthetic DEM: a smooth hill."""
        y, x = np.mgrid[0:rows, 0:cols].astype(np.float32)
        cx, cy = cols / 2, rows / 2
        dem = 500.0 + 200.0 * np.exp(-((x - cx)**2 + (y - cy)**2) / (2 * 20**2))
        return dem, res

    def test_slope_flat(self):
        from src.engine.terrain.derivatives import calc_slope
        flat = np.ones((50, 50), dtype=np.float32) * 100.0
        slope = calc_slope(flat, 30.0)
        assert slope.shape == (50, 50)
        # Flat terrain should have near-zero slope
        assert np.nanmax(slope) < 1.0  # degrees

    def test_slope_ramp(self):
        from src.engine.terrain.derivatives import calc_slope
        # 45-degree ramp: elevation rises 1m per 1m horizontal
        dem = np.zeros((50, 50), dtype=np.float32)
        for i in range(50):
            dem[i, :] = i * 30.0  # 30m rise per 30m pixel
        slope = calc_slope(dem, 30.0)
        # Should be approximately 45 degrees in the middle
        mid = slope[25, 25]
        assert 40.0 < mid < 50.0

    def test_roughness_shape(self):
        from src.engine.terrain.derivatives import calc_roughness
        dem, res = self._make_dem()
        rough = calc_roughness(dem, window=5)
        assert rough.shape == dem.shape

    def test_curvature_shape(self):
        from src.engine.terrain.derivatives import calc_curvature
        dem, res = self._make_dem()
        curv = calc_curvature(dem, res)
        assert curv.shape == dem.shape

    def test_tpi_flat(self):
        from src.engine.terrain.derivatives import calc_tpi
        flat = np.ones((50, 50), dtype=np.float32) * 100.0
        tpi = calc_tpi(flat, window=11)
        assert tpi.shape == (50, 50)
        # TPI of flat terrain should be near zero
        assert np.abs(np.nanmean(tpi)) < 0.1

    def test_local_relief_shape(self):
        from src.engine.terrain.derivatives import calc_local_relief
        dem, res = self._make_dem()
        relief = calc_local_relief(dem, window=11)
        assert relief.shape == dem.shape
        assert np.nanmin(relief) >= 0  # Relief is always non-negative

    def test_clearance_cost_base(self):
        from src.engine.terrain.derivatives import (
            calc_slope, calc_roughness, calc_clearance_cost_base
        )
        dem, res = self._make_dem()
        slope = calc_slope(dem, res)
        rough = calc_roughness(dem, window=5)
        cost = calc_clearance_cost_base(slope, rough)
        assert cost.shape == dem.shape
        assert np.nanmin(cost) >= 0


class TestPatchSampler:
    """Test patch extraction."""

    def test_patch_shape(self):
        from src.engine.terrain.patch_sampler import PatchSampler
        dem = np.random.rand(500, 500).astype(np.float32) * 1000
        metadata = {
            "transform": [30.0, 0.0, 0.0, 0.0, -30.0, 15000.0],
            "resolution": (30.0, 30.0),
            "width": 500,
            "height": 500,
        }
        sampler = PatchSampler(
            terrain_arrays={"elevation": dem},
            metadata=metadata,
        )
        patch = sampler.extract_local_hi(7500.0, 7500.0, size=32)
        assert patch.ndim == 3
        assert patch.shape[1] == 32
        assert patch.shape[2] == 32


class TestCacheManager:
    """Test terrain cache."""

    def test_save_load(self, tmp_path):
        from src.engine.terrain.cache_manager import TerrainCache
        cache = TerrainCache(str(tmp_path))
        arr = np.random.rand(100, 100).astype(np.float32)
        cache.save_array("test_key", arr)
        assert cache.has_cache("test_key")
        loaded = cache.load_array("test_key")
        np.testing.assert_array_equal(arr, loaded)

    def test_cache_miss(self, tmp_path):
        from src.engine.terrain.cache_manager import TerrainCache
        cache = TerrainCache(str(tmp_path))
        assert not cache.has_cache("nonexistent_key")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
