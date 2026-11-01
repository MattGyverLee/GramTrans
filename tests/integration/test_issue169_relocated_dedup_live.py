"""Issue #169 live gate -- relocated records must not collapse, and must not
hide a real loss on the same possibility item.

The possibility CREATE arm (`references.apply_reference`) emits one
`relocated:` record per Name / Abbreviation / Description whose only source
writing system is absent from the target (#158). All of them share the
`(owner_guid, "ThesaurusItemsRC", item_guid)` dedup identity, so before the fix
`categories._append_dropped_once` kept the FIRST and discarded the rest:

* item A (Name/Abbr/Desc all in analysis WS 'de'): 3 relocations -> 1 record;
* item B (Name in 'de', Description in VERNACULAR 'fr' only): the Name
  relocation masked the Description LOSS, so the report said "relocated" for
  an item that actually lost text.

After the fix relocations live in `RunReport.relocated_items` (their own
section, cycle-4 domain ruling c) and losses stay in `dropped_items`.

WRITE PATH: writes ONLY the two private throwaway projects below, both
restored from ``Target 2026-07-06 0218.fwbackup`` first:

* ``GT-Src-169``     -- SOURCE (write-enabled only while authoring)
* ``GT-Sandbox-169`` -- TARGET

Never Target, Esperanto, Ejagham*, Mbugwe*, Ngoreme*, GT-Probe-158-*, or
another agent's GT-Src-NNN / GT-Sandbox-NNN.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue169_relocated_dedup_live.py -v -s
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "GT-Src-169"
TARGET_NAME = "GT-Sandbox-169"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _guard(name):
    # Write guard: these two throwaway projects and nothing else.
    assert name in (SOURCE_NAME, TARGET_NAME), name
    assert TARGET_NAME == "GT-Sandbox-169" and SOURCE_NAME == "GT-Src-169"


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore(name):
    _guard(name)
    from harness.restore import restore_target
    restore_target(name, backup_path=_backup_path())


def _open(name, write=False):
    assert not write or name == SOURCE_NAME, name  # write guard
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
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but cannot open %r: %s" % (name, exc))
    return proj


def _g(obj) -> str:
    return str(obj.Guid).lower()


def _author_source() -> dict:
    """Source-only: analysis WS 'de' and vernacular WS 'fr' (both absent from
    the target), two DomainTypes possibilities referenced from one sense."""
    from SIL.LCModel import (ICmPossibilityFactory, ICmPossibilityList,
                             ILangProject, ILexDb, ILexSense)
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid
    proj = _open(SOURCE_NAME, write=True)
    try:
        ws = proj.WritingSystems
        ws.Create("de", "German", is_vernacular=False)
        ws.Create("fr", "French", is_vernacular=True)
        lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
        wsf = proj.Cache.WritingSystemFactory
        de, fr = wsf.GetWsFromStr("de"), wsf.GetWsFromStr("fr")
        pf = ICmPossibilityFactory(
            proj.Cache.ServiceLocator.GetService(ICmPossibilityFactory))
        dom = ICmPossibilityList(lexdb.DomainTypesOA)
        item_a = pf.Create(Guid.NewGuid(), dom)
        item_b = pf.Create(Guid.NewGuid(), dom)
        for ms, w, text in (
                (item_a.Name, de, "GT169-A-Name-DE"),
                (item_a.Abbreviation, de, "GT169-A-Abb-DE"),
                (item_a.Description, de, "GT169-A-Desc-DE"),
                (item_b.Name, de, "GT169-B-Name-DE"),
                (item_b.Description, fr, "GT169-B-Desc-FR")):
            ms.set_String(w, TsStringUtils.MakeString(text, w))
        entry = proj.LexEntry.Create("gtonesixtynine", create_blank_sense=False)
        sense = ILexSense(proj.Senses.Create(entry, "gt169 sense"))
        sense.ThesaurusItemsRC.Add(item_a)
        sense.ThesaurusItemsRC.Add(item_b)
        return dict(item_a=_g(item_a), item_b=_g(item_b), sense=_g(sense))
    finally:
        proj.CloseProject()


def _readback(fx) -> dict:
    from SIL.LCModel import ICmPossibility
    from System import Guid
    proj = _open(TARGET_NAME)
    try:
        repo = proj.Cache.ServiceLocator.ObjectRepository
        wsf = proj.Cache.WritingSystemFactory
        out = {}
        for key in ("item_a", "item_b"):
            poss = ICmPossibility(repo.GetObject(Guid.Parse(fx[key])))
            fields = {}
            for f in ("Name", "Abbreviation", "Description"):
                ms = getattr(poss, f)
                fields[f] = {wsf.GetStrFromWs(h): ms.get_String(h).Text
                             for h in ms.AvailableWritingSystemIds}
            out[key] = fields
        return out
    finally:
        proj.CloseProject()


def _is_relocation(d) -> bool:
    return str(getattr(d, "reason", "")).startswith("relocated:")


def _relocations(report) -> list:
    # Pre-fix there is no `relocated_items`; relocations sat in dropped_items.
    return (list(getattr(report, "relocated_items", ()))
            + [d for d in report.dropped_items if _is_relocation(d)])


@pytest.fixture(scope="module")
def live():
    try:
        import flexicon
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    _restore(SOURCE_NAME)
    _restore(TARGET_NAME)
    fx = _author_source()
    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
        selection_transform=lambda _f: Selection(categories={GC.STEMS: True}))
    res = {"fx": fx, "plan": plan, "report": report, "post": _readback(fx)}
    import gramtrans
    print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
    print("[LIVE] source=%s target=%s fixture=%s" % (SOURCE_NAME, TARGET_NAME, fx))
    print("[LIVE] actions=%d" % len(plan.actions))
    for d in report.dropped_items:
        if d.item_guid in (fx["item_a"], fx["item_b"]):
            print("[LIVE] DROPPED   %s | %s" % (d.item_guid[:8], d.reason))
    for d in getattr(report, "relocated_items", ()):
        print("[LIVE] RELOCATED %s | %s" % (d.item_guid[:8], d.reason))
    print("[LIVE] readback=%s" % res["post"])
    return res


def _fields(records):
    return sorted(r.reason.split()[1] for r in records)


def test_three_sibling_relocations_are_not_collapsed(live):
    fx, report = live["fx"], live["report"]
    recs = [d for d in _relocations(report) if d.item_guid == fx["item_a"]]
    assert _fields(recs) == ["Abbreviation", "Description", "Name"], [
        d.reason for d in recs]
    # The text really landed in the target default analysis WS.
    post = live["post"]["item_a"]
    assert post["Name"].get("en") == "GT169-A-Name-DE"
    assert post["Abbreviation"].get("en") == "GT169-A-Abb-DE"
    assert (post["Description"].get("en") or "").startswith("GT169-A-Desc-DE")


def test_loss_on_same_item_is_reported_as_a_loss(live):
    fx, report = live["fx"], live["report"]
    losses = [d for d in report.dropped_items
              if d.item_guid == fx["item_b"] and not _is_relocation(d)]
    assert losses, ("[FAIL] item B's vernacular-only Description was lost but "
                    "no loss record survived: %s" % [
                        d.reason for d in report.dropped_items
                        if d.item_guid == fx["item_b"]])
    assert "'fr' absent in target" in losses[0].reason
    relocs = [d for d in _relocations(report) if d.item_guid == fx["item_b"]]
    assert _fields(relocs) == ["Name"]
    post = live["post"]["item_b"]
    assert post["Name"].get("en") == "GT169-B-Name-DE"
    assert "GT169-B-Desc-FR" not in "".join(post["Description"].values())


def test_relocations_live_apart_from_losses(live):
    report = live["report"]
    assert hasattr(report, "relocated_items")
    assert not [d for d in report.dropped_items if _is_relocation(d)]
    assert all(_is_relocation(d) for d in report.relocated_items)
    # Ruling (a): a relocation is not lossless -- the owner stays PARTIAL.
    owner = live["fx"]["sense"]
    assert owner in report.fidelity_by_guid
    from gramtrans.Lib.report import render_text_summary
    text = "\n".join(render_text_summary(report))
    assert "Relocated text" in text
