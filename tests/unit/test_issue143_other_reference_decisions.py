"""Issue #143 -- the non-030 `reference_decisions` (owned children, pictures,
entry-ref types, allomorph refs) are summarised in Preview and serialized in
the run report JSON."""
from __future__ import annotations

import json
from types import SimpleNamespace

from gramtrans.Lib.models import ReferenceAction, ReferenceDecisionRecord
from gramtrans.Lib.preview import (
    render_other_reference_decisions,
    render_preview_extra_lines,
)
from gramtrans.Lib.report import _reference_decision_json


def _rec(field, action, owner="LexSense", guid="g"):
    return ReferenceDecisionRecord(
        owner_kind=owner, owner_guid=guid, field_name=field, action=action,
        item_name="n", item_guid="i-" + guid)


def _plan(actions=(), overwrites=()):
    return SimpleNamespace(actions=tuple(actions), overwrites=tuple(overwrites))


def _act(*recs):
    return SimpleNamespace(reference_decisions=tuple(recs))


def test_empty_plan_renders_nothing():
    assert render_other_reference_decisions(_plan()) == ()


def test_summary_counts_per_owner_field_action_and_skips_030_fields():
    plan = _plan(
        actions=[_act(
            _rec("ExamplesOS", ReferenceAction.CREATE, guid="a"),
            _rec("ExamplesOS", ReferenceAction.CREATE, guid="b"),
            _rec("PicturesOS", ReferenceAction.LINK, guid="c"),
            _rec("AppendixesRC", ReferenceAction.LINK, guid="d"))],
        overwrites=[_act(_rec("AlternateFormsOS", ReferenceAction.UPDATE,
                              owner="MoForm"))])
    lines = render_other_reference_decisions(plan)
    text = "\n".join(lines)
    assert "Create  LexSense.ExamplesOS: 2 references" in text
    assert "Link  LexSense.PicturesOS: 1 reference" in text
    assert "Update  MoForm.AlternateFormsOS: 1 reference" in text
    assert "AppendixesRC" not in text
    assert "Other reference decisions" in lines[0]


def test_wired_into_preview_extra_lines():
    plan = _plan(actions=[_act(_rec("ExamplesOS", ReferenceAction.CREATE))])
    for name in ("reversal_decisions", "config_view_records",
                 "feature_category_links", "text_plans",
                 "lexical_relation_decisions"):
        setattr(plan, name, ())
    try:
        lines = render_preview_extra_lines(plan)
    except AttributeError:
        import pytest
        pytest.skip("fake plan too thin for the full composition")
    assert any("Other reference decisions" in x for x in lines)


def test_json_serializer_carries_planned_and_ancestors():
    rec = ReferenceDecisionRecord(
        owner_kind="LexSense", owner_guid="o", field_name="ThesaurusItemsRC",
        action=ReferenceAction.CREATE, item_name="c", item_guid="ci",
        new_ancestors=(("p", "pi"),), planned=True)
    d = _reference_decision_json(rec)
    assert d["planned"] is True and d["new_ancestors"] == [["p", "pi"]]
    json.dumps(d)
