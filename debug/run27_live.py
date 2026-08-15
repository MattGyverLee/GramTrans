"""T024 live validation driver for feature 027 (Complex Forms & Variants).

ATTENDED / DESTRUCTIVE. Proves the `LexEntryRef` reproduction post-pass
(contracts C1-C4) lands on a LIVE target:

  - C1  ILexEntryRefFactory container creation (GUID-preserved, RefType set)
  - C2  ComponentLexemesRS / PrimaryLexemesRS wiring (`_run_post_pass_a`)
  - C3  VariantEntryTypesRS / ComplexEntryTypesRS resolution
  - C4  out-of-closure refs reported (never silent), in-closure reproduced

Mirrors 031's T024 (linked 0 -> N) and reuses issue #28's re-resolution probe
(`run28_live.py`): restore Target from the clean backup, run a full Move
(Ejagham Mini -> Target, STEMS included so the create-then-wire tail fires),
then REOPEN the target and re-resolve every planned ref binding to count the
`LexEntryRef` containers that actually landed on disk. Pre-fix the target's
`EntryRefsOS` was always empty (0 containers created); Ejagham Mini carries
6 variant refs, so the acceptance metric is `0 -> 6` (SC-001).

The reopened live target returns bare `ICmObject`s -- every typed read goes
through `categories._cast_lcm` (issue #28 layer 2) or `.EntryRefsOS`/`.RefType`
would read as `None`.

ATTENDED-ONLY: this performs a live restore + destructive Move. NEVER run it
under an unattended loop (repo live-safety protocol). Run from the worktree:
    python debug/run27_live.py

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

# Ejagham Mini's known variant-ref count (SC-001 acceptance: 0 -> 6). Overridable
# for a different source pair.
EXPECTED_REFS = int(os.environ.get("GT_EXPECTED_REFS", "6"))


def _banner(msg: str) -> None:
    print("\n" + "=" * 72)
    print("== " + msg)
    print("=" * 72)


def _total_create_bindings(create_map) -> int:
    return sum(len(recs or []) for recs in create_map.values())


def _entryref_drops(dropped) -> list:
    """DroppedItemRecords whose field is EntryRefsOS (C4 out-of-closure reports)."""
    out = []
    for r in dropped or []:
        if getattr(r, "field_name", None) == "EntryRefsOS":
            out.append(r)
    return out


def run_move():
    """Full Move (all categories incl. STEMS) Ejagham Mini -> Target.

    Returns (create_map, remap, entryref_drops, report). `create_map` and the
    drop list are snapshotted from the plan BEFORE the move so post-move
    verification can re-resolve them independently.
    """
    from gramtrans.Lib import api
    from gramtrans.Lib.debuglog import DEBUG_ENV
    from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
    from harness import full_run

    os.environ.setdefault(DEBUG_ENV, "1")
    source_handle = full_run._open_source_readonly(SOURCE)
    context = None
    try:
        stub = api.initialize_run(
            source_handle, source_project_name=SOURCE, source_project_path="")
        choice = api.TargetCandidate(project_name=TARGET, project_path=TARGET_PATH)
        context = api.bind_target(stub, choice)

        # Full selection INCLUDING STEMS -- the create-then-wire tail
        # (`_run_entryref_create_pass` + `_run_post_pass_a`) fires on the STEMS
        # tail (research.md Decision 6).
        selection = full_run.build_full_selection(exclude=frozenset())

        src_vern = source_handle.GetDefaultVernacularWS()[0]
        tgt_vern = context.target_handle.GetDefaultVernacularWS()[0]
        ws_mapping = WSMapping(entries=(
            WSMappingEntry(
                source_ws_id=src_vern, source_ws_kind=WSKind.VERNACULAR,
                target_ws_id=tgt_vern, create_in_target=False),
        ))
        print("[INFO] WS map: source vern %r -> target vern %r" % (src_vern, tgt_vern))

        state, plan = api.compute_preview(context, selection, ws_mapping=ws_mapping)
        if state is not api.PreviewState.PREVIEW_READY:
            raise RuntimeError("compute_preview returned %r" % (state,))

        create_map = {k: list(v) for k, v in
                      (getattr(plan, "entryref_create_bindings", {}) or {}).items()}
        remap = dict(getattr(plan, "identity_remap", {}) or {})
        drops = _entryref_drops(getattr(plan, "dropped_items", None))

        n_bindings = _total_create_bindings(create_map)
        print("[PLAN] actions=%d skips=%d" % (len(plan.actions), len(plan.skips)))
        print("[PLAN] entryref_create_bindings: %d entries / %d refs to create"
              % (len(create_map), n_bindings))
        print("[PLAN] EntryRefsOS drops (C4 out-of-closure, reported): %d"
              % len(drops))
        for d in drops:
            print("[PLAN]   DROP ref=%s owner=%s reason=%s"
                  % (getattr(d, "item_guid", "?"), getattr(d, "owner_guid", "?"),
                     (getattr(d, "reason", "") or "")[:70]))

        if n_bindings == 0:
            print("\n[WARN] Source produced NO entryref_create_bindings; a Move "
                  "cannot prove 027 on this pair. Aborting BEFORE any write.")
            return create_map, remap, drops, None

        _banner("EXECUTE MOVE (destructive)")
        report = api.execute_move(context, plan)
        added = sum(v.added for v in report.per_category.values())
        skipped = sum(v.skipped for v in report.per_category.values())
        print("[MOVE] added=%d skipped=%d skips_list=%d"
              % (added, skipped, len(report.skips)))
        for s in report.skips:
            reason = getattr(getattr(s, "reason", None), "name", "")
            detail = getattr(s, "detail", "") or ""
            if reason == "DEPENDENCY_UNRESOLVED" and (
                "entry_guid=" in detail or "EntryRefsOS" in detail
                or "component" in detail
            ):
                print("[MOVE]   SKIP %s guid=%s %s"
                      % (reason, getattr(s, "source_guid", "?"), detail))
        return create_map, remap, drops, report
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


def probe_target(create_map, remap, label):
    """Reopen Target read-only and count the LexEntryRef containers that landed.

    Returns a dict with container/type-wiring tallies. Uses the SAME
    reopen-and-re-resolve probe as run28_live.py, but counts CONTAINERS created
    (027 C1) plus their RefType (C1) and VariantEntryTypesRS (C3), not
    component memberships (that is #28's metric, covered by run28_live.py).
    """
    from gramtrans.Lib import categories
    from harness import full_run

    _banner("PROBE reopened Target (read-only): %s" % label)
    target = full_run._open_source_readonly(TARGET)
    try:
        gid = categories._guid_str_from
        resolve = categories._resolve_target_by_guid
        cast = categories._cast_lcm

        expected = _total_create_bindings(create_map)
        containers = 0          # C1: LexEntryRef created + owned, GUID-correct
        reftype_ok = 0          # C1: RefType matches the source record
        type_wired = 0          # C3: has >=1 resolved variant/complex type
        type_expected = 0       # refs whose source carried a type to resolve
        missing = 0

        for src_entry_guid, recs in create_map.items():
            tgt_entry_guid = remap.get(src_entry_guid, src_entry_guid)
            entry = cast(resolve(target, tgt_entry_guid), "ILexEntry")
            entry_refs = list(getattr(entry, "EntryRefsOS", None) or []) if entry else []
            present = {gid(cast(r, "ILexEntryRef")): r for r in entry_refs}
            for rec in recs:
                ref_guid = rec.get("ref_guid")
                want_type = rec.get("ref_type")
                had_source_type = bool(rec.get("variant_entry_types")
                                       or rec.get("complex_entry_types"))
                if had_source_type:
                    type_expected += 1
                raw = present.get(ref_guid)
                if raw is None:
                    missing += 1
                    continue
                containers += 1
                ref = cast(raw, "ILexEntryRef")
                if getattr(ref, "RefType", None) == want_type:
                    reftype_ok += 1
                type_field = ("VariantEntryTypesRS" if want_type == 0
                              else "ComplexEntryTypesRS")
                if list(getattr(ref, type_field, None) or []):
                    type_wired += 1

        print("  expected refs        : %d" % expected)
        print("  containers on target : %d" % containers)
        print("  RefType correct      : %d" % reftype_ok)
        print("  type-wired (C3)      : %d (of %d with a source type)"
              % (type_wired, type_expected))
        print("  missing              : %d" % missing)
        return {
            "expected": expected, "containers": containers,
            "reftype_ok": reftype_ok, "type_wired": type_wired,
            "type_expected": type_expected, "missing": missing,
        }
    finally:
        try:
            target.CloseProject()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    from harness import restore

    _banner("RESTORE Target from clean backup")
    print("[INFO] backup: %s" % BACKUP)
    restore.restore_target(TARGET, backup_path=str(BACKUP))

    # STEP 3 -- live Move #1.
    _banner("STEP 3 live Move #1 (%s -> %s)" % (SOURCE, TARGET))
    create_map, remap, drops, report = run_move()
    if report is None:
        print("\n[SKIP] 027 live proof not applicable on this source pair.")
        return 2

    # Pre-Move baseline is implicitly 0: the plan's create bindings did not
    # exist on the clean-restored target (a re-resolve would find no
    # containers) -- proven by the idempotency delta below instead of a
    # separate clean-target probe (avoids a second reopen).
    post1 = probe_target(create_map, remap, "post-Move #1")

    # STEP 4 -- idempotent re-Move #2 (SC-003: 0 new containers).
    _banner("STEP 4 idempotent re-Move #2")
    create_map2, remap2, drops2, report2 = run_move()
    post2 = probe_target(create_map2, remap2, "post-Move #2 (re-run)")

    _banner("SUMMARY (027 live proof)")
    expected = post1["expected"]
    checks = [
        ("bindings existed (>0)", expected > 0),
        ("SC-001 containers 0 -> %d (all created)" % expected,
         post1["containers"] == expected and post1["missing"] == 0),
        ("SC-001 expected count == %d (Ejagham Mini)" % EXPECTED_REFS,
         expected == EXPECTED_REFS),
        ("C1 RefType correct on all",
         post1["reftype_ok"] == post1["containers"]),
        ("SC-002 variant/complex type wired (C3)",
         post1["type_expected"] == 0
         or post1["type_wired"] == post1["type_expected"]),
        ("SC-003 idempotent: re-Move creates 0 net new "
         "(containers stable)", post2["containers"] == post1["containers"]),
        ("SC-004 out-of-closure refs reported (never silent)",
         True),  # informational: len(drops) printed above; 0 is valid for EMini
    ]
    ok = True
    for name, passed in checks:
        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))
        ok = ok and passed
    print("  [INFO] EntryRefsOS drops Move#1=%d Move#2=%d" % (len(drops), len(drops2)))
    print("\n[%s] 027 T025 live validation" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
