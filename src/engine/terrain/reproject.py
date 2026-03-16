"""Reprojection utilities for terrain data.

Provides UTM auto-detection and reprojection of in-memory raster arrays
using rasterio's warp engine so that all downstream terrain analysis
operates in metres.
"""
import math
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine
from rasterio.warp import calculate_default_transform, reproject, Resampling


def _utm_zone_from_lon(longitude: float) -> int:
    """Return the UTM zone number (1-60) for a given longitude."""
    return int((longitude + 180) / 6) + 1


def _utm_epsg(longitude: float, latitude: float) -> int:
    """Derive the EPSG code of the appropriate UTM zone.

    Northern hemisphere zones use EPSG 326xx, southern hemisphere 327xx,
    where xx is the two-digit zone number.
    """
    zone = _utm_zone_from_lon(longitude)
    if latitude >= 0:
        return 32600 + zone
    return 32700 + zone


def reproject_to_utm(
    data: np.ndarray,
    src_crs: CRS,
    src_transform: Affine,
    src_nodata: float | None = None,
    target_resolution: float | None = None,
    resampling: Resampling = Resampling.bilinear,
) -> dict:
    """Reproject a 2-D elevation array to the appropriate UTM zone.

    Parameters
    ----------
    data : np.ndarray
        2-D array (rows, cols) of elevation values.
    src_crs : rasterio.crs.CRS
        Coordinate reference system of *data*.
    src_transform : Affine
        Affine geo-transform that maps pixel coords -> CRS coords.
    src_nodata : float | None
        Value that represents missing data in *data*.
    target_resolution : float | None
        Desired output cell size in metres.  When *None* the resolution
        produced by ``calculate_default_transform`` is used (usually close
        to the native resolution).
    resampling : Resampling
        Resampling algorithm (default: bilinear).

    Returns
    -------
    dict with keys:
        data, crs, transform, resolution, width, height, nodata
    """
    height, width = data.shape

    # Compute the centre of the raster in its native CRS so we can
    # choose the right UTM zone.  rasterio bounds are (left, bottom,
    # right, top).
    left = src_transform.c
    top = src_transform.f
    right = left + src_transform.a * width
    bottom = top + src_transform.e * height

    # If the source CRS is already geographic (lon/lat) the bounds are
    # directly usable; otherwise we transform the centre point.
    if src_crs.is_geographic:
        centre_lon = (left + right) / 2.0
        centre_lat = (bottom + top) / 2.0
    else:
        from rasterio.warp import transform as warp_transform

        xs = [(left + right) / 2.0]
        ys = [(bottom + top) / 2.0]
        lons, lats = warp_transform(src_crs, CRS.from_epsg(4326), xs, ys)
        centre_lon = lons[0]
        centre_lat = lats[0]

    dst_epsg = _utm_epsg(centre_lon, centre_lat)
    dst_crs = CRS.from_epsg(dst_epsg)

    # Calculate the ideal output transform / dimensions.
    if target_resolution is not None:
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            dst_crs,
            width,
            height,
            left=left,
            bottom=bottom,
            right=right,
            top=top,
            resolution=target_resolution,
        )
    else:
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            dst_crs,
            width,
            height,
            left=left,
            bottom=bottom,
            right=right,
            top=top,
        )

    dst_data = np.empty((dst_height, dst_width), dtype=np.float32)

    dst_nodata = src_nodata if src_nodata is not None else -9999.0

    reproject(
        source=data.astype(np.float32),
        destination=dst_data,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        src_nodata=src_nodata,
        dst_nodata=dst_nodata,
        resampling=resampling,
    )

    res_x = abs(dst_transform.a)
    res_y = abs(dst_transform.e)

    return {
        "data": dst_data,
        "crs": dst_crs,
        "transform": dst_transform,
        "resolution": (res_x, res_y),
        "width": dst_width,
        "height": dst_height,
        "nodata": dst_nodata,
    }


def reproject_array(
    data: np.ndarray,
    src_crs: CRS,
    src_transform: Affine,
    dst_crs: CRS,
    src_nodata: float | None = None,
    target_resolution: float | None = None,
    resampling: Resampling = Resampling.bilinear,
) -> dict:
    """Reproject a 2-D array to an arbitrary target CRS.

    This is the general-purpose variant of :func:`reproject_to_utm` —
    callers supply the destination CRS explicitly.

    Returns the same dict shape as :func:`reproject_to_utm`.
    """
    height, width = data.shape

    left = src_transform.c
    top = src_transform.f
    right = left + src_transform.a * width
    bottom = top + src_transform.e * height

    if target_resolution is not None:
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            dst_crs,
            width,
            height,
            left=left,
            bottom=bottom,
            right=right,
            top=top,
            resolution=target_resolution,
        )
    else:
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            dst_crs,
            width,
            height,
            left=left,
            bottom=bottom,
            right=right,
            top=top,
        )

    dst_data = np.empty((dst_height, dst_width), dtype=np.float32)
    dst_nodata = src_nodata if src_nodata is not None else -9999.0

    reproject(
        source=data.astype(np.float32),
        destination=dst_data,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        src_nodata=src_nodata,
        dst_nodata=dst_nodata,
        resampling=resampling,
    )

    res_x = abs(dst_transform.a)
    res_y = abs(dst_transform.e)

    return {
        "data": dst_data,
        "crs": dst_crs,
        "transform": dst_transform,
        "resolution": (res_x, res_y),
        "width": dst_width,
        "height": dst_height,
        "nodata": dst_nodata,
    }
