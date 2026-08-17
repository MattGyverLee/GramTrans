"""Text container + structure walk (Feature 026, US1 + genre + tags).

Reproduces the interlinear text container and structure: title / abbreviation /
source / translation-complete flag, paragraph/segment structure, baseline
vernacular content, free/literal translations, segment notes, genre
assignments (FR-002..005), and per-segment text-markup tags (US5, FR-017).

Plan-aware (Principle III): `plan_texts` is a pure decision pass that writes
nothing; `apply_texts` executes the plan in Move mode. Reuses feature 024's
`references.decide_reference`/`apply_reference` resolver (genres + tags),
`ws_mapping` gate for every string-bearing field (FR-020), and the
`DroppedItemRecord` never-silent channel (FR-023). Delegates each segment's
human-evaluated analyses and `AnalysesRS` alignment to `Lib/wordforms.py` (see
contracts/analysis-human-eval-walk.md and contracts/segment-alignment.md).

flexicon Operations are imported lazily INSIDE the functions so this module
stays import-safe without a live LCM host (unit tests exercise the pure plan
shape with fakes; the offline suite runs without flexicon on the path).

flexicon accessors (grounded live via FLExTools MCP static surface, 2026-07-12):
`source.Texts` (TextOperations: `GetAll`, `GetName`, `GetAbbreviation`,
`GetGenre`, `GetIsTranslated`, `GetContents`, `GetParagraphs`, `Create`,
`Find`, `SetName`, `SetAbbreviation`, `SetGenre`, `SetIsTranslated`),
`source.Paragraphs` (ParagraphOperations: `GetAll`, `GetText`, `Create`),
`source.Segments` (SegmentOperations: `GetAll`, `GetBaselineText`,
`GetFreeTranslation`, `GetLiteralTranslation`, `GetNotes`, `AppendSentence`,
`SetFreeTranslation`, `SetLiteralTranslation`).
"""
from __future__ import annotations

import hashlib
import logging
from typing import List, Optional

if __package__:
    from .models import (
        DroppedItemRecord,
        ParagraphPlan,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceFieldSpec,
        SegmentPlan,
        TextTransferPlan,
    )
    from . import references as _references
    from . import owned as _owned
else:  # pragma: no cover - executed only when run as a bare script
    from models import (  # type: ignore
        DroppedItemRecord,
        ParagraphPlan,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceFieldSpec,
        SegmentPlan,
        TextTransferPlan,
    )
    import references as _references  # type: ignore
    import owned as _owned  # type: ignore

_log = logging.getLogger("gramtrans.Lib.texts")


# ===========================================================================
# Shared WS / GUID helpers (also imported by Lib/wordforms.py)
# ===========================================================================
#
# Kept here (not in ws_mapping.py, a frozen 024 reuse seam) so the 026 walk is
# self-contained. `wordforms.py` imports these by name — a single definition of
# the WS gate + GUID reader across both 026 modules.

def _guid_str(obj) -> str:
    """Lower-cased GUID string for a source/target object, or "".

    Mirrors `categories._guid_str_from`: raw LCM object → cast via ICmObject;
    flexicon wrapper → cast its `._obj`; duck-typed test fake → `.guid`/`.Guid`
    attribute. Never raises.
    """
    if obj is None:
        return ""
    try:
        from SIL.LCModel import ICmObject  # lazy — absent in unit tests
    except Exception:
        ICmObject = None
    if ICmObject is not None:
        try:
            return str(ICmObject(obj).Guid).lower()
        except Exception:
            pass
        inner = getattr(obj, "_obj", None)
        if inner is not None:
            try:
                return str(ICmObject(inner).Guid).lower()
            except Exception:
                pass
    for attr in ("guid", "Guid"):
        val = getattr(obj, attr, None)
        if val:
            return str(val).lower()
    return ""


def source_handle_to_id(source) -> dict:
    """Best-effort ``{ws_handle: ws_id}`` for the source project.

    Reuses references._project_handle_to_id (the codebase's one WS-resolver
    reader). Returns {} on any failure — callers then key strings by raw
    handle, which still round-trips for identity WS maps.
    """
    return _references._project_handle_to_id(source)


def target_ws_ids(target) -> frozenset:
    """Set of writing-system Id strings registered in the target project.

    Empty frozenset on any failure — callers treat an empty set as "cannot
    prove unmapped" and keep the string (fail-open on the gate is safe; the
    live target's own ApplySyncableProperties silently skips a truly absent WS,
    and the offline census is the backstop). A NON-empty set enables the strict
    FR-020 gate (an id not in the set is dropped + reported).
    """
    ws_ops = getattr(target, "WritingSystems", None)
    if ws_ops is None:
        return frozenset()
    try:
        return frozenset(str(ws.Id) for ws in (ws_ops.GetAll() or []) if getattr(ws, "Id", None))
    except Exception:
        return frozenset()


def gate_ws_id(src_id: str, ws_map: dict, tgt_ws_ids: frozenset):
    """Return the target WS Id a source WS Id maps to, or None when unmapped.

    `ws_map` is the ``{source_ws_id: target_ws_id}`` dict
    (`ws_mapping.to_ws_map_dict`); identity when a source id is absent. A mapped
    id absent from a NON-empty `tgt_ws_ids` is unmapped (None) — this is the
    exact case `ApplySyncableProperties`/the setter would silently skip
    (FR-020). When `tgt_ws_ids` is empty (target WS inventory unavailable), the
    gate is a no-op and the mapped id is returned as-is.
    """
    tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
    if tgt_ws_ids and tgt_id not in tgt_ws_ids:
        return None
    return tgt_id


def capture_per_ws(getter, obj, source, ws_map, tgt_ws_ids, *,
                   owner_kind, owner_guid, owner_label, field_name, dropped):
    """WS-gated capture of a per-writing-system string field into
    ``{source_ws_id: text}`` (source-truthful keying; apply translates via
    ws_map).

    `getter(obj, ws_handle) -> str|None` is a flexicon per-WS getter
    (e.g. `Segments.GetFreeTranslation`). Iterates the source project's writing
    systems; for each non-empty slot, gates the (mapped) WS Id against the
    target inventory. An unmappable WS yields exactly one `DroppedItemRecord`
    (reason "writing system not mapped", FR-020) and that slot alone is skipped.
    Never raises — a getter that throws for a WS is treated as an empty slot.
    """
    out: dict = {}
    ws_ops = getattr(source, "WritingSystems", None)
    if ws_ops is None:
        return out
    try:
        ws_list = list(ws_ops.GetAll() or [])
    except Exception:
        return out
    for ws in ws_list:
        src_id = getattr(ws, "Id", None)
        handle = getattr(ws, "Handle", None)
        if not src_id:
            continue
        try:
            text = getter(obj, handle)
        except Exception:
            text = None
        if not text or text in ("***",):
            continue
        if gate_ws_id(str(src_id), ws_map, tgt_ws_ids) is None:
            dropped.append(DroppedItemRecord(
                owner_kind=owner_kind,
                owner_guid=owner_guid or "?",
                owner_label=owner_label,
                field_name=field_name,
                item_name=str(text)[:60],
                item_guid="",
                reason="writing system not mapped",
            ))
            continue
        out[str(src_id)] = text
    return out


