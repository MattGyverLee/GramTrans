"""Feature 038 T040/T041 -- enrichment of a MATCHED destination object.

These are the RED tests for Phase 5 (US4). The behaviour they pin lands in
T043-T047; until then most of this module fails, and it is meant to.

The clause under test, quoted verbatim from `data-model.md` section 9
(lines 209-213):

    **SKIP is defined by field-identity comparison, not by mere GUID
    presence.** A matched GUID alone is a LINK, not a SKIP. Emitting SKIP
    requires that every scalar field and all seven owned collections were
    compared and needed no write; otherwise it is UPDATE. Defect G3 is
    exactly the whole-object `ALREADY_PRESENT_BY_GUID` skip taken without
    that comparison.

and, restating the same rule at constitution level, Principle IV
(`.specify/memory/constitution.md`, "Per-item disposition"):

    | `SKIP` | Selected and present in target, but all user-editable fields
    are already in sync. Report must distinguish SKIP from IGNORE. |
    ...
    SKIP is determined by field-identity comparison, not merely by GUID
    presence.

T041's half is the non-destructive half of the same principle. Principle IV,
mode vocabulary:

    | `UPDATE` | Write divergent fields from source into the target; never
    blank a target field from an empty source (non-destructive,
    source-preferring). DEFAULT for MULTI_INSTANCE categories. |

and `spec.md` FR-021:

    **FR-021**: Enrichment MUST NOT remove, blank, or overwrite content
    already present in the destination.

WHAT THE DEFECT LOOKS LIKE TODAY. `categories._plan_gold_reserved_edit`
compares exactly three multistring fields -- `Name`, `Abbreviation`,
`Description` -- and then takes one of two whole-object
`Skip(ALREADY_PRESENT_BY_GUID)` exits: one when the source project yields no
writing-system list at all ("cannot prove edit"), one when those three fields
are equal in every writing system. Neither exit has looked at a single owned
collection. A destination `Verb` that carries the right name and none of its
source counterpart's slots, templates, features, sub-categories, stem names,
inflection classes or reference forms is therefore reported as already
present -- the run claims success and the categories arrive hollow. Measured
baseline (SC-007): 3 matched categories, each missing between 3 and 4 WHOLE
collections.

WHY THE TESTS DRIVE `_plan_gold_reserved_edit` DIRECTLY. T043 names it as the
single seam to widen -- "this widens the existing path rather than adding a
parallel enrich path (recorded decision)". Testing the outcome through
`gram_categories_plan_action` as well keeps the seam honest for the caller
POS actually uses.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import categories
from gramtrans.Lib.models import (
    EnrichedCollection,
    EnrichmentRecord,
    GrammarCategory,
    PlannedOverwrite,
    RunContext,
    Skip,
    SkipReason,
    WSMapping,
)


#: The seven owned collections of `IPartOfSpeech`, exactly as data-model.md
#: and T042 enumerate them. `_RC` is a reference collection and the other six
#: are owning collections/sequences; at plan time all seven are compared the
#: same way, so the fakes below model each of them as a plain list.
POS_OWNED_COLLECTIONS = (
    "AffixSlotsOC",
    "AffixTemplatesOS",
    "InflectableFeatsRC",
    "SubPossibilitiesOS",
    "StemNamesOC",
    "InflectionClassesOC",
    "ReferenceFormsOS",
)


# ============================================================================
# Fakes -- no LCM, no flexicon. Same idiom as
# tests/unit/test_017_gold_reserved_edit_copy.py, which is the existing test
# for this very helper; only the owned-collection slots are new.
# ============================================================================

WS_EN = 100
WS_FR = 101


class _FakeTsString:
    def __init__(self, text):
        self.Text = text or None


class _FakeMultiString:
    """Fake ICmMultiString: per-handle text storage."""

    def __init__(self, data: dict):
        self._data = dict(data)

    def get_String(self, ws_handle):
        return _FakeTsString(self._data.get(ws_handle))


class _FakeWsObj:
    def __init__(self, ws_id, handle):
        self.Id = ws_id
        self.Handle = handle


class _FakeWritingSystems:
    def __init__(self, ws_list):
        self._ws = list(ws_list)

    def GetAll(self):
        return list(self._ws)


_WS_LIST = [_FakeWsObj("en", WS_EN), _FakeWsObj("fr", WS_FR)]


class _FakeChild:
    """One owned-collection child -- a slot, template, stem name, inflection
    class, sub-POS, inflectable feature or reference form. Only a GUID and a
    name; the child's own field-level comparison is T044's business, not
    T040's."""

    def __init__(self, guid, name=None):
        self.guid = guid
        self.Guid = guid
        self.Name = _FakeMultiString({WS_EN: name or guid})


