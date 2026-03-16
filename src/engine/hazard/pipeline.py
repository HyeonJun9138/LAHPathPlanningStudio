"""End-to-end hazard-build pipeline.

Orchestrates per-band risk computation, fusion, restricted-zone
overlays, observation-box feasibility, and persists the results to
disk.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .fusion import fuse_risks
from .observe_box import compute_observe_feasibility
from .risk_models import compute_single_source_risk
from .schema import HazardConfig, RestrictedZone


def _apply_restricted_zones(
    risk: NDArray[np.floating],
    zones: list[RestrictedZone],
    grid_x: NDArray[np.floating],
    grid_y: NDArray[np.floating],
    altitude: float,
) -> NDArray[np.floating]:
    """Overlay restricted-zone penalties onto the fused risk surface.

    Hard zones are set to 1.0; soft zones add their penalty value (clamped
    to [0, 1]).
    """
    result = risk.copy()
    for zone in zones:
        if altitude < zone.min_altitude_m or altitude > zone.max_altitude_m:
            continue
        mask = _point_in_polygon(grid_x, grid_y, zone.polygon)
        if zone.penalty_type == "hard":
            result[mask] = 1.0
        else:
            result[mask] = np.clip(result[mask] + zone.penalty_value, 0.0, 1.0)
    return result


def _point_in_polygon(
    gx: NDArray[np.floating],
    gy: NDArray[np.floating],
    polygon: list[list[float]],
) -> NDArray[np.bool_]:
    """Vectorised ray-casting point-in-polygon test.

    *polygon* is a list of ``[x, y]`` vertices.  The polygon is closed
    automatically (last vertex connects back to the first).
    """
    n = len(polygon)
    if n < 3:
        return np.zeros(gx.shape, dtype=bool)

    inside = np.zeros(gx.shape, dtype=bool)
    px = np.array([v[0] for v in polygon], dtype=np.float64)
    py = np.array([v[1] for v in polygon], dtype=np.float64)

    j = n - 1
    for i in range(n):
        # Edge from vertex j to vertex i
        yi = py[i]
        yj = py[j]
        xi = px[i]
        xj = px[j]

        # Condition: one vertex above, one below (or equal to) the test y
        cond = (yi > gy) != (yj > gy)
        # x-intercept of the edge at the test y
        slope = (xj - xi) / (yj - yi + 1e-30)
        x_intersect = xi + (gy - yi) * slope
        cross = cond & (gx < x_intersect)
        inside = inside ^ cross

        j = i

    return inside


def _save_preview_png(
    array: NDArray[np.floating],
    path: str | Path,
) -> None:
    """Save a quick greyscale PNG preview of a 2-D array.

    Uses raw file writing with a minimal PNG via numpy + zlib so that we
    do not depend on matplotlib or PIL at import time.  Falls back to
    ``.npy`` if the optional dependency is missing.
    """
    try:
        from PIL import Image  # type: ignore[import-untyped]

        arr = np.nan_to_num(array, nan=0.0)
        lo, hi = float(arr.min()), float(arr.max())
        if hi - lo > 1e-9:
            arr = (arr - lo) / (hi - lo)
        else:
            arr = np.zeros_like(arr)
        img = Image.fromarray((arr * 255).astype(np.uint8), mode="L")
        img.save(str(path))
    except ImportError:
        # Fallback: just save as .npy alongside
        fallback = str(path).rsplit(".", 1)[0] + ".npy"
        np.save(fallback, array)


class HazardBuildPipeline:
    """Builds composite risk surfaces and observation feasibility maps.

    Usage::

        config = HazardConfig(...)
        pipeline = HazardBuildPipeline(config)
        summary = pipeline.run(dem, transform, output_dir="workspace/hazard_out")
    """

    def __init__(self, config: HazardConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    def run(
        self,
        dem: NDArray[np.floating],
        transform,
        output_dir: str | Path,
    ) -> dict[str, Any]:
        """Execute the full hazard build.

        Parameters
        ----------
        dem:
            2-D elevation array.
        transform:
            Rasterio affine transform.
        output_dir:
            Directory where arrays, previews and the summary JSON are
            written.  Created if it does not exist.

        Returns
        -------
        Summary dict with timing, file paths and statistics.
        """
        t0 = time.time()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        nrows, ncols = dem.shape

        # Build map-coordinate meshgrid (pixel centres)
        cols = np.arange(ncols, dtype=np.float64) + 0.5
        rows = np.arange(nrows, dtype=np.float64) + 0.5
        col_grid, row_grid = np.meshgrid(cols, rows)

        a = transform.a
        b = transform.b
        c = transform.c
        d = transform.d
        e = transform.e
        f = transform.f

        grid_x = a * col_grid + b * row_grid + c
        grid_y = d * col_grid + e * row_grid + f

        enabled_sources = [s for s in self.config.sources if s.enabled]

        summary: dict[str, Any] = {
            "bands": {},
            "observe_boxes": {},
            "files": [],
            "timing_sec": 0.0,
            "n_sources": len(enabled_sources),
            "n_restricted_zones": len(self.config.restricted_zones),
            "n_observe_boxes": len(self.config.observe_boxes),
        }

        # ---- Per altitude band ------------------------------------------
        for band in self.config.altitude_bands:
            band_t0 = time.time()
            altitude = band.agl_m

            risk_layers: list[NDArray[np.floating]] = []
            for source in enabled_sources:
                layer = compute_single_source_risk(
                    source=source,
                    grid_x=grid_x,
                    grid_y=grid_y,
                    altitude=altitude,
                    dem=dem,
                    transform=transform,
                )
                risk_layers.append(layer)

            # Fuse layers (or produce a zero surface if no sources)
            if risk_layers:
                fused = fuse_risks(risk_layers, mode=self.config.fusion_mode)
            else:
                fused = np.zeros((nrows, ncols), dtype=np.float64)

            # Restricted-zone overlay
            if self.config.restricted_zones:
                fused = _apply_restricted_zones(
                    fused,
                    self.config.restricted_zones,
                    grid_x,
                    grid_y,
                    altitude,
                )

            # Persist
            band_name_safe = band.name.replace(" ", "_").lower()
            npy_path = output_dir / f"risk_{band_name_safe}.npy"
            png_path = output_dir / f"risk_{band_name_safe}.png"
            np.save(str(npy_path), fused)
            _save_preview_png(fused, png_path)

            band_stats = {
                "altitude_agl_m": altitude,
                "risk_min": float(np.nanmin(fused)),
                "risk_max": float(np.nanmax(fused)),
                "risk_mean": float(np.nanmean(fused)),
                "risk_nonzero_frac": float(np.count_nonzero(fused) / fused.size),
                "n_layers": len(risk_layers),
                "npy_file": str(npy_path),
                "png_file": str(png_path),
                "time_sec": time.time() - band_t0,
            }
            summary["bands"][band.name] = band_stats
            summary["files"].extend([str(npy_path), str(png_path)])

        # ---- Observe boxes ----------------------------------------------
        for box in self.config.observe_boxes:
            box_t0 = time.time()
            # Evaluate at the first altitude band (primary observation layer)
            obs_band = self.config.altitude_bands[0] if self.config.altitude_bands else None
            if obs_band is None:
                continue

            feasibility_map, vis_ratio_map, entry_cost_map = compute_observe_feasibility(
                box=box,
                dem=dem,
                transform=transform,
                altitude_band=obs_band,
            )

            box_id_safe = box.id.replace(" ", "_").lower()
            feas_npy = output_dir / f"obs_{box_id_safe}_feasibility.npy"
            vis_npy = output_dir / f"obs_{box_id_safe}_visibility.npy"
            cost_npy = output_dir / f"obs_{box_id_safe}_entry_cost.npy"
            feas_png = output_dir / f"obs_{box_id_safe}_feasibility.png"

            np.save(str(feas_npy), feasibility_map)
            np.save(str(vis_npy), vis_ratio_map)
            np.save(str(cost_npy), entry_cost_map)
            _save_preview_png(feasibility_map, feas_png)

            box_stats = {
                "band_used": obs_band.name,
                "feasible_cell_frac": float(
                    np.count_nonzero(feasibility_map) / feasibility_map.size
                ),
                "mean_visibility_ratio": float(np.nanmean(vis_ratio_map)),
                "mean_entry_cost_m": float(np.nanmean(entry_cost_map)),
                "files": [str(feas_npy), str(vis_npy), str(cost_npy), str(feas_png)],
                "time_sec": time.time() - box_t0,
            }
            summary["observe_boxes"][box.id] = box_stats
            summary["files"].extend(box_stats["files"])

        # ---- Summary ----------------------------------------------------
        summary["timing_sec"] = time.time() - t0
        summary_path = output_dir / "hazard_summary.json"
        with open(summary_path, "w") as fp:
            json.dump(summary, fp, indent=2)
        summary["files"].append(str(summary_path))

        return summary
