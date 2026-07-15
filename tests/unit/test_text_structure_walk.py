"""US1 (Feature 026, T011) — text container + structure walk.

Covers `Lib/texts.py`: text/paragraph/segment reproduction, free/literal
translations + notes (FR-002/003/004), genre create-via-resolver (FR-005),
the WS-mapping gate skip+report (FR-020), and non-destructive re-run (FR-021).

Offline: exercised with the shared `_fakes_texts` doubles (no flexicon host).
"""
from __future__ import annotations

from gramtrans.Lib import texts
from gramtrans.Lib.models import (
    DroppedItemRecord,
    ReferenceAction,
    Selection,
    GrammarCategory,
)
from _fakes_texts import (
    FakeWS,
    FakePossibility,
    FakePossibilityList,
    FakeLangProject,
    FakeText,
    FakeParagraph,
    FakeSegment,
    FakeProject,
    FakeCtx,
)


# WS handles: vern=1, en=2, fr=3.
WS_VERN = FakeWS("vern", 1, is_vernacular=True)
WS_EN = FakeWS("en", 2)
WS_FR = FakeWS("fr", 3)


def _source_with_one_text(free=None, literal=None, notes=(), genres=()):
    seg = FakeSegment(
        guid="seg-1",
        baseline=" abc def .",
        free=free if free is not None else {2: "the dog runs"},
        literal=literal if literal is not None else {2: "dog run"},
        notes=notes,
        wordforms=(),         # US1 has no analyses (delegated layer empty)
        analyses_rs=(),
    )
    para = FakeParagraph(guid="para-1", text_by_handle={1: "abc def."}, segments=(seg,))
    text = FakeText(
        guid="txt-1", name="Story One", abbreviation="S1",
        is_translated=True, genres=genres, paragraphs=(para,),
    )
    return FakeProject(ws_list=[WS_VERN, WS_EN, WS_FR], texts=[text])


def _target(existing_texts=(), genre_items=()):
    lp = FakeLangProject(genre_list=FakePossibilityList(genre_items))
    return FakeProject(ws_list=[WS_VERN, WS_EN], texts=list(existing_texts),
                       lang_project=lp)


def _selection():
    return Selection(categories={GrammarCategory.TEXTS: True},
                     text_picks=frozenset({"txt-1"}))


# ---------------------------------------------------------------------------
# Structure + translations + notes
# ---------------------------------------------------------------------------

def test_plan_reproduces_text_structure_and_translations():
    source = _source_with_one_text()
    target = _target()
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)

    assert len(plans) == 1
    plan = plans[0]
    assert plan.title == "Story One"
    assert plan.abbreviation == "S1"
    assert plan.is_translated is True
    assert plan.disposition == ReferenceAction.CREATE  # not in target -> ADD
    assert len(plan.paragraphs) == 1
    seg_plans = plan.paragraphs[0].segments
    assert len(seg_plans) == 1
    seg = seg_plans[0]
    # baseline keyed under the source default vernacular WS id.
    assert seg.baseline == {"vern": " abc def ."}
    assert seg.free_translation == {"en": "the dog runs"}
    assert seg.literal_translation == {"en": "dog run"}
    # No analyses in US1 (delegated layer empty, still a full plan).
    assert seg.analyses == ()


def test_plan_captures_notes_ws_gated():
    class Note:
        def __init__(self, data):
            from _fakes_texts import FakeMultiString
            self.Content = FakeMultiString(data)

    source = _source_with_one_text(notes=(Note({2: "field note"}),))
    target = _target()
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    seg = plans[0].paragraphs[0].segments[0]
    assert "field note" in seg.notes


# ---------------------------------------------------------------------------
# Genre create-via-resolver (FR-005)
# ---------------------------------------------------------------------------

def test_missing_genre_yields_create_decision():
    genre = FakePossibility(guid="genre-1", name="Narrative")
    source = _source_with_one_text(genres=(genre,))
    target = _target(genre_items=())  # empty genre list -> CREATE
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    decisions = plans[0].genre_decisions
    assert len(decisions) == 1
    assert decisions[0].action == ReferenceAction.CREATE


