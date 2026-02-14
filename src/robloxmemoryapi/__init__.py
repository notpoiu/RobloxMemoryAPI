import platform
import math

__all__ = ["RobloxRandom", "RobloxGameClient", "__version__"]
__version__ = "0.0.2"

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
        if platform.system() != "Windows":
            self.failed = True
            return

        from .utils.memory import (
            EvasiveProcess,
            PROCESS_QUERY_INFORMATION,
            PROCESS_VM_READ,
            PROCESS_VM_WRITE,
            PROCESS_VM_OPERATION,
            get_pid_by_name,
        )

        if pid is None:
            self.pid = get_pid_by_name(process_name)
        else:
            self.pid = pid

        if self.pid is None or self.pid == 0:
            raise ValueError("Failed to get PID.")

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
        if platform.system() != "Windows":
            raise RuntimeError("This module is only compatible with Windows.")
        elif self.failed:
            raise RuntimeError("There was an error while getting access to memory. Please try again later.")

        if self._fflags is None:
            from .utils.rbx.fflags import FFlagManager
            self._fflags = FFlagManager(self.memory_module)
        return self._fflags

    @property
    def DataModel(self):
        if platform.system() != "Windows":
            raise RuntimeError("This module is only compatible with Windows.")
        elif self.failed:
            raise RuntimeError("There was an error while getting access to memory. Please try again later.")

        from .utils.rbx.instance import DataModel
        return DataModel(self.memory_module)