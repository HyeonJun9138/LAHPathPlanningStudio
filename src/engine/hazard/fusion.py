"""Risk-layer fusion strategies.

Combines multiple per-source 2-D risk arrays into a single composite
risk surface.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def fuse_risks(
    risk_layers: list[NDArray[np.floating]],
    mode: str = "probabilistic_union",
) -> NDArray[np.floating]:
    """Fuse a list of 2-D risk arrays into a single composite array.

    Parameters
    ----------
    risk_layers:
        List of 2-D ``float`` arrays, each with values in ``[0, 1]``
        and identical shape.
    mode:
        Fusion strategy.

        * ``"probabilistic_union"`` -- treats each layer as an
          independent detection probability and returns
          ``1 - prod(1 - r_i)``.
        * ``"sum_clip"`` -- element-wise sum, clipped to ``[0, 1]``.
        * ``"max"`` -- element-wise maximum across layers.

    Returns
    -------
    2-D ``float64`` array of the same shape as the input layers, with
    values in ``[0, 1]``.

    Raises
    ------
    ValueError
        If *risk_layers* is empty or shapes are inconsistent.
    """
    if not risk_layers:
        raise ValueError("risk_layers must contain at least one array")

    shape = risk_layers[0].shape
    for i, layer in enumerate(risk_layers):
        if layer.shape != shape:
            raise ValueError(
                f"Shape mismatch: layer 0 has shape {shape}, "
                f"but layer {i} has shape {layer.shape}"
            )

    if mode == "probabilistic_union":
        # P(at least one) = 1 - prod(1 - p_i)
        survival = np.ones(shape, dtype=np.float64)
        for layer in risk_layers:
            survival *= (1.0 - np.clip(layer, 0.0, 1.0))
        result = 1.0 - survival

    elif mode == "sum_clip":
        result = np.zeros(shape, dtype=np.float64)
        for layer in risk_layers:
            result += layer
        result = np.clip(result, 0.0, 1.0)

    elif mode == "max":
        result = np.zeros(shape, dtype=np.float64)
        for layer in risk_layers:
            result = np.maximum(result, layer)

    else:
        raise ValueError(
            f"Unknown fusion mode '{mode}'. "
            f"Expected one of: probabilistic_union, sum_clip, max"
        )

    return result.astype(np.float64)
