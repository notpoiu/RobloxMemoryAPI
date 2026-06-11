#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace py = pybind11;

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <tlhelp32.h>
#include <psapi.h>
#elif defined(__APPLE__)
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <mach-o/loader.h>
#include <libproc.h>
#include <sys/proc_info.h>
#endif

namespace {

constexpr std::uint32_t PROCESS_QUERY_INFORMATION_VALUE = 0x0400;
constexpr std::uint32_t PROCESS_VM_READ_VALUE = 0x0010;
constexpr std::uint32_t PROCESS_VM_WRITE_VALUE = 0x0020;
constexpr std::uint32_t PROCESS_VM_OPERATION_VALUE = 0x0008;
constexpr std::uint32_t MEM_COMMIT_VALUE = 0x1000;
constexpr std::uint32_t MEM_RESERVE_VALUE = 0x2000;
constexpr std::uint32_t PAGE_READWRITE_VALUE = 0x04;
constexpr std::uint32_t PAGE_EXECUTE_READWRITE_VALUE = 0x40;

std::string hex_status(long status) {
    std::ostringstream oss;
    oss << "0x" << std::uppercase << std::hex << static_cast<unsigned long>(status);
    return oss.str();
}

[[noreturn]] void raise_python(PyObject *type, const std::string &message) {
    PyErr_SetString(type, message.c_str());
    throw py::error_already_set();
}

std::string bytes_from_object(const py::object &data) {
    if (PyBytes_Check(data.ptr())) {
        char *buffer = nullptr;
        Py_ssize_t size = 0;
        if (PyBytes_AsStringAndSize(data.ptr(), &buffer, &size) != 0) {
            throw py::error_already_set();
        }
        return std::string(buffer, static_cast<std::size_t>(size));
    }

    if (PyByteArray_Check(data.ptr())) {
        char *buffer = PyByteArray_AsString(data.ptr());
        Py_ssize_t size = PyByteArray_Size(data.ptr());
        if (buffer == nullptr || size < 0) {
            throw py::error_already_set();
        }
        return std::string(buffer, static_cast<std::size_t>(size));
    }

    raise_python(PyExc_TypeError, "data must be bytes-like.");
}

template <typename T>
T read_scalar_from_bytes(const std::string &bytes, T fallback) {
    if (bytes.size() != sizeof(T)) {
        return fallback;
    }

    T value{};
    std::memcpy(&value, bytes.data(), sizeof(T));
    return value;
}

template <typename T>
std::string scalar_to_bytes(T value) {
    std::string bytes(sizeof(T), '\0');
    std::memcpy(bytes.data(), &value, sizeof(T));
    return bytes;
}

#if defined(_WIN32)

using NtStatus = LONG;

struct CLIENT_ID_NATIVE {
    HANDLE UniqueProcess;
    HANDLE UniqueThread;
};

struct OBJECT_ATTRIBUTES_NATIVE {
    ULONG Length;
    HANDLE RootDirectory;
    PVOID ObjectName;
    ULONG Attributes;
    PVOID SecurityDescriptor;
    PVOID SecurityQualityOfService;
};

using NtOpenProcessFn = NtStatus(WINAPI *)(PHANDLE, ACCESS_MASK, OBJECT_ATTRIBUTES_NATIVE *, CLIENT_ID_NATIVE *);
using NtReadVirtualMemoryFn = NtStatus(WINAPI *)(HANDLE, PVOID, PVOID, SIZE_T, PSIZE_T);
using NtWriteVirtualMemoryFn = NtStatus(WINAPI *)(HANDLE, PVOID, PVOID, SIZE_T, PSIZE_T);
using NtCloseFn = NtStatus(WINAPI *)(HANDLE);
using NtAllocateVirtualMemoryFn = NtStatus(WINAPI *)(HANDLE, PVOID *, ULONG_PTR, PSIZE_T, ULONG, ULONG);

constexpr NtStatus STATUS_SUCCESS_VALUE = 0;
constexpr DWORD LIST_MODULES_ALL_VALUE = 0x03;

struct SyscallTable {
    NtOpenProcessFn open_process = nullptr;
    NtReadVirtualMemoryFn read_virtual_memory = nullptr;
    NtWriteVirtualMemoryFn write_virtual_memory = nullptr;
    NtCloseFn close = nullptr;
    NtAllocateVirtualMemoryFn allocate_virtual_memory = nullptr;
};

std::uint32_t get_syscall_number(HMODULE ntdll, const char *function_name) {
    auto *address = reinterpret_cast<unsigned char *>(GetProcAddress(ntdll, function_name));
    if (address == nullptr) {
        return 0;
    }

    if (address[0] == 0x4c && address[1] == 0x8b && address[2] == 0xd1 && address[3] == 0xb8) {
        std::uint32_t number = 0;
        std::memcpy(&number, address + 4, sizeof(number));
        return number;
    }

    return 0;
}

template <typename Fn>
Fn create_syscall_stub(std::uint32_t syscall_number) {
    unsigned char stub[] = {
        0x4c, 0x8b, 0xd1,
        0xb8, 0x00, 0x00, 0x00, 0x00,
        0x0f, 0x05,
        0xc3,
    };
    std::memcpy(stub + 4, &syscall_number, sizeof(syscall_number));

    void *memory = VirtualAlloc(nullptr, sizeof(stub), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (memory == nullptr) {
        raise_python(PyExc_OSError, "VirtualAlloc failed while creating syscall stub.");
    }

    std::memcpy(memory, stub, sizeof(stub));
    return reinterpret_cast<Fn>(memory);
}

SyscallTable &syscalls() {
    static SyscallTable table;
    static bool initialized = false;

    if (initialized) {
        return table;
    }

    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (ntdll == nullptr) {
        raise_python(PyExc_RuntimeError, "Could not get ntdll.dll handle.");
    }

    const std::uint32_t open_id = get_syscall_number(ntdll, "NtOpenProcess");
    const std::uint32_t read_id = get_syscall_number(ntdll, "NtReadVirtualMemory");
    const std::uint32_t write_id = get_syscall_number(ntdll, "NtWriteVirtualMemory");
    const std::uint32_t close_id = get_syscall_number(ntdll, "NtClose");
    const std::uint32_t alloc_id = get_syscall_number(ntdll, "NtAllocateVirtualMemory");

    if (open_id == 0 || read_id == 0 || write_id == 0 || close_id == 0 || alloc_id == 0) {
        raise_python(PyExc_RuntimeError, "Could not find required syscall numbers.");
    }

    table.open_process = create_syscall_stub<NtOpenProcessFn>(open_id);
    table.read_virtual_memory = create_syscall_stub<NtReadVirtualMemoryFn>(read_id);
    table.write_virtual_memory = create_syscall_stub<NtWriteVirtualMemoryFn>(write_id);
    table.close = create_syscall_stub<NtCloseFn>(close_id);
    table.allocate_virtual_memory = create_syscall_stub<NtAllocateVirtualMemoryFn>(alloc_id);
    initialized = true;
    return table;
}

std::uintptr_t get_module_base(HANDLE process_handle) {
    DWORD needed = 0;
    std::vector<HMODULE> modules(256);

    BOOL success = EnumProcessModulesEx(
        process_handle,
        modules.data(),
        static_cast<DWORD>(modules.size() * sizeof(HMODULE)),
        &needed,
        LIST_MODULES_ALL_VALUE
    );

    if (!success) {
        return 0;
    }

    if (needed > modules.size() * sizeof(HMODULE)) {
        modules.resize(needed / sizeof(HMODULE));
        success = EnumProcessModulesEx(
            process_handle,
            modules.data(),
            static_cast<DWORD>(modules.size() * sizeof(HMODULE)),
            &needed,
            LIST_MODULES_ALL_VALUE
        );
        if (!success) {
            return 0;
        }
    }

    if (needed == 0 || modules.empty() || modules[0] == nullptr) {
        return 0;
    }

    return reinterpret_cast<std::uintptr_t>(modules[0]);
}

#elif defined(__APPLE__)

bool is_macho_magic(std::uint32_t magic) {
    return magic == MH_MAGIC || magic == MH_CIGAM || magic == MH_MAGIC_64 || magic == MH_CIGAM_64;
}

#endif

class EvasiveProcess {
public:
    int pid = 0;
    std::uint32_t access = 0;
    std::uintptr_t base = 0;
    bool is_closed = true;

    EvasiveProcess(int process_id, std::uint32_t desired_access)
        : pid(process_id), access(desired_access) {
#if defined(_WIN32)
        auto &table = syscalls();

        OBJECT_ATTRIBUTES_NATIVE object_attributes{};
        object_attributes.Length = sizeof(OBJECT_ATTRIBUTES_NATIVE);

        CLIENT_ID_NATIVE client_id{};
        client_id.UniqueProcess = reinterpret_cast<HANDLE>(static_cast<std::uintptr_t>(pid));
        client_id.UniqueThread = nullptr;

        HANDLE opened_handle = nullptr;
        NtStatus status = table.open_process(
            &opened_handle,
            static_cast<ACCESS_MASK>(access),
            &object_attributes,
            &client_id
        );

        if (status != STATUS_SUCCESS_VALUE) {
            raise_python(PyExc_OSError, "NtOpenProcess failed with NTSTATUS: " + hex_status(status));
        }

        handle_ = opened_handle;
        is_closed = false;
        base = get_module_base(handle_);

        if (base == 0) {
            close();
            raise_python(PyExc_ConnectionError, "Failed to get module base address.");
        }
#elif defined(__APPLE__)
        mach_port_t task = MACH_PORT_NULL;
        kern_return_t result = task_for_pid(mach_task_self(), pid, &task);
        if (result != KERN_SUCCESS) {
            raise_python(
                PyExc_OSError,
                "task_for_pid failed: " + std::string(mach_error_string(result)) +
                    ". macOS memory reads require permission to acquire the target task port."
            );
        }

        task_ = task;
        is_closed = false;
        base = find_macos_base();

        if (base == 0) {
            close();
            raise_python(PyExc_ConnectionError, "Failed to get module base address.");
        }
#else
        (void)process_id;
        (void)desired_access;
        raise_python(PyExc_RuntimeError, "Native memory backend is only compatible with Windows and macOS.");
#endif
    }

    ~EvasiveProcess() {
        try {
            close();
        } catch (...) {
        }
    }

    bool is_invalid_handle() const {
#if defined(_WIN32)
        return is_closed || handle_ == nullptr || handle_ == INVALID_HANDLE_VALUE;
#elif defined(__APPLE__)
        return is_closed || task_ == MACH_PORT_NULL;
#else
        return true;
#endif
    }

    std::uintptr_t handle_value() const {
#if defined(_WIN32)
        return reinterpret_cast<std::uintptr_t>(handle_);
#elif defined(__APPLE__)
        return static_cast<std::uintptr_t>(task_);
#else
        return 0;
#endif
    }

    py::bytes read(std::uintptr_t address, std::size_t size) {
        return py::bytes(read_bytes(address, size));
    }

    std::size_t write(std::uintptr_t address, const py::object &data) {
        const std::string bytes = bytes_from_object(data);
        if (bytes.empty()) {
            return 0;
        }

#if defined(_WIN32)
        if (is_invalid_handle()) {
            raise_python(PyExc_ValueError, "Process handle is not valid.");
        }

        SIZE_T bytes_written = 0;
        NtStatus status = STATUS_SUCCESS_VALUE;
        {
            py::gil_scoped_release release;
            status = syscalls().write_virtual_memory(
                handle_,
                reinterpret_cast<PVOID>(address),
                const_cast<char *>(bytes.data()),
                bytes.size(),
                &bytes_written
            );
        }

        if (status != STATUS_SUCCESS_VALUE) {
            raise_python(PyExc_OSError, "NtWriteVirtualMemory failed with NTSTATUS: " + hex_status(status));
        }

        return static_cast<std::size_t>(bytes_written);
#elif defined(__APPLE__)
        (void)address;
        raise_python(PyExc_NotImplementedError, "write is not implemented on macOS; the native macOS backend is read-only.");
#else
        (void)address;
        raise_python(PyExc_RuntimeError, "Native memory backend is only compatible with Windows and macOS.");
#endif
    }

    std::uintptr_t virtual_alloc(
        std::size_t size,
        std::uint32_t allocation_type = MEM_COMMIT_VALUE | MEM_RESERVE_VALUE,
        std::uint32_t protection = PAGE_READWRITE_VALUE
    ) {
        if (size == 0) {
            raise_python(PyExc_ValueError, "size must be greater than zero.");
        }

        if (is_closed) {
            return 0;
        }

#if defined(_WIN32)
        if (is_invalid_handle()) {
            raise_python(PyExc_ValueError, "Process handle is not valid.");
        }

        PVOID base_address = nullptr;
        SIZE_T region_size = size;
        NtStatus status = STATUS_SUCCESS_VALUE;
        {
            py::gil_scoped_release release;
            status = syscalls().allocate_virtual_memory(
                handle_,
                &base_address,
                0,
                &region_size,
                allocation_type,
                protection
            );
        }

        if (status != STATUS_SUCCESS_VALUE) {
            raise_python(PyExc_OSError, "NtAllocateVirtualMemory failed with NTSTATUS: " + hex_status(status));
        }

        return reinterpret_cast<std::uintptr_t>(base_address);
#elif defined(__APPLE__)
        (void)allocation_type;
        (void)protection;
        raise_python(PyExc_NotImplementedError, "virtual_alloc is not implemented on macOS; the native macOS backend is read-only.");
#else
        (void)allocation_type;
        (void)protection;
        raise_python(PyExc_RuntimeError, "Native memory backend is only compatible with Windows and macOS.");
#endif
    }

    int read_int(std::uintptr_t address, std::uintptr_t offset = 0) {
        return read_scalar_from_bytes<std::int32_t>(read_bytes(address + offset, sizeof(std::int32_t)), 0);
    }

    long long read_int64(std::uintptr_t address, std::uintptr_t offset = 0) {
        return read_scalar_from_bytes<std::int64_t>(read_bytes(address + offset, sizeof(std::int64_t)), 0);
    }

    long long read_long(std::uintptr_t address, std::uintptr_t offset = 0) {
        return read_int64(address, offset);
    }

    double read_double(std::uintptr_t address, std::uintptr_t offset = 0) {
        try {
            return read_scalar_from_bytes<double>(read_bytes(address + offset, sizeof(double)), 0.0);
        } catch (const py::error_already_set &) {
            PyErr_Clear();
            return 0.0;
        }
    }

    float read_float(std::uintptr_t address, std::uintptr_t offset = 0) {
        try {
            return read_scalar_from_bytes<float>(read_bytes(address + offset, sizeof(float)), 0.0f);
        } catch (const py::error_already_set &) {
            PyErr_Clear();
            return 0.0f;
        }
    }

    std::vector<float> read_floats(std::uintptr_t address, std::size_t amount) {
        try {
            std::string bytes = read_bytes(address, amount * sizeof(float));
            std::vector<float> values;
            values.reserve(amount);

            for (std::size_t index = 0; index < amount; ++index) {
                const std::size_t start = index * sizeof(float);
                if (start + sizeof(float) <= bytes.size()) {
                    float value = 0.0f;
                    std::memcpy(&value, bytes.data() + start, sizeof(float));
                    values.push_back(value);
                } else {
                    values.push_back(0.0f);
                }
            }

            return values;
        } catch (const py::error_already_set &) {
            PyErr_Clear();
            return {0.0f};
        }
    }

    void write_int(std::uintptr_t address, int value) {
        const std::int32_t native_value = static_cast<std::int32_t>(value);
        write(address, py::bytes(scalar_to_bytes(native_value)));
    }

    void write_int64(std::uintptr_t address, long long value) {
        const std::int64_t native_value = static_cast<std::int64_t>(value);
        write(address, py::bytes(scalar_to_bytes(native_value)));
    }

    void write_long(std::uintptr_t address, long long value) {
        write_int64(address, value);
    }

    void write_double(std::uintptr_t address, double value) {
        write(address, py::bytes(scalar_to_bytes(value)));
    }

    void write_float(std::uintptr_t address, float value) {
        write(address, py::bytes(scalar_to_bytes(value)));
    }

    void write_floats(std::uintptr_t address, const std::vector<float> &values) {
        std::string bytes(values.size() * sizeof(float), '\0');
        if (!values.empty()) {
            std::memcpy(bytes.data(), values.data(), bytes.size());
            write(address, py::bytes(bytes));
        }
    }

    bool read_bool(std::uintptr_t address, std::uintptr_t offset = 0) {
        try {
            std::string bytes = read_bytes(address + offset, 1);
            if (bytes.empty()) {
                return false;
            }
            return bytes[0] != 0;
        } catch (const py::error_already_set &) {
            PyErr_Clear();
            return false;
        }
    }

    void write_bool(std::uintptr_t address, bool value) {
        const char byte = value ? 1 : 0;
        write(address, py::bytes(&byte, 1));
    }

    std::string read_raw_string(std::uintptr_t address, std::size_t max_length = 256) {
        std::string bytes = read_bytes(address, max_length);
        const auto null_position = bytes.find('\0');
        if (null_position != std::string::npos) {
            bytes.resize(null_position);
        }

        PyObject *decoded = PyUnicode_DecodeUTF8(bytes.data(), static_cast<Py_ssize_t>(bytes.size()), "ignore");
        if (decoded == nullptr) {
            throw py::error_already_set();
        }
        return py::reinterpret_steal<py::str>(decoded).cast<std::string>();
    }

    void write_raw_string(std::uintptr_t address, const std::string &value, bool null_terminate = true) {
        std::string bytes = value;
        if (null_terminate) {
            bytes.push_back('\0');
        }
        write(address, py::bytes(bytes));
    }

    void write_string(std::uintptr_t address, const std::string &value) {
        const std::size_t length = value.size();
        const std::uintptr_t length_address = address + 0x10;
        const std::uintptr_t capacity_address = address + 0x18;
        const int current_capacity = read_int(capacity_address);

        if (length <= static_cast<std::size_t>(std::max(current_capacity, 0))) {
            if (current_capacity > 15) {
                const std::uintptr_t pointer = static_cast<std::uintptr_t>(read_long(address));
                if (pointer != 0) {
                    write(pointer, py::bytes(value));
                    if (length < static_cast<std::size_t>(current_capacity)) {
                        const char null_byte = '\0';
                        write(pointer + length, py::bytes(&null_byte, 1));
                    }
                    write_int(length_address, static_cast<int>(length));
                    return;
                }
            } else {
                std::string inline_bytes = value;
                inline_bytes.resize(16, '\0');
                write(address, py::bytes(inline_bytes.substr(0, 16)));
                write_int(length_address, static_cast<int>(length));
                return;
            }
        }

        const std::size_t new_capacity = length + 16;
        const std::uintptr_t pointer = virtual_alloc(new_capacity);
        if (pointer == 0) {
            raise_python(PyExc_MemoryError, "Failed to allocate memory for string.");
        }

        std::string heap_bytes = value;
        heap_bytes.push_back('\0');
        write(pointer, py::bytes(heap_bytes));
        write_long(address, static_cast<long long>(pointer));
        write_int(length_address, static_cast<int>(length));
        write_int(capacity_address, static_cast<int>(new_capacity));
    }

    std::string read_string(std::uintptr_t address, std::uintptr_t offset = 0) {
        address += offset;
        const int string_length = read_int(address + 0x10);

        if (string_length <= 0 || string_length > 1024 * 1024) {
            return "";
        }

        if (string_length <= 15) {
            return read_raw_string(address, static_cast<std::size_t>(string_length));
        }

        const std::uintptr_t pointer = static_cast<std::uintptr_t>(read_long(address));
        return pointer != 0 ? read_raw_string(pointer, static_cast<std::size_t>(string_length)) : "";
    }

    std::uintptr_t get_pointer(std::uintptr_t address, std::uintptr_t offset = 0) {
        std::string bytes = read_bytes(address + offset, sizeof(std::uint64_t));
        if (bytes.size() != sizeof(std::uint64_t)) {
            return 0;
        }
        std::uint64_t value = 0;
        std::memcpy(&value, bytes.data(), sizeof(value));
        return static_cast<std::uintptr_t>(value);
    }

    std::uintptr_t get_address(std::uintptr_t address, bool pointer) {
        if (pointer) {
            return get_pointer(base + address);
        }
        return base + address;
    }

    void close() {
#if defined(_WIN32)
        if (!is_closed && handle_ != nullptr && handle_ != INVALID_HANDLE_VALUE) {
            syscalls().close(handle_);
            handle_ = nullptr;
        }
        is_closed = true;
#elif defined(__APPLE__)
        if (!is_closed && task_ != MACH_PORT_NULL) {
            mach_port_deallocate(mach_task_self(), task_);
            task_ = MACH_PORT_NULL;
        }
        is_closed = true;
#else
        is_closed = true;
#endif
    }

private:
    std::string read_bytes(std::uintptr_t address, std::size_t size) {
        if (is_closed) {
            return "";
        }

        if (is_invalid_handle()) {
            raise_python(PyExc_ValueError, "Process handle is not valid.");
        }

        std::string buffer(size, '\0');

#if defined(_WIN32)
        SIZE_T bytes_read = 0;
        NtStatus status = STATUS_SUCCESS_VALUE;
        {
            py::gil_scoped_release release;
            status = syscalls().read_virtual_memory(
                handle_,
                reinterpret_cast<PVOID>(address),
                buffer.data(),
                size,
                &bytes_read
            );
        }

        if (status != STATUS_SUCCESS_VALUE) {
            raise_python(PyExc_OSError, "NtReadVirtualMemory failed with NTSTATUS: " + hex_status(status));
        }

        buffer.resize(static_cast<std::size_t>(bytes_read));
        return buffer;
#elif defined(__APPLE__)
        mach_vm_size_t bytes_read = 0;
        kern_return_t result = KERN_SUCCESS;
        {
            py::gil_scoped_release release;
            result = mach_vm_read_overwrite(
                task_,
                static_cast<mach_vm_address_t>(address),
                static_cast<mach_vm_size_t>(size),
                reinterpret_cast<mach_vm_address_t>(buffer.data()),
                &bytes_read
            );
        }

        if (result != KERN_SUCCESS) {
            raise_python(PyExc_OSError, "mach_vm_read_overwrite failed: " + std::string(mach_error_string(result)));
        }

        buffer.resize(static_cast<std::size_t>(bytes_read));
        return buffer;
#else
        (void)address;
        (void)size;
        raise_python(PyExc_RuntimeError, "Native memory backend is only compatible with Windows and macOS.");
#endif
    }

#if defined(__APPLE__)
    std::uintptr_t find_macos_base() {
        mach_vm_address_t address = 0;

        while (true) {
            mach_vm_size_t size = 0;
            natural_t depth = 0;
            vm_region_submap_info_data_64_t info{};
            mach_msg_type_number_t count = VM_REGION_SUBMAP_INFO_COUNT_64;

            kern_return_t result = mach_vm_region_recurse(
                task_,
                &address,
                &size,
                &depth,
                reinterpret_cast<vm_region_recurse_info_t>(&info),
                &count
            );

            if (result != KERN_SUCCESS) {
                break;
            }

            if ((info.protection & VM_PROT_READ) != 0) {
                std::uint32_t magic = 0;
                mach_vm_size_t bytes_read = 0;
                result = mach_vm_read_overwrite(
                    task_,
                    address,
                    sizeof(magic),
                    reinterpret_cast<mach_vm_address_t>(&magic),
                    &bytes_read
                );

                if (result == KERN_SUCCESS && bytes_read == sizeof(magic) && is_macho_magic(magic)) {
                    return static_cast<std::uintptr_t>(address);
                }
            }

            if (size == 0) {
                break;
            }
            address += size;
        }

        return 0;
    }
#endif

#if defined(_WIN32)
    HANDLE handle_ = nullptr;
#elif defined(__APPLE__)
    mach_port_t task_ = MACH_PORT_NULL;
#endif
};

int get_pid_by_name(const std::string &process_name) {
#if defined(_WIN32)
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        raise_python(PyExc_OSError, "CreateToolhelp32Snapshot failed.");
    }

    const std::wstring wide_process_name(process_name.begin(), process_name.end());

    PROCESSENTRY32W entry{};
    entry.dwSize = sizeof(PROCESSENTRY32W);

    if (!Process32FirstW(snapshot, &entry)) {
        CloseHandle(snapshot);
        return 0;
    }

    do {
        if (wide_process_name == std::wstring_view(entry.szExeFile)) {
            const int pid = static_cast<int>(entry.th32ProcessID);
            CloseHandle(snapshot);
            return pid;
        }
    } while (Process32NextW(snapshot, &entry));

    CloseHandle(snapshot);
    return 0;
#elif defined(__APPLE__)
    const int pid_count = proc_listpids(PROC_ALL_PIDS, 0, nullptr, 0);
    if (pid_count <= 0) {
        return 0;
    }

    std::vector<pid_t> pids(static_cast<std::size_t>(pid_count));
    const int bytes = proc_listpids(PROC_ALL_PIDS, 0, pids.data(), static_cast<int>(pids.size() * sizeof(pid_t)));
    if (bytes <= 0) {
        return 0;
    }

    const std::size_t count = static_cast<std::size_t>(bytes) / sizeof(pid_t);
    for (std::size_t index = 0; index < count; ++index) {
        if (pids[index] <= 0) {
            continue;
        }

        char name_buffer[PROC_PIDPATHINFO_MAXSIZE]{};
        const int result = proc_name(pids[index], name_buffer, static_cast<std::uint32_t>(sizeof(name_buffer)));
        if (result > 0 && process_name == name_buffer) {
            return static_cast<int>(pids[index]);
        }
    }

    return 0;
#else
    (void)process_name;
    raise_python(PyExc_RuntimeError, "Native memory backend is only compatible with Windows and macOS.");
#endif
}

}  // namespace

