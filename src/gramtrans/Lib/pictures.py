"""Feature 029 (Sense Pictures) -- reproduce a copied sense's owned pictures.

Closes the 024-census `DROP_REPORTED` gap for `LexSense.PicturesOS`: when a
sense is copied by the STEMS/AFFIXES transfer, reproduce each owned `CmPicture`
(caption/description multistrings + layout scalars, in source order) **and**
copy its backing image asset into the target project's `LinkedFiles` picture
folder so the picture displays -- all under 024's never-silent guarantee.

Two public entry points, mirroring the 028
`owned.reproduce_moaffix_msenv_data` / `_plan_moaffix_msenv_decisions` pair:

- ``reproduce_sense_pictures(...)`` -- the Move leg (writes target + files).
- ``plan_sense_picture_decisions(...)`` -- its read-only Preview twin
  (Principle III): the same ADD/LINK decision + identical drop set, by
  construction, computed without writing anything or copying any file.

Structure decision (plan.md): this is a NEW module, separate from the
object-graph modules (`categories.py`/`owned.py`), because the novel concern
is **filesystem/asset** logic -- content hashing, `LinkedFiles` path
resolution, collision renaming, missing-file handling. That I/O is isolated
here so the whole feature is unit-testable host-free: the asset-copy seam is a
faked ``ctx.target_handle.Senses`` (a stubbed ``AddPicture``/``RenamePicture``)
plus real temp files for the hash/collision logic.

flexicon surface (live-confirmed via FLExToolsMCP on `Ejagham Mini`, R2/R3):
- ``project.Senses.AddPicture(sense, image_path, caption, wsHandle) -> ICmPicture``
  copies the image into the target LinkedFiles/Pictures folder and wires the
  ``CmFile`` in one call; raises ``FP_ParameterError`` if the file is absent
  (so the missing-binary case routes through the raw-factory fallback, R5) and
  sets only the caption (so layout scalars are set on the returned picture
  afterward, R2 sub-question c).
- ``project.Senses.RenamePicture(picture, new_filename) -> str`` for the
  de-duplicated collision copy (R3).
- ``project.GetLinkedFilesDir() -> str`` resolves each project's LinkedFiles
  root (source path resolution + target collision scan).

Module posture (contract G7): every per-picture / per-file failure is caught
and reported via a ``DroppedItemRecord`` -- this module MUST never raise.
"""
from __future__ import annotations

import hashlib
import os
import shutil

if __package__:
    from .models import (
        DroppedItemRecord, ReferenceAction, ReferenceDecisionRecord,
    )
    from . import references as _references
else:  # pragma: no cover - exercised only under the FlexTools sys.path convention
    from models import (  # type: ignore
        DroppedItemRecord, ReferenceAction, ReferenceDecisionRecord,
    )
    import references as _references  # type: ignore


# The five layout scalars carried verbatim (data-model.md / research R1). Enum
# and Int32 values copy directly (no WS mapping); `Caption`/`Description` are
# multistrings copied ws-mapped (see `_copy_picture_multistrings`).
_LAYOUT_SCALARS = (
    "LayoutPos", "LocationMin", "LocationMax", "LocationRangeType", "ScaleFactor",
)
_MULTISTRING_FIELDS = ("Caption", "Description")

_FIELD_NAME = "PicturesOS"
_OWNER_KIND = "LexSense"


# ============================================================================
# Casts (live host: the MCP-confirmed `requires_cast` for all 13 ICmPicture /
# 6 ICmFile props; host-free pass-through for the unit-test fakes -- same idiom
# as `owned._cast_moaffix_allomorph` / `transfer._cast_existing_to_*`).
# ============================================================================

def _cast_picture(obj):
    try:
        from SIL.LCModel import ICmPicture
        return ICmPicture(obj)
    except Exception:
        return obj


def _cast_file(obj):
    try:
        from SIL.LCModel import ICmFile
        return ICmFile(obj)
    except Exception:
        return obj


# ============================================================================
# Never-silent report helper (same dedup identity key as
# `categories._append_dropped_once` / `owned._append_dropped`).
# ============================================================================

def _dropped_key(record) -> tuple:
    return (record.owner_guid, record.field_name, record.item_guid)


def _append_dropped(dropped, record) -> None:
    if dropped is None:
        return
    key = _dropped_key(record)
    for existing in dropped:
        if _dropped_key(existing) == key:
            return
    dropped.append(record)


# ============================================================================
# Private asset-copy seam (T005 stubs; filled in by US2-US5).
# ============================================================================

def _content_hash(path) -> str:
    """SHA-256 of the file at `path`, or "" when it cannot be read (missing /
    unreadable). Never raises."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, TypeError):
        return ""


def _source_image_path(src_cmfile, source_handle):
    """Resolve the absolute source image path for a picture's `CmFile` --
    `AbsoluteInternalPath` when set, else `source LinkedFilesRootDir` joined
    with `InternalPath`. Returns "" when unresolvable. Never raises."""
    if src_cmfile is None:
        return ""
    try:
        abspath = getattr(src_cmfile, "AbsoluteInternalPath", None)
        if abspath:
            return abspath
        internal = getattr(src_cmfile, "InternalPath", None)
        if not internal:
            return ""
        root = ""
        try:
            root = source_handle.GetLinkedFilesDir()
        except (AttributeError, TypeError):
            root = ""
        return os.path.join(root, internal) if root else internal
    except (AttributeError, TypeError):
        return ""


def _resolve_target_collision(source_path, target_folder):
    """T005 stub (US3, T019). Decide the non-destructive destination for
    `source_path` in `target_folder`: reuse an identical existing file, copy
    under a de-duplicated name for a same-name/different-content clash, or a
    plain copy when there is no collision. Returns a decision tuple; the
    skeleton returns the no-collision plain-copy shape."""
    return ("copy", os.path.basename(source_path or ""), None)


# ============================================================================
# Move leg (T005 skeleton; grown by US1-US5).
# ============================================================================

def reproduce_sense_pictures(src_sense, new_sense, ctx, tag, resolver_cache,
                             dropped) -> None:
    """Move leg -- reproduce every `CmPicture` in `src_sense.PicturesOS` onto
    `new_sense`, in source order, copying each backing image asset into the
    target LinkedFiles folder (contract entry point; guarantees G1-G7).

    T005 skeleton: empty/absent source `PicturesOS` returns with no effect
    (G2); the per-picture reproduce/asset legs land in US1-US5. MUST never
    raise -- every per-picture failure is caught and reported."""
    try:
        src_pictures = list(getattr(src_sense, _FIELD_NAME, None) or [])
    except (AttributeError, TypeError):
        return
    if not src_pictures:
        return
    # --- per-picture reproduce legs land here (US1-US5) ---


# ============================================================================
# Preview twin -- read-only (T005 skeleton; grown by US1-US5).
# ============================================================================

def plan_sense_picture_decisions(src_sense, ctx, resolver_cache, dropped) -> list:
    """Read-only Preview twin of `reproduce_sense_pictures` (Principle III):
    emit the ADD/LINK `ReferenceDecisionRecord` the Move leg will act on for
    each source picture, plus the identical `DroppedItemRecord` set -- by
    construction, computed without writing anything or copying any file.

    T005 skeleton: empty/absent source `PicturesOS` returns []. Never writes;
    never raises."""
    records: list = []
    try:
        src_pictures = list(getattr(src_sense, _FIELD_NAME, None) or [])
    except (AttributeError, TypeError):
        return records
    if not src_pictures:
        return records
    # --- per-picture decision legs land here (US1-US5) ---
    return records
