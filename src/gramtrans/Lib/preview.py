"""Preview-mode plan builder (constitution v5.0.0 Principle III).

`build_run_plan(context, selection, source, target)` walks the source closure
for the user's Selection and returns an immutable RunPlan. The walk is
READ-ONLY on both source and target — MUST NOT mutate anything (the unit test
`tests/unit/test_preview_no_writes.py` will enforce this with a fake LCM that
records any write attempt).

Phase 0 MVP scope (T-Spike): only the Verb vertical (POS → Template → Slots,
with Layer 3 MSA / Allomorph / Environment as the next slice). Subsequent
tasks (T039 leaf categories, T049 affixes, T051 templates, T051b MSAs) extend
this builder with the full FR-004 category set.
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Tuple

_log = logging.getLogger(__name__)

if __package__:
    from .models import (
        CategoryScope,
        ClosureEdge,
        CreateDefinitionAction,
        ExcludedLossy,
        GrammarCategory,
        IncompletenessRecord,
        MatchBasis,
        MatchBasisRecord,
        PlannedAction,
        PlannedOverwrite,
        RunContext,
        RunPlan,
        Selection,
        Skip,
        SkipReason,
        WSMapping,
    )
    from .ws_mapping import to_ws_map_dict
    from . import census as _census
    from . import matcher as _matcher
else:
    from ws_mapping import to_ws_map_dict  # type: ignore
    import census as _census  # type: ignore
    import matcher as _matcher  # type: ignore
    from models import (
        CategoryScope,
        ClosureEdge,
        CreateDefinitionAction,
        ExcludedLossy,
        GrammarCategory,
        IncompletenessRecord,
        MatchBasis,
        MatchBasisRecord,
        PlannedAction,
        PlannedOverwrite,
        RunContext,
        RunPlan,
        Selection,
        Skip,
        SkipReason,
        WSMapping,
    )


# ============================================================================
# Feature 038 T031 -- the plan-time match decision (constitution Principle III)
# ============================================================================
#
# WHY THIS LIVES IN THE PLAN BUILDER. Preview and Move must agree about which
# destination object a source object corresponds to. Before 038 they agreed by
# parallel construction: `preview.py` scanned for a GUID one way, `transfer.py`
# scanned for it another (`_idempotency_guard` uses `target.Object(guid)`, a
# cache lookup; the plan-side helpers use category-scoped linear scans), and
# `categories.py` a third. Three implementations of one question, and the two
# opposite failure modes 038 exists to remove -- create-anyway duplicating
# starter content, resolve-only dropping the analysis -- are exactly what you
# get when the plan and the executor answer it differently.
#
# So the whole decision is computed HERE, once, and travels on the plan as a
# `MatchBasisRecord`. The executor consumes it (T036) and adds no matching
# logic of its own. "Nothing about matching may be computed only in the
# executor" is the contract, and a `MatchBasisRecord` on every
# `PlannedAction` / `PlannedOverwrite` is how it is enforced: an object whose
# record says NATURAL_KEY was matched by name in the plan, and the executor
# has no licence to re-derive that and reach a different answer.
#
# BOTH STEPS RUN HERE. Step 1 is GUID identity (plus a previous run's
# `identity_remap`); step 2 is the roster-admitted natural key. `matcher`
# owns the ordering -- identity is authoritative and the key is consulted only
# when identity finds nothing -- and this module owns only the wiring: which
# candidates to offer, and which project's writing-system handle to read each
# side's name through.
#
# THE TWO PROJECTS HAVE DIFFERENT WRITING-SYSTEM HANDLES, AND THAT MATTERS.
# A handle is a per-project integer; the source's default-vernacular handle is
# meaningless in the destination. Reading a destination object's name through
# the source's handle does not raise -- it returns None, so every candidate
# key would silently evaluate to "this object has no key" and the whole
# natural-key step would quietly match nothing at all. `resolve_match` takes
# the two mappings separately for exactly this reason.


# WHO CALLS THIS, AND THE TWO SITES THAT DELIBERATELY DO NOT (T105).
#
# T031 landed this seam with no production caller. T092 measured the
# consequence: the question it answers was being answered FOUR more times in
# `categories.py` by open-coded `matcher.resolve_match` calls, and one of the
# four had already drifted -- it lost the enumeration-failure warning below and
# converted the ambiguity error this function propagates into a silent
# "unresolved". T092 kept the seam on that evidence and filed T105 to route the
# bypasses "or record per site why not". Both outcomes happened, so the list is
# written out here: an unexplained entry is how T092's condition returns.
#
# ROUTED (T105). Both hold a `RunContext`, so both reach this function without
# a signature change, and both routings are behaviour-preserving:
#
#   * `categories._process_referent_by_natural_key` -- reproduced the candidate
#     branch below line for line. Routing it is what recovers the
#     `_log.warning`, the ONE behaviour this change adds. It keeps its own
#     `except NaturalKeyAmbiguityError` at the call site: this function's
#     contract is what it RAISES, that caller's is what it does with the raise,
#     and the two were never the same question. Its docstring says which
#     reading won and on what measurement.
#   * `categories._plan_natural_key_match` -- supplies its caller's own
#     candidate enumeration through `candidates=`, which is the parameter's
#     purpose. It propagates ambiguity, agreeing with this function already.
#
# NOT ROUTED, AND WHY -- the deviation is load-bearing in both cases. Each
# takes the two project handles ALREADY RESOLVED rather than a `RunContext`, so
# routing them needs a handle-pair entry point on this seam. That entry point
# was considered and rejected, because each site also needs this function to
# SKIP two of the four services it exists to provide, which leaves nothing for
# it to do but forward its arguments:
#
#   * `categories._match_collection_child` (T044) -- answers "is this child
#     already in THIS collection?", so the registered project-wide scope is
#     wrong for it by design. More decisively, six of the seven POS-owned
#     collections hold classes with NO natural-key binding at all --
#     `MoInflAffixSlot`, `MoInflAffixTemplate`, `FsFeatDefn`, `MoStemName`,
#     `MoInflClass`, and `ReferenceFormsOC`, whose target type is `IFsFeatStruc`
#     (verified read-only via FLExToolsMCP against `IPartOfSpeech`). Only
#     `SubPossibilitiesOS` carries one: the slot is DECLARED `ICmPossibility`
#     and its runtime children under a category owner are `PartOfSpeech`, which
#     is why that site keys on the child's own `ClassName` rather than on the
#     slot's declared type. This function returns None for an unbound class --
#     correctly -- so routing that site would answer None for six collections
#     in seven, its caller would stop matching existing children, and run 2
#     would re-add every child that run 1 wrote. That is the exact SC-008
#     re-run defect T044 exists to prevent.
#   * `categories._resolve_target_pos_by_natural_key` (T032) -- enumerates
#     candidates with `_iter_pos`, i.e. `handle.POS.GetAll(recursive=True)`,
#     which both a live host and the host-free fakes answer. The registered
#     scope for `PartOfSpeech` is `census.objects_in_class`, which needs a live
#     `SIL.LCModel` repository interface and raises `CensusError` without one;
#     through the branch below that becomes "no candidates", so routing it with
#     the default scope would turn every host-free POS key match into a miss.
#     It is also the only site that reports `parent_divergence`, and its
#     `_resolve_target_pos` entry point is a pre-038 API with ten call sites
#     whose 038 parameters are keyword-only opt-ins, so threading a context in
#     is a sweep, not a re-point.
#
# THE LIVE-BEHAVIOUR CHANGE T092 ANTICIPATED IS REAL, AND IT LIVES IN THOSE
# TWO. T092 forecast that routing would change behaviour across every category
# planning a roster-admitted class and would need its own census. Measured
# against the code, the two ROUTED sites needed none -- they already reproduced
# this function's wiring exactly. The census T092 was reaching for is what the
# other two would have required, which is a second, independent reason they
# were not routed blind.
#
# `tests/unit/test_038_plan_match_decision.py` pins all of the above
# structurally: the caller set, the surviving bypass set with these reasons,
# and the fact that neither unrouted site has acquired a context.


#: The plan-time match decision is available only for classes that have BOTH
#: halves of the natural-key basis. For every other class this module keeps its
#: pre-038 GUID-only behaviour, which is a degradation and not an error.
def plan_match_decision(
    object_class: str,
    source_obj,
    context: RunContext,
    *,
    candidates=None,
    identity_remap=None,
):
    """The whole match decision for one source object, computed at plan time.

    Parameters:
        object_class:   LCM class name as 035's roster spells it.
        source_obj:     the source object being placed.
        context:        supplies both project handles.
        candidates:     the destination candidate scope. When None, it is
                        resolved through the class's own registered scope
                        function, which enumerates instances of EXACTLY that
                        class -- never the inheritance subtree.
        identity_remap: `{source_guid: target_guid}` from a previous run.

    Returns:
        A `matcher.MatchDecision`, or **None** when the class has no
        natural-key basis AND no candidate scope could be resolved -- that is,
        when this module has nothing to add over the caller's existing
        GUID-only lookup. None is a normal answer, not an error.

    Never raises for a data condition. `NaturalKeyAmbiguityError` is allowed
    through deliberately: an ambiguous key is a harness error the operator must
    see, not something to be absorbed into a silent miss.
    """
    binding = _matcher.natural_key_binding_for(object_class)
    if binding is None:
        return None

    if candidates is None:
        scope_fn = _matcher.NATURAL_KEY_SCOPE_FNS.get(binding.scope_fn_id)
        if scope_fn is None:
            return None
        try:
            candidates = list(scope_fn(context.target_handle))
        except Exception as exc:  # noqa: BLE001 -- see below
            # A scope that cannot be enumerated is reported as "no candidates",
            # never as an empty match that would license a create. The caller
            # still gets a decision whose basis is NONE and whose may_create
            # reflects the class rule, so the outcome is accounted for rather
            # than silently turned into a duplicate.
            _log.warning(
                "038 T031: destination scope %r for %s could not be enumerated "
                "(%s: %s) -- treating as no candidates, which reports a miss "
                "rather than matching on a partial scan",
                binding.scope_fn_id, object_class, type(exc).__name__, exc,
            )
            candidates = []

    return _matcher.resolve_match(
        object_class,
        source_obj,
        candidates,
        ws_handles=_ws_handles_for(context.target_handle),
        source_ws_handles=_ws_handles_for(context.source_handle),
        identity_remap=identity_remap,
    )


def _ws_handles_for(handle) -> dict:
    """`{ws_scope: writing-system handle}` for one project.

    A scope missing from the returned mapping means the key is NOT COMPUTABLE
    for that project -- for `PhPhoneme` that is the case the roster names
    explicitly, where the pre-run writing-system mapping did not produce a
    source -> target default vernacular. It is reported, never answered by
    falling back to a secondary writing system: matching a secondary
    vernacular would have fabricated 16 matches on `Yi Sichuan` alone.
    """
    return _matcher.ws_handles_for(handle)


#: The LCM class name for a `GrammarCategory`, where the correspondence is
#: UNAMBIGUOUS. `MatchBasisRecord.object_class` must be non-empty, and it is
#: the field `report.py` groups matches by, so a wrong or guessed class name is
#: worse than no record at all: it would put a match in another class's row.
#:
#: Only one-to-one categories appear here, and the omissions are deliberate:
#:
#: * `ALLOMORPH` covers both `MoStemAllomorph` and `MoAffixAllomorph`;
#: * `MSA` covers the four `Mo*Msa` subclasses;
#: * `NATURAL_CLASSES` covers `PhNCSegments` and `PhNCFeatures`, which 038's
#:   own roster keeps strictly apart -- they must never match each other, so
#:   collapsing them to one name here would undo that at the report layer;
#: * `VARIANT_TYPES` covers `LexEntryType` and `LexEntryInflType`, the same
#:   problem again;
#: * `INFLECTION_FEATURES` covers `FsClosedFeature` and `FsComplexFeature`.
#:
#: A category absent from this map yields NO record rather than a guessed one.
#: A caller that knows better passes `object_class=` explicitly.
_LCM_CLASS_FOR_CATEGORY = {
    GrammarCategory.POS: "PartOfSpeech",
    GrammarCategory.GRAM_CATEGORIES: "PartOfSpeech",
    GrammarCategory.SLOTS: "MoInflAffixSlot",
    GrammarCategory.AFFIX_TEMPLATES: "MoInflAffixTemplate",
    GrammarCategory.INFLECTION_CLASSES: "MoInflClass",
    GrammarCategory.PH_ENVIRONMENT: "PhEnvironment",
    GrammarCategory.PHONEMES: "PhPhoneme",
    GrammarCategory.STEM_NAMES: "MoStemName",
    GrammarCategory.SEMANTIC_DOMAINS: "CmSemanticDomain",
    GrammarCategory.STRATA: "MoStratum",
    GrammarCategory.FEATURE_STRUCT_TYPES: "FsFeatStrucType",
    GrammarCategory.PHON_FEAT_TYPES: "FsFeatStrucType",
}


def lcm_class_for_category(category) -> str:
    """The LCM class name for a category, or "" when it is not one-to-one."""
    return _LCM_CLASS_FOR_CATEGORY.get(category, "")


def match_basis_for_present_by_guid(object_class: str, source_guid: str,
                                    target_guid: str):
    """The `MatchBasisRecord` for a caller that has ALREADY proven a GUID hit.

    Several plan paths establish "the target already holds this GUID" through
    their own category-scoped scan and never need the natural-key step, since
    identity is authoritative and short-circuits. They still owe the plan a
    record, because a `PlannedOverwrite` with no `match_basis` is
    indistinguishable in the report from one whose basis was never determined.
    """
    return MatchBasisRecord(
        basis=MatchBasis.IDENTITY,
        object_class=object_class,
        source_guid=source_guid,
        target_guid=target_guid,
        candidate_count=1,
    )


# ============================================================================
# Feature 024 US2 (OVERWRITE-path Preview surfacing, FIX 1a)
# ============================================================================
#
# Mirrors `transfer._OVERWRITE_SENSE_REF_FIELDS` / `_OVERWRITE_ENTRY_REF_FIELDS`
# (duplicated here rather than cross-imported, matching this module's existing
# "Re-imported helpers from preview.py — kept here to avoid a circular import"
# convention in transfer.py -- see that module's `_lex_sense_msa` for
# precedent): the reference fields the OVERWRITE-path executor routes through
# the generic resolver instead of the raw blank-on-empty ApplySyncableProperties
# copy. Used ONLY to populate `PlannedOverwrite.reference_decisions` below --
# Preview never writes (Principle III); the read-only `_decide_reference_fields`
# pass is safe here.
_OVERWRITE_SENSE_REF_FIELDS = frozenset(
    {"SenseTypeRA", "DoNotPublishInRC", "DoNotShowMainEntryInRC"}
)
_OVERWRITE_ENTRY_REF_FIELDS = frozenset(
    {"DoNotPublishInRC", "DoNotShowMainEntryInRC"}
)


def _overwrite_reference_decisions(owner_class, owner_guid, src_obj, target,
                                    keep_fields, source=None):
    """Read-only `decide_reference` pass over `keep_fields` only (the
    OVERWRITE-path resolver's actual scope, see `_OVERWRITE_*_REF_FIELDS`
    above) for a single ENTRY/SENSE `PlannedOverwrite` -- populates
    `PlannedOverwrite.reference_decisions` so Preview shows Link/Create/
    Update/Report *before* Move ever writes (Principle III), the same
    guarantee `PlannedAction.reference_decisions` gives the ADD path.

    Uses a call-local `resolver_cache`/`dropped` (this function has no
    `RunContext` to read a per-run collector from -- the verb-vertical
    planner functions that call this predate the context-based leaf-category
    plan_action functions). Never raises: any resolver failure yields an
    empty tuple, matching `categories._plan_entry_reference_decisions`'s own
    fail-soft posture for the identical duck-typing-gap class of failure.
    """
    if __package__:
        from .categories import _decide_reference_fields
        from . import references as _references
    else:
        from categories import _decide_reference_fields  # type: ignore
        import references as _references  # type: ignore
    try:
        skip_fields = frozenset(
            spec.field_name for spec in _references.field_specs_for(owner_class)
        ) - keep_fields
        return _decide_reference_fields(
            owner_class, owner_guid, src_obj, target,
            resolver_cache={}, dropped=[], skip_fields=skip_fields, source=source,
        )
    except (AttributeError, TypeError, KeyError):
        return ()


# ============================================================================
# Public API
# ============================================================================


# ============================================================================
# Feature 038 (FR-014, FR-015, FR-018) -- dependency-closure materialisation
# ============================================================================


def _closure_kind_lookup(registry: dict) -> dict:
    """Map ``(dependent_category, dependency_category)`` to the registry row
    that authorises that edge.

    The walk hands back refs, not relationship names, so materialising a
    `ClosureEdge` means recovering which `DependencyKind` authorised each
    ref. The registry is the only thing that knows, and it is also the only
    thing that may authorise an edge at all (FR-018).

    An ambiguous pair -- two registered kinds claiming the same
    (dependent, dependency) category pair -- raises. Guessing which kind
    produced an edge would put an unaudited relationship into a plan under
    another relationship's `verified_by`, which is exactly the substitution
    FR-018 exists to prevent.
    """
    lookup: dict = {}
    for kind, entry in (registry or {}).items():
        src_cat = entry.get("category")
        dep_cat = entry.get("dependency_category")
        key = (src_cat, dep_cat)
        if key in lookup and lookup[key][0] is not kind:
            raise ValueError(
                "Feature 038 FR-018: closure registry is ambiguous -- "
                + repr(lookup[key][0]) + " and " + repr(kind) + " both claim "
                "the category pair " + repr(key) + ". An edge whose "
                "DependencyKind cannot be determined must not reach a plan."
            )
        lookup[key] = (
            kind,
            bool(entry.get("verified", True)),
            entry.get("verified_by", ""),
        )
    return lookup


def _materialise_closure_edges(visit_order, pulled_in_by, registry) -> tuple:
    """Turn `closure.walk`'s `(visit_order, pulled_in_by)` into `ClosureEdge`s.

    FR-018 gate: this RAISES on any edge whose `verified` is False rather
    than planning from it. An unverified dependency edge that silently
    changes what gets transferred is the failure mode FR-018 exists to
    prevent, so it must fail loudly at plan time -- before Move writes
    anything -- not degrade to a warning nobody reads.

    With `CLOSURE_EDGES_VERIFIED` empty (its shipped state) the walk pulls
    nothing in, every ref is a seed with no parents, and this returns `()`:
    a no-op by construction.
    """
    lookup = _closure_kind_lookup(registry)
    edges = []
    seeds = {ref for ref in visit_order if not pulled_in_by.get(ref)}
    for ref in visit_order:
        parents = pulled_in_by.get(ref) or ()
        for parent in parents:
            key = (parent[0], ref[0])
            row = lookup.get(key) or lookup.get((parent[0], None))
            if row is None:
                # The walk cannot produce an edge no registry row authorised
                # -- closure_dependencies_for() only ever calls registered
                # producers. Reaching here means the registry changed under
                # us mid-walk, which is a harness error, not a data case.
                raise ValueError(
                    "Feature 038 FR-018: closure produced an edge "
                    + repr(parent) + " -> " + repr(ref) + " that no registry "
                    "entry authorises. Every edge must name the relationship "
                    "that admitted it."
                )
            kind, verified, verified_by = row
            if not verified:
                raise ValueError(
                    "Feature 038 FR-018: refusing to build a plan from the "
                    "UNVERIFIED closure edge " + repr(parent) + " -> "
                    + repr(ref) + " (" + repr(kind) + "). Each dependency "
                    "relationship must be verified on its own evidence "
                    "before it may influence a plan."
                )
            edges.append(ClosureEdge(
                dependent=parent,
                dependency=ref,
                kind=kind,
                verified=True,
                origin="chosen" if ref in seeds else "pulled_in",
                verified_by=verified_by,
            ))
    return tuple(edges)


def _walk_verified_closure(context, selection, actions, overwrites) -> tuple:
    """Run the verified-edge closure walk over what the plan already decided.

    Seeds are the items the plan is transferring -- the user's actual
    choices -- so `closure.walk`'s seed semantics hold: a directly selected
    item is `origin="chosen"` and is never reported as pulled in by
    something else.

    Fail-soft on wiring problems (a duck-typed test double without a real
    source handle) but NEVER on an FR-018 violation: a ValueError raised by
    the gate below propagates, because that is the whole point of the gate.
    """
    if __package__:
        from . import categories as _categories
        from . import closure as _closure
    else:  # pragma: no cover - flat sys.path (FLExTools) import shape
        import categories as _categories  # type: ignore
        import closure as _closure  # type: ignore

    registry = getattr(_categories, "CLOSURE_EDGES_VERIFIED", {}) or {}
    if not registry:
        # Nothing is verified, so nothing may influence the plan. Skip the
        # walk entirely rather than doing work whose result must be empty.
        _log.debug(
            "build_run_plan: closure registry empty -- no dependency edge is "
            "verified (FR-018); closure contributes nothing to this plan"
        )
        return ()

    seeds = []
    for item in list(actions) + list(overwrites):
        ref = (item.category, item.source_guid)
        if ref not in seeds:
            seeds.append(ref)

    dep_fn = _categories.closure_dependencies_for(context, selection)
    visit_order, pulled_in_by = _closure.walk(seeds, dep_fn)
    # topological() is called for its ordering contract (dependencies before
    # dependents); the order itself is consumed by the executor, while the
    # edges below are what the plan and report carry.
    _closure.topological(visit_order, pulled_in_by)
    return _materialise_closure_edges(visit_order, pulled_in_by, registry)


def _dispatch_index(category, dispatch_order):
    """Position of `category` in the leaf-dispatch order, or None."""
    try:
        return dispatch_order.index(category)
    except ValueError:
        return None


def _insert_in_dispatch_order(members, item, dispatch_order):
    """Insert `item` into `members` keeping leaf-dispatch order.

    `transfer.execute` walks `plan.actions` IN ORDER (transfer.py:516), so a
    dependency appended at the end is created AFTER the item that wires to
    it. The leaf loop already emits its members in `_LEAF_DISPATCH_CATEGORIES`
    order, so inserting before the first member of a later category keeps the
    whole list in that order and leaves every existing member's relative
    position untouched.
    """
    idx = _dispatch_index(item.category, dispatch_order)
    if idx is None:
        members.append(item)
        return
    for pos, existing in enumerate(members):
        existing_idx = _dispatch_index(existing.category, dispatch_order)
        if existing_idx is not None and existing_idx > idx:
            members.insert(pos, item)
            return
    members.append(item)


def _pull_in_is_deselected(selection, category, guid) -> bool:
    """Did the user turn this pulled-in dependency off? (FR-016, T071)

    Reuses the two knobs that already exist rather than adding a third
    (research.md R3): the per-item set (`Selection.excluded_deps` via
    `is_dep_excluded`) and the whole-category scope
    (`Selection.scope_for` -> `CategoryScope.NONE`, which is also what the
    back-compatible `include_closure=False` resolves to).
    """
    if selection is None:
        return False
    try:
        if selection.is_dep_excluded(guid):
            return True
    except AttributeError:
        pass
    try:
        return selection.scope_for(category) == CategoryScope.NONE
    except AttributeError:
        return False


def _pull_in_piece_resolver(context, selection):
    """Build the `(category, guid) -> source piece` resolver the pull-in uses.

    Extracted from `_plan_pulled_in_items` by T073 for one reason: the
    `IncompletenessRecord`s it emits have to LABEL both ends of an edge
    ("Verb", "Subject prefix"), and the labels come from the same source
    pieces the pull-in already resolves. One resolver, one enumeration cache,
    shared by both readers -- a second resolver would enumerate every category
    twice and could disagree with the first about what a ref names.

    Indexed the same way `categories.closure_dependencies_for._pieces_for`
    does, with one deliberate difference: the fallback enumeration passes
    `selection=None`. A pulled-in item is BY DEFINITION one the user did not
    select, so a category whose `enumerate_source` narrows to the user's picks
    (`pos_enumerate_source`, every `leaf_picks_for` filter) would hide exactly
    the piece the closure needs.
    """
    if __package__:
        from . import categories as _categories
    else:  # pragma: no cover - flat sys.path (FLExTools) import shape
        import categories as _categories  # type: ignore

    _piece_cache: dict = {}

    def _piece_for(category, guid):
        for sel in (selection, None):
            key = (category, sel is not None)
            if key not in _piece_cache:
                index: dict = {}
                try:
                    bundle = _categories.LEAF_CATEGORIES[category]
                    for piece in bundle["enumerate_source"](context, sel) or ():
                        g = _categories._guid_str_from(piece)
                        if g and g not in index:
                            index[g] = piece
                except Exception as exc:  # noqa: BLE001 - best-effort, reported below
                    _log.warning(
                        "closure pull-in: could not enumerate source pieces "
                        "for %s (%s) -- its pulled-in items are reported "
                        "unresolved", getattr(category, "value", category), exc,
                    )
                    index = {}
                _piece_cache[key] = index
            piece = _piece_cache[key].get(str(guid).lower())
            if piece is not None:
                return piece
        return None

    return _piece_for


def _pull_in_label(piece_for, ref) -> str:
    """Display label for one closure endpoint, never empty.

    `references._item_label` is the existing best-effort Name reader (the one
    `DroppedItemRecord.item_name` uses); the fallback is the console form of
    the ref itself, because an `IncompletenessRecord` whose two labels are
    blank tells the reader which GUIDs are involved and nothing about which
    ITEMS -- and a record the user cannot act on is not a report (SC-010).
    """
    if __package__:
        from . import references as _references
    else:  # pragma: no cover - flat sys.path (FLExTools) import shape
        import references as _references  # type: ignore

    category, guid = ref
    label = ""
    try:
        piece = piece_for(category, str(guid).lower())
        if piece is not None:
            label = _references._item_label(piece) or ""
    except Exception:  # noqa: BLE001 - a label is never worth failing a plan
        label = ""
    if label:
        return label
    return getattr(category, "value", str(category)) + " " + str(guid)[:8]


def _deselected_dependency_is_in_the_destination(
        context, ws_mapping, piece_for, category, guid) -> bool:
    """Feature 038 T093 -- is a REFUSED dependency nevertheless already in the
    destination, so the dependent's reference still resolves?

    WHY THIS EXISTS. `_plan_pulled_in_items` suppresses a deselected ref
    BEFORE its planner runs -- which is what makes "a deselected dependency is
    not planned" true and is correct for the plan -- so no
    `ALREADY_PRESENT_BY_*` skip is ever emitted on that path and
    `_plan_incompleteness` had nothing to consult. It therefore called every
    deselected dependency missing, including the ones sitting in the
    destination already. Measured on `Mbugwe LizzieHC practice`: 2 of the 5
    pulled-in POSes are already there (T070 planned them as OVERWRITEs), and 8
    of T073's 35 records named one of them. A report that cries loss where
    there was none teaches the reader to stop reading it -- the same
    phantom-loss shape CLAUDE.md records for flexicon 4.5.1.

    WHY IT IS THE PLANNER AND NOT A GUID PROBE. A bare
    `guid in target` check is Defect G3's exact shape -- `ALREADY_PRESENT_BY_
    GUID` taken without a field-identity comparison, the premise this feature
    exists to remove. This asks the category's OWN `plan_action`, the same
    matcher that decides ADD-vs-OVERWRITE for every non-deselected ref, and
    keeps nothing but its verdict:

      * `PlannedOverwrite`      -- matched an existing target object: present.
      * `Skip(ALREADY_PRESENT_*)` -- matched, nothing to write: present.
      * `PlannedAction`         -- an ADD: NOT present.
      * anything else, or a raise -- unknown, therefore NOT present.

    NOTHING IS PLANNED AND NOTHING IS SKIPPED as a result. The verdict is
    read and the result discarded, so `_plan_pulled_in_items` still emits the
    `DEPENDENCY_DESELECTED` skip it always emitted and T071's measured
    composition is unchanged -- a deselected dependency is still refused, it
    is just no longer reported as MISSING when it is not.

    UNKNOWN RESOLVES TO "REPORT IT". A planner that raises leaves the record
    standing: over-reporting one item is recoverable, and Principle I's
    failure is the silent one.
    """
    if __package__:
        from . import categories as _categories
    else:  # pragma: no cover - flat sys.path (FLExTools) import shape
        import categories as _categories  # type: ignore

    try:
        bundle = _categories.LEAF_CATEGORIES[category]
    except KeyError:
        return False
    try:
        piece = piece_for(category, guid)
    except Exception:  # noqa: BLE001 - a probe never fails a plan
        return False
    if piece is None:
        return False
    try:
        result = bundle["plan_action"](piece, context, ws_mapping)
    except Exception as exc:  # noqa: BLE001 - a probe never fails a plan
        _log.debug(
            "T093 presence probe: %s plan_action raised for %s (%s); the "
            "dependency is reported missing rather than assumed present",
            getattr(category, "value", category), guid, exc,
        )
        return False
    if isinstance(result, PlannedOverwrite):
        return True
    if isinstance(result, Skip):
        return getattr(result, "reason", None) in _DEPENDENCY_PRESENT_SKIPS
    return False


def _plan_pulled_in_items(context, selection, ws_mapping, edges,
                          actions, overwrites, skips, dispatch_order,
                          piece_for=None, deselected_but_present=None):
    """Feature 038 T070/T071 (FR-014, FR-015, FR-016) -- give every pulled-in
    dependency a plan member, marked as pulled in rather than chosen.

    WHAT THIS CLOSES. T067-T069 registered five closure edges and measured
    them against two live corpora, and T069's census asserted -- as the thing
    that made two-hop closure safe to land ahead of this task -- that the
    pulled-in items were NOT in the plan: an AFFIX_TEMPLATES-only selection
    produced 53 edges naming 23 distinct pulled-in refs and `actions` holding
    nothing but templates. The walk knew what was needed and the plan
    transferred none of it, which is FR-014 unmet.

    NO NEW SURFACE (research.md R3). The mark is `pulled_in_by` on the plan
    member -- the field `report.build_from_plan` already counts into
    `CategoryReport.closure_pulled_in` and `Lib/ui/stats_panel.py` already
    renders. Deselection is `Selection.excluded_deps` / `scope_for`, and a
    deselected dependency emits the `SkipReason.DEPENDENCY_DESELECTED` that
    the Phase 2 foundational work defined for this case and left with no
    emitter.

    ORDER. Members are inserted in leaf-dispatch order, not walk order, so a
    pulled-in POS is created before the affix that wires to it and is
    positionally indistinguishable from one the user selected directly.

    NEVER SILENT (FR-023). A ref whose own category cannot enumerate a source
    piece for it -- T089's live shape -- becomes a
    `SkipReason.DEPENDENCY_UNRESOLVED` skip rather than a quiet omission.

    Returns the edge tuple, re-stamped with `deselected=True` on every edge
    whose dependency the user turned off. `_plan_incompleteness` (T073) reads
    that flag to say which items therefore ARRIVE INCOMPLETE -- this function
    reports the missing DEPENDENCY, that one reports the DEPENDENTS.

    T093: `deselected_but_present`, when a set is passed, collects every
    refused ref that is nevertheless ALREADY IN THE DESTINATION
    (`_deselected_dependency_is_in_the_destination`). It is an OUT parameter
    rather than a return value or a `Skip` on purpose -- the refusal is still
    a refusal and still carries `DEPENDENCY_DESELECTED`, so this changes no
    plan member and no skip; it only gives `_plan_incompleteness` the fact it
    could not otherwise learn.
    """
    if not edges:
        return edges

    import dataclasses as _dc

    if __package__:
        from . import categories as _categories
    else:  # pragma: no cover - flat sys.path (FLExTools) import shape
        import categories as _categories  # type: ignore

    planned = set()
    for item in list(actions) + list(overwrites):
        planned.add(
            (item.category, str(getattr(item, "source_guid", "") or "").lower())
        )

    # Walk order, first-seen wins. The value is every dependent that asked for
    # this ref: a POS pulled in by three affixes names all three, because
    # "who needs this" is what makes a later deselection explainable.
    pullers: dict = {}
    for edge in edges:
        if edge.origin != "pulled_in":
            continue
        ref = (edge.dependency[0], str(edge.dependency[1]).lower())
        parent_guid = str(edge.dependent[1]).lower()
        bucket = pullers.setdefault(ref, [])
        if parent_guid not in bucket:
            bucket.append(parent_guid)

    if not pullers:
        return edges

    _piece_for = (
        piece_for if piece_for is not None
        else _pull_in_piece_resolver(context, selection)
    )

    deselected_refs = set()
    for ref, parents in pullers.items():
        category, guid = ref
        if ref in planned:
            # Already in the plan because its own category was selected: the
            # user CHOSE it. Restamping would overstate the closure's
            # contribution in the counter the report renders.
            continue
        if _pull_in_is_deselected(selection, category, guid):
            deselected_refs.add(ref)
            # T093: refused, but is it already THERE? The refusal stands
            # either way (the skip below is unchanged); the answer decides
            # only whether the dependents are reported as arriving INCOMPLETE.
            if deselected_but_present is not None and (
                    _deselected_dependency_is_in_the_destination(
                        context, ws_mapping, _piece_for, category, guid)):
                deselected_but_present.add(ref)
            skips.append(Skip(
                category=category,
                source_guid=guid,
                reason=SkipReason.DEPENDENCY_DESELECTED,
                detail=(
                    "closure dependency deselected by the user; needed by "
                    + ", ".join(p[:8] for p in parents)
                ),
            ))
            continue
        try:
            bundle = _categories.LEAF_CATEGORIES[category]
        except KeyError:
            bundle = None
        piece = _piece_for(category, guid) if bundle is not None else None
        if piece is None:
            skips.append(Skip(
                category=category,
                source_guid=guid,
                reason=SkipReason.DEPENDENCY_UNRESOLVED,
                detail=(
                    "closure pulled this in but "
                    + getattr(category, "value", str(category))
                    + " could not enumerate a source object for it; needed by "
                    + ", ".join(p[:8] for p in parents)
                ),
            ))
            continue
        try:
            result = bundle["plan_action"](piece, context, ws_mapping)
        except Exception as exc:  # noqa: BLE001 - planner failure becomes a skip
            skips.append(Skip(
                category=category,
                source_guid=guid,
                reason=SkipReason.DEPENDENCY_UNRESOLVED,
                detail=(
                    "closure pull-in: plan_action raised "
                    + type(exc).__name__ + ": " + str(exc)
                ),
            ))
            continue
        if isinstance(result, Skip):
            skips.append(result)
            continue
        if isinstance(result, (PlannedAction, PlannedOverwrite)):
            marked = _dc.replace(result, pulled_in_by=tuple(parents))
            target_list = (
                overwrites if isinstance(result, PlannedOverwrite) else actions
            )
            _insert_in_dispatch_order(target_list, marked, dispatch_order)
            planned.add(ref)
        elif result is not None:
            # CreateDefinitionAction and anything else a category may grow:
            # planned unmarked rather than dropped (it has no `pulled_in_by`).
            _insert_in_dispatch_order(actions, result, dispatch_order)
            planned.add(ref)

    if not deselected_refs:
        return edges
    return tuple(
        _dc.replace(edge, deselected=True)
        if (edge.dependency[0], str(edge.dependency[1]).lower())
        in deselected_refs else edge
        for edge in edges
    )


#: Skip reasons under which a pulled-in dependency IS satisfied after all: the
#: object the dependent needs is ALREADY IN THE DESTINATION, so the reference
#: resolves and nothing is incomplete. Counting these as unsatisfiable would
#: make FR-017's report fire loudest on the case where nothing was lost --
#: exactly the phantom-loss failure the flexicon 4.5.1 note in CLAUDE.md
#: records for natural-class features.
_DEPENDENCY_PRESENT_SKIPS = frozenset({
    SkipReason.ALREADY_PRESENT_BY_GUID,
    SkipReason.ALREADY_PRESENT_BY_IDENTITY,
})


def _closure_cycle_groups(edges) -> dict:
    """Refs that sit in a dependency CYCLE, each mapped to its whole cycle.

    Feature 038 T073, the third `IncompletenessRecord.cause`. `closure.walk`
    is cycle-TOLERANT by construction (it dedups on `(category, guid)`, so it
    cannot loop) and `closure.topological` DETECTS a cycle -- `if
    len(result) != len(visit_order)` -- and then throws the finding away,
    emitting the survivors "by rank to keep output total" and telling nobody.
    That is this feature's recurring shape once more: a signal that exists and
    is read at a level where it cannot do its job. Rather than change
    `topological`'s contract (its callers want a total order), T073 recovers
    the fact from the EDGES, which is where the plan and the report both
    already read.

    Tarjan's SCC, iterated rather than recursed because a source project's
    closure depth is data, not a constant. A component of one is a cycle only
    when it carries a self-loop (an item that depends on itself).

    Arc direction is "needs": `dependent -> dependency`. A cycle is therefore
    a set of items that each, transitively, need one another.
    """
    graph: dict = {}
    for edge in edges:
        dependent = (edge.dependent[0], str(edge.dependent[1]).lower())
        dependency = (edge.dependency[0], str(edge.dependency[1]).lower())
        graph.setdefault(dependent, [])
        graph.setdefault(dependency, [])
        if dependency not in graph[dependent]:
            graph[dependent].append(dependency)

    index: dict = {}
    low: dict = {}
    on_stack: dict = {}
    stack: list = []
    counter = 0
    groups: dict = {}

    for root in list(graph):
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, pos = work[-1]
            if pos == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack[node] = True
            descended = False
            succs = graph[node]
            while pos < len(succs):
                nxt = succs[pos]
                pos += 1
                if nxt not in index:
                    work[-1] = (node, pos)
                    work.append((nxt, 0))
                    descended = True
                    break
                if on_stack.get(nxt):
                    low[node] = min(low[node], index[nxt])
            if descended:
                continue
            work.pop()
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1 or node in graph[node]:
                    whole = frozenset(component)
                    for member in component:
                        groups[member] = whole
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return groups


def _plan_incompleteness(edges, actions, overwrites, skips, label_of=None,
                         already_present_refs=()):
    """Feature 038 T073 (FR-017, SC-010) -- one `IncompletenessRecord` per
    item that WILL ARRIVE in the destination missing something it needs.

    WHAT THIS CLOSES. T070/T071 put the pulled-in items in the plan and made
    them refusable, and T071 wrote `ClosureEdge.deselected` -- 53 of 53 edges
    under a full deselection. Nothing read it. A user who unticked a
    dependency got a `DEPENDENCY_DESELECTED` skip for the DEPENDENCY (correct,
    and T071's own measurement) and not one word about the ITEMS that still
    transfer and now arrive unwired. That is FR-017 unmet, and it is the same
    shape for the eighth time: a written signal read where it cannot do its
    job.

    THE GATE IS "DOES IT ARRIVE". A record is emitted only when the DEPENDENT
    is in `actions` or `overwrites` -- an item this run is actually writing.
    An item that is not being written is not "left incomplete"; it is
    dropped-with-reason, and its own `Skip` already reports it. Emitting both
    would double-count one loss under two buckets and would state, of an
    object that never reaches the destination, that it "arrives incomplete".
    Concretely, under the templates-only full deselection this turns 53 edges
    into 35 records: the 18 `SLOT_TO_POS` edges name slots that are themselves
    deselected, so the slots do not arrive at all and their POS is reported
    once -- on the slot's own skip -- not twice.

    THE DEPENDENCY IS SATISFIED THREE WAYS, not one: it is being written
    (`actions`/`overwrites`), or it is ALREADY in the destination (an
    `ALREADY_PRESENT_BY_*` skip, `_DEPENDENCY_PRESENT_SKIPS`), or -- the case
    that pays for deriving this from plan membership rather than from the
    skips -- neither, which is `unsatisfiable` whether or not any skip was
    emitted. `_plan_pulled_in_items` has one silent exit (a `plan_action`
    returning None plans nothing and skips nothing), and reading the PLAN
    instead of the skip list means that hole is reported anyway.

    CAUSE PRECEDENCE: `deselected` > `cycle` > `unsatisfiable`. The user's own
    action is the most actionable explanation there is, so it names itself
    even when the deselected item also happens to sit in a cycle.

    T093 -- "ALREADY THERE" OUTRANKS EVERY CAUSE, because it is not a cause.
    Precedence orders EXPLANATIONS for an incompleteness; it cannot decide
    whether there is one. A dependency that sits in the destination already is
    one the dependent's reference resolves against, whether the user refused
    to re-transfer it, whether it sits in a cycle, or neither -- so presence is
    tested first and ends the question. `already_present_refs` carries the
    refs `_plan_pulled_in_items` probed on the DESELECTED path, where no
    `ALREADY_PRESENT_BY_*` skip can exist to be read; the skip-derived set
    covers every other path. Live effect on `Mbugwe LizzieHC practice`: 8 of
    T073's 35 records named one of the 2 POSes that were already in the
    target.
    """
    if not edges:
        return ()

    if label_of is None:
        def label_of(ref):
            return (getattr(ref[0], "value", str(ref[0]))
                    + " " + str(ref[1])[:8])

    arriving = set()
    for item in list(actions) + list(overwrites):
        arriving.add(
            (item.category, str(getattr(item, "source_guid", "") or "").lower())
        )
    already_present = set()
    for skip in skips:
        if getattr(skip, "reason", None) in _DEPENDENCY_PRESENT_SKIPS:
            already_present.add(
                (skip.category,
                 str(getattr(skip, "source_guid", "") or "").lower())
            )
    # T093: the deselected path emits no `ALREADY_PRESENT_BY_*` skip -- it
    # refuses the ref before its planner ever runs -- so the presence fact for
    # those refs arrives here from the probe instead of from the skip list.
    for ref in already_present_refs or ():
        already_present.add((ref[0], str(ref[1]).lower()))

    cycles = _closure_cycle_groups(edges)
    records = []
    seen = set()
    for edge in edges:
        if edge.origin != "pulled_in":
            continue
        dependent = (edge.dependent[0], str(edge.dependent[1]).lower())
        dependency = (edge.dependency[0], str(edge.dependency[1]).lower())
        if dependent not in arriving:
            continue
        if dependency in already_present:
            # T093. Not a cause and not an exception to one: the object the
            # reference needs is in the destination, so there is nothing to be
            # incomplete about. Tested ahead of `deselected` and `cycle`
            # because both of those explain a loss, and this says there was
            # none.
            continue
        cycle = cycles.get(dependent)
        kind = getattr(edge.kind, "value", str(edge.kind))
        if edge.deselected:
            cause = "deselected"
            consequence = (
                "arrives without the " + kind + " dependency the user "
                "deselected; the reference is left unwired in the destination"
            )
        elif cycle is not None and dependency in cycle:
            cause = "cycle"
            consequence = (
                "dependency cycle over " + str(len(cycle)) + " items -- each "
                "needs the other, so whichever is written first cannot "
                "resolve its " + kind + " reference"
            )
        elif dependency in arriving:
            # (T093 moved the `already_present` half of this test above the
            # cause ladder, where it answers "is anything incomplete" for
            # every cause rather than only for this one.)
            continue
        else:
            cause = "unsatisfiable"
            consequence = (
                "the " + kind + " dependency could not be satisfied: it is "
                "neither transferred by this run nor already present in the "
                "destination, so the reference is left unwired"
            )
        key = (dependent, dependency, cause)
        if key in seen:
            continue
        seen.add(key)
        records.append(IncompletenessRecord(
            incomplete_item=edge.dependent,
            incomplete_label=label_of(edge.dependent),
            missing_dependency=edge.dependency,
            missing_label=label_of(edge.dependency),
            cause=cause,
            consequence=consequence,
        ))
    return tuple(records)


def build_run_plan(
    context: RunContext,
    selection: Selection,
    ws_mapping: WSMapping,
    source,
    target,
) -> RunPlan:
    """Compute a complete RunPlan for the current selection.

    Source and target are flexicon FLExProject handles (or duck-typed
    equivalents for unit tests). This function:

    1. Walks the selection's closure across the source.
    2. For each source piece, decides PlannedAction or Skip (FR-021, FR-022).
    3. Returns an immutable RunPlan that Move Mode (`Lib/transfer.py.execute`)
       consumes verbatim.

    MUST NOT mutate target. (SC-006)
    """
    actions: List[PlannedAction] = []
    skips: List[Skip] = []
    overwrites: List[PlannedOverwrite] = []
    excluded_lossy: List[ExcludedLossy] = []
    identity_remap: dict = {}

    # Walk every selected POS (or all top-level POSes when categories[POS]
    # is True and pos_picks is empty). For each POS, walk its closure:
    # POS → Template → Slots → LexEntries(MSA-points-at-POS) → Senses → MSAs
    # → Allomorphs → PhEnvironments.
    # SUPERSEDE DECISION (2026-07-06): the Phase-0 verb-vertical closure is
    # retired in favor of the Phase-3 leaf-dispatch categories, which now own
    # POS (GRAM_CATEGORIES), templates (AFFIX_TEMPLATES), slots (SLOTS),
    # affix entries+senses+MSAs+allomorphs (AFFIXES) and environments
    # (PH_ENVIRONMENT). Running both paths double-transferred those objects and
    # collided on identical GUIDs (integration harness, run 2026-07-06). This
    # flag gates the legacy path off; leaf-dispatch below is the single path.
    # (Supersedes spec 005 FR-311's coexistence mandate — tracked as a spec
    # amendment.) Flip to True only to A/B against the legacy behavior.
    _VERB_VERTICAL_ENABLED = False
    _pos_count = 0
    if _VERB_VERTICAL_ENABLED:
        for src_pos in _select_source_poses(source, selection):
            _pos_count += 1
            _plan_pos_closure(source, target, src_pos, selection, actions, skips, overwrites)
            _plan_layer3_for_pos(source, target, src_pos, selection, actions, skips, overwrites, excluded_lossy, identity_remap=identity_remap)
    _log.debug(
        "build_run_plan: verb-vertical closure enabled=%s over %d source POS(es); "
        "actions so far=%d", _VERB_VERTICAL_ENABLED, _pos_count, len(actions),
    )

    # Phase 3c binding accumulators — written by AFFIXES/STEMS plan_action;
    # consumed by AFFIX_TEMPLATES (17.1 sub-pass, US2) and STEMS (post-pass A, US3).
    # Thread via context so plan_action callbacks can access without signature change.
    # RunContext is frozen=True; use object.__setattr__ to attach dynamic attrs.
    _msa_slot_bindings: dict = {}
    _lexentry_ref_bindings: dict = {}
    object.__setattr__(context, '_msa_slot_bindings', _msa_slot_bindings)
    object.__setattr__(context, '_lexentry_ref_bindings', _lexentry_ref_bindings)
    # Feature 033: InflFeatsOA-on-affix-MSA accumulator. Same threading
    # convention as `_msa_slot_bindings` above; populated by
    # `_populate_msa_infl_feat_bindings` after the leaf dispatch and consumed
    # by the 17.1 sub-pass (`categories._run_171_subpass`).
    _msa_infl_feat_bindings: dict = {}
    object.__setattr__(context, '_msa_infl_feat_bindings', _msa_infl_feat_bindings)
    # T074 (FR-019): {msa_guid: owning entry guid} for every MSA the two
    # accumulators above can mention. Same threading convention; consumed by
    # the 17.1 sub-pass to tell "this run lost the link" from "this run never
    # promised the affix".
    _msa_owner_entry: dict = {}
    object.__setattr__(context, '_msa_owner_entry', _msa_owner_entry)
    # Feature 027 (Complex Forms & Variants, US1/US2/US3, contract C1): the
    # parallel, richer per-ref LexEntryRef CREATION binding accumulator --
    # SAME threading convention as `_lexentry_ref_bindings` above, gathered
    # by the SAME `_stash_entry_bindings` call site (extended) and consumed
    # by the Move wiring post-pass `_run_entryref_create_pass` (the front
    # half of the STEMS tail, immediately before `_run_post_pass_a`).
    _entryref_create_bindings: dict = {}
    object.__setattr__(context, '_entryref_create_bindings', _entryref_create_bindings)
    # Feature 031 (US1, T009): feature->category link accumulator, written by
    # `categories.gram_categories_plan_action` -> `_stash_feature_category_links`
    # and consumed by the Move wiring post-pass (`_run_infl_feature_link_pass`,
    # tail block on the last INFLECTION_FEATURES execute_action).
    _feature_category_links: dict = {}
    object.__setattr__(context, '_feature_category_links', _feature_category_links)
    # Phase 3c FR-338: thread the live Selection so entry-shaped leaf
    # plan_actions (AFFIXES/STEMS) can honor enable_overwrite by emitting a
    # PlannedOverwrite instead of a Skip when the target already has the GUID.
    object.__setattr__(context, '_selection', selection)

    # Phase 3c Selection UI: thread excluded_lossy collector so leaf-dispatch
    # plan_action callbacks can add EXCLUDED-LOSSY warnings.
    object.__setattr__(context, '_excluded_lossy', excluded_lossy)

    # Feature 024 (T010/T016/T017, FR-010/FR-012, contracts/dropped-item-
    # report.md "Collection"): thread the per-run dropped-item collector so
    # the referenced-possibility resolver (Lib/references.py
    # `decide_reference`, US1, wired into `Lib/categories.py`'s
    # AFFIXES/STEMS `plan_action`) can append DroppedItemRecord instances
    # (Principle III — decisions must appear in Preview, not only post-run).
    _dropped: list = []
    object.__setattr__(context, '_dropped', _dropped)

    # Feature 038 (T059, US5, FR-023..FR-025): per-run process-rule collector,
    # threaded exactly like `_dropped` above and for the same reason. The
    # entry closure's Preview twin runs `_resolve_process_graph` -- the
    # READ-ONLY half of the executor, byte-for-byte the same resolution Move
    # performs -- so a rule Move will skip is already named here, with its
    # reason, before anything is written.
    #
    # Only NON-reproductions are recorded at plan time. A `reproduced=True`
    # record would have to invent a target GUID for an object nothing has
    # created; Move records the reproductions, and `rules_not_reproduced` is
    # what a Preview reader needs in order to decide whether to run at all.
    #
    # Ordering (create-path contract criterion 1): the plan walks `InputOS`
    # before `OutputOS` because `MoCopyFromInput.ContentRA` names an `InputOS`
    # member of the same rule, and `_resolve_process_graph` is where that
    # ordering lives -- so Preview and Move share ONE implementation of it
    # rather than two that could drift.
    _process_rules: list = []
    object.__setattr__(context, '_process_rules', _process_rules)

    # Feature 024 (T016, FR-012): per-run GUID -> resolved/created target
    # item cache for the resolver, mirroring `_dropped` above. Shared across
    # every reference field/owner so a possibility already resolved earlier
    # in the walk short-circuits to LINK without re-deciding.
    _resolver_cache: dict = {}
    object.__setattr__(context, '_resolver_cache', _resolver_cache)

    # Feature 024 (T029/T030, US3, FR-009a): per-run copy-set dict
    # (`Lib/owned.py`'s `ctx._copy_set` convention -- see that module's own
    # "T029 (US3, FR-009a)" section docstring) threaded the same way as
    # `_dropped`/`_resolver_cache` above, so `_plan_allomorph_hung_data_decisions`'s
    # (`plan_allomorph_hung_data_decisions`'s) APR copy-set gate sees every
    # allomorph already planned earlier in this SAME run (across every
    # entry, not just the one currently being planned).
    _copy_set: dict = {}
    object.__setattr__(context, '_copy_set', _copy_set)

    # Feature 026 (texts-wordforms, T014): the ``{source_ws_id: target_ws_id}``
    # map (from the run's WSMapping) attached to the context so `Lib/texts.py`'s
    # plan_texts / `Lib/wordforms.py`'s plan_analyses can gate every WS-bearing
    # string at Preview time (FR-020) — matching how `transfer.execute` attaches
    # the same `_ws_map` for the apply side. Identity ({}) when no rename set.
    if __package__:
        from .ws_mapping import to_ws_map_dict as _to_ws_map_dict
    else:
        from ws_mapping import to_ws_map_dict as _to_ws_map_dict  # type: ignore
    object.__setattr__(context, '_ws_map', _to_ws_map_dict(ws_mapping))

    # Phase 3a leaf-category dispatch: iterate every Phase 3a category
    # that's enabled in the selection.  Each category's registered
    # callbacks live in Lib/categories.py.  Errors-as-skips: if an
    # enumerate_source raises, the category is treated as empty (per
    # FR-308 skip-empty semantics).
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
        # POS is the pick-driven ALIAS of GRAM_CATEGORIES (see the banner
        # above `categories.pos_enumerate_source`). It MUST dispatch here --
        # after GRAM_CATEGORIES, before every category whose executor resolves
        # an owning POS (INFLECTION_CLASSES, STEM_NAMES, POS_INFLECTABLE_FEATS,
        # SLOTS, AFFIX_TEMPLATES, AFFIXES) -- so a wizard-picked POS exists in
        # the target before those wire to it. `pos_enumerate_source` yields
        # nothing unless `selection.pos_picks` is non-empty AND
        # GRAM_CATEGORIES is off, so no existing selection changes shape.
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
        # Phase 3c (memo steps 14-18) — order matters: 17.1 sub-pass on
        # AFFIX_TEMPLATES executor tail requires AFFIXES and SLOTS to have
        # planned first; post-pass A on STEMS executor tail requires
        # AFFIXES + STEMS planning to be complete.
        GrammarCategory.AFFIXES,
        GrammarCategory.ADHOC_COMPOUND_RULES,
        GrammarCategory.SLOTS,
        GrammarCategory.AFFIX_TEMPLATES,
        GrammarCategory.STEMS,
    )
    if __package__:
        from .categories import for_category
    else:
        from categories import for_category  # type: ignore
    for cat in _LEAF_DISPATCH_CATEGORIES:
        if not selection.is_on(cat):
            continue
        try:
            bundle = for_category(cat)
        except KeyError:
            continue
        try:
            pieces = list(bundle["enumerate_source"](context, selection))
        except Exception:
            pieces = []
        # Persist/over-transfer diagnostics: how many items this category
        # enumerated and how many actions it contributes to the plan.
        _cat_actions_before = len(actions)
        for piece in pieces:
            try:
                result = bundle["plan_action"](piece, context, ws_mapping)
            except Exception as exc:  # planner-level failures become skips
                from .models import SkipReason as _SR  # noqa
                actions.append(PlannedAction(
                    category=cat,
                    source_guid=str(getattr(piece, "Guid", "?")),
                    intended_target_guid="",
                    summary=f"plan_action raised {type(exc).__name__}: {exc}",
                ))
                continue
            if isinstance(result, Skip):
                skips.append(result)
            elif isinstance(result, PlannedOverwrite):
                overwrites.append(result)
            elif isinstance(result, (PlannedAction, CreateDefinitionAction)):
                # CreateDefinitionAction (custom-field schema create) is a
                # standalone dataclass, NOT a PlannedAction subclass. Without
                # this branch it fell through every isinstance check and was
                # silently dropped, so custom fields never reached the plan and
                # execute_move's PATH-CLOSE-REBIND pre-pass never fired.
                actions.append(result)
        if _log.isEnabledFor(logging.DEBUG):
            _log.debug(
                "build_run_plan leaf category=%s  enumerated=%d actions+=%d",
                cat.value, len(pieces), len(actions) - _cat_actions_before,
            )

    # Feature 024 (T031, US3, FR-008 -- single-final-pass redesign):
    # `plan_all_lexical_relations` is the SOLE lexical-relation discovery +
    # planning path (see its own module banner at categories.py:3488-3504)
    # -- it runs exactly ONCE, here, after the leaf-category loop above has
    # planned every AFFIXES/STEMS entry, top-level sense, and recursively-
    # planned sub-sense/allomorph, so the run's `context._copy_set` is fully
    # settled. There is no per-member incremental trigger anywhere in
    # `_plan_entry_reference_decisions`/`owned.plan_owned_object_decisions`
    # during the leaf-category loop above; a relation touching any planned
    # member is discovered and evaluated for the first and only time right
    # here, source-ordered by construction
    # (`_iter_relations_touching_copy_set` walks the copy_set once). Move
    # mode runs the SAME single final pass (`transfer.
    # reproduce_all_lexical_relations`, after its own leaf-dispatch loop)
    # over the SAME kind of fully-settled copy_set, so Preview and Move
    # converge on identical relations-in/decisions-out.
    if __package__:
        from .categories import plan_all_lexical_relations
    else:
        from categories import plan_all_lexical_relations  # type: ignore
    plan_all_lexical_relations(context, _resolver_cache, _dropped)

    # Feature 025 (full reversals, US1 T018/T019): the reversal closure
    # walk -- SAME single-final-pass timing as `plan_all_lexical_relations`
    # immediately above, run once now that `context._copy_set` is fully
    # settled. Every reversal `DroppedItemRecord` this produces is already
    # in `_dropped` (folded into `dropped_items` below); `_reversal_decisions`
    # carries the Add/Link decisions themselves for Preview rendering
    # (`render_reversal_decisions`, below) before Move ever writes.
    # T037 Finding 2 (Preview/Move parity, feature-025 cycle-10 remediation):
    # thread the caller's WSMapping into `context._ws_map` -- the SAME
    # ``{source_ws_id: target_ws_id}`` dict shape `transfer.execute` computes
    # via this exact helper (`Lib/transfer.py:182`) and attaches to its own
    # exec_ctx (`Lib/transfer.py:353`) BEFORE calling
    # `reproduce_reversal_entries` -> `reversals.plan_reversals`. Without
    # this, `reversals.plan_reversals`'s `getattr(ctx, "_ws_map", None) or {}`
    # read (`Lib/reversals.py:443`) always fell back to `{}` (identity) here
    # in Preview, so a non-identity mapping's reversal-index target WS could
    # never be correctly predicted before Move ever writes. Set BEFORE
    # `plan_reversal_decisions` (immediately below) so its whole reversal
    # walk -- and any other reversal-path reader added later -- sees the
    # real mapping.
    object.__setattr__(context, '_ws_map', to_ws_map_dict(ws_mapping))

    if __package__:
        from .categories import plan_reversal_decisions
    else:
        from categories import plan_reversal_decisions  # type: ignore
    _reversal_decisions = plan_reversal_decisions(context, _resolver_cache, _dropped)

    # Feature 025 (full reversals, US3 T033): Part B `.fwdictconfig`
    # configuration-view copy plan -- SAME "compute once in Preview, write
    # once in Move" split as the reversal walk immediately above, but this
    # is a plain file-I/O decision pass (`Lib/config_views.py.plan_config_
    # views`), not an LCM closure walk. Fail-soft: `plan_config_views`
    # resolves each project's on-disk directory (for BOTH source and
    # target -- read-only, creates nothing) from its LCM cache path
    # (`config_views.compute_config_dirs`, P0-1 feature-025 cycle-6
    # remediation -- the plain, non-directory-creating path helper), which
    # raises `ValueError` for a duck-typed test double that exposes none of
    # the expected accessors
    # (`Lib/ui/main_window.py._safe_path`'s `ProjectPath`/`ProjectFilename`/
    # `ProjectFolder` convention, or the real `project.project.ProjectId
    # .Path`) -- e.g. `tests/unit/test_preview_no_writes.py`'s `_FakeProject`.
    # Swallowing that (and any other duck-typing gap) to an empty tuple
    # mirrors this function's existing "errors-as-skips" posture for leaf
    # categories above (`pieces = []` on enumerate_source failure) so a
    # project handle that can't answer the config-view question simply
    # contributes none, rather than aborting the whole Preview walk.
    if __package__:
        from .config_views import plan_config_views
    else:
        from config_views import plan_config_views  # type: ignore
    try:
        _config_view_records = plan_config_views(source, target)
    except Exception:  # noqa: BLE001 -- fail-soft, see docstring above
        _config_view_records = []
    for _cv_record in _config_view_records:
        if _cv_record.missing_refs:
            _dropped.extend(_cv_record.missing_refs)

    # Phase 3c (FR-333): populate msa_slot_bindings from source affix entries.
    # _stash_entry_bindings in categories.py uses getattr duck-typing which
    # silently returns None for base-typed IMoMorphSynAnalysis refs from live
    # LCM (pythonnet hides SlotsRC on the base interface). This explicit pass
    # uses IMoInflAffMsa casting — the same approach as _msa_fingerprint — so
    # it works for both live LCM and duck-typed fakes. It runs unconditionally
    # after the leaf dispatch so all enumerated affix entries are covered,
    # regardless of whether they were newly added or already present in target.
    _populate_msa_slot_bindings(source, _msa_slot_bindings)

    # T074 (FR-019): the owner map for both binding dicts. Runs beside them,
    # over the same walk, so a binding can never arrive without the fact that
    # tells the consumer whether it is this run's business.
    _populate_msa_owner_entry(source, _msa_owner_entry)

    # Feature 033: gather the inflection-feature STRUCTURES assigned to affix
    # MSAs (IMoInflAffMsa.InflFeatsOA). Same rationale as the slot pass above:
    # the base IMoMorphSynAnalysis interface hides InflFeatsOA under pythonnet,
    # so this needs an explicit IMoInflAffMsa cast rather than duck getattr.
    # Runs unconditionally after the leaf dispatch so every enumerated affix is
    # covered whether it was newly added or already present.
    _populate_msa_infl_feat_bindings(source, _msa_infl_feat_bindings)

    # T023: rules missing-reference detection (018-rules-page US4/FR-014/FR-015).
    # Runs AFTER the leaf dispatch so 'in-flight' actions are fully enumerated.
    # Routes into the shared excluded_lossy list -> single Move gate (T024).
    _rules_missing_ref_warnings(
        context, selection, actions, excluded_lossy, source, target
    )

    # Feature 026 (texts-wordforms, T010): dedicated text + wordform walk.
    # Texts do NOT route through the leaf-dispatch bundle above — they have
    # their own plan-builder (Lib/texts.py) that produces TextTransferPlans
    # (each carrying its paragraph/segment/analysis decisions, Principle III).
    # Runs after the lexical leaf dispatch so morph-bundle targets planned by
    # 024/025 are already in the copy set (R8 ordering). Shares the SAME
    # `_resolver_cache` (genres/tags) and `_dropped` collectors as the rest of
    # the walk so the never-silent guarantee is uniform (FR-023).
    _text_plans: list = []
    if selection.is_on(GrammarCategory.TEXTS):
        if __package__:
            from .texts import plan_texts as _plan_texts
        else:
            from texts import plan_texts as _plan_texts  # type: ignore
        _text_plans = list(_plan_texts(
            selection, source, target, context, _resolver_cache, _dropped
        ))
        _log.debug("build_run_plan: TEXTS on; plan_texts produced %d text plan(s)",
                   len(_text_plans))

    # Feature 038 (FR-014/FR-015/FR-018): materialise the verified-edge
    # closure. A no-op while CLOSURE_EDGES_VERIFIED is empty; raises rather
    # than planning from an unverified edge once it is not.
    _closure_edges = _walk_verified_closure(
        context, selection, actions, overwrites
    )

    # Feature 038 (T070/T071, FR-014/FR-015/FR-016): the edges say what is
    # needed; this is what puts it in the plan, marked `pulled_in_by` and
    # deselectable through the machinery that already existed. Mutates
    # `actions`/`overwrites`/`skips` in place and hands back the edges with
    # `deselected` stamped, so the plan and the edge set cannot disagree.
    _pull_in_pieces = _pull_in_piece_resolver(context, selection)
    # T093: refused refs that are nevertheless already in the destination. The
    # pull-in is the only place that can learn this (it holds the pieces and
    # the planners) and `_plan_incompleteness` is the only place that needs
    # it, so it travels between them and reaches no plan member.
    _deselected_but_present: set = set()
    _closure_edges = _plan_pulled_in_items(
        context, selection, ws_mapping, _closure_edges,
        actions, overwrites, skips, _LEAF_DISPATCH_CATEGORIES,
        _pull_in_pieces, _deselected_but_present,
    )

    # Feature 038 (T073, FR-017, SC-010): the edges now say what was refused
    # or unreachable; this is what tells the user which items therefore ARRIVE
    # INCOMPLETE. Read after the pull-in, because "is the dependency
    # satisfied" is a question about the finished plan -- and read off the
    # plan rather than off the skip list, so a dependency that vanished
    # without a skip is reported too.
    _incompleteness = _plan_incompleteness(
        _closure_edges, actions, overwrites, skips,
        lambda ref: _pull_in_label(_pull_in_pieces, ref),
        _deselected_but_present,
    )

    # Feature 038 (FR-020..FR-022, plan.md:111): the enrich-vs-skip decision is
    # a PLAN-TIME determination, so the enrichment records ride on the plan --
    # Preview and Move read the same tuple and agree by construction
    # (Principle III). Each record is attached by the category planner to the
    # `PlannedOverwrite` it belongs to (write_mode="merge", enforced in
    # `PlannedOverwrite.__post_init__`); harvesting them off `overwrites` here
    # keeps every record attributable to a category via that overwrite's
    # `source_guid`, which is what `report.build_from_plan` requires -- it
    # raises rather than guess a category for an orphan record.
    # Order follows plan order (the order the overwrites were planned in); no
    # sorting, so the plan stays byte-deterministic across runs.
    _enrichments = [
        ow.enrichment
        for ow in overwrites
        if getattr(ow, "enrichment", None) is not None
    ]

    _log.debug(
        "build_run_plan: done  actions=%d skips=%d overwrites=%d excluded_lossy=%d "
        "dropped_items=%d closure_edges=%d incompleteness=%d enrichments=%d",
        len(actions), len(skips), len(overwrites), len(excluded_lossy), len(_dropped),
        len(_closure_edges), len(_incompleteness), len(_enrichments),
    )
    return RunPlan(
        context=context,
        selection=selection,
        ws_mapping=ws_mapping,
        actions=tuple(actions),
        skips=tuple(skips),
        identity_remap=identity_remap,
        overwrites=tuple(overwrites),
        msa_slot_bindings=_msa_slot_bindings,
        # Feature 033: gathered InflFeatsOA bindings for affix MSAs.
        msa_infl_feat_bindings=_msa_infl_feat_bindings,
        # T074 (FR-019): which entry owns each of those MSAs.
        msa_owner_entry=_msa_owner_entry,
        lexentry_ref_bindings=_lexentry_ref_bindings,
        # Feature 027 (US1/US2/US3, contract C1): gathered create bindings
        # (see the accumulator attachment above).
        entryref_create_bindings=_entryref_create_bindings,
        # Feature 031 (US1, T009): gathered feature->category link bindings.
        feature_category_links=_feature_category_links,
        excluded_lossy=tuple(excluded_lossy),
        # QC P1 (cycle-1 review, feature 024): carry the read-only resolver's
        # projected drops into the plan so Preview is symmetric with Move
        # (Move already surfaces `_dropped` via transfer.execute's
        # extra_dropped_items -> RunReport wiring).
        dropped_items=tuple(_dropped),
        # Feature 038 (FR-014/FR-015): the verified dependency-closure edges.
        # Empty by construction while CLOSURE_EDGES_VERIFIED ships empty.
        closure_edges=_closure_edges,
        # Feature 038 (T073, FR-017/SC-010): the items that will arrive
        # KNOWINGLY incomplete because a dependency was deselected, could not
        # be satisfied, or sits in a cycle. Empty whenever `closure_edges` is,
        # so a full copy and every pre-038 caller are untouched.
        incompleteness=_incompleteness,
        # Feature 038 (FR-020..FR-022): the plan-time enrich-vs-skip decision,
        # harvested off the merge overwrites above so Preview reports the same
        # ENRICHED set Move will write (see the accumulator just above).
        enrichments=tuple(_enrichments),
        # Feature 026 (T010): per-text transfer plans consumed by transfer.py's
        # TEXTS apply hook. Empty tuple when TEXTS is not selected.
        text_plans=tuple(_text_plans),
        # Feature 025 (US1, T018/T019): the reversal closure walk's
        # decision output (see the call site above).
        reversal_decisions=tuple(_reversal_decisions),
        # Feature 025 (US3, T033): the config-view copy plan (see the call
        # site above); `missing_refs` on each record are already folded
        # into `dropped_items` above.
        config_view_records=tuple(_config_view_records),
        # Feature 038 (T059, US5): the rules this plan already knows cannot be
        # reproduced, each with the reason naming its specific blocker (see
        # the `_process_rules` accumulator attachment above).
        process_rules=tuple(_process_rules),
    )


