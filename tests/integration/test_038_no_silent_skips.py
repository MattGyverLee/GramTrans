"""T080 -- the SC-010 audit, end to end.

SC-010: *no transfer reports success while having silently discarded, or
silently altered the kind of, any object.* data-model.md:232-235 states the
mechanism: every selected item reaches exactly one of **ADD**, **UPDATE
(enriched)**, **SKIP**, or **dropped-with-reason**, each appears in the
post-run statistics panel, and *there is no fifth, unreported outcome*.

Three things have to be true for that to be a CHECKABLE claim rather than a
sentence in a spec, and this file checks each of them:

  1. the bucket vocabulary is CLOSED -- every counter and every record tuple
     the report carries is classified, so a new one cannot appear
     unclassified (`TestTheBucketVocabularyIsClosed`);
  2. every bucket REACHES THE PANEL, zero or not, on both surfaces
     (`TestEachBucketReachesBothSurfaces`);
  3. every bucket is ACCOUNTED FOR by the extended
     `RunReport.__post_init__` invariant (`TestTheInvariantCoversAllFour`).

WHAT THE AUDIT FOUND, and it is not what the task line assumed. The task says
"assert the extended `RunReport.__post_init__` accounting invariant covers all
four buckets". Measured before T080 touched anything, it covered **two**:

    bucket              counter                  records tuple      invariant
    ------------------  -----------------------  -----------------  ---------
    ADD                 per_category[*].added    (none on report)   NONE
    UPDATE (enriched)   per_category[*].enriched enrichments        equality
    SKIP                per_category[*].skipped  skips              equality
    dropped-with-reason (none)                   dropped_items      NONE

The two covered buckets are covered because each counter has a records tuple
ON THE REPORT that is its single source of truth. The two uncovered ones are
uncovered for opposite structural reasons, and neither can be fixed by copying
the equality check across:

  * **ADD has a counter and no records.** `added` is one per `PlannedAction`,
    and the plan is not carried on the RunReport, so there is nothing to
    reconcile against. `CategoryReport(added=-5)` constructed a report that
    rendered a disposition panel reading `-5`.
  * **dropped-with-reason has records and no counter.** It is
    `len(dropped_items)` and nothing else. `DroppedItemRecord.__post_init__`
    refuses an empty `reason`, but that guards the RECORD's construction, not
    the TUPLE's membership -- a stand-in carrying `reason=""` went in, was
    counted as a reported drop, and rendered a line ending in a bare "- ".

T080 gives each of them the invariant its shape actually admits: a RANGE check
for ADD (`CATEGORY_REPORT_COUNTERS`, non-negative), and a MEMBERSHIP check for
dropped-with-reason (every entry carries a reason, checked where the bucket is
counted). Both are in `RunReport.__post_init__` and both are asserted below.

AND THE FIFTH OUTCOME WAS REAL, in its exact literal form.
`ProcessRuleTransferRecord`'s docstring states a HARD INVARIANT -- a rule with
`reproduced=False` "is reported -- via a `DroppedItemRecord` plus
`Skip(NOT_REPRODUCIBLE)` -- and SKIPPED". Its own `__post_init__` enforces the
half it can see (the reason must be non-empty) and NOTHING enforced the other
half. A report carrying a rule the engine knew it had not rebuilt, named by no
Skip and no dropped record, is an item that reached none of the four buckets --
and it constructed silently, rendered a clean panel, and produced an artifact
whose `disposition.note` said "there is no fifth, unreported outcome" as an
unconditional promise.

That is now `RunReport.unreported_not_reproduced`, a PROPERTY and deliberately
not a raise: raising at build time would destroy the report that carries the
evidence of the loss, which is the SC-010 anti-pattern in miniature. T048c set
the precedent in the same direction -- when the create split had no valid basis
it withheld the number and said so rather than refusing to build. The artifact
note now points at the measured key instead of making the promise itself.

WHY THIS FILE IS AN INTEGRATION TEST with no live project. It is an audit of
the CONTRACT BETWEEN THREE MODULES -- `Lib/models.py`'s invariants,
`Lib/report.py`'s `disposition_totals`, and the console panel -- and its whole
point is that the three agree. A unit test of any one of them is what allowed
the gaps above to sit open while every module's own suite passed.
"""
from __future__ import annotations

