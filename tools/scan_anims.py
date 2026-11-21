"""Scan extracted game files for animation assets: AnimSequence / BlendSpace(1D) per skeleton. Writes anim_scan.json."""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uasset_header as U
def scan(content_root, subdirs, out_json, prev=None):
    res = prev or {}
    t = time.time(); n = 0
    for sd in subdirs:
        for r, ds, fs in os.walk(os.path.join(content_root, sd)):
            for f in fs:
                if not f.endswith(".uasset"): continue
                p = os.path.join(r, f); n += 1
                try: h = U.read(p)
                except Exception: continue
                c = U.asset_class(h)
                if c not in ("AnimSequence", "BlendSpace", "BlendSpace1D", "AnimMontage"): continue
                skel = [i[0] for i in h.imports if i[1] == "Skeleton"]
                refs = [U.imp_package(h, -k - 1) for k, i in enumerate(h.imports) if i[1] == "AnimSequence"] if c.startswith("BlendSpace") else []
                res[h.folder] = {"class": c, "skeleton": skel[0] if skel else None, "anims": refs}
    json.dump(res, open(out_json, "w"), indent=1)
    return n, len(res), time.time() - t
if __name__ == "__main__":
    root = sys.argv[1]; out = sys.argv[2]; subs = sys.argv[3:]
    prev = json.load(open(out)) if os.path.exists(out) else None
    print(scan(root, subs, out, prev))
