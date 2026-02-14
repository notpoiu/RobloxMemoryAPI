from ..offsets import get_fflag_offsets

_MODULE_SIZE_LIMIT = 0x20000000

# FLog level byte → display name.
_FLOG_LEVELS = {
    0: "None",
    1: "Trace",
    2: "Info",
    3: "Warning",
    4: "Error",
    5: "Assert",
    6: "Fatal",
}

_FLOG_LEVELS_REV = {v: k for k, v in _FLOG_LEVELS.items()}

def _decode_flog(raw_int: int) -> str:
    level_byte = (raw_int >> 8) & 0xFF
    param_byte = raw_int & 0xFF
    level_name = _FLOG_LEVELS.get(level_byte, str(level_byte))
    return f"{level_name},{param_byte}"


def _encode_flog(value: str) -> int:
    parts = value.split(",", 1)
    level_name = parts[0].strip()
    param = int(parts[1].strip()) if len(parts) > 1 else 0
    level_byte = _FLOG_LEVELS_REV.get(level_name)
    if level_byte is None:
        level_byte = int(level_name)
    return (level_byte << 8) | (param & 0xFF)


class FFlag:
    __slots__ = ("name", "type", "value", "offset")

    def __init__(self, name: str, flag_type: str, value, offset: int):
        self.name = name
        self.type = flag_type   # "bool", "int", or "string"
        self.value = value
        self.offset = offset

    def __repr__(self):
        return f"FFlag(name={self.name!r}, type={self.type!r}, value={self.value!r})"

class FFlagManager:
    def __init__(self, memory_module):
        self._mem = memory_module
        self._base = memory_module.base
        self._offsets = None

    def _ensure_offsets(self):
        if self._offsets is None:
            self._offsets = get_fflag_offsets()

    def _is_module_ptr(self, ptr: int) -> bool:
        return self._base <= ptr < self._base + _MODULE_SIZE_LIMIT

    def _reflect(self, name: str, offset: int):
        addr = self._base + offset
        raw = self._mem.read(addr, 32)
        if len(raw) < 32:
            return "unknown", None

        ptr_at_8 = int.from_bytes(raw[8:16], "little")

        if self._is_module_ptr(ptr_at_8):
            try:
                name_in_mem = self._mem.read_raw_string(ptr_at_8, 256)
            except OSError:
                name_in_mem = ""

            val_at_10 = int.from_bytes(raw[16:20], "little")

            if name_in_mem and val_at_10 == len(name_in_mem):
                return "bool", bool(raw[0])
            else:
                raw_int = int.from_bytes(raw[0:4], "little")
                return "string", _decode_flog(raw_int)
        else:
            str_len = int.from_bytes(raw[16:24], "little")
            str_cap = int.from_bytes(raw[24:32], "little")

            if str_cap == 15 and 0 <= str_len <= 15:
                return "string", self._mem.read_string(addr)

            if (str_cap >= 16 and str_cap < 0x100000
                    and 0 < str_len <= str_cap):
                ptr_at_0 = int.from_bytes(raw[0:8], "little")
                if ptr_at_0 > 0x10000:
                    return "string", self._mem.read_string(addr)

            return "int", int.from_bytes(raw[0:4], "little", signed=True)

    @property
    def offsets(self) -> dict:
        self._ensure_offsets()
        return dict(self._offsets)

    def get(self, name: str) -> FFlag | None:
        self._ensure_offsets()
        offset = self._offsets.get(name)
        if offset is None:
            return None
        flag_type, value = self._reflect(name, offset)
        return FFlag(name, flag_type, value, offset)

    def get_many(self, *names: str) -> dict[str, FFlag]:
        self._ensure_offsets()
        out = {}
        for n in names:
            flag = self.get(n)
            if flag is not None:
                out[n] = flag
        return out

    def get_all(self) -> dict[str, FFlag]:
        self._ensure_offsets()
        out = {}
        for name, offset in self._offsets.items():
            try:
                flag_type, value = self._reflect(name, offset)
                out[name] = FFlag(name, flag_type, value, offset)
            except OSError:
                pass
        return out

    def set(self, name: str, value) -> FFlag:
        self._ensure_offsets()
        offset = self._offsets.get(name)
        if offset is None:
            raise KeyError(name)

        flag_type, _ = self._reflect(name, offset)
        addr = self._base + offset

        if flag_type == "bool":
            if not isinstance(value, (bool, int)):
                raise TypeError(f"Expected bool for flag '{name}', got {type(value).__name__}")
            self._mem.write_bool(addr, bool(value))

        elif flag_type == "int":
            if not isinstance(value, int):
                raise TypeError(f"Expected int for flag '{name}', got {type(value).__name__}")
            self._mem.write_int(addr, value)

        elif flag_type == "string":
            if not isinstance(value, (str, int)):
                raise TypeError(f"Expected str or int for flag '{name}', got {type(value).__name__}")

            _, current = self._reflect(name, offset)
            is_flog = isinstance(current, str) and "," in current

            if is_flog:
                self._mem.write_int(addr, _encode_flog(str(value)) if isinstance(value, str) else value)
            else:
                self._mem.write_string(addr, str(value))

        else:
            raise RuntimeError(f"Cannot write to flag with unknown type '{flag_type}'")

        new_type, new_value = self._reflect(name, offset)
        return FFlag(name, new_type, new_value, offset)

    def __getitem__(self, name: str) -> FFlag:
        flag = self.get(name)
        if flag is None:
            raise KeyError(name)
        return flag
    
    def __getattr__(self, name) -> FFlag:
        flag = self.get(name)
        if flag is None:
            raise AttributeError(f"FFlag '{name}' not found")
        return flag

    def __setitem__(self, name: str, value):
        self.set(name, value)
    
    def __setattr__(self, name: str, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self.set(name, value)

    def __contains__(self, name: str) -> bool:
        self._ensure_offsets()
        return name in self._offsets

    def __repr__(self):
        self._ensure_offsets()
        return f"FFlagManager({len(self._offsets)} flags)"
