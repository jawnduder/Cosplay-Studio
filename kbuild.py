# Helpers for building Kismet bytecode in UAssetAPI JSON.
import json, copy
from ksize import size, T

P = "UAssetAPI.Kismet.Bytecode.Expressions.%s, UAssetAPI"
KPPT = "UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI"
FPT = "UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI"

def load(p): return json.loads(open(p, "rb").read().decode("utf-8"))
def save(d, p):
    for g in d.get("Generations") or []: g["NameCount"] = len(d["NameMap"])
    open(p, "wb").write(json.dumps(d, indent=2).replace("\n", "\r\n").encode("utf-8"))

import re as _re
def name(d, n):
    """Register a name the way UAssetAPI/Unreal store it: "Foo_2" is the entry "Foo" with number 3, so only "Foo" goes in the map."""
    m = _re.match(r"^(.+)_(0|[1-9][0-9]*)$", n)
    base = m.group(1) if m else n
    if base not in d["NameMap"]: d["NameMap"].append(base)
    return n

def export(d, n, kind=None):
    for i, e in enumerate(d["Exports"]):
        if e["ObjectName"] == n and (kind is None or kind in e["$type"]): return i + 1, e
    raise KeyError(n)

def find_import(d, obj, cls=None, outer_obj=None):
    for i, im in enumerate(d["Imports"]):
        if im["ObjectName"] != obj or (cls and im["ClassName"] != cls): continue
        if outer_obj is not None:
            o = im["OuterIndex"]
            if o == 0 or d["Imports"][-o-1]["ObjectName"] != outer_obj: continue
        return -i - 1
    return None

def add_import(d, obj, cls_pkg, cls, outer):
    """outer: import index (or 0 for a package)."""
    for i, im in enumerate(d["Imports"]):
        if im["ObjectName"] == obj and im["ClassName"] == cls and im["OuterIndex"] == outer: return -i - 1
    for n in (obj, cls_pkg, cls): name(d, n)
    d["Imports"].append({"$type": "UAssetAPI.Import, UAssetAPI", "ObjectName": obj, "OuterIndex": outer,
                         "ClassPackage": cls_pkg, "ClassName": cls, "PackageName": None, "bImportOptional": False})
    return -len(d["Imports"])

def copy_import(d, src, idx):
    """Copy import idx (and its outer chain) from asset src into d; returns the new index."""
    im = src["Imports"][-idx-1]
    outer = 0 if im["OuterIndex"] == 0 else copy_import(d, src, im["OuterIndex"])
    return add_import(d, im["ObjectName"], im["ClassPackage"], im["ClassName"], outer)

# ---------------- expressions
def X(t, **kw): return dict({"$type": P % t}, **kw)
def KPP(path, owner): return {"$type": KPPT, "New": {"$type": FPT, "Path": [path] if path else [], "ResolvedOwner": owner}}
NOKPP = lambda: KPP(None, 0)
def lv(n, owner): return X("EX_LocalVariable", Variable=KPP(n, owner))
def iv(n, owner): return X("EX_InstanceVariable", Variable=KPP(n, owner))
def ctx(obj, inner, rv=None):
    return X("EX_Context", ObjectExpression=obj, Offset=size(inner), PropertyType=0,
             RValuePointer=copy.deepcopy(rv) if rv else NOKPP(), ContextExpression=inner)
def vcall(n, *a, local=True): return X("EX_LocalVirtualFunction" if local else "EX_VirtualFunction", VirtualFunctionName=n, Parameters=list(a))
def final(stack, *a): return X("EX_FinalFunction", StackNode=stack, Parameters=list(a))
def lfinal(stack, *a): return X("EX_LocalFinalFunction", StackNode=stack, Parameters=list(a))
def math(stack, *a): return X("EX_CallMath", StackNode=stack, Parameters=list(a))
def let(var, expr):
    """var is an EX_LocalVariable / EX_InstanceVariable / EX_StructMemberContext / EX_Context."""
    t = T(var)
    if t == "EX_StructMemberContext": v = var["StructMemberExpression"]
    elif t == "EX_Context": v = var["RValuePointer"]
    else: v = var["Variable"]
    return X("EX_Let", Value=copy.deepcopy(v), Variable=var, Expression=expr)
def letbool(var, expr): return X("EX_LetBool", VariableExpression=var, AssignmentExpression=expr)
def letobj(var, expr): return X("EX_LetObj", VariableExpression=var, AssignmentExpression=expr)
def member(struct_expr, n, struct_owner): return X("EX_StructMemberContext", StructMemberExpression=KPP(n, struct_owner), StructExpression=struct_expr)
def other_var(obj_expr, n, owner):
    """Assignable member variable of another object."""
    return ctx(obj_expr, iv(n, owner), KPP(n, owner))
