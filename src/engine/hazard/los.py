"""Line-of-Sight (LoS) computation over a DEM.

Provides :func:`compute_los` which ray-marches between two 3-D points
and checks whether the interpolated flight altitude clears the terrain
(plus a configurable clearance margin) at every sample along the ray.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def _pixel_coords(x: float, y: float, transform) -> tuple[float, float]:
    """Convert map coordinates (x, y) to fractional pixel (col, row).

    ``transform`` is an :class:`rasterio.transform.Affine` (or compatible
    6-element affine).  The inverse maps world coords to pixel coords.
    """
    inv = ~transform
    col, row = inv * (x, y)
    return float(col), float(row)


def _bilinear_sample(dem: NDArray[np.floating], col: float, row: float) -> float:
    """Sample the DEM at a fractional pixel position using bilinear interpolation.

    Out-of-bounds coordinates are clamped to the DEM edges.
    """
    nrows, ncols = dem.shape
    # Clamp to valid range
    col = max(0.0, min(col, ncols - 1.0))
    row = max(0.0, min(row, nrows - 1.0))

    c0 = int(np.floor(col))
    r0 = int(np.floor(row))
    c1 = min(c0 + 1, ncols - 1)
    r1 = min(r0 + 1, nrows - 1)

    dc = col - c0
    dr = row - r0

    val = (
        dem[r0, c0] * (1.0 - dc) * (1.0 - dr)
        + dem[r0, c1] * dc * (1.0 - dr)
        + dem[r1, c0] * (1.0 - dc) * dr
        + dem[r1, c1] * dc * dr
    )
    return float(val)


def compute_los(
    source_xyz: tuple[float, float, float] | list[float],
    target_xyz: tuple[float, float, float] | list[float],
    dem: NDArray[np.floating],
    transform,
    clearance: float = 20.0,
    n_samples: int = 200,
) -> dict[str, Any]:
    """Compute line-of-sight between *source_xyz* and *target_xyz* over *dem*.

    Parameters
    ----------
    source_xyz:
        ``(x, y, z)`` of the observer in map coordinates.  ``z`` is the
        absolute altitude (metres above the vertical datum of the DEM).
    target_xyz:
        ``(x, y, z)`` of the target.
    dem:
        2-D elevation array (rows x cols).
    transform:
        Rasterio-style affine transform mapping pixel (col, row) to
        map (x, y).
    clearance:
        Minimum vertical distance (metres) that must separate the
        interpolated flight path from the terrain for the point to be
        considered *clear*.
    n_samples:
        Number of evenly-spaced sample points along the ray (including
        the endpoints).

    Returns
    -------
    dict with keys:
        visible : bool
            ``True`` when every sample point clears terrain + clearance.
        blocked_point : tuple[float, float, float] | None
            ``(x, y, z)`` of the first point where the ray is blocked, or
            ``None`` when fully visible.
        visible_ratio : float
            Fraction of sample points that are unblocked (``0.0 .. 1.0``).
        profile : list[dict]
            Per-sample detail with keys ``t``, ``x``, ``y``,
            ``terrain_z``, ``flight_z``, ``clearance``.
    """
    sx, sy, sz = float(source_xyz[0]), float(source_xyz[1]), float(source_xyz[2])
    tx, ty, tz = float(target_xyz[0]), float(target_xyz[1]), float(target_xyz[2])

    ts = np.linspace(0.0, 1.0, n_samples)

    profile: list[dict[str, float]] = []
    blocked_point: tuple[float, float, float] | None = None
    n_visible = 0

    for t in ts:
        px = sx + t * (tx - sx)
        py = sy + t * (ty - sy)
        pz = sz + t * (tz - sz)

        col, row = _pixel_coords(px, py, transform)
        terrain_z = _bilinear_sample(dem, col, row)
        point_clearance = pz - terrain_z

        is_clear = point_clearance >= clearance
        if is_clear:
            n_visible += 1
        elif blocked_point is None:
            blocked_point = (px, py, pz)

        profile.append(
            {
                "t": float(t),
                "x": px,
                "y": py,
                "terrain_z": terrain_z,
                "flight_z": pz,
                "clearance": point_clearance,
            }
        )

    visible_ratio = n_visible / max(n_samples, 1)
    visible = blocked_point is None  # True only when ALL samples clear

    return {
        "visible": visible,
        "blocked_point": blocked_point,
        "visible_ratio": visible_ratio,
        "profile": profile,
    }
