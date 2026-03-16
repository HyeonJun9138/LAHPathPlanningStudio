"""System info and CUDA detection endpoints."""

from __future__ import annotations

import os
import platform
import socket

from fastapi import APIRouter

from ..models.schemas import CudaDevice, CudaInfo, SystemInfo

router = APIRouter(prefix="/api/system", tags=["system"])


def _get_package_versions() -> dict[str, str]:
    """Collect versions of key packages."""
    pkgs: dict[str, str] = {}
    for name in [
        "fastapi", "uvicorn", "pydantic", "numpy", "torch",
        "rasterio", "gymnasium", "stable_baselines3",
    ]:
        try:
            mod = __import__(name)
            pkgs[name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            pkgs[name] = "not installed"
    return pkgs


@router.get("/info", response_model=SystemInfo)
async def system_info() -> SystemInfo:
    return SystemInfo(
        python_version=platform.python_version(),
        os_name=os.name,
        hostname=socket.gethostname(),
        platform=platform.platform(),
        packages=_get_package_versions(),
    )


@router.get("/cuda", response_model=CudaInfo)
async def cuda_info() -> CudaInfo:
    try:
        import torch
    except ImportError:
        return CudaInfo(available=False, torch_version="not installed")

    if not torch.cuda.is_available():
        return CudaInfo(
            available=False,
            torch_version=torch.__version__,
            cuda_version=getattr(torch.version, "cuda", "") or "",
        )

    devices: list[CudaDevice] = []
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        total_memory = getattr(props, "total_memory", getattr(props, "total_mem", 0))
        total_mb = total_memory / (1024 * 1024)
        try:
            free_mb = torch.cuda.mem_get_info(i)[0] / (1024 * 1024)
        except Exception:
            free_mb = 0.0
        devices.append(
            CudaDevice(
                name=props.name,
                index=i,
                total_memory_mb=round(total_mb, 1),
                free_memory_mb=round(free_mb, 1),
                torch_name=f"cuda:{i}",
            )
        )

    return CudaInfo(
        available=True,
        selected_default="cuda:0",
        devices=devices,
        torch_version=torch.__version__,
        cuda_version=getattr(torch.version, "cuda", "") or "",
        cudnn_available=torch.backends.cudnn.is_available(),
    )
