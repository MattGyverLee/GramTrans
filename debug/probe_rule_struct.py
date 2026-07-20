"""Read-only: dump a phonological rule's internal structure so we can render a
human-readable rule string (input -> output / environment). ASCII-only.
Run: GRAMTRANS_SOURCE="Mbugwe LizzieHC practice" python debug/probe_rule_struct.py
"""
from __future__ import annotations
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(r"d:\Github\_Projects\_LEX\GramTrans")/"src"/"gramtrans"/"Lib"))
NAME = os.environ.get("GRAMTRANS_SOURCE", "Mbugwe LizzieHC practice")


def _txt(x):
    try:
        return x.BestAnalysisAlternative.Text
    except Exception:
        try:
            return x.Text
        except Exception:
            return None


def dump(label, obj, depth=0):
    pad = "  " * depth
    cls = getattr(obj, "ClassName", type(obj).__name__)
    print(f"{pad}{label}: class={cls}")
    for attr in ("Name", "Abbreviation"):
        v = getattr(obj, attr, None)
        if v is not None:
            print(f"{pad}  {attr}={_txt(v)!r}")


def main() -> None:
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr
        if Sldr.IsInitialized: Sldr.Cleanup()
        Sldr.Initialize(True)
    except Exception: pass
    from flexicon import FLExProject
    from SIL.LCModel import IPhSegmentRule, IPhRegularRule, IPhSegRuleRHS
    proj = FLExProject(); proj.OpenProject(projectName=NAME, writeEnabled=False)

    rules = list(proj.PhonRules.GetAll())
    # pick a simple, telling rule
    for r in rules:
        nm = _txt(getattr(r, "Name", None))
        if nm and ("k->ch" in nm or "palatal" in nm or "deletes" in nm):
            target = r
            break
    else:
        target = rules[0]
    print("RULE:", _txt(getattr(target, "Name", None)))
    # unwrap to raw LCM
    inner = getattr(target, "_obj", target)
    seg = IPhSegmentRule(inner)
    print("Direction=", getattr(seg, "Direction", None), "Ord=", getattr(seg, "OrderNumber", None))
    print("-- StrucDescOS (input/LHS) --")
    for i, ctx in enumerate(getattr(seg, "StrucDescOS", []) or []):
        cls = ctx.ClassName
        detail = ""
        # IPhSimpleContextSeg -> FeatureStructureRA? IPhSimpleContextNC -> NaturalClassRA
        for a in ("FeatureStructureRA", "NaturalClassRA"):
            ref = getattr(ctx, a, None)
            if ref is not None:
                detail += f" {a}->{_txt(getattr(ref,'Name',None)) or _txt(getattr(ref,'Abbreviation',None))}"
        print(f"   [{i}] {cls}{detail}")
    reg = IPhRegularRule(inner)
    print("-- RightHandSidesOS --")
    for j, rhs in enumerate(getattr(reg, "RightHandSidesOS", []) or []):
        rhs = IPhSegRuleRHS(rhs)
        print(f"   RHS[{j}] class={rhs.ClassName}")
        for i, ctx in enumerate(getattr(rhs, "StrucChangeOS", []) or []):
            cls = ctx.ClassName
            detail = ""
            for a in ("FeatureStructureRA", "NaturalClassRA"):
                ref = getattr(ctx, a, None)
                if ref is not None:
                    detail += f" {a}->{_txt(getattr(ref,'Name',None)) or _txt(getattr(ref,'Abbreviation',None))}"
            print(f"      change[{i}] {cls}{detail}")
        for side in ("LeftContextOA", "RightContextOA"):
            c = getattr(rhs, side, None)
            print(f"      {side}: {c.ClassName if c is not None else None}")

    proj.CloseProject(); print("[DONE]")


if __name__ == "__main__":
    main()