def intc(v): return X("EX_IntConst", Value=v)
def bytec(v): return X("EX_ByteConst", Value=v)
def namec(v): return X("EX_NameConst", Value=v)
def strc(v): return X("EX_StringConst", Value=v)
def textc(v):
    return X("EX_TextConst", Value={"$type": "UAssetAPI.Kismet.Bytecode.FScriptText, UAssetAPI", "TextLiteralType": "LiteralString",
             "LocalizedSource": None, "LocalizedKey": None, "LocalizedNamespace": None, "InvariantLiteralString": None,
             "LiteralString": strc(v), "StringTableAsset": None, "StringTableId": None, "StringTableKey": None})
def objc(i): return X("EX_ObjectConst", Value=i)
SELF = lambda: X("EX_Self"); NOTHING = lambda: X("EX_Nothing"); NOOBJ = lambda: X("EX_NoObject")
TRUE = lambda: X("EX_True"); FALSE = lambda: X("EX_False")
def setarray(var, elems): return X("EX_SetArray", AssigningProperty=var, ArrayInnerProp=None, Elements=list(elems))
def dyncast(cls, target): return X("EX_DynamicCast", ClassPtr=cls, Target=target)
def switch(index, cases, default):
    """cases: list of (value_expr, result_expr). Offsets are filled in by place()."""
    return X("EX_SwitchValue", EndGotoOffset=0, IndexTerm=index, DefaultTerm=default,
             Cases=[{"$type": "UAssetAPI.Kismet.Bytecode.Expressions.FKismetSwitchCase, UAssetAPI", "CaseIndexValueTerm": v, "NextOffset": 0, "CaseTerm": r} for v, r in cases])
def jump(target): return X("EX_Jump", CodeOffset=target)
def jif(cond, target): return X("EX_JumpIfNot", CodeOffset=target, BooleanExpression=cond)
def push(target): return X("EX_PushExecutionFlow", PushingAddress=target)
def pop(): return X("EX_PopExecutionFlow")
def popifnot(c): return X("EX_PopExecutionFlowIfNot", BooleanExpression=c)
def ret(e=None): return X("EX_Return", ReturnExpression=e or NOTHING())
def eos(): return X("EX_EndOfScript")

# --------------- serialization-order walker (absolute offsets of nested switch values)
def children(x):
    """(leading bytes, [child exprs or ('raw', n)]) in serialization order, for the types we nest in."""
    t = T(x)
    if t == "EX_Let": return [9, x["Variable"], x["Expression"]]
    if t in ("EX_LetBool", "EX_LetObj"): return [1, x["VariableExpression"], x["AssignmentExpression"]]
    if t in ("EX_Context", "EX_Context_FailSilent"): return [1, x["ObjectExpression"], 12, x["ContextExpression"]]
    if t in ("EX_FinalFunction", "EX_CallMath", "EX_LocalFinalFunction"): return [9] + x["Parameters"] + [1]
    if t in ("EX_VirtualFunction", "EX_LocalVirtualFunction"): return [13] + x["Parameters"] + [1]
    if t == "EX_JumpIfNot": return [5, x["BooleanExpression"]]
    if t == "EX_PopExecutionFlowIfNot": return [1, x["BooleanExpression"]]
    if t == "EX_Return": return [1, x["ReturnExpression"]]
    if t == "EX_StructMemberContext": return [9, x["StructExpression"]]
    if t in ("EX_DynamicCast", "EX_MetaCast"): return [9, x["Target"]]
    if t == "EX_SetArray": return [1, x["AssigningProperty"]] + x["Elements"] + [1]
    return None

def place(x, at):
    """Fill EndGotoOffset/NextOffset of every switch inside x (x starts at absolute offset at)."""
    if T(x) == "EX_SwitchValue":
        p = at + 7; place(x["IndexTerm"], p); p += size(x["IndexTerm"])
        for c in x["Cases"]:
            place(c["CaseIndexValueTerm"], p); p += size(c["CaseIndexValueTerm"]) + 4
            place(c["CaseTerm"], p); p += size(c["CaseTerm"]); c["NextOffset"] = p
        place(x["DefaultTerm"], p); p += size(x["DefaultTerm"]); x["EndGotoOffset"] = p
        assert p == at + size(x)
        return
    ch = children(x)
    if ch is None: return
    p = at
    for c in ch:
        if isinstance(c, int): p += c
        else: place(c, p); p += size(c)
    assert p == at + size(x), (T(x), p - at, size(x))