def capture_vernacular(text, source, ws_map, tgt_ws_ids, *,
                       owner_kind, owner_guid, owner_label, field_name, dropped):
    """WS-gated capture of a single default-vernacular string into
    ``{source_ws_id: text}`` (for getters like `Segments.GetBaselineText` that
    return one vernacular string and take no WS handle).

    Keys the string under the source's default vernacular WS Id and gates it
    (FR-020). An unmappable vernacular WS yields one DroppedItemRecord."""
    if not text or text in ("***",):
        return {}
    src_id = _default_vern_id(source)
    if not src_id:
        return {}
    if gate_ws_id(str(src_id), ws_map, tgt_ws_ids) is None:
        dropped.append(DroppedItemRecord(
            owner_kind=owner_kind, owner_guid=owner_guid or "?",
            owner_label=owner_label, field_name=field_name,
            item_name=str(text)[:60], item_guid="",
            reason="writing system not mapped",
        ))
        return {}
    return {str(src_id): text}


def _default_vern_id(project) -> str:
    """Source default vernacular WS Id ("" on failure)."""
    try:
        tag_name = project.GetDefaultVernacularWS()
        # flexicon returns (language-tag, name); the tag is the Id.
        if isinstance(tag_name, (tuple, list)) and tag_name:
            return str(tag_name[0])
        return str(tag_name)
    except Exception:
        pass
    # Fallback: first vernacular WS in the inventory.
    ws_ops = getattr(project, "WritingSystems", None)
    if ws_ops is not None:
        try:
            for ws in (ws_ops.GetAll() or []):
                if getattr(ws, "IsVernacular", True) and getattr(ws, "Id", None):
                    return str(ws.Id)
        except Exception:
            pass
    return ""


def id_to_handle(project) -> dict:
    """``{ws_id: ws_handle}`` for a project (apply-time WS-handle lookup)."""
    ws_ops = getattr(project, "WritingSystems", None)
    if ws_ops is None:
        return {}
    try:
        return {str(ws.Id): ws.Handle for ws in (ws_ops.GetAll() or []) if getattr(ws, "Id", None)}
    except Exception:
        return {}


# ===========================================================================
# Genre reference field spec (IText.GenresRC -> LangProject.GenreListOA)
# ===========================================================================
#
# Not in references.REFERENCE_FIELD_MAP (that table is the 024 lexical closure).
# Built here as a standalone spec threaded through the shared resolver so genre
# creation reuses the SAME create-time concept<->GUID discipline (R6, FR-005).
# [PROBE] the exact list accessor (GenreListOA) on the live surface — research
# R6 target-list-accessor probe (T039).

def _genre_spec() -> ReferenceFieldSpec:
    return ReferenceFieldSpec(
        owner_class="Text",
        field_name="GenresRC",
        cardinality=ReferenceCardinality.COLLECTION,
        target_list_path=lambda target: target.Cache.LangProject.GenreListOA,
        hierarchical=True,
    )


# ===========================================================================
# Text-markup tag reference field spec (ITextTag.TagRA -> LangProject.
# TextMarkupTagsOA) — US5, FR-017, R6
# ===========================================================================
#
# Like the genre spec, a standalone ReferenceFieldSpec threaded through the
# shared 024 resolver so tag creation reuses the SAME create-time concept<->GUID
# discipline (create-allowed, GUID-preserving). Target-list accessor
# `LangProject.TextMarkupTagsOA` confirmed on the live LCM surface via FLExTools
# MCP (2026-07-12); the per-segment ITextTag write path itself has no flexicon
# wrapper and is reached raw (R6 [PROBE] carried to T039).

def _tag_spec() -> ReferenceFieldSpec:
    return ReferenceFieldSpec(
        owner_class="TextTag",
        field_name="TagRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: target.Cache.LangProject.TextMarkupTagsOA,
        hierarchical=True,
    )


def _source_text_tags(source, text) -> list:
    """Return the source text's `ITextTag` objects (US5), or [].

    Prefers a duck-typed `text.tags` (the offline fake shape). Production reaches
    the raw LCM surface: `TextOperations.GetContents(text)` -> `IStText.TagsOC`
    (no flexicon wrapper exists for text-markup tags). Never raises."""
    tags = getattr(text, "tags", None)
    if tags is not None:
        try:
            return list(tags)
        except Exception:
            return []
    text_ops = getattr(source, "Texts", None)
    contents = None
    if text_ops is not None and hasattr(text_ops, "GetContents"):
        contents = _safe(lambda: text_ops.GetContents(text))
    tags_oc = getattr(contents, "TagsOC", None)
    if tags_oc is None:
        return []
    try:
        return list(tags_oc)
    except Exception:
        return []


def _tags_by_begin_segment(source, text) -> dict:
    """Group the text's tags by their begin-segment source GUID (US5).

    A tag with no `TagRA` (no referenced possibility) or no begin segment is
    skipped — nothing to reproduce."""
    out: dict = {}
    for tag in _source_text_tags(source, text):
        if getattr(tag, "TagRA", None) is None:
            continue
        begin_guid = _guid_str(getattr(tag, "BeginSegmentRA", None))
        out.setdefault(begin_guid, []).append(tag)
    return out


def _decide_segment_tags(tags, source, target, resolver_cache, dropped):
    """Resolve each tag's `TagRA` possibility via the shared resolver →
    tuple[ReferenceDecision] (US5, FR-017).

    Create-allowed (a tag absent from the target list is CREATEd, GUID-
    preserving); an unresolvable tag (target list absent) is a REPORT_DROPPED
    decision carrying its own DroppedItemRecord. Never raises.

    Returns `(decisions, source_tag_guids)` — the second tuple is positionally
    parallel to the first and carries each owning source `ITextTag`'s OWN GUID
    (033), which the decision itself does not (it identifies the referenced
    possibility).
    """
    if not tags:
        return (), ()
    spec = _tag_spec()
    decisions = []
    src_guids = []
    for tag in tags:
        poss = getattr(tag, "TagRA", None)
        if poss is None:
            continue
        try:
            decision = _references.decide_reference(
                poss, target, spec, resolver_cache, source=source)
        except Exception:
            decision = None
        if decision is None:
            continue
        decisions.append(decision)
        src_guids.append(_guid_str(tag))
        if decision.dropped is not None:
            dropped.append(decision.dropped)
    return tuple(decisions), tuple(src_guids)


