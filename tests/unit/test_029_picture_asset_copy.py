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

import os

from gramtrans.Lib import pictures
from gramtrans.Lib.models import ReferenceAction


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


# ============================================================================
# Host-free asset-copy fakes: a faked `AddPicture` that performs REAL file I/O
# (copies into a target Pictures folder under tmp), plus raw ICmPicture/ICmFile
# factories served by a duck-typed `GetService(name)`. Source images are real
# temp files, so `_content_hash` / collision compares are exercised for real.
# ============================================================================

import shutil  # noqa: E402


class _WS:
    def __init__(self, handle, id_):
        self.Handle = handle
        self.Id = id_


class _WSNamespace:
    def __init__(self, wss):
        self._wss = list(wss)

    def GetAll(self):
        return list(self._wss)


class _MultiStr:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get_String(self, handle):
        return self._data.get(handle, "")

    def set_String(self, handle, value):
        self._data[handle] = value


class _CmFile:
    def __init__(self, internal="", abspath=""):
        self.InternalPath = internal
        self.AbsoluteInternalPath = abspath


class _Picture:
    ClassName = "CmPicture"

    def __init__(self, guid, caption=None, file=None):
        self.Guid = guid
        self.guid = guid
        self.Caption = _MultiStr(caption)
        self.Description = _MultiStr()
        self.PictureFileRA = file
        self.LayoutPos = 0
        self.LocationMin = 0
        self.LocationMax = 0
        self.LocationRangeType = 0
        self.ScaleFactor = 100


class _Sense:
    ClassName = "LexSense"

    def __init__(self, guid, pictures=()):
        self.Guid = guid
        self.guid = guid
        self.PicturesOS = list(pictures)


class _PictureFactory:
    def __init__(self):
        self.count = 0

    def Create(self):
        self.count += 1
        return _Picture(guid="raw-pic-%d" % self.count)


class _FileFactory:
    def __init__(self):
        self.count = 0

    def Create(self):
        self.count += 1
        return _CmFile()


class _SensesOps:
    """Fake `target.Senses`: AddPicture copies the (real) source file into the
    target Pictures folder, wires a CmFile, appends a picture to the sense.
    Raises FileNotFoundError for a missing source (mimics AddPicture's
    FP_ParameterError, R2)."""

    def __init__(self, linked_dir):
        self._linked = linked_dir
        self.add_calls = []
        self.rename_calls = []
        self.copy_count = 0

    def _pictures_dir(self):
        d = os.path.join(self._linked, "Pictures")
        os.makedirs(d, exist_ok=True)
        return d

    def AddPicture(self, sense, image_path, caption=None, wsHandle=None):
        self.add_calls.append(image_path)
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(image_path)
        name = os.path.basename(image_path)
        dest = os.path.join(self._pictures_dir(), name)
        shutil.copy2(image_path, dest)
        self.copy_count += 1
        cmfile = _CmFile(internal=os.path.join("Pictures", name), abspath=dest)
        pic = _Picture(guid="added-%d" % self.copy_count, file=cmfile)
        sense.PicturesOS.append(pic)
        return pic

    def RenamePicture(self, picture, new_filename):
        self.rename_calls.append(new_filename)
        old = picture.PictureFileRA
        old_abs = old.AbsoluteInternalPath
        new_abs = os.path.join(self._pictures_dir(), new_filename)
        os.rename(old_abs, new_abs)
        picture.PictureFileRA = _CmFile(
            internal=os.path.join("Pictures", new_filename), abspath=new_abs)
        return picture.PictureFileRA.InternalPath


class _Project:
    def __init__(self, wss, linked_dir, senses_ops=None, serve_factories=True):
        self.WritingSystems = _WSNamespace(wss)
        self._linked = linked_dir
        self.Senses = senses_ops
        self.PictureFactory = _PictureFactory()
        self.FileFactory = _FileFactory()
        self._serve = serve_factories

    def GetLinkedFilesDir(self):
        return self._linked

    def GetService(self, iface):
        if not self._serve:
            raise LookupError(iface)
        return {
            "ICmPictureFactory": self.PictureFactory,
            "ICmFileFactory": self.FileFactory,
        }.get(iface)


class _Ctx:
    def __init__(self, source_handle, target_handle, ws_map=None):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._ws_map = dict(ws_map or {})


_SRC_WS = [_WS(1, "en")]
_TGT_WS = [_WS(11, "en")]


