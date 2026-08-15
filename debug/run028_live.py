"""T019 live validation driver for feature 028 (attended, destructive).

Restores Target from the clean backup, then drives the REAL engine
(Ejagham028Src -> Target) with the AFFIXES category selected (which walks affix
entries + their allomorph hung-data, where owned.reproduce_moaffix_msenv_data
fires), capturing a read-only diagnosis of the four MsEnv/inflection-class/
position fields before/after and after an idempotent re-run.

PREREQ: run `python debug/build028_fixture.py --write` FIRST so the source
affix allomorph populates all four fields (Ejagham is vacuous otherwise).

!!! UNTESTED IN THE AUTHORING ENVIRONMENT (flexicon not installed there).
    Mirrors debug/run031_live.py, which IS a proven template. Run ATTENDED
    in the FLEx host and iterate; record results in
    specs/028-affix-allomorph-morphosyntax/verification-log.md. ASCII-only.

Run:  set GRAMTRANS_E2E=1 && python debug/run028_live.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SOURCE = os.environ.get("GT_SOURCE", "Ejagham028Src")
TARGET = os.environ.get("GT_TARGET", "Target")
TARGET_PATH = r"C:\ProgramData\SIL\FieldWorks\Projects\Target"
BACKUP = _ROOT / "backups" / "Target 2026-07-06 0218.fwbackup"


def _banner(msg):
    print("\n" + "=" * 72 + "\n== " + msg + "\n" + "=" * 72)


def diagnose(label, name=TARGET):
    """Read-only: count affix allomorphs populating each of the four fields."""
    from harness import full_run
    full_run._ensure_flex_initialized()
    from flexicon import FLExProject
    from SIL.LCModel import ILangProject, ILexEntry, IMoAffixAllomorph, IMoAffixForm

    _banner("DIAGNOSIS: %s (%s)" % (label, name))
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    try:
        counts = {"MsEnvPartOfSpeechRA": 0, "InflectionClassesRC": 0,
                  "MsEnvFeaturesOA": 0, "PositionRS": 0, "affix_allos": 0}
        for _e in proj.LexEntry.GetAll():
            e = ILexEntry(_e)
            forms = list(e.AlternateFormsOS)
            if e.LexemeFormOA is not None:
                forms.append(e.LexemeFormOA)
            for allo in forms:
                if allo is None or allo.ClassName != "MoAffixAllomorph":
                    continue
                counts["affix_allos"] += 1
                a = IMoAffixAllomorph(allo)
                f = IMoAffixForm(allo)
                if a.MsEnvPartOfSpeechRA is not None:
                    counts["MsEnvPartOfSpeechRA"] += 1
                if a.MsEnvFeaturesOA is not None:
                    counts["MsEnvFeaturesOA"] += 1
                if list(f.InflectionClassesRC):
                    counts["InflectionClassesRC"] += 1
                if list(a.PositionRS):
                    counts["PositionRS"] += 1
        print("[DIAG] %s" % counts)
        return counts
    finally:
        try:
            proj.CloseProject()
        except Exception:
            pass


def run_transfer():
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

        # AFFIXES walks affix entries + their allomorph hung-data (028 dispatch).
        # Supporting categories give the POS/class/feature resolve-or-create
        # infra the four legs reuse (R1/R3/R5). Adjust if the plan is empty.
        selection = Selection(categories={
            GrammarCategory.GRAM_CATEGORIES: True,
            GrammarCategory.INFLECTION_FEATURES: True,
            GrammarCategory.INFLECTION_CLASSES: True,
            GrammarCategory.PH_ENVIRONMENT: True,
            GrammarCategory.AFFIXES: True,
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
        print("[PLAN] actions=%d skips=%d" % (len(plan.actions), len(plan.skips)))
        # Surface any DroppedItemRecords for the four fields (never-silent).
        drops = getattr(plan, "dropped_items", None) or []
        msenv_drops = [d for d in drops if getattr(d, "field_name", "") in (
            "MsEnvPartOfSpeechRA", "InflectionClassesRC", "MsEnvFeaturesOA",
            "PositionRS")]
        print("[PLAN] MsEnv drop records: %d" % len(msenv_drops))
        for d in msenv_drops:
            print("[PLAN]   DROP field=%s item=%s reason=%s" % (
                d.field_name, getattr(d, "item_guid", "?"), getattr(d, "reason", "")))

        report = api.execute_move(context, plan)
        added = sum(v.added for v in report.per_category.values())
        skipped = sum(v.skipped for v in report.per_category.values())
        print("[MOVE] added=%d skipped=%d" % (added, skipped))
        return plan, report
    finally:
        if context is not None:
            try:
                api._close_project_watchdog(
                    context.target_handle, api._SCHEMA_CLOSE_TIMEOUT_S, "target")
            except Exception as exc:
                print("[WARN] target close: %s" % exc)
        try:
            source_handle.CloseProject()
        except Exception:
            pass


def main():
    if os.environ.get("GRAMTRANS_E2E") != "1":
        print("[SKIP] set GRAMTRANS_E2E=1 to opt into the destructive live run.")
        return 3
    from harness import restore

    src = diagnose("SOURCE baseline (fixture must be non-zero)", SOURCE)
    if src["MsEnvPartOfSpeechRA"] == 0 and src["PositionRS"] == 0:
        print("[ERROR] SOURCE fixture is vacuous -- run build028_fixture.py "
              "--write first.")
        return 2

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
    for lbl, r in (("SOURCE", src), ("pre", pre), ("post#1", post1), ("post#2", post2)):
        print("  %-8s %s" % (lbl, r))

    ok = True
    checks = [
        ("SC-001 POS reproduced (>0)", post1["MsEnvPartOfSpeechRA"] > pre["MsEnvPartOfSpeechRA"]),
        ("SC-001 PositionRS reproduced (>0)", post1["PositionRS"] > pre["PositionRS"]),
        ("SC-005 idempotent POS", post2["MsEnvPartOfSpeechRA"] == post1["MsEnvPartOfSpeechRA"]),
        ("SC-005 idempotent PositionRS", post2["PositionRS"] == post1["PositionRS"]),
    ]
    for name, passed in checks:
        print("  [%s] %s" % ("PASS" if passed else "FAIL", name))
        ok = ok and passed
    print("\n[%s] T019 live validation (partial -- see verification-log.md; "
          "forced-drop step is manual)" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