def _text_disposition(target, src_guid: str, title: str, source=None, source_text=None):
    """ADD / UPDATE-shaped disposition for one source text (FR-021).

    GUID match against the target's texts first, else a title match
    (`Texts.Find(title)`) when the text has a title. Untitled texts (empty
    title — the common shape for glossed/interlinear practice texts) can
    never match by title, so a titled-only fallback silently re-CREATEs them
    on every Move (non-idempotent). For an empty title, fall back to a
    STRUCTURAL FINGERPRINT match instead: (paragraph count, hash of the
    text's first non-empty baseline string) against each existing target
    text's own fingerprint (`_text_fingerprint`). A match → UPDATE
    (non-destructive re-run, never a duplicate); no match → ADD (modeled as
    CREATE). Returns (action, target_guid_or_None).
    """
    text_ops = getattr(target, "Texts", None)
    if text_ops is None:
        return ReferenceAction.CREATE, None
    try:
        all_targets = list(text_ops.GetAll() or [])
    except Exception:
        all_targets = []
    # GUID-first identity.
    for t in all_targets:
        if _guid_str(t) == src_guid:
            return ReferenceAction.UPDATE, src_guid
    if title:
        # Title fallback (GUID not preserved by a prior run).
        find = getattr(text_ops, "Find", None)
        if find is not None:
            try:
                match = find(title)
            except Exception:
                match = None
            if match is not None:
                return ReferenceAction.UPDATE, _guid_str(match)
    else:
        # Empty title: no name to match on. Fall back to a structural
        # fingerprint so an untitled source text still matches the target
        # text a prior Move already reproduced (idempotency).
        src_fp = _text_fingerprint(source, source_text) if source is not None else None
        if src_fp is not None:
            for t in all_targets:
                if _text_fingerprint(target, t) == src_fp:
                    return ReferenceAction.UPDATE, _guid_str(t)
    return ReferenceAction.CREATE, None


def _text_fingerprint(project, text) -> Optional[tuple]:
    """Structural fingerprint for one text: (paragraph count, sha1 of its
    first non-empty baseline string), or None when there is nothing to
    fingerprint (no baseline text found anywhere in the text).

    Used by `_text_disposition`'s empty-title fallback to recognize a target
    text a prior Move already reproduced, when the source text carries no
    title to match on (empty/blank-titled glossed/interlinear practice
    texts — finding #2's non-idempotency). Prefers a segment's baseline text
    (`Segments.GetBaselineText`, the live content for interlinear texts);
    falls back to the paragraph's own `Contents` (`Paragraphs.GetText`) when
    the text has no segments yet. Never raises.
    """
    if project is None or text is None:
        return None
    para_ops = getattr(project, "Paragraphs", None)
    if para_ops is None:
        return None
    try:
        paras = list(para_ops.GetAll(text) or [])
    except Exception:
        return None
    seg_ops = getattr(project, "Segments", None)
    first_text = ""
    for para in paras:
        if seg_ops is not None:
            try:
                segs = list(seg_ops.GetAll(para) or [])
            except Exception:
                segs = []
            for seg in segs:
                baseline = _safe(lambda s=seg: seg_ops.GetBaselineText(s))
                if baseline and baseline.strip():
                    first_text = baseline.strip()
                    break
        if first_text:
            break
        para_text = _safe(lambda p=para: para_ops.GetText(p))
        if para_text and para_text.strip():
            first_text = para_text.strip()
            break
    if not first_text:
        # No baseline text anywhere -- nothing distinctive to fingerprint;
        # matching on paragraph count alone would risk merging unrelated
        # blank texts, so decline to fingerprint-match at all.
        return None
    return (len(paras), hashlib.sha1(first_text.encode("utf-8")).hexdigest())


def _decide_genres(source_text, source, target, resolver_cache, dropped):
    """Resolve `GenresRC` via the shared resolver → tuple[ReferenceDecision].

    Each source genre possibility is decided (LINK/CREATE/UPDATE/REPORT_DROPPED)
    against `LangProject.GenreListOA`; a shared cache dedups genres reused across
    texts (FR-005). Never raises — a genre the source cannot enumerate is
    skipped (no throw), a genre that cannot resolve is a REPORT_DROPPED decision
    carrying its own DroppedItemRecord.
    """
    spec = _genre_spec()
    decisions = []
    genres = []
    try:
        genres = list(source.Texts.GetGenre(source_text) or [])
    except Exception:
        # GetGenre may return a single possibility or raise; tolerate both.
        try:
            one = source.Texts.GetGenre(source_text)
            genres = [one] if one is not None else []
        except Exception:
            genres = []
    for g in genres:
        try:
            decision = _references.decide_reference(g, target, spec, resolver_cache, source=source)
        except Exception:
            decision = None
        if decision is None:
            continue
        decisions.append(decision)
        if decision.dropped is not None:
            dropped.append(decision.dropped)
    return tuple(decisions)


def _walk_paragraphs(source_text, source, target, ctx, ws_map, tgt_ws_ids,
                     resolver_cache, dropped, text_guid, text_label,
                     tags_by_seg=None):
    """Walk the text's paragraphs → tuple[ParagraphPlan] with WS-gated content.

    For each paragraph: capture its baseline text (per-WS) and walk its segments
    (`Segments.GetAll`), building `SegmentPlan`s with WS-gated baseline /
    free+literal translation / notes (FR-002/003/004/020). Each segment's
    human-evaluated analyses + `AnalysesRS` alignment are delegated to
    `Lib/wordforms.py` (US2, T025). Per-segment text-markup tag references
    (US5, FR-017) are resolved via `_decide_segment_tags` against the tags that
    begin at that segment (`tags_by_seg`)."""
    if __package__:
        from . import wordforms as _wordforms
    else:  # pragma: no cover
        import wordforms as _wordforms  # type: ignore

    tags_by_seg = tags_by_seg or {}
    para_plans: List[ParagraphPlan] = []
    seg_ops = getattr(source, "Segments", None)
    para_ops = getattr(source, "Paragraphs", None)
    try:
        paragraphs = list(source.Texts.GetParagraphs(source_text) or [])
    except Exception:
        try:
            paragraphs = list(para_ops.GetAll(source_text) or []) if para_ops else []
        except Exception:
            paragraphs = []

    for para in paragraphs:
        para_guid = _guid_str(para)
        para_baseline = capture_per_ws(
            lambda o, h: para_ops.GetText(o, h), para, source, ws_map, tgt_ws_ids,
            owner_kind="StTxtPara", owner_guid=para_guid, owner_label=text_label,
            field_name="Contents", dropped=dropped,
        ) if para_ops else {}

        seg_plans: List[SegmentPlan] = []
        try:
            segments = list(seg_ops.GetAll(para) or []) if seg_ops else []
        except Exception:
            segments = []
        for seg in segments:
            seg_guid = _guid_str(seg)
            baseline_text = _safe(lambda: seg_ops.GetBaselineText(seg)) if seg_ops else None
            baseline = capture_vernacular(
                baseline_text, source, ws_map, tgt_ws_ids,
                owner_kind="Segment", owner_guid=seg_guid, owner_label=text_label,
                field_name="BaselineText", dropped=dropped,
            )
            free_tr = capture_per_ws(
                lambda o, h: seg_ops.GetFreeTranslation(o, h), seg, source, ws_map, tgt_ws_ids,
                owner_kind="Segment", owner_guid=seg_guid, owner_label=text_label,
                field_name="FreeTranslation", dropped=dropped,
            )
            lit_tr = capture_per_ws(
                lambda o, h: seg_ops.GetLiteralTranslation(o, h), seg, source, ws_map, tgt_ws_ids,
                owner_kind="Segment", owner_guid=seg_guid, owner_label=text_label,
                field_name="LiteralTranslation", dropped=dropped,
            )
            notes = _capture_notes(seg, seg_ops, source, ws_map, tgt_ws_ids,
                                   seg_guid, text_label, dropped)

            # US2 delegation (T025): human-evaluated analyses + alignment.
            analyses = tuple(_wordforms.plan_analyses(
                seg, source, target, ctx, resolver_cache, dropped))
            alignment = tuple(_wordforms.plan_alignment(seg, ctx, dropped))

            # US5 (T034): per-segment text-markup tag references.
            tag_decisions, tag_source_guids = _decide_segment_tags(
                tags_by_seg.get(seg_guid, ()), source, target,
                resolver_cache, dropped)

            seg_plans.append(SegmentPlan(
                source_guid=seg_guid,
                baseline=baseline,
                free_translation=free_tr,
                literal_translation=lit_tr,
                notes=notes,
                analyses=analyses,
                alignment=alignment,
                tag_decisions=tag_decisions,
                tag_source_guids=tag_source_guids,
            ))
        para_plans.append(ParagraphPlan(
            source_guid=para_guid,
            segments=tuple(seg_plans),
            baseline=para_baseline,
        ))
    return tuple(para_plans)


