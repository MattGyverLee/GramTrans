"""Read-only: does build_phonology_inventory list ALL phon rules, or does it
drop unnamed ones (making them un-previewable)? Run against Aweti (20 rules).
ASCII-only. Run: python debug/probe_rule_inventory.py
"""
from __future__ import annotations
import sys, os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src" / "gramtrans" / "Lib"))
NAME = os.environ.get("GRAMTRANS_SOURCE", "Aweti")


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
    from models import GrammarCategory as GC

    proj = FLExProject()
    proj.OpenProject(projectName=NAME, writeEnabled=False)

    rules = list(proj.PhonRules.GetAll())
    print(f"[{NAME}] PhonRules.GetAll() = {len(rules)}")
    for r in rules:
        g = str(getattr(r, "Guid", "?"))
        cls = getattr(r, "ClassName", "?")
        nm = sel._phon_name_text(r, phoneme=False) if hasattr(sel, "_phon_name_text") else "?"
        empty = sel._phon_is_empty(r, phoneme=False)
        print(f"    {g[:8]} class={cls:24} name={nm!r:30} _phon_is_empty={empty}")

    inv = sel.build_phonology_inventory(proj)
    grp = inv.group_for(GC.PHONOLOGICAL_RULES)
    n_rows = len(grp.rows) if grp else 0
    print(f"[{NAME}] inventory rule ROWS = {n_rows}  (dropped = {len(rules) - n_rows})")
    proj.CloseProject()
    print("[DONE]")


if __name__ == "__main__":
    main()
