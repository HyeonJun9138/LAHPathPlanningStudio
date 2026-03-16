"""GeoTIFF loading module using rasterio."""
import rasterio
import numpy as np
from pathlib import Path


def load_geotiff(path: str) -> dict:
    """Load GeoTIFF file and return data array + metadata.

    Reads the first band of a GeoTIFF into a float32 numpy array. If the file
    declares a nodata value, those pixels are replaced with the mean of the
    valid pixels so downstream consumers always receive a gap-free surface.

    Returns dict with keys:
        data, crs, bounds, resolution, nodata, width, height,
        transform, dtype, band_count
    """
    path = Path(path)
    with rasterio.open(str(path)) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata

        # Fill nodata pixels with the mean of valid pixels
        if nodata is not None:
            mask = data == nodata
            if mask.any():
                valid = data[~mask]
                if valid.size > 0:
                    data[mask] = np.nanmean(valid)

        res_x = abs(src.transform.a)
        res_y = abs(src.transform.e)

        return {
            "data": data,
            "crs": src.crs,
            "bounds": src.bounds,
            "resolution": (res_x, res_y),
            "nodata": nodata,
            "width": src.width,
            "height": src.height,
            "transform": src.transform,
            "dtype": str(data.dtype),
            "band_count": src.count,
        }


def get_terrain_metadata(path: str) -> dict:
    """Quick metadata extraction without loading the full raster array.

    Useful for pre-flight checks, UI display, and deciding whether
    reprojection or resampling is needed before heavy processing.
    """
    path = Path(path)
    with rasterio.open(str(path)) as src:
        res_x = abs(src.transform.a)
        res_y = abs(src.transform.e)

        return {
            "crs": str(src.crs),
            "bounds": {
                "left": src.bounds.left,
                "bottom": src.bounds.bottom,
                "right": src.bounds.right,
                "top": src.bounds.top,
            },
            "resolution": (res_x, res_y),
            "nodata": src.nodata,
            "width": src.width,
            "height": src.height,
            "transform": list(src.transform)[:6],
            "dtype": str(src.dtypes[0]),
            "band_count": src.count,
        }
