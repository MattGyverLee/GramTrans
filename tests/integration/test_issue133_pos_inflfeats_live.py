"""Issue #133 live gate -- POS `InflectableFeatsRC` has ONE writer and ONE
count, so Preview's "Link" rows equal Move's confirmed writes when the POS
already exists, and a 0-action run still links.

WRITE PATH: writes ONLY the private sandbox ``GT-Sandbox-133`` (restored
headlessly from a known backup before every test and again at the end). The
source ``Mbugwe LizzieHC practice`` is opened READ-ONLY. ``Target``,
``Esperanto``, ``Ejagham Mini`` and every other project are never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1. When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue133_pos_inflfeats_live.py -v -s

Source facts (read-only probe of ``Mbugwe LizzieHC practice``, 2026-10-31):
7 parts of speech carry a populated ``InflectableFeatsRC`` -- 14 POS->feature
pairs in total.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe LizzieHC practice"        # READ-ONLY
TARGET_NAME = "GT-Sandbox-133"                  # the ONLY project this module writes
TARGET_PATH = ("C:/ProgramData/SIL/FieldWorks/Projects/GT-Sandbox-133/"
               "GT-Sandbox-133.fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (
    _REPO / "backups",
    Path("D:/Github/_Projects/_LEX/GramTrans/backups"),
)

#: how many pairs the test deletes from the sandbox to make some "missing".
N_REMOVE = 5


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        p = d / BACKUP_NAME
        if p.is_file():
            return p
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore() -> None:
    assert TARGET_NAME == "GT-Sandbox-133"
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


@pytest.fixture(autouse=True)
def _restore_around():
    import flexicon
    import gramtrans
    print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
    _restore()
    yield
    _restore()


def _sel(*cats):
    from gramtrans.Lib.models import GrammarCategory, Selection

    def _transform(_full):
        return Selection(categories={getattr(GrammarCategory, c): True for c in cats})
    return _transform


#: run 1 seeds POS + features; later runs select ONLY the POS (the features
#: already exist in the target by GUID -- the #133 "deferral" case).
SEL_SEED = _sel("GRAM_CATEGORIES", "INFLECTION_FEATURES")
SEL_POS_ONLY = _sel("GRAM_CATEGORIES")


def _open(path_name: str, write: bool):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    if write:
        assert path_name == "GT-Sandbox-133"   # pin BEFORE any write
        proj.OpenProject(projectName=path_name, writeEnabled=True, undoable=False)
    else:
        proj.OpenProject(projectName=path_name, writeEnabled=False)
    return proj


def _pairs(project_name: str, only_pos=None) -> set:
    """{(pos guid, feature guid)} over every POS' InflectableFeatsRC, via a
    fresh read-only open."""
    from SIL.LCModel import ICmObject, IPartOfSpeech
    proj = _open(project_name, write=False)
    try:
        out = set()
        for pos in proj.POS.GetAll(recursive=True):
            c = IPartOfSpeech(pos.concrete if hasattr(pos, "concrete") else pos)
            pg = str(ICmObject(c).Guid).lower()
            if only_pos is not None and pg not in only_pos:
                continue
            for f in c.InflectableFeatsRC:
                out.add((pg, str(ICmObject(f).Guid).lower()))
        return out
    finally:
        proj.CloseProject()


def _remove_pairs(pairs) -> None:
    """Sandbox-only fixture: unlink `pairs` from InflectableFeatsRC."""
    from SIL.LCModel import ICmObject, IPartOfSpeech
    proj = _open(TARGET_NAME, write=True)
    try:
        assert proj.ProjectName() == TARGET_NAME
        want = set(pairs)
        for pos in proj.POS.GetAll(recursive=True):
            c = IPartOfSpeech(pos.concrete if hasattr(pos, "concrete") else pos)
            pg = str(ICmObject(c).Guid).lower()
            for f in list(c.InflectableFeatsRC):
                if (pg, str(ICmObject(f).Guid).lower()) in want:
                    c.InflectableFeatsRC.Remove(f)
    finally:
        proj.CloseProject()


def _run(selection_transform, monkeypatch):
    """One Move into the sandbox. Returns (plan, report, link_rows,
    skip_rows, reported_writes, pass_calls). `reported_writes` is the link
    pass's own counter (`_infl_feature_link_writes`) as Move left it."""
    from harness import full_run
    from gramtrans.Lib import categories, preview
    rows: list = []
    reported: list = []
    real_execute = full_run.api.execute_move

    def _capture_preview(context, plan, *a, **k):
        # Render against the still-unwritten target: exactly what Preview shows.
        rows.extend(preview.render_feature_category_links(plan))
        return real_execute(context, plan, *a, **k)

    real_pass = categories._run_infl_feature_link_pass

    def _capture_count(context, target, tag=None):
        skips = real_pass(context, target, tag)
        reported.append(getattr(context, "_infl_feature_link_writes", None))
        return skips

    monkeypatch.setattr(full_run.api, "execute_move", _capture_preview)
    monkeypatch.setattr(categories, "_run_infl_feature_link_pass", _capture_count)
    try:
        plan, report = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH,
            selection_transform=selection_transform)
    finally:
        monkeypatch.setattr(full_run.api, "execute_move", real_execute)
        monkeypatch.setattr(categories, "_run_infl_feature_link_pass", real_pass)
    link_rows = [r for r in rows if r.strip().startswith("Link ")]
    skip_rows = [r for r in rows if "SKIP (already linked)" in r]
    return plan, report, link_rows, skip_rows, reported, len(reported)