# ============================================================================
# Feature 025 (full reversals, US1 T019) -- reversal-decision Preview rendering
# ============================================================================

def _render_one_reversal_decision(decision, indent: int) -> List[str]:
    """One Add-entry line per `ReversalDecision`, recursing
    `sub_entry_decisions` at increasing indent -- the sub-entry TREE shape
    (R6) rendered as nested lines."""
    pad = " " * indent
    form = next(iter(decision.reversal_form_alts.values()), "") if decision.reversal_form_alts else "(no form)"
    sense_count = len(decision.linked_sense_guids)
    lines = [f"{pad}Add entry {form!r} -- links {sense_count} sense(s)"]
    for sub in decision.sub_entry_decisions:
        lines.extend(_render_one_reversal_decision(sub, indent=indent + 2))
    return lines


def render_reversal_decisions(plan: RunPlan) -> Tuple[str, ...]:
    """T019 (US1, Principle III): render `plan.reversal_decisions` for the
    Preview pane, grouped by per-writing-system target index (existing ->
    'Link', to-create -> 'Add'), one Add-entry line per top-level entry
    (recursing sub-entries) -- BEFORE Move ever writes.

    Reversal `DroppedItemRecord`s are deliberately NOT duplicated here --
    they already flow through the single unified 024 channel
    (`RunPlan.dropped_items` / `RunReport.dropped_items`, rendered by
    `report.render_text_summary`); this function renders only what WOULD be
    added/linked, not what was dropped. Returns an empty tuple when the
    plan has no reversal decisions at all (no rendering needed).

    This is a plain-text rendering surface (mirrors `report.
    render_text_summary`'s own line-based contract) -- wiring an actual
    interactive PyQt widget onto it is a separate UI concern, not part of
    this feature's US1 scope (`Lib/ui/main_window.py`/the stats panel can
    call this the same way they already consume `report.render_text_summary`
    for the run-report pane).
    """
    if not plan.reversal_decisions:
        return ()
    by_ws: dict = {}
    for decision in plan.reversal_decisions:
        by_ws.setdefault(decision.target_ws_id, []).append(decision)

    lines: List[str] = []
    for ws_id in sorted(by_ws):
        group = by_ws[ws_id]
        action = "Add" if group[0].target_index_ref is None else "Link"
        lines.append(f"  Reversal index [{ws_id}] ({action}):")
        for decision in group:
            lines.extend(_render_one_reversal_decision(decision, indent=4))
    return tuple(lines)