import dataclasses as dc
import json

import pytest

from gramtrans.Lib import report as report_module
from gramtrans.Lib.models import (
    CATEGORY_REPORT_COUNTERS,
    CategoryReport,
    DroppedItemRecord,
    EnrichedCollection,
    EnrichmentRecord,
    GrammarCategory,
    LeafExecutionFailure,
    PlannedAction,
    PlannedOverwrite,
    ProcessRuleTransferRecord,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    Skip,
    SkipReason,
    WSMapping,
)

pytestmark = pytest.mark.integration

CAT = GrammarCategory.GRAM_CATEGORIES


# ---------------------------------------------------------------------------
# The classification tables -- this file's substance, not its scaffolding
# ---------------------------------------------------------------------------
#
# Every field is named exactly once with the role it plays in SC-010's
# accounting. `BUCKET_*` are the four outcomes themselves. Everything else is
# something a reader might MISTAKE for a fifth outcome, which is why each is
# listed with the reason it is not one rather than merely omitted.

BUCKET_ADD = "bucket:add"
BUCKET_UPDATE = "bucket:update"
BUCKET_SKIP = "bucket:skip"
BUCKET_DROPPED = "bucket:dropped-with-reason"
#: Rides ON one of the four -- refines an outcome, never replaces it.
ANNOTATION = "annotation"
#: Describes how an item ENTERED the run, not what became of it.
PROVENANCE = "provenance"
#: Not a selected item at all (writing systems, empty categories, metadata).
NOT_AN_ITEM = "not-an-item"
#: The per-category counter block itself.
COUNTERS = "counters"

#: Every counter `CategoryReport` carries.
CATEGORY_FIELD_ROLES = {
    "added": BUCKET_ADD,
    "skipped": BUCKET_SKIP,
    "overwritten": BUCKET_UPDATE,
    "enriched": BUCKET_UPDATE,
    # A pulled-in item is one the closure ADDED TO THE RUN; it then reaches one
    # of the four like any seed. Counting it as an outcome would double-count.
    "closure_pulled_in": PROVENANCE,
    # How a conflict was decided, not what was decided -- the item is in
    # `overwritten` or `skipped` either way.
    "interactive_resolved": ANNOTATION,
    # A strict subset of `skipped`, kept separate so a user-chosen skip is
    # distinguishable from an engine-chosen one.
    "interactive_skipped": ANNOTATION,
    # A strict subset of `skipped` too -- one per Skip(NOT_REPRODUCIBLE), which
    # `RunReport.__post_init__` already reconciles.
    "not_reproducible": ANNOTATION,
    # A MATCH BASIS, not a disposition: the object was matched by natural key
    # rather than by GUID and then went on to UPDATE or SKIP (FR-006/FR-187).
    "identity_substitution": ANNOTATION,
    # The ENTRY still transfers -- with a null reference, and a warning. The
    # thing omitted is a DESELECTED DEPENDENCY, which was never a selected
    # item, so this is not an item losing its outcome (see `ExcludedLossy`).
    "excluded_lossy": ANNOTATION,
    "ws_mapped": NOT_AN_ITEM,
    "ws_created": NOT_AN_ITEM,
    "ws_skipped": NOT_AN_ITEM,
}

