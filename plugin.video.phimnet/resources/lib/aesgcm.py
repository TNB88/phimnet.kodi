# -*- coding: utf-8 -*-

"""Small pure-Python AES-256-GCM implementation.

Kodi does not guarantee that OpenSSL wrappers such as ``cryptography`` or
PyCryptodome are installed.  The Phim Net signer only encrypts a short local
value once per playback, so this compact dependency-free implementation is
fast enough and keeps the addon portable across Kodi platforms.
"""

import hmac


_SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)


def _xtime(value):
    return ((value << 1) ^ (0x1B if value & 0x80 else 0)) & 0xFF


def _expand_key(key):
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    words = [list(key[index:index + 4]) for index in range(0, 32, 4)]
    rcon = 1
    for index in range(8, 60):
        temp = list(words[index - 1])
        if index % 8 == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[value] for value in temp]
            temp[0] ^= rcon
            rcon = _xtime(rcon)
        elif index % 8 == 4:
            temp = [_SBOX[value] for value in temp]
        words.append([words[index - 8][offset] ^ temp[offset] for offset in range(4)])
    return [sum(words[index:index + 4], []) for index in range(0, 60, 4)]


def _add_round_key(state, round_key):
    return [value ^ round_key[index] for index, value in enumerate(state)]


def _shift_rows(state):
    shifted = list(state)
    for row in range(1, 4):
        values = [state[row + 4 * column] for column in range(4)]
        for column in range(4):
            shifted[row + 4 * column] = values[(column + row) % 4]
    return shifted


def _mix_columns(state):
    mixed = list(state)
    for column in range(4):
        offset = column * 4
        a0, a1, a2, a3 = state[offset:offset + 4]
        total = a0 ^ a1 ^ a2 ^ a3
        mixed[offset] = a0 ^ total ^ _xtime(a0 ^ a1)
        mixed[offset + 1] = a1 ^ total ^ _xtime(a1 ^ a2)
        mixed[offset + 2] = a2 ^ total ^ _xtime(a2 ^ a3)
        mixed[offset + 3] = a3 ^ total ^ _xtime(a3 ^ a0)
    return mixed


class _AES256(object):
    def __init__(self, key):
        self.round_keys = _expand_key(key)

    def encrypt_block(self, block):
        if len(block) != 16:
            raise ValueError("AES block must contain 16 bytes")
        state = _add_round_key(list(block), self.round_keys[0])
        for round_index in range(1, 14):
            state = [_SBOX[value] for value in state]
            state = _shift_rows(state)
            state = _mix_columns(state)
            state = _add_round_key(state, self.round_keys[round_index])
        state = [_SBOX[value] for value in state]
        state = _shift_rows(state)
        state = _add_round_key(state, self.round_keys[14])
        return bytes(state)


def _multiply_gf128(x_value, y_value):
    result = 0
    current = y_value
    reduction = 0xE1000000000000000000000000000000
    for bit in range(128):
        if (x_value >> (127 - bit)) & 1:
            result ^= current
        current = (current >> 1) ^ (reduction if current & 1 else 0)
    return result


def _ghash(hash_subkey, ciphertext):
    value = 0
    padded_length = ((len(ciphertext) + 15) // 16) * 16
    padded = ciphertext + (b"\x00" * (padded_length - len(ciphertext)))
    length_block = (0).to_bytes(8, "big") + (len(ciphertext) * 8).to_bytes(8, "big")
    for offset in range(0, len(padded), 16):
        block = int.from_bytes(padded[offset:offset + 16], "big")
        value = _multiply_gf128(value ^ block, hash_subkey)
    value = _multiply_gf128(value ^ int.from_bytes(length_block, "big"), hash_subkey)
    return value.to_bytes(16, "big")


def _increment_counter(counter):
    prefix = counter[:12]
    suffix = (int.from_bytes(counter[12:], "big") + 1) & 0xFFFFFFFF
    return prefix + suffix.to_bytes(4, "big")


def encrypt(key, nonce, plaintext):
    """Return AES-256-GCM ciphertext followed by the 16-byte tag."""
    if len(nonce) != 12:
        raise ValueError("This signer requires a 12-byte GCM nonce")
    aes = _AES256(key)
    initial_counter = nonce + b"\x00\x00\x00\x01"
    counter = initial_counter
    ciphertext = bytearray()
    for offset in range(0, len(plaintext), 16):
        counter = _increment_counter(counter)
        stream = aes.encrypt_block(counter)
        block = plaintext[offset:offset + 16]
        ciphertext.extend(bytes(value ^ stream[index] for index, value in enumerate(block)))
    ciphertext = bytes(ciphertext)
    hash_subkey = int.from_bytes(aes.encrypt_block(b"\x00" * 16), "big")
    authentication = _ghash(hash_subkey, ciphertext)
    tag_mask = aes.encrypt_block(initial_counter)
    tag = bytes(left ^ right for left, right in zip(authentication, tag_mask))
    return ciphertext + tag


def decrypt(key, nonce, ciphertext_and_tag):
    """Verify and decrypt AES-256-GCM ciphertext followed by a 16-byte tag."""
    if len(nonce) != 12:
        raise ValueError("This implementation requires a 12-byte GCM nonce")
    if len(ciphertext_and_tag) < 16:
        raise ValueError("AES-GCM payload is too short")
    ciphertext, supplied_tag = ciphertext_and_tag[:-16], ciphertext_and_tag[-16:]
    aes = _AES256(key)
    initial_counter = nonce + b"\x00\x00\x00\x01"
    hash_subkey = int.from_bytes(aes.encrypt_block(b"\x00" * 16), "big")
    authentication = _ghash(hash_subkey, ciphertext)
    tag_mask = aes.encrypt_block(initial_counter)
    expected_tag = bytes(left ^ right for left, right in zip(authentication, tag_mask))
    if not hmac.compare_digest(supplied_tag, expected_tag):
        raise ValueError("AES-GCM authentication failed")

    counter = initial_counter
    plaintext = bytearray()
    for offset in range(0, len(ciphertext), 16):
        counter = _increment_counter(counter)
        stream = aes.encrypt_block(counter)
        block = ciphertext[offset:offset + 16]
        plaintext.extend(bytes(value ^ stream[index] for index, value in enumerate(block)))
    return bytes(plaintext)
