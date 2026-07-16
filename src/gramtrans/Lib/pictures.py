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
# Small read helpers (host-free; SIL-optional).
# ============================================================================

def _source_handle(ctx):
    return getattr(ctx, "source_handle", None) if ctx is not None else None


def _target_handle(ctx):
    return getattr(ctx, "target_handle", None) if ctx is not None else None


def _guid_str(obj) -> str:
    try:
        return _references._guid_str(obj)
    except Exception:
        return ""


def _picture_owner_label(src_sense) -> str:
    try:
        return _references._item_label(src_sense) or ""
    except Exception:
        return ""


def _read_text(tss) -> str:
    """`.Text` off an ITsString (live) or a plain str (offline fakes), never
    the `***` empty placeholder."""
    text = getattr(tss, "Text", tss)
    if text is None or text == "***":
        return ""
    return text


def _best_multistring_text(multistr, source_handle) -> str:
    """Best non-empty alternative of a source multistring, read across the
    source project's writing-system handles. "" when none / unreadable."""
    if multistr is None:
        return ""
    try:
        for ws in source_handle.WritingSystems.GetAll():
            text = _read_text(multistr.get_String(ws.Handle))
            if text:
                return text
    except (AttributeError, TypeError):
        pass
    return ""


def _picture_label(src_pic, ctx) -> str:
    """Best-effort display label for a picture -- its caption, else "" (a
    `CmPicture` has no `.Name`)."""
    return _best_multistring_text(
        getattr(src_pic, "Caption", None), _source_handle(ctx))


def _report_picture_dropped(dropped, src_sense, src_pic, reason, ctx=None) -> None:
    _append_dropped(dropped, DroppedItemRecord(
        owner_kind=_OWNER_KIND,
        owner_guid=_guid_str(src_sense),
        owner_label=_picture_owner_label(src_sense),
        field_name=_FIELD_NAME,
        item_name=_picture_label(src_pic, ctx),
        item_guid=_guid_str(src_pic),
        reason=reason,
    ))


# ============================================================================
# Object-graph copy (US1): caption/description ws-mapped + layout scalars.
# ============================================================================

def _copy_picture_multistrings(src_pic, new_pic, ctx) -> None:
    """Copy `Caption`/`Description` across all writing systems, ws-mapped, via
    024's `categories._copy_multistrings_ws_mapped` (source->target handle
    translation). Lazy import to avoid a module load-order cycle."""
    source = _source_handle(ctx)
    target = _target_handle(ctx)
    if source is None or target is None:
        return
    ws_map = getattr(ctx, "_ws_map", None)
    if __package__:
        from . import categories as _categories
    else:  # pragma: no cover
        import categories as _categories  # type: ignore
    try:
        _categories._copy_multistrings_ws_mapped(
            src_pic, new_pic, _MULTISTRING_FIELDS,
            source=source, target=target, ws_map=ws_map)
    except (AttributeError, TypeError):
        pass


def _copy_layout_scalars(src_pic, new_pic) -> None:
    """Copy the five layout scalars (enum/Int32) verbatim -- cast both sides to
    `ICmPicture` on the live host (pass-through offline)."""
    src = _cast_picture(src_pic)
    dst = _cast_picture(new_pic)
    for name in _LAYOUT_SCALARS:
        try:
            value = getattr(src, name)
        except (AttributeError, TypeError):
            continue
        try:
            setattr(dst, name, value)
        except (AttributeError, TypeError):
            pass


_ASSET_CACHE_KEY = "_picture_asset_cache"


def _asset_cache(ctx) -> dict:
    """Per-run content-hash -> target-`CmFile` dedup cache (SC-005). Stored on
    `ctx` (mirrors `_copy_set`/`_ws_map`), so an image shared by K pictures is
    copied once and its `CmFile` reused."""
    if ctx is None:
        return {}
    cache = getattr(ctx, _ASSET_CACHE_KEY, None)
    if cache is None:
        cache = {}
        try:
            object.__setattr__(ctx, _ASSET_CACHE_KEY, cache)
        except (AttributeError, TypeError):
            pass
    return cache


def _target_pictures_dir(ctx) -> str:
    """The target project's `LinkedFiles/Pictures` folder, or "" when
    unresolvable. Never raises."""
    target = _target_handle(ctx)
    try:
        root = target.GetLinkedFilesDir()
    except (AttributeError, TypeError):
        return ""
    if not root:
        return ""
    return os.path.join(root, "Pictures")


def _target_identical_file(source_path, ctx):
    """Return the absolute path of a byte-identical file already in the target
    Pictures folder (content-hash match), else "". Read-only; never raises."""
    src_hash = _content_hash(source_path)
    if not src_hash:
        return ""
    folder = _target_pictures_dir(ctx)
    if not folder or not os.path.isdir(folder):
        return ""
    try:
        for name in os.listdir(folder):
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate) and _content_hash(candidate) == src_hash:
                return candidate
    except OSError:
        pass
    return ""


# ---- raw ICmPictureFactory / ICmFileFactory path (dedup reuse + US4 fallback)

