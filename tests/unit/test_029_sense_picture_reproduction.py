"""Unit tests for feature 029 (Sense Pictures): reproduction of the owned
`CmPicture` object graph on a copied sense -- caption/description multistrings
(ws-mapped), the five layout scalars, source `PicturesOS` order -- plus the
Preview/Move parity, idempotency (structural fingerprint), and empty-source
no-blank guarantees.

(The backing-image asset copy / reuse / rename / missing-binary report legs
live in `test_029_picture_asset_copy.py`.)

See:
- specs/029-sense-pictures/spec.md (US1/US4/US5)
- specs/029-sense-pictures/contracts/sense-picture-reproduction.md
- specs/029-sense-pictures/data-model.md

T002 SCAFFOLD (Phase 1): import-smoke only -- assert the module under test and
both entry points import cleanly. The RED-before-GREEN tests are authored per
user story: US1 (T007), US5 (T016).
"""

from gramtrans.Lib import categories, pictures
from gramtrans.Lib.models import ReferenceAction, ReferenceDecisionRecord


def test_029_module_entry_points_present():
    """T005 adds the Move leg (`reproduce_sense_pictures`) and its read-only
    Preview twin (`plan_sense_picture_decisions`). Import-smoke: the module and
    both entry points exist and are callable."""
    assert callable(pictures.reproduce_sense_pictures)
    assert callable(pictures.plan_sense_picture_decisions)


def test_029_empty_source_is_vacuous():
    """G2 skeleton contract: an absent/empty source `PicturesOS` is a no-op for
    the Move leg and yields no decisions for the Preview twin (no crash)."""

    class _NoPictures:
        PicturesOS = ()

    dropped: list = []
    pictures.reproduce_sense_pictures(
        _NoPictures(), _NoPictures(), None, None, {}, dropped)
    assert dropped == []
    assert pictures.plan_sense_picture_decisions(_NoPictures(), None, {}, []) == []


# ============================================================================
# T006 -- the Preview closure walk routes each sense through the 029 seam.
# ============================================================================

class _FakeMultiString:
    def __init__(self, data=None):
        self._data = dict(data or {})


class _FakeSense:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid
        self.ClassName = "LexSense"
        self.Gloss = _FakeMultiString()
        self.AppendixesRC = []
        self.ThesaurusItemsRC = []
        self.PicturesOS = []
        self.ExamplesOS = []
        self.SensesOS = []
        self.ExtendedNoteOS = []


class _FakeEntry:
    def __init__(self, guid, senses):
        self.Guid = guid
        self.guid = guid
        self.SensesOS = list(senses)
        self.LexemeFormOA = None
        self.AlternateFormsOS = []


class _FakeCtx:
    def __init__(self):
        self.source_handle = object()
        self.target_handle = object()


def test_029_preview_walk_routes_sense_through_picture_seam(monkeypatch):
    """T006: `_plan_entry_reference_decisions` calls
    `pictures.plan_sense_picture_decisions` for each sense and folds its
    decisions into the returned reference-decision set (feeding
    `PlannedAction.reference_decisions`)."""
    seen = []
    sentinel = ReferenceDecisionRecord(
        owner_kind="LexSense", owner_guid="sense-t006",
        field_name="PicturesOS", action=ReferenceAction.CREATE,
        item_name="a picture", item_guid="pic-t006",
    )

    def _fake_plan(src_sense, ctx, resolver_cache, dropped):
        seen.append(src_sense.guid)
        return [sentinel]

    monkeypatch.setattr(pictures, "plan_sense_picture_decisions", _fake_plan)

    sense = _FakeSense("sense-t006")
    entry = _FakeEntry("entry-t006", [sense])
    ctx = _FakeCtx()
    ctx._dropped = []

    records = categories._plan_entry_reference_decisions(entry, ctx, target=object())

    assert "sense-t006" in seen
    assert sentinel in records
