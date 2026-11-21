"""Legacy cooked package (cooked.Package) -> UE 5.4 zen package bytes, as retoc to-zen writes them (verified byte-for-byte
on Cosplay Studio's data table and blend spaces)."""
import struct
from cityhash import cityhash64, package_id
NULL = 0xFFFFFFFFFFFFFFFF
HASH_VERSION = 0xC1640000
def obj_hash(path): return cityhash64(path.lower().encode("utf-16-le"))
def script_index(path): return (obj_hash(path.replace(".", "/").replace(":", "/")) & ((1 << 62) - 1)) | (1 << 62)
def name_batch(names):
    b = struct.pack("<II", len(names), sum(len(n.encode("utf-8")) if n.isascii() else 2 * len(n) for n in names))
    if not names: return b
    b += struct.pack("<Q", HASH_VERSION)
    for n in names:
        b += struct.pack("<Q", cityhash64(n.lower().encode("utf-8") if n.isascii() else n.lower().encode("utf-16-le")))
    for n in names: b += struct.pack(">h", len(n) if n.isascii() else -len(n))
    for n in names: b += n.encode("utf-8") if n.isascii() else n.encode("utf-16-le")
    return b

def convert(pkg, uexp, dfs_bundles=False):
    """pkg: cooked.Package (legacy); uexp: its .uexp bytes. Returns (zen bytes, package id, imported package ids)."""
    imports = pkg.imports
    def full_path(i):                      # legacy import index (negative) -> list of names, package first
        chain = []
        while i < 0:
            cp, cn, outer, name, _ = imports[-i - 1]; chain.append(name); i = outer
        return chain[::-1]
    def is_script(i): return full_path(i)[0].startswith("/Script/")
    # names: those referenced by export data (same indices as legacy), then the package name / export base names if missing
    zen_names = list(pkg.names[:pkg.names_ref])
    def zname(s):
        """FName -> (zen index, number); "Foo_0" is "Foo" number 1 when "Foo" is a known name."""
        if s in zen_names: return zen_names.index(s), 0
        base, _, num = s.rpartition("_")
        if base and num.isdigit() and not (len(num) > 1 and num[0] == "0") and base in pkg.names:
            if base not in zen_names: zen_names.append(base)
            return zen_names.index(base), int(num) + 1
        zen_names.append(s); return len(zen_names) - 1, 0
    pkg_name_idx = zname(pkg.folder)[0]
    for e in pkg.exports: zname(e["name"])
    # imports
    imported_pkgs, pub_hashes, imap = [], [], []
    for k in range(len(imports)):
        i = -k - 1; chain = full_path(i)
        if chain[0].startswith("/Script/"):
            imap.append(script_index("/".join(chain)))
        elif len(chain) == 1:
            imap.append(NULL)
        else:
            if chain[0] not in imported_pkgs: imported_pkgs.append(chain[0])
            h = obj_hash("/".join(chain[1:]))
            if h not in pub_hashes: pub_hashes.append(h)
            imap.append((2 << 62) | (imported_pkgs.index(chain[0]) << 32) | pub_hashes.index(h))
    def ref(i):
        if i < 0: return imap[-i - 1]
        if i > 0: return i - 1
        return NULL
    # export map
    emap = b""
    for e in pkg.exports:
        public = bool(e["flags"] & 1)
        chain, k = [e["name"]], e["outer"]
        while k > 0: chain.append(pkg.exports[k - 1]["name"]); k = pkg.exports[k - 1]["outer"]
        ph = obj_hash("/".join(chain[::-1])) if public else 0
        ni, nn = zname(e["name"])
        emap += struct.pack("<QQIIQQQQQIB3x", e["offset"] - pkg.total, e["size"], ni, nn,
                            ref(e["outer"]), ref(e["cls"]), ref(e["sup"]), ref(e["tmpl"]), ph, e["flags"], 0)
    nodes, seen = [], set()
    def visit(i, cmd):                          # cmd 0 = create, 1 = serialize; internal export dependencies first
        if (i, cmd) in seen: return
        seen.add((i, cmd))
        sbs, cbs, sbc, cbc = pkg.exports[i].get("deps") or [[], [], [], []]
        if cmd == 0:
            for d in cbc:
                if d > 0 and d - 1 != i: visit(d - 1, 0)
            for d in sbc:
                if d > 0 and d - 1 != i: visit(d - 1, 1)
        else:
            visit(i, 0)
            o = pkg.exports[i]["outer"]
            if o > 0: visit(o - 1, 1)               # an export is serialized after its outer
            for d in cbs:
                if d > 0 and d - 1 != i: visit(d - 1, 0)
            for d in sbs:
                if d > 0 and d - 1 != i: visit(d - 1, 1)
        nodes.append((i, cmd))
    if dfs_bundles:                             # retoc's order (matches retoc byte for byte)
        for i in range(len(pkg.exports)): visit(i, 0)
        for i in range(len(pkg.exports)): visit(i, 1)
    else:                                       # retoc's order for the shipped logic file (tested in game): creates then serializes,
        dep = {}                                # each emitted at the first point where its in-package dependencies are done
        for i, e in enumerate(pkg.exports):
            sbs, cbs, sbc, cbc = e.get("deps") or [[], [], [], []]
            own = lambda lst, c: {(x - 1, c) for x in lst if x > 0 and x - 1 != i}
            dep[(i, 0)] = own(cbc, 0) | own(sbc, 1)
            dep[(i, 1)] = {(i, 0)} | own(cbs, 0) | own(sbs, 1)
        pend = [(i, 0) for i in range(len(pkg.exports))] + [(i, 1) for i in range(len(pkg.exports))]; done = set(); nodes = []
        while pend:
            k = next((k for k, nd in enumerate(pend) if dep[nd] <= done), 0)
            nd = pend.pop(k); nodes.append(nd); done.add(nd)
    bundles = b"".join(struct.pack("<II", i, c) for i, c in nodes)
    # dependency bundles: legacy deps [SBS, CBS, SBC, CBC] -> zen [CreateBeforeCreate, SerializeBeforeCreate(C on S),
    # CreateBeforeSerialize (S on C), SerializeBeforeSerialize]; script imports dropped
    dheads, dents = b"", b""; first = 0
    for n_e, e in enumerate(pkg.exports):
        sbs, cbs, sbc, cbc = e.get("deps") or [[], [], [], []]
        keep = lambda lst, me=n_e + 1: [x for x in lst if x != me and not (x < 0 and is_script(x))]
        groups = [keep(cbc), keep(sbc), keep(cbs), keep(sbs)]
        dheads += struct.pack("<i4I", first, *[len(g) for g in groups])
        for g in groups: dents += b"".join(struct.pack("<i", x) for x in g); first += len(g)
    # assemble
    names_b = name_batch(zen_names)
    pos = 52 + len(names_b)
    pad = (-(pos + 8)) % 8
    after_names = struct.pack("<Q", pad) + b"\0" * pad + struct.pack("<q", 0)        # padding, BulkDataMapSize
    off_pub = pos + len(after_names)
    pub_b = b"".join(struct.pack("<Q", h) for h in pub_hashes)
    off_imap = off_pub + len(pub_b); imap_b = b"".join(struct.pack("<Q", x) for x in imap)
    off_emap = off_imap + len(imap_b)
    off_bund = off_emap + len(emap)
    off_dh = off_bund + len(bundles)
    off_de = off_dh + len(dheads)
    off_ipn = off_de + len(dents)
    ipn = name_batch(imported_pkgs) + b"\0\0\0\0" * len(imported_pkgs)
    header_size = off_ipn + len(ipn)
    summ = struct.pack("<IIIIIIiiiiiii", 0, header_size, pkg_name_idx, 0, pkg.flags, pkg.total,
                       off_pub, off_imap, off_emap, off_bund, off_dh, off_de, off_ipn)
    z = summ + names_b + after_names + pub_b + imap_b + emap + bundles + dheads + dents + ipn
    assert len(z) == header_size
    return z + uexp, package_id(pkg.folder), [package_id(p) for p in imported_pkgs]