# ============================================================================
# Feature 025 (full reversals, US3 T033) -- config-view Preview rendering
# ============================================================================

_CONFIG_VIEW_ACTION_LABEL = {
    "add": "Add",
    "overwrite": "Overwrite",
    "skip": "Skip (already up to date)",
}


def render_config_view_records(plan: RunPlan) -> Tuple[str, ...]:
    """T033 (US3, Principle III): render `plan.config_view_records` for the
    Preview pane, grouped by `kind` ("Dictionary" / "ReversalIndex"), one
    line per `.fwdictconfig` file showing its planned Add/Overwrite/Skip
    disposition -- BEFORE Move's `Lib/transfer.py.execute` calls
    `Lib/config_views.py.apply_config_views`.

    Missing-reference records (`ConfigViewRecord.missing_refs`) are
    deliberately NOT duplicated here -- they already flow through the SAME
    unified 024 dropped-items channel as every other drop in this codebase
    (`RunPlan.dropped_items` / `RunReport.dropped_items`, rendered by
    `report.render_text_summary`); this function renders only the
    Add/Overwrite/Skip file dispositions themselves. Returns an empty tuple
    when the plan has no config-view records at all (mirrors
    `render_reversal_decisions`'s empty-plan posture).
    """
    if not plan.config_view_records:
        return ()
    by_kind: dict = {}
    for record in plan.config_view_records:
        by_kind.setdefault(record.kind, []).append(record)

    lines: List[str] = []
    lines.append("  Configuration views:")
    for kind in sorted(by_kind):
        lines.append(f"    {kind}:")
        for record in by_kind[kind]:
            label = _CONFIG_VIEW_ACTION_LABEL.get(record.action.value, record.action.value)
            lines.append(f"      {label} {record.filename!r}")
    return tuple(lines)


