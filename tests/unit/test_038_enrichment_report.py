"""T046 -- the run report tells an ENRICHED item from a CREATED one, and it
honours the certainty clause.

Two contracts are exercised here, both hermetic (no FLEx project is opened):

* **FR-022** -- "The run report MUST distinguish an enriched item from a
  created one."  `EnrichmentRecord.was_created` is False by construction, so
  the distinction exists in the data; these tests are about it existing in the
  OUTPUT -- a labelled row in the console statistics panel and a labelled key
  in the JSON artifact -- and about an enrichment never being folded into the
  created tally.

* **The certainty clause** (plan.md's Principle IV row; research.md R4) -- the
  report may never claim "identical now" on a first transfer, and may claim
  "untouched since last run" only where a residue baseline from an earlier
  GramTrans run exists.  Nothing establishes such a baseline today, so the
  default path must say LESS, and say that it is saying less.

* **SC-010** -- every selected item reaches exactly one of ADD, UPDATE
  (enriched), SKIP, or dropped-with-reason, and each appears in the post-run
  statistics panel.  There is no fifth, unreported outcome.

Sibling file `tests/unit/test_038_enrichment.py` owns the PLANNER side (which
objects become an enrichment); this file owns the REPORTING side only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from gramtrans.Lib import report as report_module
from gramtrans.Lib.models import (
    CategoryReport,
    DroppedItemRecord,
    EnrichedCollection,
    EnrichmentRecord,
    FidelityStatus,
    GrammarCategory,
    PlannedAction,
    PlannedOverwrite,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    Skip,
    SkipReason,
    WSMapping,
)

CAT = GrammarCategory.GRAM_CATEGORIES


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _ctx(**overrides) -> RunContext:
    kwargs = dict(
        source_handle=object(),
        source_project_name="Ejagham Mini",
        source_project_path=r"C:\fake\Ejagham Mini\Ejagham Mini.fwdata",
        target_handle=object(),
        target_project_name="Ejagham Full GT-Test",
        target_project_path=r"C:\fake\Ejagham Full\Ejagham Full.fwdata",
        run_id="GT-20260820-090000",
        started_at="2026-08-20T09:00:00",
    )
    kwargs.update(overrides)
    return RunContext(**kwargs)


def _plan(*, actions=(), skips=(), overwrites=(), enrichments=(),
          context=None) -> RunPlan:
    return RunPlan(
        context=context or _ctx(),
        selection=Selection(categories={CAT: True}),
        ws_mapping=WSMapping(entries=()),
        actions=tuple(actions),
        skips=tuple(skips),
        overwrites=tuple(overwrites),
        enrichments=tuple(enrichments),
    )


def _action(guid: str) -> PlannedAction:
    return PlannedAction(
        category=CAT,
        source_guid=guid,
        intended_target_guid=guid,
        summary=f"add {guid}",
    )


def _dropped(item_guid: str = "child-9") -> DroppedItemRecord:
    return DroppedItemRecord(
        owner_kind="PartOfSpeech",
        owner_guid="pos-2",
        owner_label="Noun",
        field_name="AffixSlotsOC",
        item_name="slot-3",
        item_guid=item_guid,
        reason="target list absent",
    )


def _enrichment(source_guid="pos-2", *, added=2, already_present=1,
                dropped_records=(), fields_updated=()) -> EnrichmentRecord:
    return EnrichmentRecord(
        object_class="PartOfSpeech",
        source_guid=source_guid,
        target_guid=source_guid,
        label="Noun",
        collections=(
            EnrichedCollection(
                field_name="AffixSlotsOC",
                added=added,
                already_present=already_present,
                dropped=len(dropped_records),
                dropped_records=tuple(dropped_records),
            ),
        ),
        fields_updated=tuple(fields_updated),
    )


def _overwrite(record: EnrichmentRecord | None,
               source_guid="pos-2") -> PlannedOverwrite:
    return PlannedOverwrite(
        category=CAT,
        source_guid=source_guid,
        target_guid=source_guid,
        summary=f"merge {source_guid}",
        write_mode="merge" if record is not None else "overwrite",
        enrichment=record,
    )


def _no_delta_skip(guid="pos-3") -> Skip:
    return Skip(
        category=CAT,
        source_guid=guid,
        reason=SkipReason.ALREADY_PRESENT_BY_GUID,
        detail="all seven owned collections compared equal",
    )


def _other_skip(guid="pos-4") -> Skip:
    return Skip(
        category=CAT,
        source_guid=guid,
        reason=SkipReason.UNMAPPED_WS,
        detail="ws 'etu' not mapped",
    )


def _build(plan, **kwargs) -> RunReport:
    return RunReport.build_from_plan(plan, RunMode.MOVE, **kwargs)


def _lines(report) -> list:
    return list(report_module.render_text_summary(report))


def _payload(report) -> dict:
    return json.loads(report.to_snapshot_json())


# A residue baseline has NO producer yet (see `residue_baseline_run_id`'s
# docstring), so the only way to exercise the with-baseline branch is to supply
# the attribute a future producer would. Frozen-dataclass subclasses, so the
# real `RunReport.__post_init__` invariants still run.
@dataclass(frozen=True)
class _ReportWithBaseline(RunReport):
    residue_baseline: object = None


@dataclass(frozen=True)
class _ContextWithPriorRun(RunContext):
    prior_run_id: str = ""


# ---------------------------------------------------------------------------
# FR-022 -- enriched is not created
# ---------------------------------------------------------------------------

def test_an_enrichment_is_never_folded_into_the_created_tally():
    """FR-022. One real create and one enrichment must read as 1 and 1, never
    as 2 creates -- the created tally counts `PlannedAction`s and the enriched
    tally counts `EnrichmentRecord`s, which are disjoint record types."""
    record = _enrichment()
    report = _build(_plan(
        actions=(_action("pos-1"),),
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))

    totals = report_module.disposition_totals(report)
    assert totals["add_created"] == 1
    assert totals["update_enriched"] == 1
    assert report.per_category[CAT].added == 1, (
        "the enriched object must not have inflated the ADD bucket"
    )
    assert report.per_category[CAT].enriched == 1


def test_the_console_panel_gives_created_and_enriched_separate_rows():
    """FR-022 on the surface SC-010 names: the post-run statistics panel."""
    record = _enrichment()
    report = _build(_plan(
        actions=(_action("pos-1"),),
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    lines = _lines(report)

    add_rows = [ln for ln in lines if "- ADD " in ln]
    enriched_rows = [ln for ln in lines if "ENRICHED, add-only" in ln]
    assert len(add_rows) == 1 and add_rows[0].strip().endswith(": 1")
    assert len(enriched_rows) == 1 and enriched_rows[0].strip().endswith(": 1")
    assert any("no enriched object is counted as created" in ln
               for ln in lines), (
        "the panel must STATE the distinction, not leave it to be inferred"
    )


def test_the_artifact_states_was_created_false_and_the_disjoint_sources():
    record = _enrichment()
    report = _build(_plan(
        actions=(_action("pos-1"),),
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    payload = _payload(report)

    assert payload["enrichments"][0]["was_created"] is False
    disposition = payload["disposition"]
    assert disposition["add_created"] == 1
    assert disposition["update_enriched"] == 1
    assert disposition["created_excludes_enriched"] is True
    assert "PlannedAction" in disposition["counted_from"]["add_created"]
    assert "EnrichmentRecord" in disposition["counted_from"]["update_enriched"]


def test_the_per_category_table_shows_enriched_beside_overwritten():
    """An enrichment is carried on a `PlannedOverwrite`, so `overwritten`
    counts it too. The table must say which of the overwrites were add-only
    rather than letting a reader assume all of them clobbered something."""
    record = _enrichment()
    report = _build(_plan(
        overwrites=(_overwrite(record), _overwrite(None, "pos-7")),
        enrichments=(record,),
    ))
    lines = _lines(report)

    cat_row = next(ln for ln in lines if ln.startswith(f"  {CAT.value:18s}"))
    assert "overwritten=2" in cat_row
    assert "enriched=1" in cat_row
    assert any("never counted in added" in ln for ln in lines)


def test_an_enrichment_row_uses_the_r4_wording_not_identical_now():
    """research.md R4: on a first transfer the strongest TRUE line is "the
    target already held this object; N children added, M already present"."""
    record = _enrichment(added=2, already_present=1)
    report = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    row = next(ln for ln in _lines(report)
               if "PartOfSpeech" in ln and "Noun" in ln and "->" in ln)

    assert "the target already held this object" in row
    assert "AffixSlotsOC +2" in row
    assert "1 already present" in row
    assert "identical" not in row.lower()


