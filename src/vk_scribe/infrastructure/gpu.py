"""
File:   gpu.py
Brief:  CUDA runtime detection and NVIDIA pip-wheel DLL registration.
Author: Mistress-Lukutar
Date:   2026-09-12
Version: v1.4.1
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_REGISTERED = False  # DLL search registration is process-wide; do it once

# cuBLAS ships for CUDA 12 only (the *64_12 / so.12 naming); cuDNN is
# probed across the major versions ctranslate2 may link against.
_CUBLAS_CANDIDATES = ("cublas64_12.dll", "libcublas.so.12")
_CUDNN_CANDIDATES = (
    "cudnn64_9.dll",
    "libcudnn.so.9",
    "cudnn64_8.dll",
    "libcudnn.so.8",
)


def _register_nvidia_dll_dirs() -> None:
    """Add nvidia pip-wheel ``bin`` folders to the DLL search paths.

    The ``nvidia-cublas-cu12`` / ``nvidia-cudnn-cu12`` wheels drop their
    DLLs into ``site-packages/nvidia/*/bin``, which the system loader
    does not search. Registering them lets both the ctypes probe below
    and ctranslate2 itself find ``cublas64_12`` and friends.
    """
    global _REGISTERED
    if _REGISTERED or sys.platform != "win32":
        return
    try:
        import importlib.util

        spec = importlib.util.find_spec("nvidia")
    except (ImportError, ValueError):
        return
    locations = getattr(spec, "submodule_search_locations", None) or []
    for base in locations:
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            logger.debug("Registered CUDA DLL directory: %s", bin_dir)
    _REGISTERED = True


def _can_load(names: tuple[str, ...]) -> bool:
    """Try loading the first available library from a name list.

    Args:
        names: Candidate library file names (Windows and Linux forms).

    Returns:
        True when one of the candidates loads successfully.
    """
    for name in names:
        try:
            ctypes.CDLL(name)
            return True
        except OSError:
            continue
    return False


def cuda_runtime_available() -> bool:
    """Check whether the CUDA math libraries ctranslate2 needs load.

    Registers the nvidia pip-wheel DLL folders first (Windows), then
    probes cuBLAS and cuDNN by actually loading them — the same way
    ctranslate2 will. Never raises; a missing or broken setup simply
    answers False so Whisper can fall back to CPU.

    Returns:
        True when both cuBLAS and cuDNN are loadable.
    """
    _register_nvidia_dll_dirs()
    if not _can_load(_CUBLAS_CANDIDATES):
        return False
    return _can_load(_CUDNN_CANDIDATES)