class _FakePOS:
    """CmPossibility-shaped Part of Speech carrying all seven owned
    collections. A collection the caller does not name is EMPTY, never
    absent -- an absent attribute would let a comparison pass by accident on
    `getattr(..., None) or ()`, which is precisely the kind of accident these
    tests exist to catch."""

    def __init__(self, guid, name_en=None, name_fr=None, abbr_en=None,
                 desc_en=None, **collections):
        self.guid = guid
        self.Guid = guid
        self.CatalogSourceId = ""
        self.IsProtected = False
        self.Name = _FakeMultiString({WS_EN: name_en, WS_FR: name_fr})
        self.Abbreviation = _FakeMultiString({WS_EN: abbr_en})
        self.Description = _FakeMultiString({WS_EN: desc_en})
        unknown = set(collections) - set(POS_OWNED_COLLECTIONS)
        assert not unknown, f"not a POS owned collection: {sorted(unknown)}"
        for field_name in POS_OWNED_COLLECTIONS:
            setattr(self, field_name, list(collections.get(field_name, ())))

    @property
    def concrete(self):
        return self


class _FakeGramCatOps:
    def __init__(self, items=()):
        self._items = list(items)

    def GetAll(self, recursive=True):
        return list(self._items)


class _FakeSrcProject:
    def __init__(self, pos_items=(), ws_list=None):
        self.POS = _FakeGramCatOps(pos_items)
        self.WritingSystems = _FakeWritingSystems(
            _WS_LIST if ws_list is None else ws_list
        )


class _FakeTgtProject:
    def __init__(self, pos_items=()):
        self.POS = _FakeGramCatOps(pos_items)


def _ctx(src, tgt) -> RunContext:
    return RunContext(
        source_handle=src, source_project_name="Src", source_project_path="/s",
        target_handle=tgt, target_project_name="Tgt", target_project_path="/t",
        run_id="GT-038-T040", started_at="2026-08-20T00:00:00",
    )


WSM = WSMapping(entries=())


@pytest.fixture(autouse=True)
def _patch_guid(monkeypatch):
    """The fakes carry a plain string `guid`; the production helper reads a
    .NET Guid. Same monkeypatch the 017 tests use."""
    monkeypatch.setattr(categories, "_guid_str_from", lambda o: o.guid)


def _plan(src_pos, tgt_pos, ws_list=None):
    """Run `_plan_gold_reserved_edit` for one matched POS pair."""
    src = _FakeSrcProject([src_pos], ws_list=ws_list)
    tgt = _FakeTgtProject([tgt_pos] if tgt_pos is not None else [])
    return categories._plan_gold_reserved_edit(
        src_pos,
        GrammarCategory.GRAM_CATEGORIES,
        _ctx(src, tgt),
        lambda handle: handle.POS.GetAll(recursive=True),
    )


def _enriched(result, field_name) -> EnrichedCollection:
    """The `EnrichedCollection` for `field_name` on a planned enrichment,
    with a failure message that says which of the two things is missing."""
    assert isinstance(result, PlannedOverwrite), (
        "expected an enrichment (PlannedOverwrite, write_mode='merge'), got "
        f"{result!r}"
    )
    record = result.enrichment
    assert isinstance(record, EnrichmentRecord), (
        "an enrichment must carry an EnrichmentRecord so FR-022 can tell it "
        f"apart from a creation; got enrichment={record!r}"
    )
    by_name = {c.field_name: c for c in record.collections}
    assert field_name in by_name, (
        f"{field_name} was not reported among the enriched collections "
        f"{sorted(by_name)}"
    )
    return by_name[field_name]


# ============================================================================
# T040 -- SKIP is field-identity, not GUID presence
# ============================================================================