def _capture_notes(seg, seg_ops, source, ws_map, tgt_ws_ids, seg_guid, text_label, dropped):
    """WS-gated capture of a segment's notes → tuple[str] (best-alt per note).

    `Segments.GetNotes` yields note objects; each note's content is a
    multistring. We capture each note's non-empty WS slots, gating each WS
    (FR-020). A note with no mappable slot contributes nothing (its drops are
    already reported)."""
    out = []
    if seg_ops is None:
        return tuple(out)
    try:
        note_objs = list(seg_ops.GetNotes(seg) or [])
    except Exception:
        return tuple(out)
    for note in note_objs:
        content = getattr(note, "Content", None) or note
        slots = _references._multistring_dict(content)
        if not slots:
            # A plain string note.
            text = note if isinstance(note, str) else None
            if text:
                out.append(text)
            continue
        s2i = source_handle_to_id(source)
        for handle, text in slots.items():
            if not text:
                continue
            src_id = s2i.get(handle, str(handle))
            if gate_ws_id(str(src_id), ws_map, tgt_ws_ids) is None:
                dropped.append(DroppedItemRecord(
                    owner_kind="Segment", owner_guid=seg_guid or "?",
                    owner_label=text_label, field_name="Notes",
                    item_name=str(text)[:60], item_guid="",
                    reason="writing system not mapped",
                ))
                continue
            out.append(text)
    return tuple(out)


# ===========================================================================
# plan_texts (T012) / apply_texts (T013)
# ===========================================================================

def plan_texts(selection, source, target, ctx, resolver_cache, dropped) -> List:
    """US1 pure/decision pass — build one TextTransferPlan per selected text.

    See module docstring + contracts/text-structure-walk.md. MUST NOT mutate the
    target. A text with zero human-evaluated analyses still yields a full plan
    (structure + translations + notes) — the analysis layer is simply empty.
    Returns a list of `models.TextTransferPlan`.
    """
    text_ops = getattr(source, "Texts", None)
    if text_ops is None:
        return []
    picks = set(getattr(selection, "text_picks", None) or ())
    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_ws_ids = target_ws_ids(target)

    try:
        all_texts = list(text_ops.GetAll() or [])
    except Exception:
        return []

    plans: List[TextTransferPlan] = []
    for text in all_texts:
        src_guid = _guid_str(text)
        if picks and src_guid not in picks:
            continue

        # Feature 033: capture the owned IStText contents GUID so the target's
        # contents object is created under the SAME identity (read-only here).
        try:
            src_contents_guid = _guid_str(text.ContentsOA) if text.ContentsOA is not None else ""
        except Exception:  # noqa: BLE001 -- absent/duck fake
            src_contents_guid = ""

        title = _best_str(text_ops, text, "GetName")
        abbrev = _best_str(text_ops, text, "GetAbbreviation")
        try:
            is_translated = text_ops.GetIsTranslated(text)
        except Exception:
            is_translated = None
        source_text_str = _best_str(text_ops, text, "GetSource") or ""

        action, target_guid = _text_disposition(
            target, src_guid, title, source=source, source_text=text)
        genre_decisions = _decide_genres(text, source, target, resolver_cache, dropped)
        tags_by_seg = _tags_by_begin_segment(source, text)
        paragraphs = _walk_paragraphs(
            text, source, target, ctx, ws_map, tgt_ws_ids,
            resolver_cache, dropped, src_guid, title,
            tags_by_seg=tags_by_seg,
        )

        plans.append(TextTransferPlan(
            source_guid=src_guid,
            contents_guid=src_contents_guid,
            title=title,
            disposition=action,
            genre_decisions=genre_decisions,
            paragraphs=paragraphs,
            target_guid=target_guid,
            abbreviation=abbrev,
            source_text=source_text_str,
            is_translated=is_translated,
        ))
    _log.debug("plan_texts: built %d text plan(s) (picks=%d)", len(plans), len(picks))
    return plans


def _best_str(ops, obj, method: str) -> str:
    """Call a best-alt getter (`GetName`/`GetAbbreviation`) → "" on absence."""
    fn = getattr(ops, method, None)
    if fn is None:
        return ""
    try:
        val = fn(obj)
    except Exception:
        return ""
    if not val or val in ("***",):
        return ""
    return str(val)


