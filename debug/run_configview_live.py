"""Live validation driver for the Dictionary/Reversal CONFIGURATION-VIEW copy
(feature 025-full-reversals, US3, Lib/config_views.py). ATTENDED / DESTRUCTIVE.

Closes the S4 live-proof gap recorded in
specs/025-full-reversals/HANDOFF.md: the SKIP path was live-proven, but
ADD / OVERWRITE / missing-reference were offline-only because the Ejagham
project pair carries exactly one byte-identical `.fwdictconfig`
(ReversalIndex/en.fwdictconfig) and NO Dictionary config at all. This driver
constructs a fixture that forces all three untested paths on real flexicon
handles, so the live target-introspection surfaces are genuinely exercised:
  * ADD           : a Dictionary/*.fwdictconfig the target lacks.
  * OVERWRITE     : a ReversalIndex/en.fwdictconfig that DIFFERS from target's
                    (asserts the source bytes win AND a *.gtbak backup of the
                    old target file is written first).
  * missing_refs  : the ADD file references a writing system, a paragraph
                    style, and a custom field that are all ABSENT in the
                    target -> three never-silent DroppedItemRecords, checked
                    against the LIVE target WS / Styles / CustomFields sets
                    (the exact code path offline fakes cannot cover).
  * idempotency   : a re-plan after the copy sees both files byte-identical
                    -> SKIP, while missing_refs are STILL reported on SKIP.

Scope / blast radius: config_views is a pure filesystem + read-only LCM
introspection path. It NEVER writes the target `.fwdata`; it only touches the
target's `ConfigurationSettings/` folder, which the final restore wipes clean.
Both project handles are opened READ-ONLY. This calls
config_views.plan_config_views / apply_config_views DIRECTLY (the
Preview->Move wiring at preview.py:392 / transfer.py:519 is already
engine-proven by the S4 SKIP result).

PREREQ: none -- the driver stages its own fixture into a disposable source
(EjaghamCfgSrc, restored from the Ejagham Mini backup) and a clean Target.
Neither the real Ejagham Mini nor Ejagham Full GT-Test is touched.

Run (in the FLEx host interpreter, ATTENDED):
    set GRAMTRANS_E2E=1 && python debug/run_configview_live.py

ASCII-only output (Windows-terminal safe). NEVER under an unattended loop.
"""
from __future__ import annotations

import os
import sys
import filecmp
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "src", _ROOT / "tests" / "integration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

PROJECTS_ROOT = Path(os.environ.get(
    "GRAMTRANS_PROJECTS_ROOT", r"C:\ProgramData\SIL\FieldWorks\Projects"))
SOURCE = os.environ.get("GT_SOURCE", "EjaghamCfgSrc")
TARGET = os.environ.get("GT_TARGET", "Target")
SRC_BACKUP = _ROOT / "backups" / "Ejagham Mini.fwbackup"
TGT_BACKUP = _ROOT / "backups" / "Target 2026-07-06 0218.fwbackup"

# Obviously-absent reference tokens (kept distinctive so a false match is
# impossible even if the target grows real fields later).
MISSING_WS = "zz-XX"
MISSING_STYLE = "GT-NoSuchStyle-QZ"
MISSING_FIELD = "GTNoSuchField-QZ"

ADD_FILENAME = "GT-Export-Test.fwdictconfig"
REV_FILENAME = "en.fwdictconfig"

# --- fixture file bodies ---------------------------------------------------
# ADD file: references three things the target does not have. The `vernacular`
# Option id is a MAGIC default-WS token and MUST NOT be reported as missing.
ADD_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<DictionaryConfiguration name="GT Export Test" writingSystem="%s" '
    'version="26" isRootBased="false">\n'
    '  <ConfigurationItem name="Headword" isEnabled="true" style="%s" '
    'field="HeadWord">\n'
    '    <WritingSystemOptions writingSystemType="vernacular">\n'
    '      <Option id="vernacular" isEnabled="true" />\n'
    '    </WritingSystemOptions>\n'
    '  </ConfigurationItem>\n'
    '  <ConfigurationItem name="Custom Thing" isEnabled="true" '
    'isCustomField="true" field="%s" />\n'
    '</DictionaryConfiguration>\n'
) % (MISSING_WS, MISSING_STYLE, MISSING_FIELD)

