"""Build a Cosplay Studio mod - no UAssetGUI, no retoc, no game files needed.
  data table + blend spaces are written by writer.py, converted to zen by zen.py, and packed with the prebuilt logic file
  into <name>_P.utoc / .ucas / .pak by iostore.py (optionally zipped for Vortex).
usage: build_mod.py <assignments.json> <mod name> [--zip]"""
import os, sys, json, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import paths
HERE = paths.DATA
import generator, writer, cooked, zen, iostore
PRE = os.path.join(HERE, "prebuilt")
def build(cfg, assignments, mod_name, do_pack=True, log=print, do_zip=False):
    log("Reading data...")
    g = generator.Game(None, os.path.join(HERE, "anim_scan.json"), os.path.join(HERE, "wardrobe.json"))
    log("Resolving %d outfits and %d haircuts..." % (len(assignments.get("outfits", {})), len(assignments.get("haircuts", {}))))
    b = generator.Build(g, assignments, None)
    rows = b.rows()
    full = {}
    for rn, prof in rows.items():
        f = {"Idle": [], "Breaks": [], "WalkRun": None, "Sprint": None, "SprintStart": None}; f.update(prof)
        if not f["Sprint"]: f["SprintStart"] = None
        full[rn] = f
    packages = []
    def add(folder, h, x):
        z, pid, imps = zen.convert(cooked.Package.read(h, x), x)
        packages.append(("Sandfall/Content/" + folder[len("/Game/"):] + ".uasset", z, pid, imps)); log("  " + folder.rsplit("/", 1)[1])
    h, x = writer.DataTableWriter(generator.MOD + "DT_CosplayStudio").build(full); add(generator.MOD + "DT_CosplayStudio", h, x)
    for (walk, run), bs in b.bs.items():
        h, x = writer.blendspace(PRE, bs, walk, run); add(bs, h, x)
    meta = json.load(open(os.path.join(PRE, "BP_CharacterSkinComponent.zen.json")))
    packages.append(("Sandfall/Content" + meta["package"][len("/Game"):] + ".uasset", open(os.path.join(PRE, "BP_CharacterSkinComponent.zen"), "rb").read(),
                     meta["id"], meta["imports"])); log("  BP_CharacterSkinComponent (prebuilt logic)")
    os.makedirs(cfg["output"], exist_ok=True)
    name = mod_name if mod_name.endswith("_P") else mod_name + "_P"
    base = os.path.join(cfg["output"], name)
    log("Packing %d packages..." % len(packages))
    iostore.write(base, name, packages)
    if do_zip:
        z = base + ".zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for ext in (".pak", ".utoc", ".ucas"): zf.write(base + ext, name + ext)
        log("Zipped -> " + z); return True, z
    return True, base + ".utoc"
if __name__ == "__main__":
    cfg = json.load(open(paths.CONFIG))
    ok, res = build(cfg, json.load(open(sys.argv[1])), sys.argv[2], do_zip="--zip" in sys.argv)
    print("OK ->" if ok else "FAILED:", res)
