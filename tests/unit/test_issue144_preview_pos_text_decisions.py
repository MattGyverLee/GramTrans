"""Issue #144 -- Preview renders `ReversalDecision.pos_decision` and the
`RunPlan.text_plans` genre / segment-tag decisions (constitution Principle III).

Before #144 the plan carried all three (reversal category CREATE/LINK/UPDATE,
text genre and text-markup tag CREATE/LINK) and Move applied them, but no
Preview surface rendered them. `preview.render_reversal_and_text_decisions`
now does, and `render_preview_extra_lines` composes it so every Preview pane
that shows the extra lines picks it up.

The live proof (Preview lines vs. what Move writes, re-run idempotency) is
`tests/integration/test_issue144_pos_text_decisions_live.py`.
"""
from __future__ import annotations

from gramtrans.Lib import preview, texts
from gramtrans.Lib.models import (
    DroppedItemRecord,
    GrammarCategory,
    ParagraphPlan,
    ReferenceAction,
    ReferenceDecision,
    ReversalDecision,
    RunContext,
    RunPlan,
    SegmentPlan,
    Selection,
    TextTransferPlan,
    WSMapping,
)
from _fakes_texts import (
    FakeCtx,
    FakeLangProject,
    FakeParagraph,
    FakePossibility,
    FakePossibilityList,
    FakeProject,
    FakeSegment,
    FakeText,
    FakeTextTag,
    FakeWS,
)

render = preview.render_reversal_and_text_decisions


def _plan(reversal_decisions=(), text_plans=()):
    ctx = RunContext(
        source_handle=object(), source_project_name="Src",
        source_project_path="/fake/src", target_handle=object(),
        target_project_name="Tgt", target_project_path="/fake/tgt",
        run_id="GT-144", started_at="2026-10-31T00:00:00")
    return RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()),
                   reversal_decisions=tuple(reversal_decisions),
                   text_plans=tuple(text_plans))


def _poss(guid, name, parent=None):
    p = FakePossibility(guid=guid, name=name)
    p.OwningPossibility = parent
    return p


def _create(item, chain=None):
    return ReferenceDecision(action=ReferenceAction.CREATE, source_item=item,
                             ancestors_to_create=tuple(chain or (item,)))


def _link(item):
    return ReferenceDecision(action=ReferenceAction.LINK, source_item=item,
                             target_item=object())


def _update(item):
    return ReferenceDecision(action=ReferenceAction.UPDATE, source_item=item,
                             target_item=object())


def _dropped(item, field="PartOfSpeechRA"):
    rec = DroppedItemRecord(
        owner_kind="ReversalIndexEntry", owner_guid="e", owner_label="",
        field_name=field, item_name=item.Name._data[100], item_guid=item.Guid,
        reason="target reversal category list absent")
    return ReferenceDecision(action=ReferenceAction.REPORT_DROPPED,
                             source_item=item, dropped=rec)


def _rev(guid, pos_decision=None, subs=(), ws="en"):
    return ReversalDecision(source_entry_guid=guid, target_index_ref=object(),
                            target_ws_id=ws, pos_decision=pos_decision,
                            reversal_form_alts={ws: guid},
                            sub_entry_decisions=tuple(subs))


def _text(guid, genres=(), tags=(), disposition=ReferenceAction.CREATE):
    seg = SegmentPlan(source_guid=guid + "-seg", tag_decisions=tuple(tags))
    return TextTransferPlan(source_guid=guid, title=guid, disposition=disposition,
                            genre_decisions=tuple(genres),
                            paragraphs=(ParagraphPlan(source_guid=guid + "-p",
                                                      segments=(seg,)),))


# ============================================================================
# Reversal entry category (ReversalDecision.pos_decision)
# ============================================================================

def test_empty_plan_renders_nothing():
    assert render(_plan()) == ()