#: Every field `RunReport` carries.
REPORT_FIELD_ROLES = {
    "context": NOT_AN_ITEM,
    "mode": NOT_AN_ITEM,
    "wall_clock_seconds": NOT_AN_ITEM,
    # Selected, scanned, and empty in the SOURCE -- there was no item.
    "empty_categories": NOT_AN_ITEM,
    "per_category": COUNTERS,
    "skips": BUCKET_SKIP,
    "enrichments": BUCKET_UPDATE,
    "dropped_items": BUCKET_DROPPED,
    # A create that LCM refused the source GUID for: still an ADD, under a new
    # identity, which is what the remap records.
    "identity_remap": ANNOTATION,
    "excluded_lossy": ANNOTATION,
    # FULL/PARTIAL per object, DERIVED from `dropped_items` -- a second view of
    # the dropped bucket, never a second source for it.
    "fidelity_by_guid": ANNOTATION,
    # T048c: an ADD that was planned and did not reach the database. It refines
    # the ADD bucket's outcome (`add_created_written`); it does not sit outside
    # the four.
    "leaf_execution_failures": ANNOTATION,
    "closure_edges": PROVENANCE,
    # The item ADDED, knowingly incomplete, and said so -- an outcome with a
    # caveat, not a fifth outcome.
    "incompleteness": ANNOTATION,
    # THE ONE THAT NEEDED WORK. `reproduced=True` is an ADD; `reproduced=False`
    # must be named by a Skip or a dropped record, and until T080 nothing
    # checked that it was. See `TestTheFifthOutcomeWasReal`.
    "process_rules": ANNOTATION,
    "affix_slot_links": ANNOTATION,
    "census": NOT_AN_ITEM,
    "matched_by_class": NOT_AN_ITEM,
    "matches_unattributed": NOT_AN_ITEM,
}

#: The four, by the key each is counted under in `disposition_totals`.
FOUR_BUCKET_KEYS = (
    "add_created",
    "update_enriched",
    "skip",
    "dropped_with_reason",
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _ctx() -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Ejagham W Mini",
        source_project_path=r"C:\fake\Ejagham W Mini\Ejagham W Mini.fwdata",
        target_handle=object(),
        target_project_name="GT038 T080 Target",
        target_project_path=r"C:\fake\Target\Target.fwdata",
        run_id="GT-20260825-080000",
        started_at="2026-08-25T08:00:00",
    )


def _action(guid: str = "pos-1") -> PlannedAction:
    return PlannedAction(
        category=CAT, source_guid=guid, intended_target_guid=guid,
        summary=f"add {guid}",
    )


def _enrichment(source_guid: str = "pos-2") -> EnrichmentRecord:
    return EnrichmentRecord(
        object_class="PartOfSpeech",
        source_guid=source_guid,
        target_guid=source_guid,
        label="Noun",
        collections=(EnrichedCollection(
            field_name="AffixSlotsOC", added=2, already_present=1,
        ),),
    )


def _overwrite(record: EnrichmentRecord) -> PlannedOverwrite:
    return PlannedOverwrite(
        category=CAT,
        source_guid=record.source_guid,
        target_guid=record.target_guid,
        summary="enrich " + record.source_guid,
        write_mode="merge",
        enrichment=record,
    )


def _skip(guid: str = "pos-3") -> Skip:
    return Skip(
        category=CAT, source_guid=guid,
        reason=SkipReason.ALREADY_PRESENT_BY_GUID,
        detail="all seven owned collections compared equal",
    )


def _dropped(item_guid: str = "child-9",
             owner_guid: str = "entry-4") -> DroppedItemRecord:
    return DroppedItemRecord(
        owner_kind="LexEntry", owner_guid=owner_guid, owner_label="-PL",
        field_name="AlternateFormsOS", item_name="MoAffixProcess",
        item_guid=item_guid, reason="target list absent",
    )


def _plan(*, actions=(), skips=(), overwrites=(), enrichments=()) -> RunPlan:
    return RunPlan(
        context=_ctx(),
        selection=Selection(categories={CAT: True}),
        ws_mapping=WSMapping(entries=()),
        actions=tuple(actions), skips=tuple(skips),
        overwrites=tuple(overwrites), enrichments=tuple(enrichments),
    )


def _all_four_buckets() -> RunReport:
    """A report with every one of the four buckets NON-EMPTY.

    The panel must name all four even when a bucket is zero, but a test that
    only ever sees zeros cannot tell "named" from "hard-coded", so the fixture
    the surfaces are checked against carries a real item in each.
    """
    record = _enrichment()
    return RunReport.build_from_plan(
        _plan(actions=(_action(),), skips=(_skip(),),
              overwrites=(_overwrite(record),), enrichments=(record,)),
        RunMode.MOVE,
        extra_dropped_items=(_dropped(),),
    )


def _lines(report) -> list:
    return list(report_module.render_text_summary(report))


def _payload(report) -> dict:
    return json.loads(report.to_snapshot_json())


