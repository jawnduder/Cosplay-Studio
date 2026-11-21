"""Animation logic in BP_CharacterSkinComponent (v2: fully data-driven, the same file for every build).
ApplyAnimationProfile: P = worn outfit's profile.
  1. Row named after the OUTFIT class in DT_CosplayStudio (soft-loaded): every group the row gives is written into P, and the
     group is marked as owned by the outfit.
  2. Row named after the HAIRCUT class: every group it gives is written into P unless the outfit owns that group.
  Groups: Idle (Idle has entries -> Idle + Breaks), WalkRun (set), Sprint (set -> Sprint + SprintStart).
Then P is applied (DialogueABP stays the wearer's). OnFaceSkinAssigned, OnSkinAssignCompleted and SetCharacterCustomization also call ApplyAnimationProfile;
the haircut comes from CurrentCharacterCustomization (the spawned face object only as a fallback).
Because the per-build data lives only in the table, a writer only has to produce the table (and blend spaces)."""
import copy
import kbuild as K
from ksize import T

TABLE = "/Game/Mods/CosplayStudio/DT_CosplayStudio"

def build(d, FIELDS, out_path, table_path=TABLE):
    orig = list(d["NameMap"]); n_imp0 = len(d["Imports"])
    imp = lambda o, outer=None: K.find_import(d, o, outer_obj=outer)
    eng = K.find_import(d, "/Script/Engine", "Package")
    def lib(c): return imp(c) or K.add_import(d, c, "/Script/CoreUObject", "Class", eng)
    def fn(n, c): return imp(n, c) or K.add_import(d, n, "/Script/CoreUObject", "Object", lib(c))
    OR, AND, NOT, GT = (fn(n, "KismetMathLibrary") for n in ("BooleanOR", "BooleanAND", "Not_PreBool", "Greater_IntInt"))
    S2N = fn("Conv_StringToName", "KismetStringLibrary")
    ISV, GON, LOAD = (fn(n, "KismetSystemLibrary") for n in ("IsValid", "GetObjectName", "LoadAsset_Blocking"))
    GOC = imp("GetObjectClass", "GameplayStatics")
    ALEN, GROW = fn("Array_Length", "KismetArrayLibrary"), fn("GetDataTableRowFromName", "DataTableFunctionLibrary")
    DEF_ARR = imp("Default__KismetArrayLibrary") or K.add_import(d, "Default__KismetArrayLibrary", "/Script/Engine", "KismetArrayLibrary", eng)
    DEF_DTL = imp("Default__DataTableFunctionLibrary") or K.add_import(d, "Default__DataTableFunctionLibrary", "/Script/Engine", "DataTableFunctionLibrary", eng)
    DTCLS = imp("DataTable") or K.add_import(d, "DataTable", "/Script/CoreUObject", "Class", eng)
    SAPS = imp("S_AnimationProfile_Skins")
    SCC, CLS = imp("S_CharacterCustomization"), imp("Class")
    LOADCLS = fn("LoadClassAsset_Blocking", "KismetSystemLibrary")
    FACEF = "CharacterFaceBase_10_069193A2473BA2E48EDF77841A8F3AFD"
    SKINF = "CharacterSkinBase_9_D6F8B7E048CBA86E677340839167C4FA"
    assert GOC and SAPS

    FI, F = K.export(d, "ApplyAnimationProfile", "FunctionExport")
    cls = [e for e in d["Exports"] if "ClassExport" in e["$type"]][0]
    pp = copy.deepcopy([p for p in cls["LoadedProperties"] if p["Name"] == "AnimationProfile"][0]); pp["PropertyFlags"] = "CPF_None"
    p1 = copy.deepcopy(pp); p1["Name"] = "CS_Profile"; p2 = copy.deepcopy(pp); p2["Name"] = "CS_Row"
    K.add_props(d, F, [p1, p2, K.prop_obj("CS_Table", DTCLS), K.prop_bool("CS_Found"), K.prop_int("CS_Len"),
                       K.prop_bool("CS_OwnIdle"), K.prop_bool("CS_OwnWalk"), K.prop_bool("CS_OwnSprint"),
                       K.prop_obj("CS_HairClass", CLS), K.prop_obj("CS_SkinClass", CLS)])
    L = lambda n: K.lv(n, FI)
    P, R = (lambda: L("CS_Profile")), (lambda: L("CS_Row"))
    pm = lambda k: K.member(P(), FIELDS[k], SAPS)
    rm = lambda k: K.member(R(), FIELDS[k], SAPS)
    def lookup_cls(cls_expr):      # CS_Found = GetDataTableRowFromName(CS_Table, Name(GetObjectName(cls)), CS_Row)
        return K.letbool(L("CS_Found"), K.ctx(K.objc(DEF_DTL), K.final(GROW, L("CS_Table"),
                         K.math(S2N, K.math(GON, cls_expr)), R()), K.KPP("CS_Found", FI)))
    def lookup(obj_expr): return lookup_cls(K.math(GOC, obj_expr))
    def apply_row(tag, gate_idle, gate_walk, gate_sprint, mark):
        """write the row's groups into P (gated); mark=True: remember them as owned."""
        out = [K.let(L("CS_Len"), K.ctx(K.objc(DEF_ARR), K.final(ALEN, rm("Idle")), K.KPP("CS_Len", FI))),
               K.jif(K.math(AND, K.math(GT, L("CS_Len"), K.intc(0)), gate_idle), tag + "w"),
               K.let(pm("Idle"), rm("Idle")), K.let(pm("Breaks"), rm("Breaks"))]
        if mark: out.append(K.letbool(L("CS_OwnIdle"), K.X("EX_True")))
        out += [("label", tag + "w"),
                K.jif(K.math(AND, K.math(ISV, rm("WalkRun")), gate_walk), tag + "s"),
                K.let(pm("WalkRun"), rm("WalkRun"))]
        if mark: out.append(K.letbool(L("CS_OwnWalk"), K.X("EX_True")))
        out += [("label", tag + "s"),
                K.jif(K.math(AND, K.math(ISV, rm("Sprint")), gate_sprint), tag + "end"),
                K.let(pm("Sprint"), rm("Sprint")), K.let(pm("SprintStart"), rm("SprintStart"))]
        if mark: out.append(K.letbool(L("CS_OwnSprint"), K.X("EX_True")))
        return out + [("label", tag + "end")]

    code0 = F["ScriptBytecode"]
    skin_prof = copy.deepcopy(code0[5]["ContextExpression"]["Parameters"][0])          # SpawnedCharacterSkin.AnimationProfile
    apply_stmt = copy.deepcopy(code0[5]); apply_stmt["ContextExpression"]["Parameters"][0] = P()
    obj_path = table_path + "." + table_path.rsplit("/", 1)[1]
    T_ = lambda: K.X("EX_True")
    cdo_prof = copy.deepcopy(skin_prof); cdo_prof["$type"] = cdo_prof["$type"].replace("EX_Context", "EX_ClassContext")
    cdo_prof["ObjectExpression"] = L("CS_SkinClass")                                  # CS_SkinClass's class defaults .AnimationProfile
    # the outfit: CurrentCharacterCustomization (always current; party followers' spawned skin object is gone after loading),
    # the spawned skin object if that is empty
    prog = [K.letobj(L("CS_SkinClass"), K.math(LOADCLS, K.member(K.iv("CurrentCharacterCustomization", 1), SKINF, SCC))),
            K.jif(K.math(ISV, L("CS_SkinClass")), "spawned"),
            K.let(P(), cdo_prof),
            K.jump("profok"),
            ("label", "spawned"),
            K.jif(K.math(ISV, K.iv("SpawnedCharacterSkin", 1)), "end"),
            K.let(P(), skin_prof),
            K.letobj(L("CS_SkinClass"), K.math(GOC, K.iv("SpawnedCharacterSkin", 1))),
            ("label", "profok"),
            K.letbool(L("CS_OwnIdle"), K.X("EX_False")), K.letbool(L("CS_OwnWalk"), K.X("EX_False")), K.letbool(L("CS_OwnSprint"), K.X("EX_False")),
            K.letobj(L("CS_Table"), K.dyncast(DTCLS, K.math(LOAD, K.X("EX_SoftObjectConst", Value=K.strc(obj_path))))),
            K.jif(K.math(ISV, L("CS_Table")), "apply"),
            # 1. outfit row
            lookup_cls(L("CS_SkinClass")),
            K.jif(L("CS_Found"), "hair")] + apply_row("o", T_(), T_(), T_(), True) + [
            ("label", "hair"),
            # 2. haircut row: the haircut in CurrentCharacterCustomization (always current, also on followers whose face
            #    object is not re-assigned on a haircut-only change); the spawned face object if that is empty
            K.letobj(L("CS_HairClass"), K.math(LOADCLS, K.member(K.iv("CurrentCharacterCustomization", 1), FACEF, SCC))),
            K.jif(K.math(ISV, L("CS_HairClass")), "hairobj"),
            lookup_cls(L("CS_HairClass")),
            K.jump("hairrow"),
            ("label", "hairobj"),
            K.jif(K.math(ISV, K.iv("SpawnedCharacterFace", 1)), "apply"),
            lookup(K.iv("SpawnedCharacterFace", 1)),
            ("label", "hairrow"),
            K.jif(L("CS_Found"), "apply")] + apply_row("h", K.math(NOT, L("CS_OwnIdle")), K.math(NOT, L("CS_OwnWalk")),
                                                      K.math(NOT, L("CS_OwnSprint")), False)
    tail = copy.deepcopy(code0[:5]); tail[4]["CodeOffset"] = "end"
    prog += [("label", "apply")] + tail + [apply_stmt, ("label", "end"), K.ret(), K.eos()]
    code, n, _ = K.assemble(prog)
    F["ScriptBytecode"] = code
    for i in range(-len(d["Imports"]), -n_imp0):
        if d["Imports"][-i - 1]["ClassName"] != "Package": K.add_dep(F, "CreateBeforeSerializationDependencies", i)
    K.names_in(d, code)

    FI2, F2 = K.export(d, "OnFaceSkinAssigned", "FunctionExport")
    c2 = F2["ScriptBytecode"]; offs = K.offsets(c2)
    labels = {s["CodeOffset"]: "L%d" % s["CodeOffset"] for s in c2 if "CodeOffset" in s}
    prog2 = []
    for o, s in zip(offs, c2):
        if o in labels: prog2.append(("label", labels[o]))
        s = copy.deepcopy(s)
        if "CodeOffset" in s: s["CodeOffset"] = labels[s["CodeOffset"]]
        prog2.append(s)
        if T(s) in ("EX_LocalVirtualFunction", "EX_LocalFinalFunction") and s.get("VirtualFunctionName") == "SetupCharacterFace":
            prog2.append(K.vcall("ApplyAnimationProfile"))
    assert any(isinstance(s, dict) and s.get("VirtualFunctionName") == "ApplyAnimationProfile" for s in prog2)
    code2, _, _ = K.assemble(prog2); F2["ScriptBytecode"] = code2; K.names_in(d, code2)
    # OnSkinAssignCompleted (end of every async body/face assignment): apply again, so a character whose face was assigned
    # before / without its body hook (party followers on a haircut change) still ends up with the haircut row.
    FI3, F3 = K.export(d, "OnSkinAssignCompleted", "FunctionExport")
    c3 = F3["ScriptBytecode"]; offs3 = K.offsets(c3)
    labels3 = {s["CodeOffset"]: "M%d" % s["CodeOffset"] for s in c3 if "CodeOffset" in s}
    labels3.update({s["PushingAddress"]: "M%d" % s["PushingAddress"] for s in c3 if "PushingAddress" in s})
    prog3 = [K.vcall("ApplyAnimationProfile")]
    for o, s in zip(offs3, c3):
        if o in labels3: prog3.append(("label", labels3[o]))
        s = copy.deepcopy(s)
        if "CodeOffset" in s: s["CodeOffset"] = labels3[s["CodeOffset"]]
        if "PushingAddress" in s: s["PushingAddress"] = labels3[s["PushingAddress"]]
        prog3.append(s)
    code3, _, _ = K.assemble(prog3); F3["ScriptBytecode"] = code3; K.names_in(d, code3)
    # SetCharacterCustomization: apply right after the new customization is stored (haircut-only changes on followers)
    FI4, F4 = K.export(d, "SetCharacterCustomization", "FunctionExport")
    c4 = F4["ScriptBytecode"]; prog4 = []
    for st in c4:
        st = copy.deepcopy(st); prog4.append(st)
        if T(st) == "EX_LocalFinalFunction" or (T(st) == "EX_FinalFunction" and "Ubergraph" in str(d["Exports"][st["StackNode"] - 1]["ObjectName"] if st["StackNode"] > 0 else "")):
            prog4.append(K.vcall("ApplyAnimationProfile"))
    assert sum(1 for x in prog4 if isinstance(x, dict) and x.get("VirtualFunctionName") == "ApplyAnimationProfile") == 1
    code4, _, _ = K.assemble(prog4); F4["ScriptBytecode"] = code4; K.names_in(d, code4)
    K.fix_name_order(d, orig)
    K.save(d, out_path)
    return n
