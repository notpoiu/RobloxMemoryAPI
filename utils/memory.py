import ctypes
import struct
from ctypes import wintypes

ntdll = ctypes.WinDLL('ntdll.dll')
psapi = ctypes.WinDLL('psapi.dll')
kernel32 = ctypes.WinDLL('kernel32.dll')

kernel32.VirtualAlloc.restype = wintypes.LPVOID
kernel32.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.GetProcAddress.restype = wintypes.LPVOID
kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]

NTSTATUS = wintypes.LONG
HANDLE = wintypes.HANDLE
DWORD = wintypes.DWORD
LPVOID = wintypes.LPVOID
HMODULE = wintypes.HMODULE
BOOL = wintypes.BOOL

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
LIST_MODULES_ALL = 0x03
STATUS_SUCCESS = 0
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_EXECUTE_READWRITE = 0x40
NTDLL_HANDLE = ntdll._handle

class CLIENT_ID(ctypes.Structure):
    _fields_ = [
        ("UniqueProcess", HANDLE),
        ("UniqueThread", HANDLE),
    ]

class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("RootDirectory", HANDLE),
        ("ObjectName", LPVOID),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", LPVOID),
        ("SecurityQualityOfService", LPVOID),
    ]

def get_syscall_number(function_name: str) -> int | None:
    func_address = kernel32.GetProcAddress(NTDLL_HANDLE, function_name.encode('ascii'))
    if not func_address:
        return None
    buffer = (ctypes.c_ubyte * 8).from_address(func_address)
    if tuple(buffer[0:4]) == (0x4c, 0x8b, 0xd1, 0xb8):
        return int.from_bytes(bytes(buffer[4:8]), 'little')
    return None

def create_syscall_function(syscall_number, func_prototype):
    assembly_stub = b'\x4C\x8B\xD1' + \
                    b'\xB8' + syscall_number.to_bytes(4, 'little') + \
                    b'\x0F\x05' + \
                    b'\xC3'

    exec_mem = kernel32.VirtualAlloc(None, len(assembly_stub), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
    if not exec_mem:
        raise ctypes.WinError(ctypes.get_last_error())
    ctypes.memmove(exec_mem, assembly_stub, len(assembly_stub))
    return func_prototype(exec_mem)

NtOpenProcessProto = ctypes.WINFUNCTYPE(
    NTSTATUS,
    ctypes.POINTER(HANDLE),
    DWORD,
    ctypes.POINTER(OBJECT_ATTRIBUTES),
    ctypes.POINTER(CLIENT_ID)
)
NtReadVirtualMemoryProto = ctypes.WINFUNCTYPE(
    NTSTATUS,
    HANDLE,
    LPVOID,
    LPVOID,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong)
)
NtCloseProto = ctypes.WINFUNCTYPE(NTSTATUS, HANDLE)

syscall_id_open = get_syscall_number("NtOpenProcess")
syscall_id_read = get_syscall_number("NtReadVirtualMemory")
syscall_id_close = get_syscall_number("NtClose")

if not all([syscall_id_open, syscall_id_read, syscall_id_close]):
    raise RuntimeError("Could not find required syscall numbers.")

nt_open_process_syscall = create_syscall_function(syscall_id_open, NtOpenProcessProto)
nt_read_virtual_memory_syscall = create_syscall_function(syscall_id_read, NtReadVirtualMemoryProto)
nt_close_syscall = create_syscall_function(syscall_id_close, NtCloseProto)

psapi.EnumProcessModulesEx.argtypes = [
    HANDLE,
    ctypes.POINTER(HMODULE),
    DWORD,
    ctypes.POINTER(DWORD),
    DWORD
]
psapi.EnumProcessModulesEx.restype = BOOL

def _get_module_base(process_handle: HANDLE) -> int:
    try:
        modules_arr_size = 256
        modules_arr = (HMODULE * modules_arr_size)()
        needed = DWORD(0)
        psapi.EnumProcessModulesEx(
            process_handle,
            modules_arr,
            ctypes.sizeof(modules_arr),
            ctypes.byref(needed),
            LIST_MODULES_ALL
        )
        if needed.value > ctypes.sizeof(modules_arr):
            new_size = needed.value // ctypes.sizeof(HMODULE)
            modules_arr = (HMODULE * new_size)()
            success = psapi.EnumProcessModulesEx(
                process_handle,
                modules_arr,
                ctypes.sizeof(modules_arr),
                ctypes.byref(needed),
                LIST_MODULES_ALL
            )
            if not success:
                return 0
        if needed.value > 0:
            return modules_arr[0] if modules_arr[0] else 0
        return 0
    except Exception as e:
        print(f"An exception occurred in _get_module_base: {e}")
        return 0
   