def apply_texts(plans, source, target, ctx, tag, report_sink,
                resolver_cache, dropped) -> None:
    """US1 Move-mode apply — execute the TextTransferPlans.

    See contracts/text-structure-walk.md. Creates/updates each text, its
    paragraphs and segments, writes baseline / free+literal translations
    non-destructively (FR-021), applies genre and (US5) text-markup tag
    ReferenceDecisions, wires the human-evaluated analyses + alignment via
    `Lib/wordforms.py`, and residue-tags the created objects (Carrier B, R8).
    Segment notes are captured in the plan but currently reported rather than
    reproduced — no confirmed note write path (see `_apply_segment_notes`,
    deferred to the R5-class live probe, T039).
    """
    if not plans:
        return None
    if __package__:
        from . import wordforms as _wordforms
        from .residue import apply_residue
    else:  # pragma: no cover
        import wordforms as _wordforms  # type: ignore
        from residue import apply_residue  # type: ignore

    text_ops = getattr(target, "Texts", None)
    para_ops = getattr(target, "Paragraphs", None)
    seg_ops = getattr(target, "Segments", None)
    if text_ops is None:
        return None

    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_id2h = id_to_handle(target)
    default_vern_handle = _default_vern_handle(target)

    # Provision the one human agent up-front (US2, FR-009); cached on ctx so
    # every evaluation this run reuses it.
    agent_decision = _wordforms.plan_agent(target, ctx)
    _wordforms.apply_agent(agent_decision, target, ctx)

    _added = _updated = _already = 0
    for plan in plans:
        target_text = _resolve_or_create_text(plan, text_ops, ws_map, tgt_id2h, dropped)
        if target_text is None:
            continue
        if plan.disposition == ReferenceAction.UPDATE:
            _updated += 1
        else:
            _added += 1
        # Non-string container props (FR-002).
        _set_if(text_ops, "SetAbbreviation", target_text, plan.abbreviation)
        if plan.is_translated is not None:
            _safe(lambda: text_ops.SetIsTranslated(target_text, plan.is_translated))
        # Genres (FR-005) via the shared resolver.
        _apply_genres(plan, target, target_text, resolver_cache, tag, source, ws_map, dropped)
        # Residue-tag the container (R8).
        _safe(lambda: apply_residue(target_text, default_vern_handle, tag, class_name="Text"))

        already = _apply_paragraphs(plan, target, target_text, para_ops, seg_ops,
                                    ctx, tag, ws_map, tgt_id2h, default_vern_handle,
                                    _wordforms, apply_residue, resolver_cache, source, dropped)
        if already:
            _already += 1
    if report_sink is not None and hasattr(report_sink, "Info"):
        _safe(lambda: report_sink.Info(
            f"[Move] Texts: {_added} added, {_updated} updated, "
            f"{_already} already reproduced (structure left as-is) "
            f"(dropped items so far: {len(dropped)})."))
    return None


def _default_vern_handle(project):
    try:
        return project.GetDefaultVernacularWSHandle()
    except Exception:
        return None


def _resolve_or_create_text(plan, text_ops, ws_map, tgt_id2h, dropped):
    """UPDATE (by GUID/title) or ADD a target text; returns the target object."""
    if plan.disposition == ReferenceAction.UPDATE and plan.target_guid:
        try:
            for t in (text_ops.GetAll() or []):
                if _guid_str(t) == plan.target_guid:
                    return t
        except Exception:
            pass
    # ADD: create by name. Genre attached separately (create with None genre).
    name = plan.title or "(untitled)"
    # Site-1 duplicate-name collision (finding #1): `TextOperations.Create`
    # requires a UNIQUE name and raises the generic `FP_ParameterError("A
    # text with the name '...' already exists.")` otherwise -- e.g. two
    # distinct source texts sharing a title, or a name-normalization gap
    # between this Create and the disposition-time `Find` (:_text_disposition)
    # that missed the match. That generic exception used to surface as a
    # misleading "text create failed" drop, silently discarding the whole
    # text. Check `Exists(name)` first; on a hit, reuse the existing text
    # (treat it as an UPDATE-by-name) instead of letting Create blow up.
    exists = getattr(text_ops, "Exists", None)
    if exists is not None:
        try:
            already_exists = exists(name)
        except Exception:
            already_exists = False
        if already_exists:
            find = getattr(text_ops, "Find", None)
            existing = None
            if find is not None:
                try:
                    existing = find(name)
                except Exception:
                    existing = None
            if existing is not None:
                return existing
    try:
        # GUID-preserved (033): the Text and its owned StText contents both
        # carry their source identity, so a re-run resolves them instead of
        # minting a second copy.
        return text_ops.Create(name, None,
                               guid=plan.source_guid or None,
                               contents_guid=getattr(plan, "contents_guid", None) or None)
    except Exception as e:  # never silent
        dropped.append(DroppedItemRecord(
            owner_kind="Text", owner_guid=plan.source_guid or "?",
            owner_label=plan.title, field_name="Create",
            item_name=plan.title, item_guid="",
            reason=f"text create failed: {type(e).__name__}",
        ))
        return None


def _apply_genres(plan, target, target_text, resolver_cache, tag, source, ws_map, dropped):
    spec = _genre_spec()
    for decision in plan.genre_decisions:
        _safe(lambda d=decision: _references.apply_reference(
            d, target, target_text, spec, resolver_cache, tag,
            ws_map=ws_map or None, source=source, dropped=dropped,
        ))


def _apply_segment_notes(seg_plan, tgt_seg, dropped):
    """Reproduce (or report) a segment's captured notes.

    flexicon's `SegmentOperations` exposes `GetNotes` (read) but no note
    setter/factory wrapper, and the raw `ISegment.NotesOS` + `INoteFactory`
    write path is an unconfirmed live surface (the CLR `run_module` probe is
    down — R5-class deferral). Rather than silently discard a captured note
    (the pre-census behaviour, an SC-003 violation), emit one DroppedItemRecord
    per note so the loss is always surfaced (never-silent). Reproduction via the
    raw note factory is deferred to the same live-probe pass as R5 (T039).
    """
    for note_text in (seg_plan.notes or ()):
        dropped.append(DroppedItemRecord(
            owner_kind="Segment", owner_guid=seg_plan.source_guid or "?",
            owner_label="", field_name="NotesOS",
            item_name=str(note_text)[:60], item_guid="",
            reason="segment note not reproduced: no confirmed note write path "
                   "(deferred to live-probe, T039)",
        ))


def _apply_segment_tags(seg_plan, target, target_text, tgt_seg, resolver_cache,
                        tag, source, ws_map, dropped):
    """US5 Move-mode — reproduce the per-segment text-markup tag references.

    For each tag ReferenceDecision on the segment: apply it via the shared
    resolver (LINK the existing possibility / CREATE the absent one, GUID-
    preserving, FR-017) to obtain the target tag possibility, then create the
    per-segment `ITextTag` referencing it. A REPORT_DROPPED (unresolvable) tag
    was already reported at plan time — nothing is written for it here."""
    if not seg_plan.tag_decisions:
        return
    spec = _tag_spec()
    tt_ops = getattr(target, "TextTags", None)
    # 033: positionally parallel source ITextTag GUIDs. A short/absent tuple
    # yields "" for that index, which MINTS a fresh identity (logged) rather
    # than borrowing some other object's GUID.
    src_tag_guids = getattr(seg_plan, "tag_source_guids", ()) or ()
    for idx, decision in enumerate(seg_plan.tag_decisions):
        if getattr(decision, "action", None) == ReferenceAction.REPORT_DROPPED:
            continue  # unresolvable — already reported (FR-017/023)
        possibility = _safe(lambda d=decision: _references.apply_reference(
            d, target, None, spec, resolver_cache, tag,
            ws_map=ws_map or None, source=source, dropped=dropped,
        ))
        if possibility is None:
            possibility = getattr(decision, "target_item", None)
        if possibility is None:
            continue
        src_tag_guid = src_tag_guids[idx] if idx < len(src_tag_guids) else ""
        _create_text_tag(target, target_text, tgt_seg, possibility, tt_ops,
                         seg_plan, dropped, src_tag_guid=src_tag_guid)