# ---------------------------------------------------------------------------
# The certainty clause
# ---------------------------------------------------------------------------

def test_a_run_with_no_residue_baseline_reports_none():
    report = _build(_plan(actions=(_action("pos-1"),)))
    assert report_module.residue_baseline_run_id(report) == ""


def test_a_first_transfer_claims_neither_identical_now_nor_untouched():
    """The certainty clause. Both sentences are claims about a prior state of
    the target; with no residue baseline there is no prior state on record, so
    both flags are False and the note says so."""
    record = _enrichment()
    report = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    certainty = _payload(report)["certainty"]

    assert certainty["residue_baseline_run_id"] is None
    assert certainty["is_first_transfer"] is True
    assert certainty["may_claim_identical_now"] is False
    assert certainty["may_claim_untouched_since_last_run"] is False
    assert "does NOT claim the target is identical" in certainty["note"]
    assert certainty["strongest_true_line_for_an_enriched_item"].startswith(
        "the target already held this object"
    )


def test_the_console_prints_the_certainty_note_exactly_once():
    record = _enrichment()
    report = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    lines = _lines(report)

    certainty_lines = [ln for ln in lines if ln.strip().startswith("Certainty:")]
    assert len(certainty_lines) == 1, (
        "one certainty statement per run -- repeating it per row is how two "
        "wordings drift apart"
    )
    assert "FIRST TRANSFER" in certainty_lines[0]


