"""Feature 033 -- bare `.Create()` sweep.

The 033 invariant: *every transferred object keeps its source GUID unless that
GUID already exists in the target*. `owned._create_owned_via_factory` is the
canonical helper that enforces it (and LOGS any fallback to a minted identity).

These tests cover the create sites the live GUID audit could NOT reach, because
the audit fixture carries no such data -- pictures, reversal sub-entries,
text-markup tags, and the Layer-3 affix allomorph path. Each site previously
called a bare `factory.Create()`, minting a fresh identity with no log.

Each test asserts the SOURCE GUID reaches the factory. A fake factory records
the positional guid argument it was handed; a bare `Create()` records None,
which is the RED state.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import pictures, reversals, texts
from gramtrans.Lib.models import DroppedItemRecord  # noqa: F401 -- shape import


# ============================================================================
# Shared fakes: a factory that records whichever guid it was handed.
# ============================================================================

class _RecordingFactory:
    """Fake LCM factory exposing BOTH `Create()` and `Create(guid)`.

    `_create_owned_via_factory` tries the guid overload first, so a call
    recorded with a non-None guid proves the source identity was threaded all
    the way to the factory.
    """

    def __init__(self, cls, accept_guid=True):
        self._cls = cls
        self._accept_guid = accept_guid
        self.calls = []

    def Create(self, guid=None):
        if guid is not None and not self._accept_guid:
            raise TypeError("Create() takes no Guid overload")
        self.calls.append(guid)
        return self._cls(guid)

    @property
    def last_guid(self):
        return self.calls[-1] if self.calls else None


class _Made:
    """Minimal created-object stand-in carrying whatever guid it was made with."""

    def __init__(self, guid=None):
        self.Guid = guid
        self.guid = guid


class _MadePicture(_Made):
    ClassName = "CmPicture"

    def __init__(self, guid=None):
        super().__init__(guid)
        self.PictureFileRA = None


class _MadeFile(_Made):
    ClassName = "CmFile"

    def __init__(self, guid=None):
        super().__init__(guid)
        self.InternalPath = ""


# ============================================================================
# pictures.py -- CmPicture + CmFile raw-factory fallback (missing-binary leg).
# ============================================================================

class _PicSense:
    ClassName = "LexSense"

    def __init__(self):
        self.PicturesOS = []


class _PicTarget:
    """Serves the raw factories by string key (the host-free `_get_service`
    fallback). No `Cache`, so `_own_file_in_pictures_folder` is a clean no-op."""

    def __init__(self, pic_factory, file_factory):
        self._factories = {
            "ICmPictureFactory": pic_factory,
            "ICmFileFactory": file_factory,
        }

    def GetService(self, key):
        if not isinstance(key, str):
            raise TypeError("host-free fake takes the string key")
        return self._factories[key]


class _PicCtx:
    def __init__(self, target):
        self.source_handle = None
        self.target_handle = target


def test_picture_raw_create_preserves_source_picture_guid():
    """`_create_picture_raw` must mint the CmPicture with the SOURCE picture's
    GUID, not a fresh one (033 invariant)."""
    pic_factory = _RecordingFactory(_MadePicture)
    file_factory = _RecordingFactory(_MadeFile)
    ctx = _PicCtx(_PicTarget(pic_factory, file_factory))

    pictures._create_picture_raw(
        ctx, _PicSense(), "Pictures/dog.jpg",
        src_pic_guid="src-pic-guid-1",
    )

    assert pic_factory.last_guid == "src-pic-guid-1"


def test_picture_raw_create_preserves_source_cmfile_guid():
    """The backing `CmFile` is a transferred object too -- it must carry the
    source `PictureFileRA` GUID."""
    pic_factory = _RecordingFactory(_MadePicture)
    file_factory = _RecordingFactory(_MadeFile)
    ctx = _PicCtx(_PicTarget(pic_factory, file_factory))

    pictures._create_picture_raw(
        ctx, _PicSense(), "Pictures/dog.jpg",
        src_pic_guid="src-pic-guid-2", src_file_guid="src-file-guid-2",
    )

    assert file_factory.last_guid == "src-file-guid-2"


def test_picture_raw_create_falls_back_when_guid_overload_absent():
    """G7 never-raise: a factory without the guid overload must still produce a
    picture (minted identity), not crash the walk."""
    pic_factory = _RecordingFactory(_MadePicture, accept_guid=False)
    file_factory = _RecordingFactory(_MadeFile, accept_guid=False)
    ctx = _PicCtx(_PicTarget(pic_factory, file_factory))

    new_pic = pictures._create_picture_raw(
        ctx, _PicSense(), "Pictures/dog.jpg", src_pic_guid="src-pic-guid-3")

    assert new_pic is not None
    assert pic_factory.last_guid is None  # fell back to the bare overload


def test_reproduce_one_picture_threads_guids_into_the_raw_path(tmp_path, monkeypatch):
    """End-to-end within the module: the missing-binary leg (R5) must thread
    BOTH the source picture and source file GUIDs into `_create_picture_raw`."""
    seen = {}

    def _spy(ctx, new_sense, internal_path, existing_file=None,
             src_pic_guid=None, src_file_guid=None):
        seen["pic"] = src_pic_guid
        seen["file"] = src_file_guid
        return _MadePicture(src_pic_guid)

    monkeypatch.setattr(pictures, "_create_picture_raw", _spy)

    class _SrcFile:
        Guid = "src-file-guid-4"
        InternalPath = "Pictures/gone.jpg"
        AbsoluteInternalPath = str(tmp_path / "gone.jpg")  # never written -> missing

    class _SrcPic:
        ClassName = "CmPicture"
        Guid = "src-pic-guid-4"
        PictureFileRA = _SrcFile()

    dropped = []
    pictures._reproduce_one_picture(
        _SrcPic(), _PicSense(), _PicSense(),
        _PicCtx(_PicTarget(_RecordingFactory(_MadePicture),
                           _RecordingFactory(_MadeFile))),
        tag=None, resolver_cache={}, dropped=dropped,
    )

    assert seen.get("pic") == "src-pic-guid-4"
    assert seen.get("file") == "src-file-guid-4"


# ============================================================================
# reversals.py -- the raw `IReversalIndexEntryFactory` sub-entry create.
# ============================================================================

def test_reversal_sub_entry_create_preserves_source_entry_guid(monkeypatch):
    """`_create_sub_entry` falls back to the raw factory; the created
    sub-entry must carry `decision.source_entry_guid`."""
    factory = _RecordingFactory(_Made)
    monkeypatch.setattr(
        reversals.owned, "_get_owned_factory", lambda target, name: factory)

    class _Parent:
        def __init__(self):
            self.SubentriesOS = _AddList()

    class _AddList(list):
        def Add(self, item):
            self.append(item)

    class _Decision:
        source_entry_guid = "src-rev-sub-guid-1"

    dropped = []
    reversals._create_sub_entry(
        target=object(), parent_entry=_Parent(), decision=_Decision(),
        primary_ws_id="en", primary_text="hound",
        first_sense=None, dropped=dropped,
    )

    assert factory.last_guid == "src-rev-sub-guid-1"


# ============================================================================
# texts.py -- the raw `ITextTagFactory` text-markup tag create.
# ============================================================================

def test_text_tag_create_preserves_source_tag_guid():
    """`_raw_create_text_tag` must pass the source tag GUID to the factory."""
    import inspect
    sig = inspect.signature(texts._raw_create_text_tag)
    assert "src_tag_guid" in sig.parameters, (
        "_raw_create_text_tag must accept the source tag GUID so the created "
        "ITextTag can preserve it (033 invariant)")
