"""wardrobe.json: every outfit (skin) and haircut (face) item: id, character, display name, icon texture, class.
usage: catalog_wardrobe.py <Content dir (cooked)> <DT_CharacterCustomizationItems.json> <out json>"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uasset_header as U, stringtable as ST
CHAR = {"Noah": "Gustave", "Lune": "Lune", "Maelle": "Maelle", "Sciel": "Sciel", "Verso": "Verso", "Monoco": "Monoco"}
def build(content, dt_json, out):
    st = ST.read(os.path.join(content, "StringTables/Gameplay/ST_Items.uexp"))
    rows = json.load(open(dt_json))["Exports"][0]["Table"]["Data"]
    items_dir = os.path.join(content, "Gameplay/CharacterCustomization/Data/Items")
    res, skipped = [], []
    norm = lambda x: x.lower().replace("_", "").replace("flowers", "flowersuit").replace("whiteversion", "whitever").replace("defaultdefault", "default").replace("potatoebag", "potatobag")
    das = {}
    for sub in ("Skins", "Faces"):
        for fn in os.listdir(os.path.join(items_dir, sub)):
            if fn.endswith(".uasset"): das[norm(fn[len("DA_CharacterCustomization_"):-7])] = os.path.join(items_dir, sub, fn)
    def find_da(rid):
        k = norm(rid)
        if k in das: return das[k]
        k2 = k.replace("default", "")                     # e.g. SkinGustave_Default_Red -> DA SkinGustave_Red
        if k2 != k and k2 in das: return das[k2]
        cand = [v for kk, v in das.items() if k.startswith(kk)] or [v for kk, v in das.items() if kk.startswith(k)]
        return cand[0] if len(cand) == 1 else None
    for r in rows:
        f = {x["Name"].split("_")[0] + "_" + x["Name"].split("_")[1] if x["Name"].startswith("Item_") else x["Name"].split("_")[0]: x.get("Value") for x in r["Value"]}
        rid = r["Name"]
        kind = "outfit" if rid.startswith("Skin") else "haircut" if rid.startswith("Face") else None
        char = rid[4:].split("_")[0]
        if not kind or char not in CHAR.values(): skipped.append(rid); continue
        da = find_da(rid)
        if not da: skipped.append(rid); continue
        h = U.read(da, need_exports=False)
        cls = next((n for n in h.names if n.startswith("/Game/Characters/Heros/")), None)
        if not cls: skipped.append(rid); continue
        icon = (f.get("Item_Icon") or {}).get("AssetPath", {}).get("PackageName")
        key = f.get("Item_DisplayName")
        res.append({"id": rid, "kind": kind, "character": char, "name": st.get(key) or rid.split("_", 1)[1],
                    "class": cls, "default": rid.endswith("_Default"), "icon": icon if icon and icon != "None" else None,
                    "hidden": bool(f.get("HideInInventory"))})
    import texture_png                                     # icons -> icons/<id>.png
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(out)), "icons"); os.makedirs(icon_dir, exist_ok=True)
    for x in res:
        if not x["icon"]: continue
        src = os.path.join(content, x["icon"][len("/Game/"):] + ".uexp"); dst = os.path.join(icon_dir, x["id"] + ".png")
        if os.path.exists(dst) or (os.path.exists(src) and texture_png.to_png(src, dst, 192)): x["icon_png"] = "icons/" + x["id"] + ".png"
    json.dump(res, open(out, "w"), indent=1)
    return res, skipped
if __name__ == "__main__":
    res, skipped = build(*sys.argv[1:4])
    import collections
    print(len(res), "items; skipped", skipped)
    print(collections.Counter((x["character"], x["kind"]) for x in res))
    print([x["name"] for x in res if x["character"] == "Lune" and x["kind"] == "haircut"])
