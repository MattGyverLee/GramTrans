"""Issue #32 -- LexEntryRef fidelity defects surfaced by the live complex-form
`0 -> N` proof (Korean-GIAL -> GT-Sandbox-32) and the deferred 027 items.

Covers (all in `Lib/categories.py`'s LexEntryRef region):

- ShowComplexFormsInRS is a LEXEME reference: stashed as GUIDs per ref and
  wired by C2 (`_run_post_pass_a`) in source order. Pre-fix it was routed
  through C3's publication-list resolver and silently lost (live: 3 of 4
  refs reproduced with only the LCM side-effect member).
- C2 wires PER REF (matched by ref GUID to its `entryref_create_bindings`
  record) instead of wiring the per-entry union into every target ref.
- C4 (`_entry_ref_is_reproducible`) judges a LexSense member on its owning
  entry (live: entry b135b153 was fully reproduced yet reported dropped)
  and is run-scoped when the run's Selection is known (leaf picks).
- `_lex_entry_ref_identity_label` reads a cast, class-correct label.

Fakes expose a lowercase ``.guid`` (host-free `_guid_str_from`) and a
``ClassName`` where the member class matters.
"""
from __future__ import annotations

import types

from gramtrans.Lib import categories
from gramtrans.Lib.models import GrammarCategory, Selection

from _fakes_entryref import (
    FakeLexeme,
    FakeRefSeq,
    ctx_create_and_wire,
    ref_record,
)

WS_EN = 100


# ============================================================================
# Fakes
# ============================================================================

class _MultiString:
    def __init__(self, text: str = "") -> None:
        self._data = {WS_EN: text} if text else {}


class _MorphType:
    def __init__(self, is_affix: bool = False) -> None:
        self.IsAffixType = is_affix


class _LexemeForm:
    def __init__(self, is_affix: bool = False, form: str = "") -> None:
        self.MorphTypeRA = _MorphType(is_affix)
        self.Form = _MultiString(form)


class _Entry:
    """A source LexEntry (STEMS unless `is_affix`)."""

    ClassName = "LexEntry"

    def __init__(self, guid, is_affix=False, citation="", form="", refs=()) -> None:
        self.guid = guid
        self.CitationForm = _MultiString(citation)
        self.LexemeFormOA = _LexemeForm(is_affix, form)
        self.EntryRefsOS = list(refs)


class _Sense:
    """A source LexSense component: no LexemeFormOA of its own."""

    ClassName = "LexSense"

    def __init__(self, guid, entry, gloss="") -> None:
        self.guid = guid
        self.Entry = entry
        self.Gloss = _MultiString(gloss)


class _SrcRef:
    def __init__(self, guid, ref_type=1, components=(), primaries=(),
                 show=(), complex_types=()) -> None:
        self.guid = guid
        self.RefType = ref_type
        self.ComponentLexemesRS = list(components)
        self.PrimaryLexemesRS = list(primaries)
        self.ShowComplexFormsInRS = list(show)
        self.VariantEntryTypesRS = []
        self.ComplexEntryTypesRS = list(complex_types)


class _ShowSideEffectRef:
    """Target LexEntryRef whose PrimaryLexemesRS.Add mirrors LCM's own side
    effect of also adding the primary to ShowComplexFormsInRS."""

    def __init__(self, guid) -> None:
        self.guid = guid
        self.ComponentLexemesRS = FakeRefSeq()
        self.ShowComplexFormsInRS = FakeRefSeq()
        show = self.ShowComplexFormsInRS

        class _Primaries(FakeRefSeq):
            def Add(self, obj) -> None:
                super().Add(obj)
                show.Add(obj)

        self.PrimaryLexemesRS = _Primaries()


class _TargetEntry:
    def __init__(self, guid, refs=()) -> None:
        self.guid = guid
        self.EntryRefsOS = FakeRefSeq(refs)


class _Target:
    def __init__(self, objects) -> None:
        self._objects = dict(objects)

    def get_object_by_guid(self, guid):
        return self._objects.get(guid)


def _stems_affixes_selection(picks=None):
    leaf = {} if picks is None else {
        GrammarCategory.STEMS: frozenset(picks),
        GrammarCategory.AFFIXES: frozenset(picks)}
    return Selection(categories={GrammarCategory.STEMS: True,
                                 GrammarCategory.AFFIXES: True},
                     leaf_item_picks=leaf)


def _ctx(selection=None, target=None):
    return types.SimpleNamespace(_selection=selection, target_handle=target)


# ============================================================================
# ShowComplexFormsInRS -- stashed as lexeme GUIDs, wired by C2
# ============================================================================