def _get_service(ctx, iface_name):
    """Resolve an LCM factory by interface name via `target.GetService`. On a
    live host imports the real interface from `SIL.LCModel`; host-free tests
    serve a fake via `GetService("ICmPictureFactory")` (string key). None when
    unavailable. Never raises."""
    target = _target_handle(ctx)
    getsvc = getattr(target, "GetService", None)
    if getsvc is None:
        return None
    try:
        import SIL.LCModel as _lcm
        return getsvc(getattr(_lcm, iface_name))
    except Exception:
        try:
            return getsvc(iface_name)
        except Exception:
            return None


def _append_owned_picture(new_sense, picture) -> None:
    coll = getattr(new_sense, "PicturesOS", None)
    if coll is None:
        return
    add = getattr(coll, "Add", None)
    if callable(add):
        try:
            add(picture)
            return
        except (AttributeError, TypeError):
            pass
    try:
        coll.append(picture)
    except (AttributeError, TypeError):
        pass


def _set_cmfile_internal_path(cmfile, internal_path) -> None:
    if not internal_path:
        return
    try:
        _cast_file(cmfile).InternalPath = internal_path
    except (AttributeError, TypeError):
        pass


def _own_file_in_pictures_folder(ctx, cmfile) -> None:
    """Best-effort: own a raw-created `CmFile` under the target's Local
    Pictures `CmFolder` on a live host. No-op offline (fakes have no Cache)."""
    target = _target_handle(ctx)
    try:
        folder = target.Cache.LangProject.PicturesOC[0]
        folder.FilesOC.Add(cmfile)
    except Exception:
        pass


def _create_picture_raw(ctx, new_sense, internal_path, existing_file=None):
    """Raw `ICmPictureFactory` create -- wire the new `CmPicture` to
    `existing_file` (dedup reuse, no bytes) or to a fresh `CmFile` whose
    `InternalPath` is `internal_path` (missing-binary fallback, R5). Returns
    the picture, or None when the factory is unavailable. Never raises."""
    pic_factory = _picture_factory(ctx)
    if pic_factory is None:
        return None
    try:
        picture = pic_factory.Create()
    except Exception:
        return None
    _append_owned_picture(new_sense, picture)
    cmfile = existing_file
    if cmfile is None:
        file_factory = _file_factory(ctx)
        if file_factory is not None:
            try:
                cmfile = file_factory.Create()
            except Exception:
                cmfile = None
            if cmfile is not None:
                _set_cmfile_internal_path(cmfile, internal_path)
                _own_file_in_pictures_folder(ctx, cmfile)
    if cmfile is not None:
        try:
            _cast_picture(picture).PictureFileRA = cmfile
        except (AttributeError, TypeError):
            pass
    return picture


def _picture_factory(ctx):
    return _get_service(ctx, "ICmPictureFactory")


def _file_factory(ctx):
    return _get_service(ctx, "ICmFileFactory")


def _add_picture_via_seam(ctx, new_sense, image_path):
    """Happy-path asset-copy + picture-creation seam:
    `target.Senses.AddPicture` creates the `CmPicture`, copies the image into
    the target LinkedFiles/Pictures folder, and wires the `CmFile` in one call.
    Caption is passed as None -- full caption fidelity comes from the
    subsequent ws-mapped multistring copy. Returns the new picture, or None on
    any failure (caller reports)."""
    target = _target_handle(ctx)
    senses = getattr(target, "Senses", None)
    if senses is None:
        return None
    try:
        return senses.AddPicture(new_sense, image_path, None, None)
    except Exception:
        return None


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


def _intended_internal_path(src_cmfile, source_path) -> str:
    """The portable target `InternalPath` for a picture's image -- the source
    `CmFile.InternalPath` (portable, relative) when set, else
    `Pictures/<basename>`. Used by the missing-binary fallback (R5)."""
    internal = getattr(src_cmfile, "InternalPath", None) if src_cmfile else None
    if internal:
        return internal
    base = os.path.basename(source_path or "")
    return os.path.join("Pictures", base) if base else ""


def _source_status(source_path) -> str:
    """Classify a resolved source image path, read-only (parity between Move and
    Preview by construction, R5/R6):
    - "unresolved" -- no path (no `CmFile` / empty path);
    - "missing"    -- path set but not on disk;
    - "unreadable" -- on disk but cannot be read as a file (content hash "");
    - "ok"         -- on disk and readable.
    """
    if not source_path:
        return "unresolved"
    if not os.path.exists(source_path):
        return "missing"
    if _content_hash(source_path) == "":
        return "unreadable"
    return "ok"


def _missing_reason(intended_path) -> str:
    return ("source image missing on disk -- CmPicture + CmFile wired at the "
            "intended path %r, no bytes copied (029-sense-pictures, R5)"
            % (intended_path or "",))