def _create_text_tag(target, target_text, tgt_seg, possibility, tt_ops,
                     seg_plan, dropped, src_tag_guid=""):
    """Create one per-segment `ITextTag` wired to `possibility` (US5).

    Prefers a duck-typed `target.TextTags.Create` (offline seam / any future
    wrapper); otherwise reaches the raw LCM surface (`IStText.TagsOC` +
    `ITextTagFactory`, R6 [PROBE]/T039). A single-segment span (begin==end) is
    the offline-provable slice; a multi-segment span + exact analysis indices
    are part of the deferred live confirmation. A tag that cannot be created is
    reported, never silently dropped."""
    if tt_ops is not None and hasattr(tt_ops, "Create"):
        created = _safe(lambda: tt_ops.Create(target_text, possibility, tgt_seg, tgt_seg))
        if created is not None:
            return created
    created = _safe(lambda: _raw_create_text_tag(
        target, target_text, tgt_seg, possibility, src_tag_guid=src_tag_guid))
    if created is None:
        dropped.append(DroppedItemRecord(
            owner_kind="TextTag", owner_guid=seg_plan.source_guid or "?",
            owner_label="", field_name="TagRA", item_name="",
            item_guid="", reason="text-markup tag reference could not be created",
        ))
    return created


def _segment_factory(target):
    """`ISegmentFactory`, or None host-free. Seam for tests. Never raises."""
    try:
        from SIL.LCModel import ISegmentFactory  # lazy — absent offline
    except Exception:  # noqa: BLE001
        return None
    try:
        return target.GetFactory(ISegmentFactory)
    except Exception:  # noqa: BLE001
        return None


def _segment_begin_offset(seg):
    """A segment's `BeginOffset` as int, or None. `BeginOffset` is read-only on
    `ISegment` (MCP-confirmed), which is why segments must be POSITIONED at
    creation via the factory overload rather than moved afterward. Seam for
    tests. Never raises."""
    try:
        from SIL.LCModel import ISegment  # lazy — absent offline
        return int(ISegment(seg).BeginOffset)
    except Exception:  # noqa: BLE001
        pass
    try:
        return int(getattr(seg, "BeginOffset"))
    except Exception:  # noqa: BLE001
        return None


def _rebuild_segments_with_source_guids(target, seg_ops, new_para, seg_plans,
                                        tgt_segments, text_label):
    """033 Option A — give the auto-created segments their SOURCE GUIDs.

    LCM auto-segments when a paragraph's `Contents` is set, minting identities
    (see `_log_segment_guid_loss`). This re-creates each of those segments at
    its OWN existing offset via

        ISegmentFactory.Create(IStTxtPara owner, int initialOffset,
                               LcmCache cache, Guid guid)

    (MCP-confirmed overload) so the segment keeps its source identity.

    Why this shape, and not the two obvious alternatives:

    - NOT create-empty-then-`AppendSentence`: that wrapper auto-inserts a
      ". " sentence terminator when the paragraph does not already end in
      .!? (and a " " when it does), and strips its input. Building a
      paragraph that way FABRICATES punctuation absent from the source and
      corrupts the baseline — far worse than a minted GUID.
    - NOT create-then-assign-offset: `ISegment.BeginOffset` is read-only, so
      a segment cannot be repositioned after creation.

    Reusing each auto-segment's own offset (rather than the source's) keeps
    the offsets guaranteed-valid for THIS target's `Contents` and leaves the
    positional pairing exactly as the caller's alignment loop already had it;
    only identity changes. `Contents` is never touched, so the text is
    untouched by construction.

    Conservative by design — returns the rebuilt list, or None to keep the
    caller's existing segments unchanged (host-free, missing factory,
    incomplete identity, already-preserved, or ANY failure). On a partial
    failure the paragraph is left to the caller's fallback, and the caller
    still logs the loss, so the never-silent contract holds either way.
    """
    pairs = min(len(tgt_segments), len(seg_plans))
    if pairs <= 0:
        return None
    guids = [(getattr(seg_plans[i], "source_guid", "") or "") for i in range(pairs)]
    if not all(guids):
        return None  # incomplete identity — do not disturb a working paragraph
    if all(_guid_str(tgt_segments[i]) == guids[i].lower() for i in range(pairs)):
        return None  # already preserved (e.g. a future create-first path)
    factory = _segment_factory(target)
    if factory is None:
        return None  # host-free / no factory — caller keeps auto segments
    cache = getattr(target, "Cache", None)
    if cache is None:
        return None
    offsets = [_segment_begin_offset(tgt_segments[i]) for i in range(pairs)]
    if any(o is None for o in offsets):
        return None
    parsed = [_parse_dotnet_guid(g) for g in guids]
    if any(p is None for p in parsed):
        return None
    # Delete first: a segment cannot be repositioned, so the auto-created one
    # must go before its replacement can occupy the same offset.
    for i in range(pairs):
        try:
            seg_ops.Delete(tgt_segments[i])
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "texts: segment GUID rebuild aborted in %r (delete failed at "
                "index %d: %s); keeping the auto-created segments.",
                text_label or "<untitled>", i, exc)
            return None
    rebuilt = []
    for i in range(pairs):
        try:
            rebuilt.append(factory.Create(new_para, offsets[i], cache, parsed[i]))
        except Exception as exc:  # noqa: BLE001
            _log.error(
                "texts: segment GUID rebuild FAILED in %r at index %d (%s). "
                "%d of %d segments were re-created; the paragraph text is "
                "untouched, but its segmentation is now incomplete. "
                "Re-run against a freshly restored target.",
                text_label or "<untitled>", i, exc, len(rebuilt), pairs)
            return rebuilt or None
    _log.info(
        "texts: re-created %d segment(s) in %r carrying their source GUIDs "
        "(033 Option A).", len(rebuilt), text_label or "<untitled>")
    return rebuilt


def _parse_dotnet_guid(guid_str):
    """`System.Guid` for `guid_str`, or None (host-free / malformed)."""
    if not guid_str:
        return None
    try:
        from System import Guid as _DotNetGuid  # lazy — absent offline
        return _DotNetGuid.Parse(str(guid_str))
    except Exception:  # noqa: BLE001
        return None


def _log_segment_guid_loss(tgt_segments, seg_plans, text_label) -> int:
    """Record that N segments could not keep their source GUIDs (033).

    The 033 invariant allows a GUID loss that is **justified and logged**; what
    it forbids is a SILENT one. This is the logged half for segments.

    Why the loss happens: `_create_paragraph` sets the paragraph's `Contents`,
    and LCM auto-segments on that write. By the time the alignment loop runs,
    every positional slot is already filled, so `AppendSentence(..., guid=)` --
    the only GUID-preserving path -- never fires, and LCM GUIDs are immutable
    once created. Measured live 2026-08-15: 101 of 104 segments, 0 preserved.

    Deliberately NOT a `DroppedItemRecord`: the segment IS reproduced (baseline,
    translations, notes, analyses and `AnalysesRS` all land on it) -- only its
    identity differs. Filing these as drops would inflate the single unified
    never-silent drop channel with non-drops and corrupt the drop metric the
    fidelity census and full-copy stress test read.

    One aggregated WARNING per paragraph rather than one per segment: at ~101
    per run the per-segment form would bury the log it is meant to inform.
    Returns the number of lost GUIDs (0 = nothing logged).
    """
    lost = 0
    for idx, seg_plan in enumerate(seg_plans):
        if idx >= len(tgt_segments):
            break
        src_guid = (getattr(seg_plan, "source_guid", "") or "").lower()
        if not src_guid:
            continue
        if _guid_str(tgt_segments[idx]) != src_guid:
            lost += 1
    if lost:
        _log.warning(
            "texts: %d segment(s) in %r kept a NEW identity instead of the "
            "source GUID. Reason: LCM auto-segments when paragraph Contents is "
            "set, so the positional slot is already filled and "
            "AppendSentence(guid=) never runs; LCM GUIDs are immutable after "
            "create. The segments themselves ARE reproduced -- only their "
            "identity differs -- so they are not reported as dropped items. "
            "See specs/033-guid-preservation/TODO.md (Segment).",
            lost, text_label or "<untitled>")
    return lost


