"""End-to-end terrain preprocessing pipeline.

Orchestrates the full preprocessing workflow:

1. Load a GeoTIFF elevation raster.
2. Reproject to UTM (if the source CRS is not already projected).
3. Resample to a target resolution.
4. Compute terrain derivatives (slope, aspect, roughness, curvature, etc.)
   via the sibling :mod:`derivatives` module.
5. Persist every array as ``.npy``, generate preview PNGs and histograms,
   write metadata and summary JSON files.
6. Cache intermediate products so re-runs are fast.

The pipeline is driven by a configuration dict whose structure mirrors the
``TerrainPreprocessRequest`` schema defined in the backend API.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ..io.geotiff_loader import load_geotiff
from .reproject import reproject_to_utm
from .resample import resample_array
from .preview import generate_preview_png, generate_histogram_png
from .cache_manager import TerrainCache
from .derivatives import (
    calc_slope,
    calc_aspect,
    calc_roughness,
    calc_curvature,
    calc_tpi,
    calc_openness,
    calc_local_relief,
    calc_ridge_valley_index,
    calc_clearance_cost_base,
)

logger = logging.getLogger(__name__)

# Colourmap hints for each derivative layer
_CMAPS: dict[str, str] = {
    "elevation": "terrain",
    "slope": "YlOrRd",
    "aspect": "hsv",
    "roughness": "inferno",
    "curvature": "RdBu_r",
    "tpi": "RdBu_r",
    "openness": "cividis",
    "local_relief": "magma",
    "ridge_valley_index": "RdBu_r",
    "clearance_cost_base": "hot",
}


class TerrainPreprocessPipeline:
    """Configurable terrain preprocessing pipeline.

    Parameters
    ----------
    config : dict
        Pipeline configuration with the following top-level sections:

        ``terrain``
            - ``target_crs`` (str): ``"auto"`` for UTM auto-detection or an
              EPSG string.
            - ``target_resolution_m`` (float): desired output cell size in
              metres.
            - ``nodata_fill`` (str): strategy for filling nodata pixels
              (currently ``"nearest"`` is the only supported value).
        ``patch``
            - ``hi_size`` (int): high-resolution patch side length (default 128).
            - ``mid_size`` (int): mid-resolution patch side length (default 64).
        ``derivatives``
            - Mapping of derivative name to ``True`` / ``False`` indicating
              whether it should be computed.  Recognised names: ``slope``,
              ``aspect``, ``roughness``, ``curvature``, ``tpi``, ``openness``,
              ``local_relief``, ``ridge_valley_index``, ``clearance_cost_base``.
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.terrain_cfg = config.get("terrain", {})
        self.patch_cfg = config.get("patch", {})
        self.deriv_cfg = config.get("derivatives", {
            "slope": True,
            "aspect": True,
            "roughness": True,
            "curvature": True,
            "tpi": True,
            "openness": True,
            "local_relief": True,
            "ridge_valley_index": True,
            "clearance_cost_base": True,
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _config_hash(config: dict) -> str:
        """Deterministic hash of the config dict for cache keying."""
        raw = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _array_stats(arr: np.ndarray) -> dict[str, float]:
        """Compute basic descriptive statistics over finite values."""
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}
        return {
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "mean": float(np.mean(finite)),
            "std": float(np.std(finite)),
        }

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, terrain_path: str, output_dir: str) -> dict:
        """Execute the full preprocessing pipeline.

        Parameters
        ----------
        terrain_path : str
            Path to the source GeoTIFF file.
        output_dir : str
            Directory for all outputs (.npy arrays, PNGs, JSON files).
            Created automatically if it does not exist.

        Returns
        -------
        dict
            Summary with keys:

            - ``terrain_path`` : echoed input.
            - ``output_dir`` : echoed input.
            - ``crs`` : output CRS as a string.
            - ``resolution`` : output cell size ``(res_x, res_y)``.
            - ``shape`` : ``(height, width)`` of the output arrays.
            - ``derivatives`` : list of derivative names that were computed.
            - ``stats`` : ``{name: {min, max, mean, std}}`` for each layer.
            - ``artifacts`` : list of dicts with ``name``, ``path``, ``type``.
            - ``elapsed_sec`` : wall-clock time in seconds.
        """
        t0 = time.monotonic()

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        arrays_dir = out / "arrays"
        arrays_dir.mkdir(exist_ok=True)
        previews_dir = out / "previews"
        previews_dir.mkdir(exist_ok=True)
        histograms_dir = out / "histograms"
        histograms_dir.mkdir(exist_ok=True)

        # ---- cache setup ----
        cache_dir = out / ".cache"
        cache = TerrainCache(str(cache_dir))
        cfg_hash = self._config_hash(self.config)

        artifacts: list[dict[str, Any]] = []
        stats: dict[str, dict[str, float]] = {}

        # ==============================================================
        # 1. Load GeoTIFF
        # ==============================================================
        logger.info("Loading GeoTIFF: %s", terrain_path)
        loaded = load_geotiff(terrain_path)
        elevation = loaded["data"]  # float32, 2-D
        src_crs = loaded["crs"]
        src_transform = loaded["transform"]
        src_resolution = loaded["resolution"]
        src_nodata = loaded["nodata"]

        # ==============================================================
        # 2. Reproject to UTM if needed
        # ==============================================================
        target_crs_cfg = self.terrain_cfg.get("target_crs", "auto")
        target_resolution = float(self.terrain_cfg.get("target_resolution_m", 30.0))

        cache_key_reproj = cache._compute_key("reprojected", cfg_hash)

        if cache.has_cache(cache_key_reproj):
            logger.info("Loading reprojected elevation from cache")
            elevation = cache.load_array(cache_key_reproj)
            meta_reproj = cache.load_metadata(cache_key_reproj)
            from rasterio.crs import CRS
            from rasterio.transform import Affine
            out_crs = CRS.from_user_input(meta_reproj["crs"])
            out_transform = Affine(*meta_reproj["transform"][:6])
            out_resolution = tuple(meta_reproj["resolution"])
        else:
            needs_reproject = False
            if src_crs is not None and hasattr(src_crs, "is_projected"):
                if not src_crs.is_projected:
                    needs_reproject = True
            if target_crs_cfg != "auto" and str(src_crs) != target_crs_cfg:
                needs_reproject = True

            if needs_reproject:
                logger.info("Reprojecting to UTM (target_resolution=%.1f m)", target_resolution)
                reproj = reproject_to_utm(
                    data=elevation,
                    src_crs=src_crs,
                    src_transform=src_transform,
                    src_nodata=src_nodata,
                    target_resolution=target_resolution,
                )
                elevation = reproj["data"]
                out_crs = reproj["crs"]
                out_transform = reproj["transform"]
                out_resolution = reproj["resolution"]
            else:
                out_crs = src_crs
                out_transform = src_transform
                out_resolution = src_resolution

            # ==============================================================
            # 3. Resample to exact target resolution
            # ==============================================================
            current_res = float(out_resolution[0])
            if abs(current_res - target_resolution) > 0.01 * target_resolution:
                logger.info(
                    "Resampling from %.2f m to %.2f m",
                    current_res, target_resolution,
                )
                resampled = resample_array(
                    data=elevation,
                    src_resolution=out_resolution,
                    target_resolution=target_resolution,
                    order=1,
                    src_transform=out_transform,
                )
                elevation = resampled["data"]
                out_resolution = resampled["resolution"]
                if "transform" in resampled:
                    out_transform = resampled["transform"]

            # Cache the reprojected + resampled elevation
            cache.save_array(cache_key_reproj, elevation)
            cache.save_metadata(cache_key_reproj, {
                "crs": str(out_crs),
                "transform": list(out_transform)[:6],
                "resolution": list(out_resolution),
            })

        cell_size = float(out_resolution[0])
        res_pair = (cell_size, cell_size)
        height, width = elevation.shape

        # ==============================================================
        # 4. Save elevation array
        # ==============================================================
        elev_path = arrays_dir / "elevation.npy"
        np.save(str(elev_path), elevation)
        artifacts.append({"name": "elevation", "path": str(elev_path), "type": "npy"})
        stats["elevation"] = self._array_stats(elevation)

        # Preview for elevation
        elev_png = previews_dir / "elevation.png"
        generate_preview_png(elevation, str(elev_png), cmap="terrain", title="Elevation (m)")
        artifacts.append({"name": "elevation_preview", "path": str(elev_png), "type": "png"})
        elev_hist = histograms_dir / "elevation_hist.png"
        generate_histogram_png(elevation, str(elev_hist), title="Elevation Distribution")
        artifacts.append({"name": "elevation_histogram", "path": str(elev_hist), "type": "png"})

        # ==============================================================
        # 5. Compute all derivatives using the derivatives module
        # ==============================================================
        derivatives: dict[str, np.ndarray] = {}
        derivative_names: list[str] = []

        def _maybe_compute(name: str, func, *args, **kwargs) -> np.ndarray | None:
            """Compute a derivative if enabled in config, with cache support."""
            if not self.deriv_cfg.get(name, False):
                return None
            cache_key = cache._compute_key(name, cfg_hash)
            if cache.has_cache(cache_key):
                logger.info("Loading %s from cache", name)
                arr = cache.load_array(cache_key)
            else:
                logger.info("Computing %s", name)
                arr = func(*args, **kwargs)
                cache.save_array(cache_key, arr)
            derivatives[name] = arr
            derivative_names.append(name)
            return arr

        # Primary derivatives
        slope = _maybe_compute("slope", calc_slope, elevation, res_pair)
        aspect = _maybe_compute("aspect", calc_aspect, elevation, res_pair)
        roughness = _maybe_compute("roughness", calc_roughness, elevation)
        curvature = _maybe_compute("curvature", calc_curvature, elevation, res_pair)
        tpi = _maybe_compute("tpi", calc_tpi, elevation)
        openness = _maybe_compute("openness", calc_openness, elevation, res_pair)
        local_relief = _maybe_compute("local_relief", calc_local_relief, elevation)

        # Ridge-valley index requires TPI and curvature
        if self.deriv_cfg.get("ridge_valley_index", False):
            # Ensure prerequisites are computed even if not individually requested
            if tpi is None:
                tpi = calc_tpi(elevation)
            if curvature is None:
                curvature = calc_curvature(elevation, res_pair)
            _maybe_compute("ridge_valley_index", calc_ridge_valley_index, tpi, curvature)

        # Clearance cost base requires slope and roughness
        if self.deriv_cfg.get("clearance_cost_base", False):
            if slope is None:
                slope = calc_slope(elevation, res_pair)
            if roughness is None:
                roughness = calc_roughness(elevation)
            _maybe_compute("clearance_cost_base", calc_clearance_cost_base, slope, roughness)

        # ==============================================================
        # 6. Save derivative arrays, previews, histograms
        # ==============================================================
        for name, arr in derivatives.items():
            # .npy
            arr_path = arrays_dir / f"{name}.npy"
            np.save(str(arr_path), arr)
            artifacts.append({"name": name, "path": str(arr_path), "type": "npy"})
            stats[name] = self._array_stats(arr)

            # preview PNG
            cmap = _CMAPS.get(name, "viridis")
            png_path = previews_dir / f"{name}.png"
            generate_preview_png(
                arr, str(png_path),
                cmap=cmap,
                title=name.replace("_", " ").title(),
            )
            artifacts.append({"name": f"{name}_preview", "path": str(png_path), "type": "png"})

            # histogram PNG
            hist_path = histograms_dir / f"{name}_hist.png"
            generate_histogram_png(
                arr, str(hist_path),
                title=f"{name.replace('_', ' ').title()} Distribution",
            )
            artifacts.append({"name": f"{name}_histogram", "path": str(hist_path), "type": "png"})

        # ==============================================================
        # 7. Metadata JSON
        # ==============================================================
        metadata = {
            "terrain_path": str(terrain_path),
            "output_dir": str(output_dir),
            "crs": str(out_crs),
            "transform": list(out_transform)[:6],
            "resolution": list(out_resolution),
            "width": width,
            "height": height,
            "shape": [height, width],
            "cell_size_m": cell_size,
            "derivatives_computed": derivative_names,
            "config": self.config,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = out / "metadata.json"
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, default=str)
        artifacts.append({"name": "metadata", "path": str(meta_path), "type": "json"})

        # ==============================================================
        # 8. Summary JSON
        # ==============================================================
        elapsed = time.monotonic() - t0

        summary: dict[str, Any] = {
            "terrain_path": str(terrain_path),
            "output_dir": str(output_dir),
            "crs": str(out_crs),
            "resolution": list(out_resolution),
            "shape": [height, width],
            "derivatives": derivative_names,
            "stats": stats,
            "artifacts": artifacts,
            "elapsed_sec": round(elapsed, 3),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        summary_path = out / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, default=str)
        artifacts.append({"name": "summary", "path": str(summary_path), "type": "json"})

        logger.info(
            "Pipeline complete: %d derivatives, %d artifacts in %.1fs",
            len(derivative_names),
            len(artifacts),
            elapsed,
        )

        return summary
