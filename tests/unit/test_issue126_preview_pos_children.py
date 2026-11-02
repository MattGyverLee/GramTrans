"""Issue #126 -- Preview lists, and the Move report counts, the owned children
(slots, templates, ReferenceForms FsFeatStruc, ...) of a POS the run CREATES.

Principle III: Preview rows must match Move writes. Hermetic: reuses the fakes
of `test_issue107_created_pos_collections.py`.
"""
from __future__ import annotations

import test_038_enrichment_executor as base
from test_038_enrichment_executor import (  # noqa: F401 -- autouse fixtures
    _offline_tsstrings,
    _patch_guid,
)
from test_issue107_created_pos_collections import (  # noqa: F401
    _ExecSink,
    _quiet_tail,
    _source_pos,
)

from gramtrans.Lib import categories, preview, report, transfer
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    RunContext,
    RunMode,
    RunPlan,
    Selection,
    WSMapping,
)


def _ctx(source, target):
    return RunContext(
        source_handle=source, source_project_name="S", source_project_path="",
        target_handle=target, target_project_name="T", target_project_path="",
        run_id="GT-20261101-000000", started_at="2026-11-01T00:00:00",
    )


def _action(guid, **kw):
    return PlannedAction(category=GrammarCategory.GRAM_CATEGORIES,
                         source_guid=guid, intended_target_guid=guid,
                         summary="Numeral", **kw)


def _by_field(rows):
    return {r.field_name: r.added for r in rows}


def test_preview_projection_matches_move_writes_field_for_field():
    """THE #126 acceptance: Preview rows == Move writes for a POS with slots,
    templates and ReferenceForms."""
    src = _source_pos()
    source = base._FakeProject([src])
    target = base._FakeProject([], factories=base._all_factories())

    projected = categories.project_created_pos_children(
        src, _ctx(source, target))

    created = base._FakePOS("pos-num")
    moved = transfer._fill_created_pos_collections(
        _action("pos-num"), created, source, target, base._Sink(), ws_map={})

    assert _by_field(projected) == _by_field(moved)
    assert _by_field(projected)["AffixSlotsOC"] == 1
    assert _by_field(projected)["AffixTemplatesOS"] == 1
    assert _by_field(projected)["ReferenceFormsOC"] == 2


def test_inflectable_feats_reference_collection_is_not_projected():
    """It creates no object (single link-pass writer); Move does not add it."""
    src = base._FakePOS("pos-x", InflectableFeatsRC=[base._FakeChild("f-1")])
    ctx = _ctx(base._FakeProject([src]), base._FakeProject([]))
    assert categories.project_created_pos_children(src, ctx) == ()


def test_attach_stamps_only_pos_adds_and_leaves_others_alone():
    src = _source_pos()
    ctx = _ctx(base._FakeProject([src]), base._FakeProject([]))
    other = PlannedAction(category=GrammarCategory.STEM_NAMES,
                          source_guid="sn-1", intended_target_guid="sn-1",
                          summary="stem")
    actions = [_action("pos-num"), other]
    preview._attach_created_pos_children(actions, ctx)
    assert _by_field(actions[0].owned_children)["AffixSlotsOC"] == 1
    assert actions[1] is other and other.owned_children == ()


def test_attach_never_breaks_preview_on_an_unreadable_source():
    class _Boom:
        class POS:
            @staticmethod
            def GetAll(recursive=True):
                raise RuntimeError("boom")

    ctx = _ctx(_Boom(), base._FakeProject([]))
    actions = [_action("pos-num")]
    preview._attach_created_pos_children(actions, ctx)
    assert actions[0].owned_children == ()


def _plan(actions):
    ctx = _ctx(object(), object())
    return RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=tuple(actions))


def test_preview_report_carries_and_renders_the_children():
    src = _source_pos()
    ctx = _ctx(base._FakeProject([src]), base._FakeProject([]))
    actions = [_action("pos-num")]
    preview._attach_created_pos_children(actions, ctx)
    rep = report.RunReport.build_from_plan(_plan(actions), RunMode.PREVIEW)
    assert [r.owner_guid for r in rep.created_pos_children] == ["pos-num"]
    text = "\n".join(report.render_text_summary(rep))
    assert "Owned children CREATED" in text
    assert "AffixSlotsOC +1" in text and "ReferenceFormsOC +2" in text
    assert "created_pos_children" in report.to_snapshot_json(rep)


def test_report_without_children_is_unchanged():
    rep = report.RunReport.build_from_plan(_plan([_action("p")]),
                                           RunMode.PREVIEW)
    assert rep.created_pos_children == ()
    assert "Owned children CREATED" not in "\n".join(
        report.render_text_summary(rep))


def test_move_report_counts_the_measured_children(monkeypatch, _quiet_tail):
    """execute() puts what the fill MEASURED on the report."""
    src = _source_pos()
    source = base._FakeProject([src])
    target = base._FakeProject([], factories=base._all_factories())

    def handler(action, ctx, ws, tag):
        return base._FakePOS(action.source_guid)

    monkeypatch.setattr(categories, "for_category",
                        lambda cat: {"execute_action": handler})
    ctx = _ctx(source, target)
    plan = RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()),
                   actions=(_action("pos-num"),))
    rep = transfer.execute(plan, source, target, _ExecSink(), tag=None)
    assert [r.owner_guid for r in rep.created_pos_children] == ["pos-num"]
    measured = _by_field(rep.created_pos_children[0].collections)
    assert measured == _by_field(
        categories.project_created_pos_children(src, ctx))