def _report(**kwargs) -> RunReport:
    return RunReport(context=_ctx(), mode=RunMode.MOVE, **kwargs)


# ---------------------------------------------------------------------------
# 1. The vocabulary is closed
# ---------------------------------------------------------------------------

class TestTheBucketVocabularyIsClosed:
    """"There is no fifth outcome" is only checkable if the set of things that
    COULD be one is enumerated. These tests fail when a new counter or a new
    record tuple is added without being classified -- which is the moment a
    fifth outcome would enter, and the only moment at which catching it is
    cheap."""

    def test_every_category_counter_is_classified(self):
        declared = {f.name for f in dc.fields(CategoryReport)}
        assert declared == set(CATEGORY_FIELD_ROLES), (
            "a CategoryReport counter is unclassified (or the table names one "
            "that no longer exists): "
            f"{declared ^ set(CATEGORY_FIELD_ROLES)}"
        )

    def test_every_report_field_is_classified(self):
        declared = {f.name for f in dc.fields(RunReport)}
        assert declared == set(REPORT_FIELD_ROLES), (
            "a RunReport field is unclassified (or the table names one that "
            "no longer exists): "
            f"{declared ^ set(REPORT_FIELD_ROLES)}"
        )

    def test_the_engine_ranges_over_every_counter_it_declares(self):
        """`CATEGORY_REPORT_COUNTERS` is what `__post_init__` range-checks. A
        counter missing from it is a bucket nothing bounds, so the tuple is
        pinned to the dataclass rather than maintained beside it."""
        int_fields = {
            f.name for f in dc.fields(CategoryReport)
            if f.type in ("int", int)
        }
        assert int_fields == set(CATEGORY_REPORT_COUNTERS)
        assert len(CATEGORY_REPORT_COUNTERS) == len(
            set(CATEGORY_REPORT_COUNTERS))

    def test_each_of_the_four_buckets_is_claimed_by_something(self):
        roles = set(CATEGORY_FIELD_ROLES.values()) | set(
            REPORT_FIELD_ROLES.values())
        for bucket in (BUCKET_ADD, BUCKET_UPDATE, BUCKET_SKIP, BUCKET_DROPPED):
            assert bucket in roles, f"{bucket} is claimed by no field"

    def test_the_dropped_bucket_is_the_one_with_no_counter(self):
        """Stated as a test because it is the asymmetry that made the missing
        invariant hard to see: three buckets have a counter to reconcile and
        this one is `len(dropped_items)` outright."""
        assert BUCKET_DROPPED not in set(CATEGORY_FIELD_ROLES.values())
        assert BUCKET_DROPPED in set(REPORT_FIELD_ROLES.values())


# ---------------------------------------------------------------------------
# 2. Each bucket reaches BOTH surfaces
# ---------------------------------------------------------------------------

class TestEachBucketReachesBothSurfaces:
    """SC-010's second clause: "each appears in the post-run statistics
    panel". Checked on the console AND on the JSON artifact, because a bucket
    present on one and absent from the other is exactly a silent outcome for
    whoever reads the other one."""

    def test_the_console_panel_names_all_four(self):
        panel = [ln for ln in _lines(_all_four_buckets())
                 if ln.lstrip().startswith("- ")]
        assert any("ADD" in ln and "created in target" in ln for ln in panel)
        assert any("UPDATE" in ln and "ENRICHED" in ln for ln in panel)
        assert any("SKIP" in ln for ln in panel)
        assert any("DROPPED" in ln and "reported with a reason" in ln
                   for ln in panel)

    def test_the_console_panel_names_all_four_even_at_zero(self):
        """A bucket that disappears when empty is a bucket a reader cannot
        tell from a bucket that was never checked."""
        report = RunReport.build_from_plan(
            _plan(actions=(_action(),)), RunMode.MOVE,
            extra_dropped_items=(),
            extra_process_rules=(ProcessRuleTransferRecord(
                source_guid="rule-ok", reproduced=True,
                target_guid="rule-ok"),),
        )
        panel = [ln for ln in _lines(report) if ln.lstrip().startswith("- ")]

        assert any("ENRICHED" in ln and ln.rstrip().endswith("0")
                   for ln in panel)
        assert any("DROPPED" in ln and ln.rstrip().endswith("0")
                   for ln in panel)

    def test_the_artifact_carries_all_four(self):
        disposition = _payload(_all_four_buckets())["disposition"]
        for key in FOUR_BUCKET_KEYS:
            assert key in disposition, f"{key} missing from the artifact"
            assert disposition[key] >= 1, (
                f"{key} should be non-empty in this fixture"
            )

    def test_both_surfaces_are_derived_from_one_call(self):
        """The console and the artifact must not be able to disagree. Both
        read `disposition_totals`; this asserts the artifact's numbers ARE
        that call's numbers, key for key."""
        report = _all_four_buckets()
        totals = report_module.disposition_totals(report)
        disposition = _payload(report)["disposition"]
        for key, value in totals.items():
            assert disposition[key] == value, key

    def test_every_bucket_names_the_record_it_is_answerable_to(self):
        counted_from = _payload(_all_four_buckets())["disposition"][
            "counted_from"]
        for key in FOUR_BUCKET_KEYS:
            assert counted_from.get(key), (
                f"{key} does not name the record type it is counted from, so "
                "a reader cannot check it"
            )


