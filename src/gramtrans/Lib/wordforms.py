"""Human-evaluation gate + analysis reproduction (Feature 026, US2/US3/US4).

The feature's differentiating value: reproduce the wordform analyses a **human**
approved or denied, under the never-silent, non-destructive, Preview-before-
mutate contract. Machine/parser-only and un-evaluated analyses are gated out as
ephemeral (FR-006). Closure-scoped to the selected texts (FR-001a).

Covers (per specs/026-texts-wordforms/contracts/):
- analysis-human-eval-walk.md   — human-eval gate, verdict, category resolve-or-report
- morph-bundle-identity-wiring.md — GUID identity wiring + needs-review downgrade
- segment-alignment.md          — Segment.AnalysesRS reproduction (raw-LCM fallback)
- human-agent-provisioning.md   — one provisioned/reused human agent per run

Wires morph-bundle references by source-GUID identity lookup against the per-run
target GUID index (R4) — NOT the 024 possibility resolver (a missing sense is
reported + needs-review, never fabricated).

flexicon accessors (grounded live via FLExTools MCP static surface, 2026-07-12):
`WfiAnalyses` (`GetAll`, `GetHumanEvaluation`, `GetCategory`, `GetMorphBundles`,
`GetGlosses`, `Create`, `ApproveAnalysis`, `RejectAnalysis`, `SetCategory`),
`WfiMorphBundles` (`GetAll`, `GetForm`, `GetSense`, `GetMSA`, `GetMorphType`,
`GetInflType`, `GetInflectionClass`, `Create`, `SetForm`, `SetSense`, `SetMSA`,
`SetMorphType`, `SetInflType`, `SetInflectionClass`), `Wordforms`
(`Find`, `Create`, `GetSpellingStatus`, `SetSpellingStatus`, `ApproveSpelling`),
`Segments.GetAnalyses`, `Agents` (`GetHumanAgents`, `FindByType`, `Create`,
`SetHuman`, `IsHuman`). Imported lazily so this module stays import-safe
without a live LCM host.
"""
from __future__ import annotations

import logging
from typing import List, Optional

if __package__:
    from .models import (
        AlignmentToken,
        AlignmentTokenKind,
        AnalysisPlan,
        DroppedItemRecord,
        EvalVerdict,
        GlossPlan,
        IdentityRef,
        MorphBundlePlan,
        ProvisionedAgent,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecision,
        ReferenceFieldSpec,
    )
    from . import references as _references
    from . import texts as _texts
else:  # pragma: no cover
    from models import (  # type: ignore
        AlignmentToken,
        AlignmentTokenKind,
        AnalysisPlan,
        DroppedItemRecord,
        EvalVerdict,
        GlossPlan,
        IdentityRef,
        MorphBundlePlan,
        ProvisionedAgent,
        ReferenceAction,
        ReferenceCardinality,
        ReferenceDecision,
        ReferenceFieldSpec,
    )
    import references as _references  # type: ignore
    import texts as _texts  # type: ignore

_log = logging.getLogger("gramtrans.Lib.wordforms")

# Shared helpers from Lib/texts.py — one definition of the WS gate / GUID reader.
_guid_str = _texts._guid_str
capture_per_ws = _texts.capture_per_ws
target_ws_ids = _texts.target_ws_ids
gate_ws_id = _texts.gate_ws_id
id_to_handle = _texts.id_to_handle

_AGENT_NAME = "GramTrans"  # provisioned human agent name (FR-009)


# ===========================================================================
# T019 — per-run target GUID index (R4, plan.md Performance Goals)
# ===========================================================================

def build_target_guid_index(ctx, target) -> dict:
    """Return (building + caching once on `ctx._wf_guid_index`) the source-GUID
    → target lexical-object index for morph-bundle wiring.

    Sources, in priority order:
      1. the per-run 024/025 copy-set (`ctx._copy_set`, source_guid → target
         obj) — the objects created earlier this run. Boolean placeholder
         entries (Preview-phase marks) are excluded; only real objects count.
    A miss is resolved lazily against the live target by source GUID (024's
    GUID-preserving create) in `_resolve_ref`. NOT the 024 possibility resolver
    (R4): a missing sense is reported + needs-review, never fabricated.
    """
    idx = getattr(ctx, "_wf_guid_index", None)
    if idx is not None:
        return idx
    idx = {}
    copy_set = getattr(ctx, "_copy_set", None) or {}
    for guid, obj in copy_set.items():
        if obj is True or obj is False or obj is None:
            continue
        idx[str(guid).lower()] = obj
    try:
        object.__setattr__(ctx, "_wf_guid_index", idx)
    except Exception:
        setattr(ctx, "_wf_guid_index", idx)
    return idx


def _target_object_by_guid(target, guid: str):
    """Best-effort live-target lookup by (source-preserved) GUID, or None."""
    if not guid:
        return None
    getter = getattr(target, "Object", None)
    if getter is None:
        return None
    try:
        return getter(guid)
    except Exception:
        return None


