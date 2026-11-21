"""Cosplay Studio generator core (v2: data-driven).

assignments (JSON):
  {"outfits":  {"<wardrobe item id>": {slot: value, ..., "_all": bool}, ...},
   "haircuts": {"<wardrobe item id>": {slot: value, ...}, ...}}
  slots: "idle" (anim path), "idle_breaks" (list; default [] when idle is set), "walk", "run", "sprint", "sprint_start".
  A slot left out keeps whatever the item already has.

Output (JSON for UAssetGUI fromjson / json_to_mod; later written directly by the Cosplay Studio writer):
  - DT_CosplayStudio: one row per outfit class and per haircut class (row struct S_AnimationProfile_Skins; every field
    written, empty = not given). Vanilla Esquie/Osquio outfits get rows with their own values so they keep priority.
  - BS_CS_<walk>_<run>_x<hash>: hero-style 2-D blend spaces for every walk/run pair used
  - BP_CharacterSkinComponent: the logic (identical for every build; see component.py)
No outfit class is modified, so edits never spill over to other outfits and other outfit mods stay compatible.
"""
import os, sys, json, copy, hashlib
import paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbuild as K
from ksize import T

MOD = "/Game/Mods/CosplayStudio/"
FIELDS = {"Idle": "IdleList_5_BB99C1CA49757756F20EF182978D3272", "Breaks": "IdleBreakList_8_0DB900DC4A61F90DB83DFDB3A9A5ECFE",
          "WalkRun": "WalkRunBlendspace_12_DF7E483E4DB87A4439B4B7AC8EBA3A95", "Sprint": "SprintAnim_15_353467EA494719D613E1619DEAD60B67",
          "SprintStart": "SprintStartAnim_18_D0B16C1041B551A0E56F4C887A357538", "Dialogue": "DialogueABP_21_B600531F4D184EBA959DD896567615E5"}
GROUP_FIELDS = {"Idle": ("Idle", "Breaks"), "WalkRun": ("WalkRun",), "Sprint": ("Sprint", "SprintStart")}

class Game:
    """Access to the game data the generator needs: JSON exports (cache), header scan, wardrobe."""
    def __init__(self, json_root, scan_json, wardrobe_json):
        self.json_root = json_root
        self.scan = json.load(open(scan_json))
        for v in self.scan.values():                      # older scans stored "<package>/<name>" for blend space refs
            v["anims"] = [a.rsplit("/", 1)[0] if a.count("/") > 1 and a.rsplit("/", 1)[1] == a.rsplit("/", 2)[1] else a for a in v["anims"]]
        self.wardrobe = {x["id"]: x for x in json.load(open(wardrobe_json))}
        self._idx = None
    def find_json(self, name):
        if self._idx is None:
            self._idx = {}
            for r, _, fs in os.walk(self.json_root):
                for f in fs:
                    if f.endswith(".json"): self._idx.setdefault(f[:-5], os.path.join(r, f))
        if name not in self._idx: raise FileNotFoundError("game JSON missing (export it): " + name)
        return self._idx[name]
    def load(self, name): return K.load(self.find_json(name))
    def own_profile(self, cls_name):
        """(fields this class sets itself, parent class name or None). From profiles.json when the game JSON isn't there."""
        if self.json_root is None or not os.path.isdir(self.json_root):
            if not hasattr(self, "_pj"):
                self._pj = json.load(open(os.path.join(paths.DATA, "profiles.json")))
            if cls_name not in self._pj: raise FileNotFoundError("no profile data for " + cls_name)
            e = self._pj[cls_name]; return dict(e["own"]), e["parent"]
        d = self.load(cls_name)
        cdo = [e for e in d["Exports"] if e["ObjectName"].startswith("Default__")][0]
        ce = next(e for e in d["Exports"] if "ClassExport" in e["$type"])
        sup = ce.get("SuperIndex") or ce.get("SuperStruct")
        parent = d["Imports"][-sup - 1]["ObjectName"][:-2] if isinstance(sup, int) and sup < 0 else None
        out = {}
        for p in cdo["Data"]:
            if p["Name"] != "AnimationProfile": continue
            for f in p["Value"]:
                k = next((k for k, v in FIELDS.items() if v == f["Name"]), None)
                if not k: continue
                v = f["Value"]
                if isinstance(v, list): out[k] = [self.path(d, o["Value"]) for o in v]
                else: out[k] = self.path(d, v) if v else None
        return out, parent
    def profile(self, cls_name):
        """the AnimationProfile a skin class ends up with (own fields over its parents')."""
        own, parent = self.own_profile(cls_name)
        out = self.profile(parent) if parent and parent != "BP_CharacterSkinBase" else {}
        out.update(own); return out
    @staticmethod
    def path(d, idx):
        im = d["Imports"][-idx - 1]; return d["Imports"][-im["OuterIndex"] - 1]["ObjectName"]
    def walk_run_of(self, bs_path):
        """(walk, run) animation packages of a hero-style blend space, from the header scan."""
        refs = [a for a in self.scan[bs_path]["anims"] if "Pose" not in a.rsplit("/", 1)[1]]
        walk = next((a for a in refs if "walk" in a.rsplit("/", 1)[1].lower()), None)
        run = next((a for a in refs if a != walk), None)
        return walk, run
    def anim_class(self, path):
        v = self.scan.get(path); return v["class"] if v else "AnimSequence"

