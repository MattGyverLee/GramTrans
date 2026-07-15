"""Live validation driver for the #28 MSA->slot producer port (FR-333).

ATTENDED / DESTRUCTIVE. Proves that inflectional-affix MSA slot wiring lands on
a LIVE target end to end.

Architecture (verified in categories.py):
  - The owned-child copy creates each MoInflAffMsa with `slots=None`
    (categories.py CreateInflAff) -- SlotsRC is DELIBERATELY DEFERRED. So the
    only thing that can wire SlotsRC on the target is the 17.1 sub-pass.
  - PRODUCER (the fix): `_populate_msa_slot_bindings` (preview.py) fills
    plan.msa_slot_bindings via an IMoInflAffMsa cast. Pre-fix the only producer
    was a getattr duck path that no-opped on live LCM (SlotsRC hidden on the
    base interface) -> empty dict -> nothing to wire. DECISIVE metric:
    len(plan.msa_slot_bindings) > 0 on live (was 0 pre-fix).
  - CONSUMER: `_run_171_subpass` (categories.py) reads plan.msa_slot_bindings +
    plan.identity_remap (populated DURING execute), resolves each target MSA,
    and Adds its slots (idempotent membership guard).

Metric = a project-wide count of target affix MSAs with non-empty SlotsRC
(GUID-resolution-independent -- an earlier driver bug probed with the pre-move
preview's empty identity_remap and wrongly resolved 0). Acceptance: target
wired count 0 -> N == source wired count, idempotent across a re-Move.

ATTENDED-ONLY: live restore + destructive Move. NEVER run under an unattended
loop. Run from the worktree:  python scratchpad/run_msa_slot_live.py
ASCII-only output (Windows-terminal safe).
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
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Target"
BACKUP = _ROOT / "backups" / "Target 2026-07-06 0218.fwbackup"


def _banner(msg: str) -> None:
    print("\n" + "=" * 72)
    print("== " + msg)
    print("=" * 72)


def count_affix_slots(project_name):
    """Project-wide: (count of MoInflAffMsa with non-empty SlotsRC, total slot
    refs, total MoInflAffMsa). Reopens read-only; GUID-resolution-independent."""
    from gramtrans.Lib import categories
    from gramtrans.Lib.preview import _classname_of
    from harness import full_run

    handle = full_run._open_source_readonly(project_name)
    try:
        cast = categories._cast_lcm
        wired = 0
        total_slots = 0
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
                    wired += 1
                    total_slots += len(slots)
        return wired, total_slots, all_infl
    finally:
        try:
            handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


def run_move(label):
    """Full Move SOURCE -> TARGET. Returns (n_bindings, n_slot_refs, consumer_skips)."""
    from gramtrans.Lib import api
    from gramtrans.Lib.debuglog import DEBUG_ENV
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    from harness import full_run

    os.environ.setdefault(DEBUG_ENV, "1")
    _banner(label)
    source_handle = full_run._open_source_readonly(SOURCE)
    context = None
    try:
        stub = api.initialize_run(
            source_handle, source_project_name=SOURCE, source_project_path="")
        choice = api.TargetCandidate(project_name=TARGET, project_path=TARGET_PATH)
        context = api.bind_target(stub, choice)
        selection = full_run.build_full_selection(exclude=frozenset())
        src_vern = source_handle.GetDefaultVernacularWS()[0]
        tgt_vern = context.target_handle.GetDefaultVernacularWS()[0]
        ws_mapping = WSMapping(entries=(WSMappingEntry(
            source_ws_id=src_vern, source_ws_kind=WSKind.VERNACULAR,
            target_ws_id=tgt_vern, create_in_target=False),))

        state, plan = api.compute_preview(context, selection, ws_mapping=ws_mapping)
        if state is not api.PreviewState.PREVIEW_READY:
            raise RuntimeError("compute_preview returned %r" % (state,))
        bindings = dict(getattr(plan, "msa_slot_bindings", {}) or {})
        n_bindings = len(bindings)
        n_slot_refs = sum(len(v or []) for v in bindings.values())
        print("[PLAN] actions=%d skips=%d" % (len(plan.actions), len(plan.skips)))
        print("[PLAN] msa_slot_bindings (PRODUCER on live LCM): %d MSAs / %d slot refs"
              % (n_bindings, n_slot_refs))
        if n_bindings == 0:
            print("\n[WARN] Producer yielded 0 bindings on live; cannot prove "
                  "FR-333 on this pair. Aborting BEFORE any write.")
            return 0, 0, None

        _banner("EXECUTE MOVE (destructive)")
        report = api.execute_move(context, plan)
        added = sum(v.added for v in report.per_category.values())
        skipped = sum(v.skipped for v in report.per_category.values())
        # After execute, plan.identity_remap is populated; count consumer skips.
        remap = dict(getattr(plan, "identity_remap", {}) or {})
        consumer_skips = [
            s for s in report.skips
            if getattr(getattr(s, "reason", None), "name", "") == "DEPENDENCY_UNRESOLVED"
            and ("msa_guid=" in (getattr(s, "detail", "") or "")
                 or "slot_guid=" in (getattr(s, "detail", "") or ""))
        ]
        print("[MOVE] added=%d skipped=%d | identity_remap now %d entries | "
              "MSA-guid keys in remap=%d" % (
                  added, skipped, len(remap),
                  sum(1 for k in bindings if k in remap)))
        print("[MOVE] consumer (17.1 sub-pass) DEPENDENCY_UNRESOLVED skips: %d"
              % len(consumer_skips))
        for s in consumer_skips[:5]:
            print("[MOVE]   SKIP %s" % ((getattr(s, "detail", "") or "")[:80]))
        return n_bindings, n_slot_refs, consumer_skips
    finally:
        if context is not None:
            try:
                api._close_project_watchdog(
                    context.target_handle, api._SCHEMA_CLOSE_TIMEOUT_S, "target")
            except Exception as exc:  # noqa: BLE001
                print("[WARN] target close: %s" % exc)
        try:
            source_handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    from harness import restore

    _banner("SOURCE affix-slot inventory (%s)" % SOURCE)
    src_wired, src_slots, src_all = count_affix_slots(SOURCE)
    print("  MoInflAffMsa=%d  with-SlotsRC=%d  slot-refs=%d"
          % (src_all, src_wired, src_slots))

    _banner("RESTORE Target from clean backup")
    print("[INFO] backup: %s" % BACKUP)
    restore.restore_target(TARGET, backup_path=str(BACKUP))

    base_wired, base_slots, base_all = count_affix_slots(TARGET)
    print("[BASELINE] target MoInflAffMsa=%d  with-SlotsRC=%d  slot-refs=%d"
          % (base_all, base_wired, base_slots))

    n_b1, n_sr1, skips1 = run_move("live Move #1 (%s -> %s)" % (SOURCE, TARGET))
    if skips1 is None:
        print("\n[SKIP] FR-333 live proof not applicable on this pair.")
        return 2
    p1_wired, p1_slots, p1_all = count_affix_slots(TARGET)
    print("[POST#1] target MoInflAffMsa=%d  with-SlotsRC=%d  slot-refs=%d"
          % (p1_all, p1_wired, p1_slots))

    n_b2, n_sr2, skips2 = run_move("idempotent re-Move #2")
    p2_wired, p2_slots, p2_all = count_affix_slots(TARGET)
    print("[POST#2] target MoInflAffMsa=%d  with-SlotsRC=%d  slot-refs=%d"
          % (p2_all, p2_wired, p2_slots))

    _banner("SUMMARY (FR-333 / #28 MSA->slot live proof)")
    checks = [
        ("PRODUCER works on live LCM: msa_slot_bindings > 0 (was 0 pre-fix)",
         n_b1 > 0),
        ("target SlotsRC wiring 0 -> N (baseline %d -> post %d)"
         % (base_wired, p1_wired), base_wired == 0 and p1_wired > 0),
        ("CONSUMER wired all source affix slots on target (post %d == source %d)"
         % (p1_wired, src_wired), p1_wired == src_wired and p1_slots == src_slots),
        ("no consumer DEPENDENCY_UNRESOLVED skips", len(skips1) == 0),
        ("idempotent: re-Move leaves target wiring stable (%d -> %d)"
         % (p1_wired, p2_wired),
         p2_wired == p1_wired and p2_slots == p1_slots),
    ]
    ok = True
    for name, passed in checks:
        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))
        ok = ok and passed
    print("  [INFO] producer bindings Move#1=%d Move#2=%d" % (n_b1, n_b2))
    print("\n[%s] FR-333 / #28 MSA->slot live validation"
          % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
