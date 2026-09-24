"""T048c: three writes failed and the report said nothing.

Measured on run `CENSUS-20260820-094825`
(`specs/038-transfer-fidelity-gaps/journal/T038-T048-live-gate-rerun.md`): the
executor logged `leaf-dispatch counts attempted=329 succeeded=326 failed=3`,
`disposition.add_created` read 329, and the artifact carried no failure surface
at all -- so every reader doing `.get("leaf_execution_failures")` saw `None` and
could not tell "three writes failed" from "this build does not report write
failures". A real loss going unreported is the Principle I shape.

Feature 037 had already built the record (`LeafExecutionFailure`), carried it
onto `RunReport`, and rendered it in `render_text_summary`. The gap was the
ARTIFACT -- the one surface that survives after the console scrolls away, and
the one the census reads.

Two things are deliberately NOT done, and each has a test:

  * `add_created` IS NOT SILENTLY REDUCED. It is counted from
    `per_category[*].added`, one per `PlannedAction`, and is the honest answer
    to "how many creates were planned". The write outcome gets its own keys.
  * A REMAINDER WITH NO BASIS IS NOT GUESSED. More failures than planned
    creates means the counters disagree, so `add_created_written` yields None
    and `create_split_reconciles` is False -- the `update_overwritten_not_
    enriched` precedent, and T039's lesson.
"""

from __future__ import annotations

import json

import gramtrans.Lib.report as report_mod  # noqa: F401 -- attaches build_from_plan
from gramtrans.Lib.models import (
    GrammarCategory,
    LeafExecutionFailure,
    PlannedAction,
    PlannedOverwrite,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
)


def _ctx():
    return RunContext(
        source_handle=object(),
        source_project_name="Ejagham Mini",
        source_project_path=r"C:\p\Src",
        target_handle=object(),
        target_project_name="GT038 Phase5 Target",
        target_project_path=r"C:\p\Tgt",
        run_id="GT-20260820-094825",
        started_at="2026-08-20T09:46:07",
    )


def _actions(n, category=GrammarCategory.GRAM_CATEGORIES):
    return tuple(
        PlannedAction(
            category=category,
            source_guid="src-%d" % i,
            intended_target_guid="tgt-%d" % i,
            summary="planned create %d" % i,
        )
        for i in range(n)
    )


def _failures(n, category=GrammarCategory.GRAM_CATEGORIES):
    return tuple(
        LeafExecutionFailure(
            category=category,
            source_guid="src-%d" % i,
            exception_type="RuntimeError",
            message="write refused for src-%d" % i,
        )
        for i in range(n)
    )


def _substitution():
    """One `PlannedOverwrite` matched by NAME -- the cheapest way to make a
    report carry feature-038 data without inventing a Phase-6 record type."""
    return PlannedOverwrite(
        category=GrammarCategory.GRAM_CATEGORIES,
        source_guid="sub-1",
        target_guid="sub-1",
        summary="matched by name",
        match_via="natural_key",
        write_mode="merge",
    )


def _report(planned=0, failed=0, overwrites=()):
    plan = RunPlan(
        context=_ctx(),
        selection=None,
        ws_mapping=None,
        actions=_actions(planned),
        skips=(),
        overwrites=tuple(overwrites),
    )
    return RunReport.build_from_plan(
        plan, RunMode.MOVE,
        extra_leaf_execution_failures=_failures(failed),
    )


class TestTheDispositionSplitsPlannedFromWritten:

    def test_the_measured_run(self):
        """329 planned, 3 swallowed, 326 written -- the numbers the executor
        logged and the report did not carry."""
        d = report_mod.disposition_totals(_report(planned=329, failed=3))

        assert d["add_created"] == 329, "the PLAN's number, unchanged"
        assert d["add_write_failed"] == 3
        assert d["add_created_written"] == 326
        assert d["create_split_reconciles"] is True

    def test_a_clean_run_reports_a_measured_zero(self):
        """The zero needs a home. `disposition` is emitted whenever the run has
        any reportable outcome, so a clean run says `add_write_failed: 0`
        rather than saying nothing and leaving a reader to guess."""
        d = report_mod.disposition_totals(_report(planned=12, failed=0))

        assert d["add_write_failed"] == 0
        assert d["add_created_written"] == 12
        assert d["create_split_reconciles"] is True

    def test_add_created_is_never_silently_reduced(self):
        """It is counted from the PLAN and three invariants hang on it. The
        outcome is reported beside it, not folded into it."""
        clean = report_mod.disposition_totals(_report(planned=100, failed=0))
        lossy = report_mod.disposition_totals(_report(planned=100, failed=40))

        assert clean["add_created"] == lossy["add_created"] == 100
        assert lossy["add_created_written"] == 60

    def test_a_remainder_with_no_basis_is_withheld_not_guessed(self):
        """More failures than planned creates means the two counters disagree,
        and a number whose basis does not support it is worse than no
        number (T039)."""
        d = report_mod.disposition_totals(_report(planned=2, failed=5))

        assert d["create_split_reconciles"] is False
        assert d["add_created_written"] is None
        assert d["add_write_failed"] == 5

    def test_the_count_comes_from_the_records_not_a_counter(self):
        report = _report(planned=10, failed=4)
        d = report_mod.disposition_totals(report)

        assert d["add_write_failed"] == report.leaf_failed == 4
        assert len(report.leaf_execution_failures) == 4


