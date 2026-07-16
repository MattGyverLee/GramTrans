"""Unit tests for feature 029 (Sense Pictures): the backing-image ASSET copy
seam -- copy on ADD, reuse of a byte-identical target file (dedup), copy under
a de-duplicated name on a same-name/different-content collision, and the
never-silent filesystem failure reports (missing / unreadable / unwritable) --
all host-free via a faked `AddPicture`/`RenamePicture` seam plus real temp
files (no live FLEx host).

See:
- specs/029-sense-pictures/spec.md (US2/US3/US4)
- specs/029-sense-pictures/contracts/sense-picture-reproduction.md
- specs/029-sense-pictures/research.md (R2/R3/R5)

T003 SCAFFOLD (Phase 1): import-smoke only -- assert the module and its private
asset-copy seam helpers import cleanly. The RED-before-GREEN tests are authored
per user story: US2 (T010), US4 (T013), US3 (T018).
"""

from gramtrans.Lib import pictures


def test_029_asset_seam_helpers_present():
    """T005 adds the private asset-copy seam helpers. Import-smoke: they exist
    and are callable."""
    assert callable(pictures._content_hash)
    assert callable(pictures._source_image_path)
    assert callable(pictures._resolve_target_collision)


def test_029_content_hash_of_missing_file_is_empty():
    """`_content_hash` never raises: a missing/unreadable path -> "" (the
    signal the missing-binary fallback keys on, R5)."""
    assert pictures._content_hash("/no/such/file/at/all.jpg") == ""
    assert pictures._content_hash(None) == ""