# ============================================================================
# P0-2 (feature 025 cycle-6 remediation) -- Preview surface composition
# ============================================================================

# ============================================================================
# Feature 031 (US1, T010) -- feature->category link Preview rendering
# ============================================================================

def _target_pos_infl_feat_guids(target, pos_guid):
    """Return the set of feature GUIDs already in a target POS's
    InflectableFeatsRC, or None when the target can't answer (fail-soft ->
    render as 'Link'). Used only to label already-linked pairs as SKIP (C1
    DEDUP); never mutates the target."""
    getter = getattr(target, "get_object_by_guid", None)
    if getter is None:
        return None
    try:
        pos = getter(pos_guid)
    except Exception:  # noqa: BLE001
        return None
    if pos is None:
        return None
    pos_typed = pos
    try:
        from SIL.LCModel import IPartOfSpeech  # noqa: PLC0415
        pos_typed = IPartOfSpeech(pos)
    except Exception:  # noqa: BLE001
        pos_typed = pos
    feats_rc = getattr(pos_typed, "InflectableFeatsRC", None)
    if feats_rc is None:
        return None
    out = set()
    try:
        for feat in feats_rc:
            g = str(getattr(feat, "Guid", getattr(feat, "guid", ""))).lower()
            if g:
                out.add(g)
    except (AttributeError, TypeError):
        return None
    return out


