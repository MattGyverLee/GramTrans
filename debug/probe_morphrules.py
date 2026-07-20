"""Read-only: identify the MorphRules in a project and check whether the rules
page inventory + preview handle them. ASCII-only.
Run: GRAMTRANS_SOURCE="Ejagham Full" python debug/probe_morphrules.py
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
    import selection as sel

    proj = FLExProject()
    proj.OpenProject(projectName=NAME, writeEnabled=False)
    print(f"[{NAME}]")

    for r in proj.MorphRules.GetAll():
        g = str(getattr(r, "Guid", "?"))
        cls = getattr(r, "ClassName", "?")
        nm = None
        try:
            nm = r.Name.BestAnalysisAlternative.Text
        except Exception:
            pass
        print(f"  MorphRule {g[:8]} class={cls} name={nm!r}")

    inv = sel.build_rules_inventory(proj)
    print(f"  rules_inventory adhoc rows    = {inv.adhoc.count}")
    print(f"  rules_inventory compound rows = {inv.compound.count}")
    for row in list(inv.adhoc.rows) + list(inv.compound.rows):
        print(f"    row guid={row.guid[:8]} subclass={row.subclass} label={row.label!r}")

    proj.CloseProject()
    print("[DONE]")


if __name__ == "__main__":
    main()
