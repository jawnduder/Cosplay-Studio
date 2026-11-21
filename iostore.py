"""Write an IoStore mod container (.utoc / .ucas / .pak) like retoc to-zen: uncompressed, unencrypted, TOC version 6,
container header version 3. No Oodle needed."""
import struct, hashlib
from blake3 import blake3
from cityhash import cityhash64
BLOCK = 65536
PAK_STUB = None
def _fstr(s): b = s.encode("ascii"); return struct.pack("<i", len(b) + 1) + b + b"\0"
def pak_stub():
    """the .pak retoc writes next to the container: an empty pak (v11) with mount point ../../../"""
    index = _fstr("../../../") + struct.pack("<iQ", 0, 0)
    ph_off = None
    body_len = len(index) + 4 + 16 + 20 + 4 + 16 + 20 + 4 + 4
    ph_off = body_len; fd_off = ph_off + 8
    path_hash = b"\0" * 8; full_dir = b"\0" * 4
    index += struct.pack("<I", 1) + struct.pack("<qq", ph_off, len(path_hash)) + hashlib.sha1(path_hash).digest()
    index += struct.pack("<I", 1) + struct.pack("<qq", fd_off, len(full_dir)) + hashlib.sha1(full_dir).digest()
    index += struct.pack("<i", 0) + struct.pack("<i", 0)
    assert len(index) == body_len
    footer = b"\0" * 16 + b"\0" + struct.pack("<Iiqq", 0x5A6F12E1, 11, 0, len(index)) + hashlib.sha1(index).digest() + b"\0" * 32 * 5
    return index + path_hash + full_dir + footer

def _dir_index(files):
    """files: [(path relative to mount, chunk index)] -> FIoDirectoryIndexResource bytes."""
    strings, dirs, fents = [], [[0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF]], []
    def sidx(s):
        if s not in strings: strings.append(s)
        return strings.index(s)
    def child(parent, name):
        c = dirs[parent][1]; last = None
        while c != 0xFFFFFFFF:
            if strings[dirs[c][0]] == name: return c
            last, c = c, dirs[c][2]
        dirs.append([sidx(name), 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF]); new = len(dirs) - 1
        if last is None: dirs[parent][1] = new
        else: dirs[last][2] = new
        return new
    for path, chunk in files:
        parts = path.split("/"); d = 0
        for p in parts[:-1]: d = child(d, p)
        fents.append([sidx(parts[-1]), 0xFFFFFFFF, chunk]); new = len(fents) - 1
        f = dirs[d][3]
        if f == 0xFFFFFFFF: dirs[d][3] = new
        else:
            while fents[f][1] != 0xFFFFFFFF: f = fents[f][1]
            fents[f][1] = new
    b = _fstr("../../../") + struct.pack("<i", len(dirs)) + b"".join(struct.pack("<4I", *x) for x in dirs)
    b += struct.pack("<i", len(fents)) + b"".join(struct.pack("<3I", *x) for x in fents)
    b += struct.pack("<i", len(strings)) + b"".join(_fstr(s) for s in strings)
    return b

def write(base_path, container_name, packages):
    """packages: [(file path like 'Sandfall/Content/Mods/X.uasset', zen bytes, package id, [imported package ids])].
    Writes base_path.utoc / .ucas / .pak."""
    cid = cityhash64(container_name.lower().encode("utf-16-le"))
    # container header
    order = sorted(range(len(packages)), key=lambda i: packages[i][2])
    ids = [packages[i][2] for i in order]
    entries, data = b"", b""
    base = 16 * len(order)
    for k, i in enumerate(order):
        imps = packages[i][3]
        off = base + len(data) - 16 * k
        entries += struct.pack("<iIiI", len(imps), off if imps else 0, 0, 0)
        data += b"".join(struct.pack("<Q", x) for x in imps)
    store = entries + data
    header = struct.pack("<IIQ", 0x496F436E, 3, cid) + struct.pack("<i", len(ids)) + b"".join(struct.pack("<Q", x) for x in ids)
    header += struct.pack("<i", len(store)) + store + b"\0" * 24
    header += b"\0" * (-len(header) % 16)       # retoc pads the container header to 16 bytes; the game rejects the container otherwise
    chunks = [(pid, 1, z) for _, z, pid, _ in packages] + [(cid, 6, header)]
    # ucas + blocks
    ucas, ids_b, offlen, blocks, metas = bytearray(), b"", b"", b"", b""
    logical = 0
    for cid_, typ, z in chunks:
        ids_b += struct.pack("<QHBB", cid_, 0, 0, typ)
        offlen += logical.to_bytes(5, "big") + len(z).to_bytes(5, "big")
        for s in range(0, max(len(z), 1), BLOCK):
            part = z[s:s + BLOCK]
            blocks += len(ucas).to_bytes(5, "little") + len(part).to_bytes(3, "little") + len(part).to_bytes(3, "little") + b"\0"
            ucas += part
        metas += blake3(z)[:20] + b"\0" * 12 + b"\0"                  # FIoChunkHash: BLAKE3, 20 bytes used
        logical += ((len(z) + BLOCK - 1) // BLOCK) * BLOCK
    dir_b = _dir_index([(p, i) for i, (p, _, _, _) in enumerate(packages)])
    nblocks = len(blocks) // 12
    hdr = b"-==--==--==--==-" + struct.pack("<BBHIIIIIIIIIQ", 6, 0, 0, 144, len(chunks), nblocks, 12, 0, 32, BLOCK, len(dir_b), 1, cid)
    hdr += b"\0" * 16 + struct.pack("<BBHIQII", 8, 0, 0, 0, 0xFFFFFFFFFFFFFFFF, 0, 0) + b"\0" * 40
    assert len(hdr) == 144, len(hdr)
    toc = hdr + ids_b + offlen + blocks + dir_b + metas
    open(base_path + ".utoc", "wb").write(toc); open(base_path + ".ucas", "wb").write(bytes(ucas)); open(base_path + ".pak", "wb").write(pak_stub())
    return base_path