# ---------------------------------------------------------------------------
# 3. The invariant covers all four
# ---------------------------------------------------------------------------

class TestTheInvariantCoversAllFour:
    """One test per bucket, each naming the SHAPE of invariant that bucket's
    structure admits. The two equality checks predate T080; the range check
    and the membership check are what it added."""

    def test_skip_reconciles_counter_against_records(self):
        with pytest.raises(ValueError, match="FR-018"):
            _report(per_category={CAT: CategoryReport(skipped=1)})

    def test_update_reconciles_counter_against_records(self):
        with pytest.raises(ValueError, match="enriched"):
            _report(per_category={CAT: CategoryReport(enriched=1)})

    def test_skip_not_reproducible_reconciles_against_its_skip_reason(self):
        with pytest.raises(ValueError, match="not_reproducible"):
            _report(
                per_category={CAT: CategoryReport(skipped=1,
                                                  not_reproducible=1)},
                skips=(_skip(),),
            )

    def test_add_is_range_checked_because_it_has_no_records_to_count(self):
        """The ADD bucket's counter has no records tuple on the report, so
        equality is unavailable and the range is what remains. Before T080
        this constructed, and the panel rendered "-5 created"."""
        with pytest.raises(ValueError, match="non-negative int"):
            _report(per_category={CAT: CategoryReport(added=-5)})

    def test_a_negative_counter_hides_inside_a_reconciling_sum(self):
        """Why the range check is needed even on the buckets that DO
        reconcile: the equality checks constrain the SUM, and a sum of -3 and
        4 is 1."""
        with pytest.raises(ValueError, match="non-negative int"):
            _report(
                per_category={
                    CAT: CategoryReport(skipped=-3),
                    GrammarCategory.POS: CategoryReport(skipped=4),
                },
                skips=(_skip(),),
            )

    def test_every_declared_counter_is_actually_range_checked(self):
        """Ranges over `CATEGORY_REPORT_COUNTERS` rather than spot-checking
        one, so a counter added to the tuple but not reached by the loop
        fails here."""
        for name in CATEGORY_REPORT_COUNTERS:
            with pytest.raises(ValueError, match="non-negative int"):
                _report(per_category={CAT: CategoryReport(**{name: -1})})

    def test_the_range_check_runs_BEFORE_the_equality_checks(self):
        """Order is load-bearing, not incidental. `skipped=-1` and
        `enriched=-1` each trip their equality check too, and that check would
        report `sum(...)=-1 != len(...)=0` -- arithmetic over a nonsense value,
        naming the tuple rather than the counter that is actually wrong. The
        range check is the more fundamental fact, so it speaks first."""
        for name in ("skipped", "enriched"):
            with pytest.raises(ValueError, match="non-negative int"):
                _report(per_category={CAT: CategoryReport(**{name: -1})})

    def test_dropped_is_membership_checked_because_it_has_no_counter(self):
        """The dropped bucket is `len(dropped_items)` and nothing else, so the
        only thing to check is what is IN the tuple. `DroppedItemRecord`
        refuses an empty reason at construction; this field is a plain tuple
        and accepted a stand-in that did not."""
        reasonless = type("_Stub", (), {
            "reason": "", "owner_guid": "o", "item_guid": "i",
            "owner_kind": "LexEntry", "owner_label": "x",
            "field_name": "AlternateFormsOS", "item_name": "y",
        })()
        with pytest.raises(ValueError, match="dropped-WITH-REASON"):
            _report(dropped_items=(reasonless,))

    def test_a_real_dropped_record_still_passes(self):
        assert _report(dropped_items=(_dropped(),)).dropped_items

    def test_a_clean_report_of_all_four_buckets_constructs(self):
        """The invariants must reject the failures above and NOTHING else --
        one that also rejects correct reports is not an invariant, it is an
        outage."""
        totals = report_module.disposition_totals(_all_four_buckets())
        assert all(totals[k] >= 1 for k in FOUR_BUCKET_KEYS)