def render_feature_category_links(plan: RunPlan) -> Tuple[str, ...]:
    """T010 (US1, Principle III / VR-5 / SC-004): render `plan.feature_category_
    links` for the Preview pane -- one row per (POS, feature) association with a
    proposed action **Link**, or **SKIP (already linked)** when the pair is
    already present in the target POS's InflectableFeatsRC (contract C1 DEDUP).

    The number of Link rows equals the number of (POS, feature) pairs that the
    Move wiring post-pass will write, so preview count == committed count.
    Returns an empty tuple when the plan carries no links (mirrors
    `render_reversal_decisions`)."""
    links = getattr(plan, "feature_category_links", None) or {}
    if not links:
        return ()
    target = getattr(getattr(plan, "context", None), "target_handle", None)
    lines: List[str] = ["  Inflection feature -> category links:"]
    for pos_guid in sorted(links):
        present = _target_pos_infl_feat_guids(target, pos_guid)
        for feature_guid in links[pos_guid]:
            already = present is not None and str(feature_guid).lower() in present
            action = "SKIP (already linked)" if already else "Link"
            lines.append(f"    {action}  POS {pos_guid} <- feature {feature_guid}")
    return tuple(lines)


def render_preview_extra_lines(plan: RunPlan) -> Tuple[str, ...]:
    """Compose the Preview-only extra lines -- the reversal Add/Link plan
    (`render_reversal_decisions`), the config-view Add/Overwrite/Skip
    list (`render_config_view_records`), and the feature->category link plan
    (`render_feature_category_links`) -- that `Lib/ui/main_window.py.
    _on_preview` displays alongside the existing stats-panel report text
    BEFORE Move ever writes (Principle III).

    Before this fix neither render function had any call site in the
    codebase: `_on_preview` built a `RunReport` and called `self._stats.
    set_report(report)`, which surfaces `RunPlan.dropped_items` only -- the
    reversal Add/Link plan and the config-view Add/Overwrite/Skip list were
    computed every Preview run (`build_run_plan`) but never shown to the
    user. This is the single seam `_on_preview` now calls; each underlying
    render fn already returns `()` for an empty plan, so this composition
    is a clean no-op when the plan carries neither.
    """
    return (
        tuple(render_reversal_decisions(plan))
        + tuple(render_config_view_records(plan))
        + tuple(render_feature_category_links(plan))
    )


# ============================================================================
# Rules missing-reference detection (018-rules-page T023, US4, FR-014/FR-015)
# ============================================================================

def _rules_missing_ref_warnings(
    context: "RunContext",
    selection: "Selection",
    planned_actions: List["PlannedAction"],
    excluded_lossy: List["ExcludedLossy"],
    source,
    target,
) -> None:
    """Emit ExcludedLossy warnings for kept rules with unresolvable member refs.

    For each rule that was planned (PlannedAction for ADHOC_COMPOUND_RULES),
    inspect its dependency GUIDs (via adhoc_compound_rules_dependencies).
    If a dep GUID is:
      - NOT in the set of in-flight action GUIDs (being transferred), AND
      - NOT already present in the target (by GUID),
    emit one entry-centric ExcludedLossy warning for that (rule, dep) pair
    (FR-014 one-per-ref, FR-015 routed to shared Move gate).

    ``target is None`` => treat target as lacking every ref (safe default,
    no crash — spec Assumptions / data-model.md "No target bound" invariant).

    All GUID comparisons use _guid_str_from via the categories helper so the
    normalization invariant (lowercase, braces-stripped) is upheld on both
    sides.
    """
    if __package__:
        from .categories import adhoc_compound_rules_dependencies, _rules_enumerate_all, _guid_str_from
    else:
        from categories import adhoc_compound_rules_dependencies, _rules_enumerate_all, _guid_str_from  # type: ignore

    # Build the set of GUIDs that are 'in-flight' (planned for transfer in this run)
    in_flight_guids: set = {
        a.source_guid
        for a in planned_actions
        if isinstance(a, PlannedAction)
    }

    # Build the set of GUIDs already present in the target (all rule-dep categories:
    # allomorphs, MSAs, POS objects).  We use a broad approach — collect GUIDs of
    # every reachable object in the target that might be a dep of a rule.
    target_guids: set = set()
    if target is not None:
        try:
            # Allomorphs (IMoForm)
            for entry in target.Cache.LangProject.LexDbOA.Entries:
                try:
                    for allo in entry.AlternateFormsOS:
                        target_guids.add(_guid_str_from(allo))
                except (AttributeError, TypeError):
                    pass
                try:
                    lf = entry.LexemeFormOA
                    if lf is not None:
                        target_guids.add(_guid_str_from(lf))
                except (AttributeError, TypeError):
                    pass
                # MSAs (IMoMorphSynAnalysis)
                try:
                    for msa in entry.MorphoSyntaxAnalysesOC:
                        target_guids.add(_guid_str_from(msa))
                except (AttributeError, TypeError):
                    pass
        except (AttributeError, TypeError):
            pass
        # POS objects (IPartOfSpeech — compound rule deps)
        try:
            def _iter_pos(pos_list):
                for pos in pos_list:
                    target_guids.add(_guid_str_from(pos))
                    try:
                        for child in pos.SubPossibilitiesOS:
                            _iter_pos([child])
                    except (AttributeError, TypeError):
                        pass
            poses = target.Cache.LangProject.PartsOfSpeechOA.PossibilitiesOS
            _iter_pos(list(poses))
        except (AttributeError, TypeError):
            pass

    # Identify which rules are planned (in the ADHOC_COMPOUND_RULES planned actions)
    planned_rule_guids: set = {
        a.source_guid
        for a in planned_actions
        if isinstance(a, PlannedAction)
        and getattr(a, "category", None) == GrammarCategory.ADHOC_COMPOUND_RULES
    }

    if not planned_rule_guids:
        return

    # Build a guid -> label map for kept rules using source enumeration
    rule_labels: dict = {}
    if source is not None:
        try:
            for obj in _rules_enumerate_all(source):
                g = _guid_str_from(obj)
                if g in planned_rule_guids:
                    try:
                        name = obj.Name
                        text = getattr(
                            getattr(name, "BestAnalysisAlternative", None),
                            "Text", None
                        ) if name is not None else None
                        lbl = text if text and text not in ("***", "") else g[:8]
                    except (AttributeError, TypeError):
                        lbl = g[:8]
                    rule_labels[g] = lbl
        except Exception:  # noqa: BLE001
            pass

    # Determine ref kind from dep GUID context.
    # We cannot cheaply infer ref kind from a plain GUID, so we iterate the
    # source rule objects and use the subclass-specific fields.
    def _dep_ref_kind(rule_obj, dep_guid: str) -> str:
        """Guess stranded_ref_kind from the rule subclass fields."""
        try:
            from SIL.LCModel import ICmObject
            class_name = ICmObject(getattr(rule_obj, "concrete", rule_obj)).ClassName
        except Exception:
            class_name = getattr(rule_obj, "class_name",
                                 getattr(rule_obj, "ClassName", "")) or ""
        if class_name == "MoAlloAdhocProhib":
            return "allomorph"
        if class_name == "MoMorphAdhocProhib":
            return "morpheme"
        if class_name in ("MoEndoCompound", "MoExoCompound"):
            return "part-of-speech"
        return "member"

    def _dep_label(dep_guid: str) -> str:
        return dep_guid[:8]

    # Emit warnings: one per (kept rule, stranded dep) pair
    warned: set = set()
    if source is not None:
        try:
            for rule_obj in _rules_enumerate_all(source):
                rule_guid = _guid_str_from(rule_obj)
                if rule_guid not in planned_rule_guids:
                    continue
                dep_guids = adhoc_compound_rules_dependencies(rule_obj)
                for dep_guid in dep_guids:
                    if not dep_guid:
                        continue
                    # Dep is resolved if in-flight or already in target
                    if dep_guid in in_flight_guids:
                        continue
                    if dep_guid in target_guids:
                        continue
                    key = (rule_guid, dep_guid)
                    if key in warned:
                        continue
                    warned.add(key)
                    rule_lbl = rule_labels.get(rule_guid, rule_guid[:8])
                    ref_kind = _dep_ref_kind(rule_obj, dep_guid)
                    excluded_lossy.append(ExcludedLossy(
                        category=GrammarCategory.ADHOC_COMPOUND_RULES,
                        entry_guid=rule_guid,
                        entry_label=rule_lbl,
                        dep_category=GrammarCategory.ADHOC_COMPOUND_RULES,
                        dep_guid=dep_guid,
                        dep_label=_dep_label(dep_guid),
                        message=(
                            f"Rule '{rule_lbl}' references {ref_kind} "
                            f"'{_dep_label(dep_guid)}' which is absent from the target "
                            f"and not being transferred."
                        ),
                    ))
        except Exception:  # noqa: BLE001
            pass


# ============================================================================
# Phase 3c (FR-333): MSA slot-binding population pass
# ============================================================================

def _populate_msa_slot_bindings(source, msa_slot_bindings: dict) -> None:
    """Populate `msa_slot_bindings` from every inflectional affix MSA in source
    that has non-empty SlotsRC.

    Called from `build_run_plan` after the leaf dispatch loop.  The
    categories.py `_stash_entry_bindings` helper uses `getattr` duck-typing
    that silently returns None for base-typed `IMoMorphSynAnalysis` refs when
    running against live LCM (pythonnet hides SlotsRC on the base interface).
    This function uses `IMoInflAffMsa` casting — the same technique as
    `_msa_fingerprint` — which works for both live LCM and duck-typed fakes.

    Idempotent: re-running overwrites existing keys with the same values.
    Non-inflectional MSAs (stem / deriv / unclassified) are skipped via the
    try/except guard; an `IMoInflAffMsa` cast on a non-inflectional object
    raises so we catch and skip cleanly.

    Shape written: {src_msa_guid_str: [src_slot_guid_str, ...]}
    Keys and values are lowercase GUID strings (no braces), matching the
    format used by `_run_171_subpass` in categories.py.
    """
    if source is None:
        return
    # Iterate source LexEntries via the two paths _iter_lex_entries uses:
    # live LCM (Cache.LangProject.LexDbOA) and flexicon/duck-typed handle
    # (LangProject.LexDbOA or direct Cache.LangProject.LexDbOA).
    lexdb = None
    for nav in (
        lambda h: h.Cache.LangProject.LexDbOA,
        lambda h: h.LangProject.LexDbOA,
    ):
        try:
            lexdb = nav(source)
        except (AttributeError, TypeError):
            lexdb = None
        if lexdb is not None:
            break
    if lexdb is None:
        return

    entries = None
    for attr in ("EntriesOC", "Entries"):
        coll = getattr(lexdb, attr, None)
        if coll is not None:
            entries = coll
            break
    if entries is None:
        return

    # Determine whether to use LCM interface casts (live FLEx) or duck-typed
    # attribute access (unit-test fakes).
    #
    # Strategy: try to import the three cast helpers.  If they are importable
    # AND callable (not None stubs injected by test_entry_types_*.py), probe
    # the first entry with ILexEntry().  If that cast raises TypeError it means
    # the entries are duck-typed fakes (e.g. from flexicon's own test helpers
    # that are available but cannot wrap plain Python objects), so we fall back
    # to duck-typed access for all entries.  If the cast succeeds we are in
    # live LCM mode and use interface casts throughout.
    #
    # This covers three scenarios:
    #   A. No SIL.LCModel in sys.modules (ImportError) -> duck-typed.
    #   B. SIL.LCModel stub with None types (unit tests) -> duck-typed.
    #   C. flexicon loaded SIL.LCModel with real types but entries are fakes
    #      (test_013_fill_gaps.py imports flexicon) -> probe fails -> duck-typed.
    #   D. Live FlexTools session with real LCM objects -> LCM cast path.
    _ILexEntry = None
    _IMoInflAffMsa = None
    _ICmObject = None
    try:
        from SIL.LCModel import ILexEntry as _ILE, IMoInflAffMsa as _IMIA, ICmObject as _ICO  # noqa: N813
        if callable(_ILE) and callable(_IMIA) and callable(_ICO):
            _ILexEntry, _IMoInflAffMsa, _ICmObject = _ILE, _IMIA, _ICO
    except (ImportError, Exception):  # noqa: BLE001
        pass

    # If cast helpers are unavailable, go straight to duck-typed path.
    if _ILexEntry is None:
        _populate_msa_slot_bindings_duck(entries, msa_slot_bindings)
        return

    # Probe the first entry to distinguish live LCM from duck-typed fakes
    # (scenario C above).  Convert to list once so we can iterate twice if
    # needed without exhausting a generator.
    entry_list = list(entries)
    if entry_list:
        try:
            _ILexEntry(entry_list[0])
        except TypeError:
            # First entry is a duck-typed fake — treat all as duck-typed.
            _populate_msa_slot_bindings_duck(entry_list, msa_slot_bindings)
            return
        except Exception:  # noqa: BLE001
            # Some other error on the first entry; try LCM path anyway and let
            # per-entry exception handling skip problem entries.
            pass

    for raw_entry in entry_list:
        try:
            entry = _ILexEntry(raw_entry)
        except Exception:  # noqa: BLE001
            continue
        try:
            msas = entry.MorphoSyntaxAnalysesOC
        except (AttributeError, TypeError):
            continue
        for raw_msa in msas:
            try:
                ia = _IMoInflAffMsa(raw_msa)
                msa_guid = str(_ICmObject(raw_msa).Guid).lower()
                slot_guids = [str(_ICmObject(sl).Guid).lower() for sl in ia.SlotsRC]
            except Exception:  # noqa: BLE001
                # Not an IMoInflAffMsa (stem / deriv / unclassified) — skip.
                continue
            if slot_guids:
                msa_slot_bindings[msa_guid] = slot_guids


def _iter_source_entries(source):
    """Yield source LexEntries via the same two navigations
    `_populate_msa_slot_bindings` uses (live LCM vs duck-typed handle).
    Returns an empty list when the lexicon is unreachable."""
    if source is None:
        return []
    lexdb = None
    for nav in (
        lambda h: h.Cache.LangProject.LexDbOA,
        lambda h: h.LangProject.LexDbOA,
    ):
        try:
            lexdb = nav(source)
        except (AttributeError, TypeError):
            lexdb = None
        if lexdb is not None:
            break
    if lexdb is None:
        return []
    for attr in ("EntriesOC", "Entries"):
        coll = getattr(lexdb, attr, None)
        if coll is not None:
            return list(coll)
    return []


def _populate_msa_owner_entry(source, msa_owner_entry: dict) -> None:
    """Populate `{src_msa_guid: owning src LexEntry guid}` (T074, FR-019).

    WHAT THIS IS FOR. `_populate_msa_slot_bindings` and
    `_populate_msa_infl_feat_bindings` both walk the whole source lexicon
    regardless of the selection, on purpose. That makes their output a claim
    about the SOURCE; the 17.1 sub-pass in categories.py has to turn each
    binding into a claim about THIS RUN, and the question that does so is "is
    this MSA's affix in the destination at all". The sub-pass has a target
    handle but no source handle, so the owner cannot be recovered there --
    it has to be recorded here, where the walk already knows it.

    Records EVERY MSA, not only the inflectional ones with slots or features.
    Two reasons: the same map answers the same question for the InflFeats half
    of the sub-pass (`_wire_msa_infl_feats`, which over-reported the same way),
    and a map keyed by whatever the OTHER producer decided to keep would go
    silently incomplete the moment either producer's filter changed.

    No interface cast is needed or wanted: the owner of an MSA is the entry
    the walk is standing on, so this works identically on live LCM and on the
    duck-typed fakes without the cast/probe dance its siblings need.

    Idempotent: re-running overwrites existing keys with the same values.
    """
    for entry in _iter_source_entries(source):
        entry_guid = _guid_of(entry)
        if not entry_guid:
            continue
        for msa in getattr(entry, "MorphoSyntaxAnalysesOC", None) or []:
            msa_guid = _guid_of(msa)
            if msa_guid:
                msa_owner_entry[msa_guid] = entry_guid


def _guid_of(obj):
    """Lowercase GUID string for `obj`, or "" -- live LCM or duck-typed fake.

    `.Guid` is what LCM exposes and `.guid` is what the host-free fakes carry;
    both producers above already depend on that pair, so reading them in one
    place keeps the owner map keyed identically to the bindings it explains.
    """
    for attr in ("Guid", "guid"):
        value = getattr(obj, attr, None)
        if value is not None:
            text = str(value).strip().strip("{}").lower()
            if text:
                return text
    return ""


