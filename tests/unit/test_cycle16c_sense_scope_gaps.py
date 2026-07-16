"""Write-first unit tests for the cycle-17 lead correction (fidelity census
correction -- a prior lead ruling wrongly parked 4 LexSense fields in a
SILENT `OUT_OF_SCOPE_EXCLUDED` bucket; the 024 spec forbids silent exclusion
(SC-003/FR-010: "NOTHING is silently lost")).

Corrected terminal buckets (this cycle):

- `LexSense.ExtendedNoteOS` -> COPIED. Reproduced via `Lib/owned.py`'s
  `OWNED_OBJECT_MAP` (`ILexExtendedNoteFactory`, UNOWNED_THEN_ADD), its own
  `ExamplesOS` recursed through the SAME example-reproduction machinery
  `LexSense.ExamplesOS` already uses (`_EXAMPLE_REF_SPECS`), and its
  `ExtendedNoteTypeRA` resolved against `lp.LexDbOA.ExtendedNoteTypesOA` via
  the generic resolver (`references.REFERENCE_FIELD_MAP`). Covered by
  `tests/unit/test_owned_object_walk.py`'s
  `test_extended_note_reproduced_with_examples_and_type_resolved`.

- `LexSense.AppendixesRC` -> DROP_REPORTED. `LexAppendix` is a bespoke owned
  class in `LexDb.AppendixesOC` (NOT a possibility list -- the generic
  resolver does not apply). Never reproduced; one `DroppedItemRecord` per
  referenced appendix. Routed to 030-sense-appendix-thesaurus-refs.

- `LexSense.ThesaurusItemsRC` -> DROP_REPORTED. Generic `CmPossibility` with
  no fixed home list (legacy, dynamic-owner) -- never reproduced. Routed to
  030-sense-appendix-thesaurus-refs.

- `LexSense.PicturesOS` -> DROP_REPORTED. Owns `CmPicture` -> `CmFile` ->
  disk file -- never reproduced (no `CmPicture`/`CmFile` created, no file
  copied). Routed to 029-sense-pictures.

Both the AppendixesRC/ThesaurusItemsRC/PicturesOS drop emission
(`categories._report_dropped_sense_scope_gaps`) and the ExtendedNote
reproduction are called identically from Move
(`_walk_lex_entry_closure`'s sense loop) and Preview
(`_plan_entry_reference_decisions`'s sense loop) -- this file's parity test
proves that construction holds for the drop-reporting side; the
reproduction side has no CREATE/LINK divergence risk since it goes through
the SAME `walk_owned_children`/`plan_owned_object_decisions` twin already
proven identical elsewhere.

Ejagham Mini note: all four fields are vacuous (0 populated) on Ejagham
Mini -- these tests are fakes-only this cycle; live proof deferred to the
T037-class fixture posture already accepted for lexrel/affix-MsEnv.
"""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


WS_EN = 100


# ============================================================================
# Small shared fakes
# ============================================================================

class _FakeMultiString:
    """Fake ICmMultiString -- `_multistring_dict`'s `_data`-dict fallback."""

    def __init__(self, data: dict | None = None) -> None:
        self._data = dict(data or {})


class _FakeGuidObj:
    def __init__(self, guid, name=""):
        self.Guid = guid
        self.guid = guid
        self.Name = _FakeMultiString({WS_EN: name} if name else {})


class _FakeAppendix(_FakeGuidObj):
    """Fake ILexAppendix -- no `.Name` (only `ContentsOA`), so
    `_references_item_label` must fail soft to ""."""

    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid
        # Deliberately NO `.Name` attribute -- matches the real
        # `ILexAppendix` (only `ContentsOA : IStText`).


class _FakePicture(_FakeGuidObj):
    """Fake ICmPicture -- no `.Name` (only `Caption`/`Description`)."""

    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeSourceSense(_FakeGuidObj):
    """Fake ILexSense -- just enough surface for
    `_report_dropped_sense_scope_gaps` / `_plan_entry_reference_decisions`
    to run without a live LCM host."""

    def __init__(self, guid, gloss="", appendixes=(), thesaurus_items=(),
                 pictures=()):
        self.Guid = guid
        self.guid = guid
        self.ClassName = "LexSense"
        self.Gloss = _FakeMultiString({WS_EN: gloss} if gloss else {})
        self.AppendixesRC = list(appendixes)
        self.ThesaurusItemsRC = list(thesaurus_items)
        self.PicturesOS = list(pictures)
        self.ExamplesOS = []
        self.SensesOS = []
        self.ExtendedNoteOS = []


class _FakeSourceEntry(_FakeGuidObj):
    def __init__(self, guid, senses=()):
        self.Guid = guid
        self.guid = guid
        self.SensesOS = list(senses)
        self.LexemeFormOA = None
        self.AlternateFormsOS = []


# ============================================================================
# (a) LexSense.AppendixesRC -- DROP_REPORTED
# ============================================================================

