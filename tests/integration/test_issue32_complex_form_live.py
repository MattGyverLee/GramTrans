"""Issue #32 live gate -- complex-form (`RefType=1`) LexEntryRef `0 -> N`.

WRITE PATH: writes ONLY the private throwaway ``GT-Sandbox-32``, restored
headlessly from ``Target 2026-07-06 0218.fwbackup`` before AND after each
test.  The source ``Korean-GIAL`` is opened READ-ONLY.  ``Esperanto`` is never
touched.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue32_complex_form_live.py -v -s

SKIPS when FLEXLIBS_REQUIRE_LIVE != 1 or flexicon is absent; under
FLEXLIBS_REQUIRE_LIVE=1 a missing source/backup FAILS (never a quiet skip).

Why Korean-GIAL: none of the 027 candidates (Ejagham Mini: 0 complex forms;
French-/German-/Swedish-FLExTrans samples, Spanish-FLExTrans-Demo2025: 0;
Lex Training Sample Project 1: 4, all single-component; TestLangProj: not
installed) has a MULTI-component complex form.  Korean-GIAL (383 entries)
has 34, with a primary subset, `ComplexEntryTypesRS`, and -- the shape that
exposed two defects -- a LexSense component.

The run is scoped by STEMS/AFFIXES leaf picks to four complex-form entries
plus every component's owning entry:

  poita        3 components, primary is the MIDDLE (affix) component
  twetsikoki   2-component Compound, ShowComplexFormsIn = both
  khalkojsimnita  4 components (1 stem + 3 affixes)
  mokotsimnita    4 components, the FIRST is a LexSense ('eat')

Asserted independently of the engine, on the target re-read two ways (the
.fwdata XML, and a fresh read-only LCM open with explicit casts): each
container exists with its SOURCE GUID on the right owner, RefType=1, and
ComponentLexemesRS / PrimaryLexemesRS / ShowComplexFormsInRS /
ComplexEntryTypesRS equal the source's GUID lists in order.  Preview and
Move report the same LexEntryRef-related drops, and none for these refs.  A
re-Move plans 0 actions and leaves every ref byte-identical.

Pre-fix (main 21e153e) this gate failed three ways, all live-observed:
ShowComplexFormsInRS lost every non-primary member (3 of 4 refs), the
LexSense-component ref was reported dropped although fully reproduced, and
Preview surfaced no C3 entry-type decision (its drop set was smaller than
Move's).

The second test narrows the run (one affix component un-picked) and asserts
the run-scoped C4 check now reports exactly that ref, in Preview and Move.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)
if importlib.util.find_spec("flexicon") is None:
    pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is not importable",
                pytrace=False)

SOURCE_NAME = "Korean-GIAL"       # READ-ONLY
TARGET_NAME = "GT-Sandbox-32"     # the ONLY project this module writes
TARGET_PATH = ("C:/ProgramData/SIL/FieldWorks/Projects/GT-Sandbox-32/"
               "GT-Sandbox-32.fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

# Complex-form entry GUID -> its RefType=1 LexEntryRef GUID (Korean-GIAL).
COMPLEX = {
    "38a8b1b3-25de-4eb1-a1d3-3e5c7753abdf": "38751f5b-16c3-41b0-884b-589e6a36888b",
    "4a956f4a-3123-41c9-a8d5-72eef48cdfcc": "ff749d17-34bc-470e-a9ed-714269923a0f",
    "5b4307bb-9f08-4e8f-bdc7-1cc54e0df333": "1c7a4f20-5453-4d9e-bdc2-7b7865ac1248",
    "b135b153-6cf1-4731-8351-e02960bbac9a": "5faa892d-f9f9-4b25-a8d4-18a5ce664cf6",
}
# Every component's OWNING entry (the sense 62bf111b rides on eb6ed820).
COMPONENT_ENTRIES = frozenset({
    "57731707-88f6-49b7-8163-40e54c3843c8", "f398e7f2-13f6-4ca5-a349-4a35ecf716a8",
    "96b36f28-6e00-4e03-b2ab-9169bf2d0c11", "ff91fe37-e13c-4eec-afb0-1698316f9d9a",
    "ff22b7dd-c808-4214-b237-5937cf75c0d4", "d675be41-59a4-4f75-b28d-31e0588be156",
    "c714ef74-2ae2-4442-a04c-ad39db5e8abe", "56e89046-2b02-4b58-8fd0-bed80955c908",
    "2b17c62a-1ec0-428d-8208-dc71f4f5be07", "eb6ed820-825c-45e3-abc1-4b29fa92475a",
})
PICKS = frozenset(COMPLEX) | COMPONENT_ENTRIES
# Narrowed-run probe: '-lkoj', used only by khalkojsimnita (ref 1c7a4f20).
UNPICKED_COMPONENT = "c714ef74-2ae2-4442-a04c-ad39db5e8abe"
NARROWED_REF = "1c7a4f20-5453-4d9e-bdc2-7b7865ac1248"

_FIELDS = ("ComponentLexemes", "PrimaryLexemes", "ShowComplexFormsIn",
           "ComplexEntryTypes")
_REF_RT = re.compile(
    r'<rt class="LexEntryRef" guid="([^"]+)" ownerguid="([^"]+)">(.*?)</rt>', re.S)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME, pytrace=False)


def _open_ro(name):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    try:
        proj.OpenProject(projectName=name, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] cannot open %r read-only: %s" % (name, exc),
                    pytrace=False)
    return proj


def _read_refs_lcm(project_name, ref_guids):
    """{ref_guid: {owner, RefType, <field>: [guid, ...]}} read through a fresh
    read-only LCM open with explicit casts (ICmObjectRepository + ILexEntryRef),
    independent of the engine's own resolution helpers."""
    proj = _open_ro(project_name)
    try:
        from SIL.LCModel import ICmObject, ICmObjectRepository, ILexEntryRef
        from System import Guid
        repo = proj.ObjectRepository(ICmObjectRepository)
        out = {}
        for g in ref_guids:
            parsed = Guid.Parse(g)
            if not repo.IsValidObjectId(parsed):
                continue
            ref = ILexEntryRef(repo.GetObject(parsed))

            def guids(seq):
                return [str(ICmObject(x).Guid).lower() for x in seq]
            out[g] = {
                "owner": str(ICmObject(ref).Owner.Guid).lower(),
                "RefType": int(ref.RefType),
                "ComponentLexemes": guids(ref.ComponentLexemesRS),
                "PrimaryLexemes": guids(ref.PrimaryLexemesRS),
                "ShowComplexFormsIn": guids(ref.ShowComplexFormsInRS),
                "ComplexEntryTypes": guids(ref.ComplexEntryTypesRS),
            }
        return out
    finally:
        proj.CloseProject()


