"""Read a cooked StringTable (.uexp) into {key: text}."""
import struct
def read(uexp_path):
    e = open(uexp_path, "rb").read()
    def fs(p):
        n = struct.unpack_from("<i", e, p)[0]
        if n < 0: m = -n * 2; return e[p + 4:p + 4 + m].decode("utf-16le")[:-1], p + 4 + m
        return e[p + 4:p + 4 + n].decode("latin1")[:-1], p + 4 + n
    for p in range(0, 200):
        try:
            s, q = fs(p)
            if not (s and s.isprintable() and len(s) > 3): continue
            c = struct.unpack_from("<i", e, q)[0]
            if not 0 < c < 50000: continue
            r = q + 4; out = {}
            for _ in range(c):
                k, r = fs(r); v, r = fs(r); out[k] = v
            return out
        except (UnicodeDecodeError, struct.error): pass
    raise ValueError("string table not parsed: " + uexp_path)