def get_pid_by_name(process_name: str) -> int:
    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", DWORD),
            ("cntUsage", DWORD),
            ("th32ProcessID", DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", DWORD),
            ("cntThreads", DWORD),
            ("th32ParentProcessID", DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", DWORD),
            ("szExeFile", wintypes.CHAR * 260)
        ]
    snapshot = kernel32.CreateToolhelp32Snapshot(2, 0)
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        raise ctypes.WinError()
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    try:
        if not kernel32.Process32First(snapshot, ctypes.byref(entry)):
            return 0
        while True:
            if entry.szExeFile.decode('utf-8', errors='ignore') == process_name:
                return entry.th32ProcessID
            if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return 0

class EvasiveProcess:
    def __init__(self, pid: int, access: DWORD):
        self.pid = pid
        self.access = access
        self.handle = HANDLE(0)
        self.base = 0

        object_attributes = OBJECT_ATTRIBUTES()
        client_id = CLIENT_ID()
        client_id.UniqueProcess = HANDLE(pid)
        object_attributes.Length = ctypes.sizeof(OBJECT_ATTRIBUTES)

        status = nt_open_process_syscall(
            ctypes.byref(self.handle),
            access,
            ctypes.byref(object_attributes),
            ctypes.byref(client_id)
        )
        if status != STATUS_SUCCESS:
            raise ctypes.WinError(f"NtOpenProcess failed with NTSTATUS: 0x{status:X}")
        self.base = _get_module_base(self.handle)
        if self.base == 0:
            self.close()
            raise ConnectionError("Failed to get module base address.")

    def read(self, address: int, size: int) -> bytes:
        if not self.handle or self.handle.value == 0:
            raise ValueError("Process handle is not valid.")
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_ulong(0)
        status = nt_read_virtual_memory_syscall(
            self.handle,
            LPVOID(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        if status != STATUS_SUCCESS:
            raise OSError(f"NtReadVirtualMemory failed with NTSTATUS: 0x{status:X}")
        return buffer.raw[:bytes_read.value]

    # numbers #
    def read_int(self, address: int) -> int:
        buffer = self.read(address, 4)
        return int.from_bytes(buffer, 'little') if len(buffer) == 4 else 0
        
    def read_long(self, address: int) -> int:
        buffer = self.read(address, 8)
        return int.from_bytes(buffer, 'little') if len(buffer) == 8 else 0
    
    def read_double(self, address: int) -> float:
        try:
            double_bytes = self.read(address, 8)
            return struct.unpack('<d', double_bytes)[0] if len(double_bytes) == 8 else 0.0
        except (OSError, struct.error):
            return 0.0

    def read_float(self, address: int) -> float:
        try:
            float_bytes = self.read(address, 4)
            return struct.unpack('<f', float_bytes)[0] if len(float_bytes) == 4 else 0.0
        except (OSError, struct.error):
            return 0.0
    
    def read_floats(self, address: int, amount: int):
        try:
            bulk_float_bytes = self.read(address, 4 * amount)
            floats = []
            for i in range(amount):
                start_range = i * 4
                float_bytes = bulk_float_bytes[start_range:start_range + 4]
                if len(float_bytes) == 4:
                    floats.append(struct.unpack('<f', float_bytes)[0])
                else:
                    floats.append(0.0)

            return floats
        except (OSError, struct.error) as e:
            print(e)
            return [0.0]

    # bool #
    def read_bool(self, address: int) -> bool:
        try:
            bool_byte = self.read(address, 1)
            if not bool_byte: return False
            print(int.from_bytes(bool_byte, 'little'), bool_byte)
            return bool(int.from_bytes(bool_byte, 'little'))
        except OSError:
            return False

    # string #
    def read_raw_string(self, address: int, max_length: int = 256) -> str:
        buffer = self.read(address, max_length)
        null_pos = buffer.find(b'\x00')
        valid_bytes = buffer[:null_pos] if null_pos != -1 else buffer
        return valid_bytes.decode('utf-8', errors='ignore')
        
    def read_string(self, address: int) -> str:
        string_length = self.read_int(address + 0x10)
        if string_length <= 15:
            return self.read_raw_string(address, string_length)
        else:
            string_data_pointer = self.read_long(address)
            return self.read_raw_string(string_data_pointer, string_length) if string_data_pointer else ""
    
    #########
    def close(self):
        if self.handle and self.handle.value != 0:
            nt_close_syscall(self.handle)
            self.handle = HANDLE(0)