def triple(path, cls): return (path, path.rsplit("/", 1)[1], cls)

class Build:
    def __init__(self, game, assignments, out_dir):
        self.g, self.a, self.out = game, assignments, out_dir
        if out_dir: os.makedirs(out_dir, exist_ok=True)
        self.bs = {}                       # (walk, run) -> blend space package
        self.notes = []
    # ---------------- per item: the resolved override profile (only overridden groups)
    def resolve(self, item_id, slots, base_profile):
        p = {}
        if "idle" in slots:
            p["Idle"] = [slots["idle"]] if isinstance(slots["idle"], str) else list(slots["idle"])
            p["Breaks"] = list(slots.get("idle_breaks", []))
        if "walk" in slots or "run" in slots:
            cur = base_profile.get("WalkRun")
            bw, br = self.g.walk_run_of(cur) if cur else (None, None)
            walk, run = slots.get("walk", bw), slots.get("run", br)
            if not walk or not run: raise ValueError("%s: can't resolve walk/run (current blend space %s)" % (item_id, cur))
            p["WalkRun"] = self.blendspace(walk, run)
        if "sprint" in slots or "sprint_start" in slots:
            p["Sprint"] = slots.get("sprint", base_profile.get("Sprint"))
            p["SprintStart"] = slots["sprint_start"] if "sprint_start" in slots else (None if "sprint" in slots else base_profile.get("SprintStart"))
        return p
    def blendspace(self, walk, run):
        key = (walk, run)
        if key not in self.bs:
            h = "x" + hashlib.md5(("%s|%s" % key).encode()).hexdigest()[:6]     # never all digits (FName number suffix)
            self.bs[key] = MOD + "BS_CS_%s_%s_%s" % (walk.rsplit("/", 1)[1][:24], run.rsplit("/", 1)[1][:24], h)
        return self.bs[key]
    # ---------------- writers
    def write_blendspaces(self):
        tmpl = open(self.g.find_json("BS_Movement_Noah"), encoding="utf-8").read()
        OLD_BS = "/Game/Characters/Heros/Noah/Animations/Locomotion/BS_Movement_Noah"
        OLD_W = "/Game/Characters/Heros/Noah/Animations/Locomotion/Noah_Walk_2_Retake1"
        OLD_R = "/Game/Characters/Heros/Verso/Animations/Locomotion/Verso_Run_V1"
        for (walk, run), bs in self.bs.items():
            name = bs.rsplit("/", 1)[1]
            s = tmpl.replace(OLD_BS, bs).replace('"BS_Movement_Noah"', '"%s"' % name)
            s = s.replace('"%s"' % OLD_W, '"\x01W\x01"').replace('"%s"' % OLD_R, '"\x01R\x01"')
            s = s.replace('"Noah_Walk_2_Retake1"', '"\x01w\x01"').replace('"Verso_Run_V1"', '"\x01r\x01"')
            s = s.replace('"\x01W\x01"', json.dumps(walk)).replace('"\x01R\x01"', json.dumps(run))
            s = s.replace('"\x01w\x01"', json.dumps(walk.rsplit("/", 1)[1])).replace('"\x01r\x01"', json.dumps(run.rsplit("/", 1)[1]))
            d = json.loads(s)
            if walk == run:                                     # same animation twice: point both samples at one import
                objs = [-i - 1 for i, im in enumerate(d["Imports"]) if im["ObjectName"] == walk.rsplit("/", 1)[1]]
                for p in d["Exports"][0]["Data"]:
                    if p["Name"] == "SampleData":
                        for smp in p["Value"]:
                            for f in smp["Value"]:
                                if f["Name"] == "Animation" and f["Value"] in objs[1:]: f["Value"] = objs[0]
            e = d["Exports"][0]
            e["Data"] = [p for p in e["Data"] if p["Name"] != "SampleIndexWithMarkers"]
            for p in e["Data"]:
                if p["Name"] == "SampleData":
                    for smp in p["Value"]:
                        for f in smp["Value"]:
                            if f["Name"] == "RateScale": f["Value"] = 1.0
            K.save(d, os.path.join(self.out, name + ".json"))
    def profile_template(self):
        t = self.g.load("BP_CharacterSkin_VersoOutfit_Esquie")
        prop = [p for p in [e for e in t["Exports"] if e["ObjectName"].startswith("Default__")][0]["Data"] if p["Name"] == "AnimationProfile"][0]
        return prop, {f["Name"]: f for f in prop["Value"]}
    def struct_values(self, d, prof, used):
        """struct field list for a (partial) profile, imports added to d."""
        prop, tv = self.profile_template()
        def obj(path, cls):
            pkg = K.add_import(d, path, "/Script/CoreUObject", "Package", 0)
            i = K.add_import(d, path.rsplit("/", 1)[1], "/Script/Engine", cls, pkg)
            if i not in used: used.append(i)
            return i
        def item(i, v): return {**copy.deepcopy(tv[FIELDS["Idle"]]["Value"][0] if tv[FIELDS["Idle"]]["Value"] else {}), "Name": str(i), "Value": v}
        tmpl_item = copy.deepcopy(prop["Value"][0]["Value"][0])
        vals = []
        for k in ("Idle", "Breaks"):
            if k in prof:
                f = copy.deepcopy(tv[FIELDS["Idle"]]); f["Name"] = FIELDS[k]
                f["Value"] = [{**copy.deepcopy(tmpl_item), "Name": str(i), "Value": obj(a, "AnimSequence")} for i, a in enumerate(prof[k])]
                vals.append(f)
        if "WalkRun" in prof:
            f = copy.deepcopy(tv[FIELDS["WalkRun"]])
            if prof["WalkRun"]: f["Value"] = obj(prof["WalkRun"], "BlendSpace"); f["IsZero"] = False
            else: f["Value"] = 0; f["IsZero"] = True
            vals.append(f)
        for k in ("Sprint", "SprintStart"):
            if k in prof:
                f = copy.deepcopy(tv[FIELDS["Sprint"]]); f["Name"] = FIELDS[k]
                if prof[k]: f["Value"] = obj(prof[k], "AnimSequence"); f["IsZero"] = False
                else: f["Value"] = 0; f["IsZero"] = True
                vals.append(f)
        return prop, vals
    def write_outfits(self):
        """Edits of a character's base outfit (Expedition) change the base class, which every outfit inherits. By default
        they are kept to that outfit: every sibling outfit that would inherit a changed group gets the vanilla base values.
        With "_all": true in the base item's slots they apply to every outfit that doesn't set its own (and those outfits
        then count as owning the group for haircut priority)."""
        self.outfit_groups = {"Idle": [], "WalkRun": [], "Sprint": []}
        profs = {}                                            # class path -> fields to write
        for item_id, slots in self.a.get("outfits", {}).items():
            it = self.g.wardrobe[item_id]; cls = it["class"].rsplit("/", 1)[1]
            prof = self.resolve(item_id, slots, self.g.profile(cls))
            if not prof: continue
            profs[it["class"]] = dict(prof)
            for grp, flds in GROUP_FIELDS.items():
                if flds[0] in prof: self.outfit_groups[grp].append(it["class"])
        for item_id, slots in self.a.get("outfits", {}).items():
            it = self.g.wardrobe[item_id]
            if not it.get("default") or it["class"] not in profs: continue
            base_cls = it["class"].rsplit("/", 1)[1]; base_vanilla = self.g.profile(base_cls)
            changed = [g for g, f in GROUP_FIELDS.items() if f[0] in profs[it["class"]]]
            for sib in self.g.wardrobe.values():
                if sib["kind"] != "outfit" or sib["character"] != it["character"] or sib["class"] == it["class"]: continue
                own, _ = self.g.own_profile(sib["class"].rsplit("/", 1)[1])
                mine = profs.get(sib["class"], {})
                for g in changed:
                    f = GROUP_FIELDS[g]
                    if any(k in own for k in f) or f[0] in mine: continue      # sibling sets this group itself
                    if slots.get("_all"):
                        if sib["class"] not in self.outfit_groups[g]: self.outfit_groups[g].append(sib["class"])
                    else:
                        fill = profs.setdefault(sib["class"], {})
                        for k in f:
                            if k in base_vanilla: fill[k] = base_vanilla[k]
                            elif k == "Breaks": fill[k] = []
                            elif k == "SprintStart": fill[k] = None
        for cls_path, prof in profs.items():
            cls = cls_path.rsplit("/", 1)[1]
            d = self.g.load(cls); orig = list(d["NameMap"])
            cdo = [e for e in d["Exports"] if e["ObjectName"].startswith("Default__")][0]
            used = []; prop, vals = self.struct_values(d, prof, used)
            old = next((p for p in cdo["Data"] if p["Name"] == "AnimationProfile"), None)
            if old:                                           # merge: keep vanilla fields we don't override
                keep = [f for f in old["Value"] if f["Name"] not in {x["Name"] for x in vals}]
                vals = keep + vals
            newp = copy.deepcopy(prop); newp["Value"] = vals
            cdo["Data"] = [p for p in cdo["Data"] if p["Name"] != "AnimationProfile"]; cdo["Data"].insert(0, newp)
            for i in used: K.add_dep(cdo, "CreateBeforeSerializationDependencies", i)
            for n in [newp["Name"]] + [x["Name"] for x in vals]: K.name(d, n)
            K.fix_name_order(d, orig)
            K.save(d, os.path.join(self.out, cls + ".json"))
    def write_hair_table(self):
        hair = self.a.get("haircuts", {})
        if not hair: return None
        base = self.g.load("DT_UniqueMechanic_Transform_Masks")
        name = "DT_CosplayStudio_Hair"; path = MOD + name
        d = copy.deepcopy(base)
        rows = []
        rownames = [self.g.wardrobe[i]["class"].rsplit("/", 1)[1] + "_C" for i in hair]
        d["NameMap"] = rownames + [name, path]; d["NamesReferencedFromExportDataCount"] = len(rownames)
        d["FolderName"] = path; d["Imports"] = []; d["SoftObjectPathList"] = []
        eng = K.add_import(d, "/Script/Engine", "/Script/CoreUObject", "Package", 0)
        dtc = K.add_import(d, "DataTable", "/Script/CoreUObject", "Class", eng)
        dtd = K.add_import(d, "Default__DataTable", "/Script/Engine", "DataTable", eng)
        sp = K.add_import(d, "/Game/Animations/ALS_UE5/Misc/S_AnimationProfile_Skins", "/Script/CoreUObject", "Package", 0)
        st = K.add_import(d, "S_AnimationProfile_Skins", "/Script/Engine", "UserDefinedStruct", sp)
        used = []
        for (item_id, slots), rn in zip(hair.items(), rownames):
            it = self.g.wardrobe[item_id]
            base_cls = {"Gustave": "BP_CharacterSkinBase_Noah"}.get(it["character"], "BP_CharacterSkinBase_" + it["character"])
            prof = self.resolve(item_id, slots, self.g.profile(base_cls))
            # every field written explicitly: a data-table row starts from the struct's DEFAULTS (MM_Idle, the ALS mannequin
            # walk/run, ...), so a field left out would read as "given" and overwrite the outfit's animation.
            full = {"Idle": [], "Breaks": [], "WalkRun": None, "Sprint": None, "SprintStart": None}; full.update(prof)
            prop, vals = self.struct_values(d, full, used)
            r = copy.deepcopy(prop); r["Name"] = rn; r["Value"] = vals; rows.append(r)
        e = d["Exports"][0]
        e["ObjectName"] = name; e["ClassIndex"] = dtc; e["TemplateIndex"] = dtd
        e["Data"][0]["Value"] = st; e["Table"]["Data"] = rows
        e["SerializationBeforeSerializationDependencies"] = [st]; e["CreateBeforeSerializationDependencies"] = used
        e["SerializationBeforeCreateDependencies"] = [dtc, dtd]
        if isinstance(d.get("AssetRegistryRecords"), list): d["AssetRegistryRecords"] = []
        K.save(d, os.path.join(self.out, name + ".json"))
        return path
    def write_component(self, table_path):
        import component
        owners = {g: list(v) for g, v in self.outfit_groups.items()}
        for cls_path in self.g.esquie_outfits():                # vanilla Esquie / Osquio outfits keep their animations
            prof = self.g.profile(cls_path.rsplit("/", 1)[1])
            if "Idle" in prof or "Breaks" in prof: owners["Idle"].append(cls_path)
            if "WalkRun" in prof: owners["WalkRun"].append(cls_path)
            if "Sprint" in prof: owners["Sprint"].append(cls_path)
        component.build(self.g.load("BP_CharacterSkinComponent"), table_path, owners, FIELDS,
                        os.path.join(self.out, "BP_CharacterSkinComponent.json"))
    def rows(self):
        """{class name + "_C": profile fields} for every row of DT_CosplayStudio."""
        rows = {}
        for item_id, slots in self.a.get("outfits", {}).items():
            it = self.g.wardrobe[item_id]; cls = it["class"].rsplit("/", 1)[1]
            prof = self.resolve(item_id, slots, self.g.profile(cls))
            if not prof: continue
            rows[cls + "_C"] = prof
            if slots.get("_all") and it.get("default"):        # base outfit: also every outfit that inherits these groups
                for sib in self.g.wardrobe.values():
                    if sib["kind"] != "outfit" or sib["character"] != it["character"] or sib["class"] == it["class"]: continue
                    scls = sib["class"].rsplit("/", 1)[1]
                    if scls + "_C" in rows and any(k in rows[scls + "_C"] for k in prof): pass
                    own, _ = self.g.own_profile(scls)
                    r = rows.setdefault(scls + "_C", {})
                    for g, f in GROUP_FIELDS.items():
                        if f[0] in prof and f[0] not in r and not any(k in own for k in f):
                            for k in f:
                                if k in prof: r[k] = prof[k]
        for cls_path in self.g.esquie_outfits():                 # vanilla Esquie / Osquio keep priority over haircuts
            cls = cls_path.rsplit("/", 1)[1]
            if cls + "_C" in rows: continue
            own, _ = self.g.own_profile(cls)
            if own: rows[cls + "_C"] = {k: v for k, v in own.items() if k in ("Idle", "Breaks", "WalkRun", "Sprint", "SprintStart")}
        for item_id, slots in self.a.get("haircuts", {}).items():
            it = self.g.wardrobe[item_id]
            base_cls = {"Gustave": "BP_CharacterSkinBase_Noah"}.get(it["character"], "BP_CharacterSkinBase_" + it["character"])
            prof = self.resolve(item_id, slots, self.g.profile(base_cls))
            if prof: rows[it["class"].rsplit("/", 1)[1] + "_C"] = prof
        return {k: v for k, v in rows.items() if v}
    def write_table(self, rows, name="DT_CosplayStudio"):
        base = self.g.load("DT_UniqueMechanic_Transform_Masks")
        path = MOD + name
        d = copy.deepcopy(base)
        rownames = list(rows)
        d["NameMap"] = rownames + [name, path]; d["NamesReferencedFromExportDataCount"] = len(rownames)
        d["FolderName"] = path; d["Imports"] = []; d["SoftObjectPathList"] = []
        eng = K.add_import(d, "/Script/Engine", "/Script/CoreUObject", "Package", 0)
        dtc = K.add_import(d, "DataTable", "/Script/CoreUObject", "Class", eng)
        dtd = K.add_import(d, "Default__DataTable", "/Script/Engine", "DataTable", eng)
        sp = K.add_import(d, "/Game/Animations/ALS_UE5/Misc/S_AnimationProfile_Skins", "/Script/CoreUObject", "Package", 0)
        st = K.add_import(d, "S_AnimationProfile_Skins", "/Script/Engine", "UserDefinedStruct", sp)
        used, out = [], []
        for rn, prof in rows.items():
            # every field written: a data-table row starts from the struct DEFAULTS (MM_Idle, the ALS mannequin walk, ...)
            full = {"Idle": [], "Breaks": [], "WalkRun": None, "Sprint": None, "SprintStart": None}; full.update(prof)
            if not full["Sprint"]: full["SprintStart"] = None
            prop, vals = self.struct_values(d, full, used)
            r = copy.deepcopy(prop); r["Name"] = rn; r["Value"] = vals; out.append(r)
        e = d["Exports"][0]
        e["ObjectName"] = name; e["ClassIndex"] = dtc; e["TemplateIndex"] = dtd
        e["Data"][0]["Value"] = st; e["Table"]["Data"] = out
        e["SerializationBeforeSerializationDependencies"] = [st]; e["CreateBeforeSerializationDependencies"] = used
        e["SerializationBeforeCreateDependencies"] = [dtc, dtd]
        if isinstance(d.get("AssetRegistryRecords"), list): d["AssetRegistryRecords"] = []
        K.save(d, os.path.join(self.out, name + ".json"))
        return path
    def run(self):
        rows = self.rows()
        self.write_table(rows)
        import component
        component.build(self.g.load("BP_CharacterSkinComponent"), FIELDS, os.path.join(self.out, "BP_CharacterSkinComponent.json"))
        self.write_blendspaces()
        return sorted(f for f in os.listdir(self.out) if f.endswith(".json"))

def _esquie_outfits(self):
    return [x["class"] for x in self.wardrobe.values() if x["kind"] == "outfit" and ("Esquie" in x["class"] or "Osquio" in x["class"])]
Game.esquie_outfits = _esquie_outfits

if __name__ == "__main__":
    # usage: generator.py <game json root> <anim_scan.json> <wardrobe.json> <assignments.json> <out dir>
    g = Game(sys.argv[1], sys.argv[2], sys.argv[3])
    files = Build(g, json.load(open(sys.argv[4])), sys.argv[5]).run()
    print(len(files), "files:", ", ".join(files))
