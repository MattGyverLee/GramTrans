"""T024 live validation driver for feature 031 (attended, destructive).

Restores Target from the clean backup, then drives the REAL engine
(Ejagham Mini -> Target) with GRAM_CATEGORIES + INFLECTION_FEATURES selected,
capturing the read-only diagnosis before/after and after an idempotent re-run.

ASCII-only output (Windows-terminal safe). Run from the worktree:
    python scratchpad/run031_live.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT / "src", _ROOT / "tests" / "integration", _ROOT / "debug"):
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


def diagnose(label: str, name: str = TARGET) -> dict:
    import diag_infl_features as diag
    _banner("DIAGNOSIS: %s (%s)" % (label, name))
    return diag.main(name)


def run_transfer():
    """Targeted GRAM_CATEGORIES + INFLECTION_FEATURES transfer (mirrors
    harness.full_run.run_full_transfer but with a focused Selection)."""
    from gramtrans.Lib import api
    from gramtrans.Lib.debuglog import DEBUG_ENV
    from gramtrans.Lib.models import (
        GrammarCategory, Selection, WSKind, WSMapping, WSMappingEntry,
    )
    from harness import full_run

    os.environ.setdefault(DEBUG_ENV, "1")
    source_handle = full_run._open_source_readonly(SOURCE)
    context = None
    try:
        stub = api.initialize_run(
            source_handle, source_project_name=SOURCE, source_project_path="")
        choice = api.TargetCandidate(project_name=TARGET, project_path=TARGET_PATH)
        context = api.bind_target(stub, choice)

        selection = Selection(categories={
            GrammarCategory.GRAM_CATEGORIES: True,
            GrammarCategory.INFLECTION_FEATURES: True,
        })
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
        links = getattr(plan, "feature_category_links", {}) or {}
        n_links = sum(len(v) for v in links.values())
        print("[PLAN] actions=%d skips=%d feature_category_links: %d POS / %d pairs"
              % (len(plan.actions), len(plan.skips), len(links), n_links))
        report = api.execute_move(context, plan)
        added = sum(v.added for v in report.per_category.values())
        skipped = sum(v.skipped for v in report.per_category.values())
        print("[MOVE] added=%d skipped=%d skips_list=%d"
              % (added, skipped, len(report.skips)))
        for s in report.skips:
            print("[MOVE]   SKIP %s guid=%s %s"
                  % (getattr(s.reason, "name", s.reason),
                     getattr(s, "source_guid", "?"), getattr(s, "detail", "")))
        return plan, report
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

    # Source baseline: the link/name structure the target should mirror. A
    # feature that is orphaned/complex in the SOURCE is expected to stay that
    # way in the target (we never invent links, and complex features are not
    # transferred by this path -- 031 US2 guard).
    src = diagnose("SOURCE baseline", SOURCE)

    _banner("RESTORE Target from clean backup")
    print("[INFO] backup: %s" % BACKUP)
    restore.restore_target(TARGET, backup_path=str(BACKUP))

    pre = diagnose("STEP 0 pre-Move (clean baseline)")

    _banner("STEP 3 live Move #1 (%s -> %s)" % (SOURCE, TARGET))
    run_transfer()
    post1 = diagnose("STEP 3 post-Move #1")

    _banner("STEP 4 idempotent re-Move #2")
    run_transfer()
    post2 = diagnose("STEP 4 post-Move #2 (re-run)")

    _banner("SUMMARY")
    def row(lbl, r):
        print("  %-22s feat=%d val=%d nameless_f=%d nameless_v=%d linked=%d orphaned=%d dup=%d"
              % (lbl, r["total_features"], r["total_values"], r["nameless_features"],
                 r["nameless_values"], r["linked_features"], r["orphaned_features"],
                 len(r["duplicate_guid_groups"])))
    row("SOURCE baseline", src)
    row("pre (target clean)", pre)
    row("post Move #1", post1)
    row("post Move #2", post2)

    ok = True
    checks = []
    # SC-002 named: no nameless transferred features/values after Move #1.
    checks.append(("SC-002 no nameless features", post1["nameless_features"] == 0))
    checks.append(("SC-002 no nameless values", post1["nameless_values"] == 0))
    # SC-001 linked: the target mirrors the SOURCE link structure (we neither
    # invent nor drop links). linked_features must equal the source's, and must
    # be > 0 (the whole point of US1 -- pre-fix this was 0).
    checks.append(("US1 links wired (>0)", post1["linked_features"] > 0))
    checks.append(("SC-001 linked matches source",
                   post1["linked_features"] == src["linked_features"]))
    checks.append(("features actually transferred", post1["total_features"] > 0))
    # SC-003 idempotent: Move #2 adds nothing.
    checks.append(("SC-003 idempotent feat count", post2["total_features"] == post1["total_features"]))
    checks.append(("SC-003 idempotent val count", post2["total_values"] == post1["total_values"]))
    checks.append(("SC-003 idempotent linked", post2["linked_features"] == post1["linked_features"]))
    checks.append(("no duplicate GUIDs", not post2["duplicate_guid_groups"]))
    for name, passed in checks:
        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))
        ok = ok and passed
    print("\n[%s] T024 live validation" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
