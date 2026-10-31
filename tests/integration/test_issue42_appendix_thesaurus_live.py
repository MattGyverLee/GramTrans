"""Issue #42 live gate -- feature 030 sense appendix + thesaurus references,
proven end to end through a REAL transfer on a write-enabled fixture pair.

Why a constructed fixture: `LexSense.AppendixesRC` and
`LexSense.ThesaurusItemsRC` are populated in 0 of 79 on-disk projects, so no
real project can exercise the LINK arm (appendix by GUID) or the thesaurus
CREATE arm (missing item + missing ancestors).  This module BUILDS the fixture
itself, from a known backup, every run.

WRITE PATH: writes ONLY two private throwaway projects, both rebuilt from
``Target 2026-07-06 0218.fwbackup`` at the start of the module and restored
again at the end:

* ``GT-Src-42``     -- the SOURCE (opened write-enabled only while the fixture
                       is authored; the transfer opens it read-only).
* ``GT-Sandbox-42`` -- the TARGET.

Never ``Target``, ``Esperanto`` or any real project.

Fixture construction ("author-then-fork"):

1. Restore ``GT-Src-42``; author appendix A-PRESENT; close.
2. Copy the whole project dir to ``GT-Sandbox-42`` (renaming the .fwdata).  The
   sandbox therefore owns A-PRESENT under the SAME GUID by construction (an
   appendix cannot be created GUID-first through the interface-typed factory,
   and this keeps everything else identical too).
3. Reopen ``GT-Src-42`` and author: appendix A-ABSENT (source-only); in
   ``LexDb.DomainTypesOA`` (ItemClsid 7) a NEW top-level P with a NEW child C,
   plus a NEW child C2 under an EXISTING top item E; in
   ``LangProject.SemanticDomainListOA`` (ItemClsid 66, typed factory) a NEW
   child D under an EXISTING domain SDP; and entry 1:

   - sense s1: AppendixesRC [A-PRESENT, A-ABSENT], ThesaurusItemsRC [C]
   - sense s2: AppendixesRC [A-PRESENT], ThesaurusItemsRC [C, C2, E, D]

Scenario (STEMS only, so nothing else moves; STEMS transfers EVERY source
stem -- `Selection.stem_picks` does not filter it -- which is why entry 2 is
authored only after Move 1):

* Preview  -- writes nothing; its 030 drop set equals Move 1's, and (issue
  #116) its CREATE / LINK decisions on `PlannedAction.reference_decisions`
  equal the decisions Move 1's resolvers reach and the objects Move 1
  actually creates / links.
* Move 1   -- A-PRESENT linked, A-ABSENT dropped-and-reported (never created);
  P, C, C2, D created with source GUIDs, classes and hierarchy; E linked; the
  item C shared by s1 and s2 created exactly once.
* Author entry 2 in the source: sense s3, AppendixesRC [A-PRESENT],
  ThesaurusItemsRC [C, D] -- items Move 1 already created in the target.
* Move 2   -- entry 1 skipped; entry 2 created and its C and D LINK to the
  existing target items (list counts unchanged, no duplicates, no drops).
* Move 3   -- 0 actions; the sandbox .fwdata is identical, object by object,
  to the post-Move-2 snapshot.

This test FAILED on main (21e153e): the thesaurus CREATE arm created nothing
and reported nothing (see `references.apply_reference` -- pythonnet hides the
inherited 1-arg `Create(Guid)` behind the interface cast -- and the silent
`(AttributeError, TypeError)` swallow in `categories._call_apply_reference`).

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue42_appendix_thesaurus_live.py -v -s
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

SOURCE_NAME = "GT-Src-42"        # private fixture source (written only while authoring)
# Private fixture target. Overridable (issue #116) so concurrent work can use
# its own sandbox without touching GT-Sandbox-42.
TARGET_NAME = os.environ.get("GT42_TARGET_NAME", "GT-Sandbox-42")
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
TARGET_PATH = str(PROJECTS_ROOT / TARGET_NAME / ("%s.fwdata" % TARGET_NAME))
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

APPENDIX_PRESENT_TEXT = "Appendix 42-PRESENT: shared appendix linked by GUID in both projects"
APPENDIX_ABSENT_TEXT = "Appendix 42-ABSENT: only the source owns this one so it must drop"
_FIELDS = ("AppendixesRC", "ThesaurusItemsRC")


# --------------------------------------------------------------------------
# project plumbing
# --------------------------------------------------------------------------

def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            return d / BACKUP_NAME
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore(name):
    from harness.restore import restore_target
    restore_target(name, backup_path=_backup_path())


def _open(name, write=False):
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


# --------------------------------------------------------------------------
# fixture authoring (direct LCM writes on the PRIVATE source only)
# --------------------------------------------------------------------------

def _make_appendix(proj, text) -> str:
    from SIL.LCModel import (ILangProject, ILexDb, ILexAppendixFactory, IStTextFactory,
                             IStTxtParaFactory, IStText)
    from SIL.LCModel.Core.Text import TsStringUtils
    sl = proj.Cache.ServiceLocator
    lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
    ap = sl.GetService(ILexAppendixFactory).Create()
    lexdb.AppendixesOC.Add(ap)
    st = sl.GetService(IStTextFactory).Create()
    ap.ContentsOA = st
    para = sl.GetService(IStTxtParaFactory).Create()
    IStText(st).ParagraphsOS.Add(para)
    para.Contents = TsStringUtils.MakeString(text, proj.Cache.DefaultAnalWs)
    return _g(ap)


def _name(proj, item, name):
    from SIL.LCModel.Core.Text import TsStringUtils
    ws = proj.Cache.DefaultAnalWs
    item.Name.set_String(ws, TsStringUtils.MakeString(name, ws))
    item.Abbreviation.set_String(ws, TsStringUtils.MakeString(name[:8], ws))


def _author_shared_state() -> str:
    """Phase 1: restored source + appendix A-PRESENT; then fork to the sandbox."""
    _restore(SOURCE_NAME)
    proj = _open(SOURCE_NAME, write=True)
    try:
        present = _make_appendix(proj, APPENDIX_PRESENT_TEXT)
    finally:
        proj.CloseProject()
    tdir = PROJECTS_ROOT / TARGET_NAME
    if tdir.exists():
        shutil.rmtree(tdir)
    shutil.copytree(PROJECTS_ROOT / SOURCE_NAME, tdir,
                    ignore=shutil.ignore_patterns("*.lock"))
    (tdir / ("%s.fwdata" % SOURCE_NAME)).rename(tdir / ("%s.fwdata" % TARGET_NAME))
    return present


def _author_source_only_state(present: str) -> dict:
    """Phase 3: everything the sandbox must NOT have."""
    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList, ICmPossibility,
                             ICmPossibilityFactory, ICmSemanticDomainFactory,
                             ICmSemanticDomain, ILexSense)
    from System import Guid as DotNetGuid
    proj = _open(SOURCE_NAME, write=True)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        lexdb = ILexDb(lp.LexDbOA)
        sl = proj.Cache.ServiceLocator
        absent = _make_appendix(proj, APPENDIX_ABSENT_TEXT)

        # The owner-taking overloads are explicit interface members: cast.
        pf = ICmPossibilityFactory(sl.GetService(ICmPossibilityFactory))
        dom = ICmPossibilityList(lexdb.DomainTypesOA)
        p_new = pf.Create(DotNetGuid.NewGuid(), dom)
        _name(proj, p_new, "GT42 parent")
        c_new = pf.Create(DotNetGuid.NewGuid(), ICmPossibility(p_new))
        _name(proj, c_new, "GT42 child")
        e_old = ICmPossibility(dom.PossibilitiesOS[0])
        c2_new = pf.Create(DotNetGuid.NewGuid(), e_old)
        _name(proj, c2_new, "GT42 child of existing")

        sdf = ICmSemanticDomainFactory(sl.GetService(ICmSemanticDomainFactory))
        sd = ICmPossibilityList(lp.SemanticDomainListOA)
        sdp_old = ICmSemanticDomain(sd.PossibilitiesOS[0])
        d_new = sdf.Create(DotNetGuid.NewGuid(), sdp_old)
        _name(proj, d_new, "GT42 semdom child")

        aps = {_g(a): a for a in lexdb.AppendixesOC}
        e1 = proj.LexEntry.Create("gtfixfortytwo", create_blank_sense=False)
        s1 = ILexSense(proj.Senses.Create(e1, "first sense"))
        s2 = ILexSense(proj.Senses.Create(e1, "second sense"))
        s1.AppendixesRC.Add(aps[present])
        s1.AppendixesRC.Add(aps[absent])
        s2.AppendixesRC.Add(aps[present])
        s1.ThesaurusItemsRC.Add(c_new)
        for item in (c_new, c2_new, e_old, d_new):
            s2.ThesaurusItemsRC.Add(item)
        return dict(
            appendix_present=present, appendix_absent=absent,
            entry1=_g(e1), s1=_g(s1), s2=_g(s2),
            P=_g(p_new), C=_g(c_new), C2=_g(c2_new), E=_g(e_old),
            D=_g(d_new), SDP=_g(sdp_old),
            domtypes_list=_g(dom), semdom_list=_g(sd),
        )
    finally:
        proj.CloseProject()


def _author_second_entry(fx) -> None:
    """Phase 4 (after Move 1): a second source entry whose sense references
    items Move 1 already created in the target.  Authored only now because the
    STEMS category transfers EVERY source stem (`stem_picks` does not filter
    `enumerate_source`), so it must not exist before Move 1."""
    from SIL.LCModel import ILangProject, ILexDb, ILexSense
    from System import Guid
    proj = _open(SOURCE_NAME, write=True)
    try:
        repo = proj.Cache.ServiceLocator.ObjectRepository
        lexdb = ILexDb(ILangProject(proj.Cache.LangProject).LexDbOA)
        aps = {_g(a): a for a in lexdb.AppendixesOC}
        e2 = proj.LexEntry.Create("gtfixfortytwob", create_blank_sense=False)
        s3 = ILexSense(proj.Senses.Create(e2, "third sense"))
        s3.AppendixesRC.Add(aps[fx["appendix_present"]])
        for key in ("C", "D"):
            s3.ThesaurusItemsRC.Add(repo.GetObject(Guid.Parse(fx[key])))
        fx.update(entry2=_g(e2), s3=_g(s3))
    finally:
        proj.CloseProject()


# --------------------------------------------------------------------------
# independent read-only inspection of the sandbox
# --------------------------------------------------------------------------

def _count_items(lst) -> int:
    from SIL.LCModel import ICmPossibility
    n, stack = 0, list(lst.PossibilitiesOS)
    while stack:
        item = stack.pop()
        n += 1
        stack.extend(ICmPossibility(item).SubPossibilitiesOS)
    return n


def _sandbox_state(fx) -> dict:
    from SIL.LCModel import (ILangProject, ILexDb, ICmPossibilityList, ICmPossibility,
                             ICmObject, ILexSense)
    from System import Guid
    proj = _open(TARGET_NAME)
    try:
        lp = ILangProject(proj.Cache.LangProject)
        lexdb = ILexDb(lp.LexDbOA)
        repo = proj.Cache.ServiceLocator.ObjectRepository

        def get(guid):
            try:
                return repo.GetObject(Guid.Parse(guid))
            except Exception:  # noqa: BLE001 -- absent
                return None

        out = {
            "entries": int(proj.LexiconNumberOfEntries()),
            "appendixes": sorted(_g(a) for a in lexdb.AppendixesOC),
            "domtypes_total": _count_items(ICmPossibilityList(lexdb.DomainTypesOA)),
            "semdom_total": _count_items(ICmPossibilityList(lp.SemanticDomainListOA)),
        }
        for key in ("P", "C", "C2", "E", "D", "SDP"):
            obj = get(fx[key])
            if obj is None:
                out[key] = None
                continue
            pos = ICmPossibility(obj)
            parent = pos.OwningPossibility
            out[key] = {
                "class": str(obj.ClassName),
                "owner": _g(ICmObject(obj).Owner),
                "parent": _g(parent) if parent is not None else None,
                "name": pos.Name.BestAnalysisAlternative.Text,
            }
        for key in ("s1", "s2", "s3"):
            obj = get(fx[key]) if key in fx else None
            if obj is None:
                out[key] = None
                continue
            sense = ILexSense(obj)
            out[key] = {
                "appendixes": sorted(_g(a) for a in sense.AppendixesRC),
                "thesaurus": sorted(_g(t) for t in sense.ThesaurusItemsRC),
            }
        return out
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
            if cur and (line.startswith("</rt>") or line.rstrip().endswith("/>")
                        and line.startswith("<rt ")):
                out[cur[1]] = (cur[0], "".join(buf))
                cur = None
    return out


def _ref_drops(items):
    """The 030-field drop set, keyed so Preview and Move are comparable."""
    return sorted((d.owner_guid, d.field_name, d.item_guid, d.item_name, d.reason)
                  for d in items if d.field_name in _FIELDS)


def _plan_ref_decisions(plan):
    """The 030-field `ReferenceDecisionRecord`s a plan carries (issue #116)."""
    return [d for a in plan.actions
            for d in (getattr(a, "reference_decisions", ()) or ())
            if d.field_name in _FIELDS]


def _ref_rows(records):
    """Comparable rows, in walk order: (owner, field, action, item, ancestors)."""
    return [(d.owner_guid, d.field_name, d.action.value, d.item_guid,
             tuple(g for _n, g in d.new_ancestors)) for d in records]


def _first_decision_per_item(records):
    """{(field, item): (action, ancestors)} -- the FIRST decision reached for
    each referenced item, in walk order. This is the item-level decision: an
    item a run creates is created once, by its first reference."""
    out = {}
    for _owner, field, action, item, anc in _ref_rows(records):
        out.setdefault((field, item), (action, anc))
    return out


class _capture_move_decisions:
    """Wrap the two 030 resolvers for one Move and collect the records they
    return when called in Move mode (`new_sense` -- 2nd positional -- set).
    Move discards them; this only observes. Restores the originals on exit."""

    def __enter__(self):
        from gramtrans.Lib import categories as cats
        self._cats, self.rows = cats, []
        self._orig = {n: getattr(cats, n) for n in (
            "_resolve_sense_appendixes", "_resolve_sense_thesaurus_items")}

        def wrap(fn):
            def inner(*args, **kwargs):
                recs = fn(*args, **kwargs)
                if len(args) > 1 and args[1] is not None:
                    self.rows.extend(recs)
                return recs
            return inner

        for n, fn in self._orig.items():
            setattr(cats, n, wrap(fn))
        return self.rows

    def __exit__(self, *exc):
        for n, fn in self._orig.items():
            setattr(self._cats, n, fn)
        return False


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live():
    try:
        import flexicon  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        pytest.fail("[FAIL] FLEXLIBS_REQUIRE_LIVE=1 but flexicon is unavailable: %s" % exc)
    from harness import full_run
    from gramtrans.Lib.models import GrammarCategory as GC, Selection

    snapdir = tempfile.mkdtemp(prefix="gt42_")
    try:
        present = _author_shared_state()
        fx = _author_source_only_state(present)

        def stems_only(_full):
            return Selection(categories={GC.STEMS: True})

        def move():
            return full_run.run_full_transfer(
                SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
                selection_transform=stems_only)

        res = {"fx": fx, "pre": _sandbox_state(fx)}
        pre_bytes = Path(TARGET_PATH).read_bytes()
        res["preview_plan"], _ = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH, exclude=frozenset(),
            selection_transform=stems_only, preview_only=True)
        res["preview_wrote"] = Path(TARGET_PATH).read_bytes() != pre_bytes
        res["after_preview"] = _sandbox_state(fx)

        for i in (1, 2, 3):
            if i == 2:
                _author_second_entry(fx)
            # Issue #116: capture the decisions the Move-mode resolvers reach
            # (new_sense set), to compare with the plan's Preview decisions.
            with _capture_move_decisions() as move_rows:
                plan, report = move()
            res["move%d_decisions" % i] = list(move_rows)
            snap = os.path.join(snapdir, "move%d.fwdata" % i)
            shutil.copyfile(TARGET_PATH, snap)
            res["move%d" % i] = {"plan": plan, "report": report,
                                 "state": _sandbox_state(fx),
                                 "objects": _load_objects(snap)}
            print("[LIVE] move%d actions=%d drops=%s" % (
                i, len(plan.actions), _ref_drops(report.dropped_items)))
        import gramtrans
        import flexicon
        print("[LIVE] gramtrans=%s" % gramtrans.__file__)
        print("[LIVE] flexicon=%s" % flexicon.__file__)
        print("[LIVE] source=%s target=%s" % (SOURCE_NAME, TARGET_NAME))
        print("[LIVE] preview 030 decisions=%s" % _ref_rows(
            _plan_ref_decisions(res["preview_plan"])))
        print("[LIVE] move1 030 decisions=%s" % _ref_rows(res["move1_decisions"]))
        print("[LIVE] fixture=%s" % fx)
        yield res
    finally:
        shutil.rmtree(snapdir, ignore_errors=True)
        for name in (TARGET_NAME, SOURCE_NAME):
            try:
                _restore(name)
            except Exception as exc:  # noqa: BLE001
                print("[WARN] restore of %s failed: %s" % (name, exc))


