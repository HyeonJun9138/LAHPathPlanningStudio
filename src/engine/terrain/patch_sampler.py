"""Patch extraction from multi-channel terrain data.

Provides a PatchSampler that extracts fixed-size image patches centred on
world coordinates from a dict of named terrain channels (elevation, slope,
aspect, roughness, etc.).  Boundary pixels are handled with reflection
padding so every returned patch has the exact requested shape regardless of
proximity to the raster edge.
"""

from __future__ import annotations

import numpy as np
from rasterio.transform import Affine


class PatchSampler:
    """Extract fixed-size patches from multi-channel terrain data.

    Parameters
    ----------
    terrain_data : dict[str, np.ndarray]
        Mapping from channel name (e.g. ``"elevation"``, ``"slope"``) to a
        2-D ``float32`` numpy array.  All arrays must share the same spatial
        dimensions (height, width).
    terrain_metadata : dict
        Must contain at least:
        - ``transform`` : rasterio ``Affine`` (or a 6-element sequence that
          can be unpacked into one) mapping pixel (col, row) to world coords.
        - ``resolution`` : ``(res_x, res_y)`` in CRS units.
        - ``bounds`` : rasterio-style bounds or dict with left/bottom/right/top.
        - ``crs`` : coordinate reference system (kept for provenance only).
        - ``width``, ``height`` : raster dimensions in pixels.
    """

    def __init__(self, terrain_data: dict, terrain_metadata: dict) -> None:
        self.terrain_data = terrain_data
        self.metadata = terrain_metadata

        # Build an Affine if we received a plain list / tuple
        tf = terrain_metadata["transform"]
        if isinstance(tf, Affine):
            self.transform = tf
        else:
            self.transform = Affine(*tf[:6])

        self.resolution = terrain_metadata["resolution"]
        self.width: int = int(terrain_metadata["width"])
        self.height: int = int(terrain_metadata["height"])

        # Sorted channel names give a deterministic stacking order
        self.channel_names: list[str] = sorted(terrain_data.keys())
        self.num_channels: int = len(self.channel_names)

        # Pre-validate that every channel matches the declared dimensions
        for name in self.channel_names:
            arr = self.terrain_data[name]
            if arr.shape != (self.height, self.width):
                raise ValueError(
                    f"Channel '{name}' has shape {arr.shape} but metadata "
                    f"declares (height={self.height}, width={self.width})."
                )

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def _world_to_pixel(self, x: float, y: float) -> tuple[int, int]:
        """Convert world (CRS) coordinates to pixel (row, col).

        Uses the inverse of the affine transform.  The returned indices are
        rounded to the nearest integer pixel centre.

        Parameters
        ----------
        x : float
            Easting / longitude in the terrain CRS.
        y : float
            Northing / latitude in the terrain CRS.

        Returns
        -------
        (row, col) : tuple[int, int]
        """
        inv = ~self.transform  # inverse affine
        col_f, row_f = inv * (x, y)
        row = int(round(row_f))
        col = int(round(col_f))
        return row, col

    # ------------------------------------------------------------------
    # Reflection-padded extraction
    # ------------------------------------------------------------------

    def _extract_and_pad(
        self, array: np.ndarray, row: int, col: int, size: int
    ) -> np.ndarray:
        """Extract a ``size x size`` patch centred on ``(row, col)``.

        If the patch extends beyond the array boundary, reflection padding
        (``numpy.pad`` mode ``"reflect"``) is used so the output always has
        shape ``(size, size)``.

        Parameters
        ----------
        array : np.ndarray
            2-D source array of shape ``(H, W)``.
        row, col : int
            Centre pixel of the patch.
        size : int
            Side length of the square patch.

        Returns
        -------
        np.ndarray of shape ``(size, size)``
        """
        h, w = array.shape
        half = size // 2

        # Desired slice in source coordinates (may be negative / > shape)
        r_start = row - half
        r_end = r_start + size
        c_start = col - half
        c_end = c_start + size

        # Compute how much padding is needed on each side
        pad_top = max(0, -r_start)
        pad_bottom = max(0, r_end - h)
        pad_left = max(0, -c_start)
        pad_right = max(0, c_end - w)

        # Clamp slice indices to valid range
        r_start_clamped = max(0, r_start)
        r_end_clamped = min(h, r_end)
        c_start_clamped = max(0, c_start)
        c_end_clamped = min(w, c_end)

        patch = array[r_start_clamped:r_end_clamped, c_start_clamped:c_end_clamped]

        if pad_top or pad_bottom or pad_left or pad_right:
            patch = np.pad(
                patch,
                ((pad_top, pad_bottom), (pad_left, pad_right)),
                mode="reflect",
            )

        # Guard against rounding edge-cases: ensure exact output size
        if patch.shape != (size, size):
            patch = patch[:size, :size]

        return patch

    # ------------------------------------------------------------------
    # Public extraction methods
    # ------------------------------------------------------------------

    def extract_patch(
        self,
        x_world: float,
        y_world: float,
        size: int,
        resolution_level: int = 1,
    ) -> np.ndarray:
        """Extract a multi-channel patch centred on a world coordinate.

        Parameters
        ----------
        x_world, y_world : float
            Position in the terrain CRS.
        size : int
            Side length of the square patch **at the native resolution**.
        resolution_level : int
            Down-sampling factor applied *after* extraction.  ``1`` means
            native resolution; ``2`` means every-other pixel, etc.  The
            extraction window is scaled up by this factor so that the
            *returned* patch still has ``size x size`` pixels.

        Returns
        -------
        np.ndarray of shape ``(C, size, size)`` and dtype ``float32``, where
        ``C`` is the number of terrain channels.
        """
        row, col = self._world_to_pixel(x_world, y_world)

        # When resolution_level > 1 we extract a larger window and then
        # sub-sample to keep the output at the requested *size*.
        extract_size = size * resolution_level

        channels: list[np.ndarray] = []
        for name in self.channel_names:
            raw = self._extract_and_pad(self.terrain_data[name], row, col, extract_size)
            if resolution_level > 1:
                raw = raw[::resolution_level, ::resolution_level]
            # Ensure exactly (size, size) after subsampling
            raw = raw[:size, :size]
            channels.append(raw.astype(np.float32))

        return np.stack(channels, axis=0)

    def extract_local_hi(
        self, x: float, y: float, size: int = 128
    ) -> np.ndarray:
        """High-resolution patch: all channels at native resolution.

        Parameters
        ----------
        x, y : float
            World coordinates (CRS).
        size : int
            Spatial extent in pixels (default 128).

        Returns
        -------
        np.ndarray of shape ``(C, 128, 128)`` and dtype ``float32``.
        """
        return self.extract_patch(x, y, size, resolution_level=1)

    def extract_local_mid(
        self, x: float, y: float, size: int = 64
    ) -> np.ndarray:
        """Mid-resolution patch: coarser view covering a larger ground area.

        The extraction window is 2x the native resolution so that the returned
        ``(C, 64, 64)`` tensor covers the same ground area as a ``128 x 128``
        native patch.

        Parameters
        ----------
        x, y : float
            World coordinates (CRS).
        size : int
            Output spatial extent in pixels (default 64).

        Returns
        -------
        np.ndarray of shape ``(C, 64, 64)`` and dtype ``float32``.
        """
        return self.extract_patch(x, y, size, resolution_level=2)
