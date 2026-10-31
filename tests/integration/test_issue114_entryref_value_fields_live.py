"""Issue #114 live gate -- LexEntryRef `HideMinorEntry` / `Summary`.

WRITE PATH: writes ONLY two private throwaways:

* ``GT-Src-114``     -- the SOURCE: a fresh file copy of ``Korean-GIAL`` made
  by this module (``.fwdata`` renamed to match the folder), opened
  write-enabled only while the fixture values are authored on it.
* ``GT-Sandbox-114`` -- the TARGET, restored headlessly from
  ``Target 2026-07-06 0218.fwbackup`` before AND after each test.

``Korean-GIAL`` itself is only ever COPIED at the file level (never opened);
its ``.fwdata`` SHA-256 is asserted unchanged across the module.

Why a private copy: every one of Korean-GIAL's 41 LexEntryRefs has
``HideMinorEntry == 0`` and no ``Summary`` (read-only XML scan, issue #114),
so it cannot exercise either field as-is. The four #32 complex-form refs are
reused (known-good closure, live-proven by PR #112) and seeded:

  38751f5b  HideMinorEntry=1, no Summary
  ff749d17  HideMinorEntry=0, Summary in en AND ko-fonipa (a WS the
            restored Target lacks, so the ws_mapping path is exercised)
  1c7a4f20  HideMinorEntry=1, Summary in en
  5faa892d  untouched: 0 / empty (an empty source must not blank anything)

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue114_entryref_value_fields_live.py -v -s

SKIPS when FLEXLIBS_REQUIRE_LIVE != 1; under FLEXLIBS_REQUIRE_LIVE=1 a missing
source/backup/flexicon FAILS (never a quiet skip).

The re-run MERGE arm (`_run_entryref_create_pass`'s INV-1 branch) only runs
when the STEMS tail runs, i.e. when the plan holds at least one STEMS action:
a pure re-Move plans 0 actions and never reaches it. So the merge test adds a
SPARE stem entry (no refs, not a component) to each re-run to force the tail.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
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

PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
ORIGIN_NAME = "Korean-GIAL"        # file-copied only, never opened
SOURCE_NAME = "GT-Src-114"         # private source copy (authored here)
TARGET_NAME = "GT-Sandbox-114"     # the ONLY other project this module writes
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
SOURCE_PATH = str(PROJECTS_ROOT / SOURCE_NAME / ("%s.fwdata" % SOURCE_NAME))
ORIGIN_PATH = PROJECTS_ROOT / ORIGIN_NAME / ("%s.fwdata" % ORIGIN_NAME)
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

# Complex-form entry GUID -> its RefType=1 LexEntryRef GUID (as in #32).
COMPLEX = {
    "38a8b1b3-25de-4eb1-a1d3-3e5c7753abdf": "38751f5b-16c3-41b0-884b-589e6a36888b",
    "4a956f4a-3123-41c9-a8d5-72eef48cdfcc": "ff749d17-34bc-470e-a9ed-714269923a0f",
    "5b4307bb-9f08-4e8f-bdc7-1cc54e0df333": "1c7a4f20-5453-4d9e-bdc2-7b7865ac1248",
    "b135b153-6cf1-4731-8351-e02960bbac9a": "5faa892d-f9f9-4b25-a8d4-18a5ce664cf6",
}
COMPONENT_ENTRIES = frozenset({
    "57731707-88f6-49b7-8163-40e54c3843c8", "f398e7f2-13f6-4ca5-a349-4a35ecf716a8",
    "96b36f28-6e00-4e03-b2ab-9169bf2d0c11", "ff91fe37-e13c-4eec-afb0-1698316f9d9a",
    "ff22b7dd-c808-4214-b237-5937cf75c0d4", "d675be41-59a4-4f75-b28d-31e0588be156",
    "c714ef74-2ae2-4442-a04c-ad39db5e8abe", "56e89046-2b02-4b58-8fd0-bed80955c908",
    "2b17c62a-1ec0-428d-8208-dc71f4f5be07", "eb6ed820-825c-45e3-abc1-4b29fa92475a",
})
PICKS = frozenset(COMPLEX) | COMPONENT_ENTRIES
# Stem entries with no refs, not components of any ref: adding one to a
# re-run gives the plan a STEMS action, so the STEMS tail (C1) runs.
SPARE_1 = "00e82a75-27fe-4396-9fa3-38b6cac28581"
SPARE_2 = "02d00679-1d52-4767-9935-260ed2dc7c17"

REF_HIDE_ONLY = "38751f5b-16c3-41b0-884b-589e6a36888b"
REF_TWO_WS = "ff749d17-34bc-470e-a9ed-714269923a0f"
REF_BOTH = "1c7a4f20-5453-4d9e-bdc2-7b7865ac1248"
REF_DEFAULT = "5faa892d-f9f9-4b25-a8d4-18a5ce664cf6"

SEED = {
    REF_HIDE_ONLY: (1, {}),
    REF_TWO_WS: (0, {"en": "114 summary two-ws (en)",
                     "ko-fonipa": "114 summary two-ws (ko-fonipa)"}),
    REF_BOTH: (1, {"en": "114 summary both (en)"}),
    REF_DEFAULT: (0, {}),
}

_REF_RT = re.compile(
    r'<rt class="LexEntryRef" guid="([^"]+)" ownerguid="([^"]+)">(.*?)</rt>', re.S)
_ASTR = re.compile(r'<AStr ws="([^"]+)">(.*?)</AStr>', re.S)
_RUN = re.compile(r'<Run[^>]*>(.*?)</Run>', re.S)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME, pytrace=False)


def _restore_target():
    assert TARGET_NAME == "GT-Sandbox-114"  # pinned before any write
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


def _open(name, write=False):
    if write:
        assert name in (SOURCE_NAME, TARGET_NAME), name  # never anything else
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    try:
        if write:
            proj.OpenProject(projectName=name, writeEnabled=True, undoable=False)
        else:
            proj.OpenProject(projectName=name, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] cannot open %r: %s" % (name, exc), pytrace=False)
    return proj


def _ref(proj, guid):
    from SIL.LCModel import ICmObjectRepository, ILexEntryRef
    from System import Guid
    repo = proj.ObjectRepository(ICmObjectRepository)
    return ILexEntryRef(repo.GetObject(Guid.Parse(guid)))


def _handle(proj, ws_id):
    for ws in proj.WritingSystems.GetAll():
        if ws.Id == ws_id:
            return ws.Handle
    pytest.fail("[FAIL] project has no writing system %r" % ws_id, pytrace=False)


def _set_values(name, values):
    """values: {ref_guid: (hide or None, {ws_id: text-or-""})}."""
    from SIL.LCModel.Core.Text import TsStringUtils
    proj = _open(name, write=True)
    try:
        for guid, (hide, alts) in values.items():
            ref = _ref(proj, guid)
            if hide is not None:
                ref.HideMinorEntry = hide
            for ws_id, text in alts.items():
                h = _handle(proj, ws_id)
                ref.Summary.set_String(h, TsStringUtils.MakeString(text, h))
    finally:
        proj.CloseProject()


def _build_source():
    """Fresh GT-Src-114 = file copy of Korean-GIAL, seeded with SEED."""
    sdir = PROJECTS_ROOT / SOURCE_NAME
    if sdir.exists():
        shutil.rmtree(sdir)
    shutil.copytree(PROJECTS_ROOT / ORIGIN_NAME, sdir,
                    ignore=shutil.ignore_patterns("*.lock", "*.bak"))
    (sdir / ("%s.fwdata" % ORIGIN_NAME)).rename(sdir / ("%s.fwdata" % SOURCE_NAME))
    _set_values(SOURCE_NAME, {g: (h, a) for g, (h, a) in SEED.items() if h or a})


def _read_values_xml(path):
    """{ref_guid: {"HideMinorEntry": int, "Summary": {ws: text}}} straight from
    the .fwdata XML (absent HideMinorEntry element == the LCM default 0)."""
    txt = Path(path).read_text(encoding="utf-8")
    out = {}
    for m in _REF_RT.finditer(txt):
        body = m.group(3)
        h = re.search(r'<HideMinorEntry val="(-?\d+)"', body)
        summ = {}
        sm = re.search(r"<Summary>(.*?)</Summary>", body, re.S)
        if sm:
            for ws, inner in _ASTR.findall(sm.group(1)):
                text = "".join(_RUN.findall(inner))
                if text:
                    summ[ws] = text
        out[m.group(1).lower()] = {
            "HideMinorEntry": int(h.group(1)) if h else 0, "Summary": summ}
    return out


def _read_ref_bodies_xml(path, guids):
    txt = Path(path).read_text(encoding="utf-8")
    return {m.group(1).lower(): m.group(0) for m in _REF_RT.finditer(txt)
            if m.group(1).lower() in guids}


def _read_values_lcm(name, guids):
    """Same shape through a fresh read-only LCM open (explicit casts)."""
    proj = _open(name)
    try:
        wss = [(ws.Id, ws.Handle) for ws in proj.WritingSystems.GetAll()]
        out = {}
        for g in guids:
            ref = _ref(proj, g)
            summ = {}
            for ws_id, h in wss:
                text = ref.Summary.get_String(h).Text
                if text:
                    summ[ws_id] = str(text)
            out[g] = {"HideMinorEntry": int(ref.HideMinorEntry), "Summary": summ}
        return out
    finally:
        proj.CloseProject()


def _expected():
    return {g: {"HideMinorEntry": h, "Summary": dict(a)} for g, (h, a) in SEED.items()}


def _selection(picks):
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    return Selection(categories={GC.STEMS: True, GC.AFFIXES: True},
                     include_closure=True,
                     leaf_item_picks={GC.STEMS: frozenset(picks),
                                      GC.AFFIXES: frozenset(picks)})


def _run(picks):
    from harness import full_run
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        selection_transform=lambda _full: _selection(picks))


def _value_drops(report):
    return [(d.owner_guid, d.field_name, d.item_name, d.reason)
            for d in report.dropped_items or ()
            if d.owner_kind == "LexEntryRef"
            and d.field_name in ("HideMinorEntry", "Summary")]


def _entry_in_target(guid) -> bool:
    return ('<rt class="LexEntry" guid="%s"' % guid) in Path(TARGET_PATH).read_text(
        encoding="utf-8")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _source():
    import flexicon
    import gramtrans
    print("[LIVE] gramtrans.__file__ =", gramtrans.__file__)
    print("[LIVE] flexicon.__file__  =", flexicon.__file__)
    if not ORIGIN_PATH.is_file():
        pytest.fail("[FAIL] %s not found" % ORIGIN_PATH, pytrace=False)
    before = _sha256(ORIGIN_PATH)
    print("[LIVE] %s sha256 before = %s" % (ORIGIN_NAME, before))
    _build_source()
    src = _read_values_xml(SOURCE_PATH)
    print("[LIVE] seeded source values:", {g: src[g] for g in SEED})
    assert {g: src[g] for g in SEED} == _expected(), "source seeding failed"
    yield
    after = _sha256(ORIGIN_PATH)
    print("[LIVE] %s sha256 after  = %s" % (ORIGIN_NAME, after))
    assert after == before, "Korean-GIAL changed -- it must never be written"


@pytest.fixture(autouse=True)
def _restore_around():
    _restore_target()
    yield
    _restore_target()


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_values_reproduce_on_create_and_pure_rerun_writes_nothing():
    pre = _read_values_xml(TARGET_PATH)
    assert not set(SEED) & set(pre), "sandbox not clean"

    plan1, report1 = _run(PICKS)
    print("[LIVE] move#1 actions=%d value drops=%s" % (
        len(plan1.actions), _value_drops(report1)))
    assert _value_drops(report1) == []
    after_xml = _read_values_xml(TARGET_PATH)
    after_lcm = _read_values_lcm(TARGET_NAME, SEED)
    print("[LIVE] target after move#1:", {g: after_xml.get(g) for g in SEED})
    for g, want in _expected().items():
        assert after_xml.get(g) == want, "XML %s: %s != %s" % (g, after_xml.get(g), want)
        assert after_lcm.get(g) == want, "LCM %s: %s != %s" % (g, after_lcm.get(g), want)

    bodies = _read_ref_bodies_xml(TARGET_PATH, set(SEED))
    plan2, report2 = _run(PICKS)
    print("[LIVE] move#2 actions=%d" % len(plan2.actions))
    assert len(plan2.actions) == 0
    assert _read_ref_bodies_xml(TARGET_PATH, set(SEED)) == bodies
    assert _value_drops(report2) == []


def test_rerun_merge_arm_writes_nothing_when_equal_and_merges_divergence():
    _run(PICKS)
    bodies = _read_ref_bodies_xml(TARGET_PATH, set(SEED))

    # Re-run that REACHES the merge arm (SPARE_1 is a new STEMS action) on a
    # target whose values already match: nothing may change.
    plan_a, report_a = _run(PICKS | {SPARE_1})
    print("[LIVE] re-run A actions=%d" % len(plan_a.actions))
    assert len(plan_a.actions) >= 1
    assert _entry_in_target(SPARE_1), "STEMS tail did not run (spare not created)"
    assert _read_ref_bodies_xml(TARGET_PATH, set(SEED)) == bodies, (
        "merge arm wrote to an already-equal LexEntryRef")
    assert _value_drops(report_a) == []

    # Diverge the TARGET, then re-run through the merge arm again.
    _set_values(TARGET_NAME, {
        REF_HIDE_ONLY: (0, {}),                                   # diverged int
        REF_TWO_WS: (None, {"en": "TARGET EDIT"}),                # diverged alt
        REF_BOTH: (None, {"en": "", "ko-fonipa": "target only"}),  # blank + target-only
        REF_DEFAULT: (1, {"en": "target-only summary"}),          # source 0 / empty
    })
    diverged = _read_values_xml(TARGET_PATH)
    print("[LIVE] diverged target:", {g: diverged[g] for g in SEED})

    plan_b, report_b = _run(PICKS | {SPARE_1, SPARE_2})
    print("[LIVE] re-run B actions=%d value drops=%s" % (
        len(plan_b.actions), _value_drops(report_b)))
    assert _entry_in_target(SPARE_2), "STEMS tail did not run (spare not created)"
    assert _value_drops(report_b) == []
    got = _read_values_lcm(TARGET_NAME, SEED)
    print("[LIVE] merged target:", got)
    want = _expected()
    # REF_BOTH: emptied en alt refilled; the target-only ko-fonipa alt kept.
    want[REF_BOTH]["Summary"]["ko-fonipa"] = "target only"
    # REF_DEFAULT: empty source Summary never blanks the target; policy Q2:
    # on an existing ref a source HideMinorEntry 0 is UNSET, so the diverged
    # target 1 / source 0 STAYS 1 (and records no drop).
    want[REF_DEFAULT] = {"HideMinorEntry": 1,
                         "Summary": {"en": "target-only summary"}}
    assert got == want
    xml = _read_values_xml(TARGET_PATH)
    for g, w in want.items():
        assert xml[g] == w, "XML %s: %s != %s" % (g, xml[g], w)