# --------------------------------------------------------------------------
# assertions
# --------------------------------------------------------------------------

def test_fixture_preconditions(live):
    fx, pre = live["fx"], live["pre"]
    assert pre["appendixes"] == [fx["appendix_present"]], "sandbox must own A-PRESENT only"
    assert pre["entries"] == 0
    for key in ("P", "C", "C2", "D"):
        assert pre[key] is None, "%s must be absent from the sandbox before Move" % key
    assert pre["E"] is not None and pre["SDP"] is not None


def test_preview_writes_nothing_and_drops_match_move(live):
    assert not live["preview_wrote"], "Preview modified the target .fwdata"
    assert live["after_preview"] == live["pre"]
    preview = _ref_drops(live["preview_plan"].dropped_items)
    move1 = _ref_drops(live["move1"]["report"].dropped_items)
    assert preview == move1, "Preview drop set != Move drop set (FR-008)"


def test_preview_create_link_decisions_match_move(live):
    """Issue #116: Preview lists the CREATE / LINK decisions, not just drops,
    and they are the decisions Move reaches and the objects Move writes."""
    fx, pre, st = live["fx"], live["pre"], live["move1"]["state"]
    P, C, C2, E, D = (fx[k] for k in ("P", "C", "C2", "E", "D"))
    present, absent = fx["appendix_present"], fx["appendix_absent"]
    s1, s2 = fx["s1"], fx["s2"]
    TH, AP = "ThesaurusItemsRC", "AppendixesRC"

    preview = _ref_rows(_plan_ref_decisions(live["preview_plan"]))
    move = _ref_rows(live["move1_decisions"])
    assert preview, "Preview recorded no 030 decisions (issue #116 regression)"

    # 1. The rows the issue asks Preview to show, exactly.
    assert sorted(preview) == sorted([
        (s1, AP, "link", present, ()),
        (s1, AP, "report_dropped", absent, ()),
        (s1, TH, "create", C, (P,)),          # new child under a NEW parent P
        (s2, AP, "link", present, ()),
        (s2, TH, "create", C, (P,)),          # shared C: see 3 below
        (s2, TH, "create", C2, ()),           # new child under EXISTING E
        (s2, TH, "link", E, ()),
        (s2, TH, "create", D, ()),            # new semantic domain under SDP
    ]), preview

    # 2. Item level, Preview == Move: every referenced item gets the same
    #    first decision (and the same set of ancestors to create).
    assert _first_decision_per_item(_plan_ref_decisions(live["preview_plan"])) \
        == _first_decision_per_item(live["move1_decisions"])

    # 3. Row level, Preview == Move, except the one documented cache
    #    divergence: Move's resolver cache turns a SECOND reference to an item
    #    Move created earlier in the run into a LINK; Preview never writes, so
    #    it reports that reference as the same CREATE (one item either way).
    assert [r[:2] + r[3:4] for r in preview] == [r[:2] + r[3:4] for r in move], \
        "Preview and Move decided different (owner, field, item) sets"
    created_by_move = {r[3] for r in move if r[2] == "create"}
    diverged = [(p, m) for p, m in zip(preview, move) if p != m]
    assert all(p[2] == "create" and m[2] == "link" and m[3] in created_by_move
               for p, m in diverged), diverged
    assert [(p[0], p[3]) for p, _m in diverged] == [(s2, C)], diverged

    # 4. Ground truth: Preview's CREATE items + their new ancestors are
    #    exactly the objects Move 1 brought into existence; its LINK items
    #    existed before Move and are what the senses now reference.
    preview_creates = {r[3] for r in preview if r[2] == "create"} | {
        a for r in preview if r[2] == "create" for a in r[4]}
    assert preview_creates == {P, C, C2, D}
    key = {P: "P", C: "C", C2: "C2", E: "E", D: "D"}
    assert all(pre[key[g]] is None and st[key[g]] is not None for g in preview_creates)
    assert pre["E"] is not None and E in st["s2"]["thesaurus"]
    assert present in pre["appendixes"] and st["s1"]["appendixes"] == [present]

    # 5. Move 2: its plan's Preview decisions equal the decisions its
    #    resolvers reach, row for row (no shared CREATE in this run). s3's
    #    references are to items Move 1 created: nothing is created again and
    #    nothing drops. (They decide UPDATE, not LINK -- a pre-existing CREATE
    #    fidelity defect this Preview now makes visible; see the strict xfail
    #    `test_items_created_by_move1_link_on_the_next_run`.)
    s3 = fx["s3"]
    preview2 = [r for r in _ref_rows(_plan_ref_decisions(live["move2"]["plan"]))
                if r[0] == s3]
    move2 = [r for r in _ref_rows(live["move2_decisions"]) if r[0] == s3]
    assert preview2 == move2, (preview2, move2)
    assert (s3, AP, "link", present, ()) in preview2
    s3_th = {r[3]: r[2] for r in preview2 if r[1] == TH}
    assert set(s3_th) == {C, D}
    assert not {a for a in s3_th.values()} & {"create", "report_dropped"}, s3_th


