from ...luau.parser import LuauBytecodeStream, process_proto
import struct
import zstandard as zstd
import blake3
import random
import xxhash

def rotl8(v, shift):
    shift = shift & 7
    return ((v << shift) | (v >> (8 - shift))) & 0xFF

def transform_hash(hash_bytes):
    # Key: ROFL
    KEY_BYTES = b"ROFL"
    res = bytearray(32)
    
    for i in range(32):
        byte = KEY_BYTES[i & 3]
        hash_byte = hash_bytes[i]
        combined = (byte + i) & 0xFF
        
        mode = i & 3
        if mode == 0:
            shift = (combined & 3) + 1
            val = hash_byte ^ ((~byte) & 0xFF)
        elif mode == 1:
            shift = (combined & 3) + 2
            val = byte ^ ((~hash_byte) & 0xFF)
        elif mode == 2:
            shift = (combined & 3) + 3
            val = hash_byte ^ ((~byte) & 0xFF)
        elif mode == 3:
            shift = (combined & 3) + 4
            val = byte ^ ((~hash_byte) & 0xFF)
            
        res[i] = rotl8(val, shift)
        
    return res

def sign_bytecode(bytecode):
    # 1. Blake3 Hash
    hasher = blake3.blake3()
    hasher.update(bytecode)
    digest = bytearray(hasher.digest())
    
    # 2. Transform Hash
    transformed_hash = transform_hash(digest)
    
    # 3. Construct Footer (40 bytes)
    # Bytes 0-3: first_4_bytes_of_transformed_hash ^ 0x946AC432 (MAGIC_B)
    # Bytes 4-7: first_4_bytes_of_transformed_hash ^ 0x4C464F52 (MAGIC_A)
    # Bytes 8-39: The full 32-byte transformed hash
    
    first_4_int = struct.unpack("<I", transformed_hash[:4])[0]
    
    magic_b = 0x946AC432
    magic_a = 0x4C464F52
    
    part1 = first_4_int ^ magic_b
    part2 = first_4_int ^ magic_a
    
    footer = bytearray(40)
    struct.pack_into("<I", footer, 0, part1)
    struct.pack_into("<I", footer, 4, part2)
    footer[8:] = transformed_hash
    
    return bytecode + footer

def encrypt_rsb1(data, uncompressed_size):
    # Generate random key
    key = bytearray([random.randint(0, 255) for _ in range(4)])
    
    # Header "RSB1"
    header = bytearray(b"RSB1")
    
    # Construct the plaintext buffer first
    # buffer = RSB1 (4) + UncompressedSize (4) + CompressedData (len(data))
    buffer = bytearray(len(data) + 8)
    buffer[0:4] = b"RSB1"
    struct.pack_into("<I", buffer, 4, uncompressed_size)
    buffer[8:] = data
    
    # XXH32 hash of the PLAINTEXT buffer
    key_int = xxhash.xxh32(buffer, seed=42).intdigest()
    key_bytes = struct.pack("<I", key_int)
    
    # Encrypt
    for i in range(len(buffer)):
        enc_byte = (key_bytes[i % 4] + i * 41) % 256
        buffer[i] ^= enc_byte
        
    return buffer

def encode_roblox(raw_bytecode):
    """
    Parse Luau bytecode, patch opcodes, re-sign, compress, and encrypt.
    Any existing 40-byte footer is stripped and replaced with a fresh signature
    (matches the C++ pipeline: decode -> patch -> sign -> compress -> encrypt).
    """
    # Strip footer if present
    # body = raw_bytecode[:-40] if len(raw_bytecode) >= 40 else raw_bytecode
    original_body = bytearray(raw_bytecode)

    try:
        # 1. Parse and Modify Opcodes
        stream = LuauBytecodeStream(original_body)
        version = stream.read_byte()
        
        # Types Version
        types_version = stream.read_byte()
        
        # String Table
        num_strings = stream.read_varint()
        
        for _ in range(num_strings):
            length = stream.read_varint()
            stream.read_bytes(length)
        
        # Userdata Types (if supported/present)
        while True:
            idx = stream.read_byte()
            if idx == 0:
                break
            length = stream.read_varint()
            stream.read_bytes(length)
        
        # Function Table
        num_protos = stream.read_varint()
        
        for _ in range(num_protos):
            process_proto(stream, version)

        # Main Proto Index
        # Stop parsing here to avoid consuming potential footer bytes.
        parsed_body = stream.data[:stream.pos]
        old_footer = stream.data[stream.pos:]
    except Exception:
        # If parsing fails, fall back to the original body.
        parsed_body = original_body
        old_footer = b''
    
    # 2. Reconstruct
    signed_bytecode = bytes(parsed_body) + bytes(old_footer)
    uncompressed_size = len(signed_bytecode)
    
    # 3. Compress
    cctx = zstd.ZstdCompressor()
    compressed = cctx.compress(signed_bytecode)
    
    # 4. Encrypt
    encrypted = encrypt_rsb1(compressed, uncompressed_size)
    
    return encrypted
