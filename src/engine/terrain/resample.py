"""Resampling utilities for terrain arrays.

Provides resolution-aware resampling of 2-D numpy arrays using
``scipy.ndimage.zoom`` so that downstream consumers always work at a
consistent, user-chosen cell size.
"""
import numpy as np
from scipy.ndimage import zoom
from rasterio.transform import Affine


def resample_array(
    data: np.ndarray,
    src_resolution: tuple[float, float],
    target_resolution: float,
    order: int = 1,
    src_transform: Affine | None = None,
) -> dict:
    """Resample a 2-D array to *target_resolution* using spline interpolation.

    Parameters
    ----------
    data : np.ndarray
        2-D elevation / raster array (rows, cols).
    src_resolution : tuple[float, float]
        Current (x, y) pixel size in the same linear unit as the CRS
        (usually metres after UTM reprojection).
    target_resolution : float
        Desired output cell size in the same unit.  A value larger than
        ``src_resolution`` down-samples; a smaller value up-samples.
    order : int
        Spline interpolation order passed to ``scipy.ndimage.zoom``.
        0 = nearest-neighbour, 1 = bilinear (default), 3 = cubic.
    src_transform : Affine | None
        Optional source geo-transform.  When provided the returned dict
        includes an updated ``transform`` with the new cell size.

    Returns
    -------
    dict with keys:
        data            – resampled float32 array
        resolution      – (target_resolution, target_resolution)
        width           – new number of columns
        height          – new number of rows
        zoom_factors    – (row_factor, col_factor) actually applied
        transform       – updated Affine (only when *src_transform* given)
    """
    src_res_x, src_res_y = float(src_resolution[0]), float(src_resolution[1])
    target_res = float(target_resolution)

    # Zoom factors: > 1 up-samples, < 1 down-samples
    zoom_y = src_res_y / target_res
    zoom_x = src_res_x / target_res

    resampled = zoom(
        data.astype(np.float32),
        (zoom_y, zoom_x),
        order=order,
        mode="nearest",
    )

    result: dict = {
        "data": resampled,
        "resolution": (target_res, target_res),
        "width": resampled.shape[1],
        "height": resampled.shape[0],
        "zoom_factors": (zoom_y, zoom_x),
    }

    if src_transform is not None:
        # Preserve origin, update pixel size
        sign_a = 1.0 if src_transform.a >= 0 else -1.0
        sign_e = 1.0 if src_transform.e >= 0 else -1.0
        result["transform"] = Affine(
            sign_a * target_res,
            src_transform.b,
            src_transform.c,
            src_transform.d,
            sign_e * target_res,
            src_transform.f,
        )

    return result


def resample_to_match(
    data: np.ndarray,
    src_resolution: tuple[float, float],
    reference_shape: tuple[int, int],
    order: int = 1,
) -> np.ndarray:
    """Resample *data* so its shape matches *reference_shape*.

    Useful when two layers (e.g. DEM and a land-cover raster) must be
    pixel-aligned before element-wise operations.

    Parameters
    ----------
    data : np.ndarray
        2-D source array.
    src_resolution : tuple[float, float]
        (res_x, res_y) of *data* — kept for documentation but not used
        in the zoom calculation because we derive factors from shapes.
    reference_shape : tuple[int, int]
        Target (rows, cols).
    order : int
        Spline interpolation order (default: bilinear).

    Returns
    -------
    np.ndarray
        Resampled array with shape == reference_shape.
    """
    ref_rows, ref_cols = reference_shape
    src_rows, src_cols = data.shape

    zoom_y = ref_rows / src_rows
    zoom_x = ref_cols / src_cols

    return zoom(
        data.astype(np.float32),
        (zoom_y, zoom_x),
        order=order,
        mode="nearest",
    )
