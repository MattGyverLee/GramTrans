"""Run-report aggregation and snapshot-JSON serialization.

Implements `RunReport.to_snapshot_json()` per contracts/run-report.md. The
output JSON has stable field ordering so integration-test snapshot diffs are
meaningful.

Per constitution Principle III closing clause + FR-018, every PlannedAction
in the run plan must end up in either `per_category[*].added` or `skips` —
nothing disappears silently. The FR-018 invariant is enforced by
`RunReport.__post_init__` at construction time.

Feature 038 (FR-022 + SC-010) widens that promise from "nothing disappears"
to "every outcome is named": see `disposition_totals` /
`_render_disposition_lines` for the four-bucket panel (ADD / UPDATE-enriched /
SKIP / dropped-with-reason) and `certainty_note` for the one sentence this
report is allowed to say about how much its sameness claims are worth.
"""
from __future__ import annotations

import json
from typing import Iterable

if __package__:
    from .models import (
        CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES,
        CENSUS_PHASE_GATED_CLASSES,
        CENSUS_REPORT_ONLY_RESIDUE,
        CENSUS_REPORT_ONLY_STATE,
        CENSUS_ROW_STATES,
        CLASS_CENSUS_ROW_ARTIFACT_FIELDS,
        FIDELITY_CENSUS_ARTIFACT_FIELDS,
        STARTER_BASELINE_ARTIFACT_FIELDS,
        CategoryReport,
        DroppedItemRecord,
        ExcludedLossy,
        FidelityStatus,
        GrammarCategory,
        MatchBasis,
        PlannedAction,
        RunMode,
        RunPlan,
        RunReport,
        Skip,
        SkipReason,
    )
else:
    from models import (
        CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES,
        CENSUS_PHASE_GATED_CLASSES,
        CENSUS_REPORT_ONLY_RESIDUE,
        CENSUS_REPORT_ONLY_STATE,
        CENSUS_ROW_STATES,
        CLASS_CENSUS_ROW_ARTIFACT_FIELDS,
        FIDELITY_CENSUS_ARTIFACT_FIELDS,
        STARTER_BASELINE_ARTIFACT_FIELDS,
        CategoryReport,
        DroppedItemRecord,
        ExcludedLossy,
        FidelityStatus,
        GrammarCategory,
        MatchBasis,
        PlannedAction,
        RunMode,
        RunPlan,
        RunReport,
        Skip,
        SkipReason,
    )


# ============================================================================
# RunReport factory + methods (monkey-patched onto the frozen dataclass)
# ============================================================================
# We attach these as classmethods / methods on RunReport here rather than in
# models.py so models.py stays free of JSON / serialization concerns.

def _build_from_plan(cls, plan: RunPlan, mode: RunMode,
                     wall_clock_seconds: float = 0.0,
                     extra_skips=(),
                     extra_excluded_lossy=(),
                     extra_dropped_items=(),
                     fidelity_by_guid=None,
                     extra_leaf_execution_failures=(),
                     extra_closure_edges=(),
                     extra_incompleteness=(),
                     extra_enrichments=(),
                     extra_process_rules=(),
                     extra_affix_slot_links=(),
                     census=None) -> RunReport:
    """Build a finalized RunReport from a RunPlan.

    Iterates plan.actions to accumulate per-category added/closure_pulled_in
    counts, then iterates plan.skips to accumulate per-category skipped counts
    and the aggregate skips tuple. Returns a RunReport whose FR-018 invariant
    (checked in __post_init__) will pass because the counts are built from the
    same plan.

    `extra_dropped_items` (feature 024, FR-010/FR-013): the per-run
    ``dropped: list[DroppedItemRecord]`` collector threaded through the
    closure walk (Lib/categories.py) and the resolver/owned-walk (Lib/
    references.py, Lib/owned.py). Empty by default (foundational plumbing
    only — nothing appends to it yet; see contracts/dropped-item-report.md
    "Collection"). `fidelity_by_guid` is the per-object FidelityStatus map
    (FR-013); also empty by default until US4 (T023) computes it.

    `extra_leaf_execution_failures` (feature 037, defect C): the per-run
    ``list[LeafExecutionFailure]`` collector from transfer.execute()'s
    leaf-dispatch loop -- every swallowed `execute_action` exception, one
    record each. Empty by default (Preview mode never executes anything, so
    it never has any). Threaded straight onto
    ``RunReport.leaf_execution_failures``; `RunReport.leaf_failed` is a
    property computed from its length, not a separate field, so it cannot
    drift out of sync.

    `extra_affix_slot_links` (feature 038, T074): the per-affix FR-019 link
    outcomes collected by `categories._run_171_subpass` during execute. One
    record per source affix MSA that occupied a template column, so SC-003's
    numerator and denominator are both on the report. Empty in Preview mode by
    construction -- the sub-pass runs after the writes.

    `extra_closure_edges` / `extra_incompleteness` / `extra_enrichments` /
    `extra_process_rules` / `census` (feature 038): the four fidelity buckets
    plus the census. Each is UNIONed with the same-named tuple on the plan,
    so a producer may emit at plan time (Preview) or at execute time (Move)
    without this function caring which. All empty by default -- with no 038
    producers wired yet, every one of these is a no-op and the report renders
    exactly as it did before.
    """
    per_category: dict = {}

    def _bucket(cat):
        if cat not in per_category:
            per_category[cat] = {
                "added": 0, "skipped": 0, "closure_pulled_in": 0, "overwritten": 0,
                "interactive_resolved": 0, "interactive_skipped": 0,
                "ws_mapped": 0, "ws_created": 0, "ws_skipped": 0,
                "excluded_lossy": 0,
                # Feature 038 (see the counting notes further down).
                "identity_substitution": 0, "enriched": 0,
                "not_reproducible": 0,
            }
        return per_category[cat]

    # T024d-a: per-LCM-class tally of destination objects that already existed
    # and were matched to a source object -- the census's
    # `starter_matched_to_source`. See `RunReport.matched_by_class` for why this
    # is keyed by object class rather than by category, and
    # `matched_class_is_complete` for what the unattributed bucket costs.
    matched_by_class: dict = {}
    matches_unattributed: dict = {}

    def _matched_class(obj):
        """The LCM class name for a matched item, or None when unattributable.

        Only the two AUTHORITATIVE sources are consulted. There is deliberately
        no fallback to a category->class guess: `GrammarCategory` is not 1:1
        with object class for the affix and MSA categories, so a guess would
        credit the wrong census row -- and a wrongly-credited match subtracts
        the wrong number from the wrong class. Returning None routes the count
        to `matches_unattributed`, which withholds the `baseline_matched` basis
        instead of asserting a number nothing supports.
        """
        basis = getattr(obj, "match_basis", None)
        if basis is not None and getattr(basis, "object_class", ""):
            return basis.object_class
        enrichment = getattr(obj, "enrichment", None)
        if enrichment is not None and getattr(enrichment, "object_class", ""):
            return enrichment.object_class
        return None

    def _count_matched(obj, category) -> None:
        """Tally one match onto a pre-existing destination object."""
        object_class = _matched_class(obj)
        if object_class is None:
            matches_unattributed[category] = (
                matches_unattributed.get(category, 0) + 1
            )
        else:
            matched_by_class[object_class] = (
                matched_by_class.get(object_class, 0) + 1
            )

    def _action_matched_existing(action) -> bool:
        """True when an ADD action nonetheless landed on a destination object
        that already existed -- which is what a natural-key match on a starter
        object IS (FR-006). `PlannedAction.match_basis` is None for a genuinely
        brand-new create, so the default is correctly "not a match"; a record
        naming a concrete `target_guid` with a real basis is the evidence that
        an existing object was claimed.
        """
        basis = getattr(action, "match_basis", None)
        if basis is None:
            return False
        if getattr(basis, "basis", None) is MatchBasis.NONE:
            return False
        return bool(getattr(basis, "target_guid", ""))

    def _count_substitution(bucket, obj, *, always_matched: bool = False) -> None:
        """Feature 038 (FR-006): tally objects matched by a roster-admitted
        NATURAL KEY rather than by GUID. Counted from the `match_basis`
        record on the plan item itself, so the report cannot claim a stronger
        identity basis than the matcher actually used. Items planned before
        038's matcher ran carry `match_basis=None` and are not counted.

        `always_matched` (T037) enables a SECOND, weaker source of the same
        fact and is passed only where it is safe. `PlannedOverwrite` carries
        two independent records of natural-key-ness: the structured
        `match_basis` and the plain `match_via` string, whose legal values
        models.py documents as "guid"|"identity_remap"|"fingerprint"|
        "natural_key" -- the last added by this very feature for the Phase 2
        policy code that switches on it. A producer that sets only the string
        would otherwise have its substitution silently counted as an ordinary
        match, i.e. the report would assert a GUID-strength claim the matcher
        never made, which is precisely the defect FR-006 exists to remove. The
        string is consulted ONLY when no `match_basis` is present, so it can
        never contradict or double-count the structured record.

        Why the flag rather than an unconditional check: every substitution
        counted here must also be counted by `_count_matched`, or
        `RunReport.__post_init__` rejects the report with
        `identity_substituted > matched_to_source_total` and a legitimate run
        dies at report time. Overwrites are unconditionally matched (an
        overwrite writes onto an object that already existed), so the fallback
        is safe there. ADD actions are matched only via
        `_action_matched_existing`, which requires a real `match_basis` -- so
        the fallback must never fire on that path, and the flag is what makes
        that structural rather than a comment nobody reads.
        """
        basis = getattr(obj, "match_basis", None)
        if basis is not None:
            if getattr(basis, "basis", None) is MatchBasis.NATURAL_KEY:
                bucket["identity_substitution"] += 1
            return
        if always_matched and getattr(obj, "match_via", "") == "natural_key":
            bucket["identity_substitution"] += 1

    for action in plan.actions:
        b = _bucket(action.category)
        b["added"] += 1
        _count_substitution(b, action)
        # T024d-a: an ADD is normally a create and contributes nothing to the
        # matched tally; a natural-key match on a starter object is the
        # exception, and it is exactly the case the census needs counted.
        if _action_matched_existing(action):
            _count_matched(action, action.category)
        # plan.actions is heterogeneous: PlannedAction has `pulled_in_by`,
        # but CreateDefinitionAction (schema-level custom-field creates) does
        # not.  Tolerate its absence the same way the overwrites loop below does.
        if getattr(action, "pulled_in_by", ()):
            b["closure_pulled_in"] += 1

    skips_list: list = []
    for skip in plan.skips:
        b = _bucket(skip.category)
        b["skipped"] += 1
        skips_list.append(skip)
        # Feature 038 (FR-017/FR-025): NOT_REPRODUCIBLE is counted from the
        # skips themselves, which is what RunReport.__post_init__ reconciles
        # the counter against -- so the two can never disagree.
        if skip.reason == SkipReason.NOT_REPRODUCIBLE:
            b["not_reproducible"] += 1

    # Phase 1 (FR-110): count overwrites per category. Tolerate plans
    # produced before Phase 1 (no `overwrites` attribute) by falling back
    # to an empty tuple.
    for ow in getattr(plan, "overwrites", ()):
        b = _bucket(ow.category)
        b["overwritten"] += 1
        if getattr(ow, "pulled_in_by", ()):
            b["closure_pulled_in"] += 1
        _count_substitution(b, ow, always_matched=True)
        # T024d-a: an OVERWRITE is by definition a write onto a destination
        # object that already existed, so every one of them is a match --
        # whether it was found by GUID, by identity remap, by fingerprint, or
        # by natural key.
        _count_matched(ow, ow.category)

    # Phase 2 (T030): account for INTERACTIVE_SKIP records emitted by
    # _apply_merge_decisions during execute().  These are not in
    # plan.skips (the plan was built before any user input) so they
    # flow in via the `extra_skips` parameter.
    for skip in extra_skips:
        b = _bucket(skip.category)
        b["skipped"] += 1
        skips_list.append(skip)
        if skip.reason == SkipReason.INTERACTIVE_SKIP:
            b["interactive_skipped"] += 1
        if skip.reason == SkipReason.NOT_REPRODUCIBLE:
            b["not_reproducible"] += 1

    # Phase 3c Selection UI: tally EXCLUDED-LOSSY warnings from the plan
    # and any extras passed in by the executor.
    excluded_lossy_all: list = list(getattr(plan, "excluded_lossy", ()))
    excluded_lossy_all.extend(extra_excluded_lossy)
    for el in excluded_lossy_all:
        b = _bucket(el.category)
        b["excluded_lossy"] += 1

    # Feature 038 (FR-020..FR-022): enrichment records travel on the plan,
    # but `EnrichmentRecord` carries an LCM object_class, not a
    # GrammarCategory -- so the per-category `enriched` counter has to be
    # attributed via the plan item that produced the record.
    # `RunReport.__post_init__` reconciles the counter total against
    # `len(enrichments)`, so an unattributable record is a hard error here
    # rather than a quietly-wrong count later.
    enrichments_all = tuple(getattr(plan, "enrichments", ())) + tuple(
        extra_enrichments
    )
    if enrichments_all:
        guid_to_cat: dict = {}
        for ow in getattr(plan, "overwrites", ()):
            guid_to_cat.setdefault(ow.source_guid, ow.category)
        for action in plan.actions:
            guid_to_cat.setdefault(action.source_guid, action.category)
        for enrichment in enrichments_all:
            cat = guid_to_cat.get(enrichment.source_guid)
            if cat is None:
                raise ValueError(
                    "Feature 038: cannot attribute EnrichmentRecord for "
                    f"source_guid={enrichment.source_guid!r} "
                    f"({enrichment.object_class}) to a category -- no plan "
                    "action or overwrite carries that GUID. Guessing would "
                    "make per_category[*].enriched disagree with "
                    "len(enrichments)."
                )
            _bucket(cat)["enriched"] += 1

    # SC-010: a source child an enrichment could not add is a
    # `DroppedItemRecord` like any other, and it MUST reach the statistics
    # panel. Fold those records into the ONE existing dropped channel instead
    # of leaving them visible only inside the enrichment detail list -- deduped
    # on the published `(owner_guid, field_name, item_guid)` identity so a
    # record the executor already appended to `extra_dropped_items` is not
    # reported twice.
    dropped_items_all = list(extra_dropped_items)
    _dropped_seen = {_dropped_dedup_key(d) for d in dropped_items_all}
    for _rec in _enrichment_dropped_records(enrichments_all):
        _key = _dropped_dedup_key(_rec)
        if _key in _dropped_seen:
            continue
        _dropped_seen.add(_key)
        dropped_items_all.append(_rec)

    per_category_final = {
        cat: CategoryReport(
            added=counts["added"],
            skipped=counts["skipped"],
            closure_pulled_in=counts["closure_pulled_in"],
            overwritten=counts["overwritten"],
            interactive_resolved=counts["interactive_resolved"],
            interactive_skipped=counts["interactive_skipped"],
            ws_mapped=counts["ws_mapped"],
            ws_created=counts["ws_created"],
            ws_skipped=counts["ws_skipped"],
            excluded_lossy=counts["excluded_lossy"],
            identity_substitution=counts["identity_substitution"],
            enriched=counts["enriched"],
            not_reproducible=counts["not_reproducible"],
        )
        for cat, counts in per_category.items()
    }

    # Phase 3a FR-308: categories selected by the user but with zero
    # items in source are surfaced as "empty_categories" so
    # render_text_summary can emit "[skip] no items in source for X".
    selected_cats = {
        c for c, on in getattr(plan, "selection", None).categories.items() if on
    } if getattr(plan, "selection", None) is not None else set()
    empty_cats = tuple(sorted(
        (c for c in selected_cats if c not in per_category_final),
        key=lambda c: c.value,
    ))

    return cls(
        context=plan.context,
        mode=mode,
        per_category=per_category_final,
        skips=tuple(skips_list),
        identity_remap=dict(plan.identity_remap),
        wall_clock_seconds=wall_clock_seconds,
        empty_categories=empty_cats,
        excluded_lossy=tuple(excluded_lossy_all),
        dropped_items=tuple(dropped_items_all),
        fidelity_by_guid=dict(fidelity_by_guid) if fidelity_by_guid else {},
        leaf_execution_failures=tuple(extra_leaf_execution_failures),
        # Feature 038: the four plan-side buckets flow straight through, so
        # the report surfaces below have something to render. All four are
        # empty on a plan built before 038's producers exist, which is why
        # this is a no-op for every current caller.
        closure_edges=tuple(getattr(plan, "closure_edges", ()))
        + tuple(extra_closure_edges),
        incompleteness=tuple(getattr(plan, "incompleteness", ()))
        + tuple(extra_incompleteness),
        enrichments=enrichments_all,
        process_rules=_merge_process_rules(
            getattr(plan, "process_rules", ()), extra_process_rules),
        # T074 (FR-019 / SC-003): execute-time only -- the 17.1 sub-pass runs
        # after the writes, so a Preview plan has none and the union is just
        # the run's own records. Kept a UNION anyway so this reads like its
        # four siblings above rather than being the one that does not.
        affix_slot_links=tuple(getattr(plan, "affix_slot_links", ()))
        + tuple(extra_affix_slot_links),
        census=census,
        # T024d-a: the per-class matched tallies the census consumes as
        # `starter_matched_to_source`. Sorted so the snapshot diffs
        # deterministically; empty on any plan whose matcher has not run, which
        # keeps `baseline_matched` correctly unreachable until it has.
        matched_by_class=dict(sorted(matched_by_class.items())),
        matches_unattributed=dict(
            sorted(matches_unattributed.items(), key=lambda kv: kv[0].value)
        ),
    )


