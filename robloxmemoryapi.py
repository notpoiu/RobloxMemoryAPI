from utils.memory import EvasiveProcess, PROCESS_QUERY_INFORMATION, PROCESS_VM_READ, get_pid_by_name
from utils.rbx.instance import DataModel
import platform

if platform.system() != "Windows":
    raise RuntimeError("This module is only compatible with Windows.")

class RobloxGameClient:
    def __init__(self, pid: int = None, process_name: str = "RobloxPlayerBeta.exe"):
        if pid is None:
            self.pid = get_pid_by_name(process_name)
        else:
            self.pid = pid
        
        if self.pid is None or self.pid == 0:
            raise ValueError("Failed to get PID.")

        self.memory_module = EvasiveProcess(self.pid, PROCESS_VM_READ | PROCESS_QUERY_INFORMATION)

    @property
    def DataModel(self):
        return DataModel(self.memory_module)