"""Live validation driver for the inflection_classes owner-collection fix
(coverage-content-fidelity Part A).

ATTENDED / DESTRUCTIVE. Proves that transferred inflection classes (IMoInflClass)
land under their OWNER POS's IPartOfSpeech.InflectionClassesOC on a live target --
NOT in the wrong MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS collection
(the pre-fix bug).

Metric = project-wide, GUID-based (resolution-independent):
  - CORRECT owner: walk every POS -> pos.InflectionClassesOC, collect IMoInflClass GUIDs.
  - WRONG owner:   morph_data.ProdRestrictOA.PossibilitiesOS, count any MoInflClass items.
Acceptance: the source's N inflection-class GUIDs appear 0->N under owner POSes on
target, 0 land in ProdRestrictOA.PossibilitiesOS, idempotent re-Move stable.

Source French-FLExTrans-Demo2025 (domain-confirmed): POS Verb owns 4 (ER/RE/IRREG/IR),
POS Noun owns 1 (X_PL); total 5.

ATTENDED-ONLY: live restore + destructive Move. NEVER run under an unattended loop.
Run from the worktree:  python debug/run_inflclass_live.py
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

SOURCE = os.environ.get("GT_SOURCE", "French-FLExTrans-Demo2025")
TARGET = os.environ.get("GT_TARGET", "Target")
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Target"
BACKUP = _ROOT / "backups" / "Target 2026-07-06 0218.fwbackup"


def _banner(msg: str) -> None:
    print("\n" + "=" * 72)
    print("== " + msg)
    print("=" * 72)


def count_inflection_classes(project_name):
    """Reopen read-only; return (correct_owner_guids, wrong_owner_count).

    correct_owner_guids: set of IMoInflClass GUIDs reachable via any POS's
        InflectionClassesOC (the CORRECT per-POS owner).
    wrong_owner_count:    number of MoInflClass items sitting in
        MorphologicalDataOA.ProdRestrictOA.PossibilitiesOS (the pre-fix bug site).
    """
    from gramtrans.Lib import categories
    from gramtrans.Lib.preview import _classname_of
    from harness import full_run

    handle = full_run._open_source_readonly(project_name)
    try:
        gid = categories._guid_str_from
        correct = set()
        for pos in categories._iter_pos(handle):
            pos_obj = categories._as_pos(pos)
            for ic in categories._inflection_classes_from_pos(pos_obj):
                correct.add(gid(ic))
        correct.discard(None)
        correct.discard("")

        wrong = 0
        try:
            cache = getattr(handle, "Cache")
            morph_data = cache.LangProject.MorphologicalDataOA
            prod = getattr(morph_data, "ProdRestrictOA", None)
            poss = list(getattr(prod, "PossibilitiesOS", None) or []) if prod else []
            for item in poss:
                if _classname_of(item) == "MoInflClass":
                    wrong += 1
        except Exception as exc:  # noqa: BLE001
            print("  [WARN] ProdRestrictOA probe failed: %s" % exc)
        return correct, wrong
    finally:
        try:
            handle.CloseProject()
        except Exception:  # noqa: BLE001
            pass


def run_move(label):
    """Full Move SOURCE -> TARGET (brings owner POSes + their inflection classes)."""
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
        n_ic_actions = sum(
            1 for a in plan.actions
            if getattr(getattr(a, "category", None), "name", "") == "INFLECTION_CLASSES")
        print("[PLAN] actions=%d skips=%d | INFLECTION_CLASSES actions=%d"
              % (len(plan.actions), len(plan.skips), n_ic_actions))

        _banner("EXECUTE MOVE (destructive)")
        report = api.execute_move(context, plan)
        added = sum(v.added for v in report.per_category.values())
        skipped = sum(v.skipped for v in report.per_category.values())
        ic_skips = [s for s in report.skips
                    if getattr(getattr(s, "category", None), "name", "") == "INFLECTION_CLASSES"]
        print("[MOVE] added=%d skipped=%d | INFLECTION_CLASSES skips=%d"
              % (added, skipped, len(ic_skips)))
        for s in ic_skips[:5]:
            print("[MOVE]   IC SKIP %s: %s"
                  % (getattr(getattr(s, "reason", None), "name", "?"),
                     (getattr(s, "detail", "") or "")[:70]))
        return n_ic_actions
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

    _banner("SOURCE inflection-class inventory (%s)" % SOURCE)
    src_correct, src_wrong = count_inflection_classes(SOURCE)
    print("  under owner POS InflectionClassesOC : %d" % len(src_correct))
    print("  mis-placed in ProdRestrictOA        : %d" % src_wrong)
    print("  source IC guids: %s" % ", ".join(g[:8] for g in sorted(src_correct)))

    _banner("RESTORE Target from clean backup")
    print("[INFO] backup: %s" % BACKUP)
    restore.restore_target(TARGET, backup_path=str(BACKUP))

    base_correct, base_wrong = count_inflection_classes(TARGET)
    base_from_src = len(src_correct & base_correct)
    print("[BASELINE] target IC under owner POS=%d (of source: %d) | ProdRestrictOA=%d"
          % (len(base_correct), base_from_src, base_wrong))

    n_ic1 = run_move("live Move #1 (%s -> %s)" % (SOURCE, TARGET))
    p1_correct, p1_wrong = count_inflection_classes(TARGET)
    p1_from_src = len(src_correct & p1_correct)
    print("[POST#1] target IC under owner POS=%d (of source: %d) | ProdRestrictOA=%d"
          % (len(p1_correct), p1_from_src, p1_wrong))

    n_ic2 = run_move("idempotent re-Move #2")
    p2_correct, p2_wrong = count_inflection_classes(TARGET)
    p2_from_src = len(src_correct & p2_correct)
    print("[POST#2] target IC under owner POS=%d (of source: %d) | ProdRestrictOA=%d"
          % (len(p2_correct), p2_from_src, p2_wrong))

    _banner("SUMMARY (inflection_classes owner-fix live proof)")
    n_src = len(src_correct)
    checks = [
        ("source has inflection classes (>0)", n_src > 0),
        ("baseline: 0 of the source classes on target", base_from_src == 0),
        ("all source classes landed under OWNER POS InflectionClassesOC (0 -> %d)" % n_src,
         p1_from_src == n_src),
        ("NONE mis-placed in ProdRestrictOA.PossibilitiesOS (the bug site)",
         p1_wrong == 0),
        ("idempotent: re-Move stable (owner-owned %d, ProdRestrict %d)"
         % (p2_from_src, p2_wrong),
         p2_from_src == p1_from_src and p2_wrong == p1_wrong),
    ]
    ok = True
    for name, passed in checks:
        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))
        ok = ok and passed
    print("  [INFO] INFLECTION_CLASSES plan actions Move#1=%d Move#2=%d" % (n_ic1, n_ic2))
    print("\n[%s] inflection_classes owner-fix live validation"
          % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