def _write(path, data=b"IMG-DATA"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def _build(tmp_path):
    """Return (ctx, target_senses, src_linked, tgt_linked)."""
    src_linked = str(tmp_path / "src" / "LinkedFiles")
    tgt_linked = str(tmp_path / "tgt" / "LinkedFiles")
    os.makedirs(src_linked, exist_ok=True)
    os.makedirs(tgt_linked, exist_ok=True)
    tgt_senses = _SensesOps(tgt_linked)
    src = _Project(_SRC_WS, src_linked)
    tgt = _Project(_TGT_WS, tgt_linked, senses_ops=tgt_senses)
    return _Ctx(src, tgt), tgt_senses, src_linked, tgt_linked


# ============================================================================
# Phase 4 US2 (T010) -- backing image asset copied into the target project.
# ============================================================================

def test_us2_add_invokes_seam_with_resolved_path_and_wires_cmfile(tmp_path):
    """T010: an ADD picture invokes the asset-copy seam with the resolved
    source path and the resulting target picture's PictureFileRA is a wired
    CmFile with an InternalPath under the target Pictures folder."""
    ctx, tgt_senses, src_linked, tgt_linked = _build(tmp_path)
    src_img = _write(os.path.join(src_linked, "Pictures", "dog.jpg"))
    # ^ ensure the source Pictures dir + file exist
    src_file = _CmFile(internal="Pictures/dog.jpg", abspath=src_img)
    pic = _Picture("p1", caption={1: "a dog"}, file=src_file)
    src_sense = _Sense("s", pictures=[pic])
    new_sense = _Sense("t")

    dropped = []
    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, dropped)

    assert tgt_senses.add_calls == [src_img]  # resolved absolute source path
    assert len(new_sense.PicturesOS) == 1
    wired = new_sense.PicturesOS[0].PictureFileRA
    assert wired is not None
    assert wired.InternalPath == os.path.join("Pictures", "dog.jpg")
    assert os.path.exists(os.path.join(tgt_linked, "Pictures", "dog.jpg"))
    assert dropped == []


def test_us2_shared_image_copied_once_and_cmfile_reused(tmp_path):
    """T010: an image shared by two source pictures is copied ONCE (dedup via
    the per-run content-hash cache) and the second picture reuses the same
    target CmFile."""
    ctx, tgt_senses, src_linked, tgt_linked = _build(tmp_path)
    shared = _write(os.path.join(src_linked, "Pictures", "shared.jpg"))
    f1 = _CmFile(internal="Pictures/shared.jpg", abspath=shared)
    f2 = _CmFile(internal="Pictures/shared.jpg", abspath=shared)
    src_sense = _Sense("s", pictures=[
        _Picture("p1", caption={1: "one"}, file=f1),
        _Picture("p2", caption={1: "two"}, file=f2),
    ])
    new_sense = _Sense("t")

    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, [])

    assert tgt_senses.copy_count == 1  # copied once
    assert len(new_sense.PicturesOS) == 2
    wired = [p.PictureFileRA for p in new_sense.PicturesOS]
    assert wired[0] is wired[1]  # same CmFile reused


# ============================================================================
# Phase 4 US2 (T012) -- Preview plans ADD vs LINK (reuse) read-only.
# ============================================================================

def test_us2_preview_plans_add_then_link_for_shared_image(tmp_path):
    """T012: the first occurrence of an image plans a CREATE (new copy); a
    later picture whose asset is byte-identical to an already-planned/existing
    target file plans a LINK (reuse) -- computed read-only, no file copied."""
    ctx, tgt_senses, src_linked, tgt_linked = _build(tmp_path)
    shared = _write(os.path.join(src_linked, "Pictures", "shared.jpg"))
    f1 = _CmFile(internal="Pictures/shared.jpg", abspath=shared)
    f2 = _CmFile(internal="Pictures/shared.jpg", abspath=shared)
    src_sense = _Sense("s", pictures=[
        _Picture("p1", caption={1: "one"}, file=f1),
        _Picture("p2", caption={1: "two"}, file=f2),
    ])

    decisions = pictures.plan_sense_picture_decisions(src_sense, ctx, {}, [])

    actions = [d.action for d in decisions]
    assert actions == [ReferenceAction.CREATE, ReferenceAction.LINK]
    # read-only: nothing copied
    assert tgt_senses.copy_count == 0
    assert not os.path.exists(os.path.join(tgt_linked, "Pictures", "shared.jpg"))


