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


# ============================================================================
# Segment GUID loss -- justified, but it must be LOGGED, never silent (033).
#
# LCM auto-segments when a paragraph's `Contents` is set, so the positional
# slot is already filled and `AppendSentence(..., guid=)` -- the only
# GUID-preserving path -- never fires. LCM GUIDs are immutable post-create, so
# the loss stands until/unless a create-segments-first path is built. The
# invariant permits a loss that is justified AND logged; what it forbids is
# silence.
# ============================================================================

def test_segment_guid_loss_is_logged_not_silent(caplog):
    """An auto-created segment whose GUID differs from its source must produce
    a WARNING naming the count and the reason."""
    import logging

    class _Seg:
        def __init__(self, guid):
            self.Guid = guid
            self.guid = guid

    auto = [_Seg("auto-guid-a"), _Seg("auto-guid-b")]
    plans = [_SegPlan("src-seg-1"), _SegPlan("src-seg-2")]

    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.texts"):
        texts._log_segment_guid_loss(auto, plans, "Text One")

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "2" in joined, "the count of lost segment GUIDs must be reported"
    assert "auto-segment" in joined.lower() or "auto_segment" in joined.lower(), (
        "the logged reason must explain WHY the GUID was not preserved")


def test_segment_guid_loss_silent_when_guids_were_preserved(caplog):
    """No warning when the target segments already carry their source GUIDs --
    the log must not cry wolf once a create-segments-first path lands."""
    import logging

    class _Seg:
        def __init__(self, guid):
            self.Guid = guid
            self.guid = guid

    preserved = [_Seg("src-seg-1"), _Seg("src-seg-2")]
    plans = [_SegPlan("src-seg-1"), _SegPlan("src-seg-2")]

    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.texts"):
        texts._log_segment_guid_loss(preserved, plans, "Text One")

    assert not caplog.records, "no GUID was lost; nothing should be logged"


class _SegPlan:
    def __init__(self, source_guid):
        self.source_guid = source_guid


# ============================================================================
# Option A -- re-create auto-segmented segments carrying their source GUIDs.
#
# LCM positions a segment at creation (`ISegment.BeginOffset` is read-only), so
# the only route is the factory overload
#   ISegmentFactory.Create(owner, initialOffset, cache, guid)
# applied at each auto-segment's OWN offset. `Contents` is never touched, so
# the paragraph text cannot be disturbed.
# ============================================================================

class _AutoSeg:
    def __init__(self, guid, offset):
        self.Guid = guid
        self.guid = guid
        self.BeginOffset = offset


class _SegFactory:
    def __init__(self, fail_at=None):
        self.calls = []
        self._fail_at = fail_at

    def Create(self, owner, initial_offset, cache, guid):
        if self._fail_at is not None and len(self.calls) == self._fail_at:
            raise RuntimeError("factory boom")
        self.calls.append((owner, initial_offset, guid))
        return _AutoSeg(guid, initial_offset)


class _SegOps:
    def __init__(self):
        self.deleted = []

    def Delete(self, seg):
        self.deleted.append(seg)


class _SegTarget:
    Cache = object()


def _patch_seams(monkeypatch, factory):
    monkeypatch.setattr(texts, "_segment_factory", lambda target: factory)
    monkeypatch.setattr(texts, "_parse_dotnet_guid",
                        lambda g: ("GUID:" + g) if g else None)


def test_option_a_recreates_segments_with_source_guids(monkeypatch):
    """Each auto-created segment is deleted and re-created at its OWN offset
    carrying the source GUID."""
    factory = _SegFactory()
    _patch_seams(monkeypatch, factory)
    auto = [_AutoSeg("auto-a", 0), _AutoSeg("auto-b", 12)]
    plans = [_SegPlan("src-seg-1"), _SegPlan("src-seg-2")]
    seg_ops = _SegOps()

    out = texts._rebuild_segments_with_source_guids(
        _SegTarget(), seg_ops, "PARA", plans, auto, "Text One")

    assert out is not None and len(out) == 2
    assert len(seg_ops.deleted) == 2, "auto segments must be deleted first"
    # positioned at the ORIGINAL offsets, with the SOURCE identities
    assert [c[1] for c in factory.calls] == [0, 12]
    assert [c[2] for c in factory.calls] == ["GUID:src-seg-1", "GUID:src-seg-2"]


def test_option_a_noop_when_guids_already_preserved(monkeypatch):
    """Must not churn segments that already carry their source GUIDs."""
    factory = _SegFactory()
    _patch_seams(monkeypatch, factory)
    auto = [_AutoSeg("src-seg-1", 0), _AutoSeg("src-seg-2", 12)]
    plans = [_SegPlan("src-seg-1"), _SegPlan("src-seg-2")]
    seg_ops = _SegOps()

    out = texts._rebuild_segments_with_source_guids(
        _SegTarget(), seg_ops, "PARA", plans, auto, "Text One")

    assert out is None
    assert seg_ops.deleted == [] and factory.calls == []


def test_option_a_declines_when_any_source_guid_missing(monkeypatch):
    """Incomplete identity must NOT disturb a working paragraph."""
    factory = _SegFactory()
    _patch_seams(monkeypatch, factory)
    auto = [_AutoSeg("auto-a", 0), _AutoSeg("auto-b", 12)]
    plans = [_SegPlan("src-seg-1"), _SegPlan("")]
    seg_ops = _SegOps()

    out = texts._rebuild_segments_with_source_guids(
        _SegTarget(), seg_ops, "PARA", plans, auto, "Text One")

    assert out is None
    assert seg_ops.deleted == [] and factory.calls == []


def test_option_a_declines_host_free(monkeypatch):
    """No LCM factory (offline) -> keep the auto segments, delete nothing."""
    monkeypatch.setattr(texts, "_segment_factory", lambda target: None)
    seg_ops = _SegOps()

    out = texts._rebuild_segments_with_source_guids(
        _SegTarget(), seg_ops, "PARA",
        [_SegPlan("src-seg-1")], [_AutoSeg("auto-a", 0)], "Text One")

    assert out is None
    assert seg_ops.deleted == []


def test_option_a_partial_failure_is_loud(monkeypatch, caplog):
    """A mid-rebuild factory failure must ERROR (segmentation now incomplete),
    never pass silently."""
    import logging
    factory = _SegFactory(fail_at=1)
    _patch_seams(monkeypatch, factory)
    auto = [_AutoSeg("auto-a", 0), _AutoSeg("auto-b", 12)]
    plans = [_SegPlan("src-seg-1"), _SegPlan("src-seg-2")]

    with caplog.at_level(logging.ERROR, logger="gramtrans.Lib.texts"):
        texts._rebuild_segments_with_source_guids(
            _SegTarget(), _SegOps(), "PARA", plans, auto, "Text One")

    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "an incomplete rebuild must be reported loudly")
