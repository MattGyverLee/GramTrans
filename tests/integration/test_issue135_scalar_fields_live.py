"""Issue #135 live gate -- scalar/text fields flexicon omits round-trip.

WRITE PATH: writes ONLY two throwaways:

* ``GT-Src-135`` -- SOURCE: fresh file copy of ``Korean-GIAL`` (never opened
  itself; its .fwdata SHA-256 is asserted unchanged) seeded here with values
  for LexEntry.SummaryDefinition/Restrictions, LexSense.AnthroNote/UsageNote,
  LexPronunciation.CVPattern/Tone, LexEtymology.Note/PrecComment and
  Text.Source (incl. a ko-fonipa alternative the restored Target lacks, so the
  ws_map path is exercised).
* ``Target`` -- restored headlessly from ``Target 2026-07-06 0218.fwbackup``
  before and after (the caller holds the lockout claim "Target-live-flex").

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue135_scalar_fields_live.py -v -s
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
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

ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
ORIGIN = "Korean-GIAL"
SOURCE_NAME = "GT-Src-135"
TARGET_NAME = "Target"
TARGET_PATH = str(ROOT / "Target" / "Target.fwdata")
ORIGIN_PATH = ROOT / ORIGIN / (ORIGIN + ".fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
ENTRY = "00e82a75-27fe-4396-9fa3-38b6cac28581"   # stem entry, no refs (#114 SPARE_1)

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

SEEDS = {
    "SummaryDefinition": {"en": "135 summary en", "ko-fonipa": "135 summary ko"},
    "Restrictions": {"en": "135 restr en"},
    "AnthroNote": {"en": "135 anthro en", "ko-fonipa": "135 anthro ko"},
    "UsageNote": {"en": "135 usage en"},
    "Note": {"en": "135 etym note en"},
    "PrecComment": {"en": "135 prec en"},
    "Source": {"en": "135 text source en", "ko-fonipa": "135 text source ko"},
}
CV, TONE = "CVC", "HL"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup not found", pytrace=False)


def _open(name, write=False):
    if write:
        assert name == SOURCE_NAME
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    p = FLExProject()
    if write:
        p.OpenProject(projectName=name, writeEnabled=True, undoable=False)
    else:
        p.OpenProject(projectName=name, writeEnabled=False)
    return p


def _h(proj, ws_id):
    for ws in proj.WritingSystems.GetAll():
        if ws.Id == ws_id:
            return ws.Handle
    pytest.fail("no ws %s" % ws_id, pytrace=False)


def _set_ms(proj, ms, alts):
    from SIL.LCModel.Core.Text import TsStringUtils
    for ws_id, text in alts.items():
        h = _h(proj, ws_id)
        ms.set_String(h, TsStringUtils.MakeString(text, h))


def _get_ms(proj, ms):
    out = {}
    for ws in proj.WritingSystems.GetAll():
        t = ms.get_String(ws.Handle).Text
        if t:
            out[ws.Id] = str(t)
    return out


def _obj(proj, guid, iface):
    from SIL.LCModel import ICmObjectRepository
    from System import Guid
    return iface(proj.ObjectRepository(ICmObjectRepository).GetObject(Guid.Parse(guid)))


def _build_source():
    sdir = ROOT / SOURCE_NAME
    if sdir.exists():
        shutil.rmtree(sdir)
    shutil.copytree(ROOT / ORIGIN, sdir, ignore=shutil.ignore_patterns("*.lock", "*.bak"))
    (sdir / (ORIGIN + ".fwdata")).rename(sdir / (SOURCE_NAME + ".fwdata"))
    proj = _open(SOURCE_NAME, write=True)
    from SIL.LCModel import (ILexEntry, IText, ILexPronunciationFactory,
                             ILexEtymologyFactory)
    from SIL.LCModel.Core.Text import TsStringUtils
    try:
        e = _obj(proj, ENTRY, ILexEntry)
        _set_ms(proj, e.SummaryDefinition, SEEDS["SummaryDefinition"])
        _set_ms(proj, e.Restrictions, SEEDS["Restrictions"])
        assert e.SensesOS.Count >= 1, "seed entry has no sense"
        s = e.SensesOS[0]
        _set_ms(proj, s.AnthroNote, SEEDS["AnthroNote"])
        _set_ms(proj, s.UsageNote, SEEDS["UsageNote"])
        en = _h(proj, "en")
        pf = proj.GetFactory(ILexPronunciationFactory)
        pron = pf.Create()
        e.PronunciationsOS.Add(pron)
        pron.CVPattern = TsStringUtils.MakeString(CV, en)
        pron.Tone = TsStringUtils.MakeString(TONE, en)
        ef = proj.GetFactory(ILexEtymologyFactory)
        et = ef.Create()
        e.EtymologyOS.Add(et)
        _set_ms(proj, et.Note, SEEDS["Note"])
        _set_ms(proj, et.PrecComment, SEEDS["PrecComment"])
        texts = list(proj.Texts.GetAll())
        assert texts, "source has no text"
        t = IText(texts[0].concrete if hasattr(texts[0], "concrete") else texts[0])
        _set_ms(proj, t.Source, SEEDS["Source"])
        return str(t.Guid)
    finally:
        proj.CloseProject()


def _read_target(text_guid):
    from SIL.LCModel import ILexEntry, IText
    proj = _open(TARGET_NAME)
    try:
        e = _obj(proj, ENTRY, ILexEntry)
        got = {
            "SummaryDefinition": _get_ms(proj, e.SummaryDefinition),
            "Restrictions": _get_ms(proj, e.Restrictions),
            "AnthroNote": _get_ms(proj, e.SensesOS[0].AnthroNote),
            "UsageNote": _get_ms(proj, e.SensesOS[0].UsageNote),
        }
        assert e.PronunciationsOS.Count == 1 and e.EtymologyOS.Count == 1
        p = e.PronunciationsOS[0]
        got["CVPattern"] = str(p.CVPattern.Text or "")
        got["Tone"] = str(p.Tone.Text or "")
        et = e.EtymologyOS[0]
        got["Note"] = _get_ms(proj, et.Note)
        got["PrecComment"] = _get_ms(proj, et.PrecComment)
        got["Source"] = _get_ms(proj, _obj(proj, text_guid, IText).Source)
        return got
    finally:
        proj.CloseProject()


@pytest.fixture(scope="module")
def src():
    before = _sha(ORIGIN_PATH)
    tg = _build_source()
    yield tg
    assert _sha(ORIGIN_PATH) == before, "Korean-GIAL changed"


@pytest.fixture(autouse=True)
def _around():
    _restore()
    yield
    _restore()


def _run(text_guid):
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def _sel(_full):
        picks = frozenset({ENTRY})
        return Selection(
            categories={GC.STEMS: True, GC.AFFIXES: True, GC.TEXTS: True},
            include_closure=True,
            leaf_item_picks={GC.STEMS: picks, GC.AFFIXES: picks},
            text_picks=frozenset({text_guid}))
    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, ws_mapping_mode="full",
        selection_transform=_sel)


def test_fields_round_trip_from_populated_source(src):
    plan, report = _run(src)
    got = _read_target(src)
    print("[LIVE] target values:", got)
    drops = [(d.owner_kind, d.field_name, d.reason) for d in report.dropped_items or ()
             if d.field_name in set(SEEDS) | {"CVPattern", "Tone"}]
    print("[LIVE] #135 drops:", drops)
    for k, v in SEEDS.items():
        assert got[k] == v, "%s: %s != %s" % (k, got[k], v)
    assert got["CVPattern"] == CV and got["Tone"] == TONE
    assert drops == []
