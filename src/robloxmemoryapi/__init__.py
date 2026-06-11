import platform
import math
import os
import subprocess
import sys
import tempfile

from ._version import __version__

__all__ = [
    "RobloxRandom",
    "RobloxGameClient",
    "codesign_roblox_macos",
    "codesign_python_macos",
    "__version__",
]


def codesign_roblox_macos(
    app_path: str | os.PathLike[str] | None = None,
    *,
    silicon_app_path: str | os.PathLike[str] = "/Applications/Roblox.app",
    intel_app_path: str | os.PathLike[str] = "/Applications/RobloxPlayer.app",
    use_sudo: bool = True,
) -> str:
    """Ad-hoc sign a macOS Roblox app bundle for local memory access workflows."""
    if platform.system() != "Darwin":
        raise RuntimeError("codesign_roblox_macos is only available on macOS.")

    if app_path is None:
        app_path = silicon_app_path if platform.machine().lower() == "arm64" else intel_app_path

    app_path = os.fspath(app_path)
    if not os.path.exists(app_path):
        raise FileNotFoundError(app_path)

    sudo_prefix = ["sudo"] if use_sudo and os.geteuid() != 0 else []
    subprocess.run(
        sudo_prefix + ["codesign", "--remove-signature", app_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        sudo_prefix + ["codesign", "--force", "--deep", "--sign", "-", app_path],
        check=True,
    )

    return app_path


def codesign_python_macos(
    executable_path: str | os.PathLike[str] | None = None,
    *,
    use_sudo: bool = True,
) -> str:
    """Ad-hoc sign the Python executable/launcher with the macOS debugger entitlement."""
    if platform.system() != "Darwin":
        raise RuntimeError("codesign_python_macos is only available on macOS.")

    if executable_path is None:
        executable_path = sys.executable

    executable_path = os.path.realpath(os.fspath(executable_path))
    if not os.path.exists(executable_path):
        raise FileNotFoundError(executable_path)

    entitlements = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.debugger</key>
  <true/>
  <key>com.apple.security.get-task-allow</key>
  <true/>
  <key>SecTaskAccess</key>
  <array><string>allowed</string></array>
</dict>
</plist>
"""

    sudo_prefix = ["sudo"] if use_sudo and os.geteuid() != 0 else []
    with tempfile.NamedTemporaryFile("w", suffix=".plist", delete=False) as entitlement_file:
        entitlement_file.write(entitlements)
        entitlement_path = entitlement_file.name

    try:
        subprocess.run(
            sudo_prefix + ["codesign", "--remove-signature", executable_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            sudo_prefix
            + [
                "codesign",
                "--force",
                "--sign",
                "-",
                "--entitlements",
                entitlement_path,
                executable_path,
            ],
            check=True,
        )
    finally:
        try:
            os.unlink(entitlement_path)
        except OSError:
            pass

    return executable_path


class RobloxRandom:
    MULT = 6364136223846793005
    INC = 105
    MASK64 = (1 << 64) - 1

    def __init__(self, seed):
        s = math.floor(seed)

        self._state = 0
        self._inc = RobloxRandom.INC
        self._next_internal()         # warm-up #1
        self._state = (self._state + s) & RobloxRandom.MASK64
        self._next_internal()         # warm-up #2

    def _next_internal(self):
        old = self._state
        self._state = (old * RobloxRandom.MULT + self._inc) & RobloxRandom.MASK64
        x = ((old >> 18) ^ old) >> 27
        r = old >> 59
        return ((x >> r) | (x << ((32 - r) & 31))) & 0xFFFFFFFF

    def _next_fraction64(self):
        lo = self._next_internal()
        hi = self._next_internal()
        bits = (hi << 32) | lo
        return bits / 2**64

    def NextNumber(self, minimum=0.0, maximum=1.0):
        frac = self._next_fraction64()
        return minimum + frac * (maximum - minimum)

    def NextInteger(self, a, b=None):
        if b is None:
            u = a
            r = self._next_internal()
            return ((u * r) >> 32) + 1
        else:
            lo, hi = (a, b) if a <= b else (b, a)
            u = hi - lo + 1
            r = self._next_internal()
            return ((u * r) >> 32) + lo

class RobloxGameClient:
    def __init__(
        self,
        pid: int = None,
        process_name: str = "RobloxPlayerBeta.exe",
        allow_write: bool = False,
    ):
        system = platform.system()
        if system not in {"Windows", "Darwin"}:
            self.failed = True
            return

        if system == "Darwin" and os.geteuid() != 0:
            raise PermissionError(
                "macOS memory access requires running the Python process with sudo/root. "
                "Run this script with sudo and try again."
            )

        from .utils.memory import (
            EvasiveProcess,
            PROCESS_QUERY_INFORMATION,
            PROCESS_VM_READ,
            PROCESS_VM_WRITE,
            PROCESS_VM_OPERATION,
            get_pid_by_name,
        )

        if system == "Darwin" and process_name == "RobloxPlayerBeta.exe":
            process_name = "RobloxPlayer"

        if pid is None:
            self.pid = get_pid_by_name(process_name)
        else:
            self.pid = pid

        if self.pid is None or self.pid == 0:
            raise ValueError("Failed to get PID.")

        if system == "Darwin":
            os.environ["ROBLOXMEMORYAPI_ROBLOX_PID"] = str(self.pid)

        desired_access = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION
        if allow_write:
            desired_access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION

        self.memory_module = EvasiveProcess(self.pid, desired_access)
        self.failed = False
        self._fflags = None

    def close(self):
        self.memory_module.close()

    @property
    def FFlags(self):
        if platform.system() not in {"Windows", "Darwin"}:
            raise RuntimeError("This module is only compatible with Windows and macOS.")
        elif self.failed:
            raise RuntimeError("There was an error while getting access to memory. Please try again later.")

        if self._fflags is None:
            from .utils.rbx.fflags import FFlagManager
            self._fflags = FFlagManager(self.memory_module)
        return self._fflags

    @property
    def DataModel(self):
        if platform.system() not in {"Windows", "Darwin"}:
            raise RuntimeError("This module is only compatible with Windows and macOS.")
        elif self.failed:
            raise RuntimeError("There was an error while getting access to memory. Please try again later.")

        from .utils.rbx.instance import DataModel
        return DataModel(self.memory_module)
