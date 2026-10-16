"""Issue #45: untitled source texts must not collide on a placeholder name,
and the Exists/Find guard must not disagree about non-default-WS names."""
from __future__ import annotations

from gramtrans.Lib import texts
from gramtrans.Lib.models import ReferenceAction, TextTransferPlan
from _fakes_texts import FakeWS, FakeText, FakeProject

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _plan(guid, title=""):
    return TextTransferPlan(source_guid=guid, title=title,
                            disposition=ReferenceAction.CREATE, target_guid=None)


def _run(plans, target):
    dropped = []
    out = [texts._resolve_or_create_text_ex(p, target.Texts, {}, {}, dropped)
           for p in plans]
    return out, dropped


def test_two_untitled_texts_make_two_target_texts_under_source_guids():
    # The issue's executed proof, as a regression test.
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    (r1, c1), (r2, c2) = _run([_plan("src-A"), _plan("src-B")], target)[0]
    assert r1 is not r2
    assert (r1.guid, r2.guid) == ("src-A", "src-B")
    assert len(target.Texts._texts) == 2
    assert r1.name != r2.name and r1.name and r2.name
    assert c1 and c2


def test_untitled_target_name_is_short_placeholder_not_full_guid():
    # Texts.Create requires a unique non-empty name (flexicon raises
    # FP_ParameterError on a duplicate), so the placeholder carries the first
    # 8 hex digits of the source GUID -- not the 36-char GUID (issue #45).
    guid = "0543896a-213a-4aa9-9014-a424ba4c366f"
    assert texts._untitled_create_name(_plan(guid)) == "(untitled text) 0543896a"
    assert guid not in texts._untitled_create_name(_plan(guid))
    # Two untitled texts with different GUIDs stay distinct...
    other = "07c6e20b-0000-4000-8000-000000000000"
    assert (texts._untitled_create_name(_plan(guid))
            != texts._untitled_create_name(_plan(other)))
    # ...and the placeholder is still never a lookup key (no Exists/Find),
    # see test_untitled_never_consults_exists_or_find.
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    (r, created), = _run([_plan(guid)], target)[0]
    assert r.name == "(untitled text) 0543896a" and created


def test_untitled_texts_do_not_interleave_paragraphs_and_added_is_two():
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    (r1, c1), (r2, c2) = _run([_plan("src-A"), _plan("src-B")], target)[0]
    r1.paragraphs.append("p-A")
    r2.paragraphs.append("p-B")
    assert r1.paragraphs == ["p-A"] and r2.paragraphs == ["p-B"]
    assert sum(1 for c in (c1, c2) if c) == 2


def test_untitled_never_consults_exists_or_find():
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[])
    calls = []
    target.Texts.Exists = lambda n: calls.append(("Exists", n)) or True
    target.Texts.Find = lambda n, w=None: calls.append(("Find", n)) or object()
    target.Texts.Create = lambda n, g=None, guid=None, contents_guid=None: guid
    (r, created), = _run([_plan("src-A")], target)[0]
    assert calls == [] and created and r == "src-A"


def test_titled_reuse_is_not_counted_as_created():
    existing = FakeText(guid="tgt-1", name="Story")
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    (r, created), = _run([_plan("src-X", "Story")], target)[0]
    assert r is existing and created is False


def test_name_only_in_non_default_ws_does_not_raise_and_is_reported():
    other = FakeText(guid="tgt-1", name="")
    other.alt_names = {2: "Story"}
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[other])
    # Premise: the fake diverges like flexicon.
    assert target.Texts.Exists("Story") and target.Texts.Find("Story") is None
    out, dropped = _run([_plan("src-X", "Story")], target)
    (r, created), = out
    assert (r, created) == (None, False)          # no exception escapes
    assert len(dropped) == 1                      # never silent
    assert dropped[0].reason.startswith("text create failed")
    assert len(target.Texts._texts) == 1          # nothing half-created


def test_apply_texts_returns_counts_and_skips_for_the_report():
    # Issue #45-b: apply_texts reports adds/updates/skips so execute can put
    # them into per_category[TEXTS].
    from _fakes_texts import FakeCtx
    existing = FakeText(guid="tgt-1", name="Story")
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[existing])
    ok_new = _plan("src-A")                                   # untitled -> create
    reuse = _plan("src-B", "Story")                           # titled -> reuse
    other = FakeText(guid="tgt-2", name="")
    other.alt_names = {2: "Clash"}
    target.Texts._texts.append(other)
    bad = _plan("src-C", "Clash")                             # create fails
    out = texts.apply_texts([ok_new, reuse, bad], FakeProject(
        ws_list=[WS_VERN, WS_EN], texts=[]), target,
        FakeCtx(source_handle=None, ws_map={}), tag=object(),
        report_sink=None, resolver_cache={}, dropped=[])
    assert out["added"] == 1 and out["updated"] == 1
    assert [s.source_guid for s in out["skips"]] == ["src-C"]
    assert out["skips"][0].category.value == "texts"


def test_run_report_has_a_texts_entry_for_text_adds_and_skips():
    from gramtrans.Lib import report as _report  # noqa: F401 (attaches builder)
    from gramtrans.Lib.models import (
        GrammarCategory, RunContext, RunMode, RunPlan, RunReport, Selection,
        Skip, SkipReason, WSMapping)
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00")
    plan = RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=())
    skip = Skip(category=GrammarCategory.TEXTS, source_guid="g",
                reason=SkipReason.DEPENDENCY_UNRESOLVED, detail="x")
    rep = RunReport.build_from_plan(
        plan, RunMode.MOVE, extra_skips=(skip,), text_added=3, text_updated=1)
    t = rep.per_category[GrammarCategory.TEXTS]
    assert (t.added, t.skipped, t.overwritten) == (3, 1, 1)


def test_execute_folds_apply_texts_outcome_into_per_category(monkeypatch):
    import gramtrans.Lib.categories as categories
    import gramtrans.Lib.transfer as transfer
    from gramtrans.Lib.models import (
        GrammarCategory, RunContext, RunPlan, Selection, Skip, SkipReason,
        WSMapping)
    monkeypatch.setattr(categories, "reproduce_all_lexical_relations",
                        lambda *a, **k: None)
    monkeypatch.setattr(categories, "reproduce_reversal_entries",
                        lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_171_subpass", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_owner_feat_strucs",
                        lambda *a, **k: None)
    skip = Skip(category=GrammarCategory.TEXTS, source_guid="s",
                reason=SkipReason.DEPENDENCY_UNRESOLVED, detail="x")
    monkeypatch.setattr(
        texts, "apply_texts",
        lambda *a, **k: {"added": 2, "updated": 0, "already": 0,
                         "skips": [skip]})

    class _Sink:
        def Info(self, m): pass
        def Warning(self, m): pass
        def Error(self, m): pass
        def Blank(self): pass

    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00")
    plan = RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=(),
                   text_plans=(_plan("a"), _plan("b"), _plan("c")))
    rep = transfer.execute(plan, object(), object(), _Sink(), tag=None)
    t = rep.per_category[GrammarCategory.TEXTS]
    assert (t.added, t.skipped) == (2, 1)
