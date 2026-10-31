"""Issue #31 live gate -- `_run_171_subpass` wires MoInflAffMsa.SlotsRC 0 -> N.

`Ejagham Mini` binds no affix MSA to a template slot (0 `msa_slot_bindings`),
so the 17.1 sub-pass had no live proof on the standard pair.  `Ngoreme` does:
128 MoInflAffMsa, every one occupying exactly one slot (128 slot refs,
probed read-only 2026-10-30).

WRITE PATH: writes ONLY the private sandbox ``GT-Sandbox-31``, restored
headlessly from ``Target 2026-07-06 0218.fwbackup`` once at module start.  It
is NOT restored afterwards, so the post-run state can be re-resolved by an
independent reader (FLExToolsMCP).  The source ``Ngoreme`` is opened READ-ONLY
and its ``.fwdata`` SHA-256 is asserted unchanged.  ``Esperanto`` is never
touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1.  When it is set, an unavailable LCM,
source or backup FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue31_msa_slot_live.py -v -s

What it pins, against SOURCE truth walked independently of the plan:

  * baseline: none of the source MSAs is in the sandbox (0 pairs);
  * Move 1: every source (msa, slot) pair is present in the target's SlotsRC,
    MSA resolved by GUID through `plan.identity_remap`, slot by its preserved
    GUID; `RunReport.affix_slot_links` is all LINKED with no failures;
  * Move 2 (no restore between): the pair set is identical, no SlotsRC holds
    a slot twice, and no SlotsRC count changed.

Deliberately NOT asserted: "zero new objects" on Move 2.  A known, separate
defect re-creates MoInflAffixSlot / MoInflAffixTemplate objects on a 0-action
re-run (see test_issue87_residue_idempotent_live.py); #31's idempotency claim
is about SlotsRC membership only.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Ngoreme"                # READ-ONLY
TARGET_NAME = os.environ.get(           # the ONLY project this module writes
    "GT_ISSUE31_SANDBOX", "GT-Sandbox-31")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
_PROJECTS_ROOT = Path(os.environ.get(
    "GRAMTRANS_PROJECTS_ROOT", "C:/ProgramData/SIL/FieldWorks/Projects"))
TARGET_PATH = str(_PROJECTS_ROOT / TARGET_NAME)
SOURCE_FWDATA = _PROJECTS_ROOT / SOURCE_NAME / ("%s.fwdata" % SOURCE_NAME)

#: Measured read-only on 2026-10-30 (FLExToolsMCP and this module agree).
#: A drift here means the SOURCE changed, not the code -- re-measure first.
EXPECTED_SOURCE_WIRED_MSAS = 128
EXPECTED_SOURCE_SLOT_REFS = 128

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (
    _REPO / "backups",
    Path("D:/Github/_Projects/_LEX/GramTrans/backups"),
)


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        p = d / BACKUP_NAME
        if p.is_file():
            return p
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _selection(_full):
    """Affixes plus the columns they sit in and what the MSAs reference.

    AFFIXES + SLOTS + AFFIX_TEMPLATES are all required: issue #33 scopes
    `msa_slot_bindings` to the run, so a templates-only run would record every
    binding as NOT_IN_RUN and an affixes-only run would report SLOT_MISSING.
    """
    from gramtrans.Lib.models import GrammarCategory as GC, Selection
    cats = (GC.POS, GC.GRAM_CATEGORIES, GC.INFLECTION_FEATURES,
            GC.INFLECTION_CLASSES, GC.AFFIXES, GC.SLOTS, GC.AFFIX_TEMPLATES)
    return Selection(categories={c: True for c in cats}, include_closure=True)


def _open_readonly(name):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


def _slot_map(name) -> dict:
    """{msa_guid: [slot_guid, ...]} for every MoInflAffMsa in ``name``.

    Walked with the IMoInflAffMsa cast (SlotsRC is invisible on the base
    interface under pythonnet), independently of the code under test.  The
    list keeps duplicates so a doubled membership is visible.
    """
    from gramtrans.Lib import categories
    from SIL.LCModel import ICmObject, IMoInflAffMsa
    proj = _open_readonly(name)
    try:
        out = {}
        for e in categories._iter_lex_entries(proj):
            e = categories._cast_lcm(e, "ILexEntry")
            for msa in e.MorphoSyntaxAnalysesOC:
                if msa.ClassName != "MoInflAffMsa":
                    continue
                guid = str(ICmObject(msa).Guid).lower()
                out[guid] = [str(ICmObject(s).Guid).lower()
                             for s in IMoInflAffMsa(msa).SlotsRC]
        return out
    finally:
        proj.CloseProject()


def _pairs(slot_map, msa_keys=None) -> set:
    keys = slot_map if msa_keys is None else [k for k in msa_keys if k in slot_map]
    return {(m, s) for m in keys for s in slot_map[m]}


def _link_tally(report) -> Counter:
    return Counter(r.outcome.name for r in report.affix_slot_links)


@pytest.fixture(scope="module")
def live():
    """Restore the sandbox, run Move 1 and Move 2, collect evidence."""
    assert TARGET_NAME.startswith("GT-Sandbox-") and TARGET_NAME != SOURCE_NAME
    if not SOURCE_FWDATA.is_file():
        pytest.fail("[FAIL] source %s not found" % SOURCE_FWDATA)
    try:
        import flexicon  # noqa: F401
    except ImportError as exc:
        pytest.fail("[FAIL] flexicon unavailable: %s" % exc)

    import gramtrans
    from gramtrans.Lib.census import sha256_of
    from harness import full_run
    from harness.restore import restore_target

    print("[LIVE] gramtrans=%s" % gramtrans.__file__)
    print("[LIVE] flexicon=%s" % flexicon.__file__)
    sha_before = sha256_of(SOURCE_FWDATA)

    source = {m: s for m, s in _slot_map(SOURCE_NAME).items() if s}
    restore_target(TARGET_NAME, backup_path=_backup_path())
    baseline = _slot_map(TARGET_NAME)

    plan1, report1 = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_selection)
    remap1 = dict(plan1.identity_remap or {})
    post1 = _slot_map(TARGET_NAME)

    plan2, report2 = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_selection)
    post2 = _slot_map(TARGET_NAME)

    ev = dict(source=source, baseline=baseline, post1=post1, post2=post2,
              plan1=plan1, report1=report1, remap1=remap1,
              plan2=plan2, report2=report2,
              sha_before=sha_before, sha_after=sha256_of(SOURCE_FWDATA))
    tgt_keys = [remap1.get(m, m) for m in source]
    print("[LIVE] source wired MSAs=%d slot refs=%d"
          % (len(source), sum(len(v) for v in source.values())))
    print("[LIVE] bindings plan1=%d plan2=%d | actions plan1=%d plan2=%d | "
          "source MSAs re-keyed by identity_remap=%d"
          % (len(plan1.msa_slot_bindings), len(plan2.msa_slot_bindings),
             len(plan1.actions), len(plan2.actions),
             sum(1 for m in source if remap1.get(m, m) != m)))
    print("[LIVE] target pairs for source MSAs: baseline=%d post1=%d post2=%d"
          % (len(_pairs(baseline, tgt_keys)), len(_pairs(post1, tgt_keys)),
             len(_pairs(post2, tgt_keys))))
    print("[LIVE] target MSAs with SlotsRC (project-wide): baseline=%d "
          "post1=%d post2=%d" % tuple(
              sum(1 for v in snap.values() if v)
              for snap in (baseline, post1, post2)))
    print("[LIVE] link outcomes move1=%s move2=%s"
          % (dict(_link_tally(report1)), dict(_link_tally(report2))))
    print("[LIVE] source sha256 before=%s after=%s"
          % (ev["sha_before"], ev["sha_after"]))
    return ev


def test_source_has_slot_bound_msas(live):
    src = live["source"]
    assert len(src) == EXPECTED_SOURCE_WIRED_MSAS
    assert sum(len(v) for v in src.values()) == EXPECTED_SOURCE_SLOT_REFS


def test_producer_binds_every_source_msa(live):
    """The plan's `msa_slot_bindings` equals source truth on a full-scope run."""
    bindings = {m: sorted(s) for m, s in live["plan1"].msa_slot_bindings.items()}
    assert bindings == {m: sorted(s) for m, s in live["source"].items()}


