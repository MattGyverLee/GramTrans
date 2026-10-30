"""Issue #45 live gate -- untitled source texts transfer without collision.

WRITE PATH: writes ONLY the throwaway project ``Target`` (restored headlessly
from a known backup before and after).  The source ``Mbugwe Lizzie`` is opened
READ-ONLY.  ``Esperanto`` is never touched.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue45_untitled_texts_live.py -v -s

Asserts: each untitled text lands in Target under its own SOURCE GUID; the new
text count equals the number transferred (no collisions); a SECOND identical
run adds 0 and does not rename the target texts.  Prints the exact Name the
target texts receive.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe Lizzie"          # READ-ONLY
TARGET_NAME = "Target"                 # the ONLY project this module writes
TARGET_PATH = "C:/ProgramData/SIL/FieldWorks/Projects/Target/Target.fwdata"
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"
N_TRANSFER = 3

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))


def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(TARGET_NAME, backup_path=d / BACKUP_NAME)
            return
    pytest.fail("[FAIL] backup %r not found" % BACKUP_NAME)


def _sha() -> str:
    return hashlib.sha256(Path(TARGET_PATH).read_bytes()).hexdigest()


def _snapshot(tag):
    """Optional: copy Target.fwdata to $GT_SNAP_DIR/<tag>.fwdata for diffing."""
    d = os.environ.get("GT_SNAP_DIR")
    if d:
        import shutil
        Path(d).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TARGET_PATH, str(Path(d) / (tag + ".fwdata")))


def _open(name):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


def _guid(obj) -> str:
    from SIL.LCModel import ICmObject
    return str(ICmObject(obj.concrete if hasattr(obj, "concrete") else obj).Guid).lower()


def _untitled_source_guids():
    """GUIDs of source texts untitled in the best analysis WS (read-only)."""
    from gramtrans.Lib.selection import _text_title
    proj = _open(SOURCE_NAME)
    try:
        texts = list(proj.Texts.GetAll())
        un = [_guid(t) for t in texts if _text_title(t) == "(untitled text)"]
        print("[LIVE] source %r: %d texts, %d untitled" % (SOURCE_NAME, len(texts), len(un)))
        return un
    finally:
        proj.CloseProject()


def _target_texts():
    """{guid: (name, n_paragraphs)} for every text in Target (read-only)."""
    from SIL.LCModel import IText
    proj = _open(TARGET_NAME)
    try:
        out = {}
        for t in proj.Texts.GetAll():
            tc = IText(t.concrete if hasattr(t, "concrete") else t)
            try:
                name = tc.Name.BestAnalysisAlternative.Text or ""
            except Exception:
                name = ""
            try:
                npara = tc.ContentsOA.ParagraphsOS.Count
            except Exception:
                npara = -1
            out[_guid(t)] = (name, npara)
        return out
    finally:
        proj.CloseProject()


@pytest.fixture(autouse=True)
def _restore_around():
    _restore()
    yield
    _restore()


def _run(picks):
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    def _sel(_full):
        return Selection(categories={GC.TEXTS: True}, text_picks=frozenset(picks),
                         include_closure=True)

    return full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH, selection_transform=_sel)


def test_untitled_texts_transfer_without_collision_and_idempotent():
    from gramtrans.Lib.models import GrammarCategory as GC

    untitled = _untitled_source_guids()
    if not untitled:
        pytest.fail("[SETUP] %r has no untitled texts" % SOURCE_NAME)
    assert len(untitled) >= 2, "need at least two untitled texts"
    picks = untitled[:N_TRANSFER]

    h0 = _sha()
    before = _target_texts()
    _plan1, rep1 = _run(picks)
    h1 = _sha()
    _snapshot("run1")
    after1 = _target_texts()
    new1 = set(after1) - set(before)
    print("[LIVE] sha256 before=%s after-run1=%s" % (h0, h1))
    print("[LIVE] run1 added=%s target new texts=%d (transferred %d)" % (
        getattr(rep1.per_category.get(GC.TEXTS), "added", None), len(new1), len(picks)))
    for g in sorted(picks):
        print("[LIVE]   %s -> %r paragraphs=%s" % (g, after1.get(g, ("<ABSENT>",))[0],
                                                   after1.get(g, (None, None))[1]))

    assert h1 != h0, "target unchanged by run 1"
    assert set(picks) <= set(after1), "untitled text(s) not under source GUID: %s" % (
        sorted(set(picks) - set(after1)))
    assert new1 == set(picks), "new texts != transferred set (collision/extra): %s" % (
        sorted(new1 ^ set(picks)))
    assert len(new1) == len(picks)
    names = [after1[g][0] for g in picks]
    assert len(set(names)) == len(names), "target names collide: %r" % names
    # Placeholder name: fixed label + first 8 hex of the source GUID (Texts.Create
    # needs a unique non-empty name); never the full 36-char GUID.
    for g in picks:
        assert after1[g][0] == "(untitled text) " + g.replace("-", "")[:8], (
            "unexpected placeholder name for %s: %r" % (g, after1[g][0]))
        assert g not in after1[g][0]
    # Report truthfulness (#45-b): per_category[TEXTS] counts the real adds.
    assert getattr(rep1.per_category.get(GC.TEXTS), "added", None) == len(picks), (
        "report.per_category[TEXTS].added != transferred texts: %r" % (
            rep1.per_category.get(GC.TEXTS),))

    # No paragraph interleaving: each target text's paragraph count equals the
    # source text's own count (read-only).
    from SIL.LCModel import IText
    src = _open(SOURCE_NAME)
    try:
        src_np = {}
        for t in src.Texts.GetAll():
            g = _guid(t)
            if g in picks:
                tc = IText(t.concrete if hasattr(t, "concrete") else t)
                src_np[g] = tc.ContentsOA.ParagraphsOS.Count
    finally:
        src.CloseProject()
    for g in picks:
        print("[LIVE]   paragraphs source=%s target=%s" % (src_np[g], after1[g][1]))
        assert after1[g][1] == src_np[g], "paragraph count differs for %s" % g

    # SECOND run: adds 0, names untouched.
    _plan2, rep2 = _run(picks)
    h2 = _sha()
    _snapshot("run2")
    after2 = _target_texts()
    print("[LIVE] sha256 after-run2=%s" % h2)
    print("[LIVE] run2 added=%s target total %d -> %d; names run1=%r run2=%r" % (
        getattr(rep2.per_category.get(GC.TEXTS), "added", None),
        len(after1), len(after2), names, [after2[g][0] for g in picks]))
    assert len(after2) == len(after1), "second run created texts"
    assert (getattr(rep2.per_category.get(GC.TEXTS), "added", 0) or 0) == 0
    assert [after2[g][0] for g in picks] == names, "second run renamed target texts"
    assert [after2[g][1] for g in picks] == [after1[g][1] for g in picks]
    # Issue #87: run 2 must not re-stamp already-present texts with its own
    # residue tag -- the Target file is byte-identical after the re-run.
    assert h2 == h1, "run 2 modified Target (residue re-stamp?): %s != %s" % (h2, h1)