# ============================================================================
# Phase 5 US4 (T013) -- never-silent filesystem failures.
# ============================================================================

def test_us4_missing_source_binary_wires_cmfile_and_reports(tmp_path):
    """T013(a): a missing source image still yields a CmPicture + a CmFile
    wired at the intended InternalPath (no bytes copied, raw-factory fallback)
    plus exactly one DroppedItemRecord naming the sense/picture."""
    ctx, tgt_senses, src_linked, tgt_linked = _build(tmp_path)
    gone = os.path.join(src_linked, "Pictures", "gone.jpg")  # never created
    src_file = _CmFile(internal="Pictures/gone.jpg", abspath=gone)
    pic = _Picture("p-missing", caption={1: "lost dog"}, file=src_file)
    src_sense = _Sense("s", pictures=[pic])
    new_sense = _Sense("t")

    dropped = []
    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, dropped)

    assert len(new_sense.PicturesOS) == 1
    wired = new_sense.PicturesOS[0].PictureFileRA
    assert wired is not None
    assert wired.InternalPath == "Pictures/gone.jpg"
    assert tgt_senses.copy_count == 0  # no bytes copied
    assert not os.path.exists(os.path.join(tgt_linked, "Pictures", "gone.jpg"))
    pic_drops = [d for d in dropped
                 if d.field_name == "PicturesOS" and d.item_guid == "p-missing"]
    assert len(pic_drops) == 1
    assert "missing" in pic_drops[0].reason.lower()


def test_us4_unreadable_source_reports_no_partial_write(tmp_path):
    """T013(b): an unreadable source (here a directory masquerading as the
    image path -- exists but cannot be read as a file) is reported, with no
    throw and no partial target write and no picture reproduced."""
    ctx, tgt_senses, src_linked, tgt_linked = _build(tmp_path)
    baddir = os.path.join(src_linked, "Pictures", "weird.jpg")
    os.makedirs(baddir, exist_ok=True)  # a dir, not a file
    src_file = _CmFile(internal="Pictures/weird.jpg", abspath=baddir)
    pic = _Picture("p-bad", caption={1: "x"}, file=src_file)
    src_sense = _Sense("s", pictures=[pic])
    new_sense = _Sense("t")

    dropped = []
    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, dropped)

    assert new_sense.PicturesOS == []  # no partial picture
    assert tgt_senses.copy_count == 0
    assert not os.path.exists(os.path.join(tgt_linked, "Pictures", "weird.jpg"))
    pic_drops = [d for d in dropped if d.item_guid == "p-bad"]
    assert len(pic_drops) == 1


def test_us4_preview_move_drop_parity(tmp_path):
    """T013(c): the Preview drop set is identical to the Move drop set for a
    mix of good / missing / unreadable pictures (by construction)."""
    ctx, tgt_senses, src_linked, tgt_linked = _build(tmp_path)
    good = _write(os.path.join(src_linked, "Pictures", "good.jpg"))
    gone = os.path.join(src_linked, "Pictures", "gone.jpg")  # missing
    baddir = os.path.join(src_linked, "Pictures", "bad.jpg")
    os.makedirs(baddir, exist_ok=True)  # unreadable
    src_sense = _Sense("s", pictures=[
        _Picture("pg", caption={1: "good"},
                 file=_CmFile(internal="Pictures/good.jpg", abspath=good)),
        _Picture("pm", caption={1: "missing"},
                 file=_CmFile(internal="Pictures/gone.jpg", abspath=gone)),
        _Picture("pb", caption={1: "bad"},
                 file=_CmFile(internal="Pictures/bad.jpg", abspath=baddir)),
    ])
    new_sense = _Sense("t")

    move_dropped = []
    pictures.reproduce_sense_pictures(
        src_sense, new_sense, ctx, None, {}, move_dropped)

    preview_ctx, _, _, _ = _build(tmp_path / "preview")
    # point the preview ctx's source at the SAME source files
    preview_ctx.source_handle = ctx.source_handle
    preview_dropped = []
    pictures.plan_sense_picture_decisions(
        src_sense, preview_ctx, {}, preview_dropped)

    def _key(ds):
        return sorted((d.owner_guid, d.field_name, d.item_guid, d.reason)
                      for d in ds)

    assert _key(move_dropped) == _key(preview_dropped)
    # exactly the missing + unreadable pictures are dropped (good one is not)
    assert {d.item_guid for d in move_dropped} == {"pm", "pb"}
