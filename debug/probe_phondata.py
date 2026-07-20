"""Read-only: inspect raw LCM phonology structures in a project to find where
'rules' actually live (PhonRulesOS vs flexicon PhonRules.GetAll vs other).
ASCII-only. Run: GRAMTRANS_SOURCE="Ejagham Full" python debug/probe_phondata.py
"""
from __future__ import annotations
import sys, os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src" / "gramtrans" / "Lib"))
NAME = os.environ.get("GRAMTRANS_SOURCE", "Ejagham Full")


def main() -> None:
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr
        if Sldr.IsInitialized:
            Sldr.Cleanup()
        Sldr.Initialize(True)
    except Exception:
        pass
    from flexicon import FLExProject
    from SIL.LCModel import ILangProject

    proj = FLExProject()
    proj.OpenProject(projectName=NAME, writeEnabled=False)

    print(f"[{NAME}]")
    try:
        print("  flexicon PhonRules.GetAll() =", len(list(proj.PhonRules.GetAll())))
    except Exception as exc:  # noqa: BLE001
        print("  flexicon PhonRules.GetAll() raised", repr(exc))

    lp = ILangProject(proj.project.LangProject)
    pd = getattr(lp, "PhonologicalDataOA", None)
    print("  PhonologicalDataOA =", pd)
    if pd is not None:
        pr = getattr(pd, "PhonRulesOS", None)
        print("  PhPhonData.PhonRulesOS count =", pr.Count if pr is not None else None)
        if pr is not None:
            for r in list(pr)[:10]:
                nm = None
                try:
                    nm = r.Name.BestAnalysisAlternative.Text
                except Exception:
                    pass
                print(f"      rule guid={str(r.Guid)[:8]} class={r.ClassName} name={nm!r}")
        # other owned rule-ish collections on PhPhonData
        for attr in ("PhonRuleFeatsOA", "FeatConstraintsOS", "EnvironmentsOS",
                     "NaturalClassesOS", "PhonemeSetsOS"):
            o = getattr(pd, attr, None)
            cnt = getattr(o, "Count", None) if o is not None else None
            print(f"  PhPhonData.{attr} count = {cnt}")

    # MorphRules (word grammar) for contrast
    try:
        mr = list(proj.MorphRules.GetAll())
        print("  flexicon MorphRules.GetAll() =", len(mr))
    except Exception as exc:  # noqa: BLE001
        print("  flexicon MorphRules.GetAll() raised", repr(exc))

    proj.CloseProject()
    print("[DONE]")


if __name__ == "__main__":
    main()