@pytest.mark.parametrize("field_name", POS_OWNED_COLLECTIONS)
def test_a_matched_pos_missing_one_owned_collection_is_not_skipped(field_name):
    """THE G3 test, once per collection.

    Name, Abbreviation and Description are byte-identical, so the three-field
    loop finds nothing -- and today the helper stops right there and returns
    `Skip(ALREADY_PRESENT_BY_GUID)`. But the destination lacks a child the
    source holds, so a write IS required and SKIP is a false report. Each of
    the seven is parametrised separately because covering six of seven leaves
    a whole collection silently lost, which is the shape of the live defect.
    """
    child = _FakeChild("child-1", "Nominal slot")
    src_pos = _FakePOS("pos-1", name_en="Verb", abbr_en="v",
                       **{field_name: [child]})
    tgt_pos = _FakePOS("pos-1", name_en="Verb", abbr_en="v")

    result = _plan(src_pos, tgt_pos)

    assert not isinstance(result, Skip), (
        f"defect G3: the destination POS holds none of the source's "
        f"{field_name} children, so this is an UPDATE, not a SKIP. A matched "
        f"GUID alone is a LINK (data-model.md:209-213). Got {result!r}"
    )
    assert isinstance(result, PlannedOverwrite)
    assert result.write_mode == "merge"
    assert _enriched(result, field_name).added == 1


@pytest.mark.parametrize("field_name", POS_OWNED_COLLECTIONS)
def test_the_no_writing_system_exit_also_owes_the_collection_comparison(
    field_name,
):
    """The helper's OTHER whole-object skip.

    When the source project yields no writing-system list the helper returns
    `Skip(ALREADY_PRESENT_BY_GUID)` with the detail "no WS info for
    comparison" -- an honest statement that it could not compare the scalar
    fields, turned into a dishonest claim that the object is already present.
    An owned collection needs no writing system to be compared: the child is
    either there by GUID or it is not. T043: the two early skips "may fire
    **only** when that pass also finds nothing".
    """
    src_pos = _FakePOS("pos-2", name_en="Noun",
                       **{field_name: [_FakeChild("child-2")]})
    tgt_pos = _FakePOS("pos-2", name_en="Noun")

    result = _plan(src_pos, tgt_pos, ws_list=[])

    assert not isinstance(result, Skip), (
        "an unavailable writing-system list is a reason the SCALAR comparison "
        f"could not run; it says nothing about {field_name}, which is "
        f"comparable by GUID alone. Got {result!r}"
    )
    assert _enriched(result, field_name).added == 1


def test_a_pos_missing_several_whole_collections_reports_each_of_them():
    """The live shape, not a single-collection toy: SC-007's measured
    baseline is "3 matched categories, each missing between 3 and 4 whole
    collections". Reporting only the first one found would let the rest go
    unaccounted, which SC-010 forbids."""
    src_pos = _FakePOS(
        "pos-3", name_en="Verb",
        AffixSlotsOC=[_FakeChild("slot-1"), _FakeChild("slot-2")],
        AffixTemplatesOS=[_FakeChild("tmpl-1")],
        InflectionClassesOC=[_FakeChild("iclass-1")],
        StemNamesOC=[_FakeChild("stem-1")],
    )
    tgt_pos = _FakePOS("pos-3", name_en="Verb")

    result = _plan(src_pos, tgt_pos)

    assert _enriched(result, "AffixSlotsOC").added == 2
    assert _enriched(result, "AffixTemplatesOS").added == 1
    assert _enriched(result, "InflectionClassesOC").added == 1
    assert _enriched(result, "StemNamesOC").added == 1


def test_a_partially_populated_collection_is_still_an_update():
    """The destination has ONE of the source's two slots. "Present" is not
    "complete", and the second slot is exactly the child SC-007 counts."""
    shared = _FakeChild("slot-shared")
    src_pos = _FakePOS("pos-4", name_en="Verb",
                       AffixSlotsOC=[shared, _FakeChild("slot-new")])
    tgt_pos = _FakePOS("pos-4", name_en="Verb",
                       AffixSlotsOC=[_FakeChild("slot-shared")])

    result = _plan(src_pos, tgt_pos)

    collection = _enriched(result, "AffixSlotsOC")
    assert collection.added == 1
    assert collection.already_present == 1, (
        "the child matched by GUID was compared and needed no write; it is "
        "already_present, and it is NOT counted as added"
    )