@pytest.mark.xfail(strict=True, reason=(
    "pre-existing, found by the #116 live proof: references.apply_reference's "
    "CREATE arm passes an empty source Description as a plain '' that "
    "ApplySyncableProperties rejects (TypeError: property is read-only, "
    "swallowed), and the next run decides UPDATE for items this run created. "
    "See specs/_reviews/batch-107-108-110-111-114-116/impl-116.md section 6."))
def test_items_created_by_move1_link_on_the_next_run(live):
    """An item a run created from the source must be identical to the source,
    so a later run that references it again decides LINK, not UPDATE."""
    fx = live["fx"]
    s3_th = {r[3]: r[2] for r in _ref_rows(_plan_ref_decisions(live["move2"]["plan"]))
             if r[0] == fx["s3"] and r[1] == "ThesaurusItemsRC"}
    assert s3_th == {fx["C"]: "link", fx["D"]: "link"}, s3_th


def test_preview_pane_renders_create_and_link_rows(live):
    """Issue #116: the Preview pane's extra lines carry the decisions."""
    from gramtrans.Lib.preview import render_preview_extra_lines
    fx = live["fx"]
    text = "\n".join(render_preview_extra_lines(live["preview_plan"]))
    print("[LIVE] preview pane 030 lines:\n" + text)
    assert "Sense appendix / thesaurus references:" in text
    assert ("Create  ThesaurusItemsRC 'GT42 child' {%s}  (2 senses) -- also "
            "creates ancestor(s) 'GT42 parent' {%s}" % (fx["C"], fx["P"])) in text
    assert "Create  ThesaurusItemsRC 'GT42 child of existing' {%s}" % fx["C2"] in text
    assert "Create  ThesaurusItemsRC 'GT42 semdom child' {%s}" % fx["D"] in text
    assert "Link  ThesaurusItemsRC" in text and "{%s}" % fx["E"] in text
    assert ("Link  AppendixesRC 'Appendix 42-PRESENT" in text
            and "{%s}  (2 senses)" % fx["appendix_present"] in text)
    assert "Not transferred  AppendixesRC 'Appendix 42-ABSENT" in text