# ============================================================================
# Feature 038 (transfer fidelity gaps) -- shared helpers for the new buckets
# ============================================================================
# Two surfaces, one rule each:
#
#   * The ARTIFACT (`to_snapshot_json`) is NEVER truncated. Every record in
#     every 038 bucket appears in it, in full -- it is what a linguist can
#     still consult after the console has scrolled away.
#   * The CONSOLE (`render_text_summary`) MAY truncate a long list, but only
#     while STATING how many rows it omitted and where the rest live. A
#     truncation that hides its own existence is indistinguishable from a
#     silent loss, which is the exact failure mode this feature exists to
#     remove (SC-010).
#
# Snapshot compatibility: every 038 key is OMITTED when its bucket is empty
# rather than emitted as `[]` / `{}`. A run with no 038 data therefore
# produces a BYTE-IDENTICAL snapshot to the pre-038 build, so the golden
# snapshot in tests/integration/test_full_workflow_e2e.py -- which asserts
# `normalized == golden`, not "golden is a subset of normalized" -- keeps
# matching with no re-baseline, and a reader doing
# `data.get("enrichments", [])` sees the same empty default either way.
# Deliberate departure from feature 024's always-emit convention for
# `dropped_items` / `fidelity_by_guid`: 024 could afford to change every
# snapshot because it was re-baselining them anyway; 038 is landing in waves
# alongside other work and must not.

#: Console row budget per 038 detail list. The ARTIFACT ignores this entirely.
_CONSOLE_MAX_ROWS = 20


def _enum_name(value) -> str:
    """JSON-side enum rendering: `.name`, matching the existing convention
    (`mode.name`, `category.name`, `reason.name`). Tolerates a plain string so
    a hand-built record does not explode the serializer."""
    return getattr(value, "name", str(value))


def _enum_value(value) -> str:
    """Console-side enum rendering: `.value`, matching the existing convention
    (`cat.value`, `s.reason.value`)."""
    return getattr(value, "value", str(value))


def _guid8(guid) -> str:
    """First 8 chars of a GUID -- CONSOLE ONLY. The artifact always carries
    the full GUID."""
    return str(guid)[:8]


def _pair_json(pair) -> dict:
    """Serialize a `(GrammarCategory, guid)` 2-tuple as carried by
    `ClosureEdge` and `IncompletenessRecord`."""
    cat, guid = pair
    return {"category": _enum_name(cat), "guid": guid}


def _pair_text(pair) -> str:
    """Console form of a `(GrammarCategory, guid)` pair: `affixes 1a2b3c4d`."""
    cat, guid = pair
    return f"{_enum_value(cat)} {_guid8(guid)}"


def _ordered_categories(per_category: dict) -> list:
    """The report's categories in GrammarCategory DECLARATION order, so every
    038 per-category block diffs as deterministically as `per_category`."""
    return [
        GrammarCategory[name]
        for name in GrammarCategory.__members__
        if GrammarCategory[name] in per_category
    ]


def _counter_block(report, attr: str):
    """`{"total": N, "per_category": {...}}` for one 038 CategoryReport
    counter, or None when the counter is zero everywhere (-> key omitted).

    Deliberately kept OUT of the pre-existing `per_category` block: that
    block's shape is load-bearing for existing snapshot consumers, and a run
    with no 038 data must not grow new keys inside it."""
    per = {}
    for cat in _ordered_categories(report.per_category):
        n = getattr(report.per_category[cat], attr, 0)
        if n:
            per[cat.name] = n
    total = sum(per.values())
    return {"total": total, "per_category": per} if total else None


# ============================================================================
# Feature 038 (FR-022 + SC-010) -- disposition accounting and the certainty
# clause
# ============================================================================
# Two obligations meet here, and both are about the report claiming exactly as
# much as its evidence supports and not one word more.
#
#   FR-022  The run report MUST distinguish an ENRICHED item from a CREATED
#           one. `EnrichmentRecord.was_created` is False by construction (it
#           is UNCONSTRUCTIBLE as True -- models.py raises), so the
#           distinction already exists in the data. What did not exist is the
#           distinction in the OUTPUT: an enriched object had no row of its
#           own in the statistics panel, so a reader had to infer "not
#           created" from the absence of a `PlannedAction` they cannot see.
#
#   SC-010  Every selected item reaches exactly one of ADD, UPDATE (enriched),
#           SKIP, or dropped-with-reason, and each appears in the post-run
#           statistics panel: there is no fifth, unreported outcome. Nothing
#           in this section RE-TALLIES anything. The counters are already
#           reconciled against their records by `RunReport.__post_init__`
#           (`sum(per_category[*].enriched) == len(enrichments)`, and likewise
#           for `not_reproducible`); this section only reads those counters and
#           names which record type each one is answerable to, which is what
#           makes the four-bucket claim auditable instead of decorative.
#
# THE CERTAINTY CLAUSE (plan.md's Principle IV row; research.md R4). Two
# sentences are forbidden unless the evidence for them exists:
#
#   "identical now"            -- a claim that source and target now agree.
#                                 On a FIRST transfer the run has verified no
#                                 such thing; it wrote what it had. Per R4 the
#                                 strongest TRUE line is "the target already
#                                 held this object; N children added, M
#                                 already present", and that is the line the
#                                 enrichment rows below actually print.
#   "untouched since last run" -- a claim about a PRIOR state of the target.
#                                 The only prior state this system records is
#                                 the import-residue tag an earlier GramTrans
#                                 run left on the object (`Lib/residue.py`:
#                                 `GT|<run_id>|<source>|<iso_ts>`, optionally
#                                 carrying a `snap=` props snapshot). With no
#                                 such baseline there is nothing for an object
#                                 to be untouched SINCE, so the sentence is
#                                 not said -- and its absence is stated, so a
#                                 reader is not left to wonder which way to
#                                 read the silence.
#
# This is the discipline T039 forced on the census, applied to the prose: do
# not assert a difference -- or a sameness -- with more confidence than its
# basis supports.

#: Skip reasons that mean "a field-identity comparison actually ran and found
#: no delta", as opposed to "a GUID lookup hit something" -- which is exactly
#: the meaning feature 038's G3 narrowing removed from
#: `ALREADY_PRESENT_BY_GUID`. Every other skip reason names a reason the item
#: did NOT transfer, and so belongs with dropped-with-reason, never with
#: "source and target already agreed".
_NO_DELTA_SKIP_REASONS = frozenset({
    SkipReason.ALREADY_PRESENT_BY_GUID,
    SkipReason.ALREADY_PRESENT_BY_IDENTITY,
})


def residue_baseline_run_id(report) -> str:
    """The run_id of the residue baseline this report may compare against, or
    `""` when there is none -- which is the case for every run today.

    NOTHING currently establishes a run-level baseline. `Lib/residue.py`
    WRITES the tag and `Lib/conflict.py.load_prior_log` can read one back for
    a single object, but no caller aggregates that into a fact about the run,
    and `RunReport` accordingly has no field for it. Hard-coding "there is
    never a baseline" would be true today and would silently keep the weaker
    wording forever after someone wires one up, so the lookup is by ATTRIBUTE,
    in the same tolerant style the rest of this module already uses for
    additive fields (`getattr(plan, "overwrites", ())`). Two spellings are
    honoured, whichever a future producer picks:

      * ``report.residue_baseline`` -- an object exposing ``run_id``, or the
        run-id string itself;
      * ``report.context.prior_run_id`` -- a run-id string.

    With neither present the answer is `""` and every claim resting on a
    baseline is withheld. An absent baseline is NOT evidence that the target
    is unchanged: it is the absence of evidence in either direction, the same
    rule `census.unmatched_starter` applies to an absent starter baseline.
    """
    baseline = getattr(report, "residue_baseline", None)
    if baseline is None:
        baseline = getattr(
            getattr(report, "context", None), "prior_run_id", None
        )
    if baseline is None:
        return ""
    run_id = getattr(baseline, "run_id", baseline)
    return str(run_id) if run_id else ""


def certainty_note(report) -> str:
    """The ONE sentence this report is allowed to say about what its sameness
    claims are worth.

    Single source of the wording, so the console panel and the JSON artifact
    cannot drift into two different promises -- drift being how the report
    came to overclaim in the first place.
    """
    prior = residue_baseline_run_id(report)
    if not prior:
        return (
            "FIRST TRANSFER (no residue baseline from an earlier GramTrans "
            "run was available on this target). This report states only what "
            "this run wrote and what it compared. It does NOT claim the "
            "target is identical to the source now, and nothing here means "
            "an item was untouched since a previous run -- there is no "
            "recorded earlier run for anything to be untouched since."
        )
    return (
        "A residue baseline from run " + prior + " was available, so an item "
        "this run neither created nor changed is untouched since " + prior +
        ". A sameness claim still covers only the fields and owned "
        "collections actually compared, never the whole object."
    )


def disposition_totals(report) -> dict:
    """SC-010's outcomes for this run, each counted from ONE record type.

    Returned as a plain dict so the console panel and the JSON artifact render
    the same numbers from the same call; a second derivation is a second
    chance to disagree.

    Source of truth per bucket -- this mapping is the report's answer to "is
    there a fifth outcome?", and T080's audit hangs on it:

      ``add_created``         one per `PlannedAction`    -> `per_category[*].added`
      ``update_enriched``     one per `EnrichmentRecord` -> `enrichments`
      ``update_overwritten``  one per `PlannedOverwrite` -> `per_category[*].overwritten`
      ``skip``                one per `Skip`             -> `skips`
      ``dropped_with_reason`` one per `DroppedItemRecord`-> `dropped_items`
      ``add_write_failed``    one per `LeafExecutionFailure`
                                                         -> `leaf_execution_failures`

    ``add_created`` IS COUNTED FROM THE PLAN, AND T048c IS WHY THAT MATTERS.
    `per_category[*].added` is one per `PlannedAction`, so it says what the run
    INTENDED to write, not what it wrote. The leaf-dispatch loop swallows a
    failing `execute_action` by policy (feature 037 defect C, deliberately
    unchanged), and its own debug line states the consequence in as many words:
    *"swallowed write failures do NOT reduce the reported 'added' count"*.
    Measured on run `CENSUS-20260820-094825`: the log read `attempted=329
    succeeded=326 failed=3` while `disposition.add_created` read 329 and the
    artifact carried no failure surface at all -- a real loss, unreported,
    which is the Principle I shape.

    `add_created` is left alone rather than silently reduced, because it is the
    honest answer to the question it names ("how many creates were planned")
    and three existing invariants are checked against it. The write outcome
    gets its own two keys instead: ``add_write_failed`` (the count of swallowed
    failures) and ``add_created_written`` (the remainder that actually
    reached the database). The remainder follows the `update_overwritten_not_
    enriched` precedent exactly -- when the subtraction has no valid basis
    (more failures than planned creates, which would mean the counters
    disagree) it yields ``None`` and ``create_split_reconciles`` is False,
    because a number whose basis does not support it is worse than no number.

    The buckets are counted from DISJOINT record types, which is precisely why
    an enrichment can never land in the created tally: an `EnrichmentRecord`
    is not a `PlannedAction`, and carries `was_created is False` besides.

    The one genuine overlap is stated rather than hidden. An enrichment is
    CARRIED on a `PlannedOverwrite` (`write_mode="merge"`, enforced by
    `PlannedOverwrite.__post_init__`), so `update_overwritten` includes the
    enrichments and `update_overwritten_not_enriched` is the remainder. When
    the enrichment records outnumber the overwrites that subtraction has no
    valid basis, so it yields ``None`` and ``overwrite_split_reconciles`` is
    False -- the T039 lesson, that a number whose basis does not support it is
    worse than no number.
    """
    per_cat = getattr(report, "per_category", {}) or {}
    enrichments = tuple(getattr(report, "enrichments", ()))
    created = sum(getattr(r, "added", 0) for r in per_cat.values())
    overwritten = sum(getattr(r, "overwritten", 0) for r in per_cat.values())
    enriched = len(enrichments)
    skipped = sum(getattr(r, "skipped", 0) for r in per_cat.values())
    no_delta = sum(
        1 for s in getattr(report, "skips", ())
        if getattr(s, "reason", None) in _NO_DELTA_SKIP_REASONS
    )
    dropped = len(getattr(report, "dropped_items", ()))
    # T080: the fifth-outcome check, derived ONCE here so the console panel
    # and the JSON artifact cannot disagree about it -- the same rule the
    # docstring states for every other bucket. Read from the property, never
    # re-derived: `RunReport.unreported_not_reproduced` is the single
    # definition of "knew it did not rebuild this, named it nowhere".
    unreported = tuple(getattr(report, "unreported_not_reproduced", ()))
    reconciles = enriched <= overwritten
    # T048c: read from the records, never from a counter -- `leaf_failed` is a
    # property over this same tuple for exactly that reason.
    write_failed = len(getattr(report, "leaf_execution_failures", ()))
    create_reconciles = write_failed <= created
    # FidelityStatus is REUSED here, never re-derived: `EnrichmentRecord.
    # fidelity` already applies the same FULL/PARTIAL rule
    # `categories.compute_fidelity_by_guid` applies to a created object.
    partial = sum(
        1 for r in enrichments
        if getattr(r, "fidelity", None) is FidelityStatus.PARTIAL
    )
    collections = tuple(
        c for r in enrichments for c in getattr(r, "collections", ())
    )
    return {
        "add_created": created,
        # T048c: planned versus written. `add_created` is the plan's number;
        # these two are the outcome's.
        "add_write_failed": write_failed,
        "add_created_written": (
            created - write_failed if create_reconciles else None
        ),
        "create_split_reconciles": create_reconciles,
        "update_enriched": enriched,
        "update_overwritten": overwritten,
        "update_overwritten_not_enriched": (
            overwritten - enriched if reconciles else None
        ),
        "overwrite_split_reconciles": reconciles,
        "skip": skipped,
        "skip_no_delta_after_comparison": no_delta,
        "skip_other_reason": skipped - no_delta,
        "dropped_with_reason": dropped,
        # T080: SC-010's claim, as a value rather than as prose. `True` means
        # every item this run KNOWS it did not reproduce also reached one of
        # the four buckets above. `False` names the ones that did not, and is
        # deliberately NOT a build-time refusal -- see
        # `RunReport.unreported_not_reproduced` for why a report that names
        # its own gap beats no report.
        "no_fifth_outcome": not unreported,
        "unreported_not_reproduced": len(unreported),
        "unreported_not_reproduced_guids": list(unreported),
        "enriched_partial": partial,
        "enriched_full": enriched - partial,
        "enriched_gained_nothing": sum(
            1 for r in enrichments if getattr(r, "is_empty", False)
        ),
        "enriched_children_added": sum(c.added for c in collections),
        "enriched_children_already_present": sum(
            c.already_present for c in collections
        ),
        "enriched_children_dropped": sum(c.dropped for c in collections),
    }


