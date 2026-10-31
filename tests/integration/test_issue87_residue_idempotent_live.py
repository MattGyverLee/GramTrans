"""Issue #87 live gate -- a re-run must not re-stamp or touch objects it did
not create or change.

WRITE PATH: writes ONLY the throwaway project ``Target`` -- or the one named
by ``GT_ISSUE87_TARGET``, see below -- (restored headlessly
from a known backup before and after).  The source ``Mbugwe LizzieHC practice``
is opened READ-ONLY (exact spelling).  ``Esperanto`` is never touched.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue87_residue_idempotent_live.py -v -s

Scenario: POS + GRAM_CATEGORIES + 4 picked Texts, transferred twice into the
restored Target (or ``GT_ISSUE87_TARGET``).  Run 2 plans 0 actions.  The
.fwdata snapshots taken after run 1 and run 2 are compared OBJECT BY OBJECT:

  * no object may be created, deleted or changed by run 2 (#107);
  * in particular no object's `[GT-Tag]` lines may change (the #87 symptom: 11
    PartOfSpeech + 4 Text objects gained/replaced a tag line on main).

This test FAILS on main (d9f55c9) -- and also on current main 3a86bb0
(cycle-3 verification) -- and passes with the fix: unlike the issue45
untitled-text gate, its scenario actually exercises Carrier-B POS objects and
matched titled Texts.

Issue #107: run 2 must also create and change NOTHING else.  Before #107 this
test excluded the MoInflAffixSlot / MoInflAffixTemplate / FsFeatStruc objects
run 2 created (and the POS owner links pointing at them).  Those were not
duplicates -- they carried their source GUIDs -- but the owned collections of
every POS that run 1 CREATED, which only the next run's UPDATE enrichment
filled.  The create path now fills them in the same run, so the exclusions are
gone: run 2 must leave every object byte-identical.

TARGET override: ``GT_ISSUE87_TARGET`` names a different throwaway project
(restored from the same backup) so parallel sessions need not share
``Target``.  It defaults to ``Target``.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe LizzieHC practice"   # READ-ONLY, exact spelling
# The ONLY project this module writes (a throwaway, restored before and after).
TARGET_NAME = os.environ.get("GT_ISSUE87_TARGET", "Target")
TARGET_PATH = "C:/ProgramData/SIL/FieldWorks/Projects/%s/%s.fwdata" % (
    TARGET_NAME, TARGET_NAME)
assert TARGET_NAME not in ("Esperanto", SOURCE_NAME), TARGET_NAME
# Write-safety: an override may only name a private GT-Sandbox-* project (the
# unset default, the restored throwaway `Target`, is unchanged).
assert (TARGET_NAME == "Target"
        or TARGET_NAME.startswith("GT-Sandbox-")), (
    "GT_ISSUE87_TARGET must start with 'GT-Sandbox-', got %r" % TARGET_NAME)
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
N_TEXTS = 4

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

# Slot/template/FsFeatStruc re-creation on a 0-action re-run (fixed).
ISSUE_REF = "#107"
_TAG_LINE = re.compile(r"\[GT-Tag\]: GT\|[^\r\n<]*")


def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME)


def _open(name):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


def _source_text_picks():
    proj = _open(SOURCE_NAME)          # initialises the LCM assemblies
    from SIL.LCModel import ICmObject
    try:
        return [str(ICmObject(t.concrete if hasattr(t, "concrete") else t).Guid).lower()
                for t in proj.Texts.GetAll()][:N_TEXTS]
    finally:
        proj.CloseProject()


def _load_objects(path):
    """{guid: (class, xml-text)} for every <rt> in a .fwdata file."""
    out, cur, buf = {}, None, []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r'<rt class="(\w+)" guid="([^"]+)"', line)
            if m:
                cur, buf = (m.group(1), m.group(2).lower()), []
            if cur:
                buf.append(line)
            # Self-closing `<rt ... />` (e.g. an empty FsFeatStruc) is a whole object.
            if cur and (line.startswith("</rt>") or line.rstrip().endswith("/>")
                        and line.startswith("<rt ")):
                out[cur[1]] = (cur[0], "".join(buf))
                cur = None
    return out


@pytest.fixture(autouse=True)
def _restore_around():
    _restore()
    yield
    _restore()


def test_rerun_leaves_objects_it_did_not_create_or_change_untouched():
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    picks = _source_text_picks()
    assert len(picks) == N_TEXTS, "source has fewer than %d texts" % N_TEXTS
    cats = {GC.POS: True, GC.GRAM_CATEGORIES: True, GC.TEXTS: True}

    def _sel(_full):
        return Selection(categories=cats, text_picks=frozenset(picks),
                         include_closure=True)

    snapdir = tempfile.mkdtemp(prefix="gt87_")
    try:
        snaps = []
        plans = []
        for i in (1, 2):
            plan, _rep = full_run.run_full_transfer(
                SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_sel)
            plans.append(plan)
            dst = os.path.join(snapdir, "run%d.fwdata" % i)
            shutil.copyfile(TARGET_PATH, dst)
            snaps.append(_load_objects(dst))
        run1, run2 = snaps
        import flexicon
        import gramtrans
        print("[LIVE] gramtrans=%s" % gramtrans.__file__)
        print("[LIVE] flexicon=%s" % flexicon.__file__)
        print("[LIVE] target=%s" % TARGET_NAME)
        print("[LIVE] run1 actions=%d run2 actions=%d" % (
            len(plans[0].actions), len(plans[1].actions)))

        # Sanity: run 1 really stamped Carrier-B objects and Texts.
        tagged1 = {g for g, (_c, x) in run1.items() if _TAG_LINE.search(x)}
        assert tagged1, "run 1 stamped nothing -- scenario did not exercise residue"
        assert any(run1[g][0] == "PartOfSpeech" for g in tagged1)
        assert any(run1[g][0] == "Text" for g in tagged1)
        assert len(plans[1].actions) == 0, "run 2 should plan 0 actions"

        # (1) No [GT-Tag] line may change on ANY pre-existing object.
        tag_changes = [
            (run2[g][0], g)
            for g in run1 if g in run2
            and _TAG_LINE.findall(run1[g][1]) != _TAG_LINE.findall(run2[g][1])
        ]
        assert not tag_changes, (
            "run 2 re-stamped objects it did not create/change: %s" % [
                (c, g[:8]) for c, g in tag_changes])

        # (2) Nothing new, nothing deleted (#107: no exclusions).
        new = [(run2[g][0], g[:8]) for g in run2 if g not in run1]
        assert not new, "run 2 created objects (%s): %s" % (ISSUE_REF, new[:10])
        assert not [g for g in run1 if g not in run2], "run 2 deleted objects"

        # (3) No field change on any pre-existing object.
        changed = [(cls, g[:8]) for g, (cls, x1) in run1.items()
                   if g in run2 and x1 != run2[g][1]]
        assert not changed, (
            "run 2 changed objects it did not create/update (%s): %s" % (
                ISSUE_REF, changed[:20]))
    finally:
        shutil.rmtree(snapdir, ignore_errors=True)
