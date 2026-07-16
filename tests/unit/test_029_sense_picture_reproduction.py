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


# ============================================================================
# Shared host-free fakes for the object-graph legs (US1/US5). No real file I/O:
# the asset-copy seam (`ctx.target_handle.Senses.AddPicture`) is a fake that
# creates a blank picture and appends it to the target sense's PicturesOS.
# (The asset/filesystem legs -- copy/reuse/rename/missing-binary -- use real
# temp files in `test_029_picture_asset_copy.py`.)
# ============================================================================

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
    """Duck-typed IMultiString for `_copy_multistrings_ws_mapped`'s offline
    (SIL-optional) path: get/set by ws handle over a plain-str dict."""

    def __init__(self, data=None):
        self._data = dict(data or {})

    def get_String(self, handle):
        return self._data.get(handle, "")

    def set_String(self, handle, value):
        self._data[handle] = value


class _CmFile:
    def __init__(self, abspath="", internal=""):
        self.AbsoluteInternalPath = abspath
        self.InternalPath = internal


_DEFAULT_LAYOUT = {
    "LayoutPos": 0, "LocationMin": 0, "LocationMax": 0,
    "LocationRangeType": 0, "ScaleFactor": 100,
}


class _Picture:
    ClassName = "CmPicture"

    def __init__(self, guid, caption=None, description=None, file=None,
                 layout=None):
        self.Guid = guid
        self.guid = guid
        self.Caption = _MultiStr(caption)
        self.Description = _MultiStr(description)
        self.PictureFileRA = file
        vals = dict(_DEFAULT_LAYOUT)
        vals.update(layout or {})
        for name, v in vals.items():
            setattr(self, name, v)


class _Sense:
    ClassName = "LexSense"

    def __init__(self, guid, pictures=()):
        self.Guid = guid
        self.guid = guid
        self.PicturesOS = list(pictures)


class _SensesOps:
    """Fake `ctx.target_handle.Senses`: AddPicture creates a blank picture (no
    disk copy), appends it to the target sense's PicturesOS, returns it --
    mirroring the real happy path minus the actual file copy."""

    def __init__(self):
        self.add_calls = []

    def AddPicture(self, sense, image_path, caption=None, wsHandle=None):
        self.add_calls.append((image_path, caption, wsHandle))
        pic = _Picture(guid="new-%d" % (len(self.add_calls),))
        if caption:
            pic.Caption.set_String(wsHandle or 0, caption)
        sense.PicturesOS.append(pic)
        return pic


class _Project:
    def __init__(self, wss, senses_ops=None, linked_dir=""):
        self.WritingSystems = _WSNamespace(wss)
        self.Senses = senses_ops
        self._linked_dir = linked_dir

    def GetLinkedFilesDir(self):
        return self._linked_dir


class _Ctx:
    def __init__(self, source_handle, target_handle, ws_map=None):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._ws_map = dict(ws_map or {})


_SRC_WS = [_WS(1, "en"), _WS(2, "fr")]
_TGT_WS = [_WS(11, "en"), _WS(12, "fr")]


def _make_ctx(target_senses=None):
    src = _Project(_SRC_WS)
    tgt = _Project(_TGT_WS, senses_ops=target_senses or _SensesOps())
    return _Ctx(src, tgt)


def _img(tmp_path, name, data=None):
    """Write a real temp source image so path resolution + content hashing are
    exercised for real (a picture's source file genuinely exists on disk); the
    object-graph fakes never actually copy it. Distinct `data` per name keeps
    content hashes distinct."""
    import os as _os
    p = tmp_path / name
    with open(str(p), "wb") as fh:
        fh.write(data if data is not None else ("IMG-" + name).encode())
    return str(p)


# ============================================================================
# Phase 3 US1 (T007) -- the CmPicture object deep-copy.
# ============================================================================

def test_us1_caption_description_ws_mapped_and_layout_scalars_copied(tmp_path):
    """T007: reproduce copies Caption/Description across all writing systems
    (ws-mapped src handle -> tgt handle for the same Id) and the five layout
    scalars verbatim onto the created target picture."""
    pic = _Picture(
        "src-pic-1",
        caption={1: "a dog", 2: "un chien"},
        description={1: "a friendly dog"},
        file=_CmFile(abspath=_img(tmp_path, "dog.jpg")),
        layout={"LayoutPos": 3, "LocationMin": 1, "LocationMax": 5,
                "LocationRangeType": 2, "ScaleFactor": 50},
    )
    src_sense = _Sense("src-sense-1", pictures=[pic])
    new_sense = _Sense("new-sense-1")
    ctx = _make_ctx()

    dropped: list = []
    pictures.reproduce_sense_pictures(
        src_sense, new_sense, ctx, None, {}, dropped)

    assert len(new_sense.PicturesOS) == 1
    new_pic = new_sense.PicturesOS[0]
    # ws-mapped: en handle 1 -> 11, fr handle 2 -> 12.
    assert new_pic.Caption._data == {11: "a dog", 12: "un chien"}
    assert new_pic.Description._data == {11: "a friendly dog"}
    assert new_pic.LayoutPos == 3
    assert new_pic.LocationMin == 1
    assert new_pic.LocationMax == 5
    assert new_pic.LocationRangeType == 2
    assert new_pic.ScaleFactor == 50
    assert dropped == []