#: The five keys whose emptiness means "this run had no outcome to account
#: for". Used to keep the disposition panel off a genuinely empty report
#: without ever hiding a bucket that has something in it.
_DISPOSITION_OUTCOME_KEYS = (
    "add_created",
    "update_enriched",
    "update_overwritten",
    "skip",
    "dropped_with_reason",
)


def _has_reportable_outcome(totals: dict) -> bool:
    return any(totals.get(k) for k in _DISPOSITION_OUTCOME_KEYS)


def _has_038_data(report) -> bool:
    """True when this report carries any feature-038 fidelity data.

    Gates the ARTIFACT's `disposition` / `certainty` keys, so the
    snapshot-compatibility promise stated above the helpers ("a run with no
    038 data produces a BYTE-IDENTICAL snapshot to the pre-038 build")
    survives this addition. The CONSOLE panel is deliberately NOT gated this
    way: it has no byte-compatibility contract, and SC-010's "each appears in
    the post-run statistics panel" is unconditional there.
    """
    if (getattr(report, "enrichments", ())
            or getattr(report, "closure_edges", ())
            or getattr(report, "incompleteness", ())
            or getattr(report, "process_rules", ())):
        return True
    if getattr(report, "census", None) is not None:
        return True
    # T048c: a run whose only anomaly is a SWALLOWED WRITE is exactly the run
    # that needs the disposition block, because `add_created` is the plan's
    # number and `add_created_written` is the only place the difference is
    # stated. Byte-identity is not weakened by this: such a report already
    # emits the `leaf_execution_failures` key above, so it was never
    # byte-identical to a pre-038 snapshot in the first place. A report with
    # ZERO failures is unaffected and stays byte-identical.
    if getattr(report, "leaf_execution_failures", ()):
        return True
    per_cat = getattr(report, "per_category", {}) or {}
    return any(
        getattr(r, attr, 0)
        for r in per_cat.values()
        for attr in ("identity_substitution", "enriched", "not_reproducible")
    )


def _enrichment_dropped_records(enrichments) -> tuple:
    """Every `DroppedItemRecord` carried inside an enrichment's collections.

    SC-010 forbids an anonymous drop, and `EnrichedCollection.__post_init__`
    already guarantees `dropped == len(dropped_records)`. These are ordinary
    `DroppedItemRecord`s, so they belong in the report's ONE existing dropped
    channel (`RunReport.dropped_items`, rendered by the "Dropped references /
    owned items" section) rather than in a second, enrichment-only list that
    no other consumer reads.
    """
    return tuple(
        rec
        for r in enrichments
        for c in getattr(r, "collections", ())
        for rec in getattr(c, "dropped_records", ())
    )


def _dropped_dedup_key(record):
    """`(owner_guid, field_name, item_guid)` -- the dedup identity
    `DroppedItemRecord`'s own docstring publishes and
    `categories._dropped_key` enforces. Reused verbatim so folding the
    enrichment drops into `dropped_items` cannot double-report a drop the
    executor already appended."""
    return (
        getattr(record, "owner_guid", ""),
        getattr(record, "field_name", ""),
        getattr(record, "item_guid", ""),
    )


def _closure_edge_json(e) -> dict:
    return {
        "dependent": _pair_json(e.dependent),
        "dependency": _pair_json(e.dependency),
        "kind": _enum_name(e.kind),
        "verified": bool(e.verified),
        "verified_by": e.verified_by,
        "origin": e.origin,
        "deselected": bool(e.deselected),
    }


def _incompleteness_json(r) -> dict:
    return {
        "incomplete_item": _pair_json(r.incomplete_item),
        "incomplete_label": r.incomplete_label,
        "missing_dependency": _pair_json(r.missing_dependency),
        "missing_label": r.missing_label,
        "cause": r.cause,
        # FR-016 / SC-010: what the reader actually LOSES. Never omitted --
        # a record the user cannot act on is not a report.
        "consequence": r.consequence,
    }


def _affix_slot_link_block(links) -> dict:
    """The FR-019 / SC-003 answer, as the artifact carries it (T074).

    `linked_of_attempted` is SC-003 verbatim: of the affixes this run put in
    the destination that occupied a template column in the source, how many
    occupy it now. `not_in_run` is deliberately OUTSIDE that ratio and stated
    beside it -- those are source affixes this run never transferred, so
    counting them as failures is what made the pre-T074 report say 203 losses
    on a run that lost nothing. Both numbers are present so a reader can see
    the scoping rather than have to trust it.

    Failures are listed individually and never truncated; successes are a
    count. A `SLOT_MISSING` row names the affix ENTRY, which is the thing that
    lost something -- the pre-T074 skip named only the absent slot.
    """
    by_outcome: dict = {}
    for record in links:
        name = _enum_name(record.outcome) or str(record.outcome)
        by_outcome[name] = by_outcome.get(name, 0) + 1
    attempted = sum(
        count for name, count in by_outcome.items() if name != "NOT_IN_RUN")
    failures = [
        {
            "outcome": _enum_name(r.outcome),
            "entry_guid": r.entry_guid,
            "msa_guid": r.msa_guid,
            "source_slot_guids": list(r.source_slot_guids),
            "unresolved_slot_guids": list(r.unresolved_slot_guids),
        }
        for r in links
        if _enum_name(r.outcome) in ("SLOT_MISSING", "MSA_MISSING")
    ]
    return {
        "source_msas_with_a_column": len(links),
        "by_outcome": dict(sorted(by_outcome.items())),
        "attempted": attempted,
        "linked_of_attempted": by_outcome.get("LINKED", 0),
        "not_in_run": by_outcome.get("NOT_IN_RUN", 0),
        "failures": failures,
    }


def _dropped_item_json(d) -> dict:
    """One `DroppedItemRecord`, in the shape `to_snapshot_json`'s
    `dropped_items` list has always used. Extracted so the enrichment
    collections below serialise their `dropped_records` in the SAME shape --
    one serializer, one shape, no second dialect of the same record."""
    return {
        "owner_kind": d.owner_kind,
        "owner_guid": d.owner_guid,
        "owner_label": d.owner_label,
        "field_name": d.field_name,
        "item_name": d.item_name,
        "item_guid": d.item_guid,
        "reason": d.reason,
    }


def _enrichment_json(r) -> dict:
    return {
        "object_class": r.object_class,
        "source_guid": r.source_guid,
        "target_guid": r.target_guid,
        "label": r.label,
        # FR-022: the created-vs-enriched distinction is STATED, not inferred.
        # Always False -- `EnrichmentRecord` refuses to be built with True --
        # and emitted anyway, because a reader must be able to read the
        # distinction off the artifact without knowing that rule.
        "was_created": bool(r.was_created),
        "is_empty": bool(getattr(r, "is_empty", False)),
        # FR-013's enum, REUSED: `EnrichmentRecord.fidelity` derives FULL /
        # PARTIAL under the same rule `categories.compute_fidelity_by_guid`
        # uses for a created object, so an enriched object's fidelity reads
        # the same way as a created one's.
        "fidelity": _enum_name(getattr(r, "fidelity", "")),
        "fields_updated": list(r.fields_updated),
        "collections": [
            {
                "field_name": c.field_name,
                "added": c.added,
                "already_present": c.already_present,
                "dropped": c.dropped,
                # SC-010: a dropped child is never an anonymous number. The
                # same records also appear in the report's top-level
                # `dropped_items` (folded in by `build_from_plan`); they are
                # repeated here so the enrichment row is self-contained.
                "dropped_records": [
                    _dropped_item_json(d)
                    for d in getattr(c, "dropped_records", ())
                ],
            }
            for c in r.collections
        ],
    }


def _reference_decision_json(d) -> dict:
    """Tolerant serializer for a `ReferenceDecisionRecord` carried on a
    process-rule record's `reference_decisions`."""
    action = getattr(d, "action", None)
    return {
        "owner_kind": getattr(d, "owner_kind", ""),
        "owner_guid": getattr(d, "owner_guid", ""),
        "field_name": getattr(d, "field_name", ""),
        "action": _enum_name(action) if action is not None else "",
        "item_name": getattr(d, "item_name", ""),
        "item_guid": getattr(d, "item_guid", ""),
    }



def _merge_process_rules(plan_rules, run_rules) -> tuple:
    """One record per source rule: the RUN's outcome wins over the PLAN's
    prediction (feature 038, T059/T060).

    Both sides record process rules, and they are NOT disjoint -- a rule the
    plan predicted unreproducible and the run then also skipped appears in
    both. Concatenating them listed that rule twice in
    `RunReport.rules_not_reproduced`, which is a report saying a loss happened
    twice.

    The run wins because it is the OUTCOME and the plan is a prediction. That
    is not a tie-break; it is the only direction that can be right. A plan
    resolves references against the destination as it stands BEFORE the
    transfer, so it necessarily knows less than the run that followed it --
    measured on the live `Mbugwe LizzieHC practice` run, the plan named 15
    rules unreproducible where the run rebuilt 9 of them. Letting the plan win
    would report those 9 as lost while the destination held them.

    Plan order is preserved for rules the run never reached (a run that
    aborted, or a Preview-only report with no run at all), so nothing the plan
    knew is dropped.
    """
    merged = {}
    order = []
    for record in tuple(plan_rules) + tuple(run_rules):
        guid = getattr(record, "source_guid", "")
        if not guid:  # cannot be keyed; keep it rather than lose it
            order.append(id(record))
            merged[id(record)] = record
            continue
        if guid not in merged:
            order.append(guid)
        merged[guid] = record
    return tuple(merged[key] for key in order)


def _process_rule_json(r) -> dict:
    return {
        "source_guid": r.source_guid,
        "reproduced": bool(r.reproduced),
        "target_guid": r.target_guid,
        # FR-025: guaranteed non-empty by ProcessRuleTransferRecord's
        # __post_init__ whenever `reproduced` is False.
        "not_reproducible_reason": r.not_reproducible_reason,
        "input_contexts": [
            {
                "context_class": c.context_class,
                "index": c.index,
                "referent_guid": c.referent_guid,
                "label": c.label,
                # T107: PRESENT BECAUSE IT WAS MISSING. T076 added
                # `co_created_shared` to `ProcessContextSpec` so that "a write
                # into a shared, project-level collection made as a side
                # effect of transferring a lexical entry" would not be a
                # silent write (SC-010) -- and asserted it on the in-memory
                # record only. This serializer never emitted it, so the claim
                # was true of the object and FALSE of the artifact anyone
                # actually reads. T107 found the gap the hard way: its live
                # Ejagham run cannot say whether the shared boundary context
                # was co-created here or brought across by the phonological-
                # rule path, because both write `PhPhonData.ContextsOS` and
                # the only field that distinguishes them was dropped on the
                # way out. Emitted unconditionally, empty tuple included --
                # "this rule created no shared context" is the reading that
                # makes a non-empty list mean something.
                "co_created_shared": list(c.co_created_shared),
            }
            for c in r.input_contexts
        ],
        "output_steps": [
            {
                "step_class": s.step_class,
                "index": s.index,
                "content": s.content,
                "referent_guids": list(s.referent_guids),
            }
            for s in r.output_steps
        ],
        "reference_decisions": [
            _reference_decision_json(d) for d in r.reference_decisions
        ],
    }


def _census_module():
    """`Lib/census.py`, imported LAZILY -- the ONE authority for verdicts.

    `report.py` is imported on every GramTrans run whether or not a census
    was taken, and `Lib/census.py` is a 3000-line instrument, so the import
    is deferred to the two census surfaces that actually need it.

    Nothing in this file re-declares `VERDICT_EXIT_CODES`,
    `VERDICT_HUMAN_LABELS` or `VERDICT_SEVERITY_ORDER`, and nothing here
    re-derives an exit code from a verdict token: a second copy of the exit
    table is precisely the drift feature 038 exists to remove, so every one
    of them is CALLED from `census.py` instead.
    """
    if __package__:
        from . import census as census_module
    else:
        import census as census_module  # type: ignore[no-redef]
    return census_module


def _census_internal_only_fields(table) -> frozenset:
    """The INTERNAL-ONLY field names of one `*_ARTIFACT_FIELDS` table.

    A `None` target in the table means "no artifact counterpart -- must not
    be emitted" (`models.py`'s naming-split block). Read out of the table
    rather than listed here, so adding an internal-only field in `models.py`
    cannot leave a stale copy of the list behind in this serializer.
    """
    return frozenset(name for name, target in table.items() if target is None)


def _census_reject_internal(block: dict, table, where: str) -> dict:
    """Raise if `block` carries any internal-only field name of `table`.

    Structurally unreachable for the blocks this module builds -- they are
    emitted BY the table, skipping every `None` target -- so this exists to
    catch (a) a hand-built or third-party artifact arriving on
    `RunReport.census`, and (b) a future edit that starts writing keys
    directly. It RAISES rather than quietly dropping the key: every object in
    the census artifact is `additionalProperties: false`, so an internal-only
    key is a hard validation failure, and silently repairing it would hide the
    producer bug that wrote it.
    """
    leaked = sorted(_census_internal_only_fields(table) & set(block))
    if leaked:
        raise ValueError(
            f"feature 038: census {where} carries internal-only field(s) "
            f"{leaked} -- those names have no counterpart in "
            f"contracts/census-artifact.schema.json (their entry in the "
            f"models.py translation table is None) and every artifact object "
            f"is additionalProperties:false, so emitting one is a hard "
            f"validation failure rather than a harmless extra"
        )
    return block