# The OVERWRITE pair: a pristine target baseline and a source variant that
# differs by exactly one attribute (version). All refs here are real/magic so
# they never add noise to the missing_refs assertion.
_REV_TEMPLATE = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<DictionaryConfiguration name="English" writingSystem="en" '
    'version="%s" isRootBased="false">\n'
    '  <ConfigurationItem name="Reversal Entry" isEnabled="true" '
    'field="ReversalIndexEntry">\n'
    '    <WritingSystemOptions writingSystemType="reversal">\n'
    '      <Option id="reversal" isEnabled="true" />\n'
    '    </WritingSystemOptions>\n'
    '  </ConfigurationItem>\n'
    '</DictionaryConfiguration>\n'
)
PRISTINE_REV = _REV_TEMPLATE % "26"   # what the target starts with
MODIFIED_REV = _REV_TEMPLATE % "27"   # source variant -> forces OVERWRITE


def _say(msg):
    print(msg)


def _banner(msg):
    _say("\n" + "=" * 72)
    _say("== " + msg)
    _say("=" * 72)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)


def _cfg_dirs(project_name: str):
    base = PROJECTS_ROOT / project_name / "ConfigurationSettings"
    return base / "Dictionary", base / "ReversalIndex"


def stage_fixture() -> None:
    """Deterministically stage the source fixture + target baseline on disk.
    Called AFTER both projects are restored and BEFORE either is opened."""
    _banner("STAGE FIXTURE (disk only -- no project open yet)")

    src_dict, src_rev = _cfg_dirs(SOURCE)
    tgt_dict, tgt_rev = _cfg_dirs(TARGET)

    # SOURCE: an ADD (Dictionary) file + a DIFFERING reversal file.
    _write(src_dict / ADD_FILENAME, ADD_BODY)
    _write(src_rev / REV_FILENAME, MODIFIED_REV)
    _say("[STAGE] source ADD file      : %s" % (src_dict / ADD_FILENAME))
    _say("[STAGE] source OVERWRITE file: %s (version=27)" % (src_rev / REV_FILENAME))

    # TARGET: pristine reversal baseline (forces OVERWRITE, controls .gtbak
    # bytes); ensure NO stray Dictionary copy of the ADD file exists.
    _write(tgt_rev / REV_FILENAME, PRISTINE_REV)
    stray = tgt_dict / ADD_FILENAME
    if stray.exists():
        stray.unlink()
    gtbak = tgt_rev / (REV_FILENAME + ".gtbak")
    if gtbak.exists():
        gtbak.unlink()
    _say("[STAGE] target baseline rev  : %s (version=26)" % (tgt_rev / REV_FILENAME))


def _open_ro(name: str):
    from harness import full_run
    return full_run._open_source_readonly(name)


def _close(handle) -> None:
    try:
        handle.CloseProject()
    except Exception:  # noqa: BLE001
        pass


def _rec_by_name(records, filename):
    for r in records:
        if r.filename == filename:
            return r
    return None


