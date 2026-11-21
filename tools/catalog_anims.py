"""anim_scan.json -> animations.json: mannequin-skeleton animations with source, owner, slot guess and world-locomotion use."""
import json, re, os, sys, collections
SKEL = "SK_UE5_Mannequin"
BATTLE = re.compile(r"(attack|skill|hit|death|dead|die|stun|dodge|parry|counter|combo|cast|turn|react|spawn|intro|outro|break_|"
                    r"jump|fall|land|taunt|shoot|aim|charge|slash|strike|kick|punch|grab|throw|block|guard|knock|flinch|ultimate|"
                    r"_atk|special|qte|cinematic|cs_|sequence|montage|_add|additive|pose|cam_)", re.I)
SLOTS = [("sprint", re.compile(r"sprint", re.I)), ("run", re.compile(r"(^|[_ ])(run|jog)", re.I)),
         ("walk", re.compile(r"walk", re.I)), ("idle", re.compile(r"idle", re.I))]
def source(path):
    p = path.split("/")
    if p[2:4] == ["Characters", "Heros"]: return "hero", p[4]
    if p[2:4] == ["Characters", "Enemies"]:
        # owner = the folder right before Anims/Animations/Animation, else last folder
        for i, x in enumerate(p):
            if x.lower().startswith("anim") and i > 4: return "enemy", p[i - 1]
        return "enemy", p[-2]
    if p[2] == "Characters" and p[3] in ("NPCs", "Gestrals", "Wildlife", "CleasTowerNPC"):
        for i, x in enumerate(p):
            if x.lower().startswith("anim") and i > 4: return "npc", p[i - 1]
        return "npc", p[4] if len(p) > 5 else p[-2]
    if p[2] == "Animations": return "library", p[4] if p[3] == "AnimPacks" and len(p) > 5 else p[3]
    return "other", p[-2]
def build(scan_json, out_json):
    scan = json.load(open(scan_json))
    loco = collections.defaultdict(list)                     # anim -> blend spaces using it
    for bs, v in scan.items():
        if v["class"].startswith("BlendSpace") and v["skeleton"] == SKEL:
            for a in v["anims"]:
                if a.count("/") > 1 and a.rsplit("/", 1)[1] == a.rsplit("/", 2)[1]: a = a.rsplit("/", 1)[0]   # old scans: pkg + "/" + name
                loco[a].append(bs.rsplit("/", 1)[1])
    anims = []
    for path, v in sorted(scan.items()):
        if v["class"] != "AnimSequence" or v["skeleton"] != SKEL: continue
        name = path.rsplit("/", 1)[1]; src, owner = source(path)
        slot = next((s for s, rx in SLOTS if rx.search(name)), None)
        battle = bool(BATTLE.search(name)) or "/BattleTurn/" in path and not re.search(r"world", name, re.I)
        anims.append({"path": path, "name": name, "source": src, "owner": owner, "slot": slot,
                      "battle": battle, "locomotion": loco.get(path, [])})
    json.dump(anims, open(out_json, "w"), indent=1)
    return anims
if __name__ == "__main__":
    a = build(sys.argv[1], sys.argv[2])
    c = collections.Counter((x["source"], x["slot"]) for x in a if not x["battle"])
    print(len(a), "mannequin anims;", sum(1 for x in a if x["locomotion"]), "used by blend spaces")
    for k, n in sorted(c.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))): print("  ", k, n)
    owners = collections.Counter(x["owner"] for x in a if x["source"] == "enemy" and x["slot"] and not x["battle"])
    print("enemy owners with locomotion-ish anims:", len(owners)); print("  ", ", ".join(sorted(owners)))