def test_present_genre_links_not_recreated():
    genre = FakePossibility(guid="genre-1", name="Narrative")
    tgt_genre = FakePossibility(guid="genre-1", name="Narrative")
    source = _source_with_one_text(genres=(genre,))
    target = _target(genre_items=(tgt_genre,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    decisions = plans[0].genre_decisions
    assert len(decisions) == 1
    assert decisions[0].action == ReferenceAction.LINK


# ---------------------------------------------------------------------------
# WS-mapping gate (FR-020) — unmapped WS skipped + reported
# ---------------------------------------------------------------------------

def test_unmapped_ws_translation_dropped_and_reported():
    # Free translation carries an 'en' (mapped) and 'fr' (absent in target) alt.
    source = _source_with_one_text(free={2: "the dog runs", 3: "le chien court"})
    target = _target()  # target WS = vern, en (NO fr)
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    seg = plans[0].paragraphs[0].segments[0]
    # en kept, fr dropped.
    assert seg.free_translation == {"en": "the dog runs"}
    fr_drops = [d for d in dropped if d.reason == "writing system not mapped"]
    assert any(d.field_name == "FreeTranslation" for d in fr_drops)


def test_ws_map_rename_routes_source_to_target():
    # Source 'fr' is renamed to target 'en' via ws_map -> kept under source id.
    source = _source_with_one_text(free={3: "le chien court"})
    target = _target()
    ctx = FakeCtx(source_handle=source, ws_map={"fr": "en"})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    seg = plans[0].paragraphs[0].segments[0]
    assert seg.free_translation == {"fr": "le chien court"}
    assert not [d for d in dropped if d.reason == "writing system not mapped"]


# ---------------------------------------------------------------------------
# Non-destructive re-run (FR-021) — GUID match -> UPDATE, no duplicate
# ---------------------------------------------------------------------------

def test_rerun_matches_by_guid_update_not_add():
    source = _source_with_one_text()
    existing = FakeText(guid="txt-1", name="Story One")
    target = _target(existing_texts=(existing,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    assert plans[0].disposition == ReferenceAction.UPDATE
    assert plans[0].target_guid == "txt-1"


def test_rerun_matches_by_title_when_guid_differs():
    source = _source_with_one_text()
    existing = FakeText(guid="tgt-diff", name="Story One")
    target = _target(existing_texts=(existing,))
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []

    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)
    assert plans[0].disposition == ReferenceAction.UPDATE
    assert plans[0].target_guid == "tgt-diff"


# ---------------------------------------------------------------------------
# plan_texts never writes (Principle III)
# ---------------------------------------------------------------------------

def test_plan_does_not_create_target_texts():
    source = _source_with_one_text()
    target = _target()
    ctx = FakeCtx(source_handle=source, ws_map={})
    texts.plan_texts(_selection(), source, target, ctx, {}, [])
    # No text was created on the target during Preview.
    assert target.Texts.created == []


# ---------------------------------------------------------------------------
# apply_texts — end-to-end against a fresh target
# ---------------------------------------------------------------------------

class _Sink:
    def __init__(self):
        self.msgs = []

    def Info(self, m):
        self.msgs.append(m)


def test_apply_creates_text_paragraph_segment_and_translations():
    source = _source_with_one_text()
    target = _target()
    ctx = FakeCtx(source_handle=source, ws_map={})
    dropped = []
    plans = texts.plan_texts(_selection(), source, target, ctx, {}, dropped)

    sink = _Sink()
    texts.apply_texts(plans, source, target, ctx, tag=object(),
                      report_sink=sink, resolver_cache={}, dropped=dropped)

    # A target text was created with a paragraph and a segment.
    created_text = target.Texts._texts[-1]
    assert created_text.name == "Story One"
    assert len(created_text.paragraphs) == 1
    seg = created_text.paragraphs[0].segments[0]
    # Free/literal translation written under the target 'en' handle (2).
    assert seg.free.get(2) == "the dog runs"
    assert seg.literal.get(2) == "dog run"
    assert any("Texts:" in m for m in sink.msgs)


def test_reapply_texts_does_not_duplicate_paragraphs_or_segments():
    # SC-005: a re-Move against an already-reproduced target text must not
    # re-append its paragraphs/segments (segment/analysis/gloss creation all
    # cascade from the paragraph loop).
    source = _source_with_one_text()
    target = _target()

    # Run 1 — creates the text + 1 paragraph + 1 segment.
    ctx1 = FakeCtx(source_handle=source, ws_map={})
    d1 = []
    plans1 = texts.plan_texts(_selection(), source, target, ctx1, {}, d1)
    texts.apply_texts(plans1, source, target, ctx1, tag=object(),
                      report_sink=_Sink(), resolver_cache={}, dropped=d1)
    tgt_text = target.Texts._texts[-1]
    assert len(tgt_text.paragraphs) == 1
    assert len(tgt_text.paragraphs[0].segments) == 1

    # Run 2 — same source, SAME target, fresh context. The text now matches by
    # title (disposition UPDATE); paragraphs/segments must be left as-is.
    ctx2 = FakeCtx(source_handle=source, ws_map={})
    d2 = []
    plans2 = texts.plan_texts(_selection(), source, target, ctx2, {}, d2)
    assert plans2[0].disposition == ReferenceAction.UPDATE
    sink2 = _Sink()
    texts.apply_texts(plans2, source, target, ctx2, tag=object(),
                      report_sink=sink2, resolver_cache={}, dropped=d2)

    # No duplication: still exactly 1 text, 1 paragraph, 1 segment.
    assert len(target.Texts._texts) == 1
    assert len(tgt_text.paragraphs) == 1
    assert len(tgt_text.paragraphs[0].segments) == 1
    assert any("already reproduced" in m for m in sink2.msgs)
