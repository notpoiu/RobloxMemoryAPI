"""Compatibility wrapper for the native memory backend."""

from __future__ import annotations

import platform

_SUPPORTED_PLATFORMS = {"Windows", "Darwin"}

if platform.system() not in _SUPPORTED_PLATFORMS:
    raise RuntimeError("The memory backend is only compatible with Windows and macOS.")

try:
    from robloxmemoryapi._native.memory import (  # noqa: F401
        EvasiveProcess,
        MEM_COMMIT,
        MEM_RESERVE,
        PAGE_EXECUTE_READWRITE,
        PAGE_READWRITE,
        PROCESS_QUERY_INFORMATION,
        PROCESS_VM_OPERATION,
        PROCESS_VM_READ,
        PROCESS_VM_WRITE,
        get_pid_by_name,
    )
except ImportError as exc:  # pragma: no cover - exercised by packaging failures.
    raise ImportError(
        "Failed to import robloxmemoryapi native memory backend. "
        "Install a platform wheel or build the package from source with a C++ compiler and CMake."
    ) from exc

__all__ = [
    "EvasiveProcess",
    "PROCESS_QUERY_INFORMATION",
    "PROCESS_VM_READ",
    "PROCESS_VM_WRITE",
    "PROCESS_VM_OPERATION",
    "MEM_COMMIT",
    "MEM_RESERVE",
    "PAGE_READWRITE",
    "PAGE_EXECUTE_READWRITE",
    "get_pid_by_name",
]
