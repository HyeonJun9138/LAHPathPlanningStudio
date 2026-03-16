"""Per-source risk computation on a 2-D grid.

Computes a scalar risk field for a single :class:`HazardSource` by
combining range falloff, sector masking, altitude weighting and
influence-radius clamping.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .schema import HazardSource


def _angular_difference(a: NDArray, b: float) -> NDArray:
    """Signed shortest-arc angular difference (degrees), result in [-180, 180)."""
    d = (a - b) % 360.0
    return np.where(d >= 180.0, d - 360.0, d)


def compute_single_source_risk(
    source: HazardSource,
    grid_x: NDArray[np.floating],
    grid_y: NDArray[np.floating],
    altitude: float,
    dem: NDArray[np.floating],
    transform,
) -> NDArray[np.floating]:
    """Return a 2-D risk array for *source* evaluated on the mesh grid.

    Parameters
    ----------
    source:
        The hazard source definition (position, falloff, sector, etc.).
    grid_x, grid_y:
        2-D arrays of map-coordinate positions produced by
        :func:`numpy.meshgrid` (same shape as *dem*).
    altitude:
        The AGL altitude of the evaluation band (metres).
    dem:
        2-D terrain elevation array.
    transform:
        Rasterio affine transform (unused here but accepted for API
        consistency; the grid arrays already carry the spatial info).

    Returns
    -------
    2-D ``float64`` array of risk values in ``[0, 1]`` with the same
    shape as *grid_x*.
    """
    # --- horizontal distance from source to each grid cell ---------------
    dx = grid_x - source.x
    dy = grid_y - source.y
    distance = np.sqrt(dx * dx + dy * dy)

    # --- range falloff ---------------------------------------------------
    radius = source.influence_radius_m
    scale = source.range_falloff_scale

    if source.range_falloff_type == "exp":
        risk = np.exp(-distance / scale)
    elif source.range_falloff_type == "linear":
        risk = np.clip(1.0 - distance / radius, 0.0, 1.0)
    elif source.range_falloff_type == "inverse":
        risk = 1.0 / (1.0 + distance / scale)
    else:
        # Fallback to exponential for unknown types
        risk = np.exp(-distance / scale)

    # --- influence radius mask -------------------------------------------
    risk = np.where(distance <= radius, risk, 0.0)

    # --- sector filtering ------------------------------------------------
    if source.sector_width_deg < 360.0:
        # Bearing from source to each grid cell (north-up clockwise)
        bearing = np.degrees(np.arctan2(dx, dy)) % 360.0
        ang_diff = _angular_difference(bearing, source.sector_azimuth_deg)
        half_width = source.sector_width_deg / 2.0
        in_sector = np.abs(ang_diff) <= half_width
        risk = np.where(in_sector, risk, 0.0)

    # --- altitude weighting ----------------------------------------------
    # Find the best matching altitude band weight.  The profile maps band
    # names to weights; the pipeline calls us with the numeric AGL altitude
    # and, by convention, stores the band name as the string representation.
    # We look for an exact key match first, then fall back to 1.0.
    alt_weight = 1.0
    if source.altitude_weight_profile:
        # Try exact string match of the altitude value
        alt_key = str(altitude)
        if alt_key in source.altitude_weight_profile:
            alt_weight = source.altitude_weight_profile[alt_key]
        else:
            # Try matching as a float via numeric comparison
            best_key = None
            best_dist = float("inf")
            for key, weight in source.altitude_weight_profile.items():
                try:
                    key_alt = float(key)
                except (ValueError, TypeError):
                    # Key is a band name; store for later lookup
                    continue
                d = abs(key_alt - altitude)
                if d < best_dist:
                    best_dist = d
                    best_key = key
            if best_key is not None:
                alt_weight = source.altitude_weight_profile[best_key]
            else:
                # Keys are likely band *names* – look for a key that is a
                # substring of the altitude representation or vice-versa.
                # If nothing matches, weight stays 1.0.
                for key, weight in source.altitude_weight_profile.items():
                    # Accept band name match when the pipeline passes the
                    # band name as the `altitude` string (duck-typed).
                    if key == str(altitude):
                        alt_weight = weight
                        break

    risk = risk * alt_weight

    return risk.astype(np.float64)