def _resolve_ref(ctx, target, field_name: str, referent) -> Optional[IdentityRef]:
    """Build an IdentityRef for a source morph-bundle referent, or None when the
    source did not set that reference (absent ≠ unresolved)."""
    if referent is None:
        return None
    guid = _guid_str(referent)
    idx = build_target_guid_index(ctx, target)
    obj = idx.get(guid) or _target_object_by_guid(target, guid)
    return IdentityRef(
        field_name=field_name, source_guid=guid,
        target_obj=obj, resolved=obj is not None,
    )


# ===========================================================================
# T020 — human-agent provisioning (FR-009, human-agent-provisioning.md)
# ===========================================================================

def plan_agent(target, ctx) -> ProvisionedAgent:
    """Resolve the owning human agent once per run → `models.ProvisionedAgent`.

    Prefer an existing target human agent (reuse → `created=False`, Link in
    Preview); else plan a create (`created=True`, Add). Never raises.
    """
    cached = getattr(ctx, "_wf_agent_decision", None)
    if cached is not None:
        return cached
    agent_ops = getattr(target, "Agents", None)
    existing = None
    if agent_ops is not None:
        for accessor in ("GetHumanAgents",):
            fn = getattr(agent_ops, accessor, None)
            if fn is None:
                continue
            try:
                agents = list(fn() or [])
            except Exception:
                agents = []
            if agents:
                existing = agents[0]
                break
        if existing is None:
            fbt = getattr(agent_ops, "FindByType", None)
            if fbt is not None:
                try:
                    agents = list(fbt(True) or [])
                    if agents:
                        existing = agents[0]
                except Exception:
                    pass
    decision = ProvisionedAgent(
        target_agent=existing, created=existing is None,
    )
    _stash(ctx, "_wf_agent_decision", decision)
    return decision


def apply_agent(decision, target, ctx):
    """Move-mode — realize the ProvisionedAgent and cache it on `ctx._wf_agent`.

    When `created`, `Agents.Create(name)` then `SetHuman(agent, person=None)` to
    mark it human. Cached so every evaluation this run reuses the single agent
    (no per-evaluation duplication, FR-009). Returns the agent (or None)."""
    cached = getattr(ctx, "_wf_agent", None)
    if cached is not None:
        return cached
    agent = decision.target_agent if decision is not None else None
    agent_ops = getattr(target, "Agents", None)
    if agent is None and agent_ops is not None and getattr(decision, "created", False):
        try:
            agent = agent_ops.Create(_AGENT_NAME)
        except Exception:
            agent = None
        if agent is not None:
            try:
                agent_ops.SetHuman(agent, None)
            except Exception:
                pass
    _stash(ctx, "_wf_agent", agent)
    return agent


# ===========================================================================
# T021/T026/T030 — analysis human-evaluation walk
# ===========================================================================

def _pos_spec() -> ReferenceFieldSpec:
    """CategoryRA target list = LangProject.PartsOfSpeechOA (resolve-or-report)."""
    return ReferenceFieldSpec(
        owner_class="WfiAnalysis",
        field_name="CategoryRA",
        cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda target: target.Cache.LangProject.PartsOfSpeechOA,
        hierarchical=True,
    )


def _verdict_from_eval(evaluation) -> Optional[EvalVerdict]:
    """Map a human `ICmAgentEvaluation` to HUMAN_APPROVED / HUMAN_DENIED.

    Reads the evaluation's approve flag (`Approves`, falling back to `Accepted`).
    A truthy int/bool → approved; falsy → denied. Returns None only when no
    evaluation is present (caller gates that out first). [PROBE] confirm the
    exact flag encoding on the live surface (research R1 / T039).
    """
    if evaluation is None:
        return None
    for attr in ("Approves", "Accepted"):
        val = getattr(evaluation, attr, None)
        if val is not None:
            # LCM: 0/False = disapprove, otherwise approve. (Human evals that
            # exist are approve-or-deny; no "no opinion".)
            return EvalVerdict.HUMAN_APPROVED if val else EvalVerdict.HUMAN_DENIED
    # Evaluation present but no readable flag → treat as approve (a human
    # bothered to evaluate); safest non-destructive assumption, still copied.
    return EvalVerdict.HUMAN_APPROVED


class _ApprovalEval:
    """Lightweight human-evaluation stand-in built from a live
    `IWfiAnalysis.ApprovalStatusIcon`, carrying the `Approves` flag that
    `_verdict_from_eval` reads. Only constructed for a genuine human opinion
    (icon 1 = approved / 2 = disapproved); never for parser-only (icon 0)."""
    __slots__ = ("Approves",)

    def __init__(self, approves: bool):
        self.Approves = approves


