"""Issue #127 -- Preview must show the Update rows Move writes to a
LexEntryRef already on the target (INV-1 value merge + C2 link additions).

Parity: the Preview decisions are compared with the actual Move writes on
identical fakes.
"""
from __future__ import annotations

import types

from gramtrans.Lib.categories import (
    _plan_entryref_update_decisions,
    _run_entryref_create_pass,
    _run_post_pass_a,
)
from gramtrans.Lib.models import ReferenceAction
from gramtrans.Lib.preview import render_entryref_update_decisions

from _fakes_entryref import FakeRefSeq, ctx_create_and_wire, ref_record
from test_issue114_entryref_value_fields import (
    _Entry, _MultiString, _Ref, _Target, _stub_lcm,  # noqa: F401
)


def _lex(guid):
    return types.SimpleNamespace(guid=guid)


def _setup():
    existing = _Ref("ref-1", hide=0, summary=_MultiString({10: "old"}))
    existing.ComponentLexemesRS = FakeRefSeq(initial=[_lex("c0")])
    objs = {"entry-1": _Entry("entry-1", refs=[existing])}
    for g in ("c0", "c1", "p1"):
        objs[g] = _lex(g)
    target = _Target(objs)
    rec = ref_record("ref-1", ref_type=1, hide_minor_entry=1,
                     summary={"en": "new", "fr": "filled"},
                     components=["c0", "c1"], primaries=["p1"])
    return existing, target, rec


def _ctx(rec):
    ctx = ctx_create_and_wire(
        {"entry-1": [rec]},
        lexentry_ref_bindings={"entry-1": {"ComponentLexemesRS": [],
                                           "PrimaryLexemesRS": []}})
    object.__setattr__(ctx, "_ws_map", None)
    return ctx


def test_preview_update_rows_equal_move_writes(_stub_lcm) -> None:
    existing, target, rec = _setup()
    ctx = _ctx(rec)
    src_entry = types.SimpleNamespace(guid="entry-1")

    decisions = _plan_entryref_update_decisions(src_entry, ctx, target)

    # Preview is read-only.
    assert existing.hide_sets == 0 and existing.Summary.set_log == []
    assert existing.HideMinorEntry == 0
    assert len(existing.ComponentLexemesRS) == 1
    assert all(d.action == ReferenceAction.UPDATE for d in decisions)
    got = {(d.field_name, d.item_name) for d in decisions}
    assert got == {
        ("HideMinorEntry", "0 -> 1"),
        ("Summary@en", "old -> new"),
        ("Summary@fr", " -> filled"),
        ("ComponentLexemesRS", "add c1"),
        ("PrimaryLexemesRS", "add p1"),
    }

    # Move on the same inputs writes exactly that.
    _run_entryref_create_pass(ctx, target)
    _run_post_pass_a(ctx, target)
    assert existing.HideMinorEntry == 1
    assert sorted(h for h, _v in existing.Summary.set_log) == [10, 11]
    assert [x.guid for x in existing.ComponentLexemesRS] == ["c0", "c1"]
    assert [x.guid for x in existing.PrimaryLexemesRS] == ["p1"]


def test_preview_no_rows_when_target_already_matches(_stub_lcm) -> None:
    existing = _Ref("ref-1", hide=1, summary=_MultiString({10: "same"}))
    target = _Target({"entry-1": _Entry("entry-1", refs=[existing])})
    rec = ref_record("ref-1", hide_minor_entry=1, summary={"en": "same"})
    assert _plan_entryref_update_decisions(
        types.SimpleNamespace(guid="entry-1"), _ctx(rec), target) == []


def test_render_lists_update_rows(_stub_lcm) -> None:
    _existing, target, rec = _setup()
    decisions = tuple(_plan_entryref_update_decisions(
        types.SimpleNamespace(guid="entry-1"), _ctx(rec), target))
    plan = types.SimpleNamespace(
        actions=[types.SimpleNamespace(reference_decisions=decisions)])
    lines = render_entryref_update_decisions(plan)
    assert any("HideMinorEntry: 0 -> 1" in ln for ln in lines)
    assert render_entryref_update_decisions(
        types.SimpleNamespace(actions=[])) == ()
