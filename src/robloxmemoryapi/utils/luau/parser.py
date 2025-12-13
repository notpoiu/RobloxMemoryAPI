import struct

# Roblox/Luau bytecode disassembly helpers separated for reuse.
LOP_CAPTURE = 70
OPCODE_MULTIPLIER = 227
OPCODE_DEOBFUSCATE = 203  # inverse of 227 mod 256

class LuauBytecodeStream:
    def __init__(self, data):
        self.data = bytearray(data)
        self.pos = 0

    def _ensure_available(self, n: int):
        if self.pos + n > len(self.data):
            raise IndexError(
                f"Attempted to read {n} bytes at pos {self.pos}, but only {len(self.data) - self.pos} remain"
            )

    def read_byte(self):
        self._ensure_available(1)
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_bytes(self, n):
        self._ensure_available(n)
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def read_varint(self):
        result = 0
        shift = 0
        while True:
            byte = self.read_byte()
            result |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                break
        return result

    def write_byte(self, val, pos=None):
        if pos is None:
            self.data.append(val)
        else:
            self.data[pos] = val

    def write_bytes(self, val):
        self.data.extend(val)

    def write_varint(self, val):
        while True:
            byte = val & 0x7F
            val >>= 7
            if val:
                byte |= 0x80
                self.data.append(byte)
            else:
                self.data.append(byte)
                break


def decode_instruction(insn, deobfuscate_opcodes=True):
    """
    Convert Roblox-obfuscated opcode back to Luau opcode using the inverse multiplier (203).
    """
    if deobfuscate_opcodes:
        op = insn & 0xFF
        new_op = (op * OPCODE_DEOBFUSCATE) % 256
        insn = (insn & 0xFFFFFF00) | new_op
    return insn


def encode_instruction(insn, obfuscate_opcodes=True):
    # Decode to inspect/mutate in Luau space
    op = insn & 0xFF

    # Modify LOP_CAPTURE - May not be needed? I'm not liable for client modification bans anyways so i dont care
    """if op == LOP_CAPTURE:
        # Check Capture Type (A)
        # A is bits 8-15
        capture_type = (insn >> 8) & 0xFF
        if capture_type == 1:  # LCT_REF
            # Set MSB (unused byte) to non-zero (e.g., 0xFF)
            # Check if MSB is 0
            if (insn & 0xFF000000) == 0:
                insn |= 0xFF000000"""

    # Encode Opcode back to Roblox-obfuscated form
    if obfuscate_opcodes:
        new_op = (op * OPCODE_MULTIPLIER) % 256
        insn = (insn & 0xFFFFFF00) | new_op

    return insn


def read_constant(stream: LuauBytecodeStream, version: int):
    full_ctype = stream.read_byte()
    ctype = full_ctype & 0x7  # Roblox sometimes packs extra flags in the upper bits; the low 3 bits hold the luau tag.

    if ctype == 0:  # NIL
        return
    elif ctype == 1:  # BOOLEAN
        stream.read_byte()
    elif ctype == 2:  # NUMBER
        stream.read_bytes(8)
    elif ctype == 3:  # STRING
        stream.read_varint()  # String index
    elif ctype == 4:  # IMPORT
        # Import ids are written as 32-bit values
        stream.read_bytes(4)
    elif ctype == 5:  # TABLE
        # Roblox/Luau encodes table constants using constant *indices* (not nested constants).
        array_size = stream.read_varint()
        hash_size = stream.read_varint()

        for _ in range(array_size):
            stream.read_varint()  # value const index

        for _ in range(hash_size):
            stream.read_varint()  # key const index
            stream.read_varint()  # value const index
    elif ctype == 6:  # CLOSURE
        stream.read_varint()  # Proto index
    elif ctype == 7:  # VECTOR
        stream.read_bytes(16)
    else:
        raise ValueError(f"Unknown constant type: base={ctype} full={full_ctype} at pos {stream.pos}")