def test_us1_multi_picture_order_preserved(tmp_path):
    """T007: multiple source pictures reproduce in source `PicturesOS` order."""
    p1 = _Picture("p1", caption={1: "first"},
                  file=_CmFile(abspath=_img(tmp_path, "a.jpg")))
    p2 = _Picture("p2", caption={1: "second"},
                  file=_CmFile(abspath=_img(tmp_path, "b.jpg")))
    p3 = _Picture("p3", caption={1: "third"},
                  file=_CmFile(abspath=_img(tmp_path, "c.jpg")))
    src_sense = _Sense("s", pictures=[p1, p2, p3])
    new_sense = _Sense("t")
    ctx = _make_ctx()

    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, [])

    captions = [p.Caption._data.get(11) for p in new_sense.PicturesOS]
    assert captions == ["first", "second", "third"]


# ============================================================================
# Phase 3 US1 (T009) -- Preview twin object leg + Move/Preview parity.
# ============================================================================

def test_us1_preview_emits_one_add_decision_per_picture(tmp_path):
    """T009: the Preview twin emits one CREATE ReferenceDecisionRecord per
    source picture (owner=sense, field=PicturesOS), read-only."""
    p1 = _Picture("p1", caption={1: "a dog"},
                  file=_CmFile(abspath=_img(tmp_path, "a.jpg")))
    p2 = _Picture("p2", caption={1: "a cat"},
                  file=_CmFile(abspath=_img(tmp_path, "b.jpg")))
    src_sense = _Sense("s", pictures=[p1, p2])
    ctx = _make_ctx()

    decisions = pictures.plan_sense_picture_decisions(src_sense, ctx, {}, [])

    assert len(decisions) == 2
    for d in decisions:
        assert isinstance(d, ReferenceDecisionRecord)
        assert d.owner_kind == "LexSense"
        assert d.owner_guid == "s"
        assert d.field_name == "PicturesOS"
        assert d.action == ReferenceAction.CREATE
    assert {d.item_guid for d in decisions} == {"p1", "p2"}


def test_us1_preview_move_parity_count(tmp_path):
    """T009 parity: the Preview CREATE-decision count equals the Move
    create count for the same source sense."""
    src_sense = _Sense("s", pictures=[
        _Picture("p1", file=_CmFile(abspath=_img(tmp_path, "a.jpg"))),
        _Picture("p2", file=_CmFile(abspath=_img(tmp_path, "b.jpg"))),
        _Picture("p3", file=_CmFile(abspath=_img(tmp_path, "c.jpg"))),
    ])
    new_sense = _Sense("t")

    move_ctx = _make_ctx()
    pictures.reproduce_sense_pictures(src_sense, new_sense, move_ctx, None, {}, [])
    move_creates = len(new_sense.PicturesOS)

    preview_ctx = _make_ctx()
    decisions = pictures.plan_sense_picture_decisions(src_sense, preview_ctx, {}, [])
    preview_creates = sum(
        1 for d in decisions if d.action == ReferenceAction.CREATE)

    assert preview_creates == move_creates == 3


# ============================================================================
# Phase 6 US5 (T016) -- idempotency (structural fingerprint) + non-destructive
# empty source.
# ============================================================================

def test_us5_matching_fingerprint_not_recreated(tmp_path):
    """T016(a): a target sense already carrying a picture whose fingerprint
    (image filename + content hash + caption) matches the source picture is NOT
    re-created on re-run -- 0 net-new picture/CmFile/file."""
    img = _img(tmp_path, "dog.jpg")
    src_pic = _Picture(
        "src", caption={1: "a dog"},
        file=_CmFile(internal="Pictures/dog.jpg", abspath=img))
    # A structurally-identical picture already on the target sense (prior run):
    # same image bytes (same file), same caption in the target WS.
    existing = _Picture(
        "existing", caption={11: "a dog"},
        file=_CmFile(internal="Pictures/dog.jpg", abspath=img))
    new_sense = _Sense("t", pictures=[existing])
    src_sense = _Sense("s", pictures=[src_pic])

    senses = _SensesOps()
    ctx = _Ctx(_Project(_SRC_WS), _Project(_TGT_WS, senses_ops=senses))

    dropped = []
    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, dropped)

    assert len(new_sense.PicturesOS) == 1  # existing only; no net-new
    assert new_sense.PicturesOS[0] is existing
    assert senses.add_calls == []  # AddPicture never called on re-run


def test_us5_distinct_caption_same_image_is_still_reproduced(tmp_path):
    """T016(a) boundary: an image match with a DIFFERENT caption is a distinct
    picture (not a fingerprint match) -- it IS reproduced."""
    img = _img(tmp_path, "dog.jpg")
    src_pic = _Picture(
        "src", caption={1: "a running dog"},
        file=_CmFile(internal="Pictures/dog.jpg", abspath=img))
    existing = _Picture(
        "existing", caption={11: "a sleeping dog"},
        file=_CmFile(internal="Pictures/dog.jpg", abspath=img))
    new_sense = _Sense("t", pictures=[existing])
    src_sense = _Sense("s", pictures=[src_pic])

    senses = _SensesOps()
    ctx = _Ctx(_Project(_SRC_WS), _Project(_TGT_WS, senses_ops=senses))

    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, [])

    assert len(new_sense.PicturesOS) == 2  # existing + the newly reproduced one


def test_us5_empty_source_leaves_populated_target_untouched():
    """T016(b): an empty/absent source PicturesOS leaves a populated target
    PicturesOS untouched (non-destructive, never blank -- FR-006)."""
    existing = _Picture("existing", caption={11: "keep me"})
    new_sense = _Sense("t", pictures=[existing])
    src_sense = _Sense("s", pictures=[])
    ctx = _make_ctx()

    pictures.reproduce_sense_pictures(src_sense, new_sense, ctx, None, {}, [])

    assert new_sense.PicturesOS == [existing]
