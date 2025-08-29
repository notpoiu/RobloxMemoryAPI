from utils.memory import EvasiveProcess, PROCESS_QUERY_INFORMATION, PROCESS_VM_READ, get_pid_by_name
from utils.rbx.instance import DataModel

import platform
import math

class RobloxRandom:
    MULT   = 6364136223846793005
    INC    = 105               # PCG32_INC | 1
    MASK64 = (1 << 64) - 1

    def __init__(self, seed):
        s = math.floor(seed)

        self._state = 0
        self._inc   = RobloxRandom.INC
        self._next_internal()         # warm-up #1
        self._state = (self._state + s) & RobloxRandom.MASK64
        self._next_internal()         # warm-up #2

    def _next_internal(self):
        """Advance state & return a 32-bit result."""
        old = self._state
        self._state = (old * RobloxRandom.MULT + self._inc) & RobloxRandom.MASK64

        # XSH-RR output transform
        x = ((old >> 18) ^ old) >> 27
        r = old >> 59
        return ((x >> r) | (x << ((32 - r) & 31))) & 0xFFFFFFFF

    def _next_fraction64(self):
        """Build a 64-bit fraction by two calls, then /2**64."""
        lo = self._next_internal()
        hi = self._next_internal()
        bits = (hi << 32) | lo
        return bits / 2**64

    def NextNumber(self, minimum=0.0, maximum=1.0):
        frac = self._next_fraction64()
        return minimum + frac * (maximum - minimum)

    def NextInteger(self, a, b=None):
        if b is None:
            # single-arg form → [1..a]
            u = a
            r = self._next_internal()
            return ((u * r) >> 32) + 1
        else:
            lo, hi = (a, b) if a <= b else (b, a)
            u = hi - lo + 1
            r = self._next_internal()
            return ((u * r) >> 32) + lo

class RobloxGameClient:
    def __init__(self, pid: int = None, process_name: str = "RobloxPlayerBeta.exe"):
        if platform.system() != "Windows":
            self.failed = True
            return
        
        if pid is None:
            self.pid = get_pid_by_name(process_name)
        else:
            self.pid = pid
        
        if self.pid is None or self.pid == 0:
            raise ValueError("Failed to get PID.")

        self.memory_module = EvasiveProcess(self.pid, PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)
        self.failed = False

    def close(self):
        self.memory_module.close()

    @property
    def DataModel(self):        
        if platform.system() != "Windows":
            raise RuntimeError("This module is only compatible with Windows.")
        elif self.failed:
            raise RuntimeError("There was an error while getting access to memory. Please try again later.")

        return DataModel(self.memory_module)