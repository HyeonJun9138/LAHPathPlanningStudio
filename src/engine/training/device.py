"""CUDA device detection and selection utilities.

Provides helpers that the Training Center tab and :class:`TrainRunner`
use to discover available GPUs, query memory/driver info, and resolve
the user's device preference into a concrete :class:`torch.device`.
"""

from __future__ import annotations

import torch


def detect_cuda() -> dict:
    """Detect CUDA availability and return a device inventory.

    Returns
    -------
    dict
        Keys:
        - ``available`` (*bool*) -- whether CUDA is usable.
        - ``devices`` (*list[dict]*) -- per-GPU info dicts with
          ``name``, ``index``, ``total_memory_mb``, ``torch_name``.
        - ``torch_version`` (*str*) -- PyTorch version string.
        - ``cuda_version`` (*str | None*) -- CUDA toolkit version
          reported by PyTorch, or *None* when CUDA is unavailable.
    """
    available = torch.cuda.is_available()
    devices: list[dict] = []
    if available:
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            total_memory = getattr(props, "total_memory", getattr(props, "total_mem", 0))
            devices.append(
                {
                    "name": props.name,
                    "index": i,
                    "total_memory_mb": total_memory // (1024 * 1024),
                    "torch_name": f"cuda:{i}",
                }
            )
    return {
        "available": available,
        "devices": devices,
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda if available else None,
    }


def select_device(preference: str = "auto") -> torch.device:
    """Resolve a user preference string into a :class:`torch.device`.

    Parameters
    ----------
    preference:
        One of:
        - ``"auto"`` -- use the first CUDA GPU when available, else CPU.
        - ``"cpu"`` -- force CPU.
        - ``"cuda:0"``, ``"cuda:1"``, ... -- request a specific GPU.
          Falls back to CPU if that GPU is not available.

    Returns
    -------
    torch.device
    """
    if preference == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    if preference.startswith("cuda"):
        if torch.cuda.is_available():
            # Validate the index is within range
            try:
                idx = int(preference.split(":")[1]) if ":" in preference else 0
                if idx < torch.cuda.device_count():
                    return torch.device(preference)
                # Requested index out of range -- fall back to cuda:0
                return torch.device("cuda:0")
            except (ValueError, IndexError):
                return torch.device("cuda:0")
        return torch.device("cpu")
    return torch.device("cpu")
