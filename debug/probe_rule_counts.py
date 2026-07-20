"""Read-only: count PhonRules across candidate projects, and for the first
project that HAS rules, run merge_preview.props_for() on one rule.
ASCII-only output. Run: python debug/probe_rule_counts.py
"""
from __future__ import annotations
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src" / "gramtrans" / "Lib"))

CANDIDATES = [
    "Ejagham025Src", "Ejagham029Src", "EjaghamCfgSrc", "Ejagham Mini",
    "Hdi", "IndonesianHC", "Esperanto", "Mbugwe Lizzie HCPractice",
    "Iceve-Maci Test-Iceve", "Aweti",
]


def main() -> None:
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # type: ignore
        if Sldr.IsInitialized:
            Sldr.Cleanup()
        Sldr.Initialize(True)
    except Exception:  # noqa: BLE001
        pass
    from flexicon import FLExProject
    import merge_preview as mp

    for name in CANDIDATES:
        proj = FLExProject()
        try:
            proj.OpenProject(projectName=name, writeEnabled=False)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {name}: {type(exc).__name__}")
            continue
        try:
            rules = list(proj.PhonRules.GetAll())
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] PhonRules.GetAll raised {exc!r}")
            proj.CloseProject()
            continue
        print(f"[{name}] PhonRules = {len(rules)}")
        for r in rules[:3]:
            guid = str(getattr(r, "Guid", "?"))
            try:
                raw = proj.PhonRules.GetSyncableProperties(r)
            except Exception as exc:  # noqa: BLE001
                raw = f"<raised {exc!r}>"
            try:
                props = mp.props_for(proj, "phonological_rules", guid)
            except Exception as exc:  # noqa: BLE001
                props = f"<raised {exc!r}>"
            print(f"    {guid[:8]} syncable={raw}")
            print(f"    {guid[:8]} preview ={props}")
        proj.CloseProject()

    print("[DONE]")


if __name__ == "__main__":
    main()
