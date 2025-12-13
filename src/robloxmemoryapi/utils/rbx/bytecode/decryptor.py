import struct
import zstandard as zstd

def decrypt_rsb1(encrypted_data: bytes) -> bytes:
    """
    Decrypts the RSB1 encrypted bytecode blob.
    """
    if len(encrypted_data) < 8:
        raise ValueError("Data too short to be RSB1")

    data = bytearray(encrypted_data)
    header = b"RSB1"
    
    key = bytearray(4)
    for i in range(4):
        # Calculate the term added to the key
        offset_term = (i * 41) % 256
        
        # XOR difference between expected plaintext and ciphertext
        xor_diff = header[i] ^ data[i]
        
        # Recover key byte (handling modulo 256 wrapping)
        k_byte = (xor_diff - offset_term) % 256
        key[i] = k_byte

    # Decrypt the entire buffer
    decrypted = bytearray(len(data))
    for i in range(len(data)):
        # Reconstruct the encryption byte
        enc_byte = (key[i % 4] + i * 41) % 256
        decrypted[i] = data[i] ^ enc_byte

    # Verify header
    if decrypted[:4] != b"RSB1":
        raise ValueError("Decryption failed: Header mismatch")

    return bytes(decrypted)

def decode_bytecode(raw_bytes: bytes):
    # 1. Decrypt
    try:
        decrypted = decrypt_rsb1(raw_bytes)
    except Exception as e:
        return None

    # 2. Extract Compressed Data
    # Header is "RSB1" (4 bytes) + Uncompressed Size (4 bytes)
    # Compressed data starts at offset 8
    if len(decrypted) < 8:
        return None

    uncompressed_size = struct.unpack("<I", decrypted[4:8])[0]
    compressed_payload = decrypted[8:]
    
    # 3. Decompress
    dctx = zstd.ZstdDecompressor()
    try:
        luau_bytecode = dctx.decompress(compressed_payload, max_output_size=uncompressed_size)
    except zstd.ZstdError as e:
        return
    
    return luau_bytecode