def test_baseline_has_none_of_the_source_pairs(live):
    tgt_keys = [live["remap1"].get(m, m) for m in live["source"]]
    assert _pairs(live["baseline"], tgt_keys) == set()


def test_move1_lands_every_source_slot_membership(live):
    """0 -> N: each source (msa, slot) pair is in the target, by GUID."""
    src, remap, post1 = live["source"], live["remap1"], live["post1"]
    missing = []
    for msa, slots in src.items():
        tgt_msa = remap.get(msa, msa)
        if tgt_msa not in post1:
            missing.append((msa, "MSA absent"))
            continue
        for slot in slots:
            if slot not in post1[tgt_msa]:
                missing.append((msa, slot))
    assert not missing, "unlinked: %s" % missing[:10]
    # And nothing extra: each target MSA holds exactly the source's columns.
    for msa, slots in src.items():
        assert sorted(post1[remap.get(msa, msa)]) == sorted(slots), msa


def test_move1_report_is_all_linked(live):
    tally = _link_tally(live["report1"])
    assert tally == Counter({"LINKED": EXPECTED_SOURCE_WIRED_MSAS})
    slot_skips = [s for s in live["report1"].skips
                  if "slot_guid=" in (getattr(s, "detail", "") or "")]
    assert slot_skips == []


def test_move2_is_idempotent_on_slot_membership(live):
    src, remap = live["source"], live["remap1"]
    tgt_keys = [remap.get(m, m) for m in src]
    post1, post2 = live["post1"], live["post2"]
    assert _pairs(post2, tgt_keys) == _pairs(post1, tgt_keys)
    # Non-vacuous: "stable" must mean stable at N, not at 0.
    assert len(_pairs(post2, tgt_keys)) == EXPECTED_SOURCE_SLOT_REFS
    for key in tgt_keys:
        assert len(post2[key]) == len(set(post2[key])), "duplicate slot on %s" % key
        assert len(post2[key]) == len(post1[key]), key
    # Project-wide: no MSA's SlotsRC grew or shrank between the two moves.
    assert {k: len(v) for k, v in post2.items() if k in post1} == \
        {k: len(v) for k, v in post1.items()}
    assert _link_tally(live["report2"]) == Counter(
        {"LINKED": EXPECTED_SOURCE_WIRED_MSAS})


def test_source_is_unchanged(live):
    assert live["sha_after"] == live["sha_before"]
