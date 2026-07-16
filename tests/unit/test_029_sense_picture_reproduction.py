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

from gramtrans.Lib import pictures


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
