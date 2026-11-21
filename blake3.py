"""Minimal pure-Python BLAKE3 (hash mode only), after the reference implementation. Used for IoStore chunk hashes."""
import struct
IV = [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19]
PERM = [2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8]
CHUNK_START, CHUNK_END, PARENT, ROOT = 1, 2, 4, 8
M32 = 0xFFFFFFFF
def _g(s, a, b, c, d, x, y):
    s[a] = (s[a] + s[b] + x) & M32; s[d] ^= s[a]; s[d] = ((s[d] >> 16) | (s[d] << 16)) & M32
    s[c] = (s[c] + s[d]) & M32; s[b] ^= s[c]; s[b] = ((s[b] >> 12) | (s[b] << 20)) & M32
    s[a] = (s[a] + s[b] + y) & M32; s[d] ^= s[a]; s[d] = ((s[d] >> 8) | (s[d] << 24)) & M32
    s[c] = (s[c] + s[d]) & M32; s[b] ^= s[c]; s[b] = ((s[b] >> 7) | (s[b] << 25)) & M32
def _compress(cv, block, counter, blen, flags):
    m = list(struct.unpack("<16I", block))
    s = cv[:8] + IV[:4] + [counter & M32, (counter >> 32) & M32, blen, flags]
    for r in range(7):
        _g(s, 0, 4, 8, 12, m[0], m[1]); _g(s, 1, 5, 9, 13, m[2], m[3]); _g(s, 2, 6, 10, 14, m[4], m[5]); _g(s, 3, 7, 11, 15, m[6], m[7])
        _g(s, 0, 5, 10, 15, m[8], m[9]); _g(s, 1, 6, 11, 12, m[10], m[11]); _g(s, 2, 7, 8, 13, m[12], m[13]); _g(s, 3, 4, 9, 14, m[14], m[15])
        if r < 6: m = [m[i] for i in PERM]
    return [s[i] ^ s[i + 8] for i in range(8)] + [s[i + 8] ^ cv[i] for i in range(8)]
def _chunk_output(data, counter):
    cv = IV[:]; blocks = [data[i:i + 64] for i in range(0, len(data), 64)] or [b""]
    for k, b in enumerate(blocks):
        flags = (CHUNK_START if k == 0 else 0) | (CHUNK_END if k == len(blocks) - 1 else 0)
        if k < len(blocks) - 1: cv = _compress(cv, b, counter, 64, flags)[:8]
        else: return (cv, b.ljust(64, b"\0"), counter, len(b), flags)
def _cv(out): cv, block, counter, blen, flags = out; return _compress(cv, block, counter, blen, flags)[:8]
def _parent(left, right): return (IV[:], struct.pack("<16I", *(left + right)), 0, 64, PARENT)
def blake3(data, length=32):
    chunks = [data[i:i + 1024] for i in range(0, len(data), 1024)] or [b""]
    stack = []
    for n, c in enumerate(chunks[:-1]):
        cv = _cv(_chunk_output(c, n)); total = n + 1
        while total & 1 == 0: cv = _cv(_parent(stack.pop(), cv)); total >>= 1
        stack.append(cv)
    out = _chunk_output(chunks[-1], len(chunks) - 1)
    while stack: out = _parent(stack.pop(), _cv(out))
    cv, block, counter, blen, flags = out
    res = b""; i = 0
    while len(res) < length:
        res += struct.pack("<16I", *_compress(cv, block, i, blen, flags | ROOT)); i += 1
    return res[:length]
