"""Issue #147 -- the #116 sense-list reference-decision renderer
(`preview.render_sense_list_reference_decisions`) had no row cap, so a large
lexicon flooded the Preview pane.

Now each action kind (create / update / link / not transferred) is capped at
`SENSE_LIST_REF_ROW_CAP`. Create / Update / Not-transferred rows beyond the
cap are counted on one "... and N more" line; LINK rows collapse to one count
line per field once they exceed the cap. Nothing disappears without a count.
"""
from __future__ import annotations

import re

from gramtrans.Lib.models import (
    GrammarCategory,
    PlannedAction,
    ReferenceAction,
    ReferenceDecisionRecord,
    RunContext,
    RunPlan,
    Selection,
    WSMapping,
)
from gramtrans.Lib.preview import (
    SENSE_LIST_REF_ROW_CAP as CAP,
    _capped_rows,
    render_preview_extra_lines,
    render_sense_list_reference_decisions,
)

TH, AP = "ThesaurusItemsRC", "AppendixesRC"
FOOTER = ("    (Later references to an item created earlier in this run show "
          "as create; Move links them.)")


def _plan(records):
    ctx = RunContext(
        source_handle=object(), source_project_name="Src",
        source_project_path="/fake/src", target_handle=object(),
        target_project_name="Tgt", target_project_path="/fake/tgt",
        run_id="GT-147", started_at="2026-10-31T00:00:00")
    action = PlannedAction(
        category=GrammarCategory.STEMS, source_guid="e1",
        intended_target_guid="e1", summary="entry",
        reference_decisions=tuple(records))
    return RunPlan(context=ctx, selection=Selection(),
                   ws_mapping=WSMapping(entries=()), actions=(action,))


def _rec(owner, field, action, guid, name=None):
    return ReferenceDecisionRecord(
        owner_kind="LexSense", owner_guid=owner, field_name=field,
        action=action, item_name=name or guid, item_guid=guid,
        new_ancestors=())


def _items(prefix, n, field, action, owner="s"):
    return [_rec(f"{owner}{i}", field, action, f"{prefix}{i:03d}")
            for i in range(n)]


def _more(lines):
    return [ln for ln in lines if "more" in ln and "not shown here" in ln]


def test_cap_is_a_sane_module_constant():
    assert isinstance(CAP, int) and 1 <= CAP <= 100


def test_capped_rows_helper_counts_exactly_what_it_held_back():
    assert _capped_rows(["a", "b"], 2, "X rows") == ["a", "b"]
    out = _capped_rows([f"r{i}" for i in range(7)], 3, "X rows", suffix="; y")
    assert out == ["r0", "r1", "r2",
                   "    ... and 4 more X rows not shown here (7 total; y)"]


def test_create_rows_over_cap_are_capped_with_an_explicit_count():
    k = 7
    lines = render_sense_list_reference_decisions(
        _plan(_items("c", CAP + k, TH, ReferenceAction.CREATE)))
    create = [ln for ln in lines if ln.startswith("    Create  ")]
    assert len(create) == CAP
    more = _more(lines)
    assert more == [f"    ... and {k} more Create rows not shown here "
                    f"({CAP + k} total)"]
    shown, omitted = len(create), int(re.search(r"and (\d+) more", more[0])[1])
    assert shown + omitted == CAP + k
    # The footer survives the cap.
    assert lines[-1] == FOOTER
    # Bounded: header + cap rows + more-line + footer.
    assert len(lines) == CAP + 3


def test_exactly_cap_rows_render_byte_identical_to_uncapped():
    recs = _items("c", CAP, TH, ReferenceAction.CREATE)
    lines = render_sense_list_reference_decisions(_plan(recs))
    assert not _more(lines)
    assert len([ln for ln in lines if ln.startswith("    Create  ")]) == CAP
    assert lines[1] == f"    Create  {TH} 'c000' {{c000}}  (1 sense)"


