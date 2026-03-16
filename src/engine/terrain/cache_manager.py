"""Disk-based caching for terrain arrays and metadata.

Stores numpy arrays as ``.npy`` files and metadata dicts as ``.json`` files
inside a flat cache directory, keyed by a hash that encodes the source
terrain identity and processing configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np


class TerrainCache:
    """Simple file-system cache for terrain processing artefacts.

    Parameters
    ----------
    cache_dir : str
        Root directory for cached files.  Created automatically if it does
        not already exist.
    """

    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Key computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_key(name: str, config_hash: str) -> str:
        """Derive a deterministic cache key from a logical name and config hash.

        The returned string is safe for use as a filename component.

        Parameters
        ----------
        name : str
            Human-readable logical name (e.g. ``"slope"``).
        config_hash : str
            A hash (or any short identifier) that captures the processing
            parameters that produced the artefact.

        Returns
        -------
        str
            SHA-256 hex digest of ``name + ":" + config_hash``, truncated to
            32 characters, prefixed with the sanitised *name* for debuggability.
        """
        raw = f"{name}:{config_hash}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name)
        return f"{safe_name}_{digest}"

    # ------------------------------------------------------------------
    # Array persistence
    # ------------------------------------------------------------------

    def _array_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.npy"

    def save_array(self, key: str, array: np.ndarray) -> None:
        """Persist a numpy array to disk under *key*.

        Parameters
        ----------
        key : str
            Cache key (as returned by :meth:`_compute_key`).
        array : np.ndarray
            Array to save.
        """
        np.save(str(self._array_path(key)), array)

    def load_array(self, key: str) -> np.ndarray:
        """Load a previously cached numpy array.

        Parameters
        ----------
        key : str
            Cache key.

        Returns
        -------
        np.ndarray

        Raises
        ------
        FileNotFoundError
            If *key* has not been cached.
        """
        path = self._array_path(key)
        if not path.exists():
            raise FileNotFoundError(f"No cached array for key '{key}' at {path}")
        return np.load(str(path))

    def has_cache(self, key: str) -> bool:
        """Check whether an array or metadata file exists for *key*.

        Returns ``True`` if **either** the ``.npy`` or ``.json`` artefact
        exists on disk.
        """
        return self._array_path(key).exists() or self._meta_path(key).exists()

    # ------------------------------------------------------------------
    # Metadata persistence
    # ------------------------------------------------------------------

    def _meta_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def save_metadata(self, key: str, metadata: dict) -> None:
        """Persist a JSON-serialisable metadata dict under *key*.

        Parameters
        ----------
        key : str
            Cache key.
        metadata : dict
            Must be JSON-serialisable.
        """
        path = self._meta_path(key)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2, default=str)

    def load_metadata(self, key: str) -> dict:
        """Load a previously cached metadata dict.

        Raises
        ------
        FileNotFoundError
            If *key* has not been cached.
        """
        path = self._meta_path(key)
        if not path.exists():
            raise FileNotFoundError(f"No cached metadata for key '{key}' at {path}")
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Delete **all** files inside the cache directory.

        The directory itself is preserved.
        """
        for child in self.cache_dir.iterdir():
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)

    def get_cache_size(self) -> int:
        """Return total size of cached files in bytes.

        Only regular files directly inside the cache directory are counted
        (no recursive sub-directory traversal).
        """
        total = 0
        for child in self.cache_dir.iterdir():
            if child.is_file():
                total += child.stat().st_size
        return total