def _process_proto(stream, version, read_type_section=True, read_flags=True):
    # Proto Header
    max_stack = stream.read_byte()
    num_params = stream.read_byte()
    num_upvalues = stream.read_byte()
    is_vararg = stream.read_byte()

    if version >= 4 and read_flags:
        # Flags/Type info can be missing in some Roblox blobs; guarded by flags/read_type_section.
        flags = stream.read_byte()

        if read_type_section:
            type_size = stream.read_varint()
            stream.read_bytes(type_size)

    # Instructions
    num_insns = stream.read_varint()
    # Validate we have enough bytes for the declared instructions; fallback will handle failures.
    remaining = len(stream.data) - stream.pos
    if num_insns * 4 > remaining:
        raise IndexError(
            f"Instruction section overruns buffer: need {num_insns*4} bytes, have {remaining} at pos {stream.pos}"
        )
    for _ in range(num_insns):
        # Read instruction (4 bytes)
        insn_pos = stream.pos
        insn_bytes = stream.read_bytes(4)
        raw_insn = struct.unpack("<I", insn_bytes)[0]

        # Convert Roblox-obfuscated opcode back to Luau to inspect/mutate safely
        decoded_insn = decode_instruction(raw_insn)

        # Encode
        new_insn = encode_instruction(decoded_insn)

        # Write back (in place)
        new_bytes = struct.pack("<I", new_insn)
        stream.data[insn_pos:insn_pos + 4] = new_bytes

    # Constants
    num_consts = stream.read_varint()
    for _ in range(num_consts):
        read_constant(stream, version)

    # Inner Protos
    # These are just indices to the child protos, not the protos themselves.
    num_child_protos = stream.read_varint()
    for _ in range(num_child_protos):
        stream.read_varint()  # Child proto index

    # Line Defined
    stream.read_varint()

    # Debug Name (string table index)
    stream.read_varint()

    # Line Info / Debug
    linegap_log2 = stream.read_byte()
    if linegap_log2 != 0xFF:  # 0xFF denotes stripped line info in Luau
        lineinfo_entries = (num_insns + (1 << linegap_log2) - 1) >> linegap_log2
        stream.read_bytes(lineinfo_entries)

        abslineinfo_entries = stream.read_varint()
        for _ in range(abslineinfo_entries):
            stream.read_varint()  # pc
            stream.read_varint()  # line

    # Locals
    locvar_count = stream.read_varint()
    for _ in range(locvar_count):
        stream.read_varint()  # local name
        stream.read_varint()  # start pc
        stream.read_varint()  # end pc
        stream.read_varint()  # register

    # Upvalues (debug names + descriptors)
    upvalue_debug_count = stream.read_varint()
    for _ in range(upvalue_debug_count):
        # Debug info, not used for mutation; consume safely.
        stream.read_varint()  # upvalue name
        stream.read_byte()  # instack
        stream.read_byte()  # index/kind


def process_proto(stream, version):
    """
    Parse and mutate a proto. Some Roblox bytecode blobs omit the type info
    section even on version >= 4. If parsing with type info fails due to
    length issues, retry without consuming the type section.
    """
    start_pos = stream.pos
    try:
        _process_proto(stream, version, read_type_section=True, read_flags=True)
    except IndexError:
        # Retry without type and flags if the stream ran out unexpectedly.
        stream.pos = start_pos
        try:
            _process_proto(stream, version, read_type_section=False, read_flags=True)
        except IndexError:
            stream.pos = start_pos
            try:
                _process_proto(stream, version, read_type_section=False, read_flags=False)
            except IndexError:
                # Give up gracefully: mark stream as consumed to avoid infinite loops.
                stream.pos = len(stream.data)


def _decode_utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def disassemble_pretty(raw_bytecode: bytes):
    """
    Return a structured view of the Luau bytecode header sections for quick inspection.

    The current output shape is:
    {
        "Version": {"Bytecode": int, "Types": int},
        "Strings": [<str>],
        "UserdataTypes": [{"Index": int, "Name": str}],
        "ProtoCount": int,
        "MainProtoIndex": int,
    }
    """
    stream = LuauBytecodeStream(raw_bytecode)

    # Versions
    bytecode_version = stream.read_byte()
    types_version = stream.read_byte()

    # Strings
    num_strings = stream.read_varint()
    strings = []
    for _ in range(num_strings):
        length = stream.read_varint()
        data = stream.read_bytes(length)
        strings.append(_decode_utf8(data))

    # Userdata Types (terminates with 0 byte)
    userdata_types = []
    while True:
        idx = stream.read_byte()
        if idx == 0:
            break
        name_len = stream.read_varint()
        name = _decode_utf8(stream.read_bytes(name_len))
        userdata_types.append({"Index": idx, "Name": name})

    # Function table header (only count; does not mutate)
    num_protos = stream.read_varint()

    # Skip over protos to reach main proto index.
    for _ in range(num_protos):
        # Reuse proto parser on a copy to avoid altering the caller's buffer.
        proto_start = stream.pos
        scratch = LuauBytecodeStream(stream.data[proto_start:])
        process_proto(scratch, bytecode_version)
        stream.pos = proto_start + scratch.pos

    main_proto_index = stream.read_varint()

    return {
        "Version": {"Bytecode": bytecode_version, "Types": types_version},
        "Strings": strings,
        "UserdataTypes": userdata_types,
        "ProtoCount": num_protos,
        "MainProtoIndex": main_proto_index,
    }
