"""Issue #87 live gate -- a re-run must not re-stamp or touch objects it did
not create or change.

WRITE PATH: writes ONLY the throwaway project ``Target`` (restored headlessly
from a known backup before and after).  The source ``Mbugwe LizzieHC practice``
is opened READ-ONLY (exact spelling).  ``Esperanto`` is never touched.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue87_residue_idempotent_live.py -v -s

Scenario: POS + GRAM_CATEGORIES + 4 picked Texts, transferred twice into the
restored Target.  Run 2 plans 0 actions.  The Target.fwdata snapshots taken
after run 1 and run 2 are compared OBJECT BY OBJECT:

  * no object that existed after run 1 may change, except the explicitly
    excluded separate defect below;
  * in particular no object's `[GT-Tag]` lines may change (the #87 symptom: 11
    PartOfSpeech + 4 Text objects gained/replaced a tag line on main).

This test FAILS on main (d9f55c9) -- and also on current main 3a86bb0
(cycle-3 verification) -- and passes with the fix: unlike the issue45
untitled-text gate, its scenario actually exercises Carrier-B POS objects and
matched titled Texts.

EXCLUDED (separate defect, not #87 -- see ISSUE_REF below: run 2 with 0 planned
actions still creates MoInflAffixSlot/MoInflAffixTemplate objects):
  * NEW objects of class MoInflAffixSlot / MoInflAffixTemplate / FsFeatStruc
    (run 2 adds ~47 FsFeatStruc under POS `ReferenceForms`);
  * on PartOfSpeech, ONLY the `<objsur guid="X"/>` entries inside
    `<AffixSlots>` / `<AffixTemplates>` / `<ReferenceForms>` where X is such a
    NEW object (a wrapper left empty is dropped).  Any other change inside those
    blocks fails the test.
Nothing else is excluded (MoInflAffMsa and pre-existing FsFeatStruc changes
are compared like any other object).
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
TARGET_NAME = "Target"                     # the ONLY project this module writes
TARGET_PATH = "C:/ProgramData/SIL/FieldWorks/Projects/Target/Target.fwdata"
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
N_TEXTS = 4

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

# Not filed yet; the number is added later as a docstring-only edit.
ISSUE_REF = ("cycle-3 draft issue (specs/_reviews/batch-1-87/"
             "cycle3-draft-issue-slot-template-idempotency.md)")
# Separate template/slot idempotency defect (see module docstring).
EXCLUDED_NEW_CLASSES = frozenset(
    {"MoInflAffixSlot", "MoInflAffixTemplate", "FsFeatStruc"})
_OWNER_LINK_BLOCKS = re.compile(
    r"[ \t]*<(AffixSlots|AffixTemplates|ReferenceForms)>(.*?)</\1>[ \t]*\n?",
    re.DOTALL)
_OBJSUR = re.compile(r'[ \t]*<objsur\b[^>]*\bguid="([^"]+)"[^>]*/>[ \t]*\n?')
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


def _normalise(cls, xml, drop_guids=frozenset()):
    """For PartOfSpeech only: drop `<objsur>` entries pointing at `drop_guids`
    (NEW excluded-class objects) from the three owner-link wrappers, then drop
    any wrapper left empty.  Everything else is compared verbatim."""
    if cls != "PartOfSpeech" or not drop_guids:
        return xml

    return _OWNER_LINK_BLOCKS.sub(
        lambda m: _rebuild(m, drop_guids), xml)


def _rebuild(m, drop_guids):
    inner = _OBJSUR.sub(
        lambda o: "" if o.group(1).lower() in drop_guids else o.group(0),
        m.group(2))
    if not inner.strip():
        return ""
    return m.group(0).replace(m.group(2), inner, 1)


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
        import gramtrans
        print("[LIVE] gramtrans=%s" % gramtrans.__file__)
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

        # (2) Nothing new except the excluded separate defect.
        new_other = [(run2[g][0], g) for g in run2 if g not in run1
                     and run2[g][0] not in EXCLUDED_NEW_CLASSES]
        assert not new_other, "run 2 created unexpected objects: %s" % new_other[:10]
        assert not [g for g in run1 if g not in run2], "run 2 deleted objects"

        # (3) No field change on any pre-existing object (only owner links that
        #     point at NEW excluded-class objects are tolerated, on POS).
        new_excluded = frozenset(
            g for g in run2 if g not in run1 and run2[g][0] in EXCLUDED_NEW_CLASSES)
        changed = []
        for g, (cls, x1) in run1.items():
            if g not in run2:
                continue
            if (_normalise(cls, x1, new_excluded)
                    != _normalise(cls, run2[g][1], new_excluded)):
                changed.append((cls, g))
        assert not changed, (
            "run 2 changed objects it did not create/update: %s" % [
                (c, g[:8]) for c, g in changed[:20]])
    finally:
        shutil.rmtree(snapdir, ignore_errors=True)
