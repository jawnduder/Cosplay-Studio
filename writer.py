"""Cosplay Studio writer: produces the cooked DT_CosplayStudio and BS_CS_* files directly (no UAssetGUI, no mappings).
The logic file (BP_CharacterSkinComponent) is the same for every build and ships prebuilt."""
import struct, os
import cooked

FIELD_ORDER = ("Idle", "Breaks", "WalkRun", "Sprint", "SprintStart")     # S_AnimationProfile_Skins property indices 0..4

def _unversioned_header(values_present, zero_flags):
    """one fragment covering properties 0..n-1 (n = len(values_present)), all present; zero mask for zero values."""
    n = len(values_present); has_zero = any(zero_flags)
    frag = 0 | (0x80 if has_zero else 0) | (n << 9) | 0x100
    out = struct.pack("<H", frag)
    if has_zero:
        bits = sum(1 << i for i, z in enumerate(zero_flags) if z)
        out += struct.pack("<B", bits) if n <= 8 else struct.pack("<H", bits) if n <= 16 else struct.pack("<I", bits)
    return out

class DataTableWriter:
    def __init__(self, folder, explicit_null=False):
        self.p = cooked.Package(); self.folder = folder; self.name = folder.rsplit("/", 1)[1]
        self.explicit_null = explicit_null            # write None object refs as 0 instead of flagging them in the zero mask
        self.used = []
    def imp(self, cls_pkg, cls, outer, obj):
        for i, im in enumerate(self.p.imports):
            if im[0] == cls_pkg and im[1] == cls and im[2] == outer and im[3] == obj: return -i - 1
        for n in (obj, cls_pkg, cls): self.p.nidx(n)            # same name order as UAssetAPI
        self.p.imports.append([cls_pkg, cls, outer, obj, 0]); return -len(self.p.imports)
    def obj(self, path, cls):
        pkg = self.imp("/Script/CoreUObject", "Package", 0, path)
        i = self.imp("/Script/Engine", cls, pkg, path.rsplit("/", 1)[1])
        if i not in self.used: self.used.append(i)
        return i
    def build(self, rows):
        """rows: {row name: {"Idle": [paths], "Breaks": [paths], "WalkRun": path|None, "Sprint": path|None, "SprintStart": path|None}}"""
        p = self.p
        p.names = list(rows) + [self.name, self.folder]
        eng = self.imp("/Script/CoreUObject", "Package", 0, "/Script/Engine")
        dtc = self.imp("/Script/CoreUObject", "Class", eng, "DataTable")
        dtd = self.imp("/Script/Engine", "DataTable", eng, "Default__DataTable")
        sp = self.imp("/Script/CoreUObject", "Package", 0, "/Game/Animations/ALS_UE5/Misc/S_AnimationProfile_Skins")
        st = self.imp("/Script/Engine", "UserDefinedStruct", sp, "S_AnimationProfile_Skins")
        body = b""
        for rn, prof in rows.items():
            vals, zero = [], []
            for k in FIELD_ORDER:
                v = prof.get(k)
                if k in ("Idle", "Breaks"):
                    v = v or []
                    vals.append(struct.pack("<i", len(v)) + b"".join(struct.pack("<i", self.obj(a, "AnimSequence")) for a in v)); zero.append(False)
                elif v:
                    vals.append(struct.pack("<i", self.obj(v, "BlendSpace" if k == "WalkRun" else "AnimSequence"))); zero.append(False)
                elif self.explicit_null:
                    vals.append(struct.pack("<i", 0)); zero.append(False)
                else:
                    vals.append(b""); zero.append(True)
            body += struct.pack("<ii", *p.nidx(rn)) + _unversioned_header(vals, zero) + b"".join(vals)
        data = b"\0\0\0\0" + struct.pack("<H", 0x0300) + struct.pack("<i", st) + b"\0\0\0\0" + struct.pack("<i", len(rows)) + body
        p.exports = [dict(cls=dtc, sup=0, tmpl=dtd, outer=0, name=self.name, flags=11, forced=0, not_client=0, not_server=0, inherited=0,
                          pkg_flags=0, not_always=0, is_asset=1, public_hash=0, deps=[[st], list(self.used), [dtc, dtd], []])]
        p.data = [data]; p.depends = [[]]; p.assetreg = b"\0\0\0\0"; p.names_ref = len(rows)
        p.folder = self.folder; p.flags = 0x80002200
        return p.write()

# ---------------- blend spaces: copy of Gustave's BS_Movement_Noah with new walk / run
BS_TEMPLATE = "Characters/Heros/Noah/Animations/Locomotion/BS_Movement_Noah"
OLD = {"bs": "/Game/Characters/Heros/Noah/Animations/Locomotion/BS_Movement_Noah",
       "walk": "/Game/Characters/Heros/Noah/Animations/Locomotion/Noah_Walk_2_Retake1",
       "run": "/Game/Characters/Heros/Verso/Animations/Locomotion/Verso_Run_V1"}
# export-data patch (verified against UAssetGUI output): drop SampleIndexWithMarkers, walk sample rate 1.3 -> 1.0
UEXP_PATCH = [(12, bytes.fromhex("8406"), bytes.fromhex("0504")), (18, bytes.fromhex("03"), bytes.fromhex("01")),
              (76, bytes.fromhex("6666a63f"), bytes.fromhex("0000803f"))]
def blendspace(content_root, folder, walk, run):
    base = os.path.join(content_root, BS_TEMPLATE)
    a, e = open(base + ".uasset", "rb").read(), open(base + ".uexp", "rb").read()
    e = bytearray(e)
    for off, old, new in UEXP_PATCH:
        if bytes(e[off:off + len(old)]) != old: raise ValueError("BS_Movement_Noah changed in this game version (offset %d)" % off)
        e[off:off + len(new)] = new
    p = cooked.Package.read(a, bytes(e))
    ren = {OLD["bs"]: folder, OLD["bs"].rsplit("/", 1)[1]: folder.rsplit("/", 1)[1],
           OLD["walk"]: walk, OLD["walk"].rsplit("/", 1)[1]: walk.rsplit("/", 1)[1],
           OLD["run"]: run, OLD["run"].rsplit("/", 1)[1]: run.rsplit("/", 1)[1]}
    p.names = [ren.get(n, n) for n in p.names]
    for im in p.imports:
        im[0], im[1], im[3] = ren.get(im[0], im[0]), ren.get(im[1], im[1]), ren.get(im[3], im[3])
    for x in p.exports: x["name"] = ren.get(x["name"], x["name"])
    p.folder = folder
    return p.write(folder)
