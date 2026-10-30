"""Issue #87: the residue tagger must not re-stamp objects already present.

A re-run that matches existing objects writes nothing; a freshly created
object is stamped exactly once.
"""
from __future__ import annotations

from gramtrans.Lib import texts
from gramtrans.Lib import residue as _residue
from gramtrans.Lib.residue import ImportResidueTag, apply_carrier_b
from gramtrans.Lib.models import Selection, GrammarCategory
from _fakes_texts import (
    FakeWS, FakeEvaluation, FakeAnalysis, FakeWordform, FakeText,
    FakeParagraph, FakeSegment, FakeProject, FakeLangProject, FakeCtx,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _source():
    wf = FakeWordform(guid="wf-1", form_by_handle={2: "dogs"},
                      analyses=[FakeAnalysis("an-1", human_eval=FakeEvaluation(approves=True))])
    seg = FakeSegment(guid="seg-1", baseline=" dogs .", free={2: "the dogs"}, wordforms=(wf,))
    para = FakeParagraph(guid="para-1", text_by_handle={1: "dogs."}, segments=(seg,))
    return FakeProject(ws_list=[WS_VERN, WS_EN],
                       texts=[FakeText(guid="txt-1", name="Story One", paragraphs=(para,))])


class _Sink:
    def Info(self, m):
        pass


def _run(source, target, monkeypatch, calls):
    monkeypatch.setattr(
        _residue, "apply_residue",
        lambda obj, ws, tag, class_name=None: calls.append(class_name))
    ctx = FakeCtx(source_handle=source, ws_map={})
    d = []
    sel = Selection(categories={GrammarCategory.TEXTS: True},
                    text_picks=frozenset({"txt-1"}))
    plans = texts.plan_texts(sel, source, target, ctx, {}, d)
    texts.apply_texts(plans, source, target, ctx, tag=object(),
                      report_sink=_Sink(), resolver_cache={}, dropped=d)


def test_rerun_on_present_text_writes_no_residue(monkeypatch):
    source = _source()
    target = FakeProject(ws_list=[WS_VERN, WS_EN], lang_project=FakeLangProject())
    run1, run2 = [], []
    _run(source, target, monkeypatch, run1)
    assert run1.count("Text") == 1          # created: stamped exactly once
    assert run1.count("StTxtPara") == 1
    _run(source, target, monkeypatch, run2)
    assert run2 == []                        # matched + already reproduced: no writes


def test_carrier_b_same_run_is_not_stamped_twice():
    class _MS:
        def __init__(self): self.t = ""
        def get_String(self, ws): return self
        @property
        def Text(self): return self.t
        def set_String(self, ws, v): self.t = v

    class _Obj:
        Description = _MS()

    tag = ImportResidueTag.make("GT-20260101-000000", "Src", "2026-01-01T00:00:00")
    o = _Obj()
    apply_carrier_b(o, 1, tag)
    first = o.Description.t
    apply_carrier_b(o, 1, tag)
    assert o.Description.t == first
    assert first.count("[GT-Tag]: ") == 1
    # A DIFFERENT run on an updated object appends its own line (history).
    tag2 = ImportResidueTag.make("GT-20260102-000000", "Src", "2026-01-02T00:00:00")
    apply_carrier_b(o, 1, tag2)
    assert o.Description.t.count("[GT-Tag]: ") == 2


# ---------------------------------------------------------------------------
# Cycle 3: matched text stamping counts CREATED paragraphs (QC P2)
# ---------------------------------------------------------------------------

def test_matched_empty_text_gaining_paragraphs_is_stamped_once(monkeypatch):
    source = _source()
    empty = FakeText(guid="txt-1", name="Story One", paragraphs=())
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[empty],
                         lang_project=FakeLangProject())
    run1, run2 = [], []
    _run(source, target, monkeypatch, run1)
    assert run1.count("Text") == 1           # matched, but gained a paragraph
    assert run1.count("StTxtPara") == 1
    _run(source, target, monkeypatch, run2)
    assert run2 == []                         # now populated: no second stamp


