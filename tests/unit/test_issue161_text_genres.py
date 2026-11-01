"""Issue #161 -- text genres are decided via `Texts.GetGenres` and applied with
`.Add` to the target text's `GenresRC` reference collection; every failure
records a DroppedItemRecord instead of a silent no-op.

Before the fix:
* `_decide_genres` called `Texts.GetGenre`, which raises live (LINQ
  `FirstOrDefault` is not exposed by pythonnet); the error was swallowed, so
  `genre_decisions == ()` and nothing was reported. The fake hid this because
  its `GetGenre` returned a list -- a shape the real API does not have.
* `_apply_genres` passed `owner_obj=target_text` to `apply_reference`, whose
  arms `setattr(text, "GenresRC", item)` on a reference collection; that
  failed and `_safe` swallowed it.
"""
from __future__ import annotations

from types import SimpleNamespace

from _fakes_texts import (
    FakeCtx,
    FakeLangProject,
    FakeParagraph,
    FakePossibility,
    FakePossibilityList,
    FakeProject,
    FakeRefCollection,
    FakeSegment,
    FakeText,
    FakeTextOps,
    FakeWS,
)

from gramtrans.Lib import texts
from gramtrans.Lib.models import (
    DroppedItemRecord,
    GrammarCategory,
    ReferenceAction,
    ReferenceDecision,
    Selection,
)

WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)


def _source(genres=(), text_ops_cls=None):
    seg = FakeSegment(guid="seg-1", baseline=" abc .", free={2: "x"}, literal={},
                      notes=(), wordforms=(), analyses_rs=())
    para = FakeParagraph(guid="para-1", text_by_handle={1: "abc."}, segments=(seg,))
    text = FakeText(guid="txt-1", name="Story One", genres=genres, paragraphs=(para,))
    proj = FakeProject(ws_list=[WS_VERN, WS_EN], texts=[text])
    if text_ops_cls is not None:
        proj.Texts = text_ops_cls([text])
    return proj


def _target(genre_items=()):
    lp = FakeLangProject(genre_list=FakePossibilityList(genre_items))
    return FakeProject(ws_list=[WS_VERN, WS_EN], texts=[], lang_project=lp)


def _plan(source, target, dropped):
    sel = Selection(categories={GrammarCategory.TEXTS: True},
                    text_picks=frozenset({"txt-1"}))
    ctx = FakeCtx(source_handle=source, ws_map={})
    return texts.plan_texts(sel, source, target, ctx, {}, dropped), ctx


class _LiveShapedTextOps(FakeTextOps):
    """`GetGenre` raises exactly as flexicon's does live."""

    def GetGenre(self, t):
        raise AttributeError("'ILcmReferenceCollection[ICmPossibility]' object "
                             "has no attribute 'FirstOrDefault'")


# ---------------------------------------------------------------------------
# Fakes match the real API shapes
# ---------------------------------------------------------------------------

def test_fake_genre_api_shapes_match_flexicon():
    g1, g2 = FakePossibility("g1", "A"), FakePossibility("g2", "B")
    ops = FakeTextOps()
    t = FakeText("t", "T", genres=(g1, g2))
    assert ops.GetGenre(t) is g1                       # single item, not a list
    assert ops.GetGenre(FakeText("u", "U")) is None
    assert ops.GetGenres(t) == [g1, g2]                # every genre
    assert t.GenresRC.Count == 2 and not hasattr(t.GenresRC, "FirstOrDefault")
    ops.SetGenre(t, g2)                                # flexicon: clear, then set
    assert list(t.GenresRC) == [g2]


# ---------------------------------------------------------------------------
# Decide side
# ---------------------------------------------------------------------------

def test_decide_uses_getgenres_even_though_getgenre_raises():
    genre = FakePossibility("genre-1", "Narrative")
    other = FakePossibility("genre-2", "Poetry")
    source = _source(genres=(genre, other), text_ops_cls=_LiveShapedTextOps)
    dropped: list = []
    plans, _ = _plan(source, _target(), dropped)
    actions = [d.action for d in plans[0].genre_decisions]
    assert actions == [ReferenceAction.CREATE, ReferenceAction.CREATE]
    assert dropped == []