def _read_refs_xml(path):
    """Same shape, parsed straight from the target .fwdata XML."""
    txt = Path(path).read_text(encoding="utf-8")
    out = {}
    for m in _REF_RT.finditer(txt):
        body = m.group(3)
        rt = re.search(r'<RefType val="(\d+)"', body)
        rec = {"owner": m.group(2).lower(), "RefType": int(rt.group(1)) if rt else 0}
        for f in _FIELDS:
            b = re.search(r"<%s>(.*?)</%s>" % (f, f), body, re.S)
            rec[f] = ([g.lower() for g in re.findall(r'guid="([^"]+)"', b.group(1))]
                      if b else [])
        out[m.group(1).lower()] = rec
    return out


def _selection(picks):
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    return Selection(categories={GC.STEMS: True, GC.AFFIXES: True},
                     include_closure=True,
                     leaf_item_picks={GC.STEMS: frozenset(picks),
                                      GC.AFFIXES: frozenset(picks)})


def _run(picks, preview_only=False):
    from harness import full_run
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        preview_only=preview_only,
        selection_transform=lambda _full: _selection(picks))


def _entryref_drops(records):
    """(field, owner_guid, item_guid) of every LexEntryRef-related drop:
    EntryRefsOS on a LexEntry, or any field on a LexEntryRef."""
    return sorted(
        (d.field_name, d.owner_guid, d.item_guid) for d in records or ()
        if d.field_name == "EntryRefsOS" or d.owner_kind == "LexEntryRef")