def test_matched_text_whose_paragraph_creates_all_fail_is_not_stamped(monkeypatch):
    source = _source()
    empty = FakeText(guid="txt-1", name="Story One", paragraphs=())
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[empty],
                         lang_project=FakeLangProject())

    def _boom(*a, **k):
        raise RuntimeError("create failed")
    target.Paragraphs.Create = _boom
    calls = []
    _run(source, target, monkeypatch, calls)
    assert "Text" not in calls               # nothing written -> not stamped
    assert "StTxtPara" not in calls


# ---------------------------------------------------------------------------
# Cycle 3: residue-aware comparison helpers
# ---------------------------------------------------------------------------
from gramtrans.Lib.residue import (  # noqa: E402
    strip_residue_text, strip_residue_props, residue_lines,
    restore_residue_history,
)
from gramtrans.Lib import categories as _cats  # noqa: E402
from gramtrans.Lib.conflict import compute_disposition  # noqa: E402
from gramtrans.Lib.models import ConflictMode  # noqa: E402
from gramtrans.Lib.conflict import ItemDisposition  # noqa: E402

_T1 = "[GT-Tag]: GT|GT-20260101-000000|Src|2026-01-01T00:00:00"
_T2 = "[GT-Tag]: GT|GT-20260102-000000|Src|2026-01-02T00:00:00|snap=QUJD"


def test_strip_removes_tag_and_blank_separator():
    assert strip_residue_text(f"hello\n\n{_T1}") == "hello"
    assert strip_residue_text(f"hello\n\n{_T1}\n\n{_T2}") == "hello"
    assert strip_residue_text(_T1) == ""          # tag-only -> empty


def test_strip_keeps_text_without_residue_byte_identical():
    assert strip_residue_text("plain\n") == "plain\n"
    assert strip_residue_text("") == ""
    assert strip_residue_text(None) == ""


def test_strip_is_line_start_only():
    mid = "see the [GT-Tag]: GT|x|y note in the docs"
    assert strip_residue_text(mid) == mid
    both = f"{mid}\n\n{_T1}"
    assert strip_residue_text(both) == mid
    # marker indented / not at line start is user text
    assert strip_residue_text(f"a\n x {_T1}") == f"a\n x {_T1}"


def test_residue_lines_line_start_only():
    assert residue_lines(f"x\n\n{_T1}\n\n{_T2}") == [_T1, _T2]
    assert residue_lines("mentions [GT-Tag]: mid-line") == []


def test_strip_props_multi_ws_and_drops_tag_only_alternatives():
    props = {"Name": {"en": "N"},
             "Description": {"en": f"d\n\n{_T1}", "fr": _T1, "de": "keep"}}
    out = strip_residue_props(props)
    assert out["Description"] == {"en": "d", "de": "keep"}
    assert out["Name"] == {"en": "N"}
    assert props["Description"]["fr"] == _T1      # input not mutated


def test_strip_props_without_residue_is_same_object():
    props = {"Description": {"en": "d"}}
    assert strip_residue_props(props) is props
    assert strip_residue_props(None) is None


def test_identical_except_tag_is_skip_not_update():
    src = {"Name": {"en": "Verb"}, "Description": {"en": "d"}}
    tgt = {"Name": {"en": "Verb"}, "Description": {"en": f"d\n\n{_T1}"}}
    raw = compute_disposition(src, tgt, ConflictMode.UPDATE)
    assert raw == ItemDisposition.UPDATE                       # the #87 bug
    assert compute_disposition(src, strip_residue_props(tgt),
                               ConflictMode.UPDATE) == ItemDisposition.SKIP


def test_genuine_difference_still_updates_after_strip():
    src = {"Description": {"en": "new"}}
    tgt = {"Description": {"en": f"old\n\n{_T1}"}}
    assert compute_disposition(src, strip_residue_props(tgt),
                               ConflictMode.UPDATE) == ItemDisposition.UPDATE


def test_snapshot_baseline_does_not_nest_tag():
    tag = ImportResidueTag.make("GT-20260103-000000", "Src", "2026-01-03T00:00:00")
    snap = tag.with_snapshot({"Description": {"en": f"d\n\n{_T1}"}}).decode_snapshot()
    assert snap == {"Description": {"en": "d"}}


class _MS2:
    def __init__(self, t): self.t = t
    def get_String(self, ws): return self
    @property
    def Text(self): return self.t
    def set_String(self, ws, v): self.t = v