class TestTheArtifactSaysSo:

    def test_the_failures_reach_the_snapshot_in_full(self):
        """NOT truncated. A swallowed write failure is the least truncatable
        record this report holds."""
        payload = json.loads(_report(planned=329, failed=3).to_snapshot_json())

        assert "leaf_execution_failures" in payload
        assert len(payload["leaf_execution_failures"]) == 3
        assert payload["leaf_failed"] == 3
        first = payload["leaf_execution_failures"][0]
        assert first["category"] == "GRAM_CATEGORIES"
        assert first["exception_type"] == "RuntimeError"
        assert first["source_guid"] == "src-0"
        assert "write refused" in first["message"]

    def test_every_failure_is_emitted_not_a_sample(self):
        payload = json.loads(_report(planned=500, failed=41).to_snapshot_json())

        assert len(payload["leaf_execution_failures"]) == 41
        assert payload["leaf_failed"] == 41

    def test_a_clean_run_omits_the_key_entirely(self):
        """Keeps the byte-identical-snapshot promise: a report with no 038 data
        and no swallowed write emits neither the failure list nor the
        disposition block."""
        payload = json.loads(_report(planned=12, failed=0).to_snapshot_json())

        assert "leaf_execution_failures" not in payload
        assert "leaf_failed" not in payload
        assert "disposition" not in payload

    def test_the_measured_zero_has_a_home_wherever_the_panel_appears(self):
        """The omit-when-empty trap `matched_to_source.by_natural_key` already
        records: a report that emits the disposition block states
        `add_write_failed: 0` positively, so "no writes failed" and "this build
        does not measure write failures" are different artifacts."""
        payload = json.loads(
            _report(planned=12, failed=0,
                    overwrites=[_substitution()]).to_snapshot_json())

        assert "leaf_execution_failures" not in payload
        assert payload["disposition"]["add_write_failed"] == 0
        assert payload["disposition"]["add_created_written"] == 12

    def test_a_swallowed_write_alone_earns_the_disposition_block(self):
        """A run whose ONLY anomaly is a failed write is exactly the run that
        needs `add_created_written`, so the failure records are themselves
        enough to emit the block."""
        payload = json.loads(_report(planned=329, failed=3).to_snapshot_json())

        assert payload["disposition"]["add_created"] == 329
        assert payload["disposition"]["add_created_written"] == 326

    def test_the_artifact_states_that_added_is_the_plans_number(self):
        """The defect was not only a missing list -- it was that nothing said
        `add_created` cannot be read as a write count."""
        payload = json.loads(_report(planned=329, failed=3).to_snapshot_json())

        assert "did NOT happen" in payload["leaf_failed_note"]
        assert "add_created_written" in payload["leaf_failed_note"]
        assert "PLAN" in payload["disposition"]["counted_from"]["add_created"]
        assert payload["disposition"]["counted_from"]["add_write_failed"] == (
            "LeafExecutionFailure (leaf_execution_failures)"
        )


class TestTheConsoleSaysSo:

    def _panel(self, report):
        return "\n".join(report_mod.render_text_summary(report))

    def test_the_panel_names_planned_and_written(self):
        text = self._panel(_report(planned=329, failed=3))

        assert "WRITE FAILED" in text
        assert "326 actually written" in text

    def test_the_panel_withholds_an_unsupported_remainder(self):
        text = self._panel(_report(planned=2, failed=5))

        assert "WITHHELD" in text
        assert "not" in text and "guessed" in text

    def test_a_clean_run_adds_no_row(self):
        text = self._panel(_report(planned=12, failed=0))

        assert "WRITE FAILED" not in text

    def test_the_panel_is_ascii_only(self):
        """The Windows console rule."""
        text = self._panel(_report(planned=329, failed=3))

        assert text == text.encode("ascii", "replace").decode("ascii")
