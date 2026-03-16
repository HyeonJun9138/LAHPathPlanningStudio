"""Unit tests for evaluation modules."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestMetrics:
    """Test metric aggregation."""

    def test_compute_episode_metrics(self):
        from src.engine.evaluation.metrics import compute_episode_metrics

        episode_data = {
            "steps": [
                {"risk": 0.1, "distance": 100, "time": 5.0, "visible_time": 1.0,
                 "altitude_violation": False, "zone_violation": False},
                {"risk": 0.2, "distance": 150, "time": 7.0, "visible_time": 0.5,
                 "altitude_violation": False, "zone_violation": False},
                {"risk": 0.05, "distance": 80, "time": 4.0, "visible_time": 0.0,
                 "altitude_violation": False, "zone_violation": False},
            ],
            "success": True,
            "total_return": 85.5,
        }

        metrics = compute_episode_metrics(episode_data)
        assert "success" in metrics
        assert metrics["success"] is True
        assert "total_path_length" in metrics
        assert metrics["total_path_length"] == 330.0
        assert "mean_risk" in metrics

    def test_aggregate_metrics(self):
        from src.engine.evaluation.metrics import aggregate_metrics

        episode_metrics_list = [
            {"success": True, "total_path_length": 500, "mean_risk": 0.1, "total_return": 80},
            {"success": True, "total_path_length": 600, "mean_risk": 0.15, "total_return": 75},
            {"success": False, "total_path_length": 300, "mean_risk": 0.3, "total_return": 20},
        ]

        agg = aggregate_metrics(episode_metrics_list)
        assert "success_rate" in agg
        assert abs(agg["success_rate"] - 2.0/3.0) < 0.01
        assert "mean_path_length" in agg


class TestCompare:
    """Test comparison utilities."""

    def test_compare_table(self):
        from src.engine.evaluation.compare import build_comparison_table

        results = {
            "MaskablePPO": {
                "success_rate": 0.85,
                "mean_risk": 0.12,
                "mean_path_length": 5500,
            },
            "Random": {
                "success_rate": 0.15,
                "mean_risk": 0.45,
                "mean_path_length": 8000,
            },
            "A*": {
                "success_rate": 0.70,
                "mean_risk": 0.20,
                "mean_path_length": 6000,
            },
        }

        table = build_comparison_table(results)
        assert len(table) == 3
        assert "algorithm" in table[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