def test_appendix_emits_one_dropped_record_per_referenced_appendix():
    ap1 = _FakeAppendix("appendix-1")
    ap2 = _FakeAppendix("appendix-2")
    sense = _FakeSourceSense("sense-1", gloss="headword-1",
                              appendixes=[ap1, ap2])

    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)

    assert {r.item_guid for r in dropped} == {"appendix-1", "appendix-2"}
    assert len(dropped) == 2
    for rec in dropped:
        assert isinstance(rec, DroppedItemRecord)
        assert rec.owner_kind == "LexSense"
        assert rec.owner_guid == "sense-1"
        assert rec.field_name == "AppendixesRC"
        assert "030-sense-appendix-thesaurus-refs" in rec.reason


# ============================================================================
# (b) LexSense.ThesaurusItemsRC -- DROP_REPORTED
# ============================================================================

def test_thesaurus_item_emits_one_dropped_record_per_referenced_item():
    ti1 = _FakeGuidObj("thes-1", name="Animal")
    sense = _FakeSourceSense("sense-2", thesaurus_items=[ti1])

    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)

    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.owner_kind == "LexSense"
    assert rec.field_name == "ThesaurusItemsRC"
    assert rec.item_guid == "thes-1"
    assert rec.item_name == "Animal"
    assert "030-sense-appendix-thesaurus-refs" in rec.reason


# ============================================================================
# (c) LexSense.PicturesOS -- feature 029: NO LONGER drop-reported here.
#     `_report_dropped_sense_scope_gaps` reports only AppendixesRC /
#     ThesaurusItemsRC (routed to 030); PicturesOS is reproduced by the
#     `pictures.reproduce_sense_pictures` / `plan_sense_picture_decisions`
#     seam, so it must be REMOVED from `_SENSE_SCOPE_GAP_FIELDS` (T006).
# ============================================================================

def test_picture_no_longer_reported_by_scope_gap_function():
    """T006: after wiring the 029 seam, `_report_dropped_sense_scope_gaps`
    emits NO drop for `PicturesOS` (a sense owning only pictures produces an
    empty drop set from this function -- the pictures route through the new
    seam instead)."""
    pic1 = _FakePicture("pic-1")
    pic2 = _FakePicture("pic-2")
    pic3 = _FakePicture("pic-3")
    sense = _FakeSourceSense("sense-3", pictures=[pic1, pic2, pic3])

    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)

    assert dropped == []
    assert "PicturesOS" not in dict(categories._SENSE_SCOPE_GAP_FIELDS)


# ============================================================================
# No scope-gap fields populated -- emits nothing.
# ============================================================================

def test_sense_with_no_scope_gap_fields_emits_nothing():
    sense = _FakeSourceSense("sense-4")

    dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, dropped)

    assert dropped == []


# ============================================================================
# Move + Preview parity: same drop set for all three scope-gap fields.
# ============================================================================

class _FakeRunContext:
    """Minimal ctx surface `_plan_entry_reference_decisions` needs: no live
    LCM host required (every internal call it makes is fail-soft/duck-typed
    against an object this bare)."""

    def __init__(self, source_handle):
        self.source_handle = source_handle
        self.target_handle = object()


def test_move_and_preview_drop_sets_identical_for_sense_scope_gaps():
    """`_report_dropped_sense_scope_gaps` (the Move call site's function)
    and `_plan_entry_reference_decisions` (the actual Preview entrypoint,
    which calls the SAME function internally for each sense) must produce
    the identical scope-gap drop set for the same source entry/sense."""
    ap1 = _FakeAppendix("appendix-parity")
    ti1 = _FakeGuidObj("thes-parity", name="Parity Item")
    # A picture is present on the sense but is NO LONGER a scope-gap drop
    # (feature 029 reproduces it) -- the parity set is AppendixesRC +
    # ThesaurusItemsRC only.
    pic1 = _FakePicture("pic-parity")
    sense = _FakeSourceSense(
        "sense-parity", gloss="parity-word",
        appendixes=[ap1], thesaurus_items=[ti1], pictures=[pic1])
    entry = _FakeSourceEntry("entry-parity", senses=[sense])

    move_dropped: list = []
    categories._report_dropped_sense_scope_gaps(sense, move_dropped)

    preview_dropped: list = []
    ctx = _FakeRunContext(source_handle=object())
    ctx._dropped = preview_dropped
    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    def _scope_gap_fields(records):
        return sorted(
            (r.owner_guid, r.field_name, r.item_guid, r.item_name, r.reason)
            for r in records
            if r.field_name in ("AppendixesRC", "ThesaurusItemsRC", "PicturesOS")
        )

    assert _scope_gap_fields(move_dropped) == _scope_gap_fields(preview_dropped)
    assert len(move_dropped) == 2  # AppendixesRC + ThesaurusItemsRC (PicturesOS -> 029)
