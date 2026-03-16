"""Terrain derivative calculations for path-planning cost surfaces.

Every public function in this module performs real numerical computation
on a 2-D DEM array (elevation in metres) and returns a same-shaped
float32 result.  No stubs, no placeholders.

Typical usage
-------------
>>> from engine.terrain.derivatives import calc_slope, calc_aspect
>>> slope = calc_slope(dem, res=(10.0, 10.0))
>>> aspect = calc_aspect(dem, res=(10.0, 10.0))
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import (
    generic_filter,
    maximum_filter,
    minimum_filter,
    uniform_filter,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _gradient_components(
    dem: np.ndarray,
    res: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Return (dz_dx, dz_dy) using np.gradient.

    ``res`` is (res_x, res_y) — the cell size in metres along the
    x (column) and y (row) axes respectively.
    """
    res_x, res_y = float(res[0]), float(res[1])
    # np.gradient returns gradients along each axis of the array.
    # axis 0 = rows (y direction), axis 1 = cols (x direction).
    dz_dy = np.gradient(dem.astype(np.float64), res_y, axis=0)
    dz_dx = np.gradient(dem.astype(np.float64), res_x, axis=1)
    return dz_dx, dz_dy


# ---------------------------------------------------------------------------
# primary derivatives
# ---------------------------------------------------------------------------

def calc_slope(dem: np.ndarray, res: tuple[float, float]) -> np.ndarray:
    """Slope in **degrees** — arctan(sqrt(dz_dx^2 + dz_dy^2)).

    Parameters
    ----------
    dem : 2-D float array — elevation in metres.
    res : (res_x, res_y) cell sizes in metres.

    Returns
    -------
    np.ndarray (float32) — slope values in the range [0, 90].
    """
    dz_dx, dz_dy = _gradient_components(dem, res)
    slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))
    return np.degrees(slope_rad).astype(np.float32)


def calc_aspect(dem: np.ndarray, res: tuple[float, float]) -> np.ndarray:
    """Aspect in **degrees** measured clockwise from north [0, 360).

    Uses the convention ``atan2(-dz_dy, dz_dx)`` to produce a
    mathematical angle, then converts to compass bearing (north = 0).
    Flat areas (gradient magnitude < 1e-8) are assigned -1.

    Parameters
    ----------
    dem : 2-D float array — elevation in metres.
    res : (res_x, res_y) cell sizes in metres.

    Returns
    -------
    np.ndarray (float32) — aspect in degrees.
    """
    dz_dx, dz_dy = _gradient_components(dem, res)
    # Mathematical angle: 0 = east, counter-clockwise positive
    angle_rad = np.arctan2(-dz_dy, dz_dx)
    # Convert to compass bearing: north = 0, clockwise
    aspect_deg = np.degrees(angle_rad)
    # Rotate: compass = 90 - math_angle, then normalise to [0, 360)
    compass = (90.0 - aspect_deg) % 360.0

    # Mark flat pixels
    magnitude = np.sqrt(dz_dx ** 2 + dz_dy ** 2)
    compass[magnitude < 1e-8] = -1.0

    return compass.astype(np.float32)


# ---------------------------------------------------------------------------
# texture / roughness derivatives
# ---------------------------------------------------------------------------

def calc_roughness(dem: np.ndarray, window: int = 5) -> np.ndarray:
    """Surface roughness — local standard deviation of elevation.

    Parameters
    ----------
    dem : 2-D float array.
    window : odd int — side length of the square neighbourhood.

    Returns
    -------
    np.ndarray (float32) — roughness (same units as *dem*).
    """
    dem64 = dem.astype(np.float64)

    # E[x^2] - (E[x])^2  avoids a per-pixel generic_filter
    local_mean = uniform_filter(dem64, size=window, mode="nearest")
    local_sq_mean = uniform_filter(dem64 ** 2, size=window, mode="nearest")
    variance = local_sq_mean - local_mean ** 2
    # Numerical noise can create tiny negatives
    variance = np.clip(variance, 0.0, None)
    return np.sqrt(variance).astype(np.float32)


# ---------------------------------------------------------------------------
# curvature
# ---------------------------------------------------------------------------

