"""Cosplay Studio data model (no Qt): catalog, current animations per item, enemy sets, flags, assignments, project files."""
import os, json, collections
import generator, paths
HERE = paths.DATA
SLOTS = ("idle", "walk", "run", "sprint", "sprint_start")
SLOT_LABEL = {"idle": "Idle", "walk": "Walk", "run": "Run", "sprint": "Sprint", "sprint_start": "Sprint start"}
CHARACTERS = ("Gustave", "Lune", "Maelle", "Sciel", "Verso", "Monoco")
BASE_SKIN = {"Gustave": "BP_CharacterSkinBase_Noah"}
def short(path): return path.rsplit("/", 1)[1] if path else "-"

class Catalog:
    def __init__(self, cfg):
        self.cfg = cfg
        self.game = generator.Game(cfg.get("game_json") if cfg.get("uassetgui_mode") else None, os.path.join(HERE, "anim_scan.json"), os.path.join(HERE, "wardrobe.json"))
        self.items = list(self.game.wardrobe.values())
        self.anims = json.load(open(os.path.join(HERE, "animations.json")))
        self.anim_by_path = {a["path"]: a for a in self.anims}
        self.flags = self._load_flags()
        self._profiles = {}
        self.sets = self._build_sets()
        self.hero_starts = {}                       # hero sprint animation -> that hero's sprint start
        for c, cls in (("Lune", "BP_CharacterSkinBase_Lune"), ("Maelle", "BP_CharacterSkinBase_Maelle"), ("Sciel", "BP_CharacterSkinBase_Sciel"),
                       ("Verso", "BP_CharacterSkinBase_Verso"), ("Gustave", "BP_CharacterSkinBase_Noah"), ("Monoco", "BP_CharacterSkinBase_Monoco")):
            try: pr = self.game.profile(cls)
            except FileNotFoundError: continue
            if pr.get("Sprint") and pr.get("SprintStart"): self.hero_starts[pr["Sprint"]] = (c, pr["SprintStart"])
    # ---------------- flags: {path: {"bugged": "note"}}  (user-editable flags.json next to the app)
    def _load_flags(self):
        for p in (paths.user("flags.json"), paths.data("flags.json")):     # user edits first, shipped notes otherwise
            if os.path.exists(p): return json.load(open(p, encoding="utf-8"))
        return {}
    def save_flags(self):
        json.dump(self.flags, open(paths.user("flags.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    def bugged(self, path): return (self.flags.get(path) or {}).get("bugged")
    # ---------------- items
    def items_for(self, character, kind):
        out = [x for x in self.items if x["character"] == character and x["kind"] == kind]
        return sorted(out, key=lambda x: (not x.get("default"), x["name"].lower()))
    def icon(self, item):
        p = item.get("icon_png"); return os.path.join(HERE, p) if p else None
    def current(self, item):
        """the item's own animations (vanilla): {slot: path}; haircuts show the character's base outfit."""
        cls = item["class"].rsplit("/", 1)[1] if item["kind"] == "outfit" else BASE_SKIN.get(item["character"], "BP_CharacterSkinBase_" + item["character"])
        if cls not in self._profiles:
            try: prof = self.game.profile(cls)
            except FileNotFoundError: prof = {}
            cur = {"idle": (prof.get("Idle") or [None])[0], "sprint": prof.get("Sprint"), "sprint_start": prof.get("SprintStart")}
            if prof.get("WalkRun"):
                try: cur["walk"], cur["run"] = self.game.walk_run_of(prof["WalkRun"])
                except KeyError: pass
            self._profiles[cls] = cur
        return self._profiles[cls]
    # ---------------- enemy / NPC world sets from their 1-D world blend spaces
    def _build_sets(self):
        by_bs = collections.defaultdict(dict)
        for a in self.anims:
            if a["source"] in ("enemy", "npc"):
                for bs in a["locomotion"]:
                    s = a["slot"] or "idle"
                    by_bs[bs].setdefault(s, a["path"])
                    by_bs[bs]["owner"] = a["owner"]
        sets = []
        for bs, v in sorted(by_bs.items()):
            if "walk" in v or "run" in v:
                sets.append({"name": "%s (%s)" % (v["owner"], bs), "idle": v.get("idle"), "walk": v.get("walk"), "run": v.get("run")})
        return sets
    # ---------------- animation search
    def search(self, text="", source=None, slot=None, hide_battle=True, world_only=False):
        t = text.lower().split()
        for a in self.anims:
            if source and a["source"] != source: continue
            if slot and a["slot"] != slot: continue
            if hide_battle and a["battle"] and not a["locomotion"]: continue
            if world_only and not a["locomotion"]: continue
            hay = (a["name"] + " " + a["owner"] + " " + a["path"]).lower()
            if all(w in hay for w in t): yield a

class Project:
    """assignments: {"outfits": {id: {slot: path}}, "haircuts": {...}} + notes."""
    def __init__(self):
        self.data = {"outfits": {}, "haircuts": {}}; self.path = None; self.dirty = False
    def bucket(self, item): return self.data["outfits" if item["kind"] == "outfit" else "haircuts"]
    def get(self, item): return self.bucket(item).get(item["id"], {})
    def set_slot(self, item, slot, path):
        b = self.bucket(item); slots = b.setdefault(item["id"], {})
        if path: slots[slot] = path
        else: slots.pop(slot, None)
        if not [k for k in slots if not k.startswith("_")]: b.pop(item["id"], None)
        self.dirty = True
    def set_option(self, item, key, value):
        """options like "_all" live next to the slots (only kept while the item has slots)."""
        slots = self.bucket(item).get(item["id"])
        if slots is None: return False
        if value: slots[key] = value
        else: slots.pop(key, None)
        self.dirty = True; return True
    def clear(self, item): self.bucket(item).pop(item["id"], None); self.dirty = True
    def edited(self, item): return item["id"] in self.bucket(item)
    def count(self): return len(self.data["outfits"]) + len(self.data["haircuts"])
    def save(self, path):
        json.dump({"cosplay_studio": 1, **self.data}, open(path, "w", encoding="utf-8"), indent=1); self.path = path; self.dirty = False
    def load(self, path):
        d = json.load(open(path, encoding="utf-8"))
        self.data = {"outfits": d.get("outfits", {}), "haircuts": d.get("haircuts", {})}; self.path = path; self.dirty = False
    def assignments(self):
        return {"outfits": {k: dict(v) for k, v in self.data["outfits"].items()}, "haircuts": {k: dict(v) for k, v in self.data["haircuts"].items()}}

def copies(slots, current):
    """slots that reuse another slot's animation (e.g. run as sprint): {slot: other slot}."""
    eff = {s: slots.get(s) or current.get(s) for s in SLOTS if s != "sprint_start"}
    out = {}
    for s in eff:
        for o in eff:
            if o != s and SLOTS.index(o) < SLOTS.index(s) and eff[s] and eff[s] == eff[o]: out[s] = o; break
    return out

def conflicts(catalog, project, character):
    """haircut slots that an edited outfit of the same character also sets (the outfit wins there)."""
    groups = {"idle": "idle", "walk": "walkrun", "run": "walkrun", "sprint": "sprint", "sprint_start": "sprint"}
    slots_of = lambda it: [s for s in project.get(it) if s in groups]
    res = []
    for h in catalog.items_for(character, "haircut"):
        hs = {groups[s] for s in slots_of(h)}
        for o in catalog.items_for(character, "outfit"):
            os_ = {groups[s] for s in slots_of(o)}
            both = hs & os_
            if both: res.append((h["name"], o["name"], sorted(both)))
    return res
