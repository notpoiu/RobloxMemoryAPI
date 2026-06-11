from __future__ import annotations

import ctypes
import os
import platform
import subprocess


def normalize_architecture(architecture: str | None) -> str | None:
    if not architecture:
        return None

    normalized = architecture.strip().lower()
    if normalized in {"arm", "arm64", "aarch64", "apple silicon", "silicon"}:
        return "arm64"
    if normalized in {"intel", "x64", "x86_64", "amd64"}:
        return "x64"
    return None


def process_path(pid: int) -> str | None:
    if platform.system() != "Darwin" or pid <= 0:
        return None

    try:
        libc = ctypes.CDLL(None)
        proc_pidpath = libc.proc_pidpath
        proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        proc_pidpath.restype = ctypes.c_int

        buffer = ctypes.create_string_buffer(4096)
        result = proc_pidpath(pid, buffer, ctypes.sizeof(buffer))
        if result > 0:
            return os.fsdecode(buffer.value)
    except Exception:
        pass

    try:
        output = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "comm="],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return output or None
    except Exception:
        return None


def binary_architecture(path: str | os.PathLike[str] | None) -> str | None:
    if not path:
        return None

    path = os.fspath(path)
    if not os.path.exists(path):
        return None

    try:
        output = subprocess.check_output(
            ["lipo", "-archs", path],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip().lower()
        architectures = set(output.split())
        if architectures == {"arm64"}:
            return "arm64"
        if architectures <= {"x86_64", "i386"} and "x86_64" in architectures:
            return "x64"
    except Exception:
        pass

    try:
        output = subprocess.check_output(
            ["file", "-b", path],
            stderr=subprocess.DEVNULL,
            text=True,
        ).lower()
        if "arm64" in output and "x86_64" not in output:
            return "arm64"
        if "x86_64" in output and "arm64" not in output:
            return "x64"
    except Exception:
        pass

    return None


def running_roblox_binary_path() -> str | None:
    try:
        output = subprocess.check_output(
            [
                "pgrep",
                "-f",
                "/Applications/.*Roblox.*\\.app/Contents/MacOS/RobloxPlayer",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return None

    for line in output.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue

        path = process_path(pid)
        if path:
            return path

    return None


def installed_roblox_architecture() -> str | None:
    candidates = [
        "/Applications/Roblox.app/Contents/MacOS/RobloxPlayer",
        "/Applications/RobloxPlayer.app/Contents/MacOS/RobloxPlayer",
    ]

    detected = []
    for path in candidates:
        architecture = binary_architecture(path)
        if architecture:
            detected.append(architecture)

    if len(set(detected)) == 1:
        return detected[0]
    return None


def roblox_architecture() -> str:
    env_architecture = normalize_architecture(os.environ.get("ROBLOXMEMORYAPI_ROBLOX_ARCH"))
    if env_architecture:
        return env_architecture

    try:
        pid = int(os.environ.get("ROBLOXMEMORYAPI_ROBLOX_PID", "0"))
    except ValueError:
        pid = 0

    architecture = binary_architecture(process_path(pid))
    if architecture:
        return architecture

    architecture = binary_architecture(running_roblox_binary_path())
    if architecture:
        return architecture

    architecture = installed_roblox_architecture()
    if architecture:
        return architecture

    return "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