def test_a_residue_baseline_on_the_report_unlocks_the_stronger_wording():
    """"untouched since last run" becomes sayable ONLY here: a baseline from
    an identified earlier run exists, so there is something to be untouched
    since, and the note names which run."""
    record = _enrichment()
    plain = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    report = _ReportWithBaseline(
        context=plain.context,
        mode=plain.mode,
        per_category=plain.per_category,
        skips=plain.skips,
        enrichments=plain.enrichments,
        matched_by_class=plain.matched_by_class,
        matches_unattributed=plain.matches_unattributed,
        residue_baseline="GT-20260101-000000",
    )

    assert report_module.residue_baseline_run_id(report) == "GT-20260101-000000"
    certainty = _payload(report)["certainty"]
    assert certainty["residue_baseline_run_id"] == "GT-20260101-000000"
    assert certainty["is_first_transfer"] is False
    assert certainty["may_claim_untouched_since_last_run"] is True
    assert "untouched since GT-20260101-000000" in certainty["note"]


def test_a_baseline_may_also_arrive_as_a_run_id_on_the_context():
    """The second spelling `residue_baseline_run_id` honours, so whichever a
    future producer picks, the wording upgrades without another edit here."""
    ctx = _ContextWithPriorRun(
        source_handle=object(),
        source_project_name="Ejagham Mini",
        source_project_path=r"C:\fake\a.fwdata",
        target_handle=object(),
        target_project_name="Ejagham Full GT-Test",
        target_project_path=r"C:\fake\b.fwdata",
        run_id="GT-20260820-090000",
        started_at="2026-08-20T09:00:00",
        prior_run_id="GT-20251231-235959",
    )
    report = _build(_plan(actions=(_action("pos-1"),), context=ctx))

    assert (report_module.residue_baseline_run_id(report)
            == "GT-20251231-235959")
    assert "untouched since GT-20251231-235959" in (
        report_module.certainty_note(report)
    )