def test_reversal_entry_without_category_renders_no_row():
    """Negative control: an entry whose source PartOfSpeechRA is unset has
    pos_decision=None; Move writes nothing, so Preview shows nothing."""
    assert render(_plan(reversal_decisions=[_rev("e1"), _rev("e2")])) == ()


def test_reversal_pos_create_link_update_dropped_each_rendered():
    new, shared, edited, gone = (_poss("p-new", "Noun"), _poss("p-old", "Verb"),
                                 _poss("p-upd", "Adj"), _poss("p-gone", "Adv"))
    lines = render(_plan(reversal_decisions=[
        _rev("e1", _create(new)), _rev("e2", _link(shared)),
        _rev("e3", _update(edited)), _rev("e4", _dropped(gone)), _rev("e5")]))
    assert lines[0] == "  Reversal categories (each reversal index's own category list):"
    assert "    Create  'Noun' {p-new}  (1 reversal entry)" in lines
    assert "    Link  'Verb' {p-old}  (1 reversal entry)" in lines
    assert "    Update  'Adj' {p-upd}  (1 reversal entry)" in lines
    assert ("    Not transferred  'Adv' {p-gone}  (1 reversal entry)"
            " -- see dropped items for the reason") in lines
    # Create / Update / Link / Not-transferred order, one row each.
    assert [ln.split()[0] for ln in lines[1:]] == ["Create", "Update", "Link", "Not"]


def test_reversal_pos_recurses_sub_entries_and_aggregates():
    noun = _poss("p-new", "Noun")
    tree = _rev("top", _create(noun), subs=[
        _rev("sub", _create(noun), subs=[_rev("subsub", _create(noun))])])
    lines = render(_plan(reversal_decisions=[tree]))
    assert "    Create  'Noun' {p-new}  (3 reversal entrys)" not in lines
    assert "    Create  'Noun' {p-new}  (3 reversal entrys)".replace("entrys", "entrys") \
        not in lines
    assert any(ln.startswith("    Create  'Noun' {p-new}  (3 ") for ln in lines), lines
    # Created once by Move (shared resolver cache); the note says so.
    assert "    (Created once; the other references link to it.)" in lines


def test_reversal_pos_create_names_its_ancestor_chain():
    parent = _poss("p-par", "Nominal")
    child = _poss("p-ch", "Proper", parent=parent)
    lines = render(_plan(reversal_decisions=[
        _rev("e1", _create(child, chain=(parent, child)))]))
    assert ("    Create  'Proper' {p-ch}  (1 reversal entry) -- under 'Nominal'"
            " (created too if absent)") in lines


# ============================================================================
# Text genres (TextTransferPlan.genre_decisions)
# ============================================================================

def test_genre_create_and_link_rendered_with_text_counts():
    new_g, old_g = _poss("g-new", "Folktale"), _poss("g-old", "Narrative")
    lines = render(_plan(text_plans=[
        _text("t1", genres=[_create(new_g), _link(old_g)]),
        _text("t2", genres=[_link(old_g)])]))
    assert lines[0] == "  Text genres:"
    assert "    Create  'Folktale' {g-new}  (1 text)" in lines
    assert "    Link  'Narrative' {g-old}  (2 texts)" in lines


def test_text_without_genre_or_tags_renders_nothing():
    assert render(_plan(text_plans=[_text("t1")])) == ()


# ============================================================================
# Text-markup tags (SegmentPlan.tag_decisions)
# ============================================================================

def test_tag_create_link_and_dropped_rendered():
    new_t, old_t, gone = (_poss("t-new", "Topic"), _poss("t-old", "Focus"),
                          _poss("t-gone", "Frame"))
    lines = render(_plan(text_plans=[
        _text("t1", tags=[_create(new_t), _link(old_t), _dropped(gone, "TagRA")])]))
    assert lines[0] == "  Text markup tags:"
    assert "    Create  'Topic' {t-new}  (1 tag)" in lines
    assert "    Link  'Focus' {t-old}  (1 tag)" in lines
    assert ("    Not transferred  'Frame' {t-gone}  (1 tag)"
            " -- see dropped items for the reason") in lines
    assert not any("already in the target" in ln for ln in lines)