def _raw_create_text_tag(target, target_text, tgt_seg, possibility,
                         src_tag_guid=""):
    """Raw-LCM per-segment `ITextTag` creation (R6 [PROBE]/T039).

    No flexicon wrapper exists for text-markup tags, so this is the Principle II
    fallback: create via `ITextTagFactory`, own it under the text's
    `IStText.TagsOC`, and wire `TagRA` + begin/end segment. Wrapped by `_safe`
    at the call site so an unconfirmed accessor degrades to a reported drop
    rather than aborting the walk.

    `src_tag_guid` is the OWNING source `ITextTag`'s own GUID (033) — never the
    referenced possibility's — so a re-run recognises the tag it already made.
    Empty mints a fresh identity, and the helper logs that it did."""
    from SIL.LCModel import IStText, ITextTagFactory  # lazy — absent offline
    contents = target.Texts.GetContents(target_text)
    st_text = IStText(contents)
    tag_obj = _owned._create_owned_via_factory(
        ITextTagFactory(target.GetFactory(ITextTagFactory)),
        src_tag_guid, "TextTag")
    if tag_obj is None:
        return None
    st_text.TagsOC.Add(tag_obj)
    tag_obj.TagRA = possibility
    tag_obj.BeginSegmentRA = tgt_seg
    tag_obj.EndSegmentRA = tgt_seg
    return tag_obj


def _raw_create_blank_paragraph(target, target_text, ws_handle, guid=None):
    """Back-compat alias: a blank paragraph is just verbatim empty content."""
    return _raw_create_paragraph(target, target_text, "", ws_handle, guid)


def _raw_create_paragraph(target, target_text, content, ws_handle, guid=None):
    """Raw-LCM paragraph create that writes `content` VERBATIM.

    Reproduces `ParagraphOperations.Create`'s OWN internal raw path
    (`IStTxtParaFactory.Create()` -> own under the text's
    `ContentsOA.ParagraphsOS` -> set `Contents`) in order to bypass two
    interactive-API conveniences in the wrapper that are wrong for faithful
    reproduction:

    1. **Blank content** (FIX 3, Site-2 finding #1) — the wrapper raises
       `FP_ParameterError("Content cannot be empty")`, but a genuinely blank
       source paragraph is common between segments/headers in glossed &
       interlinear practice texts, and must be reproduced as-is.
    2. **Whitespace stripping** (flexicon#242) — the wrapper does
       `content.strip()` and then writes the STRIPPED value
       (`ParagraphOperations.py:171`), so a source paragraph `'ká '` lands as
       `'ká'`. Silently: no exception, no drop record. Measured live on
       Ejagham Mini as 44 paragraphs + 41 segment baselines altered.

    Both are the same class of defect — a guard/convenience meant for a human
    typing text, applied to a client copying it. Writing `Contents` directly
    is the only way to be byte-faithful until upstream ships flexicon#242.

    Wrapped by `_safe` at the call site so an unconfirmed accessor degrades
    to a reported drop rather than aborting the walk."""
    from SIL.LCModel import IText, IStTxtParaFactory  # lazy — absent offline
    from SIL.LCModel.Core.Text import TsStringUtils
    text_obj = IText(target_text)
    factory = IStTxtParaFactory(target.GetFactory(IStTxtParaFactory))
    # GUID-preserved (033): mirrors ParagraphOperations.Create's guid= support
    # so the blank-paragraph bypass does not silently regenerate identity.
    parsed = None
    if guid:
        try:
            from System import Guid as _DotNetGuid
            parsed = _DotNetGuid.Parse(str(guid))
        except Exception:  # noqa: BLE001 -- malformed -> fall back to a new GUID
            parsed = None
    para = factory.Create(parsed) if parsed is not None else factory.Create()
    text_obj.ContentsOA.ParagraphsOS.Add(para)
    # VERBATIM -- no strip(). This is the whole point of the raw path.
    para.Contents = TsStringUtils.MakeString(content or "", ws_handle)
    return para


def _create_paragraph(para_ops, target, target_text, content, ws_handle, guid=None):
    """Create one target paragraph, faithfully reproducing a blank source
    paragraph instead of letting `ParagraphOperations.Create`'s empty-content
    guard cascade into a generic "paragraph create failed" drop (and, in turn,
    into Segment/alignment "no copied target referent" drops downstream).

    Content goes through the normal `ParagraphOperations.Create` (residue
    tagging, `_TransactionCM`, etc. all apply) EXCEPT in the two cases where
    that wrapper would not reproduce the source faithfully:

    - blank content — the wrapper's empty-content guard rejects it;
    - content with meaningful leading/trailing whitespace — the wrapper
      strips it and writes the stripped value (flexicon#242), losing it
      silently.

    Those route through `_raw_create_paragraph`, which writes `Contents`
    verbatim. The condition is deliberately narrow (`content != stripped`)
    so the overwhelming majority of paragraphs keep the wrapper's behaviour
    unchanged; revert this branch once flexicon#242 ships.

    Returns None (never raises) when even the raw path fails — the caller
    reports that as a distinct, non-generic drop reason (the paragraph truly
    has no mappable content and no confirmed raw-create surface).
    """
    if content and content.strip():
        if content != content.strip():
            # flexicon#242: the wrapper would silently drop the surrounding
            # whitespace. Write it verbatim instead.
            raw = _safe(lambda: _raw_create_paragraph(
                target, target_text, content, ws_handle, guid))
            if raw is not None:
                return raw
            # Raw surface unavailable (host-free/older LCM): fall through to
            # the wrapper rather than lose the paragraph entirely -- a
            # stripped paragraph beats no paragraph, and it is logged.
            _log.warning(
                "texts: paragraph raw-create unavailable; falling back to the "
                "stripping wrapper, so leading/trailing whitespace in %r will "
                "be lost (flexicon#242).", content[:40])
        return para_ops.Create(target_text, content, ws_handle, guid=guid)
    return _safe(lambda: _raw_create_paragraph(
        target, target_text, content or "", ws_handle, guid))