def test_skip_is_legitimate_only_once_all_seven_compared_equal():
    """The other side of the clause, and the reason it is a NARROWING rather
    than a removal. Every scalar field AND all seven collections match, so
    nothing needs writing and `Skip(ALREADY_PRESENT_BY_GUID)` is the honest
    answer. T043 must not make the skip unreachable."""
    children = {name: [_FakeChild(f"{name}-child")]
                for name in POS_OWNED_COLLECTIONS}
    src_pos = _FakePOS("pos-5", name_en="Verb", abbr_en="v", desc_en="d",
                       **children)
    tgt_pos = _FakePOS(
        "pos-5", name_en="Verb", abbr_en="v", desc_en="d",
        **{name: [_FakeChild(f"{name}-child")]
           for name in POS_OWNED_COLLECTIONS}
    )

    result = _plan(src_pos, tgt_pos)

    assert isinstance(result, Skip), (
        "with every scalar field and all seven collections compared equal "
        f"there is nothing to write, so SKIP is correct here. Got {result!r}"
    )
    assert result.reason is SkipReason.ALREADY_PRESENT_BY_GUID


def test_an_absent_pos_is_still_a_create_not_an_enrichment():
    """Guard on the widened path: enrichment acts on an object that already
    exists. No GUID hit -> `None`, and the caller emits a `PlannedAction`.
    `EnrichmentRecord.was_created` is False by construction for the same
    reason (FR-022)."""
    src_pos = _FakePOS("pos-6", name_en="Verb",
                       AffixSlotsOC=[_FakeChild("slot-x")])

    assert _plan(src_pos, None) is None


def test_the_pos_caller_sees_the_same_decision_as_the_helper():
    """`gram_categories_plan_action` is the entry point POS actually uses
    (POS is aliased to GRAM_CATEGORIES). Widening the helper is worth nothing
    if the caller re-derives its own answer."""
    src_pos = _FakePOS("pos-7", name_en="Verb",
                       SubPossibilitiesOS=[_FakeChild("subpos-1")])
    tgt_pos = _FakePOS("pos-7", name_en="Verb")

    result = categories.gram_categories_plan_action(
        src_pos,
        _ctx(_FakeSrcProject([src_pos]), _FakeTgtProject([tgt_pos])),
        WSM,
    )

    assert not isinstance(result, Skip), (
        f"the caller must inherit the widened decision, got {result!r}"
    )
    assert _enriched(result, "SubPossibilitiesOS").added == 1


# ============================================================================
# T041 -- enrichment is non-destructive (FR-021, Principle IV `update`)
# ============================================================================

def test_an_enrichment_is_never_planned_with_overwrite_semantics():
    """FR-021 in one assertion. `overwrite` is defined by Principle IV as
    "source wins on every field, INCLUDING blanking a target field when the
    source field is empty" -- which is the one thing enrichment may never do.
    `merge` is the constitution's `update`: source where non-empty, target
    where source empty."""
    src_pos = _FakePOS("pos-10", name_en="Verb",
                       AffixSlotsOC=[_FakeChild("slot-1")])
    tgt_pos = _FakePOS("pos-10", name_en="Verb")

    result = _plan(src_pos, tgt_pos)

    assert isinstance(result, PlannedOverwrite)
    assert result.write_mode == "merge", (
        "an enrichment carried as write_mode='overwrite' permits blanking, "
        "forbidden by FR-021"
    )
    assert result.enrichment is not None


@pytest.mark.parametrize("field_name", POS_OWNED_COLLECTIONS)
def test_a_destination_only_child_is_never_dropped(field_name):
    """"...and loses none of its own" (SC-007). The destination holds a child
    the source has never heard of -- local work by the target's own team. An
    enrichment adds beside it; it does not reconcile the collection to the
    source's contents."""
    tgt_own = _FakeChild("child-local", "local work")
    src_pos = _FakePOS("pos-11", name_en="Verb",
                       **{field_name: [_FakeChild("child-src")]})
    tgt_pos = _FakePOS("pos-11", name_en="Verb", **{field_name: [tgt_own]})

    result = _plan(src_pos, tgt_pos)

    collection = _enriched(result, field_name)
    assert collection.added == 1
    assert collection.dropped == 0, (
        f"the destination's own {field_name} child must survive; a planned "
        "drop here is the removal FR-021 forbids"
    )
    assert tgt_own in getattr(tgt_pos, field_name), (
        "the PLANNER must not mutate the destination at all -- Principle III "
        "separates Preview from Move"
    )