def test_stash_records_show_complex_forms_in_as_lexeme_guids() -> None:
    a, b = _Entry("lex-a"), _Entry("lex-b")
    entry = _Entry("cf-1", refs=[_SrcRef(
        "ref-1", components=[a, b], primaries=[a], show=[a, b])])
    ctx = types.SimpleNamespace(_lexentry_ref_bindings={},
                                _entryref_create_bindings={})

    categories._stash_entry_bindings(entry, ctx)

    (rec,) = ctx._entryref_create_bindings["cf-1"]
    assert rec["show_complex_forms_in"] == ["lex-a", "lex-b"]
    assert rec["components"] == ["lex-a", "lex-b"]


def test_c2_wires_show_complex_forms_in_in_source_order_despite_side_effect() -> None:
    """Live Korean-GIAL shape: show-in = every component; adding the primary
    already put it in ShowComplexFormsInRS (LCM side effect). C2 must add the
    rest, in source order, without duplicating the primary."""
    lex = {g: FakeLexeme(g) for g in ("lex-a", "lex-b", "lex-c")}
    tref = _ShowSideEffectRef("ref-1")
    target = _Target({"cf-1": _TargetEntry("cf-1", [tref]), **lex})
    ctx = ctx_create_and_wire(
        {"cf-1": [ref_record("ref-1", ref_type=1,
                             components=["lex-a", "lex-b", "lex-c"],
                             primaries=["lex-a"],
                             show_complex_forms_in=["lex-a", "lex-b", "lex-c"])]},
        {"cf-1": {"ComponentLexemesRS": ["lex-a", "lex-b", "lex-c"],
                  "PrimaryLexemesRS": ["lex-a"]}})

    skips = categories._run_post_pass_a(ctx, target)

    assert skips == []
    assert [x.guid for x in tref.ComponentLexemesRS] == ["lex-a", "lex-b", "lex-c"]
    assert [x.guid for x in tref.PrimaryLexemesRS] == ["lex-a"]
    assert [x.guid for x in tref.ShowComplexFormsInRS] == ["lex-a", "lex-b", "lex-c"]

    # Idempotent re-run: nothing added twice.
    assert categories._run_post_pass_a(ctx, target) == []
    assert [x.guid for x in tref.ShowComplexFormsInRS] == ["lex-a", "lex-b", "lex-c"]


# ============================================================================
# C2 per-ref wiring (no cross-wiring across refs of one entry)
# ============================================================================

def test_c2_wires_each_ref_from_its_own_record_only() -> None:
    """An entry owning a complex-form ref AND a variant ref: pre-#32 both
    target refs received the UNION of both refs' lexemes."""
    lex = {g: FakeLexeme(g) for g in ("lex-a", "lex-b", "lex-v")}
    cf_ref, var_ref = _ShowSideEffectRef("ref-cf"), _ShowSideEffectRef("ref-var")
    target = _Target({"e-1": _TargetEntry("e-1", [cf_ref, var_ref]), **lex})
    ctx = ctx_create_and_wire(
        {"e-1": [
            ref_record("ref-cf", ref_type=1, components=["lex-a", "lex-b"],
                       primaries=["lex-a"], show_complex_forms_in=["lex-a"]),
            ref_record("ref-var", ref_type=0, components=["lex-v"]),
        ]},
        {"e-1": {"ComponentLexemesRS": ["lex-a", "lex-b", "lex-v"],
                 "PrimaryLexemesRS": ["lex-a"]}})

    categories._run_post_pass_a(ctx, target)

    assert [x.guid for x in cf_ref.ComponentLexemesRS] == ["lex-a", "lex-b"]
    assert [x.guid for x in cf_ref.PrimaryLexemesRS] == ["lex-a"]
    assert [x.guid for x in var_ref.ComponentLexemesRS] == ["lex-v"]
    assert list(var_ref.PrimaryLexemesRS) == []
    assert list(var_ref.ShowComplexFormsInRS) == []


def test_c2_never_touches_a_target_only_ref() -> None:
    """A ref the target already owned (GUID not among this run's source
    records) must not be wired with source lexemes it never had."""
    lex_a = FakeLexeme("lex-a")
    ours, theirs = _ShowSideEffectRef("ref-src"), _ShowSideEffectRef("ref-tgt-only")
    target = _Target({"e-1": _TargetEntry("e-1", [theirs, ours]), "lex-a": lex_a})
    ctx = ctx_create_and_wire(
        {"e-1": [ref_record("ref-src", ref_type=0, components=["lex-a"])]},
        {"e-1": {"ComponentLexemesRS": ["lex-a"], "PrimaryLexemesRS": []}})

    categories._run_post_pass_a(ctx, target)

    assert [x.guid for x in ours.ComponentLexemesRS] == ["lex-a"]
    assert list(theirs.ComponentLexemesRS) == []


# ============================================================================
# C4 -- LexSense members and run-scoped reproducibility
# ============================================================================