def _unreadable_reason(source_path) -> str:
    return ("source image unreadable or target folder unwritable (%r) -- "
            "picture not reproduced (029-sense-pictures, R5)"
            % (source_path or "<unresolved>",))


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
    for src_pic in src_pictures:
        try:
            _reproduce_one_picture(
                src_pic, src_sense, new_sense, ctx, tag, resolver_cache, dropped)
        except Exception:  # noqa: BLE001 -- module posture G7: never raise
            _report_picture_dropped(
                dropped, src_sense, src_pic,
                "unexpected error reproducing picture (029)", ctx)


def _reproduce_one_picture(src_pic, src_sense, new_sense, ctx, tag,
                           resolver_cache, dropped) -> None:
    """Reproduce a single `CmPicture` onto `new_sense`: create it (+ copy the
    backing asset via the seam), then copy caption/description ws-mapped and
    the layout scalars. US1 covers the object graph; the asset copy / reuse /
    rename / missing-binary legs layer in via US2-US5."""
    src_file = getattr(src_pic, "PictureFileRA", None)
    source_path = _source_image_path(src_file, _source_handle(ctx))
    status = _source_status(source_path)

    if status == "missing":
        # US4 (R5): reproduce the object graph + wire a `CmFile` at the intended
        # target path (no bytes) so the picture self-heals once the linguist
        # supplies the file; report the missing binary (never silent).
        intended = _intended_internal_path(src_file, source_path)
        new_pic = _create_picture_raw(ctx, new_sense, intended, existing_file=None)
        _report_picture_dropped(
            dropped, src_sense, src_pic, _missing_reason(intended), ctx)
        if new_pic is None:
            return
        _copy_picture_multistrings(src_pic, new_pic, ctx)
        _copy_layout_scalars(src_pic, new_pic)
        return

    if status in ("unreadable", "unresolved"):
        # US4 (R5): unreadable source / unresolvable path -> report, no partial
        # write, no picture.
        _report_picture_dropped(
            dropped, src_sense, src_pic, _unreadable_reason(source_path), ctx)
        return

    # status == "ok": the source image is on disk and readable.
    source_hash = _content_hash(source_path)
    cache = _asset_cache(ctx)
    if source_hash and source_hash in cache:
        # US2 dedup (SC-005): the image was already copied this run -- reuse the
        # cached target `CmFile`, create the picture with no second file copy.
        new_pic = _create_picture_raw(
            ctx, new_sense, None, existing_file=cache[source_hash])
    else:
        # US2 happy path: `AddPicture` copies the image into the target
        # LinkedFiles/Pictures folder and wires the `CmFile` in one call.
        new_pic = _add_picture_via_seam(ctx, new_sense, source_path)
        if new_pic is not None and source_hash:
            wired = getattr(new_pic, "PictureFileRA", None)
            if wired is not None:
                cache[source_hash] = wired
    if new_pic is None:
        # A readable source that still failed to copy -> unwritable target (or
        # another write-time failure). Report; no partial write.
        _report_picture_dropped(
            dropped, src_sense, src_pic, _unreadable_reason(source_path), ctx)
        return
    _copy_picture_multistrings(src_pic, new_pic, ctx)
    _copy_layout_scalars(src_pic, new_pic)


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
    owner_guid = _guid_str(src_sense)
    seen_hashes: set = set()
    for src_pic in src_pictures:
        try:
            src_file = getattr(src_pic, "PictureFileRA", None)
            source_path = _source_image_path(src_file, _source_handle(ctx))
            status = _source_status(source_path)
            if status == "missing":
                # US4 parity: Move still CREATEs the picture (CmFile at the
                # intended path, no bytes) and reports -- mirror both here.
                intended = _intended_internal_path(src_file, source_path)
                _report_picture_dropped(
                    dropped, src_sense, src_pic, _missing_reason(intended), ctx)
                action = ReferenceAction.CREATE
            elif status in ("unreadable", "unresolved"):
                # US4 parity: Move reproduces no picture -> emit only the drop,
                # no decision.
                _report_picture_dropped(
                    dropped, src_sense, src_pic,
                    _unreadable_reason(source_path), ctx)
                continue
            else:  # status == "ok"
                source_hash = _content_hash(source_path)
                # US2/US3 LINK-vs-ADD: an asset already planned this run OR
                # already byte-identical in the target folder is reused (LINK);
                # otherwise a new copy is planned (CREATE). Read-only.
                if source_hash and (source_hash in seen_hashes
                                    or _target_identical_file(source_path, ctx)):
                    action = ReferenceAction.LINK
                else:
                    action = ReferenceAction.CREATE
                    if source_hash:
                        seen_hashes.add(source_hash)
            records.append(ReferenceDecisionRecord(
                owner_kind=_OWNER_KIND,
                owner_guid=owner_guid,
                field_name=_FIELD_NAME,
                action=action,
                item_name=_picture_label(src_pic, ctx),
                item_guid=_guid_str(src_pic),
            ))
        except Exception:  # noqa: BLE001 -- read-only twin; never raise
            _report_picture_dropped(
                dropped, src_sense, src_pic,
                "unexpected error planning picture decision (029)", ctx)
    return records