# ---------------------------------------------------------------------------
# 4. The fifth outcome
# ---------------------------------------------------------------------------

class TestTheFifthOutcomeWasReal:
    """A `ProcessRuleTransferRecord(reproduced=False)` named by no Skip and no
    dropped record is an item that reached none of the four buckets. It is the
    fifth, unreported outcome in the literal form SC-010 names -- and it
    constructed silently until T080."""

    def _rule(self, guid="rule-1"):
        return ProcessRuleTransferRecord(
            source_guid=guid, reproduced=False,
            not_reproducible_reason=(
                "PhSequenceContext members name shared PhPhonData.ContextsOS "
                "contexts the destination lacks"
            ),
        )

    def test_an_unreported_non_reproduction_is_detected(self):
        assert _report(
            process_rules=(self._rule(),)
        ).unreported_not_reproduced == ("rule-1",)

    def test_a_rule_reported_as_a_dropped_item_is_not_a_fifth_outcome(self):
        """The shape both producers in `Lib/categories.py` actually emit: the
        rule is reported AGAINST ITS OWNING ENTRY, with the rule's GUID as
        `item_guid` (create-path contract section 5)."""
        report = _report(
            dropped_items=(_dropped(item_guid="rule-1",
                                    owner_guid="entry-4"),),
            process_rules=(self._rule(),),
        )
        assert report.unreported_not_reproduced == ()

    def test_a_rule_reported_as_a_skip_is_not_a_fifth_outcome(self):
        report = _report(
            per_category={CAT: CategoryReport(skipped=1, not_reproducible=1)},
            skips=(Skip(category=CAT, source_guid="rule-1",
                        reason=SkipReason.NOT_REPRODUCIBLE,
                        detail="graph unresolvable"),),
            process_rules=(self._rule(),),
        )
        assert report.unreported_not_reproduced == ()

    def test_a_rule_reported_against_itself_as_owner_counts_too(self):
        """A rule that OWNS the thing lost is reported with itself as
        `owner_kind="MoAffixProcess"` / `owner_guid=<rule>`, so insisting on
        `item_guid` alone would fail on correctly reported runs."""
        report = _report(
            dropped_items=(DroppedItemRecord(
                owner_kind="MoAffixProcess", owner_guid="rule-1",
                owner_label="rule", field_name="InputOS",
                item_name="PhSequenceContext", item_guid="ctx-7",
                reason="member context absent in destination",
            ),),
            process_rules=(self._rule(),),
        )
        assert report.unreported_not_reproduced == ()

    def test_a_reproduced_rule_is_never_a_fifth_outcome(self):
        report = _report(process_rules=(ProcessRuleTransferRecord(
            source_guid="rule-2", reproduced=True, target_guid="rule-2"),))
        assert report.unreported_not_reproduced == ()

    def test_guid_matching_is_case_insensitive(self):
        """LCM hands GUIDs back in mixed case; a check that missed on case
        would report phantom fifth outcomes on every real run."""
        report = _report(
            dropped_items=(_dropped(item_guid="RULE-1"),),
            process_rules=(self._rule(guid="rule-1"),),
        )
        assert report.unreported_not_reproduced == ()

    def test_the_check_reaches_the_console_in_both_directions(self):
        clean = [ln for ln in _lines(_all_four_buckets())
                 if "Fifth-outcome check" in ln]
        assert clean and "PASS" in clean[0]

        lossy_report = RunReport.build_from_plan(
            _plan(actions=(_action(),)), RunMode.MOVE,
            extra_process_rules=(self._rule(),),
        )
        lossy_lines = _lines(lossy_report)
        lossy = [ln for ln in lossy_lines if "Fifth-outcome check" in ln]
        assert lossy and "[FAIL]" in lossy[0]
        assert any(ln.strip() == "- rule-1" for ln in lossy_lines)

    def test_the_check_reaches_the_artifact(self):
        disposition = _payload(_all_four_buckets())["disposition"]
        assert disposition["no_fifth_outcome"] is True
        assert disposition["unreported_not_reproduced"] == 0
        assert disposition["unreported_not_reproduced_guids"] == []

    def test_the_artifact_note_no_longer_makes_the_promise_itself(self):
        """The note used to assert "there is no fifth, unreported outcome"
        unconditionally, which would have been false on the report below. It
        now points at the key that measures it."""
        note = _payload(_all_four_buckets())["disposition"]["note"]
        assert "no_fifth_outcome" in note

    def test_it_is_a_property_not_a_build_time_refusal(self):
        """Pinned deliberately. Raising here would destroy the report that
        carries the evidence of the loss -- the SC-010 anti-pattern in
        miniature. A later task that "fixes" this into a raise fails here and
        gets told why."""
        report = RunReport.build_from_plan(
            _plan(actions=(_action(),)), RunMode.MOVE,
            extra_process_rules=(self._rule(),),
        )
        assert report.unreported_not_reproduced == ("rule-1",)
        assert _payload(report)["disposition"]["no_fifth_outcome"] is False


