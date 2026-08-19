"""Run-report aggregation and snapshot-JSON serialization.

Implements `RunReport.to_snapshot_json()` per contracts/run-report.md. The
output JSON has stable field ordering so integration-test snapshot diffs are
meaningful.

Per constitution Principle III closing clause + FR-018, every PlannedAction
in the run plan must end up in either `per_category[*].added` or `skips` —
nothing disappears silently. The FR-018 invariant is enforced by
`RunReport.__post_init__` at construction time.
"""
from __future__ import annotations

import json
from typing import Iterable

if __package__:
    from .models import (
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

    def _count_substitution(bucket, obj) -> None:
        """Feature 038 (FR-006): tally objects matched by a roster-admitted
        NATURAL KEY rather than by GUID. Counted from the `match_basis`
        record on the plan item itself, so the report cannot claim a stronger
        identity basis than the matcher actually used. Items planned before
        038's matcher ran carry `match_basis=None` and are not counted."""
        basis = getattr(obj, "match_basis", None)
        if basis is not None and getattr(basis, "basis", None) is MatchBasis.NATURAL_KEY:
            bucket["identity_substitution"] += 1

    for action in plan.actions:
        b = _bucket(action.category)
        b["added"] += 1
        _count_substitution(b, action)
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
        _count_substitution(b, ow)

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
        dropped_items=tuple(extra_dropped_items),
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
        process_rules=tuple(getattr(plan, "process_rules", ()))
        + tuple(extra_process_rules),
        census=census,
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


def _enrichment_json(r) -> dict:
    return {
        "object_class": r.object_class,
        "source_guid": r.source_guid,
        "target_guid": r.target_guid,
        "label": r.label,
        # FR-022: the created-vs-enriched distinction is STATED, not inferred.
        "was_created": bool(r.was_created),
        "is_empty": bool(getattr(r, "is_empty", False)),
        "fields_updated": list(r.fields_updated),
        "collections": [
            {
                "field_name": c.field_name,
                "added": c.added,
                "already_present": c.already_present,
                "dropped": c.dropped,
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


def _census_json(census):
    """T015 HOOK -- machine-readable side of `RunReport.census`.

    `FidelityCensus` does not exist yet (T015 defines it; the annotation on
    `RunReport.census` is a forward reference). Until then this deliberately
    does NOT reach into the object's internals: it asks the census to render
    itself and otherwise emits a marked, non-raising placeholder.
    `census is None` -> None -> the `census` key is omitted entirely.

    T015: give `FidelityCensus` a `to_snapshot_dict()` returning the
    per-object-class rows (FR-009..FR-013) and this function needs no edit.
    """
    if census is None:
        return None
    for method_name in ("to_snapshot_dict", "to_dict", "as_dict"):
        method = getattr(census, method_name, None)
        if callable(method):
            try:
                return json.loads(json.dumps(method(), default=str))
            except Exception:  # pragma: no cover - defensive
                break
    return {
        "unrendered": repr(census),
        "note": "census exposes no to_snapshot_dict(); see T015",
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
            {
                "category": s.category.name,
                "source_guid": s.source_guid,
                "reason": s.reason.name,
                "detail": s.detail,
            }
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
            {
                "owner_kind": d.owner_kind,
                "owner_guid": d.owner_guid,
                "owner_label": d.owner_label,
                "field_name": d.field_name,
                "item_name": d.item_name,
                "item_guid": d.item_guid,
                "reason": d.reason,
            }
            for d in self.dropped_items
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
        identity_substitution["note"] = (
            "matched by a roster-admitted natural key because no GUID "
            "counterpart existed; weaker than an identity (GUID) match"
        )
        payload["identity_substitution"] = identity_substitution

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

    # FR-009..FR-013 -- T015 hook; omitted while `census is None`.
    census = _census_json(self.census)
    if census is not None:
        payload["census"] = census

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
    for cat in sorted(report.per_category.keys(), key=lambda c: c.value):
        r = report.per_category[cat]
        total_added += r.added
        total_skipped += r.skipped
        ow = getattr(r, "overwritten", 0)
        total_overwritten += ow
        suffix = (
            f"  added={r.added}  skipped={r.skipped}"
            + (f"  overwritten={ow}" if ow else "")
            + (f"  pulled_in={r.closure_pulled_in}" if r.closure_pulled_in else "")
        )
        yield f"  {cat.value:18s}{suffix}"
    yield (
        f"  {'TOTAL':18s}  added={total_added}  skipped={total_skipped}"
        + (f"  overwritten={total_overwritten}" if total_overwritten else "")
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

def _render_038_lines(report: RunReport) -> Iterable[str]:
    """Yield the console sections for the feature-038 buckets.

    Split out of `render_text_summary` only for readability; it is called
    from there, unconditionally, immediately before the wall-clock line.

    Truncation policy: detail lists go through `_rows`, which appends an
    explicit "... and N more not shown here" line whenever it holds anything
    back. Aggregate counts are ALWAYS printed in full (they are bounded by
    the number of categories / dependency kinds), so no section can hide the
    size of what it summarises. ASCII only, per the Windows console rule.
    """
    # ---- FR-006 / FR-187: identity SUBSTITUTION, reported distinctly ------
    # An object found by name is NOT an object found by GUID. Rendering these
    # in the same bucket as ordinary matches would let the report overstate
    # its own fidelity, so substitution gets its own labelled section and its
    # own caveat line.
    substituted = getattr(report, "identity_substituted", 0)
    if substituted:
        yield (
            f"  Identity SUBSTITUTION (matched by NATURAL KEY, not by GUID) "
            f"-- {substituted} total:"
        )
        for cat in _ordered_categories(report.per_category):
            n = getattr(report.per_category[cat], "identity_substitution", 0)
            if n:
                yield f"    - [{cat.value}] {n}"
        yield (
            "    (a natural-key match is a weaker identity claim than a GUID "
            "match -- verify these before relying on them)"
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
        yield (
            f"  ENRICHED existing target objects (add-only; nothing was "
            f"blanked or overwritten) -- {len(enrichments)} total"
            + (f", {empty} of them gained nothing" if empty else "")
            + ":"
        )

        def _enrichment_row(r) -> str:
            parts = []
            if r.fields_updated:
                parts.append("fields=" + ",".join(r.fields_updated))
            for c in r.collections:
                bits = f"{c.field_name} +{c.added}"
                extra = []
                if c.already_present:
                    extra.append(f"{c.already_present} already present")
                if c.dropped:
                    extra.append(f"{c.dropped} dropped")
                if extra:
                    bits += " (" + ", ".join(extra) + ")"
                parts.append(bits)
            detail = "; ".join(parts) if parts else "nothing gained"
            return (
                f"    - {r.object_class} \"{r.label}\" "
                f"{_guid8(r.source_guid)} -> {_guid8(r.target_guid)}: {detail}"
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

    # ---- FR-009..FR-013: the fidelity census (T015 hook) -----------------
    for line in _render_census_lines(getattr(report, "census", None)):
        yield line


def _render_census_lines(census) -> Iterable[str]:
    """T015 HOOK -- human-readable side of `RunReport.census`.

    `FidelityCensus` is task T015's type and does not exist yet, so this
    deliberately renders nothing from its internals. `census is None` (the
    only state reachable today) yields no lines at all; a census that IS
    present is announced rather than silently ignored, and asked for its own
    one-line summary if it has one.

    T015: give `FidelityCensus` a `summary_lines()` returning the
    per-object-class rows and replace the placeholder branch below.
    """
    if census is None:
        return
    yield "  Fidelity census:"
    summary_lines = getattr(census, "summary_lines", None)
    if callable(summary_lines):
        for line in summary_lines():
            yield f"    {line}"
        return
    summary_line = getattr(census, "summary_line", None)
    if callable(summary_line):
        yield f"    {summary_line()}"
        return
    yield (
        "    (present; per-object-class detail is in the run-report JSON "
        "artifact)"
    )