def _census_signed(value) -> str:
    """A census difference, with its sign always visible: `-1949`, `+13`, `0`.

    The sign is load-bearing (negative = SHORTFALL, positive = SURPLUS), so a
    bare `13` that could be read either way is not an acceptable rendering.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "?"
    return "0" if number == 0 else f"{number:+d}"


def _census_class_name(row) -> str:
    """The `class` of one census row, from either an emitted row `dict` or an
    in-memory `ClassCensusRow`."""
    if isinstance(row, dict):
        return str(row.get("class") or row.get("object_class") or "")
    return str(getattr(row, "object_class", "") or "")


def _census_owner(row) -> str:
    """The owning feature system a row declares, or "" when it declares none.

    AMENDMENT A1, BOTH ENCODINGS, NEITHER HARD-CODED. A1 counts a class
    reachable from both FieldWorks feature systems (`FsFeatStrucType`) once
    per owner, and the owner rides EITHER inside the `class` string
    (`FsFeatStrucType(...)`) OR in a separate optional `owning_feature_system`
    property. This reads only the property. Under the string encoding there is
    no property to read and the owner is already part of the name
    `_census_class_name` returns, so `_census_row_label` renders the owner
    exactly once under either encoding and this module never has to know which
    one is in force.
    """
    if isinstance(row, dict):
        return str(row.get("owning_feature_system") or "")
    return str(getattr(row, "owning_feature_system", None) or "")


def _census_row_label(row) -> str:
    """`class`, qualified by its owning feature system when the row names one
    and the name does not already carry it (see `_census_owner`)."""
    name = _census_class_name(row)
    owner = _census_owner(row)
    if owner and owner not in name:
        return f"{name} ({owner})"
    return name


def _census_gate(census) -> dict:
    """The census's verdict TOKEN, exit code, human label and pass/fail.

    ONE function, called by BOTH surfaces, so the console and the JSON can
    never print different verdicts for the same census. Every value is
    obtained from `Lib/census.py`; none of its three tables is copied here.
    PASS is `census.is_passing_verdict`, i.e. exactly `CENSUS_CLEAN` or
    `CENSUS_ACCOUNTED`.

    Two shapes, two authorities:

    * an already-emitted artifact `dict` -> `census.gate_artifact`, which
      RECOMPUTES the verdict from the document's own evidence. Its answer
      OVERRIDES any `verdict` / `exit_code` stored in the document, because
      trusting a stored verdict is exactly how a forged artifact would buy
      exit 0.
    * an in-memory `FidelityCensus` -> the most severe verdict the OBJECT can
      prove, chosen by `census.most_severe_verdict` over the published
      `VERDICT_SEVERITY_ORDER`. A `FidelityCensus` carries rows and a baseline
      but no `.fwdata` digests, no instrument block, no class-list provenance
      and no duplicate reports, so `CENSUS_ERROR`, `COVERAGE_INCOMPLETE`,
      `BASELINE_STALE` and `DUPLICATE_IDENTITY` are NOT decidable from it and
      are not guessed. The answer is therefore a FLOOR (`complete` False): the
      standalone artifact's gate can return the same verdict or a MORE severe
      one, never a less severe one. `FidelityCensus.gate_pass` is never read --
      it is internal-only, and the gate recomputes.
    """
    engine = _census_module()

    if isinstance(census, dict):
        try:
            outcome = engine.gate_artifact(census)
        except Exception as exc:  # a document the gate cannot read is an error
            verdict = "CENSUS_ERROR"
            return {
                "verdict": verdict,
                "exit_code": engine.exit_code_for(verdict),
                "human_label": engine.VERDICT_HUMAN_LABELS[verdict],
                "passed": False,
                "failures": (
                    "the census gate could not read this artifact: "
                    f"{type(exc).__name__}: {exc}",
                ),
                "complete": True,
            }
        return {
            "verdict": outcome.verdict,
            "exit_code": outcome.exit_code,
            "human_label": outcome.human_label,
            "passed": bool(outcome.passed),
            "failures": tuple(outcome.failures),
            "complete": True,
        }

    rows = tuple(getattr(census, "rows", ()))
    baseline = getattr(census, "baseline", None)
    applicable = ["CENSUS_CLEAN"]
    failures: list = []

    # BASELINE_MISSING (exit 4). Absence is a verdict, never a warning and
    # never an assumed zero -- a zero baseline is a positive claim that the
    # destination shipped empty (fidelity-census.md 5.3). A census carrying no
    # baseline object at all is treated the same way.
    if baseline is None or getattr(baseline, "is_missing", True):
        applicable.append("BASELINE_MISSING")
        failures.append(
            "the starter baseline is MISSING -- nothing could be subtracted "
            "for content the destination already held, and there is no path "
            "on which a missing baseline yields exit 0"
        )

    # UNEXPLAINED_SHORTFALL (1) / UNEXPLAINED_SURPLUS (2), scoped to the rows
    # SC-005 actually gates on (`is_gate_relevant`): an advisory row cannot by
    # itself fail the gate (CP-3), though it is still counted and rendered.
    for row in rows:
        if not row.is_gate_relevant or row.counts_pass:
            continue
        applicable.append(
            "UNEXPLAINED_SHORTFALL" if row.difference < 0
            else "UNEXPLAINED_SURPLUS"
        )
        failures.append(
            f"{_census_row_label(row)}: source {row.source_count}, "
            f"destination {row.destination_count}, difference "
            f"{_census_signed(row.difference)} -- UNEXPLAINED (no accounting "
            f"reason names it)"
        )

    # CENSUS_ACCOUNTED (0) vs CENSUS_CLEAN (0): clean means nothing needed
    # explaining; accounted means something did and every unit is explained.
    if any(getattr(row, "reasons", ()) for row in rows):
        applicable.append("CENSUS_ACCOUNTED")

    verdict = engine.most_severe_verdict(applicable)
    return {
        "verdict": verdict,
        "exit_code": engine.exit_code_for(verdict),
        "human_label": engine.VERDICT_HUMAN_LABELS[verdict],
        "passed": engine.is_passing_verdict(verdict) and not failures,
        "failures": tuple(failures),
        "complete": False,
    }


def _census_cap_was_overruled(verdict: str) -> bool:
    """True when `verdict` is strictly MORE severe than 5.2's cap ceiling.

    Asked of the verdict the gate already computed, over `census.py`'s
    published `most_severe_verdict` and `GROSS_BASIS_VERDICT_CAP` -- it does
    NOT ask again whether the artifact is on the gross basis, and it does not
    restate the severity order. So it cannot disagree with the cap: it only
    reports that something above the ceiling won.

    Needed because `census.stamp_verdict` writes the cap notes whenever the
    gross basis suppressed a tally, including on a run that a more severe
    finding (say `BASELINE_MISSING`, exit 4) then decides. Rendering the note
    unqualified there would read as "capped at CENSUS_ACCOUNTED" beside a
    `[FAIL] ... exit 4` line -- two sentences the reader has to reconcile
    unaided. Display only; nothing reads this back.
    """
    engine = _census_module()
    try:
        return engine.most_severe_verdict(
            (verdict, engine.GROSS_BASIS_VERDICT_CAP)
        ) != engine.GROSS_BASIS_VERDICT_CAP
    except Exception:  # pragma: no cover - an unknown token is not our error
        return False


def _census_notes(block) -> tuple:
    """T023c -- every note this census carries, for DISPLAY only.

    The artifact's own `notes` array first, in the order it stored them, then
    any of 5.2's gross-basis cap notes that are not already there. Two sources,
    because the two paths into this renderer carry notes differently:

    * a census artifact that went through `census.stamp_verdict` already holds
      the cap notes, and they are copied through verbatim -- this renderer must
      not paraphrase what the document says about itself; and
    * an artifact `dict` handed straight to `RunReport.census` was never
      stamped, yet `_census_gate` still RECOMPUTES its verdict and would print
      a capped `CENSUS_ACCOUNTED` with nothing saying why. `census.py`'s public
      `gross_basis_cap_notes` supplies exactly the sentences `stamp_verdict`
      would have written, so the console cannot end up more silent than the
      artifact.

    The accessor is CALLED, never reimplemented: "is this capped" has one
    derivation (`census.is_gross_basis_row` over
    `starter_subtraction_basis`), and a second copy here -- even a read-only
    one -- is the duplicated-truth defect feature 038 exists to remove.

    NOT LOAD-BEARING (invariant 9). Nothing here is read back by
    `_census_gate`, by `census.recompute_verdict`, or by any exit code: a
    hand-written note cannot buy a cap, and deleting every note changes no
    verdict. It changes only what a reader is told.
    """
    engine = _census_module()
    notes = [
        str(note) for note in (
            (block.get("notes") or ()) if isinstance(block, dict) else ()
        ) if str(note).strip()
    ]
    for note in engine.gross_basis_cap_notes(block):
        if note not in notes:
            notes.append(note)
    return tuple(notes)


def _census_row_json(row) -> dict:
    """One `$defs.classRow`-shaped dict from an in-memory `ClassCensusRow`.

    DRIVEN BY THE TRANSLATION TABLE, exactly as `census.class_row_artifact`
    is: the key mapping is read out of
    `models.CLASS_CENSUS_ROW_ARTIFACT_FIELDS` and a `None` target is skipped
    -- so `starter_excluded`, `explained`, `out_of_scope` and `reasons` cannot
    reach the JSON under their internal names no matter what is added to the
    row later. `destination_count_net`, `difference_raw` and `verdict_class`
    are derived PROPERTIES on the row: read, never recomputed here, so this
    emitter cannot arrive at a second answer.

    Four required `classRow` keys are not functions of the row
    (`CLASS_CENSUS_ROW_ARTIFACT_FIELDS`'s docstring names them):

    * `gate_scope` comes from `census.gate_scope_for`, which is a pure
      function of `engine_can_create` -- called rather than restated, because
      a local `"required" if ... else "advisory"` would be a second copy of
      CP-3's rule.
    * `in_class_list_via` and `inventory_tables` are class-list PROVENANCE
      (T016). A `FidelityCensus` does not carry the class list, so they are
      OMITTED rather than invented -- fabricating `coverage_floor` for a class
      whose provenance is unknown would be a false claim about the roster.
    * `accounted_for` carries only what the row has: the reason TOKENS. The
      per-line `count`, `direction` and `report_ref` of a full `accountedLine`
      live on `census.AccountedLine`, not on the row, so they are absent
      rather than guessed.
    * `unexplained_shortfall` / `unexplained_surplus` come from
      `census.unexplained_counts`, the same arithmetic the standalone artifact
      uses. `explained` is a whole-row boolean, so an explained row owes
      nothing, and a NOT_EVALUATED row explains nothing and owes nothing.
    """
    engine = _census_module()

    block: dict = {}
    for internal, artifact_key in CLASS_CENSUS_ROW_ARTIFACT_FIELDS.items():
        if artifact_key is None:  # internal-only: never emitted
            continue
        value = getattr(row, internal, None)
        if value is None:
            # An OPTIONAL artifact property this row does not carry -- today
            # only A1's `owning_feature_system` on an ordinary class. Omitted
            # rather than emitted as null, because the property is enumerated
            # and the row object is `additionalProperties: false`.
            continue
        block[artifact_key] = value

    block["destination_count_net"] = row.destination_count_net
    block["difference_raw"] = row.difference_raw
    block["verdict_class"] = row.verdict_class

    # A1 row-property encoding; absent on every ordinary class. Idempotent with
    # the table-driven pass above now that `owning_feature_system` is a mapped
    # `ClassCensusRow` field: both write the same value, and this stays the one
    # reader that also copes with a row `dict`.
    owner = _census_owner(row)
    if owner:
        block["owning_feature_system"] = owner

    not_evaluated_reason = engine.select_not_evaluated_reason(row.reasons)
    if not_evaluated_reason is not None:
        block["not_evaluated_reason"] = not_evaluated_reason

    block["gate_scope"] = engine.gate_scope_for(
        row.object_class, row.engine_can_create)
    block["accounted_for"] = [{"reason": token} for token in row.reasons]

    if block["verdict_class"] == "NOT_EVALUATED" or row.explained:
        shortfall, surplus = 0, 0
    else:
        shortfall, surplus = engine.unexplained_counts(row.difference, ())
    block["unexplained_shortfall"] = shortfall
    block["unexplained_surplus"] = surplus

    return _census_reject_internal(
        block, CLASS_CENSUS_ROW_ARTIFACT_FIELDS,
        f"row {_census_class_name(row)!r}")


def _census_object_json(census) -> dict:
    """Machine-readable emission for an in-memory `FidelityCensus`.

    Top level DRIVEN BY `models.FIDELITY_CENSUS_ARTIFACT_FIELDS`, so the
    internal names (`run_id`, `taken_at`, `rows`, `source_project`,
    `destination_project`, `baseline`) are translated to the schema's
    (`census_id`, `generated_at`, `classes`, `projects.source`,
    `projects.destination`, `starter_baseline`) by the table and not by a
    third, hand-written set of names -- and `gate_pass`, whose table entry is
    `None`, is skipped by the loop and therefore CANNOT appear. The schema's
    top level is `additionalProperties: false` and carries `verdict` +
    `exit_code` instead, which is what the gate stamps below.

    `starter_baseline` and `totals` are produced by `census.py`'s own
    emitters (`starter_baseline_artifact`, `build_totals`), so the run report
    and the standalone artifact cannot disagree about either.

    This block is the run report's census SECTION, not a standalone census
    artifact: `instrument` and `class_list_provenance` are required at the
    artifact's top level and are not derivable from a `FidelityCensus`, so
    they are omitted and `census_artifact_complete: false` says so IN the
    document rather than leaving a reader to discover it.
    """
    engine = _census_module()
    rows = [_census_row_json(row) for row in census.rows]

    block: dict = {}
    for internal, artifact_key in FIDELITY_CENSUS_ARTIFACT_FIELDS.items():
        if artifact_key is None:  # internal-only (gate_pass): never emitted
            continue
        value = getattr(census, internal)
        if artifact_key == "starter_baseline":
            value = engine.starter_baseline_artifact(value)
            _census_reject_internal(
                value, STARTER_BASELINE_ARTIFACT_FIELDS, "starter_baseline")
        elif artifact_key == "classes":
            value = rows
        if "." in artifact_key:
            # `projects.source` / `projects.destination`: a `FidelityCensus`
            # knows the project NAME only -- the digests, `counted_at` and
            # `opened_read_only` of a full `$defs.projectRef` are the counting
            # pass's evidence and are not invented here.
            head, tail = artifact_key.split(".", 1)
            block.setdefault(head, {})[tail] = {"name": value}
        else:
            block[artifact_key] = value

    block["totals"] = engine.build_totals(rows)

    gate = _census_gate(census)
    block["verdict"] = gate["verdict"]
    block["exit_code"] = gate["exit_code"]
    block["verdict_human_label"] = gate["human_label"]
    block["census_artifact_complete"] = gate["complete"]

    return _census_reject_internal(
        block, FIDELITY_CENSUS_ARTIFACT_FIELDS, "top level")


def _census_artifact_json(artifact: dict) -> dict:
    """Machine-readable emission for an ALREADY-EMITTED census artifact.

    A `dict` on `RunReport.census` is what `census.build_artifact` /
    `census_cli` produce: already schema-shaped, so it needs no translation
    and is copied through in FULL (never truncated). The three verdict fields
    are then (re)stamped from `_census_gate`, i.e. from
    `census.gate_artifact`'s RECOMPUTED answer, which overrides whatever the
    document stored -- an artifact must not be able to buy a pass by writing
    `CENSUS_CLEAN` and `0` into itself.
    """
    block = json.loads(json.dumps(artifact, default=str))
    gate = _census_gate(artifact)
    block["verdict"] = gate["verdict"]
    block["exit_code"] = gate["exit_code"]
    block["verdict_human_label"] = gate["human_label"]
    _census_reject_internal(
        block, FIDELITY_CENSUS_ARTIFACT_FIELDS, "top level")
    baseline = block.get("starter_baseline")
    if isinstance(baseline, dict):
        _census_reject_internal(
            baseline, STARTER_BASELINE_ARTIFACT_FIELDS, "starter_baseline")
    for row in block.get("classes") or ():
        if isinstance(row, dict):
            _census_reject_internal(
                row, CLASS_CENSUS_ROW_ARTIFACT_FIELDS,
                f"row {_census_class_name(row)!r}")
    return block


def _census_json(census):
    """T022 -- machine-readable side of `RunReport.census` (FR-009..FR-013).

    `census is None` -> None -> the `census` key is OMITTED entirely, which is
    what keeps a census-free run report byte-identical to the pre-038
    snapshot (see the omit-when-empty note above `_CONSOLE_MAX_ROWS`).

    NEVER TRUNCATED. Every class row appears, in full; only
    `render_text_summary` may shorten anything, and only while saying so.

    Three shapes, in order: an already-emitted artifact `dict`; an object that
    emits itself (the hook a later, fuller census type can implement); an
    in-memory `FidelityCensus`. Anything else gets a marked, non-raising
    placeholder rather than an exception out of a serializer.
    """
    if census is None:
        return None
    if isinstance(census, dict):
        return _census_artifact_json(census)
    for method_name in ("to_artifact_dict", "to_snapshot_dict", "to_dict",
                        "as_dict"):
        method = getattr(census, method_name, None)
        if callable(method):
            try:
                emitted = json.loads(json.dumps(method(), default=str))
            except Exception:  # pragma: no cover - defensive
                break
            if isinstance(emitted, dict):
                return _census_artifact_json(emitted)
            return emitted
    if hasattr(census, "rows") and hasattr(census, "baseline"):
        return _census_object_json(census)
    return {
        "unrendered": repr(census),
        "note": (
            "RunReport.census is neither a census artifact dict nor a "
            "FidelityCensus and exposes no to_artifact_dict(); nothing could "
            "be measured from it"
        ),
    }


def _rows(records, formatter, indent: str = "    ",
          max_rows: int = _CONSOLE_MAX_ROWS):
    """CONSOLE ONLY. Yield at most `max_rows` formatted rows and then -- if
    and only if rows were actually held back -- one line stating exactly how
    many were omitted and where the complete list lives.

    The omitted count is computed from the very sequence that was sliced, so
    it cannot drift from reality. Never called by `to_snapshot_json`.
    """
    records = tuple(records)
    total = len(records)
    for rec in records[:max_rows]:
        yield formatter(rec)
    omitted = total - min(total, max_rows)
    if omitted:
        yield (
            f"{indent}... and {omitted} more not shown here "
            f"({total} total; the run-report JSON artifact lists all of them)"
        )


def _skip_snapshot(skip) -> dict:
    """One `skips[]` row, with T048e's comparison evidence when it exists.

    `collections_compared` is OMITTED rather than written as `[]` when the skip
    carries none. The distinction is load-bearing and is the same one
    `matched_to_source` makes for an absent class: an empty list would read as
    "the owned collections were compared and there are none", when the truth is
    "no collection comparison applies to this category, or none was made". Only
    the POS-owning categories populate it, so writing `[]` on the other five
    would manufacture evidence for a comparison that never ran.
    """
    row = {
        "category": skip.category.name,
        "source_guid": skip.source_guid,
        "reason": skip.reason.name,
        "detail": skip.detail,
    }
    compared = getattr(skip, "collections_compared", ())
    if compared:
        # Every member is a no-op by `Skip.__post_init__`, so `added` and
        # `dropped` are written for completeness rather than as variables --
        # a reader diffing two runs needs to see that they really are 0.
        row["collections_compared"] = [
            {
                "field_name": c.field_name,
                "added": c.added,
                "already_present": c.already_present,
                "dropped": c.dropped,
            }
            for c in compared
        ]
    return row


def _to_snapshot_json(self) -> str:
    """Render a RunReport as a deterministic JSON string for snapshot diffing.

    per_category keys are enum NAMES (e.g. "AFFIXES") ordered by
    GrammarCategory enum declaration order.
    """
    # Order per_category by GrammarCategory enum declaration order
    ordered_members = list(GrammarCategory.__members__)  # declaration order
    ordered_cats = [
        GrammarCategory[name]
        for name in ordered_members
        if GrammarCategory[name] in self.per_category
    ]

    payload = {
        "mode": self.mode.name,
        "context": {
            "run_id": self.context.run_id,
            "source_project_name": self.context.source_project_name,
            "target_project_name": self.context.target_project_name,
            "started_at": self.context.started_at,
        },
        "per_category": {
            cat.name: {
                "added": self.per_category[cat].added,
                "skipped": self.per_category[cat].skipped,
                "closure_pulled_in": self.per_category[cat].closure_pulled_in,
                "overwritten": getattr(self.per_category[cat], "overwritten", 0),
            }
            for cat in ordered_cats
        },
        "skips": [
            _skip_snapshot(s)
            for s in self.skips
        ],
        "identity_remap": dict(sorted(self.identity_remap.items())),
        "wall_clock_seconds": round(self.wall_clock_seconds, 3),
        # Feature 024 (FR-010/FR-013, contracts/dropped-item-report.md
        # "Snapshot compatibility"): additive keys only. A snapshot produced
        # before this feature simply lacks these keys; any reader that does
        # `data.get("dropped_items", [])` / `data.get("fidelity_by_guid", {})`
        # sees the same empty defaults this run report carries when nothing
        # has been dropped, so old snapshots remain loadable/comparable.
        "dropped_items": [
            _dropped_item_json(d) for d in self.dropped_items
        ],
        "fidelity_by_guid": {
            guid: status.name
            for guid, status in sorted(self.fidelity_by_guid.items())
        },
    }

    # ---- Feature 038 (transfer fidelity gaps) --------------------------
    # ADDITIVE and OMIT-WHEN-EMPTY (see the module comment above
    # `_CONSOLE_MAX_ROWS`): a report carrying no 038 data adds no keys at
    # all, so this block is a no-op for every pre-038 snapshot.
    #
    # NONE of these lists is capped. The artifact is the complete record;
    # only `render_text_summary` is allowed to shorten anything, and only
    # while saying so.

    # FR-006 / FR-187: identity SUBSTITUTION reported on its own key, never
    # folded into the ordinary match counts. A natural-key match is a
    # materially weaker fidelity claim than a GUID match, and a reader must
    # never have to infer which one happened.
    identity_substitution = _counter_block(self, "identity_substitution")
    if identity_substitution is not None:
        identity_substitution["basis"] = MatchBasis.NATURAL_KEY.name
        # T037: the count alone is unreadable. 1 substitution beside 3 matches
        # and 1 substitution beside the 1,806 matches measured on the
        # Ejagham/Ngoreme pair are different fidelity claims, and a reader must
        # not have to hunt for the denominator in another block. `null` -- NOT
        # 0 -- when the matched tally was never measured, per the same
        # "absent is not a zero" rule `census.unmatched_starter` applies.
        matched_total = self.matched_to_source_total
        identity_substitution["of_matched_to_source_total"] = (
            matched_total or None
        )
        if not matched_total:
            identity_substitution["denominator_note"] = (
                "no matched-to-source tally was measured on this run, so this "
                "substitution count has no denominator; absent is not zero"
            )
        identity_substitution["note"] = (
            "matched by a roster-admitted natural key because no GUID "
            "counterpart existed; weaker than an identity (GUID) match"
        )
        payload["identity_substitution"] = identity_substitution

    # T024d-a: the per-object-class matched tally the census reads as
    # `starter_matched_to_source`. Emitted with its own completeness flag so a
    # consumer can never read an absent class as a zero -- the distinction
    # `census.unmatched_starter` insists on, and the whole reason the
    # `baseline_matched` basis is withholdable.
    if self.matched_by_class or self.matches_unattributed:
        matched_block = {
            "by_object_class": dict(sorted(self.matched_by_class.items())),
            "total": self.matched_to_source_total,
            "complete": not self.matches_unattributed,
            "note": (
                "destination objects that already existed and were matched to "
                "a source object; an ABSENT class is not a zero -- it is no "
                "evidence the matcher evaluated that class"
            ),
            # T037 / FR-006: the basis split, carried HERE as well as under
            # `identity_substitution`, because `identity_substitution` is
            # omitted when it is empty (038's omit-when-empty discipline) and
            # a measured ZERO is exactly the reading that needed a home. On
            # the Ejagham/Ngoreme pair the report said `total: 1806` and
            # nothing else, so "found by GUID, natural key found nothing" and
            # "the natural-key path never ran" produced identical artifacts.
            "by_natural_key": self.identity_substituted,
            # Deliberately NOT named "by_identity": it is a REMAINDER, and the
            # `unattributed_by_category` matches inside it carry no basis
            # record at all. Naming it after a basis nothing recorded would
            # manufacture the GUID-strength claim FR-006 exists to prevent.
            "not_by_natural_key": (
                self.matched_to_source_total - self.identity_substituted
            ),
            "basis_note": (
                "by_natural_key is counted positively from "
                "MatchBasisRecord(basis=NATURAL_KEY); not_by_natural_key is "
                "the remainder and is NOT a positive count of GUID matches -- "
                "any match listed under unattributed_by_category carries no "
                "match-basis record, so its basis is unproven"
            ),
        }
        if self.matches_unattributed:
            matched_block["unattributed_by_category"] = {
                _enum_name(cat): n
                for cat, n in sorted(
                    self.matches_unattributed.items(), key=lambda kv: kv[0].value
                )
            }
            matched_block["unattributed_note"] = (
                "matches whose LCM object class could not be determined from a "
                "match_basis or enrichment record; while any exist, every "
                "per-class tally may be understated and no census row may use "
                "the baseline_matched subtraction basis"
            )
        payload["matched_to_source"] = matched_block

    # FR-014 / FR-015: every materialised (dependency, dependent) pair.
    if self.closure_edges:
        payload["closure_edges"] = [
            _closure_edge_json(e) for e in self.closure_edges
        ]

    # FR-016 / FR-017 / FR-019: items arriving knowingly incomplete.
    if self.incompleteness:
        payload["incompleteness"] = [
            _incompleteness_json(r) for r in self.incompleteness
        ]

    # FR-020..FR-022: add-only updates to objects that already existed.
    if self.enrichments:
        payload["enrichments"] = [
            _enrichment_json(r) for r in self.enrichments
        ]
    enriched = _counter_block(self, "enriched")
    if enriched is not None:
        payload["enriched_counts"] = enriched

    # FR-023..FR-025: MoAffixProcess outcomes, reproduced or not.
    if self.process_rules:
        payload["process_rules"] = [
            _process_rule_json(r) for r in self.process_rules
        ]
    not_reproducible = _counter_block(self, "not_reproducible")
    if not_reproducible is not None:
        payload["not_reproducible_counts"] = not_reproducible

    # FR-019 / SC-003 (T074): did each transferred affix end up in the template
    # column it occupied in the source? Emitted as a TALLY plus the failures
    # themselves -- the successes are a count because there is one per affix
    # MSA (125 on the measured corpus) and a per-success row would bury the
    # failures, but the count is what makes SC-003 answerable from the artifact
    # instead of from a bespoke driver.
    links = getattr(self, "affix_slot_links", ())
    if links:
        payload["affix_slot_links"] = _affix_slot_link_block(links)

    # ---- T048c: the swallowed write failures reach the ARTIFACT ---------
    # Feature 037 built `LeafExecutionFailure`, carried it onto `RunReport`,
    # and rendered it in `render_text_summary` -- but never emitted it here.
    # So the one surface that survives after the console has scrolled away,
    # and the one the census reads, said nothing at all: run
    # `CENSUS-20260820-094825` logged `failed=3` and its artifact had no
    # `leaf_execution_failures` key, so every reader doing `.get(...)` saw
    # `None` and could not distinguish "three writes failed" from "this build
    # does not report write failures".
    #
    # Emitted when non-empty, like every other record bucket, which keeps the
    # byte-identical-snapshot promise for a clean run. The measured ZERO is
    # not homeless as a result: `disposition.add_write_failed` carries it
    # whenever the disposition panel is emitted at all, which is the lesson
    # `matched_to_source`'s `by_natural_key` already records about
    # omit-when-empty. NOT truncated -- a swallowed write failure is the
    # least truncatable record this report holds.
    if self.leaf_execution_failures:
        payload["leaf_execution_failures"] = [
            {
                "category": _enum_name(f.category),
                "source_guid": f.source_guid,
                "exception_type": f.exception_type,
                "message": f.message,
            }
            for f in self.leaf_execution_failures
        ]
        payload["leaf_failed"] = self.leaf_failed
        payload["leaf_failed_note"] = (
            "execute_action calls that RAISED and were swallowed by the "
            "leaf-dispatch loop's swallow-and-continue policy (feature 037 "
            "defect C). These writes did NOT happen. per_category[*].added "
            "and disposition.add_created are counted from the PLAN and do not "
            "reflect them -- disposition.add_created_written does"
        )

    # ---- FR-022 / SC-010: the four-outcome disposition block -----------
    # The machine-readable half of the console panel, rendered from the SAME
    # `disposition_totals` call so the two can never disagree. Gated on the
    # report carrying 038 data (see `_has_038_data`) to keep the
    # byte-identical-snapshot promise for pre-038 runs.
    if _has_038_data(self):
        disposition = disposition_totals(self)
        if _has_reportable_outcome(disposition):
            # FR-022, stated rather than implied: the created tally and the
            # enriched tally are counted from disjoint record types, so an
            # enriched object is structurally incapable of appearing in
            # `add_created`.
            disposition["created_excludes_enriched"] = True
            disposition["counted_from"] = {
                "add_created":
                    "PlannedAction (per_category[*].added) -- the PLAN's "
                    "count of intended creates, which a swallowed write "
                    "failure does not reduce; see add_write_failed",
                "add_write_failed":
                    "LeafExecutionFailure (leaf_execution_failures)",
                "update_enriched":
                    "EnrichmentRecord (enrichments); was_created is always "
                    "false and unconstructible as true",
                "update_overwritten":
                    "PlannedOverwrite (per_category[*].overwritten); an "
                    "enrichment is CARRIED on one, so this total includes "
                    "update_enriched",
                "skip": "Skip (skips)",
                "dropped_with_reason": "DroppedItemRecord (dropped_items)",
                "no_fifth_outcome":
                    "RunReport.unreported_not_reproduced -- every "
                    "ProcessRuleTransferRecord with reproduced=False, minus "
                    "those named by a Skip.source_guid or a "
                    "DroppedItemRecord's item_guid/owner_guid",
            }
            disposition["note"] = (
                "SC-010: every selected item reaches exactly one of ADD, "
                "UPDATE (enriched), SKIP, or dropped-with-reason. Whether "
                "THIS run met that is the `no_fifth_outcome` key above, not "
                "this sentence -- T080 made the claim a measurement rather "
                "than a promise. The buckets are NOT summed: a "
                "dropped child is reported against its owner, not instead of "
                "it, so a grand total would count two different granularities "
                "as one"
            )
            payload["disposition"] = disposition

            # The certainty clause, machine-readable. Both flags hang on the
            # same evidence -- a residue baseline from an earlier GramTrans
            # run -- because both sentences are claims about a prior state of
            # the target that only that baseline records.
            prior_run_id = residue_baseline_run_id(self)
            payload["certainty"] = {
                "residue_baseline_run_id": prior_run_id or None,
                "is_first_transfer": not prior_run_id,
                "may_claim_identical_now": bool(prior_run_id),
                "may_claim_untouched_since_last_run": bool(prior_run_id),
                "strongest_true_line_for_an_enriched_item": (
                    "the target already held this object; N children added, "
                    "M already present"
                ),
                "note": certainty_note(self),
            }

    # FR-009..FR-013 -- T015 hook; omitted while `census is None`.
    census = _census_json(self.census)
    if census is not None:
        payload["census"] = census

    # T079 (R7) -- the report-only residue, as a RUN-REPORT key beside
    # `census` and deliberately NOT inside it: every object in
    # `census-artifact.schema.json` is `additionalProperties: false`, so a new
    # key on the artifact would be a hard validation failure and would force a
    # `schema_version` bump on a format that has not shipped. Emitted here so
    # the console's truncation note ("the run-report JSON artifact lists all
    # of them") is TRUE of this block too, and so a follow-up feature can
    # count R7's residue from the report rather than by parsing console text.
    # Omitted when empty, per the 038 snapshot-compatibility rule above.
    residue = report_only_residue_lines(self.census)
    if residue:
        payload["census_report_only_residue"] = [
            {
                "class": label,
                "difference": difference,
                "state": state,
                "owner": owner,
                "reason": reason,
            }
            for label, difference, state, owner, reason in residue
        ]

    return json.dumps(payload, indent=2, sort_keys=False)


# Attach as methods on RunReport (dataclass is frozen but method attachment works)
RunReport.build_from_plan = classmethod(_build_from_plan)
RunReport.to_snapshot_json = _to_snapshot_json


# ============================================================================
# Thin shim for callers that used the old module-level function
# ============================================================================

def to_snapshot_json(r: RunReport) -> str:
    """Shim: delegates to RunReport.to_snapshot_json() so preview.py /
    transfer.py callers don't break while they are updated."""
    return r.to_snapshot_json()


# ============================================================================
# Console rendering (for the FlexTools report.Info pane)
# ============================================================================

def render_text_summary(report: RunReport) -> Iterable[str]:
    """Yield human-readable summary lines for the FlexTools report pane.

    Used by gramtrans.py.MainFunction in both Preview and Move modes until
    the PyQt stats panel (T056/T066) replaces it.
    """
    yield f"[GramTrans] Run report  mode={report.mode.value}  run_id={report.context.run_id}"
    yield f"  Source: {report.context.source_project_name!r}"
    yield f"  Target: {report.context.target_project_name!r}"
    total_added = 0
    total_skipped = 0
    total_overwritten = 0
    total_enriched = 0
    for cat in sorted(report.per_category.keys(), key=lambda c: c.value):
        r = report.per_category[cat]
        total_added += r.added
        total_skipped += r.skipped
        ow = getattr(r, "overwritten", 0)
        total_overwritten += ow
        # FR-022: `enriched` rides beside `overwritten` because an enrichment
        # IS carried on a PlannedOverwrite -- and pointedly NOT beside `added`,
        # which counts creations only.
        enr = getattr(r, "enriched", 0)
        total_enriched += enr
        suffix = (
            f"  added={r.added}  skipped={r.skipped}"
            + (f"  overwritten={ow}" if ow else "")
            + (f"  enriched={enr}" if enr else "")
            + (f"  pulled_in={r.closure_pulled_in}" if r.closure_pulled_in else "")
        )
        yield f"  {cat.value:18s}{suffix}"
    yield (
        f"  {'TOTAL':18s}  added={total_added}  skipped={total_skipped}"
        + (f"  overwritten={total_overwritten}" if total_overwritten else "")
        + (f"  enriched={total_enriched}" if total_enriched else "")
    )
    if total_enriched:
        # FR-022 stated inline, where the two numbers sit side by side and a
        # reader might otherwise add them together.
        yield (
            f"  ({total_enriched} of the overwritten were ENRICHED -- add-only "
            "updates to objects the target ALREADY HAD; an enriched object is "
            "never counted in added)"
        )
    # Phase 3a FR-308: surface selected-but-empty categories explicitly so
    # the linguist sees the scan happened even when nothing transferred.
    for cat in getattr(report, "empty_categories", ()):
        yield f"  [skip] no items in source for {cat.value}"
    if report.skips:
        yield "  Skips:"
        for s in report.skips:
            yield f"    - [{s.category.value}] {s.source_guid}  {s.reason.value}: {s.detail}"
    if getattr(report, "excluded_lossy", ()):
        yield f"  Warnings (entries with missing references) -- {len(report.excluded_lossy)} total:"
        for el in report.excluded_lossy:
            yield f"    - [WARN] {el.message}"
    # Feature 024 (FR-010/FR-013, contracts/dropped-item-report.md): the
    # never-silent report channel. Renders identically whether `report` came
    # from Preview (`extra_dropped_items=payload.dropped_items`,
    # `Lib/ui/selection_wizard.py` / `Lib/ui/main_window.py`) or Move
    # (`extra_dropped_items=_dropped`, `Lib/transfer.py.execute`) -- both
    # thread through `RunReport.build_from_plan` into the same
    # `report.dropped_items` field this section reads, so the section
    # automatically appears in both the Preview pane and the post-run
    # statistics panel with no mode-specific code here. ASCII-only line
    # format (`->`/`-`, never unicode arrows/dashes) per Windows console
    # rules. An empty `dropped_items` renders no section at all.
    if report.dropped_items:
        yield f"  Dropped references / owned items -- {len(report.dropped_items)} total:"
        for d in report.dropped_items:
            yield (
                f"    - {d.owner_label} [{d.owner_kind} {d.owner_guid[:8]}] . "
                f"{d.field_name} -> \"{d.item_name}\" ({d.item_guid[:8]}) - {d.reason}"
            )
    if report.identity_remap:
        yield "  Identity remap (LCM denied GUID-on-create):"
        for src, dst in sorted(report.identity_remap.items()):
            yield f"    - {src} -> {dst}"
    # Feature 037 (defect C): swallowed execute_action failures -- without
    # this section, a run that planned N actions and only wrote (N - k) of
    # them (k execute_action calls raising and being swallowed) rendered
    # identically to a fully clean run, since per_category[*].added is
    # computed from the PLAN, not actual write outcomes. Empty
    # `leaf_execution_failures` renders no section at all (matches the
    # dropped_items convention above).
    if report.leaf_execution_failures:
        yield (
            f"  Execute failures (swallowed, run continued) -- "
            f"{report.leaf_failed} total:"
        )
        for f in report.leaf_execution_failures:
            yield (
                f"    - [{f.category.value}] {f.source_guid} - "
                f"{f.exception_type}: {f.message}"
            )
    # Feature 038 (transfer fidelity gaps): the new buckets. Every section is
    # conditional on its bucket being non-empty, so a pre-038 run renders
    # byte-identically to before this feature landed.
    for line in _render_038_lines(report):
        yield line
    yield f"  Wall clock: {report.wall_clock_seconds:.3f}s"


# ============================================================================
# Feature 038 -- console sections (human-readable surface)
# ============================================================================

def _render_disposition_lines(report) -> Iterable[str]:
    """FR-022 + SC-010: the four-outcome disposition panel.

    Every selected item reaches exactly one of ADD, UPDATE (enriched), SKIP,
    or dropped-with-reason, and this is where each one appears. The rows are
    deliberately NOT summed into a single grand total: a dropped child is
    reported AGAINST its owner, not INSTEAD of it, so the buckets count
    different granularities and an added-up figure would be a fiction. What
    the panel guarantees instead is that every bucket is named, non-empty or
    not, together with the record type it is answerable to -- which is what
    makes "there is no fifth outcome" a checkable claim.

    ASCII only, per the Windows console rule.
    """
    d = disposition_totals(report)
    if not _has_reportable_outcome(d):
        return

    def _row(tag: str, label: str, value) -> str:
        """One panel row, column-aligned so the numbers line up and a zero is
        as visible as a hundred."""
        return f"    - {tag:<8} {label:<36}: {value}"

    yield (
        "  Disposition -- every selected item reaches exactly ONE of these "
        "(SC-010). Whether THIS run managed it is the fifth-outcome check "
        "below, not this heading:"
    )
    yield _row("ADD", "created in target (new object)", d["add_created"])
    if d["add_write_failed"]:
        # T048c: never a silent difference between planned and written. The
        # row above is the plan's number; this one says what became of it.
        if d["create_split_reconciles"]:
            yield _row(
                "ADD", "of those, WRITE FAILED (swallowed)",
                f"{d['add_write_failed']} -- {d['add_created_written']} "
                "actually written",
            )
        else:
            yield _row(
                "ADD", "WRITE FAILED (swallowed)", d["add_write_failed"],
            )
            yield (
                f"      (WITHHELD: {d['add_write_failed']} swallowed write "
                f"failures against {d['add_created']} planned creates -- the "
                "written remainder has no valid subtraction basis and is not "
                "guessed)"
            )
    enriched_bits = []
    if d["enriched_partial"]:
        enriched_bits.append(
            f"{d['enriched_full']} FULL, {d['enriched_partial']} PARTIAL"
        )
    if d["enriched_gained_nothing"]:
        enriched_bits.append(f"{d['enriched_gained_nothing']} gained nothing")
    yield _row(
        "UPDATE", "ENRICHED, add-only, already existed",
        f"{d['update_enriched']}"
        + (" (" + "; ".join(enriched_bits) + ")" if enriched_bits else ""),
    )
    if d["overwrite_split_reconciles"]:
        yield _row(
            "UPDATE", "overwritten, source wins",
            d["update_overwritten_not_enriched"],
        )
    else:
        # T039's lesson: never state a subtraction whose basis does not
        # support it. An enrichment is carried ON a PlannedOverwrite, so
        # more enrichments than overwrites means the two tallies cannot be
        # split apart -- so the split is withheld and said to be withheld.
        yield _row(
            "UPDATE", "planned overwrites (total)", d["update_overwritten"],
        )
        yield (
            f"      (WITHHELD: {d['update_enriched']} enrichment records "
            f"against {d['update_overwritten']} planned overwrites -- an "
            "enrichment is carried on an overwrite, so the source-wins "
            "remainder has no valid subtraction basis here and is not guessed)"
        )
    yield _row(
        "SKIP", "matched; comparison found no delta",
        d["skip_no_delta_after_comparison"],
    )
    yield _row(
        "SKIP", "other reason (each named in Skips)", d["skip_other_reason"],
    )
    yield _row(
        "DROPPED", "reported with a reason", d["dropped_with_reason"],
    )
    if d["update_enriched"]:
        yield (
            f"    Enriched children: {d['enriched_children_added']} added, "
            f"{d['enriched_children_already_present']} already present in the "
            f"target, {d['enriched_children_dropped']} dropped with a reason"
        )
    yield (
        "    (created and enriched come from DIFFERENT records -- a "
        "PlannedAction versus an EnrichmentRecord, whose was_created is False "
        "by construction -- so no enriched object is counted as created)"
    )
    # T080: the panel's four rows say what landed in each bucket. This line
    # says whether anything landed OUTSIDE them, which is the claim SC-010
    # actually makes and the one the rows above cannot make for themselves.
    # Emitted unconditionally, in both directions: a bare "no fifth outcome"
    # with nothing to check against would be the reassuring half of a check
    # that never ran.
    if d["no_fifth_outcome"]:
        yield (
            "    Fifth-outcome check: PASS -- every item this run knew it "
            "could not reproduce is named in one of the buckets above"
        )
    else:
        yield (
            f"    Fifth-outcome check: [FAIL] "
            f"{d['unreported_not_reproduced']} item(s) recorded as NOT "
            "reproduced reached none of the four buckets -- neither a Skip "
            "nor a dropped-with-reason names them:"
        )
        for _guid in d["unreported_not_reproduced_guids"]:
            yield f"      - {_guid}"
    yield f"    Certainty: {certainty_note(report)}"


def _render_038_lines(report: RunReport) -> Iterable[str]:
    """Yield the console sections for the feature-038 buckets.

    Split out of `render_text_summary` only for readability; it is called
    from there, unconditionally, immediately before the wall-clock line.

    Truncation policy: detail lists go through `_rows`, which appends an
    explicit "... and N more not shown here" line whenever it holds anything
    back. Aggregate counts are ALWAYS printed in full (they are bounded by
    the number of categories / dependency kinds), so no section can hide the
    size of what it summarises. ASCII only, per the Windows console rule.

    Silence policy (T037, FR-006): a section is skipped when its bucket is
    EMPTY, never when its bucket is measured and reads zero. The match-basis
    section below is the case that forced the distinction -- an unrendered
    zero is indistinguishable from an unrun matcher, which is the one reading
    a fidelity report must never leave open.
    """
    # ---- FR-022 / SC-010: the four-outcome disposition panel, FIRST --------
    # It is the frame every section below is read inside: how many items
    # arrived by each route, and how much the report's sameness claims are
    # worth. Detail lists follow.
    for line in _render_disposition_lines(report):
        yield line

    # ---- FR-006 / FR-187: identity SUBSTITUTION, reported distinctly ------
    # An object found by name is NOT an object found by GUID. Rendering these
    # in the same bucket as ordinary matches would let the report overstate
    # its own fidelity, so substitution gets its own labelled section and its
    # own caveat line.
    substituted = getattr(report, "identity_substituted", 0)
    matched_total = getattr(report, "matched_to_source_total", 0)
    unattributed = sum(getattr(report, "matches_unattributed", {}).values())
    attributed = matched_total - unattributed
    if substituted:
        # The denominator is part of the claim, not decoration: "1" means one
        # thing beside 3 matches and something else entirely beside 1,806 (the
        # figure measured on the Ejagham/Ngoreme pair). It is printed only when
        # the matched tally was actually MEASURED -- a hand-built report
        # carries none, and "3 of 0" would be a fabricated denominator.
        scale = (
            f"{substituted} of {matched_total}" if matched_total
            else f"{substituted} total"
        )
        yield (
            f"  Identity SUBSTITUTION (matched by NATURAL KEY, not by GUID) "
            f"-- {scale}:"
        )
        for cat in _ordered_categories(report.per_category):
            n = getattr(report.per_category[cat], "identity_substitution", 0)
            if n:
                yield f"    - [{cat.value}] {n}"
        if matched_total:
            yield (
                f"    ({matched_total - substituted} matched without a natural "
                "key -- by GUID, by identity remap, or by fingerprint)"
            )
        if unattributed:
            yield (
                f"    ({unattributed} of those carried no match-basis record "
                "at all, so their basis is UNPROVEN -- it is not evidence of a "
                "GUID match)"
            )
        yield (
            "    (a natural-key match is a weaker identity claim than a GUID "
            "match -- verify these before relying on them)"
        )
    elif matched_total:
        # FR-006, the reading that had no console surface at all before T037.
        # Measured on the Ejagham/Ngoreme pair: the report carried
        # `matched_to_source.total == 1806` beside `identity_substituted == 0`
        # and printed NOTHING, so a run in which every object was found by GUID
        # was indistinguishable from a run in which the natural-key path had
        # never been built. Silence is the one rendering that cannot be read,
        # so a measured zero is now STATED -- and stated separately from the
        # matches whose basis nothing recorded, which prove nothing either way.
        yield (
            f"  Match basis -- {matched_total} destination "
            f"{'object' if matched_total == 1 else 'objects'} matched to a "
            f"source object:"
        )
        if attributed:
            yield (
                f"    - {attributed} "
                f"{'carries' if attributed == 1 else 'carry'} a match-basis "
                "record and NONE of them is a natural key: no identity "
                "substitution in this run"
            )
        if unattributed:
            yield (
                f"    - {unattributed} "
                f"{'carries' if unattributed == 1 else 'carry'} no "
                "match-basis record at all -- that basis is UNPROVEN, and it "
                "is NOT evidence that the natural-key path ran and found "
                "nothing"
            )

    # ---- FR-014 / FR-015: closure edges ----------------------------------
    edges = getattr(report, "closure_edges", ())
    if edges:
        yield f"  Closure edges (dependencies walked) -- {len(edges)} total:"
        by_kind: dict = {}
        for e in edges:
            k = _enum_value(e.kind)
            slot = by_kind.setdefault(k, [0, 0, 0])
            slot[0] += 1
            if e.verified:
                slot[1] += 1
            if e.deselected:
                slot[2] += 1
        for kind in sorted(by_kind):
            total, verified, deselected = by_kind[kind]
            yield (
                f"    - {kind}: {total} (verified {verified}, unverified "
                f"{total - verified}, deselected {deselected})"
            )
        attention = tuple(
            e for e in edges if not e.verified or e.deselected
        )
        if attention:
            yield (
                f"    Edges needing attention (unverified or deselected) -- "
                f"{len(attention)} of {len(edges)}; the verified remainder is "
                f"counted above and listed in full in the JSON artifact:"
            )

            def _edge_row(e) -> str:
                flags = []
                if not e.verified:
                    flags.append("unverified")
                if e.deselected:
                    flags.append("deselected")
                return (
                    f"      - [{','.join(flags)}] {_pair_text(e.dependent)} "
                    f"needs {_pair_text(e.dependency)} "
                    f"({_enum_value(e.kind)}, origin={e.origin})"
                )

            for line in _rows(attention, _edge_row, indent="      "):
                yield line

    # ---- FR-016 / FR-017 / FR-019 / SC-010: knowingly incomplete items ----
    incompleteness = getattr(report, "incompleteness", ())
    if incompleteness:
        yield (
            f"  Items arriving INCOMPLETE -- {len(incompleteness)} total "
            f"(reported, never transferred silently broken):"
        )

        def _incomplete_row(r) -> str:
            # `consequence` is what the user actually loses; it is non-empty
            # by construction and is never dropped from this line.
            return (
                f"    - \"{r.incomplete_label}\" "
                f"[{_pair_text(r.incomplete_item)}] is missing "
                f"\"{r.missing_label}\" [{_pair_text(r.missing_dependency)}] "
                f"({r.cause}) - consequence: {r.consequence}"
            )

        for line in _rows(incompleteness, _incomplete_row):
            yield line

    # ---- FR-020..FR-022: enrichments -------------------------------------
    enrichments = getattr(report, "enrichments", ())
    if enrichments:
        empty = sum(1 for r in enrichments if getattr(r, "is_empty", False))
        partial = sum(
            1 for r in enrichments
            if getattr(r, "fidelity", None) is FidelityStatus.PARTIAL
        )
        # FR-022 in the header itself: "were NOT created by this run" is the
        # whole point of the section, and a header that only said "enriched"
        # left the reader to know what the word means here.
        yield (
            f"  ENRICHED existing target objects -- UPDATE, add-only; these "
            f"objects were NOT created by this run, and nothing was blanked "
            f"or overwritten -- {len(enrichments)} total"
            + (f", {empty} of them gained nothing" if empty else "")
            + (f", {partial} PARTIAL (a source child was dropped)"
               if partial else "")
            + ":"
        )

        def _enrichment_row(r) -> str:
            # research.md R4: on a first transfer the strongest TRUE line is
            # "the target already held this object; N children added, M
            # already present" -- never "identical now", which Principle IV
            # reserves for a re-run against a known prior baseline. The
            # per-run certainty statement is printed once, by the disposition
            # panel, rather than repeated on every row.
            parts = []
            for c in r.collections:
                bits = f"{c.field_name} +{c.added}"
                extra = []
                if c.already_present:
                    extra.append(f"{c.already_present} already present")
                if c.dropped:
                    extra.append(f"{c.dropped} dropped with a reason")
                if extra:
                    bits += " (" + ", ".join(extra) + ")"
                parts.append(bits)
            if r.fields_updated:
                parts.append(
                    "fields filled where the target was empty: "
                    + ",".join(r.fields_updated)
                )
            detail = "; ".join(parts) if parts else "nothing gained"
            return (
                f"    - {r.object_class} \"{r.label}\" "
                f"{_guid8(r.source_guid)} -> {_guid8(r.target_guid)}: "
                f"[{_enum_name(getattr(r, 'fidelity', ''))}] the target "
                f"already held this object; {detail}"
            )

        for line in _rows(enrichments, _enrichment_row):
            yield line

    # ---- FR-023..FR-025 / SC-006: process rules --------------------------
    process_rules = getattr(report, "process_rules", ())
    if process_rules:
        not_reproduced = tuple(getattr(report, "rules_not_reproduced", ()))
        reproduced = len(process_rules) - len(not_reproduced)
        yield (
            f"  Process rules (MoAffixProcess) -- {len(process_rules)} total: "
            f"{reproduced} reproduced, {len(not_reproduced)} NOT reproduced:"
        )
        if not_reproduced:

            def _rule_row(r) -> str:
                # `not_reproducible_reason` is non-empty by construction for
                # every record in this list -- always rendered.
                return (
                    f"    - [NOT REPRODUCED] {_guid8(r.source_guid)} "
                    f"({len(r.input_contexts)} input contexts, "
                    f"{len(r.output_steps)} output steps) - "
                    f"{r.not_reproducible_reason}"
                )

            for line in _rows(not_reproduced, _rule_row):
                yield line

    # ---- FR-019 / SC-003: affix -> template column links (T074) ----------
    links = getattr(report, "affix_slot_links", ())
    if links:
        block = _affix_slot_link_block(links)
        attempted = block["attempted"]
        linked = block["linked_of_attempted"]
        not_in_run = block["not_in_run"]
        tail = (f" ({not_in_run} source affix(es) with a column were not "
                "part of this run)") if not_in_run else ""
        yield (
            f"  Affix template columns (FR-019) -- {linked} of {attempted} "
            f"transferred affix(es) occupy the column they had in the "
            f"source{tail}:"
        )

        def _link_row(f) -> str:
            who = _guid8(f["entry_guid"]) if f["entry_guid"] else "?"
            if f["outcome"] == "MSA_MISSING":
                return (
                    f"    - [NOT LINKED] affix {who}: it is in the "
                    "destination but its inflectional MSA "
                    f"{_guid8(f['msa_guid'])} is not, so there is nothing "
                    "to place in a column"
                )
            missing = ",".join(_guid8(g) for g in f["unresolved_slot_guids"])
            return (
                f"    - [NOT LINKED] affix {who}: template column(s) "
                f"{missing} are not in the destination"
            )

        for line in _rows(block["failures"], _link_row):
            yield line

    # ---- FR-009..FR-013: the fidelity census (T015 hook) -----------------
    for line in _render_census_lines(getattr(report, "census", None)):
        yield line


#: Row display order for the console census table, MOST URGENT FIRST. A
#: RE-EXPORT of `models.CENSUS_ROW_STATES`, never a second declaration: T079
#: moved the literal into `models.py` beside every other census vocabulary,
#: per `Lib/census.py:20` ("THE VOCABULARIES ARE RE-EXPORTS, NEVER
#: RE-DECLARATIONS"). The rationale for the ordering, and for T079's
#: `report_only` member, is recorded at that declaration.
_CENSUS_ROW_TIERS: tuple = CENSUS_ROW_STATES

# T079, checked at import: a class a 038 phase predicate gates on can never be
# report-only. Reclassifying an owned class as report-only is the one direction
# that would let this feature dodge its own gate, and a roster is exactly the
# kind of list that grows by accident, so the disjointness is ENFORCED rather
# than documented. This costs one set intersection at import and needs no
# `Lib/census.py` import; `report_only_roster_defects` is the fuller check that
# also verifies `CENSUS_PHASE_GATED_CLASSES` still mirrors the predicates.
_REPORT_ONLY_OVERREACH = sorted(
    set(CENSUS_REPORT_ONLY_RESIDUE) & CENSUS_PHASE_GATED_CLASSES)
if _REPORT_ONLY_OVERREACH:  # pragma: no cover - a source defect, not a state
    raise ValueError(
        "feature 038 T079: " + ", ".join(_REPORT_ONLY_OVERREACH) + " is both "
        "on the report-only residue roster and named by a 038 phase "
        "predicate. A class this feature has an executable gate on is OWNED; "
        "calling it report-only would let the gate be dodged by reclassifying "
        "its subject"
    )


def _census_bare_class_name(row) -> str:
    """The plain LCM class name of a row, with any A1 owner qualifier removed.

    `_census_row_label` renders `FsFeatStrucType (LangProject....)` for an
    Amendment A1 split; the roster below is keyed by the class, so the label
    form has to be reduced before it can be looked up. Splitting on " (" is
    safe because an LCM class name contains no space.
    """
    return _census_class_name(row).split(" (")[0].strip()


def report_only_residue_entry(row):
    """`(owner, reason)` if this row's class is R7 report-only, else None.

    THE ONE LOOKUP. Everything T079 renders goes through it, so there is no
    second place a class could be treated as report-only.
    """
    return CENSUS_REPORT_ONLY_RESIDUE.get(_census_bare_class_name(row))


def _census_row_tier(row: dict) -> str:
    """Which `_CENSUS_ROW_TIERS` band one emitted census row belongs to.

    T079. `report_only` sits BETWEEN the two failure bands and the two
    agreement bands, and the order of the tests below is the whole point:

    * `unexplained` still wins. A report-only class with an unaccounted loss
      keeps its `[FAIL] UNEXPLAINED` line and its place at the top of the
      table. The new state exists to stop a GREEN row reading as a promise,
      never to soften a red one.
    * `not_evaluated` still wins, because "nobody measured this" is a stronger
      statement than "nobody owns it" and the artifact already says it with a
      reason token.
    * otherwise a rostered class is `report_only` and NOT `matched`. That is
      R7's residual risk, and T078 measured it arriving inverted: on the
      ejagham pair `FsComplexFeature`, `FsSymFeatVal`, `FsClosedFeature`,
      `LexEntryInflType`, `PhFeatureConstraint`, `LexReference`, `CmFile`,
      `Segment` and `CmTranslation` ALL read MATCHED -- five because the
      transfer got them right, four because that corpus simply holds none of
      them, and `Segment` loses 26,666 objects on the next pair. One word for
      all nine would be a claim this feature never made.

    Nothing here reads or writes a verdict, an exit code, a `gate_scope` or a
    tally: the band decides display order and one column.
    """
    if row.get("unexplained_shortfall") or row.get("unexplained_surplus"):
        return "unexplained"
    verdict_class = row.get("verdict_class")
    if verdict_class == "NOT_EVALUATED":
        return "not_evaluated"
    if report_only_residue_entry(row) is not None:
        return CENSUS_REPORT_ONLY_STATE
    if verdict_class == "MATCHED":
        return "matched"
    return "accounted"


def report_only_roster_defects() -> tuple:
    """T079 -- every way the report-only roster could be lying, as strings.

    Empty means the roster is sound. Returned rather than raised so a test can
    name the defect and a live run can never die inside a renderer.

    Five checks. The first four all ask whether a class is wrongly ON the
    roster; **check 5 is the only one that asks whether one is missing from
    it**, and T113 is what it was filed for -- with four one-directional
    checks the roster could be silently short of a path the spec's Assumptions
    name and this function still reported clean.

    1. `CENSUS_PHASE_GATED_CLASSES` still equals the union of the phase
       predicates' declared scopes. `models.py` cannot import `census.py` (the
       dependency direction is census -> models), so the set is spelled there
       as names; this is what stops the copy drifting from the predicates it
       mirrors. `PHASE_5_CLASSES` is deliberately excluded: it is `None`,
       meaning "every required row", and folding that in would make every
       class phase-gated and the roster empty.
    2. No rostered class is phase-gated (also enforced at import).
    3. Every roster entry names BOTH an owner and a reason. "Report-only" with
       no successor named is a line the user cannot act on, which SC-010 does
       not accept as a report.
    4. No rostered class is one the artifact already excludes from the delta.
       `CmAnthroItem` is NOT_EVALUATED with `OUT_OF_SCOPE_CLASS`, a state
       already distinct from `matched`; rostering it would be a second name
       for a state the artifact states correctly.
    5. T113 -- COMPLETENESS, the other direction. Every class T109's
       `CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES` names is on this roster. A
       class another feature governs is measured here, reported here and
       undertaken elsewhere, which is what `report_only` says; the two rosters
       therefore cannot disagree about who governs a class. The converse is
       deliberately NOT checked -- the phonology family, the Fs* cascade and
       `CmFile` are report-only with no successor feature, which is exactly
       why they are not governed.

       Its carve-out is itself checked, because an unguarded carve-out is the
       blind spot T113 was filed about: a governed class that the artifact
       already excludes from the delta cannot be rostered (check 4 forbids it)
       and so is exempt from check 5 -- and that combination is reported as
       its own defect rather than passing quietly, since a class cannot be
       both "governed by another feature and reported" and "excluded from the
       delta before it is measured".
    """
    engine = _census_module()
    defects: list = []

    mirrored = (
        frozenset(engine.PHASE_1_CLASSES)
        | frozenset(engine.PHASE_2_MATCHED_CLASSES)
        | frozenset(engine.PHASE_3_CLASSES)
        | frozenset(engine.PHASE_4_CLASSES)
    )
    if mirrored != CENSUS_PHASE_GATED_CLASSES:
        defects.append(
            "models.CENSUS_PHASE_GATED_CLASSES no longer mirrors the phase "
            "predicates: only-in-models "
            f"{sorted(CENSUS_PHASE_GATED_CLASSES - mirrored)}, "
            f"only-in-census {sorted(mirrored - CENSUS_PHASE_GATED_CLASSES)}"
        )

    overreach = sorted(set(CENSUS_REPORT_ONLY_RESIDUE) & mirrored)
    if overreach:
        defects.append(
            f"{overreach} are report-only AND named by a phase predicate -- a "
            "class this feature gates on is owned, not report-only"
        )

    for name, entry in sorted(CENSUS_REPORT_ONLY_RESIDUE.items()):
        try:
            owner, reason = entry
        except (TypeError, ValueError):
            defects.append(
                f"{name}: roster entry is not an (owner, reason) pair: "
                f"{entry!r}"
            )
            continue
        if not str(owner).strip():
            defects.append(
                f"{name}: report-only with NO owner named -- a report line "
                "the user cannot act on is not a report (SC-010)"
            )
        if not str(reason).strip():
            defects.append(f"{name}: report-only with NO reason recorded")

    excluded = getattr(engine, "NOT_EVALUATED_CLASS_REASONS", {})
    for name in sorted(set(CENSUS_REPORT_ONLY_RESIDUE) & set(excluded)):
        defects.append(
            f"{name}: already excluded from the census delta as "
            f"{excluded[name]}, so its row is NOT_EVALUATED and already "
            "distinct from matched -- rostering it is a second name for a "
            "state the artifact states correctly"
        )

    # Check 5 (T113). Read as module globals so a test can poison either
    # roster, the same handle the four checks above are exercised through.
    governed = set(CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES)
    contradictory = sorted(governed & set(excluded))
    for name in contradictory:
        defects.append(
            f"{name}: named by CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES AND "
            f"already excluded from the census delta as {excluded[name]}. A "
            "class cannot be both governed-by-another-feature-and-reported "
            "and excluded-before-it-is-measured; check 4 forbids rostering "
            "it, so check 5 cannot require it either"
        )
    missing = sorted(governed - set(CENSUS_REPORT_ONLY_RESIDUE)
                     - set(contradictory))
    if missing:
        defects.append(
            f"{missing} are governed by another feature "
            "(CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES, derived from the "
            "spec's three named paths) but are NOT on the report-only "
            "residue roster -- so the console calls them `accounted` while "
            "the rest of their own path reads `report_only`. A class another "
            "feature governs is measured here and undertaken elsewhere, "
            "which is what report-only means"
        )

    return tuple(defects)


def report_only_residue_lines(census) -> tuple:
    """T079 -- the report-only residue of one census, as structured rows.

    `(label, difference, state, owner, reason)` per rostered class the census
    actually carries. THE MACHINE-READABLE SURFACE: a follow-up feature counts
    "what is still merely explained, not fixed" by calling this rather than by
    parsing console text, and `_render_report_only_lines` renders precisely
    what it returns, so the two cannot disagree.

    ORDERED `report_only` FIRST, then by the table's own urgency key. This is
    deliberately NOT the table's order, and the console budget is why: 23
    classes are rostered and `_CONSOLE_MAX_ROWS` is 20, so under the table's
    ordering the differing rows sort first and the truncation eats exactly the
    rows this block exists for -- measured, on the ngoreme pair, where 19
    differing rows left one of the four agreeing rows visible. The differing
    rows are already at the TOP of the table above, marked `(report-only)`;
    the ones that merely agree appear nowhere else, so they lead here.

    Deliberately NOT emitted into the census artifact. Every object in
    `census-artifact.schema.json` is `additionalProperties: false`, so a new
    key would be a hard validation failure and would force a
    `schema_version` bump on a format that has not shipped. R7 asked for a
    RUN-REPORT line, and this is the run report.
    """
    block = _census_json(census)
    rows = block.get("classes") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        return ()
    out: list = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        entry = report_only_residue_entry(row)
        if entry is None:
            continue
        owner, reason = entry
        out.append((
            (
                0 if _census_row_tier(row) == CENSUS_REPORT_ONLY_STATE else 1,
                _census_row_sort_key(row),
            ),
            (
                _census_row_label(row),
                row.get("difference"),
                _census_row_tier(row),
                owner,
                reason,
            ),
        ))
    return tuple(entry for _, entry in sorted(out, key=lambda p: p[0]))


def _render_report_only_lines(entries) -> Iterable[str]:
    """T079 -- R7's report-only residue, one line per class, with its reason.

    R7: "Phase 5 fixes nothing directly: every residual class is measured by
    the R2 census and, where counts differ, gets a run-report line with a
    reason." Before this block there was no such line: T078 measured every one
    of these classes as a bare row with `accounted_for: []`, so a reader saw
    the number and never learned that nothing in this feature undertakes it.

    The two headline figures are printed in FULL and separately -- the classes
    that DIFFER and the classes that AGREE -- because the second group is the
    one R7's residual risk is about, and a single count would hide it. Nothing
    here is netted: a class at 0 on this pair and -26,666 on the next is
    reported as both, in the reason string.
    """
    if not entries:
        return
    differing = tuple(e for e in entries if e[1] not in (0, None))
    agreeing = tuple(e for e in entries if e[1] == 0)
    unmeasured = tuple(e for e in entries if e[1] is None)
    loss = sum(-int(e[1]) for e in differing if int(e[1]) < 0)

    yield (
        f"    [INFO] Report-only residue (R7) -- {len(entries)} of these rows "
        f"are classes this feature MEASURES and does not undertake to fix: "
        f"{len(differing)} differing ({loss} objects short), "
        f"{len(agreeing)} agreeing on this pair, {len(unmeasured)} unmeasured."
    )
    yield (
        "      A class here is never reported as \"matched\": its state is "
        "\"report_only\", so one that merely agrees on THIS pair cannot rot "
        "behind a green gate (R7's residual risk). Not one of them can fail "
        "or pass the gate on this account -- the verdict above is computed "
        "from counts, bases and accounting lines alone."
    )

    def _line(entry) -> str:
        label, difference, state, owner, reason = entry
        return (
            f"      - {label} {_census_signed(difference)} [{state}] "
            f"owner: {owner} -- {reason}"
        )

    for line in _rows(entries, _line, indent="      "):
        yield line


def _census_row_sort_key(row: dict):
    """Sort emitted census rows by urgency, then by size, then by name."""
    difference = row.get("difference")
    try:
        magnitude = abs(int(difference))
    except (TypeError, ValueError):
        magnitude = 0
    return (
        _CENSUS_ROW_TIERS.index(_census_row_tier(row)),
        -magnitude,
        _census_row_label(row),
    )


def _render_census_lines(census) -> Iterable[str]:
    """T022 -- human-readable side of `RunReport.census` (FR-009..FR-013).

    Rendered FROM the same emitted block `to_snapshot_json` writes
    (`_census_json`) and gated by the same `_census_gate`, so the console and
    the artifact cannot report different counts or different verdicts for one
    census.

    Truncation policy, matching every other 038 section in this file: the
    per-class table goes through `_rows`, which appends an explicit
    "... and N more not shown here" line whenever it holds anything back, and
    the rows are ordered so what is held back is always the least urgent.
    The header counts, the per-state tally and the totals are printed in FULL
    -- they are bounded by the number of verdict classes -- so no section can
    hide the size of what it summarises. The notes block (T023c) goes through
    `_rows` for the same reason.

    A CAPPED VERDICT IS NEVER SILENT: `fidelity-census.md` 5.2 lets a
    gross-basis run report `CENSUS_ACCOUNTED` where the raw tallies say
    `UNEXPLAINED_SHORTFALL`, and the reason lives in the artifact's `notes`.
    `_census_notes` renders it here, so "accounted" can never be mistaken for
    "nothing was lost".

    A MISSING BASELINE IS A FAILURE LINE, not a blank and not a warning: it
    renders `[FAIL] ... MISSING` and the verdict line then reads
    BASELINE_MISSING / exit 4 / gate FAILED.

    The row count is labelled "rows", never "classes": Amendment A1 emits one
    row per owning feature system for a split class, so rows and classes are
    deliberately not the same number and this renderer asserts neither.

    ASCII only, per the Windows console rule.
    """
    if census is None:
        return

    block = _census_json(census)
    rows = block.get("classes") if isinstance(block, dict) else None
    if not isinstance(rows, list) or not rows:
        # Present but unrenderable (see `_census_json`'s placeholder branch).
        # Announced rather than silently dropped.
        yield "  Fidelity census: present, but it exposed no per-class rows"
        yield (
            "    (whatever could be read from it is in the run-report JSON "
            "artifact under \"census\")"
        )
        return

    gate = _census_gate(census)
    projects = block.get("projects") or {}
    source = (projects.get("source") or {}).get("name", "")
    destination = (projects.get("destination") or {}).get("name", "")

    yield (
        f"  Fidelity census -- {len(rows)} "
        f"{'row' if len(rows) == 1 else 'rows'} "
        f"({block.get('census_id') or 'no census id'}, taken "
        f"{block.get('generated_at') or 'unknown time'}):"
    )
    yield f"    Source:      {source!r}"
    yield f"    Destination: {destination!r}"

    # ---- the starter baseline. Absence is a VERDICT, so it gets [FAIL]. ----
    baseline = block.get("starter_baseline") or {}
    if not baseline or baseline.get("kind") in (None, "", "none"):
        yield (
            "    [FAIL] Starter baseline: MISSING -- nothing could be "
            "subtracted for content the destination already held. Absence is "
            "a verdict (BASELINE_MISSING, exit 4), never a warning and never "
            "an assumed zero."
        )
    else:
        yield (
            f"    Starter baseline: {baseline.get('kind')} from "
            f"{baseline.get('project_name', '')!r} -- "
            f"{baseline.get('class_count', 0)} classes, natural keys: "
            f"{'yes' if baseline.get('carries_natural_keys') else 'no'}"
        )

    # ---- the whole shape, in full: one bounded tally line. ----------------
    tally: dict = {}
    for row in rows:
        tier = _census_row_tier(row)
        tally[tier] = tally.get(tier, 0) + 1
    yield (
        "    Rows by state: "
        + ", ".join(
            f"{tier}={tally[tier]}"
            for tier in _CENSUS_ROW_TIERS if tier in tally
        )
    )

    totals = block.get("totals") or {}
    yield (
        f"    Totals: shortfall {totals.get('total_shortfall', 0)} "
        f"(unexplained {totals.get('unexplained_shortfall', 0)}), surplus "
        f"{totals.get('total_surplus', 0)} (unexplained "
        f"{totals.get('unexplained_surplus', 0)}) -- reported separately, "
        f"never netted against each other"
    )

    # ---- the per-class table ---------------------------------------------
    label_width = min(48, max(
        len("class"), *(len(_census_row_label(r)) for r in rows)))
    yield (
        f"    {'class':<{label_width}}  {'source':>6}  {'dest':>6}  "
        f"{'diff':>7}  state"
    )
    yield (
        "    " + "-" * label_width + "  " + "-" * 6 + "  " + "-" * 6
        + "  " + "-" * 7 + "  " + "-" * 13
    )

    def _census_table_row(row: dict) -> str:
        marks = []
        tier = _census_row_tier(row)
        if tier == "unexplained":
            marks.append("[FAIL] UNEXPLAINED")
        elif tier == "accounted":
            marks.append("[OK] accounted")
        if row.get("gate_scope") == "advisory":
            # CP-3: an advisory row is counted and rendered but cannot by
            # itself fail the gate. Saying so beats leaving a reader to guess
            # why a nonzero difference did not change the verdict.
            marks.append("(advisory)")
        if report_only_residue_entry(row) is not None:
            # T079/R7: this feature measures the class and does not undertake
            # to fix it. Marked on EVERY rostered row, including the ones the
            # tier system still calls `unexplained` -- the mark and the state
            # answer two different questions, and the mark is the one that
            # says who owns the class. `gate_scope` is untouched: a
            # report-only row is still `required` and still counted.
            marks.append("(report-only)")
        reasons = [
            str(line.get("reason")) for line in row.get("accounted_for") or ()
            if isinstance(line, dict) and line.get("reason")
        ]
        # `not_evaluated_reason` is the ONE token the schema requires of a
        # NOT_EVALUATED row and it is normally also one of the accounting
        # reasons, so it is printed once -- prepended, because it is why the
        # row was not measured -- rather than twice.
        not_evaluated_reason = row.get("not_evaluated_reason")
        if not_evaluated_reason:
            reasons = [str(not_evaluated_reason)] + [
                r for r in reasons if r != str(not_evaluated_reason)
            ]
        if reasons:
            marks.append(",".join(reasons))
        return (
            f"    {_census_row_label(row):<{label_width}}  "
            f"{row.get('source_count', '?'):>6}  "
            f"{row.get('destination_count_total', '?'):>6}  "
            f"{_census_signed(row.get('difference')):>7}  "
            f"{str(row.get('verdict_class') or '?'):<13} "
            + " ".join(marks)
        ).rstrip()

    ordered = sorted(rows, key=_census_row_sort_key)
    for line in _rows(ordered, _census_table_row, indent="    "):
        yield line

    # ---- T079: R7's report-only residue, each class with its reason ------
    # Placed after the table and BEFORE the verdict, in the same register as
    # the notes block: what the numbers above do and do not commit this
    # feature to. It changes no verdict; `report_only_residue_lines` reads the
    # same emitted block the table did.
    for line in _render_report_only_lines(report_only_residue_lines(census)):
        yield line

    # ---- the verdict: token, human label, exit code, pass/fail -----------
    yield (
        f"    {'[OK]' if gate['passed'] else '[FAIL]'} Census verdict: "
        f"{gate['verdict']} -- {gate['human_label']} "
        f"(exit {gate['exit_code']}); gate "
        f"{'PASSED' if gate['passed'] else 'FAILED'}"
    )
    if not gate["complete"]:
        yield (
            "    [INFO] verdict computed from the in-memory census alone (no "
            ".fwdata digests, instrument block, class-list provenance or "
            "duplicate reports), so it is a FLOOR -- the standalone census "
            "artifact's gate can return the same verdict or a MORE severe "
            "one, never a less severe one"
        )
    # ---- the artifact's own notes: where a CAPPED verdict says so -------
    # T023c. 5.2's gross-basis cap turns UNEXPLAINED_SHORTFALL into
    # CENSUS_ACCOUNTED and writes its reason into `notes`. Before this
    # block, the verdict line above printed the capped token and NOTHING
    # printed the reason, so a suppressed 21-object shortfall read exactly
    # like a run that lost nothing. Placed beside the FLOOR line because it
    # is the same kind of statement -- what the verdict above does and does
    # not establish -- and in the same register.
    notes = _census_notes(block)
    if notes:
        yield (
            f"    [WARN] Census notes -- {len(notes)} total (the census's own "
            f"reportage; every verdict above is computed from counts, bases "
            f"and accounting lines, NEVER from a note):"
        )
        for line in _rows(notes, lambda n: f"      {n}", indent="      "):
            yield line
        if _census_cap_was_overruled(gate["verdict"]):
            # A cap note is written whenever the gross basis suppressed a
            # tally, which can happen on a run a MORE severe finding then
            # decides. Left alone the note would read as though the run
            # finished at the ceiling, contradicting the [FAIL] line above.
            engine = _census_module()
            yield (
                f"      [INFO] the cap those notes describe did NOT decide "
                f"this run: {gate['verdict']} is more severe than the "
                f"{engine.GROSS_BASIS_VERDICT_CAP} ceiling, so it stands "
                f"(exit {gate['exit_code']})"
            )
    if gate["failures"]:
        yield f"    Gate failures -- {len(gate['failures'])} total:"
        for line in _rows(
                gate["failures"], lambda f: f"      - {f}", indent="      "):
            yield line