def assemble(prog):
    """prog: list of statements or ('label', name). Jump targets may be label names. Returns (code, size, labels)."""
    labels, pos = {}, 0
    for s in prog:
        if isinstance(s, tuple): labels[s[1]] = pos
        else: pos += size(s)
    code, pos = [], 0
    for s in prog:
        if isinstance(s, tuple): continue
        for k in ("CodeOffset", "PushingAddress"):
            if isinstance(s.get(k), str): s[k] = labels[s[k]]
        place(s, pos); code.append(s); pos += size(s)
    starts = set(); p = 0
    for s in code: starts.add(p); p += size(s)
    for s in code:
        for k in ("CodeOffset", "PushingAddress"):
            if k in s: assert s[k] in starts, (k, s[k])
    return code, pos, labels

def offsets(code):
    o, out = 0, []
    for s in code: out.append(o); o += size(s)
    return out

# --------------- properties
def prop_int(n, flags="CPF_None"):
    return {"$type": "UAssetAPI.FieldTypes.FGenericProperty, UAssetAPI", "ArrayDim": "TArray", "ElementSize": 4, "PropertyFlags": flags,
            "RepIndex": 0, "RepNotifyFunc": "None", "BlueprintReplicationCondition": "COND_None", "RawValue": None,
            "SerializedType": "IntProperty", "Name": n, "Flags": "RF_Public", "MetaDataMap": None}
def prop_generic(n, typ, sz, flags="CPF_None"):
    p = prop_int(n, flags); p["SerializedType"] = typ; p["ElementSize"] = sz; return p
def prop_bool(n):
    return {"$type": "UAssetAPI.FieldTypes.FBoolProperty, UAssetAPI", "FieldSize": 1, "ByteOffset": 0, "ByteMask": 1, "FieldMask": 255,
            "NativeBool": True, "Value": True, "ArrayDim": "TArray", "ElementSize": 1, "PropertyFlags": "CPF_None", "RepIndex": 0,
            "RepNotifyFunc": "None", "BlueprintReplicationCondition": "COND_None", "RawValue": None, "SerializedType": "BoolProperty",
            "Name": n, "Flags": "RF_Public", "MetaDataMap": None}
def prop_obj(n, cls, flags="CPF_None"):
    p = prop_int(n, flags); p.update({"$type": "UAssetAPI.FieldTypes.FObjectProperty, UAssetAPI", "PropertyClass": cls, "ElementSize": 8, "SerializedType": "ObjectProperty"})
    return p
def prop_struct(n, st, sz, flags="CPF_None"):
    p = prop_int(n, flags); p.update({"$type": "UAssetAPI.FieldTypes.FStructProperty, UAssetAPI", "Struct": st, "ElementSize": sz, "SerializedType": "StructProperty"})
    return p
def prop_array(n, inner, flags="CPF_None"):
    inner = copy.deepcopy(inner); inner["Name"] = n; inner["PropertyFlags"] = "CPF_None"
    p = prop_int(n, flags); p.update({"$type": "UAssetAPI.FieldTypes.FArrayProperty, UAssetAPI", "Inner": inner, "ElementSize": 16, "SerializedType": "ArrayProperty"})
    keys = ["$type", "Inner"] + [k for k in p if k not in ("$type", "Inner")]
    return {k: p[k] for k in keys}

def add_props(d, export_obj, props):
    have = {p["Name"] for p in export_obj["LoadedProperties"]}
    for p in props:
        if p["Name"] in have: continue
        name(d, p["Name"]); name(d, p["SerializedType"])
        if "Inner" in p: name(d, p["Inner"]["SerializedType"])
        export_obj["LoadedProperties"].append(p)

def add_dep(e, key, idx):
    if idx not in e[key]: e[key].append(idx)

def names_in(d, x):
    """Register every FName-ish string used by expressions (paths, function names, name constants)."""
    if isinstance(x, dict):
        t = x.get("$type", "")
        if "FFieldPath" in t: [name(d, n) for n in x["Path"]]
        if "VirtualFunctionName" in x: name(d, x["VirtualFunctionName"])
        if t.startswith(P % "EX_NameConst"): name(d, x["Value"])
        for v in x.values(): names_in(d, v)
    elif isinstance(x, list):
        for v in x: names_in(d, v)

def fix_name_order(d, original_names):
    """New names used by export data must sit inside the first NamesReferencedFromExportDataCount names."""
    n = d.get("NamesReferencedFromExportDataCount")
    if n is None: return 0
    orig = set(original_names)
    new = [x for x in d["NameMap"] if x not in orig]
    old = [x for x in d["NameMap"] if x in orig]
    d["NameMap"] = old[:n] + new + old[n:]
    d["NamesReferencedFromExportDataCount"] = n + len(new)
    return len(new)
