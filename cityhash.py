"""CityHash64 (the version Unreal Engine uses for package ids, container ids and zen name hashes)."""
M = (1 << 64) - 1
k0, k1, k2 = 0xc3a5c85c97cb3127, 0xb492b66fbe98f273, 0x9ae16a3b2f90404f
def _f64(b, i): return int.from_bytes(b[i:i + 8], "little")
def _f32(b, i): return int.from_bytes(b[i:i + 4], "little")
def _rot(v, s): return ((v >> s) | (v << (64 - s))) & M if s else v
def _smix(v): return (v ^ (v >> 47)) & M
def _bswap(v): return int.from_bytes((v & M).to_bytes(8, "big"), "little")
def _h16(u, v, mul=0x9ddfea08eb382d69):
    a = ((u ^ v) * mul) & M; a ^= a >> 47
    b = ((v ^ a) * mul) & M; b ^= b >> 47
    return (b * mul) & M
def _h0to16(s):
    n = len(s)
    if n >= 8:
        mul = (k2 + n * 2) & M; a = (_f64(s, 0) + k2) & M; b = _f64(s, n - 8)
        return _h16((_rot(b, 37) * mul + a) & M, ((_rot(a, 25) + b) * mul) & M, mul)
    if n >= 4:
        mul = (k2 + n * 2) & M
        return _h16((n + (_f32(s, 0) << 3)) & M, _f32(s, n - 4), mul)
    if n > 0:
        y = s[0] + (s[n >> 1] << 8); z = n + (s[n - 1] << 2)
        return (_smix((y * k2 ^ z * k0) & M) * k2) & M
    return k2
def _h17to32(s):
    n = len(s); mul = (k2 + n * 2) & M
    a = (_f64(s, 0) * k1) & M; b = _f64(s, 8); c = (_f64(s, n - 8) * mul) & M; d = (_f64(s, n - 16) * k2) & M
    return _h16((_rot((a + b) & M, 43) + _rot(c, 30) + d) & M, (a + _rot((b + k2) & M, 18) + c) & M, mul)
def _wh32(w, x, y, z, a, b):
    a = (a + w) & M; b = _rot((b + a + z) & M, 21); c = a
    a = (a + x) & M; a = (a + y) & M; b = (b + _rot(a, 44)) & M
    return ((a + z) & M, (b + c) & M)
def _wh32s(s, i, a, b): return _wh32(_f64(s, i), _f64(s, i + 8), _f64(s, i + 16), _f64(s, i + 24), a, b)
def _h33to64(s):
    n = len(s); mul = (k2 + n * 2) & M
    a = (_f64(s, 0) * k2) & M; b = _f64(s, 8); c = _f64(s, n - 24); d = _f64(s, n - 32)
    e = (_f64(s, 16) * k2) & M; f = (_f64(s, 24) * 9) & M; g = _f64(s, n - 8); h = (_f64(s, n - 16) * mul) & M
    u = (_rot((a + g) & M, 43) + (_rot(b, 30) + c) * 9) & M
    v = (((a + g) ^ d) + f + 1) & M
    w = (_bswap((u + v) * mul) + h) & M
    x = (_rot((e + f) & M, 42) + c) & M
    y = ((_bswap((v + w) * mul) + g) * mul) & M
    z = (e + f + c) & M
    a = (_bswap(((x + z) * mul + y) & M) + b) & M
    b = (_smix((z + a) * mul + d + h & M) * mul) & M
    return (b + x) & M
def cityhash64(s):
    n = len(s)
    if n <= 32: return _h0to16(s) if n <= 16 else _h17to32(s)
    if n <= 64: return _h33to64(s)
    x = _f64(s, n - 40); y = (_f64(s, n - 16) + _f64(s, n - 56)) & M
    z = _h16((_f64(s, n - 48) + n) & M, _f64(s, n - 24))
    v = _wh32s(s, n - 64, n, z); w = _wh32s(s, n - 32, (y + k1) & M, x)
    x = (x * k1 + _f64(s, 0)) & M
    ln = (n - 1) & ~63; i = 0
    while True:
        x = (_rot((x + y + v[0] + _f64(s, i + 8)) & M, 37) * k1) & M
        y = (_rot((y + v[1] + _f64(s, i + 48)) & M, 42) * k1) & M
        x ^= w[1]; y = (y + v[0] + _f64(s, i + 40)) & M
        z = (_rot((z + w[0]) & M, 33) * k1) & M
        v = _wh32s(s, i, (v[1] * k1) & M, (x + w[0]) & M)
        w = _wh32s(s, i + 32, (z + w[1]) & M, (y + _f64(s, i + 16)) & M)
        z, x = x, z
        i += 64; ln -= 64
        if ln == 0: break
    return _h16((_h16(v[0], w[0]) + _smix(y) * k1 + z) & M, (_h16(v[1], w[1]) + x) & M)
def package_id(name): return cityhash64(name.lower().encode("utf-16-le"))