def _apply_paragraphs(plan, target, target_text, para_ops, seg_ops, ctx, tag,
                      ws_map, tgt_id2h, default_vern_handle, _wordforms,
                      apply_residue, resolver_cache, source, dropped):
    """Reproduce the text's paragraphs/segments (+ analyses + alignment).

    Returns True when the text was already reproduced by a prior run and its
    structure is left as-is (SC-005 idempotent no-op); False when paragraphs
    were created this run."""
    if para_ops is None or seg_ops is None:
        return False
    # Idempotency (SC-005): never re-append paragraphs/segments to a text a
    # prior run already reproduced. Segment, analysis and gloss creation all
    # cascade from this paragraph loop, so a re-Move against an already-
    # populated target text must be a structural no-op. When the target text
    # already carries paragraphs, its structure + analyses + alignment are
    # present -- leave them as-is (surfaced in the run summary as "already
    # present", never silently duplicated).
    existing = _safe(lambda: list(para_ops.GetAll(target_text) or [])) or []
    if existing:
        _log.info("apply_texts: %r already reproduced (%d paragraph(s)); "
                  "re-Move leaves its structure as-is (SC-005)",
                  plan.title, len(existing))
        return True
    for para_plan in plan.paragraphs:
        content = _first_mapped(para_plan.baseline, ws_map, tgt_id2h)
        if content is None:
            # Reconstruct paragraph content from its segment baselines.
            content = " ".join(
                (_first_mapped(s.baseline, ws_map, tgt_id2h) or "")
                for s in para_plan.segments
            ).strip()
        try:
            new_para = _create_paragraph(
                para_ops, target, target_text, content, default_vern_handle,
                guid=para_plan.source_guid or None)
        except Exception as e:
            dropped.append(DroppedItemRecord(
                owner_kind="StTxtPara", owner_guid=para_plan.source_guid or "?",
                owner_label=plan.title, field_name="Create",
                item_name=(content or "")[:60], item_guid="",
                reason=f"paragraph create failed: {type(e).__name__}",
            ))
            continue
        if new_para is None:
            # A genuinely blank source paragraph whose raw-create fallback
            # also failed (no confirmed write surface) — a DISTINCT reason
            # from the generic exception label above, per FIX 3.
            dropped.append(DroppedItemRecord(
                owner_kind="StTxtPara", owner_guid=para_plan.source_guid or "?",
                owner_label=plan.title, field_name="Create",
                item_name="", item_guid="",
                reason="paragraph has no mappable baseline text",
            ))
            continue
        _safe(lambda: apply_residue(new_para, default_vern_handle, tag, class_name="StTxtPara"))

        # Align target segments to source segments positionally; append
        # sentences for any the parser did not produce.
        try:
            tgt_segments = list(seg_ops.GetAll(new_para) or [])
        except Exception:
            tgt_segments = []
        # 033 Option A: LCM auto-segmented these under minted identities.
        # Re-create them at their own offsets carrying the source GUIDs. Must
        # run BEFORE the loop below, which wires fields/analyses/AnalysesRS
        # onto these very segment objects. Conservative: returns None (keep
        # the auto segments) host-free or on any failure.
        _rebuilt = _safe(lambda: _rebuild_segments_with_source_guids(
            target, seg_ops, new_para, para_plan.segments, tgt_segments,
            plan.title))
        if _rebuilt:
            tgt_segments = list(_rebuilt) + tgt_segments[len(_rebuilt):]
        # Option B backstop: whatever identity the segments ended up with, a
        # GUID that could NOT be preserved is logged, never silent.
        _safe(lambda: _log_segment_guid_loss(
            tgt_segments, para_plan.segments, plan.title))
        for idx, seg_plan in enumerate(para_plan.segments):
            tgt_seg = tgt_segments[idx] if idx < len(tgt_segments) else None
            if tgt_seg is None:
                base = _first_mapped(seg_plan.baseline, ws_map, tgt_id2h) or ""
                tgt_seg = _safe(lambda b=base, sp=seg_plan: seg_ops.AppendSentence(
                    new_para, b, default_vern_handle,
                    guid=sp.source_guid or None))
                if tgt_seg is None:
                    dropped.append(DroppedItemRecord(
                        owner_kind="Segment", owner_guid=seg_plan.source_guid or "?",
                        owner_label=plan.title, field_name="AppendSentence",
                        item_name=base[:60], item_guid="",
                        reason="target segment slot could not be created",
                    ))
                    continue
            _write_segment_fields(seg_plan, target, seg_ops, tgt_seg, ws_map, tgt_id2h)
            _apply_segment_notes(seg_plan, tgt_seg, dropped)
            # US2: analyses + AnalysesRS alignment.
            _wordforms.apply_analyses(
                seg_plan.analyses, source_of(ctx), target, ctx, tag,
                None, dropped)
            _wordforms.apply_alignment(tgt_seg, seg_plan.alignment, ctx, dropped)
            # US5 (T035): per-segment text-markup tag references.
            _apply_segment_tags(seg_plan, target, target_text, tgt_seg,
                                resolver_cache, tag, source, ws_map, dropped)
    return False


def source_of(ctx):
    """Best-effort source handle off the run context (`source_handle`)."""
    return getattr(ctx, "source_handle", None)


def _write_segment_fields(seg_plan, target, seg_ops, tgt_seg, ws_map, tgt_id2h):
    """Non-destructive per-WS write of free/literal translation (FR-021).

    Never blanks a populated target alt from an empty source alt — only source
    slots present in the plan are written."""
    for src_id, text in (seg_plan.free_translation or {}).items():
        tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
        h = tgt_id2h.get(tgt_id)
        if h is not None and text:
            _safe(lambda t=text, hh=h: seg_ops.SetFreeTranslation(tgt_seg, t, hh))
    for src_id, text in (seg_plan.literal_translation or {}).items():
        tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
        h = tgt_id2h.get(tgt_id)
        if h is not None and text:
            _safe(lambda t=text, hh=h: seg_ops.SetLiteralTranslation(tgt_seg, t, hh))


def _first_mapped(ws_dict, ws_map, tgt_id2h) -> Optional[str]:
    """First non-empty value from a WS-id-keyed dict whose (mapped) target id is
    registered — the content string for paragraph/segment creation."""
    for src_id, text in (ws_dict or {}).items():
        if not text:
            continue
        tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
        if not tgt_id2h or tgt_id in tgt_id2h:
            return text
    # Fall back to any non-empty text (target inventory unavailable).
    for text in (ws_dict or {}).values():
        if text:
            return text
    return None


def _set_if(ops, method, obj, value):
    if not value:
        return
    fn = getattr(ops, method, None)
    if fn is None:
        return
    _safe(lambda: fn(obj, value))


def _safe(thunk):
    """Run `thunk`, swallowing runtime errors so one field's failure never
    aborts the walk (each real failure that matters is reported by its caller
    via a DroppedItemRecord). Returns the thunk's value or None."""
    try:
        return thunk()
    except Exception as e:  # pragma: no cover - live-host paths
        _log.debug("texts.apply: swallowed %s: %s", type(e).__name__, e)
        return None