def _live_human_evaluation(analysis):
    """Human evaluation from the LIVE LCM surface, or None (FR-006 gate).

    2026-07-15 live-proof fix: `WfiAnalyses.GetHumanEvaluation` and the
    `GetHumanEvaluation()` / `human_evaluation` object hooks that the offline
    fakes expose do NOT exist on a live `IWfiAnalysis`. Without a live path the
    gate returned None for every real analysis, so `plan_analyses` skipped them
    all as "parser-only" and 219 human-approved analyses were silently dropped
    (SC-003 violation). The live human/default-agent opinion is read off
    `IWfiAnalysis.ApprovalStatusIcon`: 1 = approved, 2 = disapproved, 0/other =
    no human opinion (parser-only / unevaluated -> excluded, FR-008).

    Reads the icon via a cast to `IWfiAnalysis` (required live -- the base
    `IAnalysis` does not expose it); falls back to a duck-typed
    `ApprovalStatusIcon` attribute when SIL.LCModel is unavailable (offline
    live-shaped fakes). A bare wordform / gloss token that does not cast ->
    None (no analysis-level human opinion)."""
    icon = None
    try:
        from SIL.LCModel import IWfiAnalysis  # noqa: PLC0415
        try:
            icon = IWfiAnalysis(analysis).ApprovalStatusIcon
        except Exception:
            icon = None
    except Exception:
        icon = None
    if icon is None:
        icon = getattr(analysis, "ApprovalStatusIcon", None)
    if icon == 1:
        return _ApprovalEval(True)
    if icon == 2:
        return _ApprovalEval(False)
    return None