def calc_curvature(dem: np.ndarray, res: tuple[float, float]) -> np.ndarray:
    """Profile + plan curvature (Laplacian approximation).

    Computed as ``d2z/dx2 + d2z/dy2`` — the discrete Laplacian of the
    surface, which combines profile and plan curvature into a single
    scalar.  Positive values indicate concavity (valleys), negative
    values indicate convexity (ridges).

    Parameters
    ----------
    dem : 2-D float array — elevation in metres.
    res : (res_x, res_y) cell sizes in metres.

    Returns
    -------
    np.ndarray (float32) — curvature values (1/m).
    """
    res_x, res_y = float(res[0]), float(res[1])
    dem64 = dem.astype(np.float64)

    # Second partial derivatives via central differences
    # d2z/dx2  (along columns)
    d2z_dx2 = np.zeros_like(dem64)
    d2z_dx2[:, 1:-1] = (
        dem64[:, 2:] - 2.0 * dem64[:, 1:-1] + dem64[:, :-2]
    ) / (res_x ** 2)
    # Replicate boundary values
    d2z_dx2[:, 0] = d2z_dx2[:, 1]
    d2z_dx2[:, -1] = d2z_dx2[:, -2]

    # d2z/dy2  (along rows)
    d2z_dy2 = np.zeros_like(dem64)
    d2z_dy2[1:-1, :] = (
        dem64[2:, :] - 2.0 * dem64[1:-1, :] + dem64[:-2, :]
    ) / (res_y ** 2)
    d2z_dy2[0, :] = d2z_dy2[1, :]
    d2z_dy2[-1, :] = d2z_dy2[-2, :]

    curvature = d2z_dx2 + d2z_dy2
    return curvature.astype(np.float32)


# ---------------------------------------------------------------------------
# TPI — Topographic Position Index
# ---------------------------------------------------------------------------

def calc_tpi(dem: np.ndarray, window: int = 11) -> np.ndarray:
    """Topographic Position Index — centre minus neighbourhood mean.

    Positive values → ridges / hilltops.
    Negative values → valleys / depressions.
    Near zero        → flat areas or constant slopes.

    Parameters
    ----------
    dem : 2-D float array — elevation in metres.
    window : odd int — side length of the square neighbourhood.

    Returns
    -------
    np.ndarray (float32) — TPI values (same units as *dem*).
    """
    dem64 = dem.astype(np.float64)
    local_mean = uniform_filter(dem64, size=window, mode="nearest")
    tpi = dem64 - local_mean
    return tpi.astype(np.float32)


# ---------------------------------------------------------------------------
# topographic openness
# ---------------------------------------------------------------------------

def calc_openness(
    dem: np.ndarray,
    res: tuple[float, float],
    radius: float = 500.0,
) -> np.ndarray:
    """Positive topographic openness — a view-shed proxy.

    For each pixel the algorithm looks outward in eight cardinal /
    diagonal directions up to *radius* metres and measures the maximum
    elevation angle (zenith angle from horizontal) along each ray.
    Openness is the mean of (90 - max_elevation_angle) across the eight
    directions, expressed in degrees.  High values indicate exposed
    terrain; low values indicate enclosed terrain (e.g. narrow valleys).

    This is an efficient approximation that steps outward at pixel
    increments rather than sub-pixel interpolation.

    Parameters
    ----------
    dem : 2-D float array — elevation in metres.
    res : (res_x, res_y) cell sizes in metres.
    radius : float — search radius in metres (default 500).

    Returns
    -------
    np.ndarray (float32) — openness in degrees [0, 90].
    """
    res_x, res_y = float(res[0]), float(res[1])
    dem64 = dem.astype(np.float64)
    rows, cols = dem64.shape

    # Eight directions as (row_step, col_step)
    directions = [
        (-1, 0),   # N
        (-1, 1),   # NE
        (0, 1),    # E
        (1, 1),    # SE
        (1, 0),    # S
        (1, -1),   # SW
        (0, -1),   # W
        (-1, -1),  # NW
    ]

    # Horizontal distance per step for each direction
    step_distances = []
    for dr, dc in directions:
        dist = np.sqrt((dr * res_y) ** 2 + (dc * res_x) ** 2)
        step_distances.append(dist)

    openness = np.zeros_like(dem64)

    for idx, (dr, dc) in enumerate(directions):
        step_dist = step_distances[idx]
        max_steps = max(1, int(radius / step_dist))
        max_angle = np.full_like(dem64, -90.0)  # worst-case: looking straight down

        for s in range(1, max_steps + 1):
            horiz_dist = s * step_dist
            # Compute shifted indices
            # Positive dr means moving toward higher row indices
            r_start = max(0, s * dr)
            r_end_offset = s * dr  # can be negative
            c_start = max(0, s * dc)
            c_end_offset = s * dc

            # Determine the overlapping slice
            if dr > 0:
                src_r = slice(0, rows - s * dr)
                dst_r = slice(s * dr, rows)
            elif dr < 0:
                src_r = slice(-s * dr, rows)
                dst_r = slice(0, rows + s * dr)
            else:
                src_r = slice(0, rows)
                dst_r = slice(0, rows)

            if dc > 0:
                src_c = slice(0, cols - s * dc)
                dst_c = slice(s * dc, cols)
            elif dc < 0:
                src_c = slice(-s * dc, cols)
                dst_c = slice(0, cols + s * dc)
            else:
                src_c = slice(0, cols)
                dst_c = slice(0, cols)

            dz = dem64[dst_r, dst_c] - dem64[src_r, src_c]
            elev_angle = np.degrees(np.arctan2(dz, horiz_dist))
            np.maximum(max_angle[src_r, src_c], elev_angle, out=max_angle[src_r, src_c])

        # Openness contribution for this direction: 90 - max_elevation_angle
        openness += 90.0 - max_angle

    # Average over eight directions
    openness /= len(directions)
    return np.clip(openness, 0.0, 90.0).astype(np.float32)


