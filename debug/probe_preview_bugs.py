"""Read-only probe for two reported preview bugs.

1. Phonological rules: does merge_preview.props_for() return a non-empty
   props dict for a source PhonRule?  (User: "phon rules have no Previews".)
2. Affixes-in-slots: does merge_preview._affix_msa_label() return a real
   label or the '***' placeholder?  (User: affixes come back as '***'.)

Read-only. ASCII-only output (Windows-terminal safe).
Run:  python debug/probe_preview_bugs.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src" / "gramtrans" / "Lib"))

SOURCE = os.environ.get("GRAMTRANS_SOURCE", "Ejagham Mini")


def _bv(prop):
    """Read BestVernacularAlternative text (the proposed fix path)."""
    if prop is None:
        return None
    try:
        best = getattr(prop, "BestVernacularAlternative", None)
        return getattr(best, "Text", None) if best is not None else None
    except Exception as exc:  # noqa: BLE001
        return f"<raised {exc!r}>"


def main() -> None:
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # type: ignore
        if Sldr.IsInitialized:
            Sldr.Cleanup()
        Sldr.Initialize(True)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] SLDR: {exc!r}")

    from flexicon import FLExProject
    import merge_preview as mp

    proj = FLExProject()
    proj.OpenProject(projectName=SOURCE, writeEnabled=False)
    print(f"[OK] opened source read-only: {SOURCE}")

    # ---- Bug 1: phonological rules preview ---------------------------------
    print("\n=== BUG 1: PHONOLOGICAL RULES PREVIEW ===")
    try:
        rules = list(proj.PhonRules.GetAll())
    except Exception as exc:  # noqa: BLE001
        rules = []
        print(f"[ERROR] PhonRules.GetAll() raised: {exc!r}")
    print(f"[INFO] source PhonRules count: {len(rules)}")
    for r in rules[:5]:
        guid = str(getattr(r, "Guid", "?"))
        # raw flexicon syncable props
        try:
            raw = proj.PhonRules.GetSyncableProperties(r)
        except Exception as exc:  # noqa: BLE001
            raw = f"<raised {exc!r}>"
        # what the preview pane would actually show
        try:
            props = mp.props_for(proj, "phonological_rules", guid)
        except Exception as exc:  # noqa: BLE001
            props = f"<raised {exc!r}>"
        print(f"  rule {guid[:8]}")
        print(f"    GetSyncableProperties -> {raw}")
        print(f"    props_for(preview)    -> {props}")

    # ---- Bug 2: affixes in slots ------------------------------------------
    print("\n=== BUG 2: AFFIXES IN SLOTS (*** labels) ===")
    from SIL.LCModel import IPartOfSpeech  # noqa
    found = 0
    for pos in proj.POS.GetAll(recursive=True):
        for tmpl in getattr(pos, "AffixTemplatesOS", ()) or ():
            for slot_attr in ("PrefixSlotsRS", "SuffixSlotsRS"):
                for slot in getattr(tmpl, slot_attr, ()) or ():
                    affixes = list(getattr(slot, "Affixes", None) or [])
                    if not affixes:
                        continue
                    sname = mp._slot_name(slot) if hasattr(mp, "_slot_name") else "?"
                    print(f"  slot '{sname}' ({slot_attr}) : {len(affixes)} affix MSA(s)")
                    for msa in affixes[:4]:
                        label = mp._affix_msa_label(msa)
                        # replicate _affix_msa_label's cast path exactly
                        owner = getattr(msa, "Owner", None)
                        entry = mp._lcm_cast(owner, "ILexEntry") if owner is not None else None
                        lf = getattr(entry, "LexemeFormOA", None) if entry is not None else None
                        form_prop = getattr(lf, "Form", None) if lf is not None else None
                        hwt = getattr(getattr(entry, "HeadWord", None), "Text", None) if entry is not None else None
                        print(f"      entry={owner!r} cast={entry!r} lf={lf!r} headword={hwt!r}")
                        ba = mp._best_analysis_text(form_prop)
                        bv = _bv(form_prop)
                        # full WS enumeration on the lexeme form
                        allws = mp._ms_to_dict(form_prop, mp._ws_defs(proj)) if form_prop is not None else {}
                        lf_cls = getattr(lf, "ClassName", None) if lf is not None else None
                        # allomorph forms
                        allo_forms = []
                        for al in list(getattr(owner, "AlternateFormsOS", None) or [])[:3]:
                            fp = getattr(al, "Form", None)
                            allo_forms.append(mp._ms_to_dict(fp, mp._ws_defs(proj)) if fp is not None else {})
                        print(f"      _affix_msa_label -> {label!r}")
                        print(f"         Form: analysis={ba!r} vern={bv!r} allWS={allws} lfClass={lf_cls}")
                        print(f"         AlternateForms allWS={allo_forms}")
                        found += 1
                    if found >= 8:
                        break
                if found >= 8:
                    break
            if found >= 8:
                break
        if found >= 8:
            break
    if found == 0:
        print("  [INFO] no occupied slots found in source template inventory")

    proj.CloseProject()
    print("\n[DONE]")


if __name__ == "__main__":
    main()