@pytest.fixture(autouse=True)
def _restore_around():
    _restore()
    yield
    _restore()


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_complex_form_entry_refs_reproduce_0_to_n_idempotently():
    expected = _read_refs_lcm(SOURCE_NAME, COMPLEX.values())
    assert set(expected) == set(COMPLEX.values()), "source refs missing"
    for owner, ref_guid in COMPLEX.items():
        src = expected[ref_guid]
        assert src["owner"] == owner and src["RefType"] == 1
        assert len(src["ComponentLexemes"]) >= 2
        assert set(src["PrimaryLexemes"]) < set(src["ComponentLexemes"])
        assert src["ComplexEntryTypes"]
    print("[LIVE] source refs:", expected)

    pre = _read_refs_xml(TARGET_PATH)
    assert not set(COMPLEX.values()) & set(pre), "sandbox not clean"
    pre_total = len(pre)

    # Preview: C3 decisions surfaced for every ref Move will create.
    plan, _ = _run(PICKS, preview_only=True)
    c3 = {d.owner_guid for a in plan.actions
          for d in (getattr(a, "reference_decisions", ()) or ())
          if d.owner_kind == "LexEntryRef" and d.field_name == "ComplexEntryTypesRS"}
    assert c3 == set(COMPLEX.values()), "Preview did not surface C3 decisions"
    preview_drops = _entryref_drops(plan.dropped_items)

    # Move #1.
    plan1, report1 = _run(PICKS)
    move_drops = _entryref_drops(report1.dropped_items)
    print("[LIVE] move#1 actions=%d entryref drops=%s" % (
        len(plan1.actions), move_drops))
    assert preview_drops == move_drops, "Preview/Move LexEntryRef drop sets differ"
    assert not [d for d in move_drops if d[0] == "EntryRefsOS"], (
        "a reproduced ref was reported dropped: %s" % move_drops)

    after_xml = _read_refs_xml(TARGET_PATH)
    after_lcm = _read_refs_lcm(TARGET_NAME, COMPLEX.values())
    assert len(after_xml) == pre_total + len(COMPLEX), "0 -> N count"
    for ref_guid, src in expected.items():
        assert after_xml.get(ref_guid) == src, (
            "XML mismatch for %s: %s != %s" % (ref_guid, after_xml.get(ref_guid), src))
        assert after_lcm.get(ref_guid) == src, (
            "LCM mismatch for %s: %s != %s" % (ref_guid, after_lcm.get(ref_guid), src))

    # Move #2: idempotent.
    plan2, report2 = _run(PICKS)
    print("[LIVE] move#2 actions=%d" % len(plan2.actions))
    assert len(plan2.actions) == 0
    assert _read_refs_xml(TARGET_PATH) == after_xml, "re-Move changed a LexEntryRef"
    assert not [d for d in _entryref_drops(report2.dropped_items)
                if d[0] == "EntryRefsOS"]


def test_narrowed_run_reports_the_ref_with_an_unpicked_component():
    """Run-scoped C4: with '-lkoj' un-picked, ref 1c7a4f20 cannot be fully
    reproduced on this run -- Preview and Move must both report exactly it
    (pre-#32 the intrinsic check called it reproducible)."""
    picks = PICKS - {UNPICKED_COMPONENT}
    plan, _ = _run(picks, preview_only=True)
    preview = [g for f, _o, g in _entryref_drops(plan.dropped_items)
               if f == "EntryRefsOS"]
    _plan, report = _run(picks)
    move = [g for f, _o, g in _entryref_drops(report.dropped_items)
            if f == "EntryRefsOS"]
    print("[LIVE] narrowed: preview=%s move=%s" % (preview, move))
    assert preview == move == [NARROWED_REF]