# ---------------------------------------------------------------------------
# 5. The deliberate NON-invariants
# ---------------------------------------------------------------------------

class TestTheDeliberateNonInvariants:
    """Things the audit found that LOOK like missing invariants and are not.
    Each is pinned so a later reading of this audit does not "complete" it by
    adding a raise that a real, correct run would trip."""

    def test_more_write_failures_than_planned_creates_still_constructs(self):
        """T048c's withhold path. `add_write_failed > add_created` means the
        two tallies disagree and the written remainder has no basis -- so the
        NUMBER is withheld and the report is still built. Turning it into a
        raise would make the disagreement unreportable."""
        report = RunReport.build_from_plan(
            _plan(actions=(_action(),)), RunMode.MOVE,
            extra_leaf_execution_failures=tuple(
                LeafExecutionFailure(
                    category=CAT, source_guid=f"pos-{i}",
                    exception_type="RuntimeError", message="boom",
                )
                for i in range(3)
            ),
        )
        totals = report_module.disposition_totals(report)
        assert totals["create_split_reconciles"] is False
        assert totals["add_created_written"] is None
        assert any("WITHHELD" in ln for ln in _lines(report))

    def test_the_buckets_are_never_summed_into_a_grand_total(self):
        """A dropped child is reported AGAINST its owner, not INSTEAD of it,
        so the four count different granularities. A grand total would be a
        fiction, and its absence is a design decision, not an omission."""
        disposition = _payload(_all_four_buckets())["disposition"]
        assert "total" not in disposition
        assert not any(k.endswith("_total") for k in disposition)

    def test_an_empty_run_renders_no_panel_at_all(self):
        """`_has_reportable_outcome` keeps the panel off a report with nothing
        in any bucket. That is not a hidden outcome -- there is no item."""
        report = RunReport.build_from_plan(_plan(), RunMode.PREVIEW)
        assert not any("Disposition" in ln for ln in _lines(report))

    def test_a_pre_038_report_gains_no_artifact_keys(self):
        """The snapshot-compatibility promise, re-asserted from this file
        because T080 added keys to the disposition block: a run with no 038
        data must still carry no `disposition` at all."""
        payload = _payload(RunReport.build_from_plan(
            _plan(actions=(_action(),)), RunMode.MOVE))
        assert "disposition" not in payload