def _populate_msa_infl_feat_bindings(source, bindings: dict) -> None:
    """Populate `bindings` from every affix MSA in source carrying a non-empty
    `InflFeatsOA` feature structure (feature 033).

    This is the missing half of the affix transfer: `_create_msa_for_closure`
    creates the target MSA with its POS, and the 17.1 sub-pass wires SlotsRC,
    but the inflection-feature VALUES assigned to the affix were never read from
    source at all -- so every affix arrived with an empty feature cell.

    Shape written, keyed by source MSA GUID:
        {"struc_guid": str,          # IFsFeatStruc GUID (GUID-preserved)
         "type_guid": str,           # IFsFeatStrucType GUID ("" when unset)
         "specs": [{"spec_guid": str, "feature": str, "value": str}, ...]}

    Only IFsClosedValue specs are captured; complex/negated/disjunctive values
    are recorded with an empty "value" so the consumer can report them rather
    than silently dropping them (never-silent, FR-023).

    Idempotent: re-running overwrites existing keys with the same values.
    """
    entry_list = _iter_source_entries(source)
    if not entry_list:
        return

    _ILexEntry = _IMoInflAffMsa = _ICmObject = None
    _IFsFeatStruc = _IFsClosedValue = None
    try:
        from SIL.LCModel import (  # noqa: N813
            ILexEntry as _ILE, IMoInflAffMsa as _IMIA, ICmObject as _ICO,
            IFsFeatStruc as _IFS, IFsClosedValue as _IFCV,
        )
        if all(callable(x) for x in (_ILE, _IMIA, _ICO, _IFS, _IFCV)):
            _ILexEntry, _IMoInflAffMsa, _ICmObject = _ILE, _IMIA, _ICO
            _IFsFeatStruc, _IFsClosedValue = _IFS, _IFCV
    except (ImportError, Exception):  # noqa: BLE001
        pass

    if _ILexEntry is None:
        _populate_msa_infl_feat_bindings_duck(entry_list, bindings)
        return

    # Probe for duck-typed fakes exactly as the slot pass does (scenario C).
    try:
        _ILexEntry(entry_list[0])
    except TypeError:
        _populate_msa_infl_feat_bindings_duck(entry_list, bindings)
        return
    except Exception:  # noqa: BLE001
        pass

    def _g(obj):
        try:
            return str(_ICmObject(obj).Guid).lower()
        except Exception:  # noqa: BLE001
            return ""

    for raw_entry in entry_list:
        try:
            entry = _ILexEntry(raw_entry)
            msas = entry.MorphoSyntaxAnalysesOC
        except (AttributeError, TypeError, Exception):  # noqa: BLE001
            continue
        for raw_msa in msas:
            try:
                struc = _IMoInflAffMsa(raw_msa).InflFeatsOA
            except Exception:  # noqa: BLE001 -- stem/deriv/unclassified MSA
                continue
            if struc is None:
                continue
            try:
                specs = list(_IFsFeatStruc(struc).FeatureSpecsOC)
            except Exception:  # noqa: BLE001
                continue
            if not specs:
                continue
            rows = []
            for spec in specs:
                feat_guid = value_guid = ""
                try:
                    cv = _IFsClosedValue(spec)
                    feat_guid = _g(cv.FeatureRA) if cv.FeatureRA is not None else ""
                    value_guid = _g(cv.ValueRA) if cv.ValueRA is not None else ""
                except Exception:  # noqa: BLE001 -- complex / negated value
                    feat_guid = _g(getattr(spec, "FeatureRA", None) or spec)
                rows.append({"spec_guid": _g(spec), "feature": feat_guid,
                             "value": value_guid})
            struc_type = None
            try:
                struc_type = _IFsFeatStruc(struc).TypeRA
            except Exception:  # noqa: BLE001
                struc_type = None
            bindings[_g(raw_msa)] = {
                "struc_guid": _g(struc),
                "type_guid": _g(struc_type) if struc_type is not None else "",
                "specs": rows,
            }


def _populate_msa_infl_feat_bindings_duck(entries, bindings: dict) -> None:
    """Duck-typed fallback for `_populate_msa_infl_feat_bindings` (host-free
    unit tests). Reads `.InflFeatsOA`, `.FeatureSpecsOC`, `.FeatureRA`,
    `.ValueRA` and `.guid` via getattr so the fakes in
    `test_categories_affixes.py` satisfy this path without live LCM."""
    for entry in entries:
        for msa in getattr(entry, "MorphoSyntaxAnalysesOC", None) or []:
            struc = getattr(msa, "InflFeatsOA", None)
            if struc is None:
                continue
            specs = list(getattr(struc, "FeatureSpecsOC", None) or [])
            if not specs:
                continue
            msa_guid = getattr(msa, "guid", None)
            if msa_guid is None:
                continue
            rows = []
            for spec in specs:
                feat = getattr(spec, "FeatureRA", None)
                val = getattr(spec, "ValueRA", None)
                rows.append({
                    "spec_guid": getattr(spec, "guid", "") or "",
                    "feature": (getattr(feat, "guid", "") or "") if feat is not None else "",
                    "value": (getattr(val, "guid", "") or "") if val is not None else "",
                })
            bindings[msa_guid] = {
                "struc_guid": getattr(struc, "guid", "") or "",
                "type_guid": (getattr(getattr(struc, "TypeRA", None), "guid", "") or ""),
                "specs": rows,
            }


def _populate_msa_slot_bindings_duck(entries, msa_slot_bindings: dict) -> None:
    """Duck-typed fallback for `_populate_msa_slot_bindings` when SIL.LCModel
    is not importable (host-free unit tests).

    Reads `.MorphoSyntaxAnalysesOC`, `.SlotsRC`, and `.guid` via `getattr`
    so the host-free fakes in `test_categories_affixes.py` satisfy this path
    without requiring live LCM.  Non-inflectional MSAs (no SlotsRC or empty
    SlotsRC) are silently skipped.
    """
    for entry in entries:
        for msa in getattr(entry, "MorphoSyntaxAnalysesOC", None) or []:
            slots = list(getattr(msa, "SlotsRC", None) or [])
            if not slots:
                continue
            msa_guid = getattr(msa, "guid", None)
            if msa_guid is None:
                continue
            slot_guids = [
                getattr(s, "guid", None) for s in slots
                if getattr(s, "guid", None) is not None
            ]
            if slot_guids:
                msa_slot_bindings[msa_guid] = slot_guids


# ============================================================================
# Verb-vertical plan walk (mirrors STATUS.md Layer 1+2)
# ============================================================================

def _emit_present_outcome(
    category: GrammarCategory,
    src_guid: str,
    target_guid: str,
    summary: str,
    skip_detail: str,
    selection: Selection,
    skips: List[Skip],
    overwrites: Optional[List[PlannedOverwrite]],
    *,
    pulled_in_by: tuple = (),
    match_via: str = "guid",
    owner_guid: str = "",
    object_class: str = "",
) -> None:
    """Phase 0/1 dispatcher for "target already has source GUID":

    - Phase 0 (`selection.enable_overwrite=False`, default): emit
      `Skip(ALREADY_PRESENT_BY_GUID)` per FR-009.
    - Phase 1 (`selection.enable_overwrite=True`, per FR-108): emit
      `PlannedOverwrite` instead so the executor updates the existing
      target object's syncable properties from source.

    A `MatchBasisRecord` (038 T031) is attached so the run report can tell
    "found by GUID" from "found by name because the GUID was absent". The class
    is derived from `category` through `lcm_class_for_category`, and
    `object_class=` overrides that for a caller that knows better. A category
    whose LCM class is NOT one-to-one yields no record rather than a guessed
    one -- `object_class` is the field the report groups by, so a wrong name
    would file the match under another class.

    The record is attached ONLY when the match really was by GUID --
    `match_via="guid"` or `"identity_remap"`, both of which are
    `MatchBasis.IDENTITY` (FR-001 treats a previous run's remap entry as
    identity, not as a substitution).

    It is deliberately NOT attached for `match_via="fingerprint"`. A
    fingerprint match is neither identity nor a roster-admitted natural key,
    and `MatchBasis` has no member for it. Recording one as IDENTITY would
    claim a GUID hit that never happened; recording it as NATURAL_KEY would
    corrupt `CategoryReport.identity_substitution`, whose whole purpose is to
    count roster-admitted name matches. Leaving the record absent is the
    honest answer, and `report.py` already accounts for it under
    `matches_unattributed`.
    """
    # Derived from the category rather than demanded from the caller. The
    # parameter came first and NOTHING passed it, so the record was never
    # produced -- T036 found that while proving its own no-record path, which
    # is a good illustration of why an opt-in that every caller must remember
    # is the wrong shape for an accounting record.
    resolved_class = object_class or lcm_class_for_category(category)
    match_basis = None
    if resolved_class and match_via in ("guid", "identity_remap"):
        match_basis = match_basis_for_present_by_guid(
            resolved_class, src_guid, target_guid,
        )
    if selection.enable_overwrite and overwrites is not None:
        overwrites.append(PlannedOverwrite(
            category=category,
            source_guid=src_guid,
            target_guid=target_guid,
            summary=summary,
            match_via=match_via,
            pulled_in_by=pulled_in_by,
            owner_guid=owner_guid,
            match_basis=match_basis,
        ))
    else:
        skips.append(Skip(
            category=category,
            source_guid=src_guid,
            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
            detail=skip_detail,
        ))


def _select_source_poses(source, selection: Selection) -> List:
    """Return the list of source POS objects whose closure should be walked.

    We walk a POS's closure whenever ANY category in the POS-or-downstream
    closure is selected (POS itself, Templates, Slots, Entry, Sense, MSA,
    Allomorph, PhEnvironment). Closure-off mode produces BARE_BONES skips
    for non-selected layers; that's handled inside the walker.

    POS picking:
    - If `selection.pos_picks` is non-empty, walk only those POSes (by GUID).
    - Otherwise walk every top-level POS in source.

    Returns [] when no category in the POS closure is selected.
    """
    pos_closure_cats = (
        GrammarCategory.POS,
        GrammarCategory.AFFIX_TEMPLATES,
        GrammarCategory.SLOTS,
        GrammarCategory.ENTRY,
        GrammarCategory.SENSE,
        GrammarCategory.MSA,
        GrammarCategory.ALLOMORPH,
        # Phase 3a: PH_ENVIRONMENT is now a project-wide LEAF category
        # (memo step 4b). It no longer triggers the verb-vertical walker.
        # Allomorph closure still resolves environments by GUID against
        # the same plan, so the relocation is invisible to existing
        # Phase 0/1/2 callers selecting ALLOMORPH.
    )
    if not any(selection.is_on(c) for c in pos_closure_cats):
        return []
    all_poses = list(source.POS.GetAll(recursive=True))
    if not selection.pos_picks:
        return [_unwrap(p) for p in all_poses]
    picks = set(g.lower() for g in selection.pos_picks)
    result = []
    for p in all_poses:
        concrete = _unwrap(p)
        if _guid_str(concrete) in picks:
            result.append(concrete)
    return result


def _plan_pos_closure(
    source,
    target,
    src_pos,
    selection: Selection,
    actions: List[PlannedAction],
    skips: List[Skip],
    overwrites: List[PlannedOverwrite],
) -> None:
    """POS → Template → Slot walk for a single source POS. Mirrors the
    pre-multi-POS `_plan_verb_vertical` but parameterized on the POS."""
    _plan_verb_vertical_inner(
        source, target, src_pos, selection, actions, skips, overwrites,
    )


def _plan_layer3_for_pos(
    source,
    target,
    src_pos,
    selection: Selection,
    actions: List[PlannedAction],
    skips: List[Skip],
    overwrites: List[PlannedOverwrite],
    excluded_lossy: Optional[List[ExcludedLossy]] = None,
    identity_remap: dict = None,
) -> None:
    """Layer 3 (LexEntry / Sense / MSA / Allomorph / PhEnvironment) walk for
    affix entries whose IMoInflAffMsa.PartOfSpeechRA points at `src_pos`."""
    _plan_layer3_verb_affixes_inner(
        source, target, src_pos, selection, actions, skips, overwrites,
        excluded_lossy=excluded_lossy,
        identity_remap=identity_remap if identity_remap is not None else {},
    )


def _plan_verb_vertical_inner(
    source,
    target,
    src_pos,
    selection: Selection,
    actions: List[PlannedAction],
    skips: List[Skip],
    overwrites: Optional[List[PlannedOverwrite]] = None,
) -> None:
    """POS+Template+Slot closure for a single source POS.

    Each Add/Skip decision uses GUID-presence in the target; FR-009 still
    permits duplicates but the convention validated in STATUS.md is "if
    target already has the source GUID, skip with ALREADY_PRESENT_BY_GUID
    (informational)".

    Closure semantics (FR-013, T076):
      * `selection.include_closure=True` (default): pull every reachable
        piece in the verb vertical. Non-seed pieces carry `pulled_in_by`
        pointing at their owner (POS for templates, template for slots).
      * `selection.include_closure=False`: only emit actions for pieces in
        categories the user explicitly toggled on. Pieces whose dependencies
        (owner POS for templates, slots referenced by templates) are NOT
        also user-selected become `Skip(reason=BARE_BONES_MISSING_CLOSURE)`.
    """
    # Caller already validated that `src_pos` belongs to source; if it's None
    # (defensive), bail out.
    if src_pos is None:
        return

    # Per-scope closure for POS / AFFIX_TEMPLATES / SLOTS.
    # Scope AS_NEEDED or ALL -> closure on for that category; NONE -> off.
    pos_scope = selection.scope_for(GrammarCategory.POS)
    tpl_scope = selection.scope_for(GrammarCategory.AFFIX_TEMPLATES)
    slots_scope = selection.scope_for(GrammarCategory.SLOTS)
    # Legacy closure_on: True when ANY of the three is AS_NEEDED or ALL.
    # Used as a fallback for the inter-layer "pull in" logic below.
    closure_on = any(
        s in (CategoryScope.AS_NEEDED, CategoryScope.ALL)
        for s in (pos_scope, tpl_scope, slots_scope)
    )
    pos_on = selection.is_on(GrammarCategory.POS)
    tpl_on = selection.is_on(GrammarCategory.AFFIX_TEMPLATES)
    slots_on = selection.is_on(GrammarCategory.SLOTS)

    src_verb = src_pos  # historical local name preserved; "verb" → "POS" here
    src_verb_guid = _guid_str(src_verb)

    # ----- POS layer -----
    # POS has no upstream dependency in our scope; if the user selected it
    # OR closure is on and something downstream wants it, plan it.
    pos_wanted = pos_on or (closure_on and (tpl_on or slots_on))
    if pos_wanted:
        if _target_has_pos_guid(target, src_verb_guid,
                                src_pos=src_verb, source_handle=source):
            _emit_present_outcome(
                GrammarCategory.POS,
                src_guid=src_verb_guid,
                target_guid=src_verb_guid,
                summary=f"POS already present (guid {src_verb_guid[:8]}…)",
                skip_detail="POS 'Verb' already present in target by GUID",
                selection=selection,
                skips=skips,
                overwrites=overwrites,
            )
        else:
            actions.append(PlannedAction(
                category=GrammarCategory.POS,
                source_guid=src_verb_guid,
                intended_target_guid=src_verb_guid,
                summary=f"POS 'Verb' (guid {src_verb_guid[:8]}…)",
                pulled_in_by=() if pos_on else (src_verb_guid,),  # marker: pulled in
            ))

    # ----- Templates + slots -----
    for src_template_wrap in source.MorphRules.GetAllAffixTemplatesForPOS(src_verb):
        src_template = src_template_wrap.concrete
        tpl_guid = _guid_str(src_template)

        slots_present = any(
            True
            for slot_iter in (
                src_template_wrap.prefix_slots,
                src_template_wrap.suffix_slots,
                src_template_wrap.proclitic_slots,
                src_template_wrap.enclitic_slots,
            )
            for _ in slot_iter
        )

        if tpl_on:
            # User explicitly selected templates. Check that dependencies
            # (owner POS + slots) are satisfied under closure-off mode.
            if not closure_on:
                missing_deps = []
                if not pos_on:
                    missing_deps.append("owner POS")
                if slots_present and not slots_on:
                    missing_deps.append("slots")
                if missing_deps:
                    skips.append(Skip(
                        category=GrammarCategory.AFFIX_TEMPLATES,
                        source_guid=tpl_guid,
                        reason=SkipReason.BARE_BONES_MISSING_CLOSURE,
                        detail=(
                            f"template skipped: closure off and unselected dep(s): "
                            + ", ".join(missing_deps)
                        ),
                    ))
                    # Skip the slot layer for this template too — there's
                    # nothing to attach them to.
                    continue
            _emit_template(target, src_verb_guid, tpl_guid, tpl_on, actions, skips, selection, overwrites,
                           src_owner_pos=src_verb, source_handle=source)
        elif closure_on:
            # Pulled in via closure from POS or slots being on.
            if pos_on or slots_on:
                _emit_template(target, src_verb_guid, tpl_guid, False, actions, skips, selection, overwrites,
                               src_owner_pos=src_verb, source_handle=source)
            else:
                continue
        else:
            # closure off + templates not selected → template doesn't appear
            continue

        # ----- Slot layer (only reached if template was planned, not skipped) -----
        for kind_label, slot_iter in (
            ("prefix", src_template_wrap.prefix_slots),
            ("suffix", src_template_wrap.suffix_slots),
            ("proclitic", src_template_wrap.proclitic_slots),
            ("enclitic", src_template_wrap.enclitic_slots),
        ):
            for slot in slot_iter:
                if slots_on:
                    pass  # plan
                elif closure_on:
                    pass  # pulled in
                else:
                    continue  # closure off + slots not selected → omit silently

                slot_guid = _guid_str(slot)
                slot_name = _slot_name(slot)
                if _target_has_slot_guid(target, src_verb_guid, slot_guid,
                                 src_owner_pos=src_verb, source_handle=source):
                    _emit_present_outcome(
                        GrammarCategory.SLOTS,
                        src_guid=slot_guid,
                        target_guid=slot_guid,
                        summary=f"Slot {slot_name!r} ({kind_label}) already present",
                        skip_detail=f"Slot {slot_name!r} ({kind_label}) already present by GUID",
                        selection=selection,
                        skips=skips,
                        overwrites=overwrites,
                        pulled_in_by=() if slots_on else (tpl_guid,),
                        owner_guid=src_verb_guid,  # POS owner; slots live under POS.AffixSlotsOC
                    )
                else:
                    actions.append(PlannedAction(
                        category=GrammarCategory.SLOTS,
                        source_guid=slot_guid,
                        intended_target_guid=slot_guid,
                        summary=f"Slot {slot_name!r} ({kind_label}) in Verb template",
                        pulled_in_by=() if slots_on else (tpl_guid,),
                    ))