def test_an_object_carrying_a_baseline_run_id_is_also_accepted():
    """A future producer is as likely to pass a record as a bare string."""

    class _Baseline:
        run_id = "GT-20260202-101010"

    plain = _build(_plan(actions=(_action("pos-1"),)))
    report = _ReportWithBaseline(
        context=plain.context,
        mode=plain.mode,
        per_category=plain.per_category,
        skips=plain.skips,
        residue_baseline=_Baseline(),
    )
    assert report_module.residue_baseline_run_id(report) == "GT-20260202-101010"


# ---------------------------------------------------------------------------
# SC-010 -- four buckets, no fifth outcome
# ---------------------------------------------------------------------------

def test_every_outcome_reaches_the_statistics_panel():
    """SC-010. One of each: a create, an enrichment, a plain overwrite, a
    no-delta skip, a skip for another reason, and a dropped item."""
    record = _enrichment()
    report = _build(
        _plan(
            actions=(_action("pos-1"),),
            overwrites=(_overwrite(record), _overwrite(None, "pos-7")),
            enrichments=(record,),
            skips=(_no_delta_skip(), _other_skip()),
        ),
        extra_dropped_items=(_dropped(),),
    )
    totals = report_module.disposition_totals(report)

    assert totals["add_created"] == 1
    assert totals["update_enriched"] == 1
    assert totals["update_overwritten"] == 2
    assert totals["update_overwritten_not_enriched"] == 1
    assert totals["skip"] == 2
    assert totals["skip_no_delta_after_comparison"] == 1
    assert totals["skip_other_reason"] == 1
    assert totals["dropped_with_reason"] == 1

    lines = _lines(report)
    for marker in ("- ADD ", "ENRICHED, add-only", "overwritten, source wins",
                   "comparison found no delta", "other reason",
                   "- DROPPED "):
        assert any(marker in ln for ln in lines), f"missing panel row: {marker}"


def test_the_panel_names_every_bucket_even_at_zero():
    """A bucket rendered only when non-zero is a bucket a reader cannot tell
    from a bucket that was never measured -- the T037 silence problem. Every
    row prints as long as the run had ANY outcome."""
    report = _build(_plan(actions=(_action("pos-1"),)))
    lines = _lines(report)

    assert any(ln.strip().startswith("- UPDATE   ENRICHED") and
               ln.strip().endswith(": 0") for ln in lines)
    assert any(ln.strip().startswith("- DROPPED") and
               ln.strip().endswith(": 0") for ln in lines)


def test_an_empty_run_renders_no_disposition_panel():
    report = _build(_plan())
    assert not any("Disposition --" in ln for ln in _lines(report))


def test_a_child_an_enrichment_dropped_reaches_the_one_dropped_channel():
    """SC-010 forbids an anonymous drop. `EnrichedCollection.dropped_records`
    are ordinary `DroppedItemRecord`s and must land in the report's single
    dropped channel, not only inside the enrichment detail row."""
    dropped = _dropped()
    record = _enrichment(added=1, already_present=0, dropped_records=(dropped,))
    report = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))

    assert dropped in report.dropped_items
    lines = _lines(report)
    assert any("Dropped references / owned items" in ln for ln in lines)
    assert any("target list absent" in ln for ln in lines)
    assert report_module.disposition_totals(report)["dropped_with_reason"] == 1


def test_a_drop_the_executor_already_reported_is_not_counted_twice():
    """Deduped on the published `(owner_guid, field_name, item_guid)` identity
    -- the same key `categories._dropped_key` uses."""
    dropped = _dropped()
    record = _enrichment(added=1, already_present=0, dropped_records=(dropped,))
    report = _build(
        _plan(overwrites=(_overwrite(record),), enrichments=(record,)),
        extra_dropped_items=(dropped,),
    )
    assert len(report.dropped_items) == 1


def test_a_dropped_child_carries_its_reason_into_the_artifact():
    dropped = _dropped()
    record = _enrichment(added=1, already_present=0, dropped_records=(dropped,))
    report = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    collection = _payload(report)["enrichments"][0]["collections"][0]

    assert collection["dropped"] == 1
    assert collection["dropped_records"][0]["reason"] == "target list absent"


