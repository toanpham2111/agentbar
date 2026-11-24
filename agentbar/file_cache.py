"""Small file-cache helpers that avoid unnecessary disk writes."""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path


def copy_file_if_changed(source: Path, target: Path) -> bool:
    """Copy a file only when the destination bytes differ."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if (
        target.is_file()
        and source.stat().st_size == target.stat().st_size
        and filecmp.cmp(source, target, shallow=False)
    ):
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True