def test_dropped_rows_over_cap_point_at_the_dropped_items_list():
    lines = render_sense_list_reference_decisions(
        _plan(_items("d", CAP + 2, AP, ReferenceAction.REPORT_DROPPED)))
    assert _more(lines) == [
        f"    ... and 2 more Not transferred rows not shown here "
        f"({CAP + 2} total; the dropped-items list names every one)"]
    assert FOOTER not in lines  # no create -> no footer


def test_update_rows_over_cap_are_capped():
    lines = render_sense_list_reference_decisions(
        _plan(_items("u", CAP + 1, TH, ReferenceAction.UPDATE)))
    assert len([ln for ln in lines if ln.startswith("    Update  ")]) == CAP
    assert _more(lines) == [
        f"    ... and 1 more Update rows not shown here ({CAP + 1} total)"]


def test_link_rows_over_cap_collapse_to_one_count_line_per_field():
    # 20 appendixes shared by 3 senses (M != N tests the owner union), and
    # CAP thesaurus items each on its own sense.
    recs = [_rec(f"s{i % 3}", AP, ReferenceAction.LINK, f"ap{i:03d}")
            for i in range(20)]
    recs += _items("t", CAP, TH, ReferenceAction.LINK, owner="ts")
    lines = render_sense_list_reference_decisions(_plan(recs))
    assert not [ln for ln in lines if ln.startswith("    Link  ") and "{" in ln]
    assert lines[1:] == (
        f"    Link  {AP}: 20 items already in the target  (3 senses) -- "
        f"itemized list collapsed above {CAP} rows",
        f"    Link  {TH}: {CAP} items already in the target  ({CAP} senses) "
        f"-- itemized list collapsed above {CAP} rows",
    )


def test_link_rows_at_or_under_cap_stay_itemized():
    lines = render_sense_list_reference_decisions(
        _plan(_items("ap", CAP, AP, ReferenceAction.LINK)))
    assert len([ln for ln in lines if ln.startswith(f"    Link  {AP} '")]) == CAP
    assert not any("collapsed" in ln for ln in lines)


def test_link_flood_never_crowds_out_create_or_drop_rows():
    recs = _items("ln", CAP + 5, TH, ReferenceAction.LINK)
    recs += [_rec("x1", TH, ReferenceAction.CREATE, "new1"),
             _rec("x2", TH, ReferenceAction.CREATE, "new2"),
             _rec("x3", AP, ReferenceAction.REPORT_DROPPED, "gone")]
    lines = render_sense_list_reference_decisions(_plan(recs))
    assert lines == (
        "  Sense appendix / thesaurus references:",
        f"    Create  {TH} 'new1' {{new1}}  (1 sense)",
        f"    Create  {TH} 'new2' {{new2}}  (1 sense)",
        f"    Link  {TH}: {CAP + 5} items already in the target  "
        f"({CAP + 5} senses) -- itemized list collapsed above {CAP} rows",
        f"    Not transferred  {AP} 'gone' {{gone}}  (1 sense) -- see "
        "dropped items for the reason",
        FOOTER,
    )
    assert set(lines) <= set(render_preview_extra_lines(_plan(recs)))


def test_large_lexicon_output_is_bounded():
    n = 5000
    recs = (_items("c", n, TH, ReferenceAction.CREATE)
            + _items("u", n, TH, ReferenceAction.UPDATE)
            + _items("l", n, AP, ReferenceAction.LINK)
            + _items("d", n, AP, ReferenceAction.REPORT_DROPPED))
    lines = render_sense_list_reference_decisions(_plan(recs))
    # header + 3 x (cap + more) + 1 collapsed link line + footer
    assert len(lines) == 1 + 3 * (CAP + 1) + 1 + 1
    omitted = sum(int(re.search(r"and (\d+) more", ln)[1]) for ln in _more(lines))
    assert omitted == 3 * (n - CAP)