@pytest.mark.parametrize("field_name", POS_OWNED_COLLECTIONS)
def test_an_empty_source_collection_never_blanks_a_populated_target(
    field_name,
):
    """Principle IV's `update`, restated for collections: "never blank a
    target field from an empty source". Nothing is added and nothing is
    dropped, so with the scalars equal too this is a legitimate SKIP -- and
    it must NOT become an overwrite that empties the destination."""
    tgt_children = [_FakeChild("keep-1"), _FakeChild("keep-2")]
    src_pos = _FakePOS("pos-12", name_en="Verb")
    tgt_pos = _FakePOS("pos-12", name_en="Verb",
                       **{field_name: list(tgt_children)})

    result = _plan(src_pos, tgt_pos)

    if isinstance(result, PlannedOverwrite):
        assert result.write_mode == "merge"
        for collection in (result.enrichment.collections
                           if result.enrichment else ()):
            assert collection.dropped == 0
    else:
        assert isinstance(result, Skip)
        assert result.reason is SkipReason.ALREADY_PRESENT_BY_GUID
    assert getattr(tgt_pos, field_name) == tgt_children, (
        f"the destination's {field_name} must be untouched by an empty source"
    )


def test_an_empty_source_scalar_never_blanks_a_populated_target_field():
    """The scalar half of the same rule, and a guard on T043: widening the
    helper to collections must not disturb the writing-system comparison that
    already honours it. The source has no French name; the destination has
    one, and keeps it."""
    src_pos = _FakePOS("pos-13", name_en="Verb")
    tgt_pos = _FakePOS("pos-13", name_en="Verb", name_fr="Verbe")

    result = _plan(src_pos, tgt_pos)

    assert isinstance(result, Skip), (
        "an empty source slot is not a gap and not a divergence; there is "
        f"nothing to write. Got {result!r}"
    )
    assert tgt_pos.Name.get_String(WS_FR).Text == "Verbe"


def test_enrichment_appends_and_does_not_reorder_an_owning_sequence():
    """`AffixTemplatesOS` is an ORDERED sequence and the order is meaningful.
    The destination already holds the source's second template at index 0;
    the first is new. "Never destructively reorder" (T045) means the existing
    child keeps its position and the new one arrives beside it -- it does NOT
    mean the destination is re-sorted into source order."""
    tgt_existing = _FakeChild("tmpl-b", "Template B")
    src_pos = _FakePOS(
        "pos-14", name_en="Verb",
        AffixTemplatesOS=[_FakeChild("tmpl-a", "Template A"),
                          _FakeChild("tmpl-b", "Template B")],
    )
    tgt_pos = _FakePOS("pos-14", name_en="Verb",
                       AffixTemplatesOS=[tgt_existing])

    result = _plan(src_pos, tgt_pos)

    collection = _enriched(result, "AffixTemplatesOS")
    assert collection.added == 1
    assert collection.already_present == 1
    assert collection.dropped == 0
    assert tgt_pos.AffixTemplatesOS[0] is tgt_existing, (
        "the destination's existing template must keep index 0; re-sorting "
        "the sequence into source order is the destructive reorder FR-021 "
        "and T045 forbid"
    )


def test_an_enrichment_reports_itself_as_not_created():
    """FR-022: "The run report MUST distinguish an enriched item from a
    created one." The record says so in a field rather than leaving a report
    reader to infer it from the absence of a `PlannedAction`."""
    src_pos = _FakePOS("pos-15", name_en="Verb",
                       InflectableFeatsRC=[_FakeChild("feat-1")])
    tgt_pos = _FakePOS("pos-15", name_en="Verb")

    result = _plan(src_pos, tgt_pos)

    assert isinstance(result, PlannedOverwrite)
    record = result.enrichment
    assert isinstance(record, EnrichmentRecord)
    assert record.was_created is False
    assert record.source_guid == "pos-15"
    assert record.target_guid == "pos-15"
    assert record.is_empty is False, (
        "a record with something added is not empty; only an empty one may "
        "degrade to a Skip (data-model.md section 7)"
    )
