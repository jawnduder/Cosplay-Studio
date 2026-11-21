"""Read / write cooked UE 5.4 legacy packages (.uasset header + .uexp export data), the layout retoc to-legacy and
UAssetGUI produce for Clair Obscur. Only what Cosplay Studio needs: summary, name map (with UE name hashes), imports,
exports, depends map, asset registry block, preload dependencies. Export data (.uexp) is handled as raw bytes."""
import struct, zlib

TAG = 0x9E2A83C1
def _crc_table():
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8): c = ((c << 1) ^ 0x04C11DB7) if c & 0x80000000 else (c << 1)
        t.append(c & 0xFFFFFFFF)
    return t
_T = _crc_table()
def name_hashes(s):
    """(non-case-preserving, case-preserving) 16-bit hashes as stored after each name."""
    h = 0
    for ch in s: h = ((h >> 8) & 0x00FFFFFF) ^ _T[(h ^ ord(ch.upper())) & 0xFF]
    c = zlib.crc32(b"".join(ord(ch).to_bytes(4, "little") for ch in s))
    return h & 0xFFFF, c & 0xFFFF

class R:
    def __init__(self, b, o=0): self.b, self.o = b, o
    def u(self, f):
        v = struct.unpack_from("<" + f, self.b, self.o); self.o += struct.calcsize("<" + f); return v if len(v) > 1 else v[0]
    def fstr(self):
        n = self.u("i")
        if n == 0: return ""
        if n > 0: s = self.b[self.o:self.o + n - 1].decode("latin-1"); self.o += n; return s
        s = self.b[self.o:self.o - 2 * n - 2].decode("utf-16-le"); self.o += -2 * n; return s