# ---------------------------------------------------------------------------
# local relief
# ---------------------------------------------------------------------------

def calc_local_relief(dem: np.ndarray, window: int = 11) -> np.ndarray:
    """Local relief — local maximum minus local minimum.

    Captures the range of elevation within a neighbourhood, useful for
    identifying flat vs. rugged terrain.

    Parameters
    ----------
    dem : 2-D float array — elevation in metres.
    window : odd int — side length of the square neighbourhood.

    Returns
    -------
    np.ndarray (float32) — relief values (same units as *dem*).
    """
    dem64 = dem.astype(np.float64)
    local_max = maximum_filter(dem64, size=window, mode="nearest")
    local_min = minimum_filter(dem64, size=window, mode="nearest")
    return (local_max - local_min).astype(np.float32)


# ---------------------------------------------------------------------------
# ridge / valley index
# ---------------------------------------------------------------------------

def calc_ridge_valley_index(
    tpi: np.ndarray,
    curvature: np.ndarray,
) -> np.ndarray:
    """Normalised ridge-valley composite index.

    Combines TPI and curvature into a single index in roughly [-1, 1]
    where positive values lean toward ridges and negative toward valleys.

    Both inputs are first standardised (zero mean, unit variance) and
    then averaged so that neither dominates the composite.

    Parameters
    ----------
    tpi : 2-D float array — output of :func:`calc_tpi`.
    curvature : 2-D float array — output of :func:`calc_curvature`.

    Returns
    -------
    np.ndarray (float32) — ridge-valley index.
    """
    # Standardise each input
    tpi64 = tpi.astype(np.float64)
    curv64 = curvature.astype(np.float64)

    tpi_std = tpi64.std()
    curv_std = curv64.std()

    if tpi_std > 1e-12:
        tpi_norm = (tpi64 - tpi64.mean()) / tpi_std
    else:
        tpi_norm = np.zeros_like(tpi64)

    if curv_std > 1e-12:
        curv_norm = (curv64 - curv64.mean()) / curv_std
    else:
        curv_norm = np.zeros_like(curv64)

    # TPI > 0 indicates ridges; curvature < 0 indicates ridges (convex)
    # Flip curvature sign so that ridges are positive in both terms
    composite = (tpi_norm - curv_norm) / 2.0

    return composite.astype(np.float32)


# ---------------------------------------------------------------------------
# clearance cost base
# ---------------------------------------------------------------------------

def calc_clearance_cost_base(
    slope: np.ndarray,
    roughness: np.ndarray,
    slope_weight: float = 0.7,
    roughness_weight: float = 0.3,
) -> np.ndarray:
    """Weighted clearance-cost base surface.

    Produces a [0, 1] cost layer by normalising slope and roughness to
    their respective [0, 1] ranges and combining them with configurable
    weights.  Higher values → harder to traverse.

    Parameters
    ----------
    slope : 2-D float array — slope in degrees (output of :func:`calc_slope`).
    roughness : 2-D float array — roughness (output of :func:`calc_roughness`).
    slope_weight : float — weight for slope term (default 0.7).
    roughness_weight : float — weight for roughness term (default 0.3).

    Returns
    -------
    np.ndarray (float32) — cost surface in [0, 1].
    """
    slope64 = slope.astype(np.float64)
    rough64 = roughness.astype(np.float64)

    # Min-max normalise to [0, 1]
    s_min, s_max = slope64.min(), slope64.max()
    r_min, r_max = rough64.min(), rough64.max()

    if s_max - s_min > 1e-12:
        slope_norm = (slope64 - s_min) / (s_max - s_min)
    else:
        slope_norm = np.zeros_like(slope64)

    if r_max - r_min > 1e-12:
        rough_norm = (rough64 - r_min) / (r_max - r_min)
    else:
        rough_norm = np.zeros_like(rough64)

    cost = slope_weight * slope_norm + roughness_weight * rough_norm
    # Ensure weights sum to 1 — re-normalise just in case
    total_weight = slope_weight + roughness_weight
    if abs(total_weight - 1.0) > 1e-12:
        cost /= total_weight

    return np.clip(cost, 0.0, 1.0).astype(np.float32)