def test_unreadable_genres_record_a_drop_not_silence():
    class _Broken(FakeTextOps):
        def GetGenres(self, t):
            raise RuntimeError("boom")

    source = _source(genres=(FakePossibility("g", "G"),), text_ops_cls=_Broken)
    dropped: list = []
    plans, _ = _plan(source, _target(), dropped)
    assert plans[0].genre_decisions == ()
    assert len(dropped) == 1
    rec = dropped[0]
    assert (rec.owner_kind, rec.owner_guid, rec.field_name) == ("Text", "txt-1", "GenresRC")
    assert "boom" in rec.reason


def test_older_flexicon_without_getgenres_reads_raw_collection():
    class _Old(FakeTextOps):
        GetGenres = None  # absent before flexicon 4.9.0

        def GetGenre(self, t):
            raise AttributeError("FirstOrDefault")

    source = _source(genres=(FakePossibility("g", "G"),), text_ops_cls=_Old)
    dropped: list = []
    plans, _ = _plan(source, _target(), dropped)
    assert [d.action for d in plans[0].genre_decisions] == [ReferenceAction.CREATE]
    assert dropped == []


def test_fallback_casts_to_itext_when_raw_proxy_hides_genres_rc(monkeypatch):
    """GetGenres absent AND `GenresRC` invisible on the raw (base-typed pythonnet)
    proxy: the `IText(text).GenresRC` cast branch must supply the collection."""
    import sys
    import types

    genre = FakePossibility("g", "G")
    cast_calls = []

    class _RawText:                     # no GenresRC attribute at all
        pass

    class _Cast:
        def __init__(self, obj):
            cast_calls.append(obj)
            self.GenresRC = [genre]

    lcm = types.ModuleType("SIL.LCModel")
    lcm.IText = _Cast
    monkeypatch.setitem(sys.modules, "SIL", sys.modules.get("SIL") or types.ModuleType("SIL"))
    monkeypatch.setitem(sys.modules, "SIL.LCModel", lcm)

    class _NoGetGenres:
        GetGenres = None

    raw = _RawText()
    src = SimpleNamespace(Texts=_NoGetGenres())
    assert texts._source_genres(src, raw) == [genre]
    assert cast_calls == [raw]