def test_appendix_link_arm_and_absent_drop(live):
    fx, st = live["fx"], live["move1"]["state"]
    present, absent = fx["appendix_present"], fx["appendix_absent"]
    # A-PRESENT linked by GUID onto both copied senses.
    assert st["s1"]["appendixes"] == [present]
    assert st["s2"]["appendixes"] == [present]
    # A-ABSENT never created, never linked.
    assert st["appendixes"] == [present], "an appendix was created in the target"
    drops = [d for d in live["move1"]["report"].dropped_items
             if d.field_name == "AppendixesRC"]
    assert len(drops) == 1, drops
    d = drops[0]
    assert d.item_guid == absent and d.owner_guid == fx["s1"]
    assert d.item_name.startswith("Appendix 42-ABSENT")       # #42c label, not a bare GUID
    assert "not created" in d.reason and "UNKNOWN" not in d.reason


def test_thesaurus_create_arm_with_ancestors(live):
    fx, pre, st = live["fx"], live["pre"], live["move1"]["state"]
    # Zero thesaurus drops -- every reference reproduced.
    assert not [d for d in live["move1"]["report"].dropped_items
                if d.field_name == "ThesaurusItemsRC"]
    # New top-level P + child C (ancestor created first), GUIDs preserved.
    assert st["P"] == {"class": "CmPossibility", "owner": fx["domtypes_list"],
                       "parent": None, "name": "GT42 parent"}
    assert st["C"] == {"class": "CmPossibility", "owner": fx["P"],
                       "parent": fx["P"], "name": "GT42 child"}
    # New child under an EXISTING ancestor (existing ancestor reused, not duplicated).
    assert st["C2"] == {"class": "CmPossibility", "owner": fx["E"],
                        "parent": fx["E"], "name": "GT42 child of existing"}
    # Typed list (ItemClsid 66) -> typed class, under the existing domain.
    assert st["D"] == {"class": "CmSemanticDomain", "owner": fx["SDP"],
                       "parent": fx["SDP"], "name": "GT42 semdom child"}
    assert st["domtypes_total"] == pre["domtypes_total"] + 3     # P, C, C2 -- C once
    assert st["semdom_total"] == pre["semdom_total"] + 1         # D
    assert st["s1"]["thesaurus"] == [fx["C"]]
    assert st["s2"]["thesaurus"] == sorted([fx["C"], fx["C2"], fx["E"], fx["D"]])


def test_second_entry_links_existing_items_without_duplicates(live):
    fx, m1, m2 = live["fx"], live["move1"]["state"], live["move2"]["state"]
    assert m2["entries"] == 2
    assert m2["s3"]["thesaurus"] == sorted([fx["C"], fx["D"]])
    assert m2["s3"]["appendixes"] == [fx["appendix_present"]]
    assert m2["domtypes_total"] == m1["domtypes_total"]
    assert m2["semdom_total"] == m1["semdom_total"]
    assert m2["appendixes"] == m1["appendixes"]
    assert not _ref_drops(live["move2"]["report"].dropped_items)


def test_rerun_is_idempotent_zero_writes(live):
    assert len(live["move3"]["plan"].actions) == 0, "re-run planned actions"
    assert live["move3"]["state"] == live["move2"]["state"]
    before, after = live["move2"]["objects"], live["move3"]["objects"]
    assert set(after) == set(before), "re-run added/removed objects"
    changed = [(before[g][0], g) for g in before if before[g][1] != after[g][1]]
    assert not changed, "re-run changed objects: %s" % changed[:20]