def _plan_layer3_verb_affixes_inner(
    source,
    target,
    src_pos,
    selection: Selection,
    actions: List[PlannedAction],
    skips: List[Skip],
    overwrites: Optional[List[PlannedOverwrite]] = None,
    excluded_lossy: Optional[List[ExcludedLossy]] = None,
    identity_remap: dict = None,
) -> None:
    """Walk Layer 3 for a single source POS: every source LexEntry whose
    Sense's MSA is an IMoInflAffMsa pointing at this POS. Each yields
    ENTRY+SENSE+MSA actions; each Allomorph on the entry yields an
    ALLOMORPH action; each PhEnvironment referenced by an allomorph
    (deduplicated) yields a PH_ENVIRONMENT action.

    Layer 3 is gated by category toggles:
    - ENTRY / SENSE / MSA / ALLOMORPH / PH_ENVIRONMENT must each be selected
      (or pulled in via closure when include_closure=True).
    Layer 3 is also gated by Layer 1+2 being present in the plan or target
    (POS + template + slots) — without them the MSA cross-references can't
    resolve.
    """
    src_verb = src_pos  # name retained for in-function brevity
    if src_verb is None:
        return

    if identity_remap is None:
        identity_remap = {}

    # Per-scope closure for Layer 3 categories.
    # NONE -> closure off for that category; AS_NEEDED or ALL -> closure on.
    def _scope_on(cat: GrammarCategory) -> bool:
        return selection.scope_for(cat) in (CategoryScope.AS_NEEDED, CategoryScope.ALL)

    closure_on = any(
        _scope_on(c) for c in (
            GrammarCategory.ENTRY,
            GrammarCategory.SENSE,
            GrammarCategory.MSA,
            GrammarCategory.ALLOMORPH,
            GrammarCategory.PH_ENVIRONMENT,
        )
    )
    any_l3_user = any(
        selection.is_on(c) for c in (
            GrammarCategory.ENTRY,
            GrammarCategory.SENSE,
            GrammarCategory.MSA,
            GrammarCategory.ALLOMORPH,
            GrammarCategory.PH_ENVIRONMENT,
        )
    )
    if not (any_l3_user or closure_on):
        return  # Layer 3 not selected and closure off → skip
    # Defensive: fake-source unit tests don't carry LexEntry/Allomorphs
    # accessors. Layer 3 silently skips when the source can't be walked.
    if not (hasattr(source, "LexEntry") and hasattr(source, "Allomorphs")):
        return

    src_verb_guid = _guid_str(src_verb)

    # Cache the source slot GUIDs (they should appear in target after Layer 2;
    # MSA.SlotsRC re-references them by GUID).
    src_slot_guids = set()
    for _wrap in source.MorphRules.GetAllAffixTemplatesForPOS(src_verb):
        for slot_iter in (
            _wrap.prefix_slots, _wrap.suffix_slots,
            _wrap.proclitic_slots, _wrap.enclitic_slots,
        ):
            for sl in slot_iter:
                src_slot_guids.add(_guid_str(sl))

    seen_env_guids = set()

    # Build a GUID → target-entry index once for the duration of this walk
    # (Phase 1 overwrite path uses it for direct-GUID lookup of entries/senses;
    # they're factory-created with Guid preserved, so target.LexEntry.GetAll
    # contains them under the source GUIDs).
    target_entry_index = None  # lazily built when enable_overwrite is True

    def _target_has_entry_guid(target, guid: str) -> bool:
        nonlocal target_entry_index
        if target_entry_index is None:
            target_entry_index = {}
            if hasattr(target, "LexEntry"):
                for te in target.LexEntry.GetAll():
                    target_entry_index[_guid_str(_unwrap(te))] = te
        return guid in target_entry_index

    for entry in source.LexEntry.GetAll():
        entry_qualifies = False
        sense_actions = []
        msa_actions = []

        for sense in source.LexEntry.GetSenses(entry):
            msa = _lex_sense_msa(sense)
            if msa is None:
                continue
            if _classname_of(msa) != "MoInflAffMsa":
                continue
            if not _msa_points_at_verb(msa, src_verb_guid):
                continue
            entry_qualifies = True
            sense_guid = _guid_str(sense)
            msa_guid = _guid_str(msa)
            sense_actions.append((sense, sense_guid))
            msa_actions.append((msa, msa_guid, sense_guid))

        if not entry_qualifies:
            continue

        entry_guid = _guid_str(entry)
        entry_hw = source.LexEntry.GetHeadword(entry)

        # Phase 1 (FR-101/108): if enable_overwrite is set AND the entry's
        # GUID already exists in the target, emit a PlannedOverwrite instead
        # of an ADD. Senses are owned by entries; since entry GUIDs are
        # factory-preserved in Phase 0, an entry already-in-target implies
        # its senses are too (we promote both to overwrites in lockstep).
        entry_is_overwrite = (
            selection.enable_overwrite
            and overwrites is not None
            and _target_has_entry_guid(target, entry_guid)
        )

        # T-FR001: Phase-1.5 similar-resolution hook.
        # Entry-is-overwrite (same GUID in target) takes priority — checked first.
        # Only read resolution when the entry is NOT already a same-GUID overwrite.
        if not entry_is_overwrite and overwrites is not None:
            resolution = selection.similar_resolution_for(entry_guid)
            if resolution is not None and resolution.action in ("overwrite", "merge"):
                # Identity-remap path: plan ENTRY action against the resolved target GUID.
                tgt_entry_for_remap = None
                if target_entry_index is None:
                    # Force-build the index now.
                    _target_has_entry_guid(target, resolution.target_guid)
                tgt_entry_for_remap = (target_entry_index or {}).get(resolution.target_guid)
                overwrites.append(PlannedOverwrite(
                    category=GrammarCategory.ENTRY,
                    source_guid=entry_guid,
                    target_guid=resolution.target_guid,
                    summary=f"LexEntry {entry_hw!r} -> identity remap",
                    match_via="identity_remap",
                    write_mode=resolution.action,
                    pulled_in_by=() if selection.is_on(GrammarCategory.ENTRY)
                                 else (src_verb_guid,),
                    owner_guid="",
                    reference_decisions=_overwrite_reference_decisions(
                        "LexEntry", entry_guid, entry, target,
                        _OVERWRITE_ENTRY_REF_FIELDS, source=source,
                    ),
                ))
                identity_remap[entry_guid] = resolution.target_guid
                if tgt_entry_for_remap is not None:
                    _plan_identity_remap_children(
                        entry, entry_guid, entry_hw, resolution.target_guid,
                        tgt_entry_for_remap, src_verb_guid, src_slot_guids,
                        source, target, selection,
                        actions, skips, overwrites, seen_env_guids,
                    )
                continue  # skip Phase-0 add path for this entry

        if entry_is_overwrite:
            overwrites.append(PlannedOverwrite(
                category=GrammarCategory.ENTRY,
                source_guid=entry_guid,
                target_guid=entry_guid,
                summary=f"LexEntry {entry_hw!r}",
                match_via="guid",
                pulled_in_by=() if selection.is_on(GrammarCategory.ENTRY) else (src_verb_guid,),
                owner_guid="",  # LexEntries are LexDb-owned; no parent ref needed
                reference_decisions=_overwrite_reference_decisions(
                    "LexEntry", entry_guid, entry, target,
                    _OVERWRITE_ENTRY_REF_FIELDS, source=source,
                ),
            ))
            for _sense, sense_guid in sense_actions:
                overwrites.append(PlannedOverwrite(
                    category=GrammarCategory.SENSE,
                    source_guid=sense_guid,
                    target_guid=sense_guid,
                    summary=f"Sense of {entry_hw!r}",
                    match_via="guid",
                    pulled_in_by=(entry_guid,),
                    owner_guid=entry_guid,
                    reference_decisions=_overwrite_reference_decisions(
                        "LexSense", sense_guid, _sense, target,
                        _OVERWRITE_SENSE_REF_FIELDS, source=source,
                    ),
                ))
            # Phase 1.2 (FR-104): MSAs and Allomorphs are matched by
            # fingerprint against the target entry's existing MSAs and
            # allomorphs. Their GUIDs were re-assigned in Phase 0, so
            # direct GUID lookup fails — but the fingerprint
            # (class+pos+slots for MSA; lexeme_form+morphtype for
            # allomorph) is stable across runs because every piece of
            # information in it is GUID-preserved (entry, slot, morphtype).
            tgt_entry = target_entry_index[entry_guid]
            msa_match_via, _msa_overwrite_pairs, _msa_add_list = _match_msas_by_fingerprint(
                target, tgt_entry, msa_actions, entry_guid,
            )
            for src_msa, msa_guid, sense_guid in _msa_overwrite_pairs:
                tgt_msa_guid = msa_match_via[msa_guid]
                overwrites.append(PlannedOverwrite(
                    category=GrammarCategory.MSA,
                    source_guid=msa_guid,
                    target_guid=tgt_msa_guid,
                    summary=f"InflAffMsa for {entry_hw!r}",
                    match_via="fingerprint",
                    pulled_in_by=(sense_guid,),
                    owner_guid=entry_guid,
                ))
            for _src_msa, msa_guid, sense_guid in _msa_add_list:
                actions.append(PlannedAction(
                    category=GrammarCategory.MSA,
                    source_guid=msa_guid,
                    intended_target_guid=msa_guid,
                    summary=f"InflAffMsa for {entry_hw!r}",
                    pulled_in_by=(sense_guid,),
                ))
            # Allomorphs: same pattern with default-vernacular WS handle.
            allo_match_via, _allo_overwrite_list, _allo_add_list = _match_allomorphs_by_fingerprint(
                source, target, tgt_entry, entry, entry_guid,
            )
            for src_allo, allo_guid in _allo_overwrite_list:
                tgt_allo_guid = allo_match_via[allo_guid]
                overwrites.append(PlannedOverwrite(
                    category=GrammarCategory.ALLOMORPH,
                    source_guid=allo_guid,
                    target_guid=tgt_allo_guid,
                    summary=f"Allomorph of {entry_hw!r}",
                    match_via="fingerprint",
                    pulled_in_by=(entry_guid,),
                    owner_guid=entry_guid,
                ))
            for _src_allo, allo_guid in _allo_add_list:
                actions.append(PlannedAction(
                    category=GrammarCategory.ALLOMORPH,
                    source_guid=allo_guid,
                    intended_target_guid=allo_guid,
                    summary=f"Allomorph of {entry_hw!r}",
                    pulled_in_by=(entry_guid,),
                ))
            # Phone-environments: scoped to the entry, independent of MSA/Allomorph
            # overwrite outcome. Each source allomorph may reference one or more
            # environments; same target-presence check as Phase 0.
            for allo in source.Allomorphs.GetAll(entry):
                allo_obj = _unwrap(allo)
                allo_guid = _guid_str(allo_obj)
                envs = source.Allomorphs.GetPhoneEnv(allo)
                if envs is None:
                    continue
                for env in envs:
                    env_obj = _unwrap(env)
                    env_guid = _guid_str(env_obj)
                    if env_guid in seen_env_guids:
                        continue
                    seen_env_guids.add(env_guid)
                    if _target_has_environment_guid(target, env_guid):
                        if selection.enable_overwrite:
                            overwrites.append(PlannedOverwrite(
                                category=GrammarCategory.PH_ENVIRONMENT,
                                source_guid=env_guid,
                                target_guid=env_guid,
                                summary="PhEnvironment overwrite (referenced by allomorph(s))",
                                match_via="guid",
                                pulled_in_by=(allo_guid,),
                                owner_guid="",
                            ))
                        else:
                            skips.append(Skip(
                                category=GrammarCategory.PH_ENVIRONMENT,
                                source_guid=env_guid,
                                reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                                detail="PhEnvironment already present in target by GUID",
                            ))
                    else:
                        actions.append(PlannedAction(
                            category=GrammarCategory.PH_ENVIRONMENT,
                            source_guid=env_guid,
                            intended_target_guid=env_guid,
                            summary="PhEnvironment referenced by allomorph(s)",
                            pulled_in_by=(allo_guid,),
                        ))
            continue  # skip the Phase 0 add path below for this entry

        # Entry, sense, MSA actions (Phase 0 path — entry not in target)
        actions.append(PlannedAction(
            category=GrammarCategory.ENTRY,
            source_guid=entry_guid,
            intended_target_guid=entry_guid,
            summary=f"LexEntry {entry_hw!r}",
            pulled_in_by=() if selection.is_on(GrammarCategory.ENTRY) else (src_verb_guid,),
        ))
        for _sense, sense_guid in sense_actions:
            actions.append(PlannedAction(
                category=GrammarCategory.SENSE,
                source_guid=sense_guid,
                intended_target_guid=sense_guid,
                summary=f"Sense of {entry_hw!r}",
                pulled_in_by=(entry_guid,),
            ))
        for _msa, msa_guid, sense_guid in msa_actions:
            actions.append(PlannedAction(
                category=GrammarCategory.MSA,
                source_guid=msa_guid,
                intended_target_guid=msa_guid,
                summary=f"InflAffMsa for {entry_hw!r}",
                pulled_in_by=(sense_guid,),
            ))

        # Phase 3c Selection UI: EXCLUDED-LOSSY check for MSA.PartOfSpeechRA.
        # If the user scoped POS to NONE or per-item excluded the POS GUID, and
        # the target does not already have it, emit an entry-centric warning.
        if excluded_lossy is not None:
            for _msa, msa_guid, _sense_guid in msa_actions:
                _check_msa_pos_excluded_lossy(
                    _msa, entry_guid, entry_hw, target, selection, excluded_lossy,
                    source_handle=source,
                )

        # Allomorphs + environments. Allomorphs.GetAll may return wrapped
        # objects (similar to MorphRules templates); _unwrap handles both.
        for allo in source.Allomorphs.GetAll(entry):
            allo_obj = _unwrap(allo)
            allo_guid = _guid_str(allo_obj)
            actions.append(PlannedAction(
                category=GrammarCategory.ALLOMORPH,
                source_guid=allo_guid,
                intended_target_guid=allo_guid,
                summary=f"Allomorph of {entry_hw!r}",
                pulled_in_by=(entry_guid,),
            ))
            envs = source.Allomorphs.GetPhoneEnv(allo)
            if envs is None:
                continue
            for env in envs:
                env_obj = _unwrap(env)
                env_guid = _guid_str(env_obj)
                if env_guid in seen_env_guids:
                    continue
                seen_env_guids.add(env_guid)
                # PhEnvironments are project-wide and often shared across
                # FW projects via standard templates. Check target presence
                # before emitting an action; if it's already there, emit a
                # Skip(ALREADY_PRESENT_BY_GUID) so transfer.py reuses the
                # existing object instead of trying to Create a duplicate
                # GUID (which LCM rejects).
                if _target_has_environment_guid(target, env_guid):
                    if selection.enable_overwrite:
                        overwrites.append(PlannedOverwrite(
                            category=GrammarCategory.PH_ENVIRONMENT,
                            source_guid=env_guid,
                            target_guid=env_guid,
                            summary=f"PhEnvironment overwrite (referenced by allomorph(s))",
                            match_via="guid",
                            pulled_in_by=(allo_guid,),
                            owner_guid="",
                        ))
                    else:
                        skips.append(Skip(
                            category=GrammarCategory.PH_ENVIRONMENT,
                            source_guid=env_guid,
                            reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                            detail=f"PhEnvironment already present in target by GUID",
                        ))
                else:
                    actions.append(PlannedAction(
                        category=GrammarCategory.PH_ENVIRONMENT,
                        source_guid=env_guid,
                        intended_target_guid=env_guid,
                        summary=f"PhEnvironment referenced by allomorph(s)",
                        pulled_in_by=(allo_guid,),
                    ))


def _check_msa_pos_excluded_lossy(
    msa,
    entry_guid: str,
    entry_label: str,
    target,
    selection: Selection,
    excluded_lossy: List[ExcludedLossy],
    *,
    source_handle=None,
) -> None:
    """Emit an EXCLUDED-LOSSY warning if the entry's MSA references a POS that
    the user deliberately dropped (via NONE scope or per-item exclusion) and
    the target does not already have it.

    Outcome table (plan.md section (e)):
    1. dep exists in target by GUID -> silent (LINK).
    2. dep absent + entry doesn't reference it -> not reached here.
    3. dep absent + entry references it + user dropped it -> EXCLUDED-LOSSY.

    T106: outcome 1 is called "LINK" for a reason -- the question is whether
    the MSA will end up linked to a CATEGORY, not whether one exact object
    survives. Post-T091 the destination may hold that category under a
    different GUID, where the MSA links fine and outcome 3's message ("Entry X
    will have no Part of Speech") is simply false. A warning that cries loss
    where there was none teaches the reader to stop reading it -- the phantom
    -loss shape CLAUDE.md records for flexicon 4.5.1. `source_handle` is
    keyword-only and defaults to None, so a caller that cannot supply it keeps
    the pre-T106 answer rather than silently changing behaviour.
    """
    try:
        from SIL.LCModel import IMoInflAffMsa, ICmObject
        ia = IMoInflAffMsa(_unwrap(msa))
        if ia.PartOfSpeechRA is None:
            return
        pos_guid = str(ICmObject(ia.PartOfSpeechRA).Guid).lower()
    except Exception:
        return

    pos_scope = selection.scope_for(GrammarCategory.POS)
    dep_excluded = (
        pos_scope == CategoryScope.NONE
        or selection.is_dep_excluded(pos_guid)
    )
    if not dep_excluded:
        return

    # Outcome 1: target already has it (LINK) — silent. T106: by GUID, or by
    # the natural key when the caller supplied the source handle.
    if _target_has_pos_guid(target, pos_guid,
                            src_pos=ia.PartOfSpeechRA,
                            source_handle=source_handle):
        return

    # Outcome 3: target lacks it and entry references it — EXCLUDED-LOSSY.
    excluded_lossy.append(ExcludedLossy(
        category=GrammarCategory.ENTRY,
        entry_guid=entry_guid,
        entry_label=entry_label,
        dep_category=GrammarCategory.POS,
        dep_guid=pos_guid,
        dep_label=f"POS ({pos_guid[:8]}...)",
        message=f"Entry {entry_label!r} will have no Part of Speech.",
    ))