def test_undecidable_genre_records_a_drop(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("resolver failed")

    monkeypatch.setattr(texts._references, "decide_reference", boom)
    source = _source(genres=(FakePossibility("g", "G"),))
    dropped: list = []
    plans, _ = _plan(source, _target(), dropped)
    assert plans[0].genre_decisions == ()
    assert len(dropped) == 1 and dropped[0].item_guid == "g"


# ---------------------------------------------------------------------------
# Apply side
# ---------------------------------------------------------------------------

def _link(src, tgt):
    return ReferenceDecision(action=ReferenceAction.LINK, target_item=tgt,
                             source_item=src)


def test_apply_adds_to_genres_rc_with_owner_none_and_is_idempotent(monkeypatch):
    src, tgt = FakePossibility("g", "G"), FakePossibility("g", "G")
    existing = FakePossibility("keep", "Keep")
    target_text = FakeText("tt", "T", genres=(existing,))
    seen_owner = []
    real = texts._references.apply_reference

    def spy(decision, target, owner_obj, *a, **k):
        seen_owner.append(owner_obj)
        return real(decision, target, owner_obj, *a, **k)

    monkeypatch.setattr(texts._references, "apply_reference", spy)
    plan = SimpleNamespace(genre_decisions=(_link(src, tgt),), source_guid="t1")
    dropped: list = []
    for _ in range(2):  # re-run: no duplicate member
        texts._apply_genres(plan, _target(), target_text, {}, None, None, None, dropped)
    assert seen_owner == [None, None]                  # never setattr the RC
    assert list(target_text.GenresRC) == [existing, tgt]  # existing kept
    assert dropped == []


def test_apply_reference_returning_nothing_records_a_drop(monkeypatch):
    monkeypatch.setattr(texts._references, "apply_reference", lambda *a, **k: None)
    src = FakePossibility("g", "G")
    plan = SimpleNamespace(genre_decisions=(ReferenceDecision(
        action=ReferenceAction.CREATE, source_item=src, ancestors_to_create=(src,)),),
        source_guid="t1")
    target_text = FakeText("tt", "T")
    dropped: list = []
    texts._apply_genres(plan, _target(), target_text, {}, None, None, None, dropped)
    assert list(target_text.GenresRC) == []
    assert len(dropped) == 1
    assert (dropped[0].owner_kind, dropped[0].owner_guid, dropped[0].item_guid) == (
        "Text", "t1", "g")


def test_apply_reference_raising_records_a_drop(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("create failed")

    monkeypatch.setattr(texts._references, "apply_reference", boom)
    src = FakePossibility("g", "G")
    plan = SimpleNamespace(genre_decisions=(_link(src, FakePossibility("g")),),
                           source_guid="t1")
    dropped: list = []
    texts._apply_genres(plan, _target(), FakeText("tt", "T"), {}, None, None, None, dropped)
    assert len(dropped) == 1 and "create failed" in dropped[0].reason


def test_add_failure_records_a_drop():
    class _NoAdd(FakeRefCollection):
        def Add(self, item):
            raise TypeError("read-only")

    target_text = FakeText("tt", "T")
    target_text.GenresRC = _NoAdd()
    src = FakePossibility("g", "G")
    plan = SimpleNamespace(genre_decisions=(_link(src, FakePossibility("g")),),
                           source_guid="t1")
    dropped: list = []
    texts._apply_genres(plan, _target(), target_text, {}, None, None, None, dropped)
    assert len(dropped) == 1 and "GenresRC" in dropped[0].reason


def test_report_dropped_without_target_is_not_double_reported():
    src = FakePossibility("g", "G")
    already = DroppedItemRecord(owner_kind="Text", owner_guid="t1", owner_label="",
                                field_name="GenresRC", item_name="G", item_guid="g",
                                reason="plan-time")
    plan = SimpleNamespace(genre_decisions=(ReferenceDecision(
        action=ReferenceAction.REPORT_DROPPED, source_item=src, dropped=already),),
        source_guid="t1")
    target_text = FakeText("tt", "T")
    dropped: list = []
    texts._apply_genres(plan, _target(), target_text, {}, None, None, None, dropped)
    assert dropped == [] and list(target_text.GenresRC) == []


def test_report_dropped_divergence_still_links_existing_item():
    src, tgt = FakePossibility("g", "G"), FakePossibility("g", "G2")
    diverged = DroppedItemRecord(owner_kind="Text", owner_guid="t1", owner_label="",
                                 field_name="GenresRC", item_name="G", item_guid="g",
                                 reason="diverged")
    plan = SimpleNamespace(genre_decisions=(ReferenceDecision(
        action=ReferenceAction.REPORT_DROPPED, source_item=src, target_item=tgt,
        dropped=diverged),), source_guid="t1")
    target_text = FakeText("tt", "T")
    dropped: list = []
    texts._apply_genres(plan, _target(), target_text, {}, None, None, None, dropped)
    assert list(target_text.GenresRC) == [tgt] and dropped == []


# ---------------------------------------------------------------------------
# End to end (offline): plan + apply_texts attach a shared (LINK) genre
# ---------------------------------------------------------------------------

def test_apply_texts_attaches_shared_genre_to_created_text():
    genre = FakePossibility("genre-1", "Narrative")
    tgt_genre = FakePossibility("genre-1", "Narrative")
    source = _source(genres=(genre,), text_ops_cls=_LiveShapedTextOps)
    target = _target(genre_items=(tgt_genre,))
    dropped: list = []
    plans, ctx = _plan(source, target, dropped)
    assert [d.action for d in plans[0].genre_decisions] == [ReferenceAction.LINK]
    texts.apply_texts(plans, source, target, ctx, tag=object(), report_sink=None,
                      resolver_cache={}, dropped=dropped)
    created = target.Texts._texts[-1]
    assert list(created.GenresRC) == [tgt_genre]
    assert not [d for d in dropped if d.field_name == "GenresRC"]


def test_unmapped_item_class_keeps_its_own_drop_record(monkeypatch):
    rec = DroppedItemRecord(owner_kind="Text", owner_guid="", owner_label="",
                            field_name="GenresRC", item_name="G", item_guid="g",
                            reason="unmapped item class")

    def boom(*a, **k):
        raise texts._references.UnmappedItemClassError(rec)

    monkeypatch.setattr(texts._references, "apply_reference", boom)
    src = FakePossibility("g", "G")
    plan = SimpleNamespace(genre_decisions=(_link(src, FakePossibility("g")),),
                           source_guid="t1")
    dropped: list = []
    texts._apply_genres(plan, _target(), FakeText("tt", "T"), {}, None, None, None, dropped)
    assert dropped == [rec]
