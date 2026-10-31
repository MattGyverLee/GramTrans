"""Issue #130 live gate -- OVERWRITE of an inflectional MSA's SlotsRC.

WRITE PATH: writes ONLY ``GT-Sandbox-130``, restored headlessly from
``Target 2026-07-06 0218.fwbackup`` at module start.  ``Ngoreme`` (the 128-MSA
slot source of test_issue31_msa_slot_live.py) is opened READ-ONLY and its
``.fwdata`` SHA-256 is asserted unchanged.

HOW OVERWRITE IS DRIVEN.  The planner cannot produce an MSA OVERWRITE with
differing slot membership: `preview._msa_fingerprint` includes the slot-GUID
set, so a differing membership matches nothing and plans an ADD instead.  So
this test drives the real `transfer._execute_overwrite` directly with a real
`PlannedOverwrite(category=MSA)` against the live source and target handles
(the same call path the executor uses at transfer.py's OVERWRITE loop, and the
precedent of test_issue55_gold_merge_live.py).

Steps: Move 1 (full transfer, as #31) lands the source MSAs; then for each
chosen MSA the target membership is SEEDED to a different slot of the same
POS, and
  (b) a real OVERWRITE must make SlotsRC equal the source's, no records;
  (c) mutation: Add made a no-op, then a raiser (via a proxy over the real
      collection wrapped in at the `_overwrite_msa_slots` call) must give
      WRITE_FAILED and leave the PRE-OVERWRITE membership on read-back.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.
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

SOURCE_NAME = "Ngoreme"                 # READ-ONLY
TARGET_NAME = "GT-Sandbox-130"          # the ONLY project this module writes
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
_PROJECTS_ROOT = Path(os.environ.get(
    "GRAMTRANS_PROJECTS_ROOT", "C:/ProgramData/SIL/FieldWorks/Projects"))
TARGET_PATH = str(_PROJECTS_ROOT / TARGET_NAME)
SOURCE_FWDATA = _PROJECTS_ROOT / SOURCE_NAME / ("%s.fwdata" % SOURCE_NAME)

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups",
                Path("D:/Github/_Projects/_LEX/GramTrans/backups"))


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _selection(_full):
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    cats = (GC.POS, GC.GRAM_CATEGORIES, GC.INFLECTION_FEATURES,
            GC.INFLECTION_CLASSES, GC.AFFIXES, GC.SLOTS, GC.AFFIX_TEMPLATES)
    return Selection(categories={c: True for c in cats}, include_closure=True)


def _open(name, write):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    if write:
        assert name == TARGET_NAME == "GT-Sandbox-130"   # pin before ANY write
        proj.OpenProject(projectName=name, writeEnabled=True, undoable=False)
    else:
        proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


class _Sink:
    def __init__(self):
        self.info, self.warnings = [], []

    def Info(self, m):  # noqa: N802
        self.info.append(m)

    def Warning(self, m):  # noqa: N802
        self.warnings.append(m)


class _CollProxy:
    """Real SlotsRC with a mutated Add.  The mutation stops after the second
    Clear() (the best-effort restore) so the restore itself is real."""

    def __init__(self, real, mode, state):
        self._real, self._mode, self._st = real, mode, state

    def Add(self, item):  # noqa: N802
        if not self._st["restoring"]:
            self._st["adds"] += 1
            if self._mode == "noop":
                return
            raise RuntimeError("MUTATION: Add raises")
        self._real.Add(item)

    def Clear(self):  # noqa: N802
        self._st["clears"] += 1
        if self._st["clears"] >= 2:
            self._st["restoring"] = True
        self._real.Clear()

    def __iter__(self):
        return iter(self._real)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _IAProxy:
    def __init__(self, real, mode, state):
        self._real = real
        self.SlotsRC = _CollProxy(real.SlotsRC, mode, state)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _gs(obj):
    from SIL.LCModel import ICmObject
    return str(ICmObject(obj).Guid).lower()


@pytest.fixture(scope="module")
def live():
    assert TARGET_NAME == "GT-Sandbox-130"
    if not SOURCE_FWDATA.is_file():
        pytest.fail("[FAIL] source %s not found" % SOURCE_FWDATA)
    import flexicon
    import gramtrans
    from gramtrans.Lib.census import sha256_of
    from harness import full_run
    from harness.restore import restore_target

    print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
    sha_before = sha256_of(SOURCE_FWDATA)
    restore_target(TARGET_NAME, backup_path=_backup_path())
    plan1, _rep1 = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_selection)
    remap = dict(plan1.identity_remap or {})

    source = _open(SOURCE_NAME, write=False)
    target = _open(TARGET_NAME, write=True)
    try:
        yield dict(source=source, target=target, remap=remap,
                  sha_before=sha_before, sha256_of=sha256_of)
    finally:
        source.CloseProject()
        target.CloseProject()


def _candidates(ev, want=2):
    """(src_msa, tgt_msa, owner_entry_guid, src_slot_guid, other_tgt_slot)."""
    from gramtrans.Lib import categories, transfer
    from SIL.LCModel import ICmObject, IMoInflAffMsa
    source, target, remap = ev["source"], ev["target"], ev["remap"]
    tgt_msas = {}
    for e in categories._iter_lex_entries(target):
        e = categories._cast_lcm(e, "ILexEntry")
        for m in e.MorphoSyntaxAnalysesOC:
            if m.ClassName == "MoInflAffMsa":
                tgt_msas[_gs(m)] = (m, _gs(e))
    out = []
    for e in categories._iter_lex_entries(source):
        e = categories._cast_lcm(e, "ILexEntry")
        for m in e.MorphoSyntaxAnalysesOC:
            if m.ClassName != "MoInflAffMsa":
                continue
            ia = IMoInflAffMsa(m)
            slots = [_gs(s) for s in ia.SlotsRC]
            if len(slots) != 1 or ia.PartOfSpeechRA is None:
                continue
            tgt_key = remap.get(_gs(m), _gs(m))
            if tgt_key not in tgt_msas:
                continue
            tgt_pos = transfer._target_pos_for_source_guid(
                target, _gs(ia.PartOfSpeechRA), src_pos=ia.PartOfSpeechRA,
                source_handle=source)
            if tgt_pos is None:
                continue
            others = [transfer._lcm_slot(s) for s in target.POS.GetAffixSlots(tgt_pos)
                      if _guid_of(s) != slots[0]]
            if not others:
                continue
            tmsa, owner = tgt_msas[tgt_key]
            out.append((m, tmsa, _gs(e), slots[0], others[0], tgt_key))
            if len(out) == want:
                return out
    return out


def _guid_of(s):
    from gramtrans.Lib.categories import _guid_str_from
    from gramtrans.Lib import transfer
    return _guid_str_from(transfer._unwrap(s))


def _members(tmsa):
    from SIL.LCModel import IMoInflAffMsa
    return sorted(_gs(s) for s in IMoInflAffMsa(tmsa).SlotsRC)


def _seed(tmsa, other):
    from SIL.LCModel import IMoInflAffMsa
    ia = IMoInflAffMsa(tmsa)
    ia.SlotsRC.Clear()
    ia.SlotsRC.Add(other)
    return _members(tmsa)


def _run_overwrite(ev, cand, links, wrap_mode=None):
    from gramtrans.Lib import transfer
    from gramtrans.Lib.models import GrammarCategory, PlannedOverwrite
    from gramtrans.Lib.residue import ImportResidueTag
    src_msa, tmsa, owner, _sg, _other, tgt_key = cand
    tag = ImportResidueTag(run_id="GT-20261031-120000",
                           source_project_name=SOURCE_NAME,
                           timestamp="2026-10-31T12:00:00")
    ow = PlannedOverwrite(category=GrammarCategory.MSA, source_guid=_gs(src_msa),
                          target_guid=tgt_key, summary="issue130 live",
                          owner_guid=owner)
    sink = _Sink()
    real = transfer._overwrite_msa_slots
    state = {"clears": 0, "restoring": False, "adds": 0}
    if wrap_mode:
        def _wrapped(src_ia, new_ia, *a, **k):
            return real(src_ia, _IAProxy(new_ia, wrap_mode, state), *a, **k)
        transfer._overwrite_msa_slots = _wrapped
    try:
        transfer._execute_overwrite(ow, ev["source"], ev["target"], sink, tag,
                                    affix_slot_links=links)
    finally:
        transfer._overwrite_msa_slots = real
    return sink, state


def test_clean_overwrite_matches_source_and_adds_no_records(live):
    (cand,) = _candidates(live, want=1)
    src_slot, other = cand[3], cand[4]
    seeded = _seed(cand[1], other)
    print("[LIVE] seeded target MSA %s membership=%s (source=%s)"
          % (cand[5][:8], [g[:8] for g in seeded], src_slot[:8]))
    assert seeded != [src_slot]
    links = []
    _run_overwrite(live, cand, links)
    after = _members(cand[1])
    print("[LIVE] clean OVERWRITE read-back=%s records=%s"
          % ([g[:8] for g in after], links))
    assert after == [src_slot]
    assert links == []


@pytest.mark.parametrize("mode", ["noop", "raise"])
def test_mutated_add_is_write_failed_and_membership_restored(live, mode):
    cands = _candidates(live, want=2)
    assert len(cands) == 2, "[SETUP] need two MSAs to prove the pass continues"
    seeds = {}
    for c in cands:
        seeds[c[5]] = _seed(c[1], c[4])
        assert seeds[c[5]] != [c[3]]
    links = []
    for c in cands:           # both MSAs processed: a failure does not stop the pass
        _run_overwrite(live, c, links, wrap_mode=mode)
    outcomes = [(r.outcome.name, tuple(g[:8] for g in r.unwritten_slot_guids))
                for r in links]
    after = {c[5]: _members(c[1]) for c in cands}
    print("[LIVE] MUTATION %s: records=%s" % (mode, outcomes))
    print("[LIVE] MUTATION %s: details=%s" % (mode, [r.detail for r in links]))
    print("[LIVE] MUTATION %s: pre=%s post=%s" % (
        mode, {k[:8]: [g[:8] for g in v] for k, v in seeds.items()},
        {k[:8]: [g[:8] for g in v] for k, v in after.items()}))
    assert [r.outcome.name for r in links] == ["WRITE_FAILED", "WRITE_FAILED"]
    assert all("restored" in r.detail for r in links)
    assert after == seeds            # PRE-OVERWRITE membership is intact


def test_source_is_unchanged(live):
    assert live["sha256_of"](SOURCE_FWDATA) == live["sha_before"]
