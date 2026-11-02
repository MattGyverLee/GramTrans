"""Issue #165: Preview follow-ups (run-wide overwrite cache, lexrel render
grouping by type GUID, shared relation-type helper)."""
import gramtrans.Lib.categories as categories
import gramtrans.Lib.preview as preview
from gramtrans.Lib.models import (
    ReferenceAction, ReferenceDecisionRecord, RunPlan, Selection, WSMapping,
)


def _lexref(rel, label, type_guid):
    return ReferenceDecisionRecord(
        "LexReference", rel, "MembersOC", ReferenceAction.CREATE, label, rel,
        type_guid=type_guid)


def _plan(decisions):
    plan = RunPlan(context=None, selection=Selection(categories={}),
                   ws_mapping=WSMapping(entries=()))
    object.__setattr__(plan, "lexical_relation_decisions", tuple(decisions))
    return plan


def test_same_named_types_render_as_separate_lines():
    lines = preview.render_lexical_relation_decisions(_plan([
        _lexref("r1", "Dup", "type-a"), _lexref("r2", "Dup", "type-a"),
        _lexref("r3", "Dup", "type-b"),
    ]))
    assert "    Create 2 relations of type 'Dup' {type-a}" in lines
    assert "    Create 1 relation of type 'Dup' {type-b}" in lines


def test_unique_label_has_no_guid_suffix():
    lines = preview.render_lexical_relation_decisions(_plan([
        _lexref("r1", "Solo", "type-a")]))
    assert "    Create 1 relation of type 'Solo'" in lines


def test_records_without_type_guid_still_group_by_label():
    lines = preview.render_lexical_relation_decisions(_plan([
        _lexref("r1", "L", ""), _lexref("r2", "L", "")]))
    assert "    Create 2 relations of type 'L'" in lines


def test_relation_type_of_prefers_cast_and_handles_missing_owner(monkeypatch):
    class Rel:
        Owner = object()
    sentinel = object()
    monkeypatch.setattr(categories, "_as_lex_ref_type", lambda o: sentinel)
    assert categories._relation_type_of(Rel()) is sentinel
    monkeypatch.setattr(categories, "_as_lex_ref_type", lambda o: None)
    assert categories._relation_type_of(Rel()) is Rel.Owner
    assert categories._relation_type_of(object()) is None


def test_overwrite_reference_decisions_uses_supplied_cache(monkeypatch):
    seen = []
    monkeypatch.setattr(
        categories, "_decide_reference_fields",
        lambda *a, **kw: seen.append(kw["resolver_cache"]) or ())
    shared = {}
    preview._overwrite_reference_decisions(
        "LexEntry", "g", object(), object(), frozenset(), resolver_cache=shared)
    preview._overwrite_reference_decisions(
        "LexEntry", "g", object(), object(), frozenset())
    assert seen[0] is shared
    assert seen[1] == {} and seen[1] is not shared
