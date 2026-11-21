"""Decode the largest inline mip of a cooked Texture2D (.uexp) to PNG (DXT1/DXT5/BC7/BGRA8) via Pillow's DDS reader."""
import struct, io, re
from PIL import Image
BPP = {"PF_DXT1": 4, "PF_DXT5": 8, "PF_BC7": 8, "PF_BC5": 8, "PF_B8G8R8A8": 32}
FOURCC = {"PF_DXT1": b"DXT1", "PF_DXT5": b"DXT5"}
def _dds(fmt, w, h, data):
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    if fmt in FOURCC:
        pf = struct.pack("<II4s5I", 32, 0x4, FOURCC[fmt], 0, 0, 0, 0, 0); dx10 = b""
    elif fmt == "PF_B8G8R8A8":
        pf = struct.pack("<II4s5I", 32, 0x41, b"\0\0\0\0", 32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000); dx10 = b""
    else:                                        # BC7 / BC5 through the DX10 header
        pf = struct.pack("<II4s5I", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
        dx10 = struct.pack("<5I", {"PF_BC7": 98, "PF_BC5": 83}[fmt], 3, 0, 1, 0)
    hdr = struct.pack("<4sI6I44x", b"DDS ", 124, flags, h, w, len(data), 0, 1) + pf + struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    return hdr + dx10 + data
def decode(uexp_path):
    b = open(uexp_path, "rb").read()
    m = re.search(rb"PF_[A-Za-z0-9]+\0", b)
    if not m: return None
    fmt = m.group()[:-1].decode(); bpp = BPP.get(fmt)
    if not bpp: return None
    start = m.end() + 12
    for e in range(12, 1, -1):                      # largest square-or-not inline mip whose trailer (w, h, 1) matches
        for w, h in ((1 << e, 1 << e), (1 << e, 1 << (e - 1)), (1 << (e - 1), 1 << e)):
            n = w * h * bpp // 8
            if start + n + 12 <= len(b) and struct.unpack_from("<iii", b, start + n) == (w, h, 1):
                img = Image.open(io.BytesIO(_dds(fmt, w, h, b[start:start + n]))); img.load()
                return img.convert("RGBA")
    return None
def to_png(uexp_path, png_path, size=256):
    img = decode(uexp_path)
    if img is None: return False
    img.thumbnail((size, size)); img.save(png_path); return True
