"""Minimal reader for cooked UE5 .uasset package headers (legacy format, as written by retoc): name map, imports, exports.
Enough to classify assets (class, skeleton, referenced packages) without UAssetGUI."""
import struct

class Header:
    __slots__ = ("names", "imports", "exports", "folder", "flags")

def _fstring(b, o):
    n = struct.unpack_from("<i", b, o)[0]; o += 4
    if n == 0: return "", o
    if n > 0: s = b[o:o + n - 1].decode("latin-1"); return s, o + n
    n = -n; s = b[o:o + 2 * (n - 1)].decode("utf-16-le"); return s, o + 2 * n

def read(path, need_exports=True):
    with open(path, "rb") as f:
        b = f.read(1 << 16)
        o = 0
        tag, legacy = struct.unpack_from("<Ii", b, o); o += 8
        if tag != 0x9E2A83C1: raise ValueError("not a uasset")
        if legacy != -4: o += 4                                   # LegacyUE3Version
        ue4 = struct.unpack_from("<i", b, o)[0]; o += 4
        ue5 = 0
        if legacy <= -8: ue5 = struct.unpack_from("<i", b, o)[0]; o += 4
        o += 4                                                    # licensee
        if ue4 == 0 and ue5 == 0: ue5 = 1012                      # unversioned (cooked): assume UE 5.4 layout
        if legacy <= -2:
            n = struct.unpack_from("<i", b, o)[0]; o += 4 + n * 20
        total = struct.unpack_from("<i", b, o)[0]; o += 4
        folder, o = _fstring(b, o)
        flags = struct.unpack_from("<I", b, o)[0]; o += 4
        name_count, name_off = struct.unpack_from("<ii", b, o); o += 8
        if ue5 >= 1008: o += 8                                    # soft object paths
        if not (flags & 0x80000000): _, o = _fstring(b, o)        # LocalizationId (not FilterEditorOnly)
        o += 8                                                    # gatherable text
        exp_count, exp_off, imp_count, imp_off = struct.unpack_from("<iiii", b, o)
        if total > len(b):
            f.seek(0); b = f.read(total)
    h = Header(); h.folder = folder; h.flags = flags
    names, o = [], name_off
    for _ in range(name_count):
        s, o = _fstring(b, o); o += 4                             # + hashes
        names.append(s)
    h.names = names
    def nm(o):
        i, num = struct.unpack_from("<ii", b, o)
        return names[i] if num == 0 else "%s_%d" % (names[i], num - 1)
    imps, o = [], imp_off
    for _ in range(imp_count):
        cp, cn = nm(o), nm(o + 8); outer = struct.unpack_from("<i", b, o + 16)[0]; on = nm(o + 20)
        imps.append((on, cn, outer, cp)); o += 28 + (4 if ue5 >= 1003 else 0)   # bImportOptional (OPTIONAL_RESOURCES)
    h.imports = imps
    exps = []
    if need_exports:
        o = exp_off
        for _ in range(exp_count):                                # FObjectExport, UE 5.4 cooked layout: 96 bytes
            cls, sup, tmpl, outer = struct.unpack_from("<iiii", b, o)
            exps.append((nm(o + 16), cls, outer)); o += 96
    h.exports = exps
    return h

def asset_class(h):
    """class name of the package's main object (export named like the package)."""
    base = h.folder.rsplit("/", 1)[-1]
    for n, cls, outer in h.exports:
        if outer == 0 and n in (base, base + "_C"): return imp_name(h, cls)
    return None
def imp_name(h, idx):
    return h.imports[-idx - 1][0] if idx < 0 else (h.exports[idx - 1][0] if idx > 0 and idx <= len(h.exports) else None)
def imp_package(h, idx):
    """package path of import idx (walk outers)."""
    while idx < 0:
        on, cn, outer, cp = h.imports[-idx - 1]
        if outer == 0: return on
        idx = outer
    return None
