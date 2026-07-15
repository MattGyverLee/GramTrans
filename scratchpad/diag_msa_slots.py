"""Read-only diagnostic for the MSA->slot live-proof: ground-truth counts on the
CURRENT target (post-Move) and the source, independent of GUID resolution.

Answers:
  1. How many inflectional-affix MSAs on the SOURCE have non-empty SlotsRC?
  2. How many on the current TARGET have non-empty SlotsRC (did the consumer
     wire anything)?
  3. Are source affix-MSA GUIDs present on the target (guid-preserved)?  This
     tells us whether the consumer's remap.get(src,src) + _resolve_target_by_guid
     could ever have found them.
Read-only. ASCII output.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SOURCE = os.environ.get("GT_SOURCE", "Ejagham Mini")
TARGET = os.environ.get("GT_TARGET", "Target")


def _count_infl_msas(handle):
    """Return (infl_msa_guids_with_slots, all_infl_msa_count) for a project."""
    from gramtrans.Lib import categories
    from gramtrans.Lib.preview import _classname_of
    cast = categories._cast_lcm
    gid = categories._guid_str_from
    with_slots = {}   # guid -> slot count
    all_infl = 0
    for e in categories._iter_lex_entries(handle):
        e = cast(e, "ILexEntry")
        for msa in getattr(e, "MorphoSyntaxAnalysesOC", None) or []:
            if _classname_of(msa) != "MoInflAffMsa":
                continue
            all_infl += 1
            ia = cast(msa, "IMoInflAffMsa")
            slots = list(getattr(ia, "SlotsRC", None) or [])
            if slots:
                with_slots[gid(ia)] = len(slots)
    return with_slots, all_infl


def main() -> int:
    from gramtrans.Lib import categories
    from harness import full_run

    print("=" * 72)
    print("== SOURCE (%s) infl-affix MSA / SlotsRC inventory" % SOURCE)
    print("=" * 72)
    src = full_run._open_source_readonly(SOURCE)
    try:
        src_with_slots, src_all = _count_infl_msas(src)
    finally:
        try:
            src.CloseProject()
        except Exception:  # noqa: BLE001
            pass
    print("  MoInflAffMsa total        : %d" % src_all)
    print("  ...with non-empty SlotsRC : %d" % len(src_with_slots))
    print("  ...total slot refs        : %d" % sum(src_with_slots.values()))

    print("\n" + "=" * 72)
    print("== TARGET (%s) infl-affix MSA / SlotsRC inventory (post-Move)" % TARGET)
    print("=" * 72)
    tgt = full_run._open_source_readonly(TARGET)
    try:
        tgt_with_slots, tgt_all = _count_infl_msas(tgt)
        # Guid-preservation check: how many SOURCE msa guids exist on target?
        resolve = categories._resolve_target_by_guid
        cast = categories._cast_lcm
        preserved = 0
        sample = list(src_with_slots.keys())[:5]
        for g in src_with_slots:
            if cast(resolve(tgt, g), "IMoInflAffMsa") is not None:
                preserved += 1
    finally:
        try:
            tgt.CloseProject()
        except Exception:  # noqa: BLE001
            pass
    print("  MoInflAffMsa total        : %d" % tgt_all)
    print("  ...with non-empty SlotsRC : %d" % len(tgt_with_slots))
    print("  ...total slot refs        : %d" % sum(tgt_with_slots.values()))
    print("  SOURCE msa-with-slots GUIDs also resolvable on TARGET : %d / %d"
          % (preserved, len(src_with_slots)))
    print("  (sample source guids: %s)" % ", ".join(g[:8] for g in sample))

    print("\n" + "-" * 72)
    if len(tgt_with_slots) > 0:
        print("  VERDICT: target HAS affix MSAs with wired SlotsRC (%d) -- the"
              % len(tgt_with_slots))
        print("           consumer DID wire slots; the run-driver probe missed them")
        print("           due to a GUID-mapping mismatch (source guids not"
              " preserved / not in remap).")
    else:
        print("  VERDICT: target has ZERO affix MSAs with wired SlotsRC -- the")
        print("           MSA->slot wiring did NOT land on live. Producer works")
        print("           (79 bindings) but the consumer path did not wire on")
        print("           the target. Real gap beyond the producer fix.")
    if preserved == 0 and len(src_with_slots) > 0:
        print("  NOTE: 0 source msa-with-slots GUIDs resolve on target -> MSAs are")
        print("        NOT guid-preserved and NOT in identity_remap, so the")
        print("        consumer's remap.get(src,src)+resolve can NEVER find them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