PYBIND11_MODULE(memory, module) {
    module.doc() = "Native memory backend for robloxmemoryapi";

    module.attr("PROCESS_QUERY_INFORMATION") = PROCESS_QUERY_INFORMATION_VALUE;
    module.attr("PROCESS_VM_READ") = PROCESS_VM_READ_VALUE;
    module.attr("PROCESS_VM_WRITE") = PROCESS_VM_WRITE_VALUE;
    module.attr("PROCESS_VM_OPERATION") = PROCESS_VM_OPERATION_VALUE;
    module.attr("MEM_COMMIT") = MEM_COMMIT_VALUE;
    module.attr("MEM_RESERVE") = MEM_RESERVE_VALUE;
    module.attr("PAGE_READWRITE") = PAGE_READWRITE_VALUE;
    module.attr("PAGE_EXECUTE_READWRITE") = PAGE_EXECUTE_READWRITE_VALUE;

    module.def("get_pid_by_name", &get_pid_by_name, py::arg("process_name"));

    py::class_<EvasiveProcess>(module, "EvasiveProcess")
        .def(py::init<int, std::uint32_t>(), py::arg("pid"), py::arg("access"))
        .def_readwrite("pid", &EvasiveProcess::pid)
        .def_readwrite("access", &EvasiveProcess::access)
        .def_readwrite("base", &EvasiveProcess::base)
        .def_readwrite("is_closed", &EvasiveProcess::is_closed)
        .def_property_readonly("handle", &EvasiveProcess::handle_value)
        .def_property_readonly("is_invalid_handle", &EvasiveProcess::is_invalid_handle)
        .def("read", &EvasiveProcess::read, py::arg("address"), py::arg("size"))
        .def("write", &EvasiveProcess::write, py::arg("address"), py::arg("data"))
        .def(
            "virtual_alloc",
            &EvasiveProcess::virtual_alloc,
            py::arg("size"),
            py::arg("allocation_type") = MEM_COMMIT_VALUE | MEM_RESERVE_VALUE,
            py::arg("protection") = PAGE_READWRITE_VALUE
        )
        .def("read_int", &EvasiveProcess::read_int, py::arg("address"), py::arg("offset") = 0)
        .def("read_int64", &EvasiveProcess::read_int64, py::arg("address"), py::arg("offset") = 0)
        .def("read_long", &EvasiveProcess::read_long, py::arg("address"), py::arg("offset") = 0)
        .def("read_double", &EvasiveProcess::read_double, py::arg("address"), py::arg("offset") = 0)
        .def("read_float", &EvasiveProcess::read_float, py::arg("address"), py::arg("offset") = 0)
        .def("read_floats", &EvasiveProcess::read_floats, py::arg("address"), py::arg("amount"))
        .def("write_int", &EvasiveProcess::write_int, py::arg("address"), py::arg("value"))
        .def("write_int64", &EvasiveProcess::write_int64, py::arg("address"), py::arg("value"))
        .def("write_long", &EvasiveProcess::write_long, py::arg("address"), py::arg("value"))
        .def("write_double", &EvasiveProcess::write_double, py::arg("address"), py::arg("value"))
        .def("write_float", &EvasiveProcess::write_float, py::arg("address"), py::arg("value"))
        .def("write_floats", &EvasiveProcess::write_floats, py::arg("address"), py::arg("values"))
        .def("read_bool", &EvasiveProcess::read_bool, py::arg("address"), py::arg("offset") = 0)
        .def("write_bool", &EvasiveProcess::write_bool, py::arg("address"), py::arg("value"))
        .def("read_raw_string", &EvasiveProcess::read_raw_string, py::arg("address"), py::arg("max_length") = 256)
        .def("write_raw_string", &EvasiveProcess::write_raw_string, py::arg("address"), py::arg("value"), py::arg("null_terminate") = true)
        .def("write_string", &EvasiveProcess::write_string, py::arg("address"), py::arg("value"))
        .def("read_string", &EvasiveProcess::read_string, py::arg("address"), py::arg("offset") = 0)
        .def("get_pointer", &EvasiveProcess::get_pointer, py::arg("address"), py::arg("offset") = 0)
        .def("get_address", &EvasiveProcess::get_address, py::arg("address"), py::arg("pointer"))
        .def("close", &EvasiveProcess::close);
}