def test_sense_component_is_judged_on_its_owning_entry() -> None:
    """Live Korean-GIAL entry b135b153: the first component is a LexSense.
    Pre-#32 the sense was cast to ILexEntry and tested for LexemeFormOA,
    so the fully reproduced ref was reported dropped."""
    owner = _Entry("eat-entry")
    sense = _Sense("eat-sense", owner, gloss="eat")
    entry = _Entry("cf-1", refs=[_SrcRef(
        "ref-1", components=[sense, _Entry("suffix", is_affix=True)],
        primaries=[sense])])
    dropped: list = []

    categories._report_dropped_entry_refs(entry, dropped)

    assert dropped == []


def test_sense_component_whose_entry_is_ineligible_is_still_reported() -> None:
    owner = _Entry("no-form")
    owner.LexemeFormOA = None
    entry = _Entry("cf-1", refs=[_SrcRef(
        "ref-1", components=[_Sense("s-1", owner, gloss="orphan")])])
    dropped: list = []

    categories._report_dropped_entry_refs(entry, dropped)

    assert [d.item_guid for d in dropped] == ["ref-1"]
    assert "component=orphan" in dropped[0].item_name  # cast, class-correct label


def test_run_scoped_unpicked_component_makes_ref_not_reproducible() -> None:
    """Leaf-pick-narrowed run: an eligible component that this run will NOT
    copy (and that is not on the target) means the ref cannot be fully
    reproduced -- it must be reported, not over-reported as FULL."""
    a, b = _Entry("lex-a"), _Entry("lex-b", is_affix=True)
    entry = _Entry("cf-1", refs=[_SrcRef("ref-1", components=[a, b], primaries=[a])])
    dropped: list = []
    ctx = _ctx(_stems_affixes_selection(picks={"cf-1", "lex-a"}), _Target({}))

    categories._report_dropped_entry_refs(entry, dropped, ctx)

    assert [d.item_guid for d in dropped] == ["ref-1"]


def test_run_scoped_all_components_picked_is_reproducible() -> None:
    a, b = _Entry("lex-a"), _Entry("lex-b", is_affix=True)
    entry = _Entry("cf-1", refs=[_SrcRef("ref-1", components=[a, b], primaries=[a])])
    dropped: list = []
    ctx = _ctx(_stems_affixes_selection(picks={"cf-1", "lex-a", "lex-b"}), _Target({}))

    categories._report_dropped_entry_refs(entry, dropped, ctx)

    assert dropped == []


def test_run_scoped_category_off_makes_ref_not_reproducible() -> None:
    """AFFIXES not selected at all: an affix component will not be copied."""
    a, b = _Entry("lex-a"), _Entry("lex-b", is_affix=True)
    entry = _Entry("cf-1", refs=[_SrcRef("ref-1", components=[a, b])])
    dropped: list = []
    sel = Selection(categories={GrammarCategory.STEMS: True})
    ctx = _ctx(sel, _Target({}))

    categories._report_dropped_entry_refs(entry, dropped, ctx)

    assert [d.item_guid for d in dropped] == ["ref-1"]


def test_run_scoped_unpicked_component_already_on_target_is_reproducible() -> None:
    """Out of this run's scope, but already on the target by GUID: C2
    resolves members by GUID, so the ref IS fully wired -- no report."""
    a, b = _Entry("lex-a"), _Entry("lex-b", is_affix=True)
    entry = _Entry("cf-1", refs=[_SrcRef("ref-1", components=[a, b])])
    dropped: list = []
    ctx = _ctx(_stems_affixes_selection(picks={"cf-1", "lex-a"}),
               _Target({"lex-b": object()}))

    categories._report_dropped_entry_refs(entry, dropped, ctx)

    assert dropped == []


def test_no_context_keeps_the_intrinsic_check() -> None:
    """Callers without a context (pre-#32 signature) keep the intrinsic,
    type-scoped behaviour: an eligible component is reproducible."""
    entry = _Entry("cf-1", refs=[_SrcRef("ref-1", components=[_Entry("lex-a")])])
    dropped: list = []

    categories._report_dropped_entry_refs(entry, dropped)

    assert dropped == []


# ============================================================================
# Identity label (cosmetic)
# ============================================================================

def test_identity_label_falls_back_to_lexeme_form_for_entry_component() -> None:
    """Korean-GIAL entries carry no citation form; the label used to fall
    back to the bare GUID."""
    ref = _SrcRef("ref-1", components=[_Entry("lex-a", form="khata")])

    label = categories._lex_entry_ref_identity_label(ref, "complex-form")

    assert label == "complex-form: component=khata"


def test_identity_label_prefers_citation_form() -> None:
    ref = _SrcRef("ref-1", components=[_Entry("lex-a", citation="cite", form="lf")])

    assert categories._lex_entry_ref_identity_label(ref, "variant") == (
        "variant: component=cite")
