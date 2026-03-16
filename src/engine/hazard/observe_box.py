"""Observation-box feasibility analysis.

For every cell in a DEM grid, determines whether a vehicle at a given
altitude band can observe the centre of an :class:`ObserveBox`, what
the visibility ratio is, and how much altitude change is needed to
reach the observation altitude.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .los import compute_los
from .schema import AltitudeBand, ObserveBox


def compute_observe_feasibility(
    box: ObserveBox,
    dem: NDArray[np.floating],
    transform,
    altitude_band: AltitudeBand,
) -> tuple[NDArray[np.floating], NDArray[np.floating], NDArray[np.floating]]:
    """Compute per-cell observation feasibility for *box*.

    For every cell ``(r, c)`` in the DEM the function evaluates:

    1. **feasibility_map** -- 1.0 if the cell has a visibility ratio
       at or above :pyattr:`box.required_los_ratio`, else 0.0.
    2. **visibility_ratio_map** -- the fraction of LoS samples between
       the cell and the box centre that clear the terrain.
    3. **entry_cost_map** -- absolute altitude difference (metres)
       between the observation altitude and the terrain at the cell,
       representing the climb/descent effort needed.

    Parameters
    ----------
    box:
        Observation objective.
    dem:
        2-D terrain elevation array (rows x cols).
    transform:
        Rasterio affine transform mapping pixel ``(col, row)`` to map
        ``(x, y)``.
    altitude_band:
        The altitude layer at which observation is attempted.

    Returns
    -------
    ``(feasibility_map, visibility_ratio_map, entry_cost_map)`` --
    three 2-D arrays with the same shape as *dem*.
    """
    nrows, ncols = dem.shape
    feasibility_map = np.zeros((nrows, ncols), dtype=np.float64)
    visibility_ratio_map = np.zeros((nrows, ncols), dtype=np.float64)
    entry_cost_map = np.zeros((nrows, ncols), dtype=np.float64)

    target_xyz = (
        float(box.center_xyz[0]),
        float(box.center_xyz[1]),
        float(box.center_xyz[2]),
    )

    # Pre-compute map coordinates for every DEM cell to avoid repeated
    # affine multiplication inside the loop.  The rasterio convention is:
    #   x, y = transform * (col + 0.5, row + 0.5)   (pixel centre)
    cols = np.arange(ncols, dtype=np.float64) + 0.5
    rows = np.arange(nrows, dtype=np.float64) + 0.5
    col_grid, row_grid = np.meshgrid(cols, rows)

    # Affine: x = a*col + b*row + c,  y = d*col + e*row + f
    a = transform.a
    b = transform.b
    c = transform.c
    d = transform.d
    e = transform.e
    f = transform.f

    xs = a * col_grid + b * row_grid + c
    ys = d * col_grid + e * row_grid + f

    # Observation altitude for each cell: terrain + band AGL
    obs_altitude = dem + altitude_band.agl_m

    # Compute entry cost (altitude delta from terrain to obs altitude)
    entry_cost_map[:] = np.abs(obs_altitude - dem)  # == altitude_band.agl_m everywhere

    # Vectorised distance pre-filter: skip cells that are absurdly far
    # from the observe box centre (> 2x DEM diagonal) -- practically never
    # triggered but prevents wasted work on huge grids.
    dx = xs - target_xyz[0]
    dy = ys - target_xyz[1]
    dist_sq = dx * dx + dy * dy

    # Determine a sensible max range: diagonal of the DEM extent
    x_extent = abs(a) * ncols
    y_extent = abs(e) * nrows
    max_range = 2.0 * np.sqrt(x_extent ** 2 + y_extent ** 2)
    max_range_sq = max_range * max_range

    # Use a coarser step count for the per-cell LoS to keep runtime
    # manageable on large DEMs.  50 samples is sufficient for a
    # feasibility check.
    los_samples = 50

    for r in range(nrows):
        for col_idx in range(ncols):
            if dist_sq[r, col_idx] > max_range_sq:
                continue

            source_xyz = (
                xs[r, col_idx],
                ys[r, col_idx],
                obs_altitude[r, col_idx],
            )

            los_result = compute_los(
                source_xyz=source_xyz,
                target_xyz=target_xyz,
                dem=dem,
                transform=transform,
                clearance=0.0,  # feasibility check uses zero extra clearance
                n_samples=los_samples,
            )

            vis_ratio = los_result["visible_ratio"]
            visibility_ratio_map[r, col_idx] = vis_ratio
            if vis_ratio >= box.required_los_ratio:
                feasibility_map[r, col_idx] = 1.0

    return feasibility_map, visibility_ratio_map, entry_cost_map
