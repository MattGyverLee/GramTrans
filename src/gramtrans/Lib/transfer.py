"""Move-mode plan executor (constitution v5.0.0 Principle III).

`execute(plan, source, target, report)` consumes a RunPlan produced by
`Lib/preview.py.build_run_plan` and applies its actions to the target.
The FlexTools runner already wraps `MainFunction` in an UndoableUnitOfWork
(research.md R10), so this module does NOT open its own UOW — the
`Ctrl+Z`-undoes-everything property comes from the outer runner unit.

The verb-vertical per-layer creators (POS, Template, Slot) preserve source
GUIDs via the LCM factories' `Create(Guid, owner)` overloads, then apply the
source's syncable properties via flexicon's `ApplySyncableProperties`
(see CLAUDE.md). Residue tagging routes through `Lib/residue.py.apply_residue`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional

_log = logging.getLogger(__name__)

if __package__:
    from .models import (
        ActionOutcome,
        OUTCOME_FAILED,
        OUTCOME_SKIPPED,
        DroppedItemRecord,
        GrammarCategory,
        LeafExecutionFailure,
        MatchBasis,
        MatchBasisRecord,
        MergeDecision,
        MergeDecisionLog,
        MergeResolution,
        PlannedAction,
        RunMode,
        RunPlan,
        RunReport,
        Skip,
        SkipReason,
    )
    from .residue import (
        ImportResidueTag, apply_residue, apply_carrier_b,
        strip_residue_props, residue_lines, restore_residue_history,
    )
    from .conflict import (
        _deterministic_merge,
        _MergeNotEligible,
        apply_update_semantic,
        compute_disposition,
        ItemDisposition,
        _phoneme_env_field_diff_enabled,
    )
    from .ws_mapping import to_ws_map_dict
    from . import report as _report_module  # registers RunReport.build_from_plan
else:
    from models import (
        ActionOutcome,
        OUTCOME_FAILED,
        OUTCOME_SKIPPED,
        DroppedItemRecord,
        GrammarCategory,
        LeafExecutionFailure,
        MatchBasis,
        MatchBasisRecord,
        MergeDecision,
        MergeDecisionLog,
        MergeResolution,
        PlannedAction,
        RunMode,
        RunPlan,
        RunReport,
        Skip,
        SkipReason,
    )
    from residue import (  # type: ignore
        ImportResidueTag, apply_residue, apply_carrier_b,
        strip_residue_props, residue_lines, restore_residue_history,
    )
    from conflict import (  # type: ignore
        _deterministic_merge,
        _MergeNotEligible,
        apply_update_semantic,
        compute_disposition,
        ItemDisposition,
        _phoneme_env_field_diff_enabled,
    )
    from ws_mapping import to_ws_map_dict  # type: ignore
    import report as _report_module  # registers RunReport.build_from_plan


# ============================================================================
# Feature 024 US2 (OVERWRITE-path reference-field routing, FIX 1)
# ============================================================================
#
# `_execute_overwrite`'s SENSE and ENTRY (+ AFFIXES/STEMS, same code path)
# branches call the raw flexicon `ApplySyncableProperties` with
# `fill_gaps=False`. For these specific fields, that raw call's semantics are
# BLANK-ON-EMPTY / CLEAR-AND-REBUILD (see
# tests/unit/test_overwrite_blanking.py's module docstring for the exact
# flexicon source lines) -- an empty/unset source value blanks or clears an
# already-populated target, violating FR-007's non-destructive invariant.
# A NON-empty source value has its own defect if left in place: it would
# reach BOTH the raw call AND the resolver pass below, resolving the same
# GUID to the same target object twice (double-application -- see
# `_strip_ref_fields`'s docstring).
#
# These keys are therefore stripped from `src_props` UNCONDITIONALLY
# (empty or not) BEFORE the raw `ApplySyncableProperties` call and routed
# SOLELY through `categories._apply_reference_fields` instead -- the SAME
# generic resolver (LINK/CREATE+ancestors/UPDATE/REPORT_DROPPED) the
# ADD/closure path already uses (`categories._walk_lex_entry_closure`).
# Every OTHER reference field registered in `references.REFERENCE_FIELD_MAP`
# for these owner classes (UsageTypesRC, DomainTypesRC, StatusRA, ...) is OUT
# OF SCOPE for this fix and is left on the raw-copy path unchanged --
# `_overwrite_ref_skip_fields` below excludes them from the resolver pass via
# `skip_fields=`.
_OVERWRITE_SENSE_REF_FIELDS = frozenset(
    {"SenseTypeRA", "DoNotPublishInRC", "DoNotShowMainEntryInRC"}
)
_OVERWRITE_ENTRY_REF_FIELDS = frozenset(
    {"DoNotPublishInRC", "DoNotShowMainEntryInRC"}
)


def _overwrite_ref_skip_fields(owner_class: str, keep_fields: frozenset) -> frozenset:
    """Every `references.field_specs_for(owner_class)` field name NOT in
    `keep_fields` -- passed as `_apply_reference_fields`'s `skip_fields=` so
    the OVERWRITE-path resolver pass only touches the fields this fix is
    scoped to (`_OVERWRITE_SENSE_REF_FIELDS` / `_OVERWRITE_ENTRY_REF_FIELDS`),
    leaving every other registered reference field's OVERWRITE behavior
    unchanged (out of scope for this fix)."""
    if __package__:
        from . import references as _references
    else:
        import references as _references  # type: ignore
    return frozenset(
        spec.field_name for spec in _references.field_specs_for(owner_class)
    ) - keep_fields


def _strip_ref_fields(src_props: dict, fields) -> None:
    """Remove each of `fields` from `src_props` in place, UNCONDITIONALLY --
    regardless of whether its current value is truthy or falsy.

    Feature 024 US2 FIX 1 (root-cause option (a)): the prior version
    (`_strip_empty_ref_fields`) only stripped a field when its value was
    FALSY, on the theory that a truthy (non-empty) value should still reach
    the raw `ApplySyncableProperties` call for "baseline" handling. That
    left a real double-application defect: a TRUTHY collection value
    (`DoNotPublishInRC`/`DoNotShowMainEntryInRC`) reached BOTH the raw call
    (which `Clear()`s the target collection and re-`Add()`s each resolved
    source member -- flexicon's `fill_gaps=False` semantics) AND the
    generic resolver pass immediately after
    (`categories._apply_reference_fields`, object-attribute-driven,
    `owner_coll.Add(resolved)`) -- both resolving the SAME source GUID to
    the SAME target object, so the target collection ended up holding it
    TWICE.

    Stripping unconditionally makes the resolver pass the SOLE handler for
    these fields, full stop -- the raw call never touches them, empty or
    not, so the Clear()+Add()-then-Add() double-application is removed by
    construction. The non-destructive invariant (FR-007: an empty source
    never blanks a populated target) still holds: `decide_reference`
    returns `None` for an unset/empty source item, which is a documented
    no-op for the resolver -- it never clears anything itself."""
    for field_name in fields:
        src_props.pop(field_name, None)


# ============================================================================
# Public API
# ============================================================================


def _ensure_171_subpass(exec_ctx, target, tag, exec_skips):
    """Run the 17.1 sub-pass if the AFFIX_TEMPLATES tail did not (FR-333).

    `categories._run_171_subpass` wires `MoInflAffMsa.SlotsRC` (the affix's
    template column) and `MSA.InflFeatsOA`. It is normally driven by
    `_run_tail_once` on the LAST executed AFFIX_TEMPLATES action -- which
    quietly makes it conditional on the USER'S SELECTION. A run that transfers
    affixes without also selecting affix templates has zero AFFIX_TEMPLATES
    actions, so the tail never fires: every transferred affix MSA keeps an
    empty SlotsRC and no inflection features, and nothing in the report says
    so.

    Called after the leaf-dispatch loop, where every category (slots included)
    has finished, so all wiring endpoints exist. The `_did_171_subpass` flag
    the tail sets makes this a no-op when the tail already ran, so the two
    paths never double-execute.

    Never raises: a failure here must not lose the writes the run already made.
    """
    if getattr(exec_ctx, "_did_171_subpass", False):
        return
    if __package__:
        from .categories import _run_171_subpass
    else:
        from categories import _run_171_subpass  # type: ignore
    try:
        object.__setattr__(exec_ctx, "_did_171_subpass", True)
    except (AttributeError, TypeError):
        pass
    try:
        late_skips = _run_171_subpass(exec_ctx, target, tag)
    except Exception:
        _log.exception("execute: 17.1 sub-pass safety net FAILED (swallowed)")
        return
    if late_skips and exec_skips is not None:
        try:
            exec_skips.extend(late_skips)
        except (AttributeError, TypeError):
            pass


#: Issue #54: syncable keys `_execute_update_semantic` must not hand to the
#: per-field `ApplySyncableProperties` write. `PhonemeGuids` is a list of
#: SOURCE phoneme GUIDs; flexicon's base loop writes only multistring dicts
#: and plain strings, so the "write" was a silent no-op that still counted as
#: one field written on every run (measured live: `Vowels` reported
#: "UPDATE applied (1 field(s) written)" on run 2 and never changed). Even a
#: working write would be wrong here: a source GUID does not name a starter
#: phoneme matched by natural key. Membership is wired by
#: `_ensure_matched_nc_segments`, which resolves each member properly.
_UPDATE_UNWRITABLE_KEYS: dict = {
    GrammarCategory.NATURAL_CLASSES: ("PhonemeGuids",),
}


def _ensure_matched_nc_segments(exec_ctx, target, exec_skips):
    """Issue #54: run `categories._wire_matched_nc_segments` once, AFTER the
    leaf-dispatch loop.

    The natural-key UPDATE of a starter `PhNCSegments` runs in the overwrite
    loop, BEFORE this run's phonemes are created, so it cannot reference
    them; and its only membership carrier (`PhonemeGuids`) is not written by
    the base `ApplySyncableProperties`. Placed here, every phoneme this run
    creates already exists. Own latch; never raises.
    """
    if getattr(exec_ctx, "_did_matched_nc_segments", False):
        return
    plan = getattr(exec_ctx, "_run_plan", None)
    if plan is None:
        return
    if __package__:
        from .categories import _wire_matched_nc_segments
    else:
        from categories import _wire_matched_nc_segments  # type: ignore
    try:
        object.__setattr__(exec_ctx, "_did_matched_nc_segments", True)
    except (AttributeError, TypeError):
        pass
    try:
        late_skips = _wire_matched_nc_segments(exec_ctx, target, plan)
    except Exception:
        _log.exception(
            "execute: key-matched natural-class member pass FAILED (swallowed)")
        return
    if late_skips and exec_skips is not None:
        try:
            exec_skips.extend(late_skips)
        except (AttributeError, TypeError):
            pass


def _ensure_owner_feat_strucs(exec_ctx, target, tag, exec_skips):
    """Run T119's feature-structure owner pass AFTER every category (038,
    2026-08-28).

    WHY IT IS HERE AND NOT IN THE 17.1 SUB-PASS, WHERE IT SHIPPED.
    `categories._wire_owner_feat_strucs` fills `MsFeaturesOA`,
    `From/ToMsFeaturesOA` and `MsEnvFeaturesOA` on owners that already exist --
    it is an enrichment post-pass, not a create path. It was called from
    `_run_171_subpass`, which `_run_tail_once` anchors to the last
    AFFIX_TEMPLATES action; the execute order is
    `... AFFIXES -> SLOTS -> AFFIX_TEMPLATES -> STEMS`. So it ran one category
    BEFORE `MoStemMsa` objects were created, and every `MoStemMsa` owner it
    asked about resolved to `None`.

    Measured (T124, three sanctioned pairs): `MoStemMsa.MsFeatures`
    117 / 782 / 104 -> **0 / 0 / 0**, 1,003 objects, the largest single block
    in the residue -- while `MoDerivAffMsa.From/ToMsFeatures` (17/17) and
    `MoAffixAllomorph.MsEnvFeatures` (1/1) worked, because those owners hang
    off AFFIX entries and existed already. The STEMS/AFFIXES split in the
    measurement IS the schedule and nothing else.

    ITS OWN LATCH, DELIBERATELY. `_ensure_171_subpass` guards on
    `_did_171_subpass`, which the AFFIX_TEMPLATES tail sets -- so while this
    pass lived inside that sub-pass, the post-loop safety net that would have
    re-run it was already disarmed by the time it could have helped. A shared
    latch made the bug unreachable by its own remedy. This flag is separate so
    that cannot recur.

    Called after the leaf-dispatch loop, so every owner class exists whatever
    the user selected -- the same argument `_ensure_171_subpass` makes for
    itself, applied to ordering rather than to selection.

    Never raises: a failure here must not lose the writes the run already made.
    """
    if getattr(exec_ctx, "_did_owner_feat_strucs", False):
        return
    if __package__:
        from .categories import _wire_owner_feat_strucs
    else:
        from categories import _wire_owner_feat_strucs  # type: ignore
    plan = getattr(exec_ctx, "_run_plan", None)
    if plan is None:
        return
    try:
        object.__setattr__(exec_ctx, "_did_owner_feat_strucs", True)
    except (AttributeError, TypeError):
        pass
    try:
        late_skips = _wire_owner_feat_strucs(exec_ctx, target, plan)
    except Exception:
        _log.exception(
            "execute: feature-structure owner pass FAILED (swallowed)")
        return
    if late_skips and exec_skips is not None:
        try:
            exec_skips.extend(late_skips)
        except (AttributeError, TypeError):
            pass


def _ensure_entryref_passes(exec_ctx, target, tag, exec_skips):
    """Issue #128: run the LexEntryRef C1 (create + value merge) and C2
    (component/primary wiring) tail passes AFTER the leaf-dispatch loop, on
    any run whose scope includes the lexicon -- including one that planned
    ZERO actions.

    `stems_execute_action` drives both via `_run_tail_once` on the last STEMS
    action, so a re-run that plans nothing (every entry already present)
    never reached the INV-1 merge arm and a source edit to an existing ref's
    `HideMinorEntry` / `Summary` was never carried over. The bindings the
    passes read are stashed at PLAN time for every in-scope entry, planned or
    skipped, so they are complete here; with no lexicon in scope they are
    empty and both passes are no-ops. The tail's own latches
    (`_did_entryref_create_pass`, `_did_post_pass_a`) make this a no-op when
    the tail already ran, so the passes never double-execute; both passes are
    idempotent (a second clean run writes nothing).

    Never raises: a failure must not lose the writes the run already made."""
    plan = getattr(exec_ctx, "_run_plan", None)
    if plan is None:
        return
    if __package__:
        from .categories import _run_entryref_create_pass, _run_post_pass_a
    else:
        from categories import (  # type: ignore
            _run_entryref_create_pass, _run_post_pass_a)
    for flag, runner in (("_did_entryref_create_pass", _run_entryref_create_pass),
                         ("_did_post_pass_a", _run_post_pass_a)):
        if getattr(exec_ctx, flag, False):
            continue
        try:
            object.__setattr__(exec_ctx, flag, True)
        except (AttributeError, TypeError):
            pass
        try:
            late_skips = runner(exec_ctx, target, tag)
        except Exception:
            _log.exception("execute: %s safety net FAILED (swallowed)", flag)
            continue
        if late_skips and exec_skips is not None:
            try:
                exec_skips.extend(late_skips)
            except (AttributeError, TypeError):
                pass


def _ensure_complex_feature_type_ra(exec_ctx, target, exec_skips):
    """Issue #37: wire `IFsComplexFeature.TypeRA` AFTER the leaf-dispatch
    loop, via `categories._run_complex_feature_type_ra_pass`.

    INFLECTION_FEATURES creates the complex feature one category BEFORE
    FEATURE_STRUCT_TYPES creates the type it points at, so the create path
    cannot wire it. Anchoring this to the last action of either category (the
    `_run_tail_once` idiom) is not enough: a re-run in which both objects
    already exist plans no action in either category, and that is exactly the
    run that must repair a `TypeRA` an earlier run left null. Here, after
    every category, both endpoints exist whatever the selection planned.

    Own latch; never raises (a failure must not lose the run's writes).
    """
    if getattr(exec_ctx, "_did_complex_type_ra", False):
        return
    if getattr(exec_ctx, "_run_plan", None) is None:
        return
    if __package__:
        from .categories import _run_complex_feature_type_ra_pass
    else:
        from categories import _run_complex_feature_type_ra_pass  # type: ignore
    try:
        object.__setattr__(exec_ctx, "_did_complex_type_ra", True)
    except (AttributeError, TypeError):
        pass
    try:
        late_skips = _run_complex_feature_type_ra_pass(exec_ctx, target)
    except Exception:
        _log.exception(
            "execute: complex-feature TypeRA pass FAILED (swallowed)")
        return
    if late_skips and exec_skips is not None:
        try:
            exec_skips.extend(late_skips)
        except (AttributeError, TypeError):
            pass


def _ensure_struct_type_features_rs(exec_ctx, target, exec_skips):
    """Issue #108: repair `IFsFeatStrucType.FeaturesRS` (both feature
    systems) AFTER the leaf-dispatch loop, via
    `categories._run_struct_type_features_rs_pass`.

    The create paths wire `FeaturesRS` only when the type is created; a type
    created before its member defns existed stayed incomplete forever,
    because every later run plans it ALREADY_PRESENT_BY_GUID. The repairing
    re-run plans no action in the types or the features category, so this
    cannot be an action-anchored `_run_tail_once` tail; here, after every
    category, all endpoints of the run exist whatever the selection planned.

    Own latch (never shared with the #37 TypeRA pass); never raises -- a
    failure must not lose the writes the run already made.
    """
    if getattr(exec_ctx, "_did_struct_type_features_rs", False):
        return
    if getattr(exec_ctx, "_run_plan", None) is None:
        return
    if __package__:
        from .categories import _run_struct_type_features_rs_pass
    else:
        from categories import _run_struct_type_features_rs_pass  # type: ignore
    try:
        object.__setattr__(exec_ctx, "_did_struct_type_features_rs", True)
    except (AttributeError, TypeError):
        pass
    try:
        late_skips = _run_struct_type_features_rs_pass(exec_ctx, target)
    except Exception:
        _log.exception(
            "execute: struct-type FeaturesRS repair pass FAILED (swallowed)")
        return
    if late_skips and exec_skips is not None:
        try:
            exec_skips.extend(late_skips)
        except (AttributeError, TypeError):
            pass


def execute(plan: RunPlan, source, target, report_sink, tag: ImportResidueTag,
            interactive_session=None) -> RunReport:
    """Apply `plan.actions` to `target` and return a finalized RunReport.

    `report_sink` is the FlexTools-style report object exposing
    `.Info(msg)` / `.Warning(msg)` / `.Error(msg)` / `.Blank()`. We mirror
    the spike's diagnostic logging there.

    `interactive_session` (Phase 2, optional): an InteractiveSession with
    user-resolved MergeDecisionLogs.  When supplied, each overwrite
    branch consults `session.merge_decisions_by_guid[target_guid]` and
    applies the decisions via `_apply_merge_decisions` before writing.
    When None, behaviour is bit-identical to Phase 1 (FR-109 source-wins).

    PRECONDITION (UI-enforced per contracts/module-ui.md): the caller has
    already verified that the plan was produced from the current selection.
    """
    start = time.time()

    # WS remap dict (source_ws_id -> target_ws_id) applied by every
    # ApplySyncableProperties call. Without it, multilingual values under a
    # source WS Id the target lacks (e.g. source vernacular ``mgz`` vs target
    # ``etu``) are SILENTLY DROPPED and the field lands empty. Computed once;
    # threaded to the create path via exec_ctx._ws_map and to the
    # overwrite/update path via the ws_map= parameter.
    ws_map = to_ws_map_dict(getattr(plan, "ws_mapping", None))

    # Feature 024 (T010/T016, FR-010/FR-012): per-run dropped-item collector
    # and resolver cache, created HERE (rather than alongside exec_ctx below)
    # so the OVERWRITE loop -- which runs BEFORE exec_ctx exists -- can also
    # thread them into `_execute_overwrite` (US2, FIX 1a). The SAME list/dict
    # objects are attached to exec_ctx further down (`object.__setattr__`)
    # so the leaf-dispatch/closure-walk resolver calls share one collector
    # and one cache for the whole run.
    _dropped: list = []
    _resolver_cache: dict = {}
    # Issue #130: created here (not at the exec_ctx attach below) so the
    # OVERWRITE loop, which runs first, can record MSA slot-link outcomes on
    # the SAME list the 17.1 sub-pass later appends to.
    _affix_slot_links: list = []

    if _log.isEnabledFor(logging.DEBUG):
        _log.debug(
            "execute: entry  mode=MOVE tag=%r actions=%d overwrites=%d skips=%d "
            "source=%r target_handle_id=%s interactive_session=%s",
            tag.serialize() if hasattr(tag, "serialize") else str(tag),
            len(plan.actions), len(getattr(plan, "overwrites", ()) or ()),
            len(plan.skips),
            getattr(plan.context, "source_project_name", "?"),
            id(target), interactive_session is not None,
        )

    # Behavior-neutral persist-diagnostic counters for leaf dispatch.
    leaf_attempted = 0
    leaf_succeeded = 0
    leaf_failed = 0
    # Feature 037 (defect C): first-class per-item failure records, folded
    # into RunReport.leaf_execution_failures below. `leaf_failed` (the plain
    # int counter above) stays for the existing log line's behaviour-neutral
    # diagnostics; `_leaf_execution_failures` is what actually reaches the
    # report so a caller can tell "139 planned, 139 written" from
    # "139 planned, 98 written, 41 swallowed" -- the swallow-and-continue
    # policy itself is unchanged, only the report's truthfulness.
    _leaf_execution_failures: list = []
    # Issue #68: (category, source_guid) of every leaf action that did NOT
    # end in a write (raised, or explicitly declined via `ActionOutcome`).
    # `RunReport.build_from_plan(not_added=...)` subtracts them from `added`
    # so the report counts OUTCOMES, not the plan.
    _not_added: list = []
    _declined_skips: list = []
    # Issue #49 (defect 1): (action, expected target GUID) for every leaf action
    # the handler reported as written; checked against the target after the
    # dispatch loop by `reconcile_added_actions`.
    _verify_candidates: list = []

    # Build index of source actions for quick lookup of pulled-in flag.
    # plan.actions is heterogeneous: CreateDefinitionAction has no
    # `pulled_in_by`, so read it defensively (see report.py for the same guard).
    pulled_in_guids = frozenset(
        a.source_guid for a in plan.actions if getattr(a, "pulled_in_by", ())
    )

    # Find every POS the plan touches (as action or skip) and execute its
    # closure: POS → Templates → Slots → LexEntries(MSA-points-at-POS) →
    # Senses → MSAs → Allomorphs → PhEnvironments. Mid-run exceptions
    # bubble up to the FlexTools runner's UOW, which rolls back the entire
    # transaction (R10).
    # SUPERSEDE DECISION (2026-07-06): the execute-side verb-vertical is retired
    # alongside its planning-side counterpart (preview.build_run_plan). Both it
    # and the leaf-dispatch loop below created POS/templates/slots/affix-closures,
    # double-transferring the same objects and colliding on identical GUIDs
    # (integration harness 2026-07-06: 88 affixes x2 = 176 dup-GUID errors).
    # Leaf-dispatch (AFFIXES/SLOTS/AFFIX_TEMPLATES/GRAM_CATEGORIES/PH_ENVIRONMENT)
    # is now the single execution path. Keep this flag in lockstep with
    # preview._VERB_VERTICAL_ENABLED; flip both to True only to A/B the legacy path.
    _VERB_VERTICAL_ENABLED = False
    pos_guids = _pos_guids_from_plan(plan) if _VERB_VERTICAL_ENABLED else []
    if not pos_guids:
        report_sink.Info("[Move] Verb-vertical superseded; leaf-dispatch is the sole path.")
    for pos_guid in pos_guids:
        _execute_verb_vertical(plan, source, target, report_sink, tag, pulled_in_guids, pos_guid)
        _execute_layer3(plan, source, target, report_sink, tag, pos_guid)

    # Phase 1 (FR-101): apply OVERWRITE / UPDATE actions.  Each PlannedOverwrite
    # looks up the existing target object by GUID and applies the source's
    # syncable properties.  The conflict mode for the category governs which
    # write semantic is used:
    #   ConflictMode.UPDATE    -> apply_update_semantic (real Merge, T012; the
    #                             legacy persisted "merge" resolves here, #22)
    #   ConflictMode.LINK      -> no field writes (LINK = link by GUID only)
    #   ConflictMode.OVERWRITE -> _execute_overwrite (destructive, Phase 1)
    # Pre-overwrite snapshots in the residue carrier (FR-106) are TODO Phase 1.1.
    # NOTE: AFFIXES/STEMS UPDATE is gated on Phase-3c category engines (features
    # 007/019) that don't yet emit overwrite-candidates, so UPDATE routing is
    # presently exercised via GOLD_RESERVED categories (PHONOLOGICAL_FEATURES,
    # GRAM_CATEGORIES/POS, INFLECTION_FEATURES, VARIANT_TYPES, COMPLEX_FORM_TYPES,
    # SEMANTIC_DOMAINS).
    if __package__:
        from .models import ConflictMode as _ConflictMode
    else:
        from models import ConflictMode as _ConflictMode  # type: ignore
    extra_skips = []
    # Feature 038 T045: the MEASURED enrichment records (what the writes
    # actually achieved) and the GUIDs the plan will create through their own
    # PlannedAction. The latter is what lets the owned-collection pass DEFER a
    # child whose dedicated category create path runs later in this same
    # execute() -- see `_enrich_owned_collections`.
    _measured_enrichments: list = []
    _planned_action_guids = frozenset(
        a.source_guid for a in getattr(plan, "actions", ())
        if getattr(a, "source_guid", None)
    )
    # Issue #22 Part 1 (audit blind spot 5): a merge the plan promised for a
    # category whose UPDATE executor has no ops accessor writes nothing. Say so
    # once per category, as a Warning, instead of only in per-item Info lines
    # (measured live: 1730 SEMANTIC_DOMAINS merges, every one a no-op).
    _unwired = {}
    for ow in getattr(plan, "overwrites", ()):
        if (plan.selection.conflict_mode_for(ow.category) == _ConflictMode.UPDATE
                and ow.category not in _OPS_ACCESSOR_FOR_CATEGORY
                and getattr(ow, "write_mode", "") != "structural_rebuild"
                and not (ow.category in (GrammarCategory.ENTRY,
                                         GrammarCategory.AFFIXES,
                                         GrammarCategory.STEMS)
                         and getattr(ow, "match_via", "guid") == "identity_remap")):
            _unwired[ow.category] = _unwired.get(ow.category, 0) + 1
    for _cat, _n in sorted(_unwired.items(), key=lambda kv: kv[0].value):
        report_sink.Warning(
            f"  [{_cat.value}] {_n} planned merge(s) NOT applied: the UPDATE"
            " (Merge) executor is not wired for this category"
        )
    for ow in getattr(plan, "overwrites", ()):
        # identity_remap ENTRY overwrites are handled inside _execute_layer3
        # (where identity_remap, target_verb, target_slot_by_guid, env_guid_to_target
        # are in scope). Skip them here to avoid double-execution.
        if (ow.category in (GrammarCategory.ENTRY, GrammarCategory.AFFIXES, GrammarCategory.STEMS)
                and getattr(ow, "match_via", "guid") == "identity_remap"):
            continue
        # T012: consult the selection's conflict mode before dispatching.
        _cat_mode = plan.selection.conflict_mode_for(ow.category)
        if _cat_mode == _ConflictMode.UPDATE:
            # Non-destructive UPDATE: compute disposition then apply_update_semantic.
            # LINK intent: item already present, no field writes.
            _update_skips = _execute_update_semantic(
                ow, source, target, report_sink, tag, ws_map=ws_map,
                dropped=_dropped,
                enrichments=_measured_enrichments,
                planned_action_guids=_planned_action_guids,
            )
            if _update_skips:
                extra_skips.extend(_update_skips)
        elif _cat_mode == _ConflictMode.LINK:
            # LINK: already in target by GUID — no field writes, just log.
            report_sink.Info(
                f"  [{ow.category.value}] LINK mode — item present, no field writes"
                f"  guid={ow.source_guid[:8]}"
            )
        else:
            # OVERWRITE (or any unknown mode): existing destructive path.
            # Feature 024 US2 (FIX 1a): `_dropped`/`_resolver_cache` threaded
            # in so the SENSE/ENTRY branches' reference-field routing shares
            # the SAME per-run collector/cache as the ADD/closure path --
            # `_dropped` is folded into the RunReport via `extra_dropped_items`
            # below (mutated in place; NOT re-added via extra_skips, which
            # would double-count it). `_execute_overwrite`'s return value may
            # now also contain DroppedItemRecord instances (for a caller that
            # observes the return directly, e.g. unit tests) -- only Skip
            # instances belong in extra_skips.
            _ow_result = _execute_overwrite(
                ow, source, target, report_sink, tag, interactive_session,
                ws_map=ws_map, dropped=_dropped, resolver_cache=_resolver_cache,
                affix_slot_links=_affix_slot_links,
            ) or []
            extra_skips.extend(s for s in _ow_result if isinstance(s, Skip))

    # Phase 3a leaf-category dispatch (execute side): for every
    # PlannedAction whose category is in the leaf set, route through
    # the registered execute_action callback.  Skips and overwrites
    # are handled by the existing paths above.
    _LEAF_DISPATCH_CATEGORIES = (
        # Phase 3a (memo steps 2-5 + 5b)
        GrammarCategory.PHONOLOGICAL_FEATURES,
        # PHON_FEAT_TYPES (Part B.4) MUST dispatch after PHONOLOGICAL_FEATURES
        # so its FeaturesRS resolution finds defns already landed in target
        # PhFeatureSystemOA.FeaturesOC.
        GrammarCategory.PHON_FEAT_TYPES,
        GrammarCategory.PHONEMES,
        GrammarCategory.NATURAL_CLASSES,
        GrammarCategory.PH_ENVIRONMENT,
        GrammarCategory.PHONOLOGICAL_RULES,
        GrammarCategory.STRATA,
        # Phase 3b (memo steps 6-13b)
        GrammarCategory.GRAM_CATEGORIES,
        # POS: the pick-driven ALIAS of GRAM_CATEGORIES. Kept in lockstep with
        # `preview.build_run_plan`'s identical list -- a POS-stamped
        # PlannedAction that the planner emits but this filter drops would be
        # a Preview/Move divergence (Principle III): Preview would promise a
        # POS the run never creates, and every downstream executor that
        # resolves an owning POS would then abandon its item.
        GrammarCategory.POS,
        GrammarCategory.INFLECTION_FEATURES,
        GrammarCategory.CUSTOM_FIELDS,
        GrammarCategory.INFLECTION_CLASSES,
        GrammarCategory.FEATURE_STRUCT_TYPES,
        GrammarCategory.POS_INFLECTABLE_FEATS,
        GrammarCategory.STEM_NAMES,
        GrammarCategory.EXCEPTION_FEATURES,
        GrammarCategory.VARIANT_TYPES,
        GrammarCategory.COMPLEX_FORM_TYPES,
        GrammarCategory.SEMANTIC_DOMAINS,
        # Phase 3c (memo steps 14-18) — same order as preview.py; required
        # by FR-333 (17.1 sub-pass) + FR-340 (post-pass A) tail-block timing.
        GrammarCategory.AFFIXES,
        GrammarCategory.ADHOC_COMPOUND_RULES,
        GrammarCategory.SLOTS,
        GrammarCategory.AFFIX_TEMPLATES,
        GrammarCategory.STEMS,
    )
    if __package__:
        from .categories import for_category as _for_category
    else:
        from categories import for_category as _for_category  # type: ignore
    # Build a synthetic RunContext for execute_action since the per-category
    # callbacks expect it (mirrors the planner's context).
    if __package__:
        from .models import RunContext as _RunContext
    else:
        from models import RunContext as _RunContext  # type: ignore
    exec_ctx = _RunContext(
        source_handle=source,
        source_project_name=plan.context.source_project_name,
        source_project_path=plan.context.source_project_path,
        target_handle=target,
        target_project_name=plan.context.target_project_name,
        target_project_path=plan.context.target_project_path,
        run_id=plan.context.run_id,
        started_at=plan.context.started_at,
    )
    # Phase 3c: thread plan reference so execute_action tail blocks
    # (AFFIX_TEMPLATES 17.1 sub-pass, STEMS post-pass A) can access
    # plan.msa_slot_bindings / plan.lexentry_ref_bindings / plan.identity_remap.
    # RunContext is frozen=True; use object.__setattr__ to attach dynamic attr.
    object.__setattr__(exec_ctx, '_run_plan', plan)
    # WS remap dict read by the create-path ApplySyncableProperties calls
    # (categories.py) that only receive `context`, not the ws_map arg.
    object.__setattr__(exec_ctx, '_ws_map', ws_map)
    # Phase 3c: collector for execute-time skips emitted by tail blocks
    # (AFFIX_TEMPLATES 17.1 sub-pass, STEMS post-pass A) — folded into the
    # run report's extra_skips after the leaf loop.
    _exec_skips: list = []
    object.__setattr__(exec_ctx, '_exec_skips', _exec_skips)
    # Feature 024 (T010/T016, FR-010/FR-012, contracts/dropped-item-report.md
    # "Collection"): per-run dropped-item collector threaded into the closure
    # walk (Lib/categories.py `_walk_lex_entry_closure` / `_walk_entry_allomorphs`
    # / `_apply_reference_fields`, read via `context._dropped`) so the
    # resolver (Lib/references.py, US1) can append DroppedItemRecord
    # instances. Folded into the RunReport below (`extra_dropped_items`) so
    # Move-mode reporting is wired end-to-end.
    # Feature 024 US2 (FIX 1a): `_dropped` is the SAME object created above
    # (before the OVERWRITE loop) so records the OVERWRITE-path resolver
    # calls append during that loop are ALSO present here — not a second,
    # disconnected collector.
    object.__setattr__(exec_ctx, '_dropped', _dropped)
    # Feature 024 (T016, FR-012): per-run GUID -> resolved/created target
    # item cache for the resolver, mirroring `_dropped` above (and
    # `Lib/preview.py.build_run_plan`'s identical attachment). Also the SAME
    # object created above so the OVERWRITE-path resolver calls share one
    # cache with the ADD/closure path (FR-012 idempotency across the whole
    # run, not just within one path).
    object.__setattr__(exec_ctx, '_resolver_cache', _resolver_cache)
    # Feature 024 (T029/T030, US3, FR-009a): per-run copy-set dict
    # (`Lib/owned.py`'s `ctx._copy_set` convention) threaded the same way as
    # `_dropped`/`_resolver_cache` above, so `owned.reproduce_allomorph_hung_data`'s
    # APR copy-set gate sees every allomorph already copied earlier in this
    # SAME run (across every entry, not just the one currently being copied).
    object.__setattr__(exec_ctx, '_copy_set', {})
    # Feature 038 (T060, US5, FR-023..FR-025): per-run process-rule collector,
    # threaded exactly like `_dropped` above and folded into the RunReport
    # below (`extra_process_rules`).
    #
    # WHERE THE EXECUTOR LIVES, and why it is not a leaf-dispatch category. A
    # `MoAffixProcess` is an `IMoForm` owned by `LexEntry.LexemeFormOA` /
    # `AlternateFormsOS` -- it IS an allomorph as far as ownership goes, so it
    # is reproduced inside the entry closure walk
    # (`categories._reproduce_affix_process`, reached from
    # `_walk_entry_allomorphs`) rather than from a category action of its own.
    # Giving it a parallel executor here would mean walking the entries a
    # second time and creating the rule after its owning entry, which is the
    # ordering that made the original defect invisible.
    #
    # FR-024's resolution -- every phoneme and natural-class reference
    # resolving to the destination item matched under FR-001/FR-002, identity
    # first and then a roster-admitted natural key, never a duplicate -- lives
    # in `categories._resolve_process_referent`, shared with the Preview twin
    # so the two cannot disagree.
    #
    # `plan.process_rules` carries the PLAN's non-reproductions. Both are
    # handed to `report.build`, which MERGES them by source GUID with the
    # run's record winning -- they are NOT disjoint, and an earlier version of
    # this comment claimed they were. A rule the plan predicted unreproducible
    # and the run then also skipped is in both, and concatenating them listed
    # that rule twice in `rules_not_reproduced`. See
    # `report._merge_process_rules` for why the run must win rather than the
    # plan.
    _process_rules: list = []
    object.__setattr__(exec_ctx, '_process_rules', _process_rules)
    # T074 (FR-019 / SC-003): what the 17.1 sub-pass did with each affix MSA
    # that occupied a template column in the source -- linked, or not, with the
    # reason. Same collector idiom as `_process_rules` above; handed to
    # `build_from_plan(extra_affix_slot_links=)` below. Pre-T074 the run report
    # carried no link tally at all, so SC-003 was answerable only from a
    # bespoke driver.
    object.__setattr__(exec_ctx, '_affix_slot_links', _affix_slot_links)
    # Feature 038 T036: the CURRENT action's `PlannedDestination`, re-set on
    # every leaf-dispatch iteration below. Seeded here with the
    # "plan decided nothing" value so a consumer added later never has to
    # distinguish "not attached" from "no match_basis" -- those are the same
    # answer, and only one of them should have to be written down.
    object.__setattr__(exec_ctx, '_planned_destination',
                       PlannedDestination(DESTINATION_UNDETERMINED))
    leaf_count = 0
    for action in plan.actions:
        if action.category not in _LEAF_DISPATCH_CATEGORIES:
            continue
        # C6 NOTE: the Phoneme/Environment flexicon version gate
        # (_phoneme_env_field_diff_enabled, issue #16) applies ONLY to UPDATE
        # field-diff semantics (_execute_update_semantic on the overwrite path).
        # It must NOT gate a plain ADD here: a create has no field-diff, and
        # skipping the create left phonemes/environments untransferred ->
        # downstream NC/allomorph references to them failed loud ("no
        # counterpart on target"). Creates proceed unconditionally.
        try:
            bundle = _for_category(action.category)
        except KeyError:
            continue
        leaf_attempted += 1
        _log.debug(
            "execute leaf-dispatch: attempting  category=%s guid=%s",
            action.category.value, action.source_guid,
        )
        try:
            # Feature 038 T036 -- the leaf path's half of the single
            # resolve-or-create path.
            #
            # `execute_action` lives in `categories.py` and does its own
            # guard-then-Create on the SOURCE GUID, which is blind to a
            # destination the plan matched by a roster-admitted natural key
            # (that object exists under a different GUID). Resolving the
            # plan's record HERE does two things the category code cannot do
            # for itself yet:
            #
            #   * a record naming a destination the target does not hold
            #     raises `PlannedDestinationError` BEFORE any write, so the
            #     item is never created-anyway as a duplicate, and
            #   * a `MatchBasis.NONE` whose creation the roster refuses
            #     (`MoMorphType`: the morph-types list is project-independent
            #     fixed content, all 19 GUIDs byte-identical across the three
            #     projects measured) is reported instead of minting an object
            #     the canonical list does not contain.
            #
            # The resolved destination is attached to `exec_ctx` on the same
            # `object.__setattr__` convention as `_run_plan` / `_ws_map` /
            # `_dropped`, so the category executors can CONSUME the plan's
            # decision rather than re-deriving it. It is set on every
            # iteration -- never left over from the previous action -- and no
            # consumer exists in `categories.py` yet, which is why this is a
            # seam and not a fix for that module.
            #
            # Raising inside this try is deliberate. The established per-leaf
            # policy here is swallow-and-record (feature 037 defect C), and a
            # harness error routed through it still reaches THREE channels
            # that a `_NullReportSink` cannot discard: the logged traceback,
            # the `report_sink.Warning`, and a first-class
            # `LeafExecutionFailure` in the RunReport. It also keeps the
            # counters honest -- `leaf_succeeded` is incremented only after
            # `execute_action` returns, so a refused item is never counted as
            # a success. Aborting the whole transfer for one item would be
            # louder but would discard the other 138 items' work.
            #
            # With `match_basis=None` (every plan built today) this is one
            # attribute read yielding `DESTINATION_UNDETERMINED`, one
            # `__setattr__`, and no behaviour change whatsoever.
            _dest = planned_destination_for(action, target)
            if _dest.outcome == DESTINATION_REPORT:
                raise PlannedDestinationError(
                    "plan match_basis for " + (_dest.object_class or "?")
                    + " " + action.source_guid + " found no destination and "
                    "creation is not permitted: " + _dest.detail
                )
            object.__setattr__(exec_ctx, '_planned_destination', _dest)
            _result = bundle["execute_action"](action, exec_ctx, ws_map, tag)
            # Issue #68: an explicit ActionOutcome decline is honoured; any
            # other return (None, the created object) counts as added, as it
            # always did.
            if (isinstance(_result, ActionOutcome)
                    and _result.status in (OUTCOME_SKIPPED, OUTCOME_FAILED)):
                _not_added.append((action.category, action.source_guid))
                _log.warning(
                    "execute leaf-dispatch: action %s category=%s guid=%s: %s",
                    _result.status, action.category.value,
                    action.source_guid, _result.reason,
                )
                if _result.status == OUTCOME_FAILED:
                    leaf_failed += 1
                    _leaf_execution_failures.append(LeafExecutionFailure(
                        category=action.category,
                        source_guid=action.source_guid,
                        exception_type="ActionFailed",
                        message=_result.reason,
                    ))
                elif not _result.recorded:
                    _declined_skips.append(Skip(
                        category=action.category,
                        source_guid=action.source_guid,
                        reason=_result.skip_reason
                        or SkipReason.DEPENDENCY_UNRESOLVED,
                        detail=_result.reason,
                    ))
                continue
            # Issue #107: a POS created here gets its owned collections NOW,
            # not on the next run. Own try: a fill failure must not turn the
            # (successful) POS create into a leaf failure.
            try:
                _fill_created_pos_collections(
                    action, _result, source, target, report_sink,
                    ws_map=ws_map, dropped=_dropped,
                    planned_action_guids=_planned_action_guids,
                )
            except Exception as _fill_exc:  # noqa: BLE001 -- LCM/COM failures are wide
                _log.exception(
                    "execute leaf-dispatch: created-POS collection fill FAILED "
                    "category=%s guid=%s", action.category.value,
                    action.source_guid,
                )
                report_sink.Warning(
                    f"  [{action.category.value}] created-POS owned-collection"
                    f" fill raised {type(_fill_exc).__name__}: {_fill_exc}"
                    f"  guid={action.source_guid[:8]}"
                )
                # Never-silent (FR-010): a Warning alone is discarded by the
                # export path; each unfilled collection is a reported drop.
                _record_unfilled_pos_collections(
                    action, _dropped,
                    f"owned-collection fill raised {type(_fill_exc).__name__}:"
                    f" {_fill_exc}",
                )
            leaf_count += 1
            leaf_succeeded += 1
            # Issue #49/#68: with no planned destination the expected GUID is
            # decided AFTER dispatch (None here), because a handler that
            # creates under a remapped GUID records it in identity_remap
            # while it runs -- see `reconcile_added_actions`.
            _verify_candidates.append((
                action,
                _dest.target_guid if _dest.outcome == DESTINATION_RESOLVED
                else None,
            ))
        except Exception as exc:
            leaf_failed += 1
            _not_added.append((action.category, action.source_guid))
            # Persist diagnostics: the original code only funneled this into a
            # report_sink.Warning, which the export path discards via a
            # _NullReportSink. Emit the full traceback so the swallowed failure
            # is visible when GRAMTRANS_DEBUG is on. Keep the Warning too.
            _log.exception(
                "execute leaf-dispatch: execute_action FAILED (swallowed) "
                "category=%s guid=%s",
                action.category.value, action.source_guid,
            )
            report_sink.Warning(
                f"  [{action.category.value}] execute_action raised "
                f"{type(exc).__name__}: {exc}; skipping {action.source_guid[:8]}"
            )
            # Feature 037 (defect C): the report_sink.Warning above is the
            # ONLY prior trace of this failure, and an export-mode
            # `_NullReportSink` discards it -- exactly the same shape as the
            # FeaturesOA (task 4) and rule-ref (defect B) findings. Record it
            # as a first-class LeafExecutionFailure so RunReport.leaf_failed
            # is truthful regardless of report sink.
            _leaf_execution_failures.append(LeafExecutionFailure(
                category=action.category,
                source_guid=action.source_guid,
                exception_type=type(exc).__name__,
                message=str(exc),
            ))
    if leaf_count:
        report_sink.Info(f"[Move] Leaf-dispatch executed {leaf_count} action(s).")

    # FR-333 safety net -- the 17.1 sub-pass must not depend on the SELECTION.
    #
    # `_run_171_subpass` (MoInflAffMsa.SlotsRC + MSA.InflFeatsOA wiring) is
    # normally driven by `_run_tail_once` on the LAST executed AFFIX_TEMPLATES
    # action. That makes it silently conditional on the user having selected
    # affix templates: a run that transfers AFFIXES/STEMS without them has zero
    # AFFIX_TEMPLATES actions, the tail never fires, and every transferred
    # affix MSA is left with an empty SlotsRC -- the affixes are not linked to
    # any template column -- plus no inflection features. Nothing reported it.
    #
    # Running it here instead is safe in both directions: the leaf-dispatch
    # loop above has finished EVERY category (slots included), so all wiring
    # endpoints exist, and `_did_171_subpass` makes this a no-op when the
    # template tail already ran it.
    _ensure_171_subpass(exec_ctx, target, tag, _exec_skips)

    # T119's feature-structure owner pass, AFTER the 17.1 sub-pass and after
    # every category. It used to run INSIDE that sub-pass, i.e. anchored to
    # AFFIX_TEMPLATES -- one category before STEMS creates the `MoStemMsa`
    # objects that own 1,003 of the feature structures it is meant to fill.
    # Every one of them resolved to a non-existent owner and was discarded
    # silently. See `_ensure_owner_feat_strucs` for the measurement.
    _ensure_owner_feat_strucs(exec_ctx, target, tag, _exec_skips)

    # Issue #54: a starter `PhNCSegments` the plan matched by natural key gets
    # its source class's members, after every create (see the helper).
    _ensure_matched_nc_segments(exec_ctx, target, _exec_skips)

    # Issue #128: LexEntryRef value merge + C2 wiring, also on a 0-action
    # re-run (see helper). After every category so all lexemes exist.
    _ensure_entryref_passes(exec_ctx, target, tag, _exec_skips)

    # Issue #37: complex-feature TypeRA, after every feature and struct-type
    # of the run exists -- and on a re-run that planned neither.
    _ensure_complex_feature_type_ra(exec_ctx, target, _exec_skips)

    # Issue #108: struct-type FeaturesRS, after every feature defn and
    # struct-type of the run exists -- and on a re-run that planned neither.
    _ensure_struct_type_features_rs(exec_ctx, target, _exec_skips)

    # Issue #49 (defect 1): handler exit proves nothing -- a handler that
    # returns normally while writing nothing used to be counted as added. Check
    # every reported-added action against the actual target, by GUID.
    _unverified: list = []
    for _cat, _guid, _why in reconcile_added_actions(
            target, _verify_candidates,
            identity_remap=getattr(plan, "identity_remap", None),
            unverified=_unverified):
        leaf_failed += 1
        _not_added.append((_cat, _guid))
        _log.warning("execute reconcile: %s %s: %s", _cat.value, _guid, _why)
        _leaf_execution_failures.append(LeafExecutionFailure(
            category=_cat, source_guid=_guid,
            exception_type="UnverifiedWrite", message=_why,
        ))

    # Issue #49/#68 (cycle 3 P1-c): an action whose GUID lookup RAISED could
    # not be verified. It must not read as "added-verified": record each as a
    # failure-style entry (type LookupUnverified) and take it out of `added`.
    for _cat, _guid, _why in _unverified:
        leaf_failed += 1
        _not_added.append((_cat, _guid))
        _leaf_execution_failures.append(LeafExecutionFailure(
            category=_cat, source_guid=_guid,
            exception_type="LookupUnverified", message=_why,
        ))

    # Feature 024 (T031, US3, FR-008 -- single-final-pass redesign):
    # `reproduce_all_lexical_relations` is the SOLE lexical-relation
    # discovery + reproduction path (see its own module banner at
    # categories.py:3488-3504) -- it runs exactly ONCE, here, after the
    # leaf-dispatch loop above has finished every AFFIXES/STEMS entry (the
    # two categories that populate `_copy_set`), so every top-level sense
    # and recursively-copied sub-sense/allomorph this run will ever create
    # is already registered. There is no per-member incremental trigger
    # anywhere in `_walk_lex_entry_closure`/`owned.walk_owned_children`
    # during the loop above; a relation touching any copied member is
    # discovered and evaluated for the first and only time right here,
    # source-ordered by construction (`_iter_relations_touching_copy_set`
    # walks the copy_set once). Preview runs the SAME single final pass
    # (`preview.plan_all_lexical_relations`, called from
    # `preview.build_run_plan` after its own leaf-category loop) over the
    # SAME kind of fully-settled copy_set, so the two converge on
    # identical relations-in/decisions-out.
    if __package__:
        from .categories import reproduce_all_lexical_relations
    else:
        from categories import reproduce_all_lexical_relations  # type: ignore
    reproduce_all_lexical_relations(exec_ctx, tag, _resolver_cache, _dropped)

    # Feature 026 (texts-wordforms, T010): apply the text + wordform walk.
    # Runs AFTER the lexical leaf dispatch + relation reproduction so every
    # morph-bundle target (senses/MSAs/allomorphs from 024) exists before an
    # analysis is wired to it by identity (R8 ordering). Consumes the
    # TextTransferPlans built during Preview (plan.text_plans) and shares the
    # SAME per-run `_dropped` collector + `_resolver_cache` (genres/tags) so
    # dropped texts/segments/references land in the unified report (FR-023).
    # Inert when no text was selected (empty plan.text_plans).
    _text_plans = getattr(plan, "text_plans", ()) or ()
    _text_outcome = None
    if _text_plans:
        if __package__:
            from .texts import apply_texts as _apply_texts
        else:
            from texts import apply_texts as _apply_texts  # type: ignore
        _text_outcome = _apply_texts(
            _text_plans, source, target, exec_ctx, tag, report_sink,
            _resolver_cache, _dropped)
        report_sink.Info(f"[Move] Texts walk applied {len(_text_plans)} text plan(s).")

    # Feature 025 (full reversals, US1 T018/T020): the reversal closure
    # walk's Move-mode twin -- SAME single-final-pass timing as
    # `reproduce_all_lexical_relations` immediately above, over the SAME
    # now-fully-settled `exec_ctx._copy_set` (real created target objects,
    # not Preview's `True` placeholder). Reversal index/entry writes happen
    # ONLY here, in Move mode, after the plan has already been shown to the
    # user via Preview (Principle III) -- `Lib/preview.py.build_run_plan`
    # never writes; this is the sole write path.
    if __package__:
        from .categories import reproduce_reversal_entries
    else:
        from categories import reproduce_reversal_entries  # type: ignore
    reproduce_reversal_entries(exec_ctx, tag, _resolver_cache, _dropped)

    # Feature 025 (full reversals, US3 T033): Part B `.fwdictconfig`
    # configuration-view file copy -- the sole write path for config views
    # (Preview's `Lib/preview.py.build_run_plan` only PLANS them via
    # `config_views.plan_config_views`, never writes). Runs after every LCM
    # write above (leaf-dispatch, lexical relations, reversals) so the
    # config-view copy is the run's last step, matching its role as a
    # sidecar/cosmetic file rather than model data. `plan.config_view_records`
    # defaults to `()` for any plan built before this field existed, so this
    # is a no-op for such a plan. `apply_config_views` appends every record's
    # `missing_refs` into `_dropped` -- already-collected duplicates from
    # Preview's own scan of the SAME records are harmless (missing_refs
    # describe file-reference gaps, not model writes, so there is no
    # "double execution" risk the OVERWRITE-loop comment above warns about;
    # worst case is a cosmetic duplicate report line, and `_dropped` here is
    # the same list threaded through this whole function, not a second one).
    if __package__:
        from .config_views import apply_config_views
    else:
        from config_views import apply_config_views  # type: ignore
    apply_config_views(getattr(plan, "config_view_records", ()), _dropped)

    # Fold any tail-block skips (17.1 / post-pass A) into the report.
    if _exec_skips:
        extra_skips.extend(_exec_skips)
    # Issue #68: skips the engine recorded for handlers that declined.
    if _declined_skips:
        extra_skips.extend(_declined_skips)
    # Issue #45: text adds/updates/skips reach per_category[TEXTS].
    _texts_added = _texts_updated = 0
    if isinstance(_text_outcome, dict):
        _texts_added = int(_text_outcome.get("added", 0) or 0)
        _texts_updated = int(_text_outcome.get("updated", 0) or 0)
        extra_skips.extend(_text_outcome.get("skips") or ())

    elapsed = time.time() - start
    # Persist diagnostics. Issue #68: the report's `added` counts are built
    # from dispatch OUTCOMES (`not_added=` below), not from the plan.
    _log.debug(
        "execute: leaf-dispatch counts  attempted=%d succeeded=%d failed=%d "
        "not_added=%d vs len(plan.actions)=%d",
        leaf_attempted, leaf_succeeded, leaf_failed, len(_not_added),
        len(plan.actions),
    )
    # Build the report from the plan, minus the leaf actions that raised or
    # declined (#68). Every plan.Skip → +1 skipped; every declined action
    # contributes its own Skip, so FR-018 still holds by construction.
    # Feature 024 (T023, FR-013): per-object FidelityStatus (FULL/PARTIAL)
    # computed from the same `_dropped` collector -- see
    # `categories.compute_fidelity_by_guid`'s docstring for the FULL-by-
    # absence convention.
    if __package__:
        from .categories import compute_fidelity_by_guid as _compute_fidelity_by_guid
    else:
        from categories import compute_fidelity_by_guid as _compute_fidelity_by_guid  # type: ignore
    # Feature 038 T045: hand the report the MEASURED enrichment records in
    # place of the plan's PROJECTION, so a Move report says what the writes
    # achieved. Substitution, never addition: `report._build_from_plan` UNIONs
    # `plan.enrichments` with `extra_enrichments`, so appending would report
    # every enrichment twice and break the `per_category[*].enriched ==
    # len(enrichments)` reconciliation in `RunReport.__post_init__`.
    #
    # Guarded on an exact one-to-one GUID cover: anything less means some
    # planned enrichment never reached the executor (a category whose
    # ConflictMode is not UPDATE, an object the resolve half could not find),
    # and a partial swap would silently DELETE those rows from the report. In
    # that case the projection stands, which is the pre-T045 behaviour.
    _planned_enrichments = tuple(getattr(plan, "enrichments", ()))
    if _measured_enrichments and _planned_enrichments:
        _planned_keys = [r.source_guid for r in _planned_enrichments]
        _measured_keys = [r.source_guid for r in _measured_enrichments]
        if sorted(_planned_keys) == sorted(_measured_keys):
            import dataclasses as _dc
            plan = _dc.replace(plan, enrichments=tuple(_measured_enrichments))
        else:
            _log.warning(
                "execute: %d planned enrichment(s) but %d measured; keeping the "
                "plan's projection in the report rather than dropping rows",
                len(_planned_enrichments), len(_measured_enrichments),
            )
    return RunReport.build_from_plan(
        plan, RunMode.MOVE,
        wall_clock_seconds=elapsed,
        extra_skips=tuple(extra_skips),
        # Feature 024 (T010/T016): threads end-to-end for Move mode. Live as
        # of T016 -- `_apply_reference_fields` appends a DroppedItemRecord for
        # every REPORT_DROPPED reference decision made during the AFFIXES/
        # STEMS closure write.
        extra_dropped_items=tuple(_dropped),
        fidelity_by_guid=_compute_fidelity_by_guid(_dropped),
        # Feature 037 (defect C): makes RunReport.leaf_failed truthful --
        # previously a swallowed execute_action exception left no trace on
        # the report at all (per_category[*].added is computed from the
        # PLAN, not actual write outcomes).
        extra_leaf_execution_failures=tuple(_leaf_execution_failures),
        not_added=tuple(_not_added),
        text_added=_texts_added,
        text_updated=_texts_updated,
        # Feature 038 (T060, US5): what the entry closure's process-rule
        # executor did with each MoAffixProcess it met -- rebuilt, with its
        # input and output content recorded, or skipped with the reason
        # naming the blocker (SC-010: a run that skipped a rule must not read
        # as clean).
        extra_process_rules=tuple(_process_rules),
        # T074 (FR-019, US3): one record per source affix MSA that occupied a
        # template column -- so the report can state SC-003's numerator AND
        # denominator, and so a suppressed NOT_IN_RUN binding stays countable
        # rather than merely absent.
        extra_affix_slot_links=tuple(_affix_slot_links),
    )


# ============================================================================
# Verb-vertical executor (mirrors STATUS.md Layer 1+2 parity rubric)
# ============================================================================

def _pos_guids_from_plan(plan: RunPlan) -> list:
    """Return the ordered list of source POS GUIDs the plan touches —
    union of POS PlannedActions, POS Overwrites (Phase 1), and POS Skips,
    preserving plan order with no duplicates."""
    seen = set()
    ordered = []
    for a in plan.actions:
        if a.category == GrammarCategory.POS and a.source_guid not in seen:
            seen.add(a.source_guid)
            ordered.append(a.source_guid)
    for ow in getattr(plan, "overwrites", ()):
        if ow.category == GrammarCategory.POS and ow.source_guid not in seen:
            seen.add(ow.source_guid)
            ordered.append(ow.source_guid)
    for s in plan.skips:
        if s.category == GrammarCategory.POS and s.source_guid not in seen:
            seen.add(s.source_guid)
            ordered.append(s.source_guid)
    return ordered


def _execute_verb_vertical(
    plan: RunPlan,
    source,
    target,
    report_sink,
    tag: ImportResidueTag,
    pulled_in_guids: frozenset,
    src_pos_guid: str = None,
) -> None:
    """Apply POS + Template + Slot actions for the Verb vertical.

    Reads each PlannedAction's source GUID from `plan.actions`, resolves the
    source-side LCM object, creates the corresponding target object with the
    GUID preserved, applies syncable properties, and tags with the residue
    `tag`. Mirrors `transfer_verb_vertical()` from the pre-T-Spike monolith
    so the parity rubric passes.
    """
    # ----- POS (single action for the MVP slice) -----
    target_verb = None
    for action in _filter(plan.actions, GrammarCategory.POS):
        src_pos = _find_source_pos_by_guid(source, action.source_guid)
        if src_pos is None:
            report_sink.Warning(f"Source POS {action.source_guid} vanished; skipping")
            continue
        # 038 T036: the plan's own match decision travels with the action.
        # For every plan built today it is None, and the creator behaves
        # exactly as it did before 038.
        target_verb = _create_pos_with_guid(
            target, action.source_guid, source.POS.GetSyncableProperties(src_pos), tag, report_sink,
            match_basis=getattr(action, "match_basis", None),
        )

    # If POS was skipped (already in target), look up the existing target POS
    # by GUID so Template/Slot creation can owner-attach to it.
    if target_verb is None:
        # Find by any POS GUID present in either the actions OR the skips for POS
        guid = _first_pos_guid(plan)
        if guid:
            # T106: `_first_pos_guid` reads `source_guid` off a POS action or
            # skip, so this is a SOURCE GUID. The source object is not in hand
            # here; the resolver scans for it via `source_handle`.
            target_verb = _target_pos_for_source_guid(
                target, guid,
                src_pos=_find_source_pos_by_guid(source, guid),
                source_handle=source)

    if target_verb is None:
        report_sink.Warning("No target Verb POS available; skipping template/slot layer")
        return

    # ----- Templates -----
    target_template = None
    for action in _filter(plan.actions, GrammarCategory.AFFIX_TEMPLATES):
        src_template_wrap = _find_source_template_by_guid(source, action.source_guid)
        if src_template_wrap is None:
            report_sink.Warning(f"Source template {action.source_guid} vanished; skipping")
            continue
        target_template = _create_template_with_guid(
            target,
            target_verb,
            action.source_guid,
            source.MorphRules.GetSyncableProperties(src_template_wrap),
            tag,
            report_sink,
            match_basis=getattr(action, "match_basis", None),  # 038 T036
        )

    # Owner template may have been Skip-by-GUID; resolve from target.
    if target_template is None:
        guid = _first_template_guid(plan)
        if guid:
            target_template = _find_target_template_by_guid(target, target_verb, guid)

    if target_template is None:
        report_sink.Warning("No target Verb template; skipping slot layer")
        return

    # ----- Slots — preserve source order in the template's prefix/suffix ref seqs -----
    # We need the source-side template wrapper so we can read prefix_slots /
    # suffix_slots ordering. Find it scoped to the owner POS (src_pos_guid),
    # or fall back to first-template-any-POS for the backward-compat path.
    pos_lookup_guid = src_pos_guid or _first_pos_guid(plan)
    if pos_lookup_guid is None:
        report_sink.Warning("No POS in plan to scope the template lookup")
        return
    src_template_wrap = _find_source_first_template_for_pos(source, pos_lookup_guid)
    if src_template_wrap is None:
        report_sink.Warning(
            f"Source POS {pos_lookup_guid[:8]}… has no template at execute time; "
            "slot ordering lost"
        )
        return

    ordered_src_slots = []  # list of (kind, slot, slot_guid)
    for kind, slot_iter in (
        ("prefix", src_template_wrap.prefix_slots),
        ("suffix", src_template_wrap.suffix_slots),
        ("proclitic", src_template_wrap.proclitic_slots),
        ("enclitic", src_template_wrap.enclitic_slots),
    ):
        for slot in slot_iter:
            ordered_src_slots.append((kind, slot, _guid_str(slot)))

    target_template_concrete = _cast_template(target_template)
    ref_seqs = {
        "prefix": target_template_concrete.PrefixSlotsRS,
        "suffix": target_template_concrete.SuffixSlotsRS,
        "proclitic": target_template_concrete.ProcliticSlotsRS,
        "enclitic": target_template_concrete.EncliticSlotsRS,
    }

    target_slots_by_guid: dict = {}
    # 038 T036: keep the ACTION, not just its GUID, so the plan's match
    # decision can travel to the creator. The membership test below is
    # unchanged -- `in` on a dict tests its keys, exactly as it did on the set
    # this replaced.
    planned_slot_guids = {
        a.source_guid: a for a in _filter(plan.actions, GrammarCategory.SLOTS)
    }
    for kind, src_slot, slot_guid in ordered_src_slots:
        if slot_guid in planned_slot_guids:
            slot_name = _slot_name(src_slot)
            new_slot = _create_slot_with_guid(
                target, target_verb, slot_guid, slot_name, tag, report_sink,
                match_basis=getattr(planned_slot_guids[slot_guid], "match_basis", None),
            )
            target_slots_by_guid[slot_guid] = new_slot
        else:
            # Slot was Skip-by-GUID; look up the existing target slot.
            existing = _find_target_slot_by_guid(target, target_verb, slot_guid)
            if existing is not None:
                target_slots_by_guid[slot_guid] = existing

        wire = target_slots_by_guid.get(slot_guid)
        if wire is not None and not _ref_seq_contains(ref_seqs[kind], wire):
            ref_seqs[kind].Add(wire)


# ============================================================================
# Feature 038 T036 -- the single resolve-or-create path
# ============================================================================
#
# WHAT THIS REPLACES. Before 038 the executor answered "does this source
# object already have a counterpart in the destination?" in two places, with
# two opposite failure modes:
#
#   * CREATE-ANYWAY. `_idempotency_guard` asks `target.Object(SOURCE guid)`.
#     That question can only ever find an IDENTITY match. When the plan
#     matched a starter object by a roster-admitted NATURAL KEY -- the
#     destination object exists but under a DIFFERENT GUID -- the guard sees
#     nothing and the caller Creates. The cost of that is a duplicate of
#     FLEx's own starter content: a second `Verb`, a second `n`, a second
#     `[C]`, permanently written to .fwdata on CloseProject.
#
#   * RESOLVE-ONLY. `_find_target_pos_by_guid` / `_find_target_template_by_guid`
#     / `_find_target_slot_by_guid` / `_find_target_morph_type_by_guid` /
#     `_find_target_env_by_guid` / `_find_obj_by_guid` each run their OWN
#     category-scoped linear scan; a miss produces `report_sink.Warning(...)`
#     and `return`. The work the plan did for that object is thrown away, and
#     in export mode the `_NullReportSink` discards the Warning too, so the
#     abandon leaves no trace at all (the same shape as feature 037's defect
#     C, which is why `LeafExecutionFailure` exists).
#
# One question, three implementations (`preview.py` scanned one way,
# `transfer.py` another, `categories.py` a third), so the two halves could and
# did disagree. T031 moved the decision into the plan; T036 makes the executor
# CONSUME that decision instead of re-deriving it.
#
# THE CONTRACT. The executor may RESOLVE a GUID to an object. It may NOT
# decide WHICH object corresponds to which -- no scans, no keys, no candidate
# counting, no fallbacks between strategies. Everything below is either a
# GUID -> object lookup, a read of the plan's own record, or a read of the
# roster's per-class CREATION policy (which decides whether a create is
# permitted, never which object matches).
#
# CLEAN DEGRADATION IS THE PRIME CONSTRAINT. `match_basis is None` means the
# plan builder never ran 038's matcher for this item, and that is the state of
# every category today: `preview._emit_present_outcome` attaches a record only
# when its caller passes `object_class=`, and as of T036 NO caller passes it,
# so not one plan item in production carries a record at all. Every path below
# therefore begins by returning `DESTINATION_UNDETERMINED` for a None record,
# which every call site treats as "do exactly what you did before 038". A
# category acquires the new behaviour when, and only when, its planner starts
# attaching a record.


class PlannedDestinationError(RuntimeError):
    """The plan's `match_basis` and the destination project disagree.

    RAISED, never absorbed. A `MatchBasisRecord` whose basis is IDENTITY or
    NATURAL_KEY is a positive assertion by the plan that a specific
    destination object EXISTS and is the counterpart of this source object.
    If the executor cannot resolve that GUID, exactly one of two things is
    true, and both are harness errors rather than data conditions:

      * the plan and the destination project have drifted apart (the usual
        cause is the operator editing the project in FLEx between Preview and
        Move -- the fix is to re-run Preview, not to guess), or
      * the plan builder recorded a GUID it never verified.

    Absorbing it would resurrect precisely the two defects this path exists to
    remove: falling back to Create duplicates the destination object under a
    second GUID, and falling back to a `Warning` + `return` throws the analysis
    away. Neither is safe, so the executor stops instead of choosing one.
    """


#: The plan carries no `match_basis` for this item. PRE-038 BEHAVIOUR,
#: unchanged -- the call site keeps its own GUID-only lookup or its own
#: guard-then-Create. This is a degradation, not an error (FR-013, and the
#: roster's "if 035 rejects an entry" clause).
DESTINATION_UNDETERMINED = "undetermined"

#: The plan named a destination object and it resolved. Use `.obj`; do not
#: re-scan for it, do not create anything.
DESTINATION_RESOLVED = "resolved"

#: The plan found no destination (basis NONE) and creation is permitted --
#: both by the plan item's own verb and by the roster's per-class rule.
DESTINATION_CREATE = "create"

#: The plan found no destination and creation is NOT permitted. The item is
#: reported and skipped; it is never written as something else.
DESTINATION_REPORT = "report"


@dataclass(frozen=True)
class PlannedDestination:
    """The executor-internal answer to "where does this plan item write?".

    Deliberately NOT in `models.py`: it is not part of any plan or report
    artifact, it never crosses a process boundary, and it exists only for the
    few lines between reading `match_basis` and acting on it. Putting it in
    the shared model would invite a producer to build one, which is exactly
    the "the executor decided the match" inversion T036 removes.

    Fields:
        outcome:      one of the four `DESTINATION_*` tokens above.
        obj:          the resolved destination object; only ever non-None for
                      `DESTINATION_RESOLVED`.
        target_guid:  the GUID the plan named. Empty except when RESOLVED.
        object_class: the LCM class the plan's record named.
        basis:        the `MatchBasis` the plan recorded, or None.
        detail:       for `DESTINATION_REPORT`, why creation was refused --
                      written for a human reading the run report, so it names
                      the rule rather than restating the outcome.
    """

    outcome: str
    obj: object = None
    target_guid: str = ""
    object_class: str = ""
    basis: Optional[MatchBasis] = None
    detail: str = ""

    @property
    def undetermined(self) -> bool:
        """True when the plan carried no record and pre-038 behaviour applies.

        Every call site is written as "if the plan decided, obey it; otherwise
        do what you did before", so this reads as the guard it is rather than
        a string comparison repeated a dozen times.
        """
        return self.outcome == DESTINATION_UNDETERMINED

    @property
    def resolved(self) -> bool:
        """True when the plan named a destination object and it was found."""
        return self.outcome == DESTINATION_RESOLVED


def _resolve_guid_in_target(target, guid_str: str):
    """The ONE resolution primitive: a GUID string -> the target object, or None.

    `FLExProject.Object(guid)` is a cache lookup, not a scan, so it is
    class-agnostic and O(1) -- which is why it is safe to use as the single
    primitive for every class the plan can name, where the category-scoped
    helpers below (`_find_target_pos_by_guid` and friends) each walk one
    collection and can only ever answer for their own category.

    Swallowing the exception is correct HERE and only here: "the GUID is not
    in this project" and "the GUID is malformed" are the same answer to the
    caller's question, and the caller (`resolve_planned_destination`) turns a
    None into a loud `PlannedDestinationError` that names the class, the GUID
    and the source object. Nothing is silently dropped.
    """
    try:
        return target.Object(guid_str)
    except Exception:  # noqa: BLE001 -- see docstring
        return None


def _resolved_class_name(obj) -> str:
    """The exact LCM class name of a resolved object, or "" when it has none."""
    concrete = _unwrap(obj)
    try:
        name = getattr(concrete, "ClassName", None)
    except Exception:  # noqa: BLE001 -- a proxy may raise on attribute access
        return ""
    return str(name) if name else ""


def _creation_policy(object_class: str, creation_licensed: bool):
    """`(may_create, why_not)` for a `MatchBasis.NONE` record. NOT a match.

    Two independent vetoes, both of which must pass:

    1. THE PLAN ITEM'S VERB. `creation_licensed` is True only for a
       `PlannedAction` -- the ADD verb IS the plan saying creation is allowed.
       A `PlannedOverwrite` (or an UPDATE/LINK/merge mode routed through one)
       is an instruction to write onto an object that already exists;
       creating from one would be the create-anyway defect with extra steps.

    2. THE ROSTER'S PER-CLASS RULE, read from
       `matcher.natural_key_binding_for(...).creates_on_miss`. This is a
       creation POLICY lookup, not matching logic: it decides whether a missed
       key may mint an object, never which object corresponds to which.
       `MoMorphType` is the one admitted class that sets it False -- FLEx
       treats the morph-types list as project-independent fixed content (all
       19 GUIDs byte-identical across the three projects measured), so minting
       one would add an object the canonical list does not contain.

    A class with NO binding is refused as well, and that is the honest reading
    of "never create when the record shows the key could not be computed": no
    binding means 038 binds no key function for the class, so no key was, or
    could have been, computed for it -- the record's NONE means "not keyed",
    not "keyed and missed".

    KNOWN RESIDUAL, stated rather than hidden. `MatchBasisRecord` cannot
    currently distinguish a key that RAN AND MISSED (FR-007 licenses a create)
    from a key that COULD NOT BE COMPUTED for this particular object -- an
    auto-generated rule label, a subclass mismatch, or no name in the scoped
    writing system (66 of 113 measured feature-based natural classes collide
    on an auto-generated label; 42 of 42 `Mbugwe LizzieHC practice` phonemes
    have no `en` name). `matcher._miss` builds an identical record for both,
    and the distinction lives on `MatchDecision.may_create`, which does not
    travel on the plan. That guarantee therefore rests on the PLAN BUILDER: a
    decision whose `may_create` is False must not become a `PlannedAction` at
    all. This function enforces the two vetoes it can see and does not pretend
    to enforce the third.
    """
    if not creation_licensed:
        return False, (
            "the plan item is not an ADD, so it carries no licence to create "
            "-- an OVERWRITE/UPDATE whose match_basis is NONE names no "
            "destination to write onto"
        )
    if __package__:
        from . import matcher as _matcher
    else:
        import matcher as _matcher  # type: ignore
    binding = _matcher.natural_key_binding_for(object_class)
    if binding is None:
        return False, (
            "no natural-key binding exists for object class "
            + repr(object_class) + ", so no key was computed for it and its "
            "NONE basis means 'not keyed' rather than 'keyed and missed'"
        )
    if not binding.creates_on_miss:
        return False, (
            "the roster forbids creating a " + repr(object_class)
            + " on a missed key (creates_on_miss=false): the list is "
            "project-independent fixed content, so minting one would add an "
            "object the canonical list does not contain"
        )
    return True, ""


def resolve_planned_destination(match_basis: Optional[MatchBasisRecord], target, *,
                                creation_licensed: bool,
                                resolve_fn=None) -> PlannedDestination:
    """THE resolve-or-create path. One function, four outcomes, no fallbacks.

    Parameters:
        match_basis:       the plan item's `MatchBasisRecord`, or None.
        target:            the destination project handle.
        creation_licensed: whether the CALLER's own plan verb permits a create
                           (see `_creation_policy`). Passed rather than
                           inferred so a create-site helper -- which is a
                           create by construction -- does not have to fake a
                           plan item to say so.
        resolve_fn:        injection hook for the GUID -> object primitive,
                           mirroring `matcher.resolve_match`'s existing
                           `key_fn=` convention. Production leaves it None.

    Raises:
        PlannedDestinationError: when the plan asserted a destination the
            target does not hold, or holds as a different class.

    Never scans and never keys. `MatchBasis.IDENTITY` and
    `MatchBasis.NATURAL_KEY` are handled IDENTICALLY on purpose: the plan
    already applied the ordering contract (identity first and authoritative;
    the key only when identity found nothing), and re-deciding it here is
    exactly the duplication that let the plan and the executor reach different
    answers.
    """
    if match_basis is None:
        # Pre-038. The caller keeps its own behaviour, bit-for-bit.
        return PlannedDestination(DESTINATION_UNDETERMINED)

    basis = getattr(match_basis, "basis", None)
    object_class = getattr(match_basis, "object_class", "") or ""
    source_guid = getattr(match_basis, "source_guid", "") or ""
    target_guid = getattr(match_basis, "target_guid", "") or ""

    if basis in (MatchBasis.IDENTITY, MatchBasis.NATURAL_KEY):
        # `MatchBasisRecord.__post_init__` already refuses a non-NONE basis
        # with an empty target_guid, so this can only fire for a record built
        # some other way. Checked anyway: an empty GUID reaching
        # `target.Object("")` would resolve to None and be reported as "the
        # destination is gone", which would send the operator hunting for a
        # data problem that is really a producer bug.
        if not target_guid:
            raise PlannedDestinationError(
                "plan match_basis for object class " + repr(object_class)
                + " (source " + repr(source_guid) + ") records basis "
                + str(getattr(basis, "value", basis)) + " but names no "
                "target_guid -- a matched basis without a destination GUID is "
                "not a match"
            )
        obj = (resolve_fn or _resolve_guid_in_target)(target, target_guid)
        if obj is None:
            raise PlannedDestinationError(
                "plan match_basis promised a destination "
                + repr(object_class) + " at GUID " + repr(target_guid)
                + " for source object " + repr(source_guid) + " (basis "
                + str(getattr(basis, "value", basis)) + "), but the target "
                "project does not hold it. The executor will NOT fall back to "
                "creating the object (that duplicates destination content "
                "under a second GUID) nor to skipping it (that discards the "
                "analysis). Re-run Preview against the current target."
            )
        resolved_class = _resolved_class_name(obj)
        if object_class and resolved_class and resolved_class != object_class:
            raise PlannedDestinationError(
                "plan match_basis named a " + repr(object_class) + " at GUID "
                + repr(target_guid) + " but the target holds a "
                + repr(resolved_class) + " there. `PhNCSegments` must never "
                "match `PhNCFeatures` and `LexEntryInflType` must never match "
                "`LexEntryType`, however identical their names -- writing "
                "source properties onto the wrong class is a corruption, not "
                "a mismatch to warn about."
            )
        return PlannedDestination(
            outcome=DESTINATION_RESOLVED,
            obj=obj,
            target_guid=target_guid,
            object_class=object_class,
            basis=basis,
        )

    if basis is MatchBasis.NONE:
        may_create, why_not = _creation_policy(object_class, creation_licensed)
        return PlannedDestination(
            outcome=DESTINATION_CREATE if may_create else DESTINATION_REPORT,
            target_guid="",
            object_class=object_class,
            basis=basis,
            detail="" if may_create else why_not,
        )

    raise PlannedDestinationError(
        "plan match_basis for object class " + repr(object_class)
        + " carries an unknown basis " + repr(basis) + "; the executor "
        "refuses to guess whether that means resolve or create"
    )


#: Categories whose actions have no one-object-per-GUID target counterpart
#: (a custom field is a schema entry keyed by (class, name), not an ICmObject).
_RECONCILE_EXEMPT = frozenset({GrammarCategory.CUSTOM_FIELDS})


_UNVERIFIABLE = object()


def _lookup_target_guid(target, guid):
    """Return the target object for `guid`, None if absent, or `_UNVERIFIABLE`
    when `target` offers no GUID lookup at all (offline fakes)."""
    getter = getattr(target, "get_object_by_guid", None)
    if callable(getter):
        return getter(guid)
    if not callable(getattr(target, "ObjectRepository", None)):
        return _UNVERIFIABLE
    from SIL.LCModel import ICmObjectRepository
    from System import Guid as _G
    repo = target.ObjectRepository(ICmObjectRepository)
    parsed = _G.Parse(str(guid))
    return repo.GetObject(parsed) if repo.IsValidObjectId(parsed) else None


def reconcile_added_actions(target, candidates, *, resolve=None,
                            identity_remap=None, unverified=None):
    """Post-execute truth pass (issue #49).

    `candidates` is an iterable of ``(action, expected_target_guid)`` for every
    action whose handler reported it written. When `expected_target_guid` is
    falsy (no planned destination), the expected GUID is
    ``identity_remap.get(source_guid, source_guid)`` -- a handler that created
    under a remapped GUID counts as landed. Returns a list of
    ``(category, source_guid, reason)`` for each one whose object is NOT
    present in the target by GUID, so the caller can downgrade it from added to
    failed. Pure read: one dictionary-backed repository lookup per action.

    A lookup that RAISES is not proof of absence, but it is not verification
    either: it is logged at WARNING and, when the caller passes a list as
    `unverified`, appended there as ``(category, source_guid, reason)`` so the
    run report can show the action as unverified rather than verified-added.
    `resolve(target, guid)` defaults to `_lookup_target_guid`.
    """
    if resolve is None:
        resolve = _lookup_target_guid
    remap = identity_remap or {}
    missing = []
    for action, guid in candidates:
        cat = getattr(action, "category", None)
        if not guid:
            src = getattr(action, "source_guid", None)
            guid = remap.get(src, src) if src else None
        if cat in _RECONCILE_EXEMPT or not guid:
            continue
        try:
            found = resolve(target, guid)
        except Exception as exc:  # noqa: BLE001 -- a lookup error is not proof of absence
            src = getattr(action, "source_guid", guid)
            _log.warning(
                "execute reconcile: lookup of %s %s FAILED (%s: %s); the "
                "write is UNVERIFIED", getattr(cat, "value", cat), guid,
                type(exc).__name__, exc)
            if unverified is not None:
                unverified.append((
                    cat, src,
                    "target lookup for %s raised %s: %s; write could not be "
                    "verified" % (guid, type(exc).__name__, exc)))
            continue
        if found is _UNVERIFIABLE:
            continue
        if found is None:
            missing.append((
                cat, getattr(action, "source_guid", guid),
                "reported added but object %s not found in the target after "
                "execute" % guid,
            ))
    return missing


def planned_destination_for(plan_item, target, *,
                            resolve_fn=None) -> PlannedDestination:
    """`resolve_planned_destination` for a whole plan item -- the front door.

    Reads the item's own `match_basis` and derives the creation licence from
    its VERB: only a `PlannedAction` (ADD) carries one. Every other plan item
    -- `PlannedOverwrite`, and the UPDATE/LINK/merge modes routed through it
    -- names an object that already exists, so a create from one would be the
    create-anyway defect.

    `getattr` rather than attribute access because `plan.actions` is
    heterogeneous: `CreateDefinitionAction` is a schema-level MDC write with
    no `match_basis` at all (the same reason `execute()` reads `pulled_in_by`
    defensively), and a schema action must degrade to pre-038 behaviour rather
    than raise.
    """
    return resolve_planned_destination(
        getattr(plan_item, "match_basis", None),
        target,
        creation_licensed=isinstance(plan_item, PlannedAction),
        resolve_fn=resolve_fn,
    )


# ============================================================================
# Per-layer create helpers (extracted verbatim from the pre-T-Spike monolith
# so the parity rubric in tasks.md T-Spike step 3 passes byte-for-byte on
# created objects)
# ============================================================================

def _idempotency_guard(target, src_guid: str, expected_classname: str, report_sink,
                       *, match_basis=None):
    """Idempotency guard: check if an object with `src_guid` already exists.

    Called at EVERY Guid-preserving Create site BEFORE factory.Create(guid, ...).
    LCM factory.Create(existingGuid, owner) does NOT throw -- it silently creates
    a duplicate object permanently written to .fwdata on CloseProject. This guard
    prevents that corruption.

    Returns:
        (True, existing_obj) if a same-class object was found -- caller should
            return existing_obj immediately without calling Create.
        (True, None) if a WRONG-class object was found -- caller should return
            None and skip Create entirely (log WARNING).
        (False, None) if no object exists for that GUID -- proceed with Create.

    Feature 038 T036 -- `match_basis`, and why the guard alone was never enough.
    ---------------------------------------------------------------------------
    The GUID probe below asks `target.Object(SOURCE guid)`. That question can
    only ever discover an IDENTITY match, so it is blind to precisely the case
    038 exists to fix: the destination already holds this object under a
    DIFFERENT GUID because FLEx created it as starter content, and the plan
    matched it by a roster-admitted natural key. The guard answers "no such
    object", the caller Creates, and the project ends up with two `Verb`s.

    Passing the plan item's `MatchBasisRecord` turns this into the single
    resolve-or-create path: the plan's decision is consulted FIRST and, when it
    named a destination, that object is returned and no Create happens --
    whatever GUID it carries. The guard adds no matching logic of its own; it
    only resolves the GUID the plan already chose.

    `match_basis=None` (every production call site as of T036, since no planner
    attaches a record yet) skips the whole block and leaves the pre-038 probe
    bit-for-bit unchanged.
    """
    dest = resolve_planned_destination(
        match_basis, target,
        # A create-helper call site is a create by construction: it was reached
        # because the plan asked for this object to be added. The roster's
        # per-class `creates_on_miss` veto still applies inside.
        creation_licensed=True,
    )
    if dest.resolved:
        resolved_class = _resolved_class_name(dest.obj)
        if not resolved_class or resolved_class == expected_classname:
            return (True, dest.obj)
        # `resolve_planned_destination` already rejects a class that
        # contradicts the RECORD; this catches a record whose class is right
        # but does not match what THIS create helper builds -- a wiring bug in
        # the caller, not a data condition. Reported and skipped rather than
        # created, because creating here would duplicate the object the plan
        # just resolved.
        report_sink.Warning(
            f"  [038 T036] plan resolved {dest.object_class or '?'} "
            f"{dest.target_guid[:8]}... for source {src_guid[:8]}..., but this "
            f"create site builds {expected_classname!r} (target holds "
            f"{resolved_class!r}); skipping Create to avoid duplicating it"
        )
        return (True, None)
    if dest.outcome == DESTINATION_REPORT:
        # The plan found no destination AND creation is refused. Reported and
        # skipped -- never created, never silently dropped (FR-013).
        report_sink.Warning(
            f"  [038 T036] no destination for {dest.object_class or expected_classname} "
            f"{src_guid[:8]}... and creation is not permitted: {dest.detail}"
        )
        return (True, None)

    # DESTINATION_CREATE and DESTINATION_UNDETERMINED both fall through to the
    # pre-038 probe. The probe is still required for CREATE: it is the
    # anti-corruption guard against LCM's silent duplicate-GUID Create, which
    # is a different question from "did the plan find a counterpart".
    try:
        existing = target.Object(src_guid)
    except Exception:
        existing = None

    if existing is None:
        return (False, None)

    # Object exists. Check ClassName.
    try:
        classname = existing.ClassName
    except Exception:
        classname = None

    if classname == expected_classname:
        return (True, existing)

    # Wrong class -- log and skip without create.
    report_sink.Warning(
        f"  [IDEMPOTENCY] GUID {src_guid[:8]}... exists as {classname!r} "
        f"(expected {expected_classname!r}); skipping Create to avoid corruption"
    )
    return (True, None)


def _cast_existing_to_pos(obj):
    """Direct cast for PartOfSpeech (not in cast_to_concrete map)."""
    from SIL.LCModel import IPartOfSpeech
    return IPartOfSpeech(obj)


def _cast_existing_to_slot(obj):
    """Direct cast for MoInflAffixSlot (not in cast_to_concrete map)."""
    from SIL.LCModel import IMoInflAffixSlot
    return IMoInflAffixSlot(obj)


def _cast_existing_to_environment(obj):
    """Direct cast for PhEnvironment (not in cast_to_concrete map)."""
    from SIL.LCModel import IPhEnvironment
    return IPhEnvironment(obj)


def _cast_existing_to_template(obj):
    """cast_to_concrete maps MoInflAffixTemplate; use IMoInflAffixTemplate directly."""
    from SIL.LCModel import IMoInflAffixTemplate
    return IMoInflAffixTemplate(obj)


def _cast_existing_to_lexentry(obj):
    """cast_to_concrete maps LexEntry; use ILexEntry directly."""
    from SIL.LCModel import ILexEntry
    return ILexEntry(obj)


def _cast_existing_to_lexsense(obj):
    """cast_to_concrete maps LexSense; use ILexSense directly."""
    from SIL.LCModel import ILexSense
    return ILexSense(obj)


def _create_pos_with_guid(target, src_guid: str, src_props, tag: ImportResidueTag,
                          report_sink, *, match_basis=None):
    """Create a Part-of-Speech in the target with `src_guid` preserved.

    Idempotency guard (P0): if a PartOfSpeech with this GUID already exists,
    return it without calling Create (prevents LCM silent-duplicate corruption).

    `match_basis` (038 T036): the plan item's `MatchBasisRecord`, threaded
    straight to `_idempotency_guard` so a destination the plan matched by a
    roster-admitted NATURAL KEY -- i.e. under a GUID other than `src_guid` --
    is RESOLVED here instead of being duplicated by the Create below. None
    (the default, and every production caller today) leaves the pre-038
    guard-then-Create behaviour untouched.
    """
    from SIL.LCModel import IPartOfSpeechFactory, ICmPossibilityList
    from System import Guid as DotNetGuid

    found, existing = _idempotency_guard(target, src_guid, "PartOfSpeech", report_sink,
                                        match_basis=match_basis)
    if found:
        if existing is not None:
            report_sink.Info(f"  POS already exists (idempotency reuse)  guid={src_guid}")
            return _cast_existing_to_pos(existing)
        return None  # wrong-class object; skip

    factory = IPartOfSpeechFactory(target.GetFactory(IPartOfSpeechFactory))
    cache = getattr(target, "Cache")
    pos_list = ICmPossibilityList(cache.LangProject.PartsOfSpeechOA)
    new_pos = factory.Create(DotNetGuid.Parse(src_guid), pos_list)
    target.POS.ApplySyncableProperties(new_pos, src_props)
    apply_carrier_b(new_pos, cache.DefaultAnalWs, tag)
    report_sink.Info(f"  POS created  guid={src_guid}")
    return new_pos


def _create_template_with_guid(target, owner_pos, src_guid: str, src_props,
                               tag: ImportResidueTag, report_sink, *,
                               match_basis=None):
    """Create an Affix Template in the target owned by `owner_pos`.

    Idempotency guard (P0): if a MoInflAffixTemplate with this GUID already
    exists, return it without calling Create.

    `match_basis` (038 T036): the plan item's `MatchBasisRecord`, threaded
    straight to `_idempotency_guard` so a destination the plan matched by a
    roster-admitted NATURAL KEY -- i.e. under a GUID other than `src_guid` --
    is RESOLVED here instead of being duplicated by the Create below. None
    (the default, and every production caller today) leaves the pre-038
    guard-then-Create behaviour untouched.
    """
    from SIL.LCModel import IMoInflAffixTemplateFactory
    from System import Guid as DotNetGuid

    found, existing = _idempotency_guard(target, src_guid, "MoInflAffixTemplate", report_sink,
                                        match_basis=match_basis)
    if found:
        if existing is not None:
            report_sink.Info(f"  Template already exists (idempotency reuse)  guid={src_guid}")
            return _cast_existing_to_template(existing)
        return None  # wrong-class object; skip

    factory = IMoInflAffixTemplateFactory(target.GetFactory(IMoInflAffixTemplateFactory))
    new_template = factory.Create(DotNetGuid.Parse(src_guid))
    owner_pos.AffixTemplatesOS.Add(new_template)
    target.MorphRules.ApplySyncableProperties(new_template, src_props)
    cache = getattr(target, "Cache")
    apply_carrier_b(new_template, cache.DefaultAnalWs, tag)
    report_sink.Info(f"  Template created  guid={src_guid}")
    return new_template


def _create_slot_with_guid(target, owner_pos, src_guid: str, slot_name: str,
                           tag: ImportResidueTag, report_sink, *,
                           match_basis=None):
    """Create an Affix Slot in the target owned by `owner_pos`.

    Idempotency guard (P0): if a MoInflAffixSlot with this GUID already
    exists, return it without calling Create.

    `match_basis` (038 T036): the plan item's `MatchBasisRecord`, threaded
    straight to `_idempotency_guard` so a destination the plan matched by a
    roster-admitted NATURAL KEY -- i.e. under a GUID other than `src_guid` --
    is RESOLVED here instead of being duplicated by the Create below. None
    (the default, and every production caller today) leaves the pre-038
    guard-then-Create behaviour untouched.
    """
    from SIL.LCModel import IMoInflAffixSlotFactory, IMoInflAffixSlot
    from SIL.LCModel.Core.Text import TsStringUtils
    from System import Guid as DotNetGuid

    found, existing = _idempotency_guard(target, src_guid, "MoInflAffixSlot", report_sink,
                                        match_basis=match_basis)
    if found:
        if existing is not None:
            report_sink.Info(f"  Slot already exists (idempotency reuse)  guid={src_guid}")
            return _cast_existing_to_slot(existing)
        return None  # wrong-class object; skip

    factory = IMoInflAffixSlotFactory(target.GetFactory(IMoInflAffixSlotFactory))
    new_slot = factory.Create(DotNetGuid.Parse(src_guid))
    owner_pos.AffixSlotsOC.Add(new_slot)
    cache = getattr(target, "Cache")
    ws = cache.DefaultAnalWs
    IMoInflAffixSlot(new_slot).Name.set_String(ws, TsStringUtils.MakeString(slot_name, ws))
    apply_carrier_b(new_slot, ws, tag)
    report_sink.Info(f"  Slot {slot_name!r} created  guid={src_guid}")
    return new_slot


# ============================================================================
# Source/target lookups + utilities
# ============================================================================

def _filter(actions, category: GrammarCategory) -> Iterable[PlannedAction]:
    return (a for a in actions if a.category == category)


def _apply_merge_decisions(src_props, decisions, tgt_pre_props, run_id, category, target_guid):
    """Phase 2 (FR-202..205) -- filter `src_props` per user resolutions.

    Per research.md R3, decisions are applied as a dict-filter pass that
    mirrors `_dedupe_custom_fields`:

    - TAKE_SOURCE: leave src_props[k] unchanged (Phase 1 default).
    - KEEP_TARGET: drop src_props[k] entirely (target's value survives).
    - MERGE: replace src_props[k] with _deterministic_merge(tgt, src).
      On scalar values (_MergeNotEligible), fall back to TAKE_SOURCE +
      log a warning via the returned Skip-but-not-really mechanism
      (caller renders it via report_sink).
    - SKIP: drop src_props[k] AND emit Skip(INTERACTIVE_SKIP).
    - EDIT_CUSTOM: replace src_props[k] with decision.custom_value.

    Args:
        src_props: dict of source's syncable properties.
        decisions: iterable of MergeDecision.
        tgt_pre_props: dict of target's pre-overwrite values.
        run_id: GT-YYYYMMDD-HHMMSS for the merge separator.
        category: GrammarCategory for any Skip records emitted.
        target_guid: target object's GUID for Skip records.

    Returns:
        (filtered_src_props, skip_records: list[Skip])
    """
    if not isinstance(src_props, dict):
        return src_props, []
    out = dict(src_props)
    skips = []
    for d in decisions:
        k = d.field_name
        if d.resolution == MergeResolution.TAKE_SOURCE:
            continue  # default; src_props[k] already wins
        if d.resolution == MergeResolution.KEEP_TARGET:
            out.pop(k, None)
            continue
        if d.resolution == MergeResolution.MERGE:
            left = tgt_pre_props.get(k) if isinstance(tgt_pre_props, dict) else None
            right = out.get(k)
            try:
                out[k] = _deterministic_merge(left, right, run_id)
            except _MergeNotEligible:
                # Scalar -- silently fall back to TAKE_SOURCE per R4.
                pass
            continue
        if d.resolution == MergeResolution.SKIP:
            out.pop(k, None)
            skips.append(Skip(
                category=category,
                source_guid=target_guid,
                reason=SkipReason.INTERACTIVE_SKIP,
                detail=f"User skipped field {k!r} on {target_guid[:8]}",
            ))
            continue
        if d.resolution == MergeResolution.EDIT_CUSTOM:
            out[k] = d.custom_value
            continue
    return out, skips


def _dedupe_custom_fields(src_props, tgt_pre_props):
    """FR-107: drop custom-field keys from `src_props` whose value already
    matches the target's pre-overwrite value.  Keys not in `tgt_pre_props`
    are left in `src_props` (overwrite path).  Keys present in
    `tgt_pre_props` but not in `src_props` are preserved by virtue of
    ApplySyncableProperties only touching keys it receives.

    Custom fields are identified by name prefix "Custom" (flexicon emits
    them as "Custom_<FieldName>" in the syncable props dict).  Non-custom
    properties pass through unchanged so FR-109 (source wins) still applies.

    Returns a new dict; does not mutate inputs.
    """
    if not isinstance(src_props, dict) or not isinstance(tgt_pre_props, dict):
        return src_props
    out = {}
    for k, v in src_props.items():
        if str(k).startswith("Custom") and k in tgt_pre_props and tgt_pre_props[k] == v:
            continue  # identical custom field -- skip the no-op write
        out[k] = v
    return out


def _first_pos_guid(plan: RunPlan):
    for a in plan.actions:
        if a.category == GrammarCategory.POS:
            return a.source_guid
    for s in plan.skips:
        if s.category == GrammarCategory.POS:
            return s.source_guid
    return None


def _first_template_guid(plan: RunPlan):
    for a in plan.actions:
        if a.category == GrammarCategory.AFFIX_TEMPLATES:
            return a.source_guid
    for s in plan.skips:
        if s.category == GrammarCategory.AFFIX_TEMPLATES:
            return s.source_guid
    return None


def _find_source_pos_by_guid(source, guid_str: str):
    for pos in source.POS.GetAll(recursive=True):
        concrete = _unwrap(pos)
        if _guid_str(concrete) == guid_str:
            return concrete
    return None


def _find_source_template_by_guid(source, guid_str: str, owner_pos_guid: str = None):
    """Returns the flexicon template *wrapper* (we need its prefix_slots etc.),
    not the bare LCM object. If `owner_pos_guid` is given, only searches
    that POS's templates; otherwise scans every POS."""
    candidate_poses = []
    if owner_pos_guid is not None:
        p = _find_source_pos_by_guid(source, owner_pos_guid)
        if p is not None:
            candidate_poses.append(p)
    else:
        for pos in source.POS.GetAll(recursive=True):
            candidate_poses.append(_unwrap(pos))
    for src_pos in candidate_poses:
        for t in source.MorphRules.GetAllAffixTemplatesForPOS(src_pos):
            concrete = t.concrete
            if _guid_str(concrete) == guid_str:
                return t
    return None


def _find_source_first_template_for_pos(source, owner_pos_guid: str):
    """First template under the given source POS, as flexicon wrapper."""
    src_pos = _find_source_pos_by_guid(source, owner_pos_guid)
    if src_pos is None:
        return None
    for t in source.MorphRules.GetAllAffixTemplatesForPOS(src_pos):
        return t
    return None


def _find_target_pos_by_guid(target, guid_str: str):
    """Identity only: the destination category whose GUID *is* `guid_str`.

    T106: this is the right question ONLY when the caller already holds a
    DESTINATION GUID -- a plan item's `target_guid`, or a GUID this run just
    created in the destination. Six callers reach it and they do not agree:
    one passes `overwrite.target_guid` (correct, and routing it through the
    natural key would re-derive a decision Preview already recorded), five
    pass a SOURCE GUID and want `_target_pos_for_source_guid` instead. The
    split is deliberate and is pinned in
    `tests/unit/test_038_t106_target_pos_finder_provenance.py`.
    """
    for pos in target.POS.GetAll(recursive=True):
        concrete = _unwrap(pos)
        if _guid_str(concrete) == guid_str:
            return _cast_pos(concrete)
    return None


def _target_pos_for_source_guid(target, src_pos_guid: str, *, src_pos=None,
                                source_handle=None):
    """The destination category a SOURCE category GUID names -- identity
    first, roster-admitted natural key second (T106, T095's shape one module
    out).

    THE INVARIANT THIS REPLACES is the one T091 ended: "a category's
    destination GUID is its source GUID". Once the planner REUSES a same-named
    destination category instead of duplicating it, a source category can be
    present in the destination under a different GUID, and
    `_find_target_pos_by_guid` reads that as absent.

    `src_pos` and `source_handle` are keyword-only and both default to None,
    mirroring `_resolve_target_pos`'s own opt-in shape, so a caller (or a unit
    fake) that passes neither gets exactly the pre-038 identity answer. The
    natural key needs BOTH -- the key is the category's `Name`, which a GUID
    string cannot supply, and `source_handle` supplies the source writing-system
    handles the key is scoped to -- so a site that can reach only one of them
    gains nothing and should say so rather than look fixed.

    Lazy import for the same load-order reason every other `-> categories.py`
    call in this package documents (`owned._resolve_target_pos_by_guid`).
    """
    if not src_pos_guid:
        return None
    try:
        if __package__:
            from . import categories as _categories
        else:
            import categories as _categories  # type: ignore
    except ImportError:  # pragma: no cover -- categories.py is always present
        return _find_target_pos_by_guid(target, src_pos_guid)
    return _categories._resolve_target_pos(
        target, src_pos_guid, src_pos=src_pos, source_handle=source_handle)


def _find_target_template_by_guid(target, target_pos, guid_str: str):
    for t in target.MorphRules.GetAllAffixTemplatesForPOS(target_pos):
        concrete = _unwrap(t)
        if _guid_str(concrete) == guid_str:
            return concrete
    return None


def _find_target_slot_by_guid(target, target_pos, guid_str: str):
    for s in target.POS.GetAffixSlots(target_pos):
        concrete = _unwrap(s)
        if _guid_str(concrete) == guid_str:
            return concrete
    return None


def _cast_pos(obj):
    from SIL.LCModel import IPartOfSpeech
    return IPartOfSpeech(obj)


def _cast_template(obj):
    from SIL.LCModel import IMoInflAffixTemplate
    return IMoInflAffixTemplate(obj)


def _guid_str(obj) -> str:
    from SIL.LCModel import ICmObject
    return str(ICmObject(obj).Guid).lower()


def _unwrap(obj):
    return obj.concrete if hasattr(obj, "concrete") else obj


def _slot_name(slot) -> str:
    from SIL.LCModel import IMoInflAffixSlot
    txt = IMoInflAffixSlot(_unwrap(slot)).Name.BestAnalysisAlternative.Text
    # "***" is FLEx's empty-alternative sentinel; never write it as a real Name.
    return "" if txt in (None, "***") else txt


def _ref_seq_contains(ref_seq, obj) -> bool:
    from SIL.LCModel import ICmObject
    obj_guid = str(ICmObject(obj).Guid).lower()
    for i in range(ref_seq.Count):
        if str(ICmObject(ref_seq.get_Item(i)).Guid).lower() == obj_guid:
            return True
    return False


# ============================================================================
# Layer 3 executor — LexEntry / Sense / MSA / Allomorph / PhEnvironment
# ============================================================================

def _execute_layer3(
    plan: RunPlan,
    source,
    target,
    report_sink,
    tag: ImportResidueTag,
    src_pos_guid: str = None,
) -> None:
    """Apply ENTRY / SENSE / MSA / ALLOMORPH / PH_ENVIRONMENT actions for the
    verb closure. Mirrors STATUS.md Layer 3 outline:

      ILexEntryFactory.Create(Guid, ILexDb)      → entry, owned by LexDb
      ILexSenseFactory.Create(Guid, ILexEntry)   → sense, owned by entry
      IMoInflAffMsaFactory.Create(Guid)          → MSA;
                                                    entry.MorphoSyntaxAnalysesOC.Add(msa);
                                                    sense.MorphoSyntaxAnalysisRA = msa
      IMoAffixAllomorphFactory.Create(Guid)      → allomorph; entry.LexemeFormOA OR
                                                    entry.AlternateFormsOS.Add(...)
      IPhEnvironmentFactory.Create(Guid)         → env;
                                                    LangProject.PhonologicalDataOA
                                                       .EnvironmentsOS.Add(env)

    Residue: Carrier A (LiftResidue) on Lex*, MoForm, MoMorphSynAnalysis;
    Carrier B (Description-append) on PhEnvironment.
    """
    # Quick exits.
    layer3_cats = (
        GrammarCategory.ENTRY,
        GrammarCategory.SENSE,
        GrammarCategory.MSA,
        GrammarCategory.ALLOMORPH,
        GrammarCategory.PH_ENVIRONMENT,
    )
    has_layer3 = (
        any(a.category in layer3_cats for a in plan.actions)
        or any(o.category in layer3_cats for o in getattr(plan, "overwrites", ()))
    )
    if not has_layer3:
        return

    identity_remap = dict(plan.identity_remap) if plan.identity_remap else {}

    # Locate the source POS we're executing Layer 3 for. Caller supplies
    # `src_pos_guid`; for the backward-compat path (no arg), fall back to
    # the first POS GUID in the plan.
    if src_pos_guid is None:
        src_pos_guid = _first_pos_guid(plan)
    if src_pos_guid is None:
        report_sink.Warning("[L3] No POS in plan; skipping Layer 3.")
        return
    src_verb = _find_source_pos_by_guid(source, src_pos_guid)
    if src_verb is None:
        report_sink.Warning(f"[L3] Source POS {src_pos_guid[:8]}… not found; skipping Layer 3.")
        return
    src_verb_guid = src_pos_guid
    # T106: `src_verb` was just resolved OUT OF THE SOURCE one line above, so
    # this GUID is unambiguously source-side. Carrying the object to the
    # resolver rather than discarding it is T094's `_pos_guid_of` finding.
    target_verb = _target_pos_for_source_guid(
        target, src_verb_guid, src_pos=src_verb, source_handle=source)
    if target_verb is None:
        report_sink.Warning(f"[L3] Target POS {src_pos_guid[:8]}… not present; Layer 3 needs Layer 1 first.")
        return

    # Pre-create environments (allomorphs reference them). Skipped
    # PH_ENVIRONMENTs are already in target — look them up so the allomorph
    # PhoneEnvRC wiring step can resolve them.
    env_guid_to_target = {}
    for action in _filter(plan.actions, GrammarCategory.PH_ENVIRONMENT):
        new_env = _create_environment_with_guid(
            target, action.source_guid, report_sink, tag,
            match_basis=getattr(action, "match_basis", None),  # 038 T036
        )
        env_guid_to_target[action.source_guid] = new_env
    for skip in plan.skips:
        if skip.category != GrammarCategory.PH_ENVIRONMENT:
            continue
        existing = _find_target_env_by_guid(target, skip.source_guid)
        if existing is not None:
            env_guid_to_target[skip.source_guid] = existing
            report_sink.Info(f"  PhEnvironment reused (already in target)  guid={skip.source_guid}")
    for ow in getattr(plan, "overwrites", ()):
        if ow.category != GrammarCategory.PH_ENVIRONMENT:
            continue
        existing = _find_target_env_by_guid(target, ow.target_guid)
        if existing is not None:
            env_guid_to_target[ow.source_guid] = existing

    # Map source slot GUIDs to target slot objects (Layer 2 created them).
    target_slot_by_guid = {}
    for s in target.POS.GetAffixSlots(target_verb):
        target_slot_by_guid[_guid_str(s)] = s

    # Group entry-related actions by entry_guid (sense + msa + allomorph
    # actions reference their entry through pulled_in_by).
    entry_actions = list(_filter(plan.actions, GrammarCategory.ENTRY))
    entry_action_guids = [a.source_guid for a in entry_actions]
    # 038 T036: the plan's match decision, keyed by the same source GUID the
    # loop below walks. Empty for every plan built today, which is what makes
    # the `.get()` below a no-op rather than a behaviour change.
    entry_match_basis = {
        a.source_guid: getattr(a, "match_basis", None) for a in entry_actions
    }

    # Index source entries by GUID for quick lookup.
    src_entry_by_guid = {}
    for entry in source.LexEntry.GetAll():
        src_entry_by_guid[_guid_str(entry)] = entry

    for entry_guid in entry_action_guids:
        src_entry = src_entry_by_guid.get(entry_guid)
        if src_entry is None:
            report_sink.Warning(f"[L3] Source entry {entry_guid[:8]} vanished")
            continue

        # 1. Create LexEntry.
        new_entry = _create_lexentry_with_guid(
            target, entry_guid, src_entry, source, tag, report_sink,
            match_basis=entry_match_basis.get(entry_guid),
        )

        _populate_entry_children(
            new_entry, src_entry, identity_remap, source, target,
            target_verb, target_slot_by_guid, env_guid_to_target, tag, report_sink,
        )

    # T-FR008: process identity-remap ENTRY overwrites here (inside _execute_layer3)
    # where identity_remap, target_verb, target_slot_by_guid, and env_guid_to_target
    # are in scope. These must NOT be re-processed by the main execute() loop.
    for ow in getattr(plan, "overwrites", ()):
        if not (ow.category in (GrammarCategory.ENTRY, GrammarCategory.AFFIXES, GrammarCategory.STEMS)
                and getattr(ow, "match_via", "guid") == "identity_remap"):
            continue
        _execute_overwrite_identity_remap(
            ow, source, target, report_sink, tag,
            identity_remap, target_verb, target_slot_by_guid, env_guid_to_target,
        )


def _execute_overwrite_identity_remap(
    overwrite,
    source,
    target,
    report_sink,
    tag,
    identity_remap: dict,
    target_verb,
    target_slot_by_guid: dict,
    env_guid_to_target: dict,
) -> None:
    """Execute an identity-remap ENTRY overwrite: apply source fields onto the
    resolved target entry (fill-gaps or overwrite per write_mode), then
    populate children under it."""
    from SIL.LCModel import ICmObject
    src_guid = (overwrite.source_guid or "").lower()
    tgt_guid = (overwrite.target_guid or "").lower()
    fill_gaps = (getattr(overwrite, "write_mode", "overwrite") == "merge")

    # Locate target entry.
    tgt_entry = None
    for te in target.LexEntry.GetAll():
        if str(ICmObject(_unwrap(te)).Guid).lower() == tgt_guid:
            tgt_entry = _unwrap(te)
            break
    if tgt_entry is None:
        report_sink.Warning(f"  [OW/IR] LexEntry {tgt_guid[:8]} not in target")
        return

    # Locate source entry.
    src_entry = None
    for se in source.LexEntry.GetAll():
        if str(ICmObject(_unwrap(se)).Guid).lower() == src_guid:
            src_entry = _unwrap(se)
            break
    if src_entry is None:
        report_sink.Warning(f"  [OW/IR] Source LexEntry {src_guid[:8]} vanished")
        return

    tgt_pre_props = strip_residue_props(target.LexEntry.GetSyncableProperties(tgt_entry))
    src_props = _dedupe_custom_fields(
        source.LexEntry.GetSyncableProperties(src_entry), tgt_pre_props
    )
    target.LexEntry.ApplySyncableProperties(
        tgt_entry, src_props,
        fill_gaps=fill_gaps,
    )
    cache = getattr(target, "Cache")
    apply_residue(tgt_entry, cache.DefaultAnalWs, tag.with_snapshot(tgt_pre_props))
    report_sink.Info(f"  LexEntry identity-remap overwritten  guid={src_guid}")

    # Populate children (senses, MSAs, allomorphs) under the resolved target entry.
    _populate_entry_children(
        tgt_entry, src_entry, identity_remap, source, target,
        target_verb, target_slot_by_guid, env_guid_to_target, tag, report_sink,
    )


def _populate_entry_children(
    new_entry,
    src_entry,
    identity_remap: dict,
    source,
    target,
    target_verb,
    target_slot_by_guid: dict,
    env_guid_to_target: dict,
    tag,
    report_sink,
) -> None:
    """Create senses + MSAs + allomorphs + environment wiring under new_entry
    from src_entry.

    Called from two sites:
    - Normal add path in _execute_layer3 (source GUID == target GUID).
    - Merge-into (identity-remap) path in _execute_overwrite (T-FR008), where
      new_entry is an existing target entry resolved via similar_resolution.
    """
    # Derive verb GUID from the target_verb object (GUID-preserved; same as source).
    src_verb_guid = _guid_str(target_verb) if target_verb is not None else ""

    # 2. Create senses + MSAs in source order.
    for sense in source.LexEntry.GetSenses(src_entry):
        sense_guid = _guid_str(sense)
        new_sense = _create_lexsense_with_guid(target, new_entry, sense_guid, sense, source, tag, report_sink)
        msa = _lex_sense_msa(sense)
        if msa is None:
            continue
        if _classname_of(msa) != "MoInflAffMsa":
            continue
        if not _msa_points_at_verb(msa, src_verb_guid):
            continue
        msa_guid = _guid_str(msa)
        _create_inflaff_msa_with_guid(
            target, new_entry, new_sense, msa_guid, msa, target_verb, target_slot_by_guid,
            tag, report_sink, identity_remap,
        )

    # 3. Create allomorphs + wire to environments. Allomorphs.GetAll
    # may yield wrapper objects; unwrap before LCM casts.
    for allo in source.Allomorphs.GetAll(src_entry):
        allo_obj = _unwrap(allo)
        allo_guid = _guid_str(allo_obj)
        _create_allomorph_with_guid(
            target, new_entry, allo_guid, allo_obj, source, env_guid_to_target,
            tag, report_sink, identity_remap,
        )


def _find_target_morph_type_by_guid(target, morph_type_guid: str):
    """LCM morph types live under LangProject.LexDbOA.MorphTypesOA (a
    CmPossibilityList). Same GUIDs across all FW projects; just look up by
    GUID."""
    from SIL.LCModel import ICmObject
    try:
        cache = getattr(target, "Cache")
        lex_db = cache.LangProject.LexDbOA
        morph_types_list = lex_db.MorphTypesOA
        for mt in morph_types_list.PossibilitiesOS:
            if str(ICmObject(mt).Guid).lower() == morph_type_guid:
                return mt
    except Exception:
        return None
    return None


def _find_target_env_by_guid(target, env_guid: str):
    """Lookup helper used when a PhEnvironment was Skip-by-GUID."""
    from SIL.LCModel import ICmObject
    try:
        envs = target.Environments.GetAll()
    except AttributeError:
        return None
    for e in envs:
        concrete = e.concrete if hasattr(e, "concrete") else e
        if str(ICmObject(concrete).Guid).lower() == env_guid:
            return concrete
    return None


def _create_environment_with_guid(target, src_guid: str, report_sink,
                                  tag: ImportResidueTag, *, match_basis=None):
    """Create IPhEnvironment in target's PhonologicalData with GUID preserved.

    Idempotency guard (P0): if a PhEnvironment with this GUID already exists,
    return it without calling Create.

    `match_basis` (038 T036): the plan item's `MatchBasisRecord`, threaded
    straight to `_idempotency_guard` so a destination the plan matched by a
    roster-admitted NATURAL KEY -- i.e. under a GUID other than `src_guid` --
    is RESOLVED here instead of being duplicated by the Create below. None
    (the default, and every production caller today) leaves the pre-038
    guard-then-Create behaviour untouched.
    """
    from SIL.LCModel import IPhEnvironmentFactory, IPhEnvironment
    from System import Guid as DotNetGuid

    found, existing = _idempotency_guard(target, src_guid, "PhEnvironment", report_sink,
                                        match_basis=match_basis)
    if found:
        if existing is not None:
            report_sink.Info(f"  PhEnvironment already exists (idempotency reuse)  guid={src_guid}")
            return _cast_existing_to_environment(existing)
        return None  # wrong-class object; skip

    factory = IPhEnvironmentFactory(target.GetFactory(IPhEnvironmentFactory))
    new_env = factory.Create(DotNetGuid.Parse(src_guid))
    cache = getattr(target, "Cache")
    cache.LangProject.PhonologicalDataOA.EnvironmentsOS.Add(new_env)
    # Carrier B residue (PhEnvironment has Description).
    ws = cache.DefaultAnalWs
    apply_carrier_b(new_env, ws, tag)
    report_sink.Info(f"  PhEnvironment created  guid={src_guid}")
    return new_env


def _create_lexentry_with_guid(target, src_guid: str, src_entry, source,
                               tag: ImportResidueTag, report_sink, *,
                               match_basis=None):
    """Create ILexEntry owned by target.LexDb with GUID preserved + apply
    syncable string properties.

    Idempotency guard (P0): if a LexEntry with this GUID already exists,
    return it without calling Create.

    `match_basis` (038 T036): the plan item's `MatchBasisRecord`, threaded
    straight to `_idempotency_guard` so a destination the plan matched by a
    roster-admitted NATURAL KEY -- i.e. under a GUID other than `src_guid` --
    is RESOLVED here instead of being duplicated by the Create below. None
    (the default, and every production caller today) leaves the pre-038
    guard-then-Create behaviour untouched.
    """
    from SIL.LCModel import ILexEntryFactory, ILexDb
    from System import Guid as DotNetGuid

    found, existing = _idempotency_guard(target, src_guid, "LexEntry", report_sink,
                                        match_basis=match_basis)
    if found:
        if existing is not None:
            report_sink.Info(f"  LexEntry already exists (idempotency reuse)  guid={src_guid}")
            return _cast_existing_to_lexentry(existing)
        return None  # wrong-class object; skip

    factory = ILexEntryFactory(target.GetFactory(ILexEntryFactory))
    cache = getattr(target, "Cache")
    lex_db = ILexDb(cache.LangProject.LexDbOA)
    new_entry = factory.Create(DotNetGuid.Parse(src_guid), lex_db)
    src_props = source.LexEntry.GetSyncableProperties(src_entry)
    target.LexEntry.ApplySyncableProperties(new_entry, src_props)
    apply_residue(new_entry, cache.DefaultAnalWs, tag)
    report_sink.Info(f"  LexEntry created  guid={src_guid}")
    return new_entry


def _create_lexsense_with_guid(target, new_entry, src_guid: str, src_sense, source, tag: ImportResidueTag, report_sink):
    """Create ILexSense owned by new_entry with GUID preserved.

    Idempotency guard (P0): if a LexSense with this GUID already exists,
    return it without calling Create.
    """
    from SIL.LCModel import ILexSenseFactory, ICmObject
    from System import Guid as DotNetGuid

    found, existing = _idempotency_guard(target, src_guid, "LexSense", report_sink)
    if found:
        if existing is not None:
            report_sink.Info(f"  LexSense already exists (idempotency reuse)  guid={src_guid}")
            return _cast_existing_to_lexsense(existing)
        return None  # wrong-class object; skip

    factory = ILexSenseFactory(target.GetFactory(ILexSenseFactory))
    new_sense = factory.Create(DotNetGuid.Parse(src_guid), new_entry)
    cache = ICmObject(new_entry).Cache
    src_props = source.Senses.GetSyncableProperties(src_sense)
    target.Senses.ApplySyncableProperties(new_sense, src_props)
    apply_residue(new_sense, cache.DefaultAnalWs, tag)
    report_sink.Info(f"  LexSense created  guid={src_guid}")
    return new_sense


def _create_inflaff_msa_null_tolerant(target, new_sense, target_verb, slot_objs, report_sink):
    """Null-tolerant IMoInflAffMsa creation.

    flexicon's MSAOperations.CreateInflAff calls _ValidateParam(pos, "pos") and
    REJECTS a None POS at the Python wrapper layer.  When `target_verb` is None
    (EXCLUDED-LOSSY: user deliberately dropped the POS dependency), we must
    bypass the wrapper and call the raw LCM factory directly, then clear
    PartOfSpeechRA = None post-creation.

    Strategy: call the factory's Create(ILexEntry, SandboxGenericMSA) with a
    SandboxGenericMSA that has a dummy sentinel POS, then immediately clear
    PartOfSpeechRA on the resulting object.  If the sentinel approach is
    unavailable (older LCM), fall back to a zero-field SandboxGenericMSA.
    """
    from SIL.LCModel import IMoInflAffMsaFactory, IMoInflAffMsa, ILexEntry
    from SIL.LCModel.DomainServices import SandboxGenericMSA, MsaType

    factory = IMoInflAffMsaFactory(target.GetFactory(IMoInflAffMsaFactory))
    sgm = SandboxGenericMSA()
    sgm.MsaType = MsaType.kInfl
    # Leave sgm.MainPOS unset (None) — CreateInflAff won't be called (it
    # validates pos != None); instead call the raw factory directly.
    # ILexEntry.MorphoSyntaxAnalysesOC is the owning OC.
    entry_ie = ILexEntry(new_sense.OwnerOfClass(ILexEntry.kClassId)
                         if hasattr(new_sense, "OwnerOfClass")
                         else target)
    try:
        new_msa = factory.Create(entry_ie, sgm)
    except Exception:
        # Last-resort: create with a real pos, then clear it post-creation.
        # This path requires a sentinel POS exists in target.  If none found,
        # give up and return None.
        report_sink.Warning(
            "  [EXCL-LOSSY] Null-POS MSA creation via raw factory failed; MSA skipped"
        )
        return None
    # Clear PartOfSpeechRA to honor the EXCLUDED-LOSSY intent (null POS).
    try:
        IMoInflAffMsa(new_msa).PartOfSpeechRA = None
    except Exception:
        pass  # LCM may refuse — leave whatever default it set.
    # Wire slots.
    new_ia = IMoInflAffMsa(new_msa)
    for slot_obj in slot_objs:
        try:
            new_ia.SlotsRC.Add(slot_obj)
        except Exception:
            pass
    return new_msa


def _create_inflaff_msa_with_guid(target, new_entry, new_sense, src_guid: str, src_msa,
                                    target_verb, target_slot_by_guid,
                                    tag: ImportResidueTag, report_sink,
                                    identity_remap: dict):
    """Create IMoInflAffMsa via flexicon's MSAOperations.CreateInflAff (which
    handles the LibLCM SandboxGenericMSA dance internally).

    LCM's IMoInflAffMsaFactory only exposes `Create(ILexEntry, SandboxGenericMSA)`
    — no Guid overload — so MSA GUIDs cannot be preserved. The new GUID is
    recorded in `identity_remap[src_guid] = new_guid` per FR-012.

    NULL-TOLERANT PATH (EXCLUDED-LOSSY): when `target_verb` is None (user
    deliberately dropped the POS dependency), `_create_inflaff_msa_null_tolerant`
    is called instead of the normal flexicon wrapper.  The resulting MSA has a
    null PartOfSpeechRA, as the user was warned about at Preview time.
    """
    from SIL.LCModel import IMoInflAffMsa, ICmObject

    src_slot_objs = []
    src_ia = IMoInflAffMsa(src_msa)
    for src_slot in src_ia.SlotsRC:
        src_slot_guid = str(ICmObject(src_slot).Guid).lower()
        tgt_slot = target_slot_by_guid.get(src_slot_guid)
        if tgt_slot is not None:
            src_slot_objs.append(tgt_slot)

    if target_verb is None:
        # EXCLUDED-LOSSY path: null-tolerant creation bypasses the flexicon
        # wrapper that validates pos != None.
        new_msa = _create_inflaff_msa_null_tolerant(
            target, new_sense, target_verb=None,
            slot_objs=src_slot_objs, report_sink=report_sink
        )
        if new_msa is None:
            return None
    else:
        new_msa = target.MSA.CreateInflAff(new_sense, target_verb, slots=src_slot_objs or None)

    # Record the GUID change (LCM doesn't permit preserve).
    new_guid = str(ICmObject(new_msa).Guid).lower()
    if new_guid != src_guid:
        identity_remap[src_guid] = new_guid

    new_ia = IMoInflAffMsa(new_msa)
    cache = getattr(target, "Cache")
    apply_residue(new_msa, cache.DefaultAnalWs, tag)
    report_sink.Info(
        f"  IMoInflAffMsa created  src={src_guid[:8]}  new={new_guid[:8]}"
        f"  slots={new_ia.SlotsRC.Count}"
    )
    return new_msa


def _create_allomorph_with_guid(target, new_entry, src_guid: str, src_allo, source,
                                  env_guid_to_target,
                                  tag: ImportResidueTag, report_sink,
                                  identity_remap: dict):
    """Create IMoAffixAllomorph via flexicon's LexiconAddAllomorph wrapper
    (which handles the LibLCM Create signature internally).

    GUID preservation (033): the source GUID IS preserved, via
    `owned._create_owned_via_factory`. The previous claim here -- that "LCM
    allomorph factories don't accept a Guid" -- was false: the 033 audit
    preserved 106/106 affix-allomorph GUIDs through exactly this factory's
    `Create(Guid)` overload. (Same false-docstring class as the MSA one
    corrected in d8576e0.) `identity_remap` is still recorded per FR-012, and
    now normally maps a GUID to itself; it diverges only on a LOGGED fallback
    to a minted identity.

    Phase 0 Layer 3 is structural-only — lexeme Form text content is NOT
    transferred (flexicon's ApplySyncableProperties had ITsString conversion
    gaps in early builds); a future Phase 0.5 task re-enables string
    content preservation.
    """
    from SIL.LCModel import IMoAffixAllomorphFactory, IMoAffixAllomorph, ILexEntry, ICmObject

    # Without ApplySyncableProperties, we can't easily recover the source
    # form text; create the allomorph as a bare structural placeholder.
    try:  # module-local import: transfer.py's established lazy-import idiom
        from .owned import _create_owned_via_factory
    except ImportError:  # pragma: no cover - bare-script sys.path convention
        from owned import _create_owned_via_factory  # type: ignore
    factory = IMoAffixAllomorphFactory(target.GetFactory(IMoAffixAllomorphFactory))
    new_allo = _create_owned_via_factory(factory, src_guid, "MoAffixAllomorph")
    if new_allo is None:
        report_sink.Warning(
            f"  [L3] IMoAffixAllomorphFactory.Create() unavailable; skipping allomorph {src_guid[:8]}"
        )
        return None
    entry_ie = ILexEntry(new_entry)
    if entry_ie.LexemeFormOA is None:
        entry_ie.LexemeFormOA = new_allo
    else:
        entry_ie.AlternateFormsOS.Add(new_allo)

    new_guid = str(ICmObject(new_allo).Guid).lower()
    if new_guid != src_guid:
        identity_remap[src_guid] = new_guid

    # Apply syncable properties (Form multistring + scalar bools, etc.).
    # flexicon's BaseOperations.ApplySyncableProperties now handles ITsString
    # wrapping for raw-str scalars (landed 2026-06-19).
    src_props = source.Allomorphs.GetSyncableProperties(src_allo)
    target.Allomorphs.ApplySyncableProperties(new_allo, src_props)

    # MorphTypeRA is an object reference to a global FW morph-type list item
    # — same GUID across every FW project. ApplySyncableProperties dropped
    # it as an object-reference; resolve here explicitly by GUID lookup.
    src_morph_type = IMoAffixAllomorph(src_allo).MorphTypeRA
    if src_morph_type is not None:
        morph_type_guid = str(ICmObject(src_morph_type).Guid).lower()
        target_morph_type = _find_target_morph_type_by_guid(target, morph_type_guid)
        if target_morph_type is not None:
            IMoAffixAllomorph(new_allo).MorphTypeRA = target_morph_type
        else:
            report_sink.Warning(
                f"  [L3] Allomorph {src_guid[:8]} references MorphType "
                f"{morph_type_guid[:8]} not in target"
            )

    # Wire PhoneEnvRC by GUID lookup.
    new_ia = IMoAffixAllomorph(new_allo)
    src_ia = IMoAffixAllomorph(src_allo)
    for src_env in src_ia.PhoneEnvRC:
        env_guid = str(ICmObject(src_env).Guid).lower()
        tgt_env = env_guid_to_target.get(env_guid)
        if tgt_env is None:
            report_sink.Warning(f"  [L3] Allomorph references env {env_guid[:8]} not in target")
            continue
        new_ia.PhoneEnvRC.Add(tgt_env)
    cache = getattr(target, "Cache")
    apply_residue(new_allo, cache.DefaultAnalWs, tag)
    report_sink.Info(f"  IMoAffixAllomorph created  src={src_guid[:8]}  new={new_guid[:8]}")
    return new_allo


def _project_for_cache(cache):
    """Best-effort lookup of the FLExProject wrapper from an LcmCache. Used
    when we have a child object and need to call ApplySyncableProperties via
    the project's Operations accessors. May return None on the source-side
    cache; callers must handle that."""
    # The runner injects `project` into the namespace; module code can't
    # access it. Caller must thread the target project through if they need
    # this. For now return None and skip ApplySyncableProperties on senses;
    # syncable-props on senses are lighter than on entries anyway.
    return None


# Re-imported helpers from preview.py — kept here to avoid a circular import
# at module load time.
def _lex_sense_msa(sense):
    from SIL.LCModel import ILexSense
    return ILexSense(sense).MorphoSyntaxAnalysisRA


def _classname_of(obj):
    from SIL.LCModel import ICmObject
    return ICmObject(obj).ClassName


def _msa_points_at_verb(msa, verb_guid: str) -> bool:
    from SIL.LCModel import IMoInflAffMsa, ICmObject
    ia = IMoInflAffMsa(msa)
    if ia.PartOfSpeechRA is None:
        return False
    return str(ICmObject(ia.PartOfSpeechRA).Guid).lower() == verb_guid


# ============================================================================
# Phase 1 overwrite executor (FR-101)
# ============================================================================

def _resolve_decisions_for(overwrite, interactive_session):
    """Look up the MergeDecisionLog for this overwrite's target_guid in the
    session, or return None if there's no session / no log for this object.
    """
    if interactive_session is None:
        return None
    return interactive_session.merge_decisions_by_guid.get(overwrite.target_guid)


def _resolve_and_tag(src_props, tgt_pre_props, tag, log, category, target_guid, run_id):
    """Apply MergeDecisionLog (if any) to src_props and stamp the tag with
    `with_merge_log(log)` when a log is present.

    Returns (filtered_src_props, tagged_tag, skip_records).
    """
    if log is None:
        return src_props, tag.with_snapshot(tgt_pre_props), []
    filtered, skips = _apply_merge_decisions(
        src_props=src_props,
        decisions=log.decisions,
        tgt_pre_props=tgt_pre_props,
        run_id=run_id,
        category=category,
        target_guid=target_guid,
    )
    tagged = tag.with_snapshot(tgt_pre_props).with_merge_log(log)
    return filtered, tagged, skips


# ============================================================================
# Feature 038 T045 (US4, FR-020..FR-022, SC-007/SC-008/SC-010) -- the ADD-ONLY
# owned-collection merge, executor half.
# ============================================================================
#
# T043/T044 made the PLAN honest: a GUID-matched `IPartOfSpeech` that lacks
# children its source counterpart holds is no longer `Skip(ALREADY_PRESENT_BY_
# GUID)` but a `PlannedOverwrite(write_mode="merge")` carrying an
# `EnrichmentRecord` whose `EnrichedCollection` rows PROJECT what each of the
# seven collections would gain. This section is the other half: it actually
# writes those children, and it re-measures the outcome so the report states
# what happened rather than what was projected.
#
# THE FOUR RULES THIS SECTION IS BUILT AROUND
#
# 1. ADD-ONLY, BY CONSTRUCTION (FR-021). The executor only ever CREATES a new
#    child and APPENDS it. It never removes a child, never blanks one, and
#    never writes a single field into a destination child that already
#    existed -- a child matched by `_match_collection_child` is counted
#    `already_present` and then left completely alone. "Non-destructive" is
#    therefore not a property of a careful field-by-field comparison here; it
#    is a property of the code never touching pre-existing content at all.
#
# 2. NEVER REORDER. Two of the seven are ordered SEQUENCES -- `AffixTemplatesOS`
#    and `SubPossibilitiesOS` -- where index is meaning; on the five unordered
#    COLLECTIONS (`AffixSlotsOC`, `InflectableFeatsRC`, `StemNamesOC`,
#    `InflectionClassesOC`, `ReferenceFormsOC`) "order" is not a fact about the
#    data and "never reorder" is vacuous. Appending via `.Add()` is
#    order-preserving for both shapes, and `_check_add_only` re-reads the
#    destination afterwards and WARNS if any pre-existing member moved or
#    vanished. That check is evidence, not enforcement: it cannot undo a write,
#    but it makes a violation loud instead of silent.
#
# 3. ALL SEVEN COLLECTIONS REQUIRE A PYTHONNET CAST. Live-verified
#    (FLExToolsMCP `get_object_api IPartOfSpeech` / `resolve_property
#    ReferenceFormsOC`, 2026-08-20): `requires_cast: true` on every one. An
#    UNCAST `getattr` on a base-interface proxy returns None, which reads as
#    "the collection is empty" -- so an uncast executor would write nothing and
#    report success. That is the trap that made flexicon 4.5.0's `FeaturesOA`
#    wiring 100% dead behind an unconditionally-False `hasattr` (CLAUDE.md).
#    The cast table and the receiver-probe ORDER are NOT duplicated here:
#    `_pos_writable_collection` reads `categories._POS_OWNED_COLLECTION_CASTS`
#    and calls `categories._cast_lcm`, exactly as the planner's
#    `categories._pos_owned_collection` does. The only reason a second accessor
#    exists at all is that the planner needs a SNAPSHOT (`list(raw)`) while the
#    executor needs the LIVE collection object to `.Add()` to.
#
# 4. GUID-PRESERVING CREATES ONLY (CLAUDE.md). Every create routes through
#    `categories.create_with_guid` -> `owned._create_owned_via_factory`, which
#    tries `Create(Guid)` first and LOGS the reason whenever it has to fall
#    back to a minted identity. A bare `Create()` would silently regenerate
#    identity and break SC-008 idempotence on the next run.
#
# WHY SOME CHILDREN ARE DEFERRED RATHER THAN WRITTEN. Five of the seven
# collections hold children that are ALSO independently enumerated items of
# another GramTrans category, with their own richer create path:
# `SubPossibilitiesOS` children are POSes yielded by
# `categories.gram_categories_enumerate_source` (`POS.GetAll(recursive=True)`),
# `InflectionClassesOC` by `inflection_classes_enumerate_source`, `StemNamesOC`
# by `stem_names_enumerate_source`, and so on. When the plan already carries a
# `PlannedAction` for a child's GUID, creating it HERE would win the race --
# the overwrite/UPDATE loop in `execute()` runs BEFORE leaf dispatch -- and the
# dedicated path's own `_target_has_guid` guard would then turn its richer
# create (residue carrier-B, per-category field handling) into a silent no-op.
# So such a child is DEFERRED: not written here, and counted `added` because it
# does land this run. Counting it `dropped` instead would report a loss that
# does not happen -- the same phantom-loss defect CLAUDE.md records for
# flexicon 4.5.1.
#
# WHAT IS NOT DONE HERE, STATED PLAINLY. A child created by this pass gets its
# GUID and its `Name`/`Abbreviation`/`Description` multistrings (WS-mapped via
# `categories._copy_multistrings_ws_mapped`). It does NOT get its own owned
# grandchildren (e.g. an `MoInflAffixTemplate`'s slot sequence) or its own
# reference fields. For the five collections whose children have a dedicated
# category that is what the deferral above is for; for `AffixSlotsOC` and
# `ReferenceFormsOC` this is a real, acknowledged depth limit of T045.

#: The categories whose `PlannedOverwrite` may carry an `EnrichmentRecord`.
#: Mirrors `categories._POS_OWNED_COLLECTION_CATEGORIES` (POS is ALIASED to
#: gram_categories); the seven collections are POS-only.
_ENRICHMENT_CATEGORIES = frozenset({
    GrammarCategory.GRAM_CATEGORIES,
    GrammarCategory.POS,
})

#: Scalar multistrings copied onto a child this pass creates. Same three the
#: scalar half of the merge compares (`categories._plan_gold_reserved_edit`).
_ENRICH_CHILD_SCALARS = ("Name", "Abbreviation", "Description")

#: `owner_kind` for a `DroppedItemRecord` raised by this pass. Free-form by
#: contract (`models.DroppedItemRecord`), but the owner really is the POS.
_ENRICH_OWNER_KIND = "PartOfSpeech"

#: THE ONE DELIBERATE UNKNOWN `POS_OWNED_COLLECTION_SPECS` LEFT FOR T045.
#: That roster gives `ReferenceFormsOC` `factory=None` and says so in as many
#: words -- "a DELIBERATE unknown, not an assertion that none is needed ...
#: T043/T045 must resolve it before creating into this collection". This is
#: that resolution, and it is deliberately NOT a competing factory table: the
#: other six still come from the roster, and this dict holds exactly the row
#: the roster declined to answer.
#:
#: Resolved live, read-only, via FLExToolsMCP on 2026-08-20:
#: `get_object_api IPartOfSpeech` reports `ReferenceFormsOC` as
#: `target_type: IFsFeatStruc` (an owning COLLECTION, requires_cast: true), and
#: `resolve_type IFsFeatStrucFactory` confirms
#: `from SIL.LCModel import IFsFeatStrucFactory`. Reflection over the INTERFACE
#: shows only the inherited no-arg `Create()` -- the same thing tasks.md T053
#: records for every factory in its graph, where the CONCRETE implementation
#: carries `Create(Guid)`. `create_with_guid` tries the GUID overload first and
#: LOGS the fallback, so a factory that really lacks it degrades loudly instead
#: of silently minting a new identity.
_ENRICH_FACTORY_RESOLVED = {
    "ReferenceFormsOC": "IFsFeatStrucFactory",
}


def _enrichment_factory_name(spec):
    """The factory interface name for `spec`, resolving the roster's one
    deliberate `factory=None` unknown (`ReferenceFormsOC`). Returns "" when the
    row genuinely creates nothing (`InflectableFeatsRC`, a reference
    collection) or when no factory is known at all."""
    if spec is None:
        return ""
    if spec.factory:
        return str(spec.factory)
    return _ENRICH_FACTORY_RESOLVED.get(spec.owning_field, "")


def _categories_mod():
    """`Lib.categories`, imported lazily (it imports this module at runtime)."""
    if __package__:
        from . import categories as _cats
    else:
        import categories as _cats  # type: ignore
    return _cats


def _owned_mod():
    """`Lib.owned`, imported lazily for its factory/GUID helpers."""
    if __package__:
        from . import owned as _own
    else:
        import owned as _own  # type: ignore
    return _own


def _enrichment_specs() -> dict:
    """`{canonical_field: OwnedObjectSpec}` for the seven POS collections.

    Reads `models.POS_OWNED_COLLECTION_SPECS` -- the roster T042 declared and
    that models.py's own import-time guard keeps in lockstep with
    `POS_OWNED_COLLECTION_FIELDS`. No second factory/create-kind table.
    """
    if __package__:
        from .models import POS_OWNED_COLLECTION_SPECS
    else:
        from models import POS_OWNED_COLLECTION_SPECS  # type: ignore
    return {spec.owning_field: spec for spec in POS_OWNED_COLLECTION_SPECS}


def _pos_writable_collection(obj, field_name):
    """`(receiver, spelling, live_collection)` for one of the seven, else a
    triple of Nones.

    The executor twin of `categories._pos_owned_collection`: SAME cast table
    (`categories._POS_OWNED_COLLECTION_CASTS`), SAME cast function
    (`categories._cast_lcm`), SAME receiver order (uncast first, then each
    declared interface) and SAME both-spellings probe. It differs in exactly
    one respect, which is why it exists: it returns the LIVE collection object
    (the thing `.Add()` is called on) and the cast receiver that owns it,
    rather than the planner's read-only `list(raw)` snapshot.

    A `(None, None, None)` return means the field is not reachable on this
    object at all -- which, per rule 3 above, must never be inferred from an
    UNCAST read.
    """
    cats = _categories_mod()
    if obj is None:
        return None, None, None
    if __package__:
        from .models import POS_OWNED_COLLECTION_ALIASES
    else:
        from models import POS_OWNED_COLLECTION_ALIASES  # type: ignore

    spellings = [field_name]
    for alias, canonical in POS_OWNED_COLLECTION_ALIASES.items():
        if canonical == field_name and alias not in spellings:
            spellings.append(alias)

    receivers = [obj]
    for iface_name in cats._POS_OWNED_COLLECTION_CASTS.get(field_name, ()):
        cast = cats._cast_lcm(obj, iface_name)
        if cast is not None and cast is not obj:
            receivers.append(cast)

    for receiver in receivers:
        for spelling in spellings:
            try:
                raw = getattr(receiver, spelling, None)
            except Exception:  # noqa: BLE001 -- unreadable member is "absent"
                continue
            if raw is None:
                continue
            try:
                list(raw)
            except TypeError:
                continue
            return receiver, spelling, raw
    return None, None, None


def _same_lcm_member(a, b) -> bool:
    """Identity of two collection members. Every iteration of a pythonnet
    collection yields FRESH wrapper proxies, so `is` is False for the very
    same LCM object; compare by GUID, falling back to `is` / `==`."""
    if a is b:
        return True
    cats = _categories_mod()
    ga, gb = cats._guid_str_from(a), cats._guid_str_from(b)
    if ga and gb:
        return ga == gb
    try:
        return bool(a == b)
    except Exception:  # noqa: BLE001
        return False


def _check_add_only(field_name, before, live, report_sink, src_guid):
    """Warn if the write pass disturbed pre-existing destination content.

    `before` is the member list snapshotted BEFORE any `.Add()`. Add-only means
    the post-write membership must still start with exactly those objects, in
    exactly that order -- appending cannot change either. This cannot undo a
    violation; it exists so a violation is loud (Principle I) instead of a
    silently reordered `AffixTemplatesOS`, where index is meaning.

    Returns True when the invariant held (or could not be checked).
    """
    if live is None:
        return True
    try:
        after = list(live)
    except TypeError:
        return True
    if len(after) < len(before):
        report_sink.Warning(
            f"  [enrich] {field_name}: ADD-ONLY VIOLATED -- destination went"
            f" from {len(before)} to {len(after)} member(s); enrichment must"
            f" never remove  guid={src_guid[:8]}"
        )
        return False
    for index, original in enumerate(before):
        if not _same_lcm_member(after[index], original):
            report_sink.Warning(
                f"  [enrich] {field_name}: ADD-ONLY VIOLATED -- pre-existing"
                f" member at index {index} moved or was replaced; enrichment"
                f" must never reorder  guid={src_guid[:8]}"
            )
            return False
    return True


def _add_reference_collection_member(child, live, target):
    """`InflectableFeatsRC` leg: LINK an existing target `IFsFeatDefn`.

    A REFERENCE collection creates NOTHING (`POS_OWNED_COLLECTION_SPECS` gives
    this row `factory=None` for exactly that reason). The source child is a
    feature that must already exist in the destination -- resolved by GUID
    through `categories._resolve_target_by_guid`, the same resolver
    `categories._run_infl_feature_link_pass` uses for this very field. An
    unresolved feature is a REPORTED drop, never a created duplicate.

    Returns `(added_object, reason)`; `added_object is None` means dropped.
    """
    cats = _categories_mod()
    child_guid = cats._guid_str_from(child)
    if not child_guid:
        return None, "source feature carries no GUID to resolve against target"
    target_feat = cats._resolve_target_by_guid(target, child_guid)
    if target_feat is None:
        return None, (
            "referenced IFsFeatDefn is absent from the target -- a reference "
            "collection links an existing feature and never creates one; "
            "select INFLECTION_FEATURES so the feature transfers first"
        )
    live.Add(target_feat)
    return target_feat, ""


def _create_collection_child(spec, child, receiver, live, target):
    """Create one owned child, GUID preserved, and attach it.

    UNOWNED_THEN_ADD -> `categories.create_with_guid(factory, guid, kind)` then
    `live.Add(new)`. OWNER_TAKING -> `factory.Create(guid, owner)`, the shape
    `categories.gram_categories_execute_action` already uses live for a
    sub-POS, with the SAME GUID-fallback logging `create_with_guid` performs
    (`owned._log_guid_fallback`) so an unpreserved identity is never silent.

    Returns `(new_child, reason)`; `new_child is None` means dropped.
    """
    cats = _categories_mod()
    own = _owned_mod()
    if __package__:
        from .models import OwnedCreateKind
    else:
        from models import OwnedCreateKind  # type: ignore

    factory_name = _enrichment_factory_name(spec)
    if not factory_name:
        return None, (
            "no LCM factory is wired for " + spec.owning_field + " -- the "
            "child cannot be created, so it is reported rather than lost "
            "silently"
        )
    child_guid = cats._guid_str_from(child)
    factory = own._get_owned_factory(target, factory_name)
    if factory is None:
        return None, "factory " + factory_name + " not available on the target"

    if spec.create_kind == OwnedCreateKind.OWNER_TAKING:
        guid_arg = own._guid_for_create(child_guid) if child_guid else None
        new_child = None
        if guid_arg is not None:
            try:
                new_child = factory.Create(guid_arg, receiver)
            except Exception as exc:  # noqa: BLE001 -- overload absent/GUID taken
                own._log_guid_fallback(spec.owning_field, child_guid, exc)
        if new_child is None:
            try:
                new_child = factory.Create()
            except Exception as exc:  # noqa: BLE001
                return None, f"create failed: {type(exc).__name__}: {exc}"
            live.Add(new_child)
        return new_child, ""

    new_child = cats.create_with_guid(factory, child_guid, spec.owning_field)
    if new_child is None:
        return None, f"create failed for {spec.owning_field} via {factory_name}"
    live.Add(new_child)
    return new_child, ""


def _enrich_one_collection(field_name, spec, src_obj, tgt_obj, source, target,
                           report_sink, src_guid, ws_map, ws_handles,
                           source_ws_handles, planned_action_guids):
    """Add every source child the destination lacks, for ONE collection.

    Returns `(EnrichedCollection, [DroppedItemRecord, ...])` whose three
    buckets account for every source child exactly once: `added` (written now,
    or deferred to a dedicated PlannedAction that lands this same run),
    `already_present` (the destination had it -- left entirely untouched),
    `dropped` (could not be added, each one carrying a `DroppedItemRecord`).
    `EnrichedCollection.__post_init__` refuses an anonymous drop, so there is
    no fourth outcome (SC-010).
    """
    cats = _categories_mod()
    if __package__:
        from .models import EnrichedCollection
    else:
        from models import EnrichedCollection  # type: ignore

    spelling, src_children = cats._pos_owned_collection(src_obj, field_name)
    if spelling is None:
        src_children = []
    receiver, _tgt_spelling, live = _pos_writable_collection(tgt_obj, field_name)
    try:
        before = list(live) if live is not None else []
    except TypeError:
        before = []
    candidates = list(before)
    child_class = cats._POS_OWNED_COLLECTION_CHILD_CLASS.get(field_name, "")

    added = 0
    already_present = 0
    drops: list = []

    def _drop(child, reason):
        drops.append(DroppedItemRecord(
            owner_kind=_ENRICH_OWNER_KIND,
            owner_guid=src_guid,
            owner_label=src_guid,
            field_name=field_name,
            item_name=str(getattr(child, "ClassName", "") or child_class
                          or field_name),
            item_guid=cats._guid_str_from(child) or "",
            reason=reason,
        ))
        report_sink.Warning(
            f"  [enrich] {field_name}: child not added -- {reason}"
            f"  guid={src_guid[:8]}"
        )

    for child in src_children or ():
        # T044's rule, not a second matcher: GUID first, then the R1 roster
        # key, scoped to THIS collection. This is what makes a re-run report
        # `already_present` instead of appending a duplicate (SC-008).
        try:
            matched = cats._match_collection_child(
                child, candidates, child_class, ws_handles, source_ws_handles,
            )
        except Exception as exc:  # noqa: BLE001 -- ambiguity/roster failure
            _drop(child, f"identity match failed: {type(exc).__name__}: {exc}")
            continue
        if matched is not None:
            already_present += 1
            continue

        child_guid = cats._guid_str_from(child)
        if child_guid and child_guid in planned_action_guids:
            # A dedicated category owns this child's create and runs later in
            # THIS run (leaf dispatch follows the overwrite loop). Writing it
            # here would pre-empt the richer path; reporting it dropped would
            # report a loss that does not happen.
            added += 1
            report_sink.Info(
                f"  [enrich] {field_name}: child {child_guid[:8]} deferred to"
                f" its own PlannedAction (dedicated create path)"
            )
            continue

        if live is None:
            _drop(child, (
                field_name + " is not reachable on the destination object -- "
                "no declared interface cast exposed it"
            ))
            continue

        try:
            if spec is None:
                new_child, reason = None, (
                    field_name + " has no OwnedObjectSpec row")
            elif field_name == "InflectableFeatsRC":
                new_child, reason = _add_reference_collection_member(
                    child, live, target)
            else:
                new_child, reason = _create_collection_child(
                    spec, child, receiver, live, target)
        except Exception as exc:  # noqa: BLE001 -- LCM/COM failures are wide
            _log.exception(
                "_enrich_one_collection: add failed field=%s owner=%s",
                field_name, src_guid,
            )
            new_child, reason = None, f"add failed: {type(exc).__name__}: {exc}"

        if new_child is None:
            _drop(child, reason or "child could not be added")
            continue

        # A brand-new child has no content to preserve, so copying its scalars
        # cannot overwrite anything -- which is why this is the ONLY write the
        # pass makes into a child, and why it happens only for children it
        # created itself.
        if field_name != "InflectableFeatsRC":
            try:
                cats._copy_multistrings_ws_mapped(
                    child, new_child, _ENRICH_CHILD_SCALARS,
                    source=source, target=target, ws_map=ws_map or {},
                )
            except Exception as exc:  # noqa: BLE001 -- scalar copy is best-effort
                report_sink.Warning(
                    f"  [enrich] {field_name}: a child was created but its"
                    f" scalars did not copy ({type(exc).__name__}: {exc})"
                    f"  guid={src_guid[:8]}"
                )
        added += 1
        candidates.append(new_child)

    _check_add_only(field_name, before, live, report_sink, src_guid)

    return EnrichedCollection(
        field_name=spelling or field_name,
        added=added,
        already_present=already_present,
        dropped=len(drops),
        dropped_records=tuple(drops),
    ), drops


def _enrich_owned_collections(overwrite, src_obj, tgt_obj, source, target,
                              report_sink, ws_map=None, dropped=None,
                              planned_action_guids=frozenset()):
    """Execute the plan's `EnrichmentRecord` and return the MEASURED one.

    The plan's record PROJECTS what each collection would gain; this returns a
    record of the same shape whose counts are what actually happened, so the
    run report states an outcome rather than an intention. `was_created` stays
    False by construction (`EnrichmentRecord` refuses True) -- an enrichment
    acts on an object that already existed, which is the created-vs-enriched
    distinction FR-022 requires.

    Returns None when there is nothing to execute.
    """
    planned = getattr(overwrite, "enrichment", None)
    if planned is None or not planned.collections:
        return None
    if overwrite.category not in _ENRICHMENT_CATEGORIES:
        return None
    if src_obj is None or tgt_obj is None:
        return None

    cats = _categories_mod()
    if __package__:
        from .models import EnrichmentRecord
    else:
        from models import EnrichmentRecord  # type: ignore

    src_guid = overwrite.source_guid or ""
    specs = _enrichment_specs()
    ws_handles = cats._matcher.ws_handles_for(target)
    source_ws_handles = cats._matcher.ws_handles_for(source)
    src_inner = cats._unwrap_lcm(src_obj)
    tgt_inner = cats._unwrap_lcm(tgt_obj)

    rows = []
    for planned_row in planned.collections:
        field_name = planned_row.canonical_field_name
        row, drops = _enrich_one_collection(
            field_name, specs.get(field_name), src_inner, tgt_inner,
            source, target, report_sink, src_guid, ws_map, ws_handles,
            source_ws_handles, planned_action_guids,
        )
        rows.append(row)
        if dropped is not None:
            dropped.extend(drops)

    measured = EnrichmentRecord(
        object_class=planned.object_class,
        source_guid=planned.source_guid,
        target_guid=planned.target_guid,
        label=planned.label,
        collections=tuple(rows),
        fields_updated=planned.fields_updated,
        was_created=False,
    )

    # THE T045 REPORT LINE: disposition plus per-collection counts. `UPDATE` is
    # stated literally because data-model.md section 9 binds this situation
    # ("Identity match, delta found") to that disposition, and because an
    # enrichment whose every bucket is `already_present` is precisely the
    # SC-008 re-run signal -- worth being able to read straight off the log.
    counts = " | ".join(
        f"{c.field_name}: added={c.added} already_present={c.already_present}"
        f" dropped={c.dropped}"
        for c in rows
    )
    report_sink.Info(
        f"  [{overwrite.category.value}] disposition=UPDATE enrichment"
        f" (add-only)  guid={src_guid[:8]}  {counts}"
    )
    return measured


def _record_unfilled_pos_collections(action, dropped, reason):
    """Record one `DroppedItemRecord` per POS owned collection that a created
    POS did NOT receive (#107 never-silent). The POS create itself stays
    successful; only its children are reported as not reproduced."""
    if dropped is None:
        return
    cats = _categories_mod()
    if __package__:
        from .models import POS_OWNED_COLLECTION_FIELDS
    else:
        from models import POS_OWNED_COLLECTION_FIELDS  # type: ignore
    guid = (action.source_guid or "")
    label = (getattr(action, "summary", "") or "").strip() or guid
    for field_name in POS_OWNED_COLLECTION_FIELDS:
        cats._append_dropped_once(dropped, DroppedItemRecord(
            owner_kind=_ENRICH_OWNER_KIND,
            owner_guid=guid,
            owner_label=label,
            field_name=field_name,
            item_name="(entire collection)",
            item_guid="",
            reason=reason,
        ))


def _fill_created_pos_collections(action, created, source, target, report_sink,
                                  ws_map=None, dropped=None,
                                  planned_action_guids=frozenset()):
    """Give a POS this run just CREATED its seven owned collections (#107).

    `gram_categories_execute_action` creates the POS and copies its scalars;
    it never touched AffixSlotsOC / AffixTemplatesOS / ReferenceFormsOC / ...
    Only the UPDATE path (`_enrich_owned_collections`) filled those, and only
    for a POS the target ALREADY held. So run 1 left every created POS a
    shell, and run 2 -- planning 0 actions -- found it present by GUID and
    filled it then (measured: Mbugwe LizzieHC practice -> restored Target,
    10 slots, 7 templates, 47 FsFeatStruc on run 2; run 3 clean). The
    transfer converged on the second run instead of the first.

    This runs the SAME per-collection writer (`_enrich_one_collection`: same
    GUID-then-roster matcher, same GUID-preserving create, same deferral of a
    child that has its own PlannedAction) right after the create, inside the
    leaf loop -- i.e. before SLOTS / AFFIX_TEMPLATES / the 17.1 sub-pass need
    those slots and templates to exist.

    No `EnrichmentRecord` is produced: FR-022 reserves that record for an
    object that already existed (`was_created=True` is refused), and the
    children here are part of the create. Drops still reach `dropped`.

    Returns the per-collection rows that did something, or None when `action`
    is not a POS create or `created` is not a created object.
    """
    if action.category not in _ENRICHMENT_CATEGORIES:
        return None
    if created is None or isinstance(created, ActionOutcome):
        return None
    cats = _categories_mod()
    if __package__:
        from .models import POS_OWNED_COLLECTION_FIELDS
    else:
        from models import POS_OWNED_COLLECTION_FIELDS  # type: ignore

    src_guid = (action.source_guid or "").lower()
    src_obj = None
    try:
        for pos in source.POS.GetAll(recursive=True):
            if (cats._guid_str_from(pos) or "").lower() == src_guid:
                src_obj = pos
                break
    except Exception:  # noqa: BLE001 -- an unreadable source is reported below
        src_obj = None
    if src_obj is None:
        report_sink.Warning(
            f"  [{action.category.value}] created POS: source object not found,"
            f" owned collections NOT filled  guid={src_guid[:8]}"
        )
        _record_unfilled_pos_collections(
            action, dropped,
            "source POS not found; owned collections of created POS not filled",
        )
        return None

    specs = _enrichment_specs()
    ws_handles = cats._matcher.ws_handles_for(target)
    source_ws_handles = cats._matcher.ws_handles_for(source)
    src_inner = cats._unwrap_lcm(src_obj)
    tgt_inner = cats._unwrap_lcm(created)
    rows = []
    for field_name in POS_OWNED_COLLECTION_FIELDS:
        row, drops = _enrich_one_collection(
            field_name, specs.get(field_name), src_inner, tgt_inner,
            source, target, report_sink, src_guid, ws_map, ws_handles,
            source_ws_handles, planned_action_guids,
        )
        if dropped is not None:
            dropped.extend(drops)
        if row.added or row.dropped:
            rows.append(row)
    if rows:
        report_sink.Info(
            f"  [{action.category.value}] created POS: owned collections"
            f" filled  guid={src_guid[:8]}  " + " | ".join(
                f"{c.field_name}: added={c.added} dropped={c.dropped}"
                for c in rows)
        )
    return rows


def _execute_update_semantic(overwrite, source, target, report_sink, tag: ImportResidueTag,
                             ws_map=None, dropped=None, enrichments=None,
                             planned_action_guids=frozenset()):
    """Apply the non-destructive UPDATE write semantic (T012, FR-003) for a
    PlannedOverwrite whose category mode is ConflictMode.UPDATE.

    Steps:
    1. Resolve the conflict mode and call compute_disposition (2-way, no prior
       baseline) to determine SKIP / UPDATE / ADD.
    2. If disposition is SKIP (all fields identical), log and return.
    3. If disposition is UPDATE, call apply_update_semantic (non-destructive
       field writes: never blanks a target field from an empty source).

    The category-tier lookup and per-category ops accessor mirrors _execute_overwrite
    but uses apply_update_semantic instead of ApplySyncableProperties unconditionally.

    Only categories for which flexicon exposes a syncable-property ops accessor are
    handled here.  Unknown/unsupported categories fall through to a warning and no-op.

    `dropped` (coordinator live-run defect B, feature 037): the per-run
    `DroppedItemRecord` collector, threaded through to
    `_execute_phon_rule_structural_update` -> `categories._phon_rule_apply_body`
    for its InputPOSesRC/ReqRuleFeatsRC/ExclRuleFeatsRC unresolved-reference
    reporting. Used by the generic ops-accessor path below only to carry the
    owned-collection enrichment's own drops (feature 038 T045).

    `enrichments` (feature 038 T045, FR-020..FR-022): the per-run MEASURED
    `EnrichmentRecord` collector. `overwrite.enrichment` is what the PLANNER
    projected; the record appended here is what the writes actually achieved,
    so the report can state an outcome. Optional -- a caller that does not care
    passes None and only the report_sink line is produced.

    `planned_action_guids` (feature 038 T045): source GUIDs the plan will
    CREATE through their own `PlannedAction`. A collection child in this set is
    deferred to that dedicated create path rather than written here -- see the
    "WHY SOME CHILDREN ARE DEFERRED" note above `_enrich_owned_collections`.

    STEP ORDER MATTERS FOR THE ENRICHMENT (feature 038 T045). The owned-
    collection pass runs REGARDLESS of the scalar disposition, including when
    `compute_disposition` returns SKIP. `compute_disposition` compares
    GetSyncableProperties, and none of the seven owned collections appears
    there -- so a POS whose Name/Abbreviation/Description already match returns
    SKIP while still missing whole collections. Returning early on that SKIP is
    defect G3 regenerating itself one layer down: the plan would correctly say
    UPDATE and the executor would silently write nothing.
    """
    if __package__:
        from .models import ConflictMode as _ConflictMode
    else:
        from models import ConflictMode as _ConflictMode  # type: ignore

    cat = overwrite.category
    src_guid = overwrite.source_guid
    tgt_guid = overwrite.target_guid

    # Task 7 (feature 037): a PHONOLOGICAL_RULES overwrite whose
    # `write_mode == "structural_rebuild"` came from
    # `categories.phonological_rules_plan_action` finding the target rule
    # already present by GUID but STRUCTURALLY different from source (a
    # shallow GetSyncableProperties-only compare -- Name/Description/
    # Direction/StratumGuid -- cannot see this; see
    # `categories._phon_rule_fingerprint`'s docstring for the proven case).
    # Route to the dedicated rebuild helper instead of the generic
    # ops-accessor path below, which (a) is keyed on the wrong flexicon
    # accessor name for this category (`PhonologicalRules`, which does not
    # exist -- flexicon exposes `PhonRules`) and (b) only ever compares the
    # same four shallow fields, so it could never detect or fix this class
    # of drift even if the accessor name were corrected.
    if cat == GrammarCategory.PHONOLOGICAL_RULES and getattr(overwrite, "write_mode", "") == "structural_rebuild":
        if __package__:
            from .categories import _execute_phon_rule_structural_update
        else:
            from categories import _execute_phon_rule_structural_update  # type: ignore
        return _execute_phon_rule_structural_update(
            overwrite, source, target, report_sink, tag, ws_map=ws_map,
            dropped=dropped,
        )

    # C6 guard (issue #16): the ONLY place the Phoneme/Environment flexicon
    # version gate takes effect. This path is LIVE: `_phonology_simple_plan`
    # emits a `PlannedOverwrite(write_mode="merge")` for a phoneme/environment
    # matched by natural key (any phase) or present by GUID (Phase 1). With a
    # pyflexicon at/above `_FLEXICON_ITSTRING_FIX_VERSION` (4.1.2; the floor is
    # 4.8.0) the gate is open and they get full field-diff UPDATE (Tier A);
    # below it they stay selector-only (Tier C) and nothing is written here.
    if cat in (GrammarCategory.PHONEMES, GrammarCategory.PH_ENVIRONMENT) and not _phoneme_env_field_diff_enabled():
        report_sink.Info(
            f"  [{cat.value}] field-diff gated (flexicon version"
            f" < fix release); selector-only  guid={src_guid[:8]}"
        )
        return []

    # Resolve the ops accessor for this category.  We use the same pattern as
    # _execute_overwrite: switch on category to find source/target objects and
    # the Operations instance that exposes GetSyncableProperties /
    # ApplySyncableProperties.
    ops_key = _OPS_ACCESSOR_FOR_CATEGORY.get(cat)
    if ops_key is None:
        # Category not in the UPDATE-capable set. Per-item line stays Info;
        # `execute` emits ONE Warning per such category with the count, since
        # the plan promised these merges (issue #22 Part 1, blind spot 5).
        report_sink.Info(
            f"  [{cat.value}] UPDATE mode not wired for this category; no-op"
            f"  guid={src_guid[:8]}"
        )
        return []

    # Feature 038 T036 -- same resolve half as `_execute_overwrite`. The
    # `_find_obj_by_guid(tgt_ops, tgt_guid)` below walks ONE category's
    # `GetAll()` and swallows every exception on the way, so a miss is
    # indistinguishable from an accessor that raised; either way the UPDATE is
    # abandoned with a Warning the export path discards. When the plan named
    # the destination, resolve it once here instead. Raised (not caught)
    # deliberately, and placed OUTSIDE the try below so the broad
    # `except Exception` there cannot turn a harness error into a warning.
    dest = planned_destination_for(overwrite, target)

    # Feature 038 T045: hoisted so the owned-collection pass below can still
    # see the resolved pair after the scalar half has finished -- including
    # after it took the UPDATE-SKIP exit, which says nothing about the seven
    # collections (see the step-order note in the docstring).
    src_obj = None
    tgt_obj = None

    try:
        src_ops = getattr(source, ops_key, None)
        tgt_ops = getattr(target, ops_key, None)
        if src_ops is None or tgt_ops is None:
            report_sink.Warning(
                f"  [{cat.value}] UPDATE: ops accessor '{ops_key}' not found on"
                f" source/target  guid={src_guid[:8]}"
            )
            return []

        # Locate the source and target objects by GUID.
        src_obj = _find_obj_by_guid(src_ops, src_guid)
        tgt_obj = _find_obj_by_guid(tgt_ops, tgt_guid)
        if tgt_obj is None and dest.resolved:
            tgt_obj = dest.obj
        if src_obj is None or tgt_obj is None:
            report_sink.Warning(
                f"  [{cat.value}] UPDATE: source or target object not found"
                f"  src={src_guid[:8]}  tgt={tgt_guid[:8]}"
            )
            return []

        src_props = src_ops.GetSyncableProperties(src_obj)
        # Issue #87: a Carrier-B target's Description carries OUR OWN
        # `[GT-Tag]` line. Compare (and snapshot) the target WITHOUT it, else
        # an identical-except-tag object resolves to UPDATE on every re-run and
        # the write replaces the tag line.
        tgt_props = strip_residue_props(tgt_ops.GetSyncableProperties(tgt_obj))
        # Issue #16: the snapshot keeps the target's props as read; only the
        # compare/write below sees the target-WS-space projection.
        _snapshot_props = dict(tgt_props)
        _write_ws_map = ws_map
        # Issue #54: drop keys the per-field writer cannot carry, so they
        # neither force an UPDATE nor count as "written" on every run.
        for _key in _UPDATE_UNWRITABLE_KEYS.get(cat, ()):
            src_props.pop(_key, None)
            tgt_props.pop(_key, None)
        if cat in _UPDATE_TARGET_SPACE_CATEGORIES:
            src_props, tgt_props = _to_update_target_space(
                cat, src_props, tgt_props, ws_map, target)
            # Source keys are already target WS ids; re-mapping them in
            # ApplySyncableProperties would double-map a swapped pair.
            _write_ws_map = None

        # Compute disposition (2-way, no prior baseline).
        disposition = compute_disposition(
            src_props=src_props,
            tgt_props=tgt_props,
            intent=_ConflictMode.UPDATE,
            ws_map=_write_ws_map,
        )

        if disposition == ItemDisposition.SKIP:
            # NOT a return (feature 038 T045). `compute_disposition` only ever
            # saw GetSyncableProperties, which carries none of the seven owned
            # collections, so "all fields identical" is a statement about the
            # scalars alone. Falling through lets the enrichment pass below
            # still run -- returning here is defect G3, one layer down.
            report_sink.Info(
                f"  [{cat.value}] UPDATE-SKIP (all scalar fields identical)"
                f"  guid={src_guid[:8]}"
            )
        else:
            # UPDATE: non-destructive field writes.
            cache = getattr(target, "Cache")
            # Tag-history decision (#87): earlier runs' tag lines are KEPT.
            # The source Description write replaces the whole alternative, so
            # capture them first and re-append them before this run's line.
            # conflict.load_prior_log parses with rfind (LAST line), so the
            # newest stamp still wins.
            _prior_desc = getattr(tgt_obj, "Description", None)
            _prior_lines = []
            if _prior_desc is not None:
                _prior_lines = residue_lines(
                    _prior_desc.get_String(cache.DefaultAnalWs).Text
                )
            # Issue #22 Part 1: per-field failures AND flexicon's silent skips
            # (detected by read-back inside apply_update_semantic, BEFORE the
            # residue lines below touch Description) reach the report sink.
            written = apply_update_semantic(
                src_props, tgt_props, tgt_ops, tgt_obj, ws_map=_write_ws_map,
                report_sink=report_sink,
                label=f"[{cat.value}] guid={src_guid[:8]}",
            )
            restore_residue_history(tgt_obj, cache.DefaultAnalWs, _prior_lines)
            apply_residue(tgt_obj, cache.DefaultAnalWs, tag.with_snapshot(_snapshot_props))
            report_sink.Info(
                f"  [{cat.value}] UPDATE applied ({written} field(s) written)"
                f"  guid={src_guid[:8]}"
            )
    except Exception as exc:
        _log.exception(
            "_execute_update_semantic: FAILED (swallowed) category=%s guid=%s",
            cat.value, src_guid,
        )
        report_sink.Warning(
            f"  [{cat.value}] _execute_update_semantic raised"
            f" {type(exc).__name__}: {exc}  guid={src_guid[:8]}"
        )

    # ---- Feature 038 T045 (FR-020..FR-022): the add-only collection half ----
    # In its OWN try, deliberately: a collection-level failure must not be able
    # to make the scalar half look like it failed, and vice versa. Each half
    # already reports its own outcome, so neither swallows the other's.
    if getattr(overwrite, "enrichment", None) is not None:
        try:
            measured = _enrich_owned_collections(
                overwrite, src_obj, tgt_obj, source, target, report_sink,
                ws_map=ws_map, dropped=dropped,
                planned_action_guids=planned_action_guids,
            )
        except Exception as exc:  # noqa: BLE001 -- LCM/COM failures are wide
            _log.exception(
                "_execute_update_semantic: enrichment FAILED (swallowed) "
                "category=%s guid=%s", cat.value, src_guid,
            )
            report_sink.Warning(
                f"  [{cat.value}] owned-collection enrichment raised"
                f" {type(exc).__name__}: {exc}  guid={src_guid[:8]}"
            )
        else:
            if measured is not None and enrichments is not None:
                enrichments.append(measured)
    return []


# Issue #16: categories whose UPDATE compare/write is projected into the
# TARGET's writing-system space first (see `_to_update_target_space`). Scoped
# to the two categories #16 promoted to Tier A, which were measured live; the
# same WS-space mismatch can affect other categories' vernacular multistrings
# and is a follow-up, not silently widened here.
_UPDATE_TARGET_SPACE_CATEGORIES = frozenset((
    GrammarCategory.PHONEMES,
    GrammarCategory.PH_ENVIRONMENT,
))

# Keys excluded from the PHONEMES scalar UPDATE. Feature wiring for created
# AND natural-key-matched phonemes is owned by the T081 tail pass
# (`categories._wire_phoneme_features`), which runs after the run's
# PHONOLOGICAL_FEATURES have landed. The Phase-1 overwrite loop runs BEFORE the
# leaf ADDs, so writing `Features` here raised FP_ParameterError for every
# feature this run had yet to create (measured live, #16) and aborted the rest
# of that phoneme's fields. `FeaturesGuid` is identity only: the owned
# FsFeatStruc of a starter-matched phoneme legitimately has another GUID, and
# flexicon never re-applies it.
_PHONEME_UPDATE_DEFERRED_KEYS = ("Features", "FeaturesGuid")


def _to_update_target_space(cat, src_props, tgt_props, ws_map, target):
    """Project an UPDATE's (src_props, tgt_props) into the target's WS space.

    Without this, every re-run of a phoneme re-UPDATEs (measured live on
    Mbugwe -> an Ejagham-derived sandbox, #16), because:

    * a source multistring is keyed by SOURCE WS ids (``{"mgz": "j"}``) and the
      target's by TARGET ids (``{"etu": "j"}``) -- equal data that never
      compares equal. flexicon writes the source alt through ``ws_map``, so the
      compare must too. The scalar ``BasicIPASymbol`` is keyed under each
      project's own default vernacular, so it ALWAYS hits this;
    * a source alt whose WS the target lacks (``mgz-fonipa-x-emic``) is
      could never be written (flexicon skips it) yet would stay "fillable"
      forever. It is dropped from compare and write, and logged here at INFO
      since flexicon never sees it;
    * a target holding every source alt PLUS its own extras compares unequal
      as a whole dict although UPDATE has nothing to write;
    * PHONEMES ``Features``/``FeaturesGuid`` -- see
      `_PHONEME_UPDATE_DEFERRED_KEYS`.

    Pure apart from reading the target's WS ids; returns new dicts.
    """
    ws_map = ws_map or {}

    def _norm(ws_id):
        # Mirrors flexicon's `_resolve_ws_handle` fallback (case / "_" vs "-").
        return str(ws_id).lower().replace("_", "-")

    target_ws_by_norm = None
    try:
        target_ws_by_norm = {_norm(w.Id): w.Id
                             for w in target.WritingSystems.GetAll()}
    except Exception:  # noqa: BLE001 -- unknown target WS set: keep every alt
        target_ws_by_norm = None

    dropped_ws = set()

    def _project(props):
        out = {}
        for key, val in props.items():
            if isinstance(val, dict):
                mapped = {}
                for ws_id, text in val.items():
                    tgt_id = ws_map.get(ws_id, ws_id)
                    if target_ws_by_norm is not None:
                        tgt_id = target_ws_by_norm.get(_norm(tgt_id))
                        if tgt_id is None:
                            dropped_ws.add(ws_id)
                            continue
                    mapped[tgt_id] = text
                out[key] = mapped
            else:
                out[key] = val
        return out

    src = _project(src_props or {})
    if dropped_ws:
        # These alts never reach flexicon, so its own miss-case warning cannot
        # fire; say it here. INFO, not WARNING: it repeats on every re-run.
        _log.info(
            "UPDATE [%s]: source alt(s) in WS %s have no target writing system;"
            " not compared or written", cat.value, sorted(dropped_ws))
    tgt = dict(tgt_props or {})
    # Per-alt satisfaction: UPDATE never removes a target-only alt, so a target
    # that already carries every source alt verbatim (plus extras, e.g. a
    # starter phoneme's `en` Name) needs no write. Comparing whole dicts would
    # call it "fillable" on every run.
    for key, val in src.items():
        tval = tgt.get(key)
        if (isinstance(val, dict) and val and isinstance(tval, dict)
                and all(tval.get(ws) == text for ws, text in val.items())):
            src[key] = tval
    if cat == GrammarCategory.PHONEMES:
        for key in _PHONEME_UPDATE_DEFERRED_KEYS:
            src.pop(key, None)
            tgt.pop(key, None)
    return src, tgt


# Map from GrammarCategory to the project-level ops accessor name (attribute
# on the source/target FLExProject) that exposes GetSyncableProperties /
# ApplySyncableProperties for UPDATE-capable categories.
#
# Only categories whose flexicon Operations class exposes both methods are
# listed.  Others (ENTRY, AFFIXES, STEMS, etc.) use identity_remap paths that
# are already handled by _execute_layer3 / the main overwrite loop.
_OPS_ACCESSOR_FOR_CATEGORY: dict = {
    GrammarCategory.GRAM_CATEGORIES:        "POS",
    # Issue #22 Part 1: `pos_plan_action` stamps pick-driven POS merges with
    # GrammarCategory.POS (the GRAM_CATEGORIES alias). Without this entry every
    # such PlannedOverwrite(write_mode="merge") hit the "not wired" no-op, so
    # a POS the Preview said it would merge received zero field writes.
    GrammarCategory.POS:                    "POS",
    GrammarCategory.INFLECTION_FEATURES:    "InflectionFeatures",
    GrammarCategory.INFLECTION_CLASSES:     "InflectionClasses",
    GrammarCategory.FEATURE_STRUCT_TYPES:   "FeatureStructTypes",
    GrammarCategory.PHON_FEAT_TYPES:        "PhonFeatStructTypes",
    GrammarCategory.STEM_NAMES:             "StemNames",
    GrammarCategory.EXCEPTION_FEATURES:     "ExceptionFeatures",
    GrammarCategory.NATURAL_CLASSES:        "NaturalClasses",
    GrammarCategory.PHONOLOGICAL_FEATURES:  "PhonologicalFeatures",
    # NOTE: flexicon's FLExProject exposes this Operations class as
    # `.PhonRules`, never `.PhonologicalRules` (see FLExProject.py's
    # `PhonRules` property) -- this entry previously pointed at a
    # nonexistent attribute, silently no-op'ing (see the "ops accessor ...
    # not found" Warning branch below) for any PHONOLOGICAL_RULES overwrite
    # that reached the generic path. Corrected as part of task 7 (feature
    # 037); moot in practice since a "structural_rebuild" write_mode
    # PlannedOverwrite is intercepted above before reaching this table, but
    # left correct rather than latent for any future write_mode.
    GrammarCategory.PHONOLOGICAL_RULES:     "PhonRules",
    GrammarCategory.PHONEMES:               "Phonemes",
    GrammarCategory.PH_ENVIRONMENT:         "Environments",
    GrammarCategory.STRATA:                 "Strata",
}


def _find_obj_by_guid(ops, guid_str: str):
    """Return the first object in ops.GetAll() whose GUID matches `guid_str`.

    Returns None if not found or if GetAll raises.
    """
    try:
        for obj in ops.GetAll():
            try:
                obj_guid = str(getattr(obj, "Guid", None) or "").lower()
            except Exception:
                continue
            if obj_guid == guid_str.lower():
                return obj
    except Exception:
        pass
    return None


def _lcm_slot(slot):
    """Issue #130: a raw `IMoInflAffixSlot` for `SlotsRC.Add`.

    `POS.GetAffixSlots` yields flexicon `AffixSlot` wrappers; `_unwrap` only
    honours a `.concrete` attribute they do not have (it falls through
    `__getattr__` to the LCM object), so it returned the WRAPPER and
    `SlotsRC.Add(wrapper)` raised "No method matches given arguments for
    ICollection`1.Add" on a live LCM. Found by the #130 live proof; offline
    fakes pass through unchanged.
    """
    inner = _unwrap(slot)
    inner = getattr(inner, "_obj", None) or inner
    try:
        from .categories import _cast_lcm
    except ImportError:  # flat layout
        from categories import _cast_lcm  # type: ignore
    return _cast_lcm(inner, "IMoInflAffixSlot")


def _overwrite_msa_slots(src_ia, new_ia, target_slots_by_guid, *, src_msa_guid,
                         entry_guid, report_sink, dropped, affix_slot_links):
    """Issue #130: re-sync an inflectional MSA's `SlotsRC` for OVERWRITE without
    ever losing the membership the target already had.

    The pre-fix code did `SlotsRC.Clear()` then an unguarded `Add` per source
    slot, silently skipping slots missing from the target: a raising or no-op
    `Add`, or an unresolved slot, ERASED membership and reported nothing.

    Sequence (reuses the PR #120 `WRITE_FAILED` / `_slots_absent_on_readback`
    machinery):
      1. Snapshot the target's current members.
      2. Resolve every source slot. If ANY is unresolved, DO NOT clear: the
         snapshot is kept (never destroy membership to write a partial set),
         and a SLOT_MISSING record + Skip(DEPENDENCY_UNRESOLVED) +
         DroppedItemRecord name each unresolved slot GUID.
      3. Otherwise Clear, then Add each slot in its own try/except.
      4. Read `SlotsRC` back once. On any raise or absence, restore the
         snapshot (Clear, re-Add, read back) and record WRITE_FAILED naming
         the unwritten slots and whether the restore held.
    A clean overwrite appends no record. Returns a list of Skips.
    """
    if __package__:
        from .categories import (_slots_absent_on_readback, _guid_str_from,
                                 _append_dropped_once)
        from .models import AffixSlotLinkOutcome, AffixSlotLinkRecord
    else:
        from categories import (  # type: ignore
            _slots_absent_on_readback, _guid_str_from, _append_dropped_once)
        from models import AffixSlotLinkOutcome, AffixSlotLinkRecord  # type: ignore
    skips = []
    src_slot_objs = list(src_ia.SlotsRC)
    src_slot_guids = tuple(_guid_str_from(sl) for sl in src_slot_objs)

    # 1. snapshot BEFORE any write. If we cannot even read it, write nothing.
    try:
        snapshot = list(new_ia.SlotsRC)
    except Exception as exc:  # noqa: BLE001 -- reported
        report_sink.Warning(
            f"  IMoInflAffMsa slot re-sync skipped: could not snapshot the "
            f"target SlotsRC ({type(exc).__name__}: {exc}); left unchanged")
        return skips
    snapshot_pairs = [(sl, _guid_str_from(sl)) for sl in snapshot]

    # 2. resolve.
    resolved = []
    unresolved = []
    for sg in src_slot_guids:
        tgt_slot = target_slots_by_guid.get(sg)
        if tgt_slot is None:
            unresolved.append(sg)
        else:
            resolved.append((tgt_slot, sg))
    if unresolved:
        for sg in unresolved:
            skips.append(Skip(
                category=GrammarCategory.AFFIX_TEMPLATES, source_guid=sg,
                reason=SkipReason.DEPENDENCY_UNRESOLVED,
                detail=(f"slot_guid={sg} not in target, so OVERWRITE of "
                        f"msa_guid={src_msa_guid} left its SlotsRC unchanged "
                        "rather than clear it to write a partial set")))
            _append_dropped_once(dropped, DroppedItemRecord(
                owner_kind="MoInflAffMsa", owner_guid=src_msa_guid,
                owner_label="", field_name="SlotsRC", item_name="",
                item_guid=sg,
                reason=("slot unresolved in target; OVERWRITE kept the "
                        "target's existing SlotsRC membership")))
        affix_slot_links.append(AffixSlotLinkRecord(
            msa_guid=src_msa_guid, outcome=AffixSlotLinkOutcome.SLOT_MISSING,
            entry_guid=entry_guid, source_slot_guids=src_slot_guids,
            unresolved_slot_guids=tuple(unresolved)))
        report_sink.Warning(
            f"  IMoInflAffMsa {src_msa_guid[:8]} slot re-sync skipped: "
            f"slot(s) {', '.join(g[:8] for g in unresolved)} unresolved in "
            "target; existing slot membership kept")
        return skips

    # 3. guarded Clear + Add.
    errors = []
    cleared_ok = True
    try:
        new_ia.SlotsRC.Clear()
    except Exception as exc:  # noqa: BLE001
        cleared_ok = False
        errors.append(f"Clear {type(exc).__name__}: {exc}")
    for tgt_slot, sg in resolved:
        try:
            new_ia.SlotsRC.Add(tgt_slot)
        except Exception as exc:  # noqa: BLE001 -- collected per slot
            errors.append(f"Add {sg}: {type(exc).__name__}: {exc}")

    # 4. read back once.
    unwritten = _slots_absent_on_readback(new_ia, resolved, errors)
    if not unwritten and not cleared_ok and resolved:
        unwritten = [g for _, g in resolved]
    if not unwritten:
        return skips

    # restore the snapshot (best effort) and verify the restore too.
    restore_errors = []
    try:
        new_ia.SlotsRC.Clear()
    except Exception as exc:  # noqa: BLE001
        restore_errors.append(f"Clear {type(exc).__name__}: {exc}")
    for sl, g in snapshot_pairs:
        try:
            new_ia.SlotsRC.Add(sl)
        except Exception as exc:  # noqa: BLE001
            restore_errors.append(f"Add {g}: {type(exc).__name__}: {exc}")
    missing_after = _slots_absent_on_readback(new_ia, snapshot_pairs,
                                              restore_errors)
    try:
        now = {_guid_str_from(p) for p in new_ia.SlotsRC}
        extras = sorted(now - {g for _, g in snapshot_pairs})
    except Exception:  # noqa: BLE001
        extras = []
    restored = not missing_after and not extras and not restore_errors
    restore_note = ("pre-overwrite SlotsRC membership restored" if restored
                    else "RESTORE FAILED: pre-overwrite membership "
                         f"({len(snapshot_pairs)} slot(s)) NOT fully "
                         f"recovered, missing={missing_after}")
    detail = "; ".join(errors + restore_errors) or "slot absent on read-back"
    detail = f"{detail}; {restore_note}"
    _log.warning("OVERWRITE msa_guid=%s: slot(s) %s not in SlotsRC on "
                 "read-back (%s)", src_msa_guid, ", ".join(unwritten), detail)
    for sg in unwritten:
        skips.append(Skip(
            category=GrammarCategory.AFFIX_TEMPLATES, source_guid=sg,
            reason=SkipReason.DEPENDENCY_UNRESOLVED,
            detail=(f"slot_guid={sg} not in SlotsRC on read-back after "
                    f"OVERWRITE of msa_guid={src_msa_guid} ({detail})")))
    affix_slot_links.append(AffixSlotLinkRecord(
        msa_guid=src_msa_guid, outcome=AffixSlotLinkOutcome.WRITE_FAILED,
        entry_guid=entry_guid, source_slot_guids=src_slot_guids,
        unwritten_slot_guids=tuple(unwritten), detail=detail))
    return skips


def _execute_overwrite(overwrite, source, target, report_sink, tag: ImportResidueTag,
                       interactive_session=None, ws_map=None, dropped=None,
                       resolver_cache=None, affix_slot_links=None):
    """Apply a single PlannedOverwrite: look up the target object by GUID,
    pull source's syncable properties, and apply them via flexicon's
    `ApplySyncableProperties`.

    Pre-overwrite snapshot in residue (FR-106) is currently NOT recorded —
    queued for Phase 1.1. The existing Carrier-A/B tag is still applied so
    the user can see the run_id that touched this object.

    `dropped` (Feature 024 US2, FIX 1a): the per-run `DroppedItemRecord`
    collector (`execute()`'s `_dropped`, shared with the ADD/closure path).
    `affix_slot_links` (issue #130): the per-run `AffixSlotLinkRecord`
    collector (`execute()`'s `_affix_slot_links`); the MSA branch appends a
    record ONLY when its SlotsRC re-sync did not land (see
    `_overwrite_msa_slots`). Defaults to a call-local list.
    `resolver_cache` (same feature): the per-run GUID -> resolved/created
    target item cache (`execute()`'s `_resolver_cache`, FR-012 idempotency,
    also shared with the ADD/closure path). Both default to a fresh,
    call-local collector/cache when not supplied (e.g. a direct unit-test
    call) so every branch remains callable standalone.

    Return value: a list combining this call's skip records (`ow_skips`,
    unchanged from before) with any `DroppedItemRecord`(s) appended to
    `dropped` DURING this call (not the collector's full accumulated
    history — relevant when a shared, cross-call `dropped` list is passed
    in). Every record is ALSO mutated into `dropped` in place regardless of
    what the return value contains, so a caller that folds the shared
    collector into a RunReport separately (`execute()`'s
    `extra_dropped_items=tuple(_dropped)`) never double-counts it.
    """
    if dropped is None:
        dropped = []
    if affix_slot_links is None:
        affix_slot_links = []
    if resolver_cache is None:
        resolver_cache = {}
    cat = overwrite.category
    src_guid = overwrite.source_guid
    tgt_guid = overwrite.target_guid

    # Feature 038 T036 -- the resolve half of the resolve-or-create path.
    #
    # Every branch below re-answers "which target object is this?" with its
    # OWN category-scoped linear scan, and every one of those scans ends in
    # `Warning(...)` + `return` on a miss -- the resolve-only failure mode:
    # the plan's work for this object is discarded, and in export mode the
    # `_NullReportSink` discards the Warning too, so nothing records that it
    # happened. Those scans are also NARROWER than the question: the template
    # and slot lookups are scoped to an owner POS, so a correct
    # `PlannedOverwrite` whose `owner_guid` disagrees with the destination
    # hierarchy misses an object that is demonstrably present.
    #
    # When the plan carries a `match_basis` it has ALREADY decided which
    # destination object this is, by GUID or by a roster-admitted natural key.
    # Resolving it once here means each branch's scan becomes an optimisation
    # rather than a second, weaker opinion: on a scan miss the branch falls
    # back to the object the PLAN named, instead of abandoning the item.
    #
    # A record that names a destination the target does not hold raises
    # `PlannedDestinationError` from here -- deliberately BEFORE any write, and
    # deliberately not caught, so the run stops rather than half-applying.
    # With `match_basis=None` (every plan built today) this is a single
    # attribute read returning `DESTINATION_UNDETERMINED`, and every
    # `dest.resolved` test below is False, leaving each branch bit-for-bit
    # as it was.
    dest = planned_destination_for(overwrite, target)

    # Per-category lookup + apply
    if cat == GrammarCategory.POS:
        src_obj = _find_source_pos_by_guid(source, src_guid)
        # T106: DELIBERATELY identity-only. `overwrite.target_guid` is already a
        # DESTINATION GUID -- every producer either verified the GUID present in
        # the target (`preview._emit_present_outcome`,
        # `categories._plan_gold_reserved_edit`) or took it from the matched
        # destination object itself (`categories._plan_natural_key_match`, which
        # is exactly the post-T091 reuse case). Routing this through the natural
        # key would re-derive a decision Preview already made and recorded, and
        # could override a recorded reuse with a fresh name match. Principle III.
        tgt_obj = _find_target_pos_by_guid(target, tgt_guid)
        if tgt_obj is None and dest.resolved:
            tgt_obj = _cast_existing_to_pos(_unwrap(dest.obj))
        if src_obj is None or tgt_obj is None:
            report_sink.Warning(f"  [OW] POS {src_guid[:8]} not found in source or target")
            return
        tgt_pre_props = strip_residue_props(target.POS.GetSyncableProperties(tgt_obj))
        src_props = _dedupe_custom_fields(
            source.POS.GetSyncableProperties(src_obj), tgt_pre_props
        )
        log = _resolve_decisions_for(overwrite, interactive_session)
        src_props, tagged, ow_skips = _resolve_and_tag(
            src_props, tgt_pre_props, tag, log,
            GrammarCategory.POS, overwrite.target_guid, tag.run_id,
        )
        target.POS.ApplySyncableProperties(tgt_obj, src_props, ws_map=ws_map)
        cache = getattr(target, "Cache")
        apply_residue(tgt_obj, cache.DefaultAnalWs, tagged)
        report_sink.Info(f"  POS overwritten  guid={src_guid}")
        return ow_skips

    if cat == GrammarCategory.AFFIX_TEMPLATES:
        src_tpl_wrap = _find_source_template_by_guid(source, src_guid)
        if src_tpl_wrap is None:
            report_sink.Warning(f"  [OW] Template {src_guid[:8]} vanished in source")
            return
        # owner_guid carries the POS GUID; if absent (early Phase 0 plans),
        # fall back to pulled_in_by[0].
        owner_pos_guid = getattr(overwrite, "owner_guid", "") or (
            overwrite.pulled_in_by[0] if overwrite.pulled_in_by else ""
        )
        if not owner_pos_guid:
            report_sink.Warning(f"  [OW] Template {src_guid[:8]} has no owner POS reference")
            return
        # T106: `owner_guid` / `pulled_in_by[0]` on a template overwrite is the
        # OWNING CATEGORY'S SOURCE GUID (`preview._emit_template` fills it from
        # `src_verb_guid`), so the natural key is the right second question.
        tgt_pos = _target_pos_for_source_guid(
            target, owner_pos_guid,
            src_pos=_find_source_pos_by_guid(source, owner_pos_guid),
            source_handle=source)
        tgt_tpl = None
        if tgt_pos is not None:
            tgt_tpl = _find_target_template_by_guid(target, tgt_pos, tgt_guid)
        if tgt_tpl is None and dest.resolved:
            # The owner-scoped scan above cannot see a template whose owning
            # POS in the DESTINATION differs from the source's -- exactly the
            # re-parented case 038 measured for categories. The plan already
            # resolved the template itself, so use it rather than dropping the
            # overwrite over a disagreement about its parent.
            tgt_tpl = _cast_existing_to_template(_unwrap(dest.obj))
        if tgt_pos is None and tgt_tpl is None:
            report_sink.Warning(f"  [OW] Template owner POS {owner_pos_guid[:8]} not in target")
            return
        if tgt_tpl is None:
            report_sink.Warning(f"  [OW] Template {tgt_guid[:8]} not in target")
            return
        tgt_pre_props = strip_residue_props(target.MorphRules.GetSyncableProperties(tgt_tpl))
        src_props = source.MorphRules.GetSyncableProperties(src_tpl_wrap)
        target.MorphRules.ApplySyncableProperties(tgt_tpl, src_props, ws_map=ws_map)
        cache = getattr(target, "Cache")
        apply_residue(tgt_tpl, cache.DefaultAnalWs, tag.with_snapshot(tgt_pre_props))
        report_sink.Info(f"  Template overwritten  guid={src_guid}")
        return

    if cat == GrammarCategory.SLOTS:
        owner_pos_guid = getattr(overwrite, "owner_guid", "")
        # T106: same source-side owner GUID as the template branch above. The
        # un-owner-scoped fallback below still finds the slot when this misses,
        # which is why this site cost nothing measurable -- but the fallback is
        # a whole-hierarchy scan, not a correctness guarantee.
        tgt_pos = _target_pos_for_source_guid(
            target, owner_pos_guid,
            src_pos=_find_source_pos_by_guid(source, owner_pos_guid),
            source_handle=source) if owner_pos_guid else None
        tgt_slot = None
        if tgt_pos is not None:
            tgt_slot = _find_target_slot_by_guid(target, tgt_pos, tgt_guid)
        if tgt_slot is None:
            # Fallback: scan every POS's slots
            for pos in target.POS.GetAll(recursive=True):
                concrete = _unwrap(pos)
                for s in target.POS.GetAffixSlots(concrete):
                    if _guid_str(_unwrap(s)) == tgt_guid:
                        tgt_slot = _unwrap(s)
                        break
                if tgt_slot is not None:
                    break
        if tgt_slot is None and dest.resolved:
            tgt_slot = _cast_existing_to_slot(_unwrap(dest.obj))
        if tgt_slot is None:
            report_sink.Warning(f"  [OW] Slot {tgt_guid[:8]} not in target")
            return
        # Slot has no flexicon SyncableProperties wrapper exposed for it
        # via the MorphRules accessor on slots specifically; Phase 1.0 only
        # re-applies the residue tag here. Phase 1.1 will copy the slot
        # name + description via direct property access (Name multistring).
        cache = getattr(target, "Cache")
        apply_residue(tgt_slot, cache.DefaultAnalWs, tag)
        report_sink.Info(f"  Slot tagged (overwrite, no syncable props)  guid={src_guid}")
        return

    # ENTRY (Phase 0 verb-vertical) and the entry-shaped Phase 3c leaf
    # categories AFFIXES / STEMS (FR-338 / SC-302) share the identical
    # entry-level overwrite path — no category-specific merge code: the
    # same _dedupe_custom_fields + _resolve_and_tag generic helpers run for
    # all three, so per-field conflicts surface to Phase 2 uniformly.
    #
    # LATENCY NOTE (feature 024 US2, this cycle): this branch is currently
    # UNREACHED in production for ANY of the three categories. The verb-
    # vertical planner that builds ENTRY `PlannedOverwrite`s is gated off
    # (`_VERB_VERTICAL_ENABLED = False`), and the active leaf-dispatch
    # planners for AFFIXES/STEMS (`affixes_plan_action`/`stems_plan_action`
    # in `categories.py`) return `Skip(ALREADY_PRESENT_BY_GUID)` for any
    # GUID-present item -- they never emit a `PlannedOverwrite` that would
    # route here. A future reader should NOT assume the FIX 1/2/3 reference-
    # field handling below (or any Preview overwrite-drop reporting) is
    # exercised by a live run today; it is correctness hardening for when
    # this path is enabled, not an active-data-loss fix. See
    # `tests/unit/test_overwrite_blanking.py` for the unit-level coverage
    # that keeps it correct in the meantime.
    if cat in (GrammarCategory.ENTRY, GrammarCategory.AFFIXES, GrammarCategory.STEMS):
        from SIL.LCModel import ICmObject  # lazy
        tgt_entry = None
        for te in target.LexEntry.GetAll():
            if str(ICmObject(_unwrap(te)).Guid).lower() == tgt_guid:
                tgt_entry = _unwrap(te)
                break
        if tgt_entry is None and dest.resolved:
            tgt_entry = _cast_existing_to_lexentry(_unwrap(dest.obj))
        if tgt_entry is None:
            report_sink.Warning(f"  [OW] LexEntry {tgt_guid[:8]} not in target")
            return
        # Find the source entry to read its syncable properties.
        src_entry = None
        for se in source.LexEntry.GetAll():
            if str(ICmObject(_unwrap(se)).Guid).lower() == src_guid:
                src_entry = _unwrap(se)
                break
        if src_entry is None:
            report_sink.Warning(f"  [OW] Source LexEntry {src_guid[:8]} vanished")
            return
        tgt_pre_props = strip_residue_props(target.LexEntry.GetSyncableProperties(tgt_entry))
        src_props = _dedupe_custom_fields(
            source.LexEntry.GetSyncableProperties(src_entry), tgt_pre_props
        )
        # Feature 024 US2 (FIX 1, root-cause option (a)): strip the
        # entry-level reference fields UNCONDITIONALLY (empty or not)
        # BEFORE the raw ApplySyncableProperties call -- see the
        # `_OVERWRITE_ENTRY_REF_FIELDS` module comment above `execute()` and
        # `_strip_ref_fields`'s own docstring for why this must not be
        # empty-only (double-application defect).
        _strip_ref_fields(src_props, _OVERWRITE_ENTRY_REF_FIELDS)
        log = _resolve_decisions_for(overwrite, interactive_session)
        src_props, tagged, ow_skips = _resolve_and_tag(
            src_props, tgt_pre_props, tag, log,
            cat, overwrite.target_guid, tag.run_id,
        )
        target.LexEntry.ApplySyncableProperties(
            tgt_entry, src_props, ws_map=ws_map,
            fill_gaps=(getattr(overwrite, "write_mode", "overwrite") == "merge"),
        )
        # Route the stripped fields through the SAME generic resolver the
        # ADD/closure path uses (LINK/CREATE+ancestors/UPDATE/REPORT_DROPPED)
        # -- an empty/unset source value is a documented no-op there
        # (`decide_reference` returns None), never a blank/clear.
        if __package__:
            from .categories import _apply_reference_fields as _apply_ref_fields
        else:
            from categories import _apply_reference_fields as _apply_ref_fields  # type: ignore
        _dropped_before = len(dropped)
        _apply_ref_fields(
            "LexEntry", src_entry, tgt_entry, target, tagged, resolver_cache,
            dropped,
            skip_fields=_overwrite_ref_skip_fields("LexEntry", _OVERWRITE_ENTRY_REF_FIELDS),
            ws_map=ws_map, source=source, owner_guid=src_guid,
            # Feature 024 US2 FIX 3: OVERWRITE replaces these collections
            # (target becomes exactly the resolved non-empty source
            # members), not a union-add -- see
            # `categories._apply_reference_fields`'s `clear_before_add`
            # docstring for why this is safe to gate here without touching
            # the ADD/closure path's default union semantic.
            clear_before_add=True,
        )
        cache = getattr(target, "Cache")
        apply_residue(tgt_entry, cache.DefaultAnalWs, tagged)
        report_sink.Info(f"  LexEntry overwritten ({cat.value})  guid={src_guid}")
        return list(ow_skips) + list(dropped[_dropped_before:])

    if cat == GrammarCategory.SENSE:
        # LATENCY NOTE (feature 024 US2, this cycle): this branch is
        # currently UNREACHED in production. SENSE is not one of the
        # active leaf-dispatch categories in `categories.py` at all (only
        # AFFIXES/STEMS/entry-shaped categories are dispatched today), and
        # the verb-vertical planner that would build a SENSE
        # `PlannedOverwrite` is gated off (`_VERB_VERTICAL_ENABLED =
        # False`). A future reader should NOT assume the FIX 1/2/3
        # reference-field handling below is exercised by a live run today;
        # it is correctness hardening for when this path is enabled, not an
        # active-data-loss fix. See
        # `tests/unit/test_overwrite_blanking.py` for the unit-level
        # coverage that keeps it correct in the meantime.
        #
        # owner_guid is the parent entry GUID; look up the entry first,
        # then iterate its senses.
        from SIL.LCModel import ICmObject  # lazy
        owner_entry_guid = getattr(overwrite, "owner_guid", "")
        if not owner_entry_guid:
            report_sink.Warning(f"  [OW] Sense {src_guid[:8]} has no owner entry reference")
            return
        tgt_entry = None
        for te in target.LexEntry.GetAll():
            if str(ICmObject(_unwrap(te)).Guid).lower() == owner_entry_guid:
                tgt_entry = _unwrap(te)
                break
        if tgt_entry is None:
            report_sink.Warning(f"  [OW] Sense owner entry {owner_entry_guid[:8]} not in target")
            return
        tgt_sense = None
        for s in target.LexEntry.GetSenses(tgt_entry):
            if str(ICmObject(_unwrap(s)).Guid).lower() == tgt_guid:
                tgt_sense = _unwrap(s)
                break
        if tgt_sense is None:
            report_sink.Warning(f"  [OW] LexSense {tgt_guid[:8]} not in target")
            return
        # Source-side lookup
        src_sense = None
        src_entry = None
        for se in source.LexEntry.GetAll():
            if str(ICmObject(_unwrap(se)).Guid).lower() == owner_entry_guid:
                src_entry = _unwrap(se)
                break
        if src_entry is not None:
            for s in source.LexEntry.GetSenses(src_entry):
                if str(ICmObject(_unwrap(s)).Guid).lower() == src_guid:
                    src_sense = _unwrap(s)
                    break
        if src_sense is None:
            report_sink.Warning(f"  [OW] Source LexSense {src_guid[:8]} vanished")
            return
        tgt_pre_props = strip_residue_props(target.Senses.GetSyncableProperties(tgt_sense))
        src_props = _dedupe_custom_fields(
            source.Senses.GetSyncableProperties(src_sense), tgt_pre_props
        )
        # Feature 024 US2 (FIX 1, root-cause option (a)): strip the
        # sense-level reference fields UNCONDITIONALLY (empty or not)
        # BEFORE the raw ApplySyncableProperties call -- see the
        # `_OVERWRITE_SENSE_REF_FIELDS` module comment above `execute()` and
        # `_strip_ref_fields`'s own docstring for why this must not be
        # empty-only (double-application defect).
        # `_raw_sense_type_guid` is captured for the targeted fallback below
        # (a raw GUID present only in the flat props dict, with no matching
        # live object on `src_sense` for the object-attribute-driven
        # resolver to see).
        _raw_sense_type_guid = src_props.get("SenseTypeRA")
        _strip_ref_fields(src_props, _OVERWRITE_SENSE_REF_FIELDS)
        log = _resolve_decisions_for(overwrite, interactive_session)
        src_props, tagged, ow_skips = _resolve_and_tag(
            src_props, tgt_pre_props, tag, log,
            GrammarCategory.SENSE, overwrite.target_guid, tag.run_id,
        )
        target.Senses.ApplySyncableProperties(tgt_sense, src_props, ws_map=ws_map)
        # Route the stripped fields through the SAME generic resolver the
        # ADD/closure path uses (LINK/CREATE+ancestors/UPDATE/REPORT_DROPPED)
        # -- an empty/unset source value is a documented no-op there
        # (`decide_reference` returns None), never a blank/clear.
        if __package__:
            from .categories import (
                _apply_reference_fields as _apply_ref_fields,
                _append_dropped_once as _append_dropped,
            )
        else:
            from categories import (  # type: ignore
                _apply_reference_fields as _apply_ref_fields,
                _append_dropped_once as _append_dropped,
            )
        _dropped_before = len(dropped)
        _apply_ref_fields(
            "LexSense", src_sense, tgt_sense, target, tagged, resolver_cache,
            dropped,
            skip_fields=_overwrite_ref_skip_fields("LexSense", _OVERWRITE_SENSE_REF_FIELDS),
            ws_map=ws_map, source=source, owner_guid=owner_entry_guid,
            # Feature 024 US2 FIX 3: OVERWRITE replaces these collections
            # (target becomes exactly the resolved non-empty source
            # members), not a union-add -- see
            # `categories._apply_reference_fields`'s `clear_before_add`
            # docstring for why this is safe to gate here without touching
            # the ADD/closure path's default union semantic.
            clear_before_add=True,
        )
        # Targeted fallback (documented deviation from pure option (a)): a
        # raw SenseTypeRA GUID that is present in the flat props dict but
        # has NO resolvable live object on `src_sense` (getattr returns
        # None) can never be seen by the object-attribute-driven resolver
        # call above -- `_iter_reference_items` reads `src_sense.SenseTypeRA`
        # directly, not the props dict, so it yields nothing for this shape.
        # Surface it explicitly rather than let it silently vanish once
        # stripped from `src_props` (FR-010, never-silent).
        if _raw_sense_type_guid and getattr(src_sense, "SenseTypeRA", None) is None:
            _append_dropped(dropped, DroppedItemRecord(
                owner_kind="LexSense",
                owner_guid=owner_entry_guid,
                owner_label="",
                field_name="SenseTypeRA",
                item_name="",
                item_guid=str(_raw_sense_type_guid),
                reason="unresolved custom SenseTypeRA reference (no source object available)",
            ))
        cache = getattr(target, "Cache")
        apply_residue(tgt_sense, cache.DefaultAnalWs, tagged)
        report_sink.Info(f"  LexSense overwritten  guid={src_guid}")
        return list(ow_skips) + list(dropped[_dropped_before:])

    if cat == GrammarCategory.MSA:
        from SIL.LCModel import ICmObject, ILexEntry, IMoInflAffMsa
        owner_entry_guid = getattr(overwrite, "owner_guid", "")
        if not owner_entry_guid:
            report_sink.Warning(f"  [OW] MSA {src_guid[:8]} has no owner entry reference")
            return
        # Locate target entry, then the target MSA on its MorphoSyntaxAnalysesOC.
        tgt_entry = None
        for te in target.LexEntry.GetAll():
            if str(ICmObject(_unwrap(te)).Guid).lower() == owner_entry_guid:
                tgt_entry = _unwrap(te)
                break
        if tgt_entry is None:
            report_sink.Warning(f"  [OW] MSA owner entry {owner_entry_guid[:8]} not in target")
            return
        tgt_msa = None
        for tmsa in ILexEntry(tgt_entry).MorphoSyntaxAnalysesOC:
            if str(ICmObject(tmsa).Guid).lower() == tgt_guid:
                tgt_msa = tmsa
                break
        if tgt_msa is None:
            report_sink.Warning(f"  [OW] Target MSA {tgt_guid[:8]} not found")
            return
        # Re-sync SlotsRC (slot membership may have shifted). Source MSA
        # lookup mirrors the planner's: find source entry, then matching MSA.
        src_entry = None
        for se in source.LexEntry.GetAll():
            if str(ICmObject(_unwrap(se)).Guid).lower() == owner_entry_guid:
                src_entry = _unwrap(se)
                break
        src_msa = None
        if src_entry is not None:
            for smsa in ILexEntry(src_entry).MorphoSyntaxAnalysesOC:
                if str(ICmObject(smsa).Guid).lower() == src_guid:
                    src_msa = smsa
                    break
        # Pre-overwrite snapshot: target's current SlotsRC + PartOfSpeechRA
        tgt_pre_props = {
            "slots": sorted(str(ICmObject(sl).Guid).lower()
                            for sl in IMoInflAffMsa(tgt_msa).SlotsRC),
            "pos": (str(ICmObject(IMoInflAffMsa(tgt_msa).PartOfSpeechRA).Guid).lower()
                    if IMoInflAffMsa(tgt_msa).PartOfSpeechRA is not None else None),
        }
        _msa_skips = []
        if src_msa is not None:
            src_ia = IMoInflAffMsa(src_msa)
            new_ia = IMoInflAffMsa(tgt_msa)
            # Build target slot index for the owner POS once
            from SIL.LCModel import IPartOfSpeech
            pos_obj = src_ia.PartOfSpeechRA
            if pos_obj is not None:
                pos_guid = str(ICmObject(pos_obj).Guid).lower()
                # T106: `pos_obj` is read off the SOURCE MSA, so `pos_guid` is
                # a source GUID and a GUID-only lookup answers "absent" for a
                # category T091 reused under a different identity. That miss
                # was SILENT: the `if tgt_pos is not None` below guards the
                # whole re-sync, so `SlotsRC` was left holding whatever it had
                # -- no Warning, no Skip, no DroppedItemRecord, and a
                # reference collection moves no census row, so
                # `total_shortfall` reads clean either way. Principle I's
                # exact shape. The source object IS in hand here, so the key
                # has everything it needs.
                tgt_pos = _target_pos_for_source_guid(
                    target, pos_guid, src_pos=pos_obj, source_handle=source)
                if tgt_pos is not None:
                    target_slots_by_guid = {}
                    for sl in target.POS.GetAffixSlots(tgt_pos):
                        _slot = _lcm_slot(sl)
                        target_slots_by_guid[_guid_str(_slot)] = _slot
                    # Issue #130: snapshot -> guarded Clear+Add -> read-back
                    # -> restore on failure. See `_overwrite_msa_slots`.
                    _msa_skips.extend(_overwrite_msa_slots(
                        src_ia, new_ia, target_slots_by_guid,
                        src_msa_guid=src_guid, entry_guid=owner_entry_guid,
                        report_sink=report_sink, dropped=dropped,
                        affix_slot_links=affix_slot_links))
                elif len(list(src_ia.SlotsRC)) > 0:
                    # T106: identity AND the natural key both failed, and the
                    # source MSA HAS slot membership to re-sync -- so this is a
                    # real, reportable miss rather than a no-op. Say so. The
                    # pre-T106 code returned here silently and left `SlotsRC`
                    # holding its old value, which is the one direction
                    # Principle I forbids. Guarded on a non-empty source
                    # `SlotsRC` so an MSA with nothing to sync does not
                    # manufacture a warning about a loss that cannot happen --
                    # the phantom-loss shape CLAUDE.md records for flexicon
                    # 4.5.1.
                    report_sink.Warning(
                        f"  IMoInflAffMsa slot re-sync skipped: owning category "
                        f"{pos_guid[:8]}… is not resolvable in the target by "
                        f"GUID or by natural key; slot membership left unchanged")
        cache = getattr(target, "Cache")
        apply_residue(tgt_msa, cache.DefaultAnalWs, tag.with_snapshot(tgt_pre_props))
        report_sink.Info(f"  IMoInflAffMsa overwritten  src={src_guid[:8]}  tgt={tgt_guid[:8]}")
        return _msa_skips

    if cat == GrammarCategory.ALLOMORPH:
        from SIL.LCModel import ICmObject, IMoAffixAllomorph
        owner_entry_guid = getattr(overwrite, "owner_guid", "")
        if not owner_entry_guid:
            report_sink.Warning(f"  [OW] Allomorph {src_guid[:8]} has no owner entry reference")
            return
        tgt_entry = None
        for te in target.LexEntry.GetAll():
            if str(ICmObject(_unwrap(te)).Guid).lower() == owner_entry_guid:
                tgt_entry = _unwrap(te)
                break
        if tgt_entry is None:
            report_sink.Warning(f"  [OW] Allomorph owner entry {owner_entry_guid[:8]} not in target")
            return
        tgt_allo = None
        for tallo in target.Allomorphs.GetAll(tgt_entry):
            if _guid_str(_unwrap(tallo)) == tgt_guid:
                tgt_allo = _unwrap(tallo)
                break
        if tgt_allo is None:
            report_sink.Warning(f"  [OW] Target allomorph {tgt_guid[:8]} not found")
            return
        # Source-side lookup for ApplySyncableProperties
        src_entry = None
        for se in source.LexEntry.GetAll():
            if str(ICmObject(_unwrap(se)).Guid).lower() == owner_entry_guid:
                src_entry = _unwrap(se)
                break
        src_allo = None
        if src_entry is not None:
            for sallo in source.Allomorphs.GetAll(src_entry):
                if _guid_str(_unwrap(sallo)) == src_guid:
                    src_allo = _unwrap(sallo)
                    break
        tgt_pre_props = strip_residue_props(target.Allomorphs.GetSyncableProperties(tgt_allo))
        ow_skips = []
        tagged = tag.with_snapshot(tgt_pre_props)
        if src_allo is not None:
            src_props = _dedupe_custom_fields(
                source.Allomorphs.GetSyncableProperties(src_allo), tgt_pre_props
            )
            log = _resolve_decisions_for(overwrite, interactive_session)
            src_props, tagged, ow_skips = _resolve_and_tag(
                src_props, tgt_pre_props, tag, log,
                GrammarCategory.ALLOMORPH, overwrite.target_guid, tag.run_id,
            )
            target.Allomorphs.ApplySyncableProperties(tgt_allo, src_props, ws_map=ws_map)
        cache = getattr(target, "Cache")
        apply_residue(tgt_allo, cache.DefaultAnalWs, tagged)
        report_sink.Info(f"  IMoAffixAllomorph overwritten  src={src_guid[:8]}  tgt={tgt_guid[:8]}")
        return ow_skips

    if cat == GrammarCategory.PH_ENVIRONMENT:
        tgt_env = _find_target_env_by_guid(target, tgt_guid)
        if tgt_env is None and dest.resolved:
            tgt_env = _cast_existing_to_environment(_unwrap(dest.obj))
        if tgt_env is None:
            report_sink.Warning(f"  [OW] PhEnvironment {tgt_guid[:8]} not in target")
            return
        src_env = None
        try:
            for e in source.Environments.GetAll():
                if _guid_str(_unwrap(e)) == src_guid:
                    src_env = _unwrap(e)
                    break
        except AttributeError:
            pass
        tgt_pre_props = {}
        try:
            tgt_pre_props = strip_residue_props(target.Environments.GetSyncableProperties(tgt_env))
        except AttributeError:
            pass
        if src_env is not None:
            try:
                src_props = source.Environments.GetSyncableProperties(src_env)
                target.Environments.ApplySyncableProperties(tgt_env, src_props, ws_map=ws_map)
            except AttributeError:
                pass
        cache = getattr(target, "Cache")
        apply_residue(tgt_env, cache.DefaultAnalWs, tag.with_snapshot(tgt_pre_props))
        report_sink.Info(f"  PhEnvironment overwritten  guid={src_guid}")
        return

    # GOLD_RESERVED categories: write_mode="merge" fill-gaps on Name/Abbreviation/Description.
    # These are the 6 GOLD_RESERVED categories introduced by spec 017. The
    # executor locates source+target items by GUID using the category's own iterator,
    # then fills empty-in-target WS slots from source for the 3 multistring fields.
    # write_mode="overwrite" falls through to the no-op (those overwrites are
    # generated by Phase 1 paths, not spec 017, and would need their own handler).
    #
    # PHON_FEAT_TYPES (coverage-content-fidelity-v2 Part B.4) is GOLD_RESERVED
    # per models.py, but is DELIBERATELY ABSENT here -- its plan_action (like
    # its MULTI_INSTANCE sibling FEATURE_STRUCT_TYPES) never calls
    # `_plan_gold_reserved_edit` and so never emits a write_mode="merge"
    # PlannedOverwrite; an already-present-by-GUID type is Skipped outright.
    # This mirrors POS's precedent: POS is also GOLD_RESERVED at Layer 1 but
    # absent from this set for the same structural reason (no per-category
    # opt-in into the merge-fill-gaps mechanism).
    _GOLD_RESERVED_CATS = {
        GrammarCategory.GRAM_CATEGORIES,
        GrammarCategory.INFLECTION_FEATURES,
        GrammarCategory.VARIANT_TYPES,
        GrammarCategory.COMPLEX_FORM_TYPES,
        GrammarCategory.SEMANTIC_DOMAINS,
        GrammarCategory.PHONOLOGICAL_FEATURES,
    }
    if cat in _GOLD_RESERVED_CATS and getattr(overwrite, "write_mode", "overwrite") == "merge":
        _execute_gold_reserved_merge(overwrite, source, target, report_sink,
                                     ws_map=ws_map)
        return

    # For other categories, Phase 1 just logs and skips the apply — the
    # extension lands as categories.py exposes ApplySyncableProperties for
    # each. The residue tag is still applied below for audit.
    report_sink.Info(f"  [OW] {cat.value} overwrite no-op  guid={src_guid}")


def _execute_gold_reserved_merge(overwrite, source, target, report_sink,
                                 ws_map=None):
    """Fill empty-in-target WS slots on a GOLD_RESERVED item (spec 017 FR-E08).

    Locates both the source item and the target item by GUID using the
    category's natural iterator, then for each of Name, Abbreviation,
    Description writes only those WS slots that are empty (None or '') in the
    target while non-empty in the source.  Slots where both have content are
    left untouched (per-WS conflict detection happened at plan time).

    This respects write_mode="merge" (fill-gaps-only) without calling
    ApplySyncableProperties — that path overwrites non-empty target slots.
    Instead we write directly via set_String on the multistring property.
    """
    cat = overwrite.category
    src_guid = overwrite.source_guid

    # Build per-category source/target iterators.
    def _iter_gram_categories(proj):
        if hasattr(proj, "POS"):
            try:
                return list(proj.POS.GetAll(recursive=True))
            except Exception:
                pass
        return []

    def _iter_inflection_features(proj):
        if hasattr(proj, "InflectionFeatures"):
            try:
                return list(proj.InflectionFeatures.FeatureGetAll())
            except Exception:
                pass
        return []

    def _iter_via_lexdb(accessor_name):
        def _fn(proj):
            try:
                lex_db = proj.Cache.LangProject.LexDbOA
                lst = getattr(lex_db, accessor_name, None)
            except Exception:
                return []
            if __package__:
                from .categories import _walk_possibilities as _wp
            else:
                from categories import _walk_possibilities as _wp  # type: ignore
            return _wp(lst)
        return _fn

    def _iter_semantic_domains(proj):
        try:
            lst = proj.Cache.LangProject.SemanticDomainListOA
        except Exception:
            return []
        if __package__:
            from .categories import _walk_possibilities as _wp
        else:
            from categories import _walk_possibilities as _wp  # type: ignore
        return _wp(lst)

    def _iter_phon_features(proj):
        if hasattr(proj, "PhonFeatures"):
            try:
                return list(proj.PhonFeatures.GetAll())
            except Exception:
                pass
        return []

    _iterators = {
        GrammarCategory.GRAM_CATEGORIES: _iter_gram_categories,
        GrammarCategory.INFLECTION_FEATURES: _iter_inflection_features,
        GrammarCategory.VARIANT_TYPES: _iter_via_lexdb("VariantEntryTypesOA"),
        GrammarCategory.COMPLEX_FORM_TYPES: _iter_via_lexdb("ComplexEntryTypesOA"),
        GrammarCategory.SEMANTIC_DOMAINS: _iter_semantic_domains,
        GrammarCategory.PHONOLOGICAL_FEATURES: _iter_phon_features,
    }

    iter_fn = _iterators.get(cat)
    if iter_fn is None:
        report_sink.Info(f"  [OW-MERGE] {cat.value}: no iterator registered, skipping {src_guid[:8]}")
        return

    if __package__:
        from .categories import _guid_str_from as _gstr
    else:
        from categories import _guid_str_from as _gstr  # type: ignore

    src_obj = None
    for obj in iter_fn(source):
        if _gstr(obj) == src_guid:
            src_obj = obj
            break
    if src_obj is None:
        report_sink.Warning(f"  [OW-MERGE] {cat.value} source {src_guid[:8]} not found")
        return

    tgt_obj = None
    for obj in iter_fn(target):
        if _gstr(obj) == src_guid:
            tgt_obj = obj
            break
    if tgt_obj is None:
        report_sink.Warning(f"  [OW-MERGE] {cat.value} target {src_guid[:8]} not found")
        return

    # Enumerate writing systems from source, PAIRED WITH THE TARGET HANDLE for
    # the same (mapped) WS Id. WS handles are per-project and NOT portable --
    # measured live, 999000002 is `en` in `Ngoreme FLEx` and `ngq` in
    # `Ngoreme Target`. Writing a raw source handle into the target mislabels
    # the string, or leaves a handle `WritingSystemManager.Get` cannot resolve
    # -- which throws inside `XMLBackendProvider.Commit` at CloseProject and
    # discards the WHOLE unit of work (feature 038 T024g).
    ws_map = ws_map or {}
    try:
        tgt_handle_by_id = {w.Id: w.Handle for w in target.WritingSystems.GetAll()}
    except Exception:
        tgt_handle_by_id = {}
    ws_list = []
    try:
        for ws_obj in source.WritingSystems.GetAll():
            src_id = getattr(ws_obj, "Id", str(ws_obj))
            tgt_id = ws_map.get(src_id, src_id)  # identity when unmapped
            tgt_handle = tgt_handle_by_id.get(tgt_id)
            if tgt_handle is None:
                continue  # no counterpart target WS -> skip, never a wrong handle
            ws_list.append((src_id, ws_obj.Handle, tgt_handle))
    except Exception:
        pass

    if not ws_list:
        report_sink.Info(
            f"  [OW-MERGE] {cat.value} {src_guid[:8]}: no WS info available, skipping"
        )
        return

    if __package__:
        from .texts import _is_dotnet_object
    else:
        from texts import _is_dotnet_object  # type: ignore

    # Issue #55: branch on WHAT the target multistring IS, not on whether
    # `TsStringUtils` imports. The import succeeding is a fact about the
    # PROCESS -- once anything has loaded flexicon (pythonnet + the SIL
    # assemblies) it succeeds for every object, and `MakeString` succeeds on
    # a plain `str`, so a duck-typed multistring was silently handed a real
    # .NET `ITsString`. A genuine .NET multistring gets an `ITsString`; any
    # other `set_String` receives the plain text. `TsStringUtils` is resolved
    # only when a .NET write actually needs it.
    _unresolved = object()
    tsu = _unresolved

    filled_count = 0
    for field_name in ("Name", "Abbreviation", "Description"):
        src_ms = getattr(src_obj, field_name, None)
        tgt_ms = getattr(tgt_obj, field_name, None)
        if src_ms is None or tgt_ms is None:
            continue
        for _ws_id, src_handle, tgt_handle in ws_list:
            try:
                src_ts = src_ms.get_String(src_handle)
                src_text = getattr(src_ts, "Text", None)
            except Exception:
                src_text = None
            if not src_text:
                continue
            try:
                tgt_ts = tgt_ms.get_String(tgt_handle)
                tgt_text = getattr(tgt_ts, "Text", None)
            except Exception:
                tgt_text = None
            if tgt_text:
                # Non-empty target slot: conflict (already reported at plan time).
                continue
            # Empty target slot -> fill it.
            is_live = _is_dotnet_object(tgt_ms)
            if is_live and tsu is _unresolved:
                try:
                    from SIL.LCModel.Core.Text import TsStringUtils as tsu
                except ImportError:
                    report_sink.Warning(
                        f"  [OW-MERGE] {cat.value} {src_guid[:8]}: "
                        f"LCM text utils unavailable"
                    )
                    return
            try:
                value = (tsu.MakeString(src_text, tgt_handle) if is_live
                         else src_text)
                tgt_ms.set_String(tgt_handle, value)
                filled_count += 1
            except Exception as exc:
                _log.exception(
                    "OW-MERGE: set_String FAILED (swallowed) category=%s guid=%s "
                    "field=%s ws=%s", cat.value, src_guid, field_name, tgt_handle,
                )
                report_sink.Warning(
                    f"  [OW-MERGE] {cat.value} {src_guid[:8]} "
                    f"{field_name}@ws={tgt_handle}: write failed: {exc}"
                )

    report_sink.Info(
        f"  [OW-MERGE] {cat.value} guid={src_guid[:8]}: filled {filled_count} WS slot(s)"
    )