def test_tag_rows_on_matched_text_carry_the_structure_as_is_note():
    """Move writes tags only into paragraphs it creates
    (`texts._apply_paragraphs` returns early for a target text that already has
    paragraphs), so an UPDATE text's tag rows must not read as a promise."""
    old_t = _poss("t-old", "Focus")
    lines = render(_plan(text_plans=[
        _text("t1", tags=[_link(old_t)], disposition=ReferenceAction.UPDATE)]))
    assert lines[-1] == (
        "    (1 text already in the target: tags are added only if the target "
        "text has no paragraphs yet; Move leaves an existing text's structure "
        "as-is.)")


def test_all_three_sections_in_order():
    noun, g, t = _poss("p", "Noun"), _poss("g", "Narr"), _poss("t", "Topic")
    lines = render(_plan(reversal_decisions=[_rev("e", _link(noun))],
                         text_plans=[_text("t1", genres=[_link(g)], tags=[_link(t)])]))
    headers = [ln for ln in lines if not ln.startswith("    ")]
    assert headers == ["  Reversal categories (each reversal index's own category list):",
                       "  Text genres:", "  Text markup tags:"]


def test_rows_are_capped_per_section():
    n = preview.SENSE_LIST_REF_ROW_CAP + 7
    decisions = [_rev("e%d" % i, _create(_poss("p%03d" % i, "N%d" % i)))
                 for i in range(n)]
    lines = render(_plan(reversal_decisions=decisions))
    rows = [ln for ln in lines if ln.startswith("    Create")]
    assert len(rows) == preview.SENSE_LIST_REF_ROW_CAP
    assert "    +7 more" in lines


# ============================================================================
# Composition seam + plan -> render chain
# ============================================================================

def test_render_preview_extra_lines_includes_the_new_lines():
    noun = _poss("p-new", "Noun")
    plan = _plan(reversal_decisions=[_rev("e1", _create(noun))])
    extra = preview.render_preview_extra_lines(plan)
    for line in render(plan):
        assert line in extra


WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def test_plan_texts_decisions_render_end_to_end():
    """The decisions `texts.plan_texts` really builds (fake projects) reach
    the Preview lines: an absent genre/tag is Create, a present one Link."""
    new_g, old_g = _poss("g-new", "Folktale"), _poss("g-old", "Narrative")
    new_t = _poss("t-new", "Topic")
    seg = FakeSegment(guid="seg-1", baseline=" abc .", free={2: "x"}, literal={},
                      wordforms=(), analyses_rs=())
    para = FakeParagraph(guid="para-1", text_by_handle={1: "abc."}, segments=(seg,))
    tag = FakeTextTag(guid="tt-1", tag_ra=new_t, begin_seg=seg, end_seg=seg)
    src_text = FakeText(guid="txt-1", name="Story", paragraphs=(para,),
                        genres=(new_g, old_g), tags=(tag,))
    source = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[src_text])
    lp = FakeLangProject(genre_list=FakePossibilityList(
        [FakePossibility(guid="g-old", name="Narrative")]))
    target = FakeProject(ws_list=[WS_VERN, WS_EN], texts=(), lang_project=lp)
    sel = Selection(categories={GrammarCategory.TEXTS: True},
                    text_picks=frozenset({"txt-1"}))
    plans = texts.plan_texts(sel, source, target,
                             FakeCtx(source_handle=source), {}, [])
    lines = render(_plan(text_plans=plans))
    assert "    Create  'Folktale' {g-new}  (1 text)" in lines
    assert "    Link  'Narrative' {g-old}  (1 text)" in lines
    assert "    Create  'Topic' {t-new}  (1 tag)" in lines