def _target_has_environment_guid(target, env_guid: str) -> bool:
    """True iff the target's PhonologicalData.EnvironmentsOS contains this GUID."""
    try:
        envs = target.Environments.GetAll()
    except AttributeError:
        return False
    for e in envs:
        if _guid_str(_unwrap(e)) == env_guid:
            return True
    return False


def _lex_sense_msa(sense):
    from SIL.LCModel import ILexSense
    return ILexSense(sense).MorphoSyntaxAnalysisRA


def _classname_of(obj):
    from SIL.LCModel import ICmObject
    return ICmObject(obj).ClassName


def _match_msas_by_fingerprint(target, tgt_entry, msa_actions, entry_guid: str):
    """Match source MSAs against target MSAs on the same entry by fingerprint
    (FR-104). Returns:

    - `match_via`: dict[source_msa_guid → target_msa_guid] for matched pairs
    - `overwrite_pairs`: list of (src_msa, msa_guid, sense_guid) to overwrite
    - `add_list`: list of (src_msa, msa_guid, sense_guid) that found no match

    The fingerprint per FR-104 is (category, owner_entry_guid, "MoInflAffMsa",
    pos_guid, frozenset(slot_guids)). Built independently for source and target.
    """
    from SIL.LCModel import ILexEntry, ICmObject

    # Compute target-side fingerprints → target msa guid map.
    target_fp_to_guid = {}
    try:
        for tmsa in ILexEntry(tgt_entry).MorphoSyntaxAnalysesOC:
            if _classname_of(tmsa) != "MoInflAffMsa":
                continue
            fp = _msa_fingerprint(tmsa, entry_guid)
            target_fp_to_guid[fp] = str(ICmObject(tmsa).Guid).lower()
    except (AttributeError, TypeError):
        pass

    match_via = {}
    overwrite_pairs = []
    add_list = []
    for src_msa, msa_guid, sense_guid in msa_actions:
        fp = _msa_fingerprint(src_msa, entry_guid)
        tgt_msa_guid = target_fp_to_guid.get(fp)
        if tgt_msa_guid is not None:
            match_via[msa_guid] = tgt_msa_guid
            overwrite_pairs.append((src_msa, msa_guid, sense_guid))
        else:
            add_list.append((src_msa, msa_guid, sense_guid))
    return match_via, overwrite_pairs, add_list


def _msa_fingerprint(msa, owner_entry_guid: str):
    """Inline fingerprint for MSA matching — avoids the matcher.py
    indirection so the planner can operate on flexicon wrappers
    transparently."""
    from SIL.LCModel import IMoInflAffMsa, ICmObject
    ia = IMoInflAffMsa(_unwrap(msa))
    pos_guid = ""
    if ia.PartOfSpeechRA is not None:
        pos_guid = str(ICmObject(ia.PartOfSpeechRA).Guid).lower()
    slot_guids = frozenset(str(ICmObject(sl).Guid).lower() for sl in ia.SlotsRC)
    return (GrammarCategory.MSA, owner_entry_guid.lower(), "MoInflAffMsa", pos_guid, slot_guids)


def _match_allomorphs_by_fingerprint(source, target, tgt_entry, src_entry, entry_guid: str):
    """Match source allomorphs against target allomorphs on the same entry
    by fingerprint (FR-104). Returns the same shape as _match_msas_by_fingerprint.

    Fingerprint per FR-104:
    (category, owner_entry_guid, lexeme_form_text, morph_type_guid).
    """
    from SIL.LCModel import ICmObject
    cache = getattr(target, "Cache", None)
    ws_handle = None
    try:
        if cache is not None:
            ws_handle = cache.DefaultVernWs
    except AttributeError:
        ws_handle = None

    # Target-side fingerprints
    target_fp_to_guid = {}
    try:
        for tallo in target.Allomorphs.GetAll(tgt_entry):
            tallo_obj = _unwrap(tallo)
            fp = _allomorph_fingerprint(tallo_obj, entry_guid, ws_handle)
            target_fp_to_guid[fp] = str(ICmObject(tallo_obj).Guid).lower()
    except (AttributeError, TypeError):
        pass

    match_via = {}
    overwrite_list = []
    add_list = []
    src_ws_handle = None
    try:
        src_cache = getattr(source, "Cache", None)
        if src_cache is not None:
            src_ws_handle = src_cache.DefaultVernWs
    except AttributeError:
        src_ws_handle = None
    for sallo in source.Allomorphs.GetAll(src_entry):
        sallo_obj = _unwrap(sallo)
        allo_guid = _guid_str(sallo_obj)
        fp = _allomorph_fingerprint(sallo_obj, entry_guid, src_ws_handle)
        tgt_allo_guid = target_fp_to_guid.get(fp)
        if tgt_allo_guid is not None:
            match_via[allo_guid] = tgt_allo_guid
            overwrite_list.append((sallo_obj, allo_guid))
        else:
            add_list.append((sallo_obj, allo_guid))
    return match_via, overwrite_list, add_list


def _allomorph_fingerprint(allo, owner_entry_guid: str, ws_handle):
    """Inline allomorph fingerprint per FR-104."""
    from SIL.LCModel import IMoAffixAllomorph, ICmObject
    ia = IMoAffixAllomorph(allo)
    morph_type_guid = ""
    if ia.MorphTypeRA is not None:
        morph_type_guid = str(ICmObject(ia.MorphTypeRA).Guid).lower()
    lexeme_form_text = ""
    if ws_handle is not None:
        try:
            ts_string = ia.Form.get_String(ws_handle)
            lexeme_form_text = (ts_string.Text or "") if ts_string is not None else ""
        except (AttributeError, TypeError):
            lexeme_form_text = ""
    return (GrammarCategory.ALLOMORPH, owner_entry_guid.lower(), lexeme_form_text, morph_type_guid)


def _plan_identity_remap_children(
    src_entry,
    src_entry_guid: str,
    src_entry_hw: str,
    tgt_entry_guid: str,
    tgt_entry,
    src_verb_guid: str,
    src_slot_guids: set,
    source,
    target,
    selection: "Selection",
    actions: list,
    skips: list,
    overwrites: list,
    seen_env_guids: set,
) -> None:
    """Plan MSA / Allomorph / PhEnvironment children for an identity-remap entry.

    Mirrors the Phase-1 fingerprint block in _plan_layer3_verb_affixes_inner
    (lines 609-703) but uses tgt_entry_guid (the resolved target GUID) as the
    owner override so fingerprint comparison is against the resolved target's
    children rather than the source entry.

    Called from two sites:
    - T-FR001 identity-remap branch in _plan_layer3_verb_affixes_inner.
    """
    # Collect source MSA/sense actions for this entry.
    sense_actions = []
    msa_actions = []
    for sense in source.LexEntry.GetSenses(src_entry):
        msa = _lex_sense_msa(sense)
        if msa is None:
            continue
        if _classname_of(msa) != "MoInflAffMsa":
            continue
        if not _msa_points_at_verb(msa, src_verb_guid):
            continue
        sense_guid = _guid_str(sense)
        msa_guid = _guid_str(msa)
        sense_actions.append((sense, sense_guid))
        msa_actions.append((msa, msa_guid, sense_guid))

    # MSA fingerprint matching against the resolved target entry.
    # Use tgt_entry_guid as the owner override so cross-entry comparison works.
    msa_match_via, _msa_overwrite_pairs, _msa_add_list = _match_msas_by_fingerprint(
        target, tgt_entry, msa_actions, tgt_entry_guid,
    )
    for src_msa, msa_guid, sense_guid in _msa_overwrite_pairs:
        tgt_msa_guid = msa_match_via[msa_guid]
        overwrites.append(PlannedOverwrite(
            category=GrammarCategory.MSA,
            source_guid=msa_guid,
            target_guid=tgt_msa_guid,
            summary=f"InflAffMsa for {src_entry_hw!r} (identity remap)",
            match_via="fingerprint",
            pulled_in_by=(sense_guid,),
            owner_guid=tgt_entry_guid,
        ))
    for _src_msa, msa_guid, sense_guid in _msa_add_list:
        actions.append(PlannedAction(
            category=GrammarCategory.MSA,
            source_guid=msa_guid,
            intended_target_guid=msa_guid,
            summary=f"InflAffMsa for {src_entry_hw!r} (identity remap)",
            pulled_in_by=(sense_guid,),
        ))

    # Allomorph fingerprint matching against the resolved target entry.
    allo_match_via, _allo_overwrite_list, _allo_add_list = _match_allomorphs_by_fingerprint(
        source, target, tgt_entry, src_entry, tgt_entry_guid,
    )
    for src_allo, allo_guid in _allo_overwrite_list:
        tgt_allo_guid = allo_match_via[allo_guid]
        overwrites.append(PlannedOverwrite(
            category=GrammarCategory.ALLOMORPH,
            source_guid=allo_guid,
            target_guid=tgt_allo_guid,
            summary=f"Allomorph of {src_entry_hw!r} (identity remap)",
            match_via="fingerprint",
            pulled_in_by=(src_entry_guid,),
            owner_guid=tgt_entry_guid,
        ))
    for _src_allo, allo_guid in _allo_add_list:
        actions.append(PlannedAction(
            category=GrammarCategory.ALLOMORPH,
            source_guid=allo_guid,
            intended_target_guid=allo_guid,
            summary=f"Allomorph of {src_entry_hw!r} (identity remap)",
            pulled_in_by=(src_entry_guid,),
        ))

    # Phone-environments for allomorphs under the resolved entry.
    for allo in source.Allomorphs.GetAll(src_entry):
        allo_obj = _unwrap(allo)
        allo_guid = _guid_str(allo_obj)
        envs = source.Allomorphs.GetPhoneEnv(allo)
        if envs is None:
            continue
        for env in envs:
            env_obj = _unwrap(env)
            env_guid = _guid_str(env_obj)
            if env_guid in seen_env_guids:
                continue
            seen_env_guids.add(env_guid)
            if _target_has_environment_guid(target, env_guid):
                if selection.enable_overwrite:
                    overwrites.append(PlannedOverwrite(
                        category=GrammarCategory.PH_ENVIRONMENT,
                        source_guid=env_guid,
                        target_guid=env_guid,
                        summary="PhEnvironment overwrite (identity remap allomorph)",
                        match_via="guid",
                        pulled_in_by=(allo_guid,),
                        owner_guid="",
                    ))
                else:
                    skips.append(Skip(
                        category=GrammarCategory.PH_ENVIRONMENT,
                        source_guid=env_guid,
                        reason=SkipReason.ALREADY_PRESENT_BY_GUID,
                        detail="PhEnvironment already present in target by GUID",
                    ))
            else:
                actions.append(PlannedAction(
                    category=GrammarCategory.PH_ENVIRONMENT,
                    source_guid=env_guid,
                    intended_target_guid=env_guid,
                    summary="PhEnvironment referenced by identity-remap allomorph",
                    pulled_in_by=(allo_guid,),
                ))


def _msa_points_at_verb(msa, verb_guid: str) -> bool:
    from SIL.LCModel import IMoInflAffMsa, ICmObject
    ia = IMoInflAffMsa(msa)
    if ia.PartOfSpeechRA is None:
        return False
    return str(ICmObject(ia.PartOfSpeechRA).Guid).lower() == verb_guid


def _emit_template(target,
                   owner_pos_guid: str,
                   tpl_guid: str,
                   user_selected: bool,
                   actions: List[PlannedAction],
                   skips: List[Skip],
                   selection: Selection,
                   overwrites: Optional[List[PlannedOverwrite]],
                   *,
                   src_owner_pos=None,
                   source_handle=None) -> None:
    """Emit Add or Skip-by-GUID (Phase 0) / Overwrite (Phase 1) for a template.

    T106: `owner_pos_guid` is the owning category's SOURCE GUID. The two
    keyword-only arguments carry what the natural key needs down to
    `_target_has_template_guid`; both default to None so an existing caller or
    fake keeps the identity-only answer.
    """
    if _target_has_template_guid(target, owner_pos_guid, tpl_guid,
                                 src_owner_pos=src_owner_pos,
                                 source_handle=source_handle):
        _emit_present_outcome(
            GrammarCategory.AFFIX_TEMPLATES,
            src_guid=tpl_guid,
            target_guid=tpl_guid,
            summary=f"Affix template already present (guid {tpl_guid[:8]}…)",
            skip_detail="Template already present in target by GUID",
            selection=selection,
            skips=skips,
            overwrites=overwrites,
            pulled_in_by=() if user_selected else (owner_pos_guid,),
            owner_guid=owner_pos_guid,
        )
    else:
        actions.append(PlannedAction(
            category=GrammarCategory.AFFIX_TEMPLATES,
            source_guid=tpl_guid,
            intended_target_guid=tpl_guid,
            summary=f"Affix template under Verb (guid {tpl_guid[:8]}…)",
            pulled_in_by=() if user_selected else (owner_pos_guid,),
        ))


# ============================================================================
# Read-only target probes
# ============================================================================

def _target_pos_for_source_guid(target, src_pos_guid: str, *, src_pos=None,
                                source_handle=None):
    """The destination category a SOURCE category GUID names -- identity
    first, roster-admitted natural key second (T106).

    Both keywords default to None and BOTH are required for step 2: the key is
    the category's `Name` (which a GUID string cannot supply) and it is scoped
    to the source writing systems (which only the source handle can supply).
    A caller that can reach only one of them gets exactly the pre-038 identity
    answer, which keeps this additive for every existing fake.

    Lazy import for the load-order reason `owned._resolve_target_pos_by_guid`
    documents.
    """
    if not src_pos_guid:
        return None
    try:
        if __package__:
            from . import categories as _categories
        else:
            import categories as _categories  # type: ignore
    except ImportError:  # pragma: no cover -- categories.py is always present
        return _find_pos_by_guid(target, src_pos_guid)
    return _categories._resolve_target_pos(
        target, src_pos_guid, src_pos=src_pos, source_handle=source_handle)


def _target_has_pos_guid(target, guid_str: str, *, src_pos=None,
                         source_handle=None) -> bool:
    """Is the category `guid_str` names present in the destination?

    T106: BOTH callers mean *is this CATEGORY present*, not *is this exact
    object present* -- one branches straight into "create a new category" and
    the other tells the user "Entry X will have no Part of Speech". Post-T091
    a category reused under a different GUID is present, and a GUID-only probe
    calls it absent: the first caller then plans a DUPLICATE and the second
    emits a warning about a loss that will not happen. The opt-in keywords are
    what let the probe answer the question the callers are actually asking.
    """
    for pos in target.POS.GetAll(recursive=True):
        if _guid_str(_unwrap(pos)) == guid_str:
            return True
    if src_pos is None or source_handle is None:
        return False
    return _target_pos_for_source_guid(
        target, guid_str, src_pos=src_pos,
        source_handle=source_handle) is not None


def _target_has_template_guid(target, owner_pos_guid: str, tpl_guid: str, *,
                              src_owner_pos=None, source_handle=None) -> bool:
    target_pos = _find_pos_by_guid(target, owner_pos_guid)
    if target_pos is None:
        # T106: `owner_pos_guid` is the owning category's SOURCE GUID. A miss
        # here made the planner emit an ADD for a template the destination
        # already holds -- a DUPLICATE rather than a lost item, the opposite
        # direction from T095's defect and the same root cause.
        target_pos = _target_pos_for_source_guid(
            target, owner_pos_guid, src_pos=src_owner_pos,
            source_handle=source_handle)
    if target_pos is None:
        return False
    for t in target.MorphRules.GetAllAffixTemplatesForPOS(target_pos):
        if _guid_str(_unwrap(t)) == tpl_guid:
            return True
    return False


def _target_has_slot_guid(target, owner_pos_guid: str, slot_guid: str, *,
                          src_owner_pos=None, source_handle=None) -> bool:
    target_pos = _find_pos_by_guid(target, owner_pos_guid)
    if target_pos is None:
        # T106: same source-side owner GUID, same duplicate-on-miss shape.
        target_pos = _target_pos_for_source_guid(
            target, owner_pos_guid, src_pos=src_owner_pos,
            source_handle=source_handle)
    if target_pos is None:
        return False
    for s in target.POS.GetAffixSlots(target_pos):
        if _guid_str(_unwrap(s)) == slot_guid:
            return True
    return False


def _find_pos_by_guid(target, guid_str: str):
    """Identity only. T106: every caller reaches it through one of the probes
    above, which supply the natural-key second step when they can; keeping
    this one identity-pure is what lets those probes stay additive."""
    for pos in target.POS.GetAll(recursive=True):
        concrete = _unwrap(pos)
        if _guid_str(concrete) == guid_str:
            return concrete
    return None


# ============================================================================
# Tiny utilities (LCM-aware but pure-property reads)
# ============================================================================

def _guid_str(obj) -> str:
    """Lower-cased string form of `obj.Guid`. Lazy-imports ICmObject so this
    module is import-safe outside FlexTools."""
    from SIL.LCModel import ICmObject  # lazy
    return str(ICmObject(obj).Guid).lower()


def _unwrap(obj):
    """Strip a flexicon wrapper to the concrete LCM object if present."""
    return obj.concrete if hasattr(obj, "concrete") else obj


def _slot_name(slot) -> str:
    from SIL.LCModel import IMoInflAffixSlot  # lazy
    txt = IMoInflAffixSlot(_unwrap(slot)).Name.BestAnalysisAlternative.Text
    # "***" is FLEx's empty-alternative sentinel; an unnamed slot has no name.
    return "" if txt in (None, "***") else txt