def test_planner_compare_ignores_own_tag():
    ws_list = [("en", 2)]
    gaps, conflicts = _cats._compare_multistring_per_ws(
        _MS2("d"), _MS2(f"d\n\n{_T1}"), ws_list)
    assert gaps == [] and conflicts == []
    # tag-only target + non-empty source is a real gap
    gaps, conflicts = _cats._compare_multistring_per_ws(
        _MS2("d"), _MS2(_T1), ws_list)
    assert gaps == [(2, "d")] and conflicts == []
    # genuine divergence is still a conflict, reported without the tag
    gaps, conflicts = _cats._compare_multistring_per_ws(
        _MS2("new"), _MS2(f"old\n\n{_T1}"), ws_list)
    assert conflicts == [(2, "new", "old")]


def test_history_survives_update_and_last_line_parses():
    class _O:
        Description = _MS2(f"old\n\n{_T1}")
    o = _O()
    prior = residue_lines(o.Description.t)
    o.Description.t = "new"                      # the source write wipes the line
    restore_residue_history(o, 2, prior)
    restore_residue_history(o, 2, prior)         # idempotent
    tag2 = ImportResidueTag.make("GT-20260102-000000", "Src", "2026-01-02T00:00:00")
    apply_carrier_b(o, 2, tag2)
    assert o.Description.t.count("[GT-Tag]: ") == 2
    assert o.Description.t.startswith("new\n\n[GT-Tag]: GT|GT-20260101-000000")
    # conflict.py's parse uses rfind: it must pick the NEWEST (last) line.
    assert ImportResidueTag.parse(o.Description.t).run_id == "GT-20260102-000000"


def test_carrier_b_run_id_match_is_line_start_only():
    tag = ImportResidueTag.make("GT-20260101-000000", "Src", "2026-01-01T00:00:00")
    o = type("O", (), {})()
    o.Description = _MS2("quote: [GT-Tag]: GT|GT-20260101-000000|x")
    apply_carrier_b(o, 1, tag)
    assert o.Description.t.count("[GT-Tag]: ") == 2   # user text did not suppress


# ---- cycle 4: trailing-whitespace round-trip (strip = exact inverse) -------
import pytest  # noqa: E402

_SRC_TEXTS = ["", "Foo", "Foo\n", "Foo\r\n", "Foo\n\n", "  ", "A\n\nB", "\n"]


@pytest.mark.parametrize("x", _SRC_TEXTS)
def test_strip_is_exact_inverse_after_stamp_and_history_update(x):
    from gramtrans.Lib.residue import strip_residue_text
    tag1 = ImportResidueTag.make("GT-20260101-000000", "Src", "2026-01-01T00:00:00")
    tag2 = ImportResidueTag.make("GT-20260102-000000", "Src", "2026-01-02T00:00:00")
    o = type("O", (), {})()
    o.Description = _MS2(x)
    apply_carrier_b(o, 1, tag1)
    assert strip_residue_text(o.Description.t) == x
    # UPDATE: source write wipes the tag, new run stamps, history restored.
    prior = residue_lines(o.Description.t)
    o.Description.t = x
    apply_carrier_b(o, 1, tag2)
    restore_residue_history(o, 1, prior)
    assert o.Description.t.count("[GT-Tag]: ") == 2
    assert strip_residue_text(o.Description.t) == x
    # Third run, same source: still equal (no unbounded growth trigger).
    assert strip_residue_props({"Description": {"en": o.Description.t}}) == \
        {"Description": ({"en": x} if x else {})}


@pytest.mark.parametrize("x", ["Foo", "Foo\n", "Foo\r\n"])
def test_genuine_change_still_unequal_and_legacy_stamp_strips(x):
    from gramtrans.Lib.residue import strip_residue_text
    stamped = f"{x}\n\n{_T1}"
    assert strip_residue_text(stamped) == x
    assert strip_residue_text(stamped) != x.replace("Foo", "Bar")
    assert strip_residue_text(f"Foo\n\n{_T1}") == "Foo"      # 32cd022 format
    assert strip_residue_text(f"\n{_T1}") == ""             # legacy empty
    assert strip_residue_text(x) == x                        # no residue
