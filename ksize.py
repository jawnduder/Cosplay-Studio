# In-memory (iCode) size of a UAssetAPI Kismet expression, UE5 layout: pointers 8 bytes, script names 12 bytes.
def T(x): return x["$type"].split(".")[-1].split(",")[0]
def strsize(x):
    t = T(x)
    if t == "EX_StringConst": return 1 + len(x["Value"].encode("latin-1")) + 1
    if t == "EX_UnicodeStringConst": return 1 + 2 * (len(x["Value"]) + 1)
    raise ValueError(t)
def size(x):
    t = T(x)
    if t in ("EX_LocalVariable","EX_InstanceVariable","EX_LocalOutVariable","EX_DefaultVariable","EX_ObjectConst"): return 9
    if t in ("EX_True","EX_False","EX_Self","EX_NoObject","EX_Nothing","EX_PopExecutionFlow","EX_EndOfScript","EX_IntZero","EX_IntOne"): return 1
    if t == "EX_ByteConst": return 2
    if t in ("EX_IntConst","EX_FloatConst","EX_Jump","EX_PushExecutionFlow"): return 5
    if t in ("EX_DoubleConst","EX_Int64Const","EX_UInt64Const"): return 9
    if t == "EX_NameConst": return 13
    if t in ("EX_StringConst","EX_UnicodeStringConst"): return strsize(x)
    if t in ("EX_VectorConst","EX_RotationConst"): return 25
    if t == "EX_Let": return 1 + 8 + size(x["Variable"]) + size(x["Expression"])
    if t in ("EX_LetBool","EX_LetObj","EX_LetWeakObjPtr","EX_LetDelegate","EX_LetMulticastDelegate"):
        return 1 + size(x["VariableExpression"]) + size(x["AssignmentExpression"])
    if t in ("EX_Context","EX_Context_FailSilent","EX_ClassContext"):
        return 1 + size(x["ObjectExpression"]) + 4 + 8 + size(x["ContextExpression"])
    if t in ("EX_LocalVirtualFunction","EX_VirtualFunction"): return 1 + 12 + sum(map(size, x["Parameters"])) + 1
    if t in ("EX_FinalFunction","EX_CallMath","EX_LocalFinalFunction"): return 1 + 8 + sum(map(size, x["Parameters"])) + 1
    if t == "EX_JumpIfNot": return 5 + size(x["BooleanExpression"])
    if t == "EX_PopExecutionFlowIfNot": return 1 + size(x["BooleanExpression"])
    if t == "EX_Return": return 1 + size(x["ReturnExpression"])
    if t == "EX_StructMemberContext": return 1 + 8 + size(x["StructExpression"])
    if t in ("EX_DynamicCast","EX_ObjToInterfaceCast","EX_MetaCast","EX_CrossInterfaceCast","EX_InterfaceToObjCast"):
        return 1 + 8 + size(x.get("TargetExpression") or x.get("Target"))
    if t == "EX_PrimitiveCast": return 2 + size(x["Target"])
    if t == "EX_InterfaceContext": return 1 + size(x["InterfaceValue"])
    if t == "EX_SoftObjectConst": return 1 + size(x["Value"])
    if t == "EX_SetArray": return 1 + size(x["AssigningProperty"]) + sum(map(size, x["Elements"])) + 1
    if t == "EX_StructConst": return 1 + 8 + 4 + sum(map(size, x["Value"])) + 1
    if t == "EX_CallMulticastDelegate": return 1 + 8 + size(x["Delegate"]) + sum(map(size, x["Parameters"])) + 1
    if t == "EX_SwitchValue":
        return 1 + 2 + 4 + size(x["IndexTerm"]) + sum(size(c["CaseIndexValueTerm"]) + 4 + size(c["CaseTerm"]) for c in x["Cases"]) + size(x["DefaultTerm"])
    if t == "EX_TextConst":
        v = x["Value"]; k = v["TextLiteralType"]
        if k == "Empty": return 2
        if k == "LocalizedText": return 2 + size(v["LocalizedSource"]) + size(v["LocalizedKey"]) + size(v["LocalizedNamespace"])
        if k == "InvariantText": return 2 + size(v["InvariantLiteralString"])
        if k == "LiteralString": return 2 + size(v["LiteralString"])
        if k == "StringTableEntry": return 2 + 8 + size(v["StringTableId"]) + size(v["StringTableKey"])
    if t == "EX_SkipOffsetConst": return 5
    if t == "EX_ComputedJump": return 1 + size(x["CodeOffsetExpression"])
    if t == "EX_LetValueOnPersistentFrame": return 1 + 8 + size(x["AssignmentExpression"])
    if t == "EX_BindDelegate": return 1 + 12 + size(x["Delegate"]) + size(x["ObjectTerm"])
    if t in ("EX_AddMulticastDelegate", "EX_RemoveMulticastDelegate"): return 1 + size(x["Delegate"]) + size(x["DelegateToAdd"])
    if t in ("EX_SetMap","EX_SetSet"): return 1 + size(x.get("MapProperty") or x.get("SetProperty")) + 4 + sum(map(size, x["Elements"])) + 1
    if t == "EX_SetConst" or t == "EX_MapConst" or t == "EX_ArrayConst": return 1 + 8 + 4 + sum(map(size, x["Elements"] if "Elements" in x else x["Value"])) + 1
    if t == "EX_Assert": return 1 + 2 + 1 + size(x["AssertExpression"])
    if t == "EX_WireTracepoint" or t == "EX_Tracepoint": return 1
    raise ValueError("no size rule for " + t)