def _human_evaluation(source, analysis):
    """Return the analysis's human evaluation object, or None (the FR-006 gate).

    Order: (1) the fake `WfiAnalyses.GetHumanEvaluation` ops hook; (2) a fake
    object exposing `GetHumanEvaluation()` / `human_evaluation`; (3) the LIVE
    LCM surface via `_live_human_evaluation` (`IWfiAnalysis.ApprovalStatusIcon`).
    Paths (1)/(2) keep the offline fakes working; path (3) is the 2026-07-15
    live-proof fix (see `_live_human_evaluation` -- without it every live
    analysis was silently dropped)."""
    wa_ops = getattr(source, "WfiAnalyses", None)
    if wa_ops is not None and hasattr(wa_ops, "GetHumanEvaluation"):
        try:
            return wa_ops.GetHumanEvaluation(analysis)
        except Exception:
            return None
    # Fake object fallbacks (offline duck-typed analyses).
    fn = getattr(analysis, "GetHumanEvaluation", None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            return None
    fake_attr = getattr(analysis, "human_evaluation", None)
    if fake_attr is not None:
        return fake_attr
    # Live LCM surface (real IWfiAnalysis has none of the above).
    return _live_human_evaluation(analysis)


def _iter_segment_wordforms(source, segment):
    """Yield the (wordform, [analyses]) pairs occurring in a segment.

    Uses `Segments.GetAnalyses` (tokens) and groups by owning wordform via
    `WfiAnalyses.GetOwningWordform`. Tolerant of a fake segment exposing
    `wordforms` (list of objects each with `.analyses`)."""
    seg_ops = getattr(source, "Segments", None)
    wa_ops = getattr(source, "WfiAnalyses", None)
    # Fake fast-path.
    fake_wfs = getattr(segment, "wordforms", None)
    if fake_wfs is not None:
        for wf in fake_wfs:
            yield wf, list(getattr(wf, "analyses", None) or [])
        return
    if seg_ops is None:
        return
    try:
        tokens = list(seg_ops.GetAnalyses(segment) or [])
    except Exception:
        tokens = []
    seen = {}
    order = []
    for tok in tokens:
        wf = None
        if wa_ops is not None:
            try:
                wf = wa_ops.GetOwningWordform(tok)
            except Exception:
                wf = None
        if wf is None:
            wf = tok  # token itself is a bare wordform
        key = _guid_str(wf)
        if key not in seen:
            seen[key] = []
            order.append((key, wf))
        # Collect the token if it is an analysis (has a human-eval surface).
        seen[key].append(tok)
    for key, wf in order:
        yield wf, seen[key]


def plan_analyses(segment, source, target, ctx, resolver_cache, dropped) -> List:
    """Per-segment pure/decision pass → list of `models.AnalysisPlan`.

    Keeps only analyses with a non-null human evaluation (FR-006); sets the
    verdict from the eval's approve flag (FR-007); resolves CategoryRA via
    `resolve_or_report_category` (FR-011); builds morph bundles (delegated) and
    computes `needs_review` (an approve that lost ≥1 morpheme referent, FR-014;
    a deny is never downgraded, FR-015); captures the WS-gated wordform form +
    spelling status (FR-013). No writes. Glosses (US4, T030) are captured empty
    here.
    """
    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_ws_ids = target_ws_ids(target)
    wf_ops = getattr(source, "Wordforms", None)
    plans: List[AnalysisPlan] = []

    for wordform, analyses in _iter_segment_wordforms(source, segment):
        wf_form = {}
        if wf_ops is not None and hasattr(wf_ops, "GetForm"):
            wf_form = capture_per_ws(
                lambda o, h: wf_ops.GetForm(o, h), wordform, source, ws_map, tgt_ws_ids,
                owner_kind="WfiWordform", owner_guid=_guid_str(wordform),
                owner_label="", field_name="Form", dropped=dropped,
            )
        spelling = None
        if wf_ops is not None and hasattr(wf_ops, "GetSpellingStatus"):
            spelling = _texts._safe(lambda: wf_ops.GetSpellingStatus(wordform))

        for analysis in analyses:
            evaluation = _human_evaluation(source, analysis)
            if evaluation is None:
                # FR-006: parser-only / un-evaluated — excluded (countable via
                # SC-001; nothing planned, no write).
                _log.debug("plan_analyses: skip non-human-evaluated analysis %s",
                           _guid_str(analysis))
                continue
            verdict = _verdict_from_eval(evaluation)
            wf_label = _first_text(wf_form)
            category_decision = resolve_or_report_category(
                analysis, target, resolver_cache, dropped)
            morph_bundles = tuple(plan_morph_bundles(
                analysis, target, ctx, dropped, context_label=wf_label))
            glosses = tuple(plan_glosses(analysis, source, target, ctx, dropped))

            # needs_review (FR-014): an APPROVE that lost ≥1 morpheme referent.
            # A DENY is never downgraded (FR-015).
            has_unresolved = any(mb.unresolved_refs() for mb in morph_bundles)
            needs_review = (verdict == EvalVerdict.HUMAN_APPROVED and has_unresolved)
            if needs_review:
                # FR-016: the downgrade itself is a reported gap — the approve is
                # written no-verdict (T027), so the report is the only signal the
                # linguist has to find and re-approve it once the morpheme lands.
                dropped.append(DroppedItemRecord(
                    owner_kind="WfiAnalysis",
                    owner_guid=_guid_str(analysis) or "?",
                    owner_label=wf_label,
                    field_name="verdict",
                    item_name="needs-review",
                    item_guid=_guid_str(analysis),
                    reason="approve downgraded to needs-review: "
                           "unresolved morph-bundle reference(s)",
                ))

            plans.append(AnalysisPlan(
                source_guid=_guid_str(analysis),
                wordform_form=wf_form,
                spelling_status=spelling,
                verdict=verdict,
                category_decision=category_decision,
                morph_bundles=morph_bundles,
                glosses=glosses,
                needs_review=needs_review,
            ))
    return plans


def resolve_or_report_category(analysis, target, resolver_cache, dropped):
    """CategoryRA resolve-or-report variant → `models.ReferenceDecision` (FR-011).

    Calls `references.decide_reference` against `LangProject.PartsOfSpeechOA`,
    then downgrades any CREATE to REPORT_DROPPED: an absent POS is left unset and
    a DroppedItemRecord is emitted. A POS is NEVER fabricated for an analysis.
    Returns None when the analysis has no category (nothing to write)."""
    category = getattr(analysis, "CategoryRA", None)
    if category is None:
        category = getattr(analysis, "category", None)
    if category is None:
        return None
    spec = _pos_spec()
    try:
        decision = _references.decide_reference(category, target, spec, resolver_cache)
    except Exception:
        decision = None
    if decision is None:
        return None
    if decision.action == ReferenceAction.CREATE:
        drop = DroppedItemRecord(
            owner_kind="WfiAnalysis",
            owner_guid=_guid_str(analysis) or "?",
            owner_label="",
            field_name="CategoryRA",
            item_name=_references._item_label(category),
            item_guid=_guid_str(category),
            reason="category not in target part-of-speech list",
        )
        dropped.append(drop)
        return ReferenceDecision(
            action=ReferenceAction.REPORT_DROPPED,
            source_item=category,
            dropped=drop,
        )
    if decision.dropped is not None:
        dropped.append(decision.dropped)
    return decision


# ===========================================================================
# T030 — word-level gloss human-evaluation gate (FR-008, US4)
# ===========================================================================

def _gloss_human_evaluation(source, gloss):
    """Return a WfiGloss's human evaluation, or None (the FR-008 gate).

    Prefers `WfiGlosses.GetHumanEvaluation`; tolerant of a duck-typed fake that
    exposes `GetHumanEvaluation` / `human_evaluation` on the gloss itself."""
    gl_ops = getattr(source, "WfiGlosses", None)
    if gl_ops is not None and hasattr(gl_ops, "GetHumanEvaluation"):
        try:
            return gl_ops.GetHumanEvaluation(gloss)
        except Exception:
            return None
    fn = getattr(gloss, "GetHumanEvaluation", None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            return None
    return getattr(gloss, "human_evaluation", None)


def plan_glosses(analysis, source, target, ctx, dropped) -> List:
    """Pure/decision pass → list of human-evaluated `models.GlossPlan` (FR-008).

    Applies the SAME human-evaluation gate as analyses: a `WfiGloss` is kept iff
    it carries a non-null human evaluation. Parser-only / un-evaluated glosses
    are excluded (no plan, no write). Gloss forms are WS-gated (FR-020). No
    writes.
    """
    gl_ops = getattr(source, "WfiGlosses", None)
    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_ws_ids = target_ws_ids(target)

    glosses = []
    if gl_ops is not None and hasattr(gl_ops, "GetAll"):
        glosses = _texts._safe(lambda: list(gl_ops.GetAll(analysis) or [])) or []
    if not glosses:
        glosses = list(getattr(analysis, "glosses", None)
                       or getattr(analysis, "MeaningsOC", None) or [])

    plans: List[GlossPlan] = []
    for gloss in glosses:
        evaluation = _gloss_human_evaluation(source, gloss)
        if evaluation is None:
            # FR-008: parser-only / un-evaluated gloss — excluded, no write.
            _log.debug("plan_glosses: skip non-human-evaluated gloss %s",
                       _guid_str(gloss))
            continue
        forms = {}
        if gl_ops is not None and hasattr(gl_ops, "GetForm"):
            forms = capture_per_ws(
                lambda o, h: gl_ops.GetForm(o, h), gloss, source, ws_map, tgt_ws_ids,
                owner_kind="WfiGloss", owner_guid=_guid_str(gloss),
                owner_label="", field_name="Form", dropped=dropped,
            )
        plans.append(GlossPlan(
            source_guid=_guid_str(gloss),
            forms=forms,
            verdict=_verdict_from_eval(evaluation),
        ))
    return plans


def _apply_glosses(plan, target, analysis_obj, ctx, dropped) -> None:
    """Move-mode — reproduce the human-evaluated glosses (FR-008) on the target
    analysis: create each gloss and write its WS-gated forms."""
    if not plan.glosses:
        return None
    gl_ops = getattr(target, "WfiGlosses", None)
    if gl_ops is None:
        return None
    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_id2h = id_to_handle(target)
    for gplan in plan.glosses:
        gloss = _texts._safe(lambda: gl_ops.Create(analysis_obj))
        if gloss is None:
            dropped.append(DroppedItemRecord(
                owner_kind="WfiGloss", owner_guid=gplan.source_guid or "?",
                owner_label="", field_name="Create", item_name="",
                item_guid="", reason="gloss create failed",
            ))
            continue
        for src_id, text in (gplan.forms or {}).items():
            tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
            h = tgt_id2h.get(tgt_id)
            if text and (h is not None or not tgt_id2h):
                _texts._safe(lambda t=text, hh=h: gl_ops.SetForm(gloss, t, hh))
    return None


def apply_analyses(plans, source, target, ctx, tag, resolver_cache, dropped) -> None:
    """Move-mode — realize the AnalysisPlans on the target's wordforms.

    Find-or-create the target wordform by form+WS (R7); set spelling status
    (FR-013, non-destructive); `WfiAnalyses.Create`; apply the category decision;
    wire morph bundles + copy human-evaluated glosses (delegated); write the verdict —
      HUMAN_APPROVED and not needs_review → ApproveAnalysis (owned by the run's
        provisioned agent);
      HUMAN_DENIED → RejectAnalysis (incl. the deny-with-unresolvable case);
      NEEDS_REVIEW → write NO human evaluation (natural no-verdict state, R2).
    Records the source→target analysis/wordform map on ctx for alignment (R7).
    Residue-tags the wordform/analysis (Carrier B, R8).
    """
    if not plans:
        return None
    if __package__:
        from .residue import apply_residue
    else:  # pragma: no cover
        from residue import apply_residue  # type: ignore

    wf_ops = getattr(target, "Wordforms", None)
    wa_ops = getattr(target, "WfiAnalyses", None)
    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_id2h = id_to_handle(target)
    default_analysis_handle = _default_analysis_handle(target)
    agent = getattr(ctx, "_wf_agent", None)

    analysis_map = _map_on_ctx(ctx, "_wf_analysis_map")
    wordform_map = _map_on_ctx(ctx, "_wf_wordform_map")

    for plan in plans:
        wordform = _find_or_create_wordform(plan, wf_ops, ws_map, tgt_id2h, dropped)
        if wordform is None:
            continue
        wordform_map[plan.source_guid] = wordform  # keyed by SOURCE analysis guid's wordform
        # Spelling status (FR-013), non-destructive.
        _apply_spelling(plan, wf_ops, wordform)

        if wa_ops is None:
            continue
        analysis_obj = _texts._safe(lambda: wa_ops.Create(wordform))
        if analysis_obj is None:
            dropped.append(DroppedItemRecord(
                owner_kind="WfiAnalysis", owner_guid=plan.source_guid or "?",
                owner_label="", field_name="Create", item_name="",
                item_guid="", reason="analysis create failed",
            ))
            continue
        analysis_map[plan.source_guid] = analysis_obj

        # Category (resolve-or-report). Only wire on a resolved (LINK/CREATE/
        # UPDATE→has target_item) decision; REPORT_DROPPED leaves it unset.
        _apply_category(plan, target, analysis_obj, wa_ops, resolver_cache, tag, ws_map, dropped)

        # Morph bundles (identity wiring).
        apply_morph_bundles(analysis_obj, plan.morph_bundles, target, ctx, dropped)

        # Word-level glosses (human-evaluated only, US4/FR-008).
        _apply_glosses(plan, target, analysis_obj, ctx, dropped)

        # Verdict write (the crux).
        _write_verdict(plan, wa_ops, analysis_obj, agent)

        _texts._safe(lambda: apply_residue(
            wordform, default_analysis_handle, tag, class_name="WfiWordform"))
        _texts._safe(lambda: apply_residue(
            analysis_obj, default_analysis_handle, tag, class_name="WfiAnalysis"))
    return None


def _write_verdict(plan, wa_ops, analysis_obj, agent):
    """Apply the human verdict, honoring the needs-review no-verdict path (R2)."""
    if plan.verdict == EvalVerdict.HUMAN_APPROVED and not plan.needs_review:
        _texts._safe(lambda: wa_ops.ApproveAnalysis(analysis_obj))
    elif plan.verdict == EvalVerdict.HUMAN_DENIED:
        _texts._safe(lambda: wa_ops.RejectAnalysis(analysis_obj))
    else:
        # NEEDS_REVIEW: create + write NO human evaluation (natural no-verdict
        # state). No ApproveAnalysis/RejectAnalysis, no in-FLEx marker, no
        # proxy-deny — the report entries convey needs-review (R2/FR-014).
        _log.debug("apply_analyses: analysis %s left needs-review (no verdict)",
                   plan.source_guid)


def _apply_category(plan, target, analysis_obj, wa_ops, resolver_cache, tag, ws_map, dropped):
    decision = plan.category_decision
    if decision is None or decision.action == ReferenceAction.REPORT_DROPPED:
        return  # already reported; leave category unset (FR-011)
    target_item = getattr(decision, "target_item", None)
    if target_item is None and decision.action == ReferenceAction.CREATE:
        # Should not happen (resolve_or_report suppresses CREATE); defensive.
        return
    if target_item is not None:
        _texts._safe(lambda: wa_ops.SetCategory(analysis_obj, target_item))


def _apply_spelling(plan, wf_ops, wordform):
    if plan.spelling_status is None or wf_ops is None:
        return
    setter = getattr(wf_ops, "SetSpellingStatus", None)
    if setter is not None:
        _texts._safe(lambda: setter(wordform, plan.spelling_status))


def _find_or_create_wordform(plan, wf_ops, ws_map, tgt_id2h, dropped):
    """Find-or-create the target wordform by form+WS (global identity, R7)."""
    if wf_ops is None:
        return None
    form, handle = _first_form_and_handle(plan.wordform_form, ws_map, tgt_id2h)
    if not form:
        dropped.append(DroppedItemRecord(
            owner_kind="WfiWordform", owner_guid=plan.source_guid or "?",
            owner_label="", field_name="Form", item_name="",
            item_guid="", reason="wordform form has no mappable writing system",
        ))
        return None
    found = _texts._safe(lambda: wf_ops.Find(form, handle))
    if found is not None:
        return found
    return _texts._safe(lambda: wf_ops.Create(form, handle))


def _first_form_and_handle(ws_dict, ws_map, tgt_id2h):
    for src_id, text in (ws_dict or {}).items():
        if not text:
            continue
        tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
        handle = tgt_id2h.get(tgt_id)
        if handle is not None or not tgt_id2h:
            return text, handle
    return None, None


def _default_analysis_handle(project):
    try:
        return project.GetDefaultAnalysisWSHandle()
    except Exception:
        return None


# ===========================================================================
# T023/T028 — morph-bundle identity wiring
# ===========================================================================

_BUNDLE_REF_GETTERS = (
    # (IdentityRef field_name, ops getter method name)
    ("MorphRA", "GetMorph"),
    ("MsaRA", "GetMSA"),
    ("SenseRA", "GetSense"),
    ("InflTypeRA", "GetInflType"),
)


def _bundle_referent(source_ops, bundle, field_name, getter_name):
    """Read a bundle's referent object (ops getter, else raw RA attribute)."""
    if source_ops is not None:
        fn = getattr(source_ops, getter_name, None)
        if fn is not None:
            val = _texts._safe(lambda: fn(bundle))
            if val is not None:
                return val
    return getattr(bundle, field_name, None)


def plan_morph_bundles(analysis, target, ctx, dropped, context_label="") -> List:
    """Pure/decision pass → list of `models.MorphBundlePlan`.

    For each bundle capture the WS-gated form and build up to four IdentityRefs
    (MorphRA / MsaRA / SenseRA / InflTypeRA) via the per-run target GUID index
    (R4). Every UNRESOLVED ref emits one DroppedItemRecord (owner_kind
    WfiMorphBundle, field = ref name, reason "referent not copied to target")
    with locate-and-finish context (FR-016): `context_label` carries the owning
    wordform form and `item_name` the morpheme form."""
    source = getattr(ctx, "source_handle", None)
    mb_ops = getattr(source, "WfiMorphBundles", None) if source is not None else None
    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_ws_ids = target_ws_ids(target)

    bundles = []
    if mb_ops is not None and hasattr(mb_ops, "GetAll"):
        bundles = _texts._safe(lambda: list(mb_ops.GetAll(analysis) or [])) or []
    if not bundles:
        bundles = list(getattr(analysis, "morph_bundles", None)
                       or getattr(analysis, "MorphBundlesOS", None) or [])

    plans: List[MorphBundlePlan] = []
    for bundle in bundles:
        bundle_guid = _guid_str(bundle)
        form = {}
        if mb_ops is not None and hasattr(mb_ops, "GetForm"):
            form = capture_per_ws(
                lambda o, h: mb_ops.GetForm(o, h), bundle, source, ws_map, tgt_ws_ids,
                owner_kind="WfiMorphBundle", owner_guid=bundle_guid,
                owner_label="", field_name="Form", dropped=dropped,
            )
        refs = {}
        for field_name, getter_name in _BUNDLE_REF_GETTERS:
            referent = _bundle_referent(mb_ops, bundle, field_name, getter_name)
            ref = _resolve_ref(ctx, target, field_name, referent)
            refs[field_name] = ref
            if ref is not None and not ref.resolved:
                # FR-016: unresolved referent — unlinked + reported, with the
                # wordform (owner_label) + morpheme form (item_name) so the gap
                # can be located and finished manually.
                dropped.append(DroppedItemRecord(
                    owner_kind="WfiMorphBundle", owner_guid=bundle_guid or "?",
                    owner_label=context_label, field_name=field_name,
                    item_name=_first_text(form), item_guid=ref.source_guid,
                    reason="referent not copied to target",
                ))
        plans.append(MorphBundlePlan(
            source_guid=bundle_guid,
            form=form,
            morph_ref=refs.get("MorphRA"),
            msa_ref=refs.get("MsaRA"),
            sense_ref=refs.get("SenseRA"),
            infl_type_ref=refs.get("InflTypeRA"),
        ))
    return plans


def apply_morph_bundles(analysis_obj, plans, target, ctx, dropped) -> None:
    """Move-mode — create bundles in source order, always SetForm, wire each
    resolved IdentityRef; leave unresolved refs unset (already reported)."""
    if not plans:
        return None
    mb_ops = getattr(target, "WfiMorphBundles", None)
    if mb_ops is None:
        return None
    ws_map = dict(getattr(ctx, "_ws_map", None) or {})
    tgt_id2h = id_to_handle(target)

    for plan in plans:
        bundle = _texts._safe(lambda: mb_ops.Create(analysis_obj))
        if bundle is None:
            dropped.append(DroppedItemRecord(
                owner_kind="WfiMorphBundle", owner_guid=plan.source_guid or "?",
                owner_label="", field_name="Create", item_name="",
                item_guid="", reason="morph-bundle create failed",
            ))
            continue
        # Always write the form (legible bundle even when refs are unlinked).
        for src_id, text in (plan.form or {}).items():
            tgt_id = ws_map.get(src_id, src_id) if ws_map else src_id
            h = tgt_id2h.get(tgt_id)
            if text and (h is not None or not tgt_id2h):
                _texts._safe(lambda t=text, hh=h: mb_ops.SetForm(bundle, t, hh))
        # Wire each RESOLVED reference; unresolved stay unset (reported at plan).
        _wire_ref(mb_ops, "SetSense", bundle, plan.sense_ref)
        _wire_ref(mb_ops, "SetMSA", bundle, plan.msa_ref)
        _wire_ref(mb_ops, "SetMorphType", bundle, plan.morph_ref)
        _wire_ref(mb_ops, "SetInflType", bundle, plan.infl_type_ref)
    return None


def _wire_ref(mb_ops, setter_name, bundle, ref):
    if ref is None or not ref.resolved or ref.target_obj is None:
        return
    fn = getattr(mb_ops, setter_name, None)
    if fn is not None:
        _texts._safe(lambda: fn(bundle, ref.target_obj))


# ===========================================================================
# T024 — segment alignment (AnalysesRS reproduction, FR-012, SC-006)
# ===========================================================================

def _classify_token(source, token):
    """Classify one AnalysesRS token → AlignmentTokenKind."""
    class_name = getattr(token, "ClassName", None)
    if class_name is None:
        try:
            from SIL.LCModel import ICmObject  # lazy
            class_name = ICmObject(token).ClassName
        except Exception:
            class_name = getattr(token, "kind", "") or ""
    cn = str(class_name)
    if "Analysis" in cn:
        return AlignmentTokenKind.ANALYSIS
    if "Gloss" in cn:
        return AlignmentTokenKind.ANALYSIS  # a gloss stands in for its analysis
    if "Wordform" in cn:
        return AlignmentTokenKind.WORDFORM
    if cn in ("analysis", "wordform", "punctuation"):
        return {
            "analysis": AlignmentTokenKind.ANALYSIS,
            "wordform": AlignmentTokenKind.WORDFORM,
            "punctuation": AlignmentTokenKind.PUNCTUATION,
        }[cn]
    return AlignmentTokenKind.PUNCTUATION


def plan_alignment(segment, ctx, dropped) -> List:
    """Pure/decision pass → ordered list of `models.AlignmentToken`.

    Reads the source token sequence (`Segments.GetAnalyses`), classifies each
    token, and records its source GUID so order + count mirror the source
    (FR-012). The target referent is resolved at apply time from the source→
    target maps built by `apply_analyses` (R7)."""
    source = getattr(ctx, "source_handle", None)
    seg_ops = getattr(source, "Segments", None) if source is not None else None
    tokens = []
    if seg_ops is not None and hasattr(seg_ops, "GetAnalyses"):
        tokens = _texts._safe(lambda: list(seg_ops.GetAnalyses(segment) or [])) or []
    if not tokens:
        tokens = list(getattr(segment, "analyses_rs", None) or [])
    out: List[AlignmentToken] = []
    for tok in tokens:
        out.append(AlignmentToken(
            kind=_classify_token(source, tok),
            source_guid=_guid_str(tok),
            target_ref=None,
        ))
    return out


def apply_alignment(target_segment, tokens, ctx, dropped) -> None:
    """Move-mode — rebuild the target `AnalysesRS` in source order.

    Resolves each token's target referent from the ctx source→target maps and
    appends it to the target segment's `AnalysesRS`. Where the flexicon wrapper
    exposes no setter, reaches the raw sequence via `Cache`/cast (R5). Preserves
    punctuation / bare-wordform slots. Non-destructive: only rebuilds when the
    target sequence is currently empty (re-run keeps the existing alignment).

    [PROBE] exact `AnalysesRS` write path pending live-runtime confirmation
    (research R5 / T039)."""
    if not tokens:
        return None
    analysis_map = _map_on_ctx(ctx, "_wf_analysis_map")
    wordform_map = _map_on_ctx(ctx, "_wf_wordform_map")

    seq = _analyses_rs(target_segment)
    if seq is None:
        return None
    # Non-destructive: skip when already populated (re-run).
    if _seq_len(seq) > 0:
        return None

    for tok in tokens:
        ref = None
        if tok.kind == AlignmentTokenKind.ANALYSIS:
            ref = analysis_map.get(tok.source_guid)
        elif tok.kind == AlignmentTokenKind.WORDFORM:
            ref = wordform_map.get(tok.source_guid)
        # PUNCTUATION (and unresolved) tokens are preserved positionally when
        # the raw surface exposes them; without a target referent we cannot
        # fabricate a punctuation form here, so an unresolved slot is reported
        # rather than silently dropped (SC-006 positional fidelity).
        if ref is None:
            if tok.kind != AlignmentTokenKind.PUNCTUATION:
                dropped.append(DroppedItemRecord(
                    owner_kind="Segment", owner_guid=_guid_str(target_segment) or "?",
                    owner_label="", field_name="AnalysesRS",
                    item_name="", item_guid=tok.source_guid,
                    reason="alignment token had no copied target referent",
                ))
            continue
        _texts._safe(lambda r=ref: seq.Add(r))
    return None


def _analyses_rs(target_segment):
    """Best-effort handle to the target segment's `AnalysesRS` sequence (R5).

    Prefers a direct `AnalysesRS` attribute (fakes + concrete ICmObject);
    otherwise casts through the LCM `ISegment` interface. None on failure."""
    seq = getattr(target_segment, "AnalysesRS", None)
    if seq is not None:
        return seq
    try:
        from SIL.LCModel import ISegment  # lazy
        return ISegment(target_segment).AnalysesRS
    except Exception:
        return None


def _seq_len(seq) -> int:
    for attr in ("Count",):
        val = getattr(seq, attr, None)
        if isinstance(val, int):
            return val
    try:
        return len(seq)
    except Exception:
        return 0


# ===========================================================================
# ctx helpers
# ===========================================================================

def _first_text(ws_dict) -> str:
    """First non-empty string in a WS-keyed dict (a locate label for reports)."""
    for value in (ws_dict or {}).values():
        if value:
            return value
    return ""


def _stash(ctx, name, value):
    try:
        object.__setattr__(ctx, name, value)
    except Exception:
        setattr(ctx, name, value)


def _map_on_ctx(ctx, name) -> dict:
    m = getattr(ctx, name, None)
    if m is None:
        m = {}
        _stash(ctx, name, m)
    return m
