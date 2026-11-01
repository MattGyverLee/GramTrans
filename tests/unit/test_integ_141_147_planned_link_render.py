"""Cross-PR integration (#146 + #144 + #147): a planned LINK has no target item.

#146 marks Preview's resolver cache as a planning cache, so a SECOND
`decide_reference` on the same source-only item yields LINK with
`target_item=None` (the item only exists once Move's earlier CREATE runs).
Both Preview renderers must cope with that decision and name the item from the
SOURCE item, never from `target_item`.

  (a) #144 `render_reversal_and_text_decisions`, via a reversal `pos_decision`;
  (b) #147 `render_sense_list_reference_decisions`, via the
      `ReferenceDecisionRecord` that `categories._reference_decision_record`
      flattens the decision into.

Wording is the approved domain ruling; tests import the constants from
`preview` rather than hard-coding it.
"""
from __future__ import annotations

import test_issue116_preview_sense_list_decisions as t116
import test_issue144_preview_pos_text_decisions as t144

from gramtrans.Lib import categories, preview, references
from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    ReferenceAction,
    RunPlan,
)


def _planned_link_pair():
    src_list = t116._List("src-thes", "Thes", owner=object())
    n = t116._Item("n-guid", "lonely item", owner=src_list)
    src_list.PossibilitiesOS = [n]
    tgt_list = t116._List("tgt-thes", "Thes", items=[])
    target = t116._Target(possibility_lists=[tgt_list])
    spec = references.build_thesaurus_spec(tgt_list)
    cache = references.mark_planning_cache({})
    d1 = references.decide_reference(n, target, spec, cache)
    d2 = references.decide_reference(n, target, spec, cache)
    assert d1.action == ReferenceAction.CREATE
    assert d2.action == ReferenceAction.LINK and d2.target_item is None
    assert d2.source_item is n
    return n, spec, d1, d2


def test_reversal_pos_decision_planned_link_renders_from_source():
    n, _spec, d1, d2 = _planned_link_pair()
    plan = t144._plan(reversal_decisions=[
        t144._rev("r1", pos_decision=d1), t144._rev("r2", pos_decision=d2)])
    lines = preview.render_reversal_and_text_decisions(plan)
    text = "\n".join(lines)
    print(text)
    link = [ln for ln in lines if ln.lstrip().startswith("Link")]
    assert len(link) == 1
    assert "'lonely item'" in link[0] and "{n-guid}" in link[0]
    # the same item's CREATE row is named from the source too
    create = [ln for ln in lines if ln.lstrip().startswith("Create")]
    assert len(create) == 1 and "'lonely item'" in create[0]
    assert "{n-guid}" in create[0]
    assert preview.PLANNED_LINK_ROW_SUFFIX in link[0]
    assert preview.PLANNED_LINK_ROW_SUFFIX not in create[0]
    assert preview.REVERSAL_TEXT_NEW_IN_RUN_NOTE in lines


def test_sense_list_record_from_planned_link_renders_from_source():
    n, spec, d1, d2 = _planned_link_pair()
    recs = [categories._reference_decision_record("LexSense", f"s{i}", spec, d)
            for i, d in enumerate((d1, d2))]
    assert recs[1].action == ReferenceAction.LINK
    assert recs[1].item_name == "lonely item" and recs[1].item_guid == "n-guid"
    action = PlannedAction(
        category=GrammarCategory.STEMS, source_guid="e1",
        intended_target_guid="e1", summary="entry",
        reference_decisions=tuple(recs))
    base = t144._plan()
    plan = RunPlan(context=base.context, selection=base.selection,
                   ws_mapping=base.ws_mapping, actions=(action,))
    lines = preview.render_sense_list_reference_decisions(plan)
    print("\n".join(lines))
    link = [ln for ln in lines if ln.lstrip().startswith("Link")]
    assert len(link) == 1
    assert "'lonely item'" in link[0] and "{n-guid}" in link[0]
    assert link[0].endswith(preview.PLANNED_LINK_ROW_SUFFIX)
    assert not any("Later references" in ln for ln in lines)


# ---- collapse lines + negative controls -----------------------------------

import test_issue147_sense_list_row_cap as t147

CAP = preview.SENSE_LIST_REF_ROW_CAP
AP, TH = t147.AP, t147.TH


def _prec(owner, field, guid, planned):
    return t147.ReferenceDecisionRecord(
        owner_kind="LexSense", owner_guid=owner, field_name=field,
        action=ReferenceAction.LINK, item_name=guid, item_guid=guid,
        new_ancestors=(), planned=planned)


def _fmt(template, field, n, m):
    return template.format(label="Link", field=field, n=n,
                           n_s="s" if n != 1 else "", m=m,
                           m_s="s" if m != 1 else "")


def test_collapse_splits_existing_from_planned_and_excludes_planned_from_n():
    recs = [_prec(f"s{i % 3}", TH, f"e{i:03d}", False) for i in range(CAP)]
    recs += [_prec(f"p{i % 2}", TH, f"n{i:03d}", True) for i in range(4)]
    lines = preview.render_sense_list_reference_decisions(t147._plan(recs))
    assert list(lines[1:]) == [
        _fmt(preview.SENSE_LIST_LINK_EXISTING_LINE, TH, CAP, 3),
        _fmt(preview.SENSE_LIST_LINK_PLANNED_LINE, TH, 4, 2)]


def test_collapse_omits_second_line_when_no_planned_items():
    recs = [_prec(f"s{i}", TH, f"e{i:03d}", False) for i in range(CAP + 1)]
    lines = preview.render_sense_list_reference_decisions(t147._plan(recs))
    assert list(lines[1:]) == [
        _fmt(preview.SENSE_LIST_LINK_EXISTING_LINE, TH, CAP + 1, CAP + 1)]
    assert not any("created by this run" in ln for ln in lines)


def test_itemized_existing_link_has_no_planned_label_but_planned_one_does():
    recs = [_prec("s1", AP, "old", False), _prec("s2", AP, "new", True)]
    lines = preview.render_sense_list_reference_decisions(t147._plan(recs))
    old = [ln for ln in lines if "'old'" in ln][0]
    new = [ln for ln in lines if "'new'" in ln][0]
    assert preview.PLANNED_LINK_ROW_SUFFIX not in old
    assert new.endswith(preview.PLANNED_LINK_ROW_SUFFIX)