def test_preview_link_rows_equal_move_writes_and_zero_action_run_links(monkeypatch):
    # ---- 1. get POS + features into the sandbox ---------------------------
    src_pairs = _pairs(SOURCE_NAME)
    print("[LIVE] source pairs=%d over %d POS"
          % (len(src_pairs), len({p for p, _ in src_pairs})))
    assert len(src_pairs) >= N_REMOVE + 1, "[SETUP] source has too few pairs"
    assert _pairs(TARGET_NAME, only_pos={p for p, _ in src_pairs}) == set() \
        or True   # the starter may already hold some catalog POS; not asserted

    plan1, report1, links1, skips1, writes1, calls1 = _run(SEL_SEED, monkeypatch)
    after1 = _pairs(TARGET_NAME)
    in_scope = {p for p, _ in src_pairs}
    got1 = {pf for pf in after1 if pf[0] in in_scope}
    print("[LIVE] run1: actions=%d link_rows=%d reported_writes=%s pass_calls=%d "
          "sandbox pairs=%d" % (len(plan1.actions), len(links1), writes1[0],
                                calls1, len(got1)))
    assert calls1 == 1
    assert src_pairs <= got1, "[FAIL] seed run did not link every source pair"
    assert writes1[0] == len(links1), "[FAIL] run 1: Link rows != writes"

    # ---- make some pairs missing in the sandbox ---------------------------
    removed = set(sorted(src_pairs)[:N_REMOVE])
    _remove_pairs(removed)
    mid = _pairs(TARGET_NAME)
    assert not (removed & mid), "[SETUP] pairs were not removed"
    assert len(src_pairs - mid) == N_REMOVE

    # ---- 2/3. Preview then Move; POS exist, features exist, 0 new objects -
    plan2, report2, links2, skips2, writes2, calls2 = _run(SEL_POS_ONLY, monkeypatch)
    after2 = _pairs(TARGET_NAME)
    print("[LIVE] run2: plan.actions=%d link_rows=%d skip_rows=%d "
          "reported_writes=%s pass_calls=%d" % (len(plan2.actions), len(links2),
                                                len(skips2), writes2[0], calls2))
    print("\n".join(["[LIVE] preview run2:"] + links2[:N_REMOVE + 1]))
    assert calls2 == 1, "[FAIL] the link pass did not run exactly once"
    # ---- 4. equal, and match the source pairs -----------------------------
    assert len(links2) == writes2[0] == N_REMOVE, (
        "[FAIL] Preview Link rows %d != Move writes %s (expected %d)"
        % (len(links2), writes2[0], N_REMOVE))
    assert len(skips2) == len(src_pairs) - N_REMOVE
    assert src_pairs <= {pf for pf in after2 if pf[0] in in_scope}
    assert removed <= after2                    # read-back: really relinked
    assert not any("InflectableFeatsRC" == d.field_name
                   for d in report2.dropped_items), "[FAIL] unexpected drop"

    # ---- 5. 0-action re-run: nothing to write, nothing written ------------
    plan3, report3, links3, skips3, writes3, calls3 = _run(SEL_POS_ONLY, monkeypatch)
    print("[LIVE] run3: plan.actions=%d link_rows=%d reported_writes=%s "
          "pass_calls=%d" % (len(plan3.actions), len(links3), writes3[0], calls3))
    assert calls3 == 1
    assert len(links3) == 0 and writes3[0] == 0
    assert _pairs(TARGET_NAME) == after2


def test_zero_action_run_links_a_missing_pair(monkeypatch):
    """The run that plans NO action must still link: seed everything, remove
    ONE pair, re-run -- POS and features already present, so plan.actions has
    no POS/feature create, yet the pair is linked and counted exactly once."""
    src_pairs = _pairs(SOURCE_NAME)
    _run(SEL_SEED, monkeypatch)
    victim = sorted(src_pairs)[0]
    _remove_pairs({victim})
    assert victim not in _pairs(TARGET_NAME)

    plan, report, links, _skips, writes, calls = _run(SEL_POS_ONLY, monkeypatch)
    created = [a for a in plan.actions
               if a.category.value in ("gram_categories", "pos",
                                       "inflection_features")]
    print("[LIVE] 0-action: plan.actions=%d (POS/feature creates=%d) link_rows=%d "
          "reported_writes=%s" % (len(plan.actions), len(created), len(links),
                                  writes[0]))
    assert created == [], "[SETUP] POS/features were planned again"
    assert calls == 1
    assert len(links) == writes[0] == 1
    assert victim in _pairs(TARGET_NAME)
