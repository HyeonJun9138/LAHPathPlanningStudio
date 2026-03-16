"""Publication-quality preview image generation for terrain arrays.

Generates PNG visualisations (colour-mapped rasters and histograms) of 2-D
numpy arrays using matplotlib.  Used by the preprocessing pipeline to create
quick-look artefacts that are served via the backend API and displayed in the
frontend map viewer.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend -- must be set before pyplot import

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


def generate_preview_png(
    array: np.ndarray,
    output_path: str,
    cmap: str = "terrain",
    title: str = "",
    vmin: float | None = None,
    vmax: float | None = None,
    dpi: int = 150,
) -> str:
    """Render a 2-D array as a publication-quality colour-mapped PNG.

    Parameters
    ----------
    array : np.ndarray
        2-D array (rows, cols) to visualise.
    output_path : str
        Destination file path (parent directories are created automatically).
    cmap : str
        Matplotlib colourmap name (default: ``"terrain"``).
    title : str
        Optional title rendered above the image.
    vmin, vmax : float | None
        Colour-scale limits.  When *None* they are derived from the data
        (ignoring NaNs).
    dpi : int
        Resolution of the saved image (default 150).

    Returns
    -------
    str
        The absolute path of the written PNG file.
    """
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Mask NaN / Inf for robust colour scaling
    finite_mask = np.isfinite(array)
    if finite_mask.any():
        data_min = float(np.nanmin(array[finite_mask]))
        data_max = float(np.nanmax(array[finite_mask]))
    else:
        data_min, data_max = 0.0, 1.0

    if vmin is None:
        vmin = data_min
    if vmax is None:
        vmax = data_max

    # Figure sizing: keep reasonable aspect ratio, cap at 12 inches wide
    h, w = array.shape
    aspect = h / max(w, 1)
    fig_width = min(12.0, max(6.0, w / dpi * 2))
    fig_height = fig_width * aspect
    fig_height = max(fig_height, 3.0)

    fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height), dpi=dpi)

    im = ax.imshow(
        array,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        origin="upper",
        interpolation="nearest",
        aspect="equal",
    )

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8)

    if title:
        ax.set_title(title, fontsize=11, fontweight="bold", pad=8)

    ax.set_xlabel("Column (px)", fontsize=8)
    ax.set_ylabel("Row (px)", fontsize=8)
    ax.tick_params(labelsize=7)

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return str(Path(output_path).resolve())


def generate_histogram_png(
    array: np.ndarray,
    output_path: str,
    title: str = "",
    bins: int = 100,
    dpi: int = 150,
) -> str:
    """Plot a histogram of pixel values and save as PNG.

    Parameters
    ----------
    array : np.ndarray
        2-D (or flattened) array whose value distribution is plotted.
    output_path : str
        Destination file path.
    title : str
        Optional title above the histogram.
    bins : int
        Number of histogram bins (default 100).
    dpi : int
        Image resolution.

    Returns
    -------
    str
        The absolute path of the written PNG file.
    """
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Flatten and drop non-finite values
    values = array.ravel()
    values = values[np.isfinite(values)]

    fig, ax = plt.subplots(1, 1, figsize=(8, 4), dpi=dpi)

    if values.size > 0:
        ax.hist(values, bins=bins, color="#3578b2", edgecolor="none", alpha=0.85)
        # Annotate with basic statistics
        mean_val = float(np.mean(values))
        std_val = float(np.std(values))
        min_val = float(np.min(values))
        max_val = float(np.max(values))

        stats_text = (
            f"min={min_val:.2f}  max={max_val:.2f}\n"
            f"mean={mean_val:.2f}  std={std_val:.2f}\n"
            f"N={values.size:,}"
        )
        ax.text(
            0.98, 0.95,
            stats_text,
            transform=ax.transAxes,
            fontsize=7,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )
    else:
        ax.text(
            0.5, 0.5,
            "No finite values",
            transform=ax.transAxes,
            ha="center", va="center",
            fontsize=12, color="gray",
        )

    if title:
        ax.set_title(title, fontsize=11, fontweight="bold", pad=8)

    ax.set_xlabel("Value", fontsize=9)
    ax.set_ylabel("Frequency", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return str(Path(output_path).resolve())