def Main() -> int:
    from harness import restore
    from gramtrans.Lib import config_views
    from gramtrans.Lib.models import ConfigViewAction

    checks = []

    def check(name, passed):
        checks.append((name, bool(passed)))
        _say("  [%s] %s" % ("PASS" if passed else "FAIL", name))

    # ---- restore clean projects ------------------------------------------
    _banner("RESTORE disposable source + clean target")
    restore.restore_target(SOURCE, backup_path=str(SRC_BACKUP))
    restore.restore_target(TARGET, backup_path=str(TGT_BACKUP))

    # ---- stage fixture ----------------------------------------------------
    stage_fixture()
    tgt_dict, tgt_rev = _cfg_dirs(TARGET)
    src_dict, src_rev = _cfg_dirs(SOURCE)
    tgt_add = tgt_dict / ADD_FILENAME
    tgt_rev_file = tgt_rev / REV_FILENAME
    tgt_gtbak = tgt_rev / (REV_FILENAME + ".gtbak")

    source = target = None
    try:
        source = _open_ro(SOURCE)
        target = _open_ro(TARGET)

        # ---- PLAN #1 ------------------------------------------------------
        _banner("PLAN #1 (plan_config_views)")
        records = config_views.plan_config_views(source, target)
        for r in records:
            _say("  [%s] %-28s missing_refs=%d"
                 % (r.action.name, r.filename, len(r.missing_refs)))

        add_rec = _rec_by_name(records, ADD_FILENAME)
        rev_rec = _rec_by_name(records, REV_FILENAME)
        check("ADD file planned as ADD",
              add_rec is not None and add_rec.action is ConfigViewAction.ADD)
        check("reversal file planned as OVERWRITE",
              rev_rec is not None and rev_rec.action is ConfigViewAction.OVERWRITE)

        # missing_refs on the ADD file: WS + style + custom field, live-checked.
        mr_items = {m.item_name for m in (add_rec.missing_refs if add_rec else [])}
        _say("  ADD missing_refs items: %s" % sorted(mr_items))
        check("missing WS '%s' reported" % MISSING_WS, MISSING_WS in mr_items)
        check("missing style '%s' reported" % MISSING_STYLE, MISSING_STYLE in mr_items)
        check("missing custom field '%s' reported" % MISSING_FIELD,
              MISSING_FIELD in mr_items)
        check("magic 'vernacular' token NOT reported", "vernacular" not in mr_items)

        # ---- APPLY --------------------------------------------------------
        _banner("APPLY (apply_config_views) -- DESTRUCTIVE (target config dir)")
        check("target lacks ADD file before apply", not tgt_add.exists())
        pre_gtbak = tgt_gtbak.exists()
        dropped = []
        config_views.apply_config_views(records, dropped)

        check("ADD file now present on target", tgt_add.exists())
        check("ADD file bytes == source",
              tgt_add.exists()
              and filecmp.cmp(str(tgt_add), str(src_dict / ADD_FILENAME), shallow=False))
        check("reversal file now == source (overwritten)",
              filecmp.cmp(str(tgt_rev_file), str(src_rev / REV_FILENAME), shallow=False))
        check("no .gtbak existed before apply", not pre_gtbak)
        check("OVERWRITE wrote a .gtbak backup", tgt_gtbak.exists())
        check("the .gtbak holds the PRISTINE (pre-overwrite) bytes",
              tgt_gtbak.exists()
              and tgt_gtbak.read_text(encoding="utf-8") == PRISTINE_REV)
        dropped_items = {d.item_name for d in dropped}
        check("never-silent: all 3 missing refs in run dropped collector",
              {MISSING_WS, MISSING_STYLE, MISSING_FIELD} <= dropped_items)

        # ---- PLAN #2 (idempotency) ---------------------------------------
        _banner("PLAN #2 (idempotency -- files now byte-identical)")
        records2 = config_views.plan_config_views(source, target)
        for r in records2:
            _say("  [%s] %-28s missing_refs=%d"
                 % (r.action.name, r.filename, len(r.missing_refs)))
        add_rec2 = _rec_by_name(records2, ADD_FILENAME)
        rev_rec2 = _rec_by_name(records2, REV_FILENAME)
        check("ADD file now SKIP",
              add_rec2 is not None and add_rec2.action is ConfigViewAction.SKIP)
        check("reversal file now SKIP",
              rev_rec2 is not None and rev_rec2.action is ConfigViewAction.SKIP)
        check("never-silent still holds on SKIP (ADD file keeps missing_refs)",
              add_rec2 is not None and len(add_rec2.missing_refs) >= 3)

        # A second apply must be a no-op copy-wise (still re-reports refs).
        dropped2 = []
        config_views.apply_config_views(records2, dropped2)
        check("re-apply created no second .gtbak (SKIP does no I/O)",
              not (tgt_rev / (REV_FILENAME + ".gtbak.gtbak")).exists())

    finally:
        _close(source)
        _close(target)
        _banner("RESTORE Target clean (leave no residue)")
        try:
            restore.restore_target(TARGET, backup_path=str(TGT_BACKUP))
            _say("[INFO] Target restored clean.")
        except Exception as exc:  # noqa: BLE001
            _say("[WARN] final target restore failed: %s" % exc)

    _banner("ACCEPTANCE")
    ok = all(p for _, p in checks)
    for name, passed in checks:
        _say("  [%s] %s" % ("PASS" if passed else "FAIL", name))
    _say("\n[%s] config-view live validation (ADD / OVERWRITE / missing_refs / idempotent)"
         % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    if os.environ.get("GRAMTRANS_E2E") != "1":
        _say("[ABORT] set GRAMTRANS_E2E=1 to run this attended, destructive proof.")
        raise SystemExit(2)
    raise SystemExit(Main())
