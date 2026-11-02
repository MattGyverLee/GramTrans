"""Issue #117: stem_picks / affix_picks narrow STEMS / AFFIXES, and Preview says so."""
from types import SimpleNamespace as NS

from gramtrans.Lib import categories as C
from gramtrans.Lib.models import GrammarCategory, Selection
from gramtrans.Lib.preview import lexicon_pick_notes


def _entry(guid, affix):
    return NS(guid=guid, LexemeFormOA=NS(MorphTypeRA=NS(IsAffixType=affix)))


def _ctx(entries):
    return NS(source_handle=NS(LangProject=NS(LexDbOA=NS(EntriesOC=entries))))


ENTRIES = [_entry("s1", False), _entry("s2", False), _entry("a1", True), _entry("a2", True)]


def _guids(res):
    return sorted(e.guid for e in res)


def test_stem_picks_narrow_stems():
    sel = Selection(categories={GrammarCategory.STEMS: True}, stem_picks=frozenset({"S1"}))
    assert _guids(C.stems_enumerate_source(_ctx(ENTRIES), sel)) == ["s1"]


def test_affix_picks_narrow_affixes():
    sel = Selection(categories={GrammarCategory.AFFIXES: True}, affix_picks=frozenset({"a2"}))
    assert _guids(C.affixes_enumerate_source(_ctx(ENTRIES), sel)) == ["a2"]


def test_no_picks_transfers_all():
    sel = Selection(categories={GrammarCategory.STEMS: True, GrammarCategory.AFFIXES: True})
    assert _guids(C.stems_enumerate_source(_ctx(ENTRIES), sel)) == ["s1", "s2"]
    assert _guids(C.affixes_enumerate_source(_ctx(ENTRIES), sel)) == ["a1", "a2"]


def test_explicit_leaf_picks_win():
    sel = Selection(categories={GrammarCategory.STEMS: True}, stem_picks=frozenset({"s1"}),
                    leaf_item_picks={GrammarCategory.STEMS: frozenset({"s2"})})
    assert _guids(C.stems_enumerate_source(_ctx(ENTRIES), sel)) == ["s2"]


def test_notes_distinguish_empty_from_set():
    empty = Selection(categories={GrammarCategory.STEMS: True})
    (n,) = lexicon_pick_notes(empty)
    assert "no stem picks set" in n and "every stem" in n
    one = Selection(categories={GrammarCategory.STEMS: True}, stem_picks=frozenset({"s1"}))
    (n,) = lexicon_pick_notes(one)
    assert "only the 1 picked stem entry" in n
    assert lexicon_pick_notes(Selection(categories={})) == ()