def wstr(s):
    if s == "": return struct.pack("<i", 0)
    try: b = s.encode("ascii"); return struct.pack("<i", len(b) + 1) + b + b"\0"
    except UnicodeEncodeError: b = s.encode("utf-16-le"); return struct.pack("<i", -(len(b) // 2 + 1)) + b + b"\0\0"

class Package:
    """names: [str]; imports: [(class_package, class_name, outer, object_name, optional)]; exports: [dict];
    export data: one bytes blob per export (concatenated in the .uexp, followed by the package tag)."""
    def __init__(self): self.names, self.imports, self.exports, self.data = [], [], [], []
    # ---------------- names
    def nidx(self, s):
        """FName -> (index, number). "Foo_12" is stored as "Foo" number 13 unless "Foo_12" itself is in the map."""
        if s in self.names: return self.names.index(s), 0
        base, _, num = s.rpartition("_")
        if base and num.isdigit() and not (len(num) > 1 and num[0] == "0") and base in self.names: return self.names.index(base), int(num) + 1
        self.names.append(s); return len(self.names) - 1, 0
    def name(self, idx, num): return self.names[idx] if num == 0 else "%s_%d" % (self.names[idx], num - 1)
    # ---------------- read
    @classmethod
    def read(cls, uasset_bytes, uexp_bytes):
        p = cls(); r = R(uasset_bytes)
        tag, legacy, ue3, ue4, ue5, lic, ncustom = r.u("Iiiiiii"); assert tag == TAG and legacy == -8 and ncustom == 0
        p.total = r.u("i"); p.folder = r.fstr(); p.flags = r.u("I")
        name_count, name_off, soft_count, soft_off, gather_count, gather_off = r.u("iiiiii")
        exp_count, exp_off, imp_count, imp_off, depends_off, softpkg_count, softpkg_off, search_off, thumb_off = r.u("iiiiiiiii")
        p.guid = r.b[r.o:r.o + 16]; r.o += 16
        ngen = r.u("i"); r.o += 8 * ngen
        r.o += 14 * 2                                                       # saved / compatible engine versions (empty)
        compflags, compchunks, p.pkg_source, addpkgs = r.u("IiIi"); assert compchunks == 0 and addpkgs == 0
        assetreg_off, bulk_start, world_tile = r.u("iqi")
        nchunk = r.u("i"); p.chunks = [r.u("i") for _ in range(nchunk)]
        preload_count, preload_off, p.names_ref = r.u("iii"); payload_toc, datares_off = r.u("qi")
        assert soft_count == 0 and gather_count == 0 and softpkg_count == 0
        r.o = name_off
        for _ in range(name_count):
            p.names.append(r.fstr()); r.o += 4
        r.o = imp_off
        for _ in range(imp_count):
            cpi, cpn, cni, cnn, outer, oni, onn, opt = r.u("iiiiiiii")
            p.imports.append([p.name(cpi, cpn), p.name(cni, cnn), outer, p.name(oni, onn), opt])
        r.o = exp_off
        for _ in range(exp_count):
            v = r.u("iiiiiiIqqiiiiIiiiiiiii")
            p.exports.append(dict(cls=v[0], sup=v[1], tmpl=v[2], outer=v[3], name=p.name(v[4], v[5]), flags=v[6], size=v[7], offset=v[8],
                                  forced=v[9], not_client=v[10], not_server=v[11], inherited=v[12], pkg_flags=v[13], not_always=v[14],
                                  is_asset=v[15], public_hash=v[16], first_dep=v[17], deps_counts=list(v[18:22])))
        r.o = depends_off; p.depends = []
        for _ in range(exp_count):
            n = r.u("i"); p.depends.append([r.u("i") for _ in range(n)])
        p.assetreg = uasset_bytes[assetreg_off:preload_off]                 # asset registry block, kept raw
        r.o = preload_off; pre = [r.u("i") for _ in range(preload_count)]
        for e in p.exports:
            e["deps"] = []; o = e["first_dep"]
            for n in e["deps_counts"]: e["deps"].append(pre[o:o + n] if o >= 0 else []); o += n
        for e in p.exports:
            o = e["offset"] - p.total
            p.data.append(uexp_bytes[o:o + e["size"]])
        return p
    # ---------------- write
    def write(self, folder=None):
        folder = folder or self.folder
        for e in self.exports: self.nidx(e["name"])
        for im in self.imports: self.nidx(im[0]); self.nidx(im[1]); self.nidx(im[3])
        names = b"".join(wstr(s) + struct.pack("<HH", *name_hashes(s)) for s in self.names)
        def fn(s): return struct.pack("<ii", *self.nidx(s))
        imports = b"".join(fn(a) + fn(b) + struct.pack("<i", outer) + fn(o) + struct.pack("<i", opt) for a, b, outer, o, opt in self.imports)
        preload, exp_rows = [], []
        for e in self.exports:
            deps = e.get("deps") or [[], [], [], []]
            first = len(preload) if any(deps) else -1
            for lst in deps: preload += lst
            e["_first"], e["_counts"] = first, [len(x) for x in deps]
        depends = b"".join(struct.pack("<i", len(x)) + b"".join(struct.pack("<i", v) for v in x) for x in (getattr(self, "depends", None) or [[] for _ in self.exports]))
        assetreg = getattr(self, "assetreg", b"\0\0\0\0")
        fixed = 4 * 7 + 4 + len(wstr(folder)) + 4 + 4 * 6 + 4 * 9 + 16 + 4 + 8 * 1 + 28 + 16 + 16 + 4 + 4 * len(getattr(self, "chunks", [])) + 12 + 12
        name_off = fixed; imp_off = name_off + len(names); exp_off = imp_off + len(imports)
        depends_off = exp_off + 96 * len(self.exports); assetreg_off = depends_off + len(depends)
        preload_off = assetreg_off + len(assetreg); total = preload_off + 4 * len(preload)
        off = total
        for e, blob in zip(self.exports, self.data): e["_size"], e["_off"] = len(blob), off; off += len(blob)
        exports = b"".join(struct.pack("<iiii", e["cls"], e["sup"], e["tmpl"], e["outer"]) + fn(e["name"]) +
                           struct.pack("<Iqqiiii", e["flags"], e["_size"], e["_off"], e["forced"], e["not_client"], e["not_server"], e["inherited"]) +
                           struct.pack("<Iiiii", e["pkg_flags"], e["not_always"], e["is_asset"], e["public_hash"], e["_first"]) +
                           struct.pack("<4i", *e["_counts"]) for e in self.exports)
        uexp = b"".join(self.data) + struct.pack("<I", TAG)
        h = struct.pack("<Iiiiiii", TAG, -8, 0, 0, 0, 0, 0) + struct.pack("<i", total) + wstr(folder) + struct.pack("<I", getattr(self, "flags", 0x80002200))
        h += struct.pack("<iiiiii", len(self.names), name_off, 0, imp_off, 0, 0)
        h += struct.pack("<iiiiiiiii", len(self.exports), exp_off, len(self.imports), imp_off, depends_off, 0, 0, 0, 0)
        h += getattr(self, "guid", b"\0" * 16)
        h += struct.pack("<iii", 1, len(self.exports), len(self.names))
        h += b"\0" * 28
        h += struct.pack("<IiIi", 0, 0, getattr(self, "pkg_source", 0), 0)
        h += struct.pack("<iqi", assetreg_off, total + len(uexp) - 4, 0)
        h += struct.pack("<i", len(getattr(self, "chunks", []))) + b"".join(struct.pack("<i", c) for c in getattr(self, "chunks", []))
        h += struct.pack("<iii", len(preload), preload_off, getattr(self, "names_ref", len(self.names))) + struct.pack("<qi", -1, -1)
        assert len(h) == name_off, (len(h), name_off)
        h += names + imports + exports + depends + assetreg + b"".join(struct.pack("<i", v) for v in preload)
        assert len(h) == total
        return h, uexp
