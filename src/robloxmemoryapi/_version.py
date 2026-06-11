from __future__ import annotations

from importlib import metadata
from pathlib import Path
import re

_DISTRIBUTION_NAME = "robloxmemoryapi"


def _read_source_version() -> str | None:
    for parent in Path(__file__).resolve().parents:
        pyproject_path = parent / "pyproject.toml"
        if not pyproject_path.is_file():
            continue

        in_project_section = False
        for line in pyproject_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "[project]":
                in_project_section = True
                continue
            if in_project_section and stripped.startswith("["):
                break
            if in_project_section:
                match = re.match(r'version\s*=\s*["\']([^"\']+)["\']', stripped)
                if match:
                    return match.group(1)

    return None


def _read_installed_version() -> str | None:
    try:
        return metadata.version(_DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return None


def _resolve_version() -> str:
    return _read_source_version() or _read_installed_version() or "0+unknown"


__version__ = _resolve_version()
USER_AGENT = f"RobloxMemoryAPI/{__version__}"