# ---------------------------------------------------------------------------
# Fidelity + the withheld subtraction
# ---------------------------------------------------------------------------

def test_an_enrichment_that_dropped_a_child_reports_as_partial():
    """FR-013's enum, reused rather than re-derived -- the same FULL/PARTIAL
    rule `categories.compute_fidelity_by_guid` applies to a created object."""
    record = _enrichment(added=1, already_present=0,
                         dropped_records=(_dropped(),))
    report = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))

    assert record.fidelity is FidelityStatus.PARTIAL
    totals = report_module.disposition_totals(report)
    assert totals["enriched_partial"] == 1
    assert totals["enriched_full"] == 0
    assert _payload(report)["enrichments"][0]["fidelity"] == "PARTIAL"
    assert any("PARTIAL" in ln for ln in _lines(report))


def test_enriched_child_totals_are_reported():
    record = _enrichment(added=2, already_present=3)
    report = _build(_plan(
        overwrites=(_overwrite(record),),
        enrichments=(record,),
    ))
    totals = report_module.disposition_totals(report)

    assert totals["enriched_children_added"] == 2
    assert totals["enriched_children_already_present"] == 3
    assert any("2 added, 3 already present in the target" in ln
               for ln in _lines(report))


def test_an_unreconcilable_overwrite_split_is_withheld_not_guessed():
    """The T039 lesson. An enrichment is carried ON a `PlannedOverwrite`, so
    more enrichments than overwrites means the source-wins remainder has no
    subtraction basis. Report nothing rather than a negative number."""
    record = _enrichment()
    report = RunReport(
        context=_ctx(),
        mode=RunMode.MOVE,
        per_category={CAT: CategoryReport(enriched=1)},
        enrichments=(record,),
    )
    totals = report_module.disposition_totals(report)

    assert totals["overwrite_split_reconciles"] is False
    assert totals["update_overwritten_not_enriched"] is None
    assert any("WITHHELD" in ln for ln in _lines(report))
    assert _payload(report)["disposition"][
        "update_overwritten_not_enriched"] is None


# ---------------------------------------------------------------------------
# Cross-surface + housekeeping
# ---------------------------------------------------------------------------

def test_console_and_artifact_report_the_same_numbers():
    record = _enrichment()
    report = _build(_plan(
        actions=(_action("pos-1"),),
        overwrites=(_overwrite(record),),
        enrichments=(record,),
        skips=(_no_delta_skip(),),
    ))
    disposition = _payload(report)["disposition"]

    for key in ("add_created", "update_enriched", "update_overwritten",
                "skip", "dropped_with_reason"):
        assert disposition[key] == report_module.disposition_totals(report)[key]


def test_a_report_with_no_038_data_gains_no_new_artifact_keys():
    """The module's snapshot-compatibility promise: a run carrying no 038 data
    must produce the same keys it did before 038 landed."""
    payload = _payload(_build(_plan(
        actions=(_action("pos-1"),),
        skips=(_other_skip(),),
    )))

    assert "disposition" not in payload
    assert "certainty" not in payload


def test_every_rendered_line_is_plain_ascii():
    record = _enrichment(added=1, already_present=1,
                         dropped_records=(_dropped(),),
                         fields_updated=("Description",))
    report = _build(_plan(
        actions=(_action("pos-1"),),
        overwrites=(_overwrite(record),),
        enrichments=(record,),
        skips=(_no_delta_skip(), _other_skip()),
    ))
    for line in _lines(report):
        line.encode("ascii")  # raises on any non-ASCII glyph


@pytest.mark.parametrize("reason", [
    SkipReason.ALREADY_PRESENT_BY_GUID,
    SkipReason.ALREADY_PRESENT_BY_IDENTITY,
])
def test_only_a_comparison_backed_skip_counts_as_no_delta(reason):
    report = _build(_plan(skips=(
        Skip(category=CAT, source_guid="pos-3", reason=reason,
             detail="compared equal"),
        _other_skip(),
    )))
    totals = report_module.disposition_totals(report)

    assert totals["skip_no_delta_after_comparison"] == 1
    assert totals["skip_other_reason"] == 1
