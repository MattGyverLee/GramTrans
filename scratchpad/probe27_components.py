"""Read-only follow-up probe for the T025 live result: did the 6 reproduced
LexEntryRef containers actually get their ComponentLexemesRS wired?

The main driver counts containers + RefType + variant-type, but NOT component
wiring. Move#1's plan reported all 6 refs as C4 out-of-closure drops while C1
created 6 containers -- this probe resolves whether the components landed
(drop report is a false positive) or the containers are component-less
(created AND reported dropped). Reopens Target read-only; casts via _cast_lcm
(#28 layer 2). ASCII-only. Run from the worktree.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

TARGET = os.environ.get("GT_TARGET", "Target")

# The 6 variant ref GUIDs + their owner-entry GUIDs, from the T025 plan log.
REFS = [
    ("ff3f5856-3e02-4bb0-96df-ef895d34ec4f", "1f38e3fa-1142-4af3-ba84-33260db233dd"),
    ("619aa702-161c-4882-b556-6477eb316f50", "3d03ea4a-3b8e-4e6c-9d0f-54699decd297"),
    ("e93cb20f-ebe1-48c5-9fb5-aa76c03ffe63", "728302d7-3bbd-40a2-9756-743399b42243"),
    ("c6ea6096-9a24-4783-8511-5dd26b535f3e", "a4582bc4-2a14-41e6-a817-b95d7df23f26"),
    ("ddd2b43e-ac3a-4599-a012-8a77f05a1cb8", "de0c9a78-3da9-46ab-a79c-5e4d2425e47b"),
    ("a49def35-eaba-4a67-9299-34ccd8eb67d8", "f1f5a814-83a8-446d-8dc9-d038790f29d7"),
]


def main() -> int:
    from gramtrans.Lib import categories
    from harness import full_run

    gid = categories._guid_str_from
    resolve = categories._resolve_target_by_guid
    cast = categories._cast_lcm

    target = full_run._open_source_readonly(TARGET)
    try:
        print("=" * 72)
        print("== COMPONENT-WIRING PROBE on reopened Target (read-only)")
        print("=" * 72)
        total_comp = total_prim = 0
        for ref_guid, owner_guid in REFS:
            entry = cast(resolve(target, owner_guid), "ILexEntry")
            refs = list(getattr(entry, "EntryRefsOS", None) or []) if entry else []
            match = None
            for r in refs:
                if gid(cast(r, "ILexEntryRef")) == ref_guid:
                    match = cast(r, "ILexEntryRef")
                    break
            if match is None:
                print("  ref %s : CONTAINER MISSING" % ref_guid[:8])
                continue
            comps = list(getattr(match, "ComponentLexemesRS", None) or [])
            prims = list(getattr(match, "PrimaryLexemesRS", None) or [])
            total_comp += len(comps)
            total_prim += len(prims)
            rt = getattr(match, "RefType", None)
            vtypes = list(getattr(match, "VariantEntryTypesRS", None) or [])
            print("  ref %s owner=%s RefType=%s components=%d primaries=%d variant_types=%d"
                  % (ref_guid[:8], owner_guid[:8], rt, len(comps), len(prims), len(vtypes)))
            for c in comps:
                print("      component -> %s" % gid(c))
        print("-" * 72)
        print("  TOTAL components wired across 6 refs: %d" % total_comp)
        print("  TOTAL primaries  wired across 6 refs: %d" % total_prim)
        print("-" * 72)
        if total_comp == 0:
            print("  VERDICT: containers are COMPONENT-LESS -- the 6 C4 drop reports are")
            print("           accurate (components genuinely out-of-closure / not wired).")
            print("           0->6 is containers+types only, NOT full ref reproduction.")
        else:
            print("  VERDICT: components DID wire (%d) despite the 6 C4 drop reports --" % total_comp)
            print("           the drop reports are FALSE POSITIVES (P1a heuristic mismatch:")
            print("           _entry_ref_is_reproducible said out-of-closure but the")
            print("           components resolved+wired on the live target).")
        return 0
    finally:
        try:
            target.CloseProject()